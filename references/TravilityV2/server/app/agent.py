import datetime as dt
import json
import re
from collections.abc import Iterator
from typing import get_args

from pydantic import ValidationError

from app.domain import (DEFAULT_TRAVEL_MODE, HHMM, KINDS, PACE_HOURS, PACE_STOPS, TAGS, ArrivalMode, Draft, Hub,
                        Itinerary, Place, TravelMode, Trip, TripAnswers)
from app.places_client import search_places
from app.rules import ARRIVAL_BUFFER_MIN, DEPARTURE_BUFFER_MIN, InvalidDraft, build_itinerary, vnd


class UnsupportedDestination(Exception):
    pass


class TripParseError(Exception):
    pass


PARSE_PROMPT = """Hôm nay là {today}. Chuyển yêu cầu du lịch của người dùng thành Trip bằng tool record_trip.
Destination hỗ trợ: {dests}. Nếu người dùng muốn đi nơi khác, destination = "unsupported".
Budget tính bằng VND cho cả nhóm ("3 triệu" = 3000000). Nếu không nói, ước lượng 1500000 × số người × số ngày.
Chỉ điền start_date (YYYY-MM-DD) khi người dùng nói rõ ngày đi.
Pace: "nhẹ nhàng/thong thả" = thong-tha, "đi nhiều/khám phá hết" = day, còn lại = vua.
Chỉ dùng Tag trong danh sách cho phép; Tag người dùng nói không muốn → avoided_tags.
Travel Mode (đi lại trong thành phố): thuê xe máy = xe-may, Grab/taxi = grab, xe máy của mình = xe-may-rieng, ô tô của mình = o-to-rieng.
Chỉ điền travel_mode, origin_city, arrival_mode, arrival_time, departure_time, last_day_end khi người dùng nói rõ; không đoán.
departure_time = giờ rời Destination (giờ bay / xe chạy). last_day_end = giờ muốn xong mọi hoạt động ngày cuối ("xong hết lúc 13h để ra sân bay"); hai giờ này khác nhau, đừng gộp.
Nhiều tin nhắn = cùng một chuyến, theo thứ tự thời gian; tin sau thắng tin trước khi mâu thuẫn."""


def _trip_tool(dest_slugs: list[str]) -> dict:
    tag_list = {"type": "array", "items": {"type": "string", "enum": sorted(TAGS)}}
    return {"type": "function", "function": {
        "name": "record_trip", "description": "Ghi lại Trip của người dùng",
        "parameters": {"type": "object", "properties": {
            "destination": {"type": "string", "enum": [*dest_slugs, "unsupported"]},
            "days": {"type": "integer"},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "budget": {"type": "integer", "description": "VND cho cả nhóm"},
            "travelers": {"type": "integer"},
            "required_tags": tag_list, "preferred_tags": tag_list, "avoided_tags": tag_list,
            "pace": {"type": "string", "enum": ["thong-tha", "vua", "day"]},
            "travel_mode": {"type": "string", "enum": list(get_args(TravelMode))},
            "origin_city": {"type": "string", "description": "Thành phố người dùng đi từ đó tới"},
            "arrival_mode": {"type": "string", "enum": list(get_args(ArrivalMode))},
            "arrival_time": {"type": "string", "description": "HH:MM, giờ tới Destination ngày 1"},
            "departure_time": {"type": "string", "description": "HH:MM, giờ rời Destination ngày cuối (giờ bay/xe chạy)"},
            "last_day_end": {"type": "string",
                             "description": "HH:MM, giờ muốn xong mọi hoạt động ngày cuối (không phải giờ bay)"},
        }, "required": ["destination", "days", "budget"]},
    }}


