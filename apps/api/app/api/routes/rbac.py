"""Administration of the role-permission matrix and service accounts."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.guards import require_user
from app.api.permissions import P
from app.api.routes.admin import _audit
from app.db.session import get_db
from app.models.auth_entities import ServiceAccount
from app.models.entities import User
from app.services.rbac_service import (
    RbacError, create_service_account, describe_matrix, revoke_service_account, set_role_permissions,
)

router = APIRouter(prefix="/api/admin", tags=["access control"])


class RolePermissionsRequest(BaseModel):
    permissions: list[str] = Field(max_length=200)


class ServiceAccountCreate(BaseModel):
    name: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    permissions: list[str] = Field(default_factory=lambda: ["ops:read"], max_length=20)


def _http(error: RbacError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message})


def _view(account: ServiceAccount) -> dict:
    return {"id": account.id, "name": account.name, "key_id": account.key_id, "permissions": account.permissions or [],
            "created_at": account.created_at, "last_used_at": account.last_used_at, "revoked_at": account.revoked_at}


@router.get("/rbac")
def get_matrix(actor: User = Depends(require_user(P.ADMIN_RBAC)), db: Session = Depends(get_db)):
    return describe_matrix(db)


@router.put("/rbac/roles/{role}/permissions")
def put_role_permissions(role: str, payload: RolePermissionsRequest, actor: User = Depends(require_user(P.ADMIN_RBAC)), db: Session = Depends(get_db)):
    try:
        added, removed = set_role_permissions(db, role, payload.permissions)
    except RbacError as error:
        raise _http(error) from error
    _audit(db, actor, "rbac.role_permissions_updated", "role", role, {"added": sorted(added), "removed": sorted(removed)})
    db.commit()
    return {"role": role, "added": sorted(added), "removed": sorted(removed)}


@router.get("/service-accounts")
def list_service_accounts(actor: User = Depends(require_user(P.ADMIN_SERVICE_ACCOUNTS)), db: Session = Depends(get_db)):
    return [_view(a) for a in db.scalars(select(ServiceAccount).order_by(ServiceAccount.created_at))]


@router.post("/service-accounts", status_code=201)
def post_service_account(payload: ServiceAccountCreate, actor: User = Depends(require_user(P.ADMIN_SERVICE_ACCOUNTS)), db: Session = Depends(get_db)):
    try:
        account, full_key = create_service_account(db, payload.name, payload.permissions, actor.id)
    except RbacError as error:
        raise _http(error) from error
    _audit(db, actor, "service_account.created", "service_account", account.id, {"name": account.name, "permissions": account.permissions})
    db.commit()
    return {**_view(account), "key": full_key, "notice": "Store this key now; it cannot be shown again."}


@router.delete("/service-accounts/{account_id}")
def delete_service_account(account_id: str, actor: User = Depends(require_user(P.ADMIN_SERVICE_ACCOUNTS)), db: Session = Depends(get_db)):
    try:
        account = revoke_service_account(db, account_id)
    except RbacError as error:
        raise _http(error) from error
    _audit(db, actor, "service_account.revoked", "service_account", account.id, {"name": account.name})
    db.commit()
    return _view(account)
