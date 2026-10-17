import datetime as dt

import pytest

from app import distance
from app.domain import Draft, Hub, Itinerary, Place, Trip, intent_weights, place_intents
from app.rules import InvalidDraft, build_itinerary, is_open, make_leg

WEEK = {d: ["08:00", "17:00"] for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]}


def P(id, kind="tham-quan", price=0, lat=11.94, lon=108.44, outdoor=False, tags=(), hours=None):
    return Place(id=id, destination="da-lat", name=f"P{id}", kind=kind, lat=lat, lon=lon,
                 price=price, open_hours=WEEK if hours is None else hours, outdoor=outdoor,
                 tags=list(tags))


def kinds(itin):
    """Conflict trừ missing_meal — các test này dựng Draft tối giản, không xếp bữa ăn."""
    return [c.kind for c in itin.conflicts if c.kind != "missing_meal"]


def draft(days, stay=None, start="09:00"):
    return Draft.model_validate({"stay_place_id": stay, "summary": "", "days": [
        {"stops": [{"place_id": pid, "start_time": start, "duration_min": 60} for pid in day]}
        for day in days]})


def test_short_leg_is_walk():
    leg = make_leg(P(1), P(2, lat=11.9401), "xe-may", 1)
    assert (leg.mode, leg.cost) == ("walk", 0)


def test_motorbike_leg_cost():
    leg = make_leg(P(1), P(2, lat=12.04), "xe-may", 1)  # ~0.1° vĩ độ ≈ 11.1 km × 1.3
    assert leg.mode == "xe-may"
    assert leg.distance_km == pytest.approx(14.46, abs=0.05)
    assert leg.cost == round(leg.distance_km * 2_000)


def test_total_cost():
    # 2 ngày, 2 người: Stay 500k × 1 phòng × 1 đêm + thuê 1 xe × 2 ngày + Stop × 2 người; Leg = 0 (cùng tọa độ)
    places = {1: P(1, price=50_000), 2: P(2, price=30_000), 9: P(9, kind="cho-o", price=500_000, hours={})}
    trip = Trip(destination="da-lat", days=2, travelers=2, budget=10_000_000)
    itin = build_itinerary(trip, draft([[1], [2]], stay=9), places)
    assert itin.total_cost == 500_000 + 240_000 + 100_000 + 60_000
    assert [len(d.legs) for d in itin.days] == [2, 2]  # Stay → Stop → Stay
    assert kinds(itin) == []


def test_unknown_place_rejected():
    with pytest.raises(InvalidDraft, match="999"):
        build_itinerary(Trip(destination="da-lat", days=1, budget=1), draft([[999]]), {1: P(1)})


def test_stay_place_as_stop_rejected():
    # #39: Place chỗ ở làm Stop → tiền phòng bị tính 2 lần
    places = {1: P(1), 9: P(9, kind="cho-o", price=500_000, hours={})}
    with pytest.raises(InvalidDraft, match="chỗ ở"):
        build_itinerary(Trip(destination="da-lat", days=2, budget=1), draft([[1], [9]], stay=9), places)


def test_multi_day_requires_stay():
    with pytest.raises(InvalidDraft, match="stay_place_id"):
        build_itinerary(Trip(destination="da-lat", days=2, budget=1), draft([[1], [1]]), {1: P(1)})


def test_over_budget_still_returns_itinerary():
    itin = build_itinerary(Trip(destination="da-lat", days=1, budget=10_000, travel_mode="grab"),
                           draft([[1]]), {1: P(1, price=50_000)})
    assert kinds(itin) == ["over_budget"]
    assert "40.000đ" in itin.conflicts[0].message


def test_closed_on_that_weekday():
    monday = dt.date(2026, 10, 5)
    assert monday.weekday() == 0
    closed_monday = {**WEEK, "mon": None}
    trip = Trip(destination="da-lat", days=1, budget=10**9, start_date=monday, travel_mode="grab")
    itin = build_itinerary(trip, draft([[1]]), {1: P(1, hours=closed_monday)})
    assert kinds(itin) == ["closed"]


