"""Phase 6: login throttling, response headers, deprecated provider key switch."""

import pytest

from app.auth import hash_password
from app.core.config import settings
from tests.helpers import make_user

PASSWORD = "long-enough-password"


def _login(client, email, password="wrong-password-123", ip="10.0.0.1"):
    return client.post("/api/auth/login", json={"email": email, "password": password}, headers={"x-forwarded-for": ip})


@pytest.fixture(autouse=True)
def tight_limits(monkeypatch):
    monkeypatch.setattr(settings, "auth_login_max_failures_per_account_ip", 3)
    monkeypatch.setattr(settings, "auth_login_max_failures_per_account", 5)
    monkeypatch.setattr(settings, "auth_login_max_failures_per_ip", 6)
    # The test client's peer is not an IP address, so forwarded headers are never trusted; read the header directly.
    from app.api.routes import auth as auth_routes
    monkeypatch.setattr(auth_routes, "_ip", lambda request: request.headers.get("x-forwarded-for"))


def test_wrong_passwords_are_throttled_then_429_with_retry_after(client, db_session):
    user = make_user(db_session, "traveler")
    for _ in range(3):
        assert _login(client, user.email).status_code == 401
    blocked = _login(client, user.email)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "LOGIN_THROTTLED"
    assert blocked.headers["Retry-After"] == str(settings.auth_login_window_seconds)


def test_correct_password_is_refused_while_throttled(client, db_session):
    user = make_user(db_session, "traveler", password_hash=hash_password(PASSWORD))
    for _ in range(3):
        _login(client, user.email)
    assert _login(client, user.email, PASSWORD).status_code == 429


def test_unknown_email_is_throttled_identically(client):
    codes = [_login(client, "ghost@example.com").status_code for _ in range(4)]
    assert codes == [401, 401, 401, 429]


def test_other_ip_not_blocked_by_account_ip_limit_but_by_account_limit(client, db_session):
    user = make_user(db_session, "traveler")
    for _ in range(3):
        _login(client, user.email, ip="10.0.0.1")
    assert _login(client, user.email, ip="10.0.0.2").status_code == 401  # fresh pair
    _login(client, user.email, ip="10.0.0.3")
    _login(client, user.email, ip="10.0.0.4")  # 5 failures for the account overall
    assert _login(client, user.email, ip="10.0.0.5").status_code == 429


def test_one_ip_spraying_many_emails_is_throttled(client):
    codes = [_login(client, f"u{i}@example.com").status_code for i in range(7)]
    assert codes[:6] == [401] * 6 and codes[6] == 429


def test_security_headers_and_no_store_on_auth(client):
    r = client.get("/api/auth/me")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert r.headers["Cache-Control"] == "no-store"


def test_hsts_only_in_production_over_https(client, monkeypatch):
    assert "Strict-Transport-Security" not in client.get("/api/health", headers={"x-forwarded-proto": "https"}).headers
    monkeypatch.setattr(settings, "app_env", "production")
    assert "Strict-Transport-Security" in client.get("/api/health", headers={"x-forwarded-proto": "https"}).headers
    assert "Strict-Transport-Security" not in client.get("/api/health").headers


def test_provider_key_switch(monkeypatch):
    from fastapi import HTTPException
    from app.api.routes import ai
    monkeypatch.setattr(settings, "allow_provider_access_key", False)
    class P:  # minimal stand-in
        id = "p"; is_active = True; portal_access_key = "k"
    class DB:
        def get(self, *_): return P()
    with pytest.raises(HTTPException) as e:
        ai._provider_auth(DB(), "p", "k", None)
    assert e.value.detail["code"] == "PROVIDER_KEY_DISABLED"
