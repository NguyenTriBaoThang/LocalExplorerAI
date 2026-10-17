from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.guards import public
from app.core.pilot_area import PILOT_DISTRICT
from app.db.session import get_db
from app.repositories.experience_repository import ExperienceRepository
from app.models.entities import Experience, ExperienceReview, Provider
from app.schemas.common import ExperienceRead, PartnerRead, PartnerSummary, POIDetailRead, POIRead, SlotRead
from app.services.e5_search_service import (
    E5NotConfigured,
    E5ProviderError,
    E5SearchService,
)
from app.services.experience_service import ExperienceService
from app.services.pilot_area import is_pilot_location

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/pois", response_model=list[POIRead], dependencies=[Depends(public('public catalogue'))])
def list_pois(db: Session = Depends(get_db)):
    repository = ExperienceRepository(db)
    return [read_poi(repository, item) for item in repository.list_pois(district=PILOT_DISTRICT)]


@router.get("/pois/{poi_id}", response_model=POIDetailRead, dependencies=[Depends(public('public catalogue'))])
def get_poi(poi_id: str, db: Session = Depends(get_db)):
    repository = ExperienceRepository(db)
    poi = repository.get_poi(poi_id)
    if not poi or not is_pilot_location(poi.latitude, poi.longitude):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "POI not found"})
    place = read_poi(repository, poi)
    experiences = db.scalars(
        select(Experience).where(Experience.poi_id == poi.id).order_by(Experience.name)
    ).all()
    experience_service = ExperienceService(repository)
    place_payload = place.model_dump()
    place_payload["experiences"] = [
        serialized.model_dump()
        for item in experiences
        if (serialized := experience_service.get(item.id)) is not None
    ]
    return POIDetailRead.model_validate(place_payload)


def read_poi(repository: ExperienceRepository, poi) -> POIRead:
    base = POIRead.model_validate(poi)
    is_real = poi.verification_status == "verified"
    return POIRead.model_validate({
        **base.model_dump(),
        "data_mode": "real" if is_real else "simulated",
        "source_evidence": repository.source_evidence("poi", poi.id, poi.data_revision) if is_real else [],
    })


@router.get("/experiences", response_model=list[ExperienceRead], dependencies=[Depends(public('public catalogue'))])
def list_experiences(
    intent: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    group_size: int | None = Query(default=None, ge=1),
    max_price: int | None = Query(default=None, ge=0),
    topic: str | None = None,
    is_indoor: bool | None = None,
    query: str | None = Query(default=None, max_length=200),
    max_distance_km: float | None = Query(default=None, gt=0, le=100),
    center_latitude: float | None = Query(default=None, ge=-90, le=90),
    center_longitude: float | None = Query(default=None, ge=-180, le=180),
    slot_id: str | None = None,
    db: Session = Depends(get_db),
):
    if (center_latitude is None) != (center_longitude is None):
        raise HTTPException(status_code=422, detail={"code": "CENTER_COORDINATES_REQUIRED", "message": "Provide both center latitude and longitude."})
    if max_distance_km is not None and center_latitude is None:
        raise HTTPException(status_code=422, detail={"code": "CENTER_COORDINATES_REQUIRED", "message": "Distance filtering requires center coordinates."})
    return ExperienceService(ExperienceRepository(db)).list(
        intent, start_at, end_at, group_size, max_price, topic, is_indoor, query,
        max_distance_km, center_latitude, center_longitude, slot_id, district=PILOT_DISTRICT,
    )


@router.get("/experiences/{experience_id}", response_model=ExperienceRead, dependencies=[Depends(public('public catalogue'))])
def get_experience(experience_id: str, db: Session = Depends(get_db)):
    experience = ExperienceService(ExperienceRepository(db)).get(experience_id)
    if experience is not None and not is_pilot_location(experience.poi.latitude, experience.poi.longitude):
        experience = None
    if not experience:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Experience not found"})
    return experience


# Partners that are visible to the public: approved (or legacy demo values) and not suspended.
_PUBLIC_PARTNER_STATUSES = ("verified", "mock", "simulated")


@router.get("/partners", response_model=list[PartnerSummary], dependencies=[Depends(public('public directory of approved partners'))])
def list_partners(q: str | None = Query(default=None, max_length=80), db: Session = Depends(get_db)):
    """Approved, active partners that currently have at least one public experience, best rated first."""
    providers = {p.id: p for p in db.scalars(select(Provider).where(Provider.is_active.is_(True), Provider.verification_status.in_(_PUBLIC_PARTNER_STATUSES)))}
    experiences: dict[str, list[ExperienceRead]] = {}
    for item in ExperienceService(ExperienceRepository(db)).list():
        if item.provider_id in providers:
            experiences.setdefault(item.provider_id, []).append(item)
    ratings = {pid: (count, float(avg)) for pid, count, avg in db.execute(
        select(ExperienceReview.provider_id, func.count(ExperienceReview.id), func.avg(ExperienceReview.rating)).where(
            ExperienceReview.status == "published").group_by(ExperienceReview.provider_id)).all()}
    needle = (q or "").strip().casefold()
    rows: list[PartnerSummary] = []
    for pid, items in experiences.items():
        provider = providers[pid]
        if needle and needle not in f"{provider.name} {provider.description} {provider.address}".casefold():
            continue
        count, average = ratings.get(pid, (0, None))
        rows.append(PartnerSummary(
            id=provider.id, name=provider.name, slug=provider.slug, description=provider.description[:280], address=provider.address, website=provider.website,
            cover_url=next((url for it in items for url in it.poi.image_urls[:1]), None), categories=sorted({it.poi.category for it in items})[:4],
            experience_count=len(items), min_price_vnd=min(it.price_vnd for it in items),
            rating_average=round(average, 1) if average is not None else None, rating_count=count))
    rows.sort(key=lambda r: (-(r.rating_average or 0), -r.rating_count, -r.experience_count, r.name))
    return rows


