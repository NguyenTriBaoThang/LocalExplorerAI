from datetime import datetime, timedelta, timezone

from app.adapters.llm.provider import NotConfiguredLLMProvider
from app.api.dependencies import get_llm_provider
from app.api.routes import models_3d
from app.core.config import settings
from app.models.entities import Evidence
from app.services.evidence_service import REQUIRED_FIELDS
from app.services.offline_chat_fallback import build_offline_constraints
from tests.conftest import add_slot


def model_for(poi, **changes):
    return {"display_name": poi.name, "latitude": poi.latitude, "longitude": poi.longitude, **changes}


def test_multi_turn_chat_preserves_explicit_values_and_accepts_budget_correction(client):
    client.app.dependency_overrides[get_llm_provider] = lambda: NotConfiguredLLMProvider()
    first = client.post('/api/chat/message', json={"message": "2 người, từ 09:00 đến 16:00, đi bộ"}).json()
    second = client.post('/api/chat/message', json={
        "message": "Tổng ngân sách 1.200.000 đồng, thích văn hóa",
        "previous_constraints": first['structured_constraints'],
    })
    assert second.status_code == 200
    parsed = second.json()['structured_constraints']
    assert parsed['budget_vnd'] == 1200000
    assert parsed['group_size'] == 2 and parsed['travel_mode'] == 'walking'
    assert parsed['start_time'] == '09:00' and parsed['is_complete']
    third = client.post('/api/chat/message', json={"message": "Đổi ngân sách 0 đồng", "previous_constraints": parsed})
    assert third.json()['structured_constraints']['budget_vnd'] == 0


def test_offline_money_never_treats_per_person_as_total():
    parsed, _ = build_offline_constraints('Ngân sách 500.000₫ mỗi người', 'llm_not_configured')
    assert parsed.budget_vnd is None


def test_landmark_link_requires_spatial_agreement_and_cannot_publish_unsourced_description(client, db_session, sample_experience, monkeypatch):
    poi = sample_experience.poi
    monkeypatch.setattr(models_3d, '_read_calibrations', lambda: {
        'matched': model_for(poi),
        'wrong': model_for(poi, latitude=15.877, longitude=108.326, poi_id=poi.id),
    })
    add_slot(db_session, sample_experience)
    result = client.get('/api/journey/landmarks/matched').json()
    assert result['poi_id'] == poi.id and result['in_pilot']
    assert result['description'] is None and not result['verified']
    assert result['experiences'] == []
    demo = client.get('/api/journey/landmarks/matched?demo=true').json()
    assert demo['experiences'][0]['id'] == sample_experience.id
    outside = client.get('/api/journey/landmarks/wrong?demo=true').json()
    assert not outside['in_pilot'] and outside['poi_id'] is None and outside['experiences'] == []
    client.app.dependency_overrides[get_llm_provider] = lambda: NotConfiguredLLMProvider()
    chat = client.post('/api/chat/message', json={'message': 'Kể về địa danh', 'model_id': 'matched'}).json()
    assert poi.description not in chat['reply']


def test_filters_use_trip_budget_capacity_and_date(client, db_session, sample_experience):
    add_slot(db_session, sample_experience)
    params = {'scope': 'pilot', 'start_at': '2030-10-01T01:00:00Z', 'end_at': '2030-10-01T09:00:00Z',
              'poi_id': sample_experience.poi_id, 'group_size': 2, 'total_budget_vnd': 150000}
    assert client.get('/api/experiences', params=params).json() == []
    params['total_budget_vnd'] = 200000
    assert len(client.get('/api/experiences', params=params).json()) == 1
    assert client.get('/api/experiences', params={**params, 'verified_only': True}).json() == []
    assert client.get('/api/experiences', params={**params, 'group_size': 5, 'total_budget_vnd': 999999}).json() == []
    assert client.get('/api/experience-search', params={**params, 'q': 'Paper', 'verified_only': True}).json()['items'] == []


