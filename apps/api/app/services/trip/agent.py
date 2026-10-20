import datetime as dt
import json
import re
import unicodedata
from collections.abc import Iterator
from typing import get_args

from pydantic import ValidationError

from app.prompts.registry import catalog
from app.services.ml_ranker_service import ranker_service
from app.services.ranker_features import intent_families
from app.services.trip.domain import (DEFAULT_TRAVEL_MODE, HHMM, KINDS, PACE_HOURS, PACE_STOPS, TAGS, ArrivalMode, Draft,
                                      Hub, Itinerary, Place, TravelMode, Trip, TripAnswers)
from app.services.trip.places import search_places
from app.services.trip.rules import ARRIVAL_BUFFER_MIN, DEPARTURE_BUFFER_MIN, InvalidDraft, build_itinerary, vnd


class UnsupportedDestination(Exception):
    pass


class TripParseError(Exception):
    pass


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


def _fold_destination(value: str) -> str:
    value = value.replace("đ", "d").replace("Đ", "D")
    folded = "".join(char for char in unicodedata.normalize("NFKD", value)
                     if not unicodedata.combining(char)).lower()
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def _mentions_ho_chi_minh(message: str) -> bool:
    normalized = f" {_fold_destination(message)} "
    return any(f" {alias} " in normalized for alias in (
        "sai gon", "saigon", "tp hcm", "tphcm", "hcm", "hcmc", "ho chi minh",
        "thanh pho ho chi minh",
    ))


def parse_trip(client, model: str, message: str, destinations: dict[str, str], today: dt.date) -> Trip:
    if not destinations:
        raise TripParseError("Danh mục địa điểm lập lịch trình chưa được nạp. Vui lòng thử lại sau.")
    dests = ", ".join(f"{slug} ({name})" for slug, name in destinations.items())
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": catalog.get("TRIP_PARSER").system_prompt.format(today=today.isoformat(), dests=dests)},
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
    if args.get("destination") not in destinations and _mentions_ho_chi_minh(message):
        # Common Vietnamese names are often returned as "unsupported" even when tp-hcm is in the tool enum.
        if "tp-hcm" in destinations:
            args["destination"] = "tp-hcm"
    if args.get("destination") not in destinations:
        raise UnsupportedDestination(
            "Hiện mình chỉ hỗ trợ lịch trình ở TP. Hồ Chí Minh.")
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

