# Scale T6 — Trang "Hệ thống", load test, chế độ chỉ đọc, client nối lại Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Context

T2–T5 của lát scale đã merge (PR #55–#58): cụm 15 container có Redis, `llm-gateway`, queue + `planner`, `nginx` + 2 `api`, đa agent, service `places`, bản sao đọc, 2 shard. T6 (#52) là tuần cuối của hạ tầng: cho giảng viên **thấy** cụm phản ứng khi tắt node và có **số đo**. Sau T6 kiến trúc đóng băng.

Ba món nợ đã ghi "để T6" ở các tuần trước được gộp vào (S30): `pg-catalog` chính chết thì `api` không khởi động lại được và không đăng nhập được; client chưa nối lại bằng `job_id` (S20); chưa có `scripts/smoke_cluster.sh` (spec §13).

**Chốt trong buổi grill 2026-10-02 (đã ghi vào spec §2):**

| # | Quyết định |
|---|---|
| S30 | T6 = #52 + `api` / `planner` khởi động và đăng nhập được khi `pg-catalog` chính chết + client nối lại bằng `job_id` + `scripts/smoke_cluster.sh` |
| S31 | Node một bản do bản `api` đang trả lời dò song song; tiến trình nhiều bản ghi nhịp tim vào sorted set `nodes` mỗi 2 giây, im quá 6 giây là chết, quá 10 phút thì bỏ khỏi sơ đồ. Redis chết → chỉ biết chắc bản `api` đang trả lời |
| S32 | Trang "Hệ thống" là lớp phủ, node xếp theo tầng như sơ đồ §4, không vẽ đường nối |
| S33 | "Cache tắt" đo 2 lượt lập lịch tuần tự với provider thật; "cache bật" (`replay`) đo 20 lượt đồng thời trở lên |
| S34 | Client chỉ nối lại khi luồng SSE đứt giữa chừng, tối đa 2 lần qua `GET /jobs/{job_id}/events`, bỏ qua event đã nhận |

**Goal:** `GET /system/status` + trang "Hệ thống" cho thấy node nào sống; `pg-catalog` chính chết thì chỉ đăng ký bị từ chối; client tự nối lại luồng lập lịch khi một bản `api` chết; có script load test, smoke test và runbook chạy được toàn bộ bảng trình diễn spec §12 (trừ mô hình mưa).

**Architecture:** `app/nodes.py` là nhịp tim của tiến trình nhiều bản trên Redis. `app/system.py` gộp nhịp tim, kết quả dò node một bản và số đếm có sẵn trong Redis thành một JSON. `db.get_conn` tự lùi về bản sao khi node chính chết, nên handler đăng nhập không đổi; đăng ký gặp lỗi "chỉ đọc" của Postgres thì trả 503. Client thêm một component lớp phủ và một vòng nối lại trong `streamSSE`.

**Tech Stack:** FastAPI, psycopg3, redis-py, httpx (sync để dò, async cho load test), React 19 + Tailwind 4, vitest, docker compose.

**Spec:** `docs/superpowers/specs/2026-10-01-scale-he-phan-tan-design.md` — đọc §2 (S30–S34), §10, §12, §13. ADR-0008.

## Global Constraints

- Thiếu biến môi trường của cụm → chạy như chế độ một tiến trình. 341 test server và 33 test client hiện có phải xanh, **không sửa assert cũ**.
- **Không sửa logic** `rules.py`, `replan.py`, `followup.py`, `agent.py`, `multi.py`, `gateway.py`, `places.py`, `places_service.py`, `jobs.py`.
- Giữ tên dependency `db.get_conn`: 5 file test đang override nó.
- Không thêm dependency (server lẫn client). Test dùng Postgres và Redis thật.
- Không thêm container, không thêm service: sau T6 kiến trúc đóng băng.
- Thông báo hướng tới người dùng là tiếng Việt. Hai câu mới, cố định:
  - `READ_ONLY = "Hệ thống đang ở chế độ chỉ đọc, tạm chưa đăng ký được. Bạn thử lại sau nhé."`
  - `CATALOG_DOWN = "Hệ thống tài khoản tạm không truy cập được, bạn thử lại sau nhé."`
- Lệnh test: `docker compose up -d db redis && cd server && uv run pytest` · `cd client && npm test && npm run build`.
- Trong runbook và các bước dưới, `dc` = `docker compose -f docker-compose.cluster.yml`.
- Commit message kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Node ma sau khi tạo lại container.** `dc up -d --build` hoặc đổi biến môi trường tạo container mới với hostname mới; bản cũ còn trong sorted set `nodes` và hiện đỏ tối đa 10 phút. Người demo phải có cách xoá ngay: runbook và `smoke_cluster.sh` chạy `redis-cli del nodes` (bản sống tự ghi lại sau 2 giây). Task 1 có test "bản mới ghi lại sau khi khoá bị xoá".
2. **Nối lại phát trùng event.** `GET /jobs/{id}/events` phát lại từ đầu; client không được thêm lần hai các dòng "Đang tìm…" đã hiện (Task 5 có test).
3. **Đăng ký trúng bản sao.** Node chính chết, `get_conn` trả kết nối bản sao; `INSERT` phải thành 503 `READ_ONLY`, không phải 500 (Task 3 có test).
4. **Trang "Hệ thống" ở chế độ đơn giản gọi ra Internet.** `LLM_BASE_URL` trỏ provider thật (https) thì không được dò `/health` của provider mỗi 2 giây (Task 2 có test: `httpx.get` bị gọi là test hỏng).
5. **Một node treo làm chồng request.** Node bị `docker pause` khiến mỗi lần dò chờ 2 giây; client phải chờ phản hồi xong mới hẹn lần làm mới kế tiếp, không dùng `setInterval` (Task 4, kiểm bằng đọc code khi review và bước `docker pause` ở Task 7).

## File Structure

| File | Trách nhiệm |
|---|---|
| `server/app/nodes.py` (mới) | Nhịp tim: `beat`, `start`, `seen` trên sorted set `nodes` |
| `server/app/system.py` (mới) | Router `GET /system/status`: dò node một bản, gộp nhịp tim và số đếm Redis |
| `server/app/db.py` | `get_conn` lùi về bản sao rồi 503; `init_schemas` không chết theo `pg-catalog` khi có shard; `READ_ONLY`, `CATALOG_DOWN` |
| `server/app/auth.py` | `register` đổi lỗi "chỉ đọc" thành 503 |
| `server/app/main.py`, `worker.py` | Gọi `nodes.start(role)`; gắn router `system` |
| `server/scripts/loadtest.py` (mới) | Load test: `percentile`, `summarize`, `row`, vòng chạy asyncio |
| `scripts/smoke_cluster.sh` (mới) | Dựng cụm, một lượt lập lịch, kiểm mọi node sống |
| `docker/nginx.conf`, `docker-compose.cluster.yml` | Header `X-Via`; `CATALOG_REPLICA_URL` cho `api` / `planner` |
| `client/src/api.ts` | Kiểu `SystemStatus`, `getSystemStatus`, `tiers`; `streamSSE` nối lại |
| `client/src/components/SystemPage.tsx` (mới) | Lớp phủ sơ đồ cụm, tự làm mới |
| `client/src/components/Rail.tsx`, `App.tsx` | Nút "Hệ thống" và trạng thái mở |
| `docs/runbook-cum.md`, `docs/ROADMAP.md`, `docs/2026-09-25-hien-trang-app.md` | Runbook T6 + số đo; khép lát |

---

### Task 1: Nhịp tim node

**Files:**
- Create: `server/app/nodes.py`
- Modify: `server/app/main.py:15-25` (lifespan), `server/app/worker.py:127-137` (`main`)
- Test: `server/tests/test_nodes.py`

**Interfaces:**
- Consumes: `kv.client()` (trả `redis.Redis | None`).
- Produces: `nodes.beat(role: str, host: str | None = None) -> None`; `nodes.start(role: str) -> None`; `nodes.seen() -> list[dict] | None` với mỗi phần tử `{"role": str, "host": str, "up": bool}`, xếp theo thời điểm nhịp tim tăng dần; `None` khi không có Redis hoặc Redis lỗi. Hằng `nodes.KEY = "nodes"`, biến `nodes._now` thay được trong test.

- [ ] **Step 1: Viết test hỏng**

`server/tests/test_nodes.py`:

```python
import time

import pytest

from app import kv, nodes
from app.config import settings


@pytest.fixture
def clock(monkeypatch):
    t = [1_000_000.0]
    monkeypatch.setattr(nodes, "_now", lambda: t[0])
    return t


def test_without_redis_nothing_happens():
    nodes.beat("api")
    nodes.start("api")
    assert nodes.seen() is None


def test_silent_node_is_down_then_forgotten(rds, clock):
    nodes.beat("planner", "p1")
    clock[0] += 5
    nodes.beat("planner-agent", "a1")
    assert nodes.seen() == [{"role": "planner", "host": "p1", "up": True},
                            {"role": "planner-agent", "host": "a1", "up": True}]
    clock[0] += 2  # p1 đã im 7 giây
    assert [(n["host"], n["up"]) for n in nodes.seen()] == [("p1", False), ("a1", True)]
    clock[0] += 600
    nodes.beat("planner", "p2")
    assert [n["host"] for n in nodes.seen()] == ["p2"]


def test_default_host_is_this_machine(rds):
    nodes.beat("api")
    assert nodes.seen()[0]["host"] and nodes.seen()[0]["role"] == "api"


def test_redis_down_is_silent(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")
    monkeypatch.setattr(kv, "_client", None)
    nodes.beat("api")
    assert nodes.seen() is None


def test_background_beat_comes_back_after_key_is_deleted(rds, monkeypatch):
    """Runbook xoá khoá `nodes` để dọn node ma: bản đang sống phải tự hiện lại."""
    monkeypatch.setattr(nodes, "BEAT_S", 0.05)
    nodes.start("api")
    rds.delete(nodes.KEY)
    deadline = time.time() + 2
    while not nodes.seen() and time.time() < deadline:
        time.sleep(0.02)
    assert [n["role"] for n in nodes.seen()] == ["api"]
```

- [ ] **Step 2: Chạy để thấy hỏng**

Run: `cd server && uv run pytest tests/test_nodes.py -q`
Expected: FAIL `ImportError: cannot import name 'nodes' from 'app'`

- [ ] **Step 3: Viết `server/app/nodes.py`**

```python
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


def start(role: str) -> None:
    """Báo nhịp tim ở thread nền tới khi tiến trình thoát. Thiếu REDIS_URL thì không làm gì."""
    if kv.client() is None:
        return

    def loop():
        while True:
            beat(role)
            time.sleep(BEAT_S)

    threading.Thread(target=loop, daemon=True, name="nodes-beat").start()


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
```

- [ ] **Step 4: Chạy test**

Run: `cd server && uv run pytest tests/test_nodes.py -q`
Expected: 5 passed

- [ ] **Step 5: Gắn vào `api` và worker**

`server/app/main.py` — thêm `nodes` vào import và gọi sau `init_schemas()`:

```python
from app import auth, nodes, proposals, trips, versions
```

```python
    init_schemas()
    nodes.start("api")
```

`server/app/worker.py` — thêm `nodes` vào import (`from app import jobs, kv, multi, nodes, trips`) và trong `main()` ngay sau `init_schemas()`:

```python
    init_schemas()
    nodes.start("planner-agent" if agent else "planner")
```

- [ ] **Step 6: Chạy toàn bộ test server**

Run: `cd server && uv run pytest -q`
Expected: 346 passed (341 cũ + 5 mới)

- [ ] **Step 7: Commit**

```bash
git add server/app/nodes.py server/app/main.py server/app/worker.py server/tests/test_nodes.py
git commit -m "feat(server): nhịp tim của api, planner, planner-agent trên Redis (#52)"
```

---

### Task 2: `GET /system/status`

**Files:**
- Create: `server/app/system.py`
- Modify: `server/app/main.py` (gắn router), `docker/nginx.conf:16` (header `X-Via`)
- Test: `server/tests/test_system.py`

**Interfaces:**
- Consumes: `nodes.seen()`, `nodes.beat()` (Task 1); `db._open(url)`, `db.shard_urls()`, `db.shard_of(user_id)`; `kv.client()`; `jobs.STREAM`, `jobs.GROUP`; `auth.current_user`.
- Produces: `GET /system/status` (cần JWT) trả:

```json
{
  "nodes": [{"name": "api 3f2a…", "role": "api", "state": "up"},
            {"name": "pg-catalog-replica", "role": "pg-catalog-replica", "state": "up", "lag_ms": 0}],
  "served_by": "api 3f2a…",
  "my_shard": 1,
  "planner_mode": "single",
  "stats": {"cache_hit": 0, "cache_miss": 0, "provider_call": 0, "provider_wait": 0,
            "provider_fallback": 0, "rate_limited": 0, "waiting": 0, "running": 0}
}
```

`state` ∈ `up | down | unknown`. `role` ∈ `nginx | api | planner | planner-agent | redis | llm-gateway | places | pg-catalog | pg-catalog-replica | pg-shard`. `my_shard` và `stats` là `null` ở chế độ đơn giản; `stats` cũng `null` khi Redis chết. Tên node shard là `pg-shard-<i>`.

- [ ] **Step 1: Viết test hỏng**

`server/tests/test_system.py`:

```python
import socket

import httpx
import pytest
from fastapi.testclient import TestClient

from app import jobs, kv, nodes, system, worker
from app.config import settings
from app.db import get_conn
from app.main import app
from tests.conftest import TEST_URL
from tests.test_trips_api import auth

DEAD_PG = "postgresql://travility:travility@127.0.0.1:1/travility"  # không ai nghe cổng 1
ME = f"api {socket.gethostname()}"
URL = "/system/status"


@pytest.fixture
def api(conn, monkeypatch):
    monkeypatch.setattr(settings, "database_url", TEST_URL)
    monkeypatch.setattr(settings, "llm_base_url", "https://provider.example/v1")
    monkeypatch.setattr(system, "_last", [])
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def state(body):
    return {n["name"]: n["state"] for n in body["nodes"]}


def test_needs_login(api):
    assert api.get(URL).status_code == 401


def test_simple_mode_is_this_api_and_the_database_and_never_calls_out(api, monkeypatch):
    def no_http(*a, **k):
        raise AssertionError("chế độ đơn giản không được dò ra ngoài")

    monkeypatch.setattr(httpx, "get", no_http)
    b = api.get(URL, headers=auth(api)).json()
    assert state(b) == {ME: "up", "pg-catalog": "up"}
    assert b["served_by"] == ME and b["my_shard"] is None and b["stats"] is None
    assert b["planner_mode"] == "single"


def test_dead_nodes_are_down_and_live_replica_reports_lag(api, monkeypatch):
    h = auth(api)
    monkeypatch.setattr(settings, "catalog_replica_url", DEAD_PG)
    monkeypatch.setattr(settings, "places_url", "http://127.0.0.1:1")
    monkeypatch.setattr(settings, "llm_base_url", "http://127.0.0.1:1/v1")
    s = state(api.get(URL, headers=h).json())
    assert s["pg-catalog-replica"] == s["places"] == s["llm-gateway"] == "down"
    assert s["pg-catalog"] == "up"
    monkeypatch.setattr(settings, "catalog_replica_url", TEST_URL)
    replica = next(n for n in api.get(URL, headers=h).json()["nodes"] if n["name"] == "pg-catalog-replica")
    assert replica["state"] == "up" and replica["lag_ms"] is None  # database test không phải standby


def test_users_shard_and_shard_nodes(api, shards):
    h = auth(api)
    uid = api.get("/auth/me", headers=h).json()["id"]
    b = api.get(URL, headers=h).json()
    assert b["my_shard"] == uid % 2
    assert state(b)["pg-shard-0"] == state(b)["pg-shard-1"] == "up"


def test_heartbeats_and_counters_come_from_redis(api, rds, monkeypatch):
    t = [1_000_000.0]
    monkeypatch.setattr(nodes, "_now", lambda: t[0])
    nodes.beat("planner", "p1")
    t[0] += 7
    nodes.beat("planner-agent", "a1")
    rds.set("gw:stat:hit", 42)
    rds.set("rl:blocked", 3)
    b = api.get(URL, headers=auth(api)).json()
    s = state(b)
    assert (s["planner p1"], s["planner-agent a1"], s["redis"], s[ME]) == ("down", "up", "up", "up")
    assert b["stats"] == {"cache_hit": 42, "cache_miss": 0, "provider_call": 0, "provider_wait": 0,
                          "provider_fallback": 0, "rate_limited": 3, "waiting": 0, "running": 0}


def test_queue_counts_waiting_and_running(api, rds):
    h = auth(api)
    worker.ensure_group(rds)
    jobs.enqueue("message", 1, {})
    jobs.enqueue("message", 1, {})
    rds.xreadgroup(jobs.GROUP, "p1", {jobs.STREAM: ">"}, count=1)
    st = api.get(URL, headers=h).json()["stats"]
    assert (st["waiting"], st["running"]) == (1, 1)


def test_redis_down_keeps_last_seen_nodes_as_unknown(api, rds, monkeypatch):
    h = auth(api)
    nodes.beat("planner", "p1")
    assert state(api.get(URL, headers=h).json())["planner p1"] == "up"
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")
    monkeypatch.setattr(kv, "_client", None)
    b = api.get(URL, headers=h).json()
    s = state(b)
    assert (s["redis"], s["planner p1"], s[ME]) == ("down", "unknown", "up")
    assert b["stats"] is None


def test_nginx_is_listed_only_when_the_request_came_through_it(api):
    h = auth(api)
    assert "nginx" not in state(api.get(URL, headers=h).json())
    assert state(api.get(URL, headers={**h, "X-Via": "nginx"}).json())["nginx"] == "up"
```

- [ ] **Step 2: Chạy để thấy hỏng**

Run: `cd server && uv run pytest tests/test_system.py -q`
Expected: FAIL `ImportError: cannot import name 'system' from 'app'`

- [ ] **Step 3: Viết `server/app/system.py`**

```python
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
LAG_SQL = """SELECT CASE WHEN pg_last_wal_receive_lsn() = pg_last_wal_replay_lsn() THEN 0
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
```

- [ ] **Step 4: Gắn router và header nginx**

`server/app/main.py`:

```python
from app import auth, nodes, proposals, system, trips, versions
```

```python
app.include_router(versions.router)
app.include_router(system.router)
```

`docker/nginx.conf` — thêm một dòng ngay dưới `proxy_set_header Host $host;`:

```nginx
    proxy_set_header X-Via nginx;  # api biết request đi qua nginx → trang "Hệ thống" vẽ node nginx
```

- [ ] **Step 5: Chạy test**

Run: `cd server && uv run pytest tests/test_system.py -q`
Expected: 8 passed

Nếu `test_queue_counts_waiting_and_running` cho `waiting` khác 1: in `rds.xinfo_groups("jobs")` để xem trường `lag` của bản Redis đang chạy; `lag` là `None` thì tính `waiting = xlen - entries-read`.

- [ ] **Step 6: Chạy toàn bộ test server**

Run: `cd server && uv run pytest -q`
Expected: 354 passed

- [ ] **Step 7: Commit**

```bash
git add server/app/system.py server/app/main.py server/tests/test_system.py docker/nginx.conf
git commit -m "feat(server): GET /system/status — dò node một bản, nhịp tim, số đếm queue và cache (#52)"
```

---

### Task 3: Chế độ chỉ đọc khi `pg-catalog` chính chết

**Files:**
- Modify: `server/app/db.py:67-88` (`init_schemas`, `get_conn`), `server/app/auth.py:55-63` (`register`), `docker-compose.cluster.yml:86-95` (`app_env`)
- Test: `server/tests/test_auth.py`, `server/tests/test_db.py`

**Interfaces:**
- Consumes: `db.connect()`, `db._open(url)`, `settings.catalog_replica_url`.
- Produces: `db.READ_ONLY`, `db.CATALOG_DOWN` (chuỗi ở Global Constraints). `db.get_conn` giữ nguyên tên và dạng generator; node chính chết → kết nối bản sao; cả hai chết → `HTTPException(503, CATALOG_DOWN)`. `db.init_schemas()` không ném khi node chính chết **và** có `SHARD_URLS`.

- [ ] **Step 1: Viết test hỏng**

Thêm vào cuối `server/tests/test_auth.py` (và thêm import ở đầu file: `from app.config import settings`, `from app.db import CATALOG_DOWN, READ_ONLY, get_conn`, `from tests.conftest import TEST_URL`):

```python
DEAD = "postgresql://travility:travility@127.0.0.1:1/travility"  # không ai nghe cổng 1
REPLICA = TEST_URL + "?options=-c%20default_transaction_read_only%3Don"  # như hot standby: lệnh ghi lỗi
LOGIN = {"email": "an@example.com", "password": "matkhau123"}


def test_primary_down_login_reads_replica_and_register_is_refused(conn, monkeypatch):
    monkeypatch.setattr(settings, "database_url", TEST_URL)
    api = TestClient(app)  # không override get_conn: đi đường thật
    assert register(api).status_code == 201
    monkeypatch.setattr(settings, "database_url", DEAD)
    monkeypatch.setattr(settings, "catalog_replica_url", REPLICA)
    assert api.post("/auth/login", json=LOGIN).status_code == 200
    r = register(api, email="moi@example.com")
    assert r.status_code == 503 and r.json()["detail"] == READ_ONLY
    monkeypatch.setattr(settings, "catalog_replica_url", DEAD)
    r = api.post("/auth/login", json=LOGIN)
    assert r.status_code == 503 and r.json()["detail"] == CATALOG_DOWN


def test_database_down_in_simple_mode_is_503(monkeypatch):
    monkeypatch.setattr(settings, "database_url", DEAD)
    r = TestClient(app).post("/auth/login", json=LOGIN)
    assert r.status_code == 503 and r.json()["detail"] == CATALOG_DOWN
```

Thêm vào cuối `server/tests/test_db.py` (và import `import psycopg`, `import pytest`, `from app import db`, `from app.config import settings`):

```python
DEAD = "postgresql://travility:travility@127.0.0.1:1/travility"


def test_cluster_boots_while_catalog_primary_is_down(shards, monkeypatch):
    monkeypatch.setattr(settings, "database_url", DEAD)
    db.init_schemas()  # không ném: Trip nằm ở shard, đăng nhập đọc bản sao (spec §10)


def test_simple_mode_still_refuses_to_boot_without_its_database(monkeypatch):
    monkeypatch.setattr(settings, "database_url", DEAD)
    with pytest.raises(psycopg.OperationalError):
        db.init_schemas()
```

- [ ] **Step 2: Chạy để thấy hỏng**

Run: `cd server && uv run pytest tests/test_auth.py tests/test_db.py -q`
Expected: FAIL `ImportError: cannot import name 'CATALOG_DOWN' from 'app.db'`

- [ ] **Step 3: Sửa `server/app/db.py`**

Thêm import `from fastapi import HTTPException` và hai hằng dưới `SHARD_DOWN`:

```python
READ_ONLY = "Hệ thống đang ở chế độ chỉ đọc, tạm chưa đăng ký được. Bạn thử lại sau nhé."
CATALOG_DOWN = "Hệ thống tài khoản tạm không truy cập được, bạn thử lại sau nhé."
```

Thay `init_schemas` và `get_conn`:

```python
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
```

- [ ] **Step 4: Sửa `register` ở `server/app/auth.py`**

Đổi import thành `from app.db import READ_ONLY, SHARD_DOWN, get_conn, shard_conn` và thêm một nhánh `except`:

```python
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Email đã được đăng ký") from None
    except psycopg.errors.ReadOnlySqlTransaction:  # get_conn đã lùi về bản sao: node chính chết
        raise HTTPException(503, READ_ONLY) from None
```

- [ ] **Step 5: Cho `api` và `planner` biết bản sao**

`docker-compose.cluster.yml`, trong `environment: &app_env` của `api`, thêm dưới dòng `DATABASE_URL`:

```yaml
      CATALOG_REPLICA_URL: postgresql://travility:travility@pg-catalog-replica:5432/travility
```

- [ ] **Step 6: Chạy test**

Run: `cd server && uv run pytest -q`
Expected: 358 passed

- [ ] **Step 7: Commit**

```bash
git add server/app/db.py server/app/auth.py server/tests/test_auth.py server/tests/test_db.py docker-compose.cluster.yml
git commit -m "feat(server): pg-catalog chính chết → đăng nhập đọc bản sao, đăng ký 503, cụm vẫn khởi động (#52)"
```

---

### Task 4: Trang "Hệ thống" ở client

**Files:**
- Modify: `client/src/api.ts` (cuối file), `client/src/components/Rail.tsx`, `client/src/App.tsx`
- Create: `client/src/components/SystemPage.tsx`
- Test: `client/src/api.test.ts`

**Interfaces:**
- Consumes: JSON của `GET /system/status` (Task 2); hàm `request<T>` có sẵn trong `api.ts`.
- Produces: `type NodeState`, `type SystemNode`, `type SystemStatus`, `getSystemStatus(token)`, `tiers(nodes)`; component `SystemPage({ token, onClose })`; `Rail` nhận thêm `systemOpen: boolean` và `onSystem: () => void`.

- [ ] **Step 1: Viết test hỏng**

Thêm `tiers` và `type SystemNode` vào dòng import của `client/src/api.test.ts`, rồi thêm cuối file:

```ts
describe('tiers', () => {
  const node = (name: string, role: string): SystemNode => ({ name, role, state: 'up' })
  it('xếp node theo tầng từ cổng vào xuống dữ liệu, bỏ tầng trống', () => {
    const got = tiers([node('pg-shard-1', 'pg-shard'), node('api a', 'api'), node('pg-catalog', 'pg-catalog'),
      node('planner-agent x', 'planner-agent'), node('planner p', 'planner'), node('pg-shard-0', 'pg-shard')])
    expect(got.map((t) => [t.label, t.nodes.map((n) => n.name)])).toEqual([
      ['API', ['api a']],
      ['Lập lịch', ['planner p', 'planner-agent x']],
      ['Dữ liệu', ['pg-catalog', 'pg-shard-1', 'pg-shard-0']],
    ])
  })
  it('role lạ không làm mất node', () => {
    expect(tiers([node('la', 'moi')])).toEqual([{ label: 'Khác', nodes: [node('la', 'moi')] }])
  })
})
```

- [ ] **Step 2: Chạy để thấy hỏng**

Run: `cd client && npm test`
Expected: FAIL — `tiers` không được export từ `./api`

- [ ] **Step 3: Thêm kiểu và hàm vào cuối `client/src/api.ts`**

```ts
export type NodeState = 'up' | 'down' | 'unknown'
export type SystemNode = { name: string; role: string; state: NodeState; lag_ms?: number | null }
export type SystemStatus = {
  nodes: SystemNode[]; served_by: string; my_shard: number | null; planner_mode: string
  stats: {
    cache_hit: number; cache_miss: number; provider_call: number; provider_wait: number
    provider_fallback: number; rate_limited: number; waiting: number; running: number
  } | null  // null: chế độ một tiến trình, hoặc Redis chết
}

export const getSystemStatus = (token: string) => request<SystemStatus>(token, '/system/status')

// Tầng của sơ đồ cụm, từ cổng vào xuống dữ liệu (spec scale §4). Role khớp server/app/system.py.
const TIERS: [string, string[]][] = [
  ['Cổng vào', ['nginx']],
  ['API', ['api']],
  ['Lập lịch', ['planner', 'planner-agent']],
  ['Dịch vụ', ['redis', 'llm-gateway', 'places']],
  ['Dữ liệu', ['pg-catalog', 'pg-catalog-replica', 'pg-shard']],
]

export function tiers(nodes: SystemNode[]): { label: string; nodes: SystemNode[] }[] {
  const known = TIERS.flatMap(([, roles]) => roles)
  return [...TIERS, ['Khác', [...new Set(nodes.map((n) => n.role).filter((r) => !known.includes(r)))]] as [string, string[]]]
    .map(([label, roles]) => ({ label, nodes: roles.flatMap((r) => nodes.filter((n) => n.role === r)) }))
    .filter((t) => t.nodes.length > 0)
}
```

- [ ] **Step 4: Chạy test**

Run: `cd client && npm test`
Expected: 35 passed

- [ ] **Step 5: Viết `client/src/components/SystemPage.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { getSystemStatus, tiers, type NodeState, type SystemNode, type SystemStatus } from '../api'

const BOX: Record<NodeState, string> = {
  up: 'border-emerald-500 bg-emerald-50',
  down: 'border-red-500 bg-red-50',
  unknown: 'border-stone-300 bg-stone-100 text-stone-500',
}
const DOT: Record<NodeState, string> = { up: 'bg-emerald-500', down: 'bg-red-500', unknown: 'bg-stone-400' }
const STATE: Record<NodeState, string> = { up: 'đang chạy', down: 'đã chết', unknown: 'không rõ' }
const REFRESH_MS = 2000

function note(n: SystemNode, s: SystemStatus): string | null {
  if (n.name === s.served_by) return 'vừa phục vụ bạn'
  if (s.my_shard != null && n.name === `pg-shard-${s.my_shard}`) return 'shard của bạn'
  if (n.lag_ms != null) return `trễ ${n.lag_ms} ms`
  return null
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-white px-4 py-3 shadow-sm">
      <dt className="text-xs font-semibold uppercase tracking-wider text-stone-500">{label}</dt>
      <dd className="mt-1 text-sm font-semibold">{value}</dd>
    </div>
  )
}

/** Sơ đồ cụm theo tầng (spec scale §12, S32). Tự làm mới; node chết đổi đỏ, không rõ thì xám. */
export default function SystemPage({ token, onClose }: { token: string; onClose: () => void }) {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [lost, setLost] = useState(false)

  useEffect(() => {
    let live = true
    let timer = 0
    // Hẹn lần kế tiếp sau khi có phản hồi: một node treo làm server trả chậm thì request không chồng lên nhau.
    const tick = async () => {
      try {
        const s = await getSystemStatus(token)
        if (live) { setStatus(s); setLost(false) }
      } catch {
        if (live) setLost(true)
      }
      if (live) timer = window.setTimeout(tick, REFRESH_MS)
    }
    tick()
    return () => { live = false; clearTimeout(timer) }
  }, [token])

  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    addEventListener('keydown', esc)
    return () => removeEventListener('keydown', esc)
  }, [onClose])

  const st = status?.stats
  return (
    <div role="dialog" aria-label="Hệ thống" className="absolute inset-y-0 left-16 right-0 z-30 overflow-y-auto bg-mist p-6">
      <header className="mb-6 flex items-center gap-3">
        <h2 className="text-xl font-bold">Hệ thống</h2>
        {lost && (
          <span role="status" className="rounded-full bg-red-100 px-3 py-1 text-sm text-red-800">
            Mất kết nối tới máy chủ, đang thử lại…
          </span>
        )}
        <div className="flex-1" />
        <button type="button" onClick={onClose} aria-label="Đóng trang Hệ thống" title="Đóng"
          className="grid size-9 place-items-center rounded-lg border border-stone-200 bg-white text-stone-600">✕</button>
      </header>
      {!status ? (!lost && <p className="text-stone-500">Đang tải…</p>) : (
        <>
          <div className="space-y-5">
            {tiers(status.nodes).map((t) => (
              <section key={t.label} aria-label={t.label}>
                <h3 className="mb-2 text-center text-xs font-semibold uppercase tracking-wider text-stone-500">{t.label}</h3>
                <ul className="flex flex-wrap justify-center gap-3">
                  {t.nodes.map((n) => {
                    const extra = note(n, status)
                    return (
                      <li key={n.name} className={`min-w-44 rounded-xl border-2 px-4 py-2.5 ${BOX[n.state]} ${
                        n.name === status.served_by ? 'ring-2 ring-marigold ring-offset-2 ring-offset-mist' : ''}`}>
                        <div className="flex items-center gap-2 font-semibold">
                          <span aria-hidden className={`size-2.5 shrink-0 rounded-full ${DOT[n.state]}`} />
                          <span className="truncate">{n.name}</span>
                        </div>
                        <p className="text-xs">{STATE[n.state]}{extra ? ` · ${extra}` : ''}</p>
                      </li>
                    )
                  })}
                </ul>
              </section>
            ))}
          </div>
          <dl className="mx-auto mt-8 grid max-w-4xl grid-cols-2 gap-3 lg:grid-cols-5">
            <Stat label="Lập lịch" value={status.planner_mode === 'multi' ? 'đa agent' : 'agent đơn'} />
            {st ? (
              <>
                <Stat label="Queue" value={`${st.waiting} chờ · ${st.running} đang chạy`} />
                <Stat label="Cache LLM" value={`${st.cache_hit} trúng · ${st.cache_miss} trượt`} />
                <Stat label="Provider" value={`${st.provider_call} lượt · ${st.provider_wait} chờ · ${st.provider_fallback} chuyển`} />
                <Stat label="Rate limit" value={`${st.rate_limited} lượt bị chặn`} />
              </>
            ) : <Stat label="Queue và cache" value="không có số liệu (Redis không chạy)" />}
          </dl>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 6: Thêm nút vào `client/src/components/Rail.tsx`**

Thêm hai prop vào chữ ký:

```tsx
export default function Rail({ busy, trips, currentId, systemOpen, onNewTrip, onOpenTrip, onSystem, onLogout }: {
  busy: boolean; trips: TripSummary[]; currentId: number | null; systemOpen: boolean
  onNewTrip?: () => void; onOpenTrip: (id: number) => void; onSystem: () => void; onLogout: () => void
}) {
```

Thêm nút ngay trên nút Đăng xuất (sau `<div className="flex-1" />`):

```tsx
        <button type="button" className={`${BTN} ${systemOpen ? 'bg-white/15 text-white' : ''}`} aria-label="Hệ thống"
          title="Hệ thống" aria-pressed={systemOpen} onClick={onSystem}>🖥</button>
```

- [ ] **Step 7: Nối vào `client/src/App.tsx`**

Import: `import SystemPage from './components/SystemPage'`.

State, cạnh các `useState` khác:

```tsx
  const [system, setSystem] = useState(false)  // trang "Hệ thống" đang mở
```

Trong `logout`, thêm `setSystem(false)`:

```tsx
  const logout = () => { saveToken(null); setToken(null); newTrip(); setTrips([]); setSystem(false) }
```

Sửa thẻ `<Rail …>` và thêm trang ngay trước `</div>` đóng cuối cùng:

```tsx
      <Rail busy={busy} trips={trips} currentId={tripId} onNewTrip={tripId != null ? newTrip : undefined}
        onOpenTrip={(id) => openTrip(id)} onLogout={logout}
        systemOpen={system} onSystem={() => setSystem((s) => !s)} />
```

```tsx
      {system && <SystemPage token={token} onClose={() => setSystem(false)} />}
```

- [ ] **Step 8: Build và lint**

Run: `cd client && npm test && npm run build && npm run lint`
Expected: 35 passed; build không lỗi TypeScript; lint không lỗi mới

- [ ] **Step 9: Nhìn tận mắt ở chế độ đơn giản**

Run: `docker compose up -d db && cd server && uv run uvicorn app.main:app --port 8000` và `cd client && npm run dev`, mở `http://127.0.0.1:5173`, đăng nhập, bấm 🖥.
Expected: lớp phủ hiện hai tầng "API" (một node, viền vàng, "vừa phục vụ bạn") và "Dữ liệu" (`pg-catalog` xanh); ô "Queue và cache" ghi "không có số liệu". `docker compose stop db` → trong vài giây `pg-catalog` đổi đỏ "đã chết". Esc đóng trang. `docker compose start db` trước khi làm tiếp.

- [ ] **Step 10: Commit**

```bash
git add client/src/api.ts client/src/api.test.ts client/src/components/SystemPage.tsx client/src/components/Rail.tsx client/src/App.tsx
git commit -m "feat(client): trang Hệ thống — sơ đồ cụm theo tầng, tự làm mới 2 giây (#52)"
```

---

### Task 5: Client nối lại luồng lập lịch bằng `job_id`

**Files:**
- Modify: `client/src/api.ts:102-130` (`streamSSE`)
- Test: `client/src/api.test.ts`

**Interfaces:**
- Consumes: header `X-Job-Id` của `POST /trips`, `/trips/{id}/plan`, `/trips/{id}/replan` (chỉ có khi server có `REDIS_URL`); `GET /jobs/{job_id}/events` phát lại **từ đầu** cùng định dạng SSE.
- Produces: `streamTrip`, `streamPlan`, `streamReplan` giữ nguyên chữ ký. Hành vi mới: luồng đóng hoặc đứt khi chưa có event kết thúc và có `X-Job-Id` → nối lại tối đa 2 lần, mỗi lần cách 1 giây, không phát lại event đã phát.

- [ ] **Step 1: Viết test hỏng**

Đổi dòng import đầu `client/src/api.test.ts` thành `import { afterEach, describe, expect, it, vi } from 'vitest'`, thêm `streamTrip` vào danh sách import từ `./api`, rồi thêm cuối file:

```ts
describe('streamSSE nối lại bằng job_id', () => {
  const A = { type: 'thinking', text: 'Đang đọc yêu cầu…' }
  const B = { type: 'tool_call', name: 'search_places', query: 'cafe', places: [] }
  const END = { type: 'answer', text: 'xong' }

  /** Phản hồi SSE giả: phát `events` rồi đóng (cut = đứt mạng: lần đọc sau ném lỗi). */
  function sse(events: object[], opts: { jobId?: string; cut?: boolean } = {}) {
    const chunk = new TextEncoder().encode(events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join(''))
    let sent = false
    const body = new ReadableStream<Uint8Array>({
      pull(c) {
        if (!sent) { sent = true; c.enqueue(chunk); return }
        if (opts.cut) c.error(new Error('đứt mạng')); else c.close()
      },
    })
    return new Response(body, { headers: opts.jobId ? { 'X-Job-Id': opts.jobId } : {} })
  }

  async function run(responses: (Response | Error)[]) {
    vi.useFakeTimers()
    const fetchMock = vi.fn(async () => {
      const r = responses.shift()!
      if (r instanceof Error) throw r
      return r
    })
    vi.stubGlobal('fetch', fetchMock)
    const got: AgentEvent[] = []
    const done = streamTrip('tok', 'Đà Lạt 1 ngày', null, (e) => got.push(e))
    await vi.runAllTimersAsync()
    await done
    return { got, urls: fetchMock.mock.calls.map((c) => String(c[0])) }
  }

  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

  it('luồng đứt giữa chừng → đọc tiếp từ /jobs/{id}/events, không phát trùng event đã nhận', async () => {
    const { got, urls } = await run([sse([A, B], { jobId: 'j1', cut: true }), sse([A, B, END])])
    expect(got).toEqual([A, B, END])
    expect(urls[1]).toMatch(/\/jobs\/j1\/events$/)
  })

  it('luồng đóng sớm không báo lỗi cũng được nối lại; lần nối hỏng thì thử lần nữa', async () => {
    const { got, urls } = await run([sse([A], { jobId: 'j1' }), new TypeError('fetch failed'), sse([A, END])])
    expect(got).toEqual([A, END])
    expect(urls).toHaveLength(3)
  })

  it('hết 2 lần nối lại vẫn chưa xong → một bong bóng lỗi', async () => {
    const { got, urls } = await run([sse([A], { jobId: 'j1' }), sse([A]), sse([A])])
    expect(got).toEqual([A, { type: 'error', message: 'Kết nối bị ngắt giữa chừng, bạn thử lại nhé.' }])
    expect(urls).toHaveLength(3)
  })

  it('không có X-Job-Id (chế độ một tiến trình) → báo lỗi như cũ, không gọi thêm', async () => {
    const { got, urls } = await run([sse([A])])
    expect(got).toEqual([A, { type: 'error', message: 'Kết nối bị ngắt giữa chừng, bạn thử lại nhé.' }])
    expect(urls).toHaveLength(1)
  })
})
```

- [ ] **Step 2: Chạy để thấy hỏng**

Run: `cd client && npm test`
Expected: 3 test mới FAIL (test đầu ném "đứt mạng"; hai test nối lại chỉ thấy 1 lần fetch); test "không có X-Job-Id" PASS

- [ ] **Step 3: Thay `streamSSE` trong `client/src/api.ts`**

```ts
const RECONNECTS = 2  // spec scale S34
const RECONNECT_MS = 1000  // đủ để nginx bỏ bản api vừa chết

/** Đọc một phản hồi SSE tới khi đóng hoặc đứt; bỏ qua `skip` event đầu (đã phát ở lần nối trước). */
async function readEvents(r: Response, skip: number, onEvent: (e: AgentEvent) => void) {
  const reader = r.body!.pipeThrough(new TextDecoderStream()).getReader()
  let buf = ''
  let count = 0
  let finished = false
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buf += value
      const { events, rest } = parseSSE(buf)
      buf = rest
      for (const e of events) {
        count += 1
        if (count <= skip) continue
        const ev = e as AgentEvent
        if (isFinal(ev)) finished = true
        onEvent(ev)
      }
    }
  } catch { /* mạng đứt giữa chừng: xử lý như luồng đóng sớm */ }
  return { count, finished }
}

async function streamSSE(token: string, path: string, body: unknown, onEvent: (e: AgentEvent) => void) {
  const r = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  })
  if (r.status === 401) throw new Error('unauthorized')
  if (!r.ok || !r.body) {
    const detail = (await r.json().catch(() => ({}))).detail
    onEvent({ type: 'error', message: typeof detail === 'string' ? detail : `Lỗi máy chủ (${r.status})` })
    return
  }
  // Có X-Job-Id = việc chạy trong planner và sống tiếp khi bản api này chết: nối lại ở bản api khác (spec §10).
  const jobId = r.headers.get('X-Job-Id')
  let { count: seen, finished } = await readEvents(r, 0, onEvent)
  for (let i = 0; !finished && jobId && i < RECONNECTS; i++) {
    await new Promise((ok) => setTimeout(ok, RECONNECT_MS))
    const again = await fetch(`${API}/jobs/${jobId}/events`, { headers: { Authorization: `Bearer ${token}` } })
      .catch(() => null)
    if (!again?.ok || !again.body) continue
    const got = await readEvents(again, seen, onEvent)
    seen = Math.max(seen, got.count)
    finished = got.finished
  }
  if (!finished) onEvent({ type: 'error', message: 'Kết nối bị ngắt giữa chừng, bạn thử lại nhé.' })
}
```

Thay đổi nhỏ so với trước: mạng đứt giữa lúc đọc ở chế độ một tiến trình giờ ra bong bóng "Kết nối bị ngắt giữa chừng…" thay cho "Mất kết nối tới máy chủ…" (trước đây lỗi đọc ném lên `run()` trong `App.tsx`).

- [ ] **Step 4: Chạy test và build**

Run: `cd client && npm test && npm run build`
Expected: 39 passed; build sạch

- [ ] **Step 5: Commit**

```bash
git add client/src/api.ts client/src/api.test.ts
git commit -m "feat(client): luồng lập lịch đứt giữa chừng thì nối lại bằng job_id, tối đa 2 lần (#52)"
```

---

### Task 6: Script load test

**Files:**
- Create: `server/scripts/loadtest.py`
- Test: `server/tests/test_loadtest.py`

**Interfaces:**
- Consumes: HTTP của cụm qua nginx: `POST /auth/register`, `POST /auth/login`, `GET /trips`, `GET /trips/{id}`, `POST /trips` (SSE).
- Produces: lệnh `uv run python -m scripts.loadtest --label <tên> [--base URL] [--users N] [--rounds N] [--plans N] [--sequential] [--message "…"]` in bảng Markdown; hàm thuần `percentile(xs, p)`, `summarize(samples, errors, wall)`, `row(label, scenario, s)`.

- [ ] **Step 1: Viết test hỏng**

`server/tests/test_loadtest.py`:

```python
from scripts.loadtest import percentile, row, summarize


def test_percentile_is_nearest_rank():
    xs = [0.4, 0.1, 0.3, 0.2]
    assert percentile(xs, 0.5) == 0.2
    assert percentile(xs, 0.95) == 0.4
    assert percentile([0.7], 0.95) == 0.7
    assert percentile([], 0.5) == 0.0


def test_summary_counts_errors_and_rate_of_successes():
    s = summarize([0.1, 0.2, 0.3, 0.4], errors=1, wall=2.0)
    assert s == {"n": 5, "errors": 1, "p50_ms": 200, "p95_ms": 400, "rps": 2.0}
    assert summarize([], errors=3, wall=0.0) == {"n": 3, "errors": 3, "p50_ms": 0, "p95_ms": 0, "rps": 0.0}


def test_row_is_a_markdown_table_line():
    s = summarize([0.1], errors=0, wall=1.0)
    assert row("2 api", "mở Trip", s) == "| 2 api | mở Trip | 1 | 0 | 100 | 100 | 1.0 |"
```

- [ ] **Step 2: Chạy để thấy hỏng**

Run: `cd server && uv run pytest tests/test_loadtest.py -q`
Expected: FAIL `ModuleNotFoundError: No module named 'scripts.loadtest'`

- [ ] **Step 3: Viết `server/scripts/loadtest.py`**

```python
"""Load test cụm Travility (spec scale §12, S33): in bảng Markdown p50 / p95 / lượt mỗi giây.

Chạy từ máy ngoài, trỏ vào nginx; bật cụm với PLAN_RPM=0 để không bị giới hạn theo User.

  uv run python -m scripts.loadtest --label "2 api" --users 20 --rounds 10
  uv run python -m scripts.loadtest --label "cache bật (replay)" --users 20 --plans 20 --rounds 0
  uv run python -m scripts.loadtest --label "cache tắt" --users 2 --plans 2 --sequential --rounds 0

Đăng nhập không được đo: nginx giới hạn /auth/ ở 1 request mỗi giây theo IP, nên bước tạo User chạy trước và chậm.
Cần ít nhất một lượt --plans trước đó để User có Trip cho kịch bản "mở Trip".
"""
import argparse
import asyncio
import json
import math
import time

import httpx

PASSWORD = "travility-load"
MESSAGE = "Đà Lạt 1 ngày 1 triệu cho 2 người, đi Grab"  # đủ Travel Mode, không có ngày đi → không bị hỏi lại
HEADER = ("| Cấu hình | Kịch bản | Lượt | Lỗi | p50 (ms) | p95 (ms) | Lượt/giây |\n"
          "|---|---|---|---|---|---|---|")


def percentile(xs: list[float], p: float) -> float:
    """Phân vị theo hạng gần nhất; danh sách rỗng → 0."""
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[max(0, math.ceil(p * len(s)) - 1)]


def summarize(samples: list[float], errors: int, wall: float) -> dict:
    """samples: giây của từng lượt thành công; wall: giây từ lúc bắt đầu tới lúc xong cả đợt."""
    return {"n": len(samples) + errors, "errors": errors, "p50_ms": round(percentile(samples, 0.5) * 1000),
            "p95_ms": round(percentile(samples, 0.95) * 1000), "rps": round(len(samples) / wall, 1) if wall else 0.0}


def row(label: str, scenario: str, s: dict) -> str:
    return f"| {label} | {scenario} | {s['n']} | {s['errors']} | {s['p50_ms']} | {s['p95_ms']} | {s['rps']} |"


async def token_for(http: httpx.AsyncClient, i: int) -> str:
    """Đăng ký User loadtest{i} (đã có hoặc đang chỉ đọc thì đăng nhập); nginx trả 429 thì chờ rồi thử lại."""
    body = {"email": f"loadtest{i}@travility.vn", "password": PASSWORD}
    for path in ("/auth/register", "/auth/login"):
        while (r := await http.post(path, json=body)).status_code == 429:
            await asyncio.sleep(1.1)
        if r.status_code in (200, 201):
            return r.json()["token"]
    raise SystemExit(f"Không tạo được User loadtest{i}: {r.status_code} {r.text[:200]}")


async def get_ok(http: httpx.AsyncClient, path: str, h: dict) -> bool:
    return (await http.get(path, headers=h)).status_code == 200


async def plan(http: httpx.AsyncClient, h: dict, message: str) -> bool:
    """Một lượt lập lịch: đọc SSE tới hết; thành công khi event cuối là itinerary."""
    last = None
    async with http.stream("POST", "/trips", json={"message": message, "trip_id": None}, headers=h) as r:
        if r.status_code != 200:
            return False
        async for line in r.aiter_lines():
            if line.startswith("data: "):
                last = json.loads(line[6:])["type"]
    return last == "itinerary"


async def _time(call) -> float | None:
    t0 = time.perf_counter()
    try:
        ok = await call
    except httpx.HTTPError:
        return None
    return time.perf_counter() - t0 if ok else None


async def measure(calls: list, sequential: bool = False) -> dict:
    t0 = time.perf_counter()
    got = [await _time(c) for c in calls] if sequential else await asyncio.gather(*map(_time, calls))
    done = [g for g in got if g is not None]
    return summarize(done, len(got) - len(done), time.perf_counter() - t0)


async def run(args) -> None:
    async with httpx.AsyncClient(base_url=args.base, timeout=180, limits=httpx.Limits(max_connections=None)) as http:
        heads = [{"Authorization": f"Bearer {await token_for(http, i)}"} for i in range(1, args.users + 1)]
        print(HEADER)
        if args.plans:
            calls = [plan(http, heads[i % len(heads)], args.message) for i in range(args.plans)]
            print(row(args.label, "lập lịch", await measure(calls, args.sequential)), flush=True)
        if args.rounds:
            calls = [get_ok(http, "/trips", h) for h in heads for _ in range(args.rounds)]
            print(row(args.label, "danh sách Trip", await measure(calls)), flush=True)
            mine = [(h, (await http.get("/trips", headers=h)).json()) for h in heads]
            calls = [get_ok(http, f"/trips/{ts[0]['id']}", h) for h, ts in mine if ts for _ in range(args.rounds)]
            if calls:
                print(row(args.label, "mở Trip", await measure(calls)), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Load test cụm Travility")
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--label", required=True, help="tên cấu hình đang đo, in ở cột đầu")
    ap.add_argument("--users", type=int, default=20)
    ap.add_argument("--rounds", type=int, default=10, help="số lượt đọc mỗi User cho mỗi kịch bản đọc; 0 = bỏ")
    ap.add_argument("--plans", type=int, default=0, help="số lượt lập lịch; 0 = bỏ")
    ap.add_argument("--sequential", action="store_true", help="lập lịch lần lượt (đo cache tắt với provider thật)")
    ap.add_argument("--message", default=MESSAGE)
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Chạy test**

Run: `cd server && uv run pytest tests/test_loadtest.py -q && uv run pytest -q`
Expected: 3 passed; cả bộ 361 passed

- [ ] **Step 5: Commit**

```bash
git add server/scripts/loadtest.py server/tests/test_loadtest.py
git commit -m "feat(server): scripts.loadtest — bảng p50 / p95 / lượt mỗi giây cho đọc Trip và lập lịch (#52)"
```

---

### Task 7: Smoke test cụm, runbook T6, đo thật

**Files:**
- Create: `scripts/smoke_cluster.sh`
- Modify: `docs/runbook-cum.md` (thêm mục T6 trước "Lập lịch đa agent (T4)"; sửa dòng "Chưa có ở T5")

**Interfaces:**
- Consumes: mọi thứ ở Task 1–6, chạy trên cụm thật (`server/.env` có key LLM thật).
- Produces: `./scripts/smoke_cluster.sh` thoát 0 khi cụm khoẻ; runbook có lệnh cho từng dòng bảng trình diễn spec §12 và bảng số đo.

- [ ] **Step 1: Viết `scripts/smoke_cluster.sh`**

```sh
#!/bin/sh
# Smoke test cụm (spec scale §13): dựng cụm, một lượt lập lịch, kiểm GET /system/status.
# Chạy từ gốc repo: ./scripts/smoke_cluster.sh
# Cần server/.env có key LLM thật, hoặc cache đã ghi câu bên dưới và GATEWAY_CACHE=replay.
set -eu
dc() { docker compose -f docker-compose.cluster.yml "$@"; }
BASE=http://localhost:8000

dc up -d --build
printf 'chờ api'
i=0
until curl -fsS "$BASE/health" >/dev/null 2>&1; do
  i=$((i + 1))
  [ "$i" -gt 60 ] && { echo ' quá 120 giây'; exit 1; }
  printf .
  sleep 2
done
echo

if [ "$(dc exec -T pg-catalog psql -U travility -tAc 'SELECT count(*) FROM places')" -eq 0 ]; then
  (cd server && uv run python -m scripts.import_places ../data/places)
fi
dc exec -T api uv run --no-dev python -m scripts.seed_users >/dev/null
dc exec -T redis redis-cli del nodes >/dev/null   # bỏ nhịp tim của container đời trước (node ma)
sleep 5                                           # mọi bản đang sống báo lại nhịp tim

TOKEN=$(curl -fsS "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"demo1@travility.vn","password":"travility-demo"}' |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["token"])')

curl -fsS "$BASE/system/status" -H "Authorization: Bearer $TOKEN" | python3 -c '
import json, sys
nodes = json.load(sys.stdin)["nodes"]
want = {"nginx": 1, "api": 2, "planner": 2, "planner-agent": 3, "redis": 1, "llm-gateway": 1, "places": 1,
        "pg-catalog": 1, "pg-catalog-replica": 1, "pg-shard": 2}
roles = [n["role"] for n in nodes]
bad = [n["name"] for n in nodes if n["state"] != "up"]
short = {r: roles.count(r) for r, n in want.items() if roles.count(r) < n}
if bad or short:
    sys.exit(f"node không sống: {bad}; thiếu bản: {short}")
print(f"{len(nodes)} node đều sống")'

LAST=$(curl -fsSN "$BASE/trips" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"Đà Lạt 1 ngày 1 triệu cho 2 người, đi Grab","trip_id":null}' | grep '^data: ' | tail -1)
case "$LAST" in
  *'"type": "itinerary"'*) echo 'lập lịch: ra Itinerary' ;;
  *) echo "lập lịch không ra Itinerary: $LAST"; exit 1 ;;
esac
echo 'smoke test cụm: ĐẠT'
```

Run: `chmod +x scripts/smoke_cluster.sh`

- [ ] **Step 2: Chạy smoke test trên cụm thật**

Run: `docker compose down && ./scripts/smoke_cluster.sh`
Expected: `15 node đều sống`, `lập lịch: ra Itinerary`, `smoke test cụm: ĐẠT`, mã thoát 0. Hỏng thì sửa nguyên nhân (không nới điều kiện kiểm) rồi chạy lại.

- [ ] **Step 3: Chạy từng dòng bảng trình diễn §12, ghi lại điều quan sát được**

Mở app (`cd client && npm run dev`), đăng nhập `demo1@travility.vn` / `travility-demo`, mở trang 🖥. Với mỗi dòng dưới: chạy lệnh, xác nhận hành vi, rồi bật lại node. Dòng nào không đúng hành vi mong đợi là bug: dừng, dùng `superpowers:systematic-debugging`, sửa kèm test, rồi chạy lại dòng đó.

| Kỹ thuật | Lệnh | Mong đợi |
|---|---|---|
| Phát hiện node | `dc stop places` rồi `dc start places` | `places` đỏ trong ≤ 6 giây, xanh lại sau khi bật |
| Load balancing | Để trang mở 10 giây | Viền vàng "vừa phục vụ bạn" đổi qua lại giữa hai bản `api` |
| Caching | Lập cùng một câu hai lần trên hai Trip mới | Lần hai nhanh rõ rệt; ô "Cache LLM" tăng số trúng |
| Rate limit | Gửi 6 tin nhắn lập lịch trong một phút | Lần 6 bong bóng đỏ 429; ô "Rate limit" tăng 1 |
| Message queue | Gửi câu chưa từng gửi; `dc exec redis redis-cli xpending jobs planners - + 10`; `docker kill <id>` | Một `planner` đỏ; Chat hiện "Đang thử lại…" rồi ra lịch |
| Nối lại (S34) | Gửi câu chưa từng gửi; `docker kill` một bản `api` | Một `api` đỏ; Chat không báo lỗi, vẫn ra lịch |
| Microservice | `dc stop places` | Lập lịch báo "Dịch vụ địa điểm tạm không truy cập được"; mở Trip cũ vẫn được |
| Replication | `dc stop pg-catalog-replica` | Node đỏ; lập lịch và tìm Place vẫn chạy; bật lại hiện "trễ 0 ms" |
| Sharding | `dc stop pg-shard-1`; đăng nhập `demo1` và `demo2` | Chỉ User ở shard 1 nhận 503; nhãn "shard của bạn" đúng từng người |
| CAP | `dc stop pg-catalog`; đăng ký email mới; đăng nhập `demo1`; lập lịch; `dc restart api` | Đăng ký 503 "chế độ chỉ đọc"; đăng nhập và lập lịch chạy; `api` lên lại được |
| Node treo | `docker pause travility-cluster-places-1` rồi `docker unpause …` | Trang vẫn làm mới (chậm hơn), `places` đỏ; không treo trang |
| Đa agent | `PLANNER_MODE=multi dc up -d`, `dc exec redis redis-cli del nodes`, lập lịch | Ô "Lập lịch" ghi "đa agent"; Chat có nhãn ba agent |

- [ ] **Step 4: Đo load test (4 lần chạy), giữ nguyên số in ra**

```bash
# A. 2 bản api, đọc Trip
PLAN_RPM=0 dc up -d
cd server && uv run python -m scripts.loadtest --label "khởi tạo" --users 20 --plans 20 --rounds 0   # tạo Trip cho 20 User; không ghi vào bảng
uv run python -m scripts.loadtest --label "2 bản api" --users 20 --rounds 10

# B. 1 bản api, đọc Trip
PLAN_RPM=0 dc up -d --scale api=1 && dc restart nginx
uv run python -m scripts.loadtest --label "1 bản api" --users 20 --rounds 10

# C. cache tắt: 2 lượt lập lịch tuần tự, provider thật (S33)
PLAN_RPM=0 GATEWAY_CACHE=off dc up -d && dc restart nginx
uv run python -m scripts.loadtest --label "cache tắt" --users 2 --plans 2 --sequential --rounds 0

# D. cache bật: ghi một lần rồi phát lại 20 lượt đồng thời
TODAY=$(date +%F)
PLAN_RPM=0 DEMO_TODAY=$TODAY GATEWAY_CACHE=on GATEWAY_CHAT_TTL=0 dc up -d
uv run python -m scripts.loadtest --label "ghi" --users 1 --plans 1 --rounds 0
PLAN_RPM=0 DEMO_TODAY=$TODAY GATEWAY_CACHE=replay dc up -d
uv run python -m scripts.loadtest --label "cache bật (replay)" --users 20 --plans 20 --rounds 0
```

Lần "khởi tạo" ở A gọi provider thật 20 lượt lập lịch đồng thời và sẽ vượt hạn mức Gemini free. Nếu cột Lỗi khác 0: chạy bước D trước (ghi + `replay`), dùng luôn lượt `replay` 20 lượt đó làm bước khởi tạo, rồi mới chạy A và B.

Expected: mỗi lệnh in một bảng Markdown, cột Lỗi bằng 0 ở các dòng đưa vào runbook.

- [ ] **Step 5: Viết mục T6 vào `docs/runbook-cum.md`**

Chèn mục mới `## Trang "Hệ thống", chế độ chỉ đọc, load test (T6)` ngay trước `## Lập lịch đa agent (T4)`, gồm đúng các phần sau, dùng số và quan sát thật từ Step 3–4:

1. **Trang "Hệ thống"**: nút 🖥 trên rail; ý nghĩa ba màu; node một bản được dò, tiến trình nhiều bản theo nhịp tim (chết sau 6 giây im lặng); lệnh xem thẳng: `curl -s localhost:8000/system/status -H "Authorization: Bearer <token>" | python3 -m json.tool`.
2. **Node ma**: sau `dc up -d` tạo lại container, bản cũ hiện đỏ tối đa 10 phút; xoá ngay bằng `dc exec redis redis-cli del nodes`.
3. **Bảng trình diễn**: bảng ở Step 3 với cột "Mong đợi" thay bằng điều đã quan sát được (kèm số giây đo được ở các dòng có chờ).
4. **Tắt `pg-catalog`**: `dc stop pg-catalog` → đăng ký 503 "Hệ thống đang ở chế độ chỉ đọc…"; đăng nhập đọc bản sao; lập lịch và sửa lịch chạy; `dc restart api` lên lại (log có dòng "pg-catalog không kết nối được lúc khởi động"); `import_places` và `seed_users` không chạy được cho tới khi `dc start pg-catalog`.
5. **Nối lại khi một bản `api` chết**: client nối lại tối đa 2 lần qua `GET /jobs/{id}/events`; `dc up -d` bật lại bản `api`, rồi `dc restart nginx` nếu nginx trả 502.
6. **Load test**: các lệnh ở Step 4; một bảng gộp các dòng "2 bản api", "1 bản api", "cache tắt", "cache bật (replay)" với số đo thật; ngày đo, máy đo; ghi rõ "cache tắt" là 2 lượt tuần tự còn "cache bật" là 20 lượt đồng thời (S33) và vì sao; ghi rõ đăng nhập không được đo vì nginx giới hạn `/auth/`; nếu 2 bản `api` không nhanh hơn 1 bản thì ghi đúng như vậy kèm lý do (cùng một laptop, cùng chia CPU).
7. **Smoke test**: `./scripts/smoke_cluster.sh`.

Trong mục T5, thay dòng `- Chưa có ở T5 (để T6): …` bằng:

```markdown
- `pg-catalog` chính chết: xem mục T6 "Tắt `pg-catalog`" (đăng nhập đọc bản sao, đăng ký 503, `api` vẫn khởi động lại được).
```

- [ ] **Step 6: Trả cụm về mặc định và commit**

```bash
docker compose -f docker-compose.cluster.yml up -d && docker compose -f docker-compose.cluster.yml restart nginx
git add scripts/smoke_cluster.sh docs/runbook-cum.md
git commit -m "docs: runbook T6 — bảng trình diễn, số đo load test, smoke_cluster.sh (#52)"
```

Bug tìm thấy ở Step 3 được commit riêng, mỗi bug một commit kèm test.

---

### Task 8: Khép lát

**Files:**
- Modify: `docs/ROADMAP.md`, `docs/2026-09-25-hien-trang-app.md`

- [ ] **Step 1: ROADMAP**

- Mục 11: đổi dòng T6 thành `- [x] **T6** — #52 — …` viết lại bằng một câu mô tả thứ đã có (trang "Hệ thống" + `GET /system/status`, nhịp tim node, chế độ chỉ đọc, client nối lại, `scripts.loadtest`, `smoke_cluster.sh`) kèm link runbook và câu "**Kiến trúc đóng băng từ <ngày merge>**".
- Bảng Tổng quan: nhóm 11 → `5 | 6`. Mục 10: số test → số thật sau Task 6 (server 361 + số test thêm khi sửa bug, client 39).
- Bảng lộ trình tuần, dòng T5–T6: thêm ✅ sau `(#52)`.
- "Việc cần làm ngay" mục 1: T6 xong; tiếp theo là mô hình mưa #53 (plan viết khi bắt đầu).

- [ ] **Step 2: Hiện trạng app**

Đọc `docs/2026-09-25-hien-trang-app.md`, thêm vào đúng các mục đang liệt kê endpoint, component client và script: `GET /system/status`, `SystemPage`, nút 🖥 trên rail, `streamSSE` nối lại, `scripts.loadtest`, `scripts/smoke_cluster.sh`, chế độ chỉ đọc. Giữ giọng và độ dài như các mục lân cận.

- [ ] **Step 3: Kiểm trước khi giao**

Run: `/gc-ship` (lint + typecheck + test server và client), rồi `/code-review` trên diff `main..feat/52-he-thong`. Sửa mọi phát hiện đúng; phát hiện không đồng ý thì ghi lý do.
Expected: server và client xanh; không còn phát hiện mức correctness chưa xử lý.

- [ ] **Step 4: Commit**

```bash
git add docs/ROADMAP.md docs/2026-09-25-hien-trang-app.md
git commit -m "docs: ROADMAP và hiện trạng sau scale T6; kiến trúc đóng băng (#52)"
```

Mở PR và đóng #52 khi Thành bảo.

---

## Kiểm chứng cuối (khớp tiêu chí nghiệm thu #52)

1. Tắt một container → trang "Hệ thống" đổi màu node đó trong vài giây: Task 7 Step 3, dòng "Phát hiện node".
2. Bảng load test 1 vs 2 bản `api`, cache tắt vs bật: Task 7 Step 4–5.
3. Tắt `pg-catalog` → không đăng ký được (503 có thông báo), vẫn đăng nhập và lập lịch được: Task 3 (test) + Task 7 Step 3, dòng "CAP".
4. Runbook chạy được toàn bộ bảng trình diễn §12 trừ mô hình mưa: Task 7 Step 3 và 5.
