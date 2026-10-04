from app.api.dependencies import get_current_user
from app.core.config import settings
from app.models.entities import AuditLog, IntegrationSecret, User
from cryptography.fernet import Fernet
from sqlalchemy import select
from app.api.dependencies import get_llm_provider
from uuid import uuid4


def _admin_session(client, db_session):
    admin = User(id=str(uuid4()), email=f"admin-{uuid4().hex[:8]}@example.org", display_name="Admin", role="admin")
    db_session.add(admin)
    db_session.commit()
    client.app.dependency_overrides[get_current_user] = lambda: admin


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
