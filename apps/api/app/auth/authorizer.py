"""Authorization decisions: permission check plus optional per-resource policy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .errors import Forbidden, PolicyMissing
from .permissions import RoleMatrix
from .principal import Principal

Policy = Callable[[Principal, Any], bool]


class PolicyRegistry:
    def __init__(self) -> None:
        self._policies: dict[str, Policy] = {}

    def register(self, permission: str, policy: Policy) -> None:
        if permission in self._policies:
            raise ValueError(f"A policy for {permission!r} is already registered.")
        self._policies[permission] = policy

    def get(self, permission: str) -> Policy | None:
        return self._policies.get(permission)


class Authorizer:
    def __init__(self, matrix: RoleMatrix, policies: PolicyRegistry | None = None):
        self._matrix = matrix
        self._policies = policies or PolicyRegistry()

    def permissions_of(self, principal: Principal) -> frozenset[str]:
        if principal.explicit_permissions is not None:
            return principal.explicit_permissions
        return self._matrix.permissions_for(principal.role)

    def has_permission(self, principal: Principal, permission: str) -> bool:
        return permission in self.permissions_of(principal)

    def can(self, principal: Principal, permission: str, resource: Any = None) -> bool:
        if not self.has_permission(principal, permission):
            return False
        if resource is None:
            return True
        policy = self._policies.get(permission)
        if policy is None:
            raise PolicyMissing()
        return bool(policy(principal, resource))

    def authorize(self, principal: Principal, permission: str, resource: Any = None) -> None:
        if not self.can(principal, permission, resource):
            raise Forbidden()
