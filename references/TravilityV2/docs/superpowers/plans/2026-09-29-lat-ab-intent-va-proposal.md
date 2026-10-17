# Lát A + B — Intent và Proposal thay thế Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Timeline hiện Intent + mức giữ mục đích R. Người dùng bấm "Báo đóng cửa" / "Đổi chỗ khác" trên một Stop → nhận tối đa 3 Proposal cùng Intent (code tạo, không LLM) kèm so sánh và giải thích → "Áp dụng" tạo version Itinerary mới.

**Architecture:**
- Intent là bảng ánh xạ Tag → Intent trong `domain.py`. `build_itinerary` tính thêm `intents` + `retention`.
- Engine `replan.py` là hàm thuần. Nó nhận `candidates_fn` (DB: `similar_places` dùng embedding đã lưu), lọc bằng `is_open`/`make_leg`, chấm điểm bằng `score(features)`, rồi dựng Proposal qua `build_itinerary`.
- Router mới `proposals.py` có 2 endpoint JSON và bảng `proposals` (kiêm log feedback).
- Client thêm nút trên thẻ Stop và `ProposalPanel`.

**Tech Stack:** FastAPI, psycopg 3 + pgvector, Pydantic 2, pytest (Postgres Docker); React 19 + TypeScript + Tailwind, vitest.

**Spec:** `docs/superpowers/specs/2026-09-29-revision-giu-muc-dich-design.md` (lát A, B — mục 3, 4, 5, 6). ADR-0006.

**Nhánh:** tạo `feat/revision-giu-muc-dich` từ `docs/revision-giu-muc-dich` trước Task 1: `git checkout -b feat/revision-giu-muc-dich`.

**Chạy test server:** `docker compose up -d db` (một lần), rồi `cd server && uv run pytest …`. **Client:** `cd client && npm test && npm run build`.

## Global Constraints

- Engine thay thế **không gọi LLM** (ADR-0006). Tiền, Leg và Conflict luôn qua `rules.build_itinerary`.
- Mỗi Disruption trả tối đa **3** Proposal. Proposal không trùng Place đã có trong Itinerary hoặc Stay.
- Loại Proposal sinh Conflict cứng mới. Conflict cứng gồm `closed`, `before_arrival`, `after_departure`, `over_budget`.
- Stop đã ghim + `closed`/`disliked` → **422**. `version`/`base_version` không phải bản mới nhất → **409**. Trip của User khác → **404**.
- Áp dụng cùng phương án 2 lần → trả **cùng một version** (idempotent).
- Câu `explanation` ghép từ số liệu và **không chứa ký tự "%"**.
- Toàn bộ chữ cho người dùng bằng tiếng Việt. Thuật ngữ theo CONTEXT.md: Intent, Disruption, Proposal, Intent Retention.
- Bảng `INTENT_LABELS` có ở `server/app/domain.py` và `client/src/api.ts`, **đổi thì đổi cả hai** (giống `MEALS`).
- Không thêm event SSE. Hai endpoint mới là JSON thường.
- Lát B chỉ có Disruption `closed` và `disliked`. `rain`/`late`/`insert` thuộc lát C, D.

## Review Focus

1. **Báo sự cố trên version cũ** (client còn giữ version trước khi áp dụng, hoặc app khác đã tạo version mới) → 409 với câu tiếng Việt, không tạo Proposal. Test: `test_stale_version_409` (Task 5). Client cập nhật `version` sau khi áp dụng (Task 7).
2. **Bấm "Áp dụng" hai lần** (double-click, mạng chậm) → vẫn chỉ một version mới. Test: `test_apply_is_idempotent` (Task 5).
3. **Place bị mất không thuộc Intent nào** (vd chỉ có Tag `gia-re`) → câu giải thích không có cụm "mục đích" rỗng, không có reason code `INTENT_*`. Test: `test_lost_place_without_intent` (Task 4).
4. **Itinerary lưu trước khi có `intents`/`retention`** → mở lại và báo sự cố không lỗi, không hiện chip. Test: `test_old_itinerary_json_still_loads` (Task 1), `intentChips` với Itinerary cũ (Task 2).
5. **Dữ liệu ít (37 Place), không có ứng viên** → trả `no_feasible` với lý do tiếng Việt, UI không hiện panel trống. Test: `test_no_feasible_when_no_same_kind_place` (Task 5), `noFeasibleText` (Task 6).

---

### Task 1: Intent + Intent Retention ở server

**Files:**
- Modify: `server/app/domain.py` (thêm `INTENTS`, `INTENT_LABELS`, `place_intents`, `intent_weights`; thêm 2 trường vào `Itinerary`)
- Modify: `server/app/rules.py` (thêm `intent_retention`, gọi trong `build_itinerary`)
- Test: `server/tests/test_rules.py`

**Interfaces:**
- Produces:
  - `domain.INTENTS: dict[str, tuple[str, ...]]`, `domain.INTENT_LABELS: dict[str, str]`
  - `domain.place_intents(tags: Iterable[str]) -> set[str]`
  - `domain.intent_weights(trip: Trip) -> dict[str, int]`
  - `Itinerary.intents: dict[str, bool]` (mặc định `{}`), `Itinerary.retention: float | None` (mặc định `None`)
  - `rules.intent_retention(trip, itin, places) -> tuple[dict[str, bool], float | None]`

- [ ] **Step 1: Viết test thất bại** — thêm vào cuối `server/tests/test_rules.py`:

```python
from app.domain import Itinerary, intent_weights, place_intents


def test_place_intents_ignores_constraint_tags():
    assert place_intents(["gia-re", "hai-san", "view-dep"]) == {"am-thuc", "thien-nhien"}


def test_intent_weights_required_beats_preferred():
    trip = Trip(destination="da-lat", days=1, budget=1, required_tags=["cafe-chill"],
                preferred_tags=["yen-tinh", "lich-su"])
    assert intent_weights(trip) == {"thu-gian": 2, "van-hoa": 1}


def test_retention_weighted():
    places = {1: P(1, tags=["cafe-chill"]), 2: P(2, tags=["gia-re"])}
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, required_tags=["cafe-chill"],
                preferred_tags=["lich-su"])
    itin = build_itinerary(trip, draft([[1, 2]]), places)
    assert itin.intents == {"thu-gian": True, "van-hoa": False}
    assert itin.retention == 0.67  # 2 / (2 + 1)


def test_retention_none_without_intents():
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, preferred_tags=["gia-re"])
    itin = build_itinerary(trip, draft([[1]]), {1: P(1)})
    assert (itin.intents, itin.retention) == ({}, None)


def test_old_itinerary_json_still_loads():
    itin = Itinerary.model_validate({"stay_place_id": None, "days": [], "total_cost": 0})
    assert (itin.intents, itin.retention) == ({}, None)
```

- [ ] **Step 2: Chạy test, thấy thất bại**

Run: `cd server && uv run pytest tests/test_rules.py -v`
Expected: FAIL, `ImportError: cannot import name 'intent_weights'`

- [ ] **Step 3: Cài đặt** — trong `server/app/domain.py`, ngay sau khối `TAGS = {...}`:

```python
# Intent = lý do lớn của chuyến đi, gom nhiều Tag. gia-dinh, gia-re, sang-trong là ràng buộc, không phải Intent.
INTENTS = {
    "am-thuc": ("an-dia-phuong", "hai-san", "an-chay"),
    "thien-nhien": ("thien-nhien", "view-dep"),
    "van-hoa": ("lich-su", "van-hoa"),
    "thu-gian": ("cafe-chill", "yen-tinh", "lang-man"),
    "vui-choi": ("soi-dong", "dem", "mua-sam", "check-in"),
}
# Khớp INTENT_LABELS ở client/src/api.ts
INTENT_LABELS = {"am-thuc": "Ẩm thực", "thien-nhien": "Thiên nhiên", "van-hoa": "Văn hoá", "thu-gian": "Thư giãn",
                 "vui-choi": "Vui chơi"}


def place_intents(tags) -> set[str]:
    tags = set(tags)
    return {i for i, ts in INTENTS.items() if tags.intersection(ts)}
```

