import time
from contextlib import nullcontext

import pytest

from app import kv, multi, rules
from app.config import settings
from app.domain import Trip
from tests.fakes import RoleClient, reply
from tests.helpers import add_place, unit_vec

FOOD, SIGHT, STAY = "chuyên gia Ăn uống", "chuyên gia Tham quan", "chuyên gia Chỗ ở"
SYNTH = "trợ lý lập lịch trình"
SEARCH = reply(("search_places", {"query": "x"}))


@pytest.fixture(autouse=True)
def env(conn, monkeypatch):
    monkeypatch.setattr(rules, "MEALS", ())
    monkeypatch.setattr(multi, "agent_conn", lambda: nullcontext(conn))


def fake_embed(texts):
    return [unit_vec(0) for _ in texts]


def trip(days=1):
    return Trip(destination="da-lat", days=days, budget=10_000_000, travel_mode="grab")


def pick(*ids, note="ghi chú"):
    return reply(("submit_shortlist", {"place_ids": list(ids), "note": note}))


def one(conn, role, responses):
    events, client = [], RoleClient({"chuyên gia": responses})
    return client, events, multi.shortlist(conn, client, "m", trip(), role, fake_embed, None, [], events.append)


def test_roles_skip_stay_for_one_day_trip():
    assert multi.roles_for(trip(1)) == ["an-uong", "tham-quan"]
    assert multi.roles_for(trip(2)) == ["an-uong", "tham-quan", "cho-o"]


def test_wanted_follows_meals_and_pace():
    t = trip(2)  # Pace vừa: 5 Stop/ngày, 3 bữa/ngày
    assert [multi.wanted(t, r) for r in ("an-uong", "tham-quan", "cho-o")] == [12, 8, 3]


def test_specialist_returns_places_it_searched(conn):
    food = add_place(conn, "Quán", "an-uong")
    add_place(conn, "Cafe", "cafe")
    client, events, out = one(conn, "an-uong", [SEARCH, pick(food)])
    assert out == {"role": "an-uong", "place_ids": [food], "note": "ghi chú"}
    assert events[0]["type"] == "tool_call" and events[0]["agent"] == "an-uong"
    assert [p["id"] for p in events[0]["places"]] == [food]  # code ép kind theo role
    assert "Ăn uống" in client.calls[0]["messages"][0]["content"]


def test_specialist_cannot_pick_another_roles_kind(conn):
    food, stay = add_place(conn, "Quán", "an-uong"), add_place(conn, "Khách sạn", "cho-o")
    _, _, out = one(conn, "an-uong", [reply(("search_places", {"query": "x", "kind": "cho-o"})), pick(stay, food)])
    assert out["place_ids"] == [food]


def test_sightseeing_role_takes_cafe_but_not_food(conn):
    cafe, food = add_place(conn, "Cafe", "cafe"), add_place(conn, "Quán", "an-uong")
    _, _, out = one(conn, "tham-quan", [reply(("search_places", {"query": "x", "kind": "an-uong"})), pick(cafe, food)])
    assert out["place_ids"] == [cafe]


def test_unknown_ids_dropped_and_empty_shortlist_fails(conn):
    add_place(conn, "Cafe", "cafe")
    with pytest.raises(multi.AgentFailed):
        one(conn, "tham-quan", [SEARCH] + [pick(999)] * 5)


def test_fifth_search_is_refused(conn):
    cafe = add_place(conn, "Cafe", "cafe")
    client, events, out = one(conn, "tham-quan", [SEARCH] * 5 + [pick(cafe)])
    assert len(events) == 4 and out["place_ids"] == [cafe]
    tool = [m["content"] for m in client.calls[-1]["messages"] if m.get("role") == "tool"]
    assert "hết lượt tìm" in tool[4]


def stops(*ids):
    return {"summary": "Lịch trình thử", "days": [{"stops": [
        {"place_id": pid, "start_time": f"{9 + i:02d}:00", "duration_min": 60, "reason": "hợp sở thích"}
        for i, pid in enumerate(ids)]}]}


def used(events):
    return [s["place_id"] for s in events[-1]["itinerary"]["days"][0]["stops"]]


def test_multi_plan_builds_itinerary_from_shortlists(conn):
    food, cafe = add_place(conn, "Quán Bà Tư", "an-uong"), add_place(conn, "Cafe Tùng", "cafe")
    rc = RoleClient({FOOD: [SEARCH, pick(food, note="hợp bữa trưa")], SIGHT: [SEARCH, pick(cafe)],
                     SYNTH: [reply(("submit_itinerary", stops(food, cafe)))]})
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None))
    assert events[0] == {"type": "thinking", "text": "Các chuyên gia đang tìm địa điểm…"}
    assert {e["agent"] for e in events if e["type"] == "tool_call"} == {"an-uong", "tham-quan"}
    assert used(events) == [food, cafe]
    brief = rc.calls_for(SYNTH)[0]["messages"][1]["content"]
    assert "Quán Bà Tư" in brief and "hợp bữa trưa" in brief and "Cafe Tùng" in brief
    assert not rc.calls_for(STAY)  # Trip 1 ngày không gọi agent chỗ ở


