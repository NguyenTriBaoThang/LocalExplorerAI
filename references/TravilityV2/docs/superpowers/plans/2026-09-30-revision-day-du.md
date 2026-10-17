# Revision đầy đủ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kết quả cần đạt: ghim Stop, xem và quay lại version cũ, tải lại app vẫn thấy Trip, hội thoại và các version (issue #17, #3 phần danh sách + đăng xuất, #25, #24).

**Architecture:**
- Ghim lưu trên Trip (`trips.pinned_place_ids`). Mỗi lần đọc Itinerary, hàm `load_itinerary` gán ghim vào từng Stop, nên các chỗ đang kiểm tra `stop.pinned` không phải sửa.
- Lịch sử chat nằm trong bảng `messages`, ghi bằng `log_message`.
- Ba API ghim, lịch sử chat, quay lại bản cũ nằm chung một router mới `app/versions.py`.
- Client thêm các hàm gọi API vào `api.ts`, thêm dãy version, nút ghim và danh sách Trip vào các component có sẵn.

**Tech Stack:** FastAPI, psycopg 3, Postgres/pgvector, pytest · React + TypeScript + Vite + Tailwind, vitest.

**Spec:** `docs/superpowers/specs/2026-09-30-revision-day-du-design.md`

## Global Constraints
- UI và mọi thông báo lỗi bằng **tiếng Việt**. Dùng đúng thuật ngữ trong `CONTEXT.md` (Trip, Itinerary, Stop, Place, Pinned Stop, Revision, version).
- Itinerary **bất biến**: không UPDATE `itineraries.data`. Mọi thay đổi (kể cả quay lại bản cũ) tạo version mới (`save_itinerary`).
- **Ghim không tạo version.**
- API của Trip thuộc User khác → **404** `"Không tìm thấy chuyến đi"`.
- Schema chỉ thêm theo kiểu `IF NOT EXISTS` trong `server/app/schema.sql` (file này được `apply_schema` chạy mỗi lần khởi động).
- Proposal không gọi LLM (ADR-0006). Tiền và Conflict do `rules.build_itinerary` tính.
- Chạy test server: `docker compose up -d db && cd server && uv run pytest`. Client: `cd client && npm test && npm run build`.
- Làm trên nhánh `feat/revision-day-du` tách từ `main`.

## Review Focus
1. **Ghim rồi đổi số ngày ("Lập lại"):** Place đã ghim phải còn trong lịch mới. Test ở Task 2 (`test_replan_keeps_pinned_place`).
2. **Quay lại bản cũ trong lúc một Proposal đang mở:** "Áp dụng" Proposal cũ phải trả 409, không ghi đè bản vừa quay lại. Test ở Task 4 (`test_apply_old_proposal_after_restore_is_409`).
3. **Ghim một Place không có trong bản mới nhất (ví dụ chỗ ở, hoặc Place của bản cũ):** trả 422, không lưu. Test ở Task 1 (`test_pin_place_not_in_latest_is_422`).
4. **Mở lại Trip đang chờ hỏi lại, chưa có lịch:** GET trả `itinerary: null, versions: []` và không lỗi. Test ở Task 1 (`test_get_trip_without_itinerary`).
5. **Bỏ ghim một Place chưa từng ghim:** trả 200, không lỗi. Test ở Task 1 (`test_unpin_is_idempotent`).

---

### Task 1: Ghim trên Trip + đọc version bất kỳ

**Files:**
- Modify: `server/app/schema.sql` (cuối file)
- Modify: `server/app/trips.py` (`latest_itinerary` ~dòng 105, `list_trips`/`get_trip` ~dòng 236–253)
- Modify: `server/app/proposals.py:39-49` (`create_disruption` đọc qua `load_itinerary`)
- Create: `server/app/versions.py` (router: ghim)
- Modify: `server/app/main.py` (đăng ký router)
- Modify: `server/tests/test_disruptions_api.py:29-45` (`seed(pinned=True)` ghim bằng cột mới)
- Test: `server/tests/test_versions_api.py` (mới)

**Interfaces:**
- Produces:
  - `trips.load_itinerary(conn, trip_id: int, version: int | None = None) -> tuple[int, Itinerary, dict] | None`: trả `(version, Itinerary đã gán pinned, places dict dạng lưu trong data)`.
  - `latest_itinerary` giữ nguyên chữ ký `-> tuple[int, Itinerary] | None`.
  - `GET /trips/{id}?version=N` trả `{trip_id, trip, center, version, itinerary, places, versions: list[int], pinned_place_ids: list[int]}`.
  - `GET /trips` mỗi dòng có thêm `destination_name`.
  - `PATCH /trips/{id}/pins {place_id, pinned}` trả `{pinned_place_ids}`.

- [ ] **Step 1: Tạo nhánh**

```bash
git checkout main && git pull --ff-only && git checkout -b feat/revision-day-du
```

- [ ] **Step 2: Viết test lỗi** — tạo `server/tests/test_versions_api.py`

```python
"""Ghim, xem version, lịch sử chat, quay lại bản cũ (spec revision-day-du)."""
from tests.test_trips_api import (auth, client, events, no_meal_rule, trip_with_itinerary,  # noqa: F401 (fixture)
                                  use_llm)
from tests.fakes import reply
from tests.helpers import add_place


def pin(client, h, tid, pid, pinned=True):
    return client.patch(f"/trips/{tid}/pins", headers=h, json={"place_id": pid, "pinned": pinned})


def test_pin_overlays_stop_and_lists_versions(client, conn, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    r = pin(client, h, tid, pid)
    assert r.status_code == 200 and r.json() == {"pinned_place_ids": [pid]}
    got = client.get(f"/trips/{tid}", headers=h).json()
    assert got["itinerary"]["days"][0]["stops"][0]["pinned"] is True
    assert got["versions"] == [1] and got["pinned_place_ids"] == [pid]
    assert got["center"] == [108.44, 11.94]
    assert conn.execute("SELECT count(*) AS n FROM itineraries").fetchone()["n"] == 1  # ghim không tạo version


def test_unpin_is_idempotent(client, conn, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    assert pin(client, h, tid, pid, False).json() == {"pinned_place_ids": []}
    pin(client, h, tid, pid)
    pin(client, h, tid, pid)  # ghim 2 lần không nhân đôi
    assert pin(client, h, tid, pid, False).json() == {"pinned_place_ids": []}


def test_pin_place_not_in_latest_is_422(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    other = add_place(conn, name="Không có trong lịch")
    r = pin(client, h, tid, other)
    assert r.status_code == 422 and "đang có trong lịch trình" in r.json()["detail"]


def test_get_old_version_and_missing_version(client, conn, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    other = add_place(conn, name="Cafe rẻ", kind="cafe")
    use_llm(monkeypatch, [reply(("search_places", {"query": "cafe rẻ"})),
                          reply(("edit_itinerary", {"summary": "rẻ hơn", "ops": [
                              {"op": "replace_stop", "day": 1, "stop": 1, "place_id": other}]}))])
    events(client.post("/trips", json={"message": "rẻ hơn", "trip_id": tid}, headers=h))
    v1 = client.get(f"/trips/{tid}?version=1", headers=h).json()
    assert v1["version"] == 1 and v1["versions"] == [1, 2]
    assert v1["itinerary"]["days"][0]["stops"][0]["place_id"] == pid
    assert client.get(f"/trips/{tid}?version=9", headers=h).status_code == 404


def test_get_trip_without_itinerary(client, conn, monkeypatch):
    use_llm(monkeypatch, [reply(("record_trip", {"destination": "da-lat", "days": 1, "budget": 2_000_000}))])
    h = auth(client)
    tid = events(client.post("/trips", json={"message": "Đà Lạt 1 ngày"}, headers=h))[-1]["trip_id"]
    got = client.get(f"/trips/{tid}", headers=h).json()
    assert (got["itinerary"], got["versions"], got["pinned_place_ids"]) == (None, [], [])
    assert client.get("/trips", headers=h).json()[0]["destination_name"] == "da-lat"


def test_pins_other_user_404(client, conn, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    assert pin(client, auth(client, "binh@example.com"), tid, pid).status_code == 404
```