def test_verified_journey_links_sources_selects_experience_and_plans_return_leg(client, db_session, sample_experience, monkeypatch):
    monkeypatch.setattr(settings, 'routing_provider', 'mock')
    slot = add_slot(db_session, sample_experience)
    poi = sample_experience.poi
    now = datetime.now(timezone.utc)
    for kind, target in [('poi', poi), ('experience', sample_experience), ('slot', slot)]:
        if kind != 'slot': target.verification_status = 'verified'
        db_session.add(Evidence(target_type=kind, target_id=target.id, target_revision=1,
            source_uri=f'https://example.org/{kind}', source_type='official_website',
            fields_covered=list(REQUIRED_FIELDS[kind]), verification_status='verified',
            observed_at=now - timedelta(hours=1), expires_at=now + timedelta(days=1)))
    slot.confirmed_at = now - timedelta(hours=1)
    slot.expires_at = now + timedelta(days=1)
    db_session.commit()
    monkeypatch.setattr(models_3d, '_read_calibrations', lambda: {'test': model_for(poi)})
    context = client.get('/api/journey/landmarks/test').json()
    assert context['verified'] and context['sources'][0]['observed_at']
    assert context['description'] is None  # Description is not covered by approved evidence.
    assert context['experiences'][0]['id'] == sample_experience.id
    status = client.get('/api/journey/pilot').json()
    assert status['ready_experiences'] == 1
    response = client.post('/api/itineraries/plan', json={
        'require_verified': True, 'start_at': '2030-10-01T01:00:00Z', 'end_at': '2030-10-01T09:00:00Z',
        'group_size': 2, 'budget_vnd': 200000, 'transport_mode': 'walking',
        'locked_experience_ids': [sample_experience.id], 'intent_weights': {'handicraft': 1},
        'origin_latitude': poi.latitude, 'origin_longitude': poi.longitude,
        'destination_latitude': poi.latitude, 'destination_longitude': poi.longitude,
    })
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan['estimated_cost_vnd'] <= 200000
    assert plan['stops'][0]['experience_id'] == sample_experience.id
    assert plan['estimated_return_at'] <= plan['return_deadline']
    assert len(plan['routes']) == 2
    assert 'VERIFIED_DATA' in plan['explanation']['reason_codes']


def test_verified_planner_does_not_silently_use_demo(client, db_session, sample_experience):
    add_slot(db_session, sample_experience)
    response = client.post('/api/itineraries/plan', json={
        'require_verified': True, 'start_at': '2030-10-01T01:00:00Z', 'end_at': '2030-10-01T09:00:00Z',
        'group_size': 2, 'budget_vnd': 200000,
    })
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'VERIFIED_CATALOG_EMPTY'


def test_demo_itinerary_reload_does_not_fall_back_to_mock_routing(client, db_session, sample_experience, monkeypatch):
    monkeypatch.setattr(settings, 'routing_provider', 'goong')
    monkeypatch.setattr(settings, 'goong_api_key', None)
    add_slot(db_session, sample_experience)
    poi = sample_experience.poi
    response = client.post('/api/itineraries/plan', json={
        'routing_mode': 'demo', 'start_at': '2030-10-01T01:00:00Z', 'end_at': '2030-10-01T09:00:00Z',
        'group_size': 2, 'budget_vnd': 200000, 'transport_mode': 'walking',
        'locked_experience_ids': [sample_experience.id],
        'origin_latitude': poi.latitude, 'origin_longitude': poi.longitude,
        'destination_latitude': poi.latitude, 'destination_longitude': poi.longitude,
    })
    assert response.status_code == 200, response.text
    plan = response.json()
    assert 'MOCK_ROUTING' in plan['explanation']['reason_codes']
    assert all(len(route['geometry']) >= 2 for route in plan['routes'])
    assert plan['routes'][0]['geometry'][0] == [poi.latitude, poi.longitude]
    # Existing itineraries may have been created with the old demo routing mode.
    # Reload must use the configured provider and never re-install the mock provider.
    restored = client.get('/api/itineraries/' + plan['itinerary_id'])
    if restored.status_code == 200:
        assert all(route['provider'] != 'mock' for route in restored.json()['routes'])
    else:
        assert restored.status_code in {502, 503}
