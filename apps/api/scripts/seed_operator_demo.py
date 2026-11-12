"""Idempotent demo tenant for the quote copilot: one operator org, one operator login, six suppliers with 2026 HCMC NET prices.

    python -m scripts.seed_operator_demo

Re-running adds only what is missing (org, user, any supplier+category without a card, any tour template code, any demo
history quote). Trip places are NOT seeded here.

Demo history: completed tours in Aug-Oct 2026, marked "[Demo]" (customer_name) and "DEMO-HISTORY:<key>" (raw_message), won, with
confirmed invoice reconciliation so the margin dashboard has data. The last one is won but NOT reconciled: it matches
data/demo/hoa-don-nha-xe.csv for trying the reconcile flow by hand.
"""
import os
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.auth import hash_password
from app.db.session import SessionLocal
from app.adapters.llm.provider import NotConfiguredLLMProvider
from app.models.entities import CostActual, OperatorOrg, Quote, RateCard, RateCardItem, TourTemplate, User
from app.services.quote import quote_service as qs
from app.services.quote.reconciliation import match
from app.services.quote.request_parser import QuoteRequest

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
    ("Homestay Vườn Dừa Bến Tre", "hotel", [
        ("hotel-mekong-4-sao", "Phòng đôi Resort 4★ Mekong (gồm ăn sáng)", "per_room_night", 900_000, None, 2, {}),
        ("hotel-mekong-homestay", "Phòng đôi homestay vườn dừa 3★ (gồm ăn sáng)", "per_room_night", 650_000, None, 2, {})]),
    ("Chính sách phụ thu", "surcharge", [
        ("surcharge-weekend", "Phụ thu cuối tuần", "pct", 10, None, None, {"weekdays": ["sat", "sun"], "applies_to": BEFORE_SURCHARGE}),
        ("surcharge-holiday", "Phụ thu ngày lễ", "pct", 25, None, None, {"holiday": True, "applies_to": BEFORE_SURCHARGE}),
        ("surcharge-tet", "Phụ thu Tết Nguyên Đán", "pct", 50, None, None, {"tet": True, "applies_to": BEFORE_SURCHARGE})]),
]


def _stop(name: str, ticket: str | None = None, price: int | None = None) -> dict:
    return {"name": name, **({"ticket_code": ticket} if ticket else {}), **({"price_vnd": price} if price else {})}


def _day(title: str, legs: list[tuple[str, str, int]], stops: list[dict]) -> dict:
    return {"title": title, "legs": [{"from": a, "to": b, "distance_km": km} for a, b, km in legs], "stops": stops}


CU_CHI, MEKONG, CAN_GIO = "ticket-dia-dao-cu-chi", "ticket-thuyen-mekong", "ticket-can-gio"
# (code, name, days, destinations, meals per guest in total, day plans). Distances are one-way road estimates from HCMC.
TEMPLATES = [
    ("cu-chi-1n", "Củ Chi 1 ngày", 1, ["cu_chi"], 1, [_day("TP.HCM - Địa đạo Củ Chi - TP.HCM", [("TP.HCM", "Củ Chi", 70), ("Củ Chi", "TP.HCM", 70)], [_stop("Địa đạo Củ Chi", CU_CHI)])]),
    ("mekong-1n", "Mekong 1 ngày", 1, ["mekong"], 1, [_day("TP.HCM - Mỹ Tho - Bến Tre - TP.HCM", [("TP.HCM", "Mỹ Tho", 70), ("Mỹ Tho", "Bến Tre", 20), ("Bến Tre", "TP.HCM", 85)], [_stop("Thuyền sông Mekong", MEKONG)])]),
    ("cu-chi-mekong-2n1d", "Củ Chi - Mekong 2N1Đ", 2, ["cu_chi", "mekong"], 3, [
        _day("TP.HCM - Củ Chi - Mỹ Tho", [("TP.HCM", "Củ Chi", 70), ("Củ Chi", "Mỹ Tho", 100)], [_stop("Địa đạo Củ Chi", CU_CHI)]),
        _day("Mỹ Tho - Bến Tre - TP.HCM", [("Mỹ Tho", "Bến Tre", 20), ("Bến Tre", "TP.HCM", 85)], [_stop("Thuyền sông Mekong", MEKONG)])]),
    ("can-gio-1n", "Cần Giờ 1 ngày", 1, ["can_gio"], 1, [_day("TP.HCM - Cần Giờ - TP.HCM", [("TP.HCM", "Cần Giờ", 60), ("Cần Giờ", "TP.HCM", 60), ("Cần Giờ", "Cần Giờ", 20)], [_stop("Rừng ngập mặn Cần Giờ", CAN_GIO)])]),
    ("vung-tau-2n1d", "Vũng Tàu 2N1Đ", 2, ["vung_tau"], 3, [
        _day("TP.HCM - Vũng Tàu", [("TP.HCM", "Vũng Tàu", 100), ("Vũng Tàu", "Vũng Tàu", 20)], [_stop("Tượng Chúa Kitô Vua")]),
        _day("Vũng Tàu - TP.HCM", [("Vũng Tàu", "Vũng Tàu", 20), ("Vũng Tàu", "TP.HCM", 100)], [_stop("Bãi Sau")])]),
    ("city-tour-1n", "City tour TP.HCM 1 ngày", 1, ["city"], 1, [_day("Trung tâm TP.HCM", [("TP.HCM", "TP.HCM", 40)], [_stop("Dinh Độc Lập", price=65_000), _stop("Bảo tàng Chứng tích Chiến tranh", price=40_000)])]),
]