(`add_place` tạo Destination với `name = slug`, `lat=11.94, lon=108.44`, nên `destination_name == "da-lat"` và `center == [108.44, 11.94]`.)

- [ ] **Step 3: Chạy để thấy lỗi**

Run: `cd server && uv run pytest tests/test_versions_api.py -v`
Expected: FAIL (404 cho `/pins`, thiếu khoá `versions`)

- [ ] **Step 4: Schema** — thêm vào cuối `server/app/schema.sql`

```sql
-- Pinned Stop: thuộc Trip, không thuộc version; gán vào stop.pinned khi đọc (spec revision-day-du §2 D2)
ALTER TABLE trips ADD COLUMN IF NOT EXISTS pinned_place_ids integer[] NOT NULL DEFAULT '{}';
```

- [ ] **Step 5: `load_itinerary` + `get_trip`/`list_trips`** — trong `server/app/trips.py` thay `latest_itinerary` bằng:

```python
def load_itinerary(conn, trip_id: int, version: int | None = None) -> tuple[int, Itinerary, dict] | None:
    """Đọc một version (mặc định bản mới nhất); stop.pinned lấy từ trips.pinned_place_ids, không từ data đã lưu."""
    row = conn.execute(
        """SELECT i.version, i.data, t.pinned_place_ids FROM itineraries i JOIN trips t ON t.id = i.trip_id
           WHERE i.trip_id = %s AND (%s::int IS NULL OR i.version = %s) ORDER BY i.version DESC LIMIT 1""",
        (trip_id, version, version)).fetchone()
    if not row:
        return None
    itin = Itinerary.model_validate(row["data"]["itinerary"])
    pins = set(row["pinned_place_ids"])
    for d in itin.days:
        for s in d.stops:
            s.pinned = s.place_id in pins
    return row["version"], itin, row["data"]["places"]


def latest_itinerary(conn, trip_id: int) -> tuple[int, Itinerary] | None:
    r = load_itinerary(conn, trip_id)
    return (r[0], r[1]) if r else None
```

Thay `list_trips` và `get_trip`:

```python
@router.get("/trips")
def list_trips(user_id: int = Depends(current_user), conn=Depends(get_conn)):
    return conn.execute(
        """SELECT t.id, t.spec, t.created_at, d.name AS destination_name
           FROM trips t LEFT JOIN destinations d ON d.slug = t.spec->>'destination'
           WHERE t.user_id = %s ORDER BY t.id DESC""", (user_id,)).fetchall()


@router.get("/trips/{trip_id}")
def get_trip(trip_id: int, version: int | None = None, user_id: int = Depends(current_user),
             conn=Depends(get_conn)):
    trip = conn.execute("SELECT id, spec, pinned_place_ids FROM trips WHERE id = %s AND user_id = %s",
                        (trip_id, user_id)).fetchone()
    if not trip:
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    it = load_itinerary(conn, trip_id, version)
    if version is not None and not it:
        raise HTTPException(404, "Không tìm thấy phiên bản lịch trình")
    versions = [r["version"] for r in conn.execute(
        "SELECT version FROM itineraries WHERE trip_id = %s ORDER BY version", (trip_id,)).fetchall()]
    dest = next(d for d in list_destinations(conn) if d["slug"] == trip["spec"]["destination"])
    return {"trip_id": trip["id"], "trip": trip["spec"], "center": [dest["lon"], dest["lat"]],
            "version": it[0] if it else None,
            "itinerary": it[1].model_dump(mode="json") if it else None,
            "places": it[2] if it else {}, "versions": versions, "pinned_place_ids": trip["pinned_place_ids"]}
```

- [ ] **Step 6: Router ghim** — tạo `server/app/versions.py`

```python
"""Pinned Stop, lịch sử chat, quay lại version cũ (spec revision-day-du §3.5)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import current_user
from app.db import get_conn
from app.trips import latest_itinerary

router = APIRouter()


def _own(conn, trip_id: int, user_id: int) -> dict:
    row = conn.execute("SELECT id, spec, pinned_place_ids FROM trips WHERE id = %s AND user_id = %s",
                       (trip_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    return row


class PinIn(BaseModel):
    place_id: int
    pinned: bool


@router.patch("/trips/{trip_id}/pins")
def set_pin(trip_id: int, body: PinIn, user_id: int = Depends(current_user), conn=Depends(get_conn)):
    _own(conn, trip_id, user_id)
    if body.pinned:
        latest = latest_itinerary(conn, trip_id)
        if not latest or body.place_id not in {s.place_id for d in latest[1].days for s in d.stops}:
            raise HTTPException(422, "Chỉ ghim được Stop đang có trong lịch trình mới nhất")
        sql = "array_append(array_remove(pinned_place_ids, %(p)s), %(p)s)"
    else:
        sql = "array_remove(pinned_place_ids, %(p)s)"
    row = conn.execute(f"UPDATE trips SET pinned_place_ids = {sql} WHERE id = %(t)s RETURNING pinned_place_ids",
                       {"p": body.place_id, "t": trip_id}).fetchone()
    return {"pinned_place_ids": row["pinned_place_ids"]}
```

Trong `server/app/main.py`: sửa `from app import auth, proposals, trips` thành `from app import auth, proposals, trips, versions` và thêm `app.include_router(versions.router)` sau dòng `proposals.router`.

- [ ] **Step 7: Disruption đọc qua `load_itinerary`** — trong `server/app/proposals.py`, thêm `load_itinerary` vào import `from app.trips import ...`, rồi thay đoạn đọc `row` và `itin`:

```python
    loaded = load_itinerary(conn, trip_id, body.version)
    if not loaded:
        raise HTTPException(404, "Không tìm thấy phiên bản lịch trình")
    if body.version != _latest_version(conn, trip_id):
        raise HTTPException(409, STALE)
    itin = loaded[1]
```

(Xoá dòng `itin = Itinerary.model_validate(row["data"]["itinerary"])` cũ. Nếu `Itinerary` không còn dùng trong file thì bỏ khỏi import.)

- [ ] **Step 8: Sửa `seed` trong `test_disruptions_api.py`** để ghim bằng cột mới (data đã lưu không còn quyết định ghim). Sau `save_itinerary(...)` thêm:

```python
    if pinned:
        conn.execute("UPDATE trips SET pinned_place_ids = %s WHERE id = %s", ([cafe], tid))
```

và bỏ `"pinned": pinned` khỏi dict Stop đầu tiên.

- [ ] **Step 9: Chạy toàn bộ test server**

Run: `cd server && uv run pytest -q`
Expected: tất cả PASS (151 cũ + 6 mới)

- [ ] **Step 10: Commit**

```bash
git add server/app/schema.sql server/app/trips.py server/app/proposals.py server/app/versions.py server/app/main.py server/tests/test_versions_api.py server/tests/test_disruptions_api.py
git commit -m "feat(server): Pinned Stop thuộc Trip + xem version bất kỳ (#25, #24)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Lập lại phải giữ Place đã ghim

**Files:**
- Modify: `server/app/rules.py:68-85` (`_check_draft`, `build_itinerary`)
- Modify: `server/app/agent.py:237-284` (`previous_brief`, `plan`)
- Test: `server/tests/test_rules.py`, `server/tests/test_plan.py`, `server/tests/test_versions_api.py`

**Interfaces:**
- Consumes: `latest_itinerary` đã gán pinned (Task 1). `_replan` trong `trips.py` đã truyền `previous = (latest[1], ...)` nên `plan` thấy `stop.pinned`.
- Produces: `build_itinerary(trip, draft, places, rain=None, hub=None, pinned: frozenset[int] | set[int] = frozenset()) -> Itinerary`; thiếu Place ghim thì raise `InvalidDraft("Thiếu Place đã ghim: [ids]")`.

- [ ] **Step 1: Viết test lỗi**

Thêm vào `server/tests/test_rules.py` (dùng các import sẵn có trong file; nếu thiếu thì thêm `from app.domain import Draft, Trip`, `from app.rules import InvalidDraft, build_itinerary`, `import pytest`):

```python
def test_draft_missing_pinned_place_is_rejected():
    # cần import ở đầu file: from app.domain import Place
    p = Place(id=1, destination="da-lat", name="A", kind="cafe", lat=11.94, lon=108.44, price=0,
              open_hours={}, outdoor=False, tags=[])
    trip = Trip(destination="da-lat", days=1, budget=1_000_000, travel_mode="grab")
    draft = Draft.model_validate({"summary": "", "days": [{"stops": [
        {"place_id": 1, "start_time": "09:00", "duration_min": 60}]}]})
    with pytest.raises(InvalidDraft, match="Thiếu Place đã ghim"):
        build_itinerary(trip, draft, {1: p}, pinned={1, 7})
    assert build_itinerary(trip, draft, {1: p}, pinned={1}).days[0].stops[0].place_id == 1
```

Thêm vào `server/tests/test_plan.py`:

```python
def test_plan_rejects_draft_dropping_pinned_place_then_retries(conn):
    # cần thêm ở đầu file: from app.domain import Draft · from app.places import get_places · from app.rules import build_itinerary
    a, b = add_place(conn, name="Cafe ghim", kind="cafe"), add_place(conn, name="Hồ", vec=1)
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, travel_mode="grab")
    places = get_places(conn, [a, b])
    old = build_itinerary(trip, Draft.model_validate(stops(a)), places)
    old.days[0].stops[0].pinned = True
    client = FakeClient([reply(("submit_itinerary", stops(b))), reply(("submit_itinerary", stops(a, b)))])
    events = list(plan(conn, client, "m", trip, fake_embed, None, previous=(old, places)))
    assert "Thiếu Place đã ghim" in tool_messages(client)[0]
    assert [s["place_id"] for s in events[-1]["itinerary"]["days"][0]["stops"]] == [a, b]
    assert "đã ghim" in client.calls[0]["messages"][1]["content"]
