import datetime as dt
import json

import httpx
import openai
import pytest
from sqlalchemy import func, select

from app.api.dependencies import get_llm_provider
from app.db.session import get_db
from app.models.trip_entities import Trip as TripRow, TripItinerary, TripMessage
from app.services import chat_response_service
from app.services.trip import flow, forecast, llm, rules, store
from app.services.trip.domain import Trip
from tests.helpers import bearer_for, make_user
from tests.trip.conftest import FakeClient, reply


@pytest.fixture(autouse=True)
def no_meal_rule(monkeypatch):
    """Các test ở đây không xếp bữa ăn; quy tắc 3 bữa được test riêng ở test_rules / test_missing_meal_*."""
    monkeypatch.setattr(rules, "MEALS", ())


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(llm, "embed", lambda db, texts: None)
    monkeypatch.setattr(forecast, "get_rain_chance", lambda *a, **k: None)
    route(monkeypatch, "planning")


def route(monkeypatch, intent, topic=None):
    monkeypatch.setattr(chat_response_service, "classify_chat_intent", lambda *a, **k: (intent, topic, None))


def auth(db):
    return bearer_for(make_user(db, "traveler"))


def events_of(client, url, body, headers):
    with client.stream("POST", url, json=body, headers=headers) as r:
        assert r.status_code == 200, r.read()
        assert r.headers["content-type"].startswith("text/event-stream")
        text = "".join(r.iter_text())
    return [json.loads(chunk[6:]) for chunk in text.split("\n\n") if chunk.startswith("data: ")]


def use_llm(monkeypatch, responses) -> FakeClient:
    fake = FakeClient(responses)
    monkeypatch.setattr(llm, "chat_client", lambda db: (fake, "fake-model"))
    return fake


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


RECORD = {"destination": "tp-hcm", "days": 1, "budget": 2_000_000}


def ask_first(client, db, monkeypatch, record=None):
    """POST /api/trips với câu thiếu Travel Mode → trả (headers, events)."""
    use_llm(monkeypatch, [reply(("record_trip", record or RECORD))])
    h = auth(db)
    return h, events_of(client, "/api/trips", {"message": "TP.HCM 1 ngày"}, h)


def happy(pid):
    return [reply(("record_trip", {**RECORD, "travel_mode": "grab"})),
            reply(("search_places", {"query": "cafe"})),
            reply(("submit_itinerary", {"summary": "ok", "days": [{"stops": [
                {"place_id": pid, "start_time": "09:00", "duration_min": 60, "reason": "cafe-chill"}]}]}))]


def trip_with_itinerary(client, db, monkeypatch, trip_places):
    pid = trip_places["cf-1"].id
    use_llm(monkeypatch, happy(pid))
    h = auth(db)
    return h, events_of(client, "/api/trips", {"message": "x"}, h)[-1]["trip_id"], pid


def test_create_trip_streams_and_persists(client, db_session, trip_places, monkeypatch):
    pid = trip_places["cf-1"].id
    use_llm(monkeypatch, happy(pid))
    h = auth(db_session)
    evs = events_of(client, "/api/trips", {"message": "TP.HCM 1 ngày 2 triệu"}, h)
    assert [e["type"] for e in evs] == ["thinking", "trip", "tool_call", "itinerary"]
    assert evs[1]["center"] == [106.7009, 10.7769]
    trip_id = evs[-1]["trip_id"]
    got = client.get(f"/api/trips/{trip_id}", headers=h).json()
    assert got["version"] == 1 and got["versions"] == [1]
    assert got["itinerary"]["days"][0]["stops"][0]["place_id"] == pid
    assert got["places"][str(pid)]["name"] == "Cà Phê Chung Cư"
    listed = client.get("/api/trips", headers=h).json()
    assert [t["id"] for t in listed] == [trip_id]
    assert listed[0]["destination_name"] == "TP. Hồ Chí Minh" and listed[0]["spec"]["destination"] == "tp-hcm"


