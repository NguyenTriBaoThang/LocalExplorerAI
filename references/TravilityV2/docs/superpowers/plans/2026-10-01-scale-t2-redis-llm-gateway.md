# Scale T2 — Redis + `llm-gateway` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mọi lời gọi LLM/embedding đi qua service `llm-gateway` có cache theo hash(request) (`off | on | replay`), giới hạn lượt gọi theo provider và tự chuyển provider cho chat; km Goong và dự báo mưa được cache trong Redis; kịch bản demo ghi một lần rồi phát lại được khi tắt mạng (#48, gộp #14).

**Architecture:** Một image, hai lệnh khởi động: `uvicorn app.main:app` (`api`) và `uvicorn app.gateway:app` (`llm-gateway`). Gateway nói giao thức OpenAI ở `/v1/chat/completions` và `/v1/embeddings`, trả nguyên văn phản hồi của provider; `api` chỉ đổi `LLM_BASE_URL` / `EMBED_BASE_URL`, không sửa `app/llm.py`. `app/kv.py` là lớp mỏng trên Redis: thiếu `REDIS_URL` thì không làm gì, nên chế độ một tiến trình chạy như cũ.

**Tech Stack:** FastAPI + Pydantic v2 (pydantic-settings), `redis` (redis-py, đồng bộ), `httpx`, psycopg3/Postgres + Redis 7 (Docker), pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-scale-he-phan-tan-design.md` — đọc §4 (bảng công tắc), §6, §8 (dòng `POST /distance`), §10, §13, §14. Ba bổ sung chốt khi brainstorm T2 (Task 7 ghi vào spec):

| # | Bổ sung | Lý do |
|---|---|---|
| T2-1 | `DEMO_TODAY` (ISO date) đóng băng "hôm nay" ở `parse_trip` và `forecast` | `PARSE_PROMPT` có "Hôm nay là {today}" → sang ngày khác là trượt cache |
| T2-2 | `GATEWAY_CHAT_TTL` (giây, mặc định 86400; `0` = không hết hạn) | Bản ghi cho demo/load test phải sống qua nhiều ngày |
| T2-3 | Cache dự báo Open-Meteo trong Redis | Mưa nằm trong brief; tắt mạng thì `get_rain_chance` trả `None` → brief khác bản ghi |

Khác với bản plan đã duyệt ở một điểm kỹ thuật: gateway viết **đồng bộ** (`def` handler, `redis.Redis`, `httpx.Client`) thay vì async, cho giống phần còn lại của codebase và test bằng `TestClient` không vướng event loop. Hành vi không đổi; chờ hết lượt chiếm một thread trong pool 40 thread của FastAPI, tối đa 30 giây.

## Global Constraints

- **Không sửa `server/app/llm.py`.**
- Thiếu `REDIS_URL` → app chạy như hiện nay. Toàn bộ test hiện có (203) phải xanh, **không sửa assert**.
- Dependency mới duy nhất: `redis>=5`. Không dùng thư viện giả lập Redis; test cần Redis dùng Redis thật ở `redis://localhost:6379/15` (`TEST_REDIS_URL`).
- Chỉ cache khớp chính xác theo hash(request) (S11). Chỉ ghi cache phản hồi 200.
- Embedding **không** chuyển provider (ADR-0003).
- Gateway trả nguyên văn thân phản hồi của provider (giữ `thought_signature` của Gemini). Không hỗ trợ `stream: true`.
- Redis lỗi không được chặn người dùng: `api` coi như trượt cache; gateway ở `on` vẫn gọi provider.
- Thông báo lỗi hướng tới người dùng là tiếng Việt.
- Lệnh test: `docker compose up -d db redis && cd server && uv run pytest` · `cd client && npm test && npm run build`.
- Commit message kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Redis chết giữa chừng.** `api`: `kv.get`/`kv.put` nuốt `RedisError`, lập lịch vẫn chạy (Task 1 có test). Gateway ở `on`: vẫn gọi provider (Task 4 có test).
2. **Provider trả lỗi không phải JSON** (trang HTML 502). Gateway chuyển nguyên status + thân, không cache, không lỗi 500 (Task 4 có test).
3. **Hết lượt provider mà chờ không đủ.** Chờ tối đa 30 giây rồi trả 429, không treo request vô hạn (Task 5 có test).
4. **Trúng cache không được tính lượt provider.** Nếu tính, chế độ `replay` cũng bị giới hạn và load test vô nghĩa (Task 5 có test).
5. **`DEMO_TODAY` viết sai định dạng.** Phải lỗi ngay khi khởi động, không lỗi 500 giữa stream (Task 1 có test). Và khi đã đóng băng ngày, kết quả dự báo lỗi cũng phải được ghi lại, nếu không lúc phát lại có mạng thì brief khác lúc ghi (Task 3 có test).

## File Structure

| File | Trách nhiệm |
|---|---|
| `server/app/kv.py` (mới) | `client()`, `get`, `put` trên Redis; thiếu `REDIS_URL` hoặc Redis lỗi → không làm gì |
| `server/app/config.py` | Thêm biến `redis_url`, `demo_today`, `gateway_cache`, `gateway_chat_ttl`, `llm_rpm`, `llm2_*` |
| `server/app/distance.py` | `_cache` thành lớp L1; đọc/ghi thêm Redis qua `kv` |
| `server/app/forecast.py` | Cache dự báo qua `kv` |
| `server/app/trips.py` | `_today()` theo `DEMO_TODAY`, truyền cho `parse_trip` và `forecast` |
| `server/app/gateway.py` (mới) | App FastAPI của `llm-gateway` |
| `docker-compose.yml` | Thêm service `redis` (cho test và dev) |
| `docker-compose.cluster.yml` (mới) | Cụm T2: `db`, `redis`, `llm-gateway`, `api` |
| `docs/runbook-cum.md` (mới) | Cách dựng cụm, ghi → phát lại demo, xoá cache |

---

### Task 1: Redis, cấu hình, `kv`

**Files:**
- Modify: `docker-compose.yml`, `server/pyproject.toml` + `server/uv.lock` (qua `uv add`), `server/app/config.py`, `server/tests/conftest.py`
- Create: `server/app/kv.py`, `server/tests/test_kv.py`, `server/tests/test_config.py`

**Interfaces:**
- Produces: `kv.client() -> redis.Redis | None` (`decode_responses=True`), `kv.get(key: str) -> str | None`, `kv.put(key: str, value: str, ex: int | None = None) -> None`; `settings.redis_url: str`, `settings.demo_today: dt.date | None`, `settings.gateway_cache: Literal["off","on","replay"]`, `settings.gateway_chat_ttl: int`, `settings.llm_rpm: int`, `settings.llm2_base_url / llm2_api_key / llm2_model: str`; fixture pytest `rds` (client Redis test đã `flushdb`, đồng thời trỏ `settings.redis_url` vào Redis test).

- [ ] **Step 1: Thêm Redis vào `docker-compose.yml`**

