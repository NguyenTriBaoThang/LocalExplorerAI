from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app
from scripts.seed_users import PASSWORD, seed


def test_seed_covers_every_shard_and_is_idempotent(conn, shards):
    conn.execute("INSERT INTO users(email, password_hash) VALUES ('x@example.com', 'x')")  # lệch id: không dựa vào id 1, 2
    first = seed(conn)
    assert [e for e, *_ in first] == ["demo1@travility.vn", "demo2@travility.vn"]
    assert {s for *_, s in first} == {0, 1}
    assert seed(conn) == first
    assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 3


def test_seeded_user_can_log_in_in_simple_mode(conn):
    assert len(seed(conn)) == 2
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        r = TestClient(app).post("/auth/login", json={"email": "demo1@travility.vn", "password": PASSWORD})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