def test_get_unknown_version_is_404(client, db_session, trip_places, monkeypatch):
    h, trip_id, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    assert client.get(f"/api/trips/{trip_id}?version=1", headers=h).json()["version"] == 1
    r = client.get(f"/api/trips/{trip_id}?version=9", headers=h)
    assert r.status_code == 404 and r.json()["error"]["message"] == "Không tìm thấy phiên bản lịch trình"


def test_other_user_gets_404(client, db_session, trip_places, monkeypatch):
    _, trip_id, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    other = auth(db_session)
    r = client.get(f"/api/trips/{trip_id}", headers=other)
    assert r.status_code == 404 and r.json()["error"]["message"] == "Không tìm thấy chuyến đi"
    assert client.get("/api/trips", headers=other).json() == []


def test_unsupported_destination_is_error_event(client, db_session, trip_places, monkeypatch):
    use_llm(monkeypatch, [reply(("record_trip", {"destination": "unsupported", "days": 3, "budget": 1}))])
    evs = events_of(client, "/api/trips", {"message": "Phú Quốc"}, auth(db_session))
    assert evs[-1] == {"type": "error", "message": "Hiện mình chỉ hỗ trợ lịch trình ở TP. Hồ Chí Minh."}
    assert count(db_session, TripRow) == 0


def test_llm_down_is_error_event(client, db_session, trip_places, monkeypatch):
    use_llm(monkeypatch, [openai.APIConnectionError(request=httpx.Request("POST", "http://x"))])
    evs = events_of(client, "/api/trips", {"message": "x"}, auth(db_session))
    assert evs[-1] == {"type": "error", "message": "Không kết nối được AI, kiểm tra mạng rồi thử lại nhé."}


def test_llm_error_saves_nothing(client, db_session, trip_places, monkeypatch):
    use_llm(monkeypatch, [happy(trip_places["cf-1"].id)[0],
                          openai.APIConnectionError(request=httpx.Request("POST", "http://x"))])
    evs = events_of(client, "/api/trips", {"message": "TP.HCM 1 ngày 2 triệu"}, auth(db_session))
    assert [e["type"] for e in evs] == ["thinking", "trip", "error"]
    assert evs[-1] == {"type": "error", "message": "Không kết nối được AI, kiểm tra mạng rồi thử lại nhé."}
    assert count(db_session, TripItinerary) == 0
    assert not db_session.scalars(select(TripMessage).where(TripMessage.role == "ai")).all()


def test_unexpected_exception_is_error_event(client, db_session, trip_places, monkeypatch):
    use_llm(monkeypatch, [RuntimeError("boom")])
    evs = events_of(client, "/api/trips", {"message": "x"}, auth(db_session))
    assert evs[-1] == {"type": "error", "message": "Có lỗi khi lập lịch trình, bạn thử lại nhé."}


def test_no_ai_configured_is_error_event(client, db_session, trip_places, monkeypatch):
    monkeypatch.setattr(llm, "chat_client", lambda db: None)
    evs = events_of(client, "/api/trips", {"message": "x"}, auth(db_session))
    assert evs == [{"type": "error", "message": flow.NO_AI}]


def test_requires_login(client):
    assert client.post("/api/trips", json={"message": "x"}).status_code == 401


def test_message_length_is_validated(client, db_session):
    assert client.post("/api/trips", json={"message": ""}, headers=auth(db_session)).status_code == 422


def test_missing_info_ends_with_clarify(client, db_session, trip_places, monkeypatch):
    _, evs = ask_first(client, db_session, monkeypatch)
    assert [e["type"] for e in evs] == ["thinking", "trip", "clarify"]
    assert [q["field"] for q in evs[-1]["questions"]] == ["travel_mode"]
    assert evs[-1]["trip_id"] == evs[1]["trip_id"]


