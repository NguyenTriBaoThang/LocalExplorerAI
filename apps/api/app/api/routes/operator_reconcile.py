"""Post-tour reconciliation (M9): quoted cost vs supplier invoice, and the margin analytics built on it."""
import json
from collections import defaultdict
from datetime import date
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.guards import require_user
from app.api.permissions import P
from app.api.routes.operator import _audit, _org
from app.models.entities import CostActual, OperatorDocument, OperatorOrg, Quote, RateCard, RateCardItem, User
from app.services.quote import reconciliation as rec
from app.services.quote.margin_guard import margin_pct
from app.services.quote.win_model import _default_dir

router = APIRouter(prefix="/api", tags=["operator reconciliation"])


def _fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


class ReconcileBody(BaseModel):
    document_id: str = Field(min_length=1, max_length=36)


class ActualPatch(BaseModel):
    actual_vnd: int | None = Field(default=None, ge=0, le=10_000_000_000)
    reason: str | None = Field(default=None, pattern="^(price_change|pax_change|unplanned|surcharge|not_used|other)$")
    note: str | None = Field(default=None, max_length=500)
    confirmed: bool | None = None


def row_payload(r: CostActual) -> dict:
    return {"id": r.id, "quote_id": r.quote_id, "document_id": r.document_id, "category": r.category, "label": r.label,
            "quoted_vnd": int(r.quoted_vnd), "actual_vnd": int(r.actual_vnd), "variance_vnd": int(r.variance_vnd), "reason": r.reason,
            "matched_cost_line": r.matched_cost_line, "note": r.note, "confirmed": r.confirmed}


def _quote(db: Session, org: OperatorOrg, quote_id: str) -> Quote:
    q = db.scalar(select(Quote).where(Quote.id == quote_id, Quote.org_id == org.id))
    if q is None:
        raise _fail(404, "QUOTE_NOT_FOUND", "Không tìm thấy báo giá.")
    return q


def _rows(db: Session, q: Quote) -> list[CostActual]:
    rows = db.scalars(select(CostActual).where(CostActual.quote_id == q.id)).all()
    return sorted(rows, key=lambda r: (r.matched_cost_line is None, r.matched_cost_line or 0, r.label))


def _state(db: Session, q: Quote) -> dict:
    rows = _rows(db, q)
    return {"quote_id": q.id, "code": q.code, "status": q.status, "price_vnd": q.price_vnd, "quoted_total_vnd": q.cost_total_vnd,
            "actual_cost_vnd": q.actual_cost_vnd, "finalized": q.actual_cost_vnd is not None, "rows": [row_payload(r) for r in rows],
            "totals": {"quoted_vnd": sum(int(r.quoted_vnd) for r in rows), "actual_vnd": sum(int(r.actual_vnd) for r in rows),
                       "variance_vnd": sum(int(r.variance_vnd) for r in rows)}}


@router.get("/operator/quotes/{quote_id}/reconcile")
def get_reconciliation(quote_id: str, user: User = Depends(require_user(P.OPERATOR_RECONCILE)), db: Session = Depends(get_db)):
    return _state(db, _quote(db, _org(db, user), quote_id))


@router.post("/operator/quotes/{quote_id}/reconcile")
def reconcile(quote_id: str, body: ReconcileBody, user: User = Depends(require_user(P.OPERATOR_RECONCILE)), db: Session = Depends(get_db)):
    """Match an extracted invoice (kind=invoice) to the quote; replaces earlier unconfirmed rows. Rule: only won / deposit_paid quotes."""
    org = _org(db, user)
    q = _quote(db, org, quote_id)
    if q.status not in rec.RECONCILABLE:
        raise _fail(409, "QUOTE_NOT_RECONCILABLE", "Chỉ đối chiếu được báo giá đã chốt (won) hoặc đã đặt cọc, tức tour đã/đang diễn ra.")
    if q.actual_cost_vnd is not None:
        raise _fail(409, "RECONCILIATION_FINAL", "Báo giá này đã xác nhận chi phí thực tế.")
    doc = db.scalar(select(OperatorDocument).where(OperatorDocument.id == body.document_id, OperatorDocument.org_id == org.id))
    if doc is None:
        raise _fail(404, "DOCUMENT_NOT_FOUND", "Không tìm thấy tài liệu.")
    if doc.kind != "invoice" or doc.status != "extracted" or not doc.extracted:
        raise _fail(409, "DOCUMENT_NOT_READY", "Cần một hóa đơn (kind=invoice) đã được trích xuất.")
    lines = [ln for ln in doc.extracted.get("lines", []) if ln.get("category") != "surcharge" or ln.get("unit") != "pct"]  # a % line has no VND amount
    for old in _rows(db, q):
        db.delete(old)
    for row in rec.match(q.cost["lines"], lines):
        db.add(CostActual(org_id=org.id, quote_id=q.id, document_id=doc.id, **row))
    _audit(db, user, "quote.reconciled", q.id, {"document_id": doc.id, "invoice_lines": len(lines)}, "quote")
    db.commit()
    return _state(db, q)


