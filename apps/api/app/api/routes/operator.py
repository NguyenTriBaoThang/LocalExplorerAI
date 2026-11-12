import re
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.guards import require_user
from app.api.permissions import P
from app.core.request_context import current_request_id
from app.models.entities import AuditLog, OperatorOrg, User

router = APIRouter(prefix="/api", tags=["operator portal"])


def _org(db: Session, user: User) -> OperatorOrg:
    """The caller's own organisation; every operator query must be scoped by the id this returns."""
    org = db.get(OperatorOrg, user.operator_org_id) if user.operator_org_id else None
    if org is None:
        raise HTTPException(status_code=404, detail={"code": "OPERATOR_ORG_NOT_FOUND", "message": "This account has no operator organisation."})
    return org


def org_payload(org: OperatorOrg) -> dict:
    return {"id": org.id, "name": org.name, "slug": org.slug, "margin_floor_pct": org.margin_floor_pct,
            "default_markup_pct": org.default_markup_pct, "deposit_pct": org.deposit_pct,
            "quote_validity_days": org.quote_validity_days, "ota_commission_pct": org.ota_commission_pct,
            "manual_minutes_per_quote": org.manual_minutes_per_quote, "settings": org.settings or {}}


class OperatorOrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    margin_floor_pct: int | None = Field(default=None, ge=0, le=90)
    default_markup_pct: int | None = Field(default=None, ge=0, le=300)
    deposit_pct: int | None = Field(default=None, ge=0, le=100)
    quote_validity_days: int | None = Field(default=None, ge=1, le=90)
    ota_commission_pct: int | None = Field(default=None, ge=0, le=60)
    manual_minutes_per_quote: int | None = Field(default=None, ge=1, le=1440)
    settings: dict | None = None


class OperatorOrgCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)


def _audit(db: Session, actor: User, action: str, target_id: str, details: dict) -> None:
    if request_id := current_request_id.get():
        details = {**details, "request_id": request_id}
    db.add(AuditLog(id=str(uuid4()), actor_id=actor.id, action=action, target_type="operator_org", target_id=target_id,
                    details=details, created_at=datetime.now(timezone.utc)))


@router.get("/operator/me/org")
def get_my_org(user: User = Depends(require_user(P.OPERATOR_SETTINGS)), db: Session = Depends(get_db)):
    return org_payload(_org(db, user))


@router.patch("/operator/me/org")
def update_my_org(payload: OperatorOrgUpdate, user: User = Depends(require_user(P.OPERATOR_SETTINGS)), db: Session = Depends(get_db)):
    org = _org(db, user)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in changes.items():
        setattr(org, key, value)
    _audit(db, user, "operator_org.updated", org.id, {"fields": sorted(changes)})
    db.commit()
    return org_payload(org)


@router.post("/admin/operator-orgs", status_code=201)
def create_operator_org(payload: OperatorOrgCreate, actor: User = Depends(require_user(P.ADMIN_USERS)), db: Session = Depends(get_db)):
    slug_base = re.sub(r"[^a-z0-9]+", "-", payload.name.strip().lower()).strip("-")[:180] or "operator"
    org = OperatorOrg(id=str(uuid4()), name=payload.name.strip(), slug=f"{slug_base}-{uuid4().hex[:8]}", settings={})
    db.add(org)
    db.flush()
    _audit(db, actor, "operator_org.created", org.id, {})
    db.commit()
    return org_payload(org)
