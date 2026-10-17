"""Admin management of places and landmarks (POIs) shown on the map, in itineraries and on the explore page."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.guards import require_user
from app.api.permissions import P
from app.models.entities import AuditLog, Evidence, Experience, PageView, POI, User
from app.schemas.portal import PlaceDraft, PlaceStatusRequest
from app.services.evidence_service import REQUIRED_FIELDS

router = APIRouter(prefix="/api/admin/places", tags=["admin places"])
# How long an administrator's publication vouches for the required POI fields before it must be re-confirmed.
PUBLICATION_VALIDITY = timedelta(days=365)
STATUSES = ("verified", "pending", "draft", "hidden", "rejected", "simulated")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(db: Session, actor: User, action: str, target_id: str, details: dict | None = None) -> None:
    db.add(AuditLog(id=str(uuid4()), actor_id=actor.id, action=action, target_type="poi", target_id=target_id, details=details or {}, created_at=_now()))


def _view(poi: POI, experience_count: int = 0, views_30d: int = 0) -> dict:
    return {
        "id": poi.id, "name": poi.name, "category": poi.category, "district": poi.district, "address": poi.address,
        "latitude": poi.latitude, "longitude": poi.longitude, "description": poi.description, "image_urls": poi.image_urls or [],
        "status": poi.verification_status, "is_landmark": poi.is_landmark, "opening_hours": poi.opening_hours,
        "ticket_info": poi.ticket_info, "tags": poi.tags or [], "source_url": poi.source_url, "google_place_id": poi.google_place_id,
        "submitted_by_provider_id": poi.submitted_by_provider_id, "data_revision": poi.data_revision,
        "experience_count": experience_count, "views_30d": views_30d, "updated_at": poi.updated_at,
    }


def _apply(poi: POI, payload: PlaceDraft) -> None:
    for key, value in payload.model_dump().items():
        setattr(poi, key, value.strip() if isinstance(value, str) else value)
    poi.geom = WKTElement(f"POINT({payload.longitude} {payload.latitude})", srid=4326)


def _vouch(db: Session, poi: POI, actor: User) -> None:
    """Record the administrator's publication as verified evidence for the current revision of the required fields."""
    now = _now()
    db.add(Evidence(
        id=str(uuid4()), source_uri=poi.source_url, source_type="official_website", source_label="Quản trị viên xuất bản",
        notes="Published from the admin portal against the cited source.", submitted_by=actor.id,
        target_type="poi", target_id=poi.id, target_revision=poi.data_revision, fields_covered=sorted(REQUIRED_FIELDS["poi"]),
        observed_at=now, valid_from=now, expires_at=now + PUBLICATION_VALIDITY,
        verification_status="verified", verified_by=actor.id, verified_at=now, reviewed_by=actor.id, reviewed_at=now,
    ))
    poi.verification_status = "verified"


