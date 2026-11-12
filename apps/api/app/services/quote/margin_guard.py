"""M8 Margin Guard: re-cost an open quote, flag margin below the org floor, and propose deterministic rescue options.

Every number comes from compute_cost; the LLM never prices anything. Margin is on price: (price - cost) / price.
Edits that a customer already saw (sent/viewed/accepted/deposit_paid) keep the selling price and only move the margin.
"""
from datetime import date, timedelta
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import OperatorOrg, Quote, User
from app.services.quote import quote_service as qs
from app.services.quote.cost_engine import CostBreakdown, MissingRateError, QuoteRequestLite, compute_cost
from app.services.quote.explainer import explain
from app.services.quote.request_parser import QuoteRequest
from app.services.quote.win_model import build_features, predict_p_win
from app.services.rate_cards import active_rate_items

OPEN_STATUSES = ("draft", "sent", "viewed", "accepted", "deposit_paid")
OVERRIDE_KEYS = ("vehicle_seats", "meal_code", "hotel_code")
SHIFT_DAYS = (-3, -2, -1, 1, 2, 3)
STEP = 10_000


def margin_pct(price: int | None, cost: int) -> float | None:
    return round((price - cost) / price * 100, 2) if price else None


def margin_alert(q: Quote, floor_pct: int | None = None) -> dict | None:
    floor = q.margin_floor_pct if floor_pct is None else floor_pct
    m = margin_pct(q.price_vnd, q.cost_total_vnd)
    if m is None or m >= floor:
        return None
    return {"margin_pct": m, "floor_pct": floor, "shortfall_vnd": min_price(q.cost_total_vnd, floor) - q.price_vnd}


