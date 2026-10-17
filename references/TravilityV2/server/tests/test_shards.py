import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app import db, forecast, jobs, llm, rules, worker
from app.config import settings
from app.main import app
from tests.conftest import TEST_URL
from tests.helpers import add_place, unit_vec
from tests.test_trips_api import auth, events, happy, use_llm
from tests.test_worker import published, types

DEAD = "postgresql://travility:travility@127.0.0.1:1/travility"
SPEC = {"destination": "da-lat", "days": 1, "budget": 2_000_000}


@pytest.fixture
def api(shards):
    return TestClient(app)  # không override dependency nào: định tuyến thật


def user(api, email):
    h = auth(api, email)
    return h, api.get("/auth/me", headers=h).json()["id"]


def add_trip(uid, spec=SPEC):
    with db.shard_conn(uid) as c:
        return c.execute("INSERT INTO trips(user_id, spec) VALUES (%s, %s) RETURNING id",
                         (uid, Jsonb(spec))).fetchone()["id"]


def count(url, table="trips"):
    with db._open(url) as c:
        return c.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]


def fake_planning(conn, monkeypatch):
    monkeypatch.setattr(rules, "MEALS", ())
    monkeypatch.setattr(llm, "embed", lambda texts: [unit_vec(0) for _ in texts])
    monkeypatch.setattr(forecast, "get_rain_chance", lambda *a, **k: None)
    use_llm(monkeypatch, happy(add_place(conn, kind="cafe")))


def test_shard_of_and_url_parsing(shards, monkeypatch):
    assert [db.shard_of(i) for i in (1, 2, 3, 4)] == [1, 0, 1, 0]
    monkeypatch.setattr(settings, "shard_urls", " a , b ,")
    assert db.shard_urls() == ["a", "b"]
    monkeypatch.setattr(settings, "shard_urls", "")
    assert db.shard_urls() == [] and db.shard_of(7) == 0


def test_group_review_proposals_table_on_each_shard(shards):
    for url in shards:
        with db._open(url) as shard:
            row = shard.execute(
                "SELECT to_regclass('public.group_review_proposals') AS table_name"
            ).fetchone()
            assert row["table_name"] is not None


def test_trips_live_on_the_users_shard(conn, api, shards):
    add_place(conn)
    (ha, a), (hb, b) = user(api, "a@example.com"), user(api, "b@example.com")
    assert db.shard_of(a) != db.shard_of(b)
    add_trip(a), add_trip(b), add_trip(b)
    assert count(shards[db.shard_of(a)]) == 1 and count(shards[db.shard_of(b)]) == 2
    assert count(TEST_URL) == 0
    assert len(api.get("/trips", headers=ha).json()) == 1
    assert len(api.get("/trips", headers=hb).json()) == 2


def test_same_trip_id_on_two_shards_never_crosses(conn, api, shards):
    """id Trip tự tăng theo từng shard nên trùng nhau; shard chọn theo User trước rồi mới tra id (spec §9.1)."""
    add_place(conn)
    (ha, a), (hb, b) = user(api, "a@example.com"), user(api, "b@example.com")
    ta, tb, tb2 = add_trip(a), add_trip(b, {**SPEC, "days": 3}), add_trip(b)
    assert ta == tb == 1
    assert api.get(f"/trips/{ta}", headers=ha).json()["trip"]["days"] == 1
    assert api.get(f"/trips/{tb}", headers=hb).json()["trip"]["days"] == 3
    assert api.get(f"/trips/{tb2}", headers=ha).status_code == 404


def test_dead_shard_only_blocks_its_users(conn, api, shards, monkeypatch):
    add_place(conn)
    (ha, a), (hb, b) = user(api, "a@example.com"), user(api, "b@example.com")
    add_trip(a)
    urls = list(shards)
    urls[db.shard_of(b)] = DEAD
    monkeypatch.setattr(settings, "shard_urls", ",".join(urls))
    r = api.get("/trips", headers=hb)
    assert r.status_code == 503 and r.json()["detail"] == db.SHARD_DOWN
    assert api.post("/trips", json={"message": "Đà Lạt 1 ngày"}, headers=hb).status_code == 503
    assert len(api.get("/trips", headers=ha).json()) == 1
    assert api.post("/auth/login", json={"email": "b@example.com", "password": "matkhau123"}).status_code == 200


def test_planning_writes_to_the_users_shard(conn, api, shards, monkeypatch):
    fake_planning(conn, monkeypatch)
    h, uid = user(api, "a@example.com")
    evs = events(api.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h))
    assert evs[-1]["type"] == "itinerary"
    mine, other = shards[db.shard_of(uid)], shards[1 - db.shard_of(uid)]
    assert count(mine) == 1 and count(mine, "itineraries") == 1 and count(mine, "messages") > 0
    assert count(other) == 0 and count(TEST_URL) == 0
    assert api.get(f"/trips/{evs[-1]['trip_id']}", headers=h).json()["version"] == 1


def test_trip_needs_no_user_row(conn):
    """Chế độ đơn giản cũng bỏ khoá ngoại trips.user_id → users: một schema cho cả hai chế độ (spec §9.1)."""
    conn.execute("INSERT INTO trips(user_id, spec) VALUES (999, '{}')")


def test_dead_shard_does_not_block_startup(conn, shards, monkeypatch):
    with db._open(shards[0]) as c:
        c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    monkeypatch.setattr(settings, "shard_urls", f"{shards[0]},{DEAD}")
    db.init_schemas()
    assert count(shards[0]) == 0


def enqueue(uid):
    return jobs.enqueue("message", uid, {"message": "Đà Lạt 1 ngày 2 triệu", "trip_id": None})


def test_worker_runs_job_on_the_users_shard(conn, shards, rds, monkeypatch):
    fake_planning(conn, monkeypatch)
    worker.ensure_group(rds)
    job = enqueue(3)
    assert worker.step(None, rds, "w1") is True
    assert types(rds, job)[-2:] == ["itinerary", "end"]
    assert count(shards[1]) == 1 and count(shards[0]) == 0 and count(TEST_URL) == 0


def test_dead_shard_fails_its_job_and_worker_moves_on(conn, shards, rds, monkeypatch):
    fake_planning(conn, monkeypatch)
    worker.ensure_group(rds)
    monkeypatch.setattr(settings, "shard_urls", f"{shards[0]},{DEAD}")
    dead, alive = enqueue(3), enqueue(2)
    worker.step(None, rds, "w1")
    worker.step(None, rds, "w1")
    assert published(rds, dead) == [{"type": "error", "message": db.SHARD_DOWN}, "end"]
    assert types(rds, alive)[-2:] == ["itinerary", "end"]
    assert rds.xpending_range("jobs", "planners", "-", "+", 10) == []
