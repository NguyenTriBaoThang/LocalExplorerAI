"""Queue lập lịch trên Redis Streams, phía api: giới hạn theo User, đẩy việc, chuyển event về client (spec scale §5).

Phía worker ở app/worker.py.
"""
import json
import math
import time
import uuid

from fastapi import HTTPException
from redis.exceptions import RedisError

from app import kv
from app.config import settings

_now = time.time  # test thay bằng đồng hồ giả
STREAM, GROUP = "jobs", "planners"
TTL_S = 3600  # events:{job_id} và các khoá job:{job_id}:* sống bấy nhiêu giây
QUIET_S = 120  # chờ event mới tối đa bấy nhiêu giây rồi báo lỗi (không có planner nào chạy)


def check_rate(user_id: int) -> None:
    """Mỗi User tối đa PLAN_RPM việc mỗi phút (cửa sổ cố định). Redis lỗi → cho qua (spec §5.3)."""
    c = kv.client()
    if c is None or not settings.plan_rpm:
        return
    now = _now()
    key = f"rl:{user_id}:{int(now // 60)}"
    try:
        n = c.incr(key)
        if n == 1:
            c.expire(key, 120)
        if n <= settings.plan_rpm:
            return
        c.incr("rl:blocked")
    except RedisError:
        return
    wait = max(1, math.ceil(60 - now % 60))
    raise HTTPException(429, f"Bạn gửi yêu cầu quá nhanh, chờ {wait} giây rồi thử lại nhé.",
                        headers={"Retry-After": str(wait)})


def _error(message: str) -> str:
    return f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False)}\n\n"


def enqueue(kind: str, user_id: int, params: dict) -> str:
    """Đẩy một việc vào stream; trả job_id. Redis lỗi → 503 (spec §10: redis chết thì không lập lịch được)."""
    job_id = uuid.uuid4().hex
    try:
        c = kv.client()
        c.set(f"job:{job_id}:user", user_id, ex=TTL_S)
        c.xadd(STREAM, {"job_id": job_id, "kind": kind, "user_id": user_id,
                        "params": json.dumps(params, ensure_ascii=False)}, maxlen=1000, approximate=True)
    except RedisError:
        raise HTTPException(503, "Hệ thống lập lịch tạm không dùng được, bạn thử lại sau nhé.") from None
    return job_id


def owner(job_id: str) -> int | None:
    v = kv.get(f"job:{job_id}:user")
    return int(v) if v else None


def _add(job_id: str, fields: dict) -> None:
    c, key = kv.client(), f"events:{job_id}"
    c.xadd(key, fields)
    c.expire(key, TTL_S)


def publish(job_id: str, data: str) -> None:
    """Worker ghi một event (chuỗi SSE hoàn chỉnh) cho việc."""
    _add(job_id, {"data": data})


def finish(job_id: str) -> None:
    """Worker đánh dấu việc đã xong: relay dừng ở đây."""
    _add(job_id, {"end": "1"})


def complete(job_id: str, last: str | None) -> None:
    """Worker khép việc trong một MULTI: event cuối, mục end và cờ done cùng có hoặc cùng không.

    Tách rời thì Redis chập chờn giữa chừng để lại cờ done mà thiếu event cuối: client không bao giờ thấy lịch.
    """
    key, p = f"events:{job_id}", kv.client().pipeline()
    if last is not None:
        p.xadd(key, {"data": last})
    p.xadd(key, {"end": "1"})
    p.expire(key, TTL_S)
    p.set(f"job:{job_id}:done", 1, ex=TTL_S)
    p.execute()


def relay(job_id: str):
    """Phát lại events:{job_id} từ đầu dưới dạng SSE, tới khi gặp mục end. Bản api nào cũng đọc được.

    ponytail: generator đồng bộ, mỗi stream đang mở giữ một thread trong pool 40 thread của một bản api
    (như chế độ một tiến trình). Cần nhiều stream đồng thời hơn thì viết lại bằng redis.asyncio.
    """
    c, key, last, quiet_since = kv.client(), f"events:{job_id}", "0", _now()
    while True:
        try:
            got = c.xread({key: last}, block=500, count=100)
        except RedisError:
            yield _error("Mất kết nối tới hệ thống lập lịch, bạn mở lại chuyến đi sau ít phút nhé.")
            return
        for _, entries in got or []:
            for entry_id, fields in entries:
                if "end" in fields:
                    return
                yield fields["data"]
                last = entry_id
            quiet_since = _now()
        if _now() - quiet_since > QUIET_S:
            yield _error("Hệ thống lập lịch đang bận hoặc chưa chạy, bạn thử lại sau nhé.")
            return
