import datetime as dt
import math

from app import distance
from app.domain import (DEFAULT_TRAVEL_MODE, WEEKDAYS, Conflict, Day, Draft, Hub, Itinerary, Leg, Place, Stop, Trip,
                        intent_weights, place_intents)

ROAD_FACTOR = 1.3  # chim bay → đường bộ, dùng khi chưa có km thật từ Goong (app.distance)
WALK_MAX_KM = 0.8
SPEED_KMH = {"walk": 4.5, "xe-may": 25, "grab": 25, "o-to": 25}
FUEL_PER_KM = 2_000
CAR_FUEL_PER_KM = 3_500
CAR_PARKING_PER_DAY = 50_000
GRAB_BASE, GRAB_PER_KM = 12_000, 9_000
MOTO_RENT_PER_DAY = 120_000
RAIN_PCT = 60
ARRIVAL_BUFFER_MIN = 60  # từ lúc tới đến Stop đầu tiên (nhận phòng, gửi đồ)
DEPARTURE_BUFFER_MIN = 90  # từ Stop cuối đến giờ về (ra sân bay/bến xe)
TRAVEL_SLACK_MIN = 5  # Leg được vượt khoảng trống giữa hai Stop chừng này phút trước khi báo Conflict
MEALS = (("sáng", "06:00", "10:00"), ("trưa", "11:00", "14:00"), ("tối", "17:00", "21:00"))  # Stop an-uong bắt đầu trong khung


class InvalidDraft(Exception):
    pass


def vnd(n: int) -> str:
    return f"{n:,}".replace(",", ".") + "đ"


def haversine_km(a: Place | Hub, b: Place | Hub) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def make_leg(a: Place | Hub, b: Place | Hub, mode: str, travelers: int) -> Leg:
    real = distance.lookup(a, b, mode)
    km = real[0] if real else round(haversine_km(a, b) * ROAD_FACTOR, 2)
    if km < WALK_MAX_KM:
        m, cost = "walk", 0
    elif mode == "grab":
        m, cost = "grab", (GRAB_BASE + round(km * GRAB_PER_KM)) * math.ceil(travelers / 4)
    elif mode == "o-to-rieng":
        m, cost = "o-to", round(km * CAR_FUEL_PER_KM)  # một xe cho cả nhóm (≤ 7 người)
    else:  # xe-may, xe-may-rieng
        m, cost = "xe-may", round(km * FUEL_PER_KM) * math.ceil(travelers / 2)
    minutes = real[1] if real and m != "walk" else max(1, round(km / SPEED_KMH[m] * 60))
    return Leg(from_place_id=getattr(a, "id", None), to_place_id=getattr(b, "id", None), distance_km=km,
               duration_min=minutes, mode=m, cost=cost)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def is_open(place: Place, weekday: str, start: str, duration_min: int) -> bool:
    if not place.open_hours:
        return True
    hours = place.open_hours.get(weekday)
    if not hours:
        return False
    o, c = _minutes(hours[0]), _minutes(hours[1])
    if c <= o:  # mở qua đêm, vd 18:00–02:00
        c = 24 * 60
    s = _minutes(start)
    return o <= s and s + duration_min <= c


def _check_draft(trip: Trip, draft: Draft, places: dict[int, Place], pinned=frozenset()) -> None:
    ids = {s.place_id for d in draft.days for s in d.stops}
    missing = sorted(set(pinned) - ids)
    if missing:
        raise InvalidDraft(f"Thiếu Place đã ghim: {missing} — phải giữ các Place này trong lịch")
    if draft.stay_place_id is not None:
        ids.add(draft.stay_place_id)
    unknown = sorted(i for i in ids if i not in places)
    if unknown:
        raise InvalidDraft(f"place_id không tồn tại hoặc chưa được tìm: {unknown}")
    stays = sorted({s.place_id for d in draft.days for s in d.stops if places[s.place_id].kind == "cho-o"})
    if stays:
        raise InvalidDraft(f"Place {stays} là chỗ ở — đặt vào stay_place_id, không làm Stop")
    if len(draft.days) != trip.days:
        raise InvalidDraft(f"Trip có {trip.days} ngày nhưng Itinerary có {len(draft.days)} ngày")
    if trip.days > 1 and draft.stay_place_id is None:
        raise InvalidDraft("Trip dài hơn 1 ngày phải có stay_place_id (Place kind cho-o)")
    if draft.stay_place_id is not None and places[draft.stay_place_id].kind != "cho-o":
        raise InvalidDraft("stay_place_id phải là Place kind cho-o")


