import httpx
import pytest

from app.config import settings
from app.domain import WEEKDAYS, Disruption, Draft, Place, Trip
from app.replan import InvalidDisruption, NoFeasible, propose
from app.rules import build_itinerary

WEEK = {d: ["08:00", "22:00"] for d in WEEKDAYS}
TRIP = Trip(destination="da-lat", days=1, budget=5_000_000, travel_mode="grab",
            preferred_tags=["cafe-chill", "lich-su"])


def P(id, kind="cafe", tags=(), price=0, lat=11.94, hours=None, outdoor=False):
    return Place(id=id, destination="da-lat", name=f"P{id}", kind=kind, lat=lat, lon=108.44, price=price,
                 open_hours=WEEK if hours is None else hours, outdoor=outdoor, tags=list(tags))


def setup(stops, trip=TRIP, pinned=()):
    """stops: [(Place, 'HH:MM')] → (places, Itinerary 1 ngày, mỗi Stop 60′)."""
    places = {p.id: p for p, _ in stops}
    draft = Draft.model_validate({"summary": "", "days": [{"stops": [
        {"place_id": p.id, "start_time": t, "duration_min": 60, "pinned": p.id in pinned} for p, t in stops]}]})
    return places, build_itinerary(trip, draft, places)


def cands(*ps, seen=None):
    def fn(lost, used):
        if seen is not None:
            seen.update(used)
        return [p for p in ps if p.id not in used]
    return fn


def closed(stop=0, kind="closed"):
    return Disruption(kind=kind, day_index=0, stop_index=stop)


LOST, MUSEUM = P(1, tags=["cafe-chill"]), P(2, kind="tham-quan", tags=["lich-su"])


def test_same_intent_ranks_first_and_other_stops_untouched():
    places, itin = setup([(LOST, "09:00"), (MUSEUM, "11:00")])
    same, other = P(10, tags=["cafe-chill", "yen-tinh"]), P(11, tags=["check-in"])
    opts = propose(TRIP, itin, places, closed(), cands(other, same))
    assert [o.added[0].id for o in opts] == [10, 11]
    assert opts[0].reason_codes[0] == "INTENT_MATCH"
    assert opts[0].metrics["intents_kept"] == ["thu-gian"]
    assert opts[1].metrics["intents_lost"] == ["thu-gian"]
    assert opts[0].changed == [(0, 0)]
    assert opts[0].itinerary.days[0].stops[1].place_id == 2
    assert "Giữ mục đích Thư giãn" in opts[0].explanation


def test_at_most_three_distinct_and_used_places_excluded():
    places, itin = setup([(LOST, "09:00"), (MUSEUM, "11:00")])
    seen = set()
    opts = propose(TRIP, itin, places, closed(kind="disliked"), cands(*[P(i) for i in range(10, 15)], seen=seen))
    assert seen == {1, 2}
    assert len(opts) == 3
    assert len({o.added[0].id for o in opts}) == 3
    assert "bạn muốn đổi" in opts[0].itinerary.days[0].stops[0].reason


def test_closed_at_that_time_is_skipped():
    places, itin = setup([(LOST, "09:00")])
    late_opener = P(10, hours={d: ["14:00", "22:00"] for d in WEEKDAYS})
    assert propose(TRIP, itin, places, closed(), cands(late_opener)) == NoFeasible(reason_codes=["NO_OPEN_CANDIDATE"])
    opts = propose(TRIP, itin, places, closed(), cands(late_opener, P(11)))
    assert [o.added[0].id for o in opts] == [11]


def test_no_candidate():
    places, itin = setup([(LOST, "09:00")])
    assert propose(TRIP, itin, places, closed(), cands()) == NoFeasible(reason_codes=["NO_CANDIDATE"])


def test_too_far_to_reach_next_stop_in_time():
    places, itin = setup([(MUSEUM, "09:00"), (LOST, "10:05")])
    far = P(10, lat=12.2)  # ~37 km bằng Grab ≈ 90 phút, khoảng trống chỉ 5 phút
    got = propose(TRIP, itin, places, closed(stop=1), cands(far))
    assert got == NoFeasible(reason_codes=["NOT_REACHABLE_IN_TIME"])


