"""Góp ý nhóm → xem trước → áp dụng / huỷ (port of Travility test_group_reviews_api)."""
import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api.routes.trips import GroupReviewIn
from app.models.trip_entities import TripGroupReview
from app.services.trip import llm, store
from tests.trip.conftest import FakeClient, reply
from tests.trip.test_trips_api import (auth, count, events_of, no_meal_rule, offline,  # noqa: F401 (autouse fixtures)
                                       trip_with_itinerary, use_llm)
from tests.trip.test_versions_api import two_versions

RETIME = {"summary": "Dời giờ ghé quán", "unresolved_feedback": [],
          "ops": [{"op": "retime_stop", "day": 1, "stop": 1, "start_time": "10:00"}]}


def create_review(client, h, tid, monkeypatch, feedback="Dời giờ ghé quán", payload=RETIME, source_version=1):
    use_llm(monkeypatch, [reply(("review_group_feedback", payload))])
    return events_of(client, f"/api/trips/{tid}/group-reviews",
                     {"source_version": source_version, "feedback": feedback}, h)


def create_pending_review(client, h, tid, monkeypatch):
    return create_review(client, h, tid, monkeypatch)[-1]["review"]


def test_apply_group_review_is_idempotent(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    review = create_pending_review(client, h, tid, monkeypatch)
    path = f"/api/trips/{tid}/group-reviews/{review['review_id']}/apply"
    first = client.post(path, headers=h, json={})
    retry = client.post(path, headers=h, json={})
    assert first.status_code == retry.status_code == 200
    assert first.json()["type"] == "itinerary"
    assert first.json()["version"] == retry.json()["version"] == 2
    assert client.get(f"/api/trips/{tid}", headers=h).json()["versions"] == [1, 2]
    saved_result = client.get(f"/api/trips/{tid}/messages", headers=h).json()[-1]
    assert (saved_result["role"], saved_result["version"]) == ("ai", 2)


def test_cancel_group_review_keeps_versions(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    review = create_pending_review(client, h, tid, monkeypatch)
    path = f"/api/trips/{tid}/group-reviews/{review['review_id']}/cancel"
    cancelled = client.post(path, headers=h, json={})
    retry = client.post(path, headers=h, json={})
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == retry.json()["status"] == "cancelled"
    assert client.get(f"/api/trips/{tid}", headers=h).json()["versions"] == [1]


def test_cancelled_review_cannot_be_applied_and_applied_cannot_be_cancelled(client, db_session, trip_places,
                                                                          monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    review = create_pending_review(client, h, tid, monkeypatch)
    base = f"/api/trips/{tid}/group-reviews/{review['review_id']}"
    client.post(f"{base}/cancel", headers=h, json={})
    assert client.post(f"{base}/apply", headers=h, json={}).status_code == 409
    again = create_pending_review(client, h, tid, monkeypatch)
    base = f"/api/trips/{tid}/group-reviews/{again['review_id']}"
    assert client.post(f"{base}/apply", headers=h, json={}).status_code == 200
    assert client.post(f"{base}/cancel", headers=h, json={}).status_code == 409


def test_group_review_apply_and_cancel_are_trip_scoped(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    review = create_pending_review(client, h, tid, monkeypatch)
    other = auth(db_session)
    base = f"/api/trips/{tid}/group-reviews"
    assert client.post(base, headers=other, json={"source_version": 1, "feedback": "Đổi quán"}).status_code == 404
    assert client.post(f"{base}/{review['review_id']}/apply", headers=other, json={}).status_code == 404
    assert client.post(f"{base}/{review['review_id']}/cancel", headers=other, json={}).status_code == 404
    assert client.post(f"{base}/999/apply", headers=h, json={}).status_code == 404


def test_apply_stale_group_review_returns_409(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    review = create_pending_review(client, h, tid, monkeypatch)
    path = f"/api/trips/{tid}/group-reviews/{review['review_id']}/apply"
    use_llm(monkeypatch, [reply(("search_places", {"query": "cafe rẻ"})),
                          reply(("edit_itinerary", {"summary": "Đổi sang quán rẻ hơn", "ops": [
                              {"op": "replace_stop", "day": 1, "stop": 1, "place_id": trip_places["cf-2"].id}]}))])
    events_of(client, "/api/trips", {"message": "rẻ hơn", "trip_id": tid}, h)
    stale = client.post(path, headers=h, json={})
    assert stale.status_code == 409
    assert client.get(f"/api/trips/{tid}", headers=h).json()["versions"] == [1, 2]


def test_apply_integrity_error_is_409_and_saves_nothing(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    review = create_pending_review(client, h, tid, monkeypatch)

    def clash(*args, **kwargs):
        raise IntegrityError("INSERT", {}, Exception("duplicate version"))

    with monkeypatch.context() as patch:
        patch.setattr(store, "save_itinerary", clash)
        assert client.post(f"/api/trips/{tid}/group-reviews/{review['review_id']}/apply", headers=h,
                           json={}).status_code == 409
    assert client.get(f"/api/trips/{tid}", headers=h).json()["versions"] == [1]


def test_old_source_version_uses_latest_base_without_saving(client, db_session, trip_places, monkeypatch):
    h, tid, _, _ = two_versions(client, db_session, monkeypatch, trip_places)
    unresolved = ["Một người muốn ăn trưa sớm, một người muốn ăn trưa muộn"]
    evs = create_review(client, h, tid, monkeypatch, "Nhóm góp ý cho bản 1",
                        {**RETIME, "summary": "Giữ quán, dời giờ", "unresolved_feedback": unresolved})
    review = evs[-1]["review"]
    assert evs[-1]["type"] == "group_review_preview"
    assert (review["source_version"], review["base_version"], review["source_is_old"]) == (1, 2, True)
    assert review["unresolved_feedback"] == unresolved
    assert client.get(f"/api/trips/{tid}", headers=h).json()["versions"] == [1, 2]
    saved_feedback = client.get(f"/api/trips/{tid}/messages", headers=h).json()[-1]
    assert (saved_feedback["role"], saved_feedback["text"], saved_feedback["version"]) == (
        "user", "Nhóm góp ý cho bản 1", 1)


def test_missing_source_version_is_404(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    response = client.post(f"/api/trips/{tid}/group-reviews", headers=h,
                           json={"source_version": 9, "feedback": "Đổi quán"})
    assert response.status_code == 404
    assert count(db_session, TripGroupReview) == 0


def test_group_review_feedback_length_is_checked_after_trimming():
    body = GroupReviewIn(source_version=1, feedback=" " + "x" * 2_000 + " ")
    assert body.feedback == "x" * 2_000


def test_group_review_rejects_whitespace_only_feedback():
    with pytest.raises(ValidationError):
        GroupReviewIn(source_version=1, feedback="   ")


def test_group_review_rejects_bad_body_with_422(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    url = f"/api/trips/{tid}/group-reviews"
    assert client.post(url, headers=h, json={"source_version": 0, "feedback": "x"}).status_code == 422
    assert client.post(url, headers=h, json={"source_version": 1, "feedback": "  "}).status_code == 422


def test_group_review_create_is_trip_scoped(client, db_session, trip_places, monkeypatch):
    _, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    response = client.post(f"/api/trips/{tid}/group-reviews", headers=auth(db_session),
                           json={"source_version": 1, "feedback": "Đổi quán"})
    assert response.status_code == 404
    assert count(db_session, TripGroupReview) == 0


def test_group_review_requires_login(client):
    assert client.post("/api/trips/1/group-reviews", json={"source_version": 1, "feedback": "x"}).status_code == 401


def test_preview_stale_base_does_not_persist_review(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    fake = FakeClient([reply(("review_group_feedback", RETIME))])
    create = fake.chat.completions.create

    def create_new_version(**kwargs):
        _, itin, places = store.load_itinerary(db_session, tid, 1)
        store.save_itinerary(db_session, tid, itin.model_dump(mode="json"), places)
        return create(**kwargs)

    fake.chat.completions.create = create_new_version
    monkeypatch.setattr(llm, "chat_client", lambda db: (fake, "fake-model"))
    messages_before = client.get(f"/api/trips/{tid}/messages", headers=h).json()
    evs = events_of(client, f"/api/trips/{tid}/group-reviews", {"source_version": 1, "feedback": "Dời giờ"}, h)
    assert evs[-1]["type"] == "error" and evs[-1]["code"] == "stale_base" and evs[-1]["status"] == 409
    assert client.get(f"/api/trips/{tid}", headers=h).json()["versions"] == [1, 2]
    assert count(db_session, TripGroupReview) == 0
    assert client.get(f"/api/trips/{tid}/messages", headers=h).json() == messages_before


def test_new_review_supersedes_the_pending_one(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    first = create_pending_review(client, h, tid, monkeypatch)
    evs = create_review(client, h, tid, monkeypatch, "Một góp ý khác")
    assert evs[-1]["type"] == "group_review_preview"
    second = evs[-1]["review"]
    assert db_session.get(TripGroupReview, first["review_id"]).status == "cancelled"
    assert db_session.get(TripGroupReview, second["review_id"]).status == "pending"
    assert client.post(f"/api/trips/{tid}/group-reviews/{first['review_id']}/apply", headers=h,
                       json={}).status_code == 409
    assert client.post(f"/api/trips/{tid}/group-reviews/{second['review_id']}/apply", headers=h,
                       json={}).status_code == 200


def test_new_review_on_a_newer_base_also_supersedes_the_pending_one(client, db_session, trip_places, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    first = create_pending_review(client, h, tid, monkeypatch)
    use_llm(monkeypatch, [reply(("search_places", {"query": "cafe rẻ"})),
                          reply(("edit_itinerary", {"summary": "Đổi quán", "ops": [
                              {"op": "replace_stop", "day": 1, "stop": 1, "place_id": trip_places["cf-2"].id}]}))])
    events_of(client, "/api/trips", {"message": "rẻ hơn", "trip_id": tid}, h)
    second = create_review(client, h, tid, monkeypatch, "Góp ý cho bản 2", source_version=2)[-1]["review"]
    assert second["base_version"] == 2
    assert db_session.get(TripGroupReview, first["review_id"]).status == "cancelled"
    assert client.post(f"/api/trips/{tid}/group-reviews/{first['review_id']}/apply", headers=h,
                       json={}).status_code == 409


@pytest.mark.parametrize("payload", [
    {"summary": "Đổi quán", "unresolved_feedback": [],
     "ops": [{"op": "replace_stop", "day": 1, "stop": 1, "place_id": 999_999}]},  # unknown place
    {"summary": "Đổi giờ", "unresolved_feedback": [],
     "ops": [{"op": "retime_stop", "day": 1, "stop": 1, "start_time": "9h"}]},  # bad time
    {"summary": "Đổi chỗ ở", "unresolved_feedback": [], "ops": [{"op": "change_stay", "place_id": 1}]},  # hard rule
    {"summary": "Đổi giờ", "unresolved_feedback": []},
    {"summary": "Đổi giờ", "ops": None, "unresolved_feedback": []},
    {"summary": "Đổi giờ", "ops": {}, "unresolved_feedback": []},
    {"ops": [], "unresolved_feedback": []},
    {"summary": 123, "ops": [], "unresolved_feedback": []},
])
def test_invalid_review_payload_does_not_persist(client, db_session, trip_places, monkeypatch, payload):
    h, tid, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    messages_before = client.get(f"/api/trips/{tid}/messages", headers=h).json()
    evs = create_review(client, h, tid, monkeypatch, "Đổi", payload)
    assert evs[-1]["type"] == "error"
    assert client.get(f"/api/trips/{tid}", headers=h).json()["versions"] == [1]
    assert count(db_session, TripGroupReview) == 0
    assert client.get(f"/api/trips/{tid}/messages", headers=h).json() == messages_before
