"""Engine thay thế theo mục đích (spec 2026-09-29-revision-giu-muc-dich §4, §13, ADR-0006). Code thuần, không gọi LLM."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, NamedTuple

from pydantic import BaseModel

from app import distance
from app.domain import (DEFAULT_TRAVEL_MODE, INTENT_LABELS, PACE_HOURS, WEEKDAYS, Day, Disruption, Draft, DraftDay,
                        DraftStop, Hub, Itinerary, Place, Trip, intent_weights, place_intents)
from app.rules import _minutes, build_itinerary, haversine_km, is_open, last_day_limit, make_leg, vnd

N_OPTIONS = 3
HARD = {"closed", "before_arrival", "after_departure", "over_budget"}
KIND_TEXT = {"closed": "đóng cửa", "disliked": "bạn muốn đổi", "rain": "mưa", "late": "trễ giờ"}
DROP_TEXT = {"rain": "không có chỗ trong nhà phù hợp", "late": "không kịp giờ"}


class InvalidDisruption(Exception):
    pass


class NoFeasible(BaseModel):
    reason_codes: list[str]


class ProposalOption(BaseModel):
    itinerary: Itinerary
    added: list[Place]
    changed: list[tuple[int, int]]  # (day_index, stop_index) trong itinerary mới
    metrics: dict
    reason_codes: list[str]
    explanation: str
    title: str


@dataclass(frozen=True, eq=False)  # khoá dict theo danh tính: Place (pydantic) không hash được
class Hit:
    day: int
    stop: int
    lost: Place
    mode: Literal["replace", "drop"]


class Affected(NamedTuple):
    base: Draft                    # Draft để dựng phương án (late: đã dời giờ)
    hits: list[Hit]
    codes: list[str]               # mã chung của mọi phương án, vd LATE_SHIFT, PINNED_CONFLICT
    shifted: set[tuple[int, int]]  # Stop bị dời giờ (late) → tô sáng như Stop đã đổi


CandidatesFn = Callable[[Place, set[int]], list[Place]]
Point = Place | Hub | None


def to_draft(itin: Itinerary) -> Draft:
    return Draft(stay_place_id=itin.stay_place_id, summary=itin.summary, days=[
        DraftDay(stops=[DraftStop(**s.model_dump(exclude={"est_cost"})) for s in d.stops]) for d in itin.days])


def _leg_min(a: Point, b: Point, trip: Trip) -> int:
    if a is None or b is None:
        return 0
    return make_leg(a, b, trip.travel_mode or DEFAULT_TRAVEL_MODE, trip.travelers).duration_min


def features(trip: Trip, lost: Place, cand: Place, prev: Point, nxt: Point) -> dict:
    """Đặc trưng của một ứng viên — đầu vào chung của score() và ranker ML (lát E2)."""
    w = intent_weights(trip)
    li, ci = place_intents(lost.tags), place_intents(cand.tags)
    lw = sum(w.get(i, 1) for i in li)
    lt, ct = set(lost.tags), set(cand.tags)
    return {
        "intent_overlap": sum(w.get(i, 1) for i in li & ci) / lw if lw else 0.0,
        "tag_jaccard": len(lt & ct) / len(lt | ct) if lt | ct else 0.0,
        "extra_travel_min": (_leg_min(prev, cand, trip) + _leg_min(cand, nxt, trip)
                             - _leg_min(prev, lost, trip) - _leg_min(lost, nxt, trip)),
        "extra_cost_vnd": (cand.price - lost.price) * trip.travelers,
        "price_ratio": cand.price / lost.price if lost.price else 1.0,
        "distance_km_from_lost": round(haversine_km(lost, cand), 2),
        "outdoor": int(cand.outdoor),
    }


def score(f: dict) -> float:
    # Hệ số ước lượng ban đầu; lát E1 chỉnh, lát E2 có thể thay bằng ranker cùng chữ ký.
    return 3 * f["intent_overlap"] + f["tag_jaccard"] - f["extra_travel_min"] / 30 - f["extra_cost_vnd"] / 200_000


def _neighbors(itin: Itinerary, places: dict[int, Place], di: int, si: int, hub: Hub | None) -> tuple[Point, Point]:
    day, last = itin.days[di], len(itin.days) - 1
    stay = places.get(itin.stay_place_id) if itin.stay_place_id is not None else None
    prev = places[day.stops[si - 1].place_id] if si > 0 else (hub if hub and di == 0 else stay)
    nxt = places[day.stops[si + 1].place_id] if si + 1 < len(day.stops) else (hub if hub and di == last else stay)
    return prev, nxt


def _weekdays(day: Day) -> list[str]:
    return [WEEKDAYS[day.date.weekday()]] if day.date else WEEKDAYS


def _affected(trip: Trip, itin: Itinerary, places: dict[int, Place], d: Disruption) -> Affected:
    if d.day_index >= len(itin.days) or (d.stop_index is not None
                                         and d.stop_index >= len(itin.days[d.day_index].stops)):
        raise InvalidDisruption("Không tìm thấy Stop này trong lịch trình")
    base = to_draft(itin)
    day = itin.days[d.day_index]
    if d.kind == "rain":
        outdoor = [(si, s) for si, s in enumerate(day.stops) if places[s.place_id].outdoor]
        hits = [Hit(d.day_index, si, places[s.place_id], "replace") for si, s in outdoor if not s.pinned]
        codes = ["PINNED_CONFLICT"] if any(s.pinned for _, s in outdoor) else []
        return Affected(base, hits, codes, set())
    if d.kind == "late":
        limit = _minutes(PACE_HOURS[trip.pace][1])
        if d.day_index == len(itin.days) - 1 and (lim := last_day_limit(trip)) is not None:
            limit = min(limit, lim)
        stops, wk = base.days[d.day_index].stops, _weekdays(day)
        hits, codes, shifted = [], ["LATE_SHIFT"], set()
        for si in range(d.stop_index, len(stops)):
            s = stops[si]
            p = places[s.place_id]
            old_end = _minutes(s.start_time) + s.duration_min
            start = _minutes(s.start_time) + d.minutes
            if start >= 24 * 60:
                if s.pinned:
                    raise InvalidDisruption(f"Trễ {d.minutes} phút đẩy {p.name} (đã ghim) qua nửa đêm — bỏ ghim rồi thử lại")
                hits.append(Hit(d.day_index, si, p, "drop"))
                continue
            s.start_time = f"{start // 60:02d}:{start % 60:02d}"
            shifted.add((d.day_index, si))
            over = start + s.duration_min > limit >= old_end  # chỉ tính khi chính việc dời giờ làm vượt mốc
            shut = not any(is_open(p, w, s.start_time, s.duration_min) for w in wk)
            if s.pinned:
                if (over or shut) and "PINNED_CONFLICT" not in codes:
                    codes.append("PINNED_CONFLICT")
            elif over:
                hits.append(Hit(d.day_index, si, p, "drop"))
            elif shut:
                hits.append(Hit(d.day_index, si, p, "replace"))
        return Affected(base, hits, codes, shifted - {(h.day, h.stop) for h in hits})
    stop = day.stops[d.stop_index]
    if stop.pinned:
        raise InvalidDisruption("Stop đã ghim — bỏ ghim để đổi")
    return Affected(base, [Hit(d.day_index, d.stop_index, places[stop.place_id], "replace")], [], set())


def _reject(trip: Trip, stops: list[DraftStop], weekdays: list[str], si: int, lost: Place, cand: Place,
            prev: Point, nxt: Point, indoor: bool = False) -> str | None:
    if indoor and cand.outdoor:
        # ponytail: lọc sau similar_places (top 20 theo embedding); dữ liệu lớn thì thêm tham số indoor cho truy vấn
        return "NO_INDOOR_CANDIDATE"
    stop = stops[si]
    if not any(is_open(cand, w, stop.start_time, stop.duration_min) for w in weekdays):
        return "NO_OPEN_CANDIDATE"
    start = _minutes(stop.start_time)
    # Không bắt lịch chặt hơn bản cũ: chỉ loại khi chặng mới vừa vượt khoảng trống vừa dài hơn chặng cũ.
    if si > 0:
        p = stops[si - 1]
        need = _leg_min(prev, cand, trip)
        if need > start - (_minutes(p.start_time) + p.duration_min) and need > _leg_min(prev, lost, trip):
            return "NOT_REACHABLE_IN_TIME"
    if si + 1 < len(stops):
        need = _leg_min(cand, nxt, trip)
        if need > _minutes(stops[si + 1].start_time) - start - stop.duration_min and need > _leg_min(lost, nxt, trip):
            return "NOT_REACHABLE_IN_TIME"
    return None


def _hard(itin: Itinerary) -> set[tuple[str, int | None, int | None]]:
    return {(c.kind, c.day_index, c.place_id) for c in itin.conflicts if c.kind in HARD}


def _stop_intents(trip: Trip, p: Place) -> set[str]:
    """Intent của Place mà Trip quan tâm; Trip không có Intent nào thì lấy mọi Intent của Place."""
    w = intent_weights(trip)
    return place_intents(p.tags) & w.keys() if w else place_intents(p.tags)


def _labels(intents) -> str:
    return ", ".join(INTENT_LABELS[i] for i in sorted(intents))


def _travel_min(itin: Itinerary) -> int:
    return sum(leg.duration_min for d in itin.days for leg in d.legs)


def _day_end(day: Day) -> str:
    if not day.stops:
        return "—"
    m = max(_minutes(s.start_time) + s.duration_min for s in day.stops)
    return f"{m // 60:02d}:{m % 60:02d}"


def _explain(prefix: str | None, kept: set, lost: set, dropped: str | None, travel_delta: int, cost_delta: int,
             day_end: str, di: int) -> str:
    parts = [prefix] if prefix else []
    if kept:
        parts.append(f"giữ mục đích {_labels(kept)}")
    if lost:
        parts.append(f"chuyến không còn {_labels(lost)}")
    if dropped:
        parts.append(dropped)
    parts.append("thời gian di chuyển như cũ" if travel_delta == 0
                 else f"{'thêm' if travel_delta > 0 else 'bớt'} {abs(travel_delta)} phút di chuyển")
    parts.append("chi phí như cũ" if cost_delta == 0
                 else f"{'đắt hơn' if cost_delta > 0 else 'rẻ hơn'} {vnd(abs(cost_delta))}")
    parts.append(f"ngày {di + 1} kết thúc {day_end}")
    s = "; ".join(parts)
    return s[0].upper() + s[1:] + "."


def _title(pick: dict[Hit, Place], dropped: list[Place]) -> str:
    parts = [c.name for c in pick.values()]
    if dropped:
        parts.append("bỏ " + ", ".join(p.name for p in dropped))
    s = " · ".join(parts) or "chỉ dời giờ"
    return s[0].upper() + s[1:]


def _pick(ranked: dict[Hit, list[Place]], k: int, may_drop: bool) -> dict[Hit, Place] | None:
    """Phương án k: ứng viên thứ k còn trống của từng Stop, không trùng Place.
    Thiếu ứng viên thứ k: closed/disliked → None; rain/late → lấy ứng viên tốt nhất còn trống, hết hẳn mới bỏ Stop."""
    taken, pick = set(), {}
    for h, cs in ranked.items():
        free = [c for c in cs if c.id not in taken]
        if len(free) > k or (may_drop and free):
            c = free[min(k, len(free) - 1)]
            pick[h] = c
            taken.add(c.id)
        elif not may_drop:
            return None
    return pick


def _variant(trip: Trip, itin: Itinerary, places: dict[int, Place], d: Disruption, aff: Affected,
             pick: dict[Hit, Place], hub: Hub | None) -> ProposalOption | str:
    draft = aff.base.model_copy(deep=True)
    for h, c in pick.items():
        s = draft.days[h.day].stops[h.stop]
        kept = _stop_intents(trip, h.lost) & place_intents(c.tags)
        draft.days[h.day].stops[h.stop] = DraftStop(
            place_id=c.id, start_time=s.start_time, duration_min=s.duration_min,
            reason=f"Thay {h.lost.name} ({KIND_TEXT[d.kind]})" + (f" — cùng mục đích {_labels(kept)}" if kept else ""))
    drop = {(h.day, h.stop) for h in aff.hits if h not in pick}
    touched = {(h.day, h.stop) for h in pick} | aff.shifted
    changed = []
    for di, day in enumerate(draft.days):
        kept_stops = []
        for si, s in enumerate(day.stops):
            if (di, si) in drop:
                continue
            if (di, si) in touched:
                changed.append((di, len(kept_stops)))
            kept_stops.append(s)
        day.stops = kept_stops

    new = build_itinerary(trip, draft, places | {c.id: c for c in pick.values()},
                          [x.rain_chance for x in itin.days], hub)
    pinned = {s.place_id for x in itin.days for s in x.stops if s.pinned}
    # Conflict trên Stop ghim không do engine gây ra (engine không đổi Stop ghim) → không loại phương án
    extra = {x for x in _hard(new) - _hard(itin) if x[2] is None or x[2] not in pinned}
    if extra:
        return "OVER_BUDGET" if any(k == "over_budget" for k, _, _ in extra) else "NEW_CONFLICT"

    dropped = [h.lost for h in aff.hits if h not in pick]
    # Conflict mềm mới (vd thiếu bữa vì bỏ Stop) và Conflict trên Stop ghim không loại phương án → phải nói ra
    old_msgs = {c.message for c in itin.conflicts}  # so theo message: missing_meal các bữa cùng (kind, day, None)
    notes = [c.message for c in new.conflicts if c.message not in old_msgs
             and (c.kind not in HARD or c.place_id in pinned)]
    li = set().union(*(_stop_intents(trip, h.lost) for h in pick))
    kept = set().union(*(_stop_intents(trip, h.lost) & place_intents(c.tags) for h, c in pick.items()))
    # "không còn" chỉ khi cả chuyến mất Intent đó, không phải khi Stop khác vẫn đáp ứng
    lost_trip = {k for k, hit in itin.intents.items() if hit and not new.intents.get(k)}
    cost_delta = new.total_cost - itin.total_cost
    travel_delta = _travel_min(new) - _travel_min(itin)
    di = d.day_index
    codes = list(aff.codes)
    if li:
        codes.append("INTENT_MATCH" if kept == li else "INTENT_PARTIAL" if kept else "INTENT_LOST")
    if pick and d.kind == "rain":
        codes.append("INDOOR_FOR_RAIN")
    if dropped:
        codes.append("STOP_DROPPED")
    if travel_delta > 5:
        codes.append("FARTHER")
    elif travel_delta < -5:
        codes.append("CLOSER")
    if cost_delta > 0:
        codes.append("PRICIER")
    elif cost_delta < 0:
        codes.append("CHEAPER")
    day_end = _day_end(new.days[di])
    prefix = None
    if d.kind == "late":
        prefix = f"dời {d.minutes} phút từ {places[itin.days[di].stops[d.stop_index].place_id].name}"
    drop_text = f"bỏ {', '.join(p.name for p in dropped)} ({DROP_TEXT[d.kind]})" if dropped else None
    metrics = {"cost_delta": cost_delta, "travel_min_delta": travel_delta,
               "day_end_before": _day_end(itin.days[di]), "day_end_after": day_end,
               "retention_before": itin.retention, "retention_after": new.retention,
               "intents_kept": sorted(kept), "intents_lost": sorted(lost_trip),
               "features": [features(trip, h.lost, c, *_neighbors(itin, places, h.day, h.stop, hub))
                            for h, c in pick.items()]}
    return ProposalOption(itinerary=new, added=list(pick.values()), changed=changed, metrics=metrics,
                          reason_codes=codes, title=_title(pick, dropped),
                          explanation=_explain(prefix, kept, lost_trip, drop_text, travel_delta, cost_delta, day_end, di)
                          + (f" Lưu ý: {'; '.join(notes)}." if notes else ""))


def propose(trip: Trip, itin: Itinerary, places: dict[int, Place], d: Disruption, candidates_fn: CandidatesFn,
            hub: Hub | None = None, score_fn=score) -> list[ProposalOption] | NoFeasible:
    aff = _affected(trip, itin, places, d)
    if d.kind == "rain" and not aff.hits:
        return NoFeasible(reason_codes=["NOTHING_OUTDOOR"])
    used = {s.place_id for x in itin.days for s in x.stops}
    if itin.stay_place_id is not None:
        used.add(itin.stay_place_id)

    rejected, ranked = [], {}
    for h in aff.hits:
        if h.mode != "replace":
            continue
        prev, nxt = _neighbors(itin, places, h.day, h.stop, hub)
        cands = candidates_fn(h.lost, used)
        mode = trip.travel_mode or DEFAULT_TRAVEL_MODE
        if prev is not None:  # km thật cho chặng tới/rời từng ứng viên — _reject và features gọi make_leg
            distance.prefetch([prev], [h.lost, *cands], mode)
        if nxt is not None:
            distance.prefetch([h.lost, *cands], [nxt], mode)
        ok = []
        for c in cands:
            why = _reject(trip, aff.base.days[h.day].stops, _weekdays(itin.days[h.day]), h.stop, h.lost, c,
                          prev, nxt, indoor=d.kind == "rain")
            (rejected.append(why) if why else ok.append(c))
        ok.sort(key=lambda c: score_fn(features(trip, h.lost, c, prev, nxt)), reverse=True)
        ranked[h] = ok

    may_drop = d.kind in ("rain", "late")
    variants = []
    for k in range(max([1, *map(len, ranked.values())])):  # ít nhất 1 lượt: rain/late không ứng viên → bỏ Stop
        pick = _pick(ranked, k, may_drop)
        if pick is None:
            break
        variants.append(pick)
    n_pick = N_OPTIONS - 1 if d.kind == "late" and aff.hits else N_OPTIONS
    if d.kind == "late":
        variants.append({})  # "Bỏ các Stop hỏng" — hoặc "Chỉ dời giờ" khi không có Stop hỏng

    options, seen = [], set()
    for i, pick in enumerate(variants):
        last = d.kind == "late" and i == len(variants) - 1
        if len(options) >= n_pick and not last:
            continue
        sig = frozenset((h.day, h.stop, c.id) for h, c in pick.items())
        if sig in seen:
            continue
        seen.add(sig)
        got = _variant(trip, itin, places, d, aff, pick, hub)
        (rejected.append(got) if isinstance(got, str) else options.append(got))
    return options or NoFeasible(reason_codes=sorted(set(rejected)) or ["NO_CANDIDATE"])
