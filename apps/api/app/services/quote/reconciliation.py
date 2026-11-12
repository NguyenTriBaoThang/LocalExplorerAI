"""M9: match supplier-invoice lines to the quote's cost lines and explain each difference.

Rules (all deterministic, no LLM beyond the invoice extraction itself)
- Only quotes in ``RECONCILABLE`` (won, deposit_paid) can be reconciled: the tour is going ahead or happened. A draft/sent
  quote has no costs to compare against reality yet.
- Matching: same category only. All same-category pairs scoring >= MATCH_THRESHOLD (difflib SequenceMatcher ratio of the
  accent-folded lowercase labels) are paired greedily, best score first. Then, in a category where exactly one quote line and
  one invoice line are still unpaired, they are paired anyway (suppliers rename items; one-vs-one is unambiguous).
- Quoted amount = the line's total including its surcharge. Invoice amount = ``amount_vnd`` (the line total, see INVOICE_EXTRACTOR).
- Reason for a paired line with a non-zero difference: invoice quantity != quoted quantity -> pax_change; else the difference
  equals the quoted line's own surcharge (either sign) -> surcharge; else price_change.
  Invoice line with no quote line -> unplanned. Quote line with no invoice line -> not_used (actual 0).
"""
import unicodedata
from difflib import SequenceMatcher

MATCH_THRESHOLD = 0.5
RECONCILABLE = ("won", "deposit_paid")
REASONS = ("price_change", "pax_change", "unplanned", "surcharge", "not_used", "other")


def _fold(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower().strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _fold(a), _fold(b)).ratio()


def _qty(line: dict) -> int | None:
    value = (line.get("conditions") or {}).get("qty")
    return int(value) if isinstance(value, (int, float)) and value == int(value) else None


def _reason(quoted: dict, inv: dict, delta: int) -> str | None:
    if delta == 0:
        return None
    qty = _qty(inv)
    if qty is not None and qty != quoted["qty"]:
        return "pax_change"
    if quoted["surcharge_vnd"] and abs(delta) == quoted["surcharge_vnd"]:
        return "surcharge"
    return "price_change"


def match(quote_lines: list[dict], invoice_lines: list[dict]) -> list[dict]:
    """-> rows {category, label, quoted_vnd, actual_vnd, variance_vnd, reason, matched_cost_line, note}."""
    pairs: dict[int, int] = {}  # invoice index -> quote line index
    taken: set[int] = set()
    scored = sorted(((similarity(q["label"], v["label"]), qi, vi) for qi, q in enumerate(quote_lines) for vi, v in enumerate(invoice_lines)
                     if q["category"] == v["category"]), key=lambda t: (-t[0], t[1], t[2]))
    scores = {}
    for score, qi, vi in scored:
        if score >= MATCH_THRESHOLD and vi not in pairs and qi not in taken:
            pairs[vi] = qi
            taken.add(qi)
            scores[vi] = score
    for category in {v["category"] for v in invoice_lines}:
        left_q = [qi for qi, q in enumerate(quote_lines) if q["category"] == category and qi not in taken]
        left_v = [vi for vi, v in enumerate(invoice_lines) if v["category"] == category and vi not in pairs]
        if len(left_q) == 1 and len(left_v) == 1:
            pairs[left_v[0]], scores[left_v[0]] = left_q[0], similarity(quote_lines[left_q[0]]["label"], invoice_lines[left_v[0]]["label"])
            taken.add(left_q[0])

    rows = []
    for vi, v in enumerate(invoice_lines):
        if vi in pairs:
            q = quote_lines[pairs[vi]]
            delta = v["amount_vnd"] - q["total_vnd"]
            rows.append({"category": q["category"], "label": q["label"], "quoted_vnd": q["total_vnd"], "actual_vnd": v["amount_vnd"], "variance_vnd": delta,
                         "reason": _reason(q, v, delta), "matched_cost_line": pairs[vi],
                         "note": f"Hóa đơn: {v['label']} (độ giống {scores[vi]:.0%})"})
        else:
            rows.append({"category": v["category"], "label": v["label"], "quoted_vnd": 0, "actual_vnd": v["amount_vnd"], "variance_vnd": v["amount_vnd"],
                         "reason": "unplanned", "matched_cost_line": None, "note": "Có trên hóa đơn, không có trong báo giá"})
    for qi, q in enumerate(quote_lines):
        if qi not in taken:
            rows.append({"category": q["category"], "label": q["label"], "quoted_vnd": q["total_vnd"], "actual_vnd": 0, "variance_vnd": -q["total_vnd"],
                         "reason": "not_used", "matched_cost_line": qi, "note": "Có trong báo giá, không có trên hóa đơn"})
    return sorted(rows, key=lambda r: (r["matched_cost_line"] is None, r["matched_cost_line"] or 0, r["label"]))
