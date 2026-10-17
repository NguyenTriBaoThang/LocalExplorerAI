from uuid import uuid4

from sqlalchemy import select

from app.models.auth_entities import RolePermission
from app.models.entities import AuditLog, RecommendationInteraction
from app.services.rbac_service import invalidate_matrix
from tests.helpers import bearer_for, make_user


def test_dataset_export_uses_current_signing_configuration(monkeypatch):
    import importlib.util
    from pathlib import Path
    import pytest
    from app.core.config import settings

    path = Path(__file__).resolve().parents[3] / 'scripts' / 'build_behavior_ranking_dataset.py'
    spec = importlib.util.spec_from_file_location('behavior_dataset_export', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(settings, 'app_signing_secret', 'local-test-signing-secret-for-export')
    first = module.pseudonymize('customer-a')
    assert len(first) == 32 and first == module.pseudonymize('customer-a')
    assert first != module.pseudonymize('customer-b')
    monkeypatch.setattr(settings, 'app_signing_secret', '')
    with pytest.raises(RuntimeError, match='APP_SIGNING_SECRET'):
        module.pseudonymize('customer-a')


def test_recommendations_enforce_rbac(client, db_session):
    traveler = make_user(db_session, 'traveler')
    provider = make_user(db_session, 'provider')
    assert client.get('/api/recommendations/consent').status_code == 401
    assert client.get('/api/recommendations/consent', headers=bearer_for(provider)).status_code == 403
    assert client.get('/api/recommendations/consent', headers=bearer_for(traveler)).status_code == 200
    grant = db_session.get(RolePermission, ('traveler', 'recommendations:use'))
    db_session.delete(grant)
    db_session.commit()
    invalidate_matrix()
    assert client.get('/api/recommendations/consent', headers=bearer_for(traveler)).status_code == 403


def test_consent_history_and_revocation(client, db_session, sample_experience):
    traveler = make_user(db_session, 'traveler')
    other = make_user(db_session, 'traveler')
    admin = make_user(db_session, 'admin')
    auth = bearer_for(traveler)
    event = {'event_id': str(uuid4()), 'request_id': str(uuid4()), 'experience_id': sample_experience.id,
             'event_type': 'selected', 'position': 0, 'context': {'intent_tags': ['handicraft']}}
    assert client.post('/api/recommendations/interactions', headers=auth, json={'events': [event]}).json()['accepted'] == 0
    consent = {'personalization_enabled': True, 'model_training_enabled': True, 'admin_history_enabled': False}
    assert client.put('/api/recommendations/consent', headers=auth, json=consent).status_code == 200
    assert client.post('/api/recommendations/interactions', headers=auth, json={'events': [event]}).json()['accepted'] == 1
    assert client.post('/api/recommendations/interactions', headers=auth, json={'events': [event]}).json()['accepted'] == 0
    assert not client.get('/api/recommendations/consent', headers=bearer_for(other)).json()['personalization_enabled']
    history_url = f'/api/admin/users/{traveler.id}/history'
    assert client.get(history_url, headers=auth).status_code == 403
    history = client.get(history_url, headers=bearer_for(admin))
    assert history.status_code == 200, history.text
    assert history.json()['behavior_history_visible'] is False
    assert history.json()['behavior_events'] == []
    # Granting consent now must not expose events recorded before that purpose was allowed.
    consent['admin_history_enabled'] = True
    client.put('/api/recommendations/consent', headers=auth, json=consent)
    assert client.get(history_url, headers=bearer_for(admin)).json()['behavior_events'] == []
    new_event = {**event, 'event_id': str(uuid4()), 'request_id': str(uuid4())}
    client.post('/api/recommendations/interactions', headers=auth, json={'events': [new_event]})
    assert len(client.get(history_url, headers=bearer_for(admin)).json()['behavior_events']) == 1
    assert db_session.scalar(select(AuditLog).where(AuditLog.action == 'customer_history_viewed', AuditLog.actor_id == admin.id)) is not None
    consent.update(model_training_enabled=False, admin_history_enabled=False)
    client.put('/api/recommendations/consent', headers=auth, json=consent)
    db_session.expire_all()
    rows = db_session.scalars(select(RecommendationInteraction)).all()
    assert len(rows) == 2
    assert all(row.personalization_eligible and not row.model_training_eligible and not row.admin_history_eligible for row in rows)
    assert client.get(history_url, headers=bearer_for(admin)).json()['behavior_events'] == []
    consent['personalization_enabled'] = False
    client.put('/api/recommendations/consent', headers=auth, json=consent)
    assert db_session.scalars(select(RecommendationInteraction)).all() == []