PLAN_TOOLS = [
    {"type": "function", "function": {
        "name": "search_places",
        "description": "Tìm Place thật trong Destination của Trip. Chỉ được dùng place_id trả về từ tool này.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Mô tả tự nhiên, vd 'quán cafe yên tĩnh gần sông Sài Gòn'"},
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
               user_messages: list[str] = (), weather_forecasts: list[dict | None] | None = None) -> str:
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
    if weather_forecasts:
        details = []
        for i, item in enumerate(weather_forecasts):
            if item:
                probability = item.get("precipitation_probability_pct")
                amount = item.get("precipitation_sum_mm")
                details.append(f"ngày {i + 1}: xác suất mưa {probability if probability is not None else '?'}%, "
                               f"lượng mưa dự báo {amount if amount is not None else '?'} mm")
        if details:
            lines.append("Dự báo Open-Meteo (tham khảo, không phải dữ liệu ngập): " + "; ".join(details))
    if user_messages:  # nguyên văn để AI không mất ý như "phải đi vườn hoa", "khách sạn rẻ hơn"
        lines.append("Người dùng đã nói (theo thứ tự, câu sau thắng câu trước):")
        lines += [f"- {m}" for m in user_messages]
    return "\n".join(lines)


def place_brief(p: Place) -> dict:
    return {"id": p.id, "name": p.name, "kind": p.kind, "lat": p.lat, "lon": p.lon,
            "photo_url": p.photo_url, "outdoor": p.outdoor, "price": p.price,
            "open_hours": p.open_hours, "description": p.description,
            "rank_score": p.rank_score, "rank_position": p.rank_position,
            "rank_candidate_count": p.rank_candidate_count, "ranker_source": p.ranker_source,
            "ranker_version": p.ranker_version, "ranker_warning": p.ranker_warning,
            "rank_scope": p.rank_scope,
            "rank_matched_tags": p.rank_matched_tags, "rank_price_per_person_vnd": p.rank_price_per_person_vnd}


def for_llm(p: Place) -> dict:
    return {"place_id": p.id, "name": p.name, "kind": p.kind, "tags": p.tags, "price": p.price,
            "outdoor": p.outdoor, "open_hours": p.open_hours, "lat": round(p.lat, 4), "lon": round(p.lon, 4),
            "rank_score": p.rank_score, "rank_position": p.rank_position,
            "rank_candidate_count": p.rank_candidate_count, "ranker_source": p.ranker_source,
            "rank_matched_tags": p.rank_matched_tags,
            "rank_price_per_person_vnd": p.rank_price_per_person_vnd}


def _ranker_tags(tags: list[str]) -> list[str]:
    aliases = {
        "an-chay": ("food",), "an-dia-phuong": ("food",), "hai-san": ("food",),
        "cafe-chill": ("coffee", "relaxation"), "thien-nhien": ("nature",),
        "check-in": ("sightseeing",), "view-dep": ("sightseeing",),
        "lich-su": ("culture",), "van-hoa": ("culture",),
        "soi-dong": ("entertainment",), "yen-tinh": ("relaxation",), "lang-man": ("relaxation",),
    }
    expanded = list(tags)
    for tag in tags:
        expanded.extend(aliases.get(tag, ()))
    return list(dict.fromkeys(expanded))


def _rank_search(trip: Trip, query: str, found: list[Place]) -> tuple[list[Place], list[Place]]:
    if not found:
        return [], []
    query_tags = list(dict.fromkeys([*trip.required_tags, *trip.preferred_tags]))
    rank_query_tags = _ranker_tags([*query_tags, *([query] if query else [])])
    rank_query = {
        "user_intent_text": query or " ".join(query_tags) or "Điểm tham quan phù hợp lịch trình",
        "user_intent_tags": rank_query_tags,
        "group_size": trip.travelers,
        "budget_remaining_vnd": trip.budget,
    }
    candidates = [{
        "candidate_experience_id": str(place.id),
        "candidate_name": place.name,
        "candidate_tags": _ranker_tags(place.tags),
        "price_vnd_per_person": place.price,
        "is_indoor": not place.outdoor,
    } for place in found]
    try:
        ranked, rejected_ids, status = ranker_service.rank(rank_query, candidates)
    except Exception:
        # Keep chat planning available if a model artifact or optional Ranker path fails.
        return found, []
    count = len(ranked)
    by_id = {place.id: place for place in found}
    source = status.get("ranking_source")
    version = status.get("active_version") or status.get("model_version")
    warning = status.get("warning")
    ranked_places: list[Place] = []
    for position, result in enumerate(ranked, start=1):
        place_id = int(result["candidate_experience_id"])
        place = by_id.get(place_id)
        if place is None:
            continue
        ranked_places.append(place.model_copy(update={
            "rank_score": float(result["rank_score"]),
            "rank_position": position,
            "rank_candidate_count": count,
            "ranker_source": source,
            "ranker_version": version,
            "ranker_warning": warning,
            "rank_matched_tags": sorted(
                intent_families(set(rank_query_tags)) & intent_families(set(_ranker_tags(place.tags)))
            ),
            "rank_price_per_person_vnd": place.price,
        }))
    rejected = [by_id[int(place_id)] for place_id in rejected_ids if place_id.isdigit() and int(place_id) in by_id]
    return ranked_places, rejected


def run_search(db, trip: Trip, embed_fn, args: dict, seen: dict[int, Place],
               rankings: dict[int, Place] | None = None) -> tuple[dict, str]:
    """Tool search_places: thêm kết quả vào `seen`, trả (event tool_call, kết quả cho LLM)."""
    query = str(args.get("query", ""))
    found = search_places(
        db, trip.destination, query, embed_fn,
        kind=args.get("kind") if args.get("kind") in KINDS else None,
        required_tags=[t for t in (args.get("must_have_tags") or []) if t in TAGS],
        avoided_tags=trip.avoided_tags)
    ranked, over_budget = _rank_search(trip, query, found)
    # Keep all search hits valid for itinerary validation, but expose budget-feasible results first.
    seen.update({p.id: p for p in found})
    ranked_by_id = {p.id: p for p in ranked}
    if rankings is not None:
        for place in found:
            if place.id not in ranked_by_id:
                rankings[place.id] = place.model_copy(update={
                    "rank_score": None, "rank_position": None, "rank_candidate_count": None,
                    "ranker_source": None, "ranker_version": None, "ranker_warning": None,
                    "rank_matched_tags": [], "rank_price_per_person_vnd": None,
                })
        rankings.update(ranked_by_id)
    ordered = [*ranked, *over_budget]
    llm_places = [for_llm(p) for p in ranked]
    return ({"type": "tool_call", "name": "search_places", "query": query,
             "places": [place_brief(p) for p in ordered],
             "ranker": {"source": ranked[0].ranker_source, "version": ranked[0].ranker_version,
                        "warning": ranked[0].ranker_warning} if ranked else None},
            json.dumps(llm_places, ensure_ascii=False))


def itinerary_event(itin: Itinerary, seen: dict[int, Place], rankings: dict[int, Place] | None = None,
                    trip: Trip | None = None, rank_query: str = "") -> dict:
    used = {s.place_id for d in itin.days for s in d.stops}
    if itin.stay_place_id is not None:
        used.add(itin.stay_place_id)
    rankings = rankings or {}
    # The selected stops may come from an older itinerary or from a search whose result
    # was not retained in `rankings`. Re-score the actual stops together so their score
    # and position are available in the itinerary response.
    selected_ids = list(dict.fromkeys(
        [stop.place_id for day in itin.days for stop in day.stops]
        + ([itin.stay_place_id] if itin.stay_place_id is not None else [])
    ))
    selected = [seen[place_id] for place_id in selected_ids if place_id in seen]
    if trip is not None and selected:
        scored, _ = _rank_search(trip, rank_query, selected)
        for place in scored:
            if place.rank_score is not None:
                rankings[place.id] = place.model_copy(update={"rank_scope": "itinerary_stops"})
    return {"type": "itinerary", "itinerary": itin.model_dump(mode="json"),
            "places": {str(i): place_brief(rankings.get(i, seen[i])) for i in used}}


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


def plan(db, client, model: str, trip: Trip, embed_fn, rain: list[int | None] | None,
         hub: Hub | None = None, user_messages: list[str] = (), previous: tuple[Itinerary, dict[int, Place]] | None = None,
         weather_forecasts: list[dict | None] | None = None,
         ) -> Iterator[dict]:
    # chỉ Place AI đã nhận từ search_places hoặc có trong lịch cũ mới hợp lệ
    seen: dict[int, Place] = dict(previous[1]) if previous else {}
    rankings: dict[int, Place] = {p.id: p for p in seen.values() if p.rank_score is not None}
    pinned = {s.place_id for d in previous[0].days for s in d.stops if s.pinned} if previous else set()
    brief = trip_brief(trip, rain, hub, user_messages, weather_forecasts)
    if previous:
        brief += "\n\n" + previous_brief(*previous)
    messages = [{"role": "system", "content": catalog.get("TRIP_PLANNER").system_prompt}, {"role": "user", "content": brief}]
    submits = invalid = 0
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
                ev, result = run_search(db, trip, embed_fn, args, seen, rankings)
                yield ev
            elif c.function.name == "submit_itinerary":
                try:
                    itin = build_itinerary(trip, Draft.model_validate(args), seen, rain, hub, pinned,
                                           weather_forecasts)
                except (ValidationError, InvalidDraft) as e:
                    invalid += 1
                    if invalid > MAX_INVALID:
                        if last:  # đã có phương án hợp lệ trước đó → trả phương án đó thay vì báo lỗi
                            yield itinerary_event(last, seen, rankings, trip, " ".join(user_messages))
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
            yield itinerary_event(final, seen, rankings, trip, " ".join(user_messages))
            return

    if last:  # hết lượt nhưng đã có phương án → trả phương án tốt nhất (best-effort)
        yield itinerary_event(last, seen, rankings, trip, " ".join(user_messages))
    else:
        yield {"type": "error", "message": "AI chưa hoàn thành lịch trình, bạn thử lại nhé."}
