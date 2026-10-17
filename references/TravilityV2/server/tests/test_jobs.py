import json
import threading

import pytest
from fastapi import HTTPException

from app import jobs, kv
from app.config import settings


@pytest.fixture
def minute(monkeypatch):
    """Đồng hồ đứng ở giây thứ 10 của một phút; test tự tua bằng minute[0] += …"""
    t = [60_000_010.0]
    monkeypatch.setattr(jobs, "_now", lambda: t[0])
    return t


@pytest.fixture
def redis_down(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")
    monkeypatch.setattr(kv, "_client", None)


def test_sixth_request_in_a_minute_is_429(rds, minute):
    for _ in range(5):
        jobs.check_rate(7)
    with pytest.raises(HTTPException) as e:
        jobs.check_rate(7)
    assert e.value.status_code == 429
    assert e.value.headers["Retry-After"] == "50" and "50 giây" in e.value.detail
    assert rds.get("rl:blocked") == "1"


def test_other_user_and_next_minute_are_not_limited(rds, minute):
    for _ in range(5):
        jobs.check_rate(7)
    jobs.check_rate(8)
    minute[0] += 60
    jobs.check_rate(7)


def test_counter_expires(rds, minute):
    jobs.check_rate(7)
    assert 0 < rds.ttl("rl:7:1000000") <= 120


def test_plan_rpm_zero_means_no_limit(rds, minute, monkeypatch):
    monkeypatch.setattr(settings, "plan_rpm", 0)
    for _ in range(20):
        jobs.check_rate(7)
    assert rds.keys("rl:*") == []


def test_rate_limit_lets_through_when_redis_down(redis_down):
    for _ in range(10):
        jobs.check_rate(7)


def test_no_redis_url_means_no_limit():
    for _ in range(10):
        jobs.check_rate(7)


def test_enqueue_writes_job_and_owner(rds):
    job_id = jobs.enqueue("message", 7, {"message": "Đà Lạt", "trip_id": None})
    [(_, fields)] = rds.xrange("jobs")
    assert fields == {"job_id": job_id, "kind": "message", "user_id": "7",
                      "params": '{"message": "Đà Lạt", "trip_id": null}'}
    assert jobs.owner(job_id) == 7
    assert 0 < rds.ttl(f"job:{job_id}:user") <= 3600


def test_owner_of_unknown_job_is_none(rds):
    assert jobs.owner("khong-co") is None


def test_enqueue_is_503_when_redis_down(redis_down):
    with pytest.raises(HTTPException) as e:
        jobs.enqueue("message", 7, {})
    assert e.value.status_code == 503 and "tạm không dùng được" in e.value.detail


def test_relay_yields_in_order_and_stops_at_end(rds):
    jobs.publish("j1", "data: 1\n\n")
    jobs.publish("j1", "data: 2\n\n")
    jobs.finish("j1")
    jobs.publish("j1", "data: 3\n\n")
    assert list(jobs.relay("j1")) == ["data: 1\n\n", "data: 2\n\n"]
    assert 0 < rds.ttl("events:j1") <= 3600


def test_relay_waits_for_late_events(rds):
    def later():
        jobs.publish("j2", "data: x\n\n")
        jobs.finish("j2")

    threading.Timer(0.2, later).start()
    assert list(jobs.relay("j2")) == ["data: x\n\n"]


def test_relay_gives_error_after_long_silence(rds, monkeypatch):
    t = [0.0]

    def now():
        t[0] += 61
        return t[0]

    monkeypatch.setattr(jobs, "_now", now)
    out = list(jobs.relay("j3"))
    assert len(out) == 1
    assert json.loads(out[0][6:]) == {"type": "error",
                                      "message": "Hệ thống lập lịch đang bận hoặc chưa chạy, bạn thử lại sau nhé."}


def test_relay_gives_error_when_redis_dies(redis_down):
    out = list(jobs.relay("j4"))
    assert len(out) == 1 and "Mất kết nối" in json.loads(out[0][6:])["message"]


def test_relay_quiet_timer_restarts_on_every_event(rds, monkeypatch):
    """Việc dài hơn 120 giây vẫn sống miễn là còn phát event."""
    t = [0.0]
    monkeypatch.setattr(jobs, "_now", lambda: t[0])
    jobs.publish("j5", "data: 1\n\n")
    gen = jobs.relay("j5")
    assert next(gen) == "data: 1\n\n"
    t[0] = 100
    jobs.publish("j5", "data: 2\n\n")
    assert next(gen) == "data: 2\n\n"
    t[0] = 150  # 150 giây từ đầu nhưng mới 50 giây từ event gần nhất
    jobs.finish("j5")
    assert list(gen) == []