```

Thêm vào `server/tests/test_versions_api.py` (Review Focus 1):

```python
def test_replan_keeps_pinned_place(client, conn, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    pin(client, h, tid, pid)
    other = add_place(conn, name="Hồ", vec=1)
    fake_calls = [reply(("search_places", {"query": "hồ"})),
                  reply(("submit_itinerary", {"summary": "không ghim", "days": [{"stops": [
                      {"place_id": other, "start_time": "09:00", "duration_min": 60}]}]})),
                  reply(("submit_itinerary", {"summary": "có ghim", "days": [{"stops": [
                      {"place_id": pid, "start_time": "09:00", "duration_min": 60},
                      {"place_id": other, "start_time": "11:00", "duration_min": 60}]}]}))]
    use_llm(monkeypatch, fake_calls)
    evs = events(client.post(f"/trips/{tid}/replan", headers=h,
                             json={"changes": {"budget": 3_000_000}, "message": "3 triệu"}))
    assert evs[-1]["type"] == "itinerary" and evs[-1]["itinerary"]["summary"] == "có ghim"
    got = client.get(f"/trips/{tid}", headers=h).json()
    assert got["itinerary"]["days"][0]["stops"][0]["pinned"] is True
```

- [ ] **Step 2: Chạy để thấy lỗi**

Run: `cd server && uv run pytest tests/test_rules.py::test_draft_missing_pinned_place_is_rejected tests/test_plan.py::test_plan_rejects_draft_dropping_pinned_place_then_retries tests/test_versions_api.py::test_replan_keeps_pinned_place -v`
Expected: FAIL (`unexpected keyword argument 'pinned'`, và replan trả "không ghim")

- [ ] **Step 3: `rules.py`** — thêm tham số và kiểm tra:

```python
def _check_draft(trip: Trip, draft: Draft, places: dict[int, Place], pinned=frozenset()) -> None:
    ids = {s.place_id for d in draft.days for s in d.stops}
    missing = sorted(set(pinned) - ids)
    if missing:
        raise InvalidDraft(f"Thiếu Place đã ghim: {missing} — phải giữ các Place này trong lịch")
    if draft.stay_place_id is not None:
        ids.add(draft.stay_place_id)
    # ... phần còn lại giữ nguyên
```

(Kiểm tra `missing` trước khi thêm `stay_place_id` vào `ids`, vì chỗ ở không phải Stop.)

```python
def build_itinerary(trip: Trip, draft: Draft, places: dict[int, Place],
                    rain: list[int | None] | None = None, hub: Hub | None = None, pinned=frozenset()) -> Itinerary:
    _check_draft(trip, draft, places, pinned)
```

- [ ] **Step 4: `agent.py`** — trong `previous_brief`, đánh dấu Stop đã ghim:

```python
    for i, d in enumerate(itin.days):
        lines.append(f"- Ngày {i + 1}: " + "; ".join(
            f"{s.start_time} {places[s.place_id].name} (place_id {s.place_id})"
            + (" 📌 đã ghim — BẮT BUỘC giữ" if s.pinned else "") for s in d.stops))
```

Trong `plan`, ngay sau dòng `seen: dict[int, Place] = ...`:

```python
    pinned = {s.place_id for d in previous[0].days for s in d.stops if s.pinned} if previous else set()
```

và đổi lời gọi thành `itin = build_itinerary(trip, Draft.model_validate(args), seen, rain, hub, pinned)`.

- [ ] **Step 5: Chạy toàn bộ test server**

Run: `cd server && uv run pytest -q`
Expected: tất cả PASS

- [ ] **Step 6: Commit**

```bash
git add server/app/rules.py server/app/agent.py server/tests/test_rules.py server/tests/test_plan.py server/tests/test_versions_api.py
git commit -m "feat(server): lập lại lịch phải giữ Place đã ghim (#25)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Lịch sử chat (`messages`)

**Files:**
- Modify: `server/app/schema.sql`
- Modify: `server/app/trips.py` (`log_message` mới; gọi trong `_run`, `_plan_and_save`, `_follow_up`)
- Modify: `server/app/proposals.py` (`apply_proposal`)
- Modify: `server/app/versions.py` (`GET /trips/{id}/messages`)
- Test: `server/tests/test_versions_api.py`

**Interfaces:**
- Produces:
  - `trips.log_message(conn, trip_id: int, role: str, text: str, version: int | None = None) -> None`.
  - `GET /trips/{id}/messages` trả `[{role: "user"|"ai", text, version: int|null, created_at}]` theo thứ tự ghi.

- [ ] **Step 1: Viết test lỗi** — thêm vào `server/tests/test_versions_api.py`

```python
def history(client, h, tid):
    return [(m["role"], m["text"], m["version"]) for m in client.get(f"/trips/{tid}/messages", headers=h).json()]


def test_messages_record_conversation_in_order(client, conn, monkeypatch):
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    use_llm(monkeypatch, [reply(("answer", {"text": "0 km"}))])
    events(client.post("/trips", json={"message": "bao xa?", "trip_id": tid}, headers=h))
    other = add_place(conn, name="Cafe rẻ", kind="cafe")
    use_llm(monkeypatch, [reply(("search_places", {"query": "cafe rẻ"})),
                          reply(("edit_itinerary", {"summary": "Đổi quán rẻ", "ops": [
                              {"op": "replace_stop", "day": 1, "stop": 1, "place_id": other}]}))])
    events(client.post("/trips", json={"message": "rẻ hơn", "trip_id": tid}, headers=h))
    assert history(client, h, tid) == [("user", "x", None), ("ai", "ok", 1),
                                       ("user", "bao xa?", None), ("ai", "0 km", None),
                                       ("user", "rẻ hơn", None), ("ai", "Đổi quán rẻ", 2)]


def test_messages_other_user_404(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    assert client.get(f"/trips/{tid}/messages", headers=auth(client, "binh@example.com")).status_code == 404
```

Thêm vào `server/tests/test_disruptions_api.py`:

```python
def test_apply_logs_message(client, conn):
    h, tid = seed(conn, client)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0})
    client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0})  # idempotent: không ghi lần 2
    rows = conn.execute("SELECT role, text, version FROM messages WHERE trip_id = %s", (tid,)).fetchall()
    assert [(r["role"], r["version"]) for r in rows] == [("ai", 2)]
    assert "bản 2" in rows[0]["text"]
```

- [ ] **Step 2: Chạy để thấy lỗi**

Run: `cd server && uv run pytest tests/test_versions_api.py tests/test_disruptions_api.py::test_apply_logs_message -v`
Expected: FAIL (bảng `messages` chưa có)

- [ ] **Step 3: Schema** — thêm vào `server/app/schema.sql`

```sql
-- Lịch sử chat theo Trip để mở lại thấy hội thoại (#17); không lưu thinking/tool_call/clarify/error
CREATE TABLE IF NOT EXISTS messages (
  id serial PRIMARY KEY,
  trip_id integer NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user', 'ai')),
  text text NOT NULL,
  version integer,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_trip ON messages(trip_id, id);
```

- [ ] **Step 4: `log_message` và các chỗ gọi trong `trips.py`**

Thêm ngay dưới `save_itinerary`:

```python
def log_message(conn, trip_id: int, role: str, text: str, version: int | None = None) -> None:
    conn.execute("INSERT INTO messages(trip_id, role, text, version) VALUES (%s, %s, %s, %s)",
                 (trip_id, role, text, version))
```

Trong `_plan_and_save`, trong nhánh `if ev["type"] == "itinerary":` sau dòng `version = ...`:

```python
            log_message(conn, trip_id, "ai", ev["itinerary"]["summary"], version)
```

Trong `_follow_up`, sửa hai nhánh:

```python
        if ev["type"] == "confirm_replan":
            conn.execute(...)  # giữ nguyên
            log_message(conn, prev["id"], "ai", ev["text"])
            ev = {**ev, "trip_id": prev["id"]}
        elif ev["type"] == "itinerary":
            version = save_itinerary(conn, prev["id"], ev["itinerary"], ev["places"])
            log_message(conn, prev["id"], "ai", ev["itinerary"]["summary"], version)
            conn.execute(...)  # giữ nguyên
            ev = {**ev, "trip_id": prev["id"], "version": version}
        elif ev["type"] == "answer":
            log_message(conn, prev["id"], "ai", ev["text"])
```

Trong `_run`:
- Nhánh `if latest:`, trước `yield from _follow_up(...)`, thêm `log_message(conn, prev["id"], "user", message)`.
- Sau khối `if prev: ... else: trip_id = ...` (trước `yield _trip_event(...)`), thêm `log_message(conn, trip_id, "user", message)`.

- [ ] **Step 5: `apply_proposal`** — trong `server/app/proposals.py`, thêm `log_message` vào import từ `app.trips`. Trong nhánh `else:` sau `conn.execute("UPDATE proposals SET chosen_index ...")`, thêm:

```python
            log_message(conn, trip_id, "ai", f"Đã áp dụng phương án — lịch trình bản {version}.", version)
```

- [ ] **Step 6: API** — thêm vào `server/app/versions.py`

```python
@router.get("/trips/{trip_id}/messages")
def get_messages(trip_id: int, user_id: int = Depends(current_user), conn=Depends(get_conn)):
    _own(conn, trip_id, user_id)
    return conn.execute("SELECT role, text, version, created_at FROM messages WHERE trip_id = %s ORDER BY id",
                        (trip_id,)).fetchall()
```

- [ ] **Step 7: Chạy toàn bộ test server**

Run: `cd server && uv run pytest -q`
Expected: tất cả PASS

- [ ] **Step 8: Commit**

```bash
git add server/app/schema.sql server/app/trips.py server/app/proposals.py server/app/versions.py server/tests/test_versions_api.py server/tests/test_disruptions_api.py
git commit -m "feat(server): lưu lịch sử chat theo Trip + GET /trips/{id}/messages (#17)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: "Quay lại bản này" (restore)

**Files:**
- Modify: `server/app/versions.py`
- Test: `server/tests/test_versions_api.py`, `server/tests/test_disruptions_api.py`

**Interfaces:**
- Consumes: `load_itinerary`, `itinerary_places`, `hub_for`, `save_itinerary`, `log_message` (`app.trips`); `to_draft` (`app.replan`); `build_itinerary` (`app.rules`); `itinerary_event` (`app.agent`).
- Produces: `POST /trips/{id}/restore/{version}` trả `{type: "itinerary", itinerary, places, trip_id, version, pinned_place_ids}`.

- [ ] **Step 1: Viết test lỗi** — thêm vào `server/tests/test_versions_api.py`

```python
def two_versions(client, conn, monkeypatch):
    """v1: Cà phê Tùng · v2: Cafe rẻ."""
    h, tid, pid = trip_with_itinerary(client, conn, monkeypatch)
    other = add_place(conn, name="Cafe rẻ", kind="cafe")
    use_llm(monkeypatch, [reply(("search_places", {"query": "cafe rẻ"})),
                          reply(("edit_itinerary", {"summary": "rẻ", "ops": [
                              {"op": "replace_stop", "day": 1, "stop": 1, "place_id": other}]}))])
    events(client.post("/trips", json={"message": "rẻ hơn", "trip_id": tid}, headers=h))
    return h, tid, pid, other


def test_restore_creates_new_version_and_keeps_all(client, conn, monkeypatch):
    h, tid, pid, other = two_versions(client, conn, monkeypatch)
    pin(client, h, tid, other)
    r = client.post(f"/trips/{tid}/restore/1", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "itinerary" and body["version"] == 3
    assert body["itinerary"]["days"][0]["stops"][0]["place_id"] == pid
    assert body["pinned_place_ids"] == []  # Place ghim không có trong v1 → tự bỏ ghim
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1, 2, 3]
    last = client.get(f"/trips/{tid}/messages", headers=h).json()[-1]
    assert (last["role"], last["version"]) == ("ai", 3)
    assert "bản 1" in last["text"] and "Cafe rẻ" in last["text"]


def test_restore_missing_version_404_other_user_404(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    assert client.post(f"/trips/{tid}/restore/9", headers=h).status_code == 404
    assert client.post(f"/trips/{tid}/restore/1", headers=auth(client, "binh@example.com")).status_code == 404


def test_restore_with_different_day_count_is_422(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    conn.execute("UPDATE trips SET spec = jsonb_set(spec, '{days}', '2') WHERE id = %s", (tid,))
    r = client.post(f"/trips/{tid}/restore/1", headers=h)
    assert r.status_code == 422 and "1 ngày" in r.json()["detail"]
```

Thêm vào `server/tests/test_disruptions_api.py` (Review Focus 2):

```python
def test_apply_old_proposal_after_restore_is_409(client, conn):
    h, tid = seed(conn, client)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    assert client.post(f"/trips/{tid}/restore/1", headers=h).json()["version"] == 2
    r = client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0})
    assert r.status_code == 409
```

- [ ] **Step 2: Chạy để thấy lỗi**

Run: `cd server && uv run pytest tests/test_versions_api.py -k restore tests/test_disruptions_api.py::test_apply_old_proposal_after_restore_is_409 -v`
Expected: FAIL (404/405 vì chưa có route)

- [ ] **Step 3: Viết endpoint** — sửa import đầu `server/app/versions.py` rồi thêm route

```python
from app.agent import itinerary_event
from app.domain import Trip
from app.places import get_places, list_destinations
from app.replan import to_draft
from app.rules import InvalidDraft, build_itinerary
from app.trips import hub_for, itinerary_places, latest_itinerary, load_itinerary, log_message, save_itinerary


@router.post("/trips/{trip_id}/restore/{version}")
def restore(trip_id: int, version: int, user_id: int = Depends(current_user), conn=Depends(get_conn)):
    """Chép bản cũ thành bản mới, tính lại tiền + Conflict theo Trip hiện tại (spec §2 D3–D5)."""
    row = _own(conn, trip_id, user_id)
    old = load_itinerary(conn, trip_id, version)
    if not old:
        raise HTTPException(404, "Không tìm thấy phiên bản lịch trình")
    trip, itin = Trip.model_validate(row["spec"]), old[1]
    if len(itin.days) != trip.days:
        raise HTTPException(422, f"Bản {version} có {len(itin.days)} ngày nhưng chuyến đi hiện là {trip.days} ngày "
                                 "— hãy đổi lại số ngày trước khi quay lại bản này.")
    places = itinerary_places(conn, itin)
    used = {s.place_id for d in itin.days for s in d.stops}
    pins = [p for p in row["pinned_place_ids"] if p in used]
    dropped = get_places(conn, [p for p in row["pinned_place_ids"] if p not in used])
    dest = next(d for d in list_destinations(conn) if d["slug"] == trip.destination)
    try:
        new = build_itinerary(trip, to_draft(itin), places, [d.rain_chance for d in itin.days], hub_for(dest, trip))
    except InvalidDraft as e:  # vd Place trong bản cũ đã bị xoá khỏi dữ liệu
        raise HTTPException(422, f"Không quay lại được bản {version}: {e}") from None
    ev = itinerary_event(new, places)
    with conn.transaction():
        conn.execute("UPDATE trips SET pinned_place_ids = %s WHERE id = %s", (pins, trip_id))
        n = save_itinerary(conn, trip_id, ev["itinerary"], ev["places"])
        text = f"Đã quay lại bản {version} (thành bản {n})."
        if dropped:
            text += " Bỏ ghim: " + ", ".join(p.name for p in dropped.values()) + "."
        log_message(conn, trip_id, "ai", text, n)
    return {**ev, "trip_id": trip_id, "version": n, "pinned_place_ids": pins}
```

(`get_places(conn, [])` dùng `id = ANY('{}')` nên trả `{}`, không cần kiểm tra rỗng.)

- [ ] **Step 4: Chạy toàn bộ test server**

Run: `cd server && uv run pytest -q`
Expected: tất cả PASS

- [ ] **Step 5: Commit**

```bash
git add server/app/versions.py server/tests/test_versions_api.py server/tests/test_disruptions_api.py
git commit -m "feat(server): POST /trips/{id}/restore/{version} — quay lại bản cũ thành bản mới (#24)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Client — API và hàm thuần

**Files:**
- Modify: `client/src/api.ts` (thay `postJSON` bằng `request`; thêm kiểu và hàm)
- Test: `client/src/api.test.ts`

**Interfaces:**
- Produces (dùng ở Task 6):
  - `type TripSummary = { id: number; spec: { destination: string; days: number }; created_at: string; destination_name: string | null }`
  - `type TripView = { trip_id: number; trip: { budget: number }; center: [number, number]; version: number | null; itinerary: Itinerary | null; places: Record<string, Place>; versions: number[]; pinned_place_ids: number[] }`
  - `type Message = { role: 'user' | 'ai'; text: string; version: number | null }`
  - `type RestoreEvent = ItineraryEvent & { pinned_place_ids: number[] }`
  - `listTrips(token): Promise<TripSummary[]>` · `getTrip(token, id, version?): Promise<TripView>` · `getMessages(token, id): Promise<Message[]>` · `setPin(token, tripId, placeId, pinned): Promise<{ pinned_place_ids: number[] }>` · `restoreVersion(token, tripId, version): Promise<RestoreEvent>`
  - `viewingOld(version: number | null, latest: number | null): boolean`
  - `tripLabel(t: TripSummary): string` → ví dụ `"Đà Lạt · 2 ngày · 30/09"`

- [ ] **Step 1: Viết test lỗi** — thêm vào `client/src/api.test.ts` (bổ sung `tripLabel, viewingOld` vào import từ `./api`)

```ts
describe('viewingOld', () => {
  it('chỉ đúng khi đang xem bản khác bản mới nhất', () => {
    expect(viewingOld(1, 3)).toBe(true)
    expect(viewingOld(3, 3)).toBe(false)
    expect(viewingOld(null, 3)).toBe(false)
    expect(viewingOld(1, null)).toBe(false)
  })
})

describe('tripLabel', () => {
  it('tên Destination · số ngày · ngày tạo', () => {
    expect(tripLabel({ id: 1, spec: { destination: 'da-lat', days: 2 }, created_at: '2026-09-30T12:00:00+07:00',
      destination_name: 'Đà Lạt' })).toBe('Đà Lạt · 2 ngày · 30/09')
  })
  it('thiếu tên thì dùng slug', () => {
    expect(tripLabel({ id: 1, spec: { destination: 'da-lat', days: 1 }, created_at: '2026-01-05T00:00:00Z',
      destination_name: null }).startsWith('da-lat · 1 ngày')).toBe(true)
  })
})
```

- [ ] **Step 2: Chạy để thấy lỗi**

Run: `cd client && npx vitest run src/api.test.ts`
Expected: FAIL (`viewingOld is not exported`)

- [ ] **Step 3: Cài đặt** — trong `client/src/api.ts`, thay hàm `postJSON` bằng:

```ts
async function request<T>(token: string, path: string, method = 'GET', body?: unknown): Promise<T> {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (r.status === 401) throw new Error('unauthorized')
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Lỗi máy chủ (${r.status})`)
  return data as T
}
```

Sửa hai hàm đang gọi `postJSON`:

```ts
export const reportDisruption = (token: string, tripId: number, version: number, kind: DisruptionKind,
  dayIndex: number, stopIndex: number) =>
  request<Proposal>(token, `/trips/${tripId}/disruptions`, 'POST',
    { version, kind, day_index: dayIndex, stop_index: stopIndex })

