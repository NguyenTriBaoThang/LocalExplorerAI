from uuid import uuid4

from app.api.routes import auth
from app.models.entities import User
from app.services.auth_service import hash_password


def test_registration_creates_traveler_session_and_profile(client):
    response = client.post("/api/auth/register", json={
        "email": "new.traveler@example.com",
        "display_name": "New Traveler",
        "password": "long-enough-password",
    })

    assert response.status_code == 201
    assert response.json()["role"] == "traveler"
    assert "httponly" in response.headers["set-cookie"].lower()
    profile = client.get("/api/auth/me")
    assert profile.status_code == 200
    assert profile.json()["email"] == "new.traveler@example.com"


def test_anonymous_session_bootstrap_is_not_an_auth_error(client):
    response = client.get("/api/auth/session")

    assert response.status_code == 200
    assert response.json() == {"user": None}


def test_traveler_cannot_open_admin_routes(client):
    response = client.post("/api/auth/register", json={
        "email": "traveler@example.com",
        "display_name": "Traveler",
        "password": "long-enough-password",
    })
    assert response.status_code == 201

    denied = client.get("/api/admin/dashboard")
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "ROLE_FORBIDDEN"


def test_email_login_and_logout(client, db_session):
    user = User(id=str(uuid4()), email="login@example.com", display_name="Login User",
                password_hash=hash_password("long-enough-password"), role="traveler")
    db_session.add(user)
    db_session.commit()

    response = client.post("/api/auth/login", json={"email": "LOGIN@example.com", "password": "long-enough-password"})
    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/auth/session").json()["user"]["email"] == "login@example.com"
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_google_oauth_status_shows_callback_and_requires_credentials(client, monkeypatch):
    monkeypatch.setattr(auth.settings, "google_client_id", None)
    monkeypatch.setattr(auth.settings, "google_client_secret", None)
    monkeypatch.setattr(auth.settings, "google_redirect_uri", "http://localhost:8000/api/auth/google/callback")

    response = client.get("/api/auth/google/status")

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["redirect_uri"] == "http://localhost:8000/api/auth/google/callback"
    assert "GOOGLE_CLIENT_ID" in response.json()["configuration_message"]


def test_google_oauth_rejects_non_https_production_callback(client, monkeypatch):
    monkeypatch.setattr(auth.settings, "app_env", "production")
    monkeypatch.setattr(auth.settings, "google_client_id", "configured")
    monkeypatch.setattr(auth.settings, "google_client_secret", "configured")
    monkeypatch.setattr(auth.settings, "google_redirect_uri", "http://api.example.com/api/auth/google/callback")

    response = client.get("/api/auth/google/status")

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert "HTTPS" in response.json()["configuration_message"]
