import logging
from pathlib import Path

import psycopg
from fastapi import HTTPException
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from app.config import settings

logger = logging.getLogger(__name__)
CATALOG_SCHEMA = Path(__file__).with_name("schema_catalog.sql")  # users, destinations, places
SHARD_SCHEMA = Path(__file__).with_name("schema_shard.sql")  # trips, itineraries, proposals, messages
SHARD_DOWN = "Dữ liệu chuyến đi tạm không truy cập được, bạn thử lại sau nhé."
READ_ONLY = "Hệ thống đang ở chế độ chỉ đọc, tạm chưa đăng ký được. Bạn thử lại sau nhé."
CATALOG_DOWN = "Hệ thống tài khoản tạm không truy cập được, bạn thử lại sau nhé."
CONNECT_TIMEOUT_S = 2  # node chết phải lộ ra nhanh để còn chuyển sang node khác (spec scale §10)


def _open(url: str) -> psycopg.Connection:
    return psycopg.connect(url, row_factory=dict_row, autocommit=True, connect_timeout=CONNECT_TIMEOUT_S)


def connect(url: str | None = None) -> psycopg.Connection:
    """Kết nối node chính của database chung (ghi được, có kiểu vector)."""
    conn = _open(url or settings.database_url)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    return conn


def catalog_read() -> psycopg.Connection:
    """Kết nối chỉ để đọc Place / Destination: bản sao nếu có CATALOG_REPLICA_URL, bản sao chết → node chính (spec §8)."""
    if settings.catalog_replica_url:
        try:
            conn = _open(settings.catalog_replica_url)
        except psycopg.OperationalError:
            logger.warning("bản sao pg-catalog không kết nối được, đọc node chính")
        else:
            register_vector(conn)  # bản sao là hot standby: không CREATE EXTENSION ở đây
            return conn
    return connect()


def apply_schema(conn: psycopg.Connection, catalog: bool = True, shard: bool = True) -> None:
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(4949)")  # các bản api và planner trong cụm khởi động cùng lúc
        if catalog:
            conn.execute(CATALOG_SCHEMA.read_text())
        if shard:
            conn.execute(SHARD_SCHEMA.read_text())
    if catalog:
        register_vector(conn)  # extension có thể vừa được tạo lại → đăng ký lại kiểu vector


def shard_urls() -> list[str]:
    return [u.strip() for u in settings.shard_urls.split(",") if u.strip()]


def shard_of(user_id: int) -> int:
    return user_id % max(len(shard_urls()), 1)


def shard_conn(user_id: int) -> psycopg.Connection:
    """Kết nối tới nơi chứa Trip của User: shard user_id % N; thiếu SHARD_URLS → DATABASE_URL (spec scale §9.1)."""
    urls = shard_urls()
    return _open(urls[user_id % len(urls)]) if urls else connect()


def init_schemas() -> None:
    """Lúc khởi động: áp schema chung lên node chính và schema Trip lên từng shard.

    Trong cụm, node chết không chặn khởi động: shard chết thì User của shard kia vẫn dùng được, node chính của
    database chung chết thì chỉ không đăng ký được (spec scale §10). Chế độ một database thì vẫn phải có database.
    """
    urls = shard_urls()
    try:
        with connect() as conn:
            apply_schema(conn, shard=not urls)
    except psycopg.OperationalError:
        if not urls:
            raise
        logger.warning("pg-catalog không kết nối được lúc khởi động: dữ liệu chung ở chế độ chỉ đọc")
    for i, url in enumerate(urls):
        try:
            with _open(url) as conn:
                apply_schema(conn, catalog=False)
        except psycopg.OperationalError:
            logger.warning("shard %d không kết nối được lúc khởi động", i)


def get_conn():
    """Kết nối database chung cho handler tài khoản.

    Node chính chết → bản sao: đăng nhập vẫn đọc được, lệnh ghi bị Postgres từ chối (spec §10, ADR-0008).
    Cả hai chết → 503.
    """
    try:
        conn = connect()
    except psycopg.OperationalError:
        try:
            if not settings.catalog_replica_url:
                raise
            conn = _open(settings.catalog_replica_url)
        except psycopg.OperationalError:
            raise HTTPException(503, CATALOG_DOWN) from None
    try:
        yield conn
    finally:
        conn.close()
