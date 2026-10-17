import os

import pytest

os.environ["GOONG_API_KEY"] = ""  # máy dev có key trong .env — test không được gọi Goong thật
os.environ["REDIS_URL"] = ""  # test không đụng Redis, trừ khi xin fixture rds
os.environ["DEMO_TODAY"] = ""
os.environ["PLANNER_MODE"] = ""  # máy dev có thể đặt multi trong .env — test mặc định chạy agent đơn
os.environ["PLACES_URL"] = ""  # test mặc định đọc Place trong tiến trình, một database
os.environ["CATALOG_REPLICA_URL"] = ""
os.environ["SHARD_URLS"] = ""

from app import db, distance, kv
from app.config import settings
from app.db import apply_schema, connect

TEST_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://travility:travility@localhost:5432/travility_test"
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")


@pytest.fixture
def conn():
    c = connect(TEST_URL)
    c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    apply_schema(c)
    yield c
    c.close()


@pytest.fixture
def rds(monkeypatch):
    """Redis thật (DB 15) đã xoá sạch; settings.redis_url trỏ vào đó trong lúc test chạy."""
    monkeypatch.setattr(settings, "redis_url", TEST_REDIS_URL)
    monkeypatch.setattr(kv, "_client", None)
    c = kv.client()
    c.flushdb()
    yield c
    c.flushdb()


@pytest.fixture(autouse=True)
def _clean_distance():
    distance._cache.clear()
    distance._down_until = 0.0


@pytest.fixture
def shards(conn, monkeypatch):
    """Hai database shard thật, trống; DATABASE_URL trỏ database test (đóng vai pg-catalog), SHARD_URLS trỏ hai shard."""
    urls = []
    for i in range(2):
        name = f"travility_test_s{i}"
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            conn.execute(f"CREATE DATABASE {name}")
        url = f"{TEST_URL.rsplit('/', 1)[0]}/{name}"
        with db._open(url) as c:
            c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            apply_schema(c, catalog=False)
        urls.append(url)
    monkeypatch.setattr(settings, "database_url", TEST_URL)
    monkeypatch.setattr(settings, "shard_urls", ",".join(urls))
    return urls
