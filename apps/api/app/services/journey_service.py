"""Catalog-backed handoffs between 3D discovery, chat and the existing planner."""
from datetime import datetime, timezone
from math import cos, radians, hypot

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.pilot_area import PILOT_DISTRICT
from app.models.entities import POI, Evidence
from app.repositories.experience_repository import ExperienceRepository
from app.services.evidence_service import covered_fields, entity_is_operationally_verified, current_verified_evidence
from app.services.experience_service import ExperienceService
from app.services.pilot_area import is_pilot_location, normalize_district


def pilot_status(db: Session) -> dict:
    repository = ExperienceRepository(db)
    experiences = ExperienceService(repository).list(district=PILOT_DISTRICT)
    now = datetime.now(timezone.utc)
    verified = [item for item in experiences if item.data_mode == "real"]
    ready = [item for item in verified if any(slot.start_at > now and slot.available_reported and slot.available_reported > 0 for slot in item.slots)]
    demo = [item for item in experiences if item.data_mode != "real" and any(slot.start_at > now for slot in item.slots)]
    return {
        "area": PILOT_DISTRICT, "city": "TP. Hồ Chí Minh", "as_of": now,
        "catalog_pois": db.scalar(select(func.count()).select_from(POI)),
        "evidence_records": db.scalar(select(func.count()).select_from(Evidence)),
        "pilot_experiences": len(experiences), "verified_experiences": len(verified),
        "ready_experiences": len(ready), "demo_experiences": len(demo),
        "demo_available": not settings.real_data_only and bool(demo),
        "status": "ready_for_validation" if ready else "needs_verified_data",
        "note": "Lịch trình còn phải được kiểm tra theo ngày, giờ, chặng về, số người và ngân sách. Hội An chưa nằm trong phạm vi lập lịch.",
    }


def landmark_context(db: Session, model_id: str, demo: bool = False) -> dict:
    from app.api.routes.models_3d import _get_known_model, _read_calibrations
    model = _get_known_model(model_id, _read_calibrations())
    repository = ExperienceRepository(db)
    pois = repository.list_pois()
    latitude, longitude = model["latitude"], model["longitude"]
    in_pilot = is_pilot_location(latitude, longitude)

    def nearby(poi):
        return hypot((poi.latitude - latitude) * 111_320,
                     (poi.longitude - longitude) * 111_320 * cos(radians(latitude))) <= 250

    # Never link an arbitrary nearest building. Require an ID or exact normalized
    # name AND spatial agreement. Ambiguous/obsolete metadata remains unlinked.
    candidates = [poi for poi in pois if nearby(poi) and (
        poi.id == model.get("poi_id") or normalize_district(poi.name) == normalize_district(model["display_name"])
    )]
    poi = candidates[0] if len(candidates) == 1 else None
    evidence = current_verified_evidence(db, "poi", poi.id, poi.data_revision) if poi else []
    verified = bool(poi and entity_is_operationally_verified(db, "poi", poi, evidence))
    result = {
        "model_id": model_id, "display_name": model["display_name"],
        "poi_id": poi.id if poi else None, "in_pilot": in_pilot,
        "verified": verified, "description": None,
        "latitude": poi.latitude if poi else latitude, "longitude": poi.longitude if poi else longitude,
        "sources": repository.source_evidence("poi", poi.id, poi.data_revision) if verified else [],
        "experiences": [],
        "notice": "Chưa có liên kết danh mục và nguồn đã kiểm chứng cho mô hình này.",
    }
    if verified:
        result["description"] = poi.description if "description" in covered_fields(evidence) else None
        result["notice"] = "Địa danh đã liên kết với danh mục có nguồn. Chọn trải nghiệm và ngày đi để kiểm tra lịch trình."
    elif poi:
        result["notice"] = "Mô hình đã đối chiếu tên và tọa độ với danh mục, nhưng thông tin chưa được kiểm chứng."
    if not in_pilot:
        result["notice"] = "Địa danh ngoài pilot Quận 1. Hiện chỉ xem mô hình 3D; chưa hỗ trợ lập lịch tại đây."
    if poi and in_pilot:
        items = ExperienceService(repository).list(district=PILOT_DISTRICT)
        result["experiences"] = [
            {"id": item.id, "name": item.name, "poi_id": poi.id, "data_mode": item.data_mode}
            for item in items if item.poi_id == poi.id and (item.data_mode == "real" or (demo and not settings.real_data_only))
            and any(slot.start_at > datetime.now(timezone.utc) for slot in item.slots)
        ]
    return result
