"""Partner self-registration, the review gate on the provider portal, and the admin's user/partner management."""

from app.models.entities import AuditLog, Provider, User
from app.repositories.experience_repository import ExperienceRepository
from tests.helpers import make_user, sign_in

APPLICATION = {
    "business_name": "Xưởng gốm Lái Thiêu", "business_type": "household", "description": "Lớp nặn gốm cho khách",
    "contact_phone": "0901234567", "address": "12 Đường Gốm, Thuận An", "tax_code": "0312345678",
    "website": "https://gom.example.test", "document_urls": ["https://files.example.test/giay-phep.pdf"],
}
SLOT = {"start_at": "2030-10-01T09:00:00+07:00", "end_at": "2030-10-01T10:00:00+07:00",
        "capacity_total": 8, "available_reported": 8, "expires_at": "2030-09-30T09:00:00+07:00"}


def _register(client, email="partner@example.test"):
    return client.post("/api/auth/partner/register", json={
        "email": email, "display_name": "Chủ xưởng", "password": "gom-dat-nung-lua-xanh-2030", "application": APPLICATION,
    })


def test_partner_registration_creates_a_pending_provider_and_signs_in(client, db_session):
    response = _register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "provider" and body["provider_id"]
    provider = db_session.get(Provider, body["provider_id"])
    assert provider.verification_status == "pending" and provider.applied_at is not None
    assert provider.name == "Xưởng gốm Lái Thiêu" and provider.contact_email == "partner@example.test"
    me = client.get("/api/provider/me")
    assert me.status_code == 200
    assert me.json()["verification_status"] == "pending" and me.json()["can_publish"] is False


def test_partner_registration_rejects_a_taken_email(client, db_session):
    assert _register(client, "taken@example.test").status_code == 201
    client.cookies.clear()
    assert _register(client, "taken@example.test").status_code == 409


def test_pending_partner_can_read_but_not_publish(client, db_session, sample_experience):
    provider = Provider(name="Pending partner", verification_status="pending", is_active=True)
    db_session.add(provider)
    db_session.commit()
    sample_experience.provider_id = provider.id
    db_session.commit()
    sign_in(client, make_user(db_session, "provider", provider_id=provider.id))

    assert client.get("/api/provider/experiences").status_code == 200
    blocked = client.post(f"/api/provider/experiences/{sample_experience.id}/slots", json=SLOT)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "PROVIDER_NOT_APPROVED"


def test_admin_approves_and_the_partner_can_publish(client, db_session):
    provider_id = _register(client).json()["provider_id"]
    client.cookies.clear()
    admin = make_user(db_session, "admin")
    sign_in(client, admin)

    queue = client.get("/api/admin/providers", params={"status": "pending"})
    assert [row["id"] for row in queue.json()] == [provider_id]
    assert queue.headers["X-Total-Count"] == "1"
    assert client.get("/api/admin/dashboard").json()["pending_partner_applications"] == 1
    approved = client.post(f"/api/admin/providers/{provider_id}/decision", json={"action": "approve"})

    assert approved.status_code == 200
    provider = db_session.get(Provider, provider_id)
    assert provider.verification_status == "verified" and provider.reviewed_by == admin.id
    assert db_session.query(AuditLog).filter_by(action="provider.approve", target_id=provider_id).count() == 1
    partner = db_session.query(User).filter_by(provider_id=provider_id).one()
    sign_in(client, partner)
    assert client.get("/api/provider/me").json()["can_publish"] is True


def test_rejection_needs_a_reason_and_the_partner_can_resubmit(client, db_session):
    provider_id = _register(client).json()["provider_id"]
    partner = db_session.query(User).filter_by(provider_id=provider_id).one()
    client.cookies.clear()
    sign_in(client, make_user(db_session, "admin"))

    assert client.post(f"/api/admin/providers/{provider_id}/decision", json={"action": "reject"}).status_code == 422
    assert client.post(f"/api/admin/providers/{provider_id}/decision", json={"action": "reject", "note": "Thiếu giấy phép"}).status_code == 200
    assert client.post(f"/api/admin/providers/{provider_id}/decision", json={"action": "suspend", "note": "x"}).status_code == 409

    sign_in(client, partner)
    assert client.get("/api/provider/me").json()["review_note"] == "Thiếu giấy phép"
    resubmitted = client.put("/api/provider/me/application", json={**APPLICATION, "business_license_no": "GP-001"})
    assert resubmitted.status_code == 200
    assert resubmitted.json()["verification_status"] == "pending"
    assert resubmitted.json()["business_license_no"] == "GP-001"


def test_suspending_a_partner_hides_its_experiences_and_blocks_writes(client, db_session, sample_experience):
    repository = ExperienceRepository(db_session)
    assert sample_experience.id in {item.id for item in repository.list_experiences()}
    partner = make_user(db_session, "provider", provider_id=sample_experience.provider_id)
    sign_in(client, make_user(db_session, "admin"))

    response = client.post(f"/api/admin/providers/{sample_experience.provider_id}/decision", json={"action": "suspend", "note": "Khiếu nại"})

    assert response.status_code == 200
    db_session.expire_all()
    assert sample_experience.id not in {item.id for item in repository.list_experiences()}
    assert repository.get_experience(sample_experience.id) is None
    sign_in(client, partner)
    assert client.get("/api/provider/me").json()["verification_status"] == "suspended"
    assert client.post(f"/api/provider/experiences/{sample_experience.id}/slots", json=SLOT).json()["error"]["code"] == "PROVIDER_NOT_APPROVED"


def test_traveler_can_apply_to_become_a_partner(client, db_session):
    traveler = make_user(db_session, "traveler")
    sign_in(client, traveler)

    response = client.post("/api/auth/partner/apply", json=APPLICATION)

    assert response.status_code == 201
    assert response.json()["role"] == "provider"
    db_session.refresh(traveler)
    assert db_session.get(Provider, traveler.provider_id).verification_status == "pending"
    assert client.get("/api/provider/me").status_code == 200  # the fresh session carries the new role
    assert client.post("/api/auth/partner/apply", json=APPLICATION).status_code == 409


def test_admin_user_search_detail_and_session_revocation(client, db_session):
    admin = make_user(db_session, "admin")
    target = make_user(db_session, "traveler")
    target.display_name = "Nguyễn Văn Tìm"
    db_session.commit()
    make_user(db_session, "traveler")
    sign_in(client, admin)

    found = client.get("/api/admin/users", params={"q": "Tìm", "role": "traveler"})
    assert [row["id"] for row in found.json()] == [target.id]
    assert found.headers["X-Total-Count"] == "1"
    assert client.get(f"/api/admin/users/{target.id}").json()["email"] == target.email

    old_version = target.token_version
    assert client.post(f"/api/admin/users/{target.id}/revoke-sessions").status_code == 204
    db_session.refresh(target)
    assert target.token_version == old_version + 1
    assert client.post(f"/api/admin/users/{admin.id}/revoke-sessions").status_code == 409


def test_partner_and_traveler_cannot_use_admin_partner_management(client, db_session, sample_experience):
    sign_in(client, make_user(db_session, "provider", provider_id=sample_experience.provider_id))
    assert client.get("/api/admin/providers").status_code == 403
    assert client.post(f"/api/admin/providers/{sample_experience.provider_id}/decision", json={"action": "approve"}).status_code == 403
