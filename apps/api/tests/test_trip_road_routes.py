from datetime import datetime, timezone

from app.adapters.routing.provider import RouteEstimate, RoutingProviderError
from app.api.routes import routing
from tests.helpers import bearer_for, make_user


BODY = {'origin': {'lat': 10.77, 'lon': 106.69}, 'destination': {'lat': 10.78, 'lon': 106.70}, 'mode': 'car'}


def test_road_route_requires_login(client):
    assert client.post('/api/routing/road', json=BODY).status_code == 401


def test_road_route_uses_provider_geometry_in_geojson_order(client, db_session, monkeypatch):
    user = make_user(db_session, 'traveler')
    class Provider:
        def get_route(self, origin, destination, mode):
            assert origin == (10.77, 106.69) and destination == (10.78, 106.70)
            assert mode == 'car'
            return RouteEstimate(1500, 5, provider='goong_directions_v2',
                                 geometry=[origin, (10.775, 106.697), destination])
    monkeypatch.setattr(routing, 'make_routing_provider', lambda db: Provider())
    response = client.post('/api/routing/road', json=BODY, headers=bearer_for(user))
    assert response.status_code == 200
    assert response.json()['coordinates'] == [[106.69, 10.77], [106.697, 10.775], [106.70, 10.78]]


def test_road_route_rejects_mock_and_invalid_coordinates(client, db_session, monkeypatch):
    from app.adapters.routing.provider import MockRoutingProvider
    user = make_user(db_session, 'traveler')
    monkeypatch.setattr(routing, 'make_routing_provider', lambda db: MockRoutingProvider())
    headers = bearer_for(user)
    assert client.post('/api/routing/road', json=BODY, headers=headers).status_code == 503
    assert client.post('/api/routing/road', json={**BODY, 'origin': {'lat': 100, 'lon': 0}}, headers=headers).status_code == 422
    assert client.post('/api/routing/road', json={**BODY, 'mode': 'walking'}, headers=headers).status_code == 422


def test_road_route_provider_failure_does_not_expose_credentials(client, db_session, monkeypatch):
    user = make_user(db_session, 'traveler')
    def unavailable(db):
        raise RoutingProviderError('sensitive upstream diagnostic')
    monkeypatch.setattr(routing, 'make_routing_provider', unavailable)
    result = client.post('/api/routing/road', json=BODY, headers=bearer_for(user))
    assert result.status_code == 503
    assert 'sensitive' not in result.text
