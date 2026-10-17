# Lát C — Disruption mưa + trễ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Người dùng bấm "☂ Giả sử mưa" trên một ngày, hoặc "Tôi trễ 15/30/60′" trên một Stop, và nhận tối đa 3 Proposal do code sinh ra. Áp dụng một Proposal thì tạo version mới.

**Architecture:** `replan.propose` được tổng quát hoá thành 3 bước:
1. `_affected` trả về Draft gốc (với `late` là Draft đã dời giờ), danh sách Stop bị ảnh hưởng (`Hit`) và các mã lý do chung.
2. Xếp hạng ứng viên riêng cho từng Stop `replace`.
3. Phương án k lấy ứng viên thứ k của từng Stop, không trùng Place giữa các Stop. Với `rain`/`late`, Stop thiếu ứng viên thì bị bỏ.

`closed`/`disliked` là trường hợp chỉ có 1 Hit. Không thêm endpoint. Client thêm nút trên Timeline, và ProposalPanel hiện `title` do server trả về.

**Tech Stack:** FastAPI + Pydantic v2, psycopg3/Postgres (Docker), pytest; React 19 + TypeScript + Tailwind 4, vitest.

**Spec:** `docs/superpowers/specs/2026-09-29-revision-giu-muc-dich-design.md`. Đọc §4 và **§13 (quyết định lát C, thay thế §4.1/§4.5/§6 ở phần rain/late)**.

## Global Constraints

- Engine là code thuần, không gọi LLM (ADR-0006, D4).
- Stop đã ghim: `rain`/`late` không thay và không bỏ Stop ghim (C1, C3). `closed`/`disliked` trên Stop ghim → 422 (giữ như lát B).
- Mưa **không ghi** `rain_chance` (C1).
- Tối đa 3 phương án cho mỗi sự cố. Với `late` có Stop hỏng: tối đa 2 phương án thay + 1 phương án "Bỏ các Stop hỏng" (C3).
- `minutes` ∈ 5–240. `stop_index` bắt buộc với closed/disliked/late, phải bỏ trống với rain. `minutes` chỉ dùng và bắt buộc với late. Sai → 422 (C6).
- Mọi test lát B trong `server/tests/test_replan.py` và `server/tests/test_disruptions_api.py` phải **xanh, không sửa assert**. Chỉ được sửa helper fixture.
- Câu chữ hướng tới người dùng là tiếng Việt. `explanation` không chứa "%".
- Lệnh test: `docker compose up -d db && cd server && uv run pytest` · `cd client && npm test && npm run build`.
- Commit message kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Trễ đẩy Stop qua nửa đêm.** `HHMM` chỉ nhận tới 23:59. Stop chưa ghim → bỏ. Stop ghim → 422 với câu rõ ràng, không được lỗi 500 (Task 4 có test).
2. **Stop vốn đã quá giờ Pace trước khi trễ** (AI đôi khi xếp như vậy). Chỉ coi là "quá giờ" khi việc dời giờ làm Stop **vượt qua** mốc giới hạn, để không bỏ oan Stop vốn đã quá giờ (Task 4 có test).
3. **Mưa làm ngày trống hết Stop** (mọi Stop ngoài trời, không có ứng viên). `build_itinerary` chạy được với ngày rỗng, nhưng `_day_end` phải không lỗi (Task 3 có test).
4. **Phương án của Stop ghim có Conflict cứng** (Stop ghim bị dời vào giờ đóng cửa) **không được bị loại**. Conflict cứng mới trên Place ghim được miễn (Task 4 có test).
5. **Mưa nhưng `similar_places` chỉ trả 20 Place gần nhất về embedding**, có thể toàn ngoài trời → rơi vào nhánh bỏ Stop. Chấp nhận với 37 Place Đà Lạt. Ghi `ponytail:` ở chỗ lọc; khi dữ liệu nhiều hơn thì thêm tham số `indoor` cho `similar_places`.

---

### Task 1: Mở rộng `Disruption` (rain/late) + validate theo kind

**Files:**
- Modify: `server/app/domain.py:165-169`
- Test: `server/tests/test_domain.py` (tạo mới nếu chưa có; kiểm tra bằng `ls server/tests/test_domain.py`)

**Interfaces:**
- Produces: `Disruption(kind: Literal["closed","disliked","rain","late"], day_index: int ≥0, stop_index: int|None ≥0, minutes: int|None 5–240)`. Sai hình dạng thì raise `pydantic.ValidationError`, FastAPI tự trả 422.

- [ ] **Step 1: Viết test trước**

```python
import pytest
from pydantic import ValidationError

from app.domain import Disruption


def test_disruption_shape_per_kind():
    assert Disruption(kind="rain", day_index=1).stop_index is None
    assert Disruption(kind="late", day_index=0, stop_index=2, minutes=30).minutes == 30
    assert Disruption(kind="closed", day_index=0, stop_index=0).minutes is None
    bad = [dict(kind="rain", day_index=0, stop_index=0),        # mưa là sự cố của cả ngày
           dict(kind="closed", day_index=0),                    # thiếu stop_index
           dict(kind="late", day_index=0, stop_index=0),         # thiếu minutes
           dict(kind="late", day_index=0, stop_index=0, minutes=300),
           dict(kind="late", day_index=0, stop_index=0, minutes=4),
           dict(kind="closed", day_index=0, stop_index=0, minutes=30)]
    for b in bad:
        with pytest.raises(ValidationError):
            Disruption(**b)
```

- [ ] **Step 2: Chạy, xác nhận fail**

