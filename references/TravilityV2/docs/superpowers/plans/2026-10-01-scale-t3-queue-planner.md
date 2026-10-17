# Scale T3 — Queue Redis Streams + `planner` + `nginx` + rate limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `api` đẩy việc lập lịch / lập lại / followup vào Redis Streams và chuyển event về client qua SSE; worker `planner` chạy đúng các generator hiện có, việc của worker chết được worker khác nhận lại mà không sinh bản ghi trùng; `nginx` chia tải cho 2 bản `api`; mỗi User tối đa `PLAN_RPM` việc mỗi phút (#49).

**Architecture:** Một image, thêm một lệnh khởi động: `python -m app.worker` (`planner`). `app/jobs.py` là phần Redis phía `api` (rate limit, đẩy việc, chuyển event). `app/worker.py` đọc stream `jobs` bằng consumer group `planners`, chạy `trips.JOBS[kind]` trong một transaction và ghi event vào `events:{job_id}`. Thiếu `REDIS_URL` thì `trips._stream` chạy cùng các hàm việc đó ngay trong request như hôm nay.

**Tech Stack:** FastAPI, `redis` (redis-py 8, đồng bộ), psycopg3, Redis 7 Streams, nginx, docker compose, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-scale-he-phan-tan-design.md` — đọc §4, §5, §10, §13, §14. Năm bổ sung chốt khi grill T3 (Task 7 ghi vào spec):

| # | Bổ sung | Lý do |
|---|---|---|
| T3-1 | Worker bọc mỗi việc trong **một transaction**; lỗi thường bị bắt bên trong nên vẫn commit; event cuối chỉ phát **sau khi commit** | Generator ghi `INSERT trips`, `log_message`, `pending_replan` trước khi có Itinerary. Autocommit + chạy lại = Trip và tin nhắn trùng |
| T3-2 | Nhịp tim 5 giây (`XCLAIM … JUSTID`); việc im lặng quá **20 giây** mới bị nhận lại (thay "60 giây" của §5.2) | Lập lịch có thể dài hơn 60 giây → worker đang sống bị giành việc |
| T3-3 | Ba endpoint đẩy việc chung một bộ đếm, `PLAN_RPM=5` | `api` không biết trước tin nhắn nào dẫn tới lập lịch |
| T3-4 | T3 chỉ làm phía server cho việc nối lại; client tự nối lại dời sang T6 | Giữ tiêu chí "client không sửa" |
| T3-5 | Công tắc queue = `REDIS_URL`; 120 giây không có event mới → event `error` | Quên chạy `planner` thì thấy lỗi rõ, không treo |

## Global Constraints

- **Không sửa client.** Hợp đồng HTTP + SSE giữ nguyên; chỉ thêm header `X-Job-Id` và endpoint `GET /jobs/{job_id}/events`.
- Thiếu `REDIS_URL` → app chạy như hiện nay. 243 test hiện có phải xanh, **không sửa assert**.
- **Không sửa logic** của `agent.py`, `followup.py`, `rules.py`, `replan.py`, `llm.py`. Trong `trips.py` chỉ đổi cách gọi (`_stream`, ba handler), không đổi `_run`, `_follow_up`, `_replan`, `_plan_and_save`.
- Không thêm dependency. Không dùng thư viện giả lập Redis; test dùng Redis thật qua fixture `rds` (`redis://localhost:6379/15`).
- Redis lỗi: rate limit cho qua; đẩy việc → 503 (spec §10).
- Thông báo lỗi hướng tới người dùng là tiếng Việt.
- Tên khoá Redis: `jobs` (stream), `planners` (group), `events:{job_id}`, `job:{job_id}:user`, `job:{job_id}:done`, `rl:{user_id}:{phút}`, `rl:blocked`.
- Lệnh test: `docker compose up -d db redis && cd server && uv run pytest` · `cd client && npm test && npm run build`.
- Commit message kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Việc chạy lâu hơn 20 giây.** Worker đang sống không được bị giành việc: nhịp tim giữ idle thấp và không tăng số lần giao (Task 5 có test).
2. **Worker chết sau khi đã ghi Trip.** Chạy lại phải cho đúng một Trip, một tin nhắn User (Task 5 có test).
3. **Không có `planner` nào chạy.** Request không treo vô hạn: 120 giây im lặng → event `error` (Task 3 có test).
4. **Redis chết.** Rate limit cho qua; đẩy việc trả 503 ngay; đang chuyển event thì đóng stream bằng event `error` (Task 2, 3, 6 có test).
5. **User khác đoán `job_id`.** `GET /jobs/{id}/events` trả 404, kể cả khi việc đã hết hạn (Task 6 có test).

## File Structure

| File | Trách nhiệm |
|---|---|
| `server/app/trips.py` | Thêm `guarded`, ba hàm việc, `JOBS`; `_stream(kind, user_id, **params)` chọn chạy tại chỗ hay qua queue; `GET /jobs/{job_id}/events` |
| `server/app/jobs.py` (mới) | Phía `api`: `check_rate`, `enqueue`, `owner`, `publish`, `finish`, `relay` |
| `server/app/worker.py` (mới) | `planner`: `ensure_group`, `step`, `run_job`, `_beat`, `main` |
| `server/app/config.py` | Thêm `plan_rpm` |
| `server/app/db.py` | `apply_schema` giữ advisory lock |
| `server/app/main.py` | CORS `expose_headers=["X-Job-Id"]` |
| `docker/nginx.conf` (mới) | Chia tải, SSE, `limit_req` cho `/auth/` |
| `docker/initdb/01-test-db.sql` | Tạo sẵn extension `vector` |
| `docker-compose.cluster.yml` | Thêm `nginx`, `planner`; `api` 2 bản |

---

### Task 1: Tách việc khỏi handler (`guarded`, `JOBS`)

Refactor thuần: việc không còn là closure giữ biến của handler mà là `kind` + tham số JSON được, để Task 4 chạy được ở tiến trình khác.

**Files:**
- Modify: `server/app/trips.py` (`_stream`, `create_trip`, `plan_trip`, `replan_trip`)
- Test: `server/tests/test_trips_api.py`

**Interfaces:**
- Produces:
  - `trips.guarded(events: Iterable[str]) -> Iterator[str]` — bọc generator chuỗi SSE; `openai.OpenAIError` / `Exception` → một event `error`.
  - `trips.JOBS: dict[str, Callable]` với ba khoá `"message"`, `"plan"`, `"replan"`. Chữ ký: `JOBS["message"](conn, user_id, message: str, trip_id: int | None)`, `JOBS["plan"](conn, user_id, trip_id: int)`, `JOBS["replan"](conn, user_id, trip_id: int, changes: dict, message: str)`. Mỗi hàm trả generator chuỗi SSE (`"data: {...}\n\n"`).
  - `trips._stream(kind: str, user_id: int, **params) -> StreamingResponse`.

- [ ] **Step 1: Viết test đỏ** — thêm vào cuối `server/tests/test_trips_api.py`:

```python
def test_job_message_runs_from_plain_params(client, conn, monkeypatch):
    pid = add_place(conn, kind="cafe")
    use_llm(monkeypatch, happy(pid))
    auth(client)
    uid = conn.execute("SELECT id FROM users").fetchone()["id"]
    out = trips.guarded(trips.JOBS["message"](conn, uid, message="Đà Lạt 1 ngày 2 triệu", trip_id=None))
    assert [json.loads(s[6:])["type"] for s in out] == ["thinking", "trip", "tool_call", "itinerary"]


def test_job_message_on_missing_trip_is_error_event(client, conn):
    auth(client)
    uid = conn.execute("SELECT id FROM users").fetchone()["id"]
    out = list(trips.JOBS["message"](conn, uid, message="x", trip_id=999))
    assert json.loads(out[0][6:]) == {"type": "error", "message": "Không tìm thấy chuyến đi"}


def test_guarded_turns_exception_into_error_event():
    def boom():
        yield "a"
        raise RuntimeError("x")

    out = list(trips.guarded(boom()))
    assert out[0] == "a"
    assert json.loads(out[1][6:]) == {"type": "error", "message": "Có lỗi khi lập lịch trình, bạn thử lại nhé."}
```

