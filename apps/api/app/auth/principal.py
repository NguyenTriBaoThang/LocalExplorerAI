"""The authenticated caller, independent of how it was authenticated."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PrincipalKind(str, Enum):
    USER = "user"
    SERVICE = "service"


@dataclass(frozen=True)
class Principal:
    id: str
    kind: PrincipalKind
    role: str
    provider_id: str | None = None
    session_id: str | None = None
    amr: tuple[str, ...] = ("pwd",)
    # Only set for service principals, whose permissions are explicit rather than derived from a role.
    explicit_permissions: frozenset[str] | None = field(default=None)

    @property
    def is_service(self) -> bool:
        return self.kind is PrincipalKind.SERVICE

    @property
    def has_mfa(self) -> bool:
        return "otp" in self.amr

    @property
    def audit_actor(self) -> str:
        return f"system:{self.id}" if self.is_service else self.id