Run: `cd server && uv run pytest tests/test_domain.py -q`
Expected: FAIL (`rain` không hợp lệ với Literal hiện tại).

- [ ] **Step 3: Sửa `Disruption`**

```python
class Disruption(BaseModel):
    """Sự cố người dùng báo: closed/disliked/late trên một Stop, rain trên cả ngày (spec §13 C6). Lát D thêm insert."""
    kind: Literal["closed", "disliked", "rain", "late"]
    day_index: int = Field(ge=0)
    stop_index: int | None = Field(default=None, ge=0)
    minutes: int | None = Field(default=None, ge=5, le=240)

    @model_validator(mode="after")
    def _shape(self):
        if (self.stop_index is None) != (self.kind == "rain"):
            raise ValueError("stop_index bắt buộc với sự cố trên Stop, bỏ trống với mưa")
        if (self.minutes is None) != (self.kind != "late"):
            raise ValueError("minutes chỉ dùng và bắt buộc với late")
        return self
```
Thêm `model_validator` vào dòng import pydantic của `domain.py` nếu chưa có.

- [ ] **Step 4: Chạy lại + toàn suite server**

Run: `cd server && uv run pytest -q`
Expected: PASS toàn bộ. Chỗ lát B đang dùng `d.stop_index` vẫn chạy vì closed/disliked luôn có giá trị.

- [ ] **Step 5: Commit**

```bash
git add server/app/domain.py server/tests/test_domain.py
git commit -m "feat(server): Disruption nhận rain/late, validate stop_index/minutes theo kind (#32)"
```

---

### Task 2: Tổng quát hoá `replan.propose` (không đổi hành vi lát B) + `title`/`added` trong API

**Files:**
- Modify: `server/app/replan.py` (viết lại phần `_reject`, `_hard`, `_day_end`, `_explain`, `_option`, `propose`; thêm `Hit`, `_weekdays`, `_affected`, `_pick`, `_variant`, `_title`)
- Modify: `server/app/proposals.py` (option trả thêm `title`, `added`)
- Test: `server/tests/test_replan.py`, `server/tests/test_disruptions_api.py`

**Interfaces:**
- Consumes: `Disruption` từ Task 1.
- Produces:
  - `ProposalOption` thêm `title: str`. `metrics["features"]` đổi thành **list** dict, mỗi Place thay có một dict; hiện chưa ai đọc trường này.
  - `Hit(day, stop, lost, mode: "replace"|"drop")`.
  - `_affected(trip, itin, places, d) -> Affected(base: Draft, hits: list[Hit], codes: list[str], shifted: set[tuple[int,int]])`.
  - `_reject(trip, stops: list[DraftStop], weekdays, si, lost, cand, prev, nxt, indoor=False)`.
  - JSON mỗi option có thêm `"title": str` và `"added": list[int]`.

- [ ] **Step 1: Viết test mới trước**

Thêm vào `test_replan.py`:
```python
def test_option_title_is_new_place_name():
    places, itin = setup([(LOST, "09:00")])
    opts = propose(TRIP, itin, places, closed(), cands(P(10)))
    assert opts[0].title == "P10"
```
Thêm vào `test_disruptions_api.py`:
```python
def test_options_carry_title_and_added(client, conn):
    h, tid = seed(conn, client)
    o = disrupt(client, h, tid).json()["options"][0]
    assert o["title"] == "Cafe B"
    assert [o["places"][str(i)]["name"] for i in o["added"]] == ["Cafe B"]
```

- [ ] **Step 2: Chạy, xác nhận fail**

Run: `cd server && uv run pytest tests/test_replan.py tests/test_disruptions_api.py -q -k "title"`
Expected: FAIL (`ProposalOption` chưa có `title`).

- [ ] **Step 3: Viết lại engine**

Trong `replan.py`, thay từ `KIND_TEXT` tới hết file (giữ `to_draft`, `_leg_min`, `features`, `score`, `_neighbors`, `_stop_intents`, `_labels`, `_travel_min` như cũ). Thêm `from typing import Literal, NamedTuple` và `last_day_limit` vào import từ `app.rules`, thêm `PACE_HOURS` vào import từ `app.domain` (Task 4 dùng):

