import pytest

from app import rules
from app.agent import MAX_STEPS, plan, trip_brief
from app.domain import Draft, Hub, Trip
from app.places import get_places
from app.rules import build_itinerary
from tests.fakes import FakeClient, reply
from tests.helpers import ALL_DAY, add_place, unit_vec


@pytest.fixture(autouse=True)
def no_meal_rule(monkeypatch):
    """Các test ở đây không xếp bữa ăn; quy tắc 3 bữa được test riêng ở test_rules / test_missing_meal_*."""
    monkeypatch.setattr(rules, "MEALS", ())


def fake_embed(texts):
    return [unit_vec(0) for _ in texts]


def stops(*ids):
    return {"summary": "Lịch trình thử", "days": [{"stops": [
        {"place_id": pid, "start_time": f"{9 + i:02d}:00", "duration_min": 60, "reason": "hợp sở thích"}
        for i, pid in enumerate(ids)]}]}


def run(conn, responses, budget=10_000_000):
    client = FakeClient(responses)
    trip = Trip(destination="da-lat", days=1, budget=budget, travel_mode="grab")
    return client, list(plan(conn, client, "m", trip, fake_embed, None))


def tool_messages(client):
    return [m["content"] for m in client.calls[-1]["messages"] if m.get("role") == "tool"]


def test_happy_path(conn):
    a, b = add_place(conn, name="Cafe", kind="cafe"), add_place(conn, name="Hồ", vec=1)
    _, events = run(conn, [reply(("search_places", {"query": "cafe"})),
                           reply(("submit_itinerary", stops(a, b)))])
    assert [e["type"] for e in events] == ["tool_call", "itinerary"]
    assert {p["id"] for p in events[0]["places"]} == {a, b}
    itin = events[-1]["itinerary"]
    assert [s["place_id"] for s in itin["days"][0]["stops"]] == [a, b]
    assert set(events[-1]["places"]) == {str(a), str(b)}


def test_unseen_place_rejected_then_retry(conn):
    a = add_place(conn)
    client, events = run(conn, [reply(("search_places", {"query": "x"})),
                                reply(("submit_itinerary", stops(999))),
                                reply(("submit_itinerary", stops(a)))])
    assert events[-1]["type"] == "itinerary"
    assert any(m.startswith("Lỗi") and "999" in m for m in tool_messages(client))


def test_place_not_searched_is_rejected(conn):
    a = add_place(conn)  # có trong DB nhưng AI chưa search → vẫn bị từ chối
    _, events = run(conn, [reply(("submit_itinerary", stops(a))),
                           reply(("submit_itinerary", stops(a)))])
    assert events[-1]["type"] == "error"


def test_gives_up_after_two_invalid(conn):
    add_place(conn)
    _, events = run(conn, [reply(("search_places", {"query": "x"})),
                           reply(("submit_itinerary", stops(999))),
                           reply(("submit_itinerary", stops(998)))])
    assert events[-1]["type"] == "error"


def test_malformed_arguments_do_not_crash(conn):
    a = add_place(conn)
    client, events = run(conn, [reply(("search_places", "{hỏng")),
                                reply(("search_places", {"query": "x"})),
                                reply(("submit_itinerary", stops(a)))])
    assert events[-1]["type"] == "itinerary"
    assert any("JSON" in m for m in tool_messages(client))


def test_conflict_gets_one_resubmit_then_accepted(conn):
    a = add_place(conn, price=500_000)
    client, events = run(conn, [reply(("search_places", {"query": "x"})),
                                reply(("submit_itinerary", stops(a))),
                                reply(("submit_itinerary", stops(a)))], budget=1_000)
    assert [c["kind"] for c in events[-1]["itinerary"]["conflicts"] if c["kind"] != "missing_meal"] == ["over_budget"]
    assert any(m.startswith("Conflict") for m in tool_messages(client))


def test_thinking_text_is_streamed(conn):
    a = add_place(conn)
    _, events = run(conn, [reply(("search_places", {"query": "x"}), content="Để mình tìm quán cafe"),
                           reply(("submit_itinerary", stops(a)))])
    assert events[0] == {"type": "thinking", "text": "Để mình tìm quán cafe"}


def test_null_must_have_tags_does_not_crash(conn):
    a = add_place(conn)
    _, events = run(conn, [reply(("search_places", {"query": "x", "must_have_tags": None})),
                           reply(("submit_itinerary", stops(a)))])
    assert events[-1]["type"] == "itinerary"


def test_valid_itinerary_kept_after_two_invalid_resubmits(conn):
    a = add_place(conn, price=500_000)
    _, events = run(conn, [reply(("search_places", {"query": "x"})),
                           reply(("submit_itinerary", stops(a))),
                           reply(("submit_itinerary", stops(999))),
                           reply(("submit_itinerary", stops(998)))], budget=1_000)
    assert events[-1]["type"] == "itinerary"
    assert [c["kind"] for c in events[-1]["itinerary"]["conflicts"] if c["kind"] != "missing_meal"] == ["over_budget"]


def test_max_steps_exhausted_with_no_submit_is_error(conn):
    add_place(conn)
    responses = [reply(("search_places", {"query": "x"})) for _ in range(MAX_STEPS)]
    _, events = run(conn, responses)
    assert events[-1]["type"] == "error"


def test_max_steps_exhausted_after_conflict_submit_keeps_best_effort(conn):
    a = add_place(conn, price=500_000)
    responses = [reply(("search_places", {"query": "x"})),
                 reply(("submit_itinerary", stops(a)))]
    responses += [reply(("search_places", {"query": "x"})) for _ in range(MAX_STEPS - len(responses))]
    _, events = run(conn, responses, budget=1_000)
    assert events[-1]["type"] == "itinerary"
    assert [c["kind"] for c in events[-1]["itinerary"]["conflicts"] if c["kind"] != "missing_meal"] == ["over_budget"]