@router.get("")
def list_places(response: Response, actor: User = Depends(require_user(P.ADMIN_PLACES)), db: Session = Depends(get_db),
                q: str | None = Query(default=None, max_length=120), status: str | None = Query(default=None, max_length=24),
                category: str | None = Query(default=None, max_length=40), district: str | None = Query(default=None, max_length=120),
                landmark: bool | None = None, limit: int = Query(default=200, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    query = select(POI)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(POI.name.ilike(term), POI.address.ilike(term)))
    if status:
        query = query.where(POI.verification_status == status)
    if category:
        query = query.where(POI.category == category)
    if district:
        query = query.where(POI.district == district)
    if landmark is not None:
        query = query.where(POI.is_landmark.is_(landmark))
    response.headers["X-Total-Count"] = str(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = db.scalars(query.order_by(POI.updated_at.desc()).limit(limit).offset(offset)).all()
    ids = [row.id for row in rows]
    experiences = dict(db.execute(select(Experience.poi_id, func.count(Experience.id)).where(Experience.poi_id.in_(ids)).group_by(Experience.poi_id)).all()) if ids else {}
    since = _now() - timedelta(days=30)
    views = dict(db.execute(select(PageView.entity_id, func.count(PageView.id)).where(
        PageView.entity_type == "poi", PageView.entity_id.in_(ids), PageView.occurred_at >= since).group_by(PageView.entity_id)).all()) if ids else {}
    return [_view(row, experiences.get(row.id, 0), views.get(row.id, 0)) for row in rows]


@router.get("/{place_id}")
def get_place(place_id: str, actor: User = Depends(require_user(P.ADMIN_PLACES)), db: Session = Depends(get_db)):
    poi = db.get(POI, place_id)
    if poi is None:
        raise HTTPException(status_code=404, detail={"code": "PLACE_NOT_FOUND", "message": "Place not found."})
    experiences = db.scalar(select(func.count(Experience.id)).where(Experience.poi_id == poi.id)) or 0
    views = db.scalar(select(func.count(PageView.id)).where(PageView.entity_type == "poi", PageView.entity_id == poi.id,
                                                            PageView.occurred_at >= _now() - timedelta(days=30))) or 0
    return _view(poi, experiences, views)


@router.post("", status_code=201)
def create_place(payload: PlaceDraft, publish: bool = False, actor: User = Depends(require_user(P.ADMIN_PLACES)), db: Session = Depends(get_db)):
    if publish and not payload.source_url:
        raise HTTPException(status_code=422, detail={"code": "SOURCE_REQUIRED", "message": "Publishing a place requires an HTTPS source URL."})
    poi = POI(id=str(uuid4()), verification_status="draft", data_revision=1)
    _apply(poi, payload)
    db.add(poi)
    db.flush()
    if publish:
        _vouch(db, poi, actor)
    _audit(db, actor, "place.created", poi.id, {"published": publish})
    db.commit()
    return _view(poi)


@router.patch("/{place_id}")
def update_place(place_id: str, payload: PlaceDraft, actor: User = Depends(require_user(P.ADMIN_PLACES)), db: Session = Depends(get_db)):
    poi = db.scalar(select(POI).where(POI.id == place_id).with_for_update())
    if poi is None:
        raise HTTPException(status_code=404, detail={"code": "PLACE_NOT_FOUND", "message": "Place not found."})
    was_published = poi.verification_status == "verified"
    required_before = {field: getattr(poi, field) for field in REQUIRED_FIELDS["poi"]}
    _apply(poi, payload)
    required_changed = any(getattr(poi, field) != value for field, value in required_before.items())
    if required_changed:
        poi.data_revision += 1  # previous evidence no longer describes this place
        if was_published:
            if poi.source_url:
                _vouch(db, poi, actor)  # the editing administrator re-confirms against the cited source
            else:
                poi.verification_status = "draft"
    _audit(db, actor, "place.updated", poi.id, {"data_revision": poi.data_revision, "required_fields_changed": required_changed})
    db.commit()
    return _view(poi)


@router.post("/{place_id}/status")
def set_place_status(place_id: str, payload: PlaceStatusRequest, actor: User = Depends(require_user(P.ADMIN_PLACES)), db: Session = Depends(get_db)):
    poi = db.scalar(select(POI).where(POI.id == place_id).with_for_update())
    if poi is None:
        raise HTTPException(status_code=404, detail={"code": "PLACE_NOT_FOUND", "message": "Place not found."})
    old = poi.verification_status
    if payload.action == "publish":
        poi.source_url = payload.source_url or poi.source_url
        if not poi.source_url:
            raise HTTPException(status_code=422, detail={"code": "SOURCE_REQUIRED", "message": "Publishing a place requires an HTTPS source URL."})
        _vouch(db, poi, actor)
    else:
        poi.verification_status = "hidden" if payload.action == "hide" else "draft"
    _audit(db, actor, f"place.{payload.action}", poi.id, {"old_status": old, "status": poi.verification_status})
    db.commit()
    return _view(poi)
