# Plan 1 — Nền tảng + AI Trip Planner lõi — Implementation Plan

> **Trạng thái: ✅ hoàn thành 2026-09-25** trên nhánh `feat/plan-1-core` (13/13 task, 58 test server + 2 test client pass).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** User đăng ký/đăng nhập, gõ "Đi Đà Lạt 2 ngày, 3 triệu, thích cafe chill", thấy AI tìm Place live trên bản đồ Goong, rồi nhận Itinerary (Stop, Leg, chi phí, Conflict) trên timeline + tuyến đường, camera bay qua từng Stop — trong cửa sổ desktop pywebview.

**Architecture:** Server = FastAPI + PostgreSQL/pgvector chạy bằng Docker Compose. Agent LLM (SDK `openai`) chỉ có 2 tool: `search_places` (pgvector trên dữ liệu Place tự thu thập) và `submit_itinerary`; mọi chi phí/Leg/Conflict do module `rules` tính bằng code. Client = React/Vite/Tailwind + react-map-gl (MapLibre) với style Goong, nhận sự kiện qua SSE; pywebview bọc client thành app desktop.

**Tech Stack:** Python 3.12, uv, FastAPI, psycopg 3, pgvector, pydantic v2, openai, httpx, PyJWT, bcrypt, pytest · Node 22, React 19, Vite, Tailwind v4, react-map-gl 8, maplibre-gl, @mapbox/polyline, vitest · pywebview · Docker Compose, image `pgvector/pgvector:pg17`.

**Spec:** `docs/superpowers/specs/2026-09-25-travility-design.md` · Glossary: `CONTEXT.md` · ADR: `docs/adr/`

**Roadmap:** các plan sau bám theo lộ trình trong [docs/PRD.md §12](../../PRD.md#12-lộ-trình--phân-vai).

## Global Constraints

- Python `>=3.12`, quản lý bằng `uv`; Node `>=22`.
- Tên trong code theo `CONTEXT.md`: Trip, Itinerary, Place, Stop, Stay, Leg, Budget, Conflict, Tag, Pace, Travel Mode, Destination, Forecast, Reason. Không dùng `poi`, `location`, `plan` cho các khái niệm này.
- Mọi text hiển thị cho User bằng tiếng Việt.
- Tiền là số nguyên VND.
- AI chỉ được tham chiếu Place đã nhận từ `search_places` trong cùng phiên; Place lạ → từ chối, AI làm lại tối đa 1 lần (ADR-0001).
- Chi phí, Leg, Conflict tính bằng code trong `server/app/rules.py`, không bao giờ để LLM tính.
- Mọi lời gọi LLM đi qua SDK `openai`, cấu hình bằng env `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL` (ADR-0003). Embedding luôn dùng OpenAI `text-embedding-3-small`, `dimensions=768`.
- Bản đồ và tìm đường chỉ dùng Goong (ADR-0004). Một Trip = một Destination (ADR-0005).
- Pace: `thong-tha` 3–4 Stop 09:00–20:00 · `vua` 5 Stop 08:00–21:00 · `day` 6–7 Stop 07:00–22:00.
- Budget = ăn + vé + Stay + chi phí Leg + thuê xe máy; không gồm di chuyển liên tỉnh.
- Secrets chỉ nằm trong `.env` (đã có trong `.gitignore`).

## Review Focus

- Destination ngoài danh sách ("Phú Quốc 3 ngày") → sự kiện `error` nêu rõ các Destination đang hỗ trợ, không tạo Trip — test ở Task 7.
- LLM trả `arguments` hỏng JSON hoặc sai schema → tool trả lỗi cho LLM và vòng lặp tiếp tục, không crash — test ở Task 8.
- User A mở Trip của User B → 404 như không tồn tại — test ở Task 10.
- Open-Meteo lỗi mạng / ngày đi ngoài 16 ngày → không có Forecast, Itinerary vẫn được tạo — test ở Task 6.
- Mật khẩu tiếng Việt có dấu dài hơn 72 byte (giới hạn bcrypt) → 422 có thông báo, không phải 500 — test ở Task 9.

## File Structure

```
docker-compose.yml                 db (pgvector) + api
docker/initdb/01-test-db.sql       tạo database travility_test cho pytest
data/places/da-lat.json            dữ liệu Place (nguồn gốc duy nhất, commit git)
server/
  pyproject.toml  Dockerfile  .env.example
  app/
    config.py      Settings từ env
    db.py          kết nối psycopg + áp schema
    schema.sql     bảng users, destinations, places, trips, itineraries
    domain.py      model pydantic: Trip, Place, Draft*, Stop, Leg, Day, Conflict, Itinerary, TAGS, KINDS, PACE_*
    rules.py       Leg, chi phí, build_itinerary, Conflict
    places.py      search_places, get_places, list_destinations
    forecast.py    Open-Meteo → khả năng mưa theo ngày
    llm.py         chat_client(), embed()
    agent.py       parse_trip(), plan() → sự kiện
    auth.py        /auth/register, /auth/login, current_user
    trips.py       /destinations, POST /trips (SSE), GET /trips, GET /trips/{id}
    main.py        FastAPI app
  scripts/import_places.py         seed JSON → Postgres + embedding
  tests/  conftest.py  fakes.py  test_*.py
client/                            Vite React TS
  src/api.ts  src/sse.ts  src/sse.test.ts  src/App.tsx
  src/components/{Login,ChatPanel,MapView,Timeline}.tsx
desktop/  pyproject.toml  main.py  pywebview
```

---

### Task 1: Server skeleton + Docker Compose + hạ tầng test

**Files:**
- Create: `docker-compose.yml`, `docker/initdb/01-test-db.sql`, `server/pyproject.toml`, `server/Dockerfile`, `server/.env.example`, `server/app/__init__.py`, `server/app/config.py`, `server/app/db.py`, `server/app/schema.sql`, `server/app/main.py`, `server/tests/conftest.py`, `server/tests/test_health.py`

**Interfaces:**
- Produces: `app.config.settings` (fields `database_url, jwt_secret, llm_base_url, llm_api_key, llm_model, embed_base_url, embed_api_key, embed_model`); `app.db.connect(url: str | None = None) -> psycopg.Connection` (dict rows, autocommit, pgvector registered); `app.db.apply_schema(conn) -> None`; `app.db.get_conn()` FastAPI dependency; pytest fixture `conn` (DB test sạch mỗi test); `app.main.app`.

- [x] **Step 1: Tạo Docker Compose + DB test**

`docker-compose.yml`:
```yaml
services:
  db:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_USER: travility
      POSTGRES_PASSWORD: travility
      POSTGRES_DB: travility
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./docker/initdb:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U travility"]
      interval: 2s
      retries: 30
  api:
    build: ./server
    env_file: ./server/.env
    environment:
      DATABASE_URL: postgresql://travility:travility@db:5432/travility
    ports: ["8000:8000"]
    depends_on:
      db:
        condition: service_healthy
volumes:
  pgdata: {}
```

`docker/initdb/01-test-db.sql`:
```sql
CREATE DATABASE travility_test;
```

Run: `docker compose up -d db && docker compose ps`
Expected: `db` trạng thái `healthy`.

- [x] **Step 2: Tạo project Python**

`server/pyproject.toml`:
```toml
[project]
name = "travility-server"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "psycopg[binary]>=3.2",
  "pgvector>=0.3",
  "numpy>=2.0",
  "pydantic-settings>=2.4",
  "email-validator>=2.2",
  "openai>=1.50",
  "httpx>=0.27",
  "pyjwt>=2.9",
  "bcrypt>=4.2",
]

[dependency-groups]
dev = ["pytest>=8"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

`server/.env.example`:
```
DATABASE_URL=postgresql://travility:travility@localhost:5432/travility
JWT_SECRET=doi-chuoi-nay-thanh-chuoi-ngau-nhien-dai
# Dev: Gemini qua endpoint tương thích OpenAI. Demo: https://api.openai.com/v1 + model OpenAI
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=
LLM_MODEL=gemini-2.5-flash
# Embedding luôn OpenAI (ADR-0003)
EMBED_BASE_URL=https://api.openai.com/v1
EMBED_API_KEY=
EMBED_MODEL=text-embedding-3-small
```

Run: `cd server && cp .env.example .env && uv sync`
Expected: tạo `.venv` và `uv.lock`, không lỗi.

- [x] **Step 3: Config, DB, schema**

`server/app/__init__.py`: file rỗng.

`server/app/config.py`:
```python
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


settings = Settings()
```

`server/app/schema.sql`:
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
  id serial PRIMARY KEY,
  email text UNIQUE NOT NULL,
  password_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS destinations (
  slug text PRIMARY KEY,
  name text NOT NULL,
  lat double precision NOT NULL,
  lon double precision NOT NULL
);

CREATE TABLE IF NOT EXISTS places (
  id serial PRIMARY KEY,
  ext_id text UNIQUE NOT NULL,
  destination text NOT NULL REFERENCES destinations(slug),
  name text NOT NULL,
  kind text NOT NULL,
  lat double precision NOT NULL,
  lon double precision NOT NULL,
  price integer NOT NULL DEFAULT 0,
  open_hours jsonb NOT NULL DEFAULT '{}',
  outdoor boolean NOT NULL DEFAULT false,
  tags text[] NOT NULL DEFAULT '{}',
  description text NOT NULL DEFAULT '',
  photo_url text,
  embedding vector(768) NOT NULL
);

CREATE TABLE IF NOT EXISTS trips (
  id serial PRIMARY KEY,
  user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  spec jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS itineraries (
  id serial PRIMARY KEY,
  trip_id integer NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  version integer NOT NULL,
  data jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (trip_id, version)
);
```

`server/app/db.py`:
```python
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from app.config import settings

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(url: str | None = None) -> psycopg.Connection:
    conn = psycopg.connect(url or settings.database_url, row_factory=dict_row, autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    return conn


def apply_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA.read_text())
    register_vector(conn)  # extension có thể vừa được tạo lại → đăng ký lại kiểu vector


def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
```

- [x] **Step 4: App FastAPI + test health**

`server/app/main.py`:
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import apply_schema, connect


@asynccontextmanager
async def lifespan(_: FastAPI):
    with connect() as conn:
        apply_schema(conn)
    yield


app = FastAPI(title="Travility", lifespan=lifespan)
# Client desktop gửi JWT qua header, không dùng cookie → cho mọi origin là an toàn.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"ok": True}
```

`server/tests/conftest.py`:
```python
import os

import pytest

from app.db import apply_schema, connect

TEST_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://travility:travility@localhost:5432/travility_test"
)


@pytest.fixture
def conn():
    c = connect(TEST_URL)
    c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    apply_schema(c)
    yield c
    c.close()
```

`server/tests/test_health.py`:
```python
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    assert TestClient(app).get("/health").json() == {"ok": True}


def test_schema_creates_tables(conn):
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    ).fetchall()
    assert {r["table_name"] for r in rows} >= {"users", "destinations", "places", "trips", "itineraries"}
```

- [x] **Step 5: Chạy test**

Run: `cd server && uv run pytest -v`
Expected: 2 passed.

- [x] **Step 6: Dockerfile + chạy api trong compose**

`server/Dockerfile`:
```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Run: `docker compose up -d --build api && curl -s localhost:8000/health`
Expected: `{"ok":true}`

- [x] **Step 7: Commit**

```bash
git add docker-compose.yml docker server
git commit -m "feat(server): FastAPI + Postgres/pgvector skeleton with test DB"
```

---

### Task 2: Domain models

**Files:**
- Create: `server/app/domain.py`, `server/tests/test_domain.py`

**Interfaces:**
- Produces (`app.domain`): `TAGS: set[str]`, `KINDS: tuple[str, ...]`, `WEEKDAYS: list[str]`, `PACE_STOPS: dict[str, tuple[int,int]]`, `PACE_HOURS: dict[str, tuple[str,str]]`, models `Trip`, `Place`, `DraftStop`, `DraftDay`, `Draft`, `Stop`, `Leg`, `Day`, `Conflict`, `Itinerary` (fields bên dưới).

- [x] **Step 1: Viết test**

`server/tests/test_domain.py`:
```python
import pytest
from pydantic import ValidationError

from app.domain import Draft, Trip


def test_trip_defaults():
    t = Trip(destination="da-lat", days=3, budget=3_000_000)
    assert (t.travelers, t.pace, t.travel_mode, t.start_date) == (1, "vua", "xe-may", None)


def test_trip_drops_unknown_tags():
    t = Trip(destination="da-lat", days=1, budget=1, required_tags=["an-chay", "khong-ton-tai"])
    assert t.required_tags == ["an-chay"]


@pytest.mark.parametrize("days", [0, 8])
def test_trip_days_range(days):
    with pytest.raises(ValidationError):
        Trip(destination="da-lat", days=days, budget=1)


def test_draft_rejects_bad_time():
    with pytest.raises(ValidationError):
        Draft.model_validate(
            {"days": [{"stops": [{"place_id": 1, "start_time": "25:00", "duration_min": 60}]}]}
        )
```

- [x] **Step 2: Chạy để thấy fail**

Run: `cd server && uv run pytest tests/test_domain.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domain'`

- [x] **Step 3: Viết `domain.py`**

