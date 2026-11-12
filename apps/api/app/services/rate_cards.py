"""Rate card helpers: stable item codes, version diff, and the bridge into the cost engine."""
import re
import unicodedata
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import RateCard, RateCardItem
from app.services.quote.cost_engine import RateItem


def slug(text: str) -> str:
    plain = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:60] or "item"


def make_code(category: str, label: str, unit: str, seats: int | None) -> str:
    # Vehicles are identified by seats+unit so "Xe 16 chỗ" and "Xe 16 cho" stay one code across versions.
    return f"{category}-{seats}s-{unit}" if category == "vehicle" and seats else f"{category}-{slug(label)}"


def diff_items(old: list[RateCardItem], new: list[RateCardItem]) -> dict:
    a, b = {i.code: i for i in old}, {i.code: i for i in new}
    changed = [
        {"code": c, "label": b[c].label, "old_vnd": a[c].amount_vnd, "new_vnd": b[c].amount_vnd,
         "delta_vnd": b[c].amount_vnd - a[c].amount_vnd,
         "delta_pct": round((b[c].amount_vnd - a[c].amount_vnd) * 100 / a[c].amount_vnd, 1) if a[c].amount_vnd else None}
        for c in sorted(a.keys() & b.keys()) if a[c].amount_vnd != b[c].amount_vnd
    ]
    return {
        "changed": changed,
        "added": [{"code": c, "label": b[c].label, "new_vnd": b[c].amount_vnd} for c in sorted(b.keys() - a.keys())],
        "removed": [{"code": c, "label": a[c].label, "old_vnd": a[c].amount_vnd} for c in sorted(a.keys() - b.keys())],
        "unchanged": sum(1 for c in a.keys() & b.keys() if a[c].amount_vnd == b[c].amount_vnd),
    }


def active_rate_items(db: Session, org_id: str, on_date: date) -> list[RateItem]:
    """Items of the org's active cards valid on ``on_date``, as cost-engine inputs.

    Vehicle base and per_km items pair up in the engine by (supplier, seats), so both come from the same card's
    supplier here; seed/import must give them the same seats.
    """
    cards = db.scalars(
        select(RateCard).options(selectinload(RateCard.items)).where(
            RateCard.org_id == org_id, RateCard.status == "active",
            or_(RateCard.valid_from.is_(None), RateCard.valid_from <= on_date),
            or_(RateCard.valid_to.is_(None), RateCard.valid_to >= on_date),
        ).order_by(RateCard.supplier, RateCard.category)
    ).all()
    return [
        RateItem(i.id, c.id, c.version, c.supplier, c.category, i.code, i.label, i.unit, int(i.amount_vnd),
                 i.seats, i.max_pax, i.experience_id, dict(i.conditions or {}))
        for c in cards for i in c.items
    ]
