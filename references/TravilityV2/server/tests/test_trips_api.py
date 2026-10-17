import datetime as dt
import json
import threading
import time
from contextlib import nullcontext

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app import forecast, jobs, kv, llm, multi, rules, trips, worker
from app.auth import get_shard
from app.config import settings
from app.db import get_conn
from app.domain import Trip
from app.main import app
from tests.fakes import FakeClient, RoleClient, reply
from tests.helpers import add_place, unit_vec


@pytest.fixture(autouse=True)
def no_meal_rule(monkeypatch):
    """Các test ở đây không xếp bữa ăn; quy tắc 3 bữa được test riêng ở test_rules / test_missing_meal_*."""
    monkeypatch.setattr(rules, "MEALS", ())


@pytest.fixture
def client(conn, monkeypatch):
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_shard] = lambda: conn
    monkeypatch.setattr(trips, "stream_conn", lambda *_: nullcontext(conn))
    monkeypatch.setattr(llm, "embed", lambda texts: [unit_vec(0) for _ in texts])
    monkeypatch.setattr(forecast, "get_rain_chance", lambda *a, **k: None)
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth(client, email="an@example.com"):
    token = client.post("/auth/register", json={"email": email, "password": "matkhau123"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def use_llm(monkeypatch, responses):
    monkeypatch.setattr(llm, "chat_client", lambda: FakeClient(responses))


def ask_first(conn, client, monkeypatch, record=None):
    """POST /trips với câu thiếu Travel Mode → trả (headers, events)."""
    use_llm(monkeypatch, [reply(("record_trip", record or {"destination": "da-lat", "days": 1, "budget": 2_000_000}))])
    h = auth(client)
    return h, events(client.post("/trips", json={"message": "Đà Lạt 1 ngày"}, headers=h))


def happy(pid):
    return [reply(("record_trip", {"destination": "da-lat", "days": 1, "budget": 2_000_000, "travel_mode": "grab"})),
            reply(("search_places", {"query": "cafe"})),
            reply(("submit_itinerary", {"summary": "ok", "days": [{"stops": [
                {"place_id": pid, "start_time": "09:00", "duration_min": 60, "reason": "cafe-chill"}]}]}))]


def test_create_trip_streams_and_persists(client, conn, monkeypatch):
    pid = add_place(conn, name="Cà phê Tùng", kind="cafe")
    use_llm(monkeypatch, happy(pid))
    h = auth(client)
    evs = events(client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h))
    assert [e["type"] for e in evs] == ["thinking", "trip", "tool_call", "itinerary"]
    trip_id = evs[-1]["trip_id"]
    got = client.get(f"/trips/{trip_id}", headers=h).json()
    assert got["version"] == 1
    assert got["itinerary"]["days"][0]["stops"][0]["place_id"] == pid
    assert got["places"][str(pid)]["name"] == "Cà phê Tùng"
    assert [t["id"] for t in client.get("/trips", headers=h).json()] == [trip_id]


def test_other_user_gets_404(client, conn, monkeypatch):
    pid = add_place(conn)
    use_llm(monkeypatch, happy(pid))
    evs = events(client.post("/trips", json={"message": "x"}, headers=auth(client)))
    other = auth(client, "binh@example.com")
    assert client.get(f"/trips/{evs[-1]['trip_id']}", headers=other).status_code == 404
    assert client.get("/trips", headers=other).json() == []


def test_unsupported_destination_is_error_event(client, conn, monkeypatch):
    add_place(conn)
    use_llm(monkeypatch, [reply(("record_trip", {"destination": "unsupported", "days": 3, "budget": 1}))])
    evs = events(client.post("/trips", json={"message": "Phú Quốc"}, headers=auth(client)))
    assert evs[-1]["type"] == "error" and "da-lat" in evs[-1]["message"]
    assert conn.execute("SELECT count(*) AS n FROM trips").fetchone()["n"] == 0


def test_llm_down_is_error_event(client, conn, monkeypatch):
    add_place(conn)
    use_llm(monkeypatch, [openai.APIConnectionError(request=httpx.Request("POST", "http://llm"))])
    evs = events(client.post("/trips", json={"message": "x"}, headers=auth(client)))
    assert evs[-1] == {"type": "error", "message": "Không kết nối được AI, kiểm tra mạng rồi thử lại nhé."}


def test_unexpected_exception_is_error_event(client, conn, monkeypatch):
    add_place(conn)
    use_llm(monkeypatch, [RuntimeError("boom")])
    evs = events(client.post("/trips", json={"message": "x"}, headers=auth(client)))
    assert evs[-1] == {"type": "error", "message": "Có lỗi khi lập lịch trình, bạn thử lại nhé."}


def test_requires_login(client):
    assert client.post("/trips", json={"message": "x"}).status_code == 401


def test_missing_info_ends_with_clarify(client, conn, monkeypatch):
    add_place(conn)
    _, evs = ask_first(conn, client, monkeypatch)
    assert [e["type"] for e in evs] == ["thinking", "trip", "clarify"]
    assert [q["field"] for q in evs[-1]["questions"]] == ["travel_mode"]
    assert evs[-1]["trip_id"] == evs[1]["trip_id"]


def test_plan_applies_answers_and_persists(client, conn, monkeypatch):
    pid = add_place(conn, kind="cafe")
    h, evs = ask_first(conn, client, monkeypatch)
    trip_id = evs[-1]["trip_id"]
    use_llm(monkeypatch, happy(pid)[1:])
    evs = events(client.post(f"/trips/{trip_id}/plan", json={"travel_mode": "o-to-rieng"}, headers=h))
    assert [e["type"] for e in evs] == ["trip", "tool_call", "itinerary"]
    assert evs[0]["trip"]["travel_mode"] == "o-to-rieng"
    assert client.get(f"/trips/{trip_id}", headers=h).json()["trip"]["travel_mode"] == "o-to-rieng"


def test_plan_skip_uses_default_travel_mode(client, conn, monkeypatch):
    pid = add_place(conn)
    h, evs = ask_first(conn, client, monkeypatch)
    use_llm(monkeypatch, happy(pid)[1:])
    evs = events(client.post(f"/trips/{evs[-1]['trip_id']}/plan", json={}, headers=h))
    assert evs[0]["trip"]["travel_mode"] == "xe-may"


def test_plan_twice_is_409(client, conn, monkeypatch):
    pid = add_place(conn)
    use_llm(monkeypatch, happy(pid))
    h = auth(client)
    trip_id = events(client.post("/trips", json={"message": "x"}, headers=h))[-1]["trip_id"]
    assert client.post(f"/trips/{trip_id}/plan", json={}, headers=h).status_code == 409


def test_plan_other_users_trip_is_404(client, conn, monkeypatch):
    add_place(conn)
    _, evs = ask_first(conn, client, monkeypatch)
    other = auth(client, "binh@example.com")
    assert client.post(f"/trips/{evs[-1]['trip_id']}/plan", json={}, headers=other).status_code == 404


def test_plan_bad_times_is_422_in_vietnamese(client, conn, monkeypatch):
    add_place(conn)
    h, evs = ask_first(conn, client, monkeypatch)
    r = client.post(f"/trips/{evs[-1]['trip_id']}/plan",
                    json={"arrival_time": "15:00", "departure_time": "10:00"}, headers=h)
    assert r.status_code == 422 and r.json()["detail"] == "Giờ về phải sau giờ đến"


def test_arrival_hub_starts_day_one(client, conn, monkeypatch):
    pid = add_place(conn)
    conn.execute("""UPDATE destinations SET hubs = '{"may-bay": {"name": "Sân bay", "lat": 11.75, "lon": 108.37}}'""")
    record = {"destination": "da-lat", "days": 1, "budget": 2_000_000, "travel_mode": "grab", "arrival_mode": "may-bay"}
    use_llm(monkeypatch, [reply(("record_trip", record)), *happy(pid)[1:]])
    evs = events(client.post("/trips", json={"message": "x"}, headers=auth(client)))
    assert evs[-1]["itinerary"]["days"][0]["legs"][0]["from_place_id"] is None


def test_hub_missing_for_arrival_mode_falls_back():
    trip = Trip(destination="da-lat", days=1, budget=1, arrival_mode="tau")
    assert trips.hub_for({"hubs": {"may-bay": {"name": "x", "lat": 1, "lon": 1}}}, trip) is None
    assert trips.hub_for({"hubs": {}}, Trip(destination="da-lat", days=1, budget=1)) is None


def follow_up(conn, pid, record):
    return FakeClient([reply(("record_trip", record)), *happy(pid)[1:]])


def test_follow_up_message_continues_same_trip(client, conn, monkeypatch):
    pid = add_place(conn)
    h, evs = ask_first(conn, client, monkeypatch)
    trip_id = evs[-1]["trip_id"]
    fake = follow_up(conn, pid, {"destination": "da-lat", "days": 1, "budget": 2_000_000, "travel_mode": "xe-may",
                                 "preferred_tags": ["gia-re"]})
    monkeypatch.setattr(llm, "chat_client", lambda: fake)
    evs = events(client.post("/trips", json={"message": "bằng xe máy, rẻ thôi", "trip_id": trip_id}, headers=h))
    assert [e["type"] for e in evs] == ["thinking", "trip", "tool_call", "itinerary"]
    assert evs[1]["trip_id"] == trip_id and evs[1]["trip"]["preferred_tags"] == ["gia-re"]
    parse_input = fake.calls[0]["messages"][1]["content"]
    assert "Đà Lạt 1 ngày" in parse_input and "bằng xe máy, rẻ thôi" in parse_input
    assert "bằng xe máy, rẻ thôi" in fake.calls[1]["messages"][1]["content"]  # prompt lập lịch có nguyên văn
    assert conn.execute("SELECT count(*) AS n FROM trips").fetchone()["n"] == 1


def test_follow_up_never_asks_twice(client, conn, monkeypatch):
    pid = add_place(conn)
    h, evs = ask_first(conn, client, monkeypatch)
    fake = follow_up(conn, pid, {"destination": "da-lat", "days": 1, "budget": 2_000_000})  # vẫn thiếu Travel Mode
    monkeypatch.setattr(llm, "chat_client", lambda: fake)
    evs = events(client.post("/trips", json={"message": "sao cũng được", "trip_id": evs[-1]["trip_id"]}, headers=h))
    assert evs[-1]["type"] == "itinerary" and evs[1]["trip"]["travel_mode"] == "xe-may"


def trip_with_itinerary(client, conn, monkeypatch):
    pid = add_place(conn, name="Cà phê Tùng", kind="cafe")
    use_llm(monkeypatch, happy(pid))
    h = auth(client)
    return h, events(client.post("/trips", json={"message": "x"}, headers=h))[-1]["trip_id"], pid


def test_question_after_itinerary_is_answered_without_new_version(client, conn, monkeypatch):
    h, trip_id, _ = trip_with_itinerary(client, conn, monkeypatch)
    fake = FakeClient([reply(("answer", {"text": "Tổng quãng đường 0.0 km."}))])
    monkeypatch.setattr(llm, "chat_client", lambda: fake)
    evs = events(client.post("/trips", json={"message": "tổng quãng đường bao nhiêu", "trip_id": trip_id}, headers=h))
    assert [e["type"] for e in evs] == ["thinking", "answer"]
    assert evs[-1]["text"] == "Tổng quãng đường 0.0 km."
    assert "Cà phê Tùng" in fake.calls[0]["messages"][1]["content"]  # LLM nhận lịch trình hiện tại
    assert client.get(f"/trips/{trip_id}", headers=h).json()["version"] == 1
    row = conn.execute("SELECT user_messages FROM trips WHERE id = %s", (trip_id,)).fetchone()
    assert row["user_messages"] == ["x"]  # câu hỏi không thành yêu cầu cho lần lập sau


def test_edit_changes_only_the_named_stop(client, conn, monkeypatch):
    h, trip_id, pid = trip_with_itinerary(client, conn, monkeypatch)
    other = add_place(conn, name="Cafe rẻ", kind="cafe")
    use_llm(monkeypatch, [reply(("search_places", {"query": "cafe rẻ"})),
                          reply(("edit_itinerary", {"summary": "Đổi sang quán rẻ hơn", "ops": [
                              {"op": "replace_stop", "day": 1, "stop": 1, "place_id": other, "reason": "rẻ hơn"}]}))])
    evs = events(client.post("/trips", json={"message": "đổi quán cafe rẻ hơn", "trip_id": trip_id}, headers=h))
    assert [e["type"] for e in evs] == ["thinking", "tool_call", "itinerary"]
    assert evs[-1]["version"] == 2 and evs[-1]["changed"] == [[0, 0]]
    stop = evs[-1]["itinerary"]["days"][0]["stops"][0]
    assert (stop["place_id"], stop["start_time"]) == (other, "09:00")
    assert evs[-1]["itinerary"]["summary"] == "Đổi sang quán rẻ hơn"
    row = conn.execute("SELECT user_messages FROM trips WHERE id = %s", (trip_id,)).fetchone()
    assert row["user_messages"] == ["x", "đổi quán cafe rẻ hơn"]


def test_bad_edit_twice_is_error_and_no_new_version(client, conn, monkeypatch):
    h, trip_id, _ = trip_with_itinerary(client, conn, monkeypatch)
    bad = reply(("edit_itinerary", {"summary": "", "ops": [{"op": "replace_stop", "day": 0, "stop": 0, "place_id": 999}]}))
    use_llm(monkeypatch, [bad, bad])
    evs = events(client.post("/trips", json={"message": "đổi", "trip_id": trip_id}, headers=h))
    assert evs[-1]["type"] == "error"
    assert client.get(f"/trips/{trip_id}", headers=h).json()["version"] == 1


def test_trip_change_asks_to_confirm_before_replanning(client, conn, monkeypatch):
    h, trip_id, _ = trip_with_itinerary(client, conn, monkeypatch)
    use_llm(monkeypatch, [reply(("change_trip", {"changes": {"budget": 3_000_000}, "text": "Tăng Budget lên 3 triệu?"}))])
    evs = events(client.post("/trips", json={"message": "cho 3 triệu", "trip_id": trip_id}, headers=h))
    assert evs[-1] == {"type": "confirm_replan", "trip_id": trip_id, "text": "Tăng Budget lên 3 triệu?",
                       "changes": {"budget": 3_000_000}, "message": "cho 3 triệu"}
    assert client.get(f"/trips/{trip_id}", headers=h).json()["version"] == 1
    assert client.get(f"/trips/{trip_id}", headers=h).json()["trip"]["budget"] == 2_000_000


def test_replan_applies_changes_and_reuses_old_places(client, conn, monkeypatch):
    h, trip_id, pid = trip_with_itinerary(client, conn, monkeypatch)
    fake = FakeClient([reply(("submit_itinerary", {"summary": "mới", "days": [{"stops": [
        {"place_id": pid, "start_time": "10:00", "duration_min": 60, "reason": "giữ quán cũ"}]}]}))])
    monkeypatch.setattr(llm, "chat_client", lambda: fake)
    evs = events(client.post(f"/trips/{trip_id}/replan", headers=h,
                             json={"changes": {"budget": 3_000_000}, "message": "cho 3 triệu"}))
    assert [e["type"] for e in evs] == ["trip", "itinerary"]  # Place cũ dùng được, không cần search lại
    assert evs[-1]["version"] == 2 and evs[0]["trip"]["budget"] == 3_000_000
    assert "Lịch trình cũ" in fake.calls[0]["messages"][1]["content"]
    row = conn.execute("SELECT user_messages FROM trips WHERE id = %s", (trip_id,)).fetchone()
    assert row["user_messages"] == ["x", "cho 3 triệu"]


def test_replan_bad_changes_422_other_user_404(client, conn, monkeypatch):
    h, trip_id, _ = trip_with_itinerary(client, conn, monkeypatch)
    assert client.post(f"/trips/{trip_id}/replan", headers=h,
                       json={"changes": {"days": 0}, "message": "0 ngày"}).status_code == 422
    other = auth(client, "binh@example.com")
    assert client.post(f"/trips/{trip_id}/replan", headers=other,
                       json={"changes": {"budget": 1}, "message": "x"}).status_code == 404


def test_typing_ok_after_confirm_replans(client, conn, monkeypatch):
    h, trip_id, pid = trip_with_itinerary(client, conn, monkeypatch)
    use_llm(monkeypatch, [reply(("change_trip", {"changes": {"budget": 3_000_000}, "text": "Đổi 3 triệu?"}))])
    events(client.post("/trips", json={"message": "cho 3 triệu", "trip_id": trip_id}, headers=h))
    fake = FakeClient([reply(("confirm_replan", {})),
                       reply(("submit_itinerary", {"summary": "mới", "days": [{"stops": [
                           {"place_id": pid, "start_time": "10:00", "duration_min": 60, "reason": "giữ"}]}]}))])
    monkeypatch.setattr(llm, "chat_client", lambda: fake)
    evs = events(client.post("/trips", json={"message": "oke", "trip_id": trip_id}, headers=h))
    assert "Đổi 3 triệu?" in fake.calls[0]["messages"][1]["content"]  # AI biết đang chờ xác nhận gì
    assert [e["type"] for e in evs] == ["thinking", "trip", "itinerary"]
    assert evs[1]["trip"]["budget"] == 3_000_000 and evs[-1]["version"] == 2
    row = conn.execute("SELECT pending_replan, user_messages FROM trips WHERE id = %s", (trip_id,)).fetchone()
    assert row["pending_replan"] is None and row["user_messages"] == ["x", "cho 3 triệu"]


def test_other_reply_drops_pending_confirm(client, conn, monkeypatch):
    h, trip_id, _ = trip_with_itinerary(client, conn, monkeypatch)
    use_llm(monkeypatch, [reply(("change_trip", {"changes": {"budget": 3_000_000}, "text": "Đổi 3 triệu?"}))])
    events(client.post("/trips", json={"message": "cho 3 triệu", "trip_id": trip_id}, headers=h))
    use_llm(monkeypatch, [reply(("answer", {"text": "Vâng, giữ nguyên."}))])
    events(client.post("/trips", json={"message": "thôi khỏi", "trip_id": trip_id}, headers=h))
    assert conn.execute("SELECT pending_replan FROM trips WHERE id = %s", (trip_id,)).fetchone()["pending_replan"] is None


def test_follow_up_on_other_users_trip_is_404(client, conn, monkeypatch):
    add_place(conn)
    _, evs = ask_first(conn, client, monkeypatch)
    other = auth(client, "binh@example.com")
    r = client.post("/trips", json={"message": "x", "trip_id": evs[-1]["trip_id"]}, headers=other)
    assert r.status_code == 404


def test_demo_today_freezes_parse_and_forecast(client, conn, monkeypatch):
    pid = add_place(conn, name="Cà phê Tùng", kind="cafe")
    fake = FakeClient(happy(pid))
    monkeypatch.setattr(llm, "chat_client", lambda: fake)
    monkeypatch.setattr(settings, "demo_today", dt.date(2026, 12, 1))
    seen = {}
    monkeypatch.setattr(forecast, "get_rain_chance", lambda *a, **k: seen.update(k))
    client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=auth(client))
    assert "Hôm nay là 2026-12-01" in fake.calls[0]["messages"][0]["content"]
    assert seen == {"today": dt.date(2026, 12, 1)}


