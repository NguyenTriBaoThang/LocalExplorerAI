"""Background worker for transactional email and web-push notifications (PostgreSQL only)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models.entities import NotificationDelivery, OpsJobRun
from app.services.notifications import REDACTED_BODY, SENSITIVE_KEY_PREFIX, deliver_email, deliver_webpush
from app.services.rate_limit import _redis

logger = logging.getLogger("local_explorer.worker")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run_once() -> bool:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("The notification worker requires PostgreSQL row locking (FOR UPDATE SKIP LOCKED).")
    now = utcnow()
    with SessionLocal() as db:
        # Recover rows left in sending by an abruptly terminated worker.
        db.query(NotificationDelivery).filter(
            NotificationDelivery.status == "sending",
            NotificationDelivery.locked_at < now - timedelta(minutes=5),
        ).update({NotificationDelivery.status: "retry", NotificationDelivery.available_at: now, NotificationDelivery.locked_at: None}, synchronize_session=False)
        row = db.scalar(select(NotificationDelivery).where(
            NotificationDelivery.status.in_(("queued", "retry")),
            NotificationDelivery.available_at <= now,
        ).order_by(NotificationDelivery.created_at).with_for_update(skip_locked=True).limit(1))
        if row is None:
            db.commit()
            return False
        row.status = "sending"
        row.locked_at = now
        row.attempts += 1
        db.commit()
        delivery_id = row.id
        channel, recipient, subject, body, attempt = row.channel, row.recipient_email, row.subject, row.body_text, row.attempts
        recipient_user_id = row.recipient_user_id

    error_type = None
    try:
        if channel == "webpush":
            deliver_webpush(recipient_user_id, body)
        elif channel == "email":
            deliver_email(recipient, subject, body)
        else:
            raise RuntimeError("Unsupported notification channel")
    except Exception as exc:  # Delivery outages are expected to retry; never log recipient/body.
        error_type = type(exc).__name__

    finished = utcnow()
    with SessionLocal() as db:
        row = db.get(NotificationDelivery, delivery_id)
        run = OpsJobRun(id=str(uuid4()), job_name="notification_outbox", status="completed" if error_type is None else "failed",
                        started_at=now, finished_at=finished, processed_count=1,
                        error_summary=error_type)
        db.add(run)
        if row is not None:
            row.locked_at = None
            row.updated_at = finished
            if error_type is None:
                row.status = "sent"
                row.sent_at = finished
                row.last_error = None
            else:
                row.last_error = error_type
                if attempt >= settings.notification_max_attempts:
                    row.status = "failed"
                else:
                    row.status = "retry"
                    row.available_at = finished + timedelta(seconds=min(3600, 15 * (2 ** (attempt - 1))))
            if row.status in ("sent", "failed") and row.idempotency_key.startswith(SENSITIVE_KEY_PREFIX):
                row.body_text = REDACTED_BODY  # do not keep live reset/verification links in the outbox
        db.commit()
    if error_type:
        logger.warning("notification delivery failed id=%s attempt=%s channel=%s error=%s", delivery_id, attempt, channel, error_type)
    return True


def main() -> None:
    logger.info("notification worker started")
    while True:
        try:
            try:
                _redis().set("local-explorer:worker:notification_outbox", utcnow().isoformat(), ex=30)
            except Exception:
                pass  # Worker remains useful during Redis outage; Redis is for rate limits/heartbeat.
            did_work = run_once()
            if not did_work:
                time.sleep(max(1.0, settings.notification_poll_seconds))
        except Exception:
            logger.exception("notification worker iteration failed")
            time.sleep(max(2.0, settings.notification_poll_seconds))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    main()
