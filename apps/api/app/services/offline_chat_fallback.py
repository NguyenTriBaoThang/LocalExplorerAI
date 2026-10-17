"""Conservative, deterministic parsing for chat when the external LLM is unavailable."""

import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.schemas.ai import StructuredConstraints


_INTENT_KEYS = ("thủ_công", "ẩm_thực", "văn_hóa", "thư_giãn")
_NUMBER_WORDS = {
    "mot": 1,
    "hai": 2,
    "ba": 3,
    "bon": 4,
    "tu": 4,
    "nam": 5,
    "sau": 6,
    "bay": 7,
    "tam": 8,
    "chin": 9,
    "muoi": 10,
}
_NUMBER = r"(?:\d{1,2}|mot|hai|ba|bon|tu|nam|sau|bay|tam|chin|muoi)"
_TIME = r"(?P<hour>\d{1,2})(?:(?::|h)(?P<minute>\d{2}))?\s*(?:gio)?"
_INTENT_KEYWORDS = {
    "thủ_công": ("thu cong", "lam gom", "nan gom", "theu", "nuoc hoa", "tu tay lam", "thu cong"),
    "ẩm_thực": ("am thuc", "mon an", "nau an", "banh xeo", "ca phe", "com tam", "do an"),
    "văn_hóa": ("van hoa", "bao tang", "di san", "lich su", "chua", "dinh doc lap"),
    "thư_giãn": ("thu gian", "relax", "sup", "cheo sup", "du thuyen", "can gio", "nghi ngoi"),
}


def _fold(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)).lower()


