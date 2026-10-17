import time

import pytest

from app import kv, nodes
from app.config import settings


@pytest.fixture
def clock(monkeypatch):
    t = [1_000_000.0]
    monkeypatch.setattr(nodes, "_now", lambda: t[0])
    return t


def test_without_redis_nothing_happens():
    nodes.beat("api")
    nodes.start("api")
    assert nodes.seen() is None


def test_silent_node_is_down_then_forgotten(rds, clock):
    nodes.beat("planner", "p1")
    clock[0] += 5
    nodes.beat("planner-agent", "a1")
    assert nodes.seen() == [{"role": "planner", "host": "p1", "up": True},
                            {"role": "planner-agent", "host": "a1", "up": True}]
    clock[0] += 2  # p1 đã im 7 giây
    assert [(n["host"], n["up"]) for n in nodes.seen()] == [("p1", False), ("a1", True)]
    clock[0] += 600
    nodes.beat("planner", "p2")
    assert [n["host"] for n in nodes.seen()] == ["p2"]


def test_default_host_is_this_machine(rds):
    nodes.beat("api")
    assert nodes.seen()[0]["host"] and nodes.seen()[0]["role"] == "api"


def test_redis_down_is_silent(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")
    monkeypatch.setattr(kv, "_client", None)
    nodes.beat("api")
    assert nodes.seen() is None


def test_background_beat_comes_back_after_key_is_deleted(rds, monkeypatch):
    """Runbook xoá khoá `nodes` để dọn node ma: bản đang sống phải tự hiện lại."""
    monkeypatch.setattr(nodes, "BEAT_S", 0.05)
    stop = nodes.start("api")
    try:
        rds.delete(nodes.KEY)
        deadline = time.time() + 2
        while not nodes.seen() and time.time() < deadline:
            time.sleep(0.02)
        assert [n["role"] for n in nodes.seen()] == ["api"]
    finally:
        stop.set()  # không để thread nền ghi vào Redis của các test sau