export const applyProposal = (token: string, tripId: number, proposalId: number, option: number) =>
  request<ItineraryEvent>(token, `/trips/${tripId}/proposals/${proposalId}/apply`, 'POST', { option })
```

Thêm vào cuối file:

```ts
export type TripSummary = {
  id: number; spec: { destination: string; days: number }; created_at: string; destination_name: string | null
}
export type TripView = {
  trip_id: number; trip: { budget: number }; center: [number, number]; version: number | null
  itinerary: Itinerary | null; places: Record<string, Place>; versions: number[]; pinned_place_ids: number[]
}
export type Message = { role: 'user' | 'ai'; text: string; version: number | null }
export type RestoreEvent = ItineraryEvent & { pinned_place_ids: number[] }

export const listTrips = (token: string) => request<TripSummary[]>(token, '/trips')
export const getTrip = (token: string, id: number, version?: number) =>
  request<TripView>(token, `/trips/${id}` + (version != null ? `?version=${version}` : ''))
export const getMessages = (token: string, id: number) => request<Message[]>(token, `/trips/${id}/messages`)
export const setPin = (token: string, tripId: number, placeId: number, pinned: boolean) =>
  request<{ pinned_place_ids: number[] }>(token, `/trips/${tripId}/pins`, 'PATCH', { place_id: placeId, pinned })
