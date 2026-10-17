from fastapi.testclient import TestClient

from app.main import app


def test_health():
    assert TestClient(app).get("/health").json() == {"ok": True}


def test_schema_creates_tables(conn):
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    ).fetchall()
    assert {r["table_name"] for r in rows} >= {"users", "destinations", "places", "trips", "itineraries"}