# Multi-day templates pin their room item, otherwise the engine would price the cheapest room of any province.
HOTEL_CODE = {"cu-chi-mekong-2n1d": "hotel-mekong-4-sao", "vung-tau-2n1d": "hotel-vung-tau-3-sao"}


# (key, customer, request, tweak). tweak builds the synthetic supplier invoice from the quote's own cost lines:
# scale = price per category, qty = quantity per category, no_surcharge = bill the base amount only, drop = not billed, extra = billed but unquoted.
DEMO_HISTORY = [
    ("cu-chi-gia-xe-tang", "[Demo] Công ty Minh Phát", dict(pax=30, days=1, start_date="2026-09-15", segment="corporate", destinations=["cu_chi"]),
     {"scale": {"vehicle": 1.10}}),
    ("mekong-phi-ben", "[Demo] Trường THCS Lê Lợi", dict(pax=25, days=1, start_date="2026-09-22", segment="school", destinations=["mekong"]),
     {"extra": [("ticket", "Phí neo bến và gửi xe", 450_000)]}),
    ("cu-chi-mekong-them-khach", "[Demo] Công ty Hải Âu", dict(pax=32, days=2, start_date="2026-10-07", segment="corporate", destinations=["cu_chi", "mekong"]),
     {"qty": {"meal": 1.06}, "scale": {"hotel": 1.05}}),
    ("can-gio-khong-dung-hdv", "[Demo] Gia đình anh Nam", dict(pax=20, days=1, start_date="2026-10-14", segment="family", destinations=["can_gio"]),
     {"drop": ["guide"]}),
    ("city-tour-dung-bao-gia", "[Demo] Đoàn công đoàn Sao Mai", dict(pax=18, days=1, start_date="2026-08-26", segment="corporate", destinations=["city"]), {}),
    ("vung-tau-phu-thu-cuoi-tuan", "[Demo] Công ty Bình An", dict(pax=28, days=2, start_date="2026-10-24", segment="corporate", destinations=["vung_tau"]),
     {"no_surcharge": ["vehicle"]}),
    ("chua-doi-chieu", "[Demo] Công ty Đại Nam (chưa đối chiếu)", dict(pax=24, days=1, start_date="2026-10-20", segment="corporate", destinations=["cu_chi"]), None),
]


def _invoice_lines(cost_lines: list[dict], tweak: dict) -> list[dict]:
    out = []
    for ln in cost_lines:
        c = ln["category"]
        if c in tweak.get("drop", []):
            continue
        qty, amount = ln["qty"], ln["total_vnd"]
        if c in tweak.get("qty", {}):
            qty = round(qty * tweak["qty"][c])
            amount = round(ln["total_vnd"] * qty / ln["qty"] / 1000) * 1000
        if c in tweak.get("scale", {}):
            amount = round(amount * tweak["scale"][c] / 1000) * 1000
        if c in tweak.get("no_surcharge", []):
            amount = ln["amount_vnd"]
        out.append({"category": c, "label": ln["label"], "amount_vnd": amount, "conditions": {"qty": qty, "unit_price_vnd": amount // qty}})
    out += [{"category": c, "label": label, "amount_vnd": amount, "conditions": {"qty": 1, "unit_price_vnd": amount}} for c, label, amount in tweak.get("extra", [])]
    return out


def _seed_history(db, org: OperatorOrg, user: User) -> int:
    made = 0
    for key, customer, request, tweak in DEMO_HISTORY:
        if db.scalar(select(Quote.id).where(Quote.org_id == org.id, Quote.raw_message == f"DEMO-HISTORY:{key}")):
            continue
        req = QuoteRequest(**{**request, "start_date": date.fromisoformat(request["start_date"]), "customer_name": customer})
        result = qs.draft_from_request(db, org, req, "portal", None, user, provider=NotConfiguredLLMProvider(),
                                       raw_message=f"DEMO-HISTORY:{key}", today=date.fromisoformat(request["start_date"]).replace(day=1))
        q = result.quote
        q.status, q.accepted_at = "won", datetime.now(timezone.utc)
        if tweak is not None:
            rows = match(q.cost["lines"], _invoice_lines(q.cost["lines"], tweak))
            for row in rows:
                db.add(CostActual(org_id=org.id, quote_id=q.id, confirmed=True, **row))
            q.actual_cost_vnd = sum(r["actual_vnd"] for r in rows)
        db.commit()
        made += 1
    return made


def seed(session_factory=SessionLocal, history: bool = False) -> dict:
    """``history`` adds the demo completed tours; off by default so tests that count quotes are unaffected."""
    created = {"org": False, "user": False, "cards": 0, "templates": 0, "history": 0}
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
        for code, name, days, destinations, meals, plan in TEMPLATES:
            existing = db.scalar(select(TourTemplate).where(TourTemplate.org_id == org.id, TourTemplate.code == code))
            itinerary = {"destinations": destinations, "days": plan, **({"hotel_code": HOTEL_CODE[code]} if code in HOTEL_CODE else {})}
            if existing is not None:
                if existing.itinerary != itinerary:  # older seeds lacked hotel_code
                    existing.itinerary = itinerary
                continue
            db.add(TourTemplate(org_id=org.id, code=code, name=name, days=days, meal_plan={"meals": meals}, itinerary=itinerary))
            created["templates"] += 1
        db.commit()
        if history:
            created["history"] = _seed_history(db, org, db.scalar(select(User).where(User.email == EMAIL)))
    return created


if __name__ == "__main__":
    result = seed(history=True)
    print(f"Seeded: {result}")
    print(f"Operator login: {EMAIL} / {PASSWORD}  (org: {ORG_NAME})")