Ngay sau class `Trip` (trước `class TripAnswers`):

```python
def intent_weights(trip: Trip) -> dict[str, int]:
    """Trọng số Intent của Trip: có Tag bắt buộc → 2, chỉ có Tag ưu tiên → 1 (spec D3)."""
    w = {i: 1 for i in place_intents(trip.preferred_tags)}
    w.update({i: 2 for i in place_intents(trip.required_tags)})
    return w
```

Trong class `Itinerary`, thêm sau `summary: str = ""`:

```python
    intents: dict[str, bool] = {}  # Intent của Trip → Itinerary có Stop đáp ứng không
    retention: float | None = None  # Intent Retention R; None khi Trip không có Intent
```

Trong `server/app/rules.py`, sửa dòng import domain thành:

```python
from app.domain import (DEFAULT_TRAVEL_MODE, WEEKDAYS, Conflict, Day, Draft, Hub, Itinerary, Leg, Place, Stop, Trip,
                        intent_weights, place_intents)
```

Trong `build_itinerary`, ngay sau `itin.conflicts = find_conflicts(trip, itin, places)`:

```python
    itin.intents, itin.retention = intent_retention(trip, itin, places)
```

Thêm hàm cuối file:

```python
def intent_retention(trip: Trip, itin: Itinerary, places: dict[int, Place]) -> tuple[dict[str, bool], float | None]:
    """R = Σ wₖ·zₖ / Σ wₖ; zₖ = 1 nếu có Stop mà Place thuộc Intent k."""
    w = intent_weights(trip)
    covered = set().union(*(place_intents(places[s.place_id].tags) for d in itin.days for s in d.stops))
    hit = {i: i in covered for i in w}
    total = sum(w.values())
    return hit, (round(sum(w[i] for i in w if hit[i]) / total, 2) if total else None)
```

- [ ] **Step 4: Chạy test, thấy thành công; chạy cả bộ server**

Run: `cd server && uv run pytest tests/test_rules.py -v && uv run pytest`
Expected: tất cả PASS (106 test cũ + 5 mới)

- [ ] **Step 5: Commit**

```bash
git add server/app/domain.py server/app/rules.py server/tests/test_rules.py
git commit -m "feat(server): Intent + Intent Retention trên Itinerary"
```

---

### Task 2: Chip Intent + R trên Timeline

**Files:**
- Modify: `client/src/api.ts` (kiểu `Itinerary`, `INTENT_LABELS`, `intentChips`, chuyển `vnd` vào đây)
- Modify: `client/src/components/Timeline.tsx`
- Test: `client/src/api.test.ts`

**Interfaces:**
- Consumes: JSON `itinerary.intents`, `itinerary.retention` (Task 1)
- Produces:
  - `api.INTENT_LABELS: Record<string, string>`
  - `api.intentChips(it: Itinerary): { label: string; ok: boolean }[]`
  - `api.vnd(n: number): string`

- [ ] **Step 1: Viết test thất bại** — thêm vào `client/src/api.test.ts` (sửa dòng import đầu file thành `import { clarifyAfter, intentChips, mealOf, toAnswers, type AgentEvent, type Itinerary } from './api'`):

```ts
describe('intentChips', () => {
  const base = { stay_place_id: null, days: [], total_cost: 0, conflicts: [], summary: '' }
  it('mỗi Intent của Trip thành một chip có nhãn tiếng Việt', () => {
    const it = { ...base, intents: { 'thu-gian': true, 'van-hoa': false }, retention: 0.67 } as Itinerary
    expect(intentChips(it)).toEqual([{ label: 'Thư giãn', ok: true }, { label: 'Văn hoá', ok: false }])
  })
  it('Itinerary lưu trước khi có Intent → không có chip', () => {
    expect(intentChips(base as Itinerary)).toEqual([])
  })
})
```

- [ ] **Step 2: Chạy test, thấy thất bại**

Run: `cd client && npm test`
Expected: FAIL, `intentChips is not a function` hoặc lỗi import

- [ ] **Step 3: Cài đặt** — trong `client/src/api.ts`, sửa kiểu `Itinerary`:

```ts
export type Itinerary = {
  stay_place_id: number | null; days: Day[]; total_cost: number; conflicts: Conflict[]; summary: string
  intents?: Record<string, boolean>; retention?: number | null  // thiếu ở Itinerary lưu trước lát A
}
```

Thêm sau hàm `mealOf`:

```ts
export const vnd = (n: number) => n.toLocaleString('vi-VN') + 'đ'

// Khớp INTENT_LABELS ở server/app/domain.py
export const INTENT_LABELS: Record<string, string> = {
  'am-thuc': 'Ẩm thực', 'thien-nhien': 'Thiên nhiên', 'van-hoa': 'Văn hoá', 'thu-gian': 'Thư giãn', 'vui-choi': 'Vui chơi',
}

export function intentChips(it: Itinerary): { label: string; ok: boolean }[] {
  return Object.entries(it.intents ?? {}).map(([k, ok]) => ({ label: INTENT_LABELS[k] ?? k, ok }))
}
```

Trong `client/src/components/Timeline.tsx`: xoá dòng `const vnd = ...`, sửa import thành `import { intentChips, mealOf, vnd, type Itinerary, type Place } from '../api'`. Trong thẻ tổng chi phí, ngay sau dòng `{stay && <div className="mt-1 text-xs">Chỗ ở: {stay.name}</div>}`:

```tsx
        {intentChips(itinerary).length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1 text-xs">
            {intentChips(itinerary).map((c) => (
              <span key={c.label}
                className={`rounded-full px-2 py-0.5 ${c.ok ? 'bg-emerald-100 text-emerald-800' : 'bg-stone-200 text-stone-500'}`}>
                {c.ok ? '✓' : '✗'} {c.label}
              </span>
            ))}
            {itinerary.retention != null && (
              <span className="ml-1 text-stone-500">Giữ mục đích {Math.round(itinerary.retention * 100)}%</span>
            )}
          </div>
        )}
```

- [ ] **Step 4: Chạy test + build**

Run: `cd client && npm test && npm run build`
Expected: test PASS (10), build OK

- [ ] **Step 5: Commit**

```bash
git add client/src/api.ts client/src/api.test.ts client/src/components/Timeline.tsx
git commit -m "feat(client): chip Intent và mức giữ mục đích trên Timeline"
```

---

### Task 3: `similar_places` — ứng viên bằng embedding đã lưu

**Files:**
- Modify: `server/app/places.py`
- Test: `server/tests/test_places.py`

**Interfaces:**
- Produces: `places.similar_places(conn, place_id: int, kind: str, exclude_ids=(), exclude_tags=(), limit: int = 20) -> list[Place]`. Cùng Destination với `place_id`, đúng `kind`, không nằm trong `exclude_ids`, không có Tag trong `exclude_tags`, sắp theo khoảng cách cosine tới embedding của `place_id`. Người gọi phải tự đưa `place_id` vào `exclude_ids`.

- [ ] **Step 1: Viết test thất bại** — thêm vào `server/tests/test_places.py` (sửa import: `from app.places import get_places, list_destinations, search_places, similar_places`):

```python
def test_similar_places_uses_stored_embedding_and_filters(conn):
    lost = add_place(conn, name="Mất", kind="cafe", vec=1)
    far = add_place(conn, name="Xa", kind="cafe", vec=5)
    near = add_place(conn, name="Gần", kind="cafe", vec=1)
    add_place(conn, name="Khác loại", kind="an-uong", vec=1)
    add_place(conn, name="Tránh", kind="cafe", vec=1, tags=["soi-dong"])
    add_place(conn, name="Nơi khác", kind="cafe", vec=1, destination="hoi-an")
    used = add_place(conn, name="Đã dùng", kind="cafe", vec=1)
    got = similar_places(conn, lost, "cafe", exclude_ids=[lost, used], exclude_tags=["soi-dong"])
    assert [p.id for p in got] == [near, far]
```