`server/app/domain.py`:
```python
import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator

TAGS = {
    "cafe-chill", "an-chay", "an-dia-phuong", "hai-san", "thien-nhien", "check-in",
    "lich-su", "van-hoa", "dem", "yen-tinh", "soi-dong", "gia-dinh", "lang-man",
    "mua-sam", "view-dep", "gia-re", "sang-trong",
}
KINDS = ("an-uong", "cafe", "tham-quan", "giai-tri", "cho-o")
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

Pace = Literal["thong-tha", "vua", "day"]
TravelMode = Literal["xe-may", "grab"]
PACE_STOPS = {"thong-tha": (3, 4), "vua": (5, 5), "day": (6, 7)}
PACE_HOURS = {"thong-tha": ("09:00", "20:00"), "vua": ("08:00", "21:00"), "day": ("07:00", "22:00")}

HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class Trip(BaseModel):
    destination: str
    days: int = Field(ge=1, le=7)
    start_date: dt.date | None = None
    budget: int = Field(gt=0)
    travelers: int = Field(default=1, ge=1, le=10)
    required_tags: list[str] = []
    preferred_tags: list[str] = []
    avoided_tags: list[str] = []
    pace: Pace = "vua"
    travel_mode: TravelMode = "xe-may"

    @field_validator("required_tags", "preferred_tags", "avoided_tags")
    @classmethod
    def known_tags(cls, v: list[str]) -> list[str]:
        return [t for t in v if t in TAGS]  # LLM có thể bịa Tag → bỏ qua Tag lạ


class Place(BaseModel):
    id: int
    destination: str
    name: str
    kind: str
    lat: float
    lon: float
    price: int
    open_hours: dict[str, list[str] | None]  # {} = luôn mở; "mon": null = đóng cửa
    outdoor: bool
    tags: list[str]
    description: str = ""
    photo_url: str | None = None


class DraftStop(BaseModel):
    place_id: int
    start_time: str = Field(pattern=HHMM)
    duration_min: int = Field(ge=15, le=480)
    reason: str = ""
    pinned: bool = False


class DraftDay(BaseModel):
    stops: list[DraftStop] = Field(min_length=1)


class Draft(BaseModel):
    """Itinerary do LLM đề xuất, chưa có chi phí/Leg/Conflict."""
    stay_place_id: int | None = None
    days: list[DraftDay]
    summary: str = ""


class Stop(DraftStop):
    est_cost: int


class Leg(BaseModel):
    from_place_id: int
    to_place_id: int
    distance_km: float
    duration_min: int
    mode: Literal["walk", "xe-may", "grab"]
    cost: int


class Day(BaseModel):
    date: dt.date | None = None
    stops: list[Stop]
    legs: list[Leg]
    rain_chance: int | None = None


class Conflict(BaseModel):
    kind: Literal["over_budget", "closed", "missing_tag", "rain_outdoor"]
    message: str
    day_index: int | None = None
    place_id: int | None = None


class Itinerary(BaseModel):
    stay_place_id: int | None
    days: list[Day]
    total_cost: int
    conflicts: list[Conflict] = []
    summary: str = ""
```

- [x] **Step 4: Chạy test**

Run: `cd server && uv run pytest tests/test_domain.py -v`
Expected: 5 passed.

- [x] **Step 5: Commit**

```bash
git add server/app/domain.py server/tests/test_domain.py
git commit -m "feat(server): domain models for Trip, Place, Itinerary"
```

---

### Task 3: Import dữ liệu Place + dữ liệu Đà Lạt khởi đầu

**Files:**
- Create: `server/app/llm.py`, `server/scripts/import_places.py`, `server/tests/helpers.py`, `server/tests/test_import_places.py`, `data/places/da-lat.json`

**Interfaces:**
- Consumes: `connect`, `apply_schema` (Task 1); `TAGS`, `KINDS`, `WEEKDAYS` (Task 2).
- Produces: `app.llm.EMBED_DIM = 768`, `app.llm.embed(texts: list[str]) -> list[list[float]]`, `app.llm.chat_client() -> openai.OpenAI`; `scripts.import_places.import_file(conn, path, embed_fn) -> int`; test helpers `unit_vec(i) -> list[float]`, `add_place(conn, **kw) -> int`, `ALL_DAY: dict`.

- [x] **Step 1: `llm.py`**

`server/app/llm.py`:
```python
from openai import OpenAI

from app.config import settings

EMBED_DIM = 768


def chat_client() -> OpenAI:
    return OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)


def embed(texts: list[str]) -> list[list[float]]:
    client = OpenAI(base_url=settings.embed_base_url, api_key=settings.embed_api_key)
    r = client.embeddings.create(model=settings.embed_model, input=texts, dimensions=EMBED_DIM)
    return [d.embedding for d in r.data]
```

- [x] **Step 2: Test helpers**

`server/tests/helpers.py`:
```python
import numpy as np
from psycopg.types.json import Jsonb

from app.domain import WEEKDAYS
from app.llm import EMBED_DIM

ALL_DAY = {d: ["00:00", "24:00"] for d in WEEKDAYS}


def unit_vec(i: int) -> list[float]:
    v = [0.0] * EMBED_DIM
    v[i] = 1.0
    return v


def add_place(conn, name="Place", kind="tham-quan", tags=(), price=0, lat=11.94, lon=108.44,
              outdoor=False, open_hours=None, vec=0, destination="da-lat") -> int:
    conn.execute(
        "INSERT INTO destinations(slug,name,lat,lon) VALUES (%s,%s,11.94,108.44) ON CONFLICT DO NOTHING",
        (destination, destination),
    )
    return conn.execute(
        """INSERT INTO places(ext_id,destination,name,kind,lat,lon,price,open_hours,outdoor,tags,embedding)
           VALUES (gen_random_uuid()::text,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (destination, name, kind, lat, lon, price, Jsonb(open_hours or ALL_DAY), outdoor,
         list(tags), np.array(unit_vec(vec), dtype=np.float32)),
    ).fetchone()["id"]
```

- [x] **Step 3: Viết test import**

`server/tests/test_import_places.py`:
```python
import json

import pytest

from scripts.import_places import expand_hours, import_file
from tests.helpers import unit_vec


def fake_embed(texts):
    return [unit_vec(0) for _ in texts]


def write(tmp_path, places):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({
        "destination": {"slug": "da-lat", "name": "Đà Lạt", "lat": 11.94, "lon": 108.44},
        "places": places,
    }), encoding="utf-8")
    return p


PLACE = {"ext_id": "a", "name": "Hồ Xuân Hương", "kind": "tham-quan", "lat": 11.94, "lon": 108.44,
         "price": 0, "open_hours": {"daily": ["00:00", "24:00"]}, "outdoor": True,
         "tags": ["thien-nhien"], "description": "Hồ trung tâm"}


def test_import_is_idempotent(conn, tmp_path):
    assert import_file(conn, write(tmp_path, [PLACE]), fake_embed) == 1
    import_file(conn, write(tmp_path, [{**PLACE, "name": "Hồ Xuân Hương (mới)"}]), fake_embed)
    rows = conn.execute("SELECT name FROM places").fetchall()
    assert [r["name"] for r in rows] == ["Hồ Xuân Hương (mới)"]


def test_import_rejects_unknown_tag(conn, tmp_path):
    with pytest.raises(ValueError, match="tag lạ"):
        import_file(conn, write(tmp_path, [{**PLACE, "tags": ["bay-lac"]}]), fake_embed)


def test_expand_daily_hours():
    assert expand_hours({"daily": ["07:00", "22:00"]})["sun"] == ["07:00", "22:00"]
    assert expand_hours({"daily": ["07:00", "22:00"], "mon": None})["mon"] is None
```

- [x] **Step 4: Chạy để thấy fail**

Run: `cd server && uv run pytest tests/test_import_places.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts'`

- [x] **Step 5: Viết script import**

`server/scripts/import_places.py`:
```python
"""Nạp data/places/*.json vào Postgres. Chạy: cd server && uv run python -m scripts.import_places ../data/places"""
import json
import sys
from pathlib import Path

import numpy as np
from psycopg.types.json import Jsonb

from app import llm
from app.db import apply_schema, connect
from app.domain import KINDS, TAGS, WEEKDAYS


def expand_hours(hours: dict) -> dict:
    """{"daily": [...], "mon": null} → đủ 7 ngày; ngày ghi riêng đè lên daily."""
    daily = hours.get("daily")
    out = {d: daily for d in WEEKDAYS} if daily else {}
    out.update({k: v for k, v in hours.items() if k in WEEKDAYS})
    return out


def place_text(p: dict) -> str:
    return f"{p['name']}. {p.get('description', '')}. Tags: {', '.join(p['tags'])}"


def import_file(conn, path, embed_fn) -> int:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    d = data["destination"]
    places = data["places"]
    for p in places:
        bad = set(p["tags"]) - TAGS
        if bad:
            raise ValueError(f"{p['ext_id']}: tag lạ {sorted(bad)}")
        if p["kind"] not in KINDS:
            raise ValueError(f"{p['ext_id']}: kind lạ {p['kind']}")
    conn.execute(
        """INSERT INTO destinations(slug,name,lat,lon) VALUES (%s,%s,%s,%s)
           ON CONFLICT (slug) DO UPDATE SET name=excluded.name, lat=excluded.lat, lon=excluded.lon""",
        (d["slug"], d["name"], d["lat"], d["lon"]),
    )
    vecs = embed_fn([place_text(p) for p in places])
    for p, v in zip(places, vecs, strict=True):
        conn.execute(
            """INSERT INTO places(ext_id,destination,name,kind,lat,lon,price,open_hours,outdoor,tags,
                                  description,photo_url,embedding)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (ext_id) DO UPDATE SET destination=excluded.destination, name=excluded.name,
                 kind=excluded.kind, lat=excluded.lat, lon=excluded.lon, price=excluded.price,
                 open_hours=excluded.open_hours, outdoor=excluded.outdoor, tags=excluded.tags,
                 description=excluded.description, photo_url=excluded.photo_url, embedding=excluded.embedding""",
            (p["ext_id"], d["slug"], p["name"], p["kind"], p["lat"], p["lon"], p.get("price", 0),
             Jsonb(expand_hours(p.get("open_hours", {}))), p.get("outdoor", False), p["tags"],
             p.get("description", ""), p.get("photo_url"), np.array(v, dtype=np.float32)),
        )
    return len(places)


if __name__ == "__main__":
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "../data/places")
    with connect() as conn:
        apply_schema(conn)
        for f in sorted(folder.glob("*.json")):
            print(f.name, import_file(conn, f, llm.embed))
```

- [x] **Step 6: Chạy test**

Run: `cd server && uv run pytest tests/test_import_places.py -v`
Expected: 3 passed.

- [x] **Step 7: Dữ liệu Đà Lạt khởi đầu**

Tọa độ dưới đây là **xấp xỉ** — người phụ trách dữ liệu (C) phải kiểm lại từng điểm trên bản đồ Goong trước khi commit, và bổ sung dần đến 150–300 Place (cần thêm Place `an-chay`, homestay giá rẻ `gia-re` kind `cho-o`, quán ăn tối).

