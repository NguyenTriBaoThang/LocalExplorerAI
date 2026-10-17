"""Tin nhắn tiếp theo trên Trip đã có lịch trình: trả lời, sửa bằng thao tác, hoặc xin lập lại (#22)."""
import json
from collections.abc import Iterator

from pydantic import ValidationError

from app.agent import MAX_INVALID, MAX_STEPS, PLAN_TOOLS, _trip_tool, itinerary_event, run_search, trip_brief
from app.domain import INTENT_LABELS, WEEKDAYS, Draft, DraftDay, DraftStop, Hub, Itinerary, Place, Trip
from app.replan import to_draft
from app.rules import InvalidDraft, build_itinerary, cost_breakdown, vnd

FOLLOWUP_PROMPT = """Bạn là trợ lý của một chuyến đi đã có lịch trình. Đọc tin nhắn mới và chọn đúng MỘT việc:
- Câu hỏi, nhận xét, lời cảm ơn → gọi answer. Chỉ dùng số liệu trong phần "Dữ kiện"; thiếu dữ liệu thì nói rõ app chưa có, không đoán, không bịa số. Diễn đạt tự nhiên như người, không chép nguyên văn Dữ kiện.
- Muốn đổi, thêm, bớt, dời giờ Stop hoặc đổi chỗ ở → gọi edit_itinerary với ÍT thao tác nhất; Stop không liên quan giữ nguyên. Place mới phải lấy từ search_places (hoặc Place đã có trong lịch). Không đụng Stop "đã ghim".
  day/stop đánh số từ 1 đúng như [ngày.stop] trong Dữ kiện (vd "quán trưa ngày 1" là một Stop [1.x]), theo lịch HIỆN TẠI. Mỗi ngày vẫn phải đủ 3 bữa.
- Muốn đổi thông tin gốc của chuyến (số ngày, ngày đi, số người, Budget, Pace, phương tiện, sở thích, giờ đến/về, giờ xong ngày cuối) → gọi change_trip. "Xong hết lúc 13h để ra sân bay" là last_day_end, KHÔNG sửa departure_time (giờ bay) với các trường thay đổi; text là câu hỏi xác nhận, vd "Đổi thành 3 ngày sẽ lập lại lịch trình, tiếp tục nhé?".
Trả lời tiếng Việt, ngắn gọn, thân thiện."""

