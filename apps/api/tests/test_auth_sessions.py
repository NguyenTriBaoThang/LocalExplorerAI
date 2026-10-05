"""Phase 2: cookies, server-side sessions, automatic refresh, reuse detection and immediate revocation."""

import re
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.routes import auth as auth_routes
from app.auth import hash_password
from app.core.config import settings
from app.models.auth_entities import AuthEvent, AuthSession
from app.models.entities import User
from app.services.auth_runtime import reset_auth_runtime, token_service
from app.services.auth_service import hash_password as legacy_hash_password
from tests.helpers import sign_in

PASSWORD = "long-enough-password"


def make_user(db, role="traveler", email=None, password=PASSWORD, legacy=False, **kw):
    user = User(id=str(uuid4()), email=email or f"{role}-{uuid4().hex[:6]}@example.test", display_name=role.title(),
                password_hash=(legacy_hash_password if legacy else hash_password)(password), role=role, **kw)
    db.add(user)
    db.commit()
    return user


def login(client, user, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": user.email, "password": password})


def set_cookies(response):
    return {m.group(1): m.group(0) for h in response.headers.get_list("set-cookie") if (m := re.match(r"([^=]+)=", h))}


def cookie_value(response, name):
    for header in response.headers.get_list("set-cookie"):
        if header.startswith(name + "="):
            return header.split(";", 1)[0].split("=", 1)[1]
    return None


def max_age(response, name):
    header = next(h for h in response.headers.get_list("set-cookie") if h.startswith(name + "="))
    return int(re.search(r"Max-Age=(\d+)", header).group(1))


@pytest.fixture
def fresh_runtime():
    reset_auth_runtime()
    yield
    reset_auth_runtime()


def test_login_sets_httponly_access_and_scoped_refresh_cookies(client, db_session):
    response = login(client, make_user(db_session))
    assert response.status_code == 200
    headers = {h.split("=", 1)[0]: h for h in response.headers.get_list("set-cookie")}
    assert set(headers) == {"le_at", "le_rt"}
    assert "HttpOnly" in headers["le_at"] and "samesite=lax" in headers["le_at"].lower() and "Path=/;" in headers["le_at"]
    assert "HttpOnly" in headers["le_rt"] and "Path=/api" in headers["le_rt"]
    assert 800 <= max_age(response, "le_at") <= 900
    assert client.get("/api/auth/me").status_code == 200


def test_refresh_lifetime_depends_on_role(client, db_session):
    traveler = login(client, make_user(db_session))
    admin = login(client, make_user(db_session, role="admin"))
    assert 6 * 86400 < max_age(traveler, "le_rt") <= 7 * 86400
    assert 86400 - 60 < max_age(admin, "le_rt") <= 86400


def test_login_failure_is_uniform_and_recorded(client, db_session):
    user = make_user(db_session)
    wrong_password = login(client, user, "not-the-password")
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.test", "password": PASSWORD})
    assert wrong_password.status_code == unknown.status_code == 401
    assert wrong_password.json()["error"]["code"] == unknown.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert wrong_password.json()["error"]["message"] == unknown.json()["error"]["message"]
    failures = db_session.scalars(select(AuthEvent).where(AuthEvent.event_type == "login", AuthEvent.outcome == "failure")).all()
    assert len(failures) == 2
    assert not [h for h in wrong_password.headers.get_list("set-cookie")]


def test_legacy_password_hash_is_upgraded_to_argon2id_on_login(client, db_session):
    user = make_user(db_session, legacy=True)
    assert user.password_hash.startswith("scrypt$")
    assert login(client, user).status_code == 200
    db_session.refresh(user)
    assert user.password_hash.startswith("$argon2id$")
    assert login(client, user).status_code == 200  # still valid after the upgrade


def test_expired_access_token_is_refreshed_transparently(client, db_session):
    user = make_user(db_session)
    first = login(client, user)
    old_refresh = cookie_value(first, "le_rt")
    expired, _ = token_service().issue_access(user_id=user.id, session_id="s", role=user.role, provider_id=None, token_version=0, ttl_seconds=-300)
    client.cookies.set("le_at", expired)

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert cookie_value(me, "le_at") and cookie_value(me, "le_rt") not in (None, old_refresh)
    rows = db_session.scalars(select(AuthSession).where(AuthSession.user_id == user.id).order_by(AuthSession.issued_at)).all()
    assert len(rows) == 2 and rows[0].rotated_at is not None and rows[0].replaced_by == rows[1].id
    assert rows[0].family_id == rows[1].family_id


def test_access_token_close_to_expiry_is_renewed_proactively(client, db_session):
    user = make_user(db_session)
    login(client, user)
    short, _ = token_service().issue_access(user_id=user.id, session_id="s", role=user.role, provider_id=None, token_version=0, ttl_seconds=60)
    client.cookies.set("le_at", short)
    assert cookie_value(client.get("/api/auth/me"), "le_at") not in (None, short)


def test_healthy_token_is_not_rotated(client, db_session):
    login(client, make_user(db_session))
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and not me.headers.get_list("set-cookie")


def test_concurrent_refresh_inside_grace_window_does_not_sign_the_user_out(client, db_session):
    user = make_user(db_session)
    first = login(client, user)
    stale_refresh = cookie_value(first, "le_rt")
    assert client.post("/api/auth/refresh").status_code == 200  # rotates; the old token is now "rotated"
    client.cookies.clear()
    client.cookies.set("le_rt", stale_refresh, path="/api")      # a parallel request that still carries the old cookie
    replay = client.post("/api/auth/refresh")
    assert replay.status_code == 200
    assert cookie_value(replay, "le_at") and cookie_value(replay, "le_rt") is None  # access token only
    assert db_session.scalars(select(AuthSession).where(AuthSession.revoked_at.is_not(None))).all() == []


def test_replaying_a_rotated_refresh_token_late_revokes_the_whole_family(client, db_session, monkeypatch, fresh_runtime):
    monkeypatch.setattr(settings, "auth_refresh_grace_seconds", 0)
    reset_auth_runtime()
    user = make_user(db_session)
    first = login(client, user)
    stale_refresh = cookie_value(first, "le_rt")
    rotated = client.post("/api/auth/refresh")
    newest_refresh = cookie_value(rotated, "le_rt")
    assert rotated.status_code == 200 and newest_refresh != stale_refresh

    client.cookies.clear()
    client.cookies.set("le_rt", stale_refresh, path="/api")
    theft = client.post("/api/auth/refresh")
    assert theft.status_code == 401 and theft.json()["error"]["code"] == "INVALID_SESSION"
    assert db_session.scalars(select(AuthEvent).where(AuthEvent.event_type == "refresh_reuse_detected")).all()

    client.cookies.clear()
    client.cookies.set("le_rt", newest_refresh, path="/api")      # the legitimate newest token died with the family
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_revokes_the_refresh_token_server_side(client, db_session):
    user = make_user(db_session)
    refresh = cookie_value(login(client, user), "le_rt")
    out = client.post("/api/auth/logout")
    assert out.status_code == 204
    assert {"le_at", "le_rt"} <= set(set_cookies(out))
    client.cookies.set("le_rt", refresh, path="/api")              # an attacker who kept a copy of the cookie
    assert client.post("/api/auth/refresh").status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_refresh_without_a_cookie_is_unauthorized(client):
    response = client.post("/api/auth/refresh")
    assert response.status_code == 401 and response.json()["error"]["code"] == "AUTH_REQUIRED"


def _as_admin_with_traveler_token(client, db_session):
    admin = make_user(db_session, role="admin")
    traveler = make_user(db_session)
    token = login(client, traveler).cookies.get("le_at")
    client.cookies.clear()
    sign_in(client, admin)
    bearer = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=bearer).status_code == 200
    return traveler, bearer