def parse_trip(client, model: str, message: str, destinations: dict[str, str], today: dt.date) -> Trip:
    dests = ", ".join(f"{slug} ({name})" for slug, name in destinations.items())
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": PARSE_PROMPT.format(today=today.isoformat(), dests=dests)},
                  {"role": "user", "content": message}],
        tools=[_trip_tool(list(destinations))],
        tool_choice="required",
    )
    calls = r.choices[0].message.tool_calls or []
    if not calls:
        raise TripParseError("AI chưa hiểu yêu cầu, bạn nói rõ hơn điểm đến, số ngày và ngân sách nhé.")
    try:
        args = json.loads(calls[0].function.arguments)
    except json.JSONDecodeError as e:
        raise TripParseError("AI trả về dữ liệu hỏng, thử lại nhé.") from e
    for k in ("arrival_time", "departure_time", "last_day_end"):
        if not re.fullmatch(HHMM, str(args.get(k) or "")):
            args.pop(k, None)  # LLM có thể trả "2pm"/"14h" → coi như chưa nói
    if args.get("destination") not in destinations:
        raise UnsupportedDestination(
            f"Travility chưa hỗ trợ điểm đến này. Hiện có: {', '.join(destinations.values())}.")
    try:
        return Trip.model_validate(args)
    except ValidationError as e:
        raise TripParseError(
            "Chưa lập được Trip: hỗ trợ 1–7 ngày, 1–10 người, ngân sách lớn hơn 0 và giờ về phải sau giờ đến.") from e


TRAVEL_MODE_LABELS = {"xe-may": "Thuê xe máy", "grab": "Grab/taxi", "xe-may-rieng": "Xe máy riêng",
                      "o-to-rieng": "Ô tô riêng"}
ARRIVAL_MODE_LABELS = {"may-bay": "Máy bay", "xe-khach": "Xe khách", "tau": "Tàu hoả", "tu-lai": "Tự lái"}


def _options(labels: dict[str, str]) -> list[dict]:
    return [{"value": v, "label": label} for v, label in labels.items()]


def missing_questions(trip: Trip) -> list[dict]:
    """Câu hỏi lại cho thông tin người dùng chưa nói (spec §3). Code quyết định, không phải LLM."""
    qs = []
    if trip.travel_mode is None:
        qs.append({"field": "travel_mode", "text": "Bạn đi lại trong thành phố bằng gì?",
                   "options": _options(TRAVEL_MODE_LABELS)})
    if trip.start_date and not (trip.arrival_time or trip.departure_time):
        qs.append({"field": "arrival", "text": "Bạn tới bằng gì, mấy giờ tới và mấy giờ về?",
                   "options": _options(ARRIVAL_MODE_LABELS)})
    return qs


KEEP_IF_UNSAID = ("start_date", "travel_mode", "origin_city", "arrival_mode", "arrival_time", "departure_time",
                  "last_day_end")


def merge_trip(old: Trip, new: Trip) -> Trip:
    """Tin nhắn tiếp theo của cùng Trip: trường người dùng không nhắc lại (vd đã chọn bằng chip) giữ giá trị cũ."""
    data = new.model_dump()
    for k in KEEP_IF_UNSAID:
        if data[k] is None:
            data[k] = getattr(old, k)
    return Trip.model_validate(data)


def apply_answers(trip: Trip, answers: TripAnswers) -> Trip:
    """Áp câu trả lời clarify vào Trip; Travel Mode vẫn trống → mặc định. Validate lại (giờ về > giờ đến)."""
    data = trip.model_dump() | answers.model_dump(exclude_none=True)
    data["travel_mode"] = data["travel_mode"] or DEFAULT_TRAVEL_MODE
    return Trip.model_validate(data)


MAX_STEPS = 12
MAX_INVALID = 1  # Place lạ / Draft sai: cho AI làm lại 1 lần (ADR-0001)