```python
KIND_TEXT = {"closed": "đóng cửa", "disliked": "bạn muốn đổi", "rain": "mưa", "late": "trễ giờ"}
DROP_TEXT = {"rain": "không có chỗ trong nhà phù hợp", "late": "không kịp giờ"}


class Hit(NamedTuple):
    day: int
    stop: int
    lost: Place
    mode: Literal["replace", "drop"]


class Affected(NamedTuple):
    base: Draft                        # Draft để dựng phương án (late: đã dời giờ)
    hits: list[Hit]
    codes: list[str]                   # mã chung của mọi phương án, vd LATE_SHIFT, PINNED_CONFLICT
    shifted: set[tuple[int, int]]      # Stop bị dời giờ (late) → tô sáng như Stop đã đổi


class ProposalOption(BaseModel):
    itinerary: Itinerary
    added: list[Place]
    changed: list[tuple[int, int]]  # (day_index, stop_index) trong itinerary mới
    metrics: dict
    reason_codes: list[str]
    explanation: str
    title: str


def _weekdays(day: Day) -> list[str]:
    return [WEEKDAYS[day.date.weekday()]] if day.date else WEEKDAYS


def _affected(trip: Trip, itin: Itinerary, places: dict[int, Place], d: Disruption) -> Affected:
    if d.day_index >= len(itin.days) or (d.stop_index is not None
                                         and d.stop_index >= len(itin.days[d.day_index].stops)):
        raise InvalidDisruption("Không tìm thấy Stop này trong lịch trình")
    base = to_draft(itin)
    stop = itin.days[d.day_index].stops[d.stop_index]
    if stop.pinned:
        raise InvalidDisruption("Stop đã ghim — bỏ ghim để đổi")
    return Affected(base, [Hit(d.day_index, d.stop_index, places[stop.place_id], "replace")], [], set())


def _reject(trip: Trip, stops: list[DraftStop], weekdays: list[str], si: int, lost: Place, cand: Place,
            prev: Point, nxt: Point, indoor: bool = False) -> str | None:
    stop = stops[si]
    if not any(is_open(cand, w, stop.start_time, stop.duration_min) for w in weekdays):
        return "NO_OPEN_CANDIDATE"
    start = _minutes(stop.start_time)
    # Không bắt lịch chặt hơn bản cũ: chỉ loại khi chặng mới vừa vượt khoảng trống vừa dài hơn chặng cũ.
    if si > 0:
        p = stops[si - 1]
        need = _leg_min(prev, cand, trip)
        if need > start - (_minutes(p.start_time) + p.duration_min) and need > _leg_min(prev, lost, trip):
            return "NOT_REACHABLE_IN_TIME"
    if si + 1 < len(stops):
        need = _leg_min(cand, nxt, trip)
        if need > _minutes(stops[si + 1].start_time) - start - stop.duration_min and need > _leg_min(lost, nxt, trip):
            return "NOT_REACHABLE_IN_TIME"
    return None


def _hard(itin: Itinerary) -> set[tuple[str, int | None, int | None]]:
    return {(c.kind, c.day_index, c.place_id) for c in itin.conflicts if c.kind in HARD}


def _day_end(day: Day) -> str:
    if not day.stops:
        return "—"
    m = max(_minutes(s.start_time) + s.duration_min for s in day.stops)
    return f"{m // 60:02d}:{m % 60:02d}"


def _explain(prefix: str | None, kept: set, lost: set, dropped: str | None, travel_delta: int, cost_delta: int,
             day_end: str, di: int) -> str:
    parts = [prefix] if prefix else []
    if kept:
        parts.append(f"giữ mục đích {_labels(kept)}")
    if lost:
        parts.append(f"chuyến không còn {_labels(lost)}")
    if dropped:
        parts.append(dropped)
    parts.append("thời gian di chuyển như cũ" if travel_delta == 0
                 else f"{'thêm' if travel_delta > 0 else 'bớt'} {abs(travel_delta)} phút di chuyển")
    parts.append("chi phí như cũ" if cost_delta == 0
                 else f"{'đắt hơn' if cost_delta > 0 else 'rẻ hơn'} {vnd(abs(cost_delta))}")
    parts.append(f"ngày {di + 1} kết thúc {day_end}")
    s = "; ".join(parts)
    return s[0].upper() + s[1:] + "."


def _title(pick: dict[Hit, Place], dropped: list[Place]) -> str:
    parts = [c.name for c in pick.values()]
    if dropped:
        parts.append("bỏ " + ", ".join(p.name for p in dropped))
    s = " · ".join(parts) or "chỉ dời giờ"
    return s[0].upper() + s[1:]


def _pick(ranked: dict[Hit, list[Place]], k: int, may_drop: bool) -> dict[Hit, Place] | None:
    """Phương án k: ứng viên thứ k còn trống của từng Stop, không trùng Place. Thiếu → bỏ Stop hoặc None."""
    taken, pick = set(), {}
    for h, cs in ranked.items():
        free = [c for c in cs if c.id not in taken]
        if len(free) > k:
            pick[h] = free[k]
            taken.add(free[k].id)
        elif not may_drop:
            return None
    return pick


def _variant(trip: Trip, itin: Itinerary, places: dict[int, Place], d: Disruption, aff: Affected,
             pick: dict[Hit, Place], hub: Hub | None) -> ProposalOption | str:
    draft = aff.base.model_copy(deep=True)
    for h, c in pick.items():
        s = draft.days[h.day].stops[h.stop]
        kept = _stop_intents(trip, h.lost) & place_intents(c.tags)
        draft.days[h.day].stops[h.stop] = DraftStop(
            place_id=c.id, start_time=s.start_time, duration_min=s.duration_min,
            reason=f"Thay {h.lost.name} ({KIND_TEXT[d.kind]})" + (f" — cùng mục đích {_labels(kept)}" if kept else ""))
    drop = {(h.day, h.stop) for h in aff.hits if h not in pick}
    touched = {(h.day, h.stop) for h in pick} | aff.shifted
    changed = []
    for di, day in enumerate(draft.days):
        kept_stops = []
        for si, s in enumerate(day.stops):
            if (di, si) in drop:
                continue
            if (di, si) in touched:
                changed.append((di, len(kept_stops)))
            kept_stops.append(s)
        day.stops = kept_stops

    new = build_itinerary(trip, draft, places | {c.id: c for c in pick.values()},
                          [x.rain_chance for x in itin.days], hub)
    pinned = {s.place_id for x in itin.days for s in x.stops if s.pinned}
    # Conflict trên Stop ghim không do engine gây ra (engine không đổi Stop ghim) → không loại phương án
    extra = {x for x in _hard(new) - _hard(itin) if x[2] is None or x[2] not in pinned}
    if extra:
        return "OVER_BUDGET" if any(k == "over_budget" for k, _, _ in extra) else "NEW_CONFLICT"

    dropped = [h.lost for h in aff.hits if h not in pick]
    li = set().union(*(_stop_intents(trip, h.lost) for h in pick)) if pick else set()
    kept = set().union(*(_stop_intents(trip, h.lost) & place_intents(c.tags) for h, c in pick.items())) if pick else set()
    lost_trip = {k for k, hit in itin.intents.items() if hit and not new.intents.get(k)}
    cost_delta = new.total_cost - itin.total_cost
    travel_delta = _travel_min(new) - _travel_min(itin)
    di = d.day_index
    codes = list(aff.codes)
    if li:
        codes.append("INTENT_MATCH" if kept == li else "INTENT_PARTIAL" if kept else "INTENT_LOST")
    if pick and d.kind == "rain":
        codes.append("INDOOR_FOR_RAIN")
    if dropped:
        codes.append("STOP_DROPPED")
    if travel_delta > 5:
        codes.append("FARTHER")
    elif travel_delta < -5:
        codes.append("CLOSER")
    if cost_delta > 0:
        codes.append("PRICIER")
    elif cost_delta < 0:
        codes.append("CHEAPER")
    day_end = _day_end(new.days[di])
    prefix = None
    if d.kind == "late":
        prefix = f"dời {d.minutes} phút từ {places[itin.days[di].stops[d.stop_index].place_id].name}"
    drop_text = f"bỏ {', '.join(p.name for p in dropped)} ({DROP_TEXT[d.kind]})" if dropped else None
    metrics = {"cost_delta": cost_delta, "travel_min_delta": travel_delta,
               "day_end_before": _day_end(itin.days[di]), "day_end_after": day_end,
               "retention_before": itin.retention, "retention_after": new.retention,
               "intents_kept": sorted(kept), "intents_lost": sorted(lost_trip),
               "features": [features(trip, h.lost, c, *_neighbors(itin, places, h.day, h.stop, hub))
                            for h, c in pick.items()]}
    return ProposalOption(itinerary=new, added=list(pick.values()), changed=changed, metrics=metrics,
                          reason_codes=codes, title=_title(pick, dropped),
                          explanation=_explain(prefix, kept, lost_trip, drop_text, travel_delta, cost_delta, day_end, di))


def propose(trip: Trip, itin: Itinerary, places: dict[int, Place], d: Disruption, candidates_fn: CandidatesFn,
            hub: Hub | None = None, score_fn=score) -> list[ProposalOption] | NoFeasible:
    aff = _affected(trip, itin, places, d)
    used = {s.place_id for x in itin.days for s in x.stops}
    if itin.stay_place_id is not None:
        used.add(itin.stay_place_id)

    rejected, ranked = [], {}
    for h in aff.hits:
        if h.mode != "replace":
            continue
        prev, nxt = _neighbors(itin, places, h.day, h.stop, hub)
        ok = []
        for c in candidates_fn(h.lost, used):
            why = _reject(trip, aff.base.days[h.day].stops, _weekdays(itin.days[h.day]), h.stop, h.lost, c,
                          prev, nxt, indoor=d.kind == "rain")
            (rejected.append(why) if why else ok.append(c))
        ok.sort(key=lambda c: score_fn(features(trip, h.lost, c, prev, nxt)), reverse=True)
        ranked[h] = ok

    may_drop = d.kind in ("rain", "late")
    variants = []
    for k in range(max([1, *map(len, ranked.values())])):  # ít nhất 1 lượt: rain/late không ứng viên → bỏ Stop
        pick = _pick(ranked, k, may_drop)
        if pick is None:
            break
        variants.append(pick)
    n_pick = N_OPTIONS - 1 if d.kind == "late" and aff.hits else N_OPTIONS
    if d.kind == "late":
        variants.append({})  # "Bỏ các Stop hỏng" — hoặc "Chỉ dời giờ" khi không có Stop hỏng

    options, seen = [], set()
    for i, pick in enumerate(variants):
        last = d.kind == "late" and i == len(variants) - 1
        if len(options) >= n_pick and not last:
            continue
        sig = frozenset((h.day, h.stop, c.id) for h, c in pick.items())
        if sig in seen:
            continue
        seen.add(sig)
        got = _variant(trip, itin, places, d, aff, pick, hub)
        (rejected.append(got) if isinstance(got, str) else options.append(got))
    return options or NoFeasible(reason_codes=sorted(set(rejected)) or ["NO_CANDIDATE"])
```