def build_itinerary(trip: Trip, draft: Draft, places: dict[int, Place],
                    rain: list[int | None] | None = None, hub: Hub | None = None, pinned=frozenset()) -> Itinerary:
    _check_draft(trip, draft, places, pinned)
    stay = places.get(draft.stay_place_id) if draft.stay_place_id is not None else None
    mode = trip.travel_mode or DEFAULT_TRAVEL_MODE
    pairs = math.ceil(trip.travelers / 2)  # 2 người/phòng, 2 người/xe
    total = stay.price * pairs * (trip.days - 1) if stay else 0
    if mode == "xe-may":
        total += MOTO_RENT_PER_DAY * pairs * trip.days
    elif mode == "o-to-rieng":
        total += CAR_PARKING_PER_DAY * trip.days

    days = []
    last = len(draft.days) - 1
    for i, d in enumerate(draft.days):
        stops = [Stop(**s.model_dump(), est_cost=places[s.place_id].price * trip.travelers)
                 for s in sorted(d.stops, key=lambda s: s.start_time)]
        start = hub if hub and i == 0 else stay
        end = hub if hub and i == last else stay
        route = [p for p in (start, *(places[s.place_id] for s in stops), end) if p is not None]
        distance.prefetch(route[:-1], route[1:], mode)
        legs = [make_leg(a, b, mode, trip.travelers) for a, b in zip(route, route[1:])]
        date = trip.start_date + dt.timedelta(days=i) if trip.start_date else None
        days.append(Day(date=date, stops=stops, legs=legs, rain_chance=rain[i] if rain else None))
        total += sum(s.est_cost for s in stops) + sum(leg.cost for leg in legs)

    itin = Itinerary(stay_place_id=draft.stay_place_id, days=days, total_cost=total, summary=draft.summary)
    itin.conflicts = find_conflicts(trip, itin, places)
    itin.intents, itin.retention = intent_retention(trip, itin, places)
    return itin


def last_day_limit(trip: Trip) -> int | None:
    """Phút muộn nhất Stop ngày cuối được kết thúc: giờ về − 90′ và giờ muốn xong, lấy mốc sớm hơn."""
    limits = [_minutes(trip.departure_time) - DEPARTURE_BUFFER_MIN] if trip.departure_time else []
    if trip.last_day_end:
        limits.append(_minutes(trip.last_day_end))
    return min(limits) if limits else None