PLAN_PROMPT = """Bạn là trợ lý lập lịch trình du lịch cho người Việt.
Quy tắc:
- Chỉ dùng place_id nhận được từ search_places. Không bao giờ tự nghĩ ra địa điểm.
- Gọi search_places nhiều lần cho từng nhu cầu: ăn sáng, ăn trưa, ăn tối (kind=an-uong), tham quan, cafe, và chỗ ở (kind=cho-o) nếu Trip dài hơn 1 ngày.
- Mỗi ngày bắt buộc đủ 3 bữa, mỗi bữa là một Stop tại Place kind an-uong: sáng bắt đầu 06:00–10:00, trưa 11:00–14:00, tối 17:00–21:00 (bỏ bữa rơi trước giờ tới hoặc sau giờ về). Bữa ăn tính vào số Stop theo Pace; ưu tiên quán ăn no bụng cho bữa trưa/tối, không dùng quán kem/ăn vặt thay bữa chính.
- Mỗi ngày số Stop và khung giờ theo Pace trong đề bài; sắp Stop theo thứ tự địa lý hợp lý, tránh đi vòng.
- Tôn trọng Tag bắt buộc, tránh Tag cần tránh. Ngày khả năng mưa cao thì ưu tiên Place trong nhà (outdoor=false).
- Kiểm tra open_hours của Place khi xếp giờ.
- Chừa thời gian di chuyển giữa hai Stop liên tiếp: Stop sau bắt đầu sau khi Stop trước kết thúc ít nhất 15–30 phút, Place càng xa càng chừa nhiều.
- reason: 1 câu tiếng Việt nêu vì sao chọn, nhắc Tag/sở thích liên quan.
- Không tự tính tiền: hệ thống tự tính và báo Conflict.
- Khi đủ thông tin, gọi submit_itinerary. summary: 1–2 câu tiếng Việt thân thiện tóm tắt chuyến đi."""

PLAN_TOOLS = [
    {"type": "function", "function": {
        "name": "search_places",
        "description": "Tìm Place thật trong Destination của Trip. Chỉ được dùng place_id trả về từ tool này.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Mô tả tự nhiên, vd 'quán cafe yên tĩnh view đồi thông'"},
            "kind": {"type": "string", "enum": list(KINDS)},
            "must_have_tags": {"type": "array", "items": {"type": "string", "enum": sorted(TAGS)}},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "submit_itinerary",
        "description": "Nộp Itinerary hoàn chỉnh.",
        "parameters": {"type": "object", "properties": {
            "stay_place_id": {"type": "integer", "description": "Place kind cho-o; bắt buộc nếu Trip > 1 ngày"},
            "summary": {"type": "string"},
            "days": {"type": "array", "items": {"type": "object", "properties": {
                "stops": {"type": "array", "items": {"type": "object", "properties": {
                    "place_id": {"type": "integer"},
                    "start_time": {"type": "string", "description": "HH:MM"},
                    "duration_min": {"type": "integer"},
                    "reason": {"type": "string"},
                }, "required": ["place_id", "start_time", "duration_min", "reason"]}},
            }, "required": ["stops"]}},
        }, "required": ["days", "summary"]},
    }},
]