def _as_integer(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    return _NUMBER_WORDS.get(value)


def _last_capture(patterns: tuple[str, ...], text: str) -> re.Match[str] | None:
    matches = [match for pattern in patterns for match in re.finditer(pattern, text, re.IGNORECASE)]
    return max(matches, key=lambda match: match.start()) if matches else None


def _clock_value(match: re.Match[str] | None) -> str | None:
    if match is None:
        return None
    hour = int(match.group("hour"))
    minute = int(match.groupdict().get("minute") or 0)
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _parse_money(text: str) -> int | None:
    pattern = (
        r"(?:ngan sach|budget|toi da|chi phi|du tru)"
        r"[^0-9]{0,30}(?P<amount>\d+(?:[.,]\d+)?)\s*"
        r"(?P<unit>trieu|tr|nghin|ngan|k|vnd|dong|d)?"
    )
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    if not matches:
        return None
    match = matches[-1]
    if re.match(r"\s*(?:/\s*nguoi|/\s*khach|moi\s+(?:nguoi|khach)|per\s+person)", text[match.end():match.end() + 32]):
        # A per-person amount is not the total group budget required by the planner.
        return None
    raw = match.group("amount")
    unit = (match.group("unit") or "").lower()
    if unit in {"trieu", "tr"}:
        amount = float(raw.replace(",", ".")) * 1_000_000
    elif unit in {"nghin", "ngan", "k"}:
        amount = float(raw.replace(",", ".")) * 1_000
    else:
        amount = int(raw.replace(".", "").replace(",", ""))
    return int(amount) if amount >= 0 else None


def _parse_group_size(text: str) -> int | None:
    matches = list(re.finditer(rf"\b(?P<count>{_NUMBER})\s*(?:nguoi|khach|thanh vien)\b", text, re.IGNORECASE))
    if not matches:
        return None
    count = _as_integer(matches[-1].group("count").lower())
    return count if count and count <= 50 else None


def _parse_time(patterns: tuple[str, ...], text: str) -> str | None:
    return _clock_value(_last_capture(patterns, text))


def _parse_mode(text: str) -> str:
    modes = {
        "motorcycle": ("xe may", "motorcycle", "motorbike"),
        "walking": ("di bo", "walking", "di bo"),
        "car": ("o to", "xe hoi", "car", "taxi", "di xe hoi"),
        "transit": ("xe buyt", "bus", "metro", "tau dien", "public transit"),
    }
    hits = [
        (text.rfind(alias), mode)
        for mode, aliases in modes.items()
        for alias in aliases
        if text.rfind(alias) >= 0
    ]
    return max(hits)[1] if hits else "motorcycle"


def _has_explicit_mode(text: str) -> bool:
    aliases = (
        "xe may", "motorcycle", "motorbike", "di bo", "walking", "o to", "xe hoi", "car", "taxi",
        "xe buyt", "bus", "metro", "tau dien", "public transit",
    )
    return any(alias in text for alias in aliases)


def _parse_intents(text: str) -> dict[str, float]:
    counts = {key: sum(text.count(keyword) for keyword in terms) for key, terms in _INTENT_KEYWORDS.items()}
    total = sum(counts.values())
    if total == 0:
        # StructuredConstraints requires a unit-sum distribution; equal weights are
        # explicitly identified as neutral in the accompanying fallback message.
        return {key: 0.25 for key in _INTENT_KEYS}
    return {key: counts[key] / total for key in _INTENT_KEYS}


def _parse_locked_pois(original: str) -> list[str]:
    pattern = r"(?:bắt buộc phải ghé|nhất định phải ghé|phải ghé|locked poi là)\s+([^.;,\n]+?)(?=\s+và\s+|[.;,\n]|$)"
    values = [match.group(1).strip(" ,-") for match in re.finditer(pattern, original, re.IGNORECASE)]
    return list(dict.fromkeys(value for value in values if value))[:10]


def _explicit_trip_date(text: str, today: date) -> date | None:
    candidates: list[tuple[int, date]] = []
    relative = (
        (r"\bngay\s+hom nay\b|\btoday\b", today),
        (r"\bngay\s+(?:kia|mot)\b|\bday after tomorrow\b", today + timedelta(days=2)),
        (r"\bngay\s+mai\b|\btomorrow\b", today + timedelta(days=1)),
    )
    for pattern, value in relative:
        candidates.extend((match.start(), value) for match in re.finditer(pattern, text))
    if text.strip() in {"mai", "tomorrow"}:
        candidates.append((0, today + timedelta(days=1)))
    elif text.strip() in {"hom nay", "today"}:
        candidates.append((0, today))
    elif text.strip() in {"ngay kia", "ngay mot", "day after tomorrow"}:
        candidates.append((0, today + timedelta(days=2)))

    for match in re.finditer(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text):
        try:
            candidates.append((match.start(), date(int(match.group(1)), int(match.group(2)), int(match.group(3)))))
        except ValueError:
            continue
    for match in re.finditer(r"(?<![\d-])\b(?:ngay\s+)?(\d{1,2})[/-](\d{1,2})(?:[/-](20\d{2}))?\b", text):
        try:
            candidates.append((match.start(), date(int(match.group(3) or today.year), int(match.group(2)), int(match.group(1)))))
        except ValueError:
            continue
    for match in re.finditer(r"\b(?:ngay\s+)?(\d{1,2})\s+thang\s+(\d{1,2})(?:\s+nam\s+(20\d{2}))?\b", text):
        try:
            candidates.append((match.start(), date(int(match.group(3) or today.year), int(match.group(2)), int(match.group(1)))))
        except ValueError:
            continue
    if candidates:
        return max(candidates, key=lambda item: item[0])[1]
    return None


def _parse_trip_date(text: str, context_date: date | None, latest_message: str | None) -> date | None:
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    latest_date = _explicit_trip_date(_fold(latest_message), today) if latest_message else None
    return latest_date or context_date or _explicit_trip_date(text, today)


def _parse_short_clock(value: str) -> str | None:
    match = re.fullmatch(r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?", value.strip())
    return _clock_value(match)


def _parse_standalone_money(value: str) -> int | None:
    match = re.fullmatch(
        r"(?P<amount>\d[\d.,]*)(?:\s*(?P<unit>trieu|tr|nghin|ngan|k|vnd|dong|d))?",
        _fold(value).strip(),
    )
    if match is None:
        return None
    raw = match.group("amount")
    unit = match.group("unit") or ""
    if unit in {"trieu", "tr"}:
        try:
            amount = float(raw.replace(",", ".")) * 1_000_000
        except ValueError:
            return None
    elif unit in {"nghin", "ngan", "k"}:
        try:
            amount = float(raw.replace(",", ".")) * 1_000
        except ValueError:
            return None
    else:
        try:
            amount = int(raw.replace(".", "").replace(",", ""))
        except ValueError:
            return None
    return int(amount) if amount >= 0 else None


def build_offline_constraints(
    message: str,
    reason: str,
    *,
    trip_date_context: date | None = None,
    latest_message: str | None = None,
    prior_constraints: StructuredConstraints | None = None,
) -> tuple[StructuredConstraints, str]:
    """Extract only values matching explicit simple patterns; never invent prices or availability."""
    folded = _fold(message)
    trip_date = _parse_trip_date(folded, trip_date_context or (prior_constraints.trip_date if prior_constraints else None), latest_message)
    group_size = _parse_group_size(folded)
    if group_size is None and latest_message and prior_constraints and "group_size" in prior_constraints.missing_fields:
        short_count = re.fullmatch(r"\d{1,2}", _fold(latest_message).strip())
        if short_count and 1 <= int(short_count.group()) <= 50:
            group_size = int(short_count.group())
    group_size = group_size or (prior_constraints.group_size if prior_constraints else None)
    start_time = _parse_time((rf"(?:bat dau|khoi hanh|xuat phat|di luc|tu)\s*(?:luc\s*)?{_TIME}",), folded)
    return_deadline = _parse_time((rf"(?:ve truoc|phai ve|gio ve|tro ve|den luc|den)\s*(?:luc\s*)?{_TIME}",), folded)
    if latest_message:
        latest_folded = _fold(latest_message).strip()
        short_range = re.fullmatch(
            r"(?P<start>\d{1,2}(?::\d{2})?)\s*(?:-|–|den|to)\s*(?P<end>\d{1,2}(?::\d{2})?)",
            latest_folded,
        )
        if short_range:
            start_time = _parse_short_clock(short_range.group("start")) or start_time
            return_deadline = _parse_short_clock(short_range.group("end")) or return_deadline
        else:
            short_time = _parse_short_clock(latest_folded)
            if short_time and prior_constraints:
                if "start_time" in prior_constraints.missing_fields:
                    start_time = short_time
                elif "return_deadline" in prior_constraints.missing_fields:
                    return_deadline = short_time
    start_time = start_time or (prior_constraints.start_time if prior_constraints else None)
    return_deadline = return_deadline or (prior_constraints.return_deadline if prior_constraints else None)
    budget_vnd = _parse_money(folded)
    if latest_message and prior_constraints and "budget_vnd" in prior_constraints.missing_fields:
        budget_vnd = _parse_standalone_money(latest_message) or budget_vnd
    budget_vnd = budget_vnd if budget_vnd is not None else (prior_constraints.budget_vnd if prior_constraints else None)
    travel_mode = _parse_mode(folded)
    travel_mode_confirmed = _has_explicit_mode(folded) or bool(prior_constraints and prior_constraints.travel_mode_confirmed)
    if not _has_explicit_mode(folded) and prior_constraints:
        travel_mode = prior_constraints.travel_mode
    has_explicit_intent = any(folded.count(keyword) for terms in _INTENT_KEYWORDS.values() for keyword in terms)
    intent_weights = _parse_intents(folded) if has_explicit_intent or prior_constraints is None else prior_constraints.intent_weights
    locked_pois = _parse_locked_pois(message) or (prior_constraints.locked_pois if prior_constraints else [])

    missing_fields = [
        field for field, value in (
            ("group_size", group_size),
            ("start_time", start_time),
            ("return_deadline", return_deadline),
            ("budget_vnd", budget_vnd),
        ) if value is None
    ]
    labels = {
        "group_size": "số người",
        "start_time": "giờ bắt đầu",
        "return_deadline": "giờ phải về",
        "budget_vnd": "tổng ngân sách",
    }
    clarification = (
        "Bạn cho mình biết " + ", ".join(labels[field] for field in missing_fields) + " nhé."
        if missing_fields else None
    )
    constraints = StructuredConstraints(
        trip_date=trip_date,
        group_size=group_size,
        start_time=start_time,
        return_deadline=return_deadline,
        budget_vnd=budget_vnd,
        travel_mode=travel_mode,
        travel_mode_confirmed=travel_mode_confirmed,
        intent_weights=intent_weights,
        locked_pois=locked_pois,
        is_complete=not missing_fields,
        missing_fields=missing_fields,
        clarification_question_vi=clarification,
    )

    reason_text = {
        "llm_not_configured": "chưa cấu hình khóa LLM",
        "llm_unavailable": "dịch vụ LLM bên ngoài đang lỗi hoặc quá thời gian chờ",
        "invalid_model_output": "phản hồi LLM không đúng cấu trúc an toàn",
    }.get(reason, "dịch vụ LLM bên ngoài không khả dụng")
    notes = []
    if not any(folded.count(keyword) for terms in _INTENT_KEYWORDS.values() for keyword in terms):
        notes.append("Chưa nhận diện rõ sở thích nên tỷ trọng mục đích đang để trung tính.")
    if not travel_mode_confirmed:
        notes.append("Chưa nêu phương tiện; tạm hiển thị xe máy, hãy kiểm tra lại.")
    notes.append("Bộ phân tích ngoại tuyến chỉ nhận diện mẫu câu rõ ràng; hãy kiểm tra các trường đã trích xuất.")
    if clarification:
        notes.append(clarification)
    reply = f"Đang dùng chế độ dự phòng ngoại tuyến vì {reason_text}. " + " ".join(notes)
    return constraints, reply