- [ ] **Step 2: Chạy test, thấy thất bại**

Run: `cd server && uv run pytest tests/test_places.py -v`
Expected: FAIL, `ImportError: cannot import name 'similar_places'`

- [ ] **Step 3: Cài đặt** — thêm vào `server/app/places.py` sau `search_places`:

```python
def similar_places(conn, place_id: int, kind: str, exclude_ids=(), exclude_tags=(), limit: int = 20) -> list[Place]:
    """Place giống place_id theo embedding đã lưu — không gọi API embedding, chạy được khi mất mạng."""
    rows = conn.execute(
        f"""SELECT {COLUMNS} FROM places
            WHERE destination = (SELECT destination FROM places WHERE id = %(id)s)
              AND kind = %(k)s
              AND NOT (id = ANY(%(ids)s::int[]))
              AND NOT (tags && %(ex)s::text[])
            ORDER BY embedding <=> (SELECT embedding FROM places WHERE id = %(id)s)
            LIMIT %(n)s""",
        {"id": place_id, "k": kind, "ids": list(exclude_ids), "ex": list(exclude_tags), "n": limit},
    ).fetchall()
    return [Place.model_validate(r) for r in rows]
```

- [ ] **Step 4: Chạy test**

Run: `cd server && uv run pytest tests/test_places.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/app/places.py server/tests/test_places.py
git commit -m "feat(server): similar_places theo embedding đã lưu"
```

---

### Task 4: Engine thay thế `replan.py` (closed / disliked)

**Files:**
- Modify: `server/app/domain.py` (thêm `Disruption`)
- Create: `server/app/replan.py`
- Test: `server/tests/test_replan.py`

**Interfaces:**
- Consumes: `build_itinerary`, `is_open`, `make_leg`, `haversine_km`, `_minutes`, `vnd` (rules); `intent_weights`, `place_intents`, `INTENT_LABELS` (Task 1)
- Produces:
  - `domain.Disruption(kind: Literal["closed","disliked"], day_index: int >= 0, stop_index: int >= 0)`
  - `replan.InvalidDisruption(Exception)`
  - `replan.NoFeasible(reason_codes: list[str])` — mã: `NO_CANDIDATE`, `NO_OPEN_CANDIDATE`, `NOT_REACHABLE_IN_TIME`, `OVER_BUDGET`, `NEW_CONFLICT`
  - `replan.ProposalOption(itinerary: Itinerary, added: list[Place], changed: list[tuple[int,int]], metrics: dict, reason_codes: list[str], explanation: str)`. `metrics` gồm các khoá `cost_delta`, `travel_min_delta`, `day_end_before`, `day_end_after`, `retention_before`, `retention_after`, `intents_kept`, `intents_lost`, `features`.
  - `replan.features(trip, lost, cand, prev, nxt) -> dict`, `replan.score(f: dict) -> float`
  - `replan.propose(trip, itin, places, disruption, candidates_fn, hub=None, score_fn=score) -> list[ProposalOption] | NoFeasible`, với `candidates_fn(lost: Place, used_ids: set[int]) -> list[Place]`

- [ ] **Step 1: Viết test thất bại** — tạo `server/tests/test_replan.py`:

```python
import pytest

from app.domain import WEEKDAYS, Disruption, Draft, Place, Trip
from app.replan import InvalidDisruption, NoFeasible, propose
from app.rules import build_itinerary

WEEK = {d: ["08:00", "22:00"] for d in WEEKDAYS}
TRIP = Trip(destination="da-lat", days=1, budget=5_000_000, travel_mode="grab",
            preferred_tags=["cafe-chill", "lich-su"])


def P(id, kind="cafe", tags=(), price=0, lat=11.94, hours=None):
    return Place(id=id, destination="da-lat", name=f"P{id}", kind=kind, lat=lat, lon=108.44, price=price,
                 open_hours=WEEK if hours is None else hours, outdoor=False, tags=list(tags))


def setup(stops, trip=TRIP, pinned=()):
    """stops: [(Place, 'HH:MM')] → (places, Itinerary 1 ngày, mỗi Stop 60′)."""
    places = {p.id: p for p, _ in stops}
    draft = Draft.model_validate({"summary": "", "days": [{"stops": [
        {"place_id": p.id, "start_time": t, "duration_min": 60, "pinned": p.id in pinned} for p, t in stops]}]})
    return places, build_itinerary(trip, draft, places)


def cands(*ps, seen=None):
    def fn(lost, used):
        if seen is not None:
            seen.update(used)
        return [p for p in ps if p.id not in used]
    return fn


def closed(stop=0, kind="closed"):
    return Disruption(kind=kind, day_index=0, stop_index=stop)


LOST, MUSEUM = P(1, tags=["cafe-chill"]), P(2, kind="tham-quan", tags=["lich-su"])


def test_same_intent_ranks_first_and_other_stops_untouched():
    places, itin = setup([(LOST, "09:00"), (MUSEUM, "11:00")])
    same, other = P(10, tags=["cafe-chill", "yen-tinh"]), P(11, tags=["check-in"])
    opts = propose(TRIP, itin, places, closed(), cands(other, same))
    assert [o.added[0].id for o in opts] == [10, 11]
    assert opts[0].reason_codes[0] == "INTENT_MATCH"
    assert opts[0].metrics["intents_kept"] == ["thu-gian"]
    assert opts[1].metrics["intents_lost"] == ["thu-gian"]
    assert opts[0].changed == [(0, 0)]
    assert opts[0].itinerary.days[0].stops[1].place_id == 2
    assert "Giữ mục đích Thư giãn" in opts[0].explanation


def test_at_most_three_distinct_and_used_places_excluded():
    places, itin = setup([(LOST, "09:00"), (MUSEUM, "11:00")])
    seen = set()
    opts = propose(TRIP, itin, places, closed(kind="disliked"), cands(*[P(i) for i in range(10, 15)], seen=seen))
    assert seen == {1, 2}
    assert len(opts) == 3
    assert len({o.added[0].id for o in opts}) == 3
    assert "bạn muốn đổi" in opts[0].itinerary.days[0].stops[0].reason


def test_closed_at_that_time_is_skipped():
    places, itin = setup([(LOST, "09:00")])
    late_opener = P(10, hours={d: ["14:00", "22:00"] for d in WEEKDAYS})
    assert propose(TRIP, itin, places, closed(), cands(late_opener)) == NoFeasible(reason_codes=["NO_OPEN_CANDIDATE"])
    opts = propose(TRIP, itin, places, closed(), cands(late_opener, P(11)))
    assert [o.added[0].id for o in opts] == [11]


def test_no_candidate():
    places, itin = setup([(LOST, "09:00")])
    assert propose(TRIP, itin, places, closed(), cands()) == NoFeasible(reason_codes=["NO_CANDIDATE"])


def test_too_far_to_reach_next_stop_in_time():
    places, itin = setup([(MUSEUM, "09:00"), (LOST, "10:05")])
    far = P(10, lat=12.2)  # ~37 km bằng Grab ≈ 90 phút, khoảng trống chỉ 5 phút
    got = propose(TRIP, itin, places, closed(stop=1), cands(far))
    assert got == NoFeasible(reason_codes=["NOT_REACHABLE_IN_TIME"])


def test_new_over_budget_is_rejected():
    trip = Trip(destination="da-lat", days=1, budget=100_000, travel_mode="grab")
    places, itin = setup([(P(1, price=50_000), "09:00")], trip=trip)
    got = propose(trip, itin, places, closed(), cands(P(10, price=500_000)))
    assert got == NoFeasible(reason_codes=["OVER_BUDGET"])


def test_pinned_or_missing_stop_is_invalid():
    places, itin = setup([(LOST, "09:00")], pinned={1})
    with pytest.raises(InvalidDisruption):
        propose(TRIP, itin, places, closed(), cands(P(10)))
    with pytest.raises(InvalidDisruption):
        propose(TRIP, itin, places, closed(stop=5), cands(P(10)))


def test_explanation_from_numbers_without_percent():
    places, itin = setup([(P(1, tags=["cafe-chill"], price=20_000), "09:00")])
    opts = propose(TRIP, itin, places, closed(), cands(P(10, tags=["cafe-chill"], price=50_000)))
    assert opts[0].metrics["cost_delta"] == 30_000
    assert "đắt hơn 30.000đ" in opts[0].explanation
    assert "%" not in opts[0].explanation
    assert "PRICIER" in opts[0].reason_codes


def test_lost_place_without_intent():
    places, itin = setup([(P(1, tags=["gia-re"]), "09:00")])
    opts = propose(TRIP, itin, places, closed(), cands(P(10, tags=["gia-re"])))
    assert not any(c.startswith("INTENT_") for c in opts[0].reason_codes)
    assert "mục đích" not in opts[0].explanation
```