def trip_brief(trip: Trip, rain: list[int | None] | None, hub: Hub | None = None,
               user_messages: list[str] = ()) -> str:
    lo, hi = PACE_STOPS[trip.pace]
    start, end = PACE_HOURS[trip.pace]
    when = f", bắt đầu {trip.start_date.isoformat()}" if trip.start_date else ""
    lines = [
        f"Destination: {trip.destination}",
        f"Số ngày: {trip.days}{when}",
        f"Số người: {trip.travelers}",
        f"Budget: {vnd(trip.budget)}",
        f"Pace: {lo}-{hi} Stop/ngày, từ {start} đến {end}",
        f"Travel Mode: {trip.travel_mode or DEFAULT_TRAVEL_MODE}",
        f"Tag bắt buộc: {', '.join(trip.required_tags) or 'không'}",
        f"Tag ưu tiên: {', '.join(trip.preferred_tags) or 'không'}",
        f"Tag cần tránh: {', '.join(trip.avoided_tags) or 'không'}",
    ]
    if trip.arrival_time:
        lines.append(f"Giờ tới ngày 1: {trip.arrival_time} — Stop đầu ngày 1 bắt đầu sau ít nhất {ARRIVAL_BUFFER_MIN} phút")
    if trip.departure_time:
        lines.append(f"Giờ về ngày cuối: {trip.departure_time} — Stop cuối ngày cuối kết thúc trước ít nhất "
                     f"{DEPARTURE_BUFFER_MIN} phút")
    if trip.last_day_end:
        lines.append(f"Ngày cuối xong mọi hoạt động trước {trip.last_day_end} (Stop cuối phải kết thúc trước giờ này)")
    if hub:
        lines.append(f"Ngày 1 xuất phát từ {hub.name}; ngày cuối kết thúc tại {hub.name}")
    if rain:
        chances = ", ".join(f"ngày {i + 1}: {'?' if r is None else str(r) + '%'}" for i, r in enumerate(rain))
        lines.append(f"Khả năng mưa: {chances}")
    if user_messages:  # nguyên văn để AI không mất ý như "phải đi vườn hoa", "khách sạn rẻ hơn"
        lines.append("Người dùng đã nói (theo thứ tự, câu sau thắng câu trước):")
        lines += [f"- {m}" for m in user_messages]
    return "\n".join(lines)


def place_brief(p: Place) -> dict:
    return {"id": p.id, "name": p.name, "kind": p.kind, "lat": p.lat, "lon": p.lon,
            "photo_url": p.photo_url, "outdoor": p.outdoor, "price": p.price,
            "open_hours": p.open_hours, "description": p.description}


def for_llm(p: Place) -> dict:
    return {"place_id": p.id, "name": p.name, "kind": p.kind, "tags": p.tags, "price": p.price,
            "outdoor": p.outdoor, "open_hours": p.open_hours, "lat": round(p.lat, 4), "lon": round(p.lon, 4)}


def run_search(conn, trip: Trip, embed_fn, args: dict, seen: dict[int, Place],
               kinds: tuple[str, ...] | None = None) -> tuple[dict, str]:
    """Tool search_places: thêm kết quả vào `seen`, trả (event tool_call, kết quả cho LLM).

    `kinds`: chỉ giữ Place thuộc các kind này (agent chuyên gia, spec scale §7).
    """
    query = str(args.get("query", ""))
    found = search_places(
        conn, trip.destination, query, embed_fn,
        kind=args.get("kind") if args.get("kind") in KINDS else None,
        must_have_tags=[t for t in (args.get("must_have_tags") or []) if t in TAGS],
        exclude_tags=trip.avoided_tags)
    if kinds:
        found = [p for p in found if p.kind in kinds]
    seen.update({p.id: p for p in found})
    return ({"type": "tool_call", "name": "search_places", "query": query, "places": [place_brief(p) for p in found]},
            json.dumps([for_llm(p) for p in found], ensure_ascii=False))


def itinerary_event(itin: Itinerary, seen: dict[int, Place]) -> dict:
    used = {s.place_id for d in itin.days for s in d.stops}
    if itin.stay_place_id is not None:
        used.add(itin.stay_place_id)
    return {"type": "itinerary", "itinerary": itin.model_dump(mode="json"),
            "places": {str(i): place_brief(seen[i]) for i in used}}


def previous_brief(itin: Itinerary, places: dict[int, Place]) -> str:
    """Lịch cũ gửi kèm khi lập lại sau khi đổi Trip: AI giữ Stop còn phù hợp."""
    lines = ["Lịch trình cũ (giữ các Stop còn phù hợp với Trip mới; place_id dưới đây dùng được luôn):"]
    if itin.stay_place_id is not None:
        lines.append(f"- Chỗ ở: {places[itin.stay_place_id].name} (place_id {itin.stay_place_id})")
    for i, d in enumerate(itin.days):
        lines.append(f"- Ngày {i + 1}: " + "; ".join(
            f"{s.start_time} {places[s.place_id].name} (place_id {s.place_id})"
            + (" 📌 đã ghim — BẮT BUỘC giữ" if s.pinned else "") for s in d.stops))
    return "\n".join(lines)


