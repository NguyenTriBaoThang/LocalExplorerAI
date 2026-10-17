import json

import httpx
import pytest

from app import distance, places_client
from app.config import settings
from app.domain import Hub

A, B, C = (Hub(name=n, lat=lat, lon=108.44) for n, lat in (("A", 11.94), ("B", 11.95), ("C", 11.96)))
OK = {"status": "OK", "distance": {"value": 2340}, "duration": {"value": 420}}


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setattr(settings, "goong_api_key", "k")


def client_returning(body, status=200, calls=None):
    def handler(request):
        if calls is not None:
            calls.append(request)
        return httpx.Response(status, json=body)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_prefetch_fills_cache():
    calls = []
    far = {**OK, "distance": {"value": 5000}}
    distance.prefetch([A], [B, C], "xe-may", client_returning({"rows": [{"elements": [OK, far]}]}, calls=calls))
    assert distance.lookup(A, B, "xe-may") == (2.34, 7)
    assert distance.lookup(A, C, "xe-may") == (5.0, 7)
    assert distance.lookup(B, A, "xe-may") is None  # chiều ngược lại là chặng khác
    assert distance.lookup(A, B, "o-to-rieng") is None  # xe khác, tuyến khác
    params = calls[0].url.params
    assert (params["origins"], params["destinations"], params["vehicle"]) == (
        "11.94,108.44", "11.95,108.44|11.96,108.44", "bike")


def test_cached_pairs_not_fetched_again():
    calls = []
    c = client_returning({"rows": [{"elements": [OK]}]}, calls=calls)
    distance.prefetch([A], [B], "grab", c)
    distance.prefetch([A], [B], "grab", c)
    assert len(calls) == 1 and calls[0].url.params["vehicle"] == "car"


def test_no_key_no_call(monkeypatch):
    monkeypatch.setattr(settings, "goong_api_key", "")
    calls = []
    distance.prefetch([A], [B], "xe-may", client_returning({"rows": [{"elements": [OK]}]}, calls=calls))
    assert calls == [] and distance.lookup(A, B, "xe-may") is None


@pytest.mark.parametrize("body,status", [
    ({}, 500),
    ({"error": "quota"}, 200),
    ({"rows": [{"elements": [{"status": "OK"}]}]}, 200),
])
def test_bad_response_falls_back_and_cools_down(body, status):
    distance.prefetch([A], [B], "xe-may", client_returning(body, status))
    assert distance.lookup(A, B, "xe-may") is None
    calls = []
    distance.prefetch([A], [B], "xe-may", client_returning({"rows": [{"elements": [OK]}]}, calls=calls))
    assert calls == []  # Goong vừa lỗi → nghỉ, không để mỗi ngày của Itinerary chờ một timeout


def test_element_not_ok_is_skipped():
    distance.prefetch([A], [B, C], "xe-may",
                      client_returning({"rows": [{"elements": [{"status": "ZERO_RESULTS"}, OK]}]}))
    assert distance.lookup(A, B, "xe-may") is None
    assert distance.lookup(A, C, "xe-may") == (2.34, 7)


def test_km_shared_through_redis(rds):
    distance.prefetch([A], [B], "xe-may", client_returning({"rows": [{"elements": [OK]}]}))
    distance._cache.clear()  # tiến trình khác: lớp cache trong RAM trống
    calls = []
    distance.prefetch([A], [B], "xe-may", client_returning({"rows": [{"elements": [OK]}]}, calls=calls))
    assert calls == []  # đã có trong Redis → không gọi Goong
    assert distance.lookup(A, B, "xe-may") == (2.34, 7)
    assert rds.ttl("goong:11.94:108.44:11.95:108.44:bike") == -1


def via_places(monkeypatch, handler):
    monkeypatch.setattr(settings, "places_url", "http://places")
    monkeypatch.setattr(places_client, "_http", httpx.Client(transport=httpx.MockTransport(handler)))


def test_prefetch_asks_places_service(monkeypatch):
    sent = []

    def places(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"rows": [[[1.5, 4], None]]})
    via_places(monkeypatch, places)
    distance.prefetch([A], [B, C], "xe-may")
    assert distance.lookup(A, B, "xe-may") == (1.5, 4)
    assert distance.lookup(A, C, "xe-may") is None
    pt = lambda p: {"lat": p.lat, "lon": p.lon}  # noqa: E731
    assert sent == [{"origins": [pt(A)], "destinations": [pt(B), pt(C)], "mode": "xe-may"}]


def test_places_down_cools_down(monkeypatch):
    calls = []

    def refuse(request):
        calls.append(1)
        raise httpx.ConnectError("x", request=request)
    via_places(monkeypatch, refuse)
    distance.prefetch([A], [B], "xe-may")
    distance.prefetch([A], [B], "xe-may")
    assert distance.lookup(A, B, "xe-may") is None and len(calls) == 1