def test_new_over_budget_is_rejected():
    trip = Trip(destination="da-lat", days=1, budget=100_000, travel_mode="grab")
    places, itin = setup([(P(1, price=50_000), "09:00")], trip=trip)
    got = propose(trip, itin, places, closed(), cands(P(10, price=500_000)))
    assert got == NoFeasible(reason_codes=["OVER_BUDGET"])


def test_pinned_or_missing_stop_is_invalid():
    places, itin = setup([(LOST, "09:00")], pinned={1})
    with pytest.raises(InvalidDisruption):
        propose(TRIP, itin, places, closed(), cands(P(10)))
    with pytest.raises(InvalidDisruption):
        propose(TRIP, itin, places, closed(stop=5), cands(P(10)))


def test_explanation_from_numbers_without_percent():
    places, itin = setup([(P(1, tags=["cafe-chill"], price=20_000), "09:00")])
    opts = propose(TRIP, itin, places, closed(), cands(P(10, tags=["cafe-chill"], price=50_000)))
    assert opts[0].metrics["cost_delta"] == 30_000
    assert "đắt hơn 30.000đ" in opts[0].explanation
    assert "%" not in opts[0].explanation
    assert "PRICIER" in opts[0].reason_codes


def test_lost_place_without_intent():
    places, itin = setup([(P(1, tags=["gia-re"]), "09:00")])
    opts = propose(TRIP, itin, places, closed(), cands(P(10, tags=["gia-re"])))
    assert not any(c.startswith("INTENT_") for c in opts[0].reason_codes)
    assert "mục đích" not in opts[0].explanation


def test_intent_still_covered_elsewhere_is_not_reported_lost():
    other_cafe = P(3, tags=["cafe-chill"])
    places, itin = setup([(LOST, "09:00"), (MUSEUM, "11:00"), (other_cafe, "14:00")])
    opts = propose(TRIP, itin, places, closed(), cands(P(10, tags=["check-in"])))
    assert opts[0].metrics["intents_lost"] == []
    assert "không còn" not in opts[0].explanation


def test_only_trip_intents_are_mentioned():
    places, itin = setup([(P(1, tags=["cafe-chill", "check-in"]), "09:00")])
    opts = propose(TRIP, itin, places, closed(), cands(P(10, tags=["cafe-chill"])))
    assert opts[0].reason_codes[0] == "INTENT_MATCH"
    assert "Vui chơi" not in opts[0].explanation


def test_option_title_is_new_place_name():
    places, itin = setup([(LOST, "09:00")])
    opts = propose(TRIP, itin, places, closed(), cands(P(10)))
    assert opts[0].title == "P10"


RAIN = Disruption(kind="rain", day_index=0)
PARK, LAKE = P(1, kind="tham-quan", outdoor=True), P(3, kind="tham-quan", outdoor=True)
CAFE = P(2)


def test_rain_replaces_every_outdoor_stop_with_indoor():
    places, itin = setup([(PARK, "09:00"), (CAFE, "11:00"), (LAKE, "14:00")])
    a, b = P(10, kind="tham-quan"), P(11, kind="tham-quan")
    opts = propose(TRIP, itin, places, RAIN, cands(P(12, kind="tham-quan", outdoor=True), a, b))
    for o in opts:
        assert all(not (places | {p.id: p for p in o.added})[s.place_id].outdoor
                   for s in o.itinerary.days[0].stops)
    assert [s.place_id for s in opts[0].itinerary.days[0].stops] == [10, 2, 11]
    assert opts[0].changed == [(0, 0), (0, 2)]
    assert "INDOOR_FOR_RAIN" in opts[0].reason_codes
    assert "(mưa)" in opts[0].itinerary.days[0].stops[0].reason
    assert opts[0].itinerary.days[0].rain_chance is None  # C1: không ghi giả định mưa
    # phương án 2: Công viên → P11, Hồ lấy ứng viên còn trống P10 thay vì bị bỏ (fix sau review)
    assert [s.place_id for s in opts[1].itinerary.days[0].stops] == [11, 2, 10]
    assert "STOP_DROPPED" not in opts[1].reason_codes
    assert opts[1].title == "P11 · P10"


