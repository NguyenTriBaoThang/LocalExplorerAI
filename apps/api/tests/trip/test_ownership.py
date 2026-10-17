"""Chuyến của người khác là 404 trên mọi route trip, và không bị đổi (spec: không lộ dữ liệu)."""
import pytest

from app.models.trip_entities import Trip as TripRow, TripGroupReview, TripProposal
from app.services.trip import store
from tests.helpers import bearer_for, make_user
from tests.trip.test_group_reviews_api import create_pending_review
from tests.trip.test_trips_api import (auth, no_meal_rule, offline,  # noqa: F401 (autouse fixtures)
                                       trip_with_itinerary)
from tests.trip.test_versions_api import pin

NOT_FOUND = "Không tìm thấy chuyến đi"


def test_other_users_trip_is_404_everywhere(client, db_session, trip_places, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    proposal = client.post(f"/api/trips/{tid}/disruptions", headers=h,
                           json={"version": 1, "kind": "closed", "day_index": 0, "stop_index": 0}).json()
    assert proposal["options"], proposal  # a real option, so only ownership can explain B's 404
    review = create_pending_review(client, h, tid, monkeypatch)
    assert pin(client, h, tid, pid).status_code == 200  # pin after generating valid pending previews

    def snapshot():
        db_session.expire_all()
        return {"versions": store.versions(db_session, tid), "pins": db_session.get(TripRow, tid).pinned_place_ids,
                "messages": len(store.messages(db_session, tid)),
                "proposal": db_session.get(TripProposal, proposal["proposal_id"]).applied_version,
                "review": db_session.get(TripGroupReview, review["review_id"]).status}

    before = snapshot()
    assert before["pins"] == [pid] and before["proposal"] is None and before["review"] == "pending"

    other = auth(db_session)
    base = f"/api/trips/{tid}"
    calls = [
        ("get", base, None),
        ("get", f"{base}/messages", None),
        ("patch", f"{base}/pins", {"place_id": pid, "pinned": False}),
        ("post", f"{base}/restore/1", None),
        ("post", f"{base}/disruptions", {"version": 1, "kind": "closed", "day_index": 0, "stop_index": 0}),
        ("post", f"{base}/proposals/{proposal['proposal_id']}/apply", {"option": 0}),
        ("post", "/api/trips", {"message": "đổi sang quán khác", "trip_id": tid}),
        ("post", f"{base}/plan", {"travel_mode": "grab"}),
        ("post", f"{base}/replan", {"changes": {"budget": 3_000_000}, "message": "cho 3 triệu"}),
        ("post", f"{base}/group-reviews", {"source_version": 1, "feedback": "Dời giờ ghé quán"}),
        ("post", f"{base}/group-reviews/{review['review_id']}/apply", {}),
        ("post", f"{base}/group-reviews/{review['review_id']}/cancel", {}),
    ]
    for method, url, body in calls:
        r = client.request(method, url, headers=other, **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (method, url, r.status_code)
        assert r.json()["error"]["message"] == NOT_FOUND, (method, url)

    assert client.get("/api/trips", headers=other).json() == []
    assert snapshot() == before
    assert [t["id"] for t in client.get("/api/trips", headers=h).json()] == [tid]


def test_provider_role_forbidden(client, db_session):
    h = bearer_for(make_user(db_session, "provider"))
    assert client.get("/api/trips", headers=h).status_code == 403
