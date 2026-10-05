"""Server-side sessions: issue, rotate (with reuse detection), revoke."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import (
    AccountDisabled, RefreshOutcome, StoredSession, TokenInvalid, decide_refresh, hash_refresh_token, new_refresh_token,
)
from app.models.auth_entities import AuthEvent, AuthSession
from app.models.entities import User
from app.services.auth_runtime import auth_config, invalidate_user_state, token_service


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    access_expires_at: int
    session_id: str
    user_id: str
    refresh_token: str | None = None            # None when a concurrent refresh was answered with an access token only
    refresh_expires_at: datetime | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)  # SQLite returns naive datetimes; everything is stored as UTC
    return value


def record_event(db: Session, event_type: str, *, outcome: str = "success", user_id: str | None = None, session_id: str | None = None,
                 ip: str | None = None, user_agent: str | None = None, detail: dict | None = None) -> None:
    db.add(AuthEvent(event_type=event_type, outcome=outcome, user_id=user_id, session_id=session_id, ip=ip,
                     user_agent=(user_agent or "")[:255] or None, detail=detail or {}))


def _access_for(user: User, session: AuthSession) -> tuple[str, int]:
    token, claims = token_service().issue_access(
        user_id=user.id, session_id=session.id, role=user.role, provider_id=user.provider_id,
        token_version=user.token_version, amr=tuple(session.amr or ["pwd"]),
    )
    return token, claims.exp


def start_session(db: Session, user: User, *, ip: str | None = None, user_agent: str | None = None, amr: tuple[str, ...] = ("pwd",)) -> IssuedTokens:
    now = _now()
    life = auth_config().lifetime.new_session(user.role, now)
    refresh = new_refresh_token()
    session = AuthSession(
        id=str(uuid4()), user_id=user.id, family_id=str(uuid4()), refresh_hash=refresh.hash, issued_at=now,
        expires_at=life.expires_at, absolute_expires_at=life.absolute_expires_at, last_used_at=now,
        ip=ip, user_agent=(user_agent or "")[:255] or None, amr=list(amr),
    )
    db.add(session)
    record_event(db, "login", user_id=user.id, session_id=session.id, ip=ip, user_agent=user_agent, detail={"amr": list(amr)})
    db.commit()
    access, exp = _access_for(user, session)
    return IssuedTokens(access_token=access, access_expires_at=exp, session_id=session.id, user_id=user.id,
                        refresh_token=refresh.raw, refresh_expires_at=life.expires_at)


def revoke_family(db: Session, family_id: str, reason: str) -> None:
    db.execute(update(AuthSession).where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
               .values(revoked_at=_now(), revoked_reason=reason))


def rotate_session(db: Session, refresh_raw: str, *, ip: str | None = None, user_agent: str | None = None) -> IssuedTokens:
    """Exchange a refresh token for a new access/refresh pair. Raises ``TokenInvalid`` (or ``AccountDisabled``)."""
    row = db.scalar(select(AuthSession).where(AuthSession.refresh_hash == hash_refresh_token(refresh_raw)).with_for_update())
    if row is None:
        raise TokenInvalid()
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        revoke_family(db, row.family_id, "account_disabled")
        db.commit()
        raise AccountDisabled()
    config = auth_config()
    now = _now()
    outcome = decide_refresh(
        StoredSession(expires_at=_aware(row.expires_at), absolute_expires_at=_aware(row.absolute_expires_at),
                      rotated_at=_aware(row.rotated_at), revoked_at=_aware(row.revoked_at)),
        now, config.lifetime.grace_seconds,
    )
    if outcome is RefreshOutcome.REUSE_DETECTED:
        revoke_family(db, row.family_id, "reuse_detected")
        record_event(db, "refresh_reuse_detected", outcome="failure", user_id=user.id, session_id=row.id, ip=ip, user_agent=user_agent)
        db.commit()
        raise TokenInvalid()
    if outcome in (RefreshOutcome.REVOKED, RefreshOutcome.EXPIRED):
        raise TokenInvalid()
    if outcome is RefreshOutcome.REPLAY_IN_GRACE:
        successor = db.get(AuthSession, row.replaced_by) if row.replaced_by else None
        if successor is None or successor.revoked_at is not None:
            raise TokenInvalid()
        access, exp = _access_for(user, successor)
        return IssuedTokens(access_token=access, access_expires_at=exp, session_id=successor.id, user_id=user.id)

    life = config.lifetime.rotate(user.role, now, _aware(row.absolute_expires_at))
    refresh = new_refresh_token()
    successor = AuthSession(
        id=str(uuid4()), user_id=user.id, family_id=row.family_id, refresh_hash=refresh.hash, issued_at=now,
        expires_at=life.expires_at, absolute_expires_at=life.absolute_expires_at, last_used_at=now,
        ip=ip or row.ip, user_agent=(user_agent or row.user_agent or "")[:255] or None, amr=list(row.amr or ["pwd"]),
    )
    db.add(successor)
    row.rotated_at, row.replaced_by, row.last_used_at = now, successor.id, now
    db.commit()
    access, exp = _access_for(user, successor)
    return IssuedTokens(access_token=access, access_expires_at=exp, session_id=successor.id, user_id=user.id,
                        refresh_token=refresh.raw, refresh_expires_at=life.expires_at)


def revoke_by_refresh_token(db: Session, refresh_raw: str, reason: str = "logout") -> None:
    row = db.scalar(select(AuthSession).where(AuthSession.refresh_hash == hash_refresh_token(refresh_raw)))
    if row is not None:
        revoke_family(db, row.family_id, reason)
        record_event(db, "logout", user_id=row.user_id, session_id=row.id)
        db.commit()


def bump_token_version(db: Session, user: User, *, revoke_sessions: bool = True, reason: str = "token_version_bumped") -> None:
    """Invalidate every issued access token (and optionally every session) for ``user``. The caller commits,
    then calls ``invalidate_user_state(user.id)``."""
    user.token_version = (user.token_version or 0) + 1
    if revoke_sessions:
        db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
                   .values(revoked_at=_now(), revoked_reason=reason))


def revoke_all_sessions(db: Session, user: User, *, reason: str = "logout_all") -> None:
    bump_token_version(db, user, reason=reason)
    record_event(db, reason, user_id=user.id)
    db.commit()
    invalidate_user_state(user.id)