def test_role_change_revokes_existing_tokens_immediately(client, db_session):
    traveler, bearer = _as_admin_with_traveler_token(client, db_session)
    assert client.patch(f"/api/admin/users/{traveler.id}", json={"role": "admin", "is_active": True}).status_code == 200
    denied = client.get("/api/auth/me", headers=bearer)
    assert denied.status_code == 401 and denied.json()["error"]["code"] == "INVALID_SESSION"


def test_deactivation_revokes_existing_tokens_immediately(client, db_session):
    traveler, bearer = _as_admin_with_traveler_token(client, db_session)
    assert client.patch(f"/api/admin/users/{traveler.id}", json={"role": "traveler", "is_active": False}).status_code == 200
    denied = client.get("/api/auth/me", headers=bearer)
    assert denied.status_code == 401 and denied.json()["error"]["code"] == "ACCOUNT_DISABLED"


def test_unrelated_admin_edit_does_not_revoke_tokens(client, db_session):
    traveler, bearer = _as_admin_with_traveler_token(client, db_session)
    assert client.patch(f"/api/admin/users/{traveler.id}", json={"role": "traveler", "is_active": True}).status_code == 200
    assert client.get("/api/auth/me", headers=bearer).status_code == 200


def test_deactivated_users_cannot_refresh(client, db_session):
    admin = make_user(db_session, role="admin")
    traveler = make_user(db_session)
    login(client, traveler)
    refresh_token = client.cookies.get("le_rt", path="/api")
    client.cookies.clear()
    sign_in(client, admin)
    client.patch(f"/api/admin/users/{traveler.id}", json={"role": "traveler", "is_active": False})
    client.cookies.clear()
    client.cookies.set("le_rt", refresh_token, path="/api")
    assert client.post("/api/auth/refresh").status_code == 401


