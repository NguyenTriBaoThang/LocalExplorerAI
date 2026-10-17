"""Place reviews, the Google Maps rating beside them, review moderation, and editing one's own reviews."""

from datetime import date, datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet

from app.adapters.places.google_places import FoundPlace, GooglePlaceNotFound, GooglePlacesError, PlaceRating
from app.core.config import settings
from app.models.entities import AuditLog, ExperienceReview, ExternalApiUsage, Itinerary, ItineraryStop, PlaceExternalRating, PlaceReview, Provider
from app.services import external_ratings
from app.services.review_common import ranking_score
from sqlalchemy import select
from tests.conftest import add_slot
from tests.helpers import make_user, sign_in
from tests.test_portal_platform import _attended_booking


def _plan(db_session, user, experience):
    """An itinerary of this user that includes the experience's place."""
    slot = add_slot(db_session, experience)
    now = datetime.now(timezone.utc)
    itinerary = Itinerary(user_id=user.id, group_size=1, budget_vnd=500_000, travel_mode="driving", start_at=now, end_at=now + timedelta(hours=4),
                          status="feasible", constraints={}, estimated_cost_vnd=100_000)
    db_session.add(itinerary)
    db_session.flush()
    db_session.add(ItineraryStop(itinerary_id=itinerary.id, experience_id=experience.id, slot_id=slot.id, poi_id=experience.poi_id, stop_order=1, position=1,
                                 arrival_at=slot.start_at, departure_at=slot.end_at, start_at=slot.start_at, end_at=slot.end_at,
                                 activity_duration_min=60, cost_vnd=100_000))
    db_session.commit()


# ---------------------------------------------------------------- writing and reading place reviews

def test_unknown_place_is_a_404(client):
    assert client.get("/api/pois/does-not-exist/reviews").status_code == 404


def test_only_a_traveler_who_planned_the_place_may_review_it(client, db_session, sample_experience):
    poi = sample_experience.poi_id
    assert client.put(f"/api/pois/{poi}/review", json={"rating": 5}).status_code == 401      # not signed in

    traveler = make_user(db_session, "traveler")
    sign_in(client, traveler)
    status = client.get(f"/api/pois/{poi}/reviews/mine").json()
    assert status == {"can_review": False, "reason": "no_itinerary", "review": None}
    refused = client.put(f"/api/pois/{poi}/review", json={"rating": 5, "comment": "Tuyệt"})
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "REVIEW_NOT_ALLOWED"

    _plan(db_session, traveler, sample_experience)
    assert client.get(f"/api/pois/{poi}/reviews/mine").json()["can_review"] is True
    created = client.put(f"/api/pois/{poi}/review", json={"rating": 4, "comment": "Rất đẹp", "visited_on": date.today().isoformat()})
    assert created.status_code == 200 and created.json()["rating"] == 4

    # someone else's itinerary does not count
    sign_in(client, make_user(db_session, "traveler"))
    assert client.put(f"/api/pois/{poi}/review", json={"rating": 1}).status_code == 403
    # staff roles do not hold the review permission
    sign_in(client, make_user(db_session, "provider", provider_id=sample_experience.provider_id))
    assert client.put(f"/api/pois/{poi}/review", json={"rating": 5}).status_code == 403


def test_one_review_per_user_that_can_be_edited_and_removed(client, db_session, sample_experience):
    poi = sample_experience.poi_id
    traveler = make_user(db_session, "traveler")
    _plan(db_session, traveler, sample_experience)
    sign_in(client, traveler)
    client.put(f"/api/pois/{poi}/review", json={"rating": 3, "comment": "Tạm được"})
    edited = client.put(f"/api/pois/{poi}/review", json={"rating": 5, "comment": "Đẹp hơn mong đợi"}).json()
    assert edited["rating"] == 5 and edited["updated_at"] is not None
    assert len(db_session.scalars(select(PlaceReview)).all()) == 1

    client.cookies.clear()
    public = client.get(f"/api/pois/{poi}/reviews").json()["community"]
    assert public["count"] == 1 and public["average"] == 5.0 and public["distribution"]["5"] == 1
    assert public["items"][0]["edited"] is True and public["items"][0]["author"]

    sign_in(client, traveler)
    assert client.delete(f"/api/pois/{poi}/review").status_code == 204
    assert client.delete(f"/api/pois/{poi}/review").status_code == 404
    assert client.get(f"/api/pois/{poi}/reviews").json()["community"]["count"] == 0
    # a review that exists can still be edited if the itinerary is gone later
    client.put(f"/api/pois/{poi}/review", json={"rating": 2})