def min_price(cost: int, floor_pct: int) -> int:
    """Smallest total price whose margin on price is at least floor_pct."""
    return -(-cost * 100 // (100 - floor_pct))


def _meals_per_guest(q: Quote) -> int:
    line = next((ln for ln in q.cost["lines"] if ln["category"] == "meal" and not ln["fixed"]), None)
    return line["qty"] // q.request["pax"] if line else 0


def cost_for(q: Quote, items, *, pax=None, start_date=None, overrides=None, days_plan=None) -> tuple[CostBreakdown, dict, dict]:
    """Cost of the quote with edits applied, without touching it. -> (cost, new request dict, new itinerary dict)."""
    req = dict(q.request)
    merged = {**req.get("overrides", {}), **(overrides or {})}
    req["overrides"] = {k: v for k, v in merged.items() if v is not None}
    meals = _meals_per_guest(q)  # read before pax changes
    req["pax"] = pax or req["pax"]
    if start_date:
        req["start_date"] = start_date.isoformat()
    itin = {**q.itinerary, **({"days": days_plan} if days_plan else {})}
    o = req["overrides"]
    lite = QuoteRequestLite(req["pax"], req["days"], meals, 1, o.get("meal_code"), o.get("vehicle_seats"), o.get("hotel_code"))
    return compute_cost(itin, lite, items, date.fromisoformat(req["start_date"])), req, itin


def _cost_or_none(q, items, **kw) -> CostBreakdown | None:
    try:
        return cost_for(q, items, **kw)[0]
    except MissingRateError:
        return None


def recost(db: Session, org: OperatorOrg, q: Quote, provider, user: User | None, reason: str, today: date, *, pax=None, start_date=None,
           overrides=None, days_plan=None, keep_price: bool = False) -> dict | None:
    """Apply edits, store a revision and return the margin alert (also audited) or None. Caller commits."""
    depart = start_date or date.fromisoformat(q.request["start_date"])
    items = active_rate_items(db, org.id, depart)
    if not items:
        raise qs.NoRates("Chưa có bảng giá nhà cung cấp đang hiệu lực cho ngày khởi hành.")
    try:
        cost, req, itin = cost_for(q, items, pax=pax, start_date=start_date, overrides=overrides, days_plan=days_plan)
    except MissingRateError as error:
        raise qs.NoRates(f"Bảng giá còn thiếu: {error}.") from error
    old_cost, old_price = q.cost_total_vnd, q.price_vnd
    cost_json = qs.cost_payload(cost, items)
    q.request, q.itinerary, q.cost, q.cost_total_vnd = req, itin, cost_json, cost.total
    q.rate_card_versions, q.margin_floor_pct = qs.used_versions(cost, cost_json, items), org.margin_floor_pct
    if q.status == "draft":  # nothing shown to the customer yet: re-optimize the price curve, the price follows unless kept
        q.pricing = qs.price(cost.total, QuoteRequest(**req), org.margin_floor_pct, today)
        if not keep_price:
            q.price_vnd = q.pricing["modes"][q.price_mode]["total"]
            q.explanation, _ = explain(provider, req, cost_json, q.pricing, q.price_mode)
    q.revision += 1
    qs.add_revision(db, q, user, reason)
    qs._audit(db, user, "quote.repriced", q, {"reason": reason, "old_cost_vnd": old_cost, "new_cost_vnd": cost.total,
                                              "old_price_vnd": old_price, "new_price_vnd": q.price_vnd})
    alert = margin_alert(q, org.margin_floor_pct)
    if alert:
        qs._audit(db, user, "quote.margin_alert", q, {**alert, "reason": reason})
    return alert


def requote_for_card(db: Session, org: OperatorOrg, card, provider, user: User | None, today: date) -> dict:
    """Re-cost every open, not-yet-departed quote whose cost used the approved card's supplier+category.

    ponytail: synchronous and one pass per quote (each loads the rate items once); move to the worker past a few hundred open quotes.
    """
    key = f"{card.supplier}|{card.category}"
    rows = db.scalars(select(Quote).where(Quote.org_id == org.id, Quote.status.in_(OPEN_STATUSES)).order_by(Quote.code)).all()
    changed, alerts = [], []
    for q in rows:
        if key not in q.rate_card_versions or date.fromisoformat(q.request["start_date"]) < today:
            continue
        old = q.cost_total_vnd
        try:
            alert = recost(db, org, q, provider, user, f"Bảng giá {card.supplier} ({card.category}) v{card.version} được duyệt", today)
        except qs.NoRates:
            continue
        changed.append({"quote_id": q.id, "code": q.code, "status": q.status, "old_cost_vnd": old, "new_cost_vnd": q.cost_total_vnd,
                        "margin_pct": margin_pct(q.price_vnd, q.cost_total_vnd)})
        if alert:
            alerts.append({"quote_id": q.id, "code": q.code, **alert})
    return {"requoted": len(changed), "quotes": changed, "alerts": alerts}


# ---- rescue ---------------------------------------------------------------------------------------------------------

def _option(q, code, title, changes, cost: CostBreakdown, visible: bool, price=None, p_win=None) -> dict:
    price = price or q.price_vnd
    out = {"code": code, "title": title, "changes": changes, "new_cost_vnd": cost.total, "savings_vnd": q.cost_total_vnd - cost.total,
           "new_margin_pct": margin_pct(price, cost.total), "new_price_vnd": price, "customer_visible": visible}
    return out if p_win is None else {**out, "p_win": p_win}


def _cheaper_tier(q, items, category: str, override: str, title: str) -> dict | None:
    line = next((ln for ln in q.cost["lines"] if ln["category"] == category), None)  # first line = the guests' line, not the guide FOC one
    unit = "per_room_night" if category == "hotel" else "per_pax"
    current = next((i for i in items if line and i.id == line["rate_item_id"]), None)
    if current is None:
        return None
    best = None
    for alt in (i for i in items if i.category == category and i.unit == unit and i.supplier == current.supplier
                and i.experience_id is None and i.amount_vnd < current.amount_vnd):
        cost = _cost_or_none(q, items, overrides={override: alt.code})
        if cost and (best is None or cost.total < best[1].total):
            best = (alt, cost)
    if best is None:
        return None
    alt, cost = best
    return _option(q, f"{category}_tier", f"{title}: {alt.label}", {"overrides": {override: alt.code}}, cost, True)


def rescue_options(db: Session, org: OperatorOrg, q: Quote, today: date) -> list[dict]:
    depart = date.fromisoformat(q.request["start_date"])
    items = active_rate_items(db, org.id, depart)
    out: list[dict] = []
    if not items:
        return out
    # 1. Drop a pinned vehicle size: the engine then picks the cheapest combination that seats everyone.
    if q.request.get("overrides", {}).get("vehicle_seats"):
        cost = _cost_or_none(q, items, overrides={"vehicle_seats": None})
        if cost:
            out.append(_option(q, "vehicle_optimal", "Dùng tổ hợp xe rẻ nhất vẫn đủ chỗ", {"overrides": {"vehicle_seats": None}}, cost, False))
    # 2. Shift the departure by 1..3 days (never into the past); rates and surcharges are re-read for the new date.
    best = None
    for d in SHIFT_DAYS:
        new = depart + timedelta(days=d)
        if new < today:
            continue
        cost = _cost_or_none(q, active_rate_items(db, org.id, new), start_date=new)
        if cost and (best is None or (cost.total, abs(d), d) < (best[1].total, abs(best[0]), best[0])):
            best = (d, cost, new)
    if best:
        d, cost, new = best
        out.append(_option(q, "shift_date", f"Dời khởi hành {abs(d)} ngày {'sớm' if d < 0 else 'muộn'} hơn, sang {new.strftime('%d/%m/%Y')}",
                           {"start_date": new.isoformat(), "shift_days": d}, cost, True))
    # 3. Lower meal / hotel tier among items of the same supplier.
    for opt in (_cheaper_tier(q, items, "meal", "meal_code", "Hạ hạng bữa ăn"), _cheaper_tier(q, items, "hotel", "hotel_code", "Hạ hạng khách sạn")):
        if opt:
            out.append(opt)
    out = sorted((o for o in out if o["savings_vnd"] > 0), key=lambda o: (-o["savings_vnd"], o["code"]))
    # 4. Smallest price (rounded up to 10,000 VND per guest) that restores the floor, with its P(win).
    need = min_price(q.cost_total_vnd, org.margin_floor_pct)
    if q.price_vnd and q.price_vnd < need:
        pax = q.request["pax"]
        per_pax = ceil(need / pax / STEP) * STEP
        ctx = {**qs.price_context(QuoteRequest(**q.request), today), "pax": pax}
        p = float(predict_p_win(build_features(ctx, q.cost_total_vnd, per_pax))["p_win"])
        cost = cost_for(q, items)[0]
        out.append(_option(q, "raise_price", f"Tăng giá lên {per_pax * pax:,} đ để về mức sàn".replace(",", "."),
                           {"price_vnd": per_pax * pax}, cost, True, price=per_pax * pax, p_win=round(p, 4)))
    return out


def apply_rescue(db: Session, org: OperatorOrg, q: Quote, option: dict, provider, user: User | None, today: date, confirm_resend: bool) -> dict:
    """-> {"applied", "requires_resend"}. Customer-visible options on a sent/viewed quote need confirm_resend: they pull the
    quote back to draft and kill the old link, so the customer never sees a changed price or itinerary on a link they already hold."""
    reason = f"Cứu margin: {option['title']}"
    seen = q.status in ("sent", "viewed")
    if option["customer_visible"] and seen and not confirm_resend:
        return {"applied": False, "requires_resend": True}
    c = option["changes"]
    if option["customer_visible"] and seen:
        q.status, q.public_token_hash = "draft", None
    if "price_vnd" in c:
        q.price_vnd = c["price_vnd"]
        q.revision += 1
        qs.add_revision(db, q, user, reason)
        qs._audit(db, user, "quote.repriced", q, {"reason": reason, "new_price_vnd": q.price_vnd})
    else:
        recost(db, org, q, provider, user, reason, today, start_date=date.fromisoformat(c["start_date"]) if "start_date" in c else None,
               overrides=c.get("overrides"), keep_price=True)
    qs._audit(db, user, "quote.rescue_applied", q, {"code": option["code"], "changes": c})
    return {"applied": True, "requires_resend": option["customer_visible"] and seen}
