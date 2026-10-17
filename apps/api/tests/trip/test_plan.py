import pytest

from app.services.trip import rules
from app.services.trip.agent import MAX_STEPS, PLAN_TOOLS, plan, run_search, trip_brief
from app.services.trip.domain import Draft, Hub, Trip
from app.services.trip.places import get_places
from app.services.trip.rules import build_itinerary
from tests.trip.conftest import FakeClient, reply


@pytest.fixture(autouse=True)
def no_meal_rule(monkeypatch):
    """Các test ở đây không xếp bữa ăn; quy tắc 3 bữa được test riêng ở test_rules / test_missing_meal_*."""
    monkeypatch.setattr(rules, "MEALS", ())


def fake_embed(texts):
    return None  # no embeddings configured: search_places falls back to keywords


def stops(*ids):
    return {"summary": "Lịch trình thử", "days": [{"stops": [
        {"place_id": pid, "start_time": f"{9 + i:02d}:00", "duration_min": 60, "reason": "hợp sở thích"}
        for i, pid in enumerate(ids)]}]}


def run(db, responses, budget=10_000_000):
    client = FakeClient(responses)
    trip = Trip(destination="tp-hcm", days=1, budget=budget, travel_mode="grab")
    return client, list(plan(db, client, "m", trip, fake_embed, None))


def tool_messages(client):
    return [m["content"] for m in client.calls[-1]["messages"] if m.get("role") == "tool"]


def test_happy_path(db_session, trip_places):
    a, b = trip_places["cf-1"].id, trip_places["tq-cong-vien"].id
    _, events = run(db_session, [reply(("search_places", {"query": "cafe"})),
                                 reply(("submit_itinerary", stops(a, b)))])
    assert [e["type"] for e in events] == ["tool_call", "itinerary"]
    assert {p["id"] for p in events[0]["places"]} >= {a, b}
    itin = events[-1]["itinerary"]
    assert [s["place_id"] for s in itin["days"][0]["stops"]] == [a, b]
    assert set(events[-1]["places"]) == {str(a), str(b)}


def test_unseen_place_rejected_then_retry(db_session, trip_places):
    a = trip_places["cf-1"].id
    client, events = run(db_session, [reply(("search_places", {"query": "x"})),
                                      reply(("submit_itinerary", stops(999))),
                                      reply(("submit_itinerary", stops(a)))])
    assert events[-1]["type"] == "itinerary"
    assert any(m.startswith("Lỗi") and "999" in m for m in tool_messages(client))


def test_place_not_searched_is_rejected(db_session, trip_places):
    a = trip_places["cf-1"].id  # có trong DB nhưng AI chưa search → vẫn bị từ chối
    _, events = run(db_session, [reply(("submit_itinerary", stops(a))),
                                 reply(("submit_itinerary", stops(a)))])
    assert events[-1]["type"] == "error"


def test_gives_up_after_two_invalid(db_session, trip_places):
    _, events = run(db_session, [reply(("search_places", {"query": "x"})),
                                 reply(("submit_itinerary", stops(999))),
                                 reply(("submit_itinerary", stops(998)))])
    assert events[-1]["type"] == "error"


def test_malformed_arguments_do_not_crash(db_session, trip_places):
    a = trip_places["cf-1"].id
    client, events = run(db_session, [reply(("search_places", "{hỏng")),
                                      reply(("search_places", {"query": "x"})),
                                      reply(("submit_itinerary", stops(a)))])
    assert events[-1]["type"] == "itinerary"
    assert any("JSON" in m for m in tool_messages(client))


def test_conflict_gets_one_resubmit_then_accepted(db_session, trip_places):
    a = trip_places["cf-1"].id
    client, events = run(db_session, [reply(("search_places", {"query": "x"})),
                                      reply(("submit_itinerary", stops(a))),
                                      reply(("submit_itinerary", stops(a)))], budget=1_000)
    assert [c["kind"] for c in events[-1]["itinerary"]["conflicts"] if c["kind"] != "missing_meal"] == ["over_budget"]
    assert any(m.startswith("Conflict") for m in tool_messages(client))


def test_thinking_text_is_streamed(db_session, trip_places):
    a = trip_places["cf-1"].id
    _, events = run(db_session, [reply(("search_places", {"query": "x"}), content="Để mình tìm quán cafe"),
                                 reply(("submit_itinerary", stops(a)))])
    assert events[0] == {"type": "thinking", "text": "Để mình tìm quán cafe"}


def test_null_must_have_tags_does_not_crash(db_session, trip_places):
    a = trip_places["cf-1"].id
    _, events = run(db_session, [reply(("search_places", {"query": "x", "must_have_tags": None})),
                                 reply(("submit_itinerary", stops(a)))])
    assert events[-1]["type"] == "itinerary"


def test_valid_itinerary_kept_after_two_invalid_resubmits(db_session, trip_places):
    a = trip_places["cf-1"].id
    _, events = run(db_session, [reply(("search_places", {"query": "x"})),
                                 reply(("submit_itinerary", stops(a))),
                                 reply(("submit_itinerary", stops(999))),
                                 reply(("submit_itinerary", stops(998)))], budget=1_000)
    assert events[-1]["type"] == "itinerary"
    assert [c["kind"] for c in events[-1]["itinerary"]["conflicts"] if c["kind"] != "missing_meal"] == ["over_budget"]