@router.patch("/operator/cost-actuals/{row_id}")
def patch_actual(row_id: str, body: ActualPatch, user: User = Depends(require_user(P.OPERATOR_RECONCILE)), db: Session = Depends(get_db)):
    org = _org(db, user)
    row = db.scalar(select(CostActual).where(CostActual.id == row_id, CostActual.org_id == org.id))
    if row is None:
        raise _fail(404, "COST_ACTUAL_NOT_FOUND", "Không tìm thấy dòng đối chiếu.")
    if db.scalar(select(Quote.actual_cost_vnd).where(Quote.id == row.quote_id)) is not None:
        raise _fail(409, "RECONCILIATION_FINAL", "Chi phí thực tế đã được xác nhận, không sửa được.")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    if "actual_vnd" in data and data["actual_vnd"] is not None:
        row.variance_vnd = row.actual_vnd - row.quoted_vnd
    if row.variance_vnd == 0 and "reason" not in data:
        row.reason = None
    db.commit()
    return row_payload(row)


@router.post("/operator/quotes/{quote_id}/reconcile/confirm")
def confirm_reconciliation(quote_id: str, user: User = Depends(require_user(P.OPERATOR_RECONCILE)), db: Session = Depends(get_db)):
    """Confirms every row and stores quote.actual_cost_vnd = sum of the actuals."""
    q = _quote(db, _org(db, user), quote_id)
    if q.status not in rec.RECONCILABLE:
        raise _fail(409, "QUOTE_NOT_RECONCILABLE", "Chỉ đối chiếu được báo giá đã chốt (won) hoặc đã đặt cọc.")
    rows = _rows(db, q)
    if not rows:
        raise _fail(422, "NOTHING_TO_CONFIRM", "Chưa có dòng đối chiếu nào; hãy đối chiếu một hóa đơn trước.")
    if any(r.variance_vnd and not r.reason for r in rows):
        raise _fail(422, "REASON_REQUIRED", "Còn dòng lệch chưa có lý do.")
    for r in rows:
        r.confirmed = True
    q.actual_cost_vnd = sum(int(r.actual_vnd) for r in rows)
    _audit(db, user, "quote.actual_cost_confirmed", q.id, {"actual_cost_vnd": q.actual_cost_vnd, "quoted_cost_vnd": q.cost_total_vnd}, "quote")
    db.commit()
    return _state(db, q)