ANSWER_TOOL = {"type": "function", "function": {
    "name": "answer", "description": "Trả lời người dùng, KHÔNG đổi lịch trình.",
    "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}}

EDIT_TOOL = {"type": "function", "function": {
    "name": "edit_itinerary",
    "description": "Sửa lịch trình hiện tại bằng thao tác. Gọi lại thì gửi đủ thao tác mới, áp lên lịch HIỆN TẠI.",
    "parameters": {"type": "object", "properties": {
        "summary": {"type": "string", "description": "1 câu tiếng Việt nói đã đổi gì"},
        "ops": {"type": "array", "items": {"type": "object", "properties": {
            "op": {"type": "string", "enum": ["replace_stop", "remove_stop", "add_stop", "retime_stop", "change_stay"]},
            "day": {"type": "integer", "description": "từ 1"}, "stop": {"type": "integer", "description": "từ 1"}, "place_id": {"type": "integer"},
            "start_time": {"type": "string", "description": "HH:MM"}, "duration_min": {"type": "integer"},
            "reason": {"type": "string"},
        }, "required": ["op"]}},
    }, "required": ["ops", "summary"]}}}

GROUP_REVIEW_PROMPT = """Bạn chuyển góp ý của nhóm thành một bản xem trước lịch trình.
Luôn áp thao tác lên Version nền mới nhất. Giữ mọi Stop không liên quan. Nếu các ý kiến trái chiều,
ghi nguyên các ý chưa thể dung hoà vào unresolved_feedback; không tự chọn theo đa số.
Khi cần Place mới, gọi search_places trước. Chỉ dùng Place đã có trong lịch hoặc do search_places trả về.
Không tự tính chi phí, Leg hay Conflict: ứng dụng sẽ tự tính. Trả lời tiếng Việt ngắn gọn."""

GROUP_REVIEW_TOOL = {"type": "function", "function": {
    "name": "review_group_feedback", "description": "Đề xuất thao tác cho góp ý nhóm trên lịch nền mới nhất.",
    "parameters": {"type": "object", "properties": {
        "summary": {"type": "string"},
        "ops": {"type": "array", "items": {"type": "object", "properties": {
            "op": {"type": "string", "enum": ["replace_stop", "remove_stop", "add_stop", "retime_stop", "change_stay"]},
            "day": {"type": "integer"}, "stop": {"type": "integer"}, "place_id": {"type": "integer"},
            "start_time": {"type": "string", "description": "HH:MM"}, "duration_min": {"type": "integer"},
            "reason": {"type": "string"},
        }, "required": ["op"]}},
        "unresolved_feedback": {"type": "array", "items": {"type": "string"}},
    }, "required": ["summary", "ops", "unresolved_feedback"]}}}

# Trường Trip người dùng được đổi qua change_trip (destination cố định: muốn nơi khác thì "Chuyến mới")
CHANGEABLE = ("days", "start_date", "budget", "travelers", "required_tags", "preferred_tags", "avoided_tags", "pace",
              "travel_mode", "arrival_mode", "arrival_time", "departure_time", "last_day_end")
CHANGE_TOOL = {"type": "function", "function": {
    "name": "change_trip", "description": "Đổi thông tin gốc của Trip; người dùng xác nhận xong mới lập lại lịch.",
    "parameters": {"type": "object", "properties": {
        "changes": {"type": "object", "properties": {
            k: v for k, v in _trip_tool([])["function"]["parameters"]["properties"].items() if k in CHANGEABLE}},
        "text": {"type": "string"},
    }, "required": ["changes", "text"]}}}


CONFIRM_TOOL = {"type": "function", "function": {
    "name": "confirm_replan", "description": "Người dùng đồng ý thay đổi đang chờ xác nhận → lập lại lịch ngay.",
    "parameters": {"type": "object", "properties": {}}}}


def changed_trip(trip: Trip, changes: dict) -> Trip:
    """Trip sau khi áp changes (chỉ trường CHANGEABLE); ValidationError nếu giá trị sai."""
    return Trip.model_validate(trip.model_dump() | {k: v for k, v in changes.items() if k in CHANGEABLE})


class InvalidEdit(Exception):
    pass


def apply_ops(itin: Itinerary, ops: list, allowed: set[int]) -> tuple[Draft, list[tuple[int, int]]]:
    """Áp thao tác lên lịch cũ (ngày/Stop đánh số từ 1 theo lịch cũ; changed trả chỉ số từ 0). Stop không bị nhắc giữ nguyên → changed chỉ gồm Stop mới/đổi."""
    draft = to_draft(itin)
    days = [[[st, False] for st in d.stops] for d in draft.days]  # [DraftStop, đã đổi?]
    removed: set[tuple[int, int]] = set()

    def at(o) -> tuple[int, int]:  # LLM đánh số từ 1 như Dữ kiện → chỉ số từ 0
        d, s = o.get("day"), o.get("stop")
        if not (isinstance(d, int) and 1 <= d <= len(days) and isinstance(s, int) and 1 <= s <= len(days[d - 1])):
            raise InvalidEdit(f"Không có Stop [{d}.{s}]")
        if days[d - 1][s - 1][0].pinned:
            raise InvalidEdit(f"Stop [{d}.{s}] đã ghim, không được đổi")
        return d - 1, s - 1

    def place(o) -> int:
        if o.get("place_id") not in allowed:
            raise InvalidEdit(f"place_id {o.get('place_id')} chưa có trong kết quả search_places")
        return o["place_id"]

    try:
        for o in ops:
            kind = o.get("op") if isinstance(o, dict) else None
            if kind == "replace_stop":
                d, s = at(o)
                old = days[d][s][0]
                days[d][s] = [DraftStop(place_id=place(o), start_time=o.get("start_time") or old.start_time,
                                        duration_min=o.get("duration_min") or old.duration_min,
                                        reason=o.get("reason") or ""), True]
            elif kind == "retime_stop":
                d, s = at(o)
                old = days[d][s][0]
                days[d][s] = [DraftStop(**old.model_dump() | {
                    "start_time": o.get("start_time") or old.start_time,
                    "duration_min": o.get("duration_min") or old.duration_min}), True]
            elif kind == "remove_stop":
                removed.add(at(o))
            elif kind == "add_stop":
                d = o.get("day")
                if not (isinstance(d, int) and 1 <= d <= len(days)):
                    raise InvalidEdit(f"Không có ngày {d}")
                days[d - 1].append([DraftStop(place_id=place(o), start_time=o.get("start_time") or "",
                                          duration_min=o.get("duration_min") or 60, reason=o.get("reason") or ""),
                                True])
            elif kind == "change_stay":
                draft.stay_place_id = place(o)
            else:
                raise InvalidEdit(f"Không có thao tác {kind}")
    except ValidationError as e:
        raise InvalidEdit(f"Giờ hoặc thời lượng không hợp lệ: {e.errors()[0]['msg']}") from None

    new_days, changed = [], []
    for d, stops in enumerate(days):
        kept = sorted((x for s, x in enumerate(stops) if (d, s) not in removed), key=lambda x: x[0].start_time)
        if not kept:
            raise InvalidEdit(f"Ngày {d + 1} không còn Stop nào")
        changed += [(d, i) for i, (_, ch) in enumerate(kept) if ch]
        new_days.append(DraftDay(stops=[st for st, _ in kept]))
    draft.days = new_days
    return draft, changed


def _hard(itin: Itinerary) -> set[tuple]:
    return {(c.kind, c.day_index, c.place_id) for c in itin.conflicts}


def _km_min_cost(legs) -> tuple[float, int, int]:
    return sum(x.distance_km for x in legs), sum(x.duration_min for x in legs), sum(x.cost for x in legs)


def itinerary_facts(trip: Trip, itin: Itinerary, places: dict[int, Place]) -> str:
    """Số liệu do code tính để LLM trả lời câu hỏi — LLM không tự tính hay đoán."""
    lines = []
    if itin.stay_place_id is not None:
        lines.append(f"Chỗ ở: {places[itin.stay_place_id].name} (place_id {itin.stay_place_id})")
    for di, day in enumerate(itin.days):
        wd = WEEKDAYS[day.date.weekday()] if day.date else None
        rain = "không có dự báo" if day.rain_chance is None else f"khả năng mưa {day.rain_chance}%"
        km, mins, cost = _km_min_cost(day.legs)
        date = f" ({day.date.isoformat()})" if day.date else ""
        lines.append(f"Ngày {di + 1}{date}: {rain}; di chuyển {km:.1f} km, {mins} phút, {vnd(cost)}")
        for si, s in enumerate(day.stops):
            p = places[s.place_id]
            hours = p.open_hours.get(wd) if wd and p.open_hours else None
            extra = [p.kind, vnd(s.est_cost), "ngoài trời" if p.outdoor else "trong nhà"]
            if hours:
                extra.append(f"mở {hours[0]}–{hours[1]}")
            if s.pinned:
                extra.append("đã ghim")
            lines.append(f"  [{di + 1}.{si + 1}] {s.start_time}, {s.duration_min} phút: {p.name} "
                         f"(place_id {p.id}; {', '.join(extra)})")
    km, mins, _ = _km_min_cost([x for d in itin.days for x in d.legs])
    b = cost_breakdown(trip, itin, places)
    lines += [
        f"Tổng di chuyển: {km:.1f} km, {mins} phút",
        f"Tổng chi phí {vnd(itin.total_cost)} = ăn uống {vnd(b['an_uong'])} + vé/tham quan {vnd(b['tham_quan'])}"
        f" + chỗ ở {vnd(b['cho_o'])} + di chuyển {vnd(b['di_chuyen'])}; Budget {vnd(trip.budget)}, "
        + (f"còn {vnd(left)}" if (left := trip.budget - itin.total_cost) >= 0 else f"vượt {vnd(-left)}"),
    ]
    if itin.conflicts:
        lines.append("Xung đột: " + "; ".join(c.message for c in itin.conflicts))
    if itin.intents:
        lines.append("Mục đích: " + ", ".join(f"{INTENT_LABELS[k]} {'có' if v else 'thiếu'}"
                                             for k, v in itin.intents.items()))
    lines.append("App KHÔNG có dữ liệu: nhiệt độ, giá vé thật hôm đó, kẹt xe, đánh giá của khách.")
    return "\n".join(lines)


def review_group_feedback(
        conn, client, model: str, trip: Trip, source_version: int, source: Itinerary,
        base_version: int, base: Itinerary, places: dict[int, Place], feedback: str,
        rain: list[int | None] | None, hub: Hub | None, embed_fn,
) -> Iterator[dict]:
    """Tạo candidate review bằng dữ liệu do code kiểm tra và tính lại."""
    seen = dict(places)
    context = (
        f"{GROUP_REVIEW_PROMPT}\n\nVersion nguồn: {source_version}\n"
        f"Version nền mới nhất: {base_version}\n\nDữ kiện version nguồn:\n"
        f"{itinerary_facts(trip, source, places)}\n\nDữ kiện version nền mới nhất:\n"
        f"{itinerary_facts(trip, base, places)}\n\nGóp ý nhóm: {feedback}"
    )
    messages = [{"role": "system", "content": context}]
    for _ in range(MAX_STEPS):
        msg = client.chat.completions.create(model=model, messages=messages,
                                             tools=[PLAN_TOOLS[0], GROUP_REVIEW_TOOL],
                                             tool_choice="required").choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        for call in msg.tool_calls or []:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = None
            if not isinstance(args, dict):
                raise InvalidEdit("arguments không phải JSON object hợp lệ")
            if call.function.name == "search_places":
                ev, result = run_search(conn, trip, embed_fn, args, seen)
                yield ev
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
                continue
            if call.function.name != "review_group_feedback":
                raise InvalidEdit(f"Không có tool {call.function.name}")
            if "ops" not in args or not isinstance(args["ops"], list):
                raise InvalidEdit("ops phải là danh sách thao tác")
            if "summary" not in args or not isinstance(args["summary"], str):
                raise InvalidEdit("summary phải là chuỗi")
            unresolved = args.get("unresolved_feedback")
            if not isinstance(unresolved, list) or not all(isinstance(text, str) for text in unresolved):
                raise InvalidEdit("unresolved_feedback phải là danh sách chuỗi")
            draft, changed = apply_ops(base, args["ops"], set(seen))
            draft.summary = args["summary"]
            candidate = itinerary_event(build_itinerary(trip, draft, seen, rain, hub), seen)
            yield {"type": "group_review_candidate", "candidate": {
                "summary": draft.summary,
                "unresolved_feedback": unresolved,
                "changed": changed,
                "itinerary": candidate["itinerary"],
                "places": candidate["places"],
            }}
            return
    raise InvalidEdit("AI chưa xử lý xong góp ý nhóm")


def followup(conn, client, model: str, trip: Trip, itin: Itinerary, places: dict[int, Place], message: str,
             rain: list[int | None] | None, hub: Hub | None, embed_fn, pending: dict | None = None) -> Iterator[dict]:
    seen = dict(places)  # Place đang có trong lịch + Place AI tìm thêm
    tools = [PLAN_TOOLS[0], ANSWER_TOOL, EDIT_TOOL, CHANGE_TOOL] + ([CONFIRM_TOOL] if pending else [])
    waiting = (f"\n\nĐang chờ người dùng xác nhận: «{pending['text']}» (thay đổi {pending['changes']}). "
               "Tin nhắn mới là đồng ý (oke, ừ, được, tiếp tục…) → gọi confirm_replan; từ chối → answer."
               if pending else "")
    invalid = 0
    last = None  # (Itinerary, changed) hợp lệ gần nhất nhưng còn Conflict mới
    messages = [{"role": "system", "content": FOLLOWUP_PROMPT},
                {"role": "user", "content": f"{trip_brief(trip, rain, hub)}\n\nDữ kiện lịch trình hiện tại:\n"
                                            f"{itinerary_facts(trip, itin, places)}{waiting}\n\nTin nhắn mới: {message}"}]
    for _ in range(MAX_STEPS):
        msg = client.chat.completions.create(model=model, messages=messages, tools=tools,
                                             tool_choice="required").choices[0].message
        messages.append(msg.model_dump(exclude_none=True))  # Gemini 3 cần thought_signature
        for c in msg.tool_calls or []:
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                args = None
            if not isinstance(args, dict):
                result = "Lỗi: arguments không phải JSON object hợp lệ."
            elif c.function.name == "search_places":
                ev, result = run_search(conn, trip, embed_fn, args, seen)
                yield ev
            elif c.function.name == "answer":
                yield {"type": "answer", "text": str(args.get("text", ""))}
                return
            elif c.function.name == "confirm_replan" and pending:
                yield {"type": "replan_confirmed"}
                return
            elif c.function.name == "change_trip":
                changes = {k: v for k, v in (args.get("changes") or {}).items() if k in CHANGEABLE}
                try:
                    if not changes:
                        raise ValueError("changes rỗng")
                    changed_trip(trip, changes)
                except (ValueError, ValidationError) as e:  # ValidationError là ValueError
                    result = f"Lỗi: {e}. Sửa changes rồi gọi lại."
                else:
                    yield {"type": "confirm_replan", "text": str(args.get("text", "")), "changes": changes,
                           "message": message}
                    return
            elif c.function.name == "edit_itinerary":
                try:
                    draft, changed = apply_ops(itin, args.get("ops") or [], set(seen))
                    draft.summary = str(args.get("summary") or itin.summary)
                    new = build_itinerary(trip, draft, seen, rain, hub)
                except (InvalidEdit, InvalidDraft) as e:
                    invalid += 1
                    if invalid > MAX_INVALID:
                        yield {"type": "error", "message": "AI chưa sửa được lịch trình, bạn nói rõ hơn nhé."}
                        return
                    result = f"Lỗi: {e}. Gọi lại edit_itinerary với thao tác đúng."
                else:
                    extra = [x for x in new.conflicts if (x.kind, x.day_index, x.place_id) not in _hard(itin)]
                    if not extra or last is not None:  # Conflict mới chỉ được gửi lại sửa 1 lần
                        yield {**itinerary_event(new, seen), "changed": changed}
                        return
                    last = (new, changed)
                    result = ("Conflict mới: " + "; ".join(x.message for x in extra)
                              + ". Sửa bằng edit_itinerary (áp lên lịch hiện tại) nếu có thể, không thì gọi lại y nguyên.")
            else:
                result = f"Lỗi: không có tool {c.function.name}."
            messages.append({"role": "tool", "tool_call_id": c.id, "content": result})
    if last:
        yield {**itinerary_event(last[0], seen), "changed": last[1]}
    else:
        yield {"type": "error", "message": "AI chưa xử lý xong tin nhắn, bạn thử lại nhé."}