- [ ] **Step 2: Chạy test, thấy thất bại**

Run: `cd server && uv run pytest tests/test_replan.py -v`
Expected: FAIL, `ImportError: cannot import name 'Disruption'`

- [ ] **Step 3: Cài đặt** — trong `server/app/domain.py`, thêm cuối file:

```python
class Disruption(BaseModel):
    """Sự cố người dùng báo trên một Stop. Lát C thêm rain/late, lát D thêm insert."""
    kind: Literal["closed", "disliked"]
    day_index: int = Field(ge=0)
    stop_index: int = Field(ge=0)
```

Tạo `server/app/replan.py`:

```python
"""Engine thay thế theo mục đích (spec 2026-09-29-revision-giu-muc-dich §4, ADR-0006). Code thuần, không gọi LLM."""
from collections.abc import Callable

from pydantic import BaseModel

from app.domain import (DEFAULT_TRAVEL_MODE, INTENT_LABELS, WEEKDAYS, Day, Disruption, Draft, DraftDay, DraftStop, Hub,
                        Itinerary, Place, Trip, intent_weights, place_intents)
from app.rules import _minutes, build_itinerary, haversine_km, is_open, make_leg, vnd

N_OPTIONS = 3
HARD = {"closed", "before_arrival", "after_departure", "over_budget"}
KIND_TEXT = {"closed": "đóng cửa", "disliked": "bạn muốn đổi"}


class InvalidDisruption(Exception):
    pass


class NoFeasible(BaseModel):
    reason_codes: list[str]


class ProposalOption(BaseModel):
    itinerary: Itinerary
    added: list[Place]
    changed: list[tuple[int, int]]  # (day_index, stop_index)
    metrics: dict
    reason_codes: list[str]
    explanation: str


CandidatesFn = Callable[[Place, set[int]], list[Place]]
Point = Place | Hub | None


def to_draft(itin: Itinerary) -> Draft:
    return Draft(stay_place_id=itin.stay_place_id, summary=itin.summary, days=[
        DraftDay(stops=[DraftStop(**s.model_dump(exclude={"est_cost"})) for s in d.stops]) for d in itin.days])


def _leg_min(a: Point, b: Point, trip: Trip) -> int:
    if a is None or b is None:
        return 0
    return make_leg(a, b, trip.travel_mode or DEFAULT_TRAVEL_MODE, trip.travelers).duration_min


def features(trip: Trip, lost: Place, cand: Place, prev: Point, nxt: Point) -> dict:
    """Đặc trưng của một ứng viên — đầu vào chung của score() và ranker ML (lát E2)."""
    w = intent_weights(trip)
    li, ci = place_intents(lost.tags), place_intents(cand.tags)
    lw = sum(w.get(i, 1) for i in li)
    lt, ct = set(lost.tags), set(cand.tags)
    return {
        "intent_overlap": sum(w.get(i, 1) for i in li & ci) / lw if lw else 0.0,
        "tag_jaccard": len(lt & ct) / len(lt | ct) if lt | ct else 0.0,
        "extra_travel_min": (_leg_min(prev, cand, trip) + _leg_min(cand, nxt, trip)
                             - _leg_min(prev, lost, trip) - _leg_min(lost, nxt, trip)),
        "extra_cost_vnd": (cand.price - lost.price) * trip.travelers,
        "price_ratio": cand.price / lost.price if lost.price else 1.0,
        "distance_km_from_lost": round(haversine_km(lost, cand), 2),
        "outdoor": int(cand.outdoor),
    }


def score(f: dict) -> float:
    # Hệ số ước lượng ban đầu; lát E1 chỉnh, lát E2 có thể thay bằng ranker cùng chữ ký.
    return 3 * f["intent_overlap"] + f["tag_jaccard"] - f["extra_travel_min"] / 30 - f["extra_cost_vnd"] / 200_000


def _neighbors(itin: Itinerary, places: dict[int, Place], di: int, si: int, hub: Hub | None) -> tuple[Point, Point]:
    day, last = itin.days[di], len(itin.days) - 1
    stay = places.get(itin.stay_place_id) if itin.stay_place_id is not None else None
    prev = places[day.stops[si - 1].place_id] if si > 0 else (hub if hub and di == 0 else stay)
    nxt = places[day.stops[si + 1].place_id] if si + 1 < len(day.stops) else (hub if hub and di == last else stay)
    return prev, nxt


def _reject(trip: Trip, day: Day, si: int, lost: Place, cand: Place, prev: Point, nxt: Point) -> str | None:
    stop = day.stops[si]
    weekdays = [WEEKDAYS[day.date.weekday()]] if day.date else WEEKDAYS
    if not any(is_open(cand, w, stop.start_time, stop.duration_min) for w in weekdays):
        return "NO_OPEN_CANDIDATE"
    start = _minutes(stop.start_time)
    # Không bắt lịch chặt hơn bản cũ: chỉ loại khi chặng mới vừa vượt khoảng trống vừa dài hơn chặng cũ.
    if si > 0:
        p = day.stops[si - 1]
        need = _leg_min(prev, cand, trip)
        if need > start - (_minutes(p.start_time) + p.duration_min) and need > _leg_min(prev, lost, trip):
            return "NOT_REACHABLE_IN_TIME"
    if si + 1 < len(day.stops):
        need = _leg_min(cand, nxt, trip)
        if need > _minutes(day.stops[si + 1].start_time) - start - stop.duration_min and need > _leg_min(lost, nxt, trip):
            return "NOT_REACHABLE_IN_TIME"
    return None


def _hard(itin: Itinerary) -> set[tuple[str, int | None]]:
    return {(c.kind, c.day_index) for c in itin.conflicts if c.kind in HARD}


def _labels(intents) -> str:
    return ", ".join(INTENT_LABELS[i] for i in sorted(intents))


def _travel_min(itin: Itinerary) -> int:
    return sum(leg.duration_min for d in itin.days for leg in d.legs)


def _day_end(day: Day) -> str:
    m = max(_minutes(s.start_time) + s.duration_min for s in day.stops)
    return f"{m // 60:02d}:{m % 60:02d}"


def _explain(li: set, kept: set, travel_delta: int, cost_delta: int, day_end: str, di: int) -> str:
    parts = []
    if kept:
        parts.append(f"giữ mục đích {_labels(kept)}")
    if li - kept:
        parts.append(f"không còn {_labels(li - kept)}")
    parts.append("thời gian di chuyển như cũ" if travel_delta == 0
                 else f"{'thêm' if travel_delta > 0 else 'bớt'} {abs(travel_delta)} phút di chuyển")
    parts.append("chi phí như cũ" if cost_delta == 0
                 else f"{'đắt hơn' if cost_delta > 0 else 'rẻ hơn'} {vnd(abs(cost_delta))}")
    parts.append(f"ngày {di + 1} kết thúc {day_end}")
    s = "; ".join(parts)
    return s[0].upper() + s[1:] + "."


def _option(trip: Trip, old: Itinerary, new: Itinerary, at: tuple[int, int], lost: Place, cand: Place,
            prev: Point, nxt: Point) -> ProposalOption:
    li = place_intents(lost.tags)
    kept = li & place_intents(cand.tags)
    cost_delta = new.total_cost - old.total_cost
    travel_delta = _travel_min(new) - _travel_min(old)
    di = at[0]
    codes = []
    if li:
        codes.append("INTENT_MATCH" if kept == li else "INTENT_PARTIAL" if kept else "INTENT_LOST")
    if travel_delta > 5:
        codes.append("FARTHER")
    elif travel_delta < -5:
        codes.append("CLOSER")
    if cost_delta > 0:
        codes.append("PRICIER")
    elif cost_delta < 0:
        codes.append("CHEAPER")
    day_end = _day_end(new.days[di])
    metrics = {"cost_delta": cost_delta, "travel_min_delta": travel_delta,
               "day_end_before": _day_end(old.days[di]), "day_end_after": day_end,
               "retention_before": old.retention, "retention_after": new.retention,
               "intents_kept": sorted(kept), "intents_lost": sorted(li - kept),
               "features": features(trip, lost, cand, prev, nxt)}
    return ProposalOption(itinerary=new, added=[cand], changed=[at], metrics=metrics, reason_codes=codes,
                          explanation=_explain(li, kept, travel_delta, cost_delta, day_end, di))


def propose(trip: Trip, itin: Itinerary, places: dict[int, Place], d: Disruption, candidates_fn: CandidatesFn,
            hub: Hub | None = None, score_fn=score) -> list[ProposalOption] | NoFeasible:
    if d.day_index >= len(itin.days) or d.stop_index >= len(itin.days[d.day_index].stops):
        raise InvalidDisruption("Không tìm thấy Stop này trong lịch trình")
    day = itin.days[d.day_index]
    stop = day.stops[d.stop_index]
    if stop.pinned:
        raise InvalidDisruption("Stop đã ghim — bỏ ghim để đổi")
    lost = places[stop.place_id]
    used = {s.place_id for x in itin.days for s in x.stops}
    if itin.stay_place_id is not None:
        used.add(itin.stay_place_id)
    prev, nxt = _neighbors(itin, places, d.day_index, d.stop_index, hub)

    rejected, ok = [], []
    for c in candidates_fn(lost, used):
        why = _reject(trip, day, d.stop_index, lost, c, prev, nxt)
        (rejected.append(why) if why else ok.append(c))
    ok.sort(key=lambda c: score_fn(features(trip, lost, c, prev, nxt)), reverse=True)

    rain = [x.rain_chance for x in itin.days]
    old_hard = _hard(itin)
    options: list[ProposalOption] = []
    for c in ok:
        if len(options) == N_OPTIONS:
            break
        draft = to_draft(itin)
        kept = place_intents(lost.tags) & place_intents(c.tags)
        draft.days[d.day_index].stops[d.stop_index] = DraftStop(
            place_id=c.id, start_time=stop.start_time, duration_min=stop.duration_min,
            reason=f"Thay {lost.name} ({KIND_TEXT[d.kind]})" + (f" — cùng mục đích {_labels(kept)}" if kept else ""))
        new = build_itinerary(trip, draft, places | {c.id: c}, rain, hub)
        extra = _hard(new) - old_hard
        if extra:
            rejected.append("OVER_BUDGET" if ("over_budget", None) in extra else "NEW_CONFLICT")
            continue
        options.append(_option(trip, itin, new, (d.day_index, d.stop_index), lost, c, prev, nxt))
    return options or NoFeasible(reason_codes=sorted(set(rejected)) or ["NO_CANDIDATE"])
```

