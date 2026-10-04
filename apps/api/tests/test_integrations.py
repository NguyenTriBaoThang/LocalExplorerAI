from app.api.dependencies import get_current_user
from app.core.config import settings
from app.models.entities import AuditLog, Evidence, IntegrationSecret, PlaceImportBatch, PlaceImportCandidate, POI, User
from cryptography.fernet import Fernet
from sqlalchemy import select
from app.api.dependencies import get_llm_provider
from app.api.routes import admin as admin_routes
from app.services.evidence_service import entity_is_operationally_verified
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4


def _admin_session(client, db_session):
    admin = User(id=str(uuid4()), email=f"admin-{uuid4().hex[:8]}@example.org", display_name="Admin", role="admin")
    db_session.add(admin)
    db_session.commit()
    client.app.dependency_overrides[get_current_user] = lambda: admin
    return admin


def test_admin_integration_catalog_never_returns_secret_values(client, db_session, monkeypatch):
    _admin_session(client, db_session)
    monkeypatch.setattr(settings, "goong_api_key", "goong-test-secret")
    monkeypatch.setattr(settings, "gemini_api_key", "gemini-test-secret")

    response = client.get("/api/admin/integrations")

    assert response.status_code == 200, response.text
    catalog = {group["service"]: group for group in response.json()}
    goong_key = next(field for field in catalog["routing"]["fields"] if field["key"] == "goong_api_key")
    gemini_key = next(field for field in catalog["ai"]["fields"] if field["key"] == "gemini_api_key")
    assert goong_key["configured"] is True
    assert goong_key["value"] is None
    assert gemini_key["configured"] is True
    assert gemini_key["value"] is None
    assert "goong-test-secret" not in response.text
    assert "gemini-test-secret" not in response.text


def test_admin_integration_settings_are_allowlisted_and_validated(client, db_session):
    _admin_session(client, db_session)
    unknown = client.put("/api/admin/integrations/not-a-service", json={"values": {"api_key": "value"}})
    assert unknown.status_code == 404

    unsupported = client.put("/api/admin/integrations/payments", json={"values": {"provider": "untrusted"}})
    assert unsupported.status_code == 422

    injected_url = client.put("/api/admin/integrations/routing", json={"values": {"goong_api_base_url": "javascript:alert(1)"}})
    assert injected_url.status_code == 422


def test_mock_routing_cannot_be_saved_in_real_only_mode(client, db_session, monkeypatch):
    _admin_session(client, db_session)
    monkeypatch.setattr(settings, "real_data_only", True)

    response = client.put("/api/admin/integrations/routing", json={"values": {"provider": "mock"}})

    assert response.status_code == 422
    assert "REAL_DATA_ONLY" in response.json()["error"]["message"]


def test_admin_secret_update_is_encrypted_and_never_read_back(client, db_session, monkeypatch):
    _admin_session(client, db_session)
    monkeypatch.setattr(settings, "integration_secrets_key", Fernet.generate_key().decode("ascii"))
    secret = "gemini-secret-do-not-return"

    saved = client.put("/api/admin/integrations/ai", json={"values": {"gemini_api_key": secret, "provider": "gemini"}})
    assert saved.status_code == 200, saved.text
    row = db_session.scalar(select(IntegrationSecret).where(
        IntegrationSecret.service == "ai", IntegrationSecret.config_key == "gemini_api_key",
    ))
    assert row is not None
    assert secret not in row.encrypted_value
    assert Fernet(settings.integration_secrets_key.encode()).decrypt(row.encrypted_value.encode()).decode() == secret
    assert secret not in saved.text
    saved_field = next(field for field in next(group for group in saved.json() if group["service"] == "ai")["fields"] if field["key"] == "gemini_api_key")
    assert saved_field["configured"] is True and saved_field["value"] is None
    provider = get_llm_provider(db_session)
    assert provider.model_name == settings.gemini_model
    assert provider.api_key == secret
    audit = db_session.scalar(select(AuditLog).where(AuditLog.action == "integration.settings_updated"))
    assert secret not in str(audit.details)


def test_admin_cannot_store_secrets_without_master_key(client, db_session, monkeypatch):
    _admin_session(client, db_session)
    monkeypatch.setattr(settings, "integration_secrets_key", None)
    response = client.put("/api/admin/integrations/ai", json={"values": {"gemini_api_key": "secret"}})
    assert response.status_code == 503