def test_job_message_runs_from_plain_params(client, conn, monkeypatch):
    pid = add_place(conn, kind="cafe")
    use_llm(monkeypatch, happy(pid))
    auth(client)
    uid = conn.execute("SELECT id FROM users").fetchone()["id"]
    out = trips.guarded(trips.JOBS["message"](conn, uid, message="Đà Lạt 1 ngày 2 triệu", trip_id=None))
    assert [json.loads(s[6:])["type"] for s in out] == ["thinking", "trip", "tool_call", "itinerary"]


def test_job_message_on_missing_trip_is_error_event(client, conn):
    auth(client)
    uid = conn.execute("SELECT id FROM users").fetchone()["id"]
    out = list(trips.JOBS["message"](conn, uid, message="x", trip_id=999))
    assert json.loads(out[0][6:]) == {"type": "error", "message": "Không tìm thấy chuyến đi"}


def test_guarded_turns_exception_into_error_event():
    def boom():
        yield "a"
        raise RuntimeError("x")

    out = list(trips.guarded(boom()))
    assert out[0] == "a"
    assert json.loads(out[1][6:]) == {"type": "error", "message": "Có lỗi khi lập lịch trình, bạn thử lại nhé."}


@pytest.fixture
def planner(conn, rds):
    """Chế độ queue: REDIS_URL trỏ Redis test và một planner chạy trong thread, dùng chung kết nối test."""
    worker.ensure_group(rds)
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            worker.step(conn, rds, "w1")

    t = threading.Thread(target=loop)
    t.start()
    yield
    stop.set()
    t.join()