@router.get("/partners/{slug}", response_model=PartnerRead, dependencies=[Depends(public('public profile of an approved partner'))])
def get_partner(slug: str, db: Session = Depends(get_db)):
    provider = db.scalar(select(Provider).where(Provider.slug == slug, Provider.is_active.is_(True), Provider.verification_status.in_(_PUBLIC_PARTNER_STATUSES)))
    if provider is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Partner not found"})
    experiences = [item for item in ExperienceService(ExperienceRepository(db)).list() if item.provider_id == provider.id]
    count, average = db.execute(select(func.count(ExperienceReview.id), func.avg(ExperienceReview.rating)).where(
        ExperienceReview.provider_id == provider.id, ExperienceReview.status == "published")).one()
    return PartnerRead(id=provider.id, name=provider.name, slug=provider.slug, description=provider.description, address=provider.address,
                       website=provider.website, contact_phone=provider.contact_phone, contact_email=provider.contact_email,
                       rating_average=round(float(average), 1) if average is not None else None, rating_count=count or 0, experiences=experiences)


@router.get("/experience-search", dependencies=[Depends(public('public catalogue'))])
def search_experiences(
    q: str = Query(min_length=2, max_length=200),
    semantic: bool = False,
    intent: str | None = None,
    topic: str | None = None,
    is_indoor: bool | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    group_size: int | None = Query(default=None, ge=1),
    max_price: int | None = Query(default=None, ge=0),
    max_distance_km: float | None = Query(default=None, gt=0, le=100),
    center_latitude: float | None = Query(default=None, ge=-90, le=90),
    center_longitude: float | None = Query(default=None, ge=-180, le=180),
    slot_id: str | None = None,
    db: Session = Depends(get_db),
):
    if (center_latitude is None) != (center_longitude is None):
        raise HTTPException(status_code=422, detail={"code": "CENTER_COORDINATES_REQUIRED", "message": "Provide both center latitude and longitude."})
    if max_distance_km is not None and center_latitude is None:
        raise HTTPException(status_code=422, detail={"code": "CENTER_COORDINATES_REQUIRED", "message": "Distance filtering requires center coordinates."})
    items = ExperienceService(ExperienceRepository(db)).list(
        intent=intent, start_at=start_at, end_at=end_at, group_size=group_size,
        max_price=max_price, topic=topic, is_indoor=is_indoor, query=None if semantic else q,
        max_distance_km=max_distance_km, center_latitude=center_latitude,
        center_longitude=center_longitude, slot_id=slot_id, district=PILOT_DISTRICT,
    )
    if not semantic:
        return {"mode": "keyword", "items": items}
    passages = [" ".join((item.name, item.description, item.poi.name, item.poi.description, " ".join(item.intent_tags))) for item in items]
    try:
        scores = E5SearchService().embed_and_rank(q, passages)
    except E5NotConfigured as error:
        raise HTTPException(status_code=503, detail={"code": "E5_SEARCH_NOT_CONFIGURED", "message": str(error)}) from error
    except E5ProviderError as error:
        raise HTTPException(status_code=500, detail={"code": "E5_SEARCH_FAILED", "message": str(error)}) from error
    ranked = sorted(zip(items, scores), key=lambda pair: pair[1], reverse=True)
    return {"mode": "semantic_e5", "items": [{**item.model_dump(mode="json"), "relevance_score": round(score, 5)} for item, score in ranked]}


@router.get("/experiences/{experience_id}/slots", response_model=list[SlotRead], dependencies=[Depends(public('public catalogue'))])
def get_slots(experience_id: str, start_at: datetime | None = None, end_at: datetime | None = None, db: Session = Depends(get_db)):
    repository = ExperienceRepository(db)
    experience = repository.get_experience(experience_id)
    if not experience or not is_pilot_location(experience.poi.latitude, experience.poi.longitude):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Experience not found"})
    is_real = experience.verification_status == "verified"
    result = []
    for slot in repository.list_slots(experience_id, start_at, end_at):
        base = SlotRead.model_validate(slot)
        result.append(SlotRead.model_validate({
            **base.model_dump(),
            "data_mode": "real" if is_real else "simulated",
            "source_evidence": repository.source_evidence("slot", slot.id, slot.version) if is_real else [],
        }))
    return result