Thêm service sau `db` và volume `redisdata`:

```yaml
  redis:
    image: redis:7
    command: ["redis-server", "--appendonly", "yes"]
    ports: ["127.0.0.1:6379:6379"]
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 2s
      retries: 30
```

```yaml
volumes:
  pgdata: {}
  redisdata: {}
```

Service `api` trong file này **không** thêm `REDIS_URL`.

- [ ] **Step 2: Bật Redis và thêm dependency**

Run: `docker compose up -d db redis && cd server && uv add "redis>=5"`
Expected: container `redis` healthy; `pyproject.toml` có `redis>=5`, `uv.lock` đổi.

- [ ] **Step 3: Viết test (chưa có code)**

`server/tests/conftest.py` — thêm hai dòng env ngay dưới dòng `GOONG_API_KEY`, import `kv` + `settings`, và fixture `rds`:

```python
os.environ["GOONG_API_KEY"] = ""  # máy dev có key trong .env — test không được gọi Goong thật
os.environ["REDIS_URL"] = ""  # test không đụng Redis, trừ khi xin fixture rds
os.environ["DEMO_TODAY"] = ""

from app import distance, kv
from app.config import settings
from app.db import apply_schema, connect

TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
```

```python
@pytest.fixture
def rds(monkeypatch):
    """Redis thật (DB 15) đã xoá sạch; settings.redis_url trỏ vào đó trong lúc test chạy."""
    monkeypatch.setattr(settings, "redis_url", TEST_REDIS_URL)
    monkeypatch.setattr(kv, "_client", None)
    c = kv.client()
    c.flushdb()
    yield c
    c.flushdb()
```

`server/tests/test_kv.py`:

```python
from app import kv
from app.config import settings


def test_no_redis_url_is_noop(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "")
    kv.put("a", "1")
    assert kv.client() is None and kv.get("a") is None


def test_roundtrip_and_ttl(rds):
    kv.put("a", "1")
    kv.put("b", "2", ex=60)
    assert kv.get("a") == "1" and kv.get("khong-co") is None
    assert rds.ttl("a") == -1 and 0 < rds.ttl("b") <= 60


def test_redis_down_is_a_miss(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")  # không có gì nghe ở cổng 1
    monkeypatch.setattr(kv, "_client", None)
    kv.put("a", "1")  # không được ném lỗi
    assert kv.get("a") is None
```

`server/tests/test_config.py`:

```python
import datetime as dt

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_demo_today_blank_is_none():
    assert Settings(_env_file=None, demo_today="").demo_today is None


def test_demo_today_parsed():
    assert Settings(_env_file=None, demo_today="2026-12-01").demo_today == dt.date(2026, 12, 1)


def test_demo_today_garbage_rejected_at_startup():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, demo_today="hôm nay")


def test_gateway_cache_rejects_unknown_mode():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, gateway_cache="record")
```

- [ ] **Step 4: Chạy test, xác nhận đỏ**

Run: `cd server && uv run pytest tests/test_kv.py tests/test_config.py -q`
Expected: lỗi import `cannot import name 'kv' from 'app'`.

- [ ] **Step 5: Viết code**

`server/app/config.py` (toàn bộ file):

```python
import datetime as dt
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://travility:travility@localhost:5432/travility"
    jwt_secret: str = "dev-secret-change-me"
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    embed_base_url: str = "https://api.openai.com/v1"
    embed_api_key: str = ""
    embed_model: str = "text-embedding-3-small"
    goong_api_key: str = ""
    # Scale (spec 2026-10-01 §4): thiếu biến nào thì phần đó chạy như chế độ một tiến trình.
    redis_url: str = ""
    demo_today: dt.date | None = None  # đóng băng "hôm nay" để bản ghi replay của llm-gateway trúng cache
    # llm-gateway (app/gateway.py)
    gateway_cache: Literal["off", "on", "replay"] = "on"
    gateway_chat_ttl: int = 86400  # giây; 0 = không hết hạn (ghi kịch bản demo)
    llm_rpm: int = 0  # lượt chat mỗi phút tới provider chính; 0 = không giới hạn
    llm2_base_url: str = ""  # provider phụ cho chat; trống = không chuyển provider
    llm2_api_key: str = ""
    llm2_model: str = ""

    @field_validator("demo_today", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        return v or None


settings = Settings()
```

`server/app/kv.py`:

```python
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
```

- [ ] **Step 6: Chạy test, xác nhận xanh**

Run: `cd server && uv run pytest -q`
Expected: 203 test cũ + 7 test mới pass.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml server/pyproject.toml server/uv.lock server/app/config.py server/app/kv.py server/tests/conftest.py server/tests/test_kv.py server/tests/test_config.py
git commit -m "feat(server): Redis + kv, biến cấu hình cho llm-gateway (#48)"
```

---

### Task 2: Cache km Goong sang Redis

**Files:**
- Modify: `server/app/distance.py`
- Test: `server/tests/test_distance.py`

**Interfaces:**
- Consumes: `kv.get`, `kv.put`, fixture `rds` (Task 1).
- Produces: `distance.lookup` / `distance.prefetch` giữ nguyên chữ ký. Khoá Redis: `goong:{lat}:{lon}:{lat}:{lon}:{vehicle}`, giá trị JSON `[km, phút]`, không hết hạn.

- [ ] **Step 1: Viết test đỏ**

Thêm vào cuối `server/tests/test_distance.py`:

```python
def test_km_shared_through_redis(rds):
    distance.prefetch([A], [B], "xe-may", client_returning({"rows": [{"elements": [OK]}]}))
    distance._cache.clear()  # tiến trình khác: lớp cache trong RAM trống
    calls = []
    distance.prefetch([A], [B], "xe-may", client_returning({"rows": [{"elements": [OK]}]}, calls=calls))
    assert calls == []  # đã có trong Redis → không gọi Goong
    assert distance.lookup(A, B, "xe-may") == (2.34, 7)
    assert rds.ttl("goong:11.94:108.44:11.95:108.44:bike") == -1
```

- [ ] **Step 2: Chạy, xác nhận đỏ**

Run: `cd server && uv run pytest tests/test_distance.py::test_km_shared_through_redis -q`
Expected: FAIL — `assert calls == []` (Goong bị gọi lần hai).

- [ ] **Step 3: Sửa `server/app/distance.py`**

Thêm `import json` và `from app import kv`. Thay comment `ponytail:` + khai báo `_cache`, và ba hàm `_key` / `lookup` / phần đầu `prefetch` như sau (phần `params`, `try`/`except` giữ nguyên, chỉ đổi dòng ghi cache):

```python
# Lớp cache trong tiến trình, đứng trước Redis (kv). Km giữa hai điểm không đổi nên không cần xoá.
# ponytail: không giới hạn kích thước — số Place hữu hạn.
_cache: dict[tuple, tuple[float, int]] = {}
_down_until = 0.0


