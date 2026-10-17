"""Route guards. Every route must declare exactly how it is protected:

    dependencies=[Depends(public("reason"))]                      anyone, with a stated reason
    user: User = Depends(require_user(P.SOMETHING))               a signed-in person holding the permission
    principal = Depends(require(P.OPS_READ))                      a person *or* a service account holding it
    ...(optional=True)                                            anonymous allowed; if signed in, must hold it

A test walks every route and fails if one has no declaration.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.authn import authenticate_principal
from app.api.permissions import MFA_ENROLMENT_PERMISSIONS, registry
from app.core.config import settings
from app.auth import Authorizer, Forbidden, MfaRequired, Principal, PrincipalKind
from app.db.session import get_db
from app.models.entities import User
from app.services.rbac_service import DbRoleMatrix


@dataclass(frozen=True)
class AuthPolicy:
    kind: str                      # "public" | "require"
    permission: str | None = None
    reason: str | None = None
    optional: bool = False


def public(reason: str):
    if not reason.strip():
        raise ValueError("A public route must state why it is public.")

    def dependency() -> None:
        return None

    dependency.__auth_policy__ = AuthPolicy(kind="public", reason=reason)  # type: ignore[attr-defined]
    return dependency


def _check(permission: str) -> None:
    if permission not in registry:
        raise ValueError(f"Unknown permission {permission!r}; declare it in app/api/permissions.py.")


def _enforce_mfa(principal: Principal, permission: str) -> None:
    """When ADMIN_MFA_REQUIRED is on, administrators must have passed a second factor; until then they may only enrol one."""
    if (settings.admin_mfa_required and principal.kind is PrincipalKind.USER and principal.role == "admin" and not principal.has_mfa
            and permission not in MFA_ENROLMENT_PERMISSIONS):
        raise MfaRequired()


def require(permission: str, *, optional: bool = False):
    """Principal (person or service account) holding ``permission``; ``None`` for anonymous when ``optional``."""
    _check(permission)

    def dependency(request: Request, response: Response, db: Session = Depends(get_db)) -> Principal | None:
        principal, _ = authenticate_principal(request, response, db, required=not optional)
        if principal is None:
            return None
        _enforce_mfa(principal, permission)
        if not Authorizer(DbRoleMatrix(db)).can(principal, permission):
            raise Forbidden()
        return principal

    dependency.__auth_policy__ = AuthPolicy(kind="require", permission=permission, optional=optional)  # type: ignore[attr-defined]
    return dependency


def require_user(permission: str, *, optional: bool = False):
    """Signed-in *person* (never an API key) holding ``permission``; returns the ORM user."""
    _check(permission)

    def dependency(request: Request, response: Response, db: Session = Depends(get_db)) -> User | None:
        principal, user = authenticate_principal(request, response, db, required=not optional)
        if principal is None:
            return None
        _enforce_mfa(principal, permission)
        if user is None or not Authorizer(DbRoleMatrix(db)).can(principal, permission):
            raise Forbidden()
        return user

    dependency.__auth_policy__ = AuthPolicy(kind="require", permission=permission, optional=optional)  # type: ignore[attr-defined]
    return dependency