def test_rain_keeps_pinned_outdoor_stop():
    places, itin = setup([(PARK, "09:00"), (LAKE, "14:00")], pinned={1})
    opts = propose(TRIP, itin, places, RAIN, cands(P(10, kind="tham-quan")))
    assert opts[0].itinerary.days[0].stops[0].place_id == 1
    assert opts[0].itinerary.days[0].stops[1].place_id == 10
    assert opts[0].reason_codes[0] == "PINNED_CONFLICT"


def test_rain_nothing_outdoor():
    places, itin = setup([(CAFE, "09:00")])
    assert propose(TRIP, itin, places, RAIN, cands(P(10))) == NoFeasible(reason_codes=["NOTHING_OUTDOOR"])


def test_rain_without_indoor_candidate_drops_stop_even_if_day_empties():
    places, itin = setup([(PARK, "09:00")])
    opts = propose(TRIP, itin, places, RAIN, cands(P(12, kind="tham-quan", outdoor=True)))
    assert len(opts) == 1
    assert opts[0].itinerary.days[0].stops == []
    assert opts[0].title == "Bỏ P1"
    assert opts[0].explanation.startswith("Bỏ P1 (không có chỗ trong nhà phù hợp)")  # phần đầu câu được viết hoa
    assert opts[0].metrics["day_end_after"] == "—"


def late(stop=0, minutes=30):
    return Disruption(kind="late", day_index=0, stop_index=stop, minutes=minutes)


def test_late_only_shifts_when_nothing_breaks():
    places, itin = setup([(LOST, "09:00"), (MUSEUM, "11:00")])
    opts = propose(TRIP, itin, places, late(), cands(P(10)))
    assert len(opts) == 1
    assert [s.start_time for s in opts[0].itinerary.days[0].stops] == ["09:30", "11:30"]
    assert opts[0].reason_codes == ["LATE_SHIFT"]
    assert opts[0].title == "Chỉ dời giờ"
    assert opts[0].changed == [(0, 0), (0, 1)]
    assert opts[0].explanation.startswith("Dời 30 phút từ P1")


def test_late_leaves_earlier_stops_alone():
    places, itin = setup([(LOST, "09:00"), (MUSEUM, "11:00")])
    opts = propose(TRIP, itin, places, late(stop=1), cands())
    assert [s.start_time for s in opts[0].itinerary.days[0].stops] == ["09:00", "11:30"]


def test_late_replaces_stop_closed_at_new_time_or_drops_it():
    morning = P(2, kind="tham-quan", hours={d: ["08:00", "12:00"] for d in WEEKDAYS})
    places, itin = setup([(LOST, "09:00"), (morning, "11:00")])
    opts = propose(TRIP, itin, places, late(stop=1, minutes=60), cands(P(10, kind="tham-quan")))
    assert [o.title for o in opts] == ["P10", "Bỏ P2"]
    assert opts[0].itinerary.days[0].stops[1].start_time == "12:00"
    assert opts[0].reason_codes[:1] == ["LATE_SHIFT"]
    assert "STOP_DROPPED" in opts[1].reason_codes
    assert "bỏ P2 (không kịp giờ)" in opts[1].explanation


def test_late_drops_stop_pushed_past_pace_end_in_every_option():
    places, itin = setup([(LOST, "09:00"), (MUSEUM, "19:30")])  # Pace "vua" kết thúc 21:00
    opts = propose(TRIP, itin, places, late(stop=0, minutes=60), cands(P(10, kind="tham-quan")))
    assert len(opts) == 1
    assert [s.place_id for s in opts[0].itinerary.days[0].stops] == [1]


def test_late_keeps_stop_that_was_already_past_pace_end():
    all_day = P(2, kind="tham-quan", tags=["lich-su"], hours={})  # mở cả ngày: chỉ kiểm luật quá giờ
    places, itin = setup([(LOST, "09:00"), (all_day, "21:00")])  # đã quá 21:00 từ trước
    opts = propose(TRIP, itin, places, late(stop=0, minutes=30), cands())
    assert [s.place_id for s in opts[0].itinerary.days[0].stops] == [1, 2]


