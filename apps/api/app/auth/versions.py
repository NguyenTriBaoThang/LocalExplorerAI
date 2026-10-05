"""Immediate revocation: compare the token's ``ver`` with the user's current ``token_version``.

State is cached (Redis in production) for a few seconds; on a cache miss or when the cache is unreachable the
authoritative loader (the database) is used, so correctness never depends on Redis being up.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .errors import AccountDisabled, TokenRevoked
from .tokens import AccessClaims

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class UserState:
    token_version: int
    is_active: bool


class StateStore(Protocol):
    def get(self, user_id: str) -> UserState | None: ...
    def set(self, user_id: str, state: UserState) -> None: ...
    def invalidate(self, user_id: str) -> None: ...


class InMemoryStateStore:
    """Process-local store. ``ttl_seconds=0`` disables caching (every read falls through to the loader)."""

    def __init__(self, ttl_seconds: float | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        self._data: dict[str, tuple[float, UserState]] = {}
        self._ttl, self._clock = ttl_seconds, clock

    def get(self, user_id: str) -> UserState | None:
        entry = self._data.get(user_id)
        if entry is None:
            return None
        stored_at, state = entry
        if self._ttl is not None and self._clock() - stored_at >= self._ttl:
            self._data.pop(user_id, None)
            return None
        return state

    def set(self, user_id: str, state: UserState) -> None:
        self._data[user_id] = (self._clock(), state)

    def invalidate(self, user_id: str) -> None:
        self._data.pop(user_id, None)


class RedisStateStore:
    def __init__(self, client, *, prefix: str = "auth:ver:", ttl_seconds: int = 30):
        self._r, self._prefix, self._ttl = client, prefix, ttl_seconds

    def get(self, user_id: str) -> UserState | None:
        raw = self._r.get(self._prefix + user_id)
        if raw is None:
            return None
        version, active = str(raw).split(":", 1)
        return UserState(int(version), active == "1")

    def set(self, user_id: str, state: UserState) -> None:
        self._r.setex(self._prefix + user_id, self._ttl, f"{state.token_version}:{1 if state.is_active else 0}")

    def invalidate(self, user_id: str) -> None:
        self._r.delete(self._prefix + user_id)


class TokenVersionChecker:
    def __init__(self, store: StateStore, loader: Callable[[str], UserState | None]):
        self._store, self._loader = store, loader

    def _state(self, user_id: str) -> UserState | None:
        try:
            cached = self._store.get(user_id)
            if cached is not None:
                return cached
        except Exception:
            log.warning("auth state cache unavailable; reading the database", exc_info=True)
        state = self._loader(user_id)
        if state is not None:
            try:
                self._store.set(user_id, state)
            except Exception:
                log.warning("auth state cache write failed", exc_info=True)
        return state

    def check(self, claims: AccessClaims) -> UserState:
        state = self._state(claims.sub)
        if state is None or not state.is_active:
            raise AccountDisabled()
        if claims.ver != state.token_version:
            raise TokenRevoked()
        return state

    def invalidate(self, user_id: str) -> None:
        """Call after bumping ``token_version`` or changing ``is_active`` so the change applies immediately."""
        try:
            self._store.invalidate(user_id)
        except Exception:
            log.warning("auth state cache invalidation failed", exc_info=True)
