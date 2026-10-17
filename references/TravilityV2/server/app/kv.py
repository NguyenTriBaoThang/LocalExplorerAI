"""Lớp mỏng trên Redis. Thiếu REDIS_URL hoặc Redis lỗi → coi như trượt cache, không chặn (spec scale §10)."""
import redis

from app.config import settings

_client: redis.Redis | None = None


def client() -> redis.Redis | None:
    global _client
    if not settings.redis_url:
        return None
    if _client is None:
        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True,
                                       socket_timeout=1, socket_connect_timeout=1)
    return _client


def get(key: str) -> str | None:
    c = client()
    if c is None:
        return None
    try:
        return c.get(key)
    except redis.RedisError:
        return None


def put(key: str, value: str, ex: int | None = None) -> None:
    c = client()
    if c is None:
        return
    try:
        c.set(key, value, ex=ex)
    except redis.RedisError:
        pass
