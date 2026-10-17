import httpx
import pytest
from fastapi.testclient import TestClient

from app import distance, llm, places_client, places_service, trips
from app.config import settings
from tests.helpers import add_place, unit_vec
from tests.test_trips_api import auth, client, events, happy, no_meal_rule, use_llm  # noqa: F401 (fixture)


def refuse(request):
    raise httpx.ConnectError("places không chạy", request=request)


def kill(monkeypatch):
    monkeypatch.setattr(places_client, "_http", httpx.Client(transport=httpx.MockTransport(refuse)))


def no_embed(texts):
    raise AssertionError("có PLACES_URL thì service places tự embed")


@pytest.fixture
def svc(conn, monkeypatch):
    """places_client gọi thẳng vào app của service qua TestClient: hợp đồng HTTP thật, không cần mạng."""
    places_service.app.dependency_overrides[places_service.get_read] = lambda: conn
    monkeypatch.setattr(llm, "embed", lambda texts: [unit_vec(1) for _ in texts])
    monkeypatch.setattr(settings, "places_url", "http://places")
    monkeypatch.setattr(places_client, "_http", TestClient(places_service.app))
    monkeypatch.setattr(places_client, "_dests", None)
    yield
    places_service.app.dependency_overrides.clear()


def test_client_reads_through_service(conn, svc):
    far = add_place(conn, name="Xa", vec=5, tags=["yen-tinh"])
    near = add_place(conn, name="Gần", vec=1, kind="cafe")
    found = places_client.search_places(None, "da-lat", "cafe", no_embed)
    assert [p.id for p in found] == [near, far] and found[0].name == "Gần"
    assert [p.id for p in places_client.search_places(None, "da-lat", "x", no_embed, kind="cafe")] == [near]
    assert [p.id for p in places_client.search_places(None, "da-lat", "x", no_embed, exclude_tags=["yen-tinh"])] == [near]
    assert [p.id for p in places_client.similar_places(None, near, "tham-quan")] == [far]
    assert places_client.similar_places(None, near, "tham-quan", exclude_ids={far}) == []
    assert set(places_client.get_places(None, [near, far])) == {near, far}
    assert places_client.get_places(None, []) == {}
    assert places_client.list_destinations(None)[0]["slug"] == "da-lat"


def test_places_down_raises(svc, monkeypatch):
    kill(monkeypatch)
    with pytest.raises(places_client.PlacesDown):
        places_client.get_places(None, [1])


def test_service_5xx_is_places_down(svc, monkeypatch):
    """Service trả 5xx (vd embedding lỗi) cũng là 'places không dùng được', không phải lỗi lạ."""
    def boom(texts):
        raise RuntimeError("embedding hỏng")
    monkeypatch.setattr(llm, "embed", boom)
    monkeypatch.setattr(places_client, "_http", TestClient(places_service.app, raise_server_exceptions=False))
    with pytest.raises(places_client.PlacesDown):
        places_client.search_places(None, "da-lat", "x", no_embed)


def test_destinations_survive_places_down(conn, svc, monkeypatch):
    add_place(conn)
    assert places_client.list_destinations(None)[0]["slug"] == "da-lat"
    kill(monkeypatch)
    assert places_client.list_destinations(None)[0]["slug"] == "da-lat"


def test_destinations_never_read_then_places_down_raises(svc, monkeypatch):
    kill(monkeypatch)
    with pytest.raises(places_client.PlacesDown):
        places_client.list_destinations(None)


def test_guarded_reports_places_down():
    def job():
        yield trips.sse({"type": "thinking", "text": "…"})
        raise places_client.PlacesDown("x")
    out = list(trips.guarded(job()))
    assert out[-1] == trips.sse({"type": "error", "message": places_client.PLACES_DOWN})


def test_plan_through_service_then_places_dies(conn, client, svc, monkeypatch):  # noqa: F811
    """Lập lịch qua service places; places chết → Trip cũ vẫn mở được, việc cần Place trả 503 (spec S27)."""
    use_llm(monkeypatch, happy(add_place(conn, kind="cafe")))
    h = auth(client)
    evs = events(client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h))
    assert evs[-1]["type"] == "itinerary"
    tid = evs[-1]["trip_id"]
    kill(monkeypatch)
    assert client.get(f"/trips/{tid}", headers=h).json()["version"] == 1
    assert client.get("/trips", headers=h).json()[0]["destination_name"] == "da-lat"
    r = client.post(f"/trips/{tid}/restore/1", headers=h)
    assert r.status_code == 503 and r.json()["detail"] == places_client.PLACES_DOWN
    use_llm(monkeypatch, happy(1))  # lượt mới: đọc yêu cầu xong, tới lượt tìm Place thì places đã chết
    evs = events(client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h))
    assert evs[-1] == {"type": "error", "message": places_client.PLACES_DOWN}


def test_distance_endpoint_returns_matrix(monkeypatch):
    def goong(origins, destinations, mode):
        distance._cache[distance._key(origins[0], destinations[0], "bike")] = (1.5, 4)
    monkeypatch.setattr(distance, "goong", goong)
    r = TestClient(places_service.app).post("/distance", json={
        "origins": [{"lat": 1, "lon": 2}], "destinations": [{"lat": 3, "lon": 4}, {"lat": 5, "lon": 6}],
        "mode": "xe-may"})
    assert r.json() == {"rows": [[[1.5, 4], None]]}
