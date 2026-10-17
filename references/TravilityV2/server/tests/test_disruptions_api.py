import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app.agent import itinerary_event
from app.auth import get_shard
from app.db import get_conn
from app.domain import Draft, Trip
from app.main import app
from app.places import get_places
from app.rules import build_itinerary
from app.trips import save_itinerary
from tests.helpers import add_place

TRIP = Trip(destination="da-lat", days=1, budget=5_000_000, travel_mode="grab", preferred_tags=["cafe-chill"])


@pytest.fixture
def client(conn):
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_shard] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth(client, email="an@example.com"):
    token = client.post("/auth/register", json={"email": email, "password": "matkhau123"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def seed(conn, client, pinned=False):
    """Trip 1 ngày: Cafe A 09:00 → Bảo tàng 11:00. Ứng viên: Cafe B (cùng embedding), Cafe C (xa hơn)."""
    h = auth(client)
    uid = conn.execute("SELECT id FROM users").fetchone()["id"]
    cafe = add_place(conn, name="Cafe A", kind="cafe", tags=["cafe-chill"], vec=1)
    museum = add_place(conn, name="Bảo tàng", kind="tham-quan", tags=["lich-su"], vec=2)
    add_place(conn, name="Cafe B", kind="cafe", tags=["cafe-chill"], vec=1)
    add_place(conn, name="Cafe C", kind="cafe", tags=["check-in"], vec=3)
    tid = conn.execute("INSERT INTO trips(user_id, spec) VALUES (%s, %s) RETURNING id",
                       (uid, Jsonb(TRIP.model_dump(mode="json")))).fetchone()["id"]
    places = get_places(conn, [cafe, museum])
    draft = Draft.model_validate({"summary": "", "days": [{"stops": [
        {"place_id": cafe, "start_time": "09:00", "duration_min": 60},
        {"place_id": museum, "start_time": "11:00", "duration_min": 60}]}]})
    ev = itinerary_event(build_itinerary(TRIP, draft, places), places)
    save_itinerary(conn, tid, ev["itinerary"], ev["places"])
    if pinned:
        conn.execute("UPDATE trips SET pinned_place_ids = %s WHERE id = %s", ([cafe], tid))
    return h, tid


def disrupt(client, h, tid, version=1, stop=0, kind="closed"):
    return client.post(f"/trips/{tid}/disruptions", headers=h,
                       json={"version": version, "kind": kind, "day_index": 0, "stop_index": stop})


def first_stop_name(opt):
    return opt["places"][str(opt["itinerary"]["days"][0]["stops"][0]["place_id"])]["name"]


def test_closed_returns_options_and_logs(client, conn):
    h, tid = seed(conn, client)
    r = disrupt(client, h, tid)
    assert r.status_code == 200
    body = r.json()
    assert [first_stop_name(o) for o in body["options"]] == ["Cafe B", "Cafe C"]
    assert body["options"][0]["reason_codes"][0] == "INTENT_MATCH"
    row = conn.execute("SELECT base_version, disruption, chosen_index FROM proposals WHERE id = %s",
                       (body["proposal_id"],)).fetchone()
    assert (row["base_version"], row["disruption"]["kind"], row["chosen_index"]) == (1, "closed", None)


def test_apply_is_idempotent(client, conn):
    h, tid = seed(conn, client)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    first = client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0}).json()
    again = client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0}).json()
    assert first["version"] == again["version"] == 2
    assert first["type"] == "itinerary" and first_stop_name(first) == "Cafe B"
    assert conn.execute("SELECT COUNT(*) AS n FROM itineraries WHERE trip_id = %s", (tid,)).fetchone()["n"] == 2
    assert conn.execute("SELECT chosen_index FROM proposals WHERE id = %s", (pid,)).fetchone()["chosen_index"] == 0


def test_apply_other_option_after_applied_409(client, conn):
    h, tid = seed(conn, client)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0})
    assert client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 1}).status_code == 409


def test_stale_version_409(client, conn):
    h, tid = seed(conn, client)
    old = disrupt(client, h, tid).json()["proposal_id"]
    pid = disrupt(client, h, tid).json()["proposal_id"]
    client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0})  # → version 2
    assert disrupt(client, h, tid, version=1).status_code == 409
    assert client.post(f"/trips/{tid}/proposals/{old}/apply", headers=h, json={"option": 0}).status_code == 409


def test_other_user_404(client, conn):
    h, tid = seed(conn, client)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    other = auth(client, "binh@example.com")
    assert disrupt(client, other, tid).status_code == 404
    assert client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=other, json={"option": 0}).status_code == 404


def test_pinned_or_bad_stop_422(client, conn):
    h, tid = seed(conn, client, pinned=True)
    assert disrupt(client, h, tid).status_code == 422
    assert disrupt(client, h, tid, stop=9).status_code == 422


def test_no_feasible_when_no_same_kind_place(client, conn):
    h, tid = seed(conn, client)
    body = disrupt(client, h, tid, stop=1).json()  # Bảo tàng: không có tham-quan nào khác
    assert body["no_feasible"] == ["NO_CANDIDATE"]
    assert "options" not in body