`data/places/da-lat.json`:
```json
{
  "destination": {"slug": "da-lat", "name": "Đà Lạt", "lat": 11.9404, "lon": 108.4583},
  "places": [
    {"ext_id": "dalat-ho-xuan-huong", "name": "Hồ Xuân Hương", "kind": "tham-quan", "lat": 11.9420, "lon": 108.4450, "price": 0, "open_hours": {"daily": ["00:00", "24:00"]}, "outdoor": true, "tags": ["thien-nhien", "check-in", "view-dep", "lang-man"], "description": "Hồ nước trung tâm thành phố, đi dạo hoặc đạp vịt."},
    {"ext_id": "dalat-quang-truong-lam-vien", "name": "Quảng trường Lâm Viên", "kind": "tham-quan", "lat": 11.9390, "lon": 108.4460, "price": 0, "open_hours": {"daily": ["00:00", "24:00"]}, "outdoor": true, "tags": ["check-in", "dem", "soi-dong"], "description": "Quảng trường với nụ hoa dã quỳ và bông atiso khổng lồ bằng kính."},
    {"ext_id": "dalat-cho-da-lat", "name": "Chợ Đà Lạt", "kind": "an-uong", "lat": 11.9430, "lon": 108.4370, "price": 100000, "open_hours": {"daily": ["06:00", "23:00"]}, "outdoor": false, "tags": ["an-dia-phuong", "mua-sam", "dem", "soi-dong", "gia-re"], "description": "Chợ trung tâm, buổi tối có chợ đêm với bánh tráng nướng, sữa đậu nành."},
    {"ext_id": "dalat-ga-da-lat", "name": "Ga Đà Lạt", "kind": "tham-quan", "lat": 11.9417, "lon": 108.4553, "price": 10000, "open_hours": {"daily": ["06:00", "17:00"]}, "outdoor": true, "tags": ["lich-su", "check-in"], "description": "Nhà ga kiến trúc Pháp cổ, có tàu đi Trại Mát."},
    {"ext_id": "dalat-thien-vien-truc-lam", "name": "Thiền viện Trúc Lâm", "kind": "tham-quan", "lat": 11.9030, "lon": 108.4360, "price": 0, "open_hours": {"daily": ["06:00", "17:00"]}, "outdoor": true, "tags": ["van-hoa", "yen-tinh", "thien-nhien", "view-dep"], "description": "Thiền viện trên núi Phụng Hoàng nhìn xuống hồ Tuyền Lâm."},
    {"ext_id": "dalat-dinh-bao-dai", "name": "Dinh Bảo Đại", "kind": "tham-quan", "lat": 11.9300, "lon": 108.4290, "price": 30000, "open_hours": {"daily": ["07:00", "17:00"]}, "outdoor": false, "tags": ["lich-su", "van-hoa"], "description": "Dinh thự nghỉ mát của vua Bảo Đại."},
    {"ext_id": "dalat-crazy-house", "name": "Biệt thự Hằng Nga (Crazy House)", "kind": "tham-quan", "lat": 11.9352, "lon": 108.4308, "price": 80000, "open_hours": {"daily": ["08:30", "19:00"]}, "outdoor": false, "tags": ["check-in", "van-hoa"], "description": "Công trình kiến trúc kỳ lạ như trong truyện cổ tích."},
    {"ext_id": "dalat-doi-che-cau-dat", "name": "Đồi chè Cầu Đất", "kind": "tham-quan", "lat": 11.8350, "lon": 108.5560, "price": 0, "open_hours": {"daily": ["06:00", "17:00"]}, "outdoor": true, "tags": ["thien-nhien", "view-dep", "check-in", "yen-tinh"], "description": "Đồi chè xanh ngút mắt, săn mây buổi sáng sớm."},
    {"ext_id": "dalat-cafe-tung", "name": "Cà phê Tùng", "kind": "cafe", "lat": 11.9430, "lon": 108.4380, "price": 35000, "open_hours": {"daily": ["07:00", "22:00"]}, "outdoor": false, "tags": ["cafe-chill", "lich-su", "yen-tinh"], "description": "Quán cà phê lâu đời từ thập niên 1960, không gian hoài cổ."},
    {"ext_id": "dalat-dalat-palace", "name": "Dalat Palace Heritage Hotel", "kind": "cho-o", "lat": 11.9378, "lon": 108.4400, "price": 3000000, "open_hours": {}, "outdoor": false, "tags": ["sang-trong", "lich-su", "view-dep"], "description": "Khách sạn cổ điển kiểu Pháp nhìn ra hồ Xuân Hương."}
  ]
}
```

Run (cần `EMBED_API_KEY` trong `server/.env`): `cd server && uv run python -m scripts.import_places ../data/places`
Expected: `da-lat.json 10`

- [x] **Step 8: Commit**

```bash
git add server/app/llm.py server/scripts server/tests/helpers.py server/tests/test_import_places.py data
git commit -m "feat(data): Place import script with embeddings + Da Lat seed"
```

---

### Task 4: Tìm Place bằng pgvector

**Files:**
- Create: `server/app/places.py`, `server/tests/test_places.py`

**Interfaces:**
- Consumes: `Place` (Task 2); `add_place`, `unit_vec` (Task 3).
- Produces: `search_places(conn, destination: str, query_vec: list[float], kind: str | None = None, must_have_tags: list[str] = (), exclude_tags: list[str] = (), limit: int = 8) -> list[Place]`; `get_places(conn, ids: list[int]) -> dict[int, Place]`; `list_destinations(conn) -> list[dict]` (keys `slug, name, lat, lon`).

- [x] **Step 1: Viết test**

`server/tests/test_places.py`:
```python
from app.places import get_places, list_destinations, search_places
from tests.helpers import add_place, unit_vec


def test_search_orders_by_similarity(conn):
    far = add_place(conn, name="Xa", vec=5)
    near = add_place(conn, name="Gần", vec=1)
    assert [p.id for p in search_places(conn, "da-lat", unit_vec(1))] == [near, far]


def test_search_stays_in_destination(conn):
    add_place(conn, name="Hội An", destination="hoi-an")
    mine = add_place(conn, name="Đà Lạt")
    assert [p.id for p in search_places(conn, "da-lat", unit_vec(0))] == [mine]


def test_search_filters_kind_and_tags(conn):
    add_place(conn, name="Cafe ồn", kind="cafe", tags=["cafe-chill", "soi-dong"])
    ok = add_place(conn, name="Cafe yên", kind="cafe", tags=["cafe-chill", "yen-tinh"])
    add_place(conn, name="Hồ", kind="tham-quan", tags=["cafe-chill"])
    found = search_places(conn, "da-lat", unit_vec(0), kind="cafe",
                          must_have_tags=["cafe-chill"], exclude_tags=["soi-dong"])
    assert [p.id for p in found] == [ok]


def test_get_places_and_destinations(conn):
    pid = add_place(conn, name="A")
    assert get_places(conn, [pid])[pid].name == "A"
    assert list_destinations(conn)[0]["slug"] == "da-lat"
```

- [x] **Step 2: Chạy để thấy fail**

Run: `cd server && uv run pytest tests/test_places.py -v`
Expected: FAIL — `No module named 'app.places'`

- [x] **Step 3: Viết `places.py`**

`server/app/places.py`:
```python
import numpy as np

from app.domain import Place

COLUMNS = "id, destination, name, kind, lat, lon, price, open_hours, outdoor, tags, description, photo_url"


def search_places(conn, destination: str, query_vec: list[float], kind: str | None = None,
                  must_have_tags=(), exclude_tags=(), limit: int = 8) -> list[Place]:
    rows = conn.execute(
        f"""SELECT {COLUMNS} FROM places
            WHERE destination = %(d)s
              AND (%(k)s::text IS NULL OR kind = %(k)s)
              AND tags @> %(must)s::text[]
              AND NOT (tags && %(ex)s::text[])
            ORDER BY embedding <=> %(v)s
            LIMIT %(n)s""",
        {"d": destination, "k": kind, "must": list(must_have_tags), "ex": list(exclude_tags),
         "v": np.array(query_vec, dtype=np.float32), "n": limit},
    ).fetchall()
    return [Place.model_validate(r) for r in rows]


def get_places(conn, ids: list[int]) -> dict[int, Place]:
    rows = conn.execute(f"SELECT {COLUMNS} FROM places WHERE id = ANY(%s)", (list(ids),)).fetchall()
    return {r["id"]: Place.model_validate(r) for r in rows}


def list_destinations(conn) -> list[dict]:
    return conn.execute("SELECT slug, name, lat, lon FROM destinations ORDER BY name").fetchall()
```

- [x] **Step 4: Chạy test**

Run: `cd server && uv run pytest tests/test_places.py -v`
Expected: 4 passed.

- [x] **Step 5: Commit**

```bash
git add server/app/places.py server/tests/test_places.py
git commit -m "feat(server): pgvector Place search with kind/tag filters"
```

---

### Task 5: Rules — Leg, chi phí, Conflict

**Files:**
- Create: `server/app/rules.py`, `server/tests/test_rules.py`

**Interfaces:**
- Consumes: domain models (Task 2).
- Produces: `class InvalidDraft(Exception)`; `make_leg(a: Place, b: Place, mode: str, travelers: int) -> Leg`; `is_open(place: Place, weekday: str, start: str, duration_min: int) -> bool`; `build_itinerary(trip: Trip, draft: Draft, places: dict[int, Place], rain: list[int | None] | None = None) -> Itinerary` (raise `InvalidDraft` khi Place không có trong `places`, sai số ngày, thiếu Stay, Stay không phải `cho-o`); `vnd(n: int) -> str`.

- [x] **Step 1: Viết test**

`server/tests/test_rules.py`:
```python
import datetime as dt

import pytest

from app.domain import Draft, Place, Trip
from app.rules import InvalidDraft, build_itinerary, is_open, make_leg

WEEK = {d: ["08:00", "17:00"] for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]}


def P(id, kind="tham-quan", price=0, lat=11.94, lon=108.44, outdoor=False, tags=(), hours=None):
    return Place(id=id, destination="da-lat", name=f"P{id}", kind=kind, lat=lat, lon=lon,
                 price=price, open_hours=WEEK if hours is None else hours, outdoor=outdoor,
                 tags=list(tags))


def draft(days, stay=None):
    return Draft.model_validate({"stay_place_id": stay, "summary": "", "days": [
        {"stops": [{"place_id": pid, "start_time": "09:00", "duration_min": 60} for pid in day]}
        for day in days]})


def test_short_leg_is_walk():
    leg = make_leg(P(1), P(2, lat=11.9401), "xe-may", 1)
    assert (leg.mode, leg.cost) == ("walk", 0)


def test_motorbike_leg_cost():
    leg = make_leg(P(1), P(2, lat=12.04), "xe-may", 1)  # ~0.1° vĩ độ ≈ 11.1 km × 1.3
    assert leg.mode == "xe-may"
    assert leg.distance_km == pytest.approx(14.46, abs=0.05)
    assert leg.cost == round(leg.distance_km * 2_000)


def test_total_cost():
    # 2 ngày, 2 người: Stay 500k × 1 phòng × 1 đêm + thuê 1 xe × 2 ngày + Stop × 2 người; Leg = 0 (cùng tọa độ)
    places = {1: P(1, price=50_000), 2: P(2, price=30_000), 9: P(9, kind="cho-o", price=500_000, hours={})}
    trip = Trip(destination="da-lat", days=2, travelers=2, budget=10_000_000)
    itin = build_itinerary(trip, draft([[1], [2]], stay=9), places)
    assert itin.total_cost == 500_000 + 240_000 + 100_000 + 60_000
    assert [len(d.legs) for d in itin.days] == [2, 2]  # Stay → Stop → Stay
    assert itin.conflicts == []


def test_unknown_place_rejected():
    with pytest.raises(InvalidDraft, match="999"):
        build_itinerary(Trip(destination="da-lat", days=1, budget=1), draft([[999]]), {1: P(1)})


def test_multi_day_requires_stay():
    with pytest.raises(InvalidDraft, match="stay_place_id"):
        build_itinerary(Trip(destination="da-lat", days=2, budget=1), draft([[1], [1]]), {1: P(1)})


def test_over_budget_still_returns_itinerary():
    itin = build_itinerary(Trip(destination="da-lat", days=1, budget=10_000, travel_mode="grab"),
                           draft([[1]]), {1: P(1, price=50_000)})
    assert [c.kind for c in itin.conflicts] == ["over_budget"]
    assert "40.000đ" in itin.conflicts[0].message


def test_closed_on_that_weekday():
    monday = dt.date(2026, 10, 5)
    assert monday.weekday() == 0
    closed_monday = {**WEEK, "mon": None}
    trip = Trip(destination="da-lat", days=1, budget=10**9, start_date=monday, travel_mode="grab")
    itin = build_itinerary(trip, draft([[1]]), {1: P(1, hours=closed_monday)})
    assert [c.kind for c in itin.conflicts] == ["closed"]


def test_without_date_closed_only_if_never_open():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab")
    ok = build_itinerary(trip, draft([[1]]), {1: P(1, hours={**WEEK, "mon": None})})
    assert ok.conflicts == []
    night = {d: ["18:00", "23:00"] for d in WEEK}
    bad = build_itinerary(trip, draft([[1]]), {1: P(1, hours=night)})
    assert [c.kind for c in bad.conflicts] == ["closed"]


def test_overnight_hours():
    bar = P(1, hours={d: ["18:00", "02:00"] for d in WEEK})
    assert is_open(bar, "mon", "22:00", 60)


def test_rain_outdoor_conflict():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab")
    itin = build_itinerary(trip, draft([[1]]), {1: P(1, outdoor=True)}, rain=[80])
    assert [c.kind for c in itin.conflicts] == ["rain_outdoor"]
    assert itin.days[0].rain_chance == 80


def test_missing_required_tag():
    trip = Trip(destination="da-lat", days=1, budget=10**9, required_tags=["an-chay"], travel_mode="grab")
    itin = build_itinerary(trip, draft([[1]]), {1: P(1, tags=["cafe-chill"])})
    assert [c.kind for c in itin.conflicts] == ["missing_tag"]
```

- [x] **Step 2: Chạy để thấy fail**

Run: `cd server && uv run pytest tests/test_rules.py -v`
Expected: FAIL — `No module named 'app.rules'`

- [x] **Step 3: Viết `rules.py`**

