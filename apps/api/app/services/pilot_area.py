import re
import unicodedata

from sqlalchemy import or_

from app.core.pilot_area import PILOT_DISTRICT
from app.models.entities import POI


def normalize_district(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value.strip().casefold())
    text = "".join(char for char in text if not unicodedata.combining(char)).replace("đ", "d")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def is_pilot_district(value: str | None) -> bool:
    normalized = normalize_district(value)
    # Require a boundary after 1 so names such as Quận 10 are excluded.
    return bool(re.match(r"^(?:quan|district|q)\s*1(?:\D|$)", normalized))


def pilot_district_sql_filter():
    # Prefix predicates bound the SQL result; the numeric boundary is checked again in Python.
    return or_(
        POI.district.in_([PILOT_DISTRICT, "District 1", "Q1", "Q.1", "Q 1"]),
        POI.district.startswith("Quận 1,"),
        POI.district.startswith("Quận 1 "),
        POI.district.startswith("quận 1,"),
        POI.district.startswith("quận 1 "),
        POI.district.startswith("District 1,"),
        POI.district.startswith("District 1 "),
        POI.district.startswith("district 1,"),
        POI.district.startswith("district 1 "),
    )