def test_concurrent_apply_of_two_proposals_second_gets_409(client, conn, monkeypatch):
    import threading
    import time

    from fastapi import HTTPException

    from app import db, proposals
    from app.proposals import ApplyIn, apply_proposal
    from tests.conftest import TEST_URL
    from app.db import connect

    h, tid = seed(conn, client)
    p1 = disrupt(client, h, tid).json()["proposal_id"]
    p2 = disrupt(client, h, tid, kind="disliked").json()["proposal_id"]
    uid = conn.execute("SELECT user_id FROM trips WHERE id = %s", (tid,)).fetchone()["user_id"]
    gate = threading.Barrier(2, timeout=5)
    real = proposals._trip

    def trip_then_wait(c, trip_id, user_id):  # cả hai bắt đầu trước khi transaction khoá Trip
        trip = real(c, trip_id, user_id)
        gate.wait()
        return trip

    monkeypatch.setattr(proposals, "_trip", trip_then_wait)
    blocker = db._open(TEST_URL)
    blocker.execute("BEGIN")
    blocker.execute("SELECT id FROM trips WHERE id = %s FOR NO KEY UPDATE", (tid,))
    results = {}
    pids = []

    def run(pid):
        c = connect(TEST_URL)
        try:
            pids.append(c.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"])
            results[pid] = apply_proposal(tid, pid, ApplyIn(option=0), uid, c)["version"]
        except HTTPException as e:
            results[pid] = e.status_code
        except Exception as e:  # noqa: BLE001 — ghi lại lỗi 500 để assert
            results[pid] = type(e).__name__
        finally:
            c.close()

    ts = [threading.Thread(target=run, args=(p,)) for p in (p1, p2)]
    [t.start() for t in ts]
    try:
        deadline = time.monotonic() + 2
        blocked = False
        while time.monotonic() < deadline:
            if len(pids) == 2:
                rows = [conn.execute(
                    "SELECT wait_event_type = 'Lock' AS blocked FROM pg_stat_activity WHERE pid = %s", (pid,)
                ).fetchone() for pid in pids]
                if all(row is not None and row["blocked"] for row in rows):
                    blocked = True
                    break
            time.sleep(0.01)
        assert len(pids) == 2
        assert blocked
    finally:
        blocker.commit()
        [t.join(timeout=2) for t in ts]
        blocker.close()
    assert sorted(results.values(), key=str) == sorted([2, 409], key=str)


def test_apply_logs_message(client, conn):
    h, tid = seed(conn, client)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0})
    client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0})  # idempotent: không ghi lần 2
    rows = conn.execute("SELECT role, text, version FROM messages WHERE trip_id = %s", (tid,)).fetchall()
    assert [(r["role"], r["version"]) for r in rows] == [("ai", 2)]
    assert "bản 2" in rows[0]["text"]


def test_apply_old_proposal_after_restore_is_409(client, conn):
    h, tid = seed(conn, client)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    assert client.post(f"/trips/{tid}/restore/1", headers=h).json()["version"] == 2
    r = client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0})
    assert r.status_code == 409


def test_apply_after_pinning_the_replaced_stop_is_409(client, conn):
    h, tid = seed(conn, client)
    pid = disrupt(client, h, tid).json()["proposal_id"]  # Proposal thay Cafe A
    cafe = conn.execute("SELECT id FROM places WHERE name = 'Cafe A'").fetchone()["id"]
    assert client.patch(f"/trips/{tid}/pins", headers=h, json={"place_id": cafe, "pinned": True}).status_code == 200
    r = client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0})
    assert r.status_code == 409 and "ghim" in r.json()["detail"]
    assert conn.execute("SELECT count(*) AS n FROM itineraries WHERE trip_id = %s", (tid,)).fetchone()["n"] == 1


def test_options_carry_title_and_added(client, conn):
    h, tid = seed(conn, client)
    o = disrupt(client, h, tid).json()["options"][0]
    assert o["title"] == "Cafe B"
    assert [o["places"][str(i)]["name"] for i in o["added"]] == ["Cafe B"]


def post(client, h, tid, **body):
    return client.post(f"/trips/{tid}/disruptions", headers=h, json={"version": 1, "day_index": 0, **body})


def test_rain_round_trip_creates_version(client, conn):
    h, tid = seed(conn, client)
    conn.execute("UPDATE places SET outdoor = true WHERE name = 'Bảo tàng'")
    body = post(client, h, tid, kind="rain").json()
    assert [o["title"] for o in body["options"]] == ["Bỏ Bảo tàng"]  # không có tham-quan trong nhà nào khác
    r = client.post(f"/trips/{tid}/proposals/{body['proposal_id']}/apply", headers=h, json={"option": 0})
    assert r.status_code == 200
    assert r.json()["version"] == 2
    assert [s["place_id"] for s in r.json()["itinerary"]["days"][0]["stops"]] == \
        [body["options"][0]["itinerary"]["days"][0]["stops"][0]["place_id"]]


def test_late_shift_only(client, conn):
    h, tid = seed(conn, client)
    body = post(client, h, tid, kind="late", stop_index=0, minutes=30).json()
    o = body["options"][0]
    assert o["reason_codes"] == ["LATE_SHIFT"]
    assert [s["start_time"] for s in o["itinerary"]["days"][0]["stops"]] == ["09:30", "11:30"]


def test_bad_rain_or_late_shape_422(client, conn):
    h, tid = seed(conn, client)
    assert post(client, h, tid, kind="rain", stop_index=0).status_code == 422
    assert post(client, h, tid, kind="late", stop_index=0).status_code == 422
    assert post(client, h, tid, kind="late", stop_index=0, minutes=300).status_code == 422
    assert post(client, h, tid, kind="rain", day_index=5).status_code == 422