`server/app/rules.py`:
```python
import datetime as dt
import math

from app.domain import WEEKDAYS, Conflict, Day, Draft, Itinerary, Leg, Place, Stop, Trip

# ponytail: đường chim bay × 1.3 thay cho quãng đường thật; đổi sang Goong Distance Matrix nếu cần chính xác.
ROAD_FACTOR = 1.3
WALK_MAX_KM = 0.8
SPEED_KMH = {"walk": 4.5, "xe-may": 25, "grab": 25}
FUEL_PER_KM = 2_000
GRAB_BASE, GRAB_PER_KM = 12_000, 9_000
MOTO_RENT_PER_DAY = 120_000
RAIN_PCT = 60


class InvalidDraft(Exception):
    pass


def vnd(n: int) -> str:
    return f"{n:,}".replace(",", ".") + "đ"


def haversine_km(a: Place, b: Place) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def make_leg(a: Place, b: Place, mode: str, travelers: int) -> Leg:
    km = round(haversine_km(a, b) * ROAD_FACTOR, 2)
    if km < WALK_MAX_KM:
        m, cost = "walk", 0
    elif mode == "grab":
        m, cost = "grab", (GRAB_BASE + round(km * GRAB_PER_KM)) * math.ceil(travelers / 4)
    else:
        m, cost = "xe-may", round(km * FUEL_PER_KM) * math.ceil(travelers / 2)
    return Leg(from_place_id=a.id, to_place_id=b.id, distance_km=km,
               duration_min=max(1, round(km / SPEED_KMH[m] * 60)), mode=m, cost=cost)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def is_open(place: Place, weekday: str, start: str, duration_min: int) -> bool:
    if not place.open_hours:
        return True
    hours = place.open_hours.get(weekday)
    if not hours:
        return False
    o, c = _minutes(hours[0]), _minutes(hours[1])
    if c <= o:  # mở qua đêm, vd 18:00–02:00
        c = 24 * 60
    s = _minutes(start)
    return o <= s and s + duration_min <= c


def _check_draft(trip: Trip, draft: Draft, places: dict[int, Place]) -> None:
    ids = {s.place_id for d in draft.days for s in d.stops}
    if draft.stay_place_id is not None:
        ids.add(draft.stay_place_id)
    unknown = sorted(i for i in ids if i not in places)
    if unknown:
        raise InvalidDraft(f"place_id không tồn tại hoặc chưa được tìm: {unknown}")
    if len(draft.days) != trip.days:
        raise InvalidDraft(f"Trip có {trip.days} ngày nhưng Itinerary có {len(draft.days)} ngày")
    if trip.days > 1 and draft.stay_place_id is None:
        raise InvalidDraft("Trip dài hơn 1 ngày phải có stay_place_id (Place kind cho-o)")
    if draft.stay_place_id is not None and places[draft.stay_place_id].kind != "cho-o":
        raise InvalidDraft("stay_place_id phải là Place kind cho-o")


def build_itinerary(trip: Trip, draft: Draft, places: dict[int, Place],
                    rain: list[int | None] | None = None) -> Itinerary:
    _check_draft(trip, draft, places)
    stay = places.get(draft.stay_place_id) if draft.stay_place_id is not None else None
    pairs = math.ceil(trip.travelers / 2)  # 2 người/phòng, 2 người/xe
    total = stay.price * pairs * (trip.days - 1) if stay else 0
    if trip.travel_mode == "xe-may":
        total += MOTO_RENT_PER_DAY * pairs * trip.days

    days = []
    for i, d in enumerate(draft.days):
        stops = [Stop(**s.model_dump(), est_cost=places[s.place_id].price * trip.travelers)
                 for s in sorted(d.stops, key=lambda s: s.start_time)]
        route = [places[s.place_id] for s in stops]
        if stay:
            route = [stay, *route, stay]
        legs = [make_leg(a, b, trip.travel_mode, trip.travelers) for a, b in zip(route, route[1:])]
        date = trip.start_date + dt.timedelta(days=i) if trip.start_date else None
        days.append(Day(date=date, stops=stops, legs=legs, rain_chance=rain[i] if rain else None))
        total += sum(s.est_cost for s in stops) + sum(leg.cost for leg in legs)

    itin = Itinerary(stay_place_id=draft.stay_place_id, days=days, total_cost=total, summary=draft.summary)
    itin.conflicts = find_conflicts(trip, itin, places)
    return itin


def find_conflicts(trip: Trip, itin: Itinerary, places: dict[int, Place]) -> list[Conflict]:
    out = []
    if itin.total_cost > trip.budget:
        out.append(Conflict(kind="over_budget", message=f"Vượt Budget {vnd(itin.total_cost - trip.budget)}"))
    for i, day in enumerate(itin.days):
        # Không có ngày đi → chỉ báo đóng cửa khi Place không mở vào khung giờ đó ở bất kỳ thứ nào
        weekdays = [WEEKDAYS[day.date.weekday()]] if day.date else WEEKDAYS
        for s in day.stops:
            p = places[s.place_id]
            if not any(is_open(p, w, s.start_time, s.duration_min) for w in weekdays):
                out.append(Conflict(kind="closed", day_index=i, place_id=p.id,
                                    message=f"Ngày {i + 1}: {p.name} không mở cửa lúc {s.start_time}"))
            if day.rain_chance is not None and day.rain_chance >= RAIN_PCT and p.outdoor:
                out.append(Conflict(kind="rain_outdoor", day_index=i, place_id=p.id,
                                    message=f"Ngày {i + 1} khả năng mưa {day.rain_chance}%, {p.name} ở ngoài trời"))
    covered = {t for d in itin.days for s in d.stops for t in places[s.place_id].tags}
    for t in trip.required_tags:
        if t not in covered:
            out.append(Conflict(kind="missing_tag", message=f"Chưa có Stop nào đáp ứng '{t}'"))
    return out
```

- [x] **Step 4: Chạy test**

Run: `cd server && uv run pytest tests/test_rules.py -v`
Expected: 11 passed.

- [x] **Step 5: Commit**

```bash
git add server/app/rules.py server/tests/test_rules.py
git commit -m "feat(server): rules for Leg, cost and Conflict detection"
```

---

### Task 6: Forecast từ Open-Meteo

**Files:**
- Create: `server/app/forecast.py`, `server/tests/test_forecast.py`

**Interfaces:**
- Produces: `get_rain_chance(lat: float, lon: float, start: dt.date | None, days: int, client: httpx.Client | None = None, today: dt.date | None = None) -> list[int | None] | None` — `None` khi không có ngày đi, ngày đã qua, ngoài 16 ngày, hoặc lỗi mạng; danh sách luôn dài đúng `days` (ngày ngoài horizon = `None`).

- [x] **Step 1: Viết test**

`server/tests/test_forecast.py`:
```python
import datetime as dt

import httpx

from app.forecast import get_rain_chance

TODAY = dt.date(2026, 9, 25)


def client_returning(values):
    def handler(request):
        return httpx.Response(200, json={"daily": {"precipitation_probability_max": values}})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_within_horizon():
    r = get_rain_chance(11.9, 108.4, dt.date(2026, 9, 27), 3, client_returning([10, 70, 20]), TODAY)
    assert r == [10, 70, 20]


def test_partial_horizon_is_padded():
    r = get_rain_chance(11.9, 108.4, dt.date(2026, 10, 9), 3, client_returning([10, 70]), TODAY)
    assert r == [10, 70, None]


def test_no_date_or_too_far_or_past():
    c = client_returning([1])
    assert get_rain_chance(11.9, 108.4, None, 3, c, TODAY) is None
    assert get_rain_chance(11.9, 108.4, dt.date(2026, 10, 20), 3, c, TODAY) is None
    assert get_rain_chance(11.9, 108.4, dt.date(2026, 9, 1), 3, c, TODAY) is None


def test_network_error_gives_none():
    def boom(request):
        raise httpx.ConnectError("offline")
    c = httpx.Client(transport=httpx.MockTransport(boom))
    assert get_rain_chance(11.9, 108.4, dt.date(2026, 9, 27), 2, c, TODAY) is None
```

- [x] **Step 2: Chạy để thấy fail**

Run: `cd server && uv run pytest tests/test_forecast.py -v`
Expected: FAIL — `No module named 'app.forecast'`

- [x] **Step 3: Viết `forecast.py`**

`server/app/forecast.py`:
```python
import datetime as dt

import httpx

URL = "https://api.open-meteo.com/v1/forecast"
HORIZON_DAYS = 16


def get_rain_chance(lat: float, lon: float, start: dt.date | None, days: int,
                    client: httpx.Client | None = None, today: dt.date | None = None) -> list[int | None] | None:
    if start is None:
        return None
    today = today or dt.date.today()
    horizon_end = today + dt.timedelta(days=HORIZON_DAYS - 1)
    if start < today or start > horizon_end:
        return None
    end = min(start + dt.timedelta(days=days - 1), horizon_end)
    client = client or httpx.Client(timeout=5)
    try:
        r = client.get(URL, params={
            "latitude": lat, "longitude": lon, "daily": "precipitation_probability_max",
            "timezone": "Asia/Ho_Chi_Minh", "start_date": start.isoformat(), "end_date": end.isoformat(),
        })
        r.raise_for_status()
        values = r.json()["daily"]["precipitation_probability_max"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None  # Forecast là phần phụ: lỗi thì lập lịch không có thời tiết
    return (values + [None] * days)[:days]
```

- [x] **Step 4: Chạy test**

Run: `cd server && uv run pytest tests/test_forecast.py -v`
Expected: 4 passed.

- [x] **Step 5: Commit**

```bash
git add server/app/forecast.py server/tests/test_forecast.py
git commit -m "feat(server): Open-Meteo rain forecast per Trip day"
```

---

### Task 7: Agent — hiểu yêu cầu thành Trip

**Files:**
- Create: `server/app/agent.py`, `server/tests/fakes.py`, `server/tests/test_parse_trip.py`

**Interfaces:**
- Consumes: `Trip`, `TAGS` (Task 2).
- Produces: `class UnsupportedDestination(Exception)`, `class TripParseError(Exception)`; `parse_trip(client, model: str, message: str, destinations: dict[str, str], today: dt.date) -> Trip` (`destinations` = slug → tên); test fakes `FakeClient(responses)` (có `.calls` = list kwargs), `reply(*calls, content=None)` với mỗi call là `(tool_name, args_dict_or_raw_str)`.

- [x] **Step 1: Fakes cho LLM**

`server/tests/fakes.py`:
```python
import json
from types import SimpleNamespace


def reply(*calls, content=None):
    tool_calls = [
        SimpleNamespace(id=f"call{i}", function=SimpleNamespace(
            name=name, arguments=args if isinstance(args, str) else json.dumps(args)))
        for i, (name, args) in enumerate(calls)
    ]
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))])


class FakeClient:
    """Giả lập openai.OpenAI: trả lần lượt các response đã soạn sẵn."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
```

- [x] **Step 2: Viết test**

`server/tests/test_parse_trip.py`:
```python
import datetime as dt

import pytest

from app.agent import TripParseError, UnsupportedDestination, parse_trip
from tests.fakes import FakeClient, reply

DESTS = {"da-lat": "Đà Lạt", "hoi-an": "Đà Nẵng – Hội An"}
TODAY = dt.date(2026, 9, 25)


def run(args):
    return parse_trip(FakeClient([reply(("record_trip", args))]), "m", "...", DESTS, TODAY)


def test_parses_trip():
    t = run({"destination": "da-lat", "days": 3, "budget": 3_000_000, "required_tags": ["cafe-chill"]})
    assert (t.destination, t.days, t.budget, t.required_tags) == ("da-lat", 3, 3_000_000, ["cafe-chill"])


def test_unsupported_destination_lists_supported():
    with pytest.raises(UnsupportedDestination, match="Đà Lạt"):
        run({"destination": "unsupported", "days": 3, "budget": 1})


def test_too_many_days():
    with pytest.raises(TripParseError, match="1–7 ngày"):
        run({"destination": "da-lat", "days": 10, "budget": 1})


def test_broken_json():
    with pytest.raises(TripParseError):
        run("{not json")


def test_prompt_lists_destinations_and_today():
    client = FakeClient([reply(("record_trip", {"destination": "da-lat", "days": 1, "budget": 1}))])
    parse_trip(client, "m", "...", DESTS, TODAY)
    system = client.calls[0]["messages"][0]["content"]
    assert "2026-09-25" in system and "hoi-an" in system
```

- [x] **Step 3: Chạy để thấy fail**

Run: `cd server && uv run pytest tests/test_parse_trip.py -v`
Expected: FAIL — `No module named 'app.agent'`

- [x] **Step 4: Viết phần parse của `agent.py`**

`server/app/agent.py`:
```python
import datetime as dt
import json

from pydantic import ValidationError

from app.domain import TAGS, Trip


class UnsupportedDestination(Exception):
    pass


class TripParseError(Exception):
    pass


PARSE_PROMPT = """Hôm nay là {today}. Chuyển yêu cầu du lịch của người dùng thành Trip bằng tool record_trip.
Destination hỗ trợ: {dests}. Nếu người dùng muốn đi nơi khác, destination = "unsupported".
Budget tính bằng VND cho cả nhóm ("3 triệu" = 3000000). Nếu không nói, ước lượng 1500000 × số người × số ngày.
Chỉ điền start_date (YYYY-MM-DD) khi người dùng nói rõ ngày đi.
Pace: "nhẹ nhàng/thong thả" = thong-tha, "đi nhiều/khám phá hết" = day, còn lại = vua.
Chỉ dùng Tag trong danh sách cho phép; Tag người dùng nói không muốn → avoided_tags."""


def _trip_tool(dest_slugs: list[str]) -> dict:
    tag_list = {"type": "array", "items": {"type": "string", "enum": sorted(TAGS)}}
    return {"type": "function", "function": {
        "name": "record_trip", "description": "Ghi lại Trip của người dùng",
        "parameters": {"type": "object", "properties": {
            "destination": {"type": "string", "enum": [*dest_slugs, "unsupported"]},
            "days": {"type": "integer"},
            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
            "budget": {"type": "integer", "description": "VND cho cả nhóm"},
            "travelers": {"type": "integer"},
            "required_tags": tag_list, "preferred_tags": tag_list, "avoided_tags": tag_list,
            "pace": {"type": "string", "enum": ["thong-tha", "vua", "day"]},
            "travel_mode": {"type": "string", "enum": ["xe-may", "grab"]},
        }, "required": ["destination", "days", "budget"]},
    }}


def parse_trip(client, model: str, message: str, destinations: dict[str, str], today: dt.date) -> Trip:
    dests = ", ".join(f"{slug} ({name})" for slug, name in destinations.items())
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": PARSE_PROMPT.format(today=today.isoformat(), dests=dests)},
                  {"role": "user", "content": message}],
        tools=[_trip_tool(list(destinations))],
        tool_choice="required",
    )
    calls = r.choices[0].message.tool_calls or []
    if not calls:
        raise TripParseError("AI chưa hiểu yêu cầu, bạn nói rõ hơn điểm đến, số ngày và ngân sách nhé.")
    try:
        args = json.loads(calls[0].function.arguments)
    except json.JSONDecodeError as e:
        raise TripParseError("AI trả về dữ liệu hỏng, thử lại nhé.") from e
    if args.get("destination") not in destinations:
        raise UnsupportedDestination(
            f"Travility chưa hỗ trợ điểm đến này. Hiện có: {', '.join(destinations.values())}.")
    try:
        return Trip.model_validate(args)
    except ValidationError as e:
        raise TripParseError("Chưa lập được Trip: hỗ trợ 1–7 ngày, 1–10 người và ngân sách lớn hơn 0.") from e
```