- [ ] **Step 4: Chạy test**

Run: `cd server && uv run pytest tests/test_replan.py -v && uv run pytest`
Expected: tất cả PASS

- [ ] **Step 5: Commit**

```bash
git add server/app/domain.py server/app/replan.py server/tests/test_replan.py
git commit -m "feat(server): engine thay thế theo mục đích (closed/disliked), không gọi LLM"
```

---

### Task 5: Bảng `proposals` + endpoint Disruption / Apply

**Files:**
- Modify: `server/app/schema.sql` (bảng `proposals`)
- Modify: `server/app/trips.py` (đổi `_hub` → `hub_for`, tách `save_itinerary`)
- Modify: `server/app/agent.py` (đổi `_itinerary_event` → `itinerary_event`)
- Create: `server/app/proposals.py`
- Modify: `server/app/main.py` (`include_router(proposals.router)`)
- Test: `server/tests/test_disruptions_api.py`

**Interfaces:**
- Consumes: `propose`, `NoFeasible`, `InvalidDisruption` (Task 4); `similar_places` (Task 3)
- Produces:
  - `trips.save_itinerary(conn, trip_id: int, itinerary: dict, places: dict) -> int` (version mới)
  - `trips.hub_for(dest: dict, trip: Trip) -> Hub | None`
  - `agent.itinerary_event(itin: Itinerary, seen: dict[int, Place]) -> dict`
  - `POST /trips/{id}/disruptions` body `{version, kind, day_index, stop_index}` → `{proposal_id, options: [{itinerary, places, changed, metrics, reason_codes, explanation}]}` hoặc `{proposal_id, no_feasible: [codes]}`
  - `POST /trips/{id}/proposals/{pid}/apply` body `{option}` → `{type: "itinerary", itinerary, places, trip_id, version}`

- [ ] **Step 1: Đổi tên và tách hàm (refactor, chưa đổi hành vi)**

Chạy:
```bash
cd server && grep -rlE "_itinerary_event|_hub\(" app tests | xargs perl -pi -e 's/_itinerary_event/itinerary_event/g; s/\b_hub\(/hub_for(/g'
grep -rn "itinerary_event\|hub_for" app tests
```
Expected: `agent.py` định nghĩa `def itinerary_event`; `trips.py` định nghĩa `def hub_for` và gọi `hub_for(dest, trip)`.

Trong `server/app/trips.py`, thêm hàm trước `_plan_and_save`:

```python
def save_itinerary(conn, trip_id: int, itinerary: dict, places: dict) -> int:
    """Lưu một version Itinerary mới (bất biến) và trả số version."""
    return conn.execute(
        """INSERT INTO itineraries(trip_id, version, data)
           SELECT %s, COALESCE(MAX(version), 0) + 1, %s FROM itineraries WHERE trip_id = %s
           RETURNING version""",
        (trip_id, Jsonb({"itinerary": itinerary, "places": places}), trip_id)).fetchone()["version"]
```

và thay khối INSERT trong `_plan_and_save` bằng:

```python
        if ev["type"] == "itinerary":
            version = save_itinerary(conn, trip_id, ev["itinerary"], ev["places"])
            ev = {**ev, "trip_id": trip_id, "version": version}
```

Run: `cd server && uv run pytest`
Expected: tất cả PASS (refactor không đổi hành vi)

