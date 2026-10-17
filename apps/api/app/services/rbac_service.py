"""Database-backed RBAC: catalogue sync, the cached role matrix, guarded edits, and service accounts."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.permissions import ADMIN_REQUIRED, DEFAULT_GRANTS, SERVICE_GRANTABLE, SYSTEM_ROLES, registry
from app.auth import AuthRequired, Principal, PrincipalKind, generate_service_key, parse_service_key, verify_secret
from app.core.config import settings
from app.models.auth_entities import Permission, Role, RolePermission, ServiceAccount
from app.services.auth_runtime import bump_matrix_version, matrix_version

_TTL_SECONDS = 60.0
_LAST_USED_RESOLUTION = timedelta(minutes=1)


class RbacError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422):
        self.code, self.message, self.status_code = code, message, status_code
        super().__init__(message)


# --- seeding / sync --------------------------------------------------------------------------------------------
def sync_catalog(db: Session) -> list[str]:
    """Make the database match the code catalogue. Idempotent.

    Missing roles/permissions are inserted. Default grants are inserted **only for permissions that are new**, so a
    grant an administrator removed on purpose is never silently restored. Returns the names of new permissions.
    """
    for name, description in SYSTEM_ROLES.items():
        if db.get(Role, name) is None:
            db.add(Role(name=name, description=description, is_system=True))
    existing = set(db.scalars(select(Permission.name)))
    created = [name for name in sorted(registry.names()) if name not in existing]
    for name in created:
        db.add(Permission(name=name, description=registry.description(name)))
    db.flush()
    for role, permissions in DEFAULT_GRANTS.items():
        for permission in permissions:
            if permission in created:
                db.add(RolePermission(role_name=role, permission_name=permission))
    db.commit()
    invalidate_matrix()
    return created


# --- cached matrix ---------------------------------------------------------------------------------------------
class _MatrixCache:
    def __init__(self) -> None:
        self.data: dict[str, frozenset[str]] = {}
        self.loaded_at: float | None = None
        self.version: int | None = None

    def clear(self) -> None:
        self.loaded_at = None

    def get(self, db: Session) -> dict[str, frozenset[str]]:
        ttl = 0.0 if settings.app_env.lower() == "test" else _TTL_SECONDS
        version = matrix_version()
        stale = self.loaded_at is None or time.monotonic() - self.loaded_at >= ttl or (version is not None and version != self.version)
        if stale:
            grants: dict[str, set[str]] = {}
            for row in db.execute(select(RolePermission.role_name, RolePermission.permission_name)):
                grants.setdefault(row[0], set()).add(row[1])
            self.data = {role: frozenset(perms) for role, perms in grants.items()}
            self.loaded_at, self.version = time.monotonic(), version
        return self.data


_cache = _MatrixCache()


class DbRoleMatrix:
    """Role matrix read from the database (cached per process; refreshed on TTL or when another worker edits it)."""

    def __init__(self, db: Session):
        self._db = db

    def permissions_for(self, role: str) -> frozenset[str]:
        return _cache.get(self._db).get(role, frozenset())


def invalidate_matrix() -> None:
    _cache.clear()
    bump_matrix_version()


def describe_matrix(db: Session) -> dict:
    grants = _cache.get(db)
    roles = [{"name": r.name, "description": r.description, "is_system": r.is_system, "permissions": sorted(grants.get(r.name, ()))}
             for r in db.scalars(select(Role).order_by(Role.name))]
    permissions = [{"name": p.name, "description": p.description} for p in db.scalars(select(Permission).order_by(Permission.name))]
    return {"roles": roles, "permissions": permissions}


def set_role_permissions(db: Session, role_name: str, permissions: list[str]) -> tuple[set[str], set[str]]:
    """Replace a role's permissions. Returns (added, removed). The caller audits and commits through this function's commit."""
    role = db.get(Role, role_name)
    if role is None:
        raise RbacError("ROLE_NOT_FOUND", "Role not found.", 404)
    wanted = set(permissions)
    unknown = wanted - registry.names()
    if unknown:
        raise RbacError("UNKNOWN_PERMISSION", f"Unknown permissions: {', '.join(sorted(unknown))}.")
    if role_name == "admin" and not ADMIN_REQUIRED <= wanted:
        raise RbacError("ADMIN_LOCKOUT", f"The admin role must keep: {', '.join(sorted(ADMIN_REQUIRED))}.", 409)
    current = set(db.scalars(select(RolePermission.permission_name).where(RolePermission.role_name == role_name)))
    added, removed = wanted - current, current - wanted
    if removed:
        db.execute(delete(RolePermission).where(RolePermission.role_name == role_name, RolePermission.permission_name.in_(removed)))
    for permission in added:
        db.add(RolePermission(role_name=role_name, permission_name=permission))
    db.commit()
    invalidate_matrix()
    return added, removed


# --- service accounts ------------------------------------------------------------------------------------------
def create_service_account(db: Session, name: str, permissions: list[str], created_by: str | None) -> tuple[ServiceAccount, str]:
    bad = set(permissions) - SERVICE_GRANTABLE
    if bad:
        raise RbacError("PERMISSION_NOT_GRANTABLE", f"Service accounts may only hold: {', '.join(sorted(SERVICE_GRANTABLE))}.")
    if db.scalar(select(ServiceAccount.id).where(ServiceAccount.name == name)):
        raise RbacError("SERVICE_ACCOUNT_EXISTS", "A service account with this name already exists.", 409)
    generated = generate_service_key()
    account = ServiceAccount(name=name, key_id=generated.key_id, key_hash=generated.secret_hash,
                             permissions=sorted(set(permissions)), created_by=created_by)
    db.add(account)
    db.commit()
    return account, generated.full_key


def revoke_service_account(db: Session, account_id: str) -> ServiceAccount:
    account = db.get(ServiceAccount, account_id)
    if account is None:
        raise RbacError("SERVICE_ACCOUNT_NOT_FOUND", "Service account not found.", 404)
    if account.revoked_at is None:
        account.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return account


def authenticate_service_key(db: Session, raw_key: str) -> Principal:
    """Resolve ``lek_<id>_<secret>`` to a service principal, or raise ``AuthRequired``."""
    parsed = parse_service_key(raw_key)
    account = db.scalar(select(ServiceAccount).where(ServiceAccount.key_id == parsed[0])) if parsed else None
    if account is None or account.revoked_at is not None or not verify_secret(parsed[1], account.key_hash):
        raise AuthRequired("The API key is invalid or revoked.")
    now = datetime.now(timezone.utc)
    last = account.last_used_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if last is None or now - last > _LAST_USED_RESOLUTION:   # avoid a database write on every call
        account.last_used_at = now
        db.commit()
    return Principal(id=account.name, kind=PrincipalKind.SERVICE, role="service",
                     explicit_permissions=frozenset(set(account.permissions or []) & SERVICE_GRANTABLE))