- [x] **Step 5: Chạy test**

Run: `cd server && uv run pytest tests/test_parse_trip.py -v`
Expected: 5 passed.

- [x] **Step 6: Commit**

```bash
git add server/app/agent.py server/tests/fakes.py server/tests/test_parse_trip.py
git commit -m "feat(agent): parse user request into Trip via tool call"
```

---

### Task 8: Agent — vòng lặp lập Itinerary

**Files:**
- Modify: `server/app/agent.py` (thêm phần plan vào cuối file)
- Create: `server/tests/test_plan.py`

**Interfaces:**
- Consumes: `search_places` (Task 4), `build_itinerary`, `InvalidDraft` (Task 5), `Draft`, `Place`, `Trip`, `KINDS`, `TAGS`, `PACE_STOPS`, `PACE_HOURS` (Task 2); `FakeClient`, `reply` (Task 7); `add_place` (Task 3).
- Produces: `plan(conn, client, model: str, trip: Trip, embed_fn, rain: list[int | None] | None) -> Iterator[dict]` — sự kiện:
  - `{"type": "thinking", "text": str}`
  - `{"type": "tool_call", "name": "search_places", "query": str, "places": [PlaceBrief]}`
  - `{"type": "itinerary", "itinerary": Itinerary JSON, "places": {str(id): PlaceBrief}}` (kết thúc)
  - `{"type": "error", "message": str}` (kết thúc)
  - `PlaceBrief` = `{"id", "name", "kind", "lat", "lon", "photo_url", "outdoor", "price"}`

- [x] **Step 1: Viết test**

`server/tests/test_plan.py`:
```python
from app.agent import plan
from app.domain import Trip
from tests.fakes import FakeClient, reply
from tests.helpers import add_place, unit_vec


def fake_embed(texts):
    return [unit_vec(0) for _ in texts]


def stops(*ids):
    return {"summary": "Lịch trình thử", "days": [{"stops": [
        {"place_id": pid, "start_time": f"{9 + i:02d}:00", "duration_min": 60, "reason": "hợp sở thích"}
        for i, pid in enumerate(ids)]}]}


def run(conn, responses, budget=10_000_000):
    client = FakeClient(responses)
    trip = Trip(destination="da-lat", days=1, budget=budget, travel_mode="grab")
    return client, list(plan(conn, client, "m", trip, fake_embed, None))


def tool_messages(client):
    return [m["content"] for m in client.calls[-1]["messages"] if m.get("role") == "tool"]


def test_happy_path(conn):
    a, b = add_place(conn, name="Cafe", kind="cafe"), add_place(conn, name="Hồ", vec=1)
    _, events = run(conn, [reply(("search_places", {"query": "cafe"})),
                           reply(("submit_itinerary", stops(a, b)))])
    assert [e["type"] for e in events] == ["tool_call", "itinerary"]
    assert {p["id"] for p in events[0]["places"]} == {a, b}
    itin = events[-1]["itinerary"]
    assert [s["place_id"] for s in itin["days"][0]["stops"]] == [a, b]
    assert set(events[-1]["places"]) == {str(a), str(b)}


def test_unseen_place_rejected_then_retry(conn):
    a = add_place(conn)
    client, events = run(conn, [reply(("search_places", {"query": "x"})),
                                reply(("submit_itinerary", stops(999))),
                                reply(("submit_itinerary", stops(a)))])
    assert events[-1]["type"] == "itinerary"
    assert any(m.startswith("Lỗi") and "999" in m for m in tool_messages(client))


def test_place_not_searched_is_rejected(conn):
    a = add_place(conn)  # có trong DB nhưng AI chưa search → vẫn bị từ chối
    _, events = run(conn, [reply(("submit_itinerary", stops(a))),
                           reply(("submit_itinerary", stops(a)))])
    assert events[-1]["type"] == "error"


def test_gives_up_after_two_invalid(conn):
    add_place(conn)
    _, events = run(conn, [reply(("search_places", {"query": "x"})),
                           reply(("submit_itinerary", stops(999))),
                           reply(("submit_itinerary", stops(998)))])
    assert events[-1]["type"] == "error"


def test_malformed_arguments_do_not_crash(conn):
    a = add_place(conn)
    client, events = run(conn, [reply(("search_places", "{hỏng")),
                                reply(("search_places", {"query": "x"})),
                                reply(("submit_itinerary", stops(a)))])
    assert events[-1]["type"] == "itinerary"
    assert any("JSON" in m for m in tool_messages(client))


def test_conflict_gets_one_resubmit_then_accepted(conn):
    a = add_place(conn, price=500_000)
    client, events = run(conn, [reply(("search_places", {"query": "x"})),
                                reply(("submit_itinerary", stops(a))),
                                reply(("submit_itinerary", stops(a)))], budget=1_000)
    assert [c["kind"] for c in events[-1]["itinerary"]["conflicts"]] == ["over_budget"]
    assert any(m.startswith("Conflict") for m in tool_messages(client))


def test_thinking_text_is_streamed(conn):
    a = add_place(conn)
    _, events = run(conn, [reply(("search_places", {"query": "x"}), content="Để mình tìm quán cafe"),
                           reply(("submit_itinerary", stops(a)))])
    assert events[0] == {"type": "thinking", "text": "Để mình tìm quán cafe"}
```

- [x] **Step 2: Chạy để thấy fail**

Run: `cd server && uv run pytest tests/test_plan.py -v`
Expected: FAIL — `ImportError: cannot import name 'plan'`

- [x] **Step 3: Thêm phần plan vào `agent.py`**

Sửa khối import đầu `server/app/agent.py` thành:
```python
import datetime as dt
import json
from collections.abc import Iterator

from pydantic import ValidationError

from app.domain import KINDS, PACE_HOURS, PACE_STOPS, TAGS, Draft, Itinerary, Place, Trip
from app.places import search_places
from app.rules import InvalidDraft, build_itinerary, vnd
```

Thêm vào cuối `server/app/agent.py`:
```python
MAX_STEPS = 12
MAX_INVALID = 1  # Place lạ / Draft sai: cho AI làm lại 1 lần (ADR-0001)

PLAN_PROMPT = """Bạn là trợ lý lập lịch trình du lịch cho người Việt.
Quy tắc:
- Chỉ dùng place_id nhận được từ search_places. Không bao giờ tự nghĩ ra địa điểm.
- Gọi search_places nhiều lần cho từng nhu cầu: ăn sáng, tham quan, cafe, ăn tối, và chỗ ở (kind=cho-o) nếu Trip dài hơn 1 ngày.
- Mỗi ngày số Stop và khung giờ theo Pace trong đề bài; sắp Stop theo thứ tự địa lý hợp lý, tránh đi vòng.
- Tôn trọng Tag bắt buộc, tránh Tag cần tránh. Ngày khả năng mưa cao thì ưu tiên Place trong nhà (outdoor=false).
- Kiểm tra open_hours của Place khi xếp giờ.
- reason: 1 câu tiếng Việt nêu vì sao chọn, nhắc Tag/sở thích liên quan.
- Không tự tính tiền: hệ thống tự tính và báo Conflict.
- Khi đủ thông tin, gọi submit_itinerary. summary: 1–2 câu tiếng Việt thân thiện tóm tắt chuyến đi."""

PLAN_TOOLS = [
    {"type": "function", "function": {
        "name": "search_places",
        "description": "Tìm Place thật trong Destination của Trip. Chỉ được dùng place_id trả về từ tool này.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Mô tả tự nhiên, vd 'quán cafe yên tĩnh view đồi thông'"},
            "kind": {"type": "string", "enum": list(KINDS)},
            "must_have_tags": {"type": "array", "items": {"type": "string", "enum": sorted(TAGS)}},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "submit_itinerary",
        "description": "Nộp Itinerary hoàn chỉnh.",
        "parameters": {"type": "object", "properties": {
            "stay_place_id": {"type": "integer", "description": "Place kind cho-o; bắt buộc nếu Trip > 1 ngày"},
            "summary": {"type": "string"},
            "days": {"type": "array", "items": {"type": "object", "properties": {
                "stops": {"type": "array", "items": {"type": "object", "properties": {
                    "place_id": {"type": "integer"},
                    "start_time": {"type": "string", "description": "HH:MM"},
                    "duration_min": {"type": "integer"},
                    "reason": {"type": "string"},
                }, "required": ["place_id", "start_time", "duration_min", "reason"]}},
            }, "required": ["stops"]}},
        }, "required": ["days", "summary"]},
    }},
]


def trip_brief(trip: Trip, rain: list[int | None] | None) -> str:
    lo, hi = PACE_STOPS[trip.pace]
    start, end = PACE_HOURS[trip.pace]
    when = f", bắt đầu {trip.start_date.isoformat()}" if trip.start_date else ""
    lines = [
        f"Destination: {trip.destination}",
        f"Số ngày: {trip.days}{when}",
        f"Số người: {trip.travelers}",
        f"Budget: {vnd(trip.budget)}",
        f"Pace: {lo}-{hi} Stop/ngày, từ {start} đến {end}",
        f"Travel Mode: {trip.travel_mode}",
        f"Tag bắt buộc: {', '.join(trip.required_tags) or 'không'}",
        f"Tag ưu tiên: {', '.join(trip.preferred_tags) or 'không'}",
        f"Tag cần tránh: {', '.join(trip.avoided_tags) or 'không'}",
    ]
    if rain:
        chances = ", ".join(f"ngày {i + 1}: {'?' if r is None else str(r) + '%'}" for i, r in enumerate(rain))
        lines.append(f"Khả năng mưa: {chances}")
    return "\n".join(lines)


def place_brief(p: Place) -> dict:
    return {"id": p.id, "name": p.name, "kind": p.kind, "lat": p.lat, "lon": p.lon,
            "photo_url": p.photo_url, "outdoor": p.outdoor, "price": p.price}


def _for_llm(p: Place) -> dict:
    return {"place_id": p.id, "name": p.name, "kind": p.kind, "tags": p.tags, "price": p.price,
            "outdoor": p.outdoor, "open_hours": p.open_hours, "lat": round(p.lat, 4), "lon": round(p.lon, 4)}


def _itinerary_event(itin: Itinerary, seen: dict[int, Place]) -> dict:
    used = {s.place_id for d in itin.days for s in d.stops}
    if itin.stay_place_id is not None:
        used.add(itin.stay_place_id)
    return {"type": "itinerary", "itinerary": itin.model_dump(mode="json"),
            "places": {str(i): place_brief(seen[i]) for i in used}}


def plan(conn, client, model: str, trip: Trip, embed_fn, rain: list[int | None] | None) -> Iterator[dict]:
    seen: dict[int, Place] = {}  # chỉ Place AI đã nhận từ search_places mới hợp lệ
    messages = [{"role": "system", "content": PLAN_PROMPT},
                {"role": "user", "content": trip_brief(trip, rain)}]
    submits = invalid = 0
    last: Itinerary | None = None

    for _ in range(MAX_STEPS):
        r = client.chat.completions.create(model=model, messages=messages, tools=PLAN_TOOLS,
                                           tool_choice="required")
        msg = r.choices[0].message
        calls = msg.tool_calls or []
        if msg.content:
            yield {"type": "thinking", "text": msg.content}
        assistant = {"role": "assistant", "content": msg.content}
        if calls:
            assistant["tool_calls"] = [{"id": c.id, "type": "function",
                                        "function": {"name": c.function.name, "arguments": c.function.arguments}}
                                       for c in calls]
        messages.append(assistant)

        final = None
        for c in calls:
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                args = None

            if not isinstance(args, dict):
                result = "Lỗi: arguments không phải JSON object hợp lệ."
            elif c.function.name == "search_places":
                query = str(args.get("query", ""))
                found = search_places(
                    conn, trip.destination, embed_fn([query])[0], kind=args.get("kind"),
                    must_have_tags=[t for t in args.get("must_have_tags", []) if t in TAGS],
                    exclude_tags=trip.avoided_tags)
                seen.update({p.id: p for p in found})
                yield {"type": "tool_call", "name": "search_places", "query": query,
                       "places": [place_brief(p) for p in found]}
                result = json.dumps([_for_llm(p) for p in found], ensure_ascii=False)
            elif c.function.name == "submit_itinerary":
                try:
                    itin = build_itinerary(trip, Draft.model_validate(args), seen, rain)
                except (ValidationError, InvalidDraft) as e:
                    invalid += 1
                    if invalid > MAX_INVALID:
                        yield {"type": "error", "message": "AI chưa lập được lịch trình hợp lệ, bạn thử lại nhé."}
                        return
                    result = f"Lỗi: {e}. Chỉ dùng place_id đã nhận từ search_places."
                else:
                    submits += 1
                    last = itin
                    if not itin.conflicts or submits >= 2:
                        final = itin
                    result = ("Conflict: " + "; ".join(x.message for x in itin.conflicts)
                              + ". Sửa nếu có thể rồi submit lại; nếu không thể thì submit lại y nguyên.")
            else:
                result = f"Lỗi: không có tool {c.function.name}."
            messages.append({"role": "tool", "tool_call_id": c.id, "content": result})

        if final:
            yield _itinerary_event(final, seen)
            return

    if last:  # hết lượt nhưng đã có phương án → trả phương án tốt nhất (best-effort)
        yield _itinerary_event(last, seen)
    else:
        yield {"type": "error", "message": "AI chưa hoàn thành lịch trình, bạn thử lại nhé."}
```