def _key(a, b, vehicle: str) -> tuple:
    return (a.lat, a.lon, b.lat, b.lon, vehicle)


def _kv_key(k: tuple) -> str:
    return "goong:" + ":".join(map(str, k))


def lookup(a, b, mode: str) -> tuple[float, int] | None:
    """(km, phút) đường thật đã lấy từ Goong; chưa có → None. Không gọi Goong."""
    k = _key(a, b, VEHICLE.get(mode, "bike"))
    if k not in _cache and (raw := kv.get(_kv_key(k))):
        _cache[k] = tuple(json.loads(raw))
    return _cache.get(k)
```

Trong `prefetch`, đổi điều kiện "đã có đủ" và chỗ ghi:

```python
    if all(lookup(a, b, mode) is not None for a in origins for b in destinations):
        return
```

```python
                if el["status"] == "OK":
                    k, v = _key(a, b, vehicle), (round(el["distance"]["value"] / 1000, 2),
                                                 max(1, round(el["duration"]["value"] / 60)))
                    _cache[k] = v
                    kv.put(_kv_key(k), json.dumps(v))
```

- [ ] **Step 4: Chạy, xác nhận xanh**

Run: `cd server && uv run pytest tests/test_distance.py tests/test_rules.py tests/test_replan.py -q`
Expected: tất cả pass (5 test cũ của `test_distance.py` không sửa).

- [ ] **Step 5: Commit**

```bash
git add server/app/distance.py server/tests/test_distance.py
git commit -m "feat(server): cache km Goong trong Redis, RAM chỉ còn là lớp trước (#48)"
```

---

### Task 3: Cache dự báo mưa + `DEMO_TODAY`

**Files:**
- Modify: `server/app/forecast.py`, `server/app/trips.py:95`, `server/app/trips.py:194`
- Test: `server/tests/test_forecast.py`, `server/tests/test_trips_api.py`

**Interfaces:**
- Consumes: `kv.get`, `kv.put`, `settings.demo_today`, fixture `rds` (Task 1).
- Produces: `forecast.CACHE_S = 21600`; `trips._today() -> dt.date`. Khoá Redis: `forecast:{lat}:{lon}:{start ISO}:{days}`, giá trị JSON list hoặc `null`.

- [ ] **Step 1: Viết test đỏ**

`server/tests/test_forecast.py` — thêm import `from app import forecast` và `from app.config import settings`, rồi thêm cuối file:

```python
ARGS = (11.9, 108.4, dt.date(2026, 9, 27), 2)
KEY = "forecast:11.9:108.4:2026-09-27:2"


def offline():
    def boom(request):
        raise httpx.ConnectError("offline")
    return httpx.Client(transport=httpx.MockTransport(boom))


def test_cached_in_redis_survives_network_loss(rds):
    assert get_rain_chance(*ARGS, client_returning([10, 20]), TODAY) == [10, 20]
    assert get_rain_chance(*ARGS, offline(), TODAY) == [10, 20]
    assert 0 < rds.ttl(KEY) <= forecast.CACHE_S


def test_failure_not_cached(rds):
    assert get_rain_chance(*ARGS, offline(), TODAY) is None
    assert get_rain_chance(*ARGS, client_returning([10, 20]), TODAY) == [10, 20]


def test_demo_today_records_failure_forever(rds, monkeypatch):
    """Đã đóng băng ngày thì kết quả lúc ghi (kể cả lỗi) phải lặp lại y nguyên lúc phát lại."""
    monkeypatch.setattr(settings, "demo_today", TODAY)
    assert get_rain_chance(*ARGS, offline(), TODAY) is None
    assert get_rain_chance(*ARGS, client_returning([10, 20]), TODAY) is None
    assert rds.ttl(KEY) == -1
```

`server/tests/test_trips_api.py` — thêm `import datetime as dt`, `from app.config import settings`, và test:

```python
def test_demo_today_freezes_parse_and_forecast(client, conn, monkeypatch):
    pid = add_place(conn, name="Cà phê Tùng", kind="cafe")
    fake = FakeClient(happy(pid))
    monkeypatch.setattr(llm, "chat_client", lambda: fake)
    monkeypatch.setattr(settings, "demo_today", dt.date(2026, 12, 1))
    seen = {}
    monkeypatch.setattr(forecast, "get_rain_chance", lambda *a, **k: seen.update(k))
    client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=auth(client))
    assert "Hôm nay là 2026-12-01" in fake.calls[0]["messages"][0]["content"]
    assert seen == {"today": dt.date(2026, 12, 1)}
```

- [ ] **Step 2: Chạy, xác nhận đỏ**

Run: `cd server && uv run pytest tests/test_forecast.py tests/test_trips_api.py::test_demo_today_freezes_parse_and_forecast -q`
Expected: 4 test mới FAIL (`AttributeError: CACHE_S`, lần gọi thứ hai trả `None`, prompt chứa ngày thật, `seen == {}`).

- [ ] **Step 3: Sửa `server/app/forecast.py`** (toàn bộ file)

```python
import datetime as dt
import json

import httpx

from app import kv
from app.config import settings

URL = "https://api.open-meteo.com/v1/forecast"
HORIZON_DAYS = 16
CACHE_S = 6 * 3600


def get_rain_chance(lat: float, lon: float, start: dt.date | None, days: int,
                    client: httpx.Client | None = None, today: dt.date | None = None) -> list[int | None] | None:
    if start is None:
        return None
    today = today or dt.date.today()
    horizon_end = today + dt.timedelta(days=HORIZON_DAYS - 1)
    if start < today or start > horizon_end:
        return None
    end = min(start + dt.timedelta(days=days - 1), horizon_end)
    key = f"forecast:{lat}:{lon}:{start.isoformat()}:{days}"
    if (raw := kv.get(key)) is not None:
        return json.loads(raw)
    # DEMO_TODAY: brief phải giống hệt lúc ghi thì llm-gateway mới trúng cache → ghi cả kết quả lỗi, không hết hạn.
    frozen = settings.demo_today is not None

    def _fetch(c):
        r = c.get(URL, params={
            "latitude": lat, "longitude": lon, "daily": "precipitation_probability_max",
            "timezone": "Asia/Ho_Chi_Minh", "start_date": start.isoformat(), "end_date": end.isoformat(),
        })
        r.raise_for_status()
        return r.json()["daily"]["precipitation_probability_max"]

    try:
        if client is not None:
            values = _fetch(client)
        else:
            with httpx.Client(timeout=5) as c:
                values = _fetch(c)
    except (httpx.HTTPError, KeyError, ValueError):
        if frozen:
            kv.put(key, "null")
        return None  # Forecast là phần phụ: lỗi thì lập lịch không có thời tiết
    out = (values + [None] * days)[:days]
    kv.put(key, json.dumps(out), ex=None if frozen else CACHE_S)
    return out