@router.get("/operator/analytics/margin")
def margin_analytics(date_from: date | None = Query(default=None, alias="from"), date_to: date | None = Query(default=None, alias="to"),
                     user: User = Depends(require_user(P.OPERATOR_ANALYTICS)), db: Session = Depends(get_db)):
    """Quotes with confirmed actual costs whose tour start_date falls in [from, to]: expected vs actual margin, variance by reason and supplier."""
    org = _org(db, user)
    quotes = [q for q in db.scalars(select(Quote).where(Quote.org_id == org.id, Quote.actual_cost_vnd.is_not(None)).order_by(Quote.code)).all()
              if (date_from is None or date.fromisoformat(q.request["start_date"]) >= date_from)
              and (date_to is None or date.fromisoformat(q.request["start_date"]) <= date_to)]
    items = []
    for q in quotes:
        price, expected, actual = int(q.price_vnd or 0), int(q.cost_total_vnd), int(q.actual_cost_vnd)
        items.append({"quote_id": q.id, "code": q.code, "customer_name": q.customer_name, "start_date": q.request["start_date"],
                      "price_vnd": price, "expected_cost_vnd": expected, "actual_cost_vnd": actual, "variance_vnd": actual - expected,
                      "expected_margin_pct": margin_pct(price, expected), "actual_margin_pct": margin_pct(price, actual)})
    price, expected, actual = (sum(i[k] for i in items) for k in ("price_vnd", "expected_cost_vnd", "actual_cost_vnd"))
    totals = {"quotes": len(items), "price_vnd": price, "expected_cost_vnd": expected, "actual_cost_vnd": actual, "variance_vnd": actual - expected,
              "expected_margin_pct": margin_pct(price, expected), "actual_margin_pct": margin_pct(price, actual)}

    by_reason: dict[str, dict] = defaultdict(lambda: {"variance_vnd": 0, "count": 0})
    by_supplier: dict[str, dict] = defaultdict(lambda: {"quoted_vnd": 0, "actual_vnd": 0, "variance_vnd": 0})
    ids = [q.id for q in quotes]
    rows = db.scalars(select(CostActual).where(CostActual.quote_id.in_(ids))).all() if ids else []
    by_quote = {q.id: q for q in quotes}
    item_ids = {ln.get("rate_item_id") for q in quotes for ln in q.cost["lines"] if ln.get("rate_item_id")}
    supplier_of = dict(db.execute(select(RateCardItem.id, RateCard.supplier).join(RateCard, RateCard.id == RateCardItem.card_id)
                                  .where(RateCardItem.id.in_(item_ids))).all()) if item_ids else {}
    docs = {d.id: (d.extracted or {}).get("supplier") for d in db.scalars(select(OperatorDocument).where(OperatorDocument.org_id == org.id)).all()}
    for r in rows:
        if r.variance_vnd:
            by_reason[r.reason or "other"]["variance_vnd"] += int(r.variance_vnd)
            by_reason[r.reason or "other"]["count"] += 1
        line = by_quote[r.quote_id].cost["lines"][r.matched_cost_line] if r.matched_cost_line is not None else None
        name = supplier_of.get(line.get("rate_item_id")) if line else None
        s = by_supplier[name or docs.get(r.document_id) or "Không rõ"]
        s["quoted_vnd"] += int(r.quoted_vnd)
        s["actual_vnd"] += int(r.actual_vnd)
        s["variance_vnd"] += int(r.variance_vnd)
    return {"from": date_from, "to": date_to, "totals": totals, "quotes": items,
            "by_reason": sorted(({"reason": k, **v} for k, v in by_reason.items()), key=lambda x: -abs(x["variance_vnd"])),
            "by_supplier": sorted(({"supplier": k, **v} for k, v in by_supplier.items()), key=lambda x: -abs(x["variance_vnd"]))}


WON = ("won", "deposit_paid")
BACKTEST_STRATEGIES = (("fixed_25pct_markup", "Markup cố định 25%"), ("optimizer_balanced", "Tối ưu: cân bằng"),
                       ("optimizer_max_profit", "Tối ưu: lợi nhuận tối đa"), ("oracle_max_profit_true_p", "Oracle (cận trên lý thuyết)"))


def _backtest() -> dict | None:
    """Offline backtest of the pricing optimizer vs a fixed 25% markup. Synthetic data: proves the method, not real uplift."""
    root = _default_dir()
    try:
        bt = json.loads((root / "backtest.json").read_text(encoding="utf-8"))
        status = json.loads((root / "model_metadata.json").read_text(encoding="utf-8")).get("dataset_status", "synthetic")
    except (OSError, ValueError):
        return None
    base = bt["strategies"]["fixed_25pct_markup"]["expected_profit_vnd"]
    return {"dataset_status": status, "quotes": bt.get("quotes"), "period": bt.get("period"), "baseline": "fixed_25pct_markup",
            "basis": "Lợi nhuận kỳ vọng trên tập test giả lập theo xác suất thắng thật; so với markup cố định 25%.",
            "strategies": [{"key": k, "label": label, "expected_profit_vnd": bt["strategies"][k]["expected_profit_vnd"],
                            "expected_win_rate": bt["strategies"][k]["expected_win_rate"],
                            "profit_vs_baseline_pct": round((bt["strategies"][k]["expected_profit_vnd"] / base - 1) * 100, 2) if base else None}
                           for k, label in BACKTEST_STRATEGIES if k in bt["strategies"]]}


