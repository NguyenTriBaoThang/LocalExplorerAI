import pytest
from pydantic import ValidationError

from app.group_reviews import GroupReviewIn
from app.trips import load_itinerary, save_itinerary
from tests.fakes import FakeClient, reply
from tests.test_trips_api import auth, client, events, no_meal_rule, trip_with_itinerary, use_llm  # noqa: F401
from tests.test_versions_api import two_versions


def create_pending_review(client, h, tid, monkeypatch):
    use_llm(monkeypatch, [reply(("review_group_feedback", {
        "summary": "Dời giờ ghé quán",
        "ops": [{"op": "retime_stop", "day": 1, "stop": 1, "start_time": "10:00"}],
        "unresolved_feedback": [],
    }))])
    evs = events(client.post(f"/trips/{tid}/group-reviews", headers=h,
                             json={"source_version": 1, "feedback": "Dời giờ ghé quán"}))
    return evs[-1]["review"]


def test_apply_group_review_is_idempotent(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    review = create_pending_review(client, h, tid, monkeypatch)
    path = f"/trips/{tid}/group-reviews/{review['review_id']}/apply"
    first = client.post(path, headers=h, json={})
    retry = client.post(path, headers=h, json={})
    assert first.status_code == retry.status_code == 200
    assert first.json()["version"] == retry.json()["version"] == 2
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1, 2]
    saved_result = client.get(f"/trips/{tid}/messages", headers=h).json()[-1]
    assert (saved_result["role"], saved_result["version"]) == ("ai", 2)


def test_cancel_group_review_keeps_versions(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    review = create_pending_review(client, h, tid, monkeypatch)
    path = f"/trips/{tid}/group-reviews/{review['review_id']}/cancel"
    cancelled = client.post(path, headers=h, json={})
    retry = client.post(path, headers=h, json={})
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == retry.json()["status"] == "cancelled"
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1]


def test_group_review_apply_and_cancel_are_trip_scoped(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    review = create_pending_review(client, h, tid, monkeypatch)
    other = auth(client, "binh@example.com")
    apply_path = f"/trips/{tid}/group-reviews/{review['review_id']}/apply"
    cancel_path = f"/trips/{tid}/group-reviews/{review['review_id']}/cancel"
    assert client.post(f"/trips/{tid}/group-reviews", headers=other,
                       json={"source_version": 1, "feedback": "Đổi quán"}).status_code == 404
    assert client.post(apply_path, headers=other, json={}).status_code == 404
    assert client.post(cancel_path, headers=other, json={}).status_code == 404


def test_apply_stale_group_review_returns_409(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    review = create_pending_review(client, h, tid, monkeypatch)
    path = f"/trips/{tid}/group-reviews/{review['review_id']}/apply"
    from tests.helpers import add_place
    other = add_place(conn, name="Cafe rẻ hơn", kind="cafe")
    use_llm(monkeypatch, [reply(("search_places", {"query": "cafe rẻ"})),
                          reply(("edit_itinerary", {"summary": "Đổi sang quán rẻ hơn", "ops": [
                              {"op": "replace_stop", "day": 1, "stop": 1, "place_id": other}]}))])
    events(client.post("/trips", json={"message": "rẻ hơn", "trip_id": tid}, headers=h))
    stale = client.post(path, headers=h, json={})
    assert stale.status_code == 409
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1, 2]


def test_old_source_version_uses_latest_base_without_saving(client, conn, monkeypatch):
    h, tid, _, _ = two_versions(client, conn, monkeypatch)
    use_llm(monkeypatch, [reply(("review_group_feedback", {
        "summary": "Giữ quán, dời giờ",
        "ops": [{"op": "retime_stop", "day": 1, "stop": 1, "start_time": "10:00"}],
        "unresolved_feedback": ["Một người muốn ăn trưa sớm, một người muốn ăn trưa muộn"],
    }))])
    evs = events(client.post(f"/trips/{tid}/group-reviews", headers=h,
                             json={"source_version": 1, "feedback": "Nhóm góp ý cho bản 1"}))
    review = evs[-1]["review"]
    assert evs[-1]["type"] == "group_review_preview"
    assert (review["source_version"], review["base_version"], review["source_is_old"]) == (1, 2, True)
    assert review["unresolved_feedback"] == ["Một người muốn ăn trưa sớm, một người muốn ăn trưa muộn"]
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1, 2]
    saved_feedback = client.get(f"/trips/{tid}/messages", headers=h).json()[-1]
    assert (saved_feedback["role"], saved_feedback["text"], saved_feedback["version"]) == (
        "user", "Nhóm góp ý cho bản 1", 1)