```

- [ ] **Step 4: Sửa `server/app/trips.py`**

Thêm dưới dòng `stream_conn = connect …`:

```python
def _today() -> dt.date:
    """Hôm nay theo giờ VN. DEMO_TODAY đóng băng ngày để bản ghi replay của llm-gateway trúng cache."""
    return settings.demo_today or dt.datetime.now(VN_TZ).date()
```

Dòng 95 (trong `_plan_and_save`):

```python
    rain = forecast.get_rain_chance(dest["lat"], dest["lon"], trip.start_date, trip.days, today=_today())
```

Dòng 194 (trong `_run`, tham số cuối của `parse_trip`): thay `dt.datetime.now(VN_TZ).date()` bằng `_today()`.

- [ ] **Step 5: Chạy, xác nhận xanh**

Run: `cd server && uv run pytest -q`
Expected: tất cả pass.

- [ ] **Step 6: Commit**

```bash
git add server/app/forecast.py server/app/trips.py server/tests/test_forecast.py server/tests/test_trips_api.py
git commit -m "feat(server): cache dự báo mưa trong Redis, DEMO_TODAY đóng băng ngày cho replay (#48)"
```

---

### Task 4: `llm-gateway` — proxy + cache `off | on | replay`

**Files:**
- Create: `server/app/gateway.py`, `server/tests/test_gateway.py`

**Interfaces:**
- Consumes: `kv.client()`, `settings.gateway_cache`, `settings.gateway_chat_ttl`, `settings.llm_base_url / llm_api_key`, `settings.embed_base_url / embed_api_key`, fixture `rds` (Task 1).
- Produces: `gateway.app` (FastAPI); `gateway.http` (`httpx.Client`, test thay được); `gateway._call(path: str, body: dict) -> httpx.Response` (Task 5, 6 sửa hàm này); `gateway._post(base, api_key, path, body) -> httpx.Response`; `gateway._synthetic(status, message) -> httpx.Response`; `gateway._redis(op, *args, default=None, **kw)`; `gateway._stat(name)`; hằng `CHAT = "chat/completions"`, `EMBED = "embeddings"`. Khoá Redis: `gw:cache:{sha256}`, `gw:stat:{hit|miss|provider_call}`.

- [ ] **Step 1: Viết test đỏ**

`server/tests/test_gateway.py`:

```python
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import gateway, kv
from app.config import settings

OK = {"id": "c1", "choices": [{"message": {"role": "assistant", "content": "xin chào"}}]}
CHAT = {"model": "m1", "messages": [{"role": "user", "content": "hi"}]}
EMB = {"model": "e1", "input": ["cà phê"], "dimensions": 768}

client = TestClient(gateway.app)


class Upstream:
    """Provider giả: replies[host] = (status | Exception, body); mặc định 200 OK."""

    def __init__(self):
        self.calls, self.replies = [], {}

    def __call__(self, request):
        self.calls.append(request)
        status, body = self.replies.get(request.url.host, (200, OK))
        if isinstance(status, Exception):
            raise status
        return httpx.Response(status, text=body) if isinstance(body, str) else httpx.Response(status, json=body)

    @property
    def hosts(self):
        return [c.url.host for c in self.calls]


@pytest.fixture
def up(monkeypatch, rds):
    u = Upstream()
    monkeypatch.setattr(gateway, "http", httpx.Client(transport=httpx.MockTransport(u)))
    for k, v in dict(llm_base_url="https://primary.test/v1/", llm_api_key="k1", llm_model="m1",
                     embed_base_url="https://embed.test/v1", embed_api_key="ke",
                     llm2_base_url="", llm2_api_key="", llm2_model="",
                     gateway_cache="on", gateway_chat_ttl=86400, llm_rpm=0).items():
        monkeypatch.setattr(settings, k, v)
    return u


def post(body=CHAT):
    return client.post("/v1/chat/completions", json=body)


def ask(i):
    """Một request chat khác nhau cho mỗi i (không trúng cache của nhau)."""
    return post({**CHAT, "messages": [{"role": "user", "content": f"câu {i}"}]})


def test_health():
    assert client.get("/health").json() == {"ok": True}


def test_proxies_with_gateway_key_not_callers(up):
    r = client.post("/v1/chat/completions", json=CHAT, headers={"Authorization": "Bearer cua-ben-goi"})
    assert r.status_code == 200 and r.json() == OK and r.headers["x-cache"] == "miss"
    req = up.calls[0]
    assert str(req.url) == "https://primary.test/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer k1"
    assert json.loads(req.content) == CHAT


def test_same_request_hits_cache_regardless_of_key_order(up, rds):
    post()
    r = post({"messages": CHAT["messages"], "model": "m1"})
    assert r.json() == OK and r.headers["x-cache"] == "hit" and len(up.calls) == 1
    assert rds.mget("gw:stat:hit", "gw:stat:miss", "gw:stat:provider_call") == ["1", "1", "1"]


def test_different_request_misses(up):
    ask(1)
    assert ask(2).headers["x-cache"] == "miss" and len(up.calls) == 2


def test_chat_expires_embedding_does_not(up, rds):
    post()
    r = client.post("/v1/embeddings", json=EMB)
    assert r.status_code == 200
    assert str(up.calls[1].url) == "https://embed.test/v1/embeddings"
    assert up.calls[1].headers["authorization"] == "Bearer ke"
    ttls = sorted(rds.ttl(k) for k in rds.keys("gw:cache:*"))
    assert ttls[0] == -1 and 0 < ttls[1] <= 86400


def test_chat_ttl_zero_never_expires(up, rds, monkeypatch):
    monkeypatch.setattr(settings, "gateway_chat_ttl", 0)
    post()
    assert [rds.ttl(k) for k in rds.keys("gw:cache:*")] == [-1]


def test_off_always_calls_provider(up, rds, monkeypatch):
    monkeypatch.setattr(settings, "gateway_cache", "off")
    post()
    post()
    assert len(up.calls) == 2 and rds.keys("gw:cache:*") == []


def test_replay_serves_recorded_and_rejects_unrecorded(up, monkeypatch):
    post()
    monkeypatch.setattr(settings, "gateway_cache", "replay")
    assert post().json() == OK
    r = ask(1)
    assert r.status_code == 503 and "chưa ghi" in r.json()["error"]["message"]
    assert len(up.calls) == 1  # replay không bao giờ gọi provider


def test_provider_error_passed_through_not_cached(up):
    up.replies["primary.test"] = (400, {"error": {"message": "bad"}})
    r = post()
    assert r.status_code == 400 and r.json() == {"error": {"message": "bad"}}
    post()
    assert len(up.calls) == 2


def test_non_json_provider_error_passed_through(up):
    up.replies["primary.test"] = (502, "<html>Bad Gateway</html>")
    r = post()
    assert r.status_code == 502 and r.text == "<html>Bad Gateway</html>"


def test_provider_unreachable_gives_504(up):
    up.replies["primary.test"] = (httpx.ConnectError("offline"), None)
    r = post()
    assert r.status_code == 504 and "không phản hồi" in r.json()["error"]["message"]


