from enum import StrEnum


INTENT_TAG_ALIASES = {
    "thủ_công": "handicraft",
    "ẩm_thực": "food",
    "văn_hóa": "culture",
    "thư_giãn": "relaxation",
}


def normalize_intent_tag(value: str) -> str:
    return INTENT_TAG_ALIASES.get(value, value)


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    SIMULATED = "simulated"


class SlotStatus(StrEnum):
    OPEN = "open"
    FULL = "full"
    # Kept for records created by the original project schema.
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class DataMode(StrEnum):
    REAL = "real"
    SIMULATED = "simulated"
    REPLAY = "replay"


class ItineraryStatus(StrEnum):
    CONFIRMED = "confirmed"
    AFFECTED = "affected"
    RE_PLANNED = "re_planned"
    # Lifecycle states used by the existing planner/API.
    DRAFT = "draft"
    FEASIBLE = "feasible"
    TENTATIVE = "tentative"
    ACCEPTED = "accepted"
    INVALIDATED = "invalidated"
    COMPLETED = "completed"


class PriceBasis(StrEnum):
    PER_PERSON = "per_person"
    PER_GROUP = "per_group"


def enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_type]