def plan(conn, client, model: str, trip: Trip, embed_fn, rain: list[int | None] | None,
         hub: Hub | None = None, user_messages: list[str] = (), previous: tuple[Itinerary, dict[int, Place]] | None = None,
         seeded: dict[int, Place] | None = None, notes: str = "", max_searches: int | None = None,
         ) -> Iterator[dict]:
    # chỉ Place AI đã nhận từ search_places, có trong lịch cũ, hoặc do agent chuyên gia chọn (seeded) mới hợp lệ
    seen: dict[int, Place] = {**(previous[1] if previous else {}), **(seeded or {})}
    pinned = {s.place_id for d in previous[0].days for s in d.stops if s.pinned} if previous else set()
    brief = trip_brief(trip, rain, hub, user_messages)
    if previous:
        brief += "\n\n" + previous_brief(*previous)
    if notes:
        brief += "\n\n" + notes
    messages = [{"role": "system", "content": PLAN_PROMPT}, {"role": "user", "content": brief}]
    submits = invalid = searches = 0
    last: Itinerary | None = None

    for _ in range(MAX_STEPS):
        r = client.chat.completions.create(model=model, messages=messages, tools=PLAN_TOOLS,
                                           tool_choice="required")
        msg = r.choices[0].message
        calls = msg.tool_calls or []
        if msg.content:
            yield {"type": "thinking", "text": msg.content}
        # gửi lại nguyên message: Gemini 3 cần extra_content.thought_signature trong tool_calls
        messages.append(msg.model_dump(exclude_none=True))

        final = None
        for c in calls:
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                args = None

            if not isinstance(args, dict):
                result = "Lỗi: arguments không phải JSON object hợp lệ."
            elif c.function.name == "search_places":
                searches += 1
                if max_searches is not None and searches > max_searches:
                    result = "Lỗi: hết lượt tìm. Dùng Place đã có rồi gọi submit_itinerary."
                else:
                    ev, result = run_search(conn, trip, embed_fn, args, seen)
                    yield ev
            elif c.function.name == "submit_itinerary":
                try:
                    itin = build_itinerary(trip, Draft.model_validate(args), seen, rain, hub, pinned)
                except (ValidationError, InvalidDraft) as e:
                    invalid += 1
                    if invalid > MAX_INVALID:
                        if last:  # đã có phương án hợp lệ trước đó → trả phương án đó thay vì báo lỗi
                            yield itinerary_event(last, seen)
                        else:
                            yield {"type": "error", "message": "AI chưa lập được lịch trình hợp lệ, bạn thử lại nhé."}
                        return
                    result = f"Lỗi: {e}. Chỉ dùng place_id đã nhận từ search_places."
                else:
                    submits += 1
                    last = itin
                    if not itin.conflicts or submits >= 2:
                        final = itin
                    result = ("Conflict: " + "; ".join(x.message for x in itin.conflicts)
                              + ". Sửa nếu có thể rồi submit lại; nếu không thể thì submit lại y nguyên.")
            else:
                result = f"Lỗi: không có tool {c.function.name}."
            messages.append({"role": "tool", "tool_call_id": c.id, "content": result})

        if final:
            yield itinerary_event(final, seen)
            return

    if last:  # hết lượt nhưng đã có phương án → trả phương án tốt nhất (best-effort)
        yield itinerary_event(last, seen)
    else:
        yield {"type": "error", "message": "AI chưa hoàn thành lịch trình, bạn thử lại nhé."}