export const restoreVersion = (token: string, tripId: number, version: number) =>
  request<RestoreEvent>(token, `/trips/${tripId}/restore/${version}`, 'POST', {})

/** Đang xem một bản cũ (chỉ đọc) chứ không phải bản mới nhất. */
export const viewingOld = (version: number | null, latest: number | null) =>
  version != null && latest != null && version !== latest

export function tripLabel(t: TripSummary): string {
  const d = new Date(t.created_at)
  const dd = String(d.getDate()).padStart(2, '0'), mm = String(d.getMonth() + 1).padStart(2, '0')
  return `${t.destination_name ?? t.spec.destination} · ${t.spec.days} ngày · ${dd}/${mm}`
}
```

- [ ] **Step 4: Chạy test + build**

Run: `cd client && npm test && npm run build`
Expected: PASS, build OK

- [ ] **Step 5: Commit**

```bash
git add client/src/api.ts client/src/api.test.ts
git commit -m "feat(client): API ghim / version / lịch sử chat / danh sách Trip

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Client — mở lại Trip, danh sách Trip, đăng xuất, dãy version, ghim

**Files:**
- Modify: `client/src/App.tsx`
- Modify: `client/src/components/ChatPanel.tsx`
- Modify: `client/src/components/Timeline.tsx`

**Interfaces:**
- Consumes: mọi thứ Task 5 Produces.
- Produces: props mới:
  - `ChatPanel`: `trips: TripSummary[]`, `onOpenTrip: (id: number) => void`, `onLogout: () => void`.
  - `Timeline`: `versions: number[]`, `version: number | null`, `latest: number | null`, `pins: number[]`, `onView: (v: number) => void`, `onRestore: () => void`, `onPin: (placeId: number, pinned: boolean) => void`.

Logic trong phần này đều nằm ở các hàm thuần đã test ở Task 5 (`viewingOld`, `tripLabel`). Task 6 chỉ nối dây, kiểm chứng bằng build và E2E ở Step 5.

