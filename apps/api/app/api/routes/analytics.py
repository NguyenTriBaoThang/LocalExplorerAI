"""Page-view collection from the traveler web and the traffic reports in the portal."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.authn import authenticate
from app.api.dependencies import get_db
from app.api.guards import public, require_user
from app.api.permissions import P
from app.models.entities import PageView, Provider, User
from app.schemas.portal import PageViewPayload
from app.services import analytics_service as analytics

router = APIRouter(prefix="/api", tags=["analytics"])


@router.post("/analytics/pageview", status_code=204, dependencies=[Depends(public("anonymous page-view beacon; stores no IP and only a hashed browser id"))])
def record_page_view(payload: PageViewPayload, request: Request, response: Response, db: Session = Depends(get_db)):
    agent = request.headers.get("user-agent")
    if analytics.is_bot(agent) or request.headers.get("dnt") == "1" or request.headers.get("sec-gpc") == "1":
        return Response(status_code=204)  # respect Do-Not-Track / Global Privacy Control and skip crawlers
    try:
        user = authenticate(request, response, db, required=False)
    except Exception:  # an expired cookie must never break the beacon
        user = None
    db.add(PageView(
        id=str(uuid4()), occurred_at=datetime.now(timezone.utc),
        visitor_hash=analytics.pseudonymize(payload.visitor_id), session_hash=analytics.pseudonymize(payload.session_id),
        user_id=user.id if user else None, path=payload.path, entity_type=payload.entity_type,
        entity_id=payload.entity_id if payload.entity_type else None,
        referrer_host=analytics.referrer_host(payload.referrer, request.headers.get("host")), device=analytics.device_class(agent),
    ))
    db.commit()
    return Response(status_code=204)


@router.get("/admin/analytics")
def admin_analytics(actor: User = Depends(require_user(P.ADMIN_ANALYTICS)), db: Session = Depends(get_db),
                    days: int = Query(default=30, ge=1, le=365)):
    return analytics.admin_report(db, days)


@router.get("/provider/me/analytics")
def provider_analytics(user: User = Depends(require_user(P.PROVIDER_ANALYTICS)), db: Session = Depends(get_db),
                       days: int = Query(default=30, ge=1, le=365)):
    provider = db.get(Provider, user.provider_id) if user.provider_id else None
    if provider is None:
        raise HTTPException(status_code=403, detail={"code": "PROVIDER_PROFILE_REQUIRED", "message": "This account has no provider profile."})
    return analytics.provider_report(db, provider.id, days)