def test_without_date_closed_only_if_never_open():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab")
    ok = build_itinerary(trip, draft([[1]]), {1: P(1, hours={**WEEK, "mon": None})})
    assert kinds(ok) == []
    night = {d: ["18:00", "23:00"] for d in WEEK}
    bad = build_itinerary(trip, draft([[1]]), {1: P(1, hours=night)})
    assert kinds(bad) == ["closed"]


def test_overnight_hours():
    bar = P(1, hours={d: ["18:00", "02:00"] for d in WEEK})
    assert is_open(bar, "mon", "22:00", 60)


def test_rain_outdoor_conflict():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab")
    itin = build_itinerary(trip, draft([[1]]), {1: P(1, outdoor=True)}, rain=[80])
    assert kinds(itin) == ["rain_outdoor"]
    assert itin.days[0].rain_chance == 80


def test_missing_required_tag():
    trip = Trip(destination="da-lat", days=1, budget=10**9, required_tags=["an-chay"], travel_mode="grab")
    itin = build_itinerary(trip, draft([[1]]), {1: P(1, tags=["cafe-chill"])})
    assert kinds(itin) == ["missing_tag"]


HUB = Hub(name="Sân bay Liên Khương", lat=11.75, lon=108.37)
STAY = {9: P(9, kind="cho-o", hours={})}


def test_unset_travel_mode_defaults_to_rented_motorbike():
    trip = Trip(destination="da-lat", days=1, budget=10**9)
    assert build_itinerary(trip, draft([[1]]), {1: P(1)}).total_cost == 120_000


def test_own_motorbike_has_no_rent():
    trip = Trip(destination="da-lat", days=1, travelers=2, budget=10**9, travel_mode="xe-may-rieng")
    assert build_itinerary(trip, draft([[1]]), {1: P(1)}).total_cost == 0


def test_own_car_leg_is_one_car_fuel():
    leg = make_leg(P(1), P(2, lat=12.04), "o-to-rieng", 5)
    assert leg.mode == "o-to"
    assert leg.cost == round(leg.distance_km * 3_500)


def test_own_car_pays_parking_per_day():
    trip = Trip(destination="da-lat", days=2, travelers=5, budget=10**9, travel_mode="o-to-rieng")
    itin = build_itinerary(trip, draft([[1], [1]], stay=9), {1: P(1), **STAY})
    assert itin.total_cost == 2 * 50_000


def test_hub_starts_first_day_and_ends_last_day():
    trip = Trip(destination="da-lat", days=2, budget=10**9, travel_mode="grab")
    itin = build_itinerary(trip, draft([[1], [2]], stay=9), {1: P(1), 2: P(2), **STAY}, hub=HUB)
    d1, d2 = itin.days
    assert (d1.legs[0].from_place_id, d1.legs[-1].to_place_id) == (None, 9)
    assert (d2.legs[0].from_place_id, d2.legs[-1].to_place_id) == (9, None)
    assert d1.legs[0].mode == "grab" and d1.legs[0].distance_km > 20


def test_hub_without_stay_one_day():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab")
    legs = build_itinerary(trip, draft([[1]]), {1: P(1)}, hub=HUB).days[0].legs
    assert [(leg.from_place_id, leg.to_place_id) for leg in legs] == [(None, 1), (1, None)]


def test_late_arrival_still_returns_itinerary_with_conflict():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab", arrival_time="20:00")
    itin = build_itinerary(trip, draft([[1]]), {1: P(1)})  # Stop 09:00
    assert kinds(itin) == ["before_arrival"]
    assert "20:00" in itin.conflicts[0].message


def test_stop_after_arrival_buffer_is_fine():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab", arrival_time="14:00")
    assert kinds(build_itinerary(trip, draft([[1]], start="15:00"), {1: P(1)})) == []


