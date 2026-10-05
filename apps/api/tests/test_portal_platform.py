"""Admin places, site content, page-view analytics and experience reviews (portal <-> traveler web)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.config import settings
from app.models.entities import Booking, ExperienceSlot, PageView, POI
from tests.helpers import make_user, sign_in

PLACE = {"name": "Chợ Bến Thành", "category": "market", "district": "Quận 1", "address": "Lê Lợi, Bến Thành, Quận 1",
         "latitude": 10.7725, "longitude": 106.698, "description": "Chợ biểu tượng", "image_urls": ["/images/skyline.jpg"],
         "opening_hours": "06:00 – 18:00", "ticket_info": "Miễn phí", "tags": ["ẩm thực", " ẩm thực ", "mua sắm"], "is_landmark": True,
         "source_url": "https://vi.wikipedia.org/wiki/Chợ_Bến_Thành"}
BROWSER = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile/15E148 Safari/604.1"}


def _admin(client, db_session):
    user = make_user(db_session, "admin")
    sign_in(client, user)
    return user


def test_admin_publishes_a_place_that_then_appears_in_the_public_catalog(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "real_data_only", True)
    _admin(client, db_session)

    draft = client.post("/api/admin/places", json=PLACE)
    assert draft.status_code == 201 and draft.json()["status"] == "draft"
    assert draft.json()["tags"] == ["ẩm thực", "mua sắm"]
    place_id = draft.json()["id"]
    assert client.get(f"/api/pois/{place_id}").status_code == 404

    published = client.post(f"/api/admin/places/{place_id}/status", json={"action": "publish"})
    assert published.status_code == 200 and published.json()["status"] == "verified"
    public = client.get(f"/api/pois/{place_id}").json()
    assert public["opening_hours"] == "06:00 – 18:00" and public["is_landmark"] is True and public["data_mode"] == "real"

    # Editing a required field moves to a new revision; the editing admin re-vouches so it stays public.
    edited = client.patch(f"/api/admin/places/{place_id}", json={**PLACE, "address": "Lê Lợi, Phường Bến Thành, Quận 1"})
    assert edited.json()["data_revision"] == 2 and edited.json()["status"] == "verified"
    assert client.get(f"/api/pois/{place_id}").status_code == 200

    assert client.post(f"/api/admin/places/{place_id}/status", json={"action": "hide"}).json()["status"] == "hidden"
    assert client.get(f"/api/pois/{place_id}").status_code == 404


def test_publishing_requires_an_https_source(client, db_session):
    _admin(client, db_session)
    place_id = client.post("/api/admin/places", json={**PLACE, "source_url": None}).json()["id"]
    assert client.post(f"/api/admin/places/{place_id}/status", json={"action": "publish"}).json()["error"]["code"] == "SOURCE_REQUIRED"
    assert client.post("/api/admin/places", json={**PLACE, "source_url": "http://insecure.example"}).status_code == 422
    listed = client.get("/api/admin/places", params={"status": "draft"})
    assert listed.headers["X-Total-Count"] == "1"


def test_site_content_admin_crud_and_public_home(client, db_session):
    _admin(client, db_session)
    place = client.post("/api/admin/places", params={"publish": True}, json=PLACE).json()
    draft_place = client.post("/api/admin/places", json={**PLACE, "name": "Nháp"}).json()

    banner = client.post("/api/admin/content/banners", json={"title": "Mùa lễ hội", "image_url": "/images/banner.jpg", "link_url": "/explore"})
    assert banner.status_code == 201
    client.post("/api/admin/content/banners", json={"title": "Tắt", "image_url": "/images/banner.jpg", "is_active": False})
    client.post("/api/admin/content/banners", json={"title": "Hết hạn", "image_url": "/images/banner.jpg",
                                                    "ends_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()})
    assert client.post("/api/admin/content/banners", json={"title": "x", "image_url": "javascript:alert(1)"}).status_code == 422

    first = client.post("/api/admin/content/articles", json={"title": "48 giờ ở Sài Gòn", "status": "published", "body": "# Ngày 1"}).json()
    second = client.post("/api/admin/content/articles", json={"title": "48 giờ ở Sài Gòn"}).json()
    assert first["slug"] == "48-gio-o-sai-gon" and second["slug"] == "48-gio-o-sai-gon-2" and first["published_at"]

    assert client.post("/api/admin/content/collections", json={"title": "x", "place_ids": ["missing"]}).status_code == 422
    client.post("/api/admin/content/collections", json={"title": "Biểu tượng Quận 1", "place_ids": [place["id"], draft_place["id"]]})

    client.cookies.clear()
    home = client.get("/api/content/home").json()
    assert [b["title"] for b in home["banners"]] == ["Mùa lễ hội"]
    assert [a["slug"] for a in home["articles"]] == ["48-gio-o-sai-gon"]
    assert [p["id"] for p in home["collections"][0]["places"]] == [place["id"]]  # the draft place is not shown
    assert client.get("/api/content/articles/48-gio-o-sai-gon").json()["body"] == "# Ngày 1"
    assert client.get("/api/content/articles/48-gio-o-sai-gon-2").status_code == 404  # still a draft


def test_page_views_are_pseudonymous_and_feed_the_admin_report(client, db_session):
    payload = {"visitor_id": "visitor-123456", "session_id": "session-abcdef", "path": "/explore?email=a@b.c", "referrer": "https://www.google.com/search?q=x"}
    assert client.post("/api/analytics/pageview", json=payload, headers=BROWSER).status_code == 204
    assert client.post("/api/analytics/pageview", json={**payload, "path": "/", "referrer": None}, headers=BROWSER).status_code == 204
    client.post("/api/analytics/pageview", json=payload, headers={"User-Agent": "Googlebot/2.1"})
    client.post("/api/analytics/pageview", json=payload, headers={**BROWSER, "DNT": "1"})

    rows = db_session.query(PageView).all()
    assert len(rows) == 2
    assert {row.path for row in rows} == {"/explore", "/"}  # query strings are dropped
    assert all(row.visitor_hash != "visitor-123456" and len(row.visitor_hash) == 64 for row in rows)
    assert {row.device for row in rows} == {"mobile"}

    _admin(client, db_session)
    report = client.get("/api/admin/analytics", params={"days": 7}).json()
    assert report["totals"]["visitors"] == 1 and report["totals"]["pageviews"] == 2
    assert len(report["series"]) == 7 and report["series"][-1]["pageviews"] == 2
    assert {s["label"]: s["value"] for s in report["sources"]} == {"Tìm kiếm": 1, "Trực tiếp": 1}
    assert {p["path"] for p in report["top_pages"]} == {"/explore", "/"}


def _attended_booking(db_session, experience, traveler, *, start_offset_hours=-3, status="confirmed"):
    start = datetime.now(timezone.utc) + timedelta(hours=start_offset_hours)
    slot = ExperienceSlot(id=str(uuid4()), experience_id=experience.id, start_at=start, end_at=start + timedelta(hours=1),
                          capacity_total=5, available_reported=5, status="open")
    db_session.add(slot)
    db_session.flush()
    booking = Booking(id=str(uuid4()), user_id=traveler.id, provider_id=experience.provider_id, experience_id=experience.id,
                      slot_id=slot.id, quantity=2, amount_vnd=0, status=status)
    db_session.add(booking)
    db_session.commit()
    return booking


def test_review_lifecycle_from_traveler_to_partner_reply(client, db_session, sample_experience):
    traveler = make_user(db_session, "traveler")
    traveler.display_name = "Nguyễn Minh Anh"
    db_session.commit()
    attended = _attended_booking(db_session, sample_experience, traveler)
    upcoming = _attended_booking(db_session, sample_experience, traveler, start_offset_hours=24)
    sign_in(client, traveler)

    assert [b["booking_id"] for b in client.get("/api/me/reviewable-bookings").json()] == [attended.id]
    assert client.post(f"/api/bookings/{upcoming.id}/review", json={"rating": 5}).json()["error"]["code"] == "REVIEW_NOT_ALLOWED"
    created = client.post(f"/api/bookings/{attended.id}/review", json={"rating": 5, "comment": "Tuyệt vời"})
    assert created.status_code == 201 and created.json()["author"] == "Anh N."
    assert client.post(f"/api/bookings/{attended.id}/review", json={"rating": 4}).status_code == 409

    partner = make_user(db_session, "provider", provider_id=sample_experience.provider_id)
    sign_in(client, partner)
    reviews = client.get("/api/provider/me/reviews").json()
    assert len(reviews) == 1 and reviews[0]["experience_title"]
    assert client.post(f"/api/provider/me/reviews/{reviews[0]['id']}/reply", json={"reply": "Cảm ơn bạn!"}).status_code == 200

    client.cookies.clear()
    public = client.get(f"/api/experiences/{sample_experience.id}/reviews").json()
    assert public["count"] == 1 and public["average"] == 5.0 and public["items"][0]["reply"] == "Cảm ơn bạn!"


def test_other_users_cannot_review_or_reply(client, db_session, sample_experience):
    owner = make_user(db_session, "traveler")
    booking = _attended_booking(db_session, sample_experience, owner)
    sign_in(client, make_user(db_session, "traveler"))
    assert client.post(f"/api/bookings/{booking.id}/review", json={"rating": 1}).status_code == 404
    sign_in(client, make_user(db_session, "provider", provider_id=sample_experience.provider_id))
    assert client.get("/api/admin/analytics").status_code == 403
    assert client.post("/api/admin/places", json=PLACE).status_code == 403


def test_provider_report_counts_views_of_own_experiences(client, db_session, sample_experience):
    db_session.add_all([PageView(id=str(uuid4()), occurred_at=datetime.now(timezone.utc), visitor_hash="a" * 64, session_hash="b" * 64,
                                 path=f"/explore/{sample_experience.id}", entity_type="experience", entity_id=sample_experience.id, device="desktop")
                        for _ in range(4)])
    db_session.commit()
    sign_in(client, make_user(db_session, "provider", provider_id=sample_experience.provider_id))
    report = client.get("/api/provider/me/analytics", params={"days": 7}).json()
    assert report["totals"]["views"] == 4 and report["series"][-1]["views"] == 4 and report["totals"]["rating"] is None


def test_audit_logs_name_the_actor(client, db_session):
    admin = _admin(client, db_session)
    client.post("/api/admin/places", json=PLACE)
    entry = next(row for row in client.get("/api/admin/audit").json() if row["action"] == "place.created")
    assert entry["actor_email"] == admin.email and entry["actor_name"] == admin.display_name