- [ ] **Step 2: Viết test thất bại** — tạo `server/tests/test_disruptions_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app.agent import itinerary_event
from app.db import get_conn
from app.domain import Draft, Trip
from app.main import app
from app.places import get_places
from app.rules import build_itinerary
from app.trips import save_itinerary
from tests.helpers import add_place

TRIP = Trip(destination="da-lat", days=1, budget=5_000_000, travel_mode="grab", preferred_tags=["cafe-chill"])


@pytest.fixture
def client(conn):
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth(client, email="an@example.com"):
    token = client.post("/auth/register", json={"email": email, "password": "matkhau123"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def seed(conn, client, pinned=False):
    """Trip 1 ngày: Cafe A 09:00 → Bảo tàng 11:00. Ứng viên: Cafe B (cùng embedding), Cafe C (xa hơn)."""
    h = auth(client)
    uid = conn.execute("SELECT id FROM users").fetchone()["id"]
    cafe = add_place(conn, name="Cafe A", kind="cafe", tags=["cafe-chill"], vec=1)
    museum = add_place(conn, name="Bảo tàng", kind="tham-quan", tags=["lich-su"], vec=2)
    add_place(conn, name="Cafe B", kind="cafe", tags=["cafe-chill"], vec=1)
    add_place(conn, name="Cafe C", kind="cafe", tags=["check-in"], vec=3)
    tid = conn.execute("INSERT INTO trips(user_id, spec) VALUES (%s, %s) RETURNING id",
                       (uid, Jsonb(TRIP.model_dump(mode="json")))).fetchone()["id"]
    places = get_places(conn, [cafe, museum])
    draft = Draft.model_validate({"summary": "", "days": [{"stops": [
        {"place_id": cafe, "start_time": "09:00", "duration_min": 60, "pinned": pinned},
        {"place_id": museum, "start_time": "11:00", "duration_min": 60}]}]})
    ev = itinerary_event(build_itinerary(TRIP, draft, places), places)
    save_itinerary(conn, tid, ev["itinerary"], ev["places"])
    return h, tid


def disrupt(client, h, tid, version=1, stop=0, kind="closed"):
    return client.post(f"/trips/{tid}/disruptions", headers=h,
                       json={"version": version, "kind": kind, "day_index": 0, "stop_index": stop})


def first_stop_name(opt):
    return opt["places"][str(opt["itinerary"]["days"][0]["stops"][0]["place_id"])]["name"]


def test_closed_returns_options_and_logs(client, conn):
    h, tid = seed(conn, client)
    r = disrupt(client, h, tid)
    assert r.status_code == 200
    body = r.json()
    assert [first_stop_name(o) for o in body["options"]] == ["Cafe B", "Cafe C"]
    assert body["options"][0]["reason_codes"][0] == "INTENT_MATCH"
    row = conn.execute("SELECT base_version, disruption, chosen_index FROM proposals WHERE id = %s",
                       (body["proposal_id"],)).fetchone()
    assert (row["base_version"], row["disruption"]["kind"], row["chosen_index"]) == (1, "closed", None)


def test_apply_is_idempotent(client, conn):
    h, tid = seed(conn, client)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    first = client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0}).json()
    again = client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0}).json()
    assert first["version"] == again["version"] == 2
    assert first["type"] == "itinerary" and first_stop_name(first) == "Cafe B"
    assert conn.execute("SELECT COUNT(*) AS n FROM itineraries WHERE trip_id = %s", (tid,)).fetchone()["n"] == 2
    assert conn.execute("SELECT chosen_index FROM proposals WHERE id = %s", (pid,)).fetchone()["chosen_index"] == 0


def test_apply_other_option_after_applied_409(client, conn):
    h, tid = seed(conn, client)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0})
    assert client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 1}).status_code == 409


def test_stale_version_409(client, conn):
    h, tid = seed(conn, client)
    old = disrupt(client, h, tid).json()["proposal_id"]
    pid = disrupt(client, h, tid).json()["proposal_id"]
    client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": 0})  # → version 2
    assert disrupt(client, h, tid, version=1).status_code == 409
    assert client.post(f"/trips/{tid}/proposals/{old}/apply", headers=h, json={"option": 0}).status_code == 409


def test_other_user_404(client, conn):
    h, tid = seed(conn, client)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    other = auth(client, "binh@example.com")
    assert disrupt(client, other, tid).status_code == 404
    assert client.post(f"/trips/{tid}/proposals/{pid}/apply", headers=other, json={"option": 0}).status_code == 404


def test_pinned_or_bad_stop_422(client, conn):
    h, tid = seed(conn, client, pinned=True)
    assert disrupt(client, h, tid).status_code == 422
    assert disrupt(client, h, tid, stop=9).status_code == 422


def test_no_feasible_when_no_same_kind_place(client, conn):
    h, tid = seed(conn, client)
    body = disrupt(client, h, tid, stop=1).json()  # Bảo tàng: không có tham-quan nào khác
    assert body["no_feasible"] == ["NO_CANDIDATE"]
    assert "options" not in body
```

- [ ] **Step 3: Chạy test, thấy thất bại**

Run: `cd server && uv run pytest tests/test_disruptions_api.py -v`
Expected: FAIL, 404 Not Found ở `/trips/{id}/disruptions` (route chưa có)

- [ ] **Step 4: Cài đặt** — thêm vào cuối `server/app/schema.sql`:

```sql
-- Disruption → Proposal; kiêm log feedback (đã hiện gì, chọn gì) cho ranker (spec revision-giu-muc-dich §5.1)
CREATE TABLE IF NOT EXISTS proposals (
  id serial PRIMARY KEY,
  trip_id integer NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  base_version integer NOT NULL,
  disruption jsonb NOT NULL,
  options jsonb NOT NULL,
  no_feasible text[],
  chosen_index integer,
  applied_version integer,
  created_at timestamptz NOT NULL DEFAULT now()
);
```

Tạo `server/app/proposals.py`:

```python
"""Disruption → Proposal → áp dụng (spec revision-giu-muc-dich §5). Không gọi LLM (ADR-0006)."""
from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.agent import itinerary_event
from app.auth import current_user
from app.db import get_conn
from app.domain import Disruption, Itinerary, Trip
from app.places import get_places, list_destinations, similar_places
from app.replan import InvalidDisruption, NoFeasible, propose
from app.trips import hub_for, save_itinerary

router = APIRouter()
STALE = "Lịch trình đã có bản mới hơn, hãy mở bản mới nhất rồi thử lại."


class DisruptionIn(Disruption):
    version: int


class ApplyIn(BaseModel):
    option: int = Field(ge=0)


def _trip(conn, trip_id: int, user_id: int) -> Trip:
    row = conn.execute("SELECT spec FROM trips WHERE id = %s AND user_id = %s", (trip_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    return Trip.model_validate(row["spec"])


def _latest_version(conn, trip_id: int) -> int | None:
    return conn.execute("SELECT MAX(version) AS v FROM itineraries WHERE trip_id = %s", (trip_id,)).fetchone()["v"]


@router.post("/trips/{trip_id}/disruptions")
def create_disruption(trip_id: int, body: DisruptionIn, user_id: int = Depends(current_user),
                      conn=Depends(get_conn)):
    trip = _trip(conn, trip_id, user_id)
    row = conn.execute("SELECT data FROM itineraries WHERE trip_id = %s AND version = %s",
                       (trip_id, body.version)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy phiên bản lịch trình")
    if body.version != _latest_version(conn, trip_id):
        raise HTTPException(409, STALE)
    itin = Itinerary.model_validate(row["data"]["itinerary"])
    ids = {s.place_id for d in itin.days for s in d.stops}
    if itin.stay_place_id is not None:
        ids.add(itin.stay_place_id)
    places = get_places(conn, list(ids))
    dest = next(d for d in list_destinations(conn) if d["slug"] == trip.destination)
    try:
        result = propose(trip, itin, places, body,
                         lambda lost, used: similar_places(conn, lost.id, lost.kind, used, trip.avoided_tags),
                         hub_for(dest, trip))
    except InvalidDisruption as e:
        raise HTTPException(422, str(e)) from None

    disruption = Jsonb(body.model_dump(exclude={"version"}))
    if isinstance(result, NoFeasible):
        pid = conn.execute(
            """INSERT INTO proposals(trip_id, base_version, disruption, options, no_feasible)
               VALUES (%s, %s, %s, '[]', %s) RETURNING id""",
            (trip_id, body.version, disruption, result.reason_codes)).fetchone()["id"]
        return {"proposal_id": pid, "no_feasible": result.reason_codes}

    options = []
    for o in result:
        ev = itinerary_event(o.itinerary, places | {p.id: p for p in o.added})
        options.append({"itinerary": ev["itinerary"], "places": ev["places"], "changed": o.changed,
                        "metrics": o.metrics, "reason_codes": o.reason_codes, "explanation": o.explanation})
    pid = conn.execute(
        "INSERT INTO proposals(trip_id, base_version, disruption, options) VALUES (%s, %s, %s, %s) RETURNING id",
        (trip_id, body.version, disruption, Jsonb(options))).fetchone()["id"]
    return {"proposal_id": pid, "options": options}


@router.post("/trips/{trip_id}/proposals/{proposal_id}/apply")
def apply_proposal(trip_id: int, proposal_id: int, body: ApplyIn, user_id: int = Depends(current_user),
                   conn=Depends(get_conn)):
    _trip(conn, trip_id, user_id)
    with conn.transaction():
        p = conn.execute("SELECT * FROM proposals WHERE id = %s AND trip_id = %s FOR UPDATE",
                         (proposal_id, trip_id)).fetchone()
        if not p:
            raise HTTPException(404, "Không tìm thấy phương án")
        if p["applied_version"] is not None:  # áp dụng lại cùng phương án → trả version cũ (idempotent)
            if p["chosen_index"] != body.option:
                raise HTTPException(409, "Đã áp dụng một phương án khác cho sự cố này")
            version = p["applied_version"]
        else:
            if body.option >= len(p["options"]):
                raise HTTPException(422, "Không có phương án này")
            if p["base_version"] != _latest_version(conn, trip_id):
                raise HTTPException(409, STALE)
            opt = p["options"][body.option]
            version = save_itinerary(conn, trip_id, opt["itinerary"], opt["places"])
            conn.execute("UPDATE proposals SET chosen_index = %s, applied_version = %s WHERE id = %s",
                         (body.option, version, proposal_id))
    opt = p["options"][body.option]
    return {"type": "itinerary", "itinerary": opt["itinerary"], "places": opt["places"],
            "trip_id": trip_id, "version": version}
```

