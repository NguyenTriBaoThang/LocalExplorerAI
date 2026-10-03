"""Shared Redis fixed-window limiter. Clients are keyed only by the socket peer;
forwarded headers are deliberately ignored unless a trusted proxy is explicitly added.
"""

from __future__ import annotations

from app.core.config import settings

_client = None
_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""


def _redis():
    global _client
    if _client is None:
        from redis import Redis
        _client = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1, decode_responses=True)
    return _client


def ping_redis() -> bool:
    try:
        return bool(_redis().ping())
    except Exception:
        return False


def check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
    count = int(_redis().eval(_SCRIPT, 1, key, window_seconds))
    return count <= limit, max(0, limit - count)


def reset_redis_for_tests() -> None:
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
    _client = None