def test_queue_mode_streams_same_events_and_replays(client, conn, monkeypatch, planner):
    pid = add_place(conn, kind="cafe")
    use_llm(monkeypatch, happy(pid))
    h = auth(client)
    r = client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers={**h, "Origin": "http://app"})
    assert [e["type"] for e in events(r)] == ["thinking", "trip", "tool_call", "itinerary"]
    assert "x-job-id" in r.headers["access-control-expose-headers"].lower()
    trip_id = events(r)[-1]["trip_id"]
    assert client.get(f"/trips/{trip_id}", headers=h).json()["version"] == 1

    job_id = r.headers["x-job-id"]
    again = client.get(f"/jobs/{job_id}/events", headers=h)
    assert again.text == r.text and again.headers["content-type"].startswith("text/event-stream")
    assert client.get(f"/jobs/{job_id}/events", headers=auth(client, "binh@example.com")).status_code == 404
    assert client.get("/jobs/khong-co/events", headers=h).status_code == 404
    assert client.get(f"/jobs/{job_id}/events").status_code == 401


def test_queue_mode_clarify_then_plan(client, conn, monkeypatch, planner):
    pid = add_place(conn, kind="cafe")
    h, evs = ask_first(conn, client, monkeypatch)
    assert evs[-1]["type"] == "clarify"
    use_llm(monkeypatch, happy(pid)[1:])
    r = client.post(f"/trips/{evs[-1]['trip_id']}/plan", json={"travel_mode": "grab"}, headers=h)
    assert events(r)[-1]["type"] == "itinerary" and r.headers["x-job-id"]