- [x] **Step 4: Chạy test**

Run: `cd server && uv run pytest tests/test_plan.py tests/test_parse_trip.py -v`
Expected: 12 passed.

- [x] **Step 5: Commit**

```bash
git add server/app/agent.py server/tests/test_plan.py
git commit -m "feat(agent): tool-calling loop producing validated Itinerary"
```

---

### Task 9: Auth email + mật khẩu

**Files:**
- Create: `server/app/auth.py`, `server/tests/test_auth.py`
- Modify: `server/app/main.py` (include router)

**Interfaces:**
- Consumes: `get_conn` (Task 1), `settings.jwt_secret`.
- Produces: `POST /auth/register` `{email, password}` → 201 `{"token"}` (409 nếu trùng email); `POST /auth/login` → 200 `{"token"}` (401 nếu sai); dependency `current_user(...) -> int` (user id, 401 nếu thiếu/sai token); `make_token(user_id: int) -> str`.

- [x] **Step 1: Viết test**

`server/tests/test_auth.py`:
```python
import pytest
from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app


@pytest.fixture
def client(conn):
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def register(client, email="an@example.com", password="matkhau123"):
    return client.post("/auth/register", json={"email": email, "password": password})


def test_register_and_login(client):
    assert register(client).status_code == 201
    r = client.post("/auth/login", json={"email": "AN@example.com", "password": "matkhau123"})
    assert r.status_code == 200 and r.json()["token"]


def test_duplicate_email(client):
    register(client)
    r = register(client, email="An@Example.com")
    assert r.status_code == 409


def test_wrong_password(client):
    register(client)
    assert client.post("/auth/login", json={"email": "an@example.com", "password": "sai-mat-khau"}).status_code == 401


def test_short_password(client):
    assert register(client, password="123").status_code == 422


def test_password_over_72_bytes(client):
    r = register(client, password="đường" * 10)  # 50 ký tự nhưng > 72 byte UTF-8
    assert r.status_code == 422
    assert "72 byte" in r.text


def test_protected_route_needs_token(client):
    assert client.get("/auth/me").status_code == 401
    token = register(client).json()["token"]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/auth/me", headers={"Authorization": "Bearer rac"}).status_code == 401
```

- [x] **Step 2: Chạy để thấy fail**

Run: `cd server && uv run pytest tests/test_auth.py -v`
Expected: FAIL — 404 trên `/auth/register`.

- [x] **Step 3: Viết `auth.py`**

`server/app/auth.py`:
```python
import datetime as dt

import bcrypt
import jwt
import psycopg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.config import settings
from app.db import get_conn

router = APIRouter(prefix="/auth")
bearer = HTTPBearer(auto_error=False)


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def bcrypt_limit(cls, v: str) -> str:
        if len(v.encode()) > 72:
            raise ValueError("Mật khẩu tối đa 72 byte (khoảng 24 ký tự có dấu)")
        return v


def make_token(user_id: int) -> str:
    exp = dt.datetime.now(dt.UTC) + dt.timedelta(days=7)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.jwt_secret, algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> int:
    if cred is None:
        raise HTTPException(401, "Cần đăng nhập")
    try:
        return int(jwt.decode(cred.credentials, settings.jwt_secret, algorithms=["HS256"])["sub"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Phiên đăng nhập hết hạn, đăng nhập lại nhé") from None


@router.post("/register", status_code=201)
def register(body: Credentials, conn=Depends(get_conn)):
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    try:
        row = conn.execute("INSERT INTO users(email, password_hash) VALUES (%s, %s) RETURNING id",
                           (body.email.lower(), pw_hash)).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Email đã được đăng ký") from None
    return {"token": make_token(row["id"])}


@router.post("/login")
def login(body: Credentials, conn=Depends(get_conn)):
    row = conn.execute("SELECT id, password_hash FROM users WHERE email = %s", (body.email.lower(),)).fetchone()
    if not row or not bcrypt.checkpw(body.password.encode(), row["password_hash"].encode()):
        raise HTTPException(401, "Sai email hoặc mật khẩu")
    return {"token": make_token(row["id"])}


@router.get("/me")
def me(user_id: int = Depends(current_user)):
    return {"id": user_id}
```

Sửa `server/app/main.py` — thêm import và include router ngay sau dòng `app.add_middleware(...)`:
```python
from app import auth
```
```python
app.include_router(auth.router)
```

- [x] **Step 4: Chạy test**

Run: `cd server && uv run pytest tests/test_auth.py -v`
Expected: 6 passed.

- [x] **Step 5: Commit**

```bash
git add server/app/auth.py server/app/main.py server/tests/test_auth.py
git commit -m "feat(auth): email/password register and login with JWT"
```

---

### Task 10: API Trip — SSE + lưu trữ + quyền sở hữu

**Files:**
- Create: `server/app/trips.py`, `server/tests/test_trips_api.py`
- Modify: `server/app/main.py` (include router)

**Interfaces:**
- Consumes: `parse_trip`, `plan`, `UnsupportedDestination`, `TripParseError` (Task 7–8); `get_rain_chance` (Task 6); `list_destinations` (Task 4); `current_user` (Task 9); `llm.chat_client`, `llm.embed` (Task 3).
- Produces: `GET /destinations`; `POST /trips {message}` → `text/event-stream`, mỗi dòng `data: <json>`: các sự kiện của Task 8 cộng `{"type":"trip","trip_id","trip","center":[lon,lat]}`, và sự kiện `itinerary` có thêm `trip_id`, `version`; `GET /trips` → `[{id, spec, created_at}]`; `GET /trips/{id}` → `{trip_id, trip, version, itinerary, places}` hoặc 404. `trips.stream_conn` là điểm thay thế kết nối trong test.

- [x] **Step 1: Viết test**

`server/tests/test_trips_api.py`:
```python
import json
from contextlib import nullcontext

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app import forecast, llm, trips
from app.db import get_conn
from app.main import app
from tests.fakes import FakeClient, reply
from tests.helpers import add_place, unit_vec


@pytest.fixture
def client(conn, monkeypatch):
    app.dependency_overrides[get_conn] = lambda: conn
    monkeypatch.setattr(trips, "stream_conn", lambda: nullcontext(conn))
    monkeypatch.setattr(llm, "embed", lambda texts: [unit_vec(0) for _ in texts])
    monkeypatch.setattr(forecast, "get_rain_chance", lambda *a, **k: None)
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth(client, email="an@example.com"):
    token = client.post("/auth/register", json={"email": email, "password": "matkhau123"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def use_llm(monkeypatch, responses):
    monkeypatch.setattr(llm, "chat_client", lambda: FakeClient(responses))


def happy(pid):
    return [reply(("record_trip", {"destination": "da-lat", "days": 1, "budget": 2_000_000})),
            reply(("search_places", {"query": "cafe"})),
            reply(("submit_itinerary", {"summary": "ok", "days": [{"stops": [
                {"place_id": pid, "start_time": "09:00", "duration_min": 60, "reason": "cafe-chill"}]}]}))]


def test_create_trip_streams_and_persists(client, conn, monkeypatch):
    pid = add_place(conn, name="Cà phê Tùng", kind="cafe")
    use_llm(monkeypatch, happy(pid))
    h = auth(client)
    evs = events(client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h))
    assert [e["type"] for e in evs] == ["thinking", "trip", "tool_call", "itinerary"]
    trip_id = evs[-1]["trip_id"]
    got = client.get(f"/trips/{trip_id}", headers=h).json()
    assert got["version"] == 1
    assert got["itinerary"]["days"][0]["stops"][0]["place_id"] == pid
    assert got["places"][str(pid)]["name"] == "Cà phê Tùng"
    assert [t["id"] for t in client.get("/trips", headers=h).json()] == [trip_id]


def test_other_user_gets_404(client, conn, monkeypatch):
    pid = add_place(conn)
    use_llm(monkeypatch, happy(pid))
    evs = events(client.post("/trips", json={"message": "x"}, headers=auth(client)))
    other = auth(client, "binh@example.com")
    assert client.get(f"/trips/{evs[-1]['trip_id']}", headers=other).status_code == 404
    assert client.get("/trips", headers=other).json() == []


def test_unsupported_destination_is_error_event(client, conn, monkeypatch):
    add_place(conn)
    use_llm(monkeypatch, [reply(("record_trip", {"destination": "unsupported", "days": 3, "budget": 1}))])
    evs = events(client.post("/trips", json={"message": "Phú Quốc"}, headers=auth(client)))
    assert evs[-1]["type"] == "error" and "da-lat" in evs[-1]["message"]
    assert conn.execute("SELECT count(*) AS n FROM trips").fetchone()["n"] == 0


def test_llm_down_is_error_event(client, conn, monkeypatch):
    add_place(conn)
    use_llm(monkeypatch, [openai.APIConnectionError(request=httpx.Request("POST", "http://llm"))])
    evs = events(client.post("/trips", json={"message": "x"}, headers=auth(client)))
    assert evs[-1] == {"type": "error", "message": "Không kết nối được AI, kiểm tra mạng rồi thử lại nhé."}


def test_requires_login(client):
    assert client.post("/trips", json={"message": "x"}).status_code == 401
```

Lưu ý: `add_place` tạo Destination có `name` = slug (`da-lat`), nên thông báo lỗi chứa `da-lat`.

- [x] **Step 2: Chạy để thấy fail**

Run: `cd server && uv run pytest tests/test_trips_api.py -v`
Expected: FAIL — `cannot import name 'trips' from 'app'`

- [x] **Step 3: Viết `trips.py`**

`server/app/trips.py`:
```python
import datetime as dt
import json

import openai
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app import forecast, llm
from app.agent import TripParseError, UnsupportedDestination, parse_trip, plan
from app.auth import current_user
from app.config import settings
from app.db import connect, get_conn
from app.places import list_destinations

router = APIRouter()
stream_conn = connect  # SSE chạy sau khi handler trả về → tự mở kết nối riêng; test thay bằng kết nối test


class NewTrip(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.get("/destinations")
def destinations(conn=Depends(get_conn)):
    return list_destinations(conn)


@router.post("/trips")
def create_trip(body: NewTrip, user_id: int = Depends(current_user)):
    def events():
        with stream_conn() as conn:
            try:
                yield from _run(conn, user_id, body.message)
            except openai.OpenAIError:
                yield sse({"type": "error", "message": "Không kết nối được AI, kiểm tra mạng rồi thử lại nhé."})

    return StreamingResponse(events(), media_type="text/event-stream")


def _run(conn, user_id: int, message: str):
    dests = {d["slug"]: d for d in list_destinations(conn)}
    client = llm.chat_client()
    yield sse({"type": "thinking", "text": "Đang đọc yêu cầu của bạn…"})
    try:
        trip = parse_trip(client, settings.llm_model, message,
                          {slug: d["name"] for slug, d in dests.items()}, dt.date.today())
    except (UnsupportedDestination, TripParseError) as e:
        yield sse({"type": "error", "message": str(e)})
        return
    d = dests[trip.destination]
    trip_json = trip.model_dump(mode="json")
    trip_id = conn.execute("INSERT INTO trips(user_id, spec) VALUES (%s, %s) RETURNING id",
                           (user_id, Jsonb(trip_json))).fetchone()["id"]
    yield sse({"type": "trip", "trip_id": trip_id, "trip": trip_json, "center": [d["lon"], d["lat"]]})

    rain = forecast.get_rain_chance(d["lat"], d["lon"], trip.start_date, trip.days)
    for ev in plan(conn, client, settings.llm_model, trip, llm.embed, rain):
        if ev["type"] == "itinerary":
            conn.execute("INSERT INTO itineraries(trip_id, version, data) VALUES (%s, 1, %s)",
                         (trip_id, Jsonb({"itinerary": ev["itinerary"], "places": ev["places"]})))
            ev = {**ev, "trip_id": trip_id, "version": 1}
        yield sse(ev)


@router.get("/trips")
def list_trips(user_id: int = Depends(current_user), conn=Depends(get_conn)):
    return conn.execute("SELECT id, spec, created_at FROM trips WHERE user_id = %s ORDER BY id DESC",
                        (user_id,)).fetchall()


@router.get("/trips/{trip_id}")
def get_trip(trip_id: int, user_id: int = Depends(current_user), conn=Depends(get_conn)):
    trip = conn.execute("SELECT id, spec FROM trips WHERE id = %s AND user_id = %s",
                        (trip_id, user_id)).fetchone()
    if not trip:
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    it = conn.execute("SELECT version, data FROM itineraries WHERE trip_id = %s ORDER BY version DESC LIMIT 1",
                      (trip_id,)).fetchone()
    return {"trip_id": trip["id"], "trip": trip["spec"],
            "version": it["version"] if it else None,
            "itinerary": it["data"]["itinerary"] if it else None,
            "places": it["data"]["places"] if it else {}}
```

