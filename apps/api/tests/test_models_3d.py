from uuid import uuid4

import pytest

from app.api.routes import models_3d
from app.models.entities import User
from app.services.auth_service import hash_password

VALID_PAYLOAD = {
    "latitude": 10.77981,
    "longitude": 106.69905,
    "altitude": 0.5,
    "heading": 32.0,
    "scale": 58.0,
}


@pytest.fixture(autouse=True)
def isolated_calibration_file(tmp_path, monkeypatch):
    target = tmp_path / "calibration.json"
    monkeypatch.setattr(models_3d, "CALIBRATION_FILE", target)
    return target


def _login_as(client, db_session, role: str) -> None:
    email = f"{role}-{uuid4().hex[:6]}@example.com"
    db_session.add(User(id=str(uuid4()), email=email, display_name=role,
                        password_hash=hash_password("long-enough-password"), role=role))
    db_session.commit()
    response = client.post("/api/auth/login", json={"email": email, "password": "long-enough-password"})
    assert response.status_code == 200


def test_get_default_calibration_uses_real_world_height_scale(client):
    response = client.get("/api/models-3d/calibration/nhathoducba")

    assert response.status_code == 200
    body = response.json()
    assert body["file_url"].endswith(".glb")
    assert 10 <= body["scale"] <= 200  # scale = chiều cao thực tế (mét)


def test_unknown_model_returns_404(client):
    assert client.get("/api/models-3d/calibration/khong-ton-tai").status_code == 404


def test_save_requires_login(client):
    response = client.post("/api/models-3d/calibration/nhathoducba", json=VALID_PAYLOAD)
    assert response.status_code == 401


def test_traveler_cannot_save_calibration(client, db_session):
    _login_as(client, db_session, "traveler")
    response = client.post("/api/models-3d/calibration/nhathoducba", json=VALID_PAYLOAD)
    assert response.status_code == 403


def test_admin_saves_and_persists_calibration(client, db_session, isolated_calibration_file):
    _login_as(client, db_session, "admin")

    response = client.post("/api/models-3d/calibration/nhathoducba", json=VALID_PAYLOAD)

    assert response.status_code == 200
    assert isolated_calibration_file.exists()
    saved = client.get("/api/models-3d/calibration/nhathoducba").json()
    assert saved["latitude"] == pytest.approx(10.77981)
    assert saved["heading"] == pytest.approx(32.0)
    assert saved["scale"] == pytest.approx(58.0)
    assert saved["file_url"].endswith(".glb")


@pytest.mark.parametrize("field,value", [
    ("latitude", 95.0),
    ("longitude", 200.0),
    ("scale", 0.0),
    ("scale", 5000.0),
    ("heading", 400.0),
    ("altitude", 999.0),
])
def test_admin_save_rejects_out_of_range_values(client, db_session, field, value):
    _login_as(client, db_session, "admin")
    payload = {**VALID_PAYLOAD, field: value}

    response = client.post("/api/models-3d/calibration/nhathoducba", json=payload)

    assert response.status_code == 422


def test_admin_cannot_create_unknown_model(client, db_session):
    _login_as(client, db_session, "admin")
    response = client.post("/api/models-3d/calibration/evil-model", json=VALID_PAYLOAD)
    assert response.status_code == 404
