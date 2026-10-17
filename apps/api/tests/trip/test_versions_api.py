"""Ghim, xem version, lịch sử chat, quay lại bản cũ (spec revision-day-du)."""
from tests.helpers import bearer_for, make_user
from tests.trip.conftest import reply
from tests.trip.test_trips_api import (auth, events_of, no_meal_rule, offline,  # noqa: F401 (autouse fixtures)
                                       trip_with_itinerary, use_llm)


def pin(client, h, tid, pid, pinned=True):
    return client.patch(f"/api/trips/{tid}/pins", headers=h, json={"place_id": pid, "pinned": pinned})


def edit_to(client, db, monkeypatch, h, tid, place_id, summary="rẻ", message="rẻ hơn"):
    use_llm(monkeypatch, [reply(("search_places", {"query": "cafe rẻ"})),
                          reply(("edit_itinerary", {"summary": summary, "ops": [
                              {"op": "replace_stop", "day": 1, "stop": 1, "place_id": place_id}]}))])
    events_of(client, "/api/trips", {"message": message, "trip_id": tid}, h)


def test_pin_overlays_stop_without_new_version(client, db_session, trip_places, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    r = pin(client, h, tid, pid)
    assert r.status_code == 200 and r.json() == {"pinned_place_ids": [pid]}
    got = client.get(f"/api/trips/{tid}", headers=h).json()
    assert got["itinerary"]["days"][0]["stops"][0]["pinned"] is True
    assert got["versions"] == [1] and got["pinned_place_ids"] == [pid]


def test_unpin_is_idempotent_and_pin_twice_does_not_duplicate(client, db_session, trip_places, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    assert pin(client, h, tid, pid, False).json() == {"pinned_place_ids": []}
    pin(client, h, tid, pid)
    assert pin(client, h, tid, pid).json() == {"pinned_place_ids": [pid]}
    assert pin(client, h, tid, pid, False).json() == {"pinned_place_ids": []}


def test_pin_place_not_in_latest_is_422(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    r = pin(client, h, tid, trip_places["cf-2"].id)
    assert r.status_code == 422 and "đang có trong lịch trình" in r.json()["error"]["message"]


def test_pins_other_user_404(client, db_session, trip_places, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    assert pin(client, auth(db_session), tid, pid).status_code == 404


def test_replan_keeps_pinned_place(client, db_session, trip_places, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    pin(client, h, tid, pid)
    other = trip_places["tq-dinh"].id
    use_llm(monkeypatch, [reply(("search_places", {"query": "dinh"})),
                          reply(("submit_itinerary", {"summary": "không ghim", "days": [{"stops": [
                              {"place_id": other, "start_time": "09:00", "duration_min": 60}]}]})),
                          reply(("submit_itinerary", {"summary": "có ghim", "days": [{"stops": [
                              {"place_id": pid, "start_time": "09:00", "duration_min": 60},
                              {"place_id": other, "start_time": "11:00", "duration_min": 60}]}]}))])
    evs = events_of(client, f"/api/trips/{tid}/replan", {"changes": {"budget": 3_000_000}, "message": "3 triệu"}, h)
    assert evs[-1]["type"] == "itinerary" and evs[-1]["itinerary"]["summary"] == "có ghim"
    assert client.get(f"/api/trips/{tid}", headers=h).json()["itinerary"]["days"][0]["stops"][0]["pinned"] is True


def history(client, h, tid):
    return [(m["role"], m["text"], m["version"]) for m in client.get(f"/api/trips/{tid}/messages", headers=h).json()]


def test_messages_record_conversation_in_order(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    use_llm(monkeypatch, [reply(("answer", {"text": "0 km"}))])
    events_of(client, "/api/trips", {"message": "bao xa?", "trip_id": tid}, h)
    edit_to(client, db_session, monkeypatch, h, tid, trip_places["cf-2"].id, "Đổi quán rẻ")
    assert history(client, h, tid) == [("user", "x", None), ("ai", "ok", 1),
                                       ("user", "bao xa?", None), ("ai", "0 km", None),
                                       ("user", "rẻ hơn", None), ("ai", "Đổi quán rẻ", 2)]


def test_messages_other_user_404(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    assert client.get(f"/api/trips/{tid}/messages", headers=auth(db_session)).status_code == 404


def two_versions(client, db, monkeypatch, trip_places):
    """v1: Cà Phê Chung Cư · v2: The Workshop."""
    h, tid, pid = trip_with_itinerary(client, db, monkeypatch, trip_places)
    other = trip_places["cf-2"].id
    edit_to(client, db, monkeypatch, h, tid, other)
    return h, tid, pid, other


def test_get_old_version(client, db_session, trip_places, monkeypatch):
    h, tid, pid, _ = two_versions(client, db_session, monkeypatch, trip_places)
    v1 = client.get(f"/api/trips/{tid}?version=1", headers=h).json()
    assert v1["version"] == 1 and v1["versions"] == [1, 2]
    assert v1["itinerary"]["days"][0]["stops"][0]["place_id"] == pid


def test_restore_creates_new_version_and_keeps_all(client, db_session, trip_places, monkeypatch):
    h, tid, pid, other = two_versions(client, db_session, monkeypatch, trip_places)
    pin(client, h, tid, other)
    r = client.post(f"/api/trips/{tid}/restore/1", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "itinerary" and body["version"] == 3
    assert body["itinerary"]["days"][0]["stops"][0]["place_id"] == pid
    assert body["pinned_place_ids"] == []  # Place ghim không có trong v1 → tự bỏ ghim
    assert client.get(f"/api/trips/{tid}", headers=h).json()["versions"] == [1, 2, 3]
    assert client.get(f"/api/trips/{tid}", headers=h).json()["pinned_place_ids"] == []
    last = client.get(f"/api/trips/{tid}/messages", headers=h).json()[-1]
    assert (last["role"], last["version"]) == ("ai", 3)
    assert "bản 1" in last["text"] and "The Workshop" in last["text"]


def test_restore_missing_version_404_other_user_404(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    assert client.post(f"/api/trips/{tid}/restore/9", headers=h).status_code == 404
    assert client.post(f"/api/trips/{tid}/restore/1", headers=auth(db_session)).status_code == 404


def test_restore_with_different_day_count_is_422(client, db_session, trip_places, monkeypatch):
    from app.models.trip_entities import Trip as TripRow
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    row = db_session.get(TripRow, tid)
    row.spec = {**row.spec, "days": 2}
    db_session.commit()
    r = client.post(f"/api/trips/{tid}/restore/1", headers=h)
    assert r.status_code == 422 and "1 ngày" in r.json()["error"]["message"]