def test_brief_mentions_times_and_hub():
    trip = Trip(destination="da-lat", days=1, budget=1, arrival_time="14:00", departure_time="20:00")
    text = trip_brief(trip, None, Hub(name="Sân bay Liên Khương", lat=11.75, lon=108.37))
    assert "14:00" in text and "20:00" in text and "Sân bay Liên Khương" in text
    assert "Travel Mode: xe-may" in text  # chưa nói → mặc định


def test_brief_quotes_user_messages():
    trip = Trip(destination="da-lat", days=2, budget=1)
    text = trip_brief(trip, None, None, ["Đà Lạt 2 ngày, phải đi vườn hoa", "khách sạn rẻ hơn"])
    assert "phải đi vườn hoa" in text and "khách sạn rẻ hơn" in text


def test_plan_prompt_requires_three_meals():
    from app.agent import PLAN_PROMPT
    assert "trưa" in PLAN_PROMPT and "11:00" in PLAN_PROMPT


def test_missing_meal_is_sent_back_to_ai(conn, monkeypatch):
    monkeypatch.setattr(rules, "MEALS", (("trưa", "11:00", "14:00"),))
    sight, food = add_place(conn, name="Hồ"), add_place(conn, name="Quán cơm", kind="an-uong", vec=1)
    lunch = {"summary": "ok", "days": [{"stops": [
        {"place_id": sight, "start_time": "09:00", "duration_min": 60, "reason": "x"},
        {"place_id": food, "start_time": "12:00", "duration_min": 60, "reason": "bữa trưa"}]}]}
    client, events = run(conn, [reply(("search_places", {"query": "x"})),
                                reply(("submit_itinerary", stops(sight))),
                                reply(("submit_itinerary", lunch))])
    assert any("chưa có bữa trưa" in m for m in tool_messages(client))
    assert events[-1]["itinerary"]["conflicts"] == []


def test_plan_rejects_draft_dropping_pinned_place_then_retries(conn):
    a, b = add_place(conn, name="Cafe ghim", kind="cafe"), add_place(conn, name="Hồ", vec=1)
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, travel_mode="grab")
    places = get_places(conn, [a, b])
    old = build_itinerary(trip, Draft.model_validate(stops(a)), places)
    old.days[0].stops[0].pinned = True
    client = FakeClient([reply(("submit_itinerary", stops(b))), reply(("submit_itinerary", stops(a, b)))])
    events = list(plan(conn, client, "m", trip, fake_embed, None, previous=(old, places)))
    assert "Thiếu Place đã ghim" in tool_messages(client)[0]
    assert [s["place_id"] for s in events[-1]["itinerary"]["days"][0]["stops"]] == [a, b]
    assert "đã ghim" in client.calls[0]["messages"][1]["content"]


def test_itinerary_places_carry_hours_and_description(conn):
    a, b = add_place(conn, name="Cafe", kind="cafe"), add_place(conn, name="Hồ", vec=1)
    _, events = run(conn, [reply(("search_places", {"query": "cafe"})),
                           reply(("submit_itinerary", stops(a, b)))])
    p = events[-1]["places"][str(a)]
    assert p["open_hours"] == ALL_DAY and p["description"] == ""
    assert events[0]["places"][0]["open_hours"] == ALL_DAY


def test_seeded_places_usable_without_search(conn):
    pid = add_place(conn, "Cafe A", "cafe")
    client = FakeClient([reply(("submit_itinerary", stops(pid)))])
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, travel_mode="grab")
    events = list(plan(conn, client, "m", trip, fake_embed, None, seeded=get_places(conn, [pid]),
                       notes="Chuyên gia đã chọn: Cafe A"))
    assert [e["type"] for e in events] == ["itinerary"]
    assert "Chuyên gia đã chọn: Cafe A" in client.calls[0]["messages"][1]["content"]


def test_max_searches_refuses_extra_search(conn):
    pid = add_place(conn, "Cafe A", "cafe")
    client = FakeClient([reply(("search_places", {"query": "a"})), reply(("search_places", {"query": "b"})),
                         reply(("submit_itinerary", stops(pid)))])
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, travel_mode="grab")
    events = list(plan(conn, client, "m", trip, fake_embed, None, max_searches=1))
    assert [e["type"] for e in events] == ["tool_call", "itinerary"]
    assert "hết lượt tìm" in tool_messages(client)[1]


def test_place_outside_seeded_still_rejected(conn):
    a, b = add_place(conn, "A", "cafe"), add_place(conn, "B", "cafe")
    client = FakeClient([reply(("submit_itinerary", stops(b))), reply(("submit_itinerary", stops(a)))])
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, travel_mode="grab")
    events = list(plan(conn, client, "m", trip, fake_embed, None, seeded=get_places(conn, [a])))
    assert [s["place_id"] for s in events[-1]["itinerary"]["days"][0]["stops"]] == [a]
    assert tool_messages(client)[0].startswith("Lỗi")


def test_run_search_keeps_only_allowed_kinds(conn):
    from app.agent import run_search
    cafe = add_place(conn, "Cafe", "cafe")
    add_place(conn, "Quán", "an-uong")
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, travel_mode="grab")
    seen = {}
    ev, result = run_search(conn, trip, fake_embed, {"query": "x"}, seen, kinds=("cafe",))
    assert list(seen) == [cafe] and [p["id"] for p in ev["places"]] == [cafe]
    assert "Quán" not in result
