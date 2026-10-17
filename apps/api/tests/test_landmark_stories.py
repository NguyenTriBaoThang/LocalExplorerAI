from copy import deepcopy

from app.models.entities import AuditLog, LandmarkStory
from app.schemas.landmark_story import LandmarkStoryPayload
from scripts.seed_landmark_stories import seed
from tests.helpers import bearer_for, make_user
from sqlalchemy import select


PUBLIC = "/api/landmark-stories/nhathoducba"
ADMIN = "/api/admin/landmark-stories/nhathoducba"


def test_drafts_never_leak_and_publication_preserves_previous_version(client, db_session):
    seed(db_session)
    headers = bearer_for(make_user(db_session, "admin"))
    draft = client.get(ADMIN, headers=headers).json()
    assert client.get(PUBLIC).json()["content"] is None
    assert client.post(ADMIN + "/publish", json={"revision": 1}, headers=headers).status_code == 409
    response = client.post(ADMIN + "/submit", json={"revision": 1}, headers=headers)
    assert response.status_code == 200
    response = client.post(ADMIN + "/publish", json={"revision": 2}, headers=headers)
    assert response.status_code == 200
    original = client.get(PUBLIC).json()["content"]
    draft["content"]["overview"]["text"] = "Changed editorial draft"
    response = client.put(ADMIN, json={"revision": 3, "content": draft["content"]}, headers=headers)
    assert response.status_code == 200
    assert client.get(PUBLIC).json()["content"] == original
    assert client.put(ADMIN, json={"revision": 3, "content": draft["content"]}, headers=headers).status_code == 409
    assert client.post(ADMIN + "/unpublish", json={"revision": 4}, headers=headers).status_code == 200
    assert client.get(PUBLIC).json()["content"] is None
    assert db_session.scalar(select(AuditLog).where(AuditLog.action == "landmark_story.publish"))


def test_editorial_permissions_unknown_models_and_empty_state(client, db_session):
    assert client.get(ADMIN).status_code == 401
    headers = bearer_for(make_user(db_session, "traveler"))
    assert client.get(ADMIN, headers=headers).status_code == 403
    assert client.put(ADMIN, json={"revision": 0, "content": {}}, headers=headers).status_code == 403
    assert client.get("/api/landmark-stories/unknown-model").status_code == 404
    assert client.get("/api/landmark-stories/bitexco").json()["content"] is None


def test_source_validation_and_unsourced_publication(client, db_session):
    seed(db_session)
    headers = bearer_for(make_user(db_session, "admin"))
    content = client.get(ADMIN, headers=headers).json()["content"]
    for change in ("url", "reference", "range"):
        invalid = deepcopy(content)
        if change == "url":
            invalid["sources"][0]["url"] = "javascript:alert(1)"
        elif change == "reference":
            invalid["timeline"][0]["source_ids"] = ["missing"]
        else:
            invalid["timeline"][0]["year_end"] = 1000
        assert client.put(ADMIN, json={"revision": 1, "content": invalid}, headers=headers).status_code == 422
    content["timeline"][0]["status"] = "unverified"
    assert client.put(ADMIN, json={"revision": 1, "content": content}, headers=headers).status_code == 200
    assert client.post(ADMIN + "/submit", json={"revision": 2}, headers=headers).status_code == 422


def test_curated_seed_is_valid_and_does_not_overwrite_edits(db_session):
    assert set(seed(db_session, publish=True)) == {"nhathoducba", "dinhdoclap", "chobenthanh", "nhahatthanhpho"}
    row = db_session.get(LandmarkStory, "nhathoducba")
    parsed = LandmarkStoryPayload.model_validate(row.published)
    assert len(parsed.timeline) == 5
    row.draft = {**row.draft, "image": None}
    row.workflow = "review"
    db_session.commit()
    assert seed(db_session, publish=True) == []
    assert row.workflow == "review"