Trong `proposals.py`, dòng `options.append({...})` thêm hai khoá: `"title": o.title, "added": [p.id for p in o.added]`.

- [ ] **Step 4: Chạy toàn suite server**

Run: `cd server && uv run pytest -q`
Expected: PASS toàn bộ, gồm 11 test cũ của `test_replan.py` và mọi test của `test_disruptions_api.py` mà **không sửa assert nào**. Nếu một test lát B fail thì code sai, không phải test sai → dùng superpowers:systematic-debugging.

- [ ] **Step 5: Commit**

```bash
git add server/app/replan.py server/app/proposals.py server/tests/test_replan.py server/tests/test_disruptions_api.py
git commit -m "refactor(server): propose theo danh sách Stop bị ảnh hưởng, phương án có title (#32)"
```

---

### Task 3: Sự cố mưa (C1, C2)

**Files:**
- Modify: `server/app/replan.py` (`_affected`, `_reject`, `propose`)
- Test: `server/tests/test_replan.py`

**Interfaces:**
- Consumes: `Affected`, `Hit`, `_reject(..., indoor)` từ Task 2.
- Produces: `propose(... Disruption(kind="rain", day_index=i))` trả về các phương án chỉ có Place `outdoor=False` thay cho Stop ngoài trời chưa ghim, hoặc `NoFeasible(["NOTHING_OUTDOOR"])`.

