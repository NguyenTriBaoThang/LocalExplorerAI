"""Customer message -> QuoteRequest. LLM first (QUOTE_REQUEST_PARSER); offline regex when no LLM or it fails.

Which fields are missing is always decided here, never trusted from the model.
"""
import re
import unicodedata
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.adapters.llm.provider import LLMNotConfigured, LLMProviderError
from app.services.prompt_service import InvalidStructuredOutput, PromptRunner

Segment = Literal["family", "corporate", "school"]
Destination = Literal["cu_chi", "mekong", "can_gio", "vung_tau", "city"]
REQUIRED = ("pax", "days", "start_date", "destinations")  # segment falls back to "family" (listed in assumed_fields)
QUESTIONS = {
    "pax": "Đoàn mình đi bao nhiêu khách (không tính hướng dẫn viên)? Tối đa 60 khách.",
    "days": "Tour đi mấy ngày (1 đến 3 ngày)?",
    "start_date": "Đoàn dự kiến khởi hành ngày nào?",
    "destinations": "Đoàn muốn đi điểm nào: Củ Chi, Mekong, Cần Giờ, Vũng Tàu hay city tour TP.HCM?",
}


class QuoteRequest(BaseModel):
    pax: int | None = Field(default=None, ge=1, le=60)
    days: int | None = Field(default=None, ge=1, le=3)
    start_date: date | None = None
    segment: Segment | None = None
    destinations: list[Destination] = []
    pickup: str | None = Field(default=None, max_length=255)
    hotel_class: int | None = Field(default=None, ge=1, le=5)
    meal_plan: Literal["none", "basic", "full"] | None = None
    budget_per_pax: int | None = Field(default=None, ge=0)
    interests: list[str] = []
    customer_name: str | None = Field(default=None, max_length=180)
    missing_fields: list[str] = []
    assumed_fields: list[str] = []


def finalize(req: QuoteRequest) -> QuoteRequest:
    """Recompute missing_fields from the data and apply the one default (segment)."""
    req.missing_fields = [f for f in REQUIRED if not getattr(req, f)]
    req.assumed_fields = []
    if req.segment is None:
        req.segment, req.assumed_fields = "family", ["segment"]
    return req


def clarifying_questions(req: QuoteRequest) -> list[str]:
    return [QUESTIONS[f] for f in req.missing_fields]


def _fold(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()


_DEST = {"cu_chi": ("cu chi",), "mekong": ("mekong", "my tho", "ben tre", "mien tay", "tien giang"),
         "can_gio": ("can gio",), "vung_tau": ("vung tau",), "city": ("city tour", "noi thanh", "sai gon", "tphcm", "tp.hcm", "tp hcm")}
_SEG = (("school", ("truong", "hoc sinh", "sinh vien", "lop ")), ("corporate", ("cong ty", "team building", "doanh nghiep", "nhan vien", "hoi nghi")),
        ("family", ("gia dinh", "ban be", "nhom ban")))


def _money(num: str, unit: str) -> int:
    value = float(num.replace(",", "."))
    return int(round(value * {"tr": 1_000_000, "trieu": 1_000_000, "k": 1_000, "nghin": 1_000}[unit]))


def _date(text: str, today: date) -> date | None:
    m = re.search(r"\b(\d{1,2})\s*[/\-]\s*(\d{1,2})(?:\s*[/\-]\s*(\d{4}|\d{2}))?\b", text) or \
        re.search(r"\bngay\s+(\d{1,2})\s+thang\s+(\d{1,2})(?:\s+(?:nam\s+)?(\d{4}))?", text)
    if not m:
        return None
    d, mo, y = int(m[1]), int(m[2]), m[3]
    try:
        if y:
            return date(2000 + int(y) if len(y) == 2 else int(y), mo, d)
        found = date(today.year, mo, d)
        return found if found >= today else date(today.year + 1, mo, d)
    except ValueError:
        return None


def parse_offline(message: str, today: date) -> QuoteRequest:
    t = _fold(message)
    out: dict = {}
    if m := re.search(r"\b(\d{1,3})\s*(?:nguoi|khach|pax|hoc sinh|sinh vien|nhan vien)\b", t):
        out["pax"] = int(m[1])
    if m := re.search(r"\b(\d)\s*ngay\s*\d\s*dem\b", t) or re.search(r"\b(\d)\s*ngay\b", t):
        out["days"] = int(m[1])
    elif re.search(r"trong ngay|1 ngay", t):
        out["days"] = 1
    out["start_date"] = _date(t, today)
    out["segment"] = next((s for s, keys in _SEG if any(k in t for k in keys)), None)
    out["destinations"] = [d for d, keys in _DEST.items() if any(k in t for k in keys)]
    if m := re.search(r"\b(\d+(?:[.,]\d+)?)\s*(trieu|tr|k|nghin)\b", t):
        total = _money(m[1], m[2])
        pax = out.get("pax")
        out["budget_per_pax"] = total // pax if pax and re.search(r"tong|ca doan", t) else total
    if m := re.search(r"\b([2-5])\s*sao\b", t):
        out["hotel_class"] = int(m[1])
    # Out-of-range numbers (e.g. 100 guests) count as missing, never silently clamped.
    for key, lo, hi in (("pax", 1, 60), ("days", 1, 3)):
        if key in out and not lo <= out[key] <= hi:
            out[key] = None
    return finalize(QuoteRequest(**{k: v for k, v in out.items() if v is not None}))


def parse_request(provider, message: str, today: date) -> tuple[QuoteRequest, str]:
    """-> (request, source) where source is "llm" or "offline"."""
    try:
        req = PromptRunner(provider).run("QUOTE_REQUEST_PARSER", {"message": message, "today": today.isoformat()}, QuoteRequest)
        return finalize(req), "llm"
    except (LLMNotConfigured, LLMProviderError, InvalidStructuredOutput):
        return parse_offline(message, today), "offline"