def test_queue_mode_over_limit_is_429_and_nothing_is_queued(client, conn, rds):
    h = auth(client)
    uid = conn.execute("SELECT id FROM users").fetchone()["id"]
    this_minute = int(time.time() // 60)
    for m in (this_minute, this_minute + 1):  # cả phút sau, phòng khi test chạy ngang ranh giới phút
        rds.set(f"rl:{uid}:{m}", 5)
    r = client.post("/trips", json={"message": "x"}, headers=h)
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1 and "quá nhanh" in r.json()["detail"]
    assert rds.xlen("jobs") == 0


def test_queue_mode_bad_request_does_not_use_a_slot(client, conn, rds):
    r = client.post("/trips", json={"message": "x", "trip_id": 999}, headers=auth(client))
    assert r.status_code == 404 and rds.keys("rl:*") == []


def test_queue_mode_redis_down_is_503(client, monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")
    monkeypatch.setattr(kv, "_client", None)
    r = client.post("/trips", json={"message": "x"}, headers=auth(client))
    assert r.status_code == 503 and "tạm không dùng được" in r.json()["detail"]


def test_simple_mode_has_no_job_id_and_no_job_endpoint_data(client, conn, monkeypatch):
    pid = add_place(conn, kind="cafe")
    use_llm(monkeypatch, happy(pid))
    h = auth(client)
    r = client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h)
    assert events(r)[-1]["type"] == "itinerary" and "x-job-id" not in r.headers
    assert client.get("/jobs/bat-ky/events", headers=h).status_code == 404


def test_queue_mode_replan_carries_changes_through_the_queue(client, conn, monkeypatch, planner):
    pid = add_place(conn, kind="cafe")
    use_llm(monkeypatch, happy(pid))
    h = auth(client)
    trip_id = events(client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h))[-1]["trip_id"]
    use_llm(monkeypatch, happy(pid)[1:])
    r = client.post(f"/trips/{trip_id}/replan", json={"changes": {"budget": 3_000_000}, "message": "tăng lên 3 triệu"},
                    headers=h)
    assert events(r)[-1]["type"] == "itinerary" and events(r)[-1]["version"] == 2
    assert client.get(f"/trips/{trip_id}", headers=h).json()["trip"]["budget"] == 3_000_000


