"""Ghim, xem version, lịch sử chat, quay lại bản cũ (spec revision-day-du)."""
import threading
import time

from app import db
from app.trips import save_itinerary
from tests.conftest import TEST_URL
from tests.test_trips_api import (auth, client, events, no_meal_rule, trip_with_itinerary,  # noqa: F401 (fixture)
                                  use_llm)
from tests.fakes import reply
from tests.helpers import add_place


def pin(client, h, tid, pid, pinned=True):
    return client.patch(f"/trips/{tid}/pins", headers=h, json={"place_id": pid, "pinned": pinned})


def test_save_itinerary_waits_for_trip_row_lock(client, conn, monkeypatch):
    _, trip_id, _ = trip_with_itinerary(client, conn, monkeypatch)
    blocker = db._open(TEST_URL)
    blocker.execute("BEGIN")
    blocker.execute("SELECT id FROM trips WHERE id = %s FOR NO KEY UPDATE", (trip_id,))
    started = threading.Event()
    saved = []
    pid = []

    def save():
        with db._open(TEST_URL) as writer:
            pid.append(writer.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"])
            started.set()
            saved.append(save_itinerary(writer, trip_id, {"summary": "writer"}, {}))

    thread = threading.Thread(target=save)
    thread.start()
    try:
        assert started.wait(timeout=2)
        deadline = time.monotonic() + 2
        blocked = False
        while time.monotonic() < deadline:
            row = conn.execute(
                "SELECT wait_event_type = 'Lock' AS blocked FROM pg_stat_activity WHERE pid = %s",
                (pid[0],),
            ).fetchone()
            if row is None or row["blocked"]:
                blocked = row is not None and row["blocked"]
                break
            time.sleep(0.01)
        assert blocked
    finally:
        blocker.commit()
        thread.join(timeout=2)
        blocker.close()
    assert not thread.is_alive() and saved == [2]


def test_pin_overlays_stop_and_lists_versions(client, conn, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    r = pin(client, h, tid, pid)
    assert r.status_code == 200 and r.json() == {"pinned_place_ids": [pid]}
    got = client.get(f"/trips/{tid}", headers=h).json()
    assert got["itinerary"]["days"][0]["stops"][0]["pinned"] is True
    assert got["versions"] == [1] and got["pinned_place_ids"] == [pid]
    assert got["center"] == [108.44, 11.94]
    assert conn.execute("SELECT count(*) AS n FROM itineraries").fetchone()["n"] == 1  # ghim không tạo version


def test_unpin_is_idempotent(client, conn, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    assert pin(client, h, tid, pid, False).json() == {"pinned_place_ids": []}
    pin(client, h, tid, pid)
    pin(client, h, tid, pid)  # ghim 2 lần không nhân đôi
    assert pin(client, h, tid, pid, False).json() == {"pinned_place_ids": []}


def test_pin_place_not_in_latest_is_422(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    other = add_place(conn, name="Không có trong lịch")
    r = pin(client, h, tid, other)
    assert r.status_code == 422 and "đang có trong lịch trình" in r.json()["detail"]


def test_get_old_version_and_missing_version(client, conn, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    other = add_place(conn, name="Cafe rẻ", kind="cafe")
    use_llm(monkeypatch, [reply(("search_places", {"query": "cafe rẻ"})),
                          reply(("edit_itinerary", {"summary": "rẻ hơn", "ops": [
                              {"op": "replace_stop", "day": 1, "stop": 1, "place_id": other}]}))])
    events(client.post("/trips", json={"message": "rẻ hơn", "trip_id": tid}, headers=h))
    v1 = client.get(f"/trips/{tid}?version=1", headers=h).json()
    assert v1["version"] == 1 and v1["versions"] == [1, 2]
    assert v1["itinerary"]["days"][0]["stops"][0]["place_id"] == pid
    assert client.get(f"/trips/{tid}?version=9", headers=h).status_code == 404


def test_get_trip_without_itinerary(client, conn, monkeypatch):
    use_llm(monkeypatch, [reply(("record_trip", {"destination": "da-lat", "days": 1, "budget": 2_000_000}))])
    add_place(conn)
    h = auth(client)
    tid = events(client.post("/trips", json={"message": "Đà Lạt 1 ngày"}, headers=h))[-1]["trip_id"]
    got = client.get(f"/trips/{tid}", headers=h).json()
    assert (got["itinerary"], got["versions"], got["pinned_place_ids"]) == (None, [], [])
    assert client.get("/trips", headers=h).json()[0]["destination_name"] == "da-lat"


def test_pins_other_user_404(client, conn, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    assert pin(client, auth(client, "binh@example.com"), tid, pid).status_code == 404


def test_replan_keeps_pinned_place(client, conn, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    pin(client, h, tid, pid)
    other = add_place(conn, name="Hồ", vec=1)
    use_llm(monkeypatch, [reply(("search_places", {"query": "hồ"})),
                          reply(("submit_itinerary", {"summary": "không ghim", "days": [{"stops": [
                              {"place_id": other, "start_time": "09:00", "duration_min": 60}]}]})),
                          reply(("submit_itinerary", {"summary": "có ghim", "days": [{"stops": [
                              {"place_id": pid, "start_time": "09:00", "duration_min": 60},
                              {"place_id": other, "start_time": "11:00", "duration_min": 60}]}]}))])
    evs = events(client.post(f"/trips/{tid}/replan", headers=h,
                             json={"changes": {"budget": 3_000_000}, "message": "3 triệu"}))
    assert evs[-1]["type"] == "itinerary" and evs[-1]["itinerary"]["summary"] == "có ghim"
    got = client.get(f"/trips/{tid}", headers=h).json()
    assert got["itinerary"]["days"][0]["stops"][0]["pinned"] is True


def history(client, h, tid):
    return [(m["role"], m["text"], m["version"]) for m in client.get(f"/trips/{tid}/messages", headers=h).json()]


def test_messages_record_conversation_in_order(client, conn, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    use_llm(monkeypatch, [reply(("answer", {"text": "0 km"}))])
    events(client.post("/trips", json={"message": "bao xa?", "trip_id": tid}, headers=h))
    other = add_place(conn, name="Cafe rẻ", kind="cafe")
    use_llm(monkeypatch, [reply(("search_places", {"query": "cafe rẻ"})),
                          reply(("edit_itinerary", {"summary": "Đổi quán rẻ", "ops": [
                              {"op": "replace_stop", "day": 1, "stop": 1, "place_id": other}]}))])
    events(client.post("/trips", json={"message": "rẻ hơn", "trip_id": tid}, headers=h))
    assert history(client, h, tid) == [("user", "x", None), ("ai", "ok", 1),
                                       ("user", "bao xa?", None), ("ai", "0 km", None),
                                       ("user", "rẻ hơn", None), ("ai", "Đổi quán rẻ", 2)]


def test_messages_other_user_404(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    assert client.get(f"/trips/{tid}/messages", headers=auth(client, "binh@example.com")).status_code == 404


def two_versions(client, conn, monkeypatch):
    """v1: Cà phê Tùng · v2: Cafe rẻ."""
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    other = add_place(conn, name="Cafe rẻ", kind="cafe")
    use_llm(monkeypatch, [reply(("search_places", {"query": "cafe rẻ"})),
                          reply(("edit_itinerary", {"summary": "rẻ", "ops": [
                              {"op": "replace_stop", "day": 1, "stop": 1, "place_id": other}]}))])
    events(client.post("/trips", json={"message": "rẻ hơn", "trip_id": tid}, headers=h))
    return h, tid, pid, other


def test_restore_creates_new_version_and_keeps_all(client, conn, monkeypatch):
    h, tid, pid, other = two_versions(client, conn, monkeypatch)
    pin(client, h, tid, other)
    r = client.post(f"/trips/{tid}/restore/1", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "itinerary" and body["version"] == 3
    assert body["itinerary"]["days"][0]["stops"][0]["place_id"] == pid
    assert body["pinned_place_ids"] == []  # Place ghim không có trong v1 → tự bỏ ghim
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1, 2, 3]
    last = client.get(f"/trips/{tid}/messages", headers=h).json()[-1]
    assert (last["role"], last["version"]) == ("ai", 3)
    assert "bản 1" in last["text"] and "Cafe rẻ" in last["text"]


def test_restore_missing_version_404_other_user_404(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    assert client.post(f"/trips/{tid}/restore/9", headers=h).status_code == 404
    assert client.post(f"/trips/{tid}/restore/1", headers=auth(client, "binh@example.com")).status_code == 404


def test_restore_with_different_day_count_is_422(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    conn.execute("UPDATE trips SET spec = jsonb_set(spec, '{days}', '2') WHERE id = %s", (tid,))
    r = client.post(f"/trips/{tid}/restore/1", headers=h)
    assert r.status_code == 422 and "1 ngày" in r.json()["detail"]