- [ ] **Step 1: Viết test trước**

Trong `test_replan.py`, sửa helper `P` để nhận `outdoor` (không đổi hành vi mặc định):
```python
def P(id, kind="cafe", tags=(), price=0, lat=11.94, hours=None, outdoor=False):
    return Place(id=id, destination="da-lat", name=f"P{id}", kind=kind, lat=lat, lon=108.44, price=price,
                 open_hours=WEEK if hours is None else hours, outdoor=outdoor, tags=list(tags))
```
Thêm:
```python
RAIN = Disruption(kind="rain", day_index=0)
PARK, LAKE = P(1, kind="tham-quan", outdoor=True), P(3, kind="tham-quan", outdoor=True)
CAFE = P(2)


def test_rain_replaces_every_outdoor_stop_with_indoor():
    places, itin = setup([(PARK, "09:00"), (CAFE, "11:00"), (LAKE, "14:00")])
    a, b = P(10, kind="tham-quan"), P(11, kind="tham-quan")
    opts = propose(TRIP, itin, places, RAIN, cands(P(12, kind="tham-quan", outdoor=True), a, b))
    for o in opts:
        assert all(not (places | {p.id: p for p in o.added})[s.place_id].outdoor
                   for s in o.itinerary.days[0].stops)
    assert [s.place_id for s in opts[0].itinerary.days[0].stops] == [10, 2, 11]
    assert opts[0].changed == [(0, 0), (0, 2)]
    assert "INDOOR_FOR_RAIN" in opts[0].reason_codes
    assert "(mưa)" in opts[0].itinerary.days[0].stops[0].reason
    assert opts[0].itinerary.days[0].rain_chance is None  # C1: không ghi giả định mưa
    # phương án 2: Công viên → P11, Hồ không còn ứng viên → bỏ (C2)
    assert [s.place_id for s in opts[1].itinerary.days[0].stops] == [11, 2]
    assert "STOP_DROPPED" in opts[1].reason_codes
    assert opts[1].title == "P11 · bỏ P3"


def test_rain_keeps_pinned_outdoor_stop():
    places, itin = setup([(PARK, "09:00"), (LAKE, "14:00")], pinned={1})
    opts = propose(TRIP, itin, places, RAIN, cands(P(10, kind="tham-quan")))
    assert opts[0].itinerary.days[0].stops[0].place_id == 1
    assert opts[0].itinerary.days[0].stops[1].place_id == 10
    assert opts[0].reason_codes[0] == "PINNED_CONFLICT"


def test_rain_nothing_outdoor():
    places, itin = setup([(CAFE, "09:00")])
    assert propose(TRIP, itin, places, RAIN, cands(P(10))) == NoFeasible(reason_codes=["NOTHING_OUTDOOR"])


def test_rain_without_indoor_candidate_drops_stop_even_if_day_empties():
    places, itin = setup([(PARK, "09:00")])
    opts = propose(TRIP, itin, places, RAIN, cands(P(12, kind="tham-quan", outdoor=True)))
    assert len(opts) == 1
    assert opts[0].itinerary.days[0].stops == []
    assert opts[0].title == "Bỏ P1"
    assert "bỏ P1 (không có chỗ trong nhà phù hợp)" in opts[0].explanation
    assert opts[0].metrics["day_end_after"] == "—"
```

- [ ] **Step 2: Chạy, xác nhận fail**

Run: `cd server && uv run pytest tests/test_replan.py -q -k rain`
Expected: FAIL. `_affected` hiện lấy `stops[None]` → TypeError.

- [ ] **Step 3: Cài đặt**

Trong `_affected`, trước dòng `stop = itin.days[d.day_index].stops[d.stop_index]`:
```python
    day = itin.days[d.day_index]
    if d.kind == "rain":
        outdoor = [(si, s) for si, s in enumerate(day.stops) if places[s.place_id].outdoor]
        hits = [Hit(d.day_index, si, places[s.place_id], "replace") for si, s in outdoor if not s.pinned]
        codes = ["PINNED_CONFLICT"] if any(s.pinned for _, s in outdoor) else []
        return Affected(base, hits, codes, set())
```
Đầu `_reject`:
```python
    if indoor and cand.outdoor:
        # ponytail: lọc sau similar_places (top 20 theo embedding); dữ liệu lớn thì thêm tham số indoor cho truy vấn
        return "NO_INDOOR_CANDIDATE"
```
Đầu `propose`, ngay sau `aff = _affected(...)`:
```python
    if d.kind == "rain" and not aff.hits:
        return NoFeasible(reason_codes=["NOTHING_OUTDOOR"])
```

- [ ] **Step 4: Chạy toàn suite server**

Run: `cd server && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/app/replan.py server/tests/test_replan.py
git commit -m "feat(server): sự cố mưa — thay Stop ngoài trời bằng Place trong nhà, thiếu thì bỏ (#32)"
```

---

### Task 4: Sự cố trễ (C3)

**Files:**
- Modify: `server/app/replan.py` (`_affected`)
- Test: `server/tests/test_replan.py`

**Interfaces:**
- Consumes: `Affected`, `Hit`, `_variant`/`propose` từ Task 2; `PACE_HOURS` (`domain.py:36`), `last_day_limit` (`rules.py`), `is_open`.
- Produces: `propose(... Disruption(kind="late", day_index, stop_index, minutes))`.

- [ ] **Step 1: Viết test trước**

