import datetime as dt
import json
import logging
from zoneinfo import ZoneInfo

import openai
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, ValidationError

from app import forecast, jobs, llm, multi
from app.agent import (TripParseError, UnsupportedDestination, apply_answers, merge_trip, missing_questions,
                       parse_trip, plan)
from app.domain import Hub, Itinerary, Trip, TripAnswers
from app.followup import InvalidEdit, changed_trip, followup, review_group_feedback
from app.rules import InvalidDraft
from app.auth import current_user, get_shard
from app.config import settings
from app.db import get_conn, shard_conn
from app.places_client import PLACES_DOWN, PlacesDown, get_places, list_destinations

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

router = APIRouter()
# SSE chạy sau khi handler trả về → tự mở kết nối riêng tới shard của User; test thay bằng kết nối test
stream_conn = shard_conn


def _today() -> dt.date:
    """Hôm nay theo giờ VN. DEMO_TODAY đóng băng ngày để bản ghi replay của llm-gateway trúng cache."""
    return settings.demo_today or dt.datetime.now(VN_TZ).date()


class NewTrip(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    trip_id: int | None = None  # có → tin nhắn tiếp theo của Trip đang mở (PRD §5.4: chat gắn với Trip)


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.get("/destinations")
def destinations(conn=Depends(get_conn)):
    return list_destinations(conn)


def guarded(events):
    """Chạy generator chuỗi SSE của một việc; lỗi → event error tiếng Việt. Dùng chung cho request và worker."""
    try:
        yield from events
    except openai.OpenAIError:
        logger.exception("Lỗi gọi AI khi lập lịch trình")
        yield sse({"type": "error", "message": "Không kết nối được AI, kiểm tra mạng rồi thử lại nhé."})
    except PlacesDown:
        logger.exception("Service places không trả lời")
        yield sse({"type": "error", "message": PLACES_DOWN})
    except Exception:
        logger.exception("Lỗi không lường trước khi lập lịch trình")
        yield sse({"type": "error", "message": "Có lỗi khi lập lịch trình, bạn thử lại nhé."})


def _stream(kind: str, user_id: int, **params) -> StreamingResponse:
    """Chạy việc JOBS[kind] trong SSE. Có REDIS_URL → đẩy vào queue cho planner và chuyển event về (spec scale §5);
    thiếu → chạy ngay trong request. params phải JSON được."""
    if settings.redis_url:
        jobs.check_rate(user_id)
        job_id = jobs.enqueue(kind, user_id, params)
        return StreamingResponse(jobs.relay(job_id), media_type="text/event-stream", headers={"X-Job-Id": job_id})

    def events():
        with stream_conn(user_id) as conn:
            yield from guarded(JOBS[kind](conn, user_id, **params))

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/trips")
def create_trip(body: NewTrip, user_id: int = Depends(current_user), conn=Depends(get_shard)):
    if body.trip_id is not None and not conn.execute(
            "SELECT 1 FROM trips WHERE id = %s AND user_id = %s", (body.trip_id, user_id)).fetchone():
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    return _stream("message", user_id, message=body.message, trip_id=body.trip_id)


def hub_for(dest: dict, trip: Trip) -> Hub | None:
    h = dest["hubs"].get(trip.arrival_mode) if trip.arrival_mode else None
    return Hub.model_validate(h) if h else None


def _trip_event(trip_id: int, trip: Trip, dest: dict) -> str:
    return sse({"type": "trip", "trip_id": trip_id, "trip": trip.model_dump(mode="json"),
                "center": [dest["lon"], dest["lat"]]})


def save_itinerary(conn, trip_id: int, itinerary: dict, places: dict) -> int:
    """Lưu một version Itinerary mới (bất biến) và trả số version."""
    with conn.transaction():
        conn.execute("SELECT id FROM trips WHERE id = %s FOR UPDATE", (trip_id,)).fetchone()
        return conn.execute(
            """INSERT INTO itineraries(trip_id, version, data)
               SELECT %s, COALESCE(MAX(version), 0) + 1, %s FROM itineraries WHERE trip_id = %s
               RETURNING version""",
            (trip_id, Jsonb({"itinerary": itinerary, "places": places}), trip_id)).fetchone()["version"]


def log_message(conn, trip_id: int, role: str, text: str, version: int | None = None) -> None:
    conn.execute("INSERT INTO messages(trip_id, role, text, version) VALUES (%s, %s, %s, %s)",
                 (trip_id, role, text, version))


def _plan_and_save(conn, client, trip_id: int, trip: Trip, dest: dict, user_messages: list[str], previous=None):
    rain = forecast.get_rain_chance(dest["lat"], dest["lon"], trip.start_date, trip.days, today=_today())
    planner = multi.plan if settings.planner_mode == "multi" else plan
    for ev in planner(conn, client, settings.llm_model, trip, llm.embed, rain, hub_for(dest, trip), user_messages,
                      previous):
        if ev["type"] == "itinerary":
            version = save_itinerary(conn, trip_id, ev["itinerary"], ev["places"])
            log_message(conn, trip_id, "ai", ev["itinerary"]["summary"], version)
            ev = {**ev, "trip_id": trip_id, "version": version}
        yield sse(ev)


def _parse_input(user_messages: list[str]) -> str:
    if len(user_messages) == 1:
        return user_messages[0]
    return "\n".join(f"Tin nhắn {i + 1}: {m}" for i, m in enumerate(user_messages))


def load_itinerary(conn, trip_id: int, version: int | None = None) -> tuple[int, Itinerary, dict] | None:
    """Đọc một version (mặc định bản mới nhất); stop.pinned lấy từ trips.pinned_place_ids, không từ data đã lưu."""
    row = conn.execute(
        """SELECT i.version, i.data, t.pinned_place_ids FROM itineraries i JOIN trips t ON t.id = i.trip_id
           WHERE i.trip_id = %s AND (%s::int IS NULL OR i.version = %s) ORDER BY i.version DESC LIMIT 1""",
        (trip_id, version, version)).fetchone()
    if not row:
        return None
    itin = Itinerary.model_validate(row["data"]["itinerary"])
    pins = set(row["pinned_place_ids"])
    for d in itin.days:
        for s in d.stops:
            s.pinned = s.place_id in pins
    return row["version"], itin, row["data"]["places"]


def latest_itinerary(conn, trip_id: int) -> tuple[int, Itinerary] | None:
    r = load_itinerary(conn, trip_id)
    return (r[0], r[1]) if r else None


def itinerary_places(conn, itin: Itinerary) -> dict:
    ids = {s.place_id for d in itin.days for s in d.stops} | ({itin.stay_place_id} - {None})
    return get_places(conn, list(ids))


def _follow_up(conn, client, prev: dict, itin: Itinerary, dest: dict, message: str):
    """Trip đã có lịch trình: trả lời / sửa, không lập lại từ đầu (#22)."""
    trip = Trip.model_validate(prev["spec"])
    rain = [d.rain_chance for d in itin.days]
    pending = prev["pending_replan"]
    conn.execute("UPDATE trips SET pending_replan = NULL WHERE id = %s", (prev["id"],))  # chỉ sống 1 lượt
    for ev in followup(conn, client, settings.llm_model, trip, itin, itinerary_places(conn, itin), message,
                       rain, hub_for(dest, trip), llm.embed, pending):
        if ev["type"] == "replan_confirmed":
            yield from _replan(conn, client, prev["id"], trip, prev["user_messages"], pending["changes"],
                               pending["message"])
            return
        if ev["type"] == "confirm_replan":
            conn.execute("UPDATE trips SET pending_replan = %s WHERE id = %s",
                         (Jsonb({k: ev[k] for k in ("changes", "message", "text")}), prev["id"]))
            log_message(conn, prev["id"], "ai", ev["text"])
            ev = {**ev, "trip_id": prev["id"]}
        elif ev["type"] == "itinerary":
            version = save_itinerary(conn, prev["id"], ev["itinerary"], ev["places"])
            log_message(conn, prev["id"], "ai", ev["itinerary"]["summary"], version)
            conn.execute("UPDATE trips SET user_messages = user_messages || %s WHERE id = %s", ([message], prev["id"]))
            ev = {**ev, "trip_id": prev["id"], "version": version}
        elif ev["type"] == "answer":
            log_message(conn, prev["id"], "ai", ev["text"])
        yield sse(ev)


def _replan(conn, client, trip_id: int, trip: Trip, user_messages: list[str], changes: dict, message: str):
    """Đổi Trip đã được đồng ý → lưu spec, lập lại với lịch cũ làm gợi ý."""
    try:
        trip = changed_trip(trip, changes)
    except ValidationError as e:
        yield sse({"type": "error", "message": e.errors()[0]["msg"].removeprefix("Value error, ")})
        return
    user_messages = [*user_messages, message]
    conn.execute("UPDATE trips SET spec = %s, user_messages = %s, pending_replan = NULL WHERE id = %s",
                 (Jsonb(trip.model_dump(mode="json")), user_messages, trip_id))
    dest = next(d for d in list_destinations(conn) if d["slug"] == trip.destination)
    latest = latest_itinerary(conn, trip_id)
    previous = (latest[1], itinerary_places(conn, latest[1])) if latest else None
    yield _trip_event(trip_id, trip, dest)
    yield from _plan_and_save(conn, client, trip_id, trip, dest, user_messages, previous)


def _run(conn, user_id: int, message: str, prev: dict | None = None):
    dests = {d["slug"]: d for d in list_destinations(conn)}
    client = llm.chat_client()
    user_messages = [*(prev["user_messages"] if prev else []), message]
    yield sse({"type": "thinking", "text": "Đang đọc yêu cầu của bạn…"})
    latest = latest_itinerary(conn, prev["id"]) if prev else None
    if latest:
        log_message(conn, prev["id"], "user", message)
        yield from _follow_up(conn, client, prev, latest[1], dests[prev["spec"]["destination"]], message)
        return
    try:
        trip = parse_trip(client, settings.llm_model, _parse_input(user_messages),
                          {slug: d["name"] for slug, d in dests.items()},
                          _today())
        if prev:  # tin nhắn tiếp theo: giữ câu trả lời cũ, không hỏi lại lần 2 (spec §3)
            trip = apply_answers(merge_trip(Trip.model_validate(prev["spec"]), trip), TripAnswers())
    except (UnsupportedDestination, TripParseError) as e:
        yield sse({"type": "error", "message": str(e)})
        return
    except ValidationError as e:
        yield sse({"type": "error", "message": e.errors()[0]["msg"].removeprefix("Value error, ")})
        return
    d = dests[trip.destination]
    spec = Jsonb(trip.model_dump(mode="json"))
    if prev:
        trip_id = prev["id"]
        conn.execute("UPDATE trips SET spec = %s, user_messages = %s WHERE id = %s", (spec, user_messages, trip_id))
    else:
        trip_id = conn.execute("INSERT INTO trips(user_id, spec, user_messages) VALUES (%s, %s, %s) RETURNING id",
                               (user_id, spec, user_messages)).fetchone()["id"]
    log_message(conn, trip_id, "user", message)
    yield _trip_event(trip_id, trip, d)
    questions = [] if prev else missing_questions(trip)
    if questions:
        yield sse({"type": "clarify", "trip_id": trip_id, "questions": questions})
        return
    yield from _plan_and_save(conn, client, trip_id, trip, d, user_messages)


def _trip_row(conn, user_id: int, trip_id: int) -> dict | None:
    return conn.execute("SELECT id, spec, user_messages, pending_replan FROM trips WHERE id = %s AND user_id = %s",
                        (trip_id, user_id)).fetchone()


def _job_message(conn, user_id: int, message: str, trip_id: int | None = None):
    prev = _trip_row(conn, user_id, trip_id) if trip_id is not None else None
    if trip_id is not None and not prev:
        yield sse({"type": "error", "message": "Không tìm thấy chuyến đi"})
        return
    yield from _run(conn, user_id, message, prev)


def _job_plan(conn, user_id: int, trip_id: int):
    row = _trip_row(conn, user_id, trip_id)
    trip = Trip.model_validate(row["spec"])
    dest = next(d for d in list_destinations(conn) if d["slug"] == trip.destination)
    yield _trip_event(trip_id, trip, dest)
    yield from _plan_and_save(conn, llm.chat_client(), trip_id, trip, dest, row["user_messages"])


def _job_replan(conn, user_id: int, trip_id: int, changes: dict, message: str):
    row = _trip_row(conn, user_id, trip_id)
    yield from _replan(conn, llm.chat_client(), trip_id, Trip.model_validate(row["spec"]), row["user_messages"],
                       changes, message)


def _job_group_review(conn, user_id: int, trip_id: int, source_version: int, feedback: str):
    row = _trip_row(conn, user_id, trip_id)
    source = load_itinerary(conn, trip_id, source_version)
    base = load_itinerary(conn, trip_id)
    if not row or not source or not base:
        yield sse({"type": "error", "message": "Không tìm thấy chuyến đi hoặc phiên bản lịch trình"})
        return
    source_number, source_itinerary, _ = source
    base_number, base_itinerary, _ = base
    trip = Trip.model_validate(row["spec"])
    places = itinerary_places(conn, source_itinerary) | itinerary_places(conn, base_itinerary)
    destination = next(d for d in list_destinations(conn) if d["slug"] == trip.destination)
    rain = [day.rain_chance for day in base_itinerary.days]
    yield sse({"type": "thinking", "text": "Đang đọc góp ý của nhóm…"})
    try:
        generated = review_group_feedback(conn, llm.chat_client(), settings.llm_model, trip, source_number,
                                          source_itinerary, base_number, base_itinerary, places, feedback, rain,
                                          hub_for(destination, trip), llm.embed)
        for event in generated:
            if event["type"] != "group_review_candidate":
                yield sse(event)
                continue
            candidate = event["candidate"]
            with conn.transaction():
                locked = conn.execute("SELECT id FROM trips WHERE id = %s AND user_id = %s FOR UPDATE",
                                      (trip_id, user_id)).fetchone()
                latest = load_itinerary(conn, trip_id)
                if not locked or not latest or latest[0] != base_number:
                    stale = True
                else:
                    proposal = conn.execute(
                        """INSERT INTO group_review_proposals(trip_id, source_version, base_version, feedback, candidate)
                           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                        (trip_id, source_number, base_number, feedback, Jsonb(candidate))).fetchone()
                    log_message(conn, trip_id, "user", feedback, source_number)
                    stale = False
            if stale:
                yield sse({"type": "error", "code": "stale_base",
                           "message": "Lịch trình đã có bản mới, hãy tạo lại góp ý trên bản mới nhất."})
                return
            review = {"review_id": proposal["id"], "source_version": source_number, "base_version": base_number,
                      "source_is_old": source_number != base_number, "feedback": feedback, **candidate}
            yield sse({"type": "group_review_preview", "review": review})
            return
    except (InvalidEdit, InvalidDraft) as exc:
        yield sse({"type": "error", "message": f"Không tạo được bản xem trước: {exc}"})


# Việc lập lịch theo tên: chạy trong request (chế độ một tiến trình) hoặc trong worker planner (spec scale §5).
JOBS = {"message": _job_message, "plan": _job_plan, "replan": _job_replan, "group_review": _job_group_review}


@router.get("/jobs/{job_id}/events")
def job_events(job_id: str, user_id: int = Depends(current_user)):
    """Phát lại tiến trình của một việc từ đầu (client mất kết nối giữa chừng). Việc sống 1 giờ."""
    if jobs.owner(job_id) != user_id:
        raise HTTPException(404, "Không tìm thấy việc")
    return StreamingResponse(jobs.relay(job_id), media_type="text/event-stream")


@router.post("/trips/{trip_id}/plan")
def plan_trip(trip_id: int, answers: TripAnswers, user_id: int = Depends(current_user), conn=Depends(get_shard)):
    row = conn.execute("SELECT spec, user_messages FROM trips WHERE id = %s AND user_id = %s",
                       (trip_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    if conn.execute("SELECT 1 FROM itineraries WHERE trip_id = %s", (trip_id,)).fetchone():
        raise HTTPException(409, "Chuyến đi đã có lịch trình")
    try:
        trip = apply_answers(Trip.model_validate(row["spec"]), answers)
    except ValidationError as e:
        raise HTTPException(422, e.errors()[0]["msg"].removeprefix("Value error, ")) from None
    conn.execute("UPDATE trips SET spec = %s WHERE id = %s", (Jsonb(trip.model_dump(mode="json")), trip_id))
    return _stream("plan", user_id, trip_id=trip_id)


class Replan(BaseModel):
    changes: dict
    message: str = Field(min_length=1, max_length=2000)


@router.post("/trips/{trip_id}/replan")
def replan_trip(trip_id: int, body: Replan, user_id: int = Depends(current_user), conn=Depends(get_shard)):
    """Người dùng xác nhận đổi Trip (event confirm_replan) → lập lại, gửi kèm lịch cũ làm gợi ý."""
    row = conn.execute("SELECT spec, user_messages FROM trips WHERE id = %s AND user_id = %s",
                       (trip_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    trip = Trip.model_validate(row["spec"])
    try:
        changed_trip(trip, body.changes)
    except ValidationError as e:
        raise HTTPException(422, e.errors()[0]["msg"].removeprefix("Value error, ")) from None
    return _stream("replan", user_id, trip_id=trip_id, changes=body.changes, message=body.message)


@router.get("/trips")
def list_trips(user_id: int = Depends(current_user), conn=Depends(get_shard)):
    # Trip ở shard, Destination ở database chung: không JOIN được, ghép tên bằng code (spec scale §9.1)
    rows = conn.execute("SELECT id, spec, created_at FROM trips WHERE user_id = %s ORDER BY id DESC",
                        (user_id,)).fetchall()
    names = {d["slug"]: d["name"] for d in list_destinations(conn)}
    return [{**r, "destination_name": names.get(r["spec"].get("destination"))} for r in rows]


@router.get("/trips/{trip_id}")
def get_trip(trip_id: int, version: int | None = None, user_id: int = Depends(current_user),
             conn=Depends(get_shard)):
    trip = conn.execute("SELECT id, spec, pinned_place_ids FROM trips WHERE id = %s AND user_id = %s",
                        (trip_id, user_id)).fetchone()
    if not trip:
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    it = load_itinerary(conn, trip_id, version)
    if version is not None and not it:
        raise HTTPException(404, "Không tìm thấy phiên bản lịch trình")
    versions = [r["version"] for r in conn.execute(
        "SELECT version FROM itineraries WHERE trip_id = %s ORDER BY version", (trip_id,)).fetchall()]
    dest = next(d for d in list_destinations(conn) if d["slug"] == trip["spec"]["destination"])
    return {"trip_id": trip["id"], "trip": trip["spec"], "center": [dest["lon"], dest["lat"]],
            "version": it[0] if it else None,
            "itinerary": it[1].model_dump(mode="json") if it else None,
            "places": it[2] if it else {}, "versions": versions, "pinned_place_ids": trip["pinned_place_ids"]}
