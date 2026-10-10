from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.repositories.experience_repository import ExperienceRepository
from app.core.pilot_area import PILOT_DISTRICT
from app.schemas.common import ExperienceRead, POIRead, SlotRead
from app.services.experience_service import ExperienceService
from app.db.session import get_db
from app.services.e5_search_service import E5NotConfigured, E5ProviderError, E5SearchService
from app.services.pilot_area import is_pilot_district

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/pois", response_model=list[POIRead])
def list_pois(db: Session = Depends(get_db)):
    repository = ExperienceRepository(db)
    return [read_poi(repository, item) for item in repository.list_pois(district=PILOT_DISTRICT)]


@router.get("/pois/{poi_id}", response_model=POIRead)
def get_poi(poi_id: str, db: Session = Depends(get_db)):
    repository = ExperienceRepository(db)
    poi = repository.get_poi(poi_id)
    if not poi or not is_pilot_district(poi.district):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "POI not found"})
    return read_poi(repository, poi)


def read_poi(repository: ExperienceRepository, poi) -> POIRead:
    base = POIRead.model_validate(poi)
    is_real = poi.verification_status == "verified"
    return POIRead.model_validate({
        **base.model_dump(),
        "data_mode": "real" if is_real else "simulated",
        "source_evidence": repository.source_evidence("poi", poi.id, poi.data_revision) if is_real else [],
    })


@router.get("/experiences", response_model=list[ExperienceRead])
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


@router.get("/experiences/{experience_id}", response_model=ExperienceRead)
def get_experience(experience_id: str, db: Session = Depends(get_db)):
    experience = ExperienceService(ExperienceRepository(db)).get(experience_id)
    if experience is not None and not is_pilot_district(experience.poi.district):
        experience = None
    if not experience:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Experience not found"})
    return experience


@router.get("/experience-search")
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


@router.get("/experiences/{experience_id}/slots", response_model=list[SlotRead])
def get_slots(experience_id: str, start_at: datetime | None = None, end_at: datetime | None = None, db: Session = Depends(get_db)):
    repository = ExperienceRepository(db)
    experience = repository.get_experience(experience_id)
    if not experience or not is_pilot_district(experience.poi.district):
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