```python
def late(stop=0, minutes=30):
    return Disruption(kind="late", day_index=0, stop_index=stop, minutes=minutes)


def test_late_only_shifts_when_nothing_breaks():
    places, itin = setup([(LOST, "09:00"), (MUSEUM, "11:00")])
    opts = propose(TRIP, itin, places, late(), cands(P(10)))
    assert len(opts) == 1
    assert [s.start_time for s in opts[0].itinerary.days[0].stops] == ["09:30", "11:30"]
    assert opts[0].reason_codes == ["LATE_SHIFT"]
    assert opts[0].title == "Chỉ dời giờ"
    assert opts[0].changed == [(0, 0), (0, 1)]
    assert opts[0].explanation.startswith("Dời 30 phút từ P1")


def test_late_leaves_earlier_stops_alone():
    places, itin = setup([(LOST, "09:00"), (MUSEUM, "11:00")])
    opts = propose(TRIP, itin, places, late(stop=1), cands())
    assert [s.start_time for s in opts[0].itinerary.days[0].stops] == ["09:00", "11:30"]


def test_late_replaces_stop_closed_at_new_time_or_drops_it():
    morning = P(2, kind="tham-quan", hours={d: ["08:00", "12:00"] for d in WEEKDAYS})
    places, itin = setup([(LOST, "09:00"), (morning, "11:00")])
    opts = propose(TRIP, itin, places, late(stop=1, minutes=60), cands(P(10, kind="tham-quan")))
    assert [o.title for o in opts] == ["P10", "Bỏ P2"]
    assert opts[0].itinerary.days[0].stops[1].start_time == "12:00"
    assert opts[0].reason_codes[:1] == ["LATE_SHIFT"]
    assert "STOP_DROPPED" in opts[1].reason_codes
    assert "bỏ P2 (không kịp giờ)" in opts[1].explanation


def test_late_drops_stop_pushed_past_pace_end_in_every_option():
    places, itin = setup([(LOST, "09:00"), (MUSEUM, "19:30")])  # Pace "vua" kết thúc 21:00
    opts = propose(TRIP, itin, places, late(stop=0, minutes=60), cands(P(10, kind="tham-quan")))
    assert len(opts) == 1
    assert [s.place_id for s in opts[0].itinerary.days[0].stops] == [1]


def test_late_keeps_stop_that_was_already_past_pace_end():
    all_day = P(2, kind="tham-quan", tags=["lich-su"], hours={})  # mở cả ngày: chỉ kiểm luật quá giờ
    places, itin = setup([(LOST, "09:00"), (all_day, "21:00")])  # đã quá 21:00 từ trước
    opts = propose(TRIP, itin, places, late(stop=0, minutes=30), cands())
    assert [s.place_id for s in opts[0].itinerary.days[0].stops] == [1, 2]


def test_late_pinned_stop_is_shifted_not_replaced_even_if_closed():
    morning = P(2, kind="tham-quan", hours={d: ["08:00", "12:00"] for d in WEEKDAYS})
    places, itin = setup([(LOST, "09:00"), (morning, "11:00")], pinned={2})
    opts = propose(TRIP, itin, places, late(stop=0, minutes=60), cands(P(10, kind="tham-quan")))
    assert len(opts) == 1
    assert opts[0].itinerary.days[0].stops[1].place_id == 2
    assert opts[0].itinerary.days[0].stops[1].start_time == "12:00"
    assert "PINNED_CONFLICT" in opts[0].reason_codes


def test_late_past_midnight():
    places, itin = setup([(LOST, "20:00")])
    opts = propose(TRIP, itin, places, late(minutes=240), cands())
    assert opts[0].itinerary.days[0].stops == []  # Stop chưa ghim → bỏ
    places, itin = setup([(LOST, "21:00")], pinned={1})
    with pytest.raises(InvalidDisruption, match="nửa đêm"):
        propose(TRIP, itin, places, late(minutes=240), cands())
```

- [ ] **Step 2: Chạy, xác nhận fail**

Run: `cd server && uv run pytest tests/test_replan.py -q -k late`
Expected: FAIL (late đang đi vào nhánh 1 Stop replace, không dời giờ).

- [ ] **Step 3: Cài đặt**

Trong `_affected`, sau nhánh `rain` và trước dòng `stop = ...`:
```python
    if d.kind == "late":
        limit = _minutes(PACE_HOURS[trip.pace][1])
        if d.day_index == len(itin.days) - 1 and (lim := last_day_limit(trip)) is not None:
            limit = min(limit, lim)
        stops, wk = base.days[d.day_index].stops, _weekdays(day)
        hits, codes, shifted = [], ["LATE_SHIFT"], set()
        for si in range(d.stop_index, len(stops)):
            s = stops[si]
            p = places[s.place_id]
            old_end = _minutes(s.start_time) + s.duration_min
            start = _minutes(s.start_time) + d.minutes
            if start >= 24 * 60:
                if s.pinned:
                    raise InvalidDisruption(f"Trễ {d.minutes} phút đẩy {p.name} (đã ghim) qua nửa đêm — bỏ ghim rồi thử lại")
                hits.append(Hit(d.day_index, si, p, "drop"))
                continue
            s.start_time = f"{start // 60:02d}:{start % 60:02d}"
            shifted.add((d.day_index, si))
            over = start + s.duration_min > limit >= old_end  # chỉ tính khi chính việc dời giờ làm vượt mốc
            shut = not any(is_open(p, w, s.start_time, s.duration_min) for w in wk)
            if s.pinned:
                if (over or shut) and "PINNED_CONFLICT" not in codes:
                    codes.append("PINNED_CONFLICT")
            elif over:
                hits.append(Hit(d.day_index, si, p, "drop"))
            elif shut:
                hits.append(Hit(d.day_index, si, p, "replace"))
        return Affected(base, hits, codes, shifted - {(h.day, h.stop) for h in hits})
```
Chỗ `_affected` gán `day = itin.days[d.day_index]` (đã có từ Task 3) phải nằm **trước** nhánh này. Import `PACE_HOURS` từ `app.domain` và `last_day_limit` từ `app.rules` nếu Task 2 chưa thêm.

