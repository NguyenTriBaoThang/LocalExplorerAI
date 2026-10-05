"""Regressions for the pull-request review: cookie prefixes, origin scheme, revocation with Redis down, rollback safety."""

from types import SimpleNamespace

import pytest
from starlette.datastructures import Headers

from app.auth import UserState
from app.core.client_ip import request_scheme
from app.core.config import settings
from app.services import auth_runtime
from tests.helpers import make_user, sign_in


def _cookie_client(client, db_session, monkeypatch, name):
    user = make_user(db_session, "traveler")
    token = sign_in(client, user)
    client.cookies.clear()
    client.cookies.set(name, token)
    return client


def test_bare_cookie_is_ignored_where_the_prefixed_name_is_in_force(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    _cookie_client(client, db_session, monkeypatch, "le_at")
    assert client.get("/api/auth/me").status_code == 401


def test_prefixed_cookie_is_accepted_in_production(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    _cookie_client(client, db_session, monkeypatch, "__Host-le_at")
    assert client.get("/api/auth/me").status_code == 200


def test_bare_cookie_still_works_for_plain_http_development(client, db_session, monkeypatch):
    _cookie_client(client, db_session, monkeypatch, "le_at")
    assert client.get("/api/auth/me").status_code == 200


def test_same_host_origin_must_also_match_the_scheme(client, db_session):
    _cookie_client(client, db_session, None, "le_at")
    wrong_scheme = client.post("/api/auth/logout", headers={"Origin": "https://testserver"})
    assert wrong_scheme.status_code == 403 and wrong_scheme.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"
    assert client.post("/api/auth/logout", headers={"Origin": "http://testserver"}).status_code != 403


def _request(peer, proto=None, scheme="http"):
    headers = {"x-forwarded-proto": proto} if proto else {}
    return SimpleNamespace(url=SimpleNamespace(scheme=scheme), client=SimpleNamespace(host=peer), headers=Headers(headers))


def test_forwarded_proto_is_believed_only_from_a_trusted_proxy():
    assert request_scheme(_request("10.0.0.5", "https"), "10.0.0.0/8") == "https"
    assert request_scheme(_request("203.0.113.9", "https"), "10.0.0.0/8") == "http"   # spoofed by a client
    assert request_scheme(_request("10.0.0.5", "https"), "") == "http"
    assert request_scheme(_request("10.0.0.5", "gopher"), "10.0.0.0/8") == "http"


class _FlakyRedis:
    def __init__(self):
        self.entries = {"u1": UserState(token_version=1, is_active=True)}
        self.down = False

    def get(self, user_id):
        if self.down:
            raise ConnectionError("down")
        return self.entries.get(user_id)

    def set(self, user_id, state):
        if self.down:
            raise ConnectionError("down")
        self.entries[user_id] = state

    def invalidate(self, user_id):
        if self.down:
            raise ConnectionError("down")
        self.entries.pop(user_id, None)


def test_revocation_survives_redis_being_down_while_the_user_is_invalidated():
    redis = _FlakyRedis()
    store = auth_runtime._ResilientStore(redis)
    redis.down = True
    store.invalidate("u1")            # fails: the old entry is still in Redis
    redis.down = False
    store._skip_until = 0.0           # the back-off has passed, Redis is reachable again
    assert store.get("u1") is None, "the stale entry must not be served; the caller reads the database"
    assert redis.entries["u1"].token_version == 1  # still there, which is exactly why it must be bypassed


def test_invalidate_during_backoff_is_remembered_and_expires_with_the_entry():
    redis = _FlakyRedis()
    store = auth_runtime._ResilientStore(redis)
    redis.down = True
    store.get("u1")                   # first failure starts the back-off
    store.invalidate("u1")            # skipped without touching Redis
    redis.down = False
    store._skip_until = 0.0
    assert store.get("u1") is None
    store._unconfirmed["u1"] = 0.0    # the entry's TTL has certainly elapsed
    assert store.get("u1") is redis.entries["u1"]


def test_successful_invalidate_leaves_nothing_to_bypass():
    redis = _FlakyRedis()
    store = auth_runtime._ResilientStore(redis)
    store.invalidate("u1")
    assert store._unconfirmed == {}
    assert store.get("u1") is None    # gone from Redis: a cache miss, the database answers


def test_0012_downgrade_keeps_rows_added_after_the_seed():
    import importlib.util
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    spec = importlib.util.spec_from_file_location("m0012x", "migrations/versions/0012_rbac_seed.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE roles (name VARCHAR(40) PRIMARY KEY, description VARCHAR(255), is_system BOOLEAN, created_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE permissions (name VARCHAR(80) PRIMARY KEY, description VARCHAR(255), created_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE role_permissions (role_name VARCHAR(40), permission_name VARCHAR(80))"))
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            # what an operator did afterwards
            conn.execute(sa.text("INSERT INTO roles VALUES ('support', 'custom', 0, NULL)"))
            conn.execute(sa.text("INSERT INTO permissions VALUES ('custom:report', 'custom', NULL)"))
            conn.execute(sa.text("INSERT INTO role_permissions VALUES ('traveler', 'custom:report')"))
            conn.execute(sa.text("INSERT INTO role_permissions VALUES ('support', 'chat:use')"))
            module.downgrade()
        names = lambda q: {r[0] for r in conn.execute(sa.text(q))}
        assert names("SELECT name FROM roles") == {"support", "traveler"}          # traveler still holds a custom grant
        assert names("SELECT name FROM permissions") == {"custom:report", "chat:use"}  # chat:use is still granted to support
        assert {tuple(r) for r in conn.execute(sa.text("SELECT role_name, permission_name FROM role_permissions"))} == {
            ("traveler", "custom:report"), ("support", "chat:use")}