def test_stop_too_close_to_departure_on_last_day():
    trip = Trip(destination="da-lat", days=2, budget=10**9, travel_mode="grab", departure_time="11:00")
    itin = build_itinerary(trip, draft([[1], [1]], stay=9), {1: P(1), **STAY})  # 09:00–10:00 > 11:00 − 90'
    assert [(c.kind, c.day_index) for c in itin.conflicts if c.kind != "missing_meal"] == [("after_departure", 1)]


def meal_draft(times, kind_ids):
    """Một ngày: mỗi (giờ, place_id) là một Stop 60 phút."""
    return Draft.model_validate({"stay_place_id": None, "summary": "", "days": [
        {"stops": [{"place_id": pid, "start_time": t, "duration_min": 60} for t, pid in zip(times, kind_ids)]}]})


FOOD = {1: P(1, kind="an-uong", hours={}), 2: P(2, hours={})}  # 1 = quán ăn, 2 = điểm tham quan


def meals_missing(itin):
    return [c.message for c in itin.conflicts if c.kind == "missing_meal"]


def test_three_meals_no_conflict():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab")
    itin = build_itinerary(trip, meal_draft(["07:00", "09:00", "12:00", "18:00"], [1, 2, 1, 1]), FOOD)
    assert meals_missing(itin) == []


def test_sight_at_lunch_is_missing_lunch():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab")
    itin = build_itinerary(trip, meal_draft(["07:00", "12:00", "18:00"], [1, 2, 1]), FOOD)
    assert meals_missing(itin) == ["Ngày 1 chưa có bữa trưa"]


def test_meal_before_arrival_not_required():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab", arrival_time="11:00")
    itin = build_itinerary(trip, meal_draft(["12:30", "18:00"], [1, 1]), FOOD)
    assert meals_missing(itin) == []


def test_meal_after_departure_not_required():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab", departure_time="15:00")
    itin = build_itinerary(trip, meal_draft(["07:00", "11:30"], [1, 1]), FOOD)
    assert meals_missing(itin) == []


def test_last_day_end_limits_stops_but_keeps_flight_time():
    # bay 17:00 nhưng muốn xong hết lúc 13:00: Stop tới 13:00 được, không trừ thêm 90 phút
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab", departure_time="17:00",
                last_day_end="13:00")
    ok = build_itinerary(trip, meal_draft(["07:00", "12:00"], [1, 1]), FOOD)
    assert ok.conflicts == []  # có bữa sáng + trưa; bữa tối sau 13:00 không bắt buộc
    late = build_itinerary(trip, meal_draft(["07:00", "12:30"], [1, 1]), FOOD)
    assert [c.message for c in late.conflicts] == ["Ngày 1: P1 kết thúc sau 13:00 — giờ bạn muốn xong hoạt động"]


def test_place_intents_ignores_constraint_tags():
    assert place_intents(["gia-re", "hai-san", "view-dep"]) == {"am-thuc", "thien-nhien"}


def test_intent_weights_required_beats_preferred():
    trip = Trip(destination="da-lat", days=1, budget=1, required_tags=["cafe-chill"],
                preferred_tags=["yen-tinh", "lich-su"])
    assert intent_weights(trip) == {"thu-gian": 2, "van-hoa": 1}


def test_retention_weighted():
    places = {1: P(1, tags=["cafe-chill"]), 2: P(2, tags=["gia-re"])}
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, required_tags=["cafe-chill"],
                preferred_tags=["lich-su"])
    itin = build_itinerary(trip, draft([[1, 2]]), places)
    assert itin.intents == {"thu-gian": True, "van-hoa": False}
    assert itin.retention == 0.67  # 2 / (2 + 1)


