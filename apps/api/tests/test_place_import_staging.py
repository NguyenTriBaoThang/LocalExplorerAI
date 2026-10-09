from app.models.entities import PlaceImportBatch, PlaceImportCandidate, User
from app.services.auth_service import create_session_token
from scripts.import_place_candidates import candidate_flags, make_quality_summary


def test_admin_can_review_staged_place_source_without_publishing(client, db_session):
    admin = User(email="place-import-admin@example.test", display_name="Admin", role="admin")
    batch = PlaceImportBatch(
        source_name="places.xlsx",
        source_sha256="a" * 64,
        worksheet_name="Sai_Gon",
        record_count=1,
        quality_summary={"address_missing": 1},
    )
    candidate = PlaceImportCandidate(
        batch=batch,
        external_id="sg-001",
        source_row=2,
        name="Example place",
        kind="tham-quan",
        raw_payload={"lat": 10.7, "lon": 106.6},
        quality_flags=["address_missing", "coordinates_reused"],
        review_status="needs_enrichment",
    )
    db_session.add_all([admin, batch, candidate])
    db_session.commit()
    client.cookies.set("le_session", create_session_token(admin.id))

    batches = client.get("/api/admin/place-imports")
    rows = client.get(f"/api/admin/place-imports/{batch.id}/candidates")

    assert batches.status_code == 200
    assert batches.json()[0]["record_count"] == 1
    assert rows.status_code == 200
    assert rows.json()[0]["quality_flags"] == ["address_missing", "coordinates_reused"]
    assert rows.json()[0]["review_status"] == "needs_enrichment"
    assert rows.json()[0]["target_poi_id"] is None
    assert rows.json()[0]["suggested_labels"]["label_status"] == "suggested_from_source"
    assert rows.json()[0]["suggested_labels"]["poi_type"] == "sightseeing"
    assert rows.json()[0]["suggested_labels"]["hands_on"] is None


def test_place_import_queue_is_admin_only(client, db_session):
    traveler = User(email="place-import-traveler@example.test", display_name="Traveler", role="traveler")
    db_session.add(traveler)
    db_session.commit()
    client.cookies.set("le_session", create_session_token(traveler.id))

    response = client.get("/api/admin/place-imports")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ROLE_FORBIDDEN"


def test_ai_tool_target_list_is_admin_only_and_does_not_expose_account_data(client, db_session, sample_experience):
    admin = User(email="ai-tools-admin@example.test", display_name="Admin", role="admin")
    db_session.add(admin)
    db_session.commit()
    client.cookies.set("le_session", create_session_token(admin.id))

    response = client.get("/api/admin/ai/targets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["experiences"][0]["id"] == sample_experience.id
    assert "email" not in payload["experiences"][0]
    assert all("user_id" not in itinerary for itinerary in payload["itineraries"])


def test_import_quality_distinguishes_geocoded_address_and_unverified_price():
    record = {
        "ext_id": "sg-verified-fields",
        "name": "Example place",
        "kind": "tham-quan",
        "lat": 10.7,
        "lon": 106.6,
        "price_vnd": 40_000,
        "price_basis": "per_person",
        "price_status": "source_file_value_unverified",
        "address": "Example Street, Ho Chi Minh City",
        "address_status": "reverse_geocoded_needs_POI_confirmation",
        "open_hours": {"open": "08:00", "close": "17:00"},
        "source": "https://example.test/place",
        "verified": True,
        "observed_at": None,
        "evidence_status": "field_level_evidence_pending_not_publishable",
    }

    flags = candidate_flags(record, set())
    summary = make_quality_summary([(record, 2)], set())

    assert "address_missing" not in flags
    assert "address_geocode_needs_confirmation" in flags
    assert "price_basis_missing" not in flags
    assert "price_amount_unverified" in flags
    assert "verified_flag_unsubstantiated" in flags
    assert "field_level_evidence_pending" in flags
    assert summary["address_missing"] == 0
    assert summary["price_basis_missing"] == 0
    assert summary["address_geocode_needs_confirmation"] == 1
    assert summary["price_amount_unverified"] == 1
    assert summary["verified_flag_unsubstantiated"] == 1
    assert summary["field_level_evidence_pending"] == 1
