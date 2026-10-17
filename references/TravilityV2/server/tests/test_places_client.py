from app import places_client
from app.config import settings
from tests.conftest import TEST_URL
from tests.helpers import add_place, unit_vec

DEAD = "postgresql://travility:travility@127.0.0.1:1/travility"  # không ai nghe cổng 1
READ_ONLY = TEST_URL + "?options=-c%20default_transaction_read_only%3Don"  # giống hot standby: lệnh ghi lỗi


def embed(texts):
    return [unit_vec(1) for _ in texts]


def test_simple_mode_reads_through_callers_conn(conn):
    far = add_place(conn, name="Xa", vec=5)
    near = add_place(conn, name="Gần", vec=1, kind="cafe")
    assert [p.id for p in places_client.search_places(conn, "da-lat", "cafe yên tĩnh", embed)] == [near, far]
    assert [p.id for p in places_client.search_places(conn, "da-lat", "x", embed, kind="cafe")] == [near]
    assert places_client.get_places(conn, [near])[near].name == "Gần"
    assert [p.id for p in places_client.similar_places(conn, near, "tham-quan")] == [far]
    assert places_client.list_destinations(conn)[0]["slug"] == "da-lat"


def test_replica_is_read_and_callers_conn_ignored(conn, monkeypatch):
    """Có bản sao: không đụng node chính, không dùng conn của người gọi, không chạy lệnh ghi nào."""
    pid = add_place(conn, name="A")
    monkeypatch.setattr(settings, "catalog_replica_url", READ_ONLY)
    monkeypatch.setattr(settings, "database_url", DEAD)
    assert places_client.get_places(None, [pid])[pid].name == "A"
    assert [p.id for p in places_client.search_places(None, "da-lat", "gì đó", embed)] == [pid]
    assert places_client.list_destinations(None)[0]["slug"] == "da-lat"


def test_replica_down_falls_back_to_primary(conn, monkeypatch):
    pid = add_place(conn, name="A")
    monkeypatch.setattr(settings, "catalog_replica_url", DEAD)
    monkeypatch.setattr(settings, "database_url", TEST_URL)
    assert places_client.get_places(None, [pid])[pid].name == "A"


def test_shards_without_replica_read_catalog_primary(conn, monkeypatch):
    """Có SHARD_URLS thì conn của người gọi là kết nối shard (không có bảng places) → phải đọc database chung."""
    pid = add_place(conn, name="A")
    monkeypatch.setattr(settings, "shard_urls", "postgresql://x/0,postgresql://x/1")
    monkeypatch.setattr(settings, "database_url", TEST_URL)
    assert places_client.get_places(None, [pid])[pid].name == "A"
