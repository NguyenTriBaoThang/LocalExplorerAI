import datetime as dt

import httpx

from app import forecast
from app.config import settings
from app.forecast import get_rain_chance

TODAY = dt.date(2026, 9, 25)


def client_returning(values):
    def handler(request):
        return httpx.Response(200, json={"daily": {"precipitation_probability_max": values}})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_within_horizon():
    r = get_rain_chance(11.9, 108.4, dt.date(2026, 9, 27), 3, client_returning([10, 70, 20]), TODAY)
    assert r == [10, 70, 20]


def test_partial_horizon_is_padded():
    r = get_rain_chance(11.9, 108.4, dt.date(2026, 10, 9), 3, client_returning([10, 70]), TODAY)
    assert r == [10, 70, None]


def test_no_date_or_too_far_or_past():
    c = client_returning([1])
    assert get_rain_chance(11.9, 108.4, None, 3, c, TODAY) is None
    assert get_rain_chance(11.9, 108.4, dt.date(2026, 10, 20), 3, c, TODAY) is None
    assert get_rain_chance(11.9, 108.4, dt.date(2026, 9, 1), 3, c, TODAY) is None


def test_network_error_gives_none():
    def boom(request):
        raise httpx.ConnectError("offline")
    c = httpx.Client(transport=httpx.MockTransport(boom))
    assert get_rain_chance(11.9, 108.4, dt.date(2026, 9, 27), 2, c, TODAY) is None


def test_injected_client_not_closed():
    c = client_returning([10, 20])
    r = get_rain_chance(11.9, 108.4, dt.date(2026, 9, 27), 2, c, TODAY)
    assert r == [10, 20]
    assert not c.is_closed


ARGS = (11.9, 108.4, dt.date(2026, 9, 27), 2)
KEY = "forecast:11.9:108.4:2026-09-27:2"


def offline():
    def boom(request):
        raise httpx.ConnectError("offline")
    return httpx.Client(transport=httpx.MockTransport(boom))


def test_cached_in_redis_survives_network_loss(rds):
    assert get_rain_chance(*ARGS, client_returning([10, 20]), TODAY) == [10, 20]
    assert get_rain_chance(*ARGS, offline(), TODAY) == [10, 20]
    assert 0 < rds.ttl(KEY) <= forecast.CACHE_S


def test_failure_not_cached(rds):
    assert get_rain_chance(*ARGS, offline(), TODAY) is None
    assert get_rain_chance(*ARGS, client_returning([10, 20]), TODAY) == [10, 20]


def test_demo_today_records_failure_forever(rds, monkeypatch):
    """Đã đóng băng ngày thì kết quả lúc ghi (kể cả lỗi) phải lặp lại y nguyên lúc phát lại."""
    monkeypatch.setattr(settings, "demo_today", TODAY)
    assert get_rain_chance(*ARGS, offline(), TODAY) is None
    assert get_rain_chance(*ARGS, client_returning([10, 20]), TODAY) is None
    assert rds.ttl(KEY) == -1