def multi_llm(food, cafe):
    search = reply(("search_places", {"query": "x"}))
    return RoleClient({
        "record_trip": [reply(("record_trip", {"destination": "da-lat", "days": 1, "budget": 2_000_000,
                                               "travel_mode": "grab"}))],
        "chuyên gia Ăn uống": [search, reply(("submit_shortlist", {"place_ids": [food], "note": "n"}))],
        "chuyên gia Tham quan": [search, reply(("submit_shortlist", {"place_ids": [cafe], "note": "n"}))],
        "trợ lý lập lịch trình": [reply(("submit_itinerary", {"summary": "ok", "days": [{"stops": [
            {"place_id": cafe, "start_time": "09:00", "duration_min": 60, "reason": "cafe"}]}]}))]})


def test_multi_mode_plans_with_specialists_in_threads(client, conn, monkeypatch):
    monkeypatch.setattr(settings, "planner_mode", "multi")
    monkeypatch.setattr(multi, "agent_conn", lambda: nullcontext(conn))
    rc = multi_llm(add_place(conn, "Quán", "an-uong"), add_place(conn, "Cafe", "cafe"))
    monkeypatch.setattr(llm, "chat_client", lambda: rc)
    h = auth(client)
    evs = events(client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h))
    assert {e.get("agent") for e in evs if e["type"] == "tool_call"} == {"an-uong", "tham-quan"}
    assert evs[-1]["type"] == "itinerary" and evs[-1]["version"] == 1
    assert client.get(f"/trips/{evs[-1]['trip_id']}", headers=h).json()["version"] == 1


@pytest.fixture
def agents(conn, rds, monkeypatch):
    """Một planner-agent chạy trong thread, dùng chung kết nối test."""
    monkeypatch.setattr(multi, "agent_conn", lambda: nullcontext(conn))
    worker.ensure_group(rds, multi.AGENT_STREAM, multi.AGENT_GROUP)
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            worker.agent_step(rds, "a1")

    t = threading.Thread(target=loop)
    t.start()
    yield
    stop.set()
    t.join()


def test_queue_mode_multi_runs_specialists_on_agent_worker(client, conn, rds, monkeypatch, planner, agents):
    monkeypatch.setattr(settings, "planner_mode", "multi")
    rc = multi_llm(add_place(conn, "Quán", "an-uong"), add_place(conn, "Cafe", "cafe"))
    monkeypatch.setattr(llm, "chat_client", lambda: rc)
    evs = events(client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=auth(client)))
    assert {e.get("agent") for e in evs if e["type"] == "tool_call"} == {"an-uong", "tham-quan"}
    assert evs[-1]["type"] == "itinerary"
    assert rds.xpending(multi.AGENT_STREAM, multi.AGENT_GROUP)["pending"] == 0
