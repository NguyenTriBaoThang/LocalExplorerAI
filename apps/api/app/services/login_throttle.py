"""Wrong-password throttling, counted from ``auth_events`` so it holds across workers and does not need Redis.

Failures are keyed by a hash of the e-mail *as typed*, whether or not an account exists, so a throttled unknown address
looks exactly like a throttled real one (the throttle cannot be used to find out who has an account).
Three independent limits apply inside one sliding window: one e-mail from one address, one e-mail from anywhere, and
one address against any e-mail.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import AuthError
from app.core.config import settings
from app.models.auth_entities import AuthEvent


class LoginThrottled(AuthError):
    status_code = 429
    code = "LOGIN_THROTTLED"
    default_message = "Too many failed sign-in attempts. Try again in a few minutes."

    @property
    def headers(self) -> dict[str, str]:
        return {"Retry-After": str(settings.auth_login_window_seconds)}


def email_digest(email: str) -> str:
    return hashlib.sha256((email or "").strip().lower().encode("utf-8")).hexdigest()


def failure_detail(email: str, via: str = "password") -> dict:
    return {"email_hash": email_digest(email), "via": via}


def _failures(db: Session, since: datetime, *conditions) -> int:
    return db.scalar(select(func.count(AuthEvent.id)).where(
        AuthEvent.event_type == "login", AuthEvent.outcome == "failure", AuthEvent.created_at > since, *conditions)) or 0


def check(db: Session, email: str, ip: str | None) -> None:
    since = datetime.now(timezone.utc) - timedelta(seconds=settings.auth_login_window_seconds)
    digest = email_digest(email)
    same_email = AuthEvent.detail["email_hash"].as_string() == digest
    if ip is not None:
        if _failures(db, since, same_email, AuthEvent.ip == ip) >= settings.auth_login_max_failures_per_account_ip:
            raise LoginThrottled()
        if _failures(db, since, AuthEvent.ip == ip) >= settings.auth_login_max_failures_per_ip:
            raise LoginThrottled()
    if _failures(db, since, same_email) >= settings.auth_login_max_failures_per_account:
        raise LoginThrottled()
