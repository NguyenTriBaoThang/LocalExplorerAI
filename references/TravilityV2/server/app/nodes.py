"""Nhịp tim của tiến trình chạy nhiều bản: api, planner, planner-agent (spec scale S31).

Mỗi bản ghi `role:hostname → giờ` vào sorted set `nodes`; trang "Hệ thống" đọc để biết bản nào còn sống.
Thiếu REDIS_URL hoặc Redis lỗi thì bỏ qua, không chặn (spec §10).
"""
import socket
import threading
import time

from redis.exceptions import RedisError

from app import kv

_now = time.time  # test thay bằng đồng hồ giả
KEY = "nodes"
BEAT_S = 2
DEAD_S = 6  # im lặng quá bấy nhiêu giây = chết
# ponytail: bản chết được nhớ 10 phút rồi bỏ. Container bị tạo lại (hostname mới) để lại "node ma" đỏ trong
# khoảng đó; xoá ngay bằng `redis-cli del nodes`. Cần sạch tự động thì cho bản tắt êm tự ZREM khi nhận SIGTERM.
FORGET_S = 600


def beat(role: str, host: str | None = None) -> None:
    c = kv.client()
    if c is None:
        return
    try:
        c.zadd(KEY, {f"{role}:{host or socket.gethostname()}": _now()})
    except RedisError:
        pass


def start(role: str) -> threading.Event:
    """Báo nhịp tim ở thread nền tới khi tiến trình thoát (hoặc tới khi Event trả về được set — test dùng).

    Thiếu REDIS_URL thì không làm gì.
    """
    stop = threading.Event()
    if kv.client() is None:
        return stop

    def loop():
        beat(role)
        while not stop.wait(BEAT_S):
            beat(role)

    threading.Thread(target=loop, daemon=True, name="nodes-beat").start()
    return stop


def seen() -> list[dict] | None:
    """Mọi bản đã báo nhịp tim trong 10 phút qua, cũ trước; None khi không có Redis hoặc Redis lỗi."""
    c = kv.client()
    if c is None:
        return None
    now = _now()
    try:
        c.zremrangebyscore(KEY, "-inf", now - FORGET_S)
        rows = c.zrange(KEY, 0, -1, withscores=True)
    except RedisError:
        return None
    out = []
    for member, at in rows:
        role, host = member.split(":", 1)
        out.append({"role": role, "host": host, "up": now - at <= DEAD_S})
    return out
