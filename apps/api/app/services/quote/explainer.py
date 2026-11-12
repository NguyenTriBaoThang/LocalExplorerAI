"""Quote explanation (M7-2). The LLM only sees computed numbers; its text is discarded unless every number in it
can be derived from that input, in which case a Vietnamese template built from the same numbers is used instead."""
import json
import re

from pydantic import BaseModel

from app.adapters.llm.provider import LLMNotConfigured, LLMProviderError
from app.services.prompt_service import InvalidStructuredOutput, PromptRunner

MODE_LABEL = {"safe": "An toàn", "balanced": "Cân bằng", "max_profit": "Tối đa lãi"}
_NUM = re.compile(r"(\d+(?:[.,]\d+)*)\s*(triệu|tr\b|nghìn|ngàn|k\b|%)?", re.IGNORECASE)
_THOUSANDS = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")
_SCALE = {"triệu": 1_000_000, "tr": 1_000_000, "nghìn": 1_000, "ngàn": 1_000, "k": 1_000}


class Explanation(BaseModel):
    explanation: str


def extract_numbers(text: str) -> list[tuple[tuple[float, ...], str | None]]:
    """[(readings, unit)] for every number; unit is a lowercase suffix (triệu/k/%) or None. Handles 1.200.000, 1,2 triệu, 25%.
    '1.250' is ambiguous (1250 or 1.25) so it yields both readings; the guard accepts a number when any reading fits."""
    out = []
    for m in _NUM.finditer(text):
        raw, unit = m.group(1), (m.group(2) or "").lower() or None
        seps = len(re.findall(r"[.,]", raw))
        if seps == 0:
            readings = [float(raw)]
        elif _THOUSANDS.match(raw):
            readings = [float(re.sub(r"[.,]", "", raw))] + ([float(raw.replace(",", "."))] if seps == 1 else [])
        else:
            readings = [float(raw.replace(",", ".")) if seps == 1 else float(re.sub(r"[.,]", "", raw))]
        out.append((tuple(readings), unit))
    return out


def _fits(value: float, unit: str | None, allowed: list[float]) -> bool:
    scale = _SCALE.get(unit or "")
    if scale:  # "1,2 triệu" may round the exact figure to one decimal: allow half a unit of its last digit
        return any(abs(value * scale - a) <= scale * 0.05 for a in allowed)
    tol = 0.5 if unit == "%" else 0.005
    return any(abs(value - a) <= tol for a in allowed)


def numbers_grounded(text: str, source: dict) -> bool:
    """True when every number in ``text`` is derivable from the numbers in ``source`` (the explainer input)."""
    allowed = [v for readings, _ in extract_numbers(json.dumps(source, ensure_ascii=False)) for v in readings]
    return all(any(_fits(v, unit, allowed) for v in readings) for readings, unit in extract_numbers(text))


def _vnd(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def explain_input(req: dict, cost: dict, pricing: dict, mode: str) -> dict:
    m = pricing["modes"][mode]
    lines = sorted((ln for ln in cost["lines"]), key=lambda ln: -ln["total_vnd"])[:3]
    return {
        "mode": mode, "mode_label": MODE_LABEL[mode], "pax": req["pax"], "days": req["days"],
        "price_per_pax_vnd": m["price_per_pax"], "total_price_vnd": m["total"], "cost_total_vnd": cost["total"],
        "margin_pct": round(m["margin_pct"], 1), "win_probability_pct": round(m["p_win"] * 100),
        "expected_profit_vnd": round(m["expected_profit"]), "floor_bound": m["floor_bound"],
        "top_costs": [{"label": ln["label"], "amount_vnd": ln["total_vnd"]} for ln in lines],
        "surcharges": [{"label": s["label"], "amount_vnd": s["amount_vnd"]} for s in cost["surcharges"]],
        "other_modes": [{"mode_label": MODE_LABEL[k], "price_per_pax_vnd": pricing["modes"][k]["price_per_pax"],
                         "win_probability_pct": round(pricing["modes"][k]["p_win"] * 100)} for k in MODE_LABEL if k != mode],
    }


def template_explanation(src: dict) -> str:
    parts = [f"Mức {src['mode_label']}: {_vnd(src['price_per_pax_vnd'])}đ/khách, tổng {_vnd(src['total_price_vnd'])}đ cho {src['pax']} khách, "
             f"biên lợi nhuận {src['margin_pct']}%, xác suất chốt ước tính {src['win_probability_pct']}%, lãi kỳ vọng {_vnd(src['expected_profit_vnd'])}đ."]
    costs = ", ".join(f"{c['label']} ({_vnd(c['amount_vnd'])}đ)" for c in src["top_costs"])
    parts.append(f"Giá vốn {_vnd(src['cost_total_vnd'])}đ, lớn nhất là {costs}.")
    if src["surcharges"]:
        parts.append("Đã gồm phụ thu: " + ", ".join(f"{s['label']} ({_vnd(s['amount_vnd'])}đ)" for s in src["surcharges"]) + ".")
    if src["floor_bound"]:
        parts.append("Không mức giá nào đạt xác suất chốt mục tiêu nên giá đang ở sát mức sàn lợi nhuận.")
    return " ".join(parts)


def explain(provider, req: dict, cost: dict, pricing: dict, mode: str) -> tuple[str, str]:
    """-> (text, source) with source "llm" or "template"."""
    src = explain_input(req, cost, pricing, mode)
    try:
        text = PromptRunner(provider).run("QUOTE_EXPLAINER", src, Explanation).explanation.strip()
        if text and numbers_grounded(text, src):
            return text, "llm"
    except (LLMNotConfigured, LLMProviderError, InvalidStructuredOutput):
        pass
    return template_explanation(src), "template"
