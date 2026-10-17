"""Refresh tokens and the pure rotation rules.

The rules are a pure function of the stored session state so they can be tested without a database. The
persistence layer (phase 2) loads the row, calls ``decide_refresh``, and applies the outcome.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


@dataclass(frozen=True)
class RefreshToken:
    raw: str
    hash: str


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_refresh_token() -> RefreshToken:
    raw = secrets.token_urlsafe(32)
    return RefreshToken(raw=raw, hash=hash_refresh_token(raw))


def hashes_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


@dataclass(frozen=True)
class SessionLifetime:
    expires_at: datetime
    absolute_expires_at: datetime


@dataclass(frozen=True)
class LifetimePolicy:
    refresh_ttl_seconds: int = 7 * 24 * 3600
    admin_refresh_ttl_seconds: int = 24 * 3600
    absolute_ttl_seconds: int = 30 * 24 * 3600
    admin_absolute_ttl_seconds: int = 7 * 24 * 3600
    grace_seconds: int = 10

    def _is_admin(self, role: str) -> bool:
        return role == "admin"

    def new_session(self, role: str, now: datetime) -> SessionLifetime:
        absolute = now + timedelta(seconds=self.admin_absolute_ttl_seconds if self._is_admin(role) else self.absolute_ttl_seconds)
        ttl = self.admin_refresh_ttl_seconds if self._is_admin(role) else self.refresh_ttl_seconds
        return SessionLifetime(expires_at=min(now + timedelta(seconds=ttl), absolute), absolute_expires_at=absolute)

    def rotate(self, role: str, now: datetime, absolute_expires_at: datetime) -> SessionLifetime:
        """Sliding refresh expiry, capped by the session's absolute limit."""
        ttl = self.admin_refresh_ttl_seconds if self._is_admin(role) else self.refresh_ttl_seconds
        return SessionLifetime(expires_at=min(now + timedelta(seconds=ttl), absolute_expires_at), absolute_expires_at=absolute_expires_at)


class RefreshOutcome(str, Enum):
    ROTATE = "rotate"                  # valid and current: issue a new pair
    REPLAY_IN_GRACE = "replay_in_grace"  # just rotated: concurrent request, hand back the successor
    REUSE_DETECTED = "reuse_detected"  # rotated token replayed late: revoke the whole family
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True)
class StoredSession:
    expires_at: datetime
    absolute_expires_at: datetime
    rotated_at: datetime | None
    revoked_at: datetime | None


def decide_refresh(session: StoredSession, now: datetime, grace_seconds: int) -> RefreshOutcome:
    if session.revoked_at is not None:
        return RefreshOutcome.REVOKED
    if now >= session.absolute_expires_at or now >= session.expires_at:
        return RefreshOutcome.EXPIRED
    if session.rotated_at is not None:
        if now - session.rotated_at <= timedelta(seconds=grace_seconds):
            return RefreshOutcome.REPLAY_IN_GRACE
        return RefreshOutcome.REUSE_DETECTED
    return RefreshOutcome.ROTATE


def needs_refresh(access_exp: int, now_ts: int, threshold_seconds: int = 180) -> bool:
    """True when an access token is expired or within ``threshold_seconds`` of expiring."""
    return access_exp - now_ts <= threshold_seconds