- [ ] **Step 2: Chạy, thấy đỏ**

Run: `cd server && uv run pytest tests/test_trips_api.py -k "job_message or guarded" -q`
Expected: 3 FAIL, `AttributeError: module 'app.trips' has no attribute 'guarded'` / `'JOBS'`.

- [ ] **Step 3: Sửa `server/app/trips.py`**

Thay `_stream` (dòng 48–61) bằng:

```python
def guarded(events):
    """Chạy generator chuỗi SSE của một việc; lỗi → event error tiếng Việt. Dùng chung cho request và worker."""
    try:
        yield from events
    except openai.OpenAIError:
        logger.exception("Lỗi gọi AI khi lập lịch trình")
        yield sse({"type": "error", "message": "Không kết nối được AI, kiểm tra mạng rồi thử lại nhé."})
    except Exception:
        logger.exception("Lỗi không lường trước khi lập lịch trình")
        yield sse({"type": "error", "message": "Có lỗi khi lập lịch trình, bạn thử lại nhé."})


def _stream(kind: str, user_id: int, **params) -> StreamingResponse:
    """Chạy việc JOBS[kind] trong SSE. params phải JSON được: Task 6 gửi chúng qua queue."""
    def events():
        with stream_conn() as conn:
            yield from guarded(JOBS[kind](conn, user_id, **params))

    return StreamingResponse(events(), media_type="text/event-stream")
```

Thay `create_trip` bằng:

```python
@router.post("/trips")
def create_trip(body: NewTrip, user_id: int = Depends(current_user), conn=Depends(get_conn)):
    if body.trip_id is not None and not conn.execute(
            "SELECT 1 FROM trips WHERE id = %s AND user_id = %s", (body.trip_id, user_id)).fetchone():
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    return _stream("message", user_id, message=body.message, trip_id=body.trip_id)
```

Trong `plan_trip`, thay phần từ `def run(c):` tới `return _stream(run)` bằng:

```python
    return _stream("plan", user_id, trip_id=trip_id)
```

Trong `replan_trip`, thay dòng `return _stream(lambda c: _replan(...))` bằng:

```python
    return _stream("replan", user_id, trip_id=trip_id, changes=body.changes, message=body.message)
```

Thêm ngay sau hàm `_run` (trước `@router.post("/trips/{trip_id}/plan")`):

```python
def _trip_row(conn, user_id: int, trip_id: int) -> dict | None:
    return conn.execute("SELECT id, spec, user_messages, pending_replan FROM trips WHERE id = %s AND user_id = %s",
                        (trip_id, user_id)).fetchone()


def _job_message(conn, user_id: int, message: str, trip_id: int | None = None):
    prev = _trip_row(conn, user_id, trip_id) if trip_id is not None else None
    if trip_id is not None and not prev:
        yield sse({"type": "error", "message": "Không tìm thấy chuyến đi"})
        return
    yield from _run(conn, user_id, message, prev)


def _job_plan(conn, user_id: int, trip_id: int):
    row = _trip_row(conn, user_id, trip_id)
    trip = Trip.model_validate(row["spec"])
    dest = next(d for d in list_destinations(conn) if d["slug"] == trip.destination)
    yield _trip_event(trip_id, trip, dest)
    yield from _plan_and_save(conn, llm.chat_client(), trip_id, trip, dest, row["user_messages"])


def _job_replan(conn, user_id: int, trip_id: int, changes: dict, message: str):
    row = _trip_row(conn, user_id, trip_id)
    yield from _replan(conn, llm.chat_client(), trip_id, Trip.model_validate(row["spec"]), row["user_messages"],
                       changes, message)


# Việc lập lịch theo tên: chạy trong request (chế độ một tiến trình) hoặc trong worker planner (spec scale §5).
JOBS = {"message": _job_message, "plan": _job_plan, "replan": _job_replan}
```

Trong `plan_trip` và `replan_trip`, các biến `trip` / `row` sau khi sửa vẫn được dùng cho bước kiểm 409/422 và `UPDATE trips SET spec`; giữ nguyên các dòng đó.

- [ ] **Step 4: Chạy, thấy xanh**

Run: `cd server && uv run pytest -q`
Expected: 246 passed (243 cũ + 3 mới).

- [ ] **Step 5: Commit**

```bash
git add server/app/trips.py server/tests/test_trips_api.py
git commit -m "refactor(server): việc lập lịch thành hàm theo tên với tham số thuần, sẵn sàng chạy ở worker (#49)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Rate limit theo User

**Files:**
- Create: `server/app/jobs.py`
- Modify: `server/app/config.py`
- Test: `server/tests/test_jobs.py` (mới)

**Interfaces:**
- Consumes: `kv.client() -> redis.Redis | None`, fixture `rds`.
- Produces: `jobs.check_rate(user_id: int) -> None` (ném `HTTPException(429)` có header `Retry-After`); `jobs._now` (test thay đồng hồ); `settings.plan_rpm: int = 5`.

- [ ] **Step 1: Viết test đỏ** — tạo `server/tests/test_jobs.py`:

```python
import json
import threading

import pytest
from fastapi import HTTPException

from app import jobs, kv
from app.config import settings


@pytest.fixture
def minute(monkeypatch):
    """Đồng hồ đứng ở giây thứ 10 của một phút; test tự tua bằng minute[0] += …"""
    t = [60_000_010.0]
    monkeypatch.setattr(jobs, "_now", lambda: t[0])
    return t


