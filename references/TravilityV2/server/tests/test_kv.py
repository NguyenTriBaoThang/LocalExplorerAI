from app import kv
from app.config import settings


def test_no_redis_url_is_noop(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "")
    kv.put("a", "1")
    assert kv.client() is None and kv.get("a") is None


def test_roundtrip_and_ttl(rds):
    kv.put("a", "1")
    kv.put("b", "2", ex=60)
    assert kv.get("a") == "1" and kv.get("khong-co") is None
    assert rds.ttl("a") == -1 and 0 < rds.ttl("b") <= 60


def test_redis_down_is_a_miss(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")  # không có gì nghe ở cổng 1
    monkeypatch.setattr(kv, "_client", None)
    kv.put("a", "1")  # không được ném lỗi
    assert kv.get("a") is None
