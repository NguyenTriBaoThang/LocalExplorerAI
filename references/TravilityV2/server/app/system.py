"""GET /system/status: trạng thái cụm cho trang "Hệ thống" (spec scale §12, S31).

Node một bản được dò ngay trong request; tiến trình nhiều bản đọc từ nhịp tim (app/nodes.py).
Node nào chỉ có mặt khi biến môi trường của nó được đặt, nên chế độ đơn giản trả bản api này và database.
"""
import socket
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import httpx
import psycopg
from fastapi import APIRouter, Depends, Request
from redis.exceptions import RedisError

from app import db, jobs, kv, nodes
from app.auth import current_user
from app.config import settings

router = APIRouter()
PROBE_TIMEOUT_S = 2
# Bản sao đã phát lại hết WAL nhận được → trễ 0; nếu chỉ lấy now() - mốc phát lại thì node chính rảnh sẽ bị báo trễ.
# `<=` chứ không phải `=`: bản sao vừa khởi động lại phát lại WAL có sẵn trên đĩa nên mốc nhận nhỏ hơn mốc phát lại.
LAG_SQL = """SELECT CASE WHEN pg_last_wal_receive_lsn() <= pg_last_wal_replay_lsn() THEN 0
                         ELSE EXTRACT(EPOCH FROM now() - pg_last_xact_replay_timestamp()) * 1000 END AS ms"""
STAT_KEYS = {"cache_hit": "gw:stat:hit", "cache_miss": "gw:stat:miss", "provider_call": "gw:stat:provider_call",
             "provider_wait": "gw:stat:wait", "provider_fallback": "gw:stat:fallback", "rate_limited": "rl:blocked"}
_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="probe")
_last: list[dict] = []  # các bản api / planner thấy được gần nhất; Redis chết thì trả lại với trạng thái unknown


def _pg(url: str, lag: bool = False) -> dict | None:
    """{} nếu node trả lời (bản sao kèm lag_ms), None nếu chết."""
    try:
        with db._open(url) as c:
            if not lag:
                c.execute("SELECT 1")
                return {}
            ms = c.execute(LAG_SQL).fetchone()["ms"]
            return {"lag_ms": None if ms is None else round(float(ms))}
    except psycopg.Error:
        return None


def _redis() -> dict | None:
    try:
        kv.client().ping()
        return {}
    except RedisError:
        return None


def _http(base: str) -> dict | None:
    try:
        return {} if httpx.get(base + "/health", timeout=PROBE_TIMEOUT_S).status_code == 200 else None
    except httpx.HTTPError:
        return None


def _targets() -> list[tuple]:
    """(tên, role, hàm dò) của các node một bản đang được cấu hình (spec S12)."""
    out = [("pg-catalog", "pg-catalog", partial(_pg, settings.database_url))]
    if settings.catalog_replica_url:
        out.append(("pg-catalog-replica", "pg-catalog-replica", partial(_pg, settings.catalog_replica_url, lag=True)))
    out += [(f"pg-shard-{i}", "pg-shard", partial(_pg, url)) for i, url in enumerate(db.shard_urls())]
    if settings.redis_url:
        out.append(("redis", "redis", _redis))
    # ponytail: nhận ra llm-gateway bằng http:// (địa chỉ nội bộ cụm); provider thật luôn là https và không được dò.
    # Gateway đặt sau TLS thì thêm biến GATEWAY_URL riêng.
    if settings.llm_base_url.startswith("http://"):
        out.append(("llm-gateway", "llm-gateway",
                    partial(_http, settings.llm_base_url.rstrip("/").removesuffix("/v1"))))
    if settings.places_url:
        out.append(("places", "places", partial(_http, settings.places_url)))
    return out


def _replicas(me: str) -> list[dict]:
    """Các bản api / planner / planner-agent theo nhịp tim; bản đang trả lời luôn có mặt và luôn sống."""
    global _last
    mine = {"name": me, "role": "api", "state": "up"}
    beats = nodes.seen()
    if beats is None:
        others = [{**n, "state": "unknown"} for n in _last]
    else:
        _last = others = [{"name": f"{b['role']} {b['host']}", "role": b["role"],
                           "state": "up" if b["up"] else "down"} for b in beats]
    return sorted([mine] + [n for n in others if n["name"] != me], key=lambda n: (n["role"], n["name"]))


def _stats() -> dict | None:
    c = kv.client()
    if c is None:
        return None
    try:
        vals = c.mget(*STAT_KEYS.values())
        groups = c.xinfo_groups(jobs.STREAM) if c.exists(jobs.STREAM) else []
    except RedisError:
        return None
    g = next((g for g in groups if g["name"] == jobs.GROUP), {})
    return {**{k: int(v or 0) for k, v in zip(STAT_KEYS, vals)},
            "waiting": int(g.get("lag") or 0), "running": int(g.get("pending") or 0)}


@router.get("/system/status")
def status(request: Request, user_id: int = Depends(current_user)):
    me = f"api {socket.gethostname()}"
    targets = _targets()
    probed = [{"name": name, "role": role, "state": "down" if got is None else "up", **(got or {})}
              for (name, role, _), got in zip(targets, _pool.map(lambda t: t[2](), targets))]
    via = [{"name": "nginx", "role": "nginx", "state": "up"}] if request.headers.get("x-via") == "nginx" else []
    return {"nodes": via + _replicas(me) + probed, "served_by": me,
            "my_shard": db.shard_of(user_id) if db.shard_urls() else None,
            "planner_mode": settings.planner_mode, "stats": _stats()}