def _naive(dt):
    return dt.replace(tzinfo=None)


@router.get("/operator/analytics/roi")
def roi_analytics(date_from: date | None = Query(default=None, alias="from"), date_to: date | None = Query(default=None, alias="to"),
                  user: User = Depends(require_user(P.OPERATOR_ANALYTICS)), db: Session = Depends(get_db)):
    """Business value of the copilot from live data (quotes whose tour start_date is in [from, to]); every figure carries its formula in `basis`."""
    org = _org(db, user)
    quotes = [q for q in db.scalars(select(Quote).where(Quote.org_id == org.id).order_by(Quote.code)).all()
              if (date_from is None or date.fromisoformat(q.request["start_date"]) >= date_from)
              and (date_to is None or date.fromisoformat(q.request["start_date"]) <= date_to)]
    sent = [q for q in quotes if q.sent_at is not None]
    minutes = lambda a, b: (_naive(b) - _naive(a)).total_seconds() / 60  # noqa: E731
    response = [minutes(q.received_at, q.sent_at) for q in sent]
    saved_min = [max(0.0, org.manual_minutes_per_quote - minutes(q.created_at, q.sent_at)) for q in sent]
    won = [q for q in quotes if q.status in WON]
    won_n, lost_n = len(won), sum(q.status == "lost" for q in quotes)
    uplift = sum(int(q.price_vnd or 0) - round(int(q.cost_total_vnd) * (1 + org.default_markup_pct / 100)) for q in won if q.price_vnd is not None)
    fixed_profit = sum(round(int(q.cost_total_vnd) * org.default_markup_pct / 100) for q in won if q.price_vnd is not None)
    revenue = sum(int(q.price_vnd or 0) for q in won)
    return {
        "from": date_from, "to": date_to, "quotes_count": len(quotes), "sent_count": len(sent), "won_count": won_n, "lost_count": lost_n,
        "median_response_minutes": {"value": round(median(response), 1) if response else None, "basis": "Trung vị của (sent_at − received_at) trên các báo giá đã gửi."},
        "hours_saved": {"value": round(sum(saved_min) / 60, 2) if sent else None, "manual_minutes_per_quote": org.manual_minutes_per_quote,
                        "basis": f"Σ max(0, {org.manual_minutes_per_quote} phút làm tay − (sent_at − created_at)) / 60 trên các báo giá đã gửi."},
        "win_rate": {"value": round(won_n / (won_n + lost_n), 4) if won_n + lost_n else None,
                     "basis": "(won + deposit_paid) / (won + deposit_paid + lost); báo giá chưa có kết quả không tính."},
        "margin_uplift_vnd": {"value": uplift if won else None, "pct_of_fixed_markup_profit": round(uplift / fixed_profit * 100, 2) if fixed_profit else None,
                              "default_markup_pct": org.default_markup_pct,
                              "basis": f"Σ trên báo giá won/deposit_paid của (giá bán − chi phí × (1 + {org.default_markup_pct}%)); % so với lợi nhuận nếu luôn markup cố định. Chỉ tính trên đơn đã chốt, chưa trừ các đơn có thể mất vì giá cao hơn — so sánh đầy đủ (có xác suất chốt) xem phần backtest."},
        "ota_commission_avoided_vnd": {"value": round(revenue * org.ota_commission_pct / 100) if won else None, "ota_commission_pct": org.ota_commission_pct,
                                       "basis": f"Σ giá bán của báo giá won/deposit_paid × {org.ota_commission_pct}% hoa hồng OTA."},
        "backtest": _backtest(),
    }
