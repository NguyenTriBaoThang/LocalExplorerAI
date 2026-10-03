from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_admin
from app.core.config import settings
from app.models.entities import Event, NotificationDelivery, OpsJobRun
from app.services.rate_limit import _redis

router = APIRouter(prefix="/api/ops", tags=["operations"], dependencies=[Depends(require_admin)])


@router.get("/status")
def operations_status(db: Session = Depends(get_db)) -> dict:
    counts = dict(db.execute(select(NotificationDelivery.status, func.count()).group_by(NotificationDelivery.status)).all())
    try:
        heartbeat = _redis().get("local-explorer:worker:email_outbox")
        worker = {"status": "running", "last_seen": heartbeat} if heartbeat else {"status": "unknown", "last_seen": None}
    except Exception:
        worker = {"status": "unreachable", "last_seen": None}
    latest = db.scalar(select(OpsJobRun).where(OpsJobRun.job_name == "email_outbox").order_by(OpsJobRun.started_at.desc()).limit(1))
    active_events = db.scalar(select(func.count()).select_from(Event).where(Event.status == "active")) or 0
    return {
        "generated_at": datetime.now(timezone.utc),
        "notifications": {key: counts.get(key, 0) for key in ("queued", "sending", "retry", "sent", "failed")},
        "worker": worker,
        "last_job": ({"status": latest.status, "started_at": latest.started_at, "finished_at": latest.finished_at,
                      "processed_count": latest.processed_count, "error_summary": latest.error_summary} if latest else None),
        "active_events": active_events,
        "channels": {"email_enabled": settings.email_is_configured},
        "rate_limit_enabled": settings.rate_limit_enabled,
    }


@router.get("/jobs")
def operations_jobs(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(OpsJobRun).order_by(OpsJobRun.started_at.desc()).limit(limit)).all()
    return [{"id": row.id, "job_name": row.job_name, "status": row.status, "started_at": row.started_at,
             "finished_at": row.finished_at, "processed_count": row.processed_count,
             "error_summary": row.error_summary} for row in rows]


@router.get("/events")
def operations_events(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Event).order_by(Event.created_at.desc()).limit(limit)).all()
    return [{"id": row.id, "event_type": row.event_type, "target_type": row.target_type,
             "target_id": row.target_id, "status": row.status, "valid_until": row.valid_until,
             "metadata": row.event_metadata, "created_at": row.created_at} for row in rows]


@router.get("/notifications")
def operations_notifications(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(NotificationDelivery).order_by(NotificationDelivery.created_at.desc()).limit(limit)).all()
    # Deliberately omit recipient email and message body from monitoring responses.
    return [{"id": row.id, "idempotency_key": row.idempotency_key, "channel": row.channel,
             "booking_id": row.booking_id, "event_id": row.event_id, "subject": row.subject,
             "status": row.status, "attempts": row.attempts, "available_at": row.available_at,
             "sent_at": row.sent_at, "last_error": row.last_error, "created_at": row.created_at} for row in rows]
