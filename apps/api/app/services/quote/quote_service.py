"""Draft a quote from a customer request: parse -> template -> rate items -> cost -> price curve -> explanation -> persist.

Channel-agnostic (portal now, Zalo/Telegram bots later): callers pass the LLM provider and get either a persisted
draft or the clarifying questions to send back instead of a price.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.request_context import current_request_id
from app.models.entities import AuditLog, OperatorOrg, Quote, QuoteRevision, TourTemplate, User
from app.services.quote.cost_engine import CostBreakdown, MissingRateError, QuoteRequestLite, compute_cost
from app.services.quote.explainer import explain
from app.services.quote.pricing import optimize
from app.services.quote.request_parser import QuoteRequest, clarifying_questions, finalize, parse_request
from app.services.quote.vn_calendar import day_flags
from app.services.quote.win_model import predict_p_win
from app.services.rate_cards import active_rate_items

MODES = ("safe", "balanced", "max_profit")
RAIN_BY_MONTH = (0.10, 0.05, 0.08, 0.18, 0.55, 0.75, 0.78, 0.78, 0.80, 0.75, 0.45, 0.20)  # same HCMC climatology as scripts/generate_quote_history.py
DEFAULT_RESPONSE_TIME_H = 3.0  # ~ median of the synthetic training distribution


class CustomTourNotSupported(Exception):
    """No tour template fits the request. Designing a bespoke tour (trip agent -> cost-engine itinerary) is not built yet."""


class NoRates(Exception):
    """The org has no active rate card covering the departure date, or a needed category is missing."""


@dataclass
class DraftResult:
    request: QuoteRequest
    parser: str  # "llm" | "offline" | "given"
    questions: list[str]
    quote: Quote | None = None


def select_template(templates: list[TourTemplate], req: QuoteRequest) -> TourTemplate | None:
    """Same day count and at least one shared destination; best = most shared, fewest extra; ties by code."""
    wanted = set(req.destinations)
    scored = []
    for t in templates:
        have = set(t.itinerary.get("destinations", []))
        if t.days == req.days and wanted & have:
            scored.append((-(len(wanted & have) * 10 - len(have - wanted)), t.code, t))
    return min(scored, key=lambda x: x[:2])[2] if scored else None


def cost_payload(cost: CostBreakdown, items) -> dict:
    labels = {i.code: (i.label, i.amount_vnd) for i in items if i.category == "surcharge"}
    surcharges = []
    for code, (label, pct) in labels.items():
        hit = [line for line in cost.lines if code in line.surcharge_codes]
        if hit:
            # A line's surcharge_vnd mixes every surcharge on it; split by pct for display (exact when only one applies).
            amount = sum(round(ln.surcharge_vnd * pct / sum(labels[c][1] for c in ln.surcharge_codes)) for ln in hit)
            surcharges.append({"code": code, "label": label, "pct": pct, "amount_vnd": amount})
    return {
        "pax": cost.pax, "total": cost.total, "fixed_total": cost.fixed_total, "variable_total": cost.variable_total,
        "variable_per_pax": cost.variable_per_pax, "surcharges": surcharges,
        "lines": [{"category": ln.category, "label": ln.label, "rate_item_id": ln.rate_item_id, "card_version": ln.card_version,
                   "qty": ln.qty, "unit_vnd": ln.unit_vnd, "amount_vnd": ln.amount_vnd, "fixed": ln.fixed,
                   "surcharge_vnd": ln.surcharge_vnd, "surcharge_codes": list(ln.surcharge_codes), "total_vnd": ln.total_vnd}
                  for ln in cost.lines],
    }


def price(cost_total: int, req: QuoteRequest, floor_margin_pct: int, today: date) -> dict:
    depart = req.start_date
    ctx = {"days": req.days, "lead_days": max(0, (depart - today).days), "segment": req.segment, "destination": req.destinations[0],
           **day_flags(depart), "competitor_price_index": 1.0, "rain_prob": RAIN_BY_MONTH[depart.month - 1],
           "response_time_h": DEFAULT_RESPONSE_TIME_H}
    sources = set()

    def p_win(features: dict) -> float:
        out = predict_p_win(features)
        sources.add(out["source"])
        return out["p_win"]

    # org.margin_floor_pct is a margin on price; the optimizer's floor is a markup on cost: price >= cost / (1 - margin).
    m = floor_margin_pct / 100
    result = optimize(cost_total, req.pax, ctx, m / (1 - m), p_win)
    modes = {k: result[k] for k in MODES}
    return {"floor_margin_pct": floor_margin_pct, "source": "model" if sources == {"model"} else "heuristic",
            "modes": modes, "curve": result["curve"]}


def _audit(db: Session, actor: User | None, action: str, quote: Quote, details: dict) -> None:
    if request_id := current_request_id.get():
        details = {**details, "request_id": request_id}
    db.add(AuditLog(id=str(uuid4()), actor_id=actor.id if actor else None, action=action, target_type="quote",
                    target_id=quote.id, details=details, created_at=datetime.now(timezone.utc)))


def snapshot(q: Quote) -> dict:
    return {"request": q.request, "itinerary": q.itinerary, "cost": q.cost, "pricing": q.pricing, "price_vnd": q.price_vnd,
            "price_mode": q.price_mode, "explanation": q.explanation, "rate_card_versions": q.rate_card_versions}


def add_revision(db: Session, q: Quote, user: User | None) -> None:
    db.add(QuoteRevision(id=str(uuid4()), quote_id=q.id, org_id=q.org_id, revision=q.revision, snapshot=snapshot(q),
                         created_by=user.id if user else None))


def _next_code(db: Session, org: OperatorOrg, year: int) -> str:
    codes = db.scalars(select(Quote.code).where(Quote.org_id == org.id, Quote.code.like(f"Q-{year}-%"))).all()
    return f"Q-{year}-{max((int(c.rsplit('-', 1)[1]) for c in codes), default=0) + 1:04d}"


def draft_from_request(db: Session, org: OperatorOrg, req: QuoteRequest, channel: str, contact: str | None, user: User | None, *,
                       provider, raw_message: str | None = None, parser: str = "given", today: date | None = None) -> DraftResult:
    today = today or date.today()
    req = finalize(req.model_copy(deep=True))
    if req.missing_fields:
        return DraftResult(req, parser, clarifying_questions(req))
    templates = db.scalars(select(TourTemplate).where(TourTemplate.org_id == org.id)).all()
    template = select_template(templates, req)
    if template is None:
        raise CustomTourNotSupported("Chưa hỗ trợ tour thiết kế riêng: không có lịch trình mẫu khớp điểm đến và số ngày.")
    items = active_rate_items(db, org.id, req.start_date)
    if not items:
        raise NoRates("Chưa có bảng giá nhà cung cấp đang hiệu lực cho ngày khởi hành.")
    meals = 0 if req.meal_plan == "none" else int(template.meal_plan.get("meals", 0))
    try:
        cost = compute_cost(template.itinerary, QuoteRequestLite(req.pax, req.days, meals), items, req.start_date)
    except MissingRateError as error:
        raise NoRates(f"Bảng giá còn thiếu: {error}.") from error
    cost_json = cost_payload(cost, items)
    pricing = price(cost.total, req, org.margin_floor_pct, today)
    mode = "balanced"
    explanation, _ = explain(provider, req.model_dump(mode="json"), cost_json, pricing, mode)
    used = {ln.rate_item_id for ln in cost.lines} | {i.id for i in items if i.code in {s["code"] for s in cost_json["surcharges"]}}
    now = datetime.now(timezone.utc)
    quote = Quote(
        id=str(uuid4()), org_id=org.id, code=_next_code(db, org, today.year), status="draft", channel=channel,
        customer_name=req.customer_name, customer_contact=contact, raw_message=raw_message, received_at=now,
        request=req.model_dump(mode="json"), itinerary={"template_code": template.code, "template_name": template.name, **template.itinerary},
        cost=cost_json, pricing=pricing, cost_total_vnd=cost.total, price_vnd=pricing["modes"][mode]["total"], price_mode=mode,
        rate_card_versions={f"{i.supplier}|{i.category}": i.card_version for i in items if i.id in used},
        margin_floor_pct=org.margin_floor_pct, explanation=explanation, revision=1, created_by=user.id if user else None)
    db.add(quote)
    db.flush()
    add_revision(db, quote, user)
    _audit(db, user, "quote.created", quote, {"code": quote.code, "channel": channel, "template": template.code, "parser": parser})
    db.commit()
    return DraftResult(req, parser, [], quote)


def draft_from_message(db: Session, org: OperatorOrg, text: str, channel: str, contact: str | None, user: User | None, *,
                       provider, today: date | None = None) -> DraftResult:
    today = today or date.today()
    req, parser = parse_request(provider, text, today)
    return draft_from_request(db, org, req, channel, contact, user, provider=provider, raw_message=text, parser=parser, today=today)