- [ ] **Step 1: `ChatPanel.tsx`** — thêm props và phần đầu panel

```tsx
import { useState, type ReactNode } from 'react'
import { tripLabel, type TripSummary } from '../api'
```

Đổi chữ ký:

```tsx
export default function ChatPanel({ items, busy, onSend, onNewTrip, trips, onOpenTrip, onLogout, children }: {
  items: ChatItem[]; busy: boolean; onSend: (message: string) => void; onNewTrip?: () => void
  trips: TripSummary[]; onOpenTrip: (id: number) => void; onLogout: () => void; children?: ReactNode
}) {
```

Thay khối tiêu đề `<div className="flex items-center justify-between p-4">…</div>` bằng:

```tsx
      <div className="flex items-center justify-between gap-2 p-4">
        <h1 className="text-xl font-semibold">Travility</h1>
        <div className="flex items-center gap-2">
          {onNewTrip && (
            <button disabled={busy} onClick={onNewTrip}
              className="rounded-lg border border-stone-300 px-3 py-1 text-sm disabled:opacity-50">＋ Chuyến mới</button>
          )}
          <button onClick={onLogout} className="text-xs text-stone-500 hover:underline">Đăng xuất</button>
        </div>
      </div>
      {trips.length > 0 && (
        <details className="mx-4 mb-2 text-sm">
          <summary className="cursor-pointer text-stone-600">Chuyến đi của tôi ({trips.length})</summary>
          <ul className="mt-1 max-h-48 space-y-1 overflow-y-auto">
            {trips.map((t) => (
              <li key={t.id}>
                <button disabled={busy} onClick={() => onOpenTrip(t.id)}
                  className="w-full rounded px-2 py-1 text-left hover:bg-stone-100 disabled:opacity-50">
                  {tripLabel(t)}
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
```

- [ ] **Step 2: `Timeline.tsx`** — thêm props, dãy version, banner, nút ghim

Đổi import và chữ ký:

```tsx
import { intentChips, mealOf, viewingOld, vnd, type DisruptionKind, type Itinerary, type Place } from '../api'

export default function Timeline({ itinerary, places, budget, busy = false, changed = [], onDisrupt,
  versions = [], version = null, latest = null, pins = [], onView, onRestore, onPin, children }: {
  itinerary: Itinerary | null; places: Record<string, Place>; budget: number | null; changed?: [number, number][]
  busy?: boolean; onDisrupt?: (kind: DisruptionKind, dayIndex: number, stopIndex: number) => void
  versions?: number[]; version?: number | null; latest?: number | null; pins?: number[]
  onView?: (v: number) => void; onRestore?: () => void; onPin?: (placeId: number, pinned: boolean) => void
  children?: ReactNode
}) {
```

Ngay sau dòng `const stay = ...` thêm `const old = viewingOld(version, latest)`. Ngay sau `{children}` thêm:

```tsx
      {versions.length > 1 && (
        <nav aria-label="Phiên bản lịch trình" className="mb-2 flex flex-wrap items-center gap-1 text-xs">
          {versions.map((v, i) => (
            <span key={v} className="flex items-center gap-1">
              {i > 0 && <span className="text-stone-400">·</span>}
              <button disabled={busy} aria-current={v === version ? 'true' : undefined} onClick={() => onView?.(v)}
                className={`rounded px-1.5 py-0.5 ${v === version ? 'bg-emerald-700 text-white' : 'hover:bg-stone-200'}`}>
                v{v}
              </button>
            </span>
          ))}
        </nav>
      )}
      {old && (
        <div role="status" className="mb-3 flex flex-wrap items-center gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          <span>Đang xem bản {version}</span>
          <button disabled={busy} onClick={onRestore}
            className="rounded bg-amber-600 px-2 py-0.5 text-white disabled:opacity-50">Quay lại bản này</button>
          <button disabled={busy} onClick={() => latest != null && onView?.(latest)}
            className="rounded border border-amber-600 px-2 py-0.5 disabled:opacity-50">Về bản mới nhất</button>
        </div>
      )}
```

Trong vòng lặp Stop, thêm `const pinned = pins.includes(s.place_id)` cạnh `const meal`. Đổi class của `<li>` để Stop ghim có nền nhạt:

```tsx
              <li key={j} className={`rounded-lg p-3 text-sm shadow-sm ${pinned ? 'bg-emerald-50' : 'bg-white'} ${
                changed.some(([d, k]) => d === i && k === j) ? 'ring-2 ring-amber-400' : ''}`}>
```

Thay khối `{onDisrupt && (...)}` bằng:

```tsx
                {!old && (onDisrupt || onPin) && (
                  <div className="mt-2 flex gap-2 text-xs">
                    {onPin && (
                      <button type="button" disabled={busy} aria-pressed={pinned}
                        title={pinned ? 'Bỏ ghim' : 'Ghim: AI không được đổi Stop này'}
                        onClick={() => onPin(s.place_id, !pinned)}
                        className={`rounded border px-2 py-0.5 disabled:opacity-40 ${
                          pinned ? 'border-emerald-600 bg-emerald-600 text-white' : 'border-stone-300 hover:bg-stone-100'}`}>
                        📌 {pinned ? 'Đã ghim' : 'Ghim'}
                      </button>
                    )}
                    {onDisrupt && (['closed', 'disliked'] as const).map((k) => (
                      <button key={k} type="button" disabled={busy || pinned}
                        title={pinned ? 'Bỏ ghim để đổi' : undefined}
                        onClick={() => onDisrupt(k, i, j)}
                        className="rounded border border-stone-300 px-2 py-0.5 hover:bg-stone-100 disabled:opacity-40">
                        {k === 'closed' ? 'Báo đóng cửa' : 'Đổi chỗ khác'}
                      </button>
                    ))}
                  </div>
                )}
```

- [ ] **Step 3: `App.tsx`** — nối dây

Import:

```tsx
import { useEffect, useState } from 'react'
import {
  applyProposal, clarifyAfter, confirmAfter, getMessages, getTrip, listTrips, optionPlace, reportDisruption,
  restoreVersion, setPin, streamPlan, streamReplan, streamTrip, viewingOld,
  type AgentEvent, type Answers, type Clarify, type ConfirmReplan, type DisruptionKind, type Itinerary,
  type ItineraryEvent, type Place, type Proposal, type TripSummary,
} from './api'
```

Thêm state sau `changed`:

```tsx
  const [versions, setVersions] = useState<number[]>([])
  const [latest, setLatest] = useState<number | null>(null)  // bản mới nhất; `version` là bản đang xem
  const [pins, setPins] = useState<number[]>([])
  const [trips, setTrips] = useState<TripSummary[]>([])
```

Tải danh sách và mở Trip gần nhất sau khi đăng nhập. Đặt **trước** dòng `if (!token) return <Login …/>`, vì hook không được đứng sau một lệnh return có điều kiện:

