"""Trip planning over SSE (the orchestration half of Travility's trips.py)."""
import datetime as dt
import json
import logging
from collections.abc import Iterator
from zoneinfo import ZoneInfo

import openai
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.adapters.llm.provider import LLMNotConfigured, LLMProviderError, StructuredOutputProvider
from app.models.entities import User
from app.models.trip_entities import Trip as TripRow
from app.schemas.ai import ChatDestinationContext, ChatMessage, ChatTripContext, TravelQuestionAnswer
from app.services import chat_response_service
from app.services.prompt_service import PromptRunner
from app.services.trip import forecast, llm, store
from app.services.trip.agent import (TripParseError, UnsupportedDestination, apply_answers, merge_trip, missing_questions,
                                     parse_trip, plan)
from app.services.trip.domain import Trip, TripAnswers
from app.services.trip.followup import changed_trip, followup
from app.services.trip.places import list_destinations, search_places

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
HCM_SLUG = "tp-hcm"
HCM = ChatDestinationContext(name="TP. Hồ Chí Minh", latitude=10.7769, longitude=106.7009)
NO_AI = "Chưa cấu hình AI cho lập lịch trình, bạn liên hệ quản trị viên nhé."


def _today() -> dt.date:
    return dt.datetime.now(VN_TZ).date()


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def guarded(db: Session, events):
    """Chạy generator chuỗi SSE của một việc; lỗi → event error tiếng Việt."""
    try:
        yield from events
    except (openai.OpenAIError, LLMProviderError):
        db.rollback()
        logger.exception("Lỗi gọi AI khi lập lịch trình")
        yield sse({"type": "error", "message": "Không kết nối được AI, kiểm tra mạng rồi thử lại nhé."})
    except LLMNotConfigured:
        db.rollback()
        yield sse({"type": "error", "message": NO_AI})
    except Exception:
        db.rollback()
        logger.exception("Lỗi không lường trước khi lập lịch trình")
        yield sse({"type": "error", "message": "Có lỗi khi lập lịch trình, bạn thử lại nhé."})


def _ai(db: Session) -> tuple[openai.OpenAI, str]:
    ai = llm.chat_client(db)
    if ai is None:
        raise LLMNotConfigured(NO_AI)
    return ai


def _dest(db: Session, slug: str) -> dict:
    return next(d for d in list_destinations(db) if d["slug"] == slug)


def _trip_event(trip_id: int, trip: Trip, dest: dict) -> str:
    return sse({"type": "trip", "trip_id": trip_id, "trip": trip.model_dump(mode="json"),
                "center": [dest["lon"], dest["lat"]]})


def _plan_and_save(db, client, model, trip_id: int, trip: Trip, dest: dict, user_messages: list[str], previous=None):
    rain = forecast.get_rain_chance(dest["lat"], dest["lon"], trip.start_date, trip.days, today=_today())
    for ev in plan(db, client, model, trip, lambda texts: llm.embed(db, texts), rain, store.hub_for(dest, trip),
                   user_messages, previous):
        if ev["type"] == "itinerary":
            version = store.save_itinerary(db, trip_id, ev["itinerary"], ev["places"])
            store.log_message(db, trip_id, "ai", ev["itinerary"]["summary"], version)
            ev = {**ev, "trip_id": trip_id, "version": version}
        yield sse(ev)


def _parse_input(user_messages: list[str]) -> str:
    if len(user_messages) == 1:
        return user_messages[0]
    return "\n".join(f"Tin nhắn {i + 1}: {m}" for i, m in enumerate(user_messages))


def _replan(db, client, model, trip_id: int, trip: Trip, user_messages: list[str], changes: dict, message: str):
    """Đổi Trip đã được đồng ý → lưu spec, lập lại với lịch cũ làm gợi ý."""
    try:
        trip = changed_trip(trip, changes)
    except ValidationError as e:
        yield sse({"type": "error", "message": e.errors()[0]["msg"].removeprefix("Value error, ")})
        return
    user_messages = [*user_messages, message]
    row = db.get(TripRow, trip_id)
    row.spec, row.user_messages, row.pending_replan = trip.model_dump(mode="json"), user_messages, None
    db.commit()
    dest = _dest(db, trip.destination)
    latest = store.latest_itinerary(db, trip_id)
    previous = (latest[1], store.itinerary_places(db, latest[1])) if latest else None
    yield _trip_event(trip_id, trip, dest)
    yield from _plan_and_save(db, client, model, trip_id, trip, dest, user_messages, previous)


def _follow_up(db, client, model, prev: TripRow, itin, dest: dict, message: str):
    """Trip đã có lịch trình: trả lời / sửa, không lập lại từ đầu (#22)."""
    trip = Trip.model_validate(prev.spec)
    rain = [d.rain_chance for d in itin.days]
    pending = prev.pending_replan
    prev.pending_replan = None  # chỉ sống 1 lượt
    db.commit()
    for ev in followup(db, client, model, trip, itin, store.itinerary_places(db, itin), message, rain,
                       store.hub_for(dest, trip), lambda texts: llm.embed(db, texts), pending):
        if ev["type"] == "replan_confirmed":
            yield from _replan(db, client, model, prev.id, trip, prev.user_messages, pending["changes"],
                               pending["message"])
            return
        if ev["type"] == "confirm_replan":
            prev.pending_replan = {k: ev[k] for k in ("changes", "message", "text")}
            db.commit()
            store.log_message(db, prev.id, "ai", ev["text"])
            ev = {**ev, "trip_id": prev.id}
        elif ev["type"] == "itinerary":
            version = store.save_itinerary(db, prev.id, ev["itinerary"], ev["places"])
            store.log_message(db, prev.id, "ai", ev["itinerary"]["summary"], version)
            prev.user_messages = [*prev.user_messages, message]  # reassign: JSON columns are not mutation-tracked
            db.commit()
            ev = {**ev, "trip_id": prev.id, "version": version}
        elif ev["type"] == "answer":
            store.log_message(db, prev.id, "ai", ev["text"])
        yield sse(ev)


