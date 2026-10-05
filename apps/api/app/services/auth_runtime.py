"""Wires the framework-independent ``app.auth`` toolkit to the application's settings, database and Redis."""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from sqlalchemy.orm import Session

from app.auth import (
    AuthConfig, InMemoryStateStore, LifetimePolicy, RedisStateStore, TokenService, TokenVersionChecker, UserState,
    parse_public_keys,
)
from app.core.config import settings
from app.models.entities import User

log = logging.getLogger(__name__)
_REDIS_RETRY_SECONDS = 10.0
_STATE_CACHE_SECONDS = 30


@lru_cache(maxsize=1)
def auth_config() -> AuthConfig:
    s = settings
    return AuthConfig(
        issuer=s.auth_issuer, audience=s.auth_audience, key_id=s.auth_jwt_key_id, private_key_b64=s.auth_jwt_private_key_b64,
        public_keys_b64=parse_public_keys(s.auth_jwt_public_keys_b64), access_ttl_seconds=s.auth_access_ttl_seconds,
        refresh_threshold_seconds=s.auth_refresh_threshold_seconds,
        lifetime=LifetimePolicy(
            refresh_ttl_seconds=s.auth_refresh_ttl_seconds, admin_refresh_ttl_seconds=s.auth_admin_refresh_ttl_seconds,
            absolute_ttl_seconds=s.auth_absolute_ttl_seconds, admin_absolute_ttl_seconds=s.auth_admin_absolute_ttl_seconds,
            grace_seconds=s.auth_refresh_grace_seconds,
        ),
    )


@lru_cache(maxsize=1)
def token_service() -> TokenService:
    return auth_config().build_token_service()


class _ResilientStore:
    """Redis-backed state cache that backs off for a few seconds after a failure instead of retrying every request."""

    def __init__(self, inner) -> None:
        self._inner, self._skip_until = inner, 0.0

    def _call(self, name: str, *args):
        if time.monotonic() < self._skip_until:
            return None
        try:
            return getattr(self._inner, name)(*args)
        except Exception:
            self._skip_until = time.monotonic() + _REDIS_RETRY_SECONDS
            log.warning("auth state cache unavailable; using the database for %.0fs", _REDIS_RETRY_SECONDS, exc_info=True)
            return None

    def get(self, user_id):
        return self._call("get", user_id)

    def set(self, user_id, state):
        self._call("set", user_id, state)

    def invalidate(self, user_id):
        self._call("invalidate", user_id)


@lru_cache(maxsize=1)
def state_store():
    if settings.app_env.lower() == "test":
        return InMemoryStateStore(ttl_seconds=0)  # no caching in tests: every check reads the database
    from app.services.rate_limit import _redis
    return _ResilientStore(RedisStateStore(_redis(), ttl_seconds=_STATE_CACHE_SECONDS))


def version_checker(db: Session) -> TokenVersionChecker:
    def load(user_id: str) -> UserState | None:
        user = db.get(User, user_id)
        return None if user is None else UserState(token_version=user.token_version, is_active=user.is_active)

    return TokenVersionChecker(state_store(), load)


def invalidate_user_state(user_id: str) -> None:
    """Call after changing a user's role, activation or token_version so the change applies immediately."""
    state_store().invalidate(user_id)


def reset_auth_runtime() -> None:
    """Drop cached config/services (tests that change settings)."""
    auth_config.cache_clear()
    token_service.cache_clear()
    state_store.cache_clear()
