from datetime import datetime

from app.core.config import settings
from app.models.entities import DecisionLog, Experience, Itinerary, ItineraryStop, ItineraryVersion
from tests.conftest import add_slot


def payload(poi):
    return {
        'start_at': '2030-10-01T01:00:00Z', 'end_at': '2030-10-01T09:00:00Z',
        'group_size': 2, 'budget_vnd': 400000, 'transport_mode': 'motorcycle',
        'intent_weights': {'handicraft': 1},
        'origin_latitude': poi.latitude, 'origin_longitude': poi.longitude,
        'destination_latitude': poi.latitude, 'destination_longitude': poi.longitude,
    }


def test_five_distinct_previews_do_not_write_and_choice_is_revalidated(client, db_session, sample_experience, monkeypatch):
    monkeypatch.setattr(settings, 'routing_provider', 'mock')
    add_slot(db_session, sample_experience)
    for index in range(5):
        activity = Experience(poi=sample_experience.poi, provider=sample_experience.provider,
            name=f'Workshop {index}', description='Fixture', intent_tags=['handicraft'],
            duration_min=60, indoor=True, price_basis='per_person', price_vnd=50000 + index * 10000,
            verification_status='simulated')
        db_session.add(activity)
        db_session.flush()
        add_slot(db_session, activity)
    response = client.post('/api/itineraries/suggestions', json=payload(sample_experience.poi))
    assert response.status_code == 200, response.text
    options = response.json()['options']
    assert len(options) == 5
    signatures = {tuple(s['experience_id'] for s in o['preview']['stops']) for o in options}
    assert len(signatures) == 5
    for option in options:
        plan = option['preview']
        assert plan['estimated_cost_vnd'] <= 400000
        assert datetime.fromisoformat(plan['estimated_return_at']) <= datetime.fromisoformat(plan['return_deadline'])
        assert option['request']['routing_mode'] == 'configured'
    for model in (Itinerary, ItineraryStop, ItineraryVersion, DecisionLog):
        assert db_session.query(model).count() == 0
    selected = options[0]
    chosen = client.post('/api/itineraries/plan', json=selected['request'])
    assert chosen.status_code == 200, chosen.text
    assert [s['experience_id'] for s in chosen.json()['stops']] == [s['experience_id'] for s in selected['preview']['stops']]
    assert db_session.query(Itinerary).count() == 1
    # A choice whose capacity has changed cannot be booked as if the preview were current.
    slot = sample_experience.slots[0]
    slot.available_reported = 0
    db_session.commit()
    pinned = {**payload(sample_experience.poi), 'locked_experience_ids': [sample_experience.id]}
    assert client.post('/api/itineraries/plan', json=pinned).status_code == 422


def test_small_catalog_returns_one_option_preserving_user_pins(client, db_session, sample_experience, monkeypatch):
    monkeypatch.setattr(settings, 'routing_provider', 'mock')
    add_slot(db_session, sample_experience)
    request = {**payload(sample_experience.poi), 'locked_experience_ids': [sample_experience.id], 'locked_poi_ids': [sample_experience.poi_id]}
    response = client.post('/api/itineraries/suggestions', json=request)
    assert response.status_code == 200, response.text
    assert response.json()['returned_count'] == 1
    for option in response.json()['options']:
        assert option['request']['locked_experience_ids'] == request['locked_experience_ids']
        assert option['request']['locked_poi_ids'] == request['locked_poi_ids']
        assert option['preview']['stops'][0]['experience_id'] == sample_experience.id


def test_suggestions_do_not_relax_budget_or_capacity(client, db_session, sample_experience, monkeypatch):
    monkeypatch.setattr(settings, 'routing_provider', 'mock')
    add_slot(db_session, sample_experience, available=1)
    response = client.post('/api/itineraries/suggestions', json=payload(sample_experience.poi))
    assert response.status_code == 422
    assert db_session.query(Itinerary).count() == 0
    assert client.post('/api/itineraries/suggestions', json={**payload(sample_experience.poi), 'budget_vnd': 0}).status_code == 422


def test_suggestions_release_only_unfeasible_user_pins_with_clear_label(client, db_session, sample_experience, monkeypatch):
    monkeypatch.setattr(settings, 'routing_provider', 'mock')
    add_slot(db_session, sample_experience, available=0, status='full')
    alternative = Experience(poi=sample_experience.poi, provider=sample_experience.provider,
        name='Available workshop', description='Fixture', intent_tags=['handicraft'],
        duration_min=60, indoor=True, price_basis='per_person', price_vnd=50000,
        verification_status='simulated')
    db_session.add(alternative)
    db_session.flush()
    add_slot(db_session, alternative)
    request = {**payload(sample_experience.poi), 'locked_experience_ids': [sample_experience.id]}
    response = client.post('/api/itineraries/suggestions', json=request)
    assert response.status_code == 200, response.text
    option = response.json()['options'][0]
    assert option['relaxed_experience_names'] == [sample_experience.name]
    assert option['preview']['stops'][0]['experience_id'] == alternative.id
    assert option['request']['locked_experience_ids'] == []
    assert db_session.query(Itinerary).count() == 0
