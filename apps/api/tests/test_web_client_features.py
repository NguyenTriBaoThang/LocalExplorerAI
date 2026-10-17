"""Public data the traveler web needs from the portal: partner profile page and ratings on experiences."""

from app.models.entities import ExperienceReview, Provider
from tests.helpers import make_user
from tests.test_portal_platform import _attended_booking


def _review(db_session, experience, rating, status="published"):
    traveler = make_user(db_session, "traveler")
    booking = _attended_booking(db_session, experience, traveler)
    db_session.add(ExperienceReview(experience_id=experience.id, provider_id=experience.provider_id, booking_id=booking.id,
                                    user_id=traveler.id, rating=rating, comment="", status=status))
    db_session.commit()


def test_experiences_carry_their_published_rating(client, db_session, sample_experience):
    listed = client.get("/api/experiences").json()[0]
    assert listed["rating_average"] is None and listed["rating_count"] == 0
    _review(db_session, sample_experience, 5)
    _review(db_session, sample_experience, 4)
    _review(db_session, sample_experience, 1, status="hidden")      # hidden reviews never count
    for item in (client.get("/api/experiences").json()[0], client.get(f"/api/experiences/{sample_experience.id}").json()):
        assert item["rating_count"] == 2 and item["rating_average"] == 4.5


def test_partner_profile_is_public_and_shows_only_public_fields(client, db_session, sample_experience):
    provider = db_session.get(Provider, sample_experience.provider_id)
    provider.description, provider.website, provider.contact_email = "Xưởng giấy thủ công", "https://example.com", "hi@example.com"
    provider.tax_code, provider.business_license_no, provider.review_note = "0312345678", "GPKD-1", "internal: looked fine"
    db_session.commit()
    _review(db_session, sample_experience, 5)
    client.cookies.clear()

    response = client.get(f"/api/partners/{provider.slug}")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == provider.name and body["website"] == "https://example.com" and body["description"] == "Xưởng giấy thủ công"
    assert body["rating_average"] == 5.0 and body["rating_count"] == 1
    assert [e["id"] for e in body["experiences"]] == [sample_experience.id]
    assert body["experiences"][0]["provider_slug"] == provider.slug and body["experiences"][0]["provider_name"] == provider.name
    for private in ("tax_code", "business_license_no", "review_note", "document_urls", "portal_access_key", "application_note"):
        assert private not in body
    assert "0312345678" not in response.text and "internal" not in response.text


def test_partner_profile_hides_unapproved_and_suspended_partners(client, db_session, sample_experience):
    provider = db_session.get(Provider, sample_experience.provider_id)
    for status, active in (("pending", True), ("rejected", True), ("suspended", True), ("verified", False)):
        provider.verification_status, provider.is_active = status, active
        db_session.commit()
        assert client.get(f"/api/partners/{provider.slug}").status_code == 404, (status, active)
    provider.verification_status, provider.is_active = "verified", True
    db_session.commit()
    assert client.get(f"/api/partners/{provider.slug}").status_code == 200
    assert client.get("/api/partners/does-not-exist").status_code == 404


def test_partner_directory_lists_only_public_partners_with_open_experiences(client, db_session, sample_experience):
    provider = db_session.get(Provider, sample_experience.provider_id)
    _review(db_session, sample_experience, 4)
    client.cookies.clear()
    rows = client.get("/api/partners").json()
    assert [r["slug"] for r in rows] == [provider.slug]
    row = rows[0]
    assert row["experience_count"] == 1 and row["min_price_vnd"] == sample_experience.price_vnd
    assert row["rating_average"] == 4.0 and row["rating_count"] == 1 and row["categories"] == [sample_experience.poi.category]
    assert client.get("/api/partners", params={"q": "paper-nothing-matches"}).json() == []
    assert len(client.get("/api/partners", params={"q": provider.name[:4]}).json()) == 1

    provider.verification_status = "suspended"
    db_session.commit()
    assert client.get("/api/partners").json() == []                     # hidden together with the profile page
    provider.verification_status, provider.is_active = "verified", False
    db_session.commit()
    assert client.get("/api/partners").json() == []


def test_partner_edits_report_that_evidence_was_voided(client, db_session, sample_experience):
    from tests.helpers import sign_in
    partner = make_user(db_session, "provider", provider_id=sample_experience.provider_id)
    sign_in(client, partner)
    current = client.get("/api/provider/experiences").json()[0]
    payload = {k: current[k] for k in ("name", "description", "poi_id", "intent_tags", "duration_min", "price_vnd") if k in current}
    payload.update(title=current.get("title") or current["name"], primary_intent="thủ_công")
    response = client.patch(f"/api/provider/experiences/{sample_experience.id}", json={**payload, "indoor": True, "price_basis": "per_person"})
    assert response.status_code == 200, response.text
    assert response.json()["evidence_invalidated"] is True


def test_me_lists_the_permissions_of_the_signed_in_role(client, db_session):
    from tests.helpers import sign_in
    admin = make_user(db_session, "admin")
    sign_in(client, admin)
    me = client.get("/api/auth/me").json()
    assert "admin:integrations" in me["permissions"] and "account:read" in me["permissions"]
    traveler = make_user(db_session, "traveler")
    sign_in(client, traveler)
    assert "admin:integrations" not in client.get("/api/auth/me").json()["permissions"]


def test_admin_partner_tabs_treat_legacy_demo_partners_as_approved(client, db_session, sample_experience):
    from tests.helpers import sign_in
    demo = db_session.get(Provider, sample_experience.provider_id)
    assert demo.verification_status in {"mock", "simulated"}           # the legacy value the public site already shows
    pending = Provider(name="Waiting Co", verification_status="pending")
    rejected = Provider(name="Nope Co", verification_status="rejected")
    db_session.add_all([pending, rejected])
    db_session.commit()
    sign_in(client, make_user(db_session, "admin"))

    approved = client.get("/api/admin/providers", params={"status": "verified"}).json()
    assert [row["id"] for row in approved] == [demo.id]                 # the demo partner is listed under "Đã duyệt"
    counts = client.get("/api/admin/providers/counts").json()
    assert counts == {"pending": 1, "verified": 1, "rejected": 1, "suspended": 0, "all": 3}
    assert [row["name"] for row in client.get("/api/admin/providers", params={"status": "pending"}).json()] == ["Waiting Co"]

    sign_in(client, make_user(db_session, "traveler"))
    assert client.get("/api/admin/providers/counts").status_code == 403