def test_legacy_bot_settings_refuse_plaintext_credentials(client, db_session):
    _admin_session(client, db_session)
    for patch in ({"bot_token": "never-store-this"}, {"webhook_url": "https://example.org/hook?token=secret"}):
        response = client.post("/api/admin/bot/config", json=patch)
        assert response.status_code == 422
        assert "plaintext" in response.text.lower()
        assert "never-store-this" not in response.text
        assert "token=secret" not in response.text


def test_admin_ai_connection_test_reports_safe_status(client, db_session, monkeypatch):
    _admin_session(client, db_session)

    class FakeProvider:
        model_name = "gemini-test"

        def generate(self, system_prompt, user_input, schema):
            assert user_input == {"check": "connection"}
            return {"ok": True}

    monkeypatch.setattr(admin_routes, "get_llm_provider", lambda _db: FakeProvider())
    response = client.post("/api/admin/integrations/ai/test")

    assert response.status_code == 200
    assert response.json()["status"] == "connected"
    assert response.json()["ok"] is True
    assert "secret" not in response.text.lower()


def test_admin_routing_connection_test_checks_geocoding_and_directions(client, db_session, monkeypatch):
    _admin_session(client, db_session)

    class FakeGeocoder:
        def forward(self, address, limit):
            assert address == "Ho Chi Minh City, Vietnam" and limit == 1
            return SimpleNamespace(results=[object()])

    class FakeRouter:
        def get_route(self, origin, destination, mode):
            assert origin == (10.7769, 106.7009)
            assert destination == (10.7829, 106.6951)
            assert mode == "motorcycle"
            return SimpleNamespace(distance_m=1000, duration_min=5)

    monkeypatch.setattr(admin_routes, "make_geocoding_provider", lambda _db: FakeGeocoder())
    monkeypatch.setattr(admin_routes, "make_routing_provider", lambda _db: FakeRouter())
    response = client.post("/api/admin/integrations/routing/test")

    assert response.status_code == 200
    assert response.json()["status"] == "connected"
    assert response.json()["ok"] is True


def test_admin_can_promote_candidate_only_with_current_full_evidence(client, db_session):
    admin = _admin_session(client, db_session)
    batch = PlaceImportBatch(
        id=str(uuid4()), source_name="places.xlsx", source_sha256=uuid4().hex * 2,
        worksheet_name="Places", imported_by=admin.id, record_count=1, quality_summary={},
    )
    candidate = PlaceImportCandidate(
        id=str(uuid4()), batch=batch, external_id="poi-row-1", source_row=2,
        name="Verified place", kind="culture", raw_payload={"description": "Imported place."},
        quality_flags=["address_missing", "source_url_missing"], review_status="needs_enrichment",
    )
    db_session.add(batch)
    db_session.add(candidate)
    db_session.commit()
    now = datetime.now(timezone.utc)
    fields = ["name", "address", "latitude", "longitude", "category"]
    response = client.post(
        f"/api/admin/place-imports/{batch.id}/candidates/{candidate.id}/promote",
        json={
            "address": "1 Example Street, Ho Chi Minh City",
            "latitude": 10.75,
            "longitude": 106.7,
            "category": "culture",
            "source_uri": "https://example.org/places/1",
            "source_type": "official",
            "source_label": "Official place listing",
            "fields_covered": fields,
            "observed_at": (now - timedelta(days=1)).isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "pending_review"
    poi = db_session.get(POI, response.json()["poi_id"])
    assert poi is not None and poi.verification_status == "pending"
    assert not entity_is_operationally_verified(db_session, "poi", poi)
    evidence = db_session.scalar(select(Evidence).where(Evidence.target_id == poi.id))
    assert evidence is not None and evidence.verification_status == "pending"

    evidence_review = client.patch(f"/api/admin/moderation/evidence/{evidence.id}", json={"action": "approve", "note": "Source checked."})
    assert evidence_review.status_code == 200, evidence_review.text
    poi_review = client.patch(f"/api/admin/moderation/poi/{poi.id}", json={"action": "approve", "note": "Fields checked against evidence."})
    assert poi_review.status_code == 200, poi_review.text
    db_session.refresh(poi)
    assert poi.verification_status == "verified"
    assert entity_is_operationally_verified(db_session, "poi", poi)