Trong `server/app/main.py`: sửa `from app import auth, trips` thành `from app import auth, proposals, trips` và thêm `app.include_router(proposals.router)` sau `app.include_router(trips.router)`.

- [ ] **Step 5: Chạy test**

Run: `cd server && uv run pytest tests/test_disruptions_api.py -v && uv run pytest`
Expected: tất cả PASS

- [ ] **Step 6: Commit**

```bash
git add server/app/schema.sql server/app/trips.py server/app/agent.py server/app/proposals.py server/app/main.py server/tests/
git commit -m "feat(server): API Disruption → Proposal → áp dụng, bảng proposals kiêm log feedback"
```

---

### Task 6: Client API cho Proposal

**Files:**
- Modify: `client/src/api.ts`
- Test: `client/src/api.test.ts`

**Interfaces:**
- Consumes: 2 endpoint của Task 5
- Produces:
  - Kiểu `ProposalOption`, `Proposal = { proposal_id: number; options?: ProposalOption[]; no_feasible?: string[] }`, `DisruptionKind = 'closed' | 'disliked'`, `ItineraryEvent`
  - `reportDisruption(token, tripId, version, kind, dayIndex, stopIndex): Promise<Proposal>`
  - `applyProposal(token, tripId, proposalId, option): Promise<ItineraryEvent>`
  - `noFeasibleText(codes: string[]): string[]`
  - `optionPlace(o: ProposalOption): Place | undefined`
  - `signed(n: number, unit: (x: number) => string): string`
  - Cả hai hàm gọi API ném `Error('unauthorized')` khi 401, và `Error(detail tiếng Việt)` khi lỗi khác.

- [ ] **Step 1: Viết test thất bại** — thêm vào `client/src/api.test.ts` (bổ sung `noFeasibleText, optionPlace, signed, vnd, type ProposalOption` vào import):

```ts
describe('noFeasibleText', () => {
  it('đổi mã lý do thành câu tiếng Việt, mã lạ giữ nguyên', () => {
    expect(noFeasibleText(['NO_CANDIDATE', 'XYZ'])).toEqual(['Chưa có Place nào cùng loại để thay.', 'XYZ'])
  })
})

describe('optionPlace', () => {
  it('lấy Place mới ở vị trí Stop đã đổi', () => {
    const o = {
      changed: [[0, 1]],
      itinerary: { days: [{ stops: [{ place_id: 1 }, { place_id: 7 }] }] },
      places: { '1': { id: 1, name: 'Cũ' }, '7': { id: 7, name: 'Mới' } },
    } as unknown as ProposalOption
    expect(optionPlace(o)?.name).toBe('Mới')
  })
})

describe('signed', () => {
  it('thêm dấu và đơn vị; 0 là "như cũ"', () => {
    expect(signed(30000, vnd)).toBe('+' + vnd(30000))
    expect(signed(-12, (x) => `${x} phút`)).toBe('−12 phút')
    expect(signed(0, vnd)).toBe('như cũ')
  })
})
```

- [ ] **Step 2: Chạy test, thấy thất bại**

Run: `cd client && npm test`
Expected: FAIL, `noFeasibleText is not a function`

- [ ] **Step 3: Cài đặt** — thêm vào cuối `client/src/api.ts`:

```ts
export type DisruptionKind = 'closed' | 'disliked'
export type ItineraryEvent = Extract<AgentEvent, { type: 'itinerary' }>
export type ProposalOption = {
  itinerary: Itinerary; places: Record<string, Place>; changed: [number, number][]
  metrics: {
    cost_delta: number; travel_min_delta: number; day_end_after: string; retention_after: number | null
    intents_kept: string[]; intents_lost: string[]
  }
  reason_codes: string[]; explanation: string
}
export type Proposal = { proposal_id: number; options?: ProposalOption[]; no_feasible?: string[] }

async function postJSON<T>(token: string, path: string, body: unknown): Promise<T> {
  const r = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  })
  if (r.status === 401) throw new Error('unauthorized')
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Lỗi máy chủ (${r.status})`)
  return data as T
}

export const reportDisruption = (token: string, tripId: number, version: number, kind: DisruptionKind,
  dayIndex: number, stopIndex: number) =>
  postJSON<Proposal>(token, `/trips/${tripId}/disruptions`,
    { version, kind, day_index: dayIndex, stop_index: stopIndex })

export const applyProposal = (token: string, tripId: number, proposalId: number, option: number) =>
  postJSON<ItineraryEvent>(token, `/trips/${tripId}/proposals/${proposalId}/apply`, { option })

const NO_FEASIBLE_TEXT: Record<string, string> = {
  NO_CANDIDATE: 'Chưa có Place nào cùng loại để thay.',
  NO_OPEN_CANDIDATE: 'Các Place tương tự đều đóng cửa vào giờ này.',
  NOT_REACHABLE_IN_TIME: 'Các Place tương tự quá xa, không kịp giờ Stop kế tiếp.',
  OVER_BUDGET: 'Thay thế sẽ vượt Budget.',
  NEW_CONFLICT: 'Thay thế sẽ làm lịch trình phát sinh xung đột mới.',
}
export const noFeasibleText = (codes: string[]) => codes.map((c) => NO_FEASIBLE_TEXT[c] ?? c)

export function optionPlace(o: ProposalOption): Place | undefined {
  const [d, s] = o.changed[0]
  return o.places[o.itinerary.days[d].stops[s].place_id]
}

export const signed = (n: number, unit: (x: number) => string) =>
  n === 0 ? 'như cũ' : (n > 0 ? '+' : '−') + unit(Math.abs(n))
```

- [ ] **Step 4: Chạy test**

Run: `cd client && npm test`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add client/src/api.ts client/src/api.test.ts
git commit -m "feat(client): gọi API Disruption/Proposal và hàm hiển thị"
```

---

### Task 7: Nút sự cố trên Stop + ProposalPanel + nối App; cập nhật tài liệu

**Files:**
- Create: `client/src/components/ProposalPanel.tsx`
- Modify: `client/src/components/Timeline.tsx` (prop `busy`, `onDisrupt`, `children`; 2 nút mỗi Stop)
- Modify: `client/src/App.tsx` (state `version`, `proposal`; `disrupt`, `apply`)
- Modify: `docs/2026-09-25-hien-trang-app.md`, `docs/PRD.md` (§5.11 → 🟡)

**Interfaces:**
- Consumes: Task 2 và Task 6
- Produces: `ProposalPanel({ proposal, busy, onApply(i), onClose })`; `Timeline` nhận thêm `busy?: boolean`, `onDisrupt?: (kind: DisruptionKind, dayIndex: number, stopIndex: number) => void`, `children?: ReactNode` (hiện ở đầu cột)