def test_links_and_future_visit_dates_are_refused(client, db_session, sample_experience):
    poi = sample_experience.poi_id
    traveler = make_user(db_session, "traveler")
    _plan(db_session, traveler, sample_experience)
    sign_in(client, traveler)
    spam = client.put(f"/api/pois/{poi}/review", json={"rating": 5, "comment": "Xem thêm tại https://spam.example"})
    assert spam.status_code == 422 and spam.json()["error"]["code"] == "REVIEW_REJECTED"
    future = client.put(f"/api/pois/{poi}/review", json={"rating": 5, "visited_on": (date.today() + timedelta(days=3)).isoformat()})
    assert future.status_code == 422 and future.json()["error"]["code"] == "VISIT_DATE_IN_FUTURE"
    assert client.put(f"/api/pois/{poi}/review", json={"rating": 6}).status_code == 422


def test_my_reviews_lists_places_and_experiences(client, db_session, sample_experience):
    traveler = make_user(db_session, "traveler")
    _plan(db_session, traveler, sample_experience)
    booking = _attended_booking(db_session, sample_experience, traveler)
    sign_in(client, traveler)
    client.put(f"/api/pois/{sample_experience.poi_id}/review", json={"rating": 4})
    client.post(f"/api/bookings/{booking.id}/review", json={"rating": 5, "comment": "Hay"})
    mine = client.get("/api/me/reviews").json()
    assert [r["poi_name"] for r in mine["places"]] == [sample_experience.poi.name]
    assert [r["experience_title"] for r in mine["experiences"]] == [sample_experience.title]


# ---------------------------------------------------------------- editing one's experience review

def test_author_edits_and_deletes_their_experience_review(client, db_session, sample_experience):
    traveler = make_user(db_session, "traveler")
    booking = _attended_booking(db_session, sample_experience, traveler)
    sign_in(client, traveler)
    assert client.put(f"/api/bookings/{booking.id}/review", json={"rating": 3}).status_code == 404   # nothing to edit yet
    client.post(f"/api/bookings/{booking.id}/review", json={"rating": 5, "comment": "Tuyệt"})
    edited = client.put(f"/api/bookings/{booking.id}/review", json={"rating": 4, "comment": "Khá tốt"})
    assert edited.status_code == 200 and edited.json()["rating"] == 4
    assert db_session.scalar(select(ExperienceReview)).updated_at is not None
    sign_in(client, make_user(db_session, "traveler"))
    assert client.put(f"/api/bookings/{booking.id}/review", json={"rating": 1}).status_code == 404   # not theirs
    sign_in(client, traveler)
    assert client.delete(f"/api/bookings/{booking.id}/review").status_code == 204
    assert db_session.scalar(select(ExperienceReview)) is None


# ---------------------------------------------------------------- moderation

def _review_as(client, db_session, experience, rating=5, comment="Bình luận"):
    traveler = make_user(db_session, "traveler")
    _plan(db_session, traveler, experience)
    sign_in(client, traveler)
    client.put(f"/api/pois/{experience.poi_id}/review", json={"rating": rating, "comment": comment})
    return traveler


def test_admin_hides_and_restores_a_place_review(client, db_session, sample_experience):
    _review_as(client, db_session, sample_experience, 1, "Tệ")
    review = db_session.scalar(select(PlaceReview))
    sign_in(client, make_user(db_session, "traveler"))
    assert client.get("/api/admin/reviews").status_code == 403

    admin = make_user(db_session, "admin")
    sign_in(client, admin)
    listing = client.get("/api/admin/reviews", params={"kind": "place"})
    assert listing.headers["X-Total-Count"] == "1" and listing.json()[0]["target_title"] == sample_experience.poi.name
    assert client.post(f"/api/admin/reviews/place/{review.id}/status", json={"action": "hide"}).json()["error"]["code"] == "REASON_REQUIRED"
    hidden = client.post(f"/api/admin/reviews/place/{review.id}/status", json={"action": "hide", "note": "Ngôn từ xúc phạm"})
    assert hidden.status_code == 200 and hidden.json()["status"] == "hidden"

    client.cookies.clear()
    assert client.get(f"/api/pois/{sample_experience.poi_id}/reviews").json()["community"]["count"] == 0
    sign_in(client, admin)
    assert client.get("/api/admin/reviews", params={"kind": "place", "status": "hidden"}).headers["X-Total-Count"] == "1"
    assert client.get("/api/admin/reviews", params={"kind": "place", "status": "published"}).json() == []
    assert client.post(f"/api/admin/reviews/place/{review.id}/status", json={"action": "restore"}).json()["status"] == "published"
    actions = [a.action for a in db_session.scalars(select(AuditLog)).all()]
    assert "review.hidden" in actions and "review.restored" in actions
    assert client.post("/api/admin/reviews/nonsense/x/status", json={"action": "restore"}).status_code == 404