def _run(db: Session, user: User, message: str, prev: TripRow | None = None):
    dests = {d["slug"]: d for d in list_destinations(db)}
    client, model = _ai(db)
    user_messages = [*(prev.user_messages if prev else []), message]
    yield sse({"type": "thinking", "text": "Đang đọc yêu cầu của bạn…"})
    latest = store.latest_itinerary(db, prev.id) if prev else None
    if latest:
        store.log_message(db, prev.id, "user", message)
        yield from _follow_up(db, client, model, prev, latest[1], dests[prev.spec["destination"]], message)
        return
    try:
        trip = parse_trip(client, model, _parse_input(user_messages), {slug: d["name"] for slug, d in dests.items()},
                          _today())
        if prev:  # tin nhắn tiếp theo: giữ câu trả lời cũ, không hỏi lại lần 2 (spec §3)
            trip = apply_answers(merge_trip(Trip.model_validate(prev.spec), trip), TripAnswers())
    except (UnsupportedDestination, TripParseError) as e:
        yield sse({"type": "error", "message": str(e)})
        return
    except ValidationError as e:
        yield sse({"type": "error", "message": e.errors()[0]["msg"].removeprefix("Value error, ")})
        return
    d = dests[trip.destination]
    spec = trip.model_dump(mode="json")
    if prev:
        prev.spec, prev.user_messages = spec, user_messages
        row = prev
    else:
        row = TripRow(user_id=user.id, spec=spec, user_messages=user_messages)
        db.add(row)
        db.flush()
    store.log_message(db, row.id, "user", message)  # commits the Trip too
    yield _trip_event(row.id, trip, d)
    questions = [] if prev else missing_questions(trip)
    if questions:
        yield sse({"type": "clarify", "trip_id": row.id, "questions": questions})
        return
    yield from _plan_and_save(db, client, model, row.id, trip, d, user_messages)


def _travel_answer(db: Session, provider: StructuredOutputProvider, message: str, trip: Trip | None) -> str:
    found = search_places(db, HCM_SLUG, message, embed_fn=lambda texts: None, limit=5)
    catalog_context = json.dumps([{"name": p.name, "description": p.description, "open_hours": p.open_hours,
                                   "price": p.price} for p in found], ensure_ascii=False)
    trip_context = {"trip_date": trip.start_date.isoformat() if trip and trip.start_date else None,
                    "destination": HCM.model_dump()}
    return PromptRunner(provider).run(
        "TRAVEL_ASSISTANT",
        {"message": message, "language": "vi", "trip_context": trip_context, "catalog_context": catalog_context},
        TravelQuestionAnswer,
    ).reply



def _message(db: Session, user: User, message: str, trip_id: int | None, provider: StructuredOutputProvider):
    prev = store.trip_row(db, user.id, trip_id) if trip_id is not None else None
    if trip_id is not None and not prev:
        yield sse({"type": "error", "message": "Không tìm thấy chuyến đi"})
        return
    trip = Trip.model_validate(prev.spec) if prev else None
    intent, topic, reason = chat_response_service.classify_chat_intent(message, prev is not None, provider)
    if reason is not None and topic != "weather":
        # The offline keyword router misreads most trip requests as out of scope; only trust its weather match
        # and let the planner (which reports a missing or unreachable AI itself) take everything else.
        intent = "planning"
    text = None
    if intent == "out_of_scope":
        text = chat_response_service._out_of_scope_reply("vi")
    elif intent == "travel_information" and topic == "weather":
        # ChatMessage caps messages at 1000 chars; the trip chat allows 2000.
        payload = ChatMessage(message=message[:1000], language="vi",
                              trip_context=ChatTripContext(trip_date=trip.start_date if trip else None, destination=HCM))
        text = chat_response_service._weather_reply(payload, provider, db, None).reply
    elif intent == "travel_information" and not (prev and store.latest_itinerary(db, prev.id)):
        text = _travel_answer(db, provider, message, trip)
    if text is None:
        yield from _run(db, user, message, prev)
        return
    if prev:
        store.log_message(db, prev.id, "user", message)
        store.log_message(db, prev.id, "ai", text)
    yield sse({"type": "answer", "text": text})


def run_message(db: Session, user: User, message: str, trip_id: int | None,
                provider: StructuredOutputProvider) -> Iterator[str]:
    return guarded(db, _message(db, user, message, trip_id, provider))


def _plan(db: Session, user: User, trip_id: int, answers: TripAnswers):
    row = store.trip_row(db, user.id, trip_id)
    trip = apply_answers(Trip.model_validate(row.spec), answers)
    row.spec = trip.model_dump(mode="json")
    db.commit()
    client, model = _ai(db)
    dest = _dest(db, trip.destination)
    yield _trip_event(trip_id, trip, dest)
    yield from _plan_and_save(db, client, model, trip_id, trip, dest, row.user_messages)


def run_plan(db: Session, user: User, trip_id: int, answers: TripAnswers) -> Iterator[str]:
    return guarded(db, _plan(db, user, trip_id, answers))


def _replan_job(db: Session, user: User, trip_id: int, changes: dict, message: str):
    row = store.trip_row(db, user.id, trip_id)
    client, model = _ai(db)
    yield from _replan(db, client, model, trip_id, Trip.model_validate(row.spec), row.user_messages, changes, message)


def run_replan(db: Session, user: User, trip_id: int, changes: dict, message: str) -> Iterator[str]:
    return guarded(db, _replan_job(db, user, trip_id, changes, message))