- [ ] **Step 4: Chạy toàn suite server**

Run: `cd server && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/app/replan.py server/tests/test_replan.py
git commit -m "feat(server): sự cố trễ — dời giờ, thay Stop đóng cửa, bỏ Stop quá giờ, giữ Stop ghim (#32)"
```

---

### Task 5: API mưa/trễ đi hết vòng

**Files:**
- Test: `server/tests/test_disruptions_api.py` (không cần sửa code server; nếu test fail vì code thì sửa ở `proposals.py`)

**Interfaces:**
- Consumes: `POST /trips/{id}/disruptions` với body `{version, kind, day_index, stop_index?, minutes?}`; `POST /trips/{id}/proposals/{pid}/apply`.

- [ ] **Step 1: Viết test**

```python
def post(client, h, tid, **body):
    return client.post(f"/trips/{tid}/disruptions", headers=h, json={"version": 1, "day_index": 0, **body})


def test_rain_round_trip_creates_version(client, conn):
    h, tid = seed(conn, client)
    conn.execute("UPDATE places SET outdoor = true WHERE name = 'Bảo tàng'")
    body = post(client, h, tid, kind="rain").json()
    assert [o["title"] for o in body["options"]] == ["Bỏ Bảo tàng"]  # không có tham-quan trong nhà nào khác
    r = client.post(f"/trips/{tid}/proposals/{body['proposal_id']}/apply", headers=h, json={"option": 0})
    assert r.status_code == 200
    assert r.json()["version"] == 2
    assert [s["place_id"] for s in r.json()["itinerary"]["days"][0]["stops"]] == \
        [body["options"][0]["itinerary"]["days"][0]["stops"][0]["place_id"]]


def test_late_shift_only(client, conn):
    h, tid = seed(conn, client)
    body = post(client, h, tid, kind="late", stop_index=0, minutes=30).json()
    o = body["options"][0]
    assert o["reason_codes"] == ["LATE_SHIFT"]
    assert [s["start_time"] for s in o["itinerary"]["days"][0]["stops"]] == ["09:30", "11:30"]


def test_bad_rain_or_late_shape_422(client, conn):
    h, tid = seed(conn, client)
    assert post(client, h, tid, kind="rain", stop_index=0).status_code == 422
    assert post(client, h, tid, kind="late", stop_index=0).status_code == 422
    assert post(client, h, tid, kind="late", stop_index=0, minutes=300).status_code == 422
    assert post(client, h, tid, kind="rain", day_index=5).status_code == 422
```

- [ ] **Step 2: Chạy**

Run: `docker compose up -d db && cd server && uv run pytest tests/test_disruptions_api.py -q`
Expected: PASS. Đây là test tích hợp cho Task 1–4. Nếu có test FAIL thì đó là lỗi thật: debug, không sửa assert.

- [ ] **Step 3: Chạy toàn suite + commit**

```bash
cd server && uv run pytest -q
git add server/tests/test_disruptions_api.py
git commit -m "test(server): API sự cố mưa/trễ tạo phương án và áp dụng thành version mới (#32)"
```

---

### Task 6: Client — nút Tôi trễ / Giả sử mưa, ProposalPanel dùng `title`

**Files:**
- Modify: `client/src/api.ts` (`DisruptionKind`, `ProposalOption`, `reportDisruption`, `NO_FEASIBLE_TEXT`, thay `optionPlace` bằng `optionPlaces`, thêm `rainable`)
- Modify: `client/src/components/Timeline.tsx`, `client/src/components/ProposalPanel.tsx`, `client/src/App.tsx`
- Test: `client/src/api.test.ts`

**Interfaces:**
- Consumes: JSON option có `title: string`, `added: number[]` (Task 2).
- Produces:
  - `type DisruptionReq = { kind: DisruptionKind; day_index: number; stop_index?: number; minutes?: number }`
  - `reportDisruption(token, tripId, version, d: DisruptionReq)`
  - `optionPlaces(o): Place[]`
  - `rainable(day: Day, places, pins: number[]): boolean`
  - Timeline `onDisrupt?: (d: DisruptionReq) => void`

- [ ] **Step 1: Viết test trước** (`api.test.ts`: thay khối `describe('optionPlace', …)`, sửa import `optionPlace` → `optionPlaces, rainable`)

```ts
describe('optionPlaces', () => {
  it('lấy các Place mới theo added', () => {
    const o = { added: [7], places: { '1': { id: 1, name: 'Cũ' }, '7': { id: 7, name: 'Mới' } } } as unknown as ProposalOption
    expect(optionPlaces(o).map((p) => p.name)).toEqual(['Mới'])
  })
})

describe('rainable', () => {
  const places = { '1': { outdoor: true }, '2': { outdoor: false } } as unknown as Record<string, Place>
  const day = { stops: [{ place_id: 1 }, { place_id: 2 }] } as unknown as Day
  it('có Stop ngoài trời chưa ghim', () => expect(rainable(day, places, [])).toBe(true))
  it('Stop ngoài trời đã ghim hết', () => expect(rainable(day, places, [1])).toBe(false))
})

it('noFeasibleText có mã mưa', () => {
  expect(noFeasibleText(['NOTHING_OUTDOOR'])).toEqual(['Ngày này không có Stop ngoài trời nào cần đổi.'])
})
```
Import thêm `type Day`, `type Place` nếu file test chưa có.