def test_synthesizer_still_rejects_place_outside_shortlists(conn):
    food, cafe, other = add_place(conn, "Quán", "an-uong"), add_place(conn, "Cafe", "cafe"), add_place(conn, "Lạ", "cafe")
    # "Lạ" có thật và chuyên gia đã thấy khi tìm, nhưng không được chọn vào danh sách ngắn
    rc = RoleClient({FOOD: [SEARCH, pick(food)], SIGHT: [SEARCH, pick(cafe)],
                     SYNTH: [reply(("submit_itinerary", stops(other))), reply(("submit_itinerary", stops(cafe)))]})
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None))
    assert used(events) == [cafe]
    tool = [m["content"] for m in rc.calls_for(SYNTH)[-1]["messages"] if m.get("role") == "tool"]
    assert tool[0].startswith("Lỗi")


def test_agent_error_falls_back_to_single(conn):
    cafe = add_place(conn, "Cafe", "cafe")
    rc = RoleClient({FOOD: [RuntimeError("boom")], SIGHT: [SEARCH, pick(cafe)],
                     SYNTH: [SEARCH, reply(("submit_itinerary", stops(cafe)))]})
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None))
    assert {"type": "thinking", "text": multi.FALLBACK_TEXT} in events
    assert used(events) == [cafe]
    assert "Các chuyên gia đã chọn" not in rc.calls_for(SYNTH)[0]["messages"][1]["content"]


def test_slow_agent_falls_back_after_deadline(conn, monkeypatch):
    monkeypatch.setattr(multi, "AGENT_WAIT_S", 0.3)
    cafe = add_place(conn, "Cafe", "cafe")

    def slow():
        time.sleep(0.8)
        raise RuntimeError("muộn")

    rc = RoleClient({FOOD: [slow], SIGHT: [SEARCH, pick(cafe)],
                     SYNTH: [SEARCH, reply(("submit_itinerary", stops(cafe)))]})
    t0 = time.monotonic()
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None))
    assert time.monotonic() - t0 < 0.8  # không chờ agent chậm
    assert {"type": "thinking", "text": multi.FALLBACK_TEXT} in events and used(events) == [cafe]
    time.sleep(0.7)  # để thread chậm kết thúc trước khi fixture đóng kết nối


def test_remote_without_agent_worker_falls_back(conn, rds, monkeypatch):
    monkeypatch.setattr(multi, "AGENT_WAIT_S", 0.6)
    cafe = add_place(conn, "Cafe", "cafe")
    rc = RoleClient({SYNTH: [SEARCH, reply(("submit_itinerary", stops(cafe)))]})
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None))
    assert {"type": "thinking", "text": multi.FALLBACK_TEXT} in events and used(events) == [cafe]
    assert rds.xlen(multi.AGENT_STREAM) == 2  # việc đã gửi, không ai nhận


def test_remote_redis_down_falls_back_at_once(conn, monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")
    monkeypatch.setattr(kv, "_client", None)
    cafe = add_place(conn, "Cafe", "cafe")
    rc = RoleClient({SYNTH: [SEARCH, reply(("submit_itinerary", stops(cafe)))]})
    t0 = time.monotonic()
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None))
    assert time.monotonic() - t0 < 5 and used(events) == [cafe]
    monkeypatch.setattr(kv, "_client", None)


def test_local_flag_uses_threads_even_with_redis(conn, rds):
    food, cafe = add_place(conn, "Quán", "an-uong"), add_place(conn, "Cafe", "cafe")
    rc = RoleClient({FOOD: [SEARCH, pick(food)], SIGHT: [SEARCH, pick(cafe)],
                     SYNTH: [reply(("submit_itinerary", stops(cafe)))]})
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None, local=True))
    assert used(events) == [cafe] and rds.xlen(multi.AGENT_STREAM) == 0


def test_notes_order_is_fixed_whichever_agent_finishes_first(conn):
    """Brief của agent tổng hợp phải y hệt giữa các lần chạy để cache / replay của llm-gateway trúng."""
    food, cafe = add_place(conn, "Quán", "an-uong"), add_place(conn, "Cafe", "cafe")

    def late():
        time.sleep(0.3)
        return SEARCH

    rc = RoleClient({FOOD: [late, pick(food)], SIGHT: [SEARCH, pick(cafe)],
                     SYNTH: [reply(("submit_itinerary", stops(cafe)))]})
    list(multi.plan(conn, rc, "m", trip(), fake_embed, None))
    brief = rc.calls_for(SYNTH)[0]["messages"][1]["content"]
    assert brief.index("Ăn uống —") < brief.index("Tham quan —")


def test_specialist_llm_calls_are_bounded_by_coordinator_wait(conn):
    """Provider treo một lượt: chuyên gia không được giữ worker / kết nối lâu hơn thời gian điều phối chờ."""
    cafe = add_place(conn, "Cafe", "cafe")
    rc, out = RoleClient({SIGHT: [SEARCH, pick(cafe)]}), []
    multi._work(out.append, rc, "m", trip(), "tham-quan", fake_embed, None, [])
    assert rc.options == {"timeout": multi.AGENT_WAIT_S, "max_retries": 0}
    assert out[-1]["place_ids"] == [cafe]