def test_admin_moderates_experience_reviews_too(client, db_session, sample_experience):
    traveler = make_user(db_session, "traveler")
    booking = _attended_booking(db_session, sample_experience, traveler)
    sign_in(client, traveler)
    client.post(f"/api/bookings/{booking.id}/review", json={"rating": 2, "comment": "Quảng cáo"})
    review = db_session.scalar(select(ExperienceReview))
    sign_in(client, make_user(db_session, "admin"))
    assert client.get("/api/admin/reviews", params={"kind": "experience"}).json()[0]["author_name"]
    client.post(f"/api/admin/reviews/experience/{review.id}/status", json={"action": "hide", "note": "Quảng cáo"})
    client.cookies.clear()
    assert client.get(f"/api/experiences/{sample_experience.id}/reviews").json()["count"] == 0


# ---------------------------------------------------------------- ranking

def test_ranking_score_does_not_let_one_five_star_review_win():
    assert ranking_score(None, 0) == 0.0
    assert ranking_score(5.0, 1) < ranking_score(4.8, 40)
    assert ranking_score(4.0, 10_000) == pytest.approx(4.0, abs=0.01)


# ---------------------------------------------------------------- Google Maps rating

class FakeGoogle:
    def __init__(self, *, found=None, rating=PlaceRating(4.6, 1200, "https://maps.google.com/?cid=1", "Nhà thờ"), fail=None):
        self.found, self.result, self.fail, self.calls = found, rating, fail, []

    def find_place(self, name, latitude, longitude, **_):
        self.calls.append("find")
        if self.fail:
            raise self.fail
        return self.found

    def rating(self, place_id):
        self.calls.append(f"rating:{place_id}")
        if self.fail:
            raise self.fail
        return self.result


@pytest.fixture
def google(monkeypatch, db_session, sample_experience):
    monkeypatch.setattr(settings, "integration_secrets_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    monkeypatch.setattr(settings, "google_places_monthly_call_cap", 900)
    monkeypatch.setattr(settings, "google_places_cache_hours", 24)
    poi = sample_experience.poi
    poi.is_landmark = True
    db_session.commit()
    fake = FakeGoogle(found=FoundPlace("ChIJabc", "Nhà thờ", poi.latitude, poi.longitude))
    monkeypatch.setattr(external_ratings, "make_client", lambda key: fake)
    return fake, poi


def test_google_rating_is_found_once_then_served_from_the_cache(db_session, google):
    fake, poi = google
    now = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)
    first = external_ratings.google_rating(db_session, poi, now=now)
    assert first["rating"] == 4.6 and first["rating_count"] == 1200 and first["maps_uri"].startswith("https://")
    assert fake.calls == ["find", "rating:ChIJabc"] and external_ratings.calls_this_month(db_session, now) == 2

    assert external_ratings.google_rating(db_session, poi, now=now + timedelta(hours=3)) == first
    assert len(fake.calls) == 2                                              # nothing new within the cache window
    external_ratings.google_rating(db_session, poi, now=now + timedelta(hours=25))
    assert fake.calls[2:] == ["rating:ChIJabc"]                              # refreshed; the place id is remembered


