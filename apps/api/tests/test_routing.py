from datetime import datetime, timedelta, timezone

import pytest

from app.adapters.routing.goong import (
    AddressCandidate,
    AddressResolution,
    GoongDirectionsProvider,
    GoongGeocodingProvider,
)
from app.adapters.routing.provider import (
    RouteEstimate,
    RoutingConfigurationError,
    UnsupportedTravelMode,
)
from app.api.routes import routing as routing_routes
from app.core.config import settings
from app.schemas.planner import PlanRequest
from app.services.planner_service import PlannerService
from tests.conftest import add_slot


@pytest.mark.parametrize(
    ("app_mode", "goong_vehicle"),
    [("motorcycle", "bike"), ("walking", "foot"), ("car", "car")],
)
def test_goong_directions_mode_mapping_and_eta_cache(app_mode, goong_vehicle):
    provider = GoongDirectionsProvider("test-key", eta_ttl_seconds=300)
    calls = []

    def fake_request(path, params):
        calls.append((path, params))
        return {"status": "OK", "routes": [{"legs": [{
            "distance": {"value": 1234}, "duration": {"value": 61},
        }], "overview_polyline": {"points": "_p~iF~ps|U_ulLnnqC_mqNvxq`@"}}]}

    provider._request_json = fake_request
    first = provider.get_route((10.75, 106.6), (10.76, 106.7), app_mode)
    second = provider.get_route((10.75, 106.6), (10.76, 106.7), app_mode)

    assert calls[0][0] == "/v2/direction"
    assert calls[0][1]["vehicle"] == goong_vehicle
    assert len(calls) == 1
    assert first == second
    assert first.distance_m == 1234
    assert first.duration_min == 2  # Round up partial minutes for the return-deadline check.
    assert first.provider == "goong_directions_v2"
    assert first.is_realtime is False
    assert first.calculated_at is not None and first.valid_until is not None
    assert first.source_uri.startswith("https://help.goong.io/")
    assert first.geometry is not None
    assert first.geometry[0] == pytest.approx((38.5, -120.2))


@pytest.mark.parametrize("mode", ["transit", "bicycling", "walking_transit"])
def test_goong_rejects_unconfigured_transport_modes(mode):
    provider = GoongDirectionsProvider("test-key")
    with pytest.raises(UnsupportedTravelMode):
        provider.get_route((10.75, 106.6), (10.76, 106.7), mode)


def test_goong_requires_server_api_key():
    configured = GoongDirectionsProvider("configured-test-key")
    configured._route_cache[(10.75, 106.6, 10.76, 106.7, "car")] = RouteEstimate(
        distance_m=1, duration_min=1, provider="goong_directions_v2", is_realtime=False,
        eta_source="test", calculated_at=datetime.now(timezone.utc),
        valid_until=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    # A route cached by a configured client must never bypass another client's
    # missing-key check.
    provider = GoongDirectionsProvider(None)
    with pytest.raises(RoutingConfigurationError, match="GOONG_API_KEY"):
        provider.get_route((10.75, 106.6), (10.76, 106.7), "car")


def test_plan_requires_both_ends_if_one_end_is_given():
    with pytest.raises(ValueError, match="both origin and return-destination"):
        PlanRequest.model_validate({
            "start_at": "2030-10-01T08:00:00+07:00",
            "end_at": "2030-10-01T16:00:00+07:00",
            "group_size": 2,
            "budget_vnd": 1_000_000,
            "origin_latitude": 10.77,
            "origin_longitude": 106.68,
        })


def test_goong_forward_geocoding_normalizes_and_caches_result():
    provider = GoongGeocodingProvider("test-key", cache_ttl_seconds=3600)
    calls = []

    def fake_request(path, params):
        calls.append((path, params))
        return {"status": "OK", "results": [{
            "formatted_address": "1 Example Street, Ho Chi Minh City",
            "geometry": {"location": {"lat": 10.75, "lng": 106.7}},
            "place_id": "example-place",
        }]}

    provider._request_json = fake_request
    first = provider.forward("  1 Example Street,  Ho Chi Minh City  ")
    second = provider.forward("1 example street, ho chi minh city")

    assert len(calls) == 1
    assert calls[0][0] == "/v2/geocode"
    assert calls[0][1]["address"] == "1 Example Street, Ho Chi Minh City"
    assert first == second
    assert first.provider == "goong_geocode_v2"
    assert first.results[0].latitude == pytest.approx(10.75)
    assert first.results[0].longitude == pytest.approx(106.7)
    assert first.results[0].place_id == "example-place"
    assert first.valid_until > first.resolved_at


def test_geocoding_endpoint_returns_source_and_age(client, monkeypatch):
    resolved_at = datetime.now(timezone.utc) - timedelta(seconds=12)
    result = AddressResolution(
        results=[AddressCandidate("District 1, Ho Chi Minh City", 10.77, 106.7, "place-1")],
        resolved_at=resolved_at,
        valid_until=resolved_at + timedelta(days=1),
    )

    class FakeGeocoder:
        def __init__(self, db=None):
            self.db = db

        def forward(self, address):
            assert address == "District 1, Ho Chi Minh City"
            return result

    monkeypatch.setattr(routing_routes, "make_geocoding_provider", FakeGeocoder)
    response = client.get("/api/geocoding/forward", params={"address": "District 1, Ho Chi Minh City"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "goong_geocode_v2"
    assert body["age_seconds"] >= 12
    assert body["source_uri"].startswith("https://help.goong.io/")
    assert body["results"][0]["place_id"] == "place-1"


def test_plan_checks_outbound_and_return_for_each_goong_mode(db_session, sample_experience):
    add_slot(db_session, sample_experience)

    class FakeRoutingProvider:
        def __init__(self):
            self.calls = []

        def get_route(self, origin, destination, mode):
            self.calls.append((origin, destination, mode))
            now = datetime.now(timezone.utc)
            return RouteEstimate(
                distance_m=1800,
                duration_min=10,
                provider="goong_directions_v2",
                is_realtime=False,
                eta_source="Goong Directions API v2 test fixture",
                calculated_at=now,
                valid_until=now + timedelta(minutes=5),
                source_uri="https://help.goong.io/directions",
            )

    for mode in ("motorcycle", "walking", "car"):
        routing = FakeRoutingProvider()
        request = PlanRequest.model_validate({
            "start_at": "2030-10-01T08:00:00+07:00",
            "end_at": "2030-10-01T16:00:00+07:00",
            "group_size": 2,
            "budget_vnd": 1_000_000,
            "transport_mode": mode,
            "origin_latitude": 10.77,
            "origin_longitude": 106.68,
            "destination_latitude": 10.78,
            "destination_longitude": 106.69,
            "origin_label": "Start",
            "destination_label": "Return",
            "intent_weights": {"handicraft": 1.0},
        })

        plan = PlannerService(db_session, routing=routing).plan(request)

        assert len(plan["routes"]) == 2
        assert {call[2] for call in routing.calls} == {mode}
        assert all(route["provider"] == "goong_directions_v2" for route in plan["routes"])
        assert all(route["eta_age_seconds"] >= 0 for route in plan["routes"])
        assert all(route["eta_source_uri"].startswith("https://help.goong.io/") for route in plan["routes"])
        assert plan["routes"][0]["from_label"] == "Start"
        assert plan["routes"][-1]["to_label"] == "Return"
        assert plan["estimated_return_at"] < request.end_at