Sửa `server/app/main.py`: đổi dòng import thành `from app import auth, trips` và thêm sau `app.include_router(auth.router)`:
```python
app.include_router(trips.router)
```

- [x] **Step 4: Chạy toàn bộ test server**

Run: `cd server && uv run pytest -v`
Expected: 52 passed.

- [x] **Step 5: Thử thật với LLM (cần `LLM_API_KEY`, `EMBED_API_KEY` và đã chạy import Task 3)**

Run:
```bash
cd server && uv run uvicorn app.main:app --port 8000 &
TOKEN=$(curl -s localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"matkhau123"}' | python -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -N localhost:8000/trips -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"Đi Đà Lạt 2 ngày, 5 triệu, thích cafe chill và thiên nhiên"}'
```
Expected: luồng `data: {...}` gồm `trip`, vài `tool_call`, kết thúc bằng `itinerary` (hoặc `error` có thông báo rõ ràng). Tắt server sau khi thử.

- [x] **Step 6: Commit**

```bash
git add server/app/trips.py server/app/main.py server/tests/test_trips_api.py
git commit -m "feat(api): stream Trip planning over SSE with per-user ownership"
```

---

### Task 11: Client — scaffold, đăng nhập, API + SSE

**Files:**
- Create: `client/` (Vite React TS), `client/.env.example`, `client/src/sse.ts`, `client/src/sse.test.ts`, `client/src/api.ts`, `client/src/components/Login.tsx`
- Modify: `client/vite.config.ts`, `client/src/index.css`, `client/src/App.tsx`, `client/package.json` (script test)
- Delete: `client/src/App.css`

**Interfaces:**
- Consumes: API Task 9–10.
- Produces: `parseSSE(buffer: string): { events: unknown[]; rest: string }`; `authRequest(path: '/auth/login' | '/auth/register', email: string, password: string): Promise<string>`; `streamTrip(token: string, message: string, onEvent: (e: AgentEvent) => void): Promise<void>` (throw `Error('unauthorized')` khi 401); types `Place, Stop, Leg, Day, Conflict, Itinerary, AgentEvent`; component `<Login onToken={(t: string) => void} />`.

- [x] **Step 1: Scaffold**

Run:
```bash
npm create vite@latest client -- --template react-ts
cd client && npm install
npm install maplibre-gl react-map-gl @mapbox/polyline
npm install -D tailwindcss @tailwindcss/vite vitest @types/mapbox__polyline
rm src/App.css
```

`client/vite.config.ts`:
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// base './' để bản build chạy được khi pywebview mở file tĩnh
export default defineConfig({ plugins: [react(), tailwindcss()], base: './' })
```

`client/src/index.css` (thay toàn bộ):
```css
@import "tailwindcss";
@import "maplibre-gl/dist/maplibre-gl.css";
```

`client/.env.example`:
```
VITE_API_URL=http://localhost:8000
VITE_GOONG_MAPTILES_KEY=
VITE_GOONG_API_KEY=
```

Thêm vào `"scripts"` trong `client/package.json`: `"test": "vitest run"`.

Run: `cp .env.example .env` (điền key Goong từ https://account.goong.io).

- [x] **Step 2: Viết test SSE**

`client/src/sse.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { parseSSE } from './sse'

describe('parseSSE', () => {
  it('tách sự kiện hoàn chỉnh và giữ phần dở dang', () => {
    const { events, rest } = parseSSE('data: {"type":"thinking","text":"a"}\n\ndata: {"type":"er')
    expect(events).toEqual([{ type: 'thinking', text: 'a' }])
    expect(rest).toBe('data: {"type":"er')
  })

  it('ghép tiếp phần còn lại ở lần đọc sau', () => {
    const first = parseSSE('data: {"a":')
    const second = parseSSE(first.rest + '1}\n\n')
    expect(second.events).toEqual([{ a: 1 }])
    expect(second.rest).toBe('')
  })
})
```

Run: `cd client && npm test`
Expected: FAIL — không tìm thấy `./sse`.

- [x] **Step 3: Viết `sse.ts` và `api.ts`**

`client/src/sse.ts`:
```ts
export function parseSSE(buffer: string): { events: unknown[]; rest: string } {
  const parts = buffer.split('\n\n')
  const rest = parts.pop() ?? ''
  const events = parts
    .map((p) => p.split('\n').filter((l) => l.startsWith('data: ')).map((l) => l.slice(6)).join('\n'))
    .filter(Boolean)
    .map((s) => JSON.parse(s))
  return { events, rest }
}
```

`client/src/api.ts`:
```ts
import { parseSSE } from './sse'

const API = import.meta.env.VITE_API_URL as string

export type Place = {
  id: number; name: string; kind: string; lat: number; lon: number
  photo_url: string | null; outdoor: boolean; price: number
}
export type Stop = {
  place_id: number; start_time: string; duration_min: number; reason: string; pinned: boolean; est_cost: number
}
export type Leg = {
  from_place_id: number; to_place_id: number; distance_km: number; duration_min: number; mode: string; cost: number
}
export type Day = { date: string | null; stops: Stop[]; legs: Leg[]; rain_chance: number | null }
export type Conflict = { kind: string; message: string; day_index: number | null; place_id: number | null }
export type Itinerary = {
  stay_place_id: number | null; days: Day[]; total_cost: number; conflicts: Conflict[]; summary: string
}
export type AgentEvent =
  | { type: 'thinking'; text: string }
  | { type: 'trip'; trip_id: number; trip: { budget: number }; center: [number, number] }
  | { type: 'tool_call'; name: string; query: string; places: Place[] }
  | { type: 'itinerary'; itinerary: Itinerary; places: Record<string, Place>; trip_id: number; version: number }
  | { type: 'error'; message: string }

export async function authRequest(path: '/auth/login' | '/auth/register', email: string, password: string) {
  const r = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  const body = await r.json()
  if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Email hoặc mật khẩu không hợp lệ (mật khẩu tối thiểu 8 ký tự)')
  return body.token as string
}

export async function streamTrip(token: string, message: string, onEvent: (e: AgentEvent) => void) {
  const r = await fetch(API + '/trips', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ message }),
  })
  if (r.status === 401) throw new Error('unauthorized')
  if (!r.ok || !r.body) {
    onEvent({ type: 'error', message: `Lỗi máy chủ (${r.status})` })
    return
  }
  const reader = r.body.pipeThrough(new TextDecoderStream()).getReader()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += value
    const { events, rest } = parseSSE(buf)
    buf = rest
    events.forEach((e) => onEvent(e as AgentEvent))
  }
}
```

Run: `cd client && npm test`
Expected: 2 passed.

- [x] **Step 4: Màn hình đăng nhập + App tạm**

`client/src/components/Login.tsx`:
```tsx
import { useState, type FormEvent } from 'react'
import { authRequest } from '../api'

const INPUT = 'mt-1 w-full rounded-lg border border-stone-300 px-3 py-2'

export default function Login({ onToken }: { onToken: (token: string) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onToken(await authRequest(mode === 'login' ? '/auth/login' : '/auth/register', email, password))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Có lỗi xảy ra')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex h-screen items-center justify-center bg-stone-100 px-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-3 rounded-2xl bg-white p-6 shadow">
        <h1 className="text-2xl font-semibold">Travility</h1>
        <label className="block text-sm">
          Email
          <input type="email" required autoComplete="email" className={INPUT}
            value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="block text-sm">
          Mật khẩu
          <input type="password" required minLength={8} className={INPUT}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <button disabled={busy} className="w-full rounded-lg bg-emerald-700 py-2 text-white disabled:opacity-50">
          {mode === 'login' ? 'Đăng nhập' : 'Đăng ký'}
        </button>
        <button type="button" className="w-full text-sm text-emerald-800"
          onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? 'Chưa có tài khoản? Đăng ký' : 'Đã có tài khoản? Đăng nhập'}
        </button>
      </form>
    </main>
  )
}
```

`client/src/App.tsx` (tạm, Task 12 thay bằng bản đầy đủ):
```tsx
import { useState } from 'react'
import Login from './components/Login'

export default function App() {
  const [token, setToken] = useState<string | null>(null)
  if (!token) return <Login onToken={setToken} />
  return <p className="p-6">Đã đăng nhập.</p>
}
```

- [x] **Step 5: Kiểm tra tay**

Run: `docker compose up -d` (server chạy ở :8000), rồi `cd client && npm run dev` và mở http://localhost:5173
Expected: đăng ký tài khoản mới → thấy "Đã đăng nhập."; đăng nhập sai mật khẩu → "Sai email hoặc mật khẩu". `npm run build` không lỗi TypeScript.

- [x] **Step 6: Commit**

```bash
git add client
git commit -m "feat(client): Vite React scaffold with login and SSE client"
```

---

### Task 12: Client — Chat, bản đồ Goong 3D, Timeline

**Files:**
- Create: `client/src/components/ChatPanel.tsx`, `client/src/components/MapView.tsx`, `client/src/components/Timeline.tsx`
- Modify: `client/src/App.tsx` (thay toàn bộ)

**Interfaces:**
- Consumes: `streamTrip`, types, `Login` (Task 11).
- Produces: `<ChatPanel items busy onSend />` với `type ChatItem = { role: 'user' | 'ai' | 'tool' | 'error'; text: string }`; `<MapView center searchPins itinerary places />`; `<Timeline itinerary places budget />`.

- [x] **Step 1: ChatPanel**

`client/src/components/ChatPanel.tsx`:
```tsx
import { useState } from 'react'

export type ChatItem = { role: 'user' | 'ai' | 'tool' | 'error'; text: string }

const STYLE: Record<ChatItem['role'], string> = {
  user: 'self-end bg-emerald-700 text-white',
  ai: 'bg-white border border-stone-200',
  tool: 'text-xs italic text-stone-500',
  error: 'bg-red-50 text-red-700 border border-red-200',
}

export default function ChatPanel({ items, busy, onSend }: {
  items: ChatItem[]; busy: boolean; onSend: (message: string) => void
}) {
  const [text, setText] = useState('')
  return (
    <aside className="flex min-h-0 flex-col border-r border-stone-200">
      <h1 className="p-4 text-xl font-semibold">Travility</h1>
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-4" aria-live="polite">
        {items.length === 0 && (
          <p className="text-sm text-stone-500">Thử: "Đi Đà Lạt 2 ngày, 5 triệu, thích cafe chill và thiên nhiên"</p>
        )}
        {items.map((it, i) => (
          <div key={i} className={`max-w-[90%] rounded-xl px-3 py-2 text-sm ${STYLE[it.role]}`}>{it.text}</div>
        ))}
        {busy && <div className="animate-pulse text-xs text-stone-500">AI đang lên lịch trình…</div>}
      </div>
      <form className="flex gap-2 border-t border-stone-200 p-3" onSubmit={(e) => {
        e.preventDefault()
        const m = text.trim()
        if (!m || busy) return
        setText('')
        onSend(m)
      }}>
        <input aria-label="Yêu cầu chuyến đi" placeholder="Bạn muốn đi đâu?"
          className="min-w-0 flex-1 rounded-lg border border-stone-300 px-3 py-2 text-sm"
          value={text} onChange={(e) => setText(e.target.value)} />
        <button disabled={busy} className="rounded-lg bg-emerald-700 px-4 text-sm text-white disabled:opacity-50">Gửi</button>
      </form>
    </aside>
  )
}
```

- [x] **Step 2: MapView**

`client/src/components/MapView.tsx`:
```tsx
import { useEffect, useRef, useState } from 'react'
import Map, { Layer, Marker, Source, type MapRef } from 'react-map-gl/maplibre'
import polyline from '@mapbox/polyline'
import type { Itinerary, Place } from '../api'

const STYLE_URL = `https://tiles.goong.io/assets/goong_map_web.json?api_key=${import.meta.env.VITE_GOONG_MAPTILES_KEY}`
export const DAY_COLORS = ['#047857', '#b45309', '#1d4ed8', '#be123c', '#7c3aed', '#0f766e', '#a16207']
const EMPTY: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }

async function legLine(a: Place, b: Place): Promise<[number, number][]> {
  try {
    const r = await fetch(`https://rsapi.goong.io/Direction?origin=${a.lat},${a.lon}&destination=${b.lat},${b.lon}` +
      `&vehicle=bike&api_key=${import.meta.env.VITE_GOONG_API_KEY}`)
    const body = await r.json()
    return polyline.decode(body.routes[0].overview_polyline.points).map(([lat, lon]) => [lon, lat])
  } catch {
    return [[a.lon, a.lat], [b.lon, b.lat]] // Goong lỗi → vẽ đường thẳng, không chặn demo
  }
}

export default function MapView({ center, searchPins, itinerary, places }: {
  center: [number, number]; searchPins: Place[]; itinerary: Itinerary | null; places: Record<string, Place>
}) {
  const mapRef = useRef<MapRef>(null)
  const [routes, setRoutes] = useState<GeoJSON.FeatureCollection>(EMPTY)

  useEffect(() => {
    mapRef.current?.flyTo({ center, zoom: 12.5, pitch: 50, duration: 2000 })
  }, [center])

  useEffect(() => {
    if (!itinerary) {
      setRoutes(EMPTY)
      return
    }
    let cancelled = false
    ;(async () => {
      const features: GeoJSON.Feature[] = []
      for (const [i, day] of itinerary.days.entries()) {
        for (const leg of day.legs) {
          const a = places[leg.from_place_id], b = places[leg.to_place_id]
          if (!a || !b) continue
          features.push({ type: 'Feature', properties: { color: DAY_COLORS[i % DAY_COLORS.length] },
            geometry: { type: 'LineString', coordinates: await legLine(a, b) } })
        }
      }
      if (cancelled) return
      setRoutes({ type: 'FeatureCollection', features })
      for (const day of itinerary.days) {
        for (const s of day.stops) {
          const p = places[s.place_id], map = mapRef.current
          if (cancelled || !p || !map) return
          map.flyTo({ center: [p.lon, p.lat], zoom: 15, pitch: 60, bearing: (map.getBearing() + 40) % 360, duration: 1800 })
          await new Promise((r) => setTimeout(r, 2200))
        }
      }
    })()
    return () => { cancelled = true }
  }, [itinerary, places])

  const stay = itinerary?.stay_place_id != null ? places[itinerary.stay_place_id] : undefined

  return (
    <Map ref={mapRef} mapStyle={STYLE_URL} style={{ width: '100%', height: '100%' }}
      initialViewState={{ longitude: center[0], latitude: center[1], zoom: 12, pitch: 45 }}>
      <Source id="routes" type="geojson" data={routes}>
        <Layer id="routes" type="line" layout={{ 'line-cap': 'round', 'line-join': 'round' }}
          paint={{ 'line-color': ['get', 'color'], 'line-width': 4, 'line-opacity': 0.85 }} />
      </Source>
      {searchPins.map((p) => (
        <Marker key={`s${p.id}`} longitude={p.lon} latitude={p.lat}>
          <span className="relative flex size-3" title={p.name}>
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-amber-400 opacity-75" />
            <span className="relative inline-flex size-3 rounded-full bg-amber-500" />
          </span>
        </Marker>
      ))}
      {itinerary?.days.flatMap((day, i) => day.stops.map((s, j) => {
        const p = places[s.place_id]
        return p && (
          <Marker key={`d${i}-${j}`} longitude={p.lon} latitude={p.lat}>
            <div title={p.name} style={{ background: DAY_COLORS[i % DAY_COLORS.length] }}
              className="flex size-7 items-center justify-center rounded-full border-2 border-white text-xs font-bold text-white shadow">
              {j + 1}
            </div>
          </Marker>
        )
      }))}
      {stay && (
        <Marker longitude={stay.lon} latitude={stay.lat}>
          <div title={stay.name} className="rounded-md border-2 border-white bg-stone-900 px-2 py-1 text-xs font-semibold text-white shadow">
            Chỗ ở
          </div>
        </Marker>
      )}
    </Map>
  )
}
```

- [x] **Step 3: Timeline**

`client/src/components/Timeline.tsx`:
```tsx
import type { Itinerary, Place } from '../api'

const vnd = (n: number) => n.toLocaleString('vi-VN') + 'đ'

export default function Timeline({ itinerary, places, budget }: {
  itinerary: Itinerary | null; places: Record<string, Place>; budget: number | null
}) {
  if (!itinerary) {
    return <aside className="border-l border-stone-200 p-4 text-sm text-stone-500">Lịch trình sẽ hiện ở đây.</aside>
  }
  const stay = itinerary.stay_place_id != null ? places[itinerary.stay_place_id] : undefined
  return (
    <aside className="min-h-0 overflow-y-auto border-l border-stone-200 p-4">
      <div className="mb-3 rounded-xl bg-white p-3 shadow-sm">
        <div className="text-sm text-stone-500">Tổng chi phí ước tính</div>
        <div className="text-2xl font-semibold">{vnd(itinerary.total_cost)}</div>
        {budget != null && <div className="text-xs text-stone-500">Budget {vnd(budget)} · chưa gồm vé đến/rời thành phố</div>}
        {stay && <div className="mt-1 text-xs">Chỗ ở: {stay.name}</div>}
      </div>
      {itinerary.conflicts.length > 0 && (
        <ul className="mb-3 space-y-1 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {itinerary.conflicts.map((c, i) => <li key={i}>{c.message}</li>)}
        </ul>
      )}
      {itinerary.days.map((day, i) => (
        <section key={i} className="mb-4">
          <h2 className="mb-2 font-semibold">
            Ngày {i + 1}{day.date && ` · ${day.date}`}{day.rain_chance != null && ` · mưa ${day.rain_chance}%`}
          </h2>
          <ol className="space-y-2">
            {day.stops.map((s, j) => (
              <li key={j} className="rounded-lg bg-white p-3 text-sm shadow-sm">
                <div className="flex justify-between gap-2">
                  <span className="font-medium">{s.start_time} · {places[s.place_id]?.name}</span>
                  <span className="shrink-0">{vnd(s.est_cost)}</span>
                </div>
                <p className="mt-1 text-xs text-stone-500">{s.reason}</p>
              </li>
            ))}
          </ol>
          <p className="mt-1 text-xs text-stone-500">
            Di chuyển: {day.legs.reduce((a, l) => a + l.distance_km, 0).toFixed(1)} km · {vnd(day.legs.reduce((a, l) => a + l.cost, 0))}
          </p>
        </section>
      ))}
    </aside>
  )
}
```

- [x] **Step 4: App đầy đủ**

`client/src/App.tsx` (thay toàn bộ):
```tsx
import { useState } from 'react'
import { streamTrip, type Itinerary, type Place } from './api'
import ChatPanel, { type ChatItem } from './components/ChatPanel'
import Login from './components/Login'
import MapView from './components/MapView'
import Timeline from './components/Timeline'

function loadToken() {
  try { return localStorage.getItem('token') } catch { return null }
}
function saveToken(t: string | null) {
  try {
    if (t) localStorage.setItem('token', t)
    else localStorage.removeItem('token')
  } catch { /* chỉ là tiện ích nhớ đăng nhập */ }
}

export default function App() {
  const [token, setToken] = useState<string | null>(loadToken)
  const [chat, setChat] = useState<ChatItem[]>([])
  const [busy, setBusy] = useState(false)
  const [center, setCenter] = useState<[number, number]>([108.4583, 11.9404])
  const [searchPins, setSearchPins] = useState<Place[]>([])
  const [itinerary, setItinerary] = useState<Itinerary | null>(null)
  const [places, setPlaces] = useState<Record<string, Place>>({})
  const [budget, setBudget] = useState<number | null>(null)

  if (!token) return <Login onToken={(t) => { saveToken(t); setToken(t) }} />

  const add = (item: ChatItem) => setChat((c) => [...c, item])

  async function send(message: string) {
    setBusy(true)
    add({ role: 'user', text: message })
    setSearchPins([])
    try {
      await streamTrip(token!, message, (e) => {
        switch (e.type) {
          case 'thinking': add({ role: 'ai', text: e.text }); break
          case 'trip': setCenter(e.center); setBudget(e.trip.budget); setItinerary(null); break
          case 'tool_call':
            add({ role: 'tool', text: `Đang tìm: ${e.query} (${e.places.length} kết quả)` })
            setSearchPins((p) => [...p, ...e.places])
            break
          case 'itinerary':
            setPlaces(e.places); setItinerary(e.itinerary); setSearchPins([])
            add({ role: 'ai', text: e.itinerary.summary })
            break
          case 'error': add({ role: 'error', text: e.message }); break
        }
      })
    } catch (err) {
      if (err instanceof Error && err.message === 'unauthorized') { saveToken(null); setToken(null) }
      else add({ role: 'error', text: 'Mất kết nối tới máy chủ. Kiểm tra server đã chạy chưa.' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid h-screen grid-cols-[22rem_1fr_24rem] bg-stone-50 text-stone-900">
      <ChatPanel items={chat} busy={busy} onSend={send} />
      <MapView center={center} searchPins={searchPins} itinerary={itinerary} places={places} />
      <Timeline itinerary={itinerary} places={places} budget={budget} />
    </div>
  )
}
```

- [x] **Step 5: Kiểm tra tay end-to-end**

Run: `docker compose up -d` + đã import Place (Task 3), `cd client && npm run dev`, mở http://localhost:5173
Expected:
1. Đăng nhập → thấy bản đồ Goong Đà Lạt (Hoàng Sa/Trường Sa hiển thị đúng khi zoom ra).
2. Gõ "Đi Đà Lạt 2 ngày, 5 triệu, thích cafe chill và thiên nhiên" → chat hiện "Đang tìm: …", pin vàng nhấp nháy.
3. Itinerary xuất hiện: timeline có 2 ngày, tổng chi phí, Reason; bản đồ vẽ tuyến màu theo ngày; camera bay qua từng Stop.
4. Gõ "Phú Quốc 3 ngày" → thông báo đỏ liệt kê Destination đang hỗ trợ.
5. `npm run build && npm test` không lỗi.

- [x] **Step 6: Commit**

```bash
git add client/src
git commit -m "feat(client): chat, Goong 3D map with live search pins, itinerary timeline"
```

---

### Task 13: Vỏ desktop pywebview + hướng dẫn chạy

**Files:**
- Create: `desktop/pyproject.toml`, `desktop/main.py`, `README.md`
- Modify: `CLAUDE.md` (thêm mục Commands)

**Interfaces:**
- Consumes: bản build `client/dist` (Task 12).
- Produces: `uv run python main.py [url]` mở cửa sổ desktop "Travility".

- [x] **Step 1: Project desktop**

`desktop/pyproject.toml`:
```toml
[project]
name = "travility-desktop"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pywebview>=5.3"]
```

`desktop/main.py`:
```python
"""Mở Travility trong cửa sổ desktop.

uv run python main.py                        # bản build client/dist
uv run python main.py http://localhost:5173  # khi đang dev client
"""
import sys
from pathlib import Path

import webview

DIST = Path(__file__).resolve().parent.parent / "client" / "dist" / "index.html"


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else str(DIST)
    if not url.startswith("http") and not DIST.exists():
        sys.exit("Chưa có client/dist — chạy `cd client && npm run build` trước.")
    webview.create_window("Travility", url, width=1440, height=900, min_size=(1100, 700))
    webview.start(http_server=True)


if __name__ == "__main__":
    main()
```

Run: `cd client && npm run build && cd ../desktop && uv sync && uv run python main.py`
Expected: cửa sổ native "Travility" mở màn hình đăng nhập; đăng nhập và lập một Trip chạy giống Task 12 bước 5.

- [x] **Step 2: README + CLAUDE.md**

`README.md`:
````markdown
# Travility

App desktop giúp người Việt lên kế hoạch du lịch trong nước bằng AI trên bản đồ. Xem `CONTEXT.md` (thuật ngữ), `docs/superpowers/specs/` (spec), `docs/adr/` (quyết định kiến trúc).

## Chạy lần đầu

```bash
cp server/.env.example server/.env        # điền LLM_API_KEY, EMBED_API_KEY, JWT_SECRET
cp client/.env.example client/.env        # điền key Goong
docker compose up -d --build              # Postgres + API ở http://localhost:8000
cd server && uv sync && uv run python -m scripts.import_places ../data/places
cd ../client && npm install && npm run build
cd ../desktop && uv sync && uv run python main.py
```

## Phát triển

- Test server: `docker compose up -d db && cd server && uv run pytest`
- Test client: `cd client && npm test`
- Client dev: `cd client && npm run dev`, rồi `cd desktop && uv run python main.py http://localhost:5173`
- Đổi AI sang OpenAI khi demo: trong `server/.env` đặt `LLM_BASE_URL=https://api.openai.com/v1`, `LLM_API_KEY`, `LLM_MODEL` rồi `docker compose up -d --build api`
````

Thêm vào cuối `CLAUDE.md`:
```markdown
## Commands

- Server test: `docker compose up -d db && cd server && uv run pytest`
- Client test/build: `cd client && npm test && npm run build`
- Import Place: `cd server && uv run python -m scripts.import_places ../data/places`
- Desktop: `cd desktop && uv run python main.py [url]`
```

- [x] **Step 3: Commit**

```bash
git add desktop README.md CLAUDE.md
git commit -m "feat(desktop): pywebview shell and run instructions"
```