def test_google_is_not_queried_without_a_key_or_for_ordinary_places(db_session, google, monkeypatch):
    fake, poi = google
    poi.is_landmark = False
    db_session.commit()
    assert external_ratings.google_rating(db_session, poi) is None and fake.calls == []     # not a landmark, no linked id
    poi.google_place_id = "ChIJmanual"
    db_session.commit()
    assert external_ratings.google_rating(db_session, poi)["rating"] == 4.6
    assert fake.calls == ["rating:ChIJmanual"]                               # a linked id skips the text search
    monkeypatch.setattr(settings, "google_places_api_key", None)
    db_session.query(PlaceExternalRating).delete()
    db_session.commit()
    assert external_ratings.google_rating(db_session, poi) is None


def test_a_far_away_match_is_rejected_and_not_retried_for_a_week(db_session, google):
    fake, poi = google
    fake.found = FoundPlace("ChIJother", "Nơi khác", poi.latitude + 0.05, poi.longitude)     # ~5.5 km away
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    assert external_ratings.google_rating(db_session, poi, now=now) is None
    assert external_ratings.google_rating(db_session, poi, now=now + timedelta(days=3)) is None
    assert fake.calls == ["find"]
    external_ratings.google_rating(db_session, poi, now=now + timedelta(days=8))
    assert fake.calls == ["find", "find"]


def test_the_monthly_cap_stops_calls_and_keeps_the_last_value(db_session, google, monkeypatch):
    fake, poi = google
    now = datetime(2030, 1, 5, tzinfo=timezone.utc)
    good = external_ratings.google_rating(db_session, poi, now=now)
    monkeypatch.setattr(settings, "google_places_monthly_call_cap", 2)       # already spent
    stale = external_ratings.google_rating(db_session, poi, now=now + timedelta(days=2))
    assert stale == good and len(fake.calls) == 2
    # a new month starts a new counter
    external_ratings.google_rating(db_session, poi, now=datetime(2030, 2, 2, tzinfo=timezone.utc))
    assert len(fake.calls) == 3 and {u.period: u.calls for u in db_session.scalars(select(ExternalApiUsage))} == {"2030-01": 2, "2030-02": 1}


def test_google_errors_never_raise_and_back_off(db_session, google):
    fake, poi = google
    fake.fail = GooglePlacesError("HTTP 403")
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    assert external_ratings.google_rating(db_session, poi, now=now) is None
    assert external_ratings.google_rating(db_session, poi, now=now + timedelta(minutes=10)) is None
    assert fake.calls == ["find"]                                            # not retried within the hour
    fake.fail = None
    assert external_ratings.google_rating(db_session, poi, now=now + timedelta(hours=2))["rating"] == 4.6
    fake.fail = GooglePlaceNotFound("gone")
    poi.google_place_id = "ChIJgone"
    db_session.commit()
    assert external_ratings.google_rating(db_session, poi, now=now + timedelta(days=2)) is None


def test_public_endpoint_shows_two_separate_blocks_and_survives_a_google_failure(client, db_session, google, monkeypatch):
    fake, poi = google
    body = client.get(f"/api/pois/{poi.id}/reviews").json()
    assert body["google"]["rating"] == 4.6 and body["community"]["count"] == 0         # separate, never averaged together
    db_session.query(PlaceExternalRating).delete()
    db_session.commit()
    monkeypatch.setattr(external_ratings, "google_rating", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    ok = client.get(f"/api/pois/{poi.id}/reviews")
    assert ok.status_code == 200 and ok.json()["google"] is None


def test_admin_links_a_google_place_id_and_tests_the_connection(client, db_session, google):
    fake, poi = google
    sign_in(client, make_user(db_session, "admin"))
    current = client.get(f"/api/admin/places/{poi.id}").json()
    payload = {k: current[k] for k in ("name", "category", "district", "address", "latitude", "longitude", "description", "image_urls",
                                       "opening_hours", "ticket_info", "tags", "is_landmark", "source_url")}
    saved = client.patch(f"/api/admin/places/{poi.id}", json={**payload, "google_place_id": "ChIJlinked"})
    assert saved.status_code == 200 and saved.json()["google_place_id"] == "ChIJlinked"
    assert client.patch(f"/api/admin/places/{poi.id}", json={**payload, "google_place_id": "has spaces!"}).status_code == 422
    test = client.post("/api/admin/integrations/google_places/test").json()
    assert test["ok"] is True and test["check_type"] == "external_request"
    fake.fail = GooglePlacesError("HTTP 403")
    assert client.post("/api/admin/integrations/google_places/test").json()["ok"] is False