def test_max_steps_exhausted_with_no_submit_is_error(db_session, trip_places):
    responses = [reply(("search_places", {"query": "x"})) for _ in range(MAX_STEPS)]
    _, events = run(db_session, responses)
    assert events[-1]["type"] == "error"


def test_max_steps_exhausted_after_conflict_submit_keeps_best_effort(db_session, trip_places):
    a = trip_places["cf-1"].id
    responses = [reply(("search_places", {"query": "x"})),
                 reply(("submit_itinerary", stops(a)))]
    responses += [reply(("search_places", {"query": "x"})) for _ in range(MAX_STEPS - len(responses))]
    _, events = run(db_session, responses, budget=1_000)
    assert events[-1]["type"] == "itinerary"
    assert [c["kind"] for c in events[-1]["itinerary"]["conflicts"] if c["kind"] != "missing_meal"] == ["over_budget"]


def test_brief_mentions_times_and_hub():
    trip = Trip(destination="tp-hcm", days=1, budget=1, arrival_time="14:00", departure_time="20:00")
    text = trip_brief(trip, None, Hub(name="Sân bay Tân Sơn Nhất", lat=10.8188, lon=106.6519))
    assert "14:00" in text and "20:00" in text and "Sân bay Tân Sơn Nhất" in text
    assert "Travel Mode: xe-may" in text  # chưa nói → mặc định


def test_brief_quotes_user_messages():
    trip = Trip(destination="tp-hcm", days=2, budget=1)
    text = trip_brief(trip, None, None, ["TP.HCM 2 ngày, phải đi Dinh Độc Lập", "khách sạn rẻ hơn"])
    assert "phải đi Dinh Độc Lập" in text and "khách sạn rẻ hơn" in text


def test_plan_prompt_requires_three_meals(db_session, trip_places):
    client, _ = run(db_session, [reply(("submit_itinerary", stops(999))), reply(("submit_itinerary", stops(999)))])
    system = client.calls[0]["messages"][0]["content"]
    assert "trưa" in system and "11:00" in system


def test_missing_meal_is_sent_back_to_ai(db_session, trip_places, monkeypatch):
    monkeypatch.setattr(rules, "MEALS", (("trưa", "11:00", "14:00"),))
    sight, food = trip_places["tq-dinh"].id, trip_places["an-pho"].id
    lunch = {"summary": "ok", "days": [{"stops": [
        {"place_id": sight, "start_time": "09:00", "duration_min": 60, "reason": "x"},
        {"place_id": food, "start_time": "12:00", "duration_min": 60, "reason": "bữa trưa"}]}]}
    client, events = run(db_session, [reply(("search_places", {"query": "x"})),
                                      reply(("submit_itinerary", stops(sight))),
                                      reply(("submit_itinerary", lunch))])
    assert any("chưa có bữa trưa" in m for m in tool_messages(client))
    assert events[-1]["itinerary"]["conflicts"] == []


def test_plan_rejects_draft_dropping_pinned_place_then_retries(db_session, trip_places):
    a, b = trip_places["cf-1"].id, trip_places["tq-cong-vien"].id
    trip = Trip(destination="tp-hcm", days=1, budget=10_000_000, travel_mode="grab")
    places = get_places(db_session, [a, b])
    old = build_itinerary(trip, Draft.model_validate(stops(a)), places)
    old.days[0].stops[0].pinned = True
    client = FakeClient([reply(("submit_itinerary", stops(b))), reply(("submit_itinerary", stops(a, b)))])
    events = list(plan(db_session, client, "m", trip, fake_embed, None, previous=(old, places)))
    assert "Thiếu Place đã ghim" in tool_messages(client)[0]
    assert [s["place_id"] for s in events[-1]["itinerary"]["days"][0]["stops"]] == [a, b]
    assert "đã ghim" in client.calls[0]["messages"][1]["content"]


def test_itinerary_places_carry_hours_and_description(db_session, trip_places):
    a, b = trip_places["cf-1"].id, trip_places["tq-cong-vien"].id
    _, events = run(db_session, [reply(("search_places", {"query": "cafe"})),
                                 reply(("submit_itinerary", stops(a, b)))])
    p = events[-1]["places"][str(a)]
    assert p["open_hours"] == trip_places["cf-1"].open_hours and p["description"] == ""
    assert events[0]["places"][0]["open_hours"]


def test_run_search_event_and_result_shape(db_session, trip_places):
    trip = Trip(destination="tp-hcm", days=1, budget=10_000_000, travel_mode="grab")
    seen = {}
    ev, result = run_search(db_session, trip, fake_embed, {"query": "cafe", "kind": "cafe"}, seen)
    cafes = {trip_places["cf-1"].id, trip_places["cf-2"].id}
    assert set(seen) == cafes and {p["id"] for p in ev["places"]} == cafes
    assert ev["type"] == "tool_call" and ev["name"] == "search_places" and ev["query"] == "cafe"
    assert "place_id" in result and "Phở" not in result


def test_search_tool_description_has_no_other_city():
    assert "Đà Lạt" not in str(PLAN_TOOLS) and "đồi thông" not in str(PLAN_TOOLS)