def test_changing_the_password_signs_other_devices_out_but_not_this_one(client, db_session):
    user = make_user(db_session)
    other_device_token = login(client, user).cookies.get("le_at")
    client.cookies.clear()
    login(client, user)                                          # "this device"
    changed = client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "another-long-password"})
    assert changed.status_code == 200 and cookie_value(changed, "le_at")
    assert client.get("/api/auth/me").status_code == 200
    stale = client.get("/api/auth/me", headers={"Authorization": f"Bearer {other_device_token}"})
    assert stale.status_code == 401
    assert login(client, user, "another-long-password").status_code == 200


@pytest.mark.parametrize("cookie", ["le_session", "le_at"])
def test_legacy_and_garbage_cookies_are_rejected(client, cookie):
    client.cookies.set(cookie, "eyJhbGciOiJIUzI1NiJ9.e30.garbage")
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_bearer_header_authenticates_without_cookies(client, db_session):
    user = make_user(db_session)
    token = login(client, user).cookies.get("le_at")
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_cookie_authenticated_writes_from_a_foreign_origin_are_blocked(client, db_session):
    login(client, make_user(db_session))
    blocked = client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"
    assert client.get("/api/auth/me").status_code == 200           # the blocked request did not log the user out
    allowed = client.post("/api/auth/logout", headers={"Origin": settings.web_app_url})
    assert allowed.status_code == 204


def test_origin_check_does_not_affect_bearer_or_anonymous_requests(client, db_session):
    token = login(client, make_user(db_session)).cookies.get("le_at")
    client.cookies.clear()
    foreign = {"Origin": "https://evil.example"}
    assert client.post("/api/auth/logout", headers=foreign).status_code == 204
    assert client.post("/api/auth/logout", headers={**foreign, "Authorization": f"Bearer {token}"}).status_code == 204


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _google(monkeypatch, email):
    monkeypatch.setattr(auth_routes, "_google_config", lambda db: {"client_id": "c", "client_secret": "s", "redirect_uri": "http://localhost/cb"})
    monkeypatch.setattr(auth_routes, "_google_configuration_issue", lambda db: None)
    monkeypatch.setattr(auth_routes.httpx, "post", lambda *a, **k: _FakeResponse({"access_token": "g"}))
    monkeypatch.setattr(auth_routes.httpx, "get", lambda *a, **k: _FakeResponse({"email": email, "sub": "g-1", "email_verified": True, "name": "G"}))


def _callback(client):
    client.cookies.set("le_google_state", "st")
    client.cookies.set("le_google_verifier", "ver")
    return client.get("/api/auth/google/callback?code=x&state=st", follow_redirects=False)


def test_admins_cannot_sign_in_with_google(client, db_session, monkeypatch):
    admin = make_user(db_session, role="admin", email="boss@example.test")
    _google(monkeypatch, admin.email)
    response = _callback(client)
    assert response.status_code == 303 and "admin_requires_password" in response.headers["location"]
    assert "le_at" not in set_cookies(response)
    db_session.refresh(admin)
    assert admin.google_sub is None                      # no Google identity is ever linked to an administrator
    assert db_session.scalars(select(AuthSession)).all() == []


def test_travelers_can_sign_in_with_google_and_get_a_google_amr(client, db_session, monkeypatch):
    _google(monkeypatch, "visitor@example.test")
    response = _callback(client)
    assert response.status_code == 303 and "error=" not in response.headers["location"]
    assert {"le_at", "le_rt"} <= set(set_cookies(response))
    session = db_session.scalars(select(AuthSession)).one()
    assert session.amr == ["google"]