```tsx
  useEffect(() => {
    if (!token) return
    listTrips(token).then((ts) => {
      setTrips(ts)
      if (ts.length > 0) openTrip(ts[0].id)
    }).catch(() => { /* server chưa chạy → giữ empty state, lỗi sẽ hiện khi gửi tin */ })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])
```

Thêm các hàm sau hàm `call` (khai báo bằng `function` để hoisting cho `useEffect` gọi được):

```tsx
  function showView(v: { itinerary: Itinerary | null; places: Record<string, Place>; version: number | null }) {
    setItinerary(v.itinerary); setPlaces(v.places); setVersion(v.version); setChanged([])
    setProposal(null); setSearchPins([])
  }

  async function openTrip(id: number, withChat = true) {
    const t = await call(() => getTrip(token!, id))
    if (!t) return
    setTripId(id); setCenter(t.center); setBudget(t.trip.budget); setClarify(null); setConfirm(null)
    setVersions(t.versions); setLatest(t.version); setPins(t.pinned_place_ids)
    showView(t)
    if (withChat) {
      const ms = await call(() => getMessages(token!, id))
      setChat((ms ?? []).map(({ role, text }) => ({ role, text })))
    }
  }

  const viewVersion = async (v: number) => {
    const t = await call(() => getTrip(token!, tripId!, v))
    if (t) showView(t)
  }

  const restore = async () => {
    const ev = await call(() => restoreVersion(token!, tripId!, version!))
    if (!ev) return
    setVersions((vs) => [...vs, ev.version]); setLatest(ev.version); setPins(ev.pinned_place_ids)
    showView(ev)
    add({ role: 'ai', text: `Đã quay lại bản ${version} (thành bản ${ev.version}).` })
  }

  const pin = async (placeId: number, pinned: boolean) => {
    const r = await call(() => setPin(token!, tripId!, placeId, pinned))
    if (r) setPins(r.pinned_place_ids)
  }

  const logout = () => { saveToken(null); setToken(null); newTrip(); setTrips([]) }
```

Sửa `handle`:
- Case `'trip'`: thêm `if (e.trip_id !== tripId) { setVersions([]); setPins([]); setLatest(null) }` ở đầu case.
- Case `'itinerary'`: thêm `setLatest(e.version); setVersions((vs) => vs.includes(e.version) ? vs : [...vs, e.version])`.

Trong `apply`, sau `setVersion(ev.version)` thêm:

```tsx
    setLatest(ev.version); setVersions((vs) => [...vs, ev.version])
```

Sửa `send` để quay về bản mới nhất trước khi gửi, và làm mới danh sách Trip sau khi gửi:

```tsx
  const send = async (message: string) => {
    if (viewingOld(version, latest)) await viewVersion(latest!)
    add({ role: 'user', text: message })
    await run((on) => streamTrip(token!, message, tripId, on))
    listTrips(token!).then(setTrips).catch(() => {})
  }
```

Trong `newTrip` thêm `setVersions([]); setLatest(null); setPins([])`.

Truyền props:

```tsx
      <ChatPanel items={chat} busy={busy} onSend={send} onNewTrip={tripId != null ? newTrip : undefined}
        trips={trips} onOpenTrip={(id) => openTrip(id)} onLogout={logout}>
```

```tsx
      <Timeline itinerary={itinerary} places={places} budget={budget} busy={busy} changed={changed}
        onDisrupt={tripId != null && version != null ? disrupt : undefined}
        versions={versions} version={version} latest={latest} pins={pins}
        onView={viewVersion} onRestore={restore} onPin={tripId != null && version != null ? pin : undefined}>
```

- [ ] **Step 4: Test + build**

Run: `cd client && npm test && npm run build`
Expected: PASS, build OK, không có lỗi TypeScript

- [ ] **Step 5: E2E thủ công** (Gemini thật, app desktop)

```bash
docker compose up -d && cd client && npm run build && rm -rf ~/Library/Caches/python3 && cd ../desktop && uv run python main.py
```

Kiểm tra lần lượt:
1. "Đi Đà Lạt 2 ngày, 2 người, 3 triệu, thích cafe chill" → có v1.
2. Ghim một quán cafe → nền xanh, "Đã ghim"; nút "Báo đóng cửa" trên Stop đó bị khoá.
3. "Ngày 2 mưa thì sao?" → v2; quán đã ghim giữ nguyên.
4. "Bớt 500k" → v3 rẻ hơn.
5. Bấm v1 → banner "Đang xem bản 1"; các nút trên Stop ẩn.
6. "Quay lại bản này" → v4 giống v1, chat báo.
7. Đóng app, mở lại → thấy Trip, hội thoại, dãy `v1 · v2 · v3 · v4`.
8. "Chuyến đi của tôi" → mở Trip khác được. "Đăng xuất" → về màn Login.

- [ ] **Step 6: Commit**

```bash
git add client/src/App.tsx client/src/components/ChatPanel.tsx client/src/components/Timeline.tsx
git commit -m "feat(client): mở lại Trip + lịch sử chat, danh sách Trip, đăng xuất, dãy version, ghim Stop (#17 #3 #24 #25)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Tài liệu + đóng issue

**Files:**
- Modify: `docs/2026-09-25-hien-trang-app.md` (§2.2 thêm luồng ghim / restore / messages; §2.4 bỏ các dòng đã xong; §3.3 thêm hàng cho v1·v2, ghim, banner)
- Modify: `docs/ROADMAP.md` (tick mục 3 "Revision, Pinned, version" và mục 1 "Đăng xuất"; bỏ 🟡 ở "Mở lại Trip cũ")
- Modify: `docs/PRD.md` §5.4 (🟡 → ✅ cho các phần đã có), §8 (API mới: `PATCH /trips/{id}/pins`, `POST /trips/{id}/restore/{version}`, `GET /trips/{id}/messages` → đã có)

- [ ] **Step 1: Sửa ba file theo danh sách trên.** Dùng đúng tên endpoint và bảng như trong Task 1–4.
- [ ] **Step 2: Chạy lại toàn bộ test**

Run: `docker compose up -d db && (cd server && uv run pytest -q) && (cd client && npm test && npm run build)`
Expected: PASS hết

- [ ] **Step 3: Commit + PR**

```bash
git add docs/
git commit -m "docs: hiện trạng + ROADMAP sau lát Revision đầy đủ

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push -u origin feat/revision-day-du
gh pr create --title "Revision đầy đủ: ghim, dãy version, lịch sử chat, mở lại Trip" --body "Spec: docs/superpowers/specs/2026-09-30-revision-day-du-design.md

Closes #17, #24, #25. #3: xong danh sách Trip + đăng xuất + mở lại Trip gần nhất; phần rail làm cùng UI mới (#16).

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```