def test_plan_applies_answers_and_persists(client, db_session, trip_places, monkeypatch):
    h, evs = ask_first(client, db_session, monkeypatch)
    trip_id = evs[-1]["trip_id"]
    use_llm(monkeypatch, happy(trip_places["cf-1"].id)[1:])
    evs = events_of(client, f"/api/trips/{trip_id}/plan", {"travel_mode": "o-to-rieng"}, h)
    assert [e["type"] for e in evs] == ["trip", "tool_call", "itinerary"]
    assert evs[0]["trip"]["travel_mode"] == "o-to-rieng"
    assert client.get(f"/api/trips/{trip_id}", headers=h).json()["trip"]["travel_mode"] == "o-to-rieng"


def test_plan_skip_uses_default_travel_mode(client, db_session, trip_places, monkeypatch):
    h, evs = ask_first(client, db_session, monkeypatch)
    use_llm(monkeypatch, happy(trip_places["cf-1"].id)[1:])
    evs = events_of(client, f"/api/trips/{evs[-1]['trip_id']}/plan", {}, h)
    assert evs[0]["trip"]["travel_mode"] == "xe-may"


def test_plan_twice_is_409(client, db_session, trip_places, monkeypatch):
    h, trip_id, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    assert client.post(f"/api/trips/{trip_id}/plan", json={}, headers=h).status_code == 409


def test_plan_other_users_trip_is_404(client, db_session, trip_places, monkeypatch):
    _, evs = ask_first(client, db_session, monkeypatch)
    other = auth(db_session)
    assert client.post(f"/api/trips/{evs[-1]['trip_id']}/plan", json={}, headers=other).status_code == 404


