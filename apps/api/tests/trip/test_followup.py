import pytest

from app.services.trip.agent import merge_trip, trip_brief
from app.services.trip.domain import WEEKDAYS, Draft, Place, Trip
from app.services.trip.followup import (CHANGE_TOOL, InvalidEdit, apply_ops, changed_trip, itinerary_facts,
                                        review_group_feedback)
from app.services.trip.rules import build_itinerary, cost_breakdown
from tests.trip.conftest import FakeClient, reply

WEEK = {d: ["08:00", "22:00"] for d in WEEKDAYS}
TRIP = Trip(destination="tp-hcm", days=2, budget=5_000_000, travelers=2, travel_mode="xe-may")


def P(id, kind="cafe", price=0, lat=11.94, outdoor=False):
    return Place(id=id, destination="tp-hcm", name=f"P{id}", kind=kind, lat=lat, lon=108.44, price=price,
                 open_hours=WEEK, outdoor=outdoor, tags=[])


PLACES = {1: P(1, "an-uong", 50_000), 2: P(2, "tham-quan", 100_000, lat=11.96, outdoor=True),
          3: P(3, "cafe", 40_000), 9: P(9, "cho-o", 500_000, lat=11.95)}


def itin(pinned=()):
    draft = Draft.model_validate({"stay_place_id": 9, "summary": "", "days": [
        {"stops": [{"place_id": 1, "start_time": "08:00", "duration_min": 60},
                   {"place_id": 2, "start_time": "10:00", "duration_min": 90, "pinned": 2 in pinned}]},
        {"stops": [{"place_id": 3, "start_time": "09:00", "duration_min": 60}]}]})
    return build_itinerary(TRIP, draft, PLACES)


def test_cost_breakdown_sums_to_total():
    it = itin()
    b = cost_breakdown(TRIP, it, PLACES)
    assert b["an_uong"] == (50_000 + 40_000) * 2
    assert b["tham_quan"] == 100_000 * 2
    assert b["cho_o"] == 500_000 * 1 * 1  # 1 phòng × 1 đêm
    assert sum(b.values()) == it.total_cost


def test_group_review_uses_code_computed_cost_and_keeps_unresolved_feedback():
    base = itin()
    ops = [{"op": "retime_stop", "day": 1, "stop": 1, "start_time": "09:00"}]
    draft, _ = apply_ops(base, ops, set(PLACES))
    expected = build_itinerary(TRIP, draft, PLACES)
    fake = FakeClient([reply(("review_group_feedback", {
        "summary": "Dời giờ", "ops": ops, "unresolved_feedback": ["Ý kiến trái chiều"],
        "total_cost": 999_999_999,
    }))])
    generated = list(review_group_feedback(
        None, fake, "test-model", TRIP, 1, base, 2, base, PLACES,
        "Dời giờ", [None, None], None, lambda _texts: [],
    ))
    prompt = fake.calls[0]["messages"][0]["content"]
    assert "Version nguồn: 1" in prompt and "Version nền mới nhất: 2" in prompt
    assert "không tự chọn theo đa số" in prompt
    candidate = generated[-1]["candidate"]
    assert candidate["unresolved_feedback"] == ["Ý kiến trái chiều"]
    assert candidate["itinerary"]["total_cost"] == expected.total_cost
    assert candidate["itinerary"]["total_cost"] != 999_999_999


def test_facts_have_code_computed_numbers_and_indexes():
    it = itin(pinned={2})
    km = sum(leg.distance_km for d in it.days for leg in d.legs)
    facts = itinerary_facts(TRIP, it, PLACES)
    assert f"{km:.1f} km" in facts
    assert "[1.2]" in facts and "đã ghim" in facts  # ngày 1, Stop 2 — đánh số như người dùng nói
    assert "không có dự báo" in facts  # Trip không có ngày đi
    assert "nhiệt độ" in facts  # nói rõ app không có dữ liệu này


def stops(draft):
    return [[(s.place_id, s.start_time) for s in d.stops] for d in draft.days]


def test_replace_keeps_every_other_stop():
    it = itin()
    draft, changed = apply_ops(it, [{"op": "replace_stop", "day": 2, "stop": 1, "place_id": 4, "reason": "rẻ hơn"}],
                               {1, 2, 3, 4, 9})
    assert stops(draft) == [[(1, "08:00"), (2, "10:00")], [(4, "09:00")]]
    assert changed == [(1, 0)]
    assert draft.days[1].stops[0].duration_min == 60  # giữ thời lượng cũ khi không nói


def test_remove_and_add_use_old_indexes_and_sort_by_time():
    it = itin()
    draft, changed = apply_ops(it, [{"op": "remove_stop", "day": 1, "stop": 1},
                                    {"op": "add_stop", "day": 1, "place_id": 3, "start_time": "13:00"},
                                    {"op": "retime_stop", "day": 1, "stop": 2, "start_time": "09:00"}],
                               {1, 2, 3, 9})
    assert stops(draft)[0] == [(2, "09:00"), (3, "13:00")]
    assert changed == [(0, 0), (0, 1)]


def test_change_stay():
    draft, changed = apply_ops(itin(), [{"op": "change_stay", "place_id": 8}], {8})
    assert draft.stay_place_id == 8 and changed == []


@pytest.mark.parametrize("op", [
    {"op": "replace_stop", "day": 1, "stop": 2, "place_id": 3},  # Stop đã ghim
    {"op": "replace_stop", "day": 1, "stop": 1, "place_id": 77},  # Place chưa search
    {"op": "remove_stop", "day": 6, "stop": 1},  # sai chỉ số
    {"op": "remove_stop", "day": 2, "stop": 1},  # ngày không còn Stop
    {"op": "retime_stop", "day": 1, "stop": 1, "start_time": "9h"},  # giờ sai định dạng
    {"op": "fly"},
])
def test_invalid_edits(op):
    with pytest.raises(InvalidEdit):
        apply_ops(itin(pinned={2}), [op], {1, 2, 3, 9})


def test_last_day_end_is_separate_from_flight_time():
    t = changed_trip(TRIP.model_copy(update={"departure_time": "17:00"}), {"last_day_end": "13:00"})
    assert (t.departure_time, t.last_day_end) == ("17:00", "13:00")
    assert "last_day_end" in CHANGE_TOOL["function"]["parameters"]["properties"]["changes"]["properties"]
    assert "xong mọi hoạt động trước 13:00" in trip_brief(t, None)
    assert merge_trip(t, TRIP).last_day_end == "13:00"  # tin sau không nhắc lại thì giữ