def test_retention_none_without_intents():
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, preferred_tags=["gia-re"])
    itin = build_itinerary(trip, draft([[1]]), {1: P(1)})
    assert (itin.intents, itin.retention) == ({}, None)


def test_old_itinerary_json_still_loads():
    itin = Itinerary.model_validate({"stay_place_id": None, "days": [], "total_cost": 0})
    assert (itin.intents, itin.retention) == ({}, None)


def test_draft_missing_pinned_place_is_rejected():
    p = Place(id=1, destination="da-lat", name="A", kind="cafe", lat=11.94, lon=108.44, price=0,
              open_hours={}, outdoor=False, tags=[])
    trip = Trip(destination="da-lat", days=1, budget=1_000_000, travel_mode="grab")
    draft = Draft.model_validate({"summary": "", "days": [{"stops": [
        {"place_id": 1, "start_time": "09:00", "duration_min": 60}]}]})
    with pytest.raises(InvalidDraft, match="Thiếu Place đã ghim"):
        build_itinerary(trip, draft, {1: p}, pinned={1, 7})
    assert build_itinerary(trip, draft, {1: p}, pinned={1}).days[0].stops[0].place_id == 1


def test_leg_uses_goong_when_cached():
    a, b = P(1), P(2, lat=12.04)
    distance._cache[distance._key(a, b, "bike")] = (20.0, 48)
    leg = make_leg(a, b, "xe-may", 1)
    assert (leg.distance_km, leg.duration_min, leg.cost) == (20.0, 48, 40_000)
    assert make_leg(b, a, "xe-may", 1).distance_km == pytest.approx(14.46, abs=0.05)  # chưa có → chim bay × 1.3


def test_goong_short_leg_still_walks():
    a, b = P(1), P(2, lat=11.9401)
    distance._cache[distance._key(a, b, "bike")] = (0.5, 2)
    leg = make_leg(a, b, "xe-may", 1)
    assert (leg.mode, leg.cost, leg.duration_min) == ("walk", 0, 7)  # 0.5 km đi bộ, không lấy phút xe máy


def two_stops(second_start, lat=12.04):
    trip = Trip(destination="da-lat", days=1, budget=10_000_000)
    d = Draft.model_validate({"summary": "", "days": [{"stops": [
        {"place_id": 1, "start_time": "09:00", "duration_min": 60},
        {"place_id": 2, "start_time": second_start, "duration_min": 60}]}]})
    return build_itinerary(trip, d, {1: P(1), 2: P(2, lat=lat)})


def test_no_travel_time_conflict():
    itin = two_stops("10:10")  # ~14.5 km xe máy ≈ 35′, chỉ có 10′
    c = next(c for c in itin.conflicts if c.kind == "no_travel_time")
    assert (c.day_index, c.place_id) == (0, 2)
    assert c.message == "Ngày 1: không kịp đi từ P1 đến P2 — cần 35′, chỉ có 10′"


def test_enough_gap_no_travel_conflict():
    assert kinds(two_stops("10:40")) == []
    assert kinds(two_stops("10:00", lat=11.9401)) == []  # sát giờ nhưng đi bộ 1′ → trong mức du di


def test_overlapping_stops_conflict():
    assert "no_travel_time" in kinds(two_stops("09:30", lat=11.9401))


def test_no_travel_time_with_stay_and_hub():
    trip = Trip(destination="da-lat", days=2, budget=10_000_000)
    d = Draft.model_validate({"stay_place_id": 9, "summary": "", "days": [{"stops": [
        {"place_id": 1, "start_time": "09:00", "duration_min": 60},
        {"place_id": 2, "start_time": "10:10", "duration_min": 60}]},
        {"stops": [{"place_id": 1, "start_time": "09:00", "duration_min": 60}]}]})
    itin = build_itinerary(trip, d, {1: P(1), 2: P(2, lat=12.04), **STAY}, hub=HUB)
    assert [c.place_id for c in itin.conflicts if c.kind == "no_travel_time"] == [2]
