"""Quote drafting for operators (M5) and the pricing curve (M7)."""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_llm_provider
from app.api.guards import require_user
from app.api.permissions import P
from app.api.routes.operator import _org
from app.core.config import settings
from app.models.entities import AuditLog, OperatorOrg, PaymentTransaction, Quote, QuoteRevision, User
from app.services.quote import margin_guard as mg
from app.services.quote import quote_service as qs
from app.services.quote.explainer import explain, explain_rescue
from app.services.quote.request_parser import QuoteRequest, clarifying_questions, finalize, parse_request

router = APIRouter(prefix="/api", tags=["operator quotes"])
OPEN_STATUSES = mg.OPEN_STATUSES


def _fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


class QuoteCreate(BaseModel):
    message: str | None = Field(default=None, min_length=3, max_length=4000)
    request: QuoteRequest | None = None  # a request the operator has confirmed/edited; wins over parsing ``message``
    customer_contact: str | None = Field(default=None, max_length=255)
    parse_only: bool = False  # return the parsed request (and questions) without creating a quote

    @model_validator(mode="after")
    def _one_source(self):
        if not (self.message or self.request):
            raise ValueError("Cần message hoặc request.")
        return self


class ModeBody(BaseModel):
    mode: str = Field(pattern="^(safe|balanced|max_profit)$")


