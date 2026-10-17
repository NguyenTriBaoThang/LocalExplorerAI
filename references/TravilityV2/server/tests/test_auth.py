import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import CATALOG_DOWN, READ_ONLY, get_conn
from app.main import app
from tests.conftest import TEST_URL


@pytest.fixture
def client(conn):
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def register(client, email="an@example.com", password="matkhau123"):
    return client.post("/auth/register", json={"email": email, "password": password})


def test_register_and_login(client):
    assert register(client).status_code == 201
    r = client.post("/auth/login", json={"email": "AN@example.com", "password": "matkhau123"})
    assert r.status_code == 200 and r.json()["token"]


def test_duplicate_email(client):
    register(client)
    r = register(client, email="An@Example.com")
    assert r.status_code == 409


def test_wrong_password(client):
    register(client)
    assert client.post("/auth/login", json={"email": "an@example.com", "password": "sai-mat-khau"}).status_code == 401


def test_short_password(client):
    assert register(client, password="123").status_code == 422


def test_password_over_72_bytes(client):
    r = register(client, password="đường" * 10)  # 50 ký tự nhưng > 72 byte UTF-8
    assert r.status_code == 422
    assert "72 byte" in r.text


def test_protected_route_needs_token(client):
    assert client.get("/auth/me").status_code == 401
    token = register(client).json()["token"]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/auth/me", headers={"Authorization": "Bearer rac"}).status_code == 401


DEAD = "postgresql://travility:travility@127.0.0.1:1/travility"  # không ai nghe cổng 1
REPLICA = TEST_URL + "?options=-c%20default_transaction_read_only%3Don"  # như hot standby: lệnh ghi lỗi
LOGIN = {"email": "an@example.com", "password": "matkhau123"}


def test_primary_down_login_reads_replica_and_register_is_refused(conn, monkeypatch):
    monkeypatch.setattr(settings, "database_url", TEST_URL)
    api = TestClient(app)  # không override get_conn: đi đường thật
    assert register(api).status_code == 201
    monkeypatch.setattr(settings, "database_url", DEAD)
    monkeypatch.setattr(settings, "catalog_replica_url", REPLICA)
    assert api.post("/auth/login", json=LOGIN).status_code == 200
    r = register(api, email="moi@example.com")
    assert r.status_code == 503 and r.json()["detail"] == READ_ONLY
    monkeypatch.setattr(settings, "catalog_replica_url", DEAD)
    r = api.post("/auth/login", json=LOGIN)
    assert r.status_code == 503 and r.json()["detail"] == CATALOG_DOWN


def test_database_down_in_simple_mode_is_503(monkeypatch):
    monkeypatch.setattr(settings, "database_url", DEAD)
    r = TestClient(app).post("/auth/login", json=LOGIN)
    assert r.status_code == 503 and r.json()["detail"] == CATALOG_DOWN
