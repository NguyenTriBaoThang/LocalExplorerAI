from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.adapters.routing.goong import GoongDirectionsProvider
from app.core.config import settings
from app.models.entities import ExperienceSlot, POI, Provider, User
from app.auth.passwords import hash_password
from tests.helpers import sign_in


def test_catalog_requires_current_sources_and_hides_expired_slot(client, db_session, monkeypatch):
    provider = Provider(name="Source-backed studio", status="active")
    db_session.add(provider)
    db_session.flush()
    provider_user = User(
        id=str(uuid4()), email="source-provider@example.com", display_name="Source Provider",
        role="provider", provider_id=provider.id, is_active=True,
    )
    admin = User(id=str(uuid4()), email="source-admin@example.com", display_name="Admin", role="admin", is_active=True)
    traveler = User(id=str(uuid4()), email="source-traveler@example.com", display_name="Traveler",
                    password_hash=hash_password("long-enough-password"), role="traveler", is_active=True,
                    email_verified_at=datetime.now(timezone.utc))
    db_session.add_all([provider_user, admin, traveler])
    db_session.commit()

    sign_in(client, provider_user)
    poi_response = client.post("/api/provider/pois", json={
        "name": "Verified craft studio",
        "description": "A small workshop",
        "district": "District 1",
        "latitude": 10.775,
        "longitude": 106.7,
        "category": "handicraft",
        "address": "1 Example Street, Ho Chi Minh City",
    })
    assert poi_response.status_code == 201, poi_response.text
    poi_id = poi_response.json()["id"]
    db_poi = db_session.get(POI, poi_id)
    db_poi.details = {
        "opening_hours": "Mo-Su 08:00-17:00",
        "osm_url": "https://www.openstreetmap.org/node/123",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "osm_tags": {"tourism": "museum"},
        "images": [{
            "url": "https://upload.wikimedia.org/example.jpg",
            "source_url": "https://commons.wikimedia.org/wiki/File:Example.jpg",
            "license": "CC BY-SA 4.0",
        }],
    }
    db_session.commit()
    assert any(item["id"] == poi_id for item in client.get("/api/provider/pois").json())

    poi_evidence = client.post("/api/provider/evidence", json={
        "target_type": "poi", "target_id": poi_id,
        "source_uri": "https://example.org/studio/contact",
        "source_type": "official_website", "source_label": "Studio official page",
        "license": "Provider supplied", "fields_covered": ["name", "address", "latitude", "longitude", "category"],
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    })
    assert poi_evidence.status_code == 201, poi_evidence.text
    poi_evidence_id = poi_evidence.json()["id"]

    # Evidence must be reviewed before a catalog row can be approved.
    sign_in(client, admin)
    blocked = client.patch(f"/api/admin/moderation/poi/{poi_id}", json={"action": "approve"})
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "CATALOG_EVIDENCE_INCOMPLETE"
    approved_evidence = client.patch(f"/api/admin/moderation/evidence/{poi_evidence_id}", json={"action": "approve"})
    assert approved_evidence.status_code == 200, approved_evidence.text
    approved_poi = client.patch(f"/api/admin/moderation/poi/{poi_id}", json={"action": "approve"})
    assert approved_poi.status_code == 200, approved_poi.text

    sign_in(client, provider_user)
    experience_response = client.post("/api/provider/experiences", json={
        "poi_id": poi_id, "title": "Hands-on wheel pottery", "description": "Guests shape a clay cup.",
        "primary_intent": "thủ_công",
        "intent_tags": ["handicraft"], "is_hands_on": True, "is_indoor": True,
        "duration_min": 90, "price_vnd": 250000, "price_basis": "per_person",
    })
    assert experience_response.status_code == 201, experience_response.text
    experience_id = experience_response.json()["id"]
    experience_evidence = client.post("/api/provider/evidence", json={
        "target_type": "experience", "target_id": experience_id,
        "source_uri": "https://example.org/studio/workshop",
        "source_type": "official_website", "source_label": "Workshop details",
        "fields_covered": ["title", "description", "primary_intent", "intent_tags", "is_hands_on", "duration_min", "price_vnd", "price_basis"],
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
    })
    assert experience_evidence.status_code == 201, experience_evidence.text
    experience_evidence_id = experience_evidence.json()["id"]

    sign_in(client, admin)
    assert client.patch(f"/api/admin/moderation/evidence/{experience_evidence_id}", json={"action": "approve"}).status_code == 200
    assert client.patch(f"/api/admin/moderation/experience/{experience_id}", json={"action": "approve"}).status_code == 200

    sign_in(client, provider_user)
    slot_start = datetime.now(timezone.utc) + timedelta(days=1)
    slot_response = client.post(f"/api/provider/experiences/{experience_id}/slots", json={
        "start_at": slot_start.isoformat(), "end_at": (slot_start + timedelta(minutes=90)).isoformat(),
        "capacity_total": 8, "available_reported": 5,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
    })
    assert slot_response.status_code == 201, slot_response.text
    provider_evidence = client.get("/api/provider/evidence")
    assert provider_evidence.status_code == 200, provider_evidence.text
    assert len(provider_evidence.json()) == 3

    listing = client.get("/api/experiences")
    assert listing.status_code == 200, listing.text
    record = next(row for row in listing.json() if row["id"] == experience_id)
    assert record["data_mode"] == "real"
    assert record["source_evidence"][0]["source_uri"] == "https://example.org/studio/workshop"
    assert record["slots"][0]["data_mode"] == "real"
    assert record["slots"][0]["confirmed_at"]
    assert record["slots"][0]["expires_at"]
    detail = client.get(f"/api/experiences/{experience_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["data_mode"] == "real"
    assert detail.json()["source_evidence"]
    poi_detail = client.get(f"/api/pois/{poi_id}")
    assert poi_detail.status_code == 200, poi_detail.text
    assert poi_detail.json()["data_mode"] == "real"
    assert poi_detail.json()["source_evidence"]
    assert poi_detail.json()["details"]["opening_hours"] == "Mo-Su 08:00-17:00"
    assert poi_detail.json()["details"]["images"][0]["license"] == "CC BY-SA 4.0"
    assert [item["id"] for item in poi_detail.json()["experiences"]] == [experience_id]

    monkeypatch.setattr(settings, "routing_provider", "goong")
    monkeypatch.setattr(settings, "goong_api_key", "test-goong-key")

    def fake_goong_request(_provider, path, params):
        assert path == "/v2/direction"
        assert params["vehicle"] == "foot"
        return {"status": "OK", "routes": [{"legs": [{
            "distance": {"value": 1_200}, "duration": {"value": 300},
        }]}]}

    monkeypatch.setattr(GoongDirectionsProvider, "_request_json", fake_goong_request)

    trip_start = slot_start - timedelta(hours=1)
    sign_in(client, traveler)
    planned = client.post("/api/itineraries/plan", json={
        "start_at": trip_start.isoformat(), "end_at": (slot_start + timedelta(minutes=110)).isoformat(),
        "group_size": 2, "budget_vnd": 1000000, "transport_mode": "walking",
        "intent_weights": {"thủ_công": 1.0}, "locked_experience_ids": [experience_id],
        "origin_latitude": 10.76, "origin_longitude": 106.68,
        "destination_latitude": 10.78, "destination_longitude": 106.69,
        "origin_label": "Điểm xuất phát", "destination_label": "Điểm trở về",
    })
    assert planned.status_code == 200, planned.text
    planned_stop = planned.json()["stops"][0]
    assert planned.json()["data_mode"] == "real"
    assert "VERIFIED_DATA" in planned.json()["explanation"]["reason_codes"]
    assert len(planned.json()["explanation"]["evidence_refs"]) == 3
    assert planned_stop["data_status"] == "verified"
    assert planned_stop["poi"]["source_evidence"][0]["id"] == poi_evidence_id
    assert planned_stop["source_evidence"][0]["source_uri"] == "https://example.org/studio/workshop"
    assert planned_stop["slot_source_evidence"][0]["target_type"] == "slot"
    assert planned_stop["slot_confirmed_at"]
    assert planned_stop["slot_expires_at"]
    assert len(planned.json()["routes"]) == 2
    assert [route["provider"] for route in planned.json()["routes"]] == [
        "goong_directions_v2", "goong_directions_v2",
    ]
    assert planned.json()["routes"][0]["from_label"] == "Điểm xuất phát"
    assert planned.json()["routes"][-1]["to_label"] == "Điểm trở về"

    hold = client.post("/api/bookings", json={
        "itinerary_id": planned.json()["itinerary_id"],
        "itinerary_stop_id": planned_stop["id"],
        "quantity": 2,
    })
    assert hold.status_code == 201, hold.text
    assert hold.json()["status"] == "pending_provider"
    assert hold.json()["amount_vnd"] == 500000

    client.cookies.clear()
    sign_in(client, provider_user)
    confirmation = client.post(
        f"/api/provider/me/bookings/{hold.json()['id']}/decision",
        json={"action": "accept", "note": "Capacity checked by provider"},
    )
    assert confirmation.status_code == 200, confirmation.text
    assert confirmation.json()["status"] == "awaiting_payment"

    client.cookies.clear()
    sign_in(client, traveler)
    reread = client.get(f"/api/itineraries/{planned.json()['itinerary_id']}")
    assert reread.status_code == 200, reread.text
    assert reread.json()["data_mode"] == "real"
    assert "VERIFIED_DATA" in reread.json()["explanation"]["reason_codes"]

    # Expiration removes a slot from the operational availability surface even if its old status is open.
    slot = db_session.query(ExperienceSlot).filter_by(experience_id=experience_id).one()
    slot.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    listing_after_expiry = client.get("/api/experiences")
    record_after_expiry = next(row for row in listing_after_expiry.json() if row["id"] == experience_id)
    assert record_after_expiry["slots"] == []


def test_provider_edit_invalidates_previously_submitted_evidence(client, db_session, sample_experience):
    provider = sample_experience.provider
    user = User(id=str(uuid4()), email="edit-provider@example.com", display_name="Provider", role="provider", provider_id=provider.id)
    db_session.add(user)
    db_session.commit()
    sign_in(client, user)
    revision = sample_experience.data_revision
    response = client.patch(f"/api/provider/experiences/{sample_experience.id}", json={
        "poi_id": sample_experience.poi_id, "title": "Updated workshop", "description": "Updated detail",
        "primary_intent": "thủ_công",
        "intent_tags": ["handicraft"], "is_hands_on": True, "is_indoor": True,
        "duration_min": 75, "price_vnd": 200000, "price_basis": "per_person",
    })
    assert response.status_code == 200, response.text
    db_session.refresh(sample_experience)
    assert sample_experience.data_revision == revision + 1
    assert sample_experience.verification_status == "pending"
