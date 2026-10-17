import socket

import httpx
import pytest
from fastapi.testclient import TestClient

from app import jobs, kv, nodes, system, worker
from app.config import settings
from app.db import get_conn
from app.main import app
from tests.conftest import TEST_URL
from tests.test_trips_api import auth

DEAD_PG = "postgresql://travility:travility@127.0.0.1:1/travility"  # không ai nghe cổng 1
ME = f"api {socket.gethostname()}"
URL = "/system/status"


@pytest.fixture
def api(conn, monkeypatch):
    monkeypatch.setattr(settings, "database_url", TEST_URL)
    monkeypatch.setattr(settings, "llm_base_url", "https://provider.example/v1")
    monkeypatch.setattr(system, "_last", [])
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def state(body):
    return {n["name"]: n["state"] for n in body["nodes"]}


def test_needs_login(api):
    assert api.get(URL).status_code == 401


def test_simple_mode_is_this_api_and_the_database_and_never_calls_out(api, monkeypatch):
    def no_http(*a, **k):
        raise AssertionError("chế độ đơn giản không được dò ra ngoài")

    monkeypatch.setattr(httpx, "get", no_http)
    b = api.get(URL, headers=auth(api)).json()
    assert state(b) == {ME: "up", "pg-catalog": "up"}
    assert b["served_by"] == ME and b["my_shard"] is None and b["stats"] is None
    assert b["planner_mode"] == "single"


def test_dead_nodes_are_down_and_live_replica_reports_lag(api, monkeypatch):
    h = auth(api)
    monkeypatch.setattr(settings, "catalog_replica_url", DEAD_PG)
    monkeypatch.setattr(settings, "places_url", "http://127.0.0.1:1")
    monkeypatch.setattr(settings, "llm_base_url", "http://127.0.0.1:1/v1")
    s = state(api.get(URL, headers=h).json())
    assert s["pg-catalog-replica"] == s["places"] == s["llm-gateway"] == "down"
    assert s["pg-catalog"] == "up"
    monkeypatch.setattr(settings, "catalog_replica_url", TEST_URL)
    replica = next(n for n in api.get(URL, headers=h).json()["nodes"] if n["name"] == "pg-catalog-replica")
    assert replica["state"] == "up" and replica["lag_ms"] is None  # database test không phải standby


def test_users_shard_and_shard_nodes(api, shards):
    h = auth(api)
    uid = api.get("/auth/me", headers=h).json()["id"]
    b = api.get(URL, headers=h).json()
    assert b["my_shard"] == uid % 2
    assert state(b)["pg-shard-0"] == state(b)["pg-shard-1"] == "up"


def test_heartbeats_and_counters_come_from_redis(api, rds, monkeypatch):
    t = [1_000_000.0]
    monkeypatch.setattr(nodes, "_now", lambda: t[0])
    nodes.beat("planner", "p1")
    t[0] += 7
    nodes.beat("planner-agent", "a1")
    rds.set("gw:stat:hit", 42)
    rds.set("rl:blocked", 3)
    b = api.get(URL, headers=auth(api)).json()
    s = state(b)
    assert (s["planner p1"], s["planner-agent a1"], s["redis"], s[ME]) == ("down", "up", "up", "up")
    assert b["stats"] == {"cache_hit": 42, "cache_miss": 0, "provider_call": 0, "provider_wait": 0,
                          "provider_fallback": 0, "rate_limited": 3, "waiting": 0, "running": 0}


def test_queue_counts_waiting_and_running(api, rds):
    h = auth(api)
    worker.ensure_group(rds)
    jobs.enqueue("message", 1, {})
    jobs.enqueue("message", 1, {})
    rds.xreadgroup(jobs.GROUP, "p1", {jobs.STREAM: ">"}, count=1)
    st = api.get(URL, headers=h).json()["stats"]
    assert (st["waiting"], st["running"]) == (1, 1)


def test_redis_down_keeps_last_seen_nodes_as_unknown(api, rds, monkeypatch):
    h = auth(api)
    nodes.beat("planner", "p1")
    assert state(api.get(URL, headers=h).json())["planner p1"] == "up"
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")
    monkeypatch.setattr(kv, "_client", None)
    b = api.get(URL, headers=h).json()
    s = state(b)
    assert (s["redis"], s["planner p1"], s[ME]) == ("down", "unknown", "up")
    assert b["stats"] is None


def test_nginx_is_listed_only_when_the_request_came_through_it(api):
    h = auth(api)
    assert "nginx" not in state(api.get(URL, headers=h).json())
    assert state(api.get(URL, headers={**h, "X-Via": "nginx"}).json())["nginx"] == "up"