- [ ] **Step 1: Tạo `client/src/components/ProposalPanel.tsx`**

```tsx
import { noFeasibleText, optionPlace, signed, vnd, type Proposal } from '../api'

export default function ProposalPanel({ proposal, busy, onApply, onClose }: {
  proposal: Proposal; busy: boolean; onApply: (option: number) => void; onClose: () => void
}) {
  return (
    <section aria-live="polite" className="mb-3 rounded-xl border border-sky-200 bg-sky-50 p-3 text-sm">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="font-semibold">Phương án thay thế</h2>
        <button type="button" onClick={onClose} className="text-xs text-stone-500 hover:underline">Huỷ</button>
      </div>
      {proposal.no_feasible && (
        <ul className="space-y-1 text-stone-700">
          {noFeasibleText(proposal.no_feasible).map((t) => <li key={t}>{t}</li>)}
        </ul>
      )}
      <ol className="space-y-2">
        {proposal.options?.map((o, i) => {
          const m = o.metrics
          return (
            <li key={i} className="rounded-lg bg-white p-3 shadow-sm">
              <div className="font-medium">{i + 1}. {optionPlace(o)?.name}</div>
              <p className="mt-1 text-xs text-stone-600">{o.explanation}</p>
              <dl className="mt-2 grid grid-cols-3 gap-1 text-xs">
                <div><dt className="text-stone-500">Chi phí</dt><dd>{signed(m.cost_delta, vnd)}</dd></div>
                <div><dt className="text-stone-500">Di chuyển</dt><dd>{signed(m.travel_min_delta, (x) => `${x} phút`)}</dd></div>
                <div>
                  <dt className="text-stone-500">Giữ mục đích</dt>
                  <dd>{m.retention_after == null ? '—' : `${Math.round(m.retention_after * 100)}%`}</dd>
                </div>
              </dl>
              <button type="button" disabled={busy} onClick={() => onApply(i)}
                className="mt-2 rounded bg-emerald-700 px-3 py-1 text-xs text-white disabled:opacity-50">
                Áp dụng
              </button>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
```

- [ ] **Step 2: Sửa `Timeline.tsx`** — import thêm `type DisruptionKind` và `type ReactNode` (`import type { ReactNode } from 'react'`); đổi chữ ký:

```tsx
export default function Timeline({ itinerary, places, budget, busy = false, onDisrupt, children }: {
  itinerary: Itinerary | null; places: Record<string, Place>; budget: number | null
  busy?: boolean; onDisrupt?: (kind: DisruptionKind, dayIndex: number, stopIndex: number) => void
  children?: ReactNode
}) {
```

Ngay sau thẻ mở `<aside className="min-h-0 overflow-y-auto border-l border-stone-200 p-4">` (nhánh có itinerary) thêm `{children}`. Trong mỗi `<li>` Stop, sau `<p className="mt-1 text-xs text-stone-500">{s.reason}</p>`:

```tsx
                {onDisrupt && (
                  <div className="mt-2 flex gap-2 text-xs">
                    {(['closed', 'disliked'] as const).map((k) => (
                      <button key={k} type="button" disabled={busy || s.pinned}
                        title={s.pinned ? 'Bỏ ghim để đổi' : undefined}
                        onClick={() => onDisrupt(k, i, j)}
                        className="rounded border border-stone-300 px-2 py-0.5 hover:bg-stone-100 disabled:opacity-40">
                        {k === 'closed' ? 'Báo đóng cửa' : 'Đổi chỗ khác'}
                      </button>
                    ))}
                  </div>
                )}
```

- [ ] **Step 3: Sửa `App.tsx`**

Import thêm: `applyProposal, optionPlace, reportDisruption, type DisruptionKind, type ItineraryEvent, type Proposal` từ `./api` và `ProposalPanel` từ `./components/ProposalPanel`.

Thêm state sau `tripId`:

```tsx
  const [version, setVersion] = useState<number | null>(null)  // version Itinerary đang xem, gửi kèm Disruption
  const [proposal, setProposal] = useState<Proposal | null>(null)
```

Trong `handle`: case `'trip'` thêm `setVersion(null); setProposal(null)`; case `'itinerary'` thêm `setVersion(e.version)`.

Thêm sau hàm `run`:

```tsx
  async function call<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true)
    try {
      return await fn()
    } catch (err) {
      if (err instanceof Error && err.message === 'unauthorized') { saveToken(null); setToken(null) }
      else if (err instanceof Error && !(err instanceof TypeError)) add({ role: 'error', text: err.message })
      else add({ role: 'error', text: 'Mất kết nối tới máy chủ. Kiểm tra server đã chạy chưa.' })
    } finally {
      setBusy(false)
    }
  }

  const disrupt = async (kind: DisruptionKind, day: number, stop: number) => {
    const p = await call(() => reportDisruption(token!, tripId!, version!, kind, day, stop))
    if (!p) return
    setProposal(p)
    setSearchPins((p.options ?? []).map(optionPlace).filter((x): x is Place => x !== undefined))
  }

  const apply = async (option: number) => {
    const ev: ItineraryEvent | undefined = await call(() => applyProposal(token!, tripId!, proposal!.proposal_id, option))
    if (!ev) return
    setProposal(null); setSearchPins([])
    setPlaces(ev.places); setItinerary(ev.itinerary); setVersion(ev.version)
    add({ role: 'ai', text: `Đã áp dụng phương án — lịch trình bản ${ev.version}.` })
  }
```

Trong `newTrip` thêm `setVersion(null); setProposal(null)`. Thay dòng `<Timeline …/>` bằng:

```tsx
      <Timeline itinerary={itinerary} places={places} budget={budget} busy={busy}
        onDisrupt={tripId != null && version != null ? disrupt : undefined}>
        {proposal && <ProposalPanel proposal={proposal} busy={busy} onApply={apply}
          onClose={() => { setProposal(null); setSearchPins([]) }} />}
      </Timeline>
```

- [ ] **Step 4: Test + build**

Run: `cd client && npm test && npm run build && npm run lint`
Expected: test PASS, build OK, lint không có lỗi mới

- [ ] **Step 5: E2E trên app desktop**

```bash
docker compose up -d db
cd server && uv run uvicorn app.main:app --port 8000 &   # hoặc cách chạy server đang dùng trong README
cd client && npm run build && rm -rf ~/Library/Caches/python3 && cd ../desktop && uv run python main.py
```

Kịch bản:
1. "Đi Đà Lạt 2 ngày, 2 người, 3 triệu, thích cafe chill và thiên nhiên" → có chip Thư giãn / Thiên nhiên và "Giữ mục đích …%".
2. Bấm "Báo đóng cửa" trên một Stop cafe → panel hiện ≤ 3 phương án trong < 2 s, pin vàng tại Place thay thế.
3. Bấm "Áp dụng" → Timeline đổi Stop, chat báo "bản 2".
4. Báo tiếp một sự cố → không bị 409 (version đã được cập nhật).

Ghi lại kết quả thật (chụp màn hình nếu có). Nếu có bước không đạt, báo rõ bước đó, không đánh dấu hoàn thành.

- [ ] **Step 6: Cập nhật tài liệu**
  - `docs/2026-09-25-hien-trang-app.md`:
    - §1: thêm dòng "Lát A+B Revision giữ mục đích".
    - §2: thêm luồng `POST /trips/{id}/disruptions` → `replan.propose` → `proposals` → `/apply`.
    - §2.3: thêm nguyên tắc "Proposal do code tạo, INTENT_LABELS ở cả server lẫn client".
    - §3.3: thêm dòng UI cho nút sự cố và panel.
  - `docs/PRD.md` §5.11: đổi ⏳ → 🟡, ghi rõ lát A, B đã có; lát C–F chưa.

- [ ] **Step 7: Commit**

```bash
git add client/src docs/2026-09-25-hien-trang-app.md docs/PRD.md
git commit -m "feat(client): nút sự cố trên Stop và ProposalPanel; cập nhật tài liệu lát A+B"
```
