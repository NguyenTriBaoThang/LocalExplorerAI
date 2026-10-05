"""Permission catalogue and the role -> permission matrix.

Permission *names* are declared in code (so routes can reference them and a test can verify coverage); which
role holds which permission lives in the database and is read through a cached ``RoleMatrix``.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable
from typing import Protocol

_NAME = re.compile(r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$")


class PermissionRegistry:
    def __init__(self) -> None:
        self._items: dict[str, str] = {}

    def define(self, name: str, description: str = "") -> str:
        if not _NAME.match(name):
            raise ValueError(f"Invalid permission name {name!r}; use 'resource:action'.")
        if name in self._items:
            raise ValueError(f"Permission {name!r} is already defined.")
        self._items[name] = description
        return name

    def names(self) -> frozenset[str]:
        return frozenset(self._items)

    def description(self, name: str) -> str:
        return self._items[name]

    def __contains__(self, name: object) -> bool:
        return name in self._items


class RoleMatrix(Protocol):
    def permissions_for(self, role: str) -> frozenset[str]: ...


class StaticRoleMatrix:
    def __init__(self, grants: dict[str, Iterable[str]]):
        self._grants = {role: frozenset(perms) for role, perms in grants.items()}

    def permissions_for(self, role: str) -> frozenset[str]:
        return self._grants.get(role, frozenset())


class CachedRoleMatrix:
    """Loads the matrix through ``loader`` and refreshes when ``version()`` changes or the TTL passes.

    ``version`` is typically a Redis counter bumped whenever an admin edits role permissions, so every worker
    notices within a request or two instead of waiting for the TTL.
    """

    def __init__(self, loader: Callable[[], dict[str, frozenset[str]]], version: Callable[[], int] | None = None,
                 ttl_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self._loader, self._version, self._ttl, self._clock = loader, version, ttl_seconds, clock
        self._data: dict[str, frozenset[str]] = {}
        self._loaded_at: float | None = None
        self._seen_version: int | None = None

    def _stale(self) -> bool:
        if self._loaded_at is None or self._clock() - self._loaded_at >= self._ttl:
            return True
        if self._version is not None:
            try:
                return self._version() != self._seen_version
            except Exception:
                return False  # version source down: keep serving the cached matrix until the TTL
        return False

    def permissions_for(self, role: str) -> frozenset[str]:
        if self._stale():
            self.refresh()
        return self._data.get(role, frozenset())

    def refresh(self) -> None:
        self._data = {role: frozenset(perms) for role, perms in self._loader().items()}
        self._loaded_at = self._clock()
        if self._version is not None:
            try:
                self._seen_version = self._version()
            except Exception:
                self._seen_version = None