@pytest.fixture
def redis_down(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")
    monkeypatch.setattr(kv, "_client", None)


def test_sixth_request_in_a_minute_is_429(rds, minute):
    for _ in range(5):
        jobs.check_rate(7)
    with pytest.raises(HTTPException) as e:
        jobs.check_rate(7)
    assert e.value.status_code == 429
    assert e.value.headers["Retry-After"] == "50" and "50 giây" in e.value.detail
    assert rds.get("rl:blocked") == "1"


def test_other_user_and_next_minute_are_not_limited(rds, minute):
    for _ in range(5):
        jobs.check_rate(7)
    jobs.check_rate(8)
    minute[0] += 60
    jobs.check_rate(7)


def test_counter_expires(rds, minute):
    jobs.check_rate(7)
    assert 0 < rds.ttl("rl:7:1000000") <= 120


def test_plan_rpm_zero_means_no_limit(rds, minute, monkeypatch):
    monkeypatch.setattr(settings, "plan_rpm", 0)
    for _ in range(20):
        jobs.check_rate(7)
    assert rds.keys("rl:*") == []


def test_rate_limit_lets_through_when_redis_down(redis_down):
    for _ in range(10):
        jobs.check_rate(7)


def test_no_redis_url_means_no_limit():
    for _ in range(10):
        jobs.check_rate(7)
```

- [ ] **Step 2: Chạy, thấy đỏ**

Run: `cd server && uv run pytest tests/test_jobs.py -q`
Expected: lỗi collect `ImportError: cannot import name 'jobs' from 'app'`.

- [ ] **Step 3: Viết code**

`server/app/config.py` — thêm ngay sau dòng `redis_url: str = ""`:

```python
    plan_rpm: int = 5  # việc lập lịch mỗi phút cho một User (cần REDIS_URL); 0 = không giới hạn
```

Tạo `server/app/jobs.py`:

```python
"""Queue lập lịch trên Redis Streams, phía api: giới hạn theo User, đẩy việc, chuyển event về client (spec scale §5).

Phía worker ở app/worker.py.
"""
import math
import time

from fastapi import HTTPException
from redis.exceptions import RedisError

from app import kv
from app.config import settings

_now = time.time  # test thay bằng đồng hồ giả


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
```

- [ ] **Step 4: Chạy, thấy xanh**

Run: `cd server && uv run pytest tests/test_jobs.py -q`
Expected: 6 passed. (`test_no_redis_url_means_no_limit` và `test_rate_limit_lets_through_when_redis_down` xanh ngay từ lần đầu có module: chúng là rào chống hồi quy, giữ lại.)

- [ ] **Step 5: Commit**

```bash
git add server/app/jobs.py server/app/config.py server/tests/test_jobs.py
git commit -m "feat(server): giới hạn số việc lập lịch mỗi phút theo User (#49)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Đẩy việc và chuyển event (`enqueue`, `publish`, `finish`, `relay`)

**Files:**
- Modify: `server/app/jobs.py`
- Test: `server/tests/test_jobs.py`

**Interfaces:**
- Produces:
  - `jobs.STREAM = "jobs"`, `jobs.GROUP = "planners"`, `jobs.TTL_S = 3600`, `jobs.QUIET_S = 120`.
  - `jobs.enqueue(kind: str, user_id: int, params: dict) -> str` — trả `job_id` (uuid hex); mục trong stream có các trường chuỗi `job_id`, `kind`, `user_id`, `params` (JSON). Redis lỗi → `HTTPException(503)`.
  - `jobs.owner(job_id: str) -> int | None`.
  - `jobs.publish(job_id: str, data: str) -> None` — `data` là chuỗi SSE hoàn chỉnh. Ném `RedisError` nếu Redis lỗi (worker tự xử lý).
  - `jobs.finish(job_id: str) -> None` — ghi mục đánh dấu `end`.
  - `jobs.relay(job_id: str) -> Iterator[str]` — phát lại từ đầu `events:{job_id}`, dừng ở `end`.

- [ ] **Step 1: Viết test đỏ** — thêm vào cuối `server/tests/test_jobs.py`:

```python
def test_enqueue_writes_job_and_owner(rds):
    job_id = jobs.enqueue("message", 7, {"message": "Đà Lạt", "trip_id": None})
    [(_, fields)] = rds.xrange("jobs")
    assert fields == {"job_id": job_id, "kind": "message", "user_id": "7",
                      "params": '{"message": "Đà Lạt", "trip_id": null}'}
    assert jobs.owner(job_id) == 7
    assert 0 < rds.ttl(f"job:{job_id}:user") <= 3600


def test_owner_of_unknown_job_is_none(rds):
    assert jobs.owner("khong-co") is None


def test_enqueue_is_503_when_redis_down(redis_down):
    with pytest.raises(HTTPException) as e:
        jobs.enqueue("message", 7, {})
    assert e.value.status_code == 503 and "tạm không dùng được" in e.value.detail


def test_relay_yields_in_order_and_stops_at_end(rds):
    jobs.publish("j1", "data: 1\n\n")
    jobs.publish("j1", "data: 2\n\n")
    jobs.finish("j1")
    jobs.publish("j1", "data: 3\n\n")
    assert list(jobs.relay("j1")) == ["data: 1\n\n", "data: 2\n\n"]
    assert 0 < rds.ttl("events:j1") <= 3600


def test_relay_waits_for_late_events(rds):
    def later():
        jobs.publish("j2", "data: x\n\n")
        jobs.finish("j2")

    threading.Timer(0.2, later).start()
    assert list(jobs.relay("j2")) == ["data: x\n\n"]


def test_relay_gives_error_after_long_silence(rds, monkeypatch):
    t = [0.0]

    def now():
        t[0] += 61
        return t[0]

    monkeypatch.setattr(jobs, "_now", now)
    out = list(jobs.relay("j3"))
    assert len(out) == 1
    assert json.loads(out[0][6:]) == {"type": "error",
                                      "message": "Hệ thống lập lịch đang bận hoặc chưa chạy, bạn thử lại sau nhé."}


def test_relay_gives_error_when_redis_dies(redis_down):
    out = list(jobs.relay("j4"))
    assert len(out) == 1 and "Mất kết nối" in json.loads(out[0][6:])["message"]
```

- [ ] **Step 2: Chạy, thấy đỏ**

Run: `cd server && uv run pytest tests/test_jobs.py -q`
Expected: 7 FAIL với `AttributeError: module 'app.jobs' has no attribute 'enqueue'` (hoặc `publish`, `relay`); 6 test của Task 2 vẫn pass.

- [ ] **Step 3: Viết code** — trong `server/app/jobs.py`:

Thêm `import json` và `import uuid` vào khối import. Thêm ngay dưới `_now = time.time`:

```python
STREAM, GROUP = "jobs", "planners"
TTL_S = 3600  # events:{job_id} và các khoá job:{job_id}:* sống bấy nhiêu giây
QUIET_S = 120  # chờ event mới tối đa bấy nhiêu giây rồi báo lỗi (không có planner nào chạy)
```

Thêm vào cuối file:

```python
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


def relay(job_id: str):
    """Phát lại events:{job_id} từ đầu dưới dạng SSE, tới khi gặp mục end. Bản api nào cũng đọc được."""
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
```

`block=500` vì `kv.client()` đặt `socket_timeout=1`.

- [ ] **Step 4: Chạy, thấy xanh**

Run: `cd server && uv run pytest tests/test_jobs.py -q`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add server/app/jobs.py server/tests/test_jobs.py
git commit -m "feat(server): đẩy việc lập lịch vào Redis Streams và chuyển event về SSE (#49)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Worker chạy việc trong một transaction

**Files:**
- Create: `server/app/worker.py`
- Test: `server/tests/test_worker.py` (mới)

**Interfaces:**
- Consumes: `trips.JOBS`, `trips.guarded`, `trips.sse`; `jobs.STREAM`, `jobs.GROUP`, `jobs.TTL_S`, `jobs.enqueue`, `jobs.publish`, `jobs.finish`.
- Produces:
  - `worker.ensure_group(c: redis.Redis) -> None`.
  - `worker.step(conn, c, me: str) -> bool` — nhận và chạy tối đa một việc; `True` nếu có việc.
  - `worker.run_job(conn, c, me: str, msg_id: str, f: dict, retry: bool = False) -> None`.

- [ ] **Step 1: Viết test đỏ** — tạo `server/tests/test_worker.py`:

```python
import json
import threading
import time

import pytest

from app import forecast, jobs, llm, rules, trips, worker
from app.db import connect
from tests.conftest import TEST_URL
from tests.fakes import FakeClient, reply
from tests.helpers import add_place, unit_vec

RECORD = reply(("record_trip", {"destination": "da-lat", "days": 1, "budget": 2_000_000, "travel_mode": "grab"}))


@pytest.fixture(autouse=True)
def env(conn, rds, monkeypatch):
    monkeypatch.setattr(rules, "MEALS", ())
    monkeypatch.setattr(llm, "embed", lambda texts: [unit_vec(0) for _ in texts])
    monkeypatch.setattr(forecast, "get_rain_chance", lambda *a, **k: None)
    worker.ensure_group(rds)


def use_llm(monkeypatch, responses):
    monkeypatch.setattr(llm, "chat_client", lambda: FakeClient(responses))


def happy(pid):
    return [RECORD, reply(("search_places", {"query": "cafe"})),
            reply(("submit_itinerary", {"summary": "ok", "days": [{"stops": [
                {"place_id": pid, "start_time": "09:00", "duration_min": 60, "reason": "cafe-chill"}]}]}))]


def submit(conn):
    uid = conn.execute("INSERT INTO users(email, password_hash) VALUES ('an@example.com', 'x') RETURNING id"
                       ).fetchone()["id"]
    return jobs.enqueue("message", uid, {"message": "Đà Lạt 1 ngày 2 triệu", "trip_id": None})


def published(rds, job_id):
    return ["end" if "end" in f else json.loads(f["data"][6:]) for _, f in rds.xrange(f"events:{job_id}")]


def types(rds, job_id):
    return [e if e == "end" else e["type"] for e in published(rds, job_id)]


def count(conn, table):
    return conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]


def pending(rds):
    return rds.xpending_range("jobs", "planners", "-", "+", 10)


def test_job_runs_and_publishes_events_then_end(conn, rds, monkeypatch):
    use_llm(monkeypatch, happy(add_place(conn, kind="cafe")))
    job_id = submit(conn)
    assert worker.step(conn, rds, "w1") is True
    assert types(rds, job_id) == ["thinking", "trip", "tool_call", "itinerary", "end"]
    assert rds.get(f"job:{job_id}:done") == "1" and pending(rds) == []
    assert count(conn, "itineraries") == 1


def test_step_without_work_returns_false(conn, rds):
    assert worker.step(conn, rds, "w1") is False


def test_last_event_is_published_only_after_commit(conn, rds, monkeypatch):
    use_llm(monkeypatch, happy(add_place(conn, kind="cafe")))
    other, seen, real = connect(TEST_URL), [], jobs.publish

    def spy(job_id, data):
        seen.append((json.loads(data[6:])["type"], count(other, "trips")))
        real(job_id, data)

    monkeypatch.setattr(jobs, "publish", spy)
    submit(conn)
    worker.step(conn, rds, "w1")
    other.close()
    assert seen == [("thinking", 0), ("trip", 0), ("tool_call", 0), ("itinerary", 1)]


def test_error_event_still_commits_the_unfinished_trip(conn, rds, monkeypatch):
    add_place(conn)
    use_llm(monkeypatch, [RECORD, RuntimeError("boom")])
    job_id = submit(conn)
    worker.step(conn, rds, "w1")
    assert types(rds, job_id) == ["thinking", "trip", "error", "end"]
    assert count(conn, "trips") == 1 and pending(rds) == []  # Trip dở vẫn còn để User gửi tiếp, như chế độ một tiến trình


def test_done_job_is_not_run_again(conn, rds, monkeypatch):
    use_llm(monkeypatch, [])  # gọi LLM là hỏng
    job_id = submit(conn)
    rds.set(f"job:{job_id}:done", 1)
    worker.step(conn, rds, "w1")
    assert count(conn, "trips") == 0 and pending(rds) == [] and types(rds, job_id) == ["end"]
```

- [ ] **Step 2: Chạy, thấy đỏ**

Run: `cd server && uv run pytest tests/test_worker.py -q`
Expected: lỗi collect `ImportError: cannot import name 'worker' from 'app'`.

- [ ] **Step 3: Viết code** — tạo `server/app/worker.py`:

```python
"""planner: nhận việc lập lịch từ Redis Streams và chạy đúng các generator của app.trips (spec scale §5).

Chạy: python -m app.worker
"""
import json
import logging

from redis.exceptions import ResponseError

from app import jobs, trips

logger = logging.getLogger(__name__)


def ensure_group(c) -> None:
    try:
        c.xgroup_create(jobs.STREAM, jobs.GROUP, id="0", mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


def run_job(conn, c, me: str, msg_id: str, f: dict, retry: bool = False) -> None:
    """Chạy một việc trong một transaction: worker chết giữa chừng → Postgres rollback, lần chạy lại bắt đầu sạch.

    Event cuối chỉ phát sau khi commit, để client không bao giờ thấy Itinerary chưa được lưu.
    """
    job_id = f["job_id"]
    if c.exists(f"job:{job_id}:done"):  # đã xong ở lần giao trước
        jobs.finish(job_id)
        c.xack(jobs.STREAM, jobs.GROUP, msg_id)
        return
    held = None
    with conn.transaction():
        for ev in trips.guarded(trips.JOBS[f["kind"]](conn, int(f["user_id"]), **json.loads(f["params"]))):
            if held is not None:
                jobs.publish(job_id, held)
            held = ev
    c.set(f"job:{job_id}:done", 1, ex=jobs.TTL_S)
    if held is not None:
        jobs.publish(job_id, held)
    jobs.finish(job_id)
    c.xack(jobs.STREAM, jobs.GROUP, msg_id)
    logger.info("xong việc %s (%s)", job_id, f["kind"])


def step(conn, c, me: str) -> bool:
    """Nhận và chạy tối đa một việc; True nếu có việc.

    ponytail: một việc một lúc mỗi tiến trình; cần chạy song song nhiều hơn thì tăng số bản planner.
    """
    got = c.xreadgroup(jobs.GROUP, me, {jobs.STREAM: ">"}, count=1, block=500)
    if not got:
        return False
    msg_id, f = got[0][1][0]
    run_job(conn, c, me, msg_id, f)
    return True
```

- [ ] **Step 4: Chạy, thấy xanh**

Run: `cd server && uv run pytest tests/test_worker.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add server/app/worker.py server/tests/test_worker.py
git commit -m "feat(server): worker planner chạy việc trong một transaction, event cuối phát sau commit (#49)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Nhận lại việc của worker chết, nhịp tim, giới hạn chạy lại, `main`

**Files:**
- Modify: `server/app/worker.py`
- Test: `server/tests/test_worker.py`

**Interfaces:**
- Consumes: `worker.run_job`, `worker.step` của Task 4.
- Produces: `worker.CLAIM_IDLE_MS = 20_000`, `worker.BEAT_S = 5`, `worker.MAX_DELIVERIES = 2`, `worker._beat(c, msg_id, me, stop: threading.Event)`, `worker.main()`.

- [ ] **Step 1: Viết test đỏ** — thêm vào cuối `server/tests/test_worker.py`:

```python
class Crash(BaseException):
    """Worker bị giết giữa chừng: guarded chỉ bắt Exception nên lỗi này xuyên qua như tiến trình chết."""


def crash_midway(conn, rds, monkeypatch):
    """w1 nhận việc, ghi Trip rồi chết trước khi có Itinerary. Trả (job_id, hàm plan thật)."""
    real = trips.plan

    def dying_plan(*a, **k):
        raise Crash()
        yield

    use_llm(monkeypatch, [RECORD])
    monkeypatch.setattr(trips, "plan", dying_plan)
    job_id = submit(conn)
    with pytest.raises(Crash):
        worker.step(conn, rds, "w1")
    return job_id, real


def make_idle(rds, ms=30_000):
    """Giả lập việc đã im lặng ms mili giây (không tăng số lần giao)."""
    [p] = pending(rds)
    rds.xclaim("jobs", "planners", p["consumer"], 0, [p["message_id"]], idle=ms, justid=True)


def test_abandoned_job_is_rerun_without_duplicates(conn, rds, monkeypatch):
    pid = add_place(conn, kind="cafe")
    job_id, real_plan = crash_midway(conn, rds, monkeypatch)
    assert count(conn, "trips") == 0  # transaction của lần chạy dở đã rollback
    make_idle(rds)
    monkeypatch.setattr(trips, "plan", real_plan)
    use_llm(monkeypatch, happy(pid))
    assert worker.step(conn, rds, "w2") is True
    evs = published(rds, job_id)
    assert types(rds, job_id) == ["thinking", "thinking", "thinking", "trip", "tool_call", "itinerary", "end"]
    assert evs[1]["text"] == "Đang thử lại…"
    assert count(conn, "trips") == 1 and count(conn, "messages WHERE role = 'user'") == 1
    assert pending(rds) == []


def test_fresh_pending_job_is_not_stolen(conn, rds, monkeypatch):
    crash_midway(conn, rds, monkeypatch)  # vừa giao cho w1, chưa im lặng đủ 20 giây
    assert worker.step(conn, rds, "w2") is False
    assert pending(rds)[0]["consumer"] == "w1"


def test_third_delivery_gives_error_instead_of_running(conn, rds, monkeypatch):
    job_id, _ = crash_midway(conn, rds, monkeypatch)
    make_idle(rds)
    with pytest.raises(Crash):
        worker.step(conn, rds, "w2")  # lần chạy lại cũng chết
    make_idle(rds)
    worker.step(conn, rds, "w3")
    assert published(rds, job_id)[-2:] == [
        {"type": "error", "message": "Có lỗi khi lập lịch trình, bạn thử lại nhé."}, "end"]
    assert pending(rds) == [] and count(conn, "trips") == 0


def test_heartbeat_keeps_job_fresh_without_counting_as_delivery(conn, rds, monkeypatch):
    crash_midway(conn, rds, monkeypatch)
    make_idle(rds)
    monkeypatch.setattr(worker, "BEAT_S", 0.01)
    stop = threading.Event()
    t = threading.Thread(target=worker._beat, args=(rds, pending(rds)[0]["message_id"], "w1", stop))
    t.start()
    time.sleep(0.1)
    stop.set()
    t.join()
    [p] = pending(rds)
    assert p["time_since_delivered"] < 5000 and p["times_delivered"] == 1


def test_job_runs_under_heartbeat_and_stops_it(conn, rds, monkeypatch):
    beats = []
    monkeypatch.setattr(worker, "_beat", lambda c, msg_id, me, stop: beats.append((me, stop)))
    use_llm(monkeypatch, happy(add_place(conn, kind="cafe")))
    submit(conn)
    worker.step(conn, rds, "w1")
    time.sleep(0.05)
    assert len(beats) == 1 and beats[0][0] == "w1" and beats[0][1].is_set()


def test_heartbeat_stops_when_job_crashes(conn, rds, monkeypatch):
    beats = []
    monkeypatch.setattr(worker, "_beat", lambda c, msg_id, me, stop: beats.append(stop))
    crash_midway(conn, rds, monkeypatch)
    time.sleep(0.05)
    assert beats[0].is_set()
```

- [ ] **Step 2: Chạy, thấy đỏ**

Run: `cd server && uv run pytest tests/test_worker.py -q`
Expected: 6 FAIL trong các test mới (`worker.step(…, "w2")` trả `False` thay vì nhận lại việc; `AttributeError: … has no attribute '_beat'` / `'BEAT_S'`). `test_fresh_pending_job_is_not_stolen` có thể xanh sẵn (rào chống hồi quy, giữ lại). 5 test của Task 4 vẫn pass.

- [ ] **Step 3: Viết code** — trong `server/app/worker.py`:

Khối import thành:

```python
import json
import logging
import socket
import threading
import time

from redis.exceptions import RedisError, ResponseError

from app import jobs, kv, trips
from app.db import apply_schema, connect
```

Thêm dưới `logger = …`:

```python
CLAIM_IDLE_MS = 20_000  # việc im lặng quá bấy nhiêu = worker giữ nó đã chết → worker khác nhận lại
BEAT_S = 5  # worker đang chạy việc báo "còn sống" mỗi bấy nhiêu giây
MAX_DELIVERIES = 2  # chạy lại tối đa 1 lần (spec §5.2)


def _beat(c, msg_id: str, me: str, stop: threading.Event) -> None:
    """Nhịp tim: XCLAIM JUSTID đặt lại thời gian im lặng của việc mà không tăng số lần giao."""
    while not stop.wait(BEAT_S):
        try:
            c.xclaim(jobs.STREAM, jobs.GROUP, me, 0, [msg_id], justid=True)
        except RedisError:
            pass
```

Thay toàn bộ `run_job` bằng:

```python
def run_job(conn, c, me: str, msg_id: str, f: dict, retry: bool = False) -> None:
    """Chạy một việc trong một transaction: worker chết giữa chừng → Postgres rollback, lần chạy lại bắt đầu sạch.

    Event cuối chỉ phát sau khi commit, để client không bao giờ thấy Itinerary chưa được lưu.
    """
    job_id = f["job_id"]

    def close():
        jobs.finish(job_id)
        c.xack(jobs.STREAM, jobs.GROUP, msg_id)

    if c.exists(f"job:{job_id}:done"):  # đã xong ở lần giao trước
        return close()
    if retry:
        delivered = c.xpending_range(jobs.STREAM, jobs.GROUP, msg_id, msg_id, 1)[0]["times_delivered"]
        if delivered > MAX_DELIVERIES:
            jobs.publish(job_id, trips.sse({"type": "error", "message": "Có lỗi khi lập lịch trình, bạn thử lại nhé."}))
            return close()
        jobs.publish(job_id, trips.sse({"type": "thinking", "text": "Đang thử lại…"}))
    stop = threading.Event()
    threading.Thread(target=_beat, args=(c, msg_id, me, stop), daemon=True).start()
    try:
        held = None
        with conn.transaction():
            for ev in trips.guarded(trips.JOBS[f["kind"]](conn, int(f["user_id"]), **json.loads(f["params"]))):
                if held is not None:
                    jobs.publish(job_id, held)
                held = ev
        c.set(f"job:{job_id}:done", 1, ex=jobs.TTL_S)
        if held is not None:
            jobs.publish(job_id, held)
        close()
        logger.info("xong việc %s (%s)", job_id, f["kind"])
    finally:
        stop.set()
```

Thay toàn bộ `step` bằng:

```python
def step(conn, c, me: str) -> bool:
    """Nhận và chạy tối đa một việc; True nếu có việc. Việc bị worker chết bỏ dở được ưu tiên trước.

    ponytail: một việc một lúc mỗi tiến trình; cần chạy song song nhiều hơn thì tăng số bản planner.
    """
    claimed = c.xautoclaim(jobs.STREAM, jobs.GROUP, me, CLAIM_IDLE_MS, count=1)[1]
    if claimed:
        run_job(conn, c, me, *claimed[0], retry=True)
        return True
    got = c.xreadgroup(jobs.GROUP, me, {jobs.STREAM: ">"}, count=1, block=500)
    if not got:
        return False
    run_job(conn, c, me, *got[0][1][0])
    return True
```

Thêm vào cuối file:

```python
def main() -> None:
    logging.basicConfig(level=logging.INFO)
    c, me = kv.client(), socket.gethostname()
    if c is None:
        raise SystemExit("planner cần REDIS_URL")
    with connect() as conn:
        apply_schema(conn)
    logger.info("planner %s sẵn sàng", me)
    conn = None
    while True:
        try:
            ensure_group(c)  # mỗi vòng: `redis-cli flushdb` trong runbook xoá luôn consumer group
            conn = conn or connect()
            step(conn, c, me)
        except Exception:
            logger.exception("planner lỗi, thử lại sau 1 giây")
            if conn is not None:
                conn.close()
            conn = None
            time.sleep(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Chạy, thấy xanh**

Run: `cd server && uv run pytest tests/test_worker.py -q && uv run pytest -q`
Expected: 11 passed; cả bộ 270 passed (243 + 3 + 13 + 11).

- [ ] **Step 5: Commit**

```bash
git add server/app/worker.py server/tests/test_worker.py
git commit -m "feat(server): planner nhận lại việc của worker chết, nhịp tim, chạy lại tối đa một lần (#49)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Nối `api` vào queue, `X-Job-Id`, `GET /jobs/{job_id}/events`

**Files:**
- Modify: `server/app/trips.py` (`_stream`, import, endpoint mới), `server/app/main.py` (CORS)
- Test: `server/tests/test_trips_api.py`

**Interfaces:**
- Consumes: `jobs.check_rate`, `jobs.enqueue`, `jobs.relay`, `jobs.owner`; `worker.ensure_group`, `worker.step`.
- Produces: có `REDIS_URL` → ba endpoint lập lịch trả SSE từ queue kèm header `X-Job-Id`; `GET /jobs/{job_id}/events`.

- [ ] **Step 1: Viết test đỏ** — trong `server/tests/test_trips_api.py`:

Thêm `import threading` và `import time` vào khối import đầu file; sửa dòng import app thành `from app import forecast, jobs, kv, llm, rules, trips, worker`.

Thêm vào cuối file:

```python
@pytest.fixture
def planner(conn, rds):
    """Chế độ queue: REDIS_URL trỏ Redis test và một planner chạy trong thread, dùng chung kết nối test."""
    worker.ensure_group(rds)
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            worker.step(conn, rds, "w1")

    t = threading.Thread(target=loop)
    t.start()
    yield
    stop.set()
    t.join()


def test_queue_mode_streams_same_events_and_replays(client, conn, monkeypatch, planner):
    pid = add_place(conn, kind="cafe")
    use_llm(monkeypatch, happy(pid))
    h = auth(client)
    r = client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers={**h, "Origin": "http://app"})
    assert [e["type"] for e in events(r)] == ["thinking", "trip", "tool_call", "itinerary"]
    assert "x-job-id" in r.headers["access-control-expose-headers"].lower()
    trip_id = events(r)[-1]["trip_id"]
    assert client.get(f"/trips/{trip_id}", headers=h).json()["version"] == 1

    job_id = r.headers["x-job-id"]
    again = client.get(f"/jobs/{job_id}/events", headers=h)
    assert again.text == r.text and again.headers["content-type"].startswith("text/event-stream")
    assert client.get(f"/jobs/{job_id}/events", headers=auth(client, "binh@example.com")).status_code == 404
    assert client.get("/jobs/khong-co/events", headers=h).status_code == 404
    assert client.get(f"/jobs/{job_id}/events").status_code == 401


def test_queue_mode_clarify_then_plan(client, conn, monkeypatch, planner):
    pid = add_place(conn, kind="cafe")
    h, evs = ask_first(conn, client, monkeypatch)
    assert evs[-1]["type"] == "clarify"
    use_llm(monkeypatch, happy(pid)[1:])
    r = client.post(f"/trips/{evs[-1]['trip_id']}/plan", json={"travel_mode": "grab"}, headers=h)
    assert events(r)[-1]["type"] == "itinerary" and r.headers["x-job-id"]


def test_queue_mode_over_limit_is_429_and_nothing_is_queued(client, conn, rds):
    h = auth(client)
    uid = conn.execute("SELECT id FROM users").fetchone()["id"]
    this_minute = int(time.time() // 60)
    for m in (this_minute, this_minute + 1):  # cả phút sau, phòng khi test chạy ngang ranh giới phút
        rds.set(f"rl:{uid}:{m}", 5)
    r = client.post("/trips", json={"message": "x"}, headers=h)
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1 and "quá nhanh" in r.json()["detail"]
    assert rds.xlen("jobs") == 0


def test_queue_mode_bad_request_does_not_use_a_slot(client, conn, rds):
    r = client.post("/trips", json={"message": "x", "trip_id": 999}, headers=auth(client))
    assert r.status_code == 404 and rds.keys("rl:*") == []


def test_queue_mode_redis_down_is_503(client, monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")
    monkeypatch.setattr(kv, "_client", None)
    r = client.post("/trips", json={"message": "x"}, headers=auth(client))
    assert r.status_code == 503 and "tạm không dùng được" in r.json()["detail"]


def test_simple_mode_has_no_job_id_and_no_job_endpoint_data(client, conn, monkeypatch):
    pid = add_place(conn, kind="cafe")
    use_llm(monkeypatch, happy(pid))
    h = auth(client)
    r = client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h)
    assert events(r)[-1]["type"] == "itinerary" and "x-job-id" not in r.headers
    assert client.get("/jobs/bat-ky/events", headers=h).status_code == 404
```

Ghi chú cho `test_queue_mode_clarify_then_plan`: `ask_first` gửi câu thiếu Travel Mode nên việc đầu kết thúc bằng `clarify`; `happy(pid)[1:]` bỏ lượt `record_trip` vì `/plan` không đọc lại yêu cầu.

- [ ] **Step 2: Chạy, thấy đỏ**

Run: `cd server && uv run pytest tests/test_trips_api.py -k "queue_mode or simple_mode" -q`
Expected: 5 FAIL (`KeyError: 'x-job-id'` / `'access-control-expose-headers'`, 404 cho `/jobs/...`, status 200 thay vì 429 và 503). `test_queue_mode_bad_request_does_not_use_a_slot` xanh sẵn (rào chống hồi quy, giữ lại).

- [ ] **Step 3: Viết code**

`server/app/trips.py` — sửa dòng import thành:

```python
from app import forecast, jobs, llm
```

Thay `_stream` bằng:

```python
def _stream(kind: str, user_id: int, **params) -> StreamingResponse:
    """Chạy việc JOBS[kind] trong SSE. Có REDIS_URL → đẩy vào queue cho planner và chuyển event về (spec scale §5);
    thiếu → chạy ngay trong request. params phải JSON được."""
    if settings.redis_url:
        jobs.check_rate(user_id)
        job_id = jobs.enqueue(kind, user_id, params)
        return StreamingResponse(jobs.relay(job_id), media_type="text/event-stream", headers={"X-Job-Id": job_id})

    def events():
        with stream_conn() as conn:
            yield from guarded(JOBS[kind](conn, user_id, **params))

    return StreamingResponse(events(), media_type="text/event-stream")
```

Thêm ngay sau `JOBS = {...}`:

```python
@router.get("/jobs/{job_id}/events")
def job_events(job_id: str, user_id: int = Depends(current_user)):
    """Phát lại tiến trình của một việc từ đầu (client mất kết nối giữa chừng). Việc sống 1 giờ."""
    if jobs.owner(job_id) != user_id:
        raise HTTPException(404, "Không tìm thấy việc")
    return StreamingResponse(jobs.relay(job_id), media_type="text/event-stream")
```

`server/app/main.py` — sửa dòng `add_middleware` thành:

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["X-Job-Id"])
```

- [ ] **Step 4: Chạy, thấy xanh**

Run: `cd server && uv run pytest -q`
Expected: 276 passed.

- [ ] **Step 5: Commit**

```bash
git add server/app/trips.py server/app/main.py server/tests/test_trips_api.py
git commit -m "feat(server): api đẩy việc lập lịch qua queue khi có REDIS_URL, phát lại tiến trình theo job_id (#49)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `nginx` + 2 bản `api` + `planner` trong cụm, tài liệu, kiểm chứng đầu-cuối

**Files:**
- Modify: `server/app/db.py`, `docker/initdb/01-test-db.sql`, `docker-compose.cluster.yml`, `server/.env.example`
- Create: `docker/nginx.conf`, `server/tests/test_db.py`
- Modify (tài liệu): `docs/superpowers/specs/2026-10-01-scale-he-phan-tan-design.md`, `docs/runbook-cum.md`, `docs/ROADMAP.md`, `docs/2026-09-25-hien-trang-app.md`

**Interfaces:**
- Consumes: `python -m app.worker` (Task 5), `GET /jobs/{job_id}/events` (Task 6).

- [ ] **Step 1: Test đỏ cho khởi động đồng thời** — tạo `server/tests/test_db.py`:

```python
import threading

from app.db import apply_schema, connect
from tests.conftest import TEST_URL


def test_apply_schema_survives_concurrent_startup(conn):
    """2 bản api + 2 planner cùng khởi động trên database trống."""
    conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    errors, gate = [], threading.Barrier(4)

    def boot():
        c = connect(TEST_URL)
        try:
            gate.wait()
            apply_schema(c)
        except Exception as e:
            errors.append(e)
        finally:
            c.close()

    threads = [threading.Thread(target=boot) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0
```

- [ ] **Step 2: Chạy, thấy đỏ**

Run: `cd server && for i in 1 2 3; do uv run pytest tests/test_db.py -q; done`
Expected: FAIL ít nhất một lần (`UniqueViolation` trên `pg_extension_name_index` / `pg_type_typname_nsp_index`, hoặc `DuplicateTable`). Nếu cả ba lần đều xanh: ghi ruling vào ledger rằng cuộc đua không tái hiện được trên máy này, vẫn làm Step 3 vì khoá là phòng ngừa.

- [ ] **Step 3: Sửa `server/app/db.py`** — thay `apply_schema`:

```python
def apply_schema(conn: psycopg.Connection) -> None:
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(4949)")  # các bản api và planner trong cụm khởi động cùng lúc
        conn.execute(SCHEMA.read_text())
    register_vector(conn)  # extension có thể vừa được tạo lại → đăng ký lại kiểu vector
```

`docker/initdb/01-test-db.sql` — thêm dòng đầu (để `connect()` của nhiều container không đua nhau tạo extension trên volume mới):

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

- [ ] **Step 4: Chạy, thấy xanh**

Run: `cd server && for i in 1 2 3; do uv run pytest tests/test_db.py -q; done && uv run pytest -q`
Expected: 3 lần `1 passed`; cả bộ 277 passed.

- [ ] **Step 5: Tạo `docker/nginx.conf`**

```nginx
# Cụm Travility (spec scale §4): chia đều cho các bản api, không buffer SSE, chặn dò mật khẩu ở /auth/.
events {}

http {
  limit_req_zone $binary_remote_addr zone=auth:1m rate=1r/s;

  upstream api {
    server api:8000;  # DNS của compose trả IP của mọi bản api → nginx xoay vòng
  }

  server {
    listen 80;
    charset utf-8;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Host $host;
    add_header X-Upstream $upstream_addr always;  # thấy được bản api nào phục vụ

    location / {
      proxy_pass http://api;
      proxy_buffering off;       # SSE: chuyển từng event ngay
      proxy_read_timeout 300s;   # api tự đóng stream sau 120 giây im lặng
    }

    location /auth/ {
      limit_req zone=auth burst=10 nodelay;
      limit_req_status 429;
      error_page 429 = @too_fast;
      proxy_pass http://api;
    }

    location @too_fast {
      default_type application/json;
      add_header Access-Control-Allow-Origin * always;
      return 429 '{"detail": "Bạn thử quá nhiều lần, chờ ít giây rồi thử lại nhé."}';
    }
  }
}
```

- [ ] **Step 6: Sửa `docker-compose.cluster.yml`**

Sửa dòng chú thích đầu thành `# Cụm phân tán (spec scale §4). T3: db + redis + llm-gateway + 2 api + 2 planner + nginx.`

Thay khối `api:` bằng ba khối sau (giữ nguyên `db`, `redis`, `llm-gateway`, `volumes`):

```yaml
  api:
    build: ./server
    env_file: ./server/.env
    environment: &app_env
      DATABASE_URL: postgresql://travility:travility@db:5432/travility
      REDIS_URL: redis://redis:6379/0
      LLM_BASE_URL: http://llm-gateway:8000/v1
      EMBED_BASE_URL: http://llm-gateway:8000/v1
      DEMO_TODAY: ${DEMO_TODAY:-}
      PLAN_RPM: ${PLAN_RPM:-5}
    deploy:
      replicas: 2
    depends_on: &app_deps
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      llm-gateway:
        condition: service_started
  planner:
    build: ./server
    command: ["uv", "run", "--no-dev", "python", "-m", "app.worker"]
    env_file: ./server/.env
    environment: *app_env
    deploy:
      replicas: 2
    depends_on: *app_deps
  nginx:
    image: nginx:1.27-alpine
    volumes:
      - ./docker/nginx.conf:/etc/nginx/nginx.conf:ro
    ports: ["127.0.0.1:8000:80"]
    depends_on: [api]
```

Run: `docker compose -f docker-compose.cluster.yml config -q && echo ok`
Expected: `ok`.

- [ ] **Step 7: `server/.env.example`** — thay hai dòng

```
# Có REDIS_URL → km Goong và dự báo mưa cache trong Redis. Cụm (docker-compose.cluster.yml) tự đặt.
REDIS_URL=
```

bằng:

```
# Có REDIS_URL → km Goong và dự báo mưa cache trong Redis, VÀ việc lập lịch đi qua queue: phải chạy thêm
# `uv run python -m app.worker`, không thì request báo lỗi sau 120 giây. Cụm (docker-compose.cluster.yml) tự đặt.
REDIS_URL=
# Số việc lập lịch mỗi phút cho một User (cần REDIS_URL); 0 = không giới hạn
PLAN_RPM=5
```

- [ ] **Step 8: Kiểm chứng đầu-cuối trên cụm** (cần `server/.env` có key LLM thật)

```bash
docker compose down
docker compose -f docker-compose.cluster.yml up -d --build
docker compose -f docker-compose.cluster.yml ps
```
Expected: 8 container chạy: `db`, `redis`, `llm-gateway`, `api-1`, `api-2`, `planner-1`, `planner-2`, `nginx`.

Volume cụm còn Place từ T2; nếu trống: `cd server && uv run python -m scripts.import_places ../data/places`.

```bash
for i in 1 2 3 4; do curl -si localhost:8000/health | grep -i x-upstream; done
```
Expected: hai địa chỉ IP khác nhau xen kẽ.

```bash
TOKEN=$(curl -s localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"t3@example.com","password":"matkhau123"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')
curl -siN localhost:8000/trips -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"Đà Lạt 2 ngày 3 triệu, đi grab, thích cafe"}' | tee /tmp/claude-t3-plan.txt | head -40
```
Expected: header `X-Job-Id`, các event `thinking` … rồi `itinerary` (hoặc `clarify`).

```bash
JOB=$(grep -i '^x-job-id' /tmp/claude-t3-plan.txt | tr -d '\r' | awk '{print $2}')
curl -sN localhost:8000/jobs/$JOB/events -H "Authorization: Bearer $TOKEN" | head -5
```
Expected: cùng các event, phát lại từ đầu.

Tắt worker giữa chừng: gửi một yêu cầu lập lịch mới (nền), rồi

```bash
docker compose -f docker-compose.cluster.yml exec redis redis-cli xpending jobs planners - + 10
docker kill <consumer>      # consumer = hostname = id container đang giữ việc
```
Expected: stream của client hiện "Đang thử lại…" sau khoảng 20 giây rồi ra `itinerary`; `GET /trips` chỉ có một Trip cho yêu cầu đó. Bật lại: `docker compose -f docker-compose.cluster.yml up -d`.

Rate limit:

```bash
for i in 1 2 3 4 5 6; do curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/trips \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"message":"x"}' --max-time 2; done
```
Expected: trong cùng một phút, các lần đầu `200` (hoặc `000` do `--max-time` cắt stream), lần vượt `PLAN_RPM` trả `429`.

Không có worker: `docker compose -f docker-compose.cluster.yml stop planner`, gửi một yêu cầu → sau 120 giây nhận event `error` "đang bận hoặc chưa chạy". Bật lại `planner`.

RAM: `docker stats --no-stream` → ghi tổng vào ROADMAP (spec §4: đo cuối T3).

Mở app desktop (`cd desktop && uv run python main.py`), lập một Trip qua cụm → ra Itinerary, client không sửa.

Trả về chế độ đơn giản: `docker compose -f docker-compose.cluster.yml down && docker compose up -d db redis`, rồi `cd server && uv run pytest -q` (277 passed) và `cd client && npm test && npm run build`.

Bước nào không chạy được (thiếu key, hết quota) thì ghi rõ trong báo cáo cuối, không đánh dấu là đã kiểm.

- [ ] **Step 9: Sửa spec** `docs/superpowers/specs/2026-10-01-scale-he-phan-tan-design.md`

Thêm vào bảng §2, sau dòng S17:

```markdown
| S18 | Worker chạy mỗi việc trong một transaction; event cuối phát sau khi commit | Generator ghi Trip và tin nhắn trước khi có Itinerary; chạy lại sau khi worker chết không được sinh bản ghi trùng |
| S19 | Worker báo nhịp tim 5 giây; việc im lặng quá 20 giây mới bị nhận lại | Lập lịch có thể dài hơn 60 giây; không nhịp tim thì worker đang sống bị giành việc |
| S20 | T3 chỉ làm phía server cho việc nối lại bằng `job_id`; client tự nối lại ở T6 | Giữ "client không sửa" trong T3 |
| S21 | `api` chờ event tối đa 120 giây im lặng rồi phát `error` | Có `REDIS_URL` mà không có `planner` thì không treo |
```

§5.1: thay dòng `planner: … xong: SET job:{job_id}:done, XACK` trong khối code bằng

```
  planner: XREADGROUP jobs → chạy đúng generator hiện có trong một transaction → XADD events:{job_id} cho mỗi event
           commit → SET job:{job_id}:done → phát event cuối → XADD mục `end` → XACK
```

và thay gạch đầu dòng "Event kết thúc: …" bằng:

```markdown
- Stream kết thúc bằng mục `end` do worker ghi; event cuối vẫn là `itinerary`, `answer`, `clarify`, `confirm_replan` hoặc `error` như hiện nay. `events:{job_id}` hết hạn sau 1 giờ.
- `api` chờ event mới tối đa 120 giây; quá thì phát `error` "Hệ thống lập lịch đang bận hoặc chưa chạy" và đóng stream.
- Client rớt giữa chừng thì việc vẫn chạy tới cùng trong worker; mở lại Trip là thấy lịch.
```

§5.2: thay bốn gạch đầu dòng đầu bằng:

```markdown
- Worker đọc bằng consumer group `planners`. Việc chưa `XACK` nằm trong danh sách chờ.
- Worker đang chạy việc báo nhịp tim mỗi 5 giây (`XCLAIM … JUSTID`: đặt lại thời gian im lặng, không tăng số lần giao). Việc im lặng quá 20 giây nghĩa là worker giữ nó đã chết: worker khác `XAUTOCLAIM` và chạy lại từ đầu, phát `thinking` "Đang thử lại…".
- Mỗi việc chạy trong một transaction Postgres. Worker chết → rollback, nên lần chạy lại không thấy Trip hay tin nhắn dở. Lỗi thường (LLM hỏng, yêu cầu sai) được bắt bên trong và vẫn commit như chế độ một tiến trình.
- Chống chạy trùng: trước khi chạy kiểm `job:{job_id}:done`. Đã có thì chỉ `XACK`.
- Chạy lại tối đa 1 lần; lần giao thứ ba thì phát `error` và `XACK`.
- Ngữ nghĩa giao việc là "ít nhất một lần". Khe hở còn lại: worker chết sau khi commit nhưng trước khi đặt `done` → việc chạy lại và có thể sinh bản ghi trùng. Chấp nhận, ghi trong báo cáo.
```

(xoá gạch đầu dòng cũ về "Khe hở còn lại" để không lặp.)

§5.3: thay gạch đầu dòng đầu bằng:

```markdown
- Áp cho ba endpoint đẩy việc vào queue (`POST /trips`, `/trips/{id}/plan`, `/trips/{id}/replan`), chung một bộ đếm cửa sổ cố định trong Redis: `rl:{user_id}:{phút}`, giới hạn `PLAN_RPM` (mặc định 5, `0` = tắt). Kiểm sau 404/409/422 để request sai không tốn lượt.
```

§4 bảng công tắc, dòng `REDIS_URL`, cột "Có →": `Queue (phải có planner chạy), cache Redis, rate limit`.

- [ ] **Step 10: Runbook** — thêm vào cuối `docs/runbook-cum.md`:

````markdown
## Queue và planner (T3)

Cụm có 2 bản `api` sau `nginx` (cổng 8000) và 2 `planner`. Header `X-Upstream` của mọi phản hồi cho biết bản `api` nào phục vụ.

```bash
dc exec redis redis-cli xlen jobs                          # số việc đã đẩy (tối đa ~1000 mục gần nhất)
dc exec redis redis-cli xpending jobs planners - + 10      # việc đang chạy: id, planner giữ nó, ms im lặng, số lần giao
dc logs -f planner
```

### Tắt một planner giữa lúc lập lịch

1. Gửi một yêu cầu lập lịch trong app.
2. `dc exec redis redis-cli xpending jobs planners - + 10` → cột thứ hai là id container đang giữ việc.
3. `docker kill <id>`.
4. Sau khoảng 20 giây Chat hiện "Đang thử lại…", rồi ra lịch. Danh sách chuyến đi chỉ có một Trip.
5. Bật lại: `dc up -d`.

Việc chạy lại tối đa một lần. Tắt cả hai `planner` thì request báo lỗi sau 120 giây.

### Rate limit

Mỗi User tối đa `PLAN_RPM` (mặc định 5) tin nhắn / lập lịch mỗi phút; vượt → 429 kèm `Retry-After`. Đổi cho một lần chạy: `PLAN_RPM=20 dc up -d`. Số lần bị chặn: `dc exec redis redis-cli get rl:blocked`.

`/auth/*` bị `nginx` giới hạn 1 request/giây theo IP (burst 10).

### Phát lại tiến trình của một việc

```bash
curl -N localhost:8000/jobs/<X-Job-Id>/events -H "Authorization: Bearer <token>"
```

Việc sống 1 giờ. User khác hoặc việc đã hết hạn → 404.

### Lưu ý

- Bật lại một bản `api` mà `nginx` không chuyển request tới: `dc restart nginx` (nginx chỉ phân giải tên `api` lúc khởi động).
- `redis-cli flushdb` xoá cả queue và việc đang chạy; `planner` tự tạo lại consumer group.
````

Sửa dòng đầu mục "Dựng cụm": `` `api` ở `localhost:8000` `` → `` `nginx` (trước 2 bản `api`) ở `localhost:8000` ``.

- [ ] **Step 11: ROADMAP, hiện trạng, CLAUDE.md**

`docs/ROADMAP.md`: tick dòng T3 (`- [x] **T3** — #49 — …` kèm link runbook), bảng tuần dòng T3 `⏳` → `✅` cho phần scale, số test server `243` → số thật sau Step 4, dòng "Tiếp:" trỏ sang T4 (#50 nếu đúng số issue — kiểm bằng `gh issue list --search "Scale T4"`), ghi tổng RAM đo được ở Step 8.

`docs/2026-09-25-hien-trang-app.md`: thêm một mục ngắn cạnh mục `llm-gateway`:

```markdown
Queue lập lịch (`server/app/jobs.py`, `server/app/worker.py`, chỉ khi có `REDIS_URL`, #49):

```
client ─► nginx ─► api ×2 ──XADD jobs──► planner ×2 (python -m app.worker)
                    ▲                        │ chạy trips.JOBS[kind] trong một transaction
                    └──XREAD events:{job_id}─┘ XADD events:{job_id}; nhịp tim 5 s, nhận lại sau 20 s im lặng
  rate limit theo User: rl:{user_id}:{phút} ≤ PLAN_RPM → 429 + Retry-After
  GET /jobs/{job_id}/events: phát lại tiến trình (header X-Job-Id)
```

Thiếu `REDIS_URL`: việc chạy ngay trong request như trước.
```

`CLAUDE.md`: dòng "Cụm" sửa thành `Cụm (nginx + 2 api + 2 planner + Redis + llm-gateway)`.

- [ ] **Step 12: Commit**

```bash
git add server/app/db.py server/tests/test_db.py docker/ docker-compose.cluster.yml server/.env.example docs/ CLAUDE.md
git commit -m "feat: cụm thêm nginx trước 2 bản api và 2 planner; runbook queue, rate limit, phát lại (#49)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-review (đã chạy khi viết plan)

- **Phủ spec:** §5.1 → Task 1, 3, 4, 6. §5.2 → Task 4, 5. §5.3 → Task 2, 6 (`limit_req` ở Task 7). §4 (`nginx`, 2 `api`, `planner`, công tắc `REDIS_URL`) → Task 6, 7. §13 dòng "Queue" → `test_worker.py`. §14 nghiệm thu T3 → Task 7 Step 8.
- **Ngoài phạm vi:** client tự nối lại (T6); stream `agent_jobs` và đa agent (T4); `GET /system/status` (T6).
- **Tên dùng chung:** `jobs.STREAM/GROUP/TTL_S`, `jobs.publish/finish/relay/enqueue/owner/check_rate`, `worker.ensure_group/step/run_job/_beat`, `trips.JOBS/guarded/sse` — khớp giữa các task.
