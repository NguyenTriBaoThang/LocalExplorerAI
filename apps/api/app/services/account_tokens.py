"""Single-use emailed tokens (password reset, email verification) and itinerary claim tokens.

Only SHA-256 hashes are stored. Consumption is an atomic ``UPDATE ... WHERE used_at IS NULL`` so a token can be used
exactly once even when two requests race.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.auth_entities import AuthToken
from app.models.entities import ItineraryClaimToken, User

RESET_PASSWORD = "reset_password"
VERIFY_EMAIL = "verify_email"
MFA_LOGIN = "mfa_login"   # handed out after the password step, spent after the code step
TTL_SECONDS = {RESET_PASSWORD: 30 * 60, VERIFY_EMAIL: 24 * 3600, MFA_LOGIN: 5 * 60}
RESEND_INTERVAL_SECONDS = 60
CLAIM_TTL_SECONDS = 7 * 24 * 3600


class InvalidAccountToken(Exception):
    """Unknown, expired, already used, or issued for another purpose."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)  # SQLite returns naive datetimes; everything is stored as UTC
    return value


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issued_recently(db: Session, user: User, purpose: str, within_seconds: int = RESEND_INTERVAL_SECONDS) -> bool:
    latest = db.scalar(select(AuthToken.created_at).where(AuthToken.user_id == user.id, AuthToken.purpose == purpose)
                       .order_by(AuthToken.created_at.desc()).limit(1))
    return latest is not None and _now() - _aware(latest) < timedelta(seconds=within_seconds)


def issue(db: Session, user: User, purpose: str) -> tuple[AuthToken, str]:
    """Create a token and retire any earlier unused one for the same purpose. The caller commits."""
    now = _now()
    db.execute(update(AuthToken).where(AuthToken.user_id == user.id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None))
               .values(used_at=now))
    raw = secrets.token_urlsafe(32)
    row = AuthToken(user_id=user.id, purpose=purpose, token_hash=hash_token(raw), created_at=now,
                    expires_at=now + timedelta(seconds=TTL_SECONDS[purpose]))
    db.add(row)
    db.flush()
    return row, raw


def consume(db: Session, raw: str, purpose: str) -> User:
    """Mark the token used and return its user. Raises ``InvalidAccountToken``. The caller commits."""
    row = db.scalar(select(AuthToken).where(AuthToken.token_hash == hash_token(raw or "")))
    now = _now()
    if row is None or row.purpose != purpose or row.used_at is not None or _aware(row.expires_at) <= now:
        raise InvalidAccountToken()
    claimed = db.execute(update(AuthToken).where(AuthToken.id == row.id, AuthToken.used_at.is_(None)).values(used_at=now))
    user = db.get(User, row.user_id)
    if claimed.rowcount != 1 or user is None or not user.is_active:
        raise InvalidAccountToken()
    return user


def peek(db: Session, raw: str, purpose: str) -> tuple[AuthToken, User]:
    """Validate a token *without* spending it (the MFA ticket survives a wrong code, within the attempt limit)."""
    row = db.scalar(select(AuthToken).where(AuthToken.token_hash == hash_token(raw or "")))
    if row is None or row.purpose != purpose or row.used_at is not None or _aware(row.expires_at) <= _now():
        raise InvalidAccountToken()
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise InvalidAccountToken()
    return row, user


def spend(db: Session, row: AuthToken) -> None:
    """Atomically mark a peeked token used; raises if another request got there first."""
    claimed = db.execute(update(AuthToken).where(AuthToken.id == row.id, AuthToken.used_at.is_(None)).values(used_at=_now()))
    if claimed.rowcount != 1:
        raise InvalidAccountToken()


def issue_claim_token(db: Session, itinerary_id: str) -> str:
    raw = secrets.token_urlsafe(32)
    now = _now()
    db.add(ItineraryClaimToken(itinerary_id=itinerary_id, token_hash=hash_token(raw), created_at=now,
                               expires_at=now + timedelta(seconds=CLAIM_TTL_SECONDS)))
    return raw


def find_claim_token(db: Session, raw: str) -> ItineraryClaimToken:
    row = db.scalar(select(ItineraryClaimToken).where(ItineraryClaimToken.token_hash == hash_token(raw or "")).with_for_update())
    if row is None or row.used_at is not None or _aware(row.expires_at) <= _now():
        raise InvalidAccountToken()
    return row


def consume_claim_token(db: Session, row: ItineraryClaimToken, user: User) -> None:
    claimed = db.execute(update(ItineraryClaimToken).where(ItineraryClaimToken.id == row.id, ItineraryClaimToken.used_at.is_(None))
                         .values(used_at=_now(), used_by=user.id))
    if claimed.rowcount != 1:
        raise InvalidAccountToken()
