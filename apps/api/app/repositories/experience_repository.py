from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import settings
from app.core.pilot_area import PILOT_DISTRICT
from app.models.entities import Evidence, Experience, ExperienceSlot, POI
from app.services.evidence_service import (
    current_verified_evidence,
    entity_is_operationally_verified,
    evidence_summary,
    is_current_and_unexpired,
    slot_is_operationally_verified,
    target_revision,
)
from app.services.pilot_area import is_pilot_district, pilot_district_sql_filter


class ExperienceRepository:
    def __init__(self, db: Session):
        self.db = db
        self._evidence_cache: dict[tuple[str, str, int], list[Evidence]] = {}

    def list_experiences(
        self,
        intent: str | None = None,
        max_price: int | None = None,
        district: str | None = None,
        slot_start_at: datetime | None = None,
        slot_end_at: datetime | None = None,
    ) -> list[Experience]:
        slot_criteria = []
        if slot_start_at is not None:
            slot_criteria.append(ExperienceSlot.start_at >= slot_start_at)
        if slot_end_at is not None:
            slot_criteria.append(ExperienceSlot.end_at <= slot_end_at)
        slot_loader = selectinload(Experience.slots.and_(*slot_criteria)) if slot_criteria else selectinload(Experience.slots)

        query = select(Experience).join(POI).options(joinedload(Experience.poi), slot_loader)
        allowed_statuses = ["verified"] if settings.real_data_only else ["verified", "simulated"]
        query = query.where(Experience.verification_status.in_(allowed_statuses), POI.verification_status.in_(allowed_statuses))
        if max_price is not None:
            query = query.where(Experience.price_vnd <= max_price)
        if district:
            query = query.where(pilot_district_sql_filter() if district == PILOT_DISTRICT else self._district_filter(district))
        if slot_criteria:
            query = query.execution_options(populate_existing=True)
        items = list(self.db.scalars(query.order_by(Experience.name)).unique())
        self._prime_evidence_cache(experiences=items)
        items = [item for item in items if (not district or is_pilot_district(item.poi.district)) and self._is_public(item)]
        if intent:
            items = [item for item in items if intent in (item.intent_tags or [])]
        return items

    def get_experience(self, experience_id: str) -> Experience | None:
        allowed_statuses = ["verified"] if settings.real_data_only else ["verified", "simulated"]
        item = self.db.scalar(
            select(Experience)
            .join(POI)
            .where(Experience.id == experience_id, Experience.verification_status.in_(allowed_statuses), POI.verification_status.in_(allowed_statuses))
            .options(joinedload(Experience.poi), selectinload(Experience.slots))
        )
        if item is None:
            return None
        self._prime_evidence_cache(experiences=[item])
        return item if self._is_public(item) else None

    def list_pois(self, district: str | None = None) -> list[POI]:
        allowed_statuses = ["verified"] if settings.real_data_only else ["verified", "simulated"]
        query = select(POI).where(POI.verification_status.in_(allowed_statuses))
        if district:
            query = query.where(pilot_district_sql_filter() if district == PILOT_DISTRICT else self._district_filter(district))
        items = list(self.db.scalars(query.order_by(POI.name)))
        self._prime_evidence_cache(pois=items)
        return [item for item in items if (not district or is_pilot_district(item.district)) and ((not settings.real_data_only and item.verification_status == "simulated") or self._is_verified("poi", item))]

    def get_poi(self, poi_id: str) -> POI | None:
        allowed_statuses = ["verified"] if settings.real_data_only else ["verified", "simulated"]
        item = self.db.scalar(select(POI).where(POI.id == poi_id, POI.verification_status.in_(allowed_statuses)))
        if item is not None:
            self._prime_evidence_cache(pois=[item])
        if item is None or (settings.real_data_only or item.verification_status != "simulated") and not self._is_verified("poi", item):
            return None
        return item

    def list_slots(self, experience_id: str, start_at: datetime | None = None, end_at: datetime | None = None) -> list[ExperienceSlot]:
        query = select(ExperienceSlot).where(ExperienceSlot.experience_id == experience_id).order_by(ExperienceSlot.start_at)
        if start_at:
            query = query.where(ExperienceSlot.start_at >= start_at)
        if end_at:
            query = query.where(ExperienceSlot.end_at <= end_at)
        items = list(self.db.scalars(query))
        experience = self.db.get(Experience, experience_id)
        if experience and (settings.real_data_only or experience.verification_status == "verified"):
            items = [slot for slot in items if self.is_fresh_slot(slot)]
        return items

    def source_evidence(self, target_type: str, target_id: str, revision: int) -> list[dict]:
        key = (target_type, target_id, revision)
        evidence = self._evidence_cache.get(key)
        if evidence is None:
            evidence = current_verified_evidence(self.db, target_type, target_id, revision)
        return [evidence_summary(item) for item in evidence]

    def _is_public(self, item: Experience) -> bool:
        if settings.real_data_only and (item.verification_status != "verified" or item.poi.verification_status != "verified"):
            return False
        if item.verification_status == "simulated" and item.poi.verification_status == "simulated":
            return True
        return (
            self._is_verified("experience", item)
            and self._is_verified("poi", item.poi)
        )

    def is_fresh_slot(self, slot: ExperienceSlot) -> bool:
        return slot_is_operationally_verified(self.db, slot, self._evidence_for("slot", slot))

    def _evidence_for(self, target_type: str, target) -> list[Evidence]:
        key = (target_type, target.id, target_revision(target_type, target))
        evidence = self._evidence_cache.get(key)
        if evidence is None:
            evidence = current_verified_evidence(self.db, *key)
            self._evidence_cache[key] = evidence
        return evidence

    def _is_verified(self, target_type: str, target) -> bool:
        return entity_is_operationally_verified(self.db, target_type, target, self._evidence_for(target_type, target))

    def _prime_evidence_cache(
        self,
        *,
        experiences: list[Experience] | None = None,
        pois: list[POI] | None = None,
    ) -> None:
        targets: dict[str, dict[str, int]] = {"poi": {}, "experience": {}, "slot": {}}
        for poi in pois or []:
            targets["poi"][poi.id] = target_revision("poi", poi)
        for experience in experiences or []:
            targets["poi"][experience.poi.id] = target_revision("poi", experience.poi)
            targets["experience"][experience.id] = target_revision("experience", experience)
            for slot in experience.slots:
                targets["slot"][slot.id] = target_revision("slot", slot)

        for target_type, revisions in targets.items():
            ids = list(revisions)
            for chunk_start in range(0, len(ids), 500):
                id_chunk = ids[chunk_start:chunk_start + 500]
                for target_id in id_chunk:
                    self._evidence_cache.setdefault((target_type, target_id, revisions[target_id]), [])
                rows = self.db.scalars(select(Evidence).where(
                    Evidence.target_type == target_type,
                    Evidence.target_id.in_(id_chunk),
                    Evidence.verification_status == "verified",
                )).all()
                for row in rows:
                    if revisions.get(row.target_id) != row.target_revision or not is_current_and_unexpired(row):
                        continue
                    self._evidence_cache[(target_type, row.target_id, row.target_revision)].append(row)

    @staticmethod
    def _district_filter(district: str):
        normalized = " ".join(district.casefold().replace(".", " ").split())
        if normalized in {"quận 1", "quan 1", "district 1", "q 1", "q1"}:
            # Use exact district-number boundaries so "Quận 10" is never treated as Quận 1.
            return or_(
                POI.district.in_(["Quận 1", "quan 1", "District 1", "Q1", "Q.1"]),
                POI.district.startswith("Quận 1,"),
                POI.district.startswith("Quận 1 "),
                POI.district.startswith("District 1,"),
                POI.district.startswith("District 1 "),
            )
        return func.lower(POI.district).contains(normalized)
