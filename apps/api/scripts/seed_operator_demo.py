"""Idempotent demo tenant for the quote copilot: one operator org, one operator login, six suppliers with 2026 HCMC NET prices.

    python -m scripts.seed_operator_demo

Re-running adds only what is missing (org, user, and any supplier+category without a card). Tour templates and
trip places are NOT seeded here.
"""
import os
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.auth import hash_password
from app.db.session import SessionLocal
from app.models.entities import OperatorOrg, RateCard, RateCardItem, User

ORG_NAME, ORG_SLUG = "Saigon Group Tours", "saigon-group-tours"
EMAIL = os.environ.get("DEMO_OPERATOR_EMAIL", "operator@saigongroup.example").strip().lower()
PASSWORD = os.environ.get("DEMO_OPERATOR_PASSWORD", "SaigonGroup-Demo-2026")
VALID_FROM = date(2026, 1, 1)

# (supplier, category, [(code, label, unit, amount_vnd, seats, max_pax, conditions)])
VEHICLES = [(4, 800_000, 6_000), (7, 1_000_000, 7_000), (16, 1_600_000, 9_000), (29, 2_400_000, 12_000), (45, 3_300_000, 15_000)]
BEFORE_SURCHARGE = ["vehicle", "guide", "hotel"]  # tickets and meals are venue-priced, not marked up on weekends
CARDS = [
    ("Nhà xe Phương Nam", "vehicle",
     [(f"vehicle-{s}s-per_day", f"Xe {s} chỗ (thuê ngày)", "per_day", day, s, None, {}) for s, day, _ in VEHICLES]
     + [(f"vehicle-{s}s-per_km", f"Xe {s} chỗ (theo km)", "per_km", km, s, None, {}) for s, _, km in VEHICLES]),
    ("Saigon Guide Network", "guide", [
        ("guide-noi-dia", "Hướng dẫn viên nội địa", "per_day", 800_000, None, None, {}),
        ("guide-tieng-viet-chuyen-tuyen", "Hướng dẫn viên chuyên tuyến", "per_day", 1_000_000, None, None, {}),
        ("guide-tieng-anh", "Hướng dẫn viên tiếng Anh", "per_day", 1_200_000, None, None, {})]),
    ("Nhà hàng Sen Việt", "meal", [
        ("meal-com-suat", "Cơm suất (set 6 món)", "per_pax", 120_000, None, None, {}),
        ("meal-set-dac-san", "Set menu đặc sản Nam Bộ", "per_pax", 180_000, None, None, {}),
        ("meal-hai-san", "Tiệc hải sản", "per_pax", 250_000, None, None, {})]),
    ("BQL Địa đạo Củ Chi", "ticket", [
        ("ticket-dia-dao-cu-chi", "Vé tham quan Địa đạo Củ Chi", "per_pax", 125_000, None, None, {})]),
    ("Mekong & Cần Giờ Boats", "ticket", [
        ("ticket-thuyen-mekong", "Thuyền sông Mekong (Mỹ Tho - Bến Tre)", "per_pax", 150_000, None, 40, {}),
        ("ticket-can-gio", "Vé + xuồng rừng ngập mặn Cần Giờ", "per_pax", 130_000, None, 30, {})]),
    ("KS Biển Xanh Vũng Tàu 3★", "hotel", [
        ("hotel-vung-tau-3-sao", "Phòng đôi 3★ Vũng Tàu (gồm ăn sáng)", "per_room_night", 700_000, None, 2, {})]),
    ("Chính sách phụ thu", "surcharge", [
        ("surcharge-weekend", "Phụ thu cuối tuần", "pct", 10, None, None, {"weekdays": ["sat", "sun"], "applies_to": BEFORE_SURCHARGE}),
        ("surcharge-holiday", "Phụ thu ngày lễ", "pct", 25, None, None, {"holiday": True, "applies_to": BEFORE_SURCHARGE}),
        ("surcharge-tet", "Phụ thu Tết Nguyên Đán", "pct", 50, None, None, {"tet": True, "applies_to": BEFORE_SURCHARGE})]),
]


def seed(session_factory=SessionLocal) -> dict:
    created = {"org": False, "user": False, "cards": 0}
    with session_factory() as db:
        org = db.scalar(select(OperatorOrg).where(OperatorOrg.slug == ORG_SLUG))
        if org is None:
            org = OperatorOrg(name=ORG_NAME, slug=ORG_SLUG, settings={})
            db.add(org)
            db.flush()
            created["org"] = True
        if db.scalar(select(User.id).where(User.email == EMAIL)) is None:
            db.add(User(email=EMAIL, display_name="Điều hành Saigon Group", password_hash=hash_password(PASSWORD), role="operator",
                        operator_org_id=org.id, email_verified_at=datetime.now(timezone.utc)))
            created["user"] = True
        for supplier, category, items in CARDS:
            if db.scalar(select(RateCard.id).where(RateCard.org_id == org.id, RateCard.supplier == supplier, RateCard.category == category)):
                continue
            card = RateCard(org_id=org.id, supplier=supplier, category=category, version=1, status="active",
                            valid_from=VALID_FROM, approved_at=datetime.now(timezone.utc))
            for code, label, unit, amount, seats, max_pax, conditions in items:
                card.items.append(RateCardItem(org_id=org.id, code=code, label=label, unit=unit, amount_vnd=amount,
                                               seats=seats, max_pax=max_pax, conditions=conditions, confidence=1.0))
            db.add(card)
            created["cards"] += 1
        db.commit()
    return created


if __name__ == "__main__":
    result = seed()
    print(f"Seeded: {result}")
    print(f"Operator login: {EMAIL} / {PASSWORD}  (org: {ORG_NAME})")