def find_conflicts(trip: Trip, itin: Itinerary, places: dict[int, Place]) -> list[Conflict]:
    out = []
    if itin.total_cost > trip.budget:
        out.append(Conflict(kind="over_budget", message=f"Vượt Budget {vnd(itin.total_cost - trip.budget)}"))
    last = len(itin.days) - 1
    for i, day in enumerate(itin.days):
        # Không có ngày đi → chỉ báo đóng cửa khi Place không mở vào khung giờ đó ở bất kỳ thứ nào
        weekdays = [WEEKDAYS[day.date.weekday()]] if day.date else WEEKDAYS
        for s in day.stops:
            p = places[s.place_id]
            if not any(is_open(p, w, s.start_time, s.duration_min) for w in weekdays):
                out.append(Conflict(kind="closed", day_index=i, place_id=p.id,
                                    message=f"Ngày {i + 1}: {p.name} không mở cửa lúc {s.start_time}"))
            if day.rain_chance is not None and day.rain_chance >= RAIN_PCT and p.outdoor:
                out.append(Conflict(kind="rain_outdoor", day_index=i, place_id=p.id,
                                    message=f"Ngày {i + 1} khả năng mưa {day.rain_chance}%, {p.name} ở ngoài trời"))
            if i == 0 and trip.arrival_time and _minutes(s.start_time) < _minutes(trip.arrival_time) + ARRIVAL_BUFFER_MIN:
                out.append(Conflict(kind="before_arrival", day_index=i, place_id=p.id,
                                    message=f"Ngày 1: {p.name} lúc {s.start_time} nhưng {trip.arrival_time} bạn mới tới"))
            end = _minutes(s.start_time) + s.duration_min
            if i == last and trip.last_day_end and end > _minutes(trip.last_day_end):
                out.append(Conflict(kind="after_departure", day_index=i, place_id=p.id,
                                    message=f"Ngày {i + 1}: {p.name} kết thúc sau {trip.last_day_end}"
                                            " — giờ bạn muốn xong hoạt động"))
            elif i == last and trip.departure_time and end > _minutes(trip.departure_time) - DEPARTURE_BUFFER_MIN:
                out.append(Conflict(kind="after_departure", day_index=i, place_id=p.id,
                                    message=f"Ngày {i + 1}: {p.name} kết thúc quá sát giờ về {trip.departure_time}"))
    for i, day in enumerate(itin.days):
        # Leg đầu ngày đi từ Hub/Stay (không bao giờ là Stop) → bỏ qua để legs[k] nối Stop k với Stop k+1
        legs = day.legs[1 if day.stops and day.legs and day.legs[0].from_place_id != day.stops[0].place_id else 0:]
        for a, b, leg in zip(day.stops, day.stops[1:], legs):
            gap = _minutes(b.start_time) - _minutes(a.start_time) - a.duration_min
            if leg.duration_min > gap + TRAVEL_SLACK_MIN:
                out.append(Conflict(kind="no_travel_time", day_index=i, place_id=b.place_id,
                                    message=f"Ngày {i + 1}: không kịp đi từ {places[a.place_id].name} đến "
                                            f"{places[b.place_id].name} — cần {leg.duration_min}′, chỉ có {max(gap, 0)}′"))
    for i, day in enumerate(itin.days):
        for meal, lo, hi in MEALS:
            if i == 0 and trip.arrival_time and _minutes(hi) <= _minutes(trip.arrival_time) + ARRIVAL_BUFFER_MIN:
                continue  # bữa trước khi tới nơi
            if i == last and (limit := last_day_limit(trip)) is not None and _minutes(lo) >= limit:
                continue  # bữa sau khi đã xong / đã về
            if not any(places[s.place_id].kind == "an-uong" and lo <= s.start_time < hi for s in day.stops):
                out.append(Conflict(kind="missing_meal", day_index=i, message=f"Ngày {i + 1} chưa có bữa {meal}"))
    covered = {t for d in itin.days for s in d.stops for t in places[s.place_id].tags}
    for t in trip.required_tags:
        if t not in covered:
            out.append(Conflict(kind="missing_tag", message=f"Chưa có Stop nào đáp ứng '{t}'"))
    return out


def intent_retention(trip: Trip, itin: Itinerary, places: dict[int, Place]) -> tuple[dict[str, bool], float | None]:
    """R = Σ wₖ·zₖ / Σ wₖ; zₖ = 1 nếu có Stop mà Place thuộc Intent k."""
    w = intent_weights(trip)
    covered = set().union(*(place_intents(places[s.place_id].tags) for d in itin.days for s in d.stops))
    hit = {i: i in covered for i in w}
    total = sum(w.values())
    return hit, (round(sum(w[i] for i in w if hit[i]) / total, 2) if total else None)


def cost_breakdown(trip: Trip, itin: Itinerary, places: dict[int, Place]) -> dict[str, int]:
    """Chia total_cost theo nhóm; di_chuyen = Leg + tiền thuê xe/gửi xe (phần còn lại)."""
    food = sum(s.est_cost for d in itin.days for s in d.stops if places[s.place_id].kind in ("an-uong", "cafe"))
    stops = sum(s.est_cost for d in itin.days for s in d.stops)
    stay = places[itin.stay_place_id].price * math.ceil(trip.travelers / 2) * (trip.days - 1) \
        if itin.stay_place_id is not None else 0
    return {"an_uong": food, "tham_quan": stops - food, "cho_o": stay,
            "di_chuyen": itin.total_cost - stops - stay}
