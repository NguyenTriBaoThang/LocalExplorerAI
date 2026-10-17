# Scale T5 — Service `places`, bản sao đọc, 2 shard theo `user_id` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Context

T2–T4 của lát scale đã merge (PR #55, #56, #57): cụm có Redis, `llm-gateway`, queue + `planner`, `nginx` + 2 `api`, đa agent. Cả cụm vẫn dùng **một** Postgres và một `conn` duy nhất chạy xuyên `agent.plan`, `followup`, `multi`, `proposals`, `versions`, vừa ghi Trip vừa đọc Place. T5 (#51) là tuần cuối thêm thành phần hạ tầng: tách `places` thành service đọc từ bản sao, chia dữ liệu người dùng ra 2 shard. Ba kỹ thuật còn thiếu để chấm là microservice, replication, sharding; T6 chỉ còn trang "Hệ thống", load test và chế độ chỉ đọc.

Kết quả cần có: tắt bản sao không ai thấy gì; tắt một shard chỉ User của shard đó nhận 503; tắt `places` chỉ việc cần tìm Place bị lỗi; thiếu biến môi trường thì mọi thứ chạy trên một database như hôm nay.

**Chốt trong buổi grill 2026-10-01 (ghi vào spec §2 ở Task 0):**

| # | Quyết định |
|---|---|
| S26 | Giữ `conn` trong mọi chữ ký; `conn` nghĩa là kết nối Trip. `places_client` nhận `conn` và chỉ dùng nó để đọc Place ở chế độ đơn giản. 306 test hiện có không sửa assert |
| S27 | `places` chết: `places_client.list_destinations` trả bản Destination đọc được gần nhất trong tiến trình → danh sách Trip, mở Trip, ghim vẫn chạy; lập lịch, Disruption → Proposal, khôi phục version báo 503 |
| S28 | `seed_users` chỉ tạo User; Trip mẫu sinh bằng luồng thật khi ghi kịch bản demo |
| S29 | Worker mở kết nối shard theo từng việc; shard chết → event `error`, không thử lại. Shard chết lúc khởi động không chặn `api` / `planner` |

**Goal:** Đọc Place đi qua một cửa `places_client` (trong tiến trình, bản sao, hoặc HTTP tới service `places`); Trip của User nằm ở shard `user_id % N`; cụm 15 container chạy đúng bảng hành vi §10 cho bản sao, shard và `places`.

**Architecture:** `app/places_client.py` là vết cắt duy nhất giữa dữ liệu Trip và dữ liệu chung: thiếu biến thì gọi `app/places.py` trên `conn` của người gọi, có `CATALOG_REPLICA_URL`/`SHARD_URLS` thì tự mở kết nối đọc (bản sao, chết thì node chính), có `PLACES_URL` thì gọi HTTP sang `app/places_service.py`. `db.shard_conn(user_id)` chọn shard; handler Trip dùng dependency `auth.get_shard`, worker mở kết nối shard cho từng việc. `schema.sql` tách thành `schema_catalog.sql` và `schema_shard.sql`.

**Tech Stack:** FastAPI, psycopg3, pgvector, httpx, Postgres 17 streaming replication (`pg_basebackup -R`), docker compose, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-scale-he-phan-tan-design.md` — đọc §2, §4, §8, §9, §10, §13. ADR-0008.

## Global Constraints

- Thiếu `PLACES_URL`, `CATALOG_REPLICA_URL`, `SHARD_URLS` → chạy trên một database như cũ. 306 test hiện có phải xanh, **không sửa assert**. Chỉ được sửa fixture `client` ở `tests/test_trips_api.py` và `tests/test_disruptions_api.py` (Task 4 nêu rõ từng dòng).
- **Không sửa logic** `rules.py`, `replan.py`, `followup.py`, `llm.py`, `places.py`, `gateway.py`, `jobs.py`.
- Không thêm dependency. Test dùng Postgres và Redis thật; không giả lập database.
- Ngoài phạm vi (T6): `GET /system/status`, trang "Hệ thống", load test, chế độ chỉ đọc khi `pg-catalog` chính chết (đăng nhập đọc bản sao), client tự nối lại.
- Thông báo hướng tới người dùng là tiếng Việt. Hai câu cố định:
  - `SHARD_DOWN = "Dữ liệu chuyến đi tạm không truy cập được, bạn thử lại sau nhé."`
  - `PLACES_DOWN = "Dịch vụ địa điểm tạm không truy cập được, bạn thử lại sau nhé."`
- Service `places` không được có `PLACES_URL` trong môi trường của nó.
- Lệnh test: `docker compose up -d db redis && cd server && uv run pytest` · `cd client && npm test && npm run build`.
- Commit message kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Kết nối bản sao chạy lệnh ghi.** `db.connect()` hiện chạy `CREATE EXTENSION IF NOT EXISTS vector` mỗi lần mở; trên hot standby lệnh này lỗi. Kết nối đọc bản sao không được ghi gì (Task 1, test dùng URL `default_transaction_read_only=on`).
2. **Hai User khác shard có Trip trùng id.** `trips.id` tự tăng theo từng shard; User A gọi `/trips/1` phải thấy Trip của A, không bao giờ của B (Task 4 có test).
3. **Việc của shard chết làm kẹt worker.** Worker gặp việc của User thuộc shard chết phải báo lỗi, `XACK`, rồi chạy tiếp việc của User shard kia (Task 5 có test).
4. **Shard chết đúng lúc `api` khởi động lại.** Không được làm `api` chết theo: User shard còn sống vẫn phải dùng được (Task 4 có test `init_schemas`).
5. **`places` trả 5xx thay vì mất kết nối** (ví dụ embedding lỗi). Người dùng phải nhận đúng câu `PLACES_DOWN`, stream SSE phải kết thúc, không treo (Task 2 có test).

## File Structure

| File | Trách nhiệm |
|---|---|
| `server/app/config.py` | `places_url`, `catalog_replica_url`, `shard_urls` |
| `server/app/db.py` | `_open`, `connect`, `catalog_read`, `shard_urls`, `shard_of`, `shard_conn`, `apply_schema(catalog, shard)`, `init_schemas`, `SHARD_DOWN` |
| `server/app/schema_catalog.sql`, `schema_shard.sql` (thay `schema.sql`) | Bảng chung / bảng theo User |
| `server/app/places_client.py` (mới) | Một cửa đọc Place + Destination; `call`, `PlacesDown`, `PLACES_DOWN` |
| `server/app/places_service.py` (mới) | App FastAPI của service `places` |
| `server/app/distance.py` | `prefetch` chọn `goong` (trong tiến trình) hay nhờ `places` |
| `server/app/auth.py` | Dependency `get_shard` |
| `server/app/trips.py`, `proposals.py`, `versions.py`, `agent.py`, `multi.py`, `main.py`, `worker.py` | Đổi import sang `places_client`; handler Trip dùng `get_shard`; `guarded` bắt `PlacesDown`; khởi động bằng `init_schemas` |
| `server/scripts/seed_users.py` (mới), `import_places.py`, `golden.py` | User mẫu; import chỉ áp schema chung |
| `docker-compose.cluster.yml`, `docker/initdb-catalog/01-replication.sh`, `docker/replica.sh`, `server/Dockerfile` | 4 Postgres + `places` |
| `server/tests/conftest.py` | Biến môi trường trống; fixture `shards` |
| `server/tests/test_places_client.py`, `test_places_service.py`, `test_shards.py`, `test_seed_users.py` (mới) | Test T5 |
| `docs/…` | spec (S26–S29, §8, §10), runbook, ROADMAP, CLAUDE.md, `.env.example` |

---

### Task 0: Nhánh, lưu plan, ghi quyết định vào spec

**Files:**
- Create: `docs/superpowers/plans/2026-10-01-scale-t5-places-ban-sao-shard.md` (chép nguyên file plan này)
- Modify: `docs/superpowers/specs/2026-10-01-scale-he-phan-tan-design.md`

- [ ] **Step 1: Nhánh mới từ `main`**

```bash
git checkout main && git pull && git checkout -b feat/51-places-shard
```

- [ ] **Step 2: Chép plan vào repo**

```bash
cp ~/.claude/plans/v-o-mode-superpowers-brainstorming-ti-n-polymorphic-dragonfly.md docs/superpowers/plans/2026-10-01-scale-t5-places-ban-sao-shard.md
```

- [ ] **Step 3: Sửa spec**

Thêm vào cuối bảng §2 (sau dòng S25):

```markdown
| S26 | Giữ `conn` trong chữ ký các hàm lập lịch; `conn` là kết nối Trip. `places_client` nhận `conn` và chỉ dùng nó để đọc Place ở chế độ đơn giản | 306 test hiện có không đổi; vết cắt nằm ở một module |
| S27 | `places` chết: `api` dùng bản Destination đọc được gần nhất trong tiến trình | Danh sách Trip và mở Trip cũ vẫn chạy; khớp ADR-0008 (Destination ưu tiên sẵn sàng) |
| S28 | `seed_users` chỉ tạo User | Trip mẫu sinh bằng luồng thật khi ghi kịch bản demo; không có đường ghi Trip thứ hai |
| S29 | Worker mở kết nối shard theo từng việc; shard chết → event `error`, không thử lại. Shard chết lúc khởi động không chặn `api` / `planner` | Một shard chết không được kéo theo User của shard kia |
```

Ở §8, đổi dòng `GET /places?ids=` thành `` `GET /places?ids=1&ids=2` ``.

Ở §10, thay dòng `places` của bảng "Node chết" bằng:

```markdown
| `places` | Lập lịch, Disruption → Proposal và khôi phục version báo lỗi; danh sách Trip, mở Trip, ghim vẫn chạy (Destination lấy bản đọc được gần nhất, S27); km quay về ước tính |
```

Ở §8, thay gạch đầu dòng "`places` chết: lập lịch và mở Trip trả lỗi rõ ràng; …" bằng: "`places` chết: việc cần tìm hoặc đọc Place trả lỗi rõ ràng (S27); `POST /distance` lỗi thì `make_leg` dùng chim bay × 1.3 như hiện nay."

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers
git commit -m "docs: plan T5 và quyết định S26–S29 trong spec scale (#51)"
```

---

### Task 1: `places_client` (vết cắt) và đọc bản sao có dự phòng

**Files:**
- Create: `server/app/places_client.py`, `server/tests/test_places_client.py`
- Modify: `server/app/config.py`, `server/app/db.py`, `server/tests/conftest.py`
- Modify (đổi import): `server/app/agent.py:11,225-229`, `server/app/multi.py:18`, `server/app/trips.py:20`, `server/app/proposals.py:11`, `server/app/versions.py:9`, `server/scripts/golden.py:19`

**Interfaces:**
- Produces: `settings.places_url`, `settings.catalog_replica_url`, `settings.shard_urls` (đều `str`, mặc định `""`)
- Produces: `db._open(url) -> Connection` (không đụng extension), `db.catalog_read() -> Connection`
- Produces: `places_client.search_places(conn, destination, query: str, embed_fn, kind=None, must_have_tags=(), exclude_tags=(), limit=8) -> list[Place]`; `similar_places(conn, place_id, kind, exclude_ids=(), exclude_tags=(), limit=20) -> list[Place]`; `get_places(conn, ids) -> dict[int, Place]`; `list_destinations(conn) -> list[dict]`
- Khác `app.places.search_places`: nhận **câu truy vấn + `embed_fn`**, không nhận vector (service `places` tự embed ở Task 2).

- [ ] **Step 1: Biến môi trường trống trong test**

`server/tests/conftest.py`, thêm sau dòng `os.environ["PLANNER_MODE"] = ""`:

```python
os.environ["PLACES_URL"] = ""  # test mặc định đọc Place trong tiến trình, một database
os.environ["CATALOG_REPLICA_URL"] = ""
os.environ["SHARD_URLS"] = ""
```

- [ ] **Step 2: Viết test (sẽ fail)**

`server/tests/test_places_client.py`:

```python
from app import places_client
from app.config import settings
from tests.conftest import TEST_URL
from tests.helpers import add_place, unit_vec

DEAD = "postgresql://travility:travility@127.0.0.1:1/travility"  # không ai nghe cổng 1
READ_ONLY = TEST_URL + "?options=-c%20default_transaction_read_only%3Don"  # giống hot standby: lệnh ghi lỗi


def embed(texts):
    return [unit_vec(1) for _ in texts]


def test_simple_mode_reads_through_callers_conn(conn):
    far = add_place(conn, name="Xa", vec=5)
    near = add_place(conn, name="Gần", vec=1, kind="cafe")
    assert [p.id for p in places_client.search_places(conn, "da-lat", "cafe yên tĩnh", embed)] == [near, far]
    assert [p.id for p in places_client.search_places(conn, "da-lat", "x", embed, kind="cafe")] == [near]
    assert places_client.get_places(conn, [near])[near].name == "Gần"
    assert [p.id for p in places_client.similar_places(conn, near, "tham-quan")] == [far]
    assert places_client.list_destinations(conn)[0]["slug"] == "da-lat"


def test_replica_is_read_and_callers_conn_ignored(conn, monkeypatch):
    """Có bản sao: không đụng node chính, không dùng conn của người gọi, không chạy lệnh ghi nào."""
    pid = add_place(conn, name="A")
    monkeypatch.setattr(settings, "catalog_replica_url", READ_ONLY)
    monkeypatch.setattr(settings, "database_url", DEAD)
    assert places_client.get_places(None, [pid])[pid].name == "A"
    assert [p.id for p in places_client.search_places(None, "da-lat", "gì đó", embed)] == [pid]
    assert places_client.list_destinations(None)[0]["slug"] == "da-lat"


def test_replica_down_falls_back_to_primary(conn, monkeypatch):
    pid = add_place(conn, name="A")
    monkeypatch.setattr(settings, "catalog_replica_url", DEAD)
    monkeypatch.setattr(settings, "database_url", TEST_URL)
    assert places_client.get_places(None, [pid])[pid].name == "A"


def test_shards_without_replica_read_catalog_primary(conn, monkeypatch):
    """Có SHARD_URLS thì conn của người gọi là kết nối shard (không có bảng places) → phải đọc database chung."""
    pid = add_place(conn, name="A")
    monkeypatch.setattr(settings, "shard_urls", "postgresql://x/0,postgresql://x/1")
    monkeypatch.setattr(settings, "database_url", TEST_URL)
    assert places_client.get_places(None, [pid])[pid].name == "A"
```

- [ ] **Step 3: Chạy, thấy fail**

Run: `cd server && uv run pytest tests/test_places_client.py -q`
Expected: FAIL `ImportError: cannot import name 'places_client'`

- [ ] **Step 4: `config.py`**

Thêm sau dòng `planner_mode: …`:

```python
    places_url: str = ""  # có → Place, Destination và km Goong đi qua service places (app/places_service.py)
    catalog_replica_url: str = ""  # có → đọc Place từ bản sao; bản sao chết thì đọc DATABASE_URL
    shard_urls: str = ""  # URL các shard, cách nhau dấu phẩy; có → Trip của User nằm ở shard user_id % N
```

- [ ] **Step 5: `db.py` — `_open` và `catalog_read`**

Thay hàm `connect` bằng khối sau (thêm `import logging` ở đầu file và `logger = logging.getLogger(__name__)` sau các import):

```python
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
```

- [ ] **Step 6: `places_client.py`**

```python
"""Một cửa cho mọi lần đọc Place / Destination (spec scale §8): code gọi không biết dữ liệu đến từ đâu.

`conn` là kết nối Trip của người gọi. Nó chỉ được dùng để đọc Place ở chế độ đơn giản (một database);
có CATALOG_REPLICA_URL hoặc SHARD_URLS thì module tự mở kết nối đọc database chung.
"""
from contextlib import contextmanager

from app import db, places
from app.config import settings
from app.domain import Place


@contextmanager
def _reader(conn):
    if settings.catalog_replica_url or settings.shard_urls:
        with db.catalog_read() as c:
            yield c
    else:
        yield conn


def search_places(conn, destination: str, query: str, embed_fn, kind: str | None = None,
                  must_have_tags=(), exclude_tags=(), limit: int = 8) -> list[Place]:
    vec = embed_fn([query])[0]
    with _reader(conn) as c:
        return places.search_places(c, destination, vec, kind, must_have_tags, exclude_tags, limit)


def similar_places(conn, place_id: int, kind: str, exclude_ids=(), exclude_tags=(), limit: int = 20) -> list[Place]:
    with _reader(conn) as c:
        return places.similar_places(c, place_id, kind, exclude_ids, exclude_tags, limit)


def get_places(conn, ids) -> dict[int, Place]:
    with _reader(conn) as c:
        return places.get_places(c, list(ids))


def list_destinations(conn) -> list[dict]:
    with _reader(conn) as c:
        return places.list_destinations(c)
```

- [ ] **Step 7: Đổi nơi gọi**

- `app/agent.py:11`: `from app.places_client import search_places`
- `app/agent.py` trong `run_search`, thay lời gọi:

```python
    found = search_places(
        conn, trip.destination, query, embed_fn,
        kind=args.get("kind") if args.get("kind") in KINDS else None,
        must_have_tags=[t for t in (args.get("must_have_tags") or []) if t in TAGS],
        exclude_tags=trip.avoided_tags)
```

- `app/multi.py:18`: `from app.places_client import get_places`
- `app/trips.py:20`: `from app.places_client import get_places, list_destinations`
- `app/proposals.py:11`: `from app.places_client import get_places, list_destinations, similar_places`
- `app/versions.py:9`: `from app.places_client import get_places, list_destinations`
- `scripts/golden.py:19`: `from app.places_client import list_destinations`

Kiểm không còn ai gọi thẳng `app.places` ngoài `places_client` (và sau Task 2 là `places_service`):

Run: `cd server && grep -rn "from app.places import\|from app import.*places" app scripts`
Expected: chỉ còn dòng trong `app/places_client.py`.

- [ ] **Step 8: Chạy toàn bộ test**

Run: `cd server && uv run pytest -q`
Expected: 310 passed (306 cũ + 4 mới).

- [ ] **Step 9: Commit**

```bash
git add server && git commit -m "feat(server): places_client làm một cửa đọc Place, đọc bản sao có dự phòng về node chính (#51)"
```

---

### Task 2: Service `places` qua HTTP

**Files:**
- Create: `server/app/places_service.py`, `server/tests/test_places_service.py`
- Modify: `server/app/places_client.py`, `server/app/trips.py` (`guarded`), `server/app/main.py`, `server/app/multi.py:22`

**Interfaces:**
- Consumes: `places_client.*`, `db.catalog_read` (Task 1)
- Produces: `places_client.call(method: str, path: str, **kw) -> Any` (JSON đã parse; lỗi → `PlacesDown`), `places_client.PlacesDown`, `places_client.PLACES_DOWN`, `places_client._http` (hook cho test), `places_client._dests`
- Produces: `places_service.app`, `places_service.get_read` (dependency, test override)
- Endpoint: `POST /search`, `POST /similar`, `GET /places?ids=1&ids=2`, `GET /destinations`, `GET /health`

- [ ] **Step 1: Viết test (sẽ fail)**

`server/tests/test_places_service.py`:

```python
import httpx
import pytest
from fastapi.testclient import TestClient

from app import llm, places_client, places_service, trips
from app.config import settings
from tests.helpers import add_place, unit_vec
from tests.test_trips_api import auth, client, events, happy, no_meal_rule, use_llm  # noqa: F401 (fixture)


def refuse(request):
    raise httpx.ConnectError("places không chạy", request=request)


def kill(monkeypatch):
    monkeypatch.setattr(places_client, "_http", httpx.Client(transport=httpx.MockTransport(refuse)))


def no_embed(texts):
    raise AssertionError("có PLACES_URL thì service places tự embed")


@pytest.fixture
def svc(conn, monkeypatch):
    """places_client gọi thẳng vào app của service qua TestClient: hợp đồng HTTP thật, không cần mạng."""
    places_service.app.dependency_overrides[places_service.get_read] = lambda: conn
    monkeypatch.setattr(llm, "embed", lambda texts: [unit_vec(1) for _ in texts])
    monkeypatch.setattr(settings, "places_url", "http://places")
    monkeypatch.setattr(places_client, "_http", TestClient(places_service.app))
    monkeypatch.setattr(places_client, "_dests", None)
    yield
    places_service.app.dependency_overrides.clear()


def test_client_reads_through_service(conn, svc):
    far = add_place(conn, name="Xa", vec=5, tags=["yen-tinh"])
    near = add_place(conn, name="Gần", vec=1, kind="cafe")
    found = places_client.search_places(None, "da-lat", "cafe", no_embed)
    assert [p.id for p in found] == [near, far] and found[0].name == "Gần"
    assert [p.id for p in places_client.search_places(None, "da-lat", "x", no_embed, kind="cafe")] == [near]
    assert [p.id for p in places_client.search_places(None, "da-lat", "x", no_embed, exclude_tags=["yen-tinh"])] == [near]
    assert [p.id for p in places_client.similar_places(None, near, "tham-quan")] == [far]
    assert places_client.similar_places(None, near, "tham-quan", exclude_ids={far}) == []
    assert set(places_client.get_places(None, [near, far])) == {near, far}
    assert places_client.get_places(None, []) == {}
    assert places_client.list_destinations(None)[0]["slug"] == "da-lat"


def test_places_down_raises(svc, monkeypatch):
    kill(monkeypatch)
    with pytest.raises(places_client.PlacesDown):
        places_client.get_places(None, [1])


def test_service_5xx_is_places_down(svc, monkeypatch):
    """Service trả 5xx (vd embedding lỗi) cũng là 'places không dùng được', không phải lỗi lạ."""
    def boom(texts):
        raise RuntimeError("embedding hỏng")
    monkeypatch.setattr(llm, "embed", boom)
    monkeypatch.setattr(places_client, "_http", TestClient(places_service.app, raise_server_exceptions=False))
    with pytest.raises(places_client.PlacesDown):
        places_client.search_places(None, "da-lat", "x", no_embed)


def test_destinations_survive_places_down(conn, svc, monkeypatch):
    add_place(conn)
    assert places_client.list_destinations(None)[0]["slug"] == "da-lat"
    kill(monkeypatch)
    assert places_client.list_destinations(None)[0]["slug"] == "da-lat"


def test_destinations_never_read_then_places_down_raises(svc, monkeypatch):
    kill(monkeypatch)
    with pytest.raises(places_client.PlacesDown):
        places_client.list_destinations(None)


def test_guarded_reports_places_down():
    def job():
        yield trips.sse({"type": "thinking", "text": "…"})
        raise places_client.PlacesDown("x")
    out = list(trips.guarded(job()))
    assert out[-1] == trips.sse({"type": "error", "message": places_client.PLACES_DOWN})


def test_plan_through_service_then_places_dies(conn, client, svc, monkeypatch):
    """Lập lịch qua service places; places chết → Trip cũ vẫn mở được, việc cần Place trả 503 (spec S27)."""
    use_llm(monkeypatch, happy(add_place(conn, kind="cafe")))
    h = auth(client)
    evs = events(client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h))
    assert evs[-1]["type"] == "itinerary"
    tid = evs[-1]["trip_id"]
    kill(monkeypatch)
    assert client.get(f"/trips/{tid}", headers=h).json()["version"] == 1
    assert client.get("/trips", headers=h).json()[0]["destination_name"] == "da-lat"
    r = client.post(f"/trips/{tid}/restore/1", headers=h)
    assert r.status_code == 503 and r.json()["detail"] == places_client.PLACES_DOWN
    use_llm(monkeypatch, happy(1))  # lượt mới: đọc yêu cầu xong, tới lượt tìm Place thì places đã chết
    evs = events(client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h))
    assert evs[-1] == {"type": "error", "message": places_client.PLACES_DOWN}
```

- [ ] **Step 2: Chạy, thấy fail**

Run: `cd server && uv run pytest tests/test_places_service.py -q`
Expected: FAIL `ImportError: cannot import name 'places_service'`

- [ ] **Step 3: `places_service.py`**

```python
"""Service places: tìm Place bằng vector, Place tương tự, Place theo id, Destination (spec scale §8).

Chạy: uvicorn app.places_service:app. Đọc bản sao của database chung; bản sao chết thì đọc node chính.
Chỉ nghe trong mạng nội bộ của cụm nên không kiểm JWT. Không được đặt PLACES_URL cho service này.
"""
from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel

from app import db, llm, places
from app.domain import Place

app = FastAPI(title="Travility places")


def get_read():
    conn = db.catalog_read()
    try:
        yield conn
    finally:
        conn.close()


class SearchIn(BaseModel):
    destination: str
    query: str
    kind: str | None = None
    must_have_tags: list[str] = []
    exclude_tags: list[str] = []
    limit: int = 8


class SimilarIn(BaseModel):
    place_id: int
    kind: str
    exclude_ids: list[int] = []
    exclude_tags: list[str] = []
    limit: int = 20


@app.post("/search")
def search(body: SearchIn, conn=Depends(get_read)) -> list[Place]:
    vec = llm.embed([body.query])[0]
    return places.search_places(conn, body.destination, vec, body.kind, body.must_have_tags, body.exclude_tags,
                                body.limit)


@app.post("/similar")
def similar(body: SimilarIn, conn=Depends(get_read)) -> list[Place]:
    return places.similar_places(conn, body.place_id, body.kind, body.exclude_ids, body.exclude_tags, body.limit)


@app.get("/places")
def by_ids(ids: list[int] = Query(default=[]), conn=Depends(get_read)) -> list[Place]:
    return list(places.get_places(conn, ids).values())


@app.get("/destinations")
def destinations(conn=Depends(get_read)) -> list[dict]:
    return places.list_destinations(conn)


@app.get("/health")
def health():
    return {"ok": True}
```

- [ ] **Step 4: `places_client.py` — nhánh HTTP**

Thêm `import httpx` và, sau các import:

```python
PLACES_DOWN = "Dịch vụ địa điểm tạm không truy cập được, bạn thử lại sau nhé."
TIMEOUT_S = 15  # /search có một lượt embedding qua llm-gateway

_http: httpx.Client | None = None  # test thay bằng TestClient của places_service
_dests: list[dict] | None = None  # Destination đọc được gần nhất; dùng khi places chết (spec S27)


class PlacesDown(Exception):
    """Service places không trả lời hoặc trả lỗi."""


def call(method: str, path: str, **kw):
    try:
        r = (_http or httpx).request(method, settings.places_url + path, timeout=TIMEOUT_S, **kw)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise PlacesDown(str(e)) from e
```

Thay bốn hàm công khai bằng:

```python
def search_places(conn, destination: str, query: str, embed_fn, kind: str | None = None,
                  must_have_tags=(), exclude_tags=(), limit: int = 8) -> list[Place]:
    if settings.places_url:  # service tự embed qua llm-gateway; embed_fn của người gọi không dùng
        rows = call("POST", "/search", json={
            "destination": destination, "query": query, "kind": kind, "must_have_tags": list(must_have_tags),
            "exclude_tags": list(exclude_tags), "limit": limit})
        return [Place.model_validate(r) for r in rows]
    vec = embed_fn([query])[0]
    with _reader(conn) as c:
        return places.search_places(c, destination, vec, kind, must_have_tags, exclude_tags, limit)


def similar_places(conn, place_id: int, kind: str, exclude_ids=(), exclude_tags=(), limit: int = 20) -> list[Place]:
    if settings.places_url:
        rows = call("POST", "/similar", json={
            "place_id": place_id, "kind": kind, "exclude_ids": list(exclude_ids), "exclude_tags": list(exclude_tags),
            "limit": limit})
        return [Place.model_validate(r) for r in rows]
    with _reader(conn) as c:
        return places.similar_places(c, place_id, kind, exclude_ids, exclude_tags, limit)


def get_places(conn, ids) -> dict[int, Place]:
    ids = list(ids)
    if settings.places_url:
        rows = call("GET", "/places", params={"ids": ids}) if ids else []
        return {r["id"]: Place.model_validate(r) for r in rows}
    with _reader(conn) as c:
        return places.get_places(c, ids)


def list_destinations(conn) -> list[dict]:
    global _dests
    if not settings.places_url:
        with _reader(conn) as c:
            return places.list_destinations(c)
    try:
        _dests = call("GET", "/destinations")
    except PlacesDown:
        if _dests is None:
            raise
    return _dests
```

- [ ] **Step 5: `trips.guarded` bắt `PlacesDown`**

`app/trips.py`: sửa import thành `from app.places_client import PLACES_DOWN, PlacesDown, get_places, list_destinations`, rồi thêm nhánh **trước** `except Exception`:

```python
    except PlacesDown:
        logger.exception("Service places không trả lời")
        yield sse({"type": "error", "message": PLACES_DOWN})
```

- [ ] **Step 6: `main.py` — 503 cho handler thường, nạp sẵn Destination**

Thêm import `from fastapi.responses import JSONResponse` và `from app.places_client import PLACES_DOWN, PlacesDown, list_destinations`. Trong `lifespan`, sau khi áp schema và trước `yield`:

```python
    if settings.places_url:  # nạp sẵn Destination: places chết sau đó thì danh sách và mở Trip vẫn chạy (spec S27)
        try:
            list_destinations(None)
        except PlacesDown:
            pass
```

Sau các `include_router`:

```python
@app.exception_handler(PlacesDown)
def places_down(_request, _exc):
    return JSONResponse({"detail": PLACES_DOWN}, status_code=503)
```

- [ ] **Step 7: `multi.agent_conn` không mở database khi có `PLACES_URL`**

`app/multi.py`: thêm `from contextlib import nullcontext`, thay dòng `agent_conn = connect …` bằng:

```python
def agent_conn():
    """Mỗi chuyên gia một kết nối riêng để đọc Place; có PLACES_URL thì không cần database. Test thay bằng kết nối test."""
    return nullcontext(None) if settings.places_url else connect()
```

- [ ] **Step 8: Chạy test**

Run: `cd server && uv run pytest -q`
Expected: 317 passed.

- [ ] **Step 9: Commit**

```bash
git add server && git commit -m "feat(server): service places qua HTTP; places chết thì Trip cũ vẫn mở được (#51)"
```

---

### Task 3: Km Goong đi qua `places`

**Files:**
- Modify: `server/app/distance.py`, `server/app/places_service.py`
- Test: `server/tests/test_distance.py`, `server/tests/test_places_service.py`

**Interfaces:**
- Consumes: `places_client.call`, `places_client.PlacesDown` (Task 2)
- Produces: `distance.goong(origins, destinations, mode, client=None)` (thân `prefetch` cũ, nguyên văn); `distance.prefetch(origins, destinations, mode, client=None)` giữ chữ ký, chọn đường
- Endpoint: `POST /distance` nhận `{"origins": [{"lat","lon"}], "destinations": [{"lat","lon"}], "mode": str}`, trả `{"rows": [[[km, phút] | null, …], …]}`

- [ ] **Step 1: Viết test (sẽ fail)**

Thêm vào cuối `server/tests/test_distance.py` (thêm `import json` và `from app import places_client` ở đầu file):

```python
def via_places(monkeypatch, handler):
    monkeypatch.setattr(settings, "places_url", "http://places")
    monkeypatch.setattr(places_client, "_http", httpx.Client(transport=httpx.MockTransport(handler)))


def test_prefetch_asks_places_service(monkeypatch):
    sent = []

    def places(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"rows": [[[1.5, 4], None]]})
    via_places(monkeypatch, places)
    distance.prefetch([A], [B, C], "xe-may")
    assert distance.lookup(A, B, "xe-may") == (1.5, 4)
    assert distance.lookup(A, C, "xe-may") is None
    pt = lambda p: {"lat": p.lat, "lon": p.lon}  # noqa: E731
    assert sent == [{"origins": [pt(A)], "destinations": [pt(B), pt(C)], "mode": "xe-may"}]


def test_places_down_cools_down(monkeypatch):
    calls = []

    def refuse(request):
        calls.append(1)
        raise httpx.ConnectError("x", request=request)
    via_places(monkeypatch, refuse)
    distance.prefetch([A], [B], "xe-may")
    distance.prefetch([A], [B], "xe-may")
    assert distance.lookup(A, B, "xe-may") is None and len(calls) == 1
```

Thêm vào `server/tests/test_places_service.py` (thêm `distance` vào dòng `from app import …`):

```python
def test_distance_endpoint_returns_matrix(monkeypatch):
    def goong(origins, destinations, mode, client=None):
        distance._cache[distance._key(origins[0], destinations[0], "bike")] = (1.5, 4)
    monkeypatch.setattr(distance, "goong", goong)
    r = TestClient(places_service.app).post("/distance", json={
        "origins": [{"lat": 1, "lon": 2}], "destinations": [{"lat": 3, "lon": 4}, {"lat": 5, "lon": 6}],
        "mode": "xe-may"})
    assert r.json() == {"rows": [[[1.5, 4], None]]}
```

- [ ] **Step 2: Chạy, thấy fail**

Run: `cd server && uv run pytest tests/test_distance.py tests/test_places_service.py -q`
Expected: 3 FAILED (`lookup` trả `None`; `distance` không có `goong`; `/distance` 404).

- [ ] **Step 3: `distance.py`**

Thêm `places_client` vào import: `from app import kv, places_client`. Đổi tên hàm `prefetch` hiện có thành `goong` (thân giữ nguyên từng dòng), rồi thêm phía trên nó:

```python
def prefetch(origins: list, destinations: list, mode: str, client: httpx.Client | None = None) -> None:
    """Lấy km/phút thật cho mọi cặp origins × destinations vào cache của lookup().

    Có PLACES_URL → nhờ service places gọi Goong (spec scale §8); không thì gọi Goong ngay trong tiến trình.
    """
    if settings.places_url:
        _via_places(origins, destinations, mode)
    else:
        goong(origins, destinations, mode, client)


def _via_places(origins: list, destinations: list, mode: str) -> None:
    global _down_until
    if time.monotonic() < _down_until or all(lookup(a, b, mode) is not None for a in origins for b in destinations):
        return
    vehicle = VEHICLE.get(mode, "bike")
    try:
        rows = places_client.call("POST", "/distance", json={
            "origins": [{"lat": p.lat, "lon": p.lon} for p in origins],
            "destinations": [{"lat": p.lat, "lon": p.lon} for p in destinations], "mode": mode})["rows"]
        for a, row in zip(origins, rows):
            for b, v in zip(destinations, row):
                if v:
                    _cache[_key(a, b, vehicle)] = (v[0], v[1])
    except (places_client.PlacesDown, KeyError, TypeError, IndexError):
        _down_until = time.monotonic() + COOLDOWN_S  # places chết: make_leg dùng chim bay × 1.3 như khi Goong lỗi
```

Sửa dòng đầu docstring của `goong` thành: `"""Một request Goong Distance Matrix cho mọi cặp origins × destinations, ghi vào cache cho lookup()."""` (đã đúng, giữ nguyên).

- [ ] **Step 4: `places_service.py` — `POST /distance`**

Thêm `distance` vào import (`from app import db, distance, llm, places`) và sửa docstring module thành "…, Destination, km Goong". Thêm trước `/health`:

```python
class Pt(BaseModel):
    lat: float
    lon: float


class DistanceIn(BaseModel):
    origins: list[Pt]
    destinations: list[Pt]
    mode: str


@app.post("/distance")
def distance_matrix(body: DistanceIn) -> dict:
    """Gọi thẳng distance.goong (không qua prefetch) để service không bao giờ tự gọi lại chính nó."""
    distance.goong(body.origins, body.destinations, body.mode)
    return {"rows": [[distance.lookup(a, b, body.mode) for b in body.destinations] for a in body.origins]}
```

- [ ] **Step 5: Chạy test**

Run: `cd server && uv run pytest -q`
Expected: 320 passed.

- [ ] **Step 6: Commit**

```bash
git add server && git commit -m "feat(server): km Goong đi qua service places khi có PLACES_URL (#51)"
```

---

### Task 4: Tách schema và định tuyến shard ở `api`

**Files:**
- Create: `server/app/schema_shard.sql`, `server/tests/test_shards.py`
- Rename: `server/app/schema.sql` → `server/app/schema_catalog.sql`
- Modify: `server/app/db.py`, `server/app/auth.py`, `server/app/trips.py`, `server/app/proposals.py`, `server/app/versions.py`, `server/app/main.py`, `server/scripts/import_places.py`
- Modify (fixture): `server/tests/conftest.py`, `server/tests/test_trips_api.py:28-34`, `server/tests/test_disruptions_api.py:17-21`

**Interfaces:**
- Consumes: `db._open`, `db.connect` (Task 1)
- Produces: `db.SHARD_DOWN`, `db.shard_urls() -> list[str]`, `db.shard_of(user_id) -> int`, `db.shard_conn(user_id) -> Connection`, `db.apply_schema(conn, catalog=True, shard=True)`, `db.init_schemas()`
- Produces: `auth.get_shard` (dependency, phụ thuộc `current_user`)
- Produces: `trips.stream_conn(user_id)` (trước đây không tham số)
- Produces: fixture `shards` trong `conftest.py` → `list[str]` hai URL shard test; đặt `settings.database_url = TEST_URL`

- [ ] **Step 1: Fixture `shards`**

`server/tests/conftest.py`: đổi import thành `from app import db, distance, kv`, thêm cuối file:

```python
@pytest.fixture
def shards(conn, monkeypatch):
    """Hai database shard thật, trống; DATABASE_URL trỏ database test (đóng vai pg-catalog), SHARD_URLS trỏ hai shard."""
    urls = []
    for i in range(2):
        name = f"travility_test_s{i}"
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            conn.execute(f"CREATE DATABASE {name}")
        url = f"{TEST_URL.rsplit('/', 1)[0]}/{name}"
        with db._open(url) as c:
            c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            apply_schema(c, catalog=False)
        urls.append(url)
    monkeypatch.setattr(settings, "database_url", TEST_URL)
    monkeypatch.setattr(settings, "shard_urls", ",".join(urls))
    return urls
```

- [ ] **Step 2: Viết test (sẽ fail)**

`server/tests/test_shards.py`:

```python
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app import db, forecast, llm, rules
from app.config import settings
from app.main import app
from tests.conftest import TEST_URL
from tests.helpers import add_place, unit_vec
from tests.test_trips_api import auth, events, happy, use_llm

DEAD = "postgresql://travility:travility@127.0.0.1:1/travility"
SPEC = {"destination": "da-lat", "days": 1, "budget": 2_000_000}


@pytest.fixture
def api(shards):
    return TestClient(app)  # không override dependency nào: định tuyến thật


def user(api, email):
    h = auth(api, email)
    return h, api.get("/auth/me", headers=h).json()["id"]


def add_trip(uid, spec=SPEC):
    with db.shard_conn(uid) as c:
        return c.execute("INSERT INTO trips(user_id, spec) VALUES (%s, %s) RETURNING id",
                         (uid, Jsonb(spec))).fetchone()["id"]


def count(url, table="trips"):
    with db._open(url) as c:
        return c.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]


def fake_planning(conn, monkeypatch):
    monkeypatch.setattr(rules, "MEALS", ())
    monkeypatch.setattr(llm, "embed", lambda texts: [unit_vec(0) for _ in texts])
    monkeypatch.setattr(forecast, "get_rain_chance", lambda *a, **k: None)
    use_llm(monkeypatch, happy(add_place(conn, kind="cafe")))


def test_shard_of_and_url_parsing(shards, monkeypatch):
    assert [db.shard_of(i) for i in (1, 2, 3, 4)] == [1, 0, 1, 0]
    monkeypatch.setattr(settings, "shard_urls", " a , b ,")
    assert db.shard_urls() == ["a", "b"]
    monkeypatch.setattr(settings, "shard_urls", "")
    assert db.shard_urls() == [] and db.shard_of(7) == 0


def test_trips_live_on_the_users_shard(conn, api, shards):
    add_place(conn)
    (ha, a), (hb, b) = user(api, "a@example.com"), user(api, "b@example.com")
    assert db.shard_of(a) != db.shard_of(b)
    add_trip(a), add_trip(b), add_trip(b)
    assert count(shards[db.shard_of(a)]) == 1 and count(shards[db.shard_of(b)]) == 2
    assert count(TEST_URL) == 0
    assert len(api.get("/trips", headers=ha).json()) == 1
    assert len(api.get("/trips", headers=hb).json()) == 2


def test_same_trip_id_on_two_shards_never_crosses(conn, api, shards):
    """id Trip tự tăng theo từng shard nên trùng nhau; shard chọn theo User trước rồi mới tra id (spec §9.1)."""
    add_place(conn)
    (ha, a), (hb, b) = user(api, "a@example.com"), user(api, "b@example.com")
    ta, tb, tb2 = add_trip(a), add_trip(b, {**SPEC, "days": 3}), add_trip(b)
    assert ta == tb == 1
    assert api.get(f"/trips/{ta}", headers=ha).json()["trip"]["days"] == 1
    assert api.get(f"/trips/{tb}", headers=hb).json()["trip"]["days"] == 3
    assert api.get(f"/trips/{tb2}", headers=ha).status_code == 404


def test_dead_shard_only_blocks_its_users(conn, api, shards, monkeypatch):
    add_place(conn)
    (ha, a), (hb, b) = user(api, "a@example.com"), user(api, "b@example.com")
    add_trip(a)
    urls = list(shards)
    urls[db.shard_of(b)] = DEAD
    monkeypatch.setattr(settings, "shard_urls", ",".join(urls))
    r = api.get("/trips", headers=hb)
    assert r.status_code == 503 and r.json()["detail"] == db.SHARD_DOWN
    assert api.post("/trips", json={"message": "Đà Lạt 1 ngày"}, headers=hb).status_code == 503
    assert len(api.get("/trips", headers=ha).json()) == 1
    assert api.post("/auth/login", json={"email": "b@example.com", "password": "matkhau123"}).status_code == 200


def test_planning_writes_to_the_users_shard(conn, api, shards, monkeypatch):
    fake_planning(conn, monkeypatch)
    h, uid = user(api, "a@example.com")
    evs = events(api.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h))
    assert evs[-1]["type"] == "itinerary"
    mine, other = shards[db.shard_of(uid)], shards[1 - db.shard_of(uid)]
    assert count(mine) == 1 and count(mine, "itineraries") == 1 and count(mine, "messages") > 0
    assert count(other) == 0 and count(TEST_URL) == 0
    assert api.get(f"/trips/{evs[-1]['trip_id']}", headers=h).json()["version"] == 1


def test_trip_needs_no_user_row(conn):
    """Chế độ đơn giản cũng bỏ khoá ngoại trips.user_id → users: một schema cho cả hai chế độ (spec §9.1)."""
    conn.execute("INSERT INTO trips(user_id, spec) VALUES (999, '{}')")


def test_dead_shard_does_not_block_startup(conn, shards, monkeypatch):
    with db._open(shards[0]) as c:
        c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    monkeypatch.setattr(settings, "shard_urls", f"{shards[0]},{DEAD}")
    db.init_schemas()
    assert count(shards[0]) == 0
```

- [ ] **Step 3: Chạy, thấy fail**

Run: `cd server && uv run pytest tests/test_shards.py -q`
Expected: FAIL ở fixture (`apply_schema() got an unexpected keyword argument 'catalog'`).

- [ ] **Step 4: Tách schema**

```bash
cd server && git mv app/schema.sql app/schema_catalog.sql
```

`app/schema_catalog.sql`: chỉ giữ `CREATE EXTENSION`, `users`, `destinations` (+ `ALTER … hubs`), `places`. Cắt phần còn lại (từ `CREATE TABLE IF NOT EXISTS trips` tới hết) sang `app/schema_shard.sql`, và sửa định nghĩa `trips`:

```sql
-- Bảng theo User: nằm ở shard user_id % N khi có SHARD_URLS, không thì chung database với schema_catalog.sql.
CREATE TABLE IF NOT EXISTS trips (
  id serial PRIMARY KEY,
  -- users nằm ở database chung nên không có khoá ngoại; user_id luôn lấy từ JWT đã kiểm (spec scale §9.1)
  user_id integer NOT NULL,
  spec jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE trips DROP CONSTRAINT IF EXISTS trips_user_id_fkey;  -- database tạo trước khi tách shard
```

Các dòng `ALTER TABLE trips ADD COLUMN …`, `itineraries`, `proposals`, `messages`, index giữ nguyên văn và nguyên thứ tự.

- [ ] **Step 5: `db.py`**

Thay hằng `SCHEMA` và hàm `apply_schema`, thêm phần shard:

```python
CATALOG_SCHEMA = Path(__file__).with_name("schema_catalog.sql")  # users, destinations, places
SHARD_SCHEMA = Path(__file__).with_name("schema_shard.sql")  # trips, itineraries, proposals, messages
SHARD_DOWN = "Dữ liệu chuyến đi tạm không truy cập được, bạn thử lại sau nhé."


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

    Một shard chết không chặn khởi động: User của các shard còn sống vẫn phải dùng được (spec scale §10).
    """
    urls = shard_urls()
    with connect() as conn:
        apply_schema(conn, shard=not urls)
    for i, url in enumerate(urls):
        try:
            with _open(url) as conn:
                apply_schema(conn, catalog=False)
        except psycopg.OperationalError:
            logger.warning("shard %d không kết nối được lúc khởi động", i)
```

- [ ] **Step 6: `auth.get_shard`**

`app/auth.py`: đổi import thành `from app.db import SHARD_DOWN, get_conn, shard_conn`, thêm sau `current_user`:

```python
def get_shard(user_id: int = Depends(current_user)):
    """Kết nối tới shard của User đang đăng nhập; shard chết → 503 chỉ cho User của shard đó (spec scale §10)."""
    try:
        conn = shard_conn(user_id)
    except psycopg.OperationalError:
        raise HTTPException(503, SHARD_DOWN) from None
    try:
        yield conn
    finally:
        conn.close()
```

- [ ] **Step 7: Handler Trip dùng `get_shard`**

- `app/trips.py`: import `from app.auth import current_user, get_shard` và `from app.db import get_conn, shard_conn`. Đổi `stream_conn = connect  # …` thành:

```python
stream_conn = shard_conn  # SSE chạy sau khi handler trả về → tự mở kết nối riêng tới shard của User; test thay bằng kết nối test
```

  Trong `_stream`: `with stream_conn(user_id) as conn:`.
  Đổi `conn=Depends(get_conn)` → `conn=Depends(get_shard)` ở `create_trip`, `plan_trip`, `replan_trip`, `list_trips`, `get_trip`. **`destinations` giữ `get_conn`** (không có User; T6 xử lý khi `pg-catalog` chết).
  Thay thân `list_trips` (truy vấn nối bảng người dùng với bảng chung phải tách làm hai, spec §9.1):

```python
@router.get("/trips")
def list_trips(user_id: int = Depends(current_user), conn=Depends(get_shard)):
    rows = conn.execute("SELECT id, spec, created_at FROM trips WHERE user_id = %s ORDER BY id DESC",
                        (user_id,)).fetchall()
    names = {d["slug"]: d["name"] for d in list_destinations(conn)}
    return [{**r, "destination_name": names.get(r["spec"].get("destination"))} for r in rows]
```

- `app/proposals.py`: `from app.auth import current_user, get_shard`, bỏ `from app.db import get_conn`; hai handler đổi sang `Depends(get_shard)`.
- `app/versions.py`: tương tự cho `set_pin`, `get_messages`, `restore`.
- `app/main.py`: `from app.db import init_schemas`; trong `lifespan` thay `with connect() as conn: apply_schema(conn)` bằng `init_schemas()`.
- `scripts/import_places.py`: `apply_schema(conn, shard=False)` (import chỉ cần bảng chung; không tạo bảng Trip trống trên `pg-catalog`).

- [ ] **Step 8: Sửa hai fixture `client` (không đụng assert)**

`tests/test_trips_api.py`: thêm `from app.auth import get_shard`, và trong fixture `client`:

```python
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_shard] = lambda: conn
    monkeypatch.setattr(trips, "stream_conn", lambda *_: nullcontext(conn))
```

`tests/test_disruptions_api.py`: thêm `from app.auth import get_shard`, và trong fixture `client` thêm dòng `app.dependency_overrides[get_shard] = lambda: conn`.

Kiểm không còn chỗ override nào bị sót:

Run: `cd server && grep -rn "dependency_overrides\[" tests`
Expected: mọi file có handler Trip (`test_trips_api`, `test_disruptions_api`) đều override cả `get_conn` lẫn `get_shard`; `test_auth` chỉ cần `get_conn`.

- [ ] **Step 9: Chạy toàn bộ test**

Run: `cd server && uv run pytest -q`
Expected: 327 passed.

- [ ] **Step 10: Commit**

```bash
git add server && git commit -m "feat(server): tách schema chung / Trip, định tuyến shard theo user_id ở api; shard chết → 503 cho đúng User (#51)"
```

---

### Task 5: Worker chạy việc trên shard của User

**Files:**
- Modify: `server/app/worker.py`
- Test: `server/tests/test_shards.py`

**Interfaces:**
- Consumes: `db.shard_urls`, `db.shard_conn`, `db.SHARD_DOWN`, `db.init_schemas` (Task 4)
- Produces: `worker.run_job(conn, …)` và `worker.step(conn, …)` giữ chữ ký; `conn` được phép là `None` khi có `SHARD_URLS`

- [ ] **Step 1: Viết test (sẽ fail)**

Thêm vào `server/tests/test_shards.py` (thêm `jobs, worker` vào `from app import …` và `from tests.test_worker import published, types`):

```python
def enqueue(uid):
    return jobs.enqueue("message", uid, {"message": "Đà Lạt 1 ngày 2 triệu", "trip_id": None})


def test_worker_runs_job_on_the_users_shard(conn, shards, rds, monkeypatch):
    fake_planning(conn, monkeypatch)
    worker.ensure_group(rds)
    job = enqueue(3)
    assert worker.step(None, rds, "w1") is True
    assert types(rds, job)[-2:] == ["itinerary", "end"]
    assert count(shards[1]) == 1 and count(shards[0]) == 0 and count(TEST_URL) == 0


def test_dead_shard_fails_its_job_and_worker_moves_on(conn, shards, rds, monkeypatch):
    fake_planning(conn, monkeypatch)
    worker.ensure_group(rds)
    monkeypatch.setattr(settings, "shard_urls", f"{shards[0]},{DEAD}")
    dead, alive = enqueue(3), enqueue(2)
    worker.step(None, rds, "w1")
    worker.step(None, rds, "w1")
    assert published(rds, dead) == [{"type": "error", "message": db.SHARD_DOWN}, "end"]
    assert types(rds, alive)[-2:] == ["itinerary", "end"]
    assert rds.xpending_range("jobs", "planners", "-", "+", 10) == []
```

- [ ] **Step 2: Chạy, thấy fail**

Run: `cd server && uv run pytest tests/test_shards.py -q -k worker`
Expected: 2 FAILED (`AttributeError: 'NoneType' object has no attribute 'transaction'`).

- [ ] **Step 3: `worker.py`**

Import: thêm `import psycopg`, đổi `from app.db import apply_schema, connect` thành `from app.db import SHARD_DOWN, connect, init_schemas, shard_conn, shard_urls`.

Trong `run_job`, sửa dòng đầu docstring thành:

```python
    """Chạy một việc trong một transaction: worker chết giữa chừng → Postgres rollback, lần chạy lại bắt đầu sạch.

    `conn` là kết nối sẵn của worker ở chế độ một database. Có SHARD_URLS thì mỗi việc tự mở kết nối tới shard
    của User (conn có thể là None); shard chết → event error, không thử lại (spec scale S29).
    Event cuối chỉ phát sau khi commit, để client không bao giờ thấy Itinerary chưa được lưu.
    """
```

Thay khối từ `stop = threading.Event()` tới hết hàm bằng:

```python
    own = None
    if shard_urls():
        try:
            own = shard_conn(int(f["user_id"]))
        except psycopg.OperationalError:
            return fail(SHARD_DOWN)
    job_conn = own or conn
    stop = threading.Event()
    threading.Thread(target=_beat, args=(c, msg_id, me, stop), daemon=True).start()
    try:
        held = None
        with job_conn.transaction():
            for ev in trips.guarded(trips.JOBS[f["kind"]](job_conn, int(f["user_id"]), **json.loads(f["params"]))):
                if held is not None:
                    jobs.publish(job_id, held)
                held = ev
        jobs.complete(job_id, held)
        c.xack(jobs.STREAM, jobs.GROUP, msg_id)
        logger.info("xong việc %s (%s)", job_id, f["kind"])
    finally:
        stop.set()
        if own is not None:
            own.close()
```

Trong `main`: thay `with connect() as conn: apply_schema(conn)` bằng `init_schemas()`, và thay `conn = conn or connect()` bằng:

```python
            if conn is None and not shard_urls():  # có shard thì mỗi việc tự mở kết nối (run_job)
                conn = connect()
```

- [ ] **Step 4: Chạy toàn bộ test**

Run: `cd server && uv run pytest -q`
Expected: 329 passed.

- [ ] **Step 5: Commit**

```bash
git add server && git commit -m "feat(server): planner chạy mỗi việc trên shard của User; shard chết không kẹt worker (#51)"
```

---

### Task 6: `seed_users`

**Files:**
- Create: `server/scripts/seed_users.py`, `server/tests/test_seed_users.py`
- Modify: `server/Dockerfile`

**Interfaces:**
- Consumes: `db.connect`, `db.shard_of`, `db.shard_urls` (Task 4)
- Produces: `seed_users.seed(conn) -> list[tuple[str, int, int]]` (email, user_id, shard); `seed_users.PASSWORD`

- [ ] **Step 1: Viết test (sẽ fail)**

`server/tests/test_seed_users.py`:

```python
from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app
from scripts.seed_users import PASSWORD, seed


def test_seed_covers_every_shard_and_is_idempotent(conn, shards):
    conn.execute("INSERT INTO users(email, password_hash) VALUES ('x@example.com', 'x')")  # lệch id: không dựa vào id 1, 2
    first = seed(conn)
    assert [e for e, *_ in first] == ["demo1@travility.vn", "demo2@travility.vn"]
    assert {s for *_, s in first} == {0, 1}
    assert seed(conn) == first
    assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 3


def test_seeded_user_can_log_in_in_simple_mode(conn):
    assert len(seed(conn)) == 2
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        r = TestClient(app).post("/auth/login", json={"email": "demo1@travility.vn", "password": PASSWORD})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
```

- [ ] **Step 2: Chạy, thấy fail**

Run: `cd server && uv run pytest tests/test_seed_users.py -q`
Expected: FAIL `ModuleNotFoundError: No module named 'scripts.seed_users'`

- [ ] **Step 3: `scripts/seed_users.py`**

```python
"""Tạo User mẫu sao cho shard nào cũng có người (spec scale §9.3). Chạy lại không tạo trùng.

Trong cụm: docker compose -f docker-compose.cluster.yml exec api uv run --no-dev python -m scripts.seed_users
"""
import bcrypt

from app.db import connect, shard_of, shard_urls

PASSWORD = "travility-demo"
MAX_USERS = 10


def seed(conn) -> list[tuple[str, int, int]]:
    """Tạo demo1, demo2, … tới khi có ít nhất 2 User và đủ mặt mọi shard; trả [(email, user_id, shard)]."""
    need, out = max(len(shard_urls()), 1), []
    pw = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    for i in range(1, MAX_USERS + 1):
        email = f"demo{i}@travility.vn"
        conn.execute("INSERT INTO users(email, password_hash) VALUES (%s, %s) ON CONFLICT (email) DO NOTHING",
                     (email, pw))
        uid = conn.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()["id"]
        out.append((email, uid, shard_of(uid)))
        if i >= 2 and len({s for *_, s in out}) == need:
            return out
    raise SystemExit(f"Đã tạo {MAX_USERS} User mà chưa phủ đủ {need} shard")


if __name__ == "__main__":
    with connect() as conn:
        for email, uid, shard in seed(conn):
            print(f"{email}  mật khẩu {PASSWORD}  user_id {uid}  shard {shard}")
```

- [ ] **Step 4: Đưa `scripts` vào image**

`server/Dockerfile`, sau `COPY app ./app`:

```dockerfile
COPY scripts ./scripts
```

- [ ] **Step 5: Chạy test**

Run: `cd server && uv run pytest -q`
Expected: 331 passed.

- [ ] **Step 6: Commit**

```bash
git add server && git commit -m "feat(server): seed_users tạo User mẫu phủ đủ mọi shard (#51)"
```

---

### Task 7: Cụm 15 container, chạy thử thật, tài liệu

**Files:**
- Create: `docker/initdb-catalog/01-replication.sh`, `docker/replica.sh`
- Modify: `docker-compose.cluster.yml`, `server/.env.example`, `docs/runbook-cum.md`, `docs/ROADMAP.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: mọi thứ từ Task 1–6. Không sản xuất gì cho task khác.

- [ ] **Step 1: Script replication**

`docker/initdb-catalog/01-replication.sh`:

```sh
#!/bin/sh
# pg_hba mặc định của image chỉ mở "host all all all": dòng đó không gồm kết nối replication từ pg-catalog-replica.
echo "host replication travility all scram-sha-256" >> "$PGDATA/pg_hba.conf"
```

`docker/replica.sh`:

```sh
#!/bin/sh
# Bản sao đọc của pg-catalog (spec scale §9.2): volume trống → chép từ node chính, rồi chạy hot standby.
set -e
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  until pg_basebackup -h pg-catalog -U travility -D "$PGDATA" -R -X stream; do
    echo "chờ pg-catalog…"; sleep 1
  done
fi
exec docker-entrypoint.sh postgres
```

```bash
chmod +x docker/initdb-catalog/01-replication.sh docker/replica.sh
```

- [ ] **Step 2: `docker-compose.cluster.yml`**

Thay service `db` bằng bốn Postgres, thêm `places`, sửa `app_env` và `app_deps`. Phần đầu file và các service đổi:

```yaml
# Cụm phân tán (spec scale §4). T5: nginx + 2 api + 2 planner + 3 planner-agent + llm-gateway + places + redis
# + pg-catalog và bản sao + 2 shard = 15 container.
# Dùng chung cổng 5432/6379/8000 với docker-compose.yml → `docker compose down` trước khi bật cụm.
name: travility-cluster
x-pg: &pg
  image: pgvector/pgvector:pg17
  environment: &pg_env
    POSTGRES_USER: travility
    POSTGRES_PASSWORD: travility
    POSTGRES_DB: travility
  healthcheck:
    # -h 127.0.0.1: chỉ báo sẵn sàng khi server thật đã nghe TCP, không phải server tạm lúc initdb
    test: ["CMD-SHELL", "pg_isready -U travility -h 127.0.0.1"]
    interval: 2s
    retries: 30
services:
  pg-catalog:  # database chung, node chính: users, destinations, places
    <<: *pg
    ports: ["127.0.0.1:5432:5432"]
    volumes:
      - pgcatalog:/var/lib/postgresql/data
      - ./docker/initdb-catalog:/docker-entrypoint-initdb.d
  pg-catalog-replica:  # bản sao đọc (streaming replication bất đồng bộ); chỉ service places đọc
    <<: *pg
    environment:
      <<: *pg_env
      PGPASSWORD: travility
    entrypoint: ["/bin/sh", "/replica.sh"]
    volumes:
      - pgreplica:/var/lib/postgresql/data
      - ./docker/replica.sh:/replica.sh:ro
    depends_on:
      pg-catalog:
        condition: service_healthy
  pg-shard-0:  # trips, itineraries, proposals, messages của User có user_id % 2 == 0
    <<: *pg
    volumes:
      - pgshard0:/var/lib/postgresql/data
  pg-shard-1:
    <<: *pg
    volumes:
      - pgshard1:/var/lib/postgresql/data
```

`redis` và `llm-gateway` giữ nguyên. Thêm `places` sau `llm-gateway`:

```yaml
  places:  # tìm Place bằng vector, Place tương tự, Destination, km Goong; đọc bản sao, bản sao chết thì đọc node chính
    build: ./server
    command: ["uv", "run", "--no-dev", "uvicorn", "app.places_service:app", "--host", "0.0.0.0", "--port", "8000"]
    env_file: ./server/.env
    environment:
      DATABASE_URL: postgresql://travility:travility@pg-catalog:5432/travility
      CATALOG_REPLICA_URL: postgresql://travility:travility@pg-catalog-replica:5432/travility
      REDIS_URL: redis://redis:6379/0
      EMBED_BASE_URL: http://llm-gateway:8000/v1
      PLACES_URL: ""  # service này không bao giờ gọi chính nó
    ports: ["127.0.0.1:8002:8000"]
    depends_on:
      pg-catalog:
        condition: service_healthy
      redis:
        condition: service_healthy
      llm-gateway:
        condition: service_started
```

`api`: sửa hai khối neo (các dòng khác giữ nguyên):

```yaml
    environment: &app_env
      DATABASE_URL: postgresql://travility:travility@pg-catalog:5432/travility
      SHARD_URLS: postgresql://travility:travility@pg-shard-0:5432/travility,postgresql://travility:travility@pg-shard-1:5432/travility
      PLACES_URL: http://places:8000
      REDIS_URL: redis://redis:6379/0
      LLM_BASE_URL: http://llm-gateway:8000/v1
      EMBED_BASE_URL: http://llm-gateway:8000/v1
      DEMO_TODAY: ${DEMO_TODAY:-}
      PLAN_RPM: ${PLAN_RPM:-5}
      PLANNER_MODE: ${PLANNER_MODE:-single}
    deploy:
      replicas: 2
    depends_on: &app_deps
      pg-catalog:
        condition: service_healthy
      pg-shard-0:
        condition: service_healthy
      pg-shard-1:
        condition: service_healthy
      redis:
        condition: service_healthy
      llm-gateway:
        condition: service_started
      places:
        condition: service_started
```

Cuối file:

```yaml
volumes:
  pgcatalog: {}
  pgreplica: {}
  pgshard0: {}
  pgshard1: {}
  redisdata: {}
```

- [ ] **Step 3: `.env.example`**

Thêm vào khối Scale, sau `PLANNER_MODE=single`:

```bash
# Có PLACES_URL → Place, Destination và km Goong đi qua service places (uvicorn app.places_service:app)
PLACES_URL=
# Có → đọc Place từ bản sao của database chung; bản sao chết thì đọc DATABASE_URL
CATALOG_REPLICA_URL=
# URL các shard cách nhau dấu phẩy. Có → Trip của User nằm ở shard user_id % N; DATABASE_URL chỉ còn users + Place
SHARD_URLS=
```

- [ ] **Step 4: Dựng cụm với volume mới**

```bash
docker compose down
docker compose -f docker-compose.cluster.yml down
docker volume rm travility-cluster_pgdata   # volume một-database của T2–T4, không dùng nữa (spec S13)
docker compose -f docker-compose.cluster.yml up -d --build
docker compose -f docker-compose.cluster.yml ps
```

Expected: 15 container `running`; 4 Postgres `healthy`.

Nếu `pg-catalog-replica` không lên: `docker compose -f docker-compose.cluster.yml logs pg-catalog-replica`. Lỗi `no pg_hba.conf entry for replication` nghĩa là `01-replication.sh` chưa chạy (volume `pgcatalog` đã khởi tạo từ trước) → `down -v` rồi dựng lại.

- [ ] **Step 5: Nạp dữ liệu và kiểm dữ liệu nằm đúng chỗ**

Từ đây `dc` = `docker compose -f docker-compose.cluster.yml`.

```bash
cd server && uv run python -m scripts.import_places ../data/places && cd ..
dc exec api uv run --no-dev python -m scripts.seed_users
dc exec pg-catalog psql -U travility -c '\dt'
dc exec pg-shard-0 psql -U travility -c '\dt'
dc exec pg-catalog-replica psql -U travility -c "SELECT pg_is_in_recovery(), (SELECT count(*) FROM places)"
```

Expected: `seed_users` in hai dòng, một `shard 0` một `shard 1`. `pg-catalog` chỉ có `users`, `destinations`, `places`. `pg-shard-0` chỉ có `trips`, `itineraries`, `proposals`, `messages`. Bản sao: `t` và số Place bằng số vừa import.

- [ ] **Step 6: Chạy thử theo nghiệm thu của #51**

```bash
login() { curl -s localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"$1\",\"password\":\"travility-demo\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])'; }
T1=$(login demo1@travility.vn); T2=$(login demo2@travility.vn)
plan() { curl -sN localhost:8000/trips -H "Authorization: Bearer $1" -H 'Content-Type: application/json' \
  -d '{"message":"Đà Lạt 2 ngày 3 triệu, 2 người, đi xe máy, khởi hành thứ bảy tuần sau"}' | tail -c 400; }
trips() { curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/trips -H "Authorization: Bearer $1"; }
```

1. Lập lịch cho cả hai User: `plan $T1; plan $T2`. Expected: mỗi lượt kết thúc bằng event `itinerary` (hoặc `clarify`: khi đó Trip vẫn được tạo).
2. Mỗi shard có đúng Trip của User mình: `dc exec pg-shard-0 psql -U travility -c 'SELECT id, user_id FROM trips'` và tương tự `pg-shard-1`. Expected: `user_id` chẵn ở shard 0, lẻ ở shard 1.
3. **Tắt bản sao:** `dc stop pg-catalog-replica; plan $T1`. Expected: vẫn ra lịch; `dc logs places | grep "bản sao"` có dòng cảnh báo. Bật lại: `dc start pg-catalog-replica`.
4. **Tắt một shard:** `dc stop pg-shard-1; trips $T1; trips $T2`. Expected: User ở shard 1 nhận `503`, User kia `200`. `plan` của User shard 1 trả JSON `{"detail":"Dữ liệu chuyến đi tạm không truy cập được, bạn thử lại sau nhé."}`. Bật lại: `dc start pg-shard-1`, cả hai `200`.
5. **Tắt `places`:** `dc stop places; trips $T1; plan $T1`. Expected: `200`; `plan` kết thúc bằng event `error` "Dịch vụ địa điểm tạm không truy cập được…". Bật lại: `dc start places`.
6. RAM: `docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' | grep travility-cluster`. Ghi tổng để điền ROADMAP.

Bước nào không đúng Expected thì dừng, dùng `superpowers:systematic-debugging`, sửa code kèm test, rồi chạy lại từ Step 4.

- [ ] **Step 7: Runbook**

`docs/runbook-cum.md`: trong "Dựng cụm" thêm dòng `dc exec api uv run --no-dev python -m scripts.seed_users` sau lệnh import, và sửa câu mô tả cổng thành: "`nginx` ở `localhost:8000`, `llm-gateway` ở `localhost:8001`, `places` ở `localhost:8002` (hai cổng sau chỉ để kiểm tra), `pg-catalog` ở `localhost:5432`." Thêm mục mới trước "Lập lịch đa agent (T4)" hoặc cuối file:

````markdown
## `places`, bản sao đọc, shard (T5)

Bốn Postgres: `pg-catalog` (users, destinations, places) có bản sao `pg-catalog-replica`; `pg-shard-0` và `pg-shard-1` giữ trips, itineraries, proposals, messages. Trip của User nằm ở shard `user_id % 2`. Đọc Place đi qua service `places`, service này đọc bản sao.

```bash
dc exec api uv run --no-dev python -m scripts.seed_users          # demo1/demo2@travility.vn, mật khẩu travility-demo; in shard của từng User
dc exec pg-shard-0 psql -U travility -c 'SELECT id, user_id FROM trips'
dc exec pg-catalog-replica psql -U travility -c "SELECT pg_is_in_recovery(), now() - pg_last_xact_replay_timestamp() AS tre"
```

### Tắt bản sao

`dc stop pg-catalog-replica` → không ai thấy gì: `places` đọc node chính (`dc logs places` có dòng "bản sao pg-catalog không kết nối được"). `dc start pg-catalog-replica` là bản sao tự đuổi kịp.

### Tắt một shard

`dc stop pg-shard-1` → User có `user_id` lẻ nhận 503 "Dữ liệu chuyến đi tạm không truy cập được" ở mọi request về Trip; User chẵn dùng bình thường; đăng nhập của cả hai vẫn chạy. Việc lập lịch đang xếp hàng của User shard chết nhận event `error`, worker chạy tiếp việc khác. Shard không có bản sao: bật lại bằng `dc start pg-shard-1`.

### Tắt `places`

`dc stop places` → lập lịch, Disruption → Proposal, khôi phục version báo "Dịch vụ địa điểm tạm không truy cập được". Danh sách Trip, mở Trip, ghim vẫn chạy (mỗi bản `api` giữ bản Destination đọc được gần nhất). Km của Leg quay về ước tính chim bay × 1.3.

### Lưu ý

- Volume mới hoàn toàn: sau `dc down -v` phải chạy lại `import_places` và `seed_users`.
- `import_places` chạy từ máy ngoài, ghi vào `pg-catalog` qua `localhost:5432`; bản sao nhận theo sau vài mili giây.
- `trips.id` tự tăng theo từng shard nên hai User khác shard có thể cùng có Trip số 1. Không lẫn: shard chọn theo User trong JWT trước rồi mới tra id.
- Thêm shard thứ ba đòi chuyển dữ liệu (`user_id % N` đổi kết quả với hầu hết User): không làm; hướng giải là consistent hashing.
- Chưa có ở T5 (để T6): `pg-catalog` chính chết thì `api` không khởi động lại được và không đăng nhập được.
````

- [ ] **Step 8: ROADMAP, CLAUDE.md**

- `docs/ROADMAP.md` dòng T5: đổi `- [ ]` thành `- [x]` và viết lại phần mô tả: "Service `places` (tìm vector, Place tương tự, km Goong) đọc bản sao `pg-catalog-replica`, bản sao chết thì đọc node chính; Trip chia 2 shard theo `user_id % 2`, shard chết chỉ User của shard đó nhận 503; `seed_users` ([runbook](runbook-cum.md)). Cụm 15 container dùng khoảng <số đo ở Step 6> MB RAM · *microservice, replication, sharding*". Ở mục "Tiếp theo" (dòng ~155) đổi "Tiếp: lát scale T5 (#51 …)" thành "✅ T5 (#51) xong 2026-10-01. Tiếp: T6 (#52)".
- `CLAUDE.md` dòng "Cụm": đổi phần trong ngoặc thành `(nginx + 2 api + 2 planner + 3 planner-agent + llm-gateway + places + Redis + 4 Postgres)`.

- [ ] **Step 9: Test lần cuối ở chế độ đơn giản**

```bash
docker compose -f docker-compose.cluster.yml down
docker compose up -d db redis && cd server && uv run pytest -q && cd ../client && npm test && npm run build
```

Expected: 331 passed; client test và build xanh (client không đổi dòng nào).

- [ ] **Step 10: Commit**

```bash
git add docker docker-compose.cluster.yml server/.env.example docs CLAUDE.md
git commit -m "feat: cụm 15 container — places, bản sao đọc pg-catalog, 2 shard; runbook T5 (#51)"
```

---

### Task 8: Rà soát và PR

- [ ] **Step 1:** `/gc-ship` (lint + test).
- [ ] **Step 2:** `/code-review` trên diff `main...feat/51-places-shard`, kèm `superpowers:requesting-code-review` với 5 mục ở "Review Focus". Sửa phát hiện có thật, mỗi lần sửa kèm test.
- [ ] **Step 3:** Hỏi Thành trước khi push. Được đồng ý thì `git push -u origin feat/51-places-shard` và mở PR vào `main`, tiêu đề "feat: service places + bản sao đọc + 2 shard theo user_id (#51)", thân có bảng nghiệm thu của #51 đã tick và dòng `Closes #51`.

---

## Verification (tóm tắt)

| Nghiệm thu #51 | Chứng cứ |
|---|---|
| Tắt bản sao → `places` đọc node chính | `test_replica_down_falls_back_to_primary`; Task 7 Step 6.3 |
| Tắt một shard → chỉ User shard đó nhận 503 | `test_dead_shard_only_blocks_its_users`, `test_dead_shard_fails_its_job_and_worker_moves_on`; Step 6.4 |
| User shard này không đọc được Trip shard kia | `test_same_trip_id_on_two_shards_never_crosses`, `test_trips_live_on_the_users_shard` |
| Thiếu biến → một database như cũ, test cũ pass | 306 test cũ không sửa assert; Task 7 Step 9 |
| `places` chết → chỉ việc cần Place lỗi (S27) | `test_plan_through_service_then_places_dies`; Step 6.5 |

## Self-Review

- **Phủ spec:** §8 `places` (Task 1–3, đủ 5 endpoint), §9.1 chia bảng + `shard_conn` + bỏ khoá ngoại + tách `JOIN` (Task 4), §9.2 replication (Task 7), §9.3 khởi tạo cụm + `seed_users` (Task 6, 7), §10 dòng bản sao / shard / `places` (Task 1, 4, 5, 2), §13 "hai database test" (fixture `shards`). `scripts/smoke_cluster.sh` của §13 kiểm `/system/status` nên thuộc T6.
- **Lệch spec có chủ ý:** dependency chung vẫn tên `get_conn` (spec gọi `get_catalog`) để fixture của `test_auth` không đổi; `GET /destinations` còn mở kết nối `pg-catalog` chính dù có `PLACES_URL` (T6 xử lý cùng chế độ chỉ đọc).
- **Tên nhất quán giữa các task:** `places_client.call` / `PlacesDown` / `PLACES_DOWN` / `_http` / `_dests`; `db._open` / `catalog_read` / `shard_urls` / `shard_of` / `shard_conn` / `init_schemas` / `SHARD_DOWN`; `auth.get_shard`; `distance.goong`.
- **Số test dự kiến:** 306 → 310 → 317 → 320 → 327 → 329 → 331. Số thật lệch thì báo con số thật, không sửa cho khớp.
