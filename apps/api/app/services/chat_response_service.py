"""Routes the latest chat turn and keeps planner state isolated from Q&A."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.adapters.llm.provider import LLMNotConfigured, LLMProviderError, StructuredOutputProvider
from app.core.config import settings
from app.models.entities import Experience, POI
from app.prompts.registry import catalog
from app.repositories.experience_repository import ExperienceRepository
from app.schemas.ai import (
    ChatDestinationContext,
    ChatIntentDecision,
    ChatMessage,
    ChatReply,
    ChatTripContext,
    ChatWeatherForecast,
    StructuredConstraints,
    TravelQuestionAnswer,
)
from app.services.offline_chat_fallback import build_offline_constraints
from app.services.open_meteo_service import OpenMeteoUnavailable, daily_forecast
from app.services.prompt_service import InvalidStructuredOutput, PromptRunner


LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
FALLBACK_VERSION = "1.0.0"


def _fold(value: str) -> str:
    value = value.replace("đ", "d").replace("Đ", "D")
    return "".join(char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)).lower()


def _assistant_mode(provider: StructuredOutputProvider) -> str:
    if provider.model_name == "not-configured":
        return "local_fallback"
    base_url = getattr(provider, "base_url", "")
    return "gemini_compatible" if "generativelanguage" in base_url else "openai_compatible"


def _offline_intent(message: str, has_planning_context: bool = False) -> tuple[str, str | None]:
    text = _fold(message)
    if any(word in text for word in ("mua", "thoi tiet", "weather", "rain", "raining", "precipitation", "temperature", "nhiet do", "nang khong")) or re.search(r"\bbao\b(?! tang)", text):
        return "travel_information", "weather"

    if any(word in text for word in (
        "lap lich", "lich trinh", "itinerary", "schedule", "plan a trip", "di du lich", "nhom minh",
        "ngan sach", "budget", "phai ve", "ve truoc", "xuat phat", "di luc", "xe may", "motorcycle",
        "di bo", "walking", "o to", "car", "so nguoi", "moi nguoi", "thich", "uu tien", "muon di", "want to go",
    )):
        return "planning", None

    topics = {
        "place": ("dia diem", "cho nao", "o dau", "where", "hotel", "khach san", "tham quan", "landmark"),
        "activity": ("choi gi", "lam gi", "hoat dong", "activity", "things to do"),
        "opening_hours": ("gio mo cua", "mo cua luc", "dong cua", "opening hours", "open now"),
        "food": ("an gi", "quan an", "mon an", "cafe", "ca phe", "restaurant", "food", "eat"),
        "transport": ("di den", "di nhu the nao", "phuong tien", "bus", "metro", "transport", "get to"),
    }
    for topic, phrases in topics.items():
        if any(phrase in text for phrase in phrases):
            return "travel_information", topic
    if has_planning_context and (
        re.fullmatch(r"(?:ngay\s+)?(?:hom\s+nay|mai|kia|mot|today|tomorrow|day\s+after\s+tomorrow|\d{1,2}[/-]\d{1,2}(?:[/-]20\d{2})?|\d{1,2}\s+thang\s+\d{1,2}(?:\s+nam\s+20\d{2})?|20\d{2}-\d{2}-\d{2})", text)
        or re.fullmatch(r"\d{1,2}(?::\d{2})?(?:\s*(?:-|–|den)\s*\d{1,2}(?::\d{2})?)?", text)
        or re.fullmatch(r"\d{1,3}(?:[.,]\d+)?\s*(?:trieu|tr|nghin|ngan|k|vnd|dong|d)", text)
        or re.fullmatch(r"\d{1,2}\s*(?:nguoi|khach|thanh vien)", text)
        or any(mode in text for mode in ("xe may", "motorcycle", "motorbike", "di bo", "walking", "o to", "xe hoi", "car", "xe buyt", "metro", "public transit"))
    ):
        return "planning", None
    return "out_of_scope", None


def _language_is_english(language: str) -> bool:
    return language == "en"


def _reply(
    payload: ChatMessage,
    intent: str,
    reply: str,
    *,
    provider: StructuredOutputProvider,
    prompt_version: str | None = None,
    reason: str | None = None,
    constraints: StructuredConstraints | None = None,
    forecast: ChatWeatherForecast | None = None,
) -> ChatReply:
    is_fallback = reason is not None
    return ChatReply(
        status="fallback" if is_fallback else "parsed",
        assistant_mode="local_fallback" if is_fallback else _assistant_mode(provider),
        conversation_id=payload.conversation_id,
        prompt_version=prompt_version if not is_fallback else None,
        fallback_version=FALLBACK_VERSION if is_fallback else None,
        fallback_reason=reason,
        intent=intent,
        reply=reply,
        structured_constraints=constraints,
        weather_forecast=forecast,
    )


def _planning_text(payload: ChatMessage) -> str:
    turns = [*payload.prior_user_messages, payload.message]
    return "\n".join(f"Tin nhắn {index + 1} của du khách: {turn}" for index, turn in enumerate(turns))


def _explicit_poi(message: str, db: Session) -> POI | None:
    folded = _fold(message)
    pois = ExperienceRepository(db).list_pois()
    matches = [poi for poi in pois if len(_fold(poi.name)) >= 3 and _fold(poi.name) in folded]
    return max(matches, key=lambda poi: len(_fold(poi.name))) if matches else None


def _has_unknown_explicit_location(message: str) -> bool:
    text = _fold(message)
    cue = re.search(r"\b(?:o|tai|in|at|near)\s+([a-z0-9][a-z0-9 -]{1,45})", text)
    if not cue:
        return False
    candidate = cue.group(1).strip()
    return candidate not in {"do", "day", "there", "this place", "khu nay"} and not candidate.startswith("dau ")


def _resolve_weather_location(message: str, context: ChatTripContext | None, db: Session) -> ChatDestinationContext | None:
    match = _explicit_poi(message, db)
    if match:
        return ChatDestinationContext(name=match.name, latitude=match.latitude, longitude=match.longitude)
    if _has_unknown_explicit_location(message):
        return None
    return context.destination if context else None


def _resolve_weather_date(message: str, context: ChatTripContext | None) -> date | None:
    text = _fold(message)
    today = datetime.now(LOCAL_TZ).date()
    if re.search(r"\b(?:hom nay|today)\b", text):
        return today
    if re.search(r"\b(?:ngay kia|ngay mot|day after tomorrow)\b", text):
        return today + timedelta(days=2)
    if re.search(r"\b(?:ngay mai|mai|tomorrow)\b", text):
        return today + timedelta(days=1)
    iso = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text)
    dmy = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](20\d{2}))?\b", text)
    try:
        if iso:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        if dmy:
            return date(int(dmy.group(3) or today.year), int(dmy.group(2)), int(dmy.group(1)))
    except ValueError:
        return None
    return context.trip_date if context else None


def _format_forecast(data: dict[str, Any]) -> tuple[str, ChatWeatherForecast]:
    forecast = ChatWeatherForecast.model_validate(data)
    local_time = forecast.retrieved_at.astimezone(LOCAL_TZ).strftime("%H:%M %d/%m/%Y")
    day_label = forecast.forecast_date.strftime("%d/%m/%Y")
    reply = (
        f"Dự báo tại {forecast.location} ngày {day_label}: xác suất mưa cao nhất "
        f"{forecast.precipitation_probability_pct}%, lượng mưa dự kiến {forecast.precipitation_sum_mm:g} mm. "
        f"Đây là dự báo, không phải cam kết thời tiết. Cập nhật lúc {local_time} (giờ Việt Nam), "
        f"nguồn: {forecast.source} — {forecast.source_url}. {forecast.attribution}"
    )
    return reply, forecast


def _weather_reply(payload: ChatMessage, provider: StructuredOutputProvider, db: Session, reason: str | None) -> ChatReply:
    location = _resolve_weather_location(payload.message, payload.trip_context, db)
    if location is None:
        text = (
            "Bạn muốn xem dự báo thời tiết ở đâu? Hãy nêu địa điểm trong tin nhắn hoặc chọn điểm đến ở khung tuyến đường."
            if not _language_is_english(payload.language)
            else "Where would you like the forecast? Name a place in your message or choose a destination in the route panel."
        )
        return _reply(payload, "travel_information", text, provider=provider, reason=reason)

    requested_date = _resolve_weather_date(payload.message, payload.trip_context)
    if requested_date is None:
        text = "Bạn muốn xem dự báo cho ngày nào?" if not _language_is_english(payload.language) else "Which date should I check?"
        return _reply(payload, "travel_information", text, provider=provider, reason=reason)
    try:
        data = daily_forecast(location.latitude, location.longitude, requested_date, location.name)
    except OpenMeteoUnavailable:
        text = (
            f"Mình chưa lấy được dự báo Open-Meteo cho {location.name} ngày {requested_date.strftime('%d/%m/%Y')}, nên không thể xác nhận trời có mưa hay không."
            if not _language_is_english(payload.language)
            else f"I could not retrieve an Open-Meteo forecast for {location.name} on {requested_date.isoformat()}, so I cannot confirm whether it will rain."
        )
        return _reply(payload, "travel_information", text, provider=provider, reason=reason)
    text, forecast = _format_forecast(data)
    if _language_is_english(payload.language):
        text = (
            f"Forecast for {forecast.location} on {forecast.forecast_date.isoformat()}: maximum precipitation probability "
            f"{forecast.precipitation_probability_pct}%, expected precipitation {forecast.precipitation_sum_mm:g} mm. "
            f"This is a forecast, not a guarantee. Retrieved {forecast.retrieved_at.astimezone(LOCAL_TZ).strftime('%H:%M %d/%m/%Y')} Vietnam time; "
            f"source: {forecast.source} — {forecast.source_url}. {forecast.attribution}"
        )
    return _reply(payload, "travel_information", text, provider=provider, reason=reason, forecast=forecast)


def _catalog_context(message: str, db: Session) -> tuple[list[POI], str]:
    folded = _fold(message)
    pois = ExperienceRepository(db).list_pois()
    named = [poi for poi in pois if len(_fold(poi.name)) >= 3 and _fold(poi.name) in folded]
    if named:
        selected = sorted(named, key=lambda poi: len(_fold(poi.name)), reverse=True)[:5]
    else:
        words = [word for word in re.findall(r"[a-z0-9]{3,}", folded) if word not in {
            "quan", "nao", "cho", "mot", "nhung", "giup", "minh", "toi", "ban", "dep", "ngon", "gan", "where", "best", "good",
        }]
        scored = []
        for poi in pois:
            haystack = _fold(" ".join((poi.name, poi.category, poi.district or "", poi.address, *(poi.tags or []))))
            score = sum(1 for word in words if word in haystack)
            if score:
                scored.append((score, poi))
        selected = [poi for _, poi in sorted(scored, key=lambda item: (-item[0], item[1].name))[:5]]
    if not selected:
        return [], ""

    experiences = db.scalars(
        select(Experience).where(Experience.poi_id.in_([poi.id for poi in selected])).options(joinedload(Experience.poi)).order_by(Experience.name).limit(20)
    ).unique().all()
    experience_by_poi: dict[str, list[Experience]] = {}
    for experience in experiences:
        if settings.real_data_only and (experience.verification_status != "verified" or experience.poi.verification_status != "verified"):
            continue
        experience_by_poi.setdefault(experience.poi_id, []).append(experience)

    records: list[dict[str, Any]] = []
    for poi in selected:
        record: dict[str, Any] = {
            "name": poi.name,
            "category": poi.category,
            "district": poi.district,
            "address": poi.address,
            "description": poi.description,
            "opening_hours_catalog": poi.opening_hours,
            "ticket_info_catalog": poi.ticket_info,
            "source_attribution": poi.source_attribution,
            "verification_status": poi.verification_status,
            "experiences": [
                {
                    "name": item.name,
                    "description": item.description,
                    "price_vnd_catalog": item.price_vnd,
                    "price_basis": item.price_basis,
                    "duration_min": item.duration_min,
                    "intent_tags": item.intent_tags or [],
                    "verification_status": item.verification_status,
                }
                for item in experience_by_poi.get(poi.id, [])[:4]
            ],
        }
        records.append(record)
    import json
    return selected, json.dumps(records, ensure_ascii=False)


def _catalog_fallback_reply(message: str, pois: list[POI], language: str) -> str:
    is_english = _language_is_english(language)
    if not pois:
        return (
            "Mình chưa tìm thấy địa điểm phù hợp trong danh mục hiện có. Bạn cho mình biết quận hoặc loại trải nghiệm muốn tìm nhé."
            if not is_english
            else "I could not find a matching place in the current catalog. Tell me the district or type of experience you want."
        )
    rows = []
    for poi in pois[:3]:
        detail = poi.description or poi.address
        hours = f" Giờ trong danh mục: {poi.opening_hours}." if poi.opening_hours else ""
        rows.append(f"• {poi.name} ({poi.district or poi.category}) — {detail}{hours}")
    heading = "Mình tìm thấy một số địa điểm trong danh mục:" if not is_english else "I found these places in the catalog:"
    note = " Thông tin giờ mở cửa là dữ liệu danh mục, bạn nên xác nhận trước khi đi." if not is_english else " Catalog hours can change, so confirm them before visiting."
    return heading + "\n" + "\n".join(rows) + note


def _out_of_scope_reply(language: str) -> str:
    if _language_is_english(language):
        return "I can help with trip planning and travel questions. Ask me about an itinerary, weather, places, food, or getting around."
    return "Mình hỗ trợ lập lịch trình và thông tin du lịch. Bạn có thể hỏi về kế hoạch đi chơi, thời tiết, địa điểm, ăn uống hoặc phương tiện."


def route_chat_message(payload: ChatMessage, provider: StructuredOutputProvider, db: Session) -> ChatReply:
    runner = PromptRunner(provider)
    reason: str | None = None
    decision: ChatIntentDecision | None = None
    try:
        decision = runner.run(
            "CHAT_INTENT_ROUTER",
            {"message": payload.message, "has_planning_context": bool(payload.trip_context and payload.trip_context.has_planning_context)},
            ChatIntentDecision,
        )
    except LLMNotConfigured:
        reason = "llm_not_configured"
    except LLMProviderError:
        reason = "llm_unavailable"
    except InvalidStructuredOutput:
        reason = "invalid_model_output"

    if decision is None:
        intent, topic = _offline_intent(payload.message, bool(payload.trip_context and payload.trip_context.has_planning_context))
    else:
        intent, topic = decision.intent, decision.topic

    if intent == "out_of_scope":
        return _reply(payload, intent, _out_of_scope_reply(payload.language), provider=provider, prompt_version=catalog.version, reason=reason)

    if intent == "planning":
        planning_text = _planning_text(payload)
        try:
            constraints = runner.run(
                "CONVERSATION_PARSER",
                {
                    "message": planning_text,
                    "latest_message": payload.message,
                    "conversation_id": payload.conversation_id,
                    "trip_date_context": payload.trip_context.trip_date if payload.trip_context else None,
                    "existing_constraints": payload.trip_context.planner_constraints.model_dump(mode="json")
                    if payload.trip_context and payload.trip_context.planner_constraints else None,
                    "today_local": datetime.now(LOCAL_TZ).date(),
                },
                StructuredConstraints,
            )
            return _reply(
                payload,
                "planning",
                constraints.clarification_question_vi or "Mình đã ghi nhận các ràng buộc chuyến đi.",
                provider=provider,
                prompt_version=catalog.version,
                constraints=constraints,
            )
        except (LLMNotConfigured, LLMProviderError, InvalidStructuredOutput) as error:
            if reason is None:
                reason = "llm_not_configured" if isinstance(error, LLMNotConfigured) else "invalid_model_output" if isinstance(error, InvalidStructuredOutput) else "llm_unavailable"
            if not settings.llm_fallback_enabled:
                if reason == "llm_not_configured":
                    raise LLMNotConfigured("The local chat fallback is disabled.") from error
                raise LLMProviderError("The external LLM is unavailable and the local fallback is disabled.") from error
            constraints, reply = build_offline_constraints(
                planning_text,
                reason,
                trip_date_context=payload.trip_context.trip_date if payload.trip_context else None,
                latest_message=payload.message,
                prior_constraints=payload.trip_context.planner_constraints if payload.trip_context else None,
            )
            return _reply(payload, "planning", reply, provider=provider, reason=reason, constraints=constraints)

    if topic == "weather":
        return _weather_reply(payload, provider, db, reason)

    catalog_pois, catalog_context = _catalog_context(payload.message, db)
    if not catalog_context:
        unavailable = (
            "Mình chưa tìm được dữ liệu danh mục phù hợp để trả lời câu hỏi du lịch này. Hãy nêu tên địa điểm hoặc khu vực cụ thể nhé."
            if not _language_is_english(payload.language)
            else "I could not find relevant catalog data for this travel question. Please name a place or area."
        )
        return _reply(payload, "travel_information", unavailable, provider=provider, reason=reason or "llm_unavailable")

    if decision is None:
        return _reply(payload, "travel_information", _catalog_fallback_reply(payload.message, catalog_pois, payload.language), provider=provider, reason=reason)
    try:
        answer = runner.run(
            "TRAVEL_ASSISTANT",
            {
                "message": payload.message,
                "language": payload.language,
                "trip_context": payload.trip_context.model_dump(
                    mode="json", exclude={"has_planning_context", "planner_constraints"}
                ) if payload.trip_context else {},
                "catalog_context": catalog_context,
            },
            TravelQuestionAnswer,
        )
        return _reply(payload, "travel_information", answer.reply, provider=provider, prompt_version=catalog.version)
    except (LLMNotConfigured, LLMProviderError, InvalidStructuredOutput) as error:
        fallback_reason = "llm_not_configured" if isinstance(error, LLMNotConfigured) else "invalid_model_output" if isinstance(error, InvalidStructuredOutput) else "llm_unavailable"
        return _reply(payload, "travel_information", _catalog_fallback_reply(payload.message, catalog_pois, payload.language), provider=provider, reason=fallback_reason)