class Stop(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    ticket_code: str | None = Field(default=None, max_length=120)
    price_vnd: int | None = Field(default=None, ge=0, le=100_000_000)
    price_basis: str | None = Field(default=None, pattern="^(per_person|per_group)$")


class Leg(BaseModel):
    from_: str = Field(alias="from", max_length=120)
    to: str = Field(max_length=120)
    distance_km: float = Field(ge=0, le=2000)


class Day(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    legs: list[Leg] = Field(max_length=20)
    stops: list[Stop] = Field(max_length=20)


class Overrides(BaseModel):
    vehicle_seats: int | None = Field(default=None, ge=1, le=100)  # None clears the override
    meal_code: str | None = Field(default=None, max_length=120)
    hotel_code: str | None = Field(default=None, max_length=120)


class QuotePatch(BaseModel):
    pax: int | None = Field(default=None, ge=1, le=60)
    start_date: date | None = None
    overrides: Overrides | None = None
    itinerary_days: list[Day] | None = Field(default=None, max_length=3)  # same day count as the quote; legs/stops as the cost engine reads them
    reason: str | None = Field(default=None, max_length=255)


class RescueApply(BaseModel):
    confirm_resend: bool = False


class MarkBody(BaseModel):
    outcome: str = Field(pattern="^(won|lost)$")
    reason: str | None = Field(default=None, max_length=255)


def quote_summary(q: Quote) -> dict:
    return {"id": q.id, "code": q.code, "status": q.status, "channel": q.channel, "customer_name": q.customer_name,
            "pax": q.request.get("pax"), "days": q.request.get("days"), "start_date": q.request.get("start_date"),
            "destinations": q.request.get("destinations", []), "price_vnd": q.price_vnd, "price_mode": q.price_mode,
            "cost_total_vnd": q.cost_total_vnd, "margin_pct": mg.margin_pct(q.price_vnd, q.cost_total_vnd), "created_at": q.created_at}


def quote_payload(q: Quote, floor_pct: int | None = None) -> dict:
    return {**quote_summary(q), "margin_alert": mg.margin_alert(q, floor_pct), "customer_contact": q.customer_contact, "raw_message": q.raw_message, "received_at": q.received_at,
            "request": q.request, "itinerary": q.itinerary, "cost": q.cost, "pricing": {k: v for k, v in q.pricing.items() if k != "curve"},
            "rate_card_versions": q.rate_card_versions, "margin_floor_pct": q.margin_floor_pct, "explanation": q.explanation,
            "lost_reason": q.lost_reason, "accepted_at": q.accepted_at, "revision": q.revision,
            "sent_at": q.sent_at, "expires_at": q.expires_at, "first_viewed_at": q.first_viewed_at, "view_count": q.view_count}


def _quote(db: Session, org: OperatorOrg, quote_id: str) -> Quote:
    q = db.scalar(select(Quote).where(Quote.id == quote_id, Quote.org_id == org.id))
    if q is None:
        raise _fail(404, "QUOTE_NOT_FOUND", "Không tìm thấy báo giá.")
    return q


@router.post("/operator/quotes")
def create_quote(body: QuoteCreate, response: Response, user: User = Depends(require_user(P.OPERATOR_QUOTE)),
                 db: Session = Depends(get_db), provider=Depends(get_llm_provider)):
    """201 + quote when drafted; 200 + questions when required fields are missing; 200 + request when parse_only."""
    org = _org(db, user)
    today = date.today()
    if body.request is not None:
        req, parser = finalize(body.request), "given"
    else:
        req, parser = parse_request(provider, body.message, today)
    if body.parse_only:
        return {"quote": None, "request": req, "parser": parser, "questions": clarifying_questions(req)}
    try:
        result = qs.draft_from_request(db, org, req, "portal", body.customer_contact, user, provider=provider,
                                       raw_message=body.message, parser=parser, today=today)
    except qs.CustomTourNotSupported as error:
        raise _fail(501, "CUSTOM_TOUR_UNSUPPORTED", str(error))
    except qs.NoRates as error:
        raise _fail(422, "NO_RATES", str(error))
    if result.quote is not None:
        response.status_code = 201
    return {"quote": quote_payload(result.quote) if result.quote else None, "request": result.request, "parser": result.parser,
            "questions": result.questions}


@router.get("/operator/quotes")
def list_quotes(status: str | None = Query(default=None), needs_followup: bool | None = Query(default=None),
                user: User = Depends(require_user(P.OPERATOR_QUOTE)), db: Session = Depends(get_db)):
    """``needs_followup``: sent/viewed quotes matching a rule of ``quote_service.followup_reason``, each with a reminder text."""
    org = _org(db, user)
    stmt = select(Quote).where(Quote.org_id == org.id).order_by(Quote.created_at.desc(), Quote.code.desc())
    if status:
        stmt = stmt.where(Quote.status == status)
    rows = db.scalars(stmt.limit(200)).all()
    now = datetime.now(timezone.utc)
    if any([qs.expire_due(q, now) for q in rows]):
        db.commit()
    if status:
        rows = [q for q in rows if q.status == status]
    if not needs_followup:
        return [quote_summary(q) for q in rows]
    out = []
    for q in rows:
        if reason := qs.followup_reason(q, now):
            out.append({**quote_summary(q), "followup_reason": reason, "reminder_text": qs.reminder_text(q, reason),
                        "sent_at": q.sent_at, "first_viewed_at": q.first_viewed_at, "expires_at": q.expires_at})
    return out


@router.get("/operator/quotes/intake-inbox")
def intake_inbox(user: User = Depends(require_user(P.OPERATOR_QUOTE)), db: Session = Depends(get_db)):
    """Bot requests that could not be drafted (custom tour, missing rates): a human must answer them. Last 30 days."""
    org = _org(db, user)
    since = datetime.now(timezone.utc) - timedelta(days=30)
    rows = db.scalars(select(AuditLog).where(AuditLog.action == "quote.intake_needs_human", AuditLog.target_id == org.id,
                                             AuditLog.created_at >= since).order_by(AuditLog.created_at.desc()).limit(100)).all()
    return [{"id": r.id, "created_at": r.created_at, **r.details} for r in rows]


@router.get("/operator/quotes/{quote_id}")
def get_quote(quote_id: str, user: User = Depends(require_user(P.OPERATOR_QUOTE)), db: Session = Depends(get_db)):
    org = _org(db, user)
    q = _quote(db, org, quote_id)
    if qs.expire_due(q, datetime.now(timezone.utc)):
        db.commit()
    paid = db.scalar(select(PaymentTransaction.updated_at).where(PaymentTransaction.quote_id == q.id, PaymentTransaction.status == "succeeded")
                     .order_by(PaymentTransaction.updated_at).limit(1))
    return {**quote_payload(q, org.margin_floor_pct), "deposit_pct": org.deposit_pct, "deposit_vnd": qs.deposit_vnd(q.price_vnd, org.deposit_pct) if q.price_vnd else None,
            "deposit_paid_at": paid if q.status == "deposit_paid" else None}


@router.post("/operator/quotes/{quote_id}/send")
def send_quote(quote_id: str, user: User = Depends(require_user(P.OPERATOR_QUOTE)), db: Session = Depends(get_db)):
    """Issue the customer link (re-sending rotates it and renews the validity). The plain URL is returned only here."""
    org = _org(db, user)
    q = _quote(db, org, quote_id)
    if q.status not in ("draft", "sent", "viewed", "expired"):
        raise _fail(409, "QUOTE_LOCKED", "Báo giá đã được khách chấp nhận hoặc đã đóng, không gửi lại được.")
    token = qs.send(db, org, q, user)
    url = f"{settings.web_app_url.rstrip('/')}/q/{token}"
    return {"quote": quote_payload(q), "share_url": url, "message": qs.share_message(org, q, url)}


@router.post("/operator/quotes/{quote_id}/select-mode")
def select_mode(quote_id: str, body: ModeBody, user: User = Depends(require_user(P.OPERATOR_QUOTE)), db: Session = Depends(get_db),
                provider=Depends(get_llm_provider)):
    q = _quote(db, _org(db, user), quote_id)
    if q.status != "draft":
        raise _fail(409, "QUOTE_LOCKED", "Chỉ đổi được mức giá khi báo giá còn là nháp.")
    q.price_mode, q.price_vnd = body.mode, q.pricing["modes"][body.mode]["total"]
    q.explanation, _ = explain(provider, q.request, q.cost, q.pricing, body.mode)
    q.revision += 1
    qs.add_revision(db, q, user)
    qs._audit(db, user, "quote.mode_selected", q, {"mode": body.mode, "price_vnd": q.price_vnd})
    db.commit()
    return quote_payload(q)


@router.post("/operator/quotes/{quote_id}/mark")
def mark_quote(quote_id: str, body: MarkBody, user: User = Depends(require_user(P.OPERATOR_QUOTE)), db: Session = Depends(get_db)):
    q = _quote(db, _org(db, user), quote_id)
    if q.status not in OPEN_STATUSES:
        raise _fail(409, "QUOTE_CLOSED", "Báo giá đã đóng, không đổi được kết quả.")
    q.status = body.outcome
    q.lost_reason = body.reason if body.outcome == "lost" else None
    if body.outcome == "won":
        q.accepted_at = q.accepted_at or datetime.now(timezone.utc)
    qs._audit(db, user, f"quote.{body.outcome}", q, {"reason": body.reason})
    db.commit()
    return quote_payload(q)


@router.get("/operator/quotes/{quote_id}/pricing-curve")
def pricing_curve(quote_id: str, user: User = Depends(require_user(P.OPERATOR_QUOTE)), db: Session = Depends(get_db)):
    q = _quote(db, _org(db, user), quote_id)
    pax = q.request["pax"]
    return {"quote_id": q.id, "pax": pax, "cost_total_vnd": q.cost_total_vnd, "cost_per_pax": round(q.cost_total_vnd / pax),
            "selected_mode": q.price_mode, "source": q.pricing["source"], "floor_margin_pct": q.pricing["floor_margin_pct"],
            "modes": q.pricing["modes"],
            "points": [{"price_per_pax": p["price_per_pax"], "p_win": p["p_win"], "expected_profit": p["expected_profit"]}
                       for p in q.pricing["curve"]]}


@router.patch("/operator/quotes/{quote_id}")
def patch_quote(quote_id: str, body: QuotePatch, user: User = Depends(require_user(P.OPERATOR_QUOTE)), db: Session = Depends(get_db),
                provider=Depends(get_llm_provider)):
    """Edit pax / departure / vehicle-meal-hotel pins / itinerary and re-cost with the rate cards of the (new) departure date.
    Draft: price is re-optimized. Sent or later: the selling price stays, only the margin moves (``margin_alert`` below the floor)."""
    org = _org(db, user)
    q = _quote(db, org, quote_id)
    if q.status not in OPEN_STATUSES:
        raise _fail(409, "QUOTE_CLOSED", "Báo giá đã đóng, không sửa được.")
    days_plan = [d.model_dump(by_alias=True, exclude_none=True) for d in body.itinerary_days] if body.itinerary_days else None
    if days_plan is not None and len(days_plan) != q.request["days"]:
        raise _fail(422, "ITINERARY_DAYS_MISMATCH", f"Lịch trình phải đủ {q.request['days']} ngày.")
    overrides = body.overrides.model_dump(exclude_unset=True) if body.overrides else None
    if not (body.pax or body.start_date or overrides or days_plan):
        raise _fail(422, "NOTHING_TO_CHANGE", "Không có thay đổi nào.")
    parts = [f"pax {body.pax}" if body.pax else "", f"ngày đi {body.start_date.isoformat()}" if body.start_date else "",
             "xe/bữa/khách sạn" if overrides else "", "lịch trình" if days_plan else ""]
    reason = body.reason or "Sửa báo giá: " + ", ".join(p for p in parts if p)
    try:
        mg.recost(db, org, q, provider, user, reason, date.today(), pax=body.pax, start_date=body.start_date, overrides=overrides, days_plan=days_plan)
    except qs.NoRates as error:
        db.rollback()
        raise _fail(422, "NO_RATES", str(error))
    db.commit()
    return quote_payload(q, org.margin_floor_pct)


@router.get("/operator/quotes/{quote_id}/revisions")
def list_revisions(quote_id: str, user: User = Depends(require_user(P.OPERATOR_QUOTE)), db: Session = Depends(get_db)):
    q = _quote(db, _org(db, user), quote_id)
    rows = db.scalars(select(QuoteRevision).where(QuoteRevision.quote_id == q.id).order_by(QuoteRevision.revision.desc())).all()
    out = []
    for r in rows:
        s = r.snapshot
        cost = (s.get("cost") or {}).get("total")
        out.append({"revision": r.revision, "reason": s.get("reason"), "created_at": r.created_at, "price_vnd": s.get("price_vnd"),
                    "cost_total_vnd": cost, "margin_pct": mg.margin_pct(s.get("price_vnd"), cost) if cost else None})
    return out


@router.get("/operator/quotes/{quote_id}/rescue")
def rescue(quote_id: str, user: User = Depends(require_user(P.OPERATOR_QUOTE)), db: Session = Depends(get_db), provider=Depends(get_llm_provider)):
    org = _org(db, user)
    q = _quote(db, org, quote_id)
    if q.status not in OPEN_STATUSES:
        raise _fail(409, "QUOTE_CLOSED", "Báo giá đã đóng.")
    options = mg.rescue_options(db, org, q, date.today())
    alert = mg.margin_alert(q, org.margin_floor_pct)
    text, source = explain_rescue(provider, alert, options)
    return {"quote_id": q.id, "margin_alert": alert, "options": options, "explanation": text, "explanation_source": source}


@router.post("/operator/quotes/{quote_id}/apply-rescue/{code}")
def apply_rescue(quote_id: str, code: str, body: RescueApply | None = None, user: User = Depends(require_user(P.OPERATOR_QUOTE)),
                 db: Session = Depends(get_db), provider=Depends(get_llm_provider)):
    """Creates a revision. A change the customer would see (price, date, tier) on a sent/viewed quote is NOT applied until
    ``confirm_resend`` is true; then the quote goes back to draft with its old link revoked and must be sent again."""
    org = _org(db, user)
    q = _quote(db, org, quote_id)
    if q.status not in OPEN_STATUSES:
        raise _fail(409, "QUOTE_CLOSED", "Báo giá đã đóng.")
    option = next((o for o in mg.rescue_options(db, org, q, date.today()) if o["code"] == code), None)
    if option is None:
        raise _fail(404, "RESCUE_OPTION_NOT_FOUND", "Phương án không còn khả dụng.")
    if option["customer_visible"] and q.status in ("accepted", "deposit_paid"):
        raise _fail(409, "QUOTE_LOCKED", "Khách đã chấp nhận báo giá; chỉ áp dụng được phương án không đổi những gì khách đã thấy.")
    result = mg.apply_rescue(db, org, q, option, provider, user, date.today(), bool(body and body.confirm_resend))
    db.commit()
    return {**result, "option": option, "suggested_price_vnd": option["new_price_vnd"], "quote": quote_payload(q, org.margin_floor_pct)}