def test_plan_bad_times_is_422_in_vietnamese(client, db_session, trip_places, monkeypatch):
    h, evs = ask_first(client, db_session, monkeypatch)
    r = client.post(f"/api/trips/{evs[-1]['trip_id']}/plan",
                    json={"arrival_time": "15:00", "departure_time": "10:00"}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["message"] == "Giờ về phải sau giờ đến"


def test_arrival_hub_starts_day_one(client, db_session, trip_places, monkeypatch):
    record = {**RECORD, "travel_mode": "grab", "arrival_mode": "may-bay"}
    use_llm(monkeypatch, [reply(("record_trip", record)), *happy(trip_places["cf-1"].id)[1:]])
    evs = events_of(client, "/api/trips", {"message": "x"}, auth(db_session))
    assert evs[-1]["itinerary"]["days"][0]["legs"][0]["from_place_id"] is None


def test_hub_missing_for_arrival_mode_falls_back():
    trip = Trip(destination="tp-hcm", days=1, budget=1, arrival_mode="tau")
    assert store.hub_for({"hubs": {"may-bay": {"name": "x", "lat": 1, "lon": 1}}}, trip) is None
    assert store.hub_for({"hubs": {}}, Trip(destination="tp-hcm", days=1, budget=1)) is None


def test_follow_up_message_continues_same_trip(client, db_session, trip_places, monkeypatch):
    h, evs = ask_first(client, db_session, monkeypatch)
    trip_id = evs[-1]["trip_id"]
    fake = use_llm(monkeypatch, [reply(("record_trip", {**RECORD, "travel_mode": "xe-may", "preferred_tags": ["gia-re"]})),
                                 *happy(trip_places["cf-1"].id)[1:]])
    evs = events_of(client, "/api/trips", {"message": "bằng xe máy, rẻ thôi", "trip_id": trip_id}, h)
    assert [e["type"] for e in evs] == ["thinking", "trip", "tool_call", "itinerary"]
    assert evs[1]["trip_id"] == trip_id and evs[1]["trip"]["preferred_tags"] == ["gia-re"]
    parse_input = fake.calls[0]["messages"][1]["content"]
    assert "TP.HCM 1 ngày" in parse_input and "bằng xe máy, rẻ thôi" in parse_input
    assert "bằng xe máy, rẻ thôi" in fake.calls[1]["messages"][1]["content"]  # prompt lập lịch có nguyên văn
    assert count(db_session, TripRow) == 1


def test_follow_up_never_asks_twice(client, db_session, trip_places, monkeypatch):
    h, evs = ask_first(client, db_session, monkeypatch)
    use_llm(monkeypatch, [reply(("record_trip", RECORD)), *happy(trip_places["cf-1"].id)[1:]])  # vẫn thiếu Travel Mode
    evs = events_of(client, "/api/trips", {"message": "sao cũng được", "trip_id": evs[-1]["trip_id"]}, h)
    assert evs[-1]["type"] == "itinerary" and evs[1]["trip"]["travel_mode"] == "xe-may"


def test_follow_up_on_other_users_trip_is_404(client, db_session, trip_places, monkeypatch):
    _, evs = ask_first(client, db_session, monkeypatch)
    r = client.post("/api/trips", json={"message": "x", "trip_id": evs[-1]["trip_id"]}, headers=auth(db_session))
    assert r.status_code == 404


def test_message_after_itinerary_is_not_supported_yet(client, db_session, trip_places, monkeypatch):
    h, trip_id, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    evs = events_of(client, "/api/trips", {"message": "đổi quán cafe", "trip_id": trip_id}, h)
    assert evs[-1] == {"type": "error", "message": "Sửa lịch bằng hội thoại chưa sẵn sàng."}
    assert count(db_session, TripItinerary) == 1


def test_replan_applies_changes_and_reuses_old_places(client, db_session, trip_places, monkeypatch):
    h, trip_id, pid = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    fake = use_llm(monkeypatch, [reply(("submit_itinerary", {"summary": "mới", "days": [{"stops": [
        {"place_id": pid, "start_time": "10:00", "duration_min": 60, "reason": "giữ quán cũ"}]}]}))])
    evs = events_of(client, f"/api/trips/{trip_id}/replan", {"changes": {"budget": 3_000_000}, "message": "cho 3 triệu"}, h)
    assert [e["type"] for e in evs] == ["trip", "itinerary"]  # Place cũ dùng được, không cần search lại
    assert evs[-1]["version"] == 2 and evs[0]["trip"]["budget"] == 3_000_000
    assert "Lịch trình cũ" in fake.calls[0]["messages"][1]["content"]
    row = db_session.get(TripRow, trip_id)
    db_session.refresh(row)
    assert row.user_messages == ["x", "cho 3 triệu"] and row.spec["budget"] == 3_000_000


def test_replan_bad_changes_422_other_user_404(client, db_session, trip_places, monkeypatch):
    h, trip_id, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    assert client.post(f"/api/trips/{trip_id}/replan", headers=h,
                       json={"changes": {"days": 0}, "message": "0 ngày"}).status_code == 422
    assert client.post(f"/api/trips/{trip_id}/replan", headers=auth(db_session),
                       json={"changes": {"budget": 1}, "message": "x"}).status_code == 404


def test_out_of_scope_does_not_create_trip(client, db_session, trip_places, monkeypatch):
    route(monkeypatch, "out_of_scope")
    evs = events_of(client, "/api/trips", {"message": "viết giúp mình bài thơ"}, auth(db_session))
    assert evs == [{"type": "answer", "text": chat_response_service._out_of_scope_reply("vi")}]
    assert count(db_session, TripRow) == 0


def test_weather_question_answers_without_new_version(client, db_session, trip_places, monkeypatch):
    h, trip_id, _ = trip_with_itinerary(client, db_session, monkeypatch, trip_places)
    route(monkeypatch, "travel_information", "weather")
    seen = {}

    def daily_forecast(lat, lon, day, name=""):
        seen.update(lat=lat, lon=lon)
        return {"location": name, "forecast_date": day.isoformat(), "precipitation_probability_pct": 40,
                "precipitation_sum_mm": 1.5, "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "source": "Open-Meteo", "source_url": "https://open-meteo.com/en/docs", "attribution": "Open-Meteo"}

    monkeypatch.setattr(chat_response_service, "daily_forecast", daily_forecast)
    evs = events_of(client, "/api/trips", {"message": "mai có mưa không", "trip_id": trip_id}, h)
    assert [e["type"] for e in evs] == ["answer"] and "Open-Meteo" in evs[0]["text"]
    assert seen == {"lat": 10.7769, "lon": 106.7009}
    assert client.get(f"/api/trips/{trip_id}", headers=h).json()["versions"] == [1]
    logged = db_session.scalars(select(TripMessage).where(TripMessage.trip_id == trip_id).order_by(TripMessage.id)).all()
    assert [(m.role, m.text) for m in logged[-2:]] == [("user", "mai có mưa không"), ("ai", evs[0]["text"])]


class FakeProvider:
    model_name = "fake"

    def __init__(self):
        self.inputs = []

    def generate(self, system_prompt, user_input, schema):
        self.inputs.append(user_input)
        return {"reply": "Phở Lệ mở 06:00–22:00 theo danh mục."}


def test_travel_question_before_itinerary_uses_trip_places(client, db_session, trip_places, monkeypatch):
    route(monkeypatch, "travel_information", "food")
    provider = FakeProvider()
    client.app.dependency_overrides[get_llm_provider] = lambda: provider
    evs = events_of(client, "/api/trips", {"message": "phở ở đâu ngon"}, auth(db_session))
    assert evs == [{"type": "answer", "text": "Phở Lệ mở 06:00–22:00 theo danh mục."}]
    catalog = json.loads(provider.inputs[0]["catalog_context"])
    assert catalog[0]["name"] == "Phở Lệ" and catalog[0]["price"] == 60_000 and "open_hours" in catalog[0]
    assert len(catalog) <= 5
    assert count(db_session, TripRow) == 0


def test_stream_session_survives_until_end(client, db_session, trip_places, monkeypatch):
    order = []

    def tracked_db():
        try:
            yield db_session
        finally:
            order.append("closed")

    real_save = store.save_itinerary
    monkeypatch.setattr(store, "save_itinerary", lambda *a: order.append("saved") or real_save(*a))
    client.app.dependency_overrides[get_db] = tracked_db
    use_llm(monkeypatch, happy(trip_places["cf-1"].id))
    evs = events_of(client, "/api/trips", {"message": "TP.HCM 1 ngày 2 triệu"}, auth(db_session))
    assert evs[-1]["type"] == "itinerary" and evs[-1]["version"] == 1
    assert order[-2:] == ["saved", "closed"]  # the request session is closed only after the stream finished
    ai = db_session.scalars(select(TripMessage).where(TripMessage.trip_id == evs[-1]["trip_id"],
                                                      TripMessage.role == "ai")).all()
    assert [(m.text, m.version) for m in ai] == [("ok", 1)]


def test_run_message_on_missing_trip_is_error_event(db_session):
    user = make_user(db_session, "traveler")
    out = list(flow.run_message(db_session, user, "x", 999, None))
    assert json.loads(out[0][6:]) == {"type": "error", "message": "Không tìm thấy chuyến đi"}


def test_guarded_turns_exception_into_error_event(db_session):
    def boom():
        yield "a"
        raise RuntimeError("x")

    out = list(flow.guarded(db_session, boom()))
    assert out[0] == "a"
    assert json.loads(out[1][6:]) == {"type": "error", "message": "Có lỗi khi lập lịch trình, bạn thử lại nhé."}


def test_save_itinerary_numbers_versions_per_trip(db_session):
    user = make_user(db_session, "traveler")
    a, b = TripRow(user_id=user.id, spec={}), TripRow(user_id=user.id, spec={})
    db_session.add_all([a, b])
    db_session.commit()
    assert [store.save_itinerary(db_session, a.id, {}, {}) for _ in range(2)] == [1, 2]
    assert store.save_itinerary(db_session, b.id, {}, {}) == 1
