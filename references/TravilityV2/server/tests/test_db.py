import threading

import psycopg
import pytest

from app import db
from app.config import settings
from app.db import apply_schema, connect
from tests.conftest import TEST_URL


def test_apply_schema_survives_concurrent_startup(conn):
    """2 bản api + 2 planner cùng khởi động trên database trống."""
    conns = [connect(TEST_URL) for _ in range(4)]
    conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    errors, gate = [], threading.Barrier(4, timeout=10)

    def boot(c):
        try:
            gate.wait()
            apply_schema(c)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=boot, args=(c,)) for c in conns]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for c in conns:
        c.close()
    assert errors == []
    assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0


DEAD = "postgresql://travility:travility@127.0.0.1:1/travility"


def test_cluster_boots_while_catalog_primary_is_down(shards, monkeypatch):
    monkeypatch.setattr(settings, "database_url", DEAD)
    db.init_schemas()  # không ném: Trip nằm ở shard, đăng nhập đọc bản sao (spec §10)


def test_simple_mode_still_refuses_to_boot_without_its_database(monkeypatch):
    monkeypatch.setattr(settings, "database_url", DEAD)
    with pytest.raises(psycopg.OperationalError):
        db.init_schemas()