def test_late_pinned_stop_is_shifted_not_replaced_even_if_closed():
    morning = P(2, kind="tham-quan", hours={d: ["08:00", "12:00"] for d in WEEKDAYS})
    places, itin = setup([(LOST, "09:00"), (morning, "11:00")], pinned={2})
    opts = propose(TRIP, itin, places, late(stop=0, minutes=60), cands(P(10, kind="tham-quan")))
    assert len(opts) == 1
    assert opts[0].itinerary.days[0].stops[1].place_id == 2
    assert opts[0].itinerary.days[0].stops[1].start_time == "12:00"
    assert "PINNED_CONFLICT" in opts[0].reason_codes


def test_late_past_midnight():
    places, itin = setup([(LOST, "20:00")])
    opts = propose(TRIP, itin, places, late(minutes=240), cands())
    assert opts[0].itinerary.days[0].stops == []  # Stop chưa ghim → bỏ
    places, itin = setup([(LOST, "21:00")], pinned={1})
    with pytest.raises(InvalidDisruption, match="nửa đêm"):
        propose(TRIP, itin, places, late(minutes=240), cands())


def test_rain_keeps_replacing_stop_that_has_only_one_candidate():
    # review: phương án 2–3 không được bỏ Stop khi Stop đó vẫn còn chỗ thay
    places, itin = setup([(PARK, "09:00"), (LAKE, "14:00")])
    a = [P(i, kind="tham-quan") for i in (10, 11, 12)]
    b0 = P(20, kind="tham-quan")
    opts = propose(TRIP, itin, places, RAIN, lambda lost, used: a if lost.id == 1 else [b0])
    assert len(opts) == 3
    assert all("STOP_DROPPED" not in o.reason_codes for o in opts)
    assert all(o.itinerary.days[0].stops[1].place_id == 20 for o in opts)


def test_late_explains_new_missing_meal_and_pinned_conflict():
    dinner = P(2, kind="an-uong")
    places, itin = setup([(LOST, "09:00"), (dinner, "19:30")])
    opts = propose(TRIP, itin, places, late(stop=1, minutes=60), cands())
    assert "chưa có bữa tối" in opts[0].explanation
    morning = P(2, kind="tham-quan", hours={d: ["08:00", "12:00"] for d in WEEKDAYS})
    places, itin = setup([(LOST, "09:00"), (morning, "11:00")], pinned={2})
    opts = propose(TRIP, itin, places, late(stop=0, minutes=60), cands())
    assert "P2 không mở cửa lúc 12:00" in opts[0].explanation


def test_candidates_ranked_by_real_road_time(monkeypatch):
    """Ứng viên chim bay gần hơn nhưng đường thật vòng xa → bị loại vì không kịp giờ."""
    monkeypatch.setattr(settings, "goong_api_key", "k")

    def handler(request):  # mọi chặng 1 km / 3′, riêng chặng dính tới P3 (lat 11.9402) là 30 km / 70′
        q = request.url.params
        return httpx.Response(200, json={"rows": [{"elements": [
            {"status": "OK", "distance": {"value": m}, "duration": {"value": s}}
            for d in q["destinations"].split("|")
            for m, s in [(30_000, 4200) if "11.9402" in o + d else (1000, 180)]]}
            for o in q["origins"].split("|")]})
    monkeypatch.setattr(httpx, "get", lambda url, params, timeout: httpx.Client(
        transport=httpx.MockTransport(handler)).get(url, params=params))

    a, lost, b = P(1), P(2, lat=11.9401), P(4)
    near_but_slow, ok = P(3, lat=11.9402), P(5, lat=11.95)
    places, itin = setup([(a, "09:00"), (lost, "10:15"), (b, "11:30")])
    opts = propose(TRIP, itin, places, Disruption(version=1, kind="closed", day_index=0, stop_index=1),
                   lambda lost, used: [near_but_slow, ok])
    assert [o.added[0].id for o in opts] == [5]