- [ ] **Step 2: Chạy, xác nhận fail**

Run: `cd client && npm test`
Expected: FAIL (`optionPlaces` / `rainable` chưa export).

- [ ] **Step 3: Cài đặt `api.ts`**

```ts
export type DisruptionKind = 'closed' | 'disliked' | 'rain' | 'late'
export type DisruptionReq = { kind: DisruptionKind; day_index: number; stop_index?: number; minutes?: number }
// ProposalOption: thêm `title: string; added: number[]`

export const reportDisruption = (token: string, tripId: number, version: number, d: DisruptionReq) =>
  request<Proposal>(token, `/trips/${tripId}/disruptions`, 'POST', { version, ...d })

// NO_FEASIBLE_TEXT thêm:
//   NOTHING_OUTDOOR: 'Ngày này không có Stop ngoài trời nào cần đổi.',
//   NO_INDOOR_CANDIDATE: 'Không có Place trong nhà nào thay được.',

export const optionPlaces = (o: ProposalOption): Place[] =>
  o.added.map((id) => o.places[id]).filter((p): p is Place => p !== undefined)

export const rainable = (day: Day, places: Record<string, Place>, pins: number[]) =>
  day.stops.some((s) => places[s.place_id]?.outdoor && !pins.includes(s.place_id))
```
Xoá `optionPlace`. Nếu `api.ts` chưa export type ngày, dùng `Itinerary['days'][number]` làm `Day`.

- [ ] **Step 4: UI**

`ProposalPanel.tsx`: `{i + 1}. {optionPlace(o)?.name}` → `{i + 1}. {o.title}`, bỏ import `optionPlace`.

`App.tsx`:
```ts
const disrupt = async (d: DisruptionReq) => {
  const p = await call(() => reportDisruption(token!, tripId!, version!, d))
  if (!p) return
  setProposal(p)
  setSearchPins((p.options ?? []).flatMap(optionPlaces))
}
```
Import `optionPlaces`, `type DisruptionReq`, bỏ `optionPlace`, `DisruptionKind` nếu không còn dùng.

`Timeline.tsx`:
- Prop: `onDisrupt?: (d: DisruptionReq) => void`.
- Header ngày: sau `<h2>…</h2>`, bọc cả header trong `flex items-center justify-between` và thêm nút:
```tsx
{!old && onDisrupt && rainable(day, places, pins) && (
  <button type="button" disabled={busy} onClick={() => onDisrupt({ kind: 'rain', day_index: i })}
    className="rounded border border-sky-300 px-2 py-0.5 text-xs text-sky-800 hover:bg-sky-50 disabled:opacity-40">
    ☂ Giả sử mưa
  </button>
)}
```
- Nút closed/disliked: `onClick={() => onDisrupt({ kind: k, day_index: i, stop_index: j })}`.
- Sau các nút đó, trong cùng khối `onDisrupt && on`, thêm hàng trễ (không khoá khi Stop đã ghim):
```tsx
{onDisrupt && on && (
  <span className="flex items-center gap-1">
    Tôi trễ
    {[15, 30, 60].map((m) => (
      <button key={m} type="button" disabled={busy}
        onClick={() => onDisrupt({ kind: 'late', day_index: i, stop_index: j, minutes: m })}
        className="rounded border border-stone-300 px-1.5 py-0.5 hover:bg-stone-100 disabled:opacity-40">
        {m}′
      </button>
    ))}
  </span>
)}
```

- [ ] **Step 5: Test + build**

Run: `cd client && npm test && npm run build`
Expected: test PASS, build không lỗi type.

- [ ] **Step 6: Commit**

```bash
git add client/src
git commit -m "feat(client): nút Tôi trễ 15/30/60′ và Giả sử mưa, ProposalPanel hiện title phương án (#32)"
```

---

### Task 7: E2E, tài liệu, review

**Files:**
- Modify: `docs/ROADMAP.md` (mục 4 lát C → `[x]`, bảng tổng quan nhóm 4: 3/7, "Việc cần làm ngay"), `docs/2026-09-25-hien-trang-app.md` (phần Revision giữ mục đích: thêm rain/late), `CONTEXT.md` nếu có mục Disruption (ghi rain/late đã có).

- [ ] **Step 1: E2E bằng Playwright với server thật**

`docker compose up -d --build api`. Dev server client ở cổng 5173. Mở Trip Đà Lạt 2 ngày (tạo mới nếu cần), rồi kiểm:
  1. Chọn ngày có Stop ngoài trời → bấm "☂ Giả sử mưa" → ProposalPanel chỉ có Place trong nhà (xem popup: "trong nhà") → Áp dụng → dãy version có thêm bản mới, Stop đổi được tô viền.
  2. Chọn Stop 2 → "Tôi trễ 60′" → phương án có "Chỉ dời giờ" hoặc "Bỏ …", giờ trên Timeline dời đúng sau khi áp dụng.
  3. Ghim một Stop ngoài trời → mưa → Stop ghim vẫn giữ nguyên.

Expected: cả 3 bước đúng, console không có lỗi.

- [ ] **Step 2: Cập nhật docs và commit**

```bash
git add docs CONTEXT.md
git commit -m "docs: ROADMAP + hiện trạng sau lát C mưa + trễ (#32)"
```

- [ ] **Step 3: Review cả nhánh** bằng subagent Opus theo skill thực thi. Chỉ sửa Critical/Important, mỗi bản sửa phải có test đi RED→GREEN. Mở PR "Closes #32".
