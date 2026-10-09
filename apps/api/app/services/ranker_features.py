"""Versioned deterministic features shared by ranking training and inference."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

LEGACY_FEATURE_VERSION = "ranker-features-v1"
FEATURE_VERSION = "ranker-features-v2"

LEGACY_FEATURE_NAMES = [
    "tag_jaccard", "intent_match", "is_hands_on", "is_indoor",
    "duration_ratio", "eta_ratio", "total_time_ratio", "group_cost_ratio",
    "rain_mm", "outdoor_rain_mm", "temperature_c", "pm2_5", "european_aqi",
]
FEATURE_NAMES = [
    *LEGACY_FEATURE_NAMES,
    "is_hands_on_known",
    "is_indoor_known",
]


def feature_names_for_version(version: str) -> list[str]:
    if version == LEGACY_FEATURE_VERSION:
        return list(LEGACY_FEATURE_NAMES)
    if version == FEATURE_VERSION:
        return list(FEATURE_NAMES)
    raise ValueError(f"Unsupported ranker feature version: {version}")


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(char for char in text if not unicodedata.combining(char))


def parse_tags(value: Any) -> set[str]:
    raw = value if isinstance(value, (list, tuple, set)) else re.split(r"[;,|]", str(value or ""))
    return {_fold(tag).strip() for tag in raw if _fold(tag).strip()}


def _number(value: Any) -> float:
    if value is None or value == "":
        return math.nan
    try:
        number = float(value)
        return number if math.isfinite(number) else math.nan
    except (TypeError, ValueError):
        return math.nan


def _truthy(value: Any) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value != 0)
    return float(str(value or "").strip().casefold() in {"true", "1", "yes", "y", "co", "có"})


def _intent_families_v1(tags: set[str]) -> set[str]:
    families: set[str] = set()
    for tag in tags:
        if any(key in tag for key in ("thu cong", "thu_cong", "handicraft", "craft", "my nghe")):
            families.add("handicraft")
        if any(key in tag for key in ("am thuc", "am_thuc", "food", "cuisine", "nau an")):
            families.add("food")
        if any(key in tag for key in ("van hoa", "van_hoa", "culture", "heritage", "di san", "bao tang", "lich su")):
            families.add("culture")
        if any(key in tag for key in ("thu gian", "thu_gian", "relax", "nature", "sinh thai", "the thao", "sup")):
            families.add("relaxation")
    return families


def build_feature_row_v1(query: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float]:
    query_tags = parse_tags(query.get("user_intent_tags"))
    candidate_tags = parse_tags(candidate.get("candidate_tags"))
    union = query_tags | candidate_tags
    tag_jaccard = len(query_tags & candidate_tags) / len(union) if union else 0.0
    wanted = _intent_families_v1(query_tags)
    offered = _intent_families_v1(candidate_tags)
    intent_match = float(bool(wanted & offered)) if wanted else tag_jaccard

    remaining = _number(query.get("remaining_time_min"))
    duration = _number(candidate.get("duration_min"))
    eta = _number(candidate.get("eta_min"))
    group_size = _number(query.get("group_size"))
    budget = _number(query.get("budget_remaining_vnd"))
    price = _number(candidate.get("price_vnd_per_person", candidate.get("price_vnd")))
    total_cost = _number(candidate.get("total_cost_vnd"))
    if math.isnan(total_cost) and not math.isnan(price) and not math.isnan(group_size):
        total_cost = price * group_size

    def ratio(numerator: float, denominator: float) -> float:
        return numerator / denominator if not math.isnan(numerator) and not math.isnan(denominator) and denominator > 0 else math.nan

    rain = _number(query.get("rain_mm", candidate.get("rain_mm")))
    indoor = _truthy(candidate.get("is_indoor", candidate.get("indoor")))
    return {
        "tag_jaccard": tag_jaccard,
        "intent_match": intent_match,
        "is_hands_on": _truthy(candidate.get("is_hands_on")),
        "is_indoor": indoor,
        "duration_ratio": ratio(duration, remaining),
        "eta_ratio": ratio(eta, remaining),
        "total_time_ratio": ratio(duration + eta, remaining) if not math.isnan(duration) and not math.isnan(eta) else math.nan,
        "group_cost_ratio": ratio(total_cost, budget),
        "rain_mm": rain,
        "outdoor_rain_mm": rain * (1 - indoor) if not math.isnan(rain) else math.nan,
        "temperature_c": _number(query.get("temperature_c", candidate.get("temperature_c"))),
        "pm2_5": _number(query.get("pm2_5", candidate.get("pm2_5"))),
        "european_aqi": _number(query.get("european_aqi", candidate.get("european_aqi"))),
    }


def intent_families(tags: set[str]) -> set[str]:
    """Map Vietnamese and English activity tags to stable, broad intents."""
    aliases = {
        "handicraft": ("thu cong", "handicraft", "craft", "my nghe", "artisan"),
        "food": ("am thuc", "food", "cuisine", "nau an", "restaurant", "nha hang"),
        "coffee": ("coffee", "cafe", "ca phe"),
        "culture": ("van hoa", "culture", "heritage", "di san", "bao tang", "museum", "lich su"),
        "art": ("art", "gallery", "artwork", "fine art", "truc chi", "painting"),
        "nature": ("nature", "park", "garden", "sinh thai", "ecology", "outdoor"),
        "entertainment": ("entertainment", "cinema", "theatre", "theater", "movie", "show"),
        "sightseeing": ("sightseeing", "attraction", "viewpoint", "tham quan"),
        "sport": ("sport", "sports centre", "sports_center", "sup", "the thao"),
        "relaxation": ("thu gian", "relax", "cruise", "river", "sup"),
    }
    families: set[str] = set()
    for tag in tags:
        normalized = _fold(tag).replace("_", " ").replace("-", " ").strip()
        for family, keys in aliases.items():
            if any(key in normalized for key in keys):
                families.add(family)
    return families


def _known_truth(value: Any) -> float:
    if value is None:
        return math.nan
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value != 0) if math.isfinite(float(value)) else math.nan
    normalized = _fold(value).strip()
    if not normalized or normalized in {"unknown", "unk", "null", "none", "na", "n a"}:
        return math.nan
    if normalized in {"true", "1", "yes", "y", "co", "indoor", "open"}:
        return 1.0
    if normalized in {"false", "0", "no", "n", "khong", "outdoor"}:
        return 0.0
    return math.nan


def build_feature_row(query: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float]:
    """Build v2 online features; unknown source values stay missing, not false."""
    query_tags = parse_tags(query.get("user_intent_tags"))
    candidate_tags = parse_tags(candidate.get("candidate_tags"))
    union = query_tags | candidate_tags
    tag_jaccard = len(query_tags & candidate_tags) / len(union) if union else 0.0
    wanted = intent_families(query_tags)
    offered = intent_families(candidate_tags)
    intent_match = float(bool(wanted & offered)) if wanted else tag_jaccard

    remaining = _number(query.get("remaining_time_min"))
    duration = _number(candidate.get("duration_min"))
    eta = _number(candidate.get("eta_min"))
    group_size = _number(query.get("group_size"))
    budget = _number(query.get("budget_remaining_vnd"))
    price = _number(candidate.get("price_vnd_per_person", candidate.get("price_vnd")))
    total_cost = _number(candidate.get("total_cost_vnd"))
    if math.isnan(total_cost) and not math.isnan(price) and not math.isnan(group_size):
        total_cost = price * group_size

    def ratio(numerator: float, denominator: float) -> float:
        return numerator / denominator if not math.isnan(numerator) and not math.isnan(denominator) and denominator > 0 else math.nan

    rain = _number(query.get("rain_mm", candidate.get("rain_mm")))
    hands_on = _known_truth(candidate.get("is_hands_on"))
    indoor = _known_truth(candidate.get("is_indoor", candidate.get("indoor")))
    return {
        "tag_jaccard": tag_jaccard,
        "intent_match": intent_match,
        "is_hands_on": hands_on,
        "is_indoor": indoor,
        "duration_ratio": ratio(duration, remaining),
        "eta_ratio": ratio(eta, remaining),
        "total_time_ratio": ratio(duration + eta, remaining) if not math.isnan(duration) and not math.isnan(eta) else math.nan,
        "group_cost_ratio": ratio(total_cost, budget),
        "rain_mm": rain,
        "outdoor_rain_mm": rain * (1 - indoor) if not math.isnan(rain) and not math.isnan(indoor) else math.nan,
        "temperature_c": _number(query.get("temperature_c", candidate.get("temperature_c"))),
        "pm2_5": _number(query.get("pm2_5", candidate.get("pm2_5"))),
        "european_aqi": _number(query.get("european_aqi", candidate.get("european_aqi"))),
        "is_hands_on_known": float(not math.isnan(hands_on)),
        "is_indoor_known": float(not math.isnan(indoor)),
    }


def is_hard_feasible(query: dict[str, Any], candidate: dict[str, Any]) -> bool:
    if str(candidate.get("hard_feasible", True)).strip().casefold() in {"0", "false", "no"}:
        return False
    remaining = _number(query.get("remaining_time_min"))
    duration = _number(candidate.get("duration_min"))
    eta = _number(candidate.get("eta_min"))
    if not math.isnan(remaining) and not math.isnan(duration) and not math.isnan(eta) and duration + eta > remaining:
        return False
    group_size = _number(query.get("group_size"))
    budget = _number(query.get("budget_remaining_vnd"))
    price = _number(candidate.get("price_vnd_per_person", candidate.get("price_vnd")))
    total_cost = _number(candidate.get("total_cost_vnd"))
    if math.isnan(total_cost) and not math.isnan(price) and not math.isnan(group_size):
        total_cost = price * group_size
    return math.isnan(budget) or math.isnan(total_cost) or total_cost <= budget