def test_stream_rejected(up):
    r = post({**CHAT, "stream": True})
    assert r.status_code == 400 and up.calls == []


def test_redis_down_still_answers(up, monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")
    monkeypatch.setattr(kv, "_client", None)
    assert post().status_code == 200 and post().headers["x-cache"] == "miss"
    assert len(up.calls) == 2
```

- [ ] **Step 2: Chạy, xác nhận đỏ**

Run: `cd server && uv run pytest tests/test_gateway.py -q`
Expected: lỗi import `cannot import name 'gateway' from 'app'`.

- [ ] **Step 3: Viết `server/app/gateway.py`**

```python
"""llm-gateway: proxy giao thức OpenAI đứng giữa các service và provider (spec scale §6).

Cache theo hash(request), giới hạn lượt gọi theo provider, chuyển sang provider phụ khi provider chính lỗi.
Chạy: uvicorn app.gateway:app
"""
import hashlib
import json

import httpx
from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse, Response
from redis.exceptions import RedisError

from app import kv
from app.config import settings

CHAT, EMBED = "chat/completions", "embeddings"

app = FastAPI(title="Travility llm-gateway")
http = httpx.Client(timeout=60)  # test thay bằng MockTransport


def _redis(op: str, *args, default=None, **kw):
    """Gọi một lệnh Redis; không cấu hình hoặc lỗi → default (Redis lỗi thì bỏ qua, không chặn — spec §10)."""
    c = kv.client()
    if c is None:
        return default
    try:
        return getattr(c, op)(*args, **kw)
    except RedisError:
        return default


def _stat(name: str) -> None:
    _redis("incr", f"gw:stat:{name}")


def _synthetic(status: int, message: str) -> httpx.Response:
    """Lỗi do gateway tự sinh, cùng dạng thân lỗi của OpenAI để SDK phía gọi đọc được."""
    return httpx.Response(status, json={"error": {"message": message, "type": "gateway_error"}})


def _post(base: str, api_key: str, path: str, body: dict) -> httpx.Response:
    _stat("provider_call")
    try:
        return http.post(f"{base.rstrip('/')}/{path}", json=body, headers={"Authorization": f"Bearer {api_key}"})
    except httpx.HTTPError as e:
        return _synthetic(504, f"provider không phản hồi ({type(e).__name__})")


def _call(path: str, body: dict) -> httpx.Response:
    if path == EMBED:
        return _post(settings.embed_base_url, settings.embed_api_key, path, body)
    return _post(settings.llm_base_url, settings.llm_api_key, path, body)


def _cache_key(path: str, body: dict) -> str:
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "gw:cache:" + hashlib.sha256(f"{path}\n{canon}".encode()).hexdigest()


def _handle(path: str, body: dict) -> Response:
    if body.get("stream"):
        return JSONResponse({"error": {"message": "llm-gateway không hỗ trợ stream"}}, status_code=400)
    mode, key = settings.gateway_cache, _cache_key(path, body)
    if mode != "off":
        hit = _redis("get", key)
        if hit is not None:
            _stat("hit")
            return Response(hit, media_type="application/json", headers={"X-Cache": "hit"})
        if mode == "replay":
            return JSONResponse({"error": {"message": "llm-gateway đang ở chế độ replay và chưa ghi phản hồi "
                                                      "cho request này"}}, status_code=503)
        _stat("miss")
    r = _call(path, body)
    if r.status_code == 200 and mode == "on":
        ttl = settings.gateway_chat_ttl if path == CHAT else 0  # embedding không hết hạn
        _redis("set", key, r.text, ex=ttl or None)
    return Response(r.content, status_code=r.status_code,
                    media_type=r.headers.get("content-type", "application/json"), headers={"X-Cache": "miss"})


@app.post("/v1/chat/completions")
def chat_completions(body: dict = Body(...)):
    return _handle(CHAT, body)


@app.post("/v1/embeddings")
def embeddings(body: dict = Body(...)):
    return _handle(EMBED, body)


@app.get("/health")
def health():
    return {"ok": True}
```

- [ ] **Step 4: Chạy, xác nhận xanh**

Run: `cd server && uv run pytest tests/test_gateway.py -q`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add server/app/gateway.py server/tests/test_gateway.py
git commit -m "feat(server): llm-gateway proxy giao thức OpenAI với cache off/on/replay (#48)"
```

---

### Task 5: `llm-gateway` — giới hạn lượt gọi theo provider

**Files:**
- Modify: `server/app/gateway.py`
- Test: `server/tests/test_gateway.py`

**Interfaces:**
- Consumes: `_redis`, `_stat`, `_synthetic`, `_post`, `_call` (Task 4); `settings.llm_rpm`.
- Produces: `gateway._take_slot() -> bool`; `gateway._now`, `gateway._sleep` (test thay bằng đồng hồ giả); hằng `MAX_WAIT_S = 30`. Khoá Redis: `gw:rl:{phút}` (hết hạn 120 giây), `gw:stat:wait`.

- [ ] **Step 1: Viết test đỏ**

Thêm vào `server/tests/test_gateway.py`:

```python
class Clock:
    def __init__(self, second_of_minute):
        self.t, self.slept = 60_000_000.0 + second_of_minute, []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def use_clock(monkeypatch, second_of_minute, rpm):
    c = Clock(second_of_minute)
    monkeypatch.setattr(gateway, "_now", c.now)
    monkeypatch.setattr(gateway, "_sleep", c.sleep)
    monkeypatch.setattr(settings, "llm_rpm", rpm)
    return c


def test_out_of_slots_waits_for_next_minute(up, rds, monkeypatch):
    clock = use_clock(monkeypatch, second_of_minute=50, rpm=2)
    assert [ask(i).status_code for i in range(3)] == [200, 200, 200]
    assert clock.slept == [10] and len(up.calls) == 3
    assert rds.get("gw:stat:wait") == "1"


def test_gives_429_after_waiting_30s(up, monkeypatch):
    clock = use_clock(monkeypatch, second_of_minute=0, rpm=1)
    ask(1)
    r = ask(2)
    assert r.status_code == 429 and "hết lượt" in r.json()["error"]["message"]
    assert clock.slept == [30] and len(up.calls) == 1


def test_cache_hit_does_not_take_a_slot(up, monkeypatch):
    clock = use_clock(monkeypatch, second_of_minute=0, rpm=1)
    assert [post().status_code, post().status_code] == [200, 200]
    assert clock.slept == [] and len(up.calls) == 1


def test_embeddings_not_rate_limited(up, monkeypatch):
    clock = use_clock(monkeypatch, second_of_minute=0, rpm=1)
    for i in range(3):
        assert client.post("/v1/embeddings", json={**EMB, "input": [f"q{i}"]}).status_code == 200
    assert clock.slept == []


def test_rpm_zero_means_no_limit(up, rds):
    for i in range(5):
        ask(i)
    assert len(up.calls) == 5 and rds.keys("gw:rl:*") == []
```

- [ ] **Step 2: Chạy, xác nhận đỏ**

Run: `cd server && uv run pytest tests/test_gateway.py -q -k "slot or 429 or rate or rpm"`
Expected: FAIL — `AttributeError: … has no attribute '_now'`.

- [ ] **Step 3: Sửa `server/app/gateway.py`**

Thêm `import time`, và dưới `CHAT, EMBED = …`:

```python
MAX_WAIT_S = 30  # hết lượt của provider: chờ tối đa bấy nhiêu rồi mới trả 429
```

Dưới dòng `http = …`:

```python
_now, _sleep = time.time, time.sleep  # test thay bằng đồng hồ giả
```

Thêm hàm trước `_call`, và sửa `_call`:

```python
def _take_slot() -> bool:
    """Giữ một lượt gọi provider chính trong phút này. Hết lượt thì chờ sang phút sau, tối đa MAX_WAIT_S.

    ponytail: cửa sổ cố định theo phút, chỉ áp cho chat của provider chính. Embedding không giới hạn
    (cache không hết hạn nên gần như luôn trúng); cần thì thêm bộ đếm theo host của provider.
    """
    if not settings.llm_rpm:
        return True
    waited = 0.0
    while True:
        now = _now()
        key = f"gw:rl:{int(now // 60)}"
        n = _redis("incr", key, default=0)
        if n == 1:
            _redis("expire", key, 120)
        if n <= settings.llm_rpm:
            return True
        if waited >= MAX_WAIT_S:
            return False
        if not waited:
            _stat("wait")
        pause = min(60 - now % 60, MAX_WAIT_S - waited)
        _sleep(pause)
        waited += pause


def _call(path: str, body: dict) -> httpx.Response:
    if path == EMBED:
        return _post(settings.embed_base_url, settings.embed_api_key, path, body)
    if not _take_slot():
        return _synthetic(429, "llm-gateway: hết lượt gọi provider trong phút này, thử lại sau ít giây")
    return _post(settings.llm_base_url, settings.llm_api_key, path, body)
```

- [ ] **Step 4: Chạy, xác nhận xanh**

Run: `cd server && uv run pytest tests/test_gateway.py -q`
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git add server/app/gateway.py server/tests/test_gateway.py
git commit -m "feat(server): llm-gateway giới hạn lượt gọi theo provider, hết lượt thì chờ (#48)"
```

---

### Task 6: `llm-gateway` — chuyển provider + bỏ qua provider chính khi lỗi liên tiếp

**Files:**
- Modify: `server/app/gateway.py`
- Test: `server/tests/test_gateway.py`

**Interfaces:**
- Consumes: `_take_slot`, `_post`, `_synthetic`, `_redis`, `_stat` (Task 4, 5); `settings.llm2_base_url / llm2_api_key / llm2_model`.
- Produces: hằng `DOWN_S = 30`, `FAILS_TO_SKIP = 3`. Khoá Redis: `gw:fail` (đếm lỗi liên tiếp), `gw:down` (hết hạn `DOWN_S`), `gw:stat:fallback`.

- [ ] **Step 1: Viết test đỏ**

Thêm vào `server/tests/test_gateway.py`:

```python
@pytest.fixture
def backup(up, monkeypatch):
    for k, v in dict(llm2_base_url="https://backup.test/v1", llm2_api_key="k2", llm2_model="m2").items():
        monkeypatch.setattr(settings, k, v)
    return up


@pytest.mark.parametrize("failure", [(429, {}), (500, {}), (httpx.ReadTimeout("chậm"), None)])
def test_chat_falls_back_and_swaps_model(backup, rds, failure):
    backup.replies["primary.test"] = failure
    r = post()
    assert r.status_code == 200 and r.json() == OK
    assert backup.hosts == ["primary.test", "backup.test"]
    second = backup.calls[1]
    assert json.loads(second.content)["model"] == "m2" and second.headers["authorization"] == "Bearer k2"
    assert rds.get("gw:stat:fallback") == "1"


def test_bad_request_does_not_fall_back(backup):
    backup.replies["primary.test"] = (400, {"error": {"message": "bad"}})
    assert post().status_code == 400 and backup.hosts == ["primary.test"]


def test_embedding_never_falls_back(backup):
    backup.replies["embed.test"] = (500, {})
    assert client.post("/v1/embeddings", json=EMB).status_code == 500
    assert backup.hosts == ["embed.test"]


def test_no_backup_returns_primary_error(up):
    up.replies["primary.test"] = (500, {"error": {"message": "hỏng"}})
    assert post().status_code == 500 and up.hosts == ["primary.test"]


def test_backup_error_is_returned(backup):
    backup.replies["primary.test"] = (500, {})
    backup.replies["backup.test"] = (503, {"error": {"message": "cũng hỏng"}})
    r = post()
    assert r.status_code == 503 and r.json()["error"]["message"] == "cũng hỏng"


def test_three_failures_skip_primary(backup):
    backup.replies["primary.test"] = (500, {})
    for i in range(3):
        ask(i)
    assert ask(3).status_code == 200
    assert backup.hosts == ["primary.test", "backup.test"] * 3 + ["backup.test"]


def test_success_resets_failure_count(backup):
    backup.replies["primary.test"] = (500, {})
    ask(0)
    ask(1)
    del backup.replies["primary.test"]
    ask(2)  # thành công → đếm lại từ đầu
    backup.replies["primary.test"] = (500, {})
    ask(3)
    ask(4)
    assert backup.hosts[-2:] == ["primary.test", "backup.test"]  # lần thứ 5 vẫn thử provider chính


def test_skipped_primary_without_backup_gives_503(up):
    up.replies["primary.test"] = (500, {})
    for i in range(3):
        ask(i)
    r = ask(3)
    assert r.status_code == 503 and "tạm nghỉ" in r.json()["error"]["message"]
    assert len(up.calls) == 3
```

- [ ] **Step 2: Chạy, xác nhận đỏ**

Run: `cd server && uv run pytest tests/test_gateway.py -q`
Expected: các test `falls_back`, `backup_error`, `three_failures`, `success_resets`, `skipped_primary` FAIL (chưa có lời gọi tới `backup.test`).

- [ ] **Step 3: Sửa `server/app/gateway.py`**

Thêm dưới `MAX_WAIT_S`:

```python
DOWN_S = 30  # provider chính lỗi FAILS_TO_SKIP lần liên tiếp → bỏ qua nó bấy nhiêu giây
FAILS_TO_SKIP = 3
```

Thay toàn bộ `_call`:

```python
def _failed(r: httpx.Response) -> bool:
    return r.status_code == 429 or r.status_code >= 500


def _call(path: str, body: dict) -> httpx.Response:
    if path == EMBED:
        # Không chuyển provider: hai provider cho hai không gian vector khác nhau, đổi là phải import lại Place (ADR-0003).
        return _post(settings.embed_base_url, settings.embed_api_key, path, body)
    r = _synthetic(503, "provider chính đang tạm nghỉ sau nhiều lỗi liên tiếp, thử lại sau ít giây")
    if not _redis("exists", "gw:down", default=0):
        if not _take_slot():
            return _synthetic(429, "llm-gateway: hết lượt gọi provider trong phút này, thử lại sau ít giây")
        r = _post(settings.llm_base_url, settings.llm_api_key, path, body)
        if not _failed(r):
            _redis("delete", "gw:fail")
            return r
        if _redis("incr", "gw:fail", default=0) >= FAILS_TO_SKIP:
            _redis("set", "gw:down", "1", ex=DOWN_S)
            _redis("delete", "gw:fail")
    if not settings.llm2_base_url:
        return r
    _stat("fallback")
    return _post(settings.llm2_base_url, settings.llm2_api_key, path, {**body, "model": settings.llm2_model})
```

- [ ] **Step 4: Chạy, xác nhận xanh**

Run: `cd server && uv run pytest -q`
Expected: toàn bộ pass (test gateway: 28).

- [ ] **Step 5: Commit**

```bash
git add server/app/gateway.py server/tests/test_gateway.py
git commit -m "feat(server): llm-gateway chuyển provider phụ cho chat, bỏ qua provider chính khi lỗi liên tiếp (#48)"
```

---

### Task 7: Cụm compose, tài liệu, kiểm chứng đầu-cuối

**Files:**
- Create: `docker-compose.cluster.yml`, `docs/runbook-cum.md`
- Modify: `server/.env.example`, `CLAUDE.md`, `docs/superpowers/specs/2026-10-01-scale-he-phan-tan-design.md`, `docs/ROADMAP.md`, `docs/2026-09-25-hien-trang-app.md`

**Interfaces:**
- Consumes: `app.gateway:app`, mọi biến môi trường của Task 1.

- [ ] **Step 1: Viết `docker-compose.cluster.yml`**

```yaml
# Cụm phân tán (spec scale §4). T2: db + redis + llm-gateway + api.
# Dùng chung cổng 5432/6379/8000 với docker-compose.yml → `docker compose down` trước khi bật cụm.
name: travility-cluster
services:
  db:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_USER: travility
      POSTGRES_PASSWORD: travility
      POSTGRES_DB: travility
    ports: ["127.0.0.1:5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./docker/initdb:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U travility"]
      interval: 2s
      retries: 30
  redis:
    image: redis:7
    command: ["redis-server", "--appendonly", "yes"]
    ports: ["127.0.0.1:6379:6379"]
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 2s
      retries: 30
  llm-gateway:
    build: ./server
    command: ["uv", "run", "--no-dev", "uvicorn", "app.gateway:app", "--host", "0.0.0.0", "--port", "8000"]
    env_file: ./server/.env  # LLM_* / EMBED_* ở đây là provider thật
    environment:
      REDIS_URL: redis://redis:6379/0
      GATEWAY_CACHE: ${GATEWAY_CACHE:-on}
      GATEWAY_CHAT_TTL: ${GATEWAY_CHAT_TTL:-86400}
    ports: ["127.0.0.1:8001:8000"]
    depends_on:
      redis:
        condition: service_healthy
  api:
    build: ./server
    env_file: ./server/.env
    environment:
      DATABASE_URL: postgresql://travility:travility@db:5432/travility
      REDIS_URL: redis://redis:6379/0
      LLM_BASE_URL: http://llm-gateway:8000/v1
      EMBED_BASE_URL: http://llm-gateway:8000/v1
      DEMO_TODAY: ${DEMO_TODAY:-}
    ports: ["127.0.0.1:8000:8000"]
    depends_on:
      db:
        condition: service_healthy
      llm-gateway:
        condition: service_started
volumes:
  pgdata: {}
  redisdata: {}
```

- [ ] **Step 2: Thêm vào cuối `server/.env.example`**

```bash
# --- Scale (spec 2026-10-01). Để trống cả khối này = chạy một tiến trình như cũ. ---
# Có REDIS_URL → km Goong và dự báo mưa cache trong Redis. Cụm (docker-compose.cluster.yml) tự đặt.
REDIS_URL=
# Đóng băng "hôm nay" (YYYY-MM-DD) để bản ghi replay trúng cache ở ngày khác. Xem docs/runbook-cum.md
DEMO_TODAY=
# llm-gateway: off | on | replay. replay = chỉ đọc cache, request chưa ghi → 503 (demo mất mạng)
GATEWAY_CACHE=on
# Giây; 0 = không hết hạn (dùng khi ghi kịch bản demo)
GATEWAY_CHAT_TTL=86400
# Lượt chat mỗi phút tới provider chính; 0 = không giới hạn. Gemini free: đặt thấp hơn quota một chút
LLM_RPM=0
# Provider phụ cho chat khi provider chính trả 429/5xx/timeout. Trống = không chuyển
LLM2_BASE_URL=
LLM2_API_KEY=
LLM2_MODEL=
```

- [ ] **Step 3: Viết `docs/runbook-cum.md`**

````markdown
# Runbook cụm Travility

Cụm phân tán chạy bằng `docker-compose.cluster.yml` ([spec](superpowers/specs/2026-10-01-scale-he-phan-tan-design.md)). Dev hằng ngày vẫn dùng `docker compose up` (một tiến trình). Hai chế độ dùng chung cổng nên chỉ bật một.

## Dựng cụm

```bash
docker compose down                                        # tắt chế độ một tiến trình nếu đang chạy
docker compose -f docker-compose.cluster.yml up -d --build
cd server && uv run python -m scripts.import_places ../data/places   # lần đầu: volume mới chưa có Place
```

`api` ở `localhost:8000`, `llm-gateway` ở `localhost:8001` (chỉ để kiểm tra). Mọi lệnh dưới đây viết tắt `dc` = `docker compose -f docker-compose.cluster.yml`.

## Số đếm của gateway

```bash
dc exec redis redis-cli mget gw:stat:hit gw:stat:miss gw:stat:provider_call gw:stat:wait gw:stat:fallback
```

## Ghi kịch bản demo rồi phát lại khi mất mạng

Request LLM phải lặp lại y nguyên mới trúng cache, nên "hôm nay" phải cố định và database không được import lại giữa lúc ghi và lúc phát.

1. Chọn ngày ghi, ví dụ hôm nay. Bật cụm ở chế độ ghi, không hết hạn:
   ```bash
   DEMO_TODAY=2026-10-01 GATEWAY_CACHE=on GATEWAY_CHAT_TTL=0 dc up -d
   ```
2. Có mạng: chạy đúng kịch bản demo trong app, từng tin nhắn theo đúng thứ tự, trên Trip mới.
3. Chuyển sang phát lại (giữ nguyên `DEMO_TODAY`):
   ```bash
   DEMO_TODAY=2026-10-01 GATEWAY_CACHE=replay dc up -d
   ```
4. Tắt mạng, tạo Trip mới, chạy lại kịch bản. Tin nhắn ngoài kịch bản → bong bóng lỗi (gateway trả 503).

Ngày đi trong kịch bản nên nằm trong 16 ngày kể từ `DEMO_TODAY` để có dự báo mưa. Kết quả dự báo lúc ghi (kể cả lỗi) được giữ lại cho lúc phát.

## Xoá cache

```bash
dc exec redis sh -c "redis-cli --scan --pattern 'gw:cache:*' | xargs -r redis-cli del"   # chỉ cache LLM/embedding
dc exec redis redis-cli flushdb                                                           # mọi thứ: cache, km Goong, dự báo, số đếm
```
````

- [ ] **Step 4: Sửa `CLAUDE.md` mục Commands**

Thay dòng Server test và thêm một dòng:

```markdown
- Server test: `docker compose up -d db redis && cd server && uv run pytest`
- Cụm (Redis + llm-gateway): `docker compose -f docker-compose.cluster.yml up -d --build` — xem `docs/runbook-cum.md`
```

- [ ] **Step 5: Ghi ba bổ sung vào spec**

Trong `docs/superpowers/specs/2026-10-01-scale-he-phan-tan-design.md`:

1. Bảng §2, thêm ba dòng sau S14:
   ```markdown
   | S15 | `DEMO_TODAY` đóng băng "hôm nay" ở `parse_trip` và `forecast` | Prompt đọc yêu cầu có ngày hôm nay; không đóng băng thì bản ghi `replay` trượt cache khi sang ngày khác |
   | S16 | `GATEWAY_CHAT_TTL`, `0` = không hết hạn | Bản ghi cho demo và load test phải sống qua nhiều ngày |
   | S17 | Dự báo Open-Meteo cache trong Redis (6 giờ; có `DEMO_TODAY` thì không hết hạn và ghi cả kết quả lỗi) | Khả năng mưa nằm trong brief gửi LLM; mất mạng mà brief đổi thì trượt cache |
   ```
2. Bảng công tắc §4, thêm dòng: `| `DEMO_TODAY` | Dùng ngày thật theo giờ VN | Mọi chỗ cần "hôm nay" dùng ngày này |`
3. §6, bảng chế độ cache, dòng `on`: đổi "Chat hết hạn sau 24 giờ" thành "Chat hết hạn sau `GATEWAY_CHAT_TTL` giây (mặc định 24 giờ, `0` = không hết hạn)". Đoạn "Quy trình demo" đổi thành: "Quy trình demo: đặt `DEMO_TODAY` và `GATEWAY_CHAT_TTL=0`, chạy kịch bản một lần ở chế độ `on` khi có mạng, rồi chuyển `replay` ([runbook](../../runbook-cum.md))."
4. §6, cuối đoạn "Giới hạn theo provider", thêm: "Chỉ áp cho chat của provider chính; trúng cache không tính lượt."
5. §6, thêm một câu cuối mục: "Gateway viết đồng bộ như phần còn lại của server; lượt chờ chiếm một thread trong pool của FastAPI."

- [ ] **Step 6: Kiểm chứng đầu-cuối trên cụm (cần mạng + key thật trong `server/.env`)**

```bash
docker compose down
docker compose -f docker-compose.cluster.yml up -d --build
cd server && uv run python -m scripts.import_places ../data/places && cd ..
alias dc='docker compose -f docker-compose.cluster.yml'
plan() {  # $1 = email → đăng ký User mới rồi lập một Trip, in event cuối và thời gian
  TOKEN=$(curl -s localhost:8000/auth/register -H 'content-type: application/json' \
    -d "{\"email\":\"$1\",\"password\":\"matkhau123\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
  time curl -sN localhost:8000/trips -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
    -d '{"message":"Đà Lạt 2 ngày 3 triệu cho 2 người, đi xe máy thuê, thích cà phê và thiên nhiên"}' | tail -c 400
}
plan a@example.com
dc exec redis redis-cli mget gw:stat:hit gw:stat:miss gw:stat:provider_call
plan b@example.com
dc exec redis redis-cli mget gw:stat:hit gw:stat:miss gw:stat:provider_call
```

Expected: lần 1 kết thúc bằng event `"type": "itinerary"`, `miss` và `provider_call` > 0. Lần 2 nhanh rõ rệt (vài giây), `hit` tăng, `provider_call` **không tăng**.

Phát lại khi provider không tới được:

```bash
GATEWAY_CACHE=replay dc up -d llm-gateway
plan c@example.com          # Expected: vẫn ra itinerary, provider_call không tăng
TOKEN=$(curl -s localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"email":"c@example.com","password":"matkhau123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -sN localhost:8000/trips -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"message":"Đà Lạt 1 ngày 1 triệu"}' | tail -c 300
# Expected: event "type": "error" (gateway trả 503 cho request chưa ghi)
```

Chuyển provider (nếu có key provider thứ hai): đặt `LLM2_*` trong `server/.env`, chạy `GATEWAY_CACHE=off LLM_API_KEY=sai dc up -d llm-gateway`, `plan d@example.com` → vẫn ra itinerary, `gw:stat:fallback` > 0. Không có key thứ hai thì ghi rõ trong PR là bước này chưa kiểm tay (đã có test tự động).

Cuối cùng: `cd server && uv run pytest -q` và `cd client && npm test && npm run build`.

- [ ] **Step 7: Cập nhật ROADMAP và hiện trạng**

- `docs/ROADMAP.md`: tick `[x]` dòng **T2 — #48**; bảng tổng quan nhóm 11 thành `1 | 6`; dòng test tự động ở nhóm 10 ghi số test server mới (lấy từ kết quả pytest); bảng lộ trình tuần T2 thành ✅; mục "Việc cần làm ngay" số 1 đổi "Tiếp: lát scale T3 (#49)".
- `docs/2026-09-25-hien-trang-app.md`: ở §2.2 đổi "cache trong tiến trình" của Leg thành "cache trong tiến trình + Redis khi có `REDIS_URL`"; ở §2.4 đổi dòng "Mỗi lần search gọi embedding một lần…" thành hướng xử lý "llm-gateway cache (#48): chạy cụm `docker-compose.cluster.yml`"; thêm một đoạn ngắn dưới §2.2 mô tả `llm-gateway` (2–3 dòng, trỏ sang runbook).

- [ ] **Step 8: Commit**

```bash
git add docker-compose.cluster.yml server/.env.example docs/runbook-cum.md CLAUDE.md docs/superpowers/specs/2026-10-01-scale-he-phan-tan-design.md docs/superpowers/plans/2026-10-01-scale-t2-redis-llm-gateway.md docs/ROADMAP.md docs/2026-09-25-hien-trang-app.md
git commit -m "feat: cụm docker-compose.cluster.yml (Redis + llm-gateway), runbook ghi và phát lại demo (#48, #14)"
```

PR: tiêu đề `feat(server): Redis + llm-gateway — cache, replay, giới hạn và chuyển provider (#48)`, thân có `Closes #48` và `Closes #14`.
