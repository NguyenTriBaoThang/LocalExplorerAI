from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.models.entities import Evidence
from app.repositories.experience_repository import ExperienceRepository
from app.services.evidence_service import REQUIRED_FIELDS
from scripts.adapt_legacy_demo_catalog import adapt_poi


def test_legacy_approval_is_demo_not_operational_evidence(db_session, sample_experience, monkeypatch):
    poi = sample_experience.poi
    poi.verification_status = 'verified'
    poi.details = {'source_url': 'https://example.org/venue', 'venue_facts': {'public_hours': '09:00–17:00'}}
    now = datetime.now(timezone.utc)
    db_session.add(Evidence(source_uri='https://example.org/venue', source_type='official_website',
        target_type='poi', target_id=poi.id, target_revision=poi.data_revision,
        fields_covered=['name', 'full_address', 'latitude', 'longitude', 'category'],
        verification_status='approved', observed_at=now, expires_at=now + timedelta(days=1)))
    db_session.flush()
    assert adapt_poi(db_session, poi, {'verification_status': 'verified'}, {})
    db_session.flush()
    assert poi.verification_status == 'simulated'
    assert poi.details['legacy_import']['verification_status'] == 'verified'
    assert poi.source_url == 'https://example.org/venue'
    assert poi.opening_hours == '09:00–17:00'
    assert not adapt_poi(db_session, poi, {'verification_status': 'verified'}, {})
    monkeypatch.setattr(settings, 'real_data_only', False)
    assert ExperienceRepository(db_session).get_poi(poi.id) is poi
    monkeypatch.setattr(settings, 'real_data_only', True)
    assert ExperienceRepository(db_session).get_poi(poi.id) is None


def test_current_verified_data_is_not_downgraded(db_session, sample_experience):
    poi = sample_experience.poi
    poi.verification_status = 'verified'
    now = datetime.now(timezone.utc)
    db_session.add(Evidence(source_uri='https://example.org/venue', source_type='official_website',
        target_type='poi', target_id=poi.id, target_revision=poi.data_revision,
        fields_covered=sorted(REQUIRED_FIELDS['poi']), verification_status='verified',
        observed_at=now, expires_at=now + timedelta(days=1)))
    db_session.flush()
    adapt_poi(db_session, poi, {'verification_status': 'verified'}, {})
    assert poi.verification_status == 'verified'