def test_missing_source_version_is_404(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    response = client.post(f"/trips/{tid}/group-reviews", headers=h,
                           json={"source_version": 9, "feedback": "Đổi quán"})
    assert response.status_code == 404
    assert conn.execute("SELECT count(*) AS n FROM group_review_proposals").fetchone()["n"] == 0


def test_group_review_feedback_length_is_checked_after_trimming():
    body = GroupReviewIn(source_version=1, feedback=" " + "x" * 2_000 + " ")
    assert body.feedback == "x" * 2_000


def test_group_review_rejects_whitespace_only_feedback():
    with pytest.raises(ValidationError):
        GroupReviewIn(source_version=1, feedback="   ")


def test_group_review_create_is_trip_scoped(client, conn, monkeypatch):
    _, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    other = auth(client, "binh@example.com")
    response = client.post(f"/trips/{tid}/group-reviews", headers=other,
                           json={"source_version": 1, "feedback": "Đổi quán"})
    assert response.status_code == 404
    assert conn.execute("SELECT count(*) AS n FROM group_review_proposals").fetchone()["n"] == 0


def test_preview_stale_base_does_not_persist_review(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    fake = FakeClient([reply(("review_group_feedback", {
        "summary": "Dời giờ", "ops": [{"op": "retime_stop", "day": 1, "stop": 1, "start_time": "10:00"}],
        "unresolved_feedback": [],
    }))])
    create = fake.chat.completions.create

    def create_new_version(**kwargs):
        _, itin, places = load_itinerary(conn, tid, 1)
        save_itinerary(conn, tid, itin.model_dump(mode="json"), places)
        return create(**kwargs)

    fake.chat.completions.create = create_new_version
    monkeypatch.setattr("app.llm.chat_client", lambda: fake)
    messages_before = client.get(f"/trips/{tid}/messages", headers=h).json()
    evs = events(client.post(f"/trips/{tid}/group-reviews", headers=h,
                             json={"source_version": 1, "feedback": "Dời giờ"}))
    assert evs[-1]["type"] == "error" and evs[-1]["code"] == "stale_base"
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1, 2]
    assert conn.execute("SELECT count(*) AS n FROM group_review_proposals").fetchone()["n"] == 0
    assert client.get(f"/trips/{tid}/messages", headers=h).json() == messages_before


def test_invalid_place_does_not_persist_review(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    messages_before = client.get(f"/trips/{tid}/messages", headers=h).json()
    use_llm(monkeypatch, [reply(("review_group_feedback", {
        "summary": "Đổi quán",
        "ops": [{"op": "replace_stop", "day": 1, "stop": 1, "place_id": 999_999}],
        "unresolved_feedback": [],
    }))])
    evs = events(client.post(f"/trips/{tid}/group-reviews", headers=h,
                             json={"source_version": 1, "feedback": "Đổi quán"}))
    assert evs[-1]["type"] == "error"
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1]
    assert conn.execute("SELECT count(*) AS n FROM group_review_proposals").fetchone()["n"] == 0
    assert client.get(f"/trips/{tid}/messages", headers=h).json() == messages_before


def test_invalid_edit_does_not_persist_review(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    messages_before = client.get(f"/trips/{tid}/messages", headers=h).json()
    use_llm(monkeypatch, [reply(("review_group_feedback", {
        "summary": "Đổi giờ",
        "ops": [{"op": "retime_stop", "day": 1, "stop": 1, "start_time": "9h"}],
        "unresolved_feedback": [],
    }))])
    evs = events(client.post(f"/trips/{tid}/group-reviews", headers=h,
                             json={"source_version": 1, "feedback": "Đổi giờ"}))
    assert evs[-1]["type"] == "error"
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1]
    assert conn.execute("SELECT count(*) AS n FROM group_review_proposals").fetchone()["n"] == 0
    assert client.get(f"/trips/{tid}/messages", headers=h).json() == messages_before


def test_invalid_hard_rule_does_not_persist_review(client, conn, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    messages_before = client.get(f"/trips/{tid}/messages", headers=h).json()
    use_llm(monkeypatch, [reply(("review_group_feedback", {
        "summary": "Đổi chỗ ở",
        "ops": [{"op": "change_stay", "place_id": pid}],
        "unresolved_feedback": [],
    }))])
    evs = events(client.post(f"/trips/{tid}/group-reviews", headers=h,
                             json={"source_version": 1, "feedback": "Đổi chỗ ở"}))
    assert evs[-1]["type"] == "error"
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1]
    assert conn.execute("SELECT count(*) AS n FROM group_review_proposals").fetchone()["n"] == 0
    assert client.get(f"/trips/{tid}/messages", headers=h).json() == messages_before


@pytest.mark.parametrize("payload", [
    {"summary": "Đổi giờ", "unresolved_feedback": []},
    {"summary": "Đổi giờ", "ops": None, "unresolved_feedback": []},
    {"summary": "Đổi giờ", "ops": {}, "unresolved_feedback": []},
    {"ops": [], "unresolved_feedback": []},
    {"summary": 123, "ops": [], "unresolved_feedback": []},
])
def test_malformed_review_tool_payload_does_not_persist(client, conn, monkeypatch, payload):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    messages_before = client.get(f"/trips/{tid}/messages", headers=h).json()
    use_llm(monkeypatch, [reply(("review_group_feedback", payload))])
    evs = events(client.post(f"/trips/{tid}/group-reviews", headers=h,
                             json={"source_version": 1, "feedback": "Đổi giờ"}))
    assert evs[-1]["type"] == "error"
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1]
    assert conn.execute("SELECT count(*) AS n FROM group_review_proposals").fetchone()["n"] == 0
    assert client.get(f"/trips/{tid}/messages", headers=h).json() == messages_before
