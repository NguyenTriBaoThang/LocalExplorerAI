from datetime import datetime
from math import asin, cos, radians, sin, sqrt

from app.core.enums import SlotStatus
from app.repositories.experience_repository import ExperienceRepository
from app.schemas.common import ExperienceRead, POIRead, SlotRead


class ExperienceService:
    def __init__(self, repository: ExperienceRepository):
        self.repository = repository

    def list(
        self,
        intent: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        group_size: int | None = None,
        max_price: int | None = None,
        topic: str | None = None,
        is_indoor: bool | None = None,
        query: str | None = None,
        max_distance_km: float | None = None,
        center_latitude: float | None = None,
        center_longitude: float | None = None,
        slot_id: str | None = None,
        district: str | None = None,
    ):
        items = self.repository.list_experiences(
            intent=intent,
            max_price=max_price,
            district=district,
            slot_start_at=start_at,
            slot_end_at=end_at,
        )
        result: list[ExperienceRead] = []
        for item in items:
            if topic and topic.casefold() not in " ".join(item.intent_tags or []).casefold() and topic.casefold() not in item.poi.category.casefold():
                continue
            if is_indoor is not None and item.is_indoor != is_indoor:
                continue
            if query:
                searchable = " ".join((item.name, item.title, item.description, item.poi.name, item.poi.district or "", item.poi.address, *(item.intent_tags or []))).casefold()
                if query.casefold() not in searchable:
                    continue
            if max_distance_km is not None:
                if center_latitude is None or center_longitude is None:
                    continue
                dlat = radians(item.poi.latitude - center_latitude)
                dlon = radians(item.poi.longitude - center_longitude)
                lat1, lat2 = radians(center_latitude), radians(item.poi.latitude)
                a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
                distance_km = 6371.0 * 2 * asin(sqrt(min(1.0, a)))
                if distance_km > max_distance_km:
                    continue
            slots = [slot for slot in item.slots if slot.status not in {
                SlotStatus.FULL.value, SlotStatus.UNAVAILABLE.value, SlotStatus.CANCELLED.value,
            } and slot.available_reported != 0]
            if item.verification_status == "verified":
                slots = [slot for slot in slots if slot.status in {SlotStatus.OPEN.value, SlotStatus.AVAILABLE.value}
                         and self.repository.is_fresh_slot(slot)]
            if start_at:
                slots = [slot for slot in slots if slot.start_at.replace(tzinfo=slot.start_at.tzinfo or start_at.tzinfo) >= start_at]
            if end_at:
                slots = [slot for slot in slots if slot.end_at.replace(tzinfo=slot.end_at.tzinfo or end_at.tzinfo) <= end_at]
            if group_size:
                slots = [slot for slot in slots if slot.available_reported is None or slot.available_reported >= group_size]
            if slot_id:
                slots = [slot for slot in slots if slot.id == slot_id]
            if (start_at or end_at) and not slots:
                continue
            result.append(self.serialize(item, slots, item.verification_status == "verified"))
        stats = self.repository.review_stats([item.id for item in result])
        return [item.model_copy(update={"rating_count": stats[item.id][0], "rating_average": stats[item.id][1]}) if item.id in stats else item for item in result]

    def get(self, experience_id: str) -> ExperienceRead | None:
        item = self.repository.get_experience(experience_id)
        if item is None:
            return None
        slots = [slot for slot in item.slots if slot.status not in {
            SlotStatus.FULL.value, SlotStatus.UNAVAILABLE.value, SlotStatus.CANCELLED.value,
        } and slot.available_reported != 0]
        if item.verification_status == "verified":
            slots = [slot for slot in slots if slot.status in {SlotStatus.OPEN.value, SlotStatus.AVAILABLE.value}
                     and self.repository.is_fresh_slot(slot)]
        return self.serialize(item, slots, item.verification_status == "verified")

    def serialize(self, item, slots, is_real: bool) -> ExperienceRead:
        poi = POIRead.model_validate(item.poi)
        poi = POIRead.model_validate({
            **poi.model_dump(),
            "data_mode": "real" if is_real else "simulated",
            "source_evidence": self.repository.source_evidence("poi", item.poi.id, item.poi.data_revision) if is_real else [],
        })
        experience = ExperienceRead.model_validate({
            **ExperienceRead.model_validate(item).model_dump(),
            "poi": poi.model_dump(),
            "provider_name": item.provider.name if item.provider else None,
            "provider_slug": item.provider.slug if item.provider else None,
            "data_mode": "real" if is_real else "simulated",
            "source_evidence": self.repository.source_evidence("experience", item.id, item.data_revision) if is_real else [],
        })
        slot_reads = []
        for slot in slots:
            slot_read = SlotRead.model_validate(slot)
            slot_reads.append(SlotRead.model_validate({
                **slot_read.model_dump(),
                "data_mode": "real" if is_real else "simulated",
                "source_evidence": self.repository.source_evidence("slot", slot.id, slot.version) if is_real else [],
            }))
        return experience.model_copy(update={"slots": slot_reads})
