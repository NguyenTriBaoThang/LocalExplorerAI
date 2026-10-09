"""Deterministic, source-derived POI labels for admin review.

These labels classify a place record. They are not experience outcomes,
human preference grades, or evidence that operational fields are verified.
"""

import re
import unicodedata
from collections.abc import Mapping


LABEL_RULESET_VERSION = "poi-label-suggestions-v1"

KIND_LABELS = {
    "tham-quan": ("sightseeing", "Điểm tham quan", "passive_visit"),
    "an-uong": ("restaurant", "Ăn uống", "food_service"),
    "cafe": ("cafe", "Quán cà phê", "coffee_service"),
    "giai-tri": ("entertainment", "Giải trí", "entertainment"),
    "cho-o": ("accommodation", "Lưu trú", "lodging"),
}

INTENT_CUES = {
    "handicraft": (
        "lam gom", "nan gom", "theu tay", "che tac", "pottery class",
        "craft workshop", "workshop lam gom", "thuc hanh thu cong",
    ),
    "food": (
        "am thuc", "an uong", "nha hang", "quan an", "mon an", "mon viet",
        "street food", "restaurant", "cuisine", "banh xeo", "com tam", "pho bo",
        "an vat", "cafe", "coffee", "ca phe", "tra sua", "barista",
    ),
    "culture": (
        "lich su", "van hoa", "bao tang", "di san", "di tich", "kien truc",
        "ton giao", "tam linh", "chua", "nha tho", "museum", "heritage",
        "historic", "historical", "art gallery",
    ),
    "relaxation": (
        "thu gian", "thien nhien", "sinh thai", "cong vien", "san vuon", "ven song",
        "song sai gon", "ngam canh", "hoang hon", "yoga", "spa", "wellness",
        "massage", "garden", "park", "riverside", "sunset", "nature",
    ),
}

OTHER_TOPIC_CUES = {
    "shopping": ("mua sam", "trung tam thuong mai", "mall", "shopping"),
    "entertainment": (
        "giai tri", "am nhac", "nhac song", "live music", "nightclub", "pub",
        "bar", "theatre", "theater", "rap chieu phim", "tro choi", "xiec", "dj",
    ),
    "accommodation": ("khach san", "hotel", "homestay", "luu tru", "resort"),
    "sightseeing": ("tham quan", "check in", "check-in", "view dep", "bieu tuong"),
}

HANDS_ON_CUES = (
    "du khach tu tay", "khach tu tay", "ban tu tay", "du khach tu lam",
    "khach tu lam", "tu tay lam gom", "tu tay lam banh", "tu tay pha che",
    "tham gia lam", "thuc hanh lam", "nan gom", "theu tay", "che tac",
    "cheo sup", "kayak", "leo nui nhan tao", "cooking class", "lop nau an",
)

OUTDOOR_CUES = ("outdoor", "open air", "ngoai troi", "ngoai that")


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold().replace("đ", "d"))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _has_cue(text: str, cues: tuple[str, ...]) -> bool:
    padded_text = f" {_fold(text)} "
    return any(f" {_fold(cue)} " in padded_text for cue in cues)


def suggest_place_labels(record: Mapping[str, object], kind: str | None = None) -> dict:
    """Classify a staged POI from its supplied kind, tags and description only."""
    source_kind = _fold(kind or record.get("kind")).replace(" ", "-")
    type_code, type_label, activity_mode = KIND_LABELS.get(
        source_kind, ("other", "Khác / cần phân loại", "unknown")
    )

    raw_tags = record.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
    source_tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()] if isinstance(raw_tags, list) else []
    folded_tags = [_fold(tag) for tag in source_tags]
    description = _fold(record.get("description"))
    name = _fold(record.get("name"))
    text = " ".join([name, description, *folded_tags, _fold(source_kind)])

    intent_tags = set()
    for intent, cues in INTENT_CUES.items():
        if _has_cue(text, cues):
            intent_tags.add(intent)
    for topic, cues in OTHER_TOPIC_CUES.items():
        if _has_cue(text, cues):
            intent_tags.add(topic)
    if type_code in {"sightseeing", "entertainment", "accommodation"}:
        intent_tags.add(type_code)

    # A place's type is stronger evidence than incidental tags in its description.
    primary_intent = None
    if source_kind in {"an-uong", "cafe"}:
        primary_intent = "food"
        intent_tags.add("food")
    elif _has_cue(text, INTENT_CUES["handicraft"]):
        primary_intent = "handicraft"
    elif _has_cue(text, INTENT_CUES["culture"]):
        primary_intent = "culture"
    elif _has_cue(text, INTENT_CUES["relaxation"]):
        primary_intent = "relaxation"

    hands_on = True if _has_cue(text, HANDS_ON_CUES) else None
    if hands_on:
        activity_mode = "participatory_activity"

    outdoor_value = record.get("outdoor")
    is_outdoor = outdoor_value if isinstance(outdoor_value, bool) else None
    if is_outdoor is None and _has_cue(text, OUTDOOR_CUES):
        is_outdoor = True

    if is_outdoor is None:
        indoor_outdoor = "unknown"
        weather_sensitivity = "unknown"
    elif is_outdoor:
        indoor_outdoor = "outdoor"
        weather_sensitivity = "rain_sensitive"
    else:
        indoor_outdoor = "indoor"
        weather_sensitivity = "indoor_safe"

    return {
        "ruleset_version": LABEL_RULESET_VERSION,
        "label_status": "suggested_from_source",
        "poi_type": type_code,
        "poi_type_label_vi": type_label,
        "activity_mode": activity_mode,
        "primary_intent": primary_intent,
        "intent_tags": sorted(intent_tags),
        "source_topic_tags": source_tags,
        "hands_on": hands_on,
        "hands_on_status": "explicit_source_cue" if hands_on else "unknown_at_poi_level",
        "indoor_outdoor": indoor_outdoor,
        "weather_sensitivity": weather_sensitivity,
        "basis_fields": [
            field for field in ("kind", "tags", "description", "outdoor")
            if field == "kind" or (record.get(field) not in (None, "", []))
        ],
        "warning": "Nhãn gợi ý từ dữ liệu nguồn, không xác minh bằng chứng và không phải điểm đánh giá sau chuyến đi.",
    }
