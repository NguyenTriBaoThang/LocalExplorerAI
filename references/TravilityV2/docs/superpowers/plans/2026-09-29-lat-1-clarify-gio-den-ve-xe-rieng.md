# Lát 1 — Clarify + giờ đến/về + xe riêng + Hub · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khi câu chat thiếu phương tiện hoặc giờ đến/về, AI hỏi lại một vòng bằng chip; lịch trình tôn trọng giờ đến/về, xuất phát từ sân bay/bến xe (Hub) và tính đúng chi phí xe máy/ô tô riêng.

**Architecture:** `parse_trip` để trống trường người dùng không nói. Hàm thuần `missing_questions` quyết định có hỏi lại không → event SSE `clarify` rồi đóng stream. Client gửi câu trả lời qua `POST /trips/{id}/plan` → hàm thuần `apply_answers` áp vào Trip (không gọi LLM) → `plan()` như cũ. Chi phí xe riêng, Leg từ Hub, Conflict giờ đến/về đều nằm trong `rules.py`.

**Tech Stack:** FastAPI + Pydantic v2 + psycopg/pgvector (server), pytest; React 19 + TypeScript + Vite + vitest (client).

**Spec:** `docs/superpowers/specs/2026-09-29-ca-nhan-hoa-trip-design.md` — lát 1 ở §11. Booked Stay, Must-visit, Traveler Profile thuộc lát 2–3, **không làm ở đây** (vì vậy câu hỏi `stay` ở spec §3 cũng để sang lát 2).

## Global Constraints

- Toàn bộ UI và lời nhắn tiếng Việt; thuật ngữ theo `CONTEXT.md` (Trip, Travel Mode, Stay, Leg, Conflict…).
- LLM chỉ chọn Place và xếp giờ; tiền, Leg, Conflict do code tính (`server/app/rules.py`).
- Không tính tiền/thời gian di chuyển liên tỉnh (ADR-0005). Arrival Mode chỉ để chọn Hub.
- Giờ đến: Stop ngày 1 bắt đầu trước `arrival_time + 60'` → Conflict `before_arrival`.
- Giờ về: Stop ngày cuối kết thúc sau `departure_time − 90'` → Conflict `after_departure`.
- `xe-may-rieng` = xăng/km như `xe-may`, không tiền thuê. `o-to-rieng` = `CAR_FUEL_PER_KM = 3_500` × km (một xe cho cả nhóm) + `CAR_PARKING_PER_DAY = 50_000` × số ngày. Leg < 800 m vẫn đi bộ.
- Travel Mode chưa nói và không được trả lời → mặc định `xe-may`.
- Hỏi lại tối đa một vòng; câu `arrival` chỉ hỏi khi Trip có ngày đi.
- Test server: `docker compose up -d db && cd server && uv run pytest`. Test client: `cd client && npm test && npm run build`.
- Commit message kết thúc bằng dòng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Ô giờ bỏ trống trên client gửi `""` → server trả 422. Kỳ vọng: client bỏ trường rỗng trước khi gửi (test `toAnswers`, Task 6).
2. LLM trả giờ sai định dạng ("2pm", "14h") → kỳ vọng: bỏ trường đó, Trip vẫn parse được, không báo lỗi "1–7 ngày" (Task 4).
3. Tới quá muộn (20:00) không còn chỗ cho Stop ngày 1 → kỳ vọng: vẫn có Itinerary kèm Conflict `before_arrival`, không exception (Task 2).
4. Gọi `/plan` lần hai hoặc trên Trip của người khác → kỳ vọng: 409 / 404 trước khi mở stream (Task 5).
5. Arrival Mode không có Hub ở Destination (vd `tu-lai`, hoặc `tau` ở Đà Lạt) → kỳ vọng: ngày 1 xuất phát từ Stay như cũ, không lỗi (Task 5 test `_hub`).

## File Structure

| File | Trách nhiệm trong lát này |
|---|---|
| `server/app/domain.py` | `TravelMode` mới, `ArrivalMode`, `Hub`, `TripAnswers`, trường giờ trên `Trip`, Leg/Conflict mở rộng |
| `server/app/rules.py` | Chi phí xe riêng, Leg từ Hub, Conflict giờ đến/về |
| `server/app/schema.sql`, `server/app/places.py`, `server/scripts/import_places.py`, `data/places/da-lat.json` | Cột `hubs` của Destination |
| `server/app/agent.py` | Tool `record_trip` mở rộng, `missing_questions`, `apply_answers`, `trip_brief`/`plan` nhận Hub |
| `server/app/trips.py` | Event `clarify`, `POST /trips/{id}/plan`, tách `_plan_and_save`, `_stream` |
| `client/src/api.ts` | Kiểu `clarify`, `streamPlan`, `toAnswers` |
| `client/src/components/ClarifyCard.tsx` (mới) | Chip + ô giờ + "Bỏ qua" |
| `client/src/components/ChatPanel.tsx`, `client/src/App.tsx`, `client/src/components/MapView.tsx` | Gắn ClarifyCard; Leg có id `null` |
| `CONTEXT.md`, `docs/PRD.md` | Thuật ngữ + trạng thái |

---

### Task 0: Commit các fix đang treo

Trên nhánh `feat/ca-nhan-hoa-trip` đang có 4 file sửa chưa commit từ phiên chạy thử (fix bản đồ MapLibre worker, fix Gemini `thought_signature`, log lỗi AI, test fake dùng `ChatCompletionMessage`). Task 4–5 dựa trên `agent.py`/`fakes.py` đã sửa.

- [ ] **Step 1: Chạy test để chắc trạng thái xanh**

Run: `docker compose up -d db && cd server && uv run pytest -q && cd ../client && npm test && npm run build`
Expected: server `58 passed`, client `2 passed`, build OK.

- [ ] **Step 2: Commit**

```bash
git add client/src/components/MapView.tsx server/app/agent.py server/app/trips.py server/tests/fakes.py
git commit -m "fix: MapLibre worker khi build, gửi lại nguyên message cho Gemini 3, log lỗi AI

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 1: Domain — Travel Mode mới, giờ đến/về, Hub, TripAnswers

**Files:**
- Modify: `server/app/domain.py`
- Test: `server/tests/test_domain.py`

**Interfaces:**
- Produces:
  - `TravelMode = Literal["xe-may", "grab", "xe-may-rieng", "o-to-rieng"]`, `DEFAULT_TRAVEL_MODE = "xe-may"`
  - `ArrivalMode = Literal["may-bay", "xe-khach", "tau", "tu-lai"]`
  - `Trip.travel_mode: TravelMode | None = None`; `Trip.origin_city: str | None`; `Trip.arrival_mode: ArrivalMode | None`; `Trip.arrival_time: str | None` (HH:MM); `Trip.departure_time: str | None` (HH:MM). Trip 1 ngày: giờ về ≤ giờ đến → `ValueError("Giờ về phải sau giờ đến")`.
  - `class Hub(BaseModel): name: str; lat: float; lon: float`
  - `class TripAnswers(BaseModel)`: `travel_mode`, `arrival_mode`, `arrival_time`, `departure_time` — tất cả tuỳ chọn.
  - `Leg.from_place_id / to_place_id: int | None` (`None` = Hub); `Leg.mode` thêm `"o-to"`.
  - `Conflict.kind` thêm `"before_arrival"`, `"after_departure"`.

- [ ] **Step 1: Write the failing tests** — thay `test_trip_defaults` và thêm vào cuối `server/tests/test_domain.py`:

```python
from app.domain import Draft, Trip, TripAnswers


def test_trip_defaults():
    t = Trip(destination="da-lat", days=3, budget=3_000_000)
    assert (t.travelers, t.pace, t.travel_mode, t.start_date) == (1, "vua", None, None)
    assert (t.arrival_time, t.departure_time, t.arrival_mode) == (None, None, None)


def test_one_day_departure_must_be_after_arrival():
    with pytest.raises(ValidationError, match="Giờ về phải sau giờ đến"):
        Trip(destination="da-lat", days=1, budget=1, arrival_time="15:00", departure_time="09:00")


def test_multi_day_departure_may_be_earlier_clock_time():
    t = Trip(destination="da-lat", days=2, budget=1, arrival_time="15:00", departure_time="09:00")
    assert t.departure_time == "09:00"


def test_trip_rejects_bad_time():
    with pytest.raises(ValidationError):
        Trip(destination="da-lat", days=1, budget=1, arrival_time="2pm")


def test_own_vehicle_modes_accepted():
    assert Trip(destination="da-lat", days=1, budget=1, travel_mode="o-to-rieng").travel_mode == "o-to-rieng"


def test_answers_all_optional():
    assert TripAnswers().model_dump(exclude_none=True) == {}
```

(Sửa dòng import đầu file thành `from app.domain import Draft, Trip, TripAnswers`.)

- [ ] **Step 2: Run to verify they fail**

Run: `cd server && uv run pytest tests/test_domain.py -q`
Expected: FAIL — `ImportError: cannot import name 'TripAnswers'`.

- [ ] **Step 3: Implement** — trong `server/app/domain.py`:

Đổi import và khai báo kiểu (thay 2 dòng `Pace`/`TravelMode` hiện có):

```python
from pydantic import BaseModel, Field, field_validator, model_validator

Pace = Literal["thong-tha", "vua", "day"]
TravelMode = Literal["xe-may", "grab", "xe-may-rieng", "o-to-rieng"]
ArrivalMode = Literal["may-bay", "xe-khach", "tau", "tu-lai"]
DEFAULT_TRAVEL_MODE: TravelMode = "xe-may"
```

Trong `class Trip`, thay dòng `travel_mode: TravelMode = "xe-may"` bằng:

```python
    travel_mode: TravelMode | None = None  # None = người dùng chưa nói → hỏi lại, không trả lời thì DEFAULT_TRAVEL_MODE
    origin_city: str | None = None
    arrival_mode: ArrivalMode | None = None
    arrival_time: str | None = Field(default=None, pattern=HHMM)
    departure_time: str | None = Field(default=None, pattern=HHMM)
```

và thêm validator sau `known_tags`:

```python
    @model_validator(mode="after")
    def departure_after_arrival(self):
        if self.days == 1 and self.arrival_time and self.departure_time and self.departure_time <= self.arrival_time:
            raise ValueError("Giờ về phải sau giờ đến")
        return self


class TripAnswers(BaseModel):
    """Câu trả lời cho event clarify; trường bỏ trống = người dùng không trả lời."""
    travel_mode: TravelMode | None = None
    arrival_mode: ArrivalMode | None = None
    arrival_time: str | None = Field(default=None, pattern=HHMM)
    departure_time: str | None = Field(default=None, pattern=HHMM)


class Hub(BaseModel):
    """Sân bay/bến xe/ga của một Destination — điểm đầu ngày 1 và điểm cuối ngày cuối."""
    name: str
    lat: float
    lon: float
```

Trong `class Leg`:

```python
    from_place_id: int | None  # None = Hub
    to_place_id: int | None
    distance_km: float
    duration_min: int
    mode: Literal["walk", "xe-may", "grab", "o-to"]
```

Trong `class Conflict`:

```python
    kind: Literal["over_budget", "closed", "missing_tag", "rain_outdoor", "before_arrival", "after_departure"]
```

Giữ `rules.py` xanh khi Trip mặc định `travel_mode=None`: trong `server/app/rules.py` thêm `DEFAULT_TRAVEL_MODE` vào dòng `from app.domain import ...` và trong `build_itinerary` thay `if trip.travel_mode == "xe-may":` bằng `if (trip.travel_mode or DEFAULT_TRAVEL_MODE) == "xe-may":` (Task 2 thay dòng này bằng biến `mode`).

- [ ] **Step 4: Run tests**

Run: `cd server && uv run pytest -q`
Expected: toàn bộ PASS.

- [ ] **Step 5: Commit**

```bash
git add server/app/domain.py server/app/rules.py server/tests/test_domain.py
git commit -m "feat(domain): Travel Mode xe riêng, giờ đến/về, Hub, TripAnswers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Rules — chi phí xe riêng, Leg từ Hub, Conflict giờ đến/về

**Files:**
- Modify: `server/app/rules.py`
- Test: `server/tests/test_rules.py`

**Interfaces:**
- Consumes: `Hub`, `DEFAULT_TRAVEL_MODE`, Trip trường giờ (Task 1).
- Produces:
  - `make_leg(a: Place | Hub, b: Place | Hub, mode: str, travelers: int) -> Leg` — `mode` nhận Travel Mode (`xe-may`, `grab`, `xe-may-rieng`, `o-to-rieng`).
  - `build_itinerary(trip, draft, places, rain=None, hub: Hub | None = None) -> Itinerary`
  - Hằng: `CAR_FUEL_PER_KM = 3_500`, `CAR_PARKING_PER_DAY = 50_000`, `ARRIVAL_BUFFER_MIN = 60`, `DEPARTURE_BUFFER_MIN = 90`.

- [ ] **Step 1: Write the failing tests** — trong `server/tests/test_rules.py`:

Sửa import và helper `draft` (thêm tham số `start`, tương thích ngược):

```python
from app.domain import Draft, Hub, Place, Trip
from app.rules import InvalidDraft, build_itinerary, is_open, make_leg


def draft(days, stay=None, start="09:00"):
    return Draft.model_validate({"stay_place_id": stay, "summary": "", "days": [
        {"stops": [{"place_id": pid, "start_time": start, "duration_min": 60} for pid in day]}
        for day in days]})
```

Thêm vào cuối file:

```python
HUB = Hub(name="Sân bay Liên Khương", lat=11.75, lon=108.37)
STAY = {9: P(9, kind="cho-o", hours={})}


def test_unset_travel_mode_defaults_to_rented_motorbike():
    trip = Trip(destination="da-lat", days=1, budget=10**9)
    assert build_itinerary(trip, draft([[1]]), {1: P(1)}).total_cost == 120_000


def test_own_motorbike_has_no_rent():
    trip = Trip(destination="da-lat", days=1, travelers=2, budget=10**9, travel_mode="xe-may-rieng")
    assert build_itinerary(trip, draft([[1]]), {1: P(1)}).total_cost == 0


def test_own_car_leg_is_one_car_fuel():
    leg = make_leg(P(1), P(2, lat=12.04), "o-to-rieng", 5)
    assert leg.mode == "o-to"
    assert leg.cost == round(leg.distance_km * 3_500)


def test_own_car_pays_parking_per_day():
    trip = Trip(destination="da-lat", days=2, travelers=5, budget=10**9, travel_mode="o-to-rieng")
    itin = build_itinerary(trip, draft([[1], [1]], stay=9), {1: P(1), **STAY})
    assert itin.total_cost == 2 * 50_000


def test_hub_starts_first_day_and_ends_last_day():
    trip = Trip(destination="da-lat", days=2, budget=10**9, travel_mode="grab")
    itin = build_itinerary(trip, draft([[1], [2]], stay=9), {1: P(1), 2: P(2), **STAY}, hub=HUB)
    d1, d2 = itin.days
    assert (d1.legs[0].from_place_id, d1.legs[-1].to_place_id) == (None, 9)
    assert (d2.legs[0].from_place_id, d2.legs[-1].to_place_id) == (9, None)
    assert d1.legs[0].mode == "grab" and d1.legs[0].distance_km > 20


def test_hub_without_stay_one_day():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab")
    legs = build_itinerary(trip, draft([[1]]), {1: P(1)}, hub=HUB).days[0].legs
    assert [(l.from_place_id, l.to_place_id) for l in legs] == [(None, 1), (1, None)]


def test_late_arrival_still_returns_itinerary_with_conflict():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab", arrival_time="20:00")
    itin = build_itinerary(trip, draft([[1]]), {1: P(1)})  # Stop 09:00
    assert [c.kind for c in itin.conflicts] == ["before_arrival"]
    assert "20:00" in itin.conflicts[0].message


def test_stop_after_arrival_buffer_is_fine():
    trip = Trip(destination="da-lat", days=1, budget=10**9, travel_mode="grab", arrival_time="14:00")
    assert build_itinerary(trip, draft([[1]], start="15:00"), {1: P(1)}).conflicts == []


def test_stop_too_close_to_departure_on_last_day():
    trip = Trip(destination="da-lat", days=2, budget=10**9, travel_mode="grab", departure_time="11:00")
    itin = build_itinerary(trip, draft([[1], [1]], stay=9), {1: P(1), **STAY})  # 09:00–10:00 > 11:00 − 90'
    assert [(c.kind, c.day_index) for c in itin.conflicts] == [("after_departure", 1)]
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd server && uv run pytest tests/test_rules.py -q`
Expected: FAIL — `build_itinerary() got an unexpected keyword argument 'hub'`, `KeyError: 'o-to'` / thiếu Conflict.

- [ ] **Step 3: Implement** — `server/app/rules.py`:

Import và hằng số:

```python
from app.domain import DEFAULT_TRAVEL_MODE, WEEKDAYS, Conflict, Day, Draft, Hub, Itinerary, Leg, Place, Stop, Trip

SPEED_KMH = {"walk": 4.5, "xe-may": 25, "grab": 25, "o-to": 25}
FUEL_PER_KM = 2_000
CAR_FUEL_PER_KM = 3_500
CAR_PARKING_PER_DAY = 50_000
GRAB_BASE, GRAB_PER_KM = 12_000, 9_000
MOTO_RENT_PER_DAY = 120_000
RAIN_PCT = 60
ARRIVAL_BUFFER_MIN = 60  # từ lúc tới đến Stop đầu tiên (nhận phòng, gửi đồ)
DEPARTURE_BUFFER_MIN = 90  # từ Stop cuối đến giờ về (ra sân bay/bến xe)
```

`haversine_km(a: Place | Hub, b: Place | Hub)` — chỉ đổi annotation. Thay `make_leg`:

```python
def make_leg(a: Place | Hub, b: Place | Hub, mode: str, travelers: int) -> Leg:
    km = round(haversine_km(a, b) * ROAD_FACTOR, 2)
    if km < WALK_MAX_KM:
        m, cost = "walk", 0
    elif mode == "grab":
        m, cost = "grab", (GRAB_BASE + round(km * GRAB_PER_KM)) * math.ceil(travelers / 4)
    elif mode == "o-to-rieng":
        m, cost = "o-to", round(km * CAR_FUEL_PER_KM)  # một xe cho cả nhóm (≤ 7 người)
    else:  # xe-may, xe-may-rieng
        m, cost = "xe-may", round(km * FUEL_PER_KM) * math.ceil(travelers / 2)
    return Leg(from_place_id=getattr(a, "id", None), to_place_id=getattr(b, "id", None), distance_km=km,
               duration_min=max(1, round(km / SPEED_KMH[m] * 60)), mode=m, cost=cost)
```

Thay `build_itinerary`:

```python
def build_itinerary(trip: Trip, draft: Draft, places: dict[int, Place],
                    rain: list[int | None] | None = None, hub: Hub | None = None) -> Itinerary:
    _check_draft(trip, draft, places)
    stay = places.get(draft.stay_place_id) if draft.stay_place_id is not None else None
    mode = trip.travel_mode or DEFAULT_TRAVEL_MODE
    pairs = math.ceil(trip.travelers / 2)  # 2 người/phòng, 2 người/xe
    total = stay.price * pairs * (trip.days - 1) if stay else 0
    if mode == "xe-may":
        total += MOTO_RENT_PER_DAY * pairs * trip.days
    elif mode == "o-to-rieng":
        total += CAR_PARKING_PER_DAY * trip.days

    days = []
    last = len(draft.days) - 1
    for i, d in enumerate(draft.days):
        stops = [Stop(**s.model_dump(), est_cost=places[s.place_id].price * trip.travelers)
                 for s in sorted(d.stops, key=lambda s: s.start_time)]
        start = hub if hub and i == 0 else stay
        end = hub if hub and i == last else stay
        route = [p for p in (start, *(places[s.place_id] for s in stops), end) if p is not None]
        legs = [make_leg(a, b, mode, trip.travelers) for a, b in zip(route, route[1:])]
        date = trip.start_date + dt.timedelta(days=i) if trip.start_date else None
        days.append(Day(date=date, stops=stops, legs=legs, rain_chance=rain[i] if rain else None))
        total += sum(s.est_cost for s in stops) + sum(leg.cost for leg in legs)

    itin = Itinerary(stay_place_id=draft.stay_place_id, days=days, total_cost=total, summary=draft.summary)
    itin.conflicts = find_conflicts(trip, itin, places)
    return itin
```

Trong `find_conflicts`, thêm `last = len(itin.days) - 1` trước vòng lặp ngày và, trong vòng `for s in day.stops:` ngay sau khối `rain_outdoor`:

```python
            if i == 0 and trip.arrival_time and _minutes(s.start_time) < _minutes(trip.arrival_time) + ARRIVAL_BUFFER_MIN:
                out.append(Conflict(kind="before_arrival", day_index=i, place_id=p.id,
                                    message=f"Ngày 1: {p.name} lúc {s.start_time} nhưng {trip.arrival_time} bạn mới tới"))
            if (i == last and trip.departure_time
                    and _minutes(s.start_time) + s.duration_min > _minutes(trip.departure_time) - DEPARTURE_BUFFER_MIN):
                out.append(Conflict(kind="after_departure", day_index=i, place_id=p.id,
                                    message=f"Ngày {i + 1}: {p.name} kết thúc quá sát giờ về {trip.departure_time}"))
```

Xoá dòng sửa tạm `(trip.travel_mode or DEFAULT_TRAVEL_MODE) == "xe-may"` của Task 1 (đã thay bằng biến `mode`).

- [ ] **Step 4: Run tests**

Run: `cd server && uv run pytest -q`
Expected: toàn bộ PASS.

- [ ] **Step 5: Commit**

```bash
git add server/app/rules.py server/tests/test_rules.py
git commit -m "feat(rules): chi phí xe riêng, Leg từ Hub, Conflict giờ đến/về

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Hub trong dữ liệu Destination

**Files:**
- Modify: `server/app/schema.sql`, `server/scripts/import_places.py`, `server/app/places.py:29-30`, `data/places/da-lat.json:2`
- Test: `server/tests/test_import_places.py`

**Interfaces:**
- Consumes: `ArrivalMode` (Task 1).
- Produces: bảng `destinations` có cột `hubs jsonb` dạng `{"may-bay": {"name", "lat", "lon"}, ...}`; `list_destinations(conn)` trả thêm khoá `hubs`.

- [ ] **Step 1: Write the failing tests** — `server/tests/test_import_places.py`:

Sửa helper `write` và import:

```python
from app.places import list_destinations
from scripts.import_places import expand_hours, import_file


def write(tmp_path, places, hubs=None):
    p = tmp_path / "x.json"
    dest = {"slug": "da-lat", "name": "Đà Lạt", "lat": 11.94, "lon": 108.44}
    if hubs is not None:
        dest["hubs"] = hubs
    p.write_text(json.dumps({"destination": dest, "places": places}), encoding="utf-8")
    return p
```

Thêm:

```python
def test_import_saves_hubs(conn, tmp_path):
    hubs = {"may-bay": {"name": "Sân bay Liên Khương", "lat": 11.75, "lon": 108.37}}
    import_file(conn, write(tmp_path, [PLACE], hubs), fake_embed)
    assert list_destinations(conn)[0]["hubs"] == hubs


def test_destination_without_hubs_gets_empty(conn, tmp_path):
    import_file(conn, write(tmp_path, [PLACE]), fake_embed)
    assert list_destinations(conn)[0]["hubs"] == {}


def test_import_rejects_unknown_hub(conn, tmp_path):
    with pytest.raises(ValueError, match="hub lạ"):
        import_file(conn, write(tmp_path, [PLACE], {"tau-ngam": {"name": "x", "lat": 1, "lon": 1}}), fake_embed)
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd server && uv run pytest tests/test_import_places.py -q`
Expected: FAIL — `KeyError: 'hubs'`.

- [ ] **Step 3: Implement**

`server/app/schema.sql` — thêm ngay sau bảng `destinations` (bảng đã tồn tại ở máy mọi người nên cần `ALTER`):

```sql
ALTER TABLE destinations ADD COLUMN IF NOT EXISTS hubs jsonb NOT NULL DEFAULT '{}';
```

`server/app/places.py`:

```python
def list_destinations(conn) -> list[dict]:
    return conn.execute("SELECT slug, name, lat, lon, hubs FROM destinations ORDER BY name").fetchall()
```

`server/scripts/import_places.py` — import `from typing import get_args` và `ArrivalMode` (`from app.domain import KINDS, TAGS, WEEKDAYS, ArrivalMode`); trong `import_file`, sau vòng kiểm tra Place:

```python
    hubs = d.get("hubs", {})
    bad_hubs = set(hubs) - set(get_args(ArrivalMode))
    if bad_hubs:
        raise ValueError(f"{d['slug']}: hub lạ {sorted(bad_hubs)}")
    conn.execute(
        """INSERT INTO destinations(slug,name,lat,lon,hubs) VALUES (%s,%s,%s,%s,%s)
           ON CONFLICT (slug) DO UPDATE SET name=excluded.name, lat=excluded.lat, lon=excluded.lon,
             hubs=excluded.hubs""",
        (d["slug"], d["name"], d["lat"], d["lon"], Jsonb(hubs)),
    )
```

(thay cho câu `INSERT INTO destinations` cũ).

`data/places/da-lat.json` dòng 2 — thêm Hub (toạ độ cần một thành viên kiểm chứng trên bản đồ trước khi merge, theo PRD §9):

```json
  "destination": {"slug": "da-lat", "name": "Đà Lạt", "lat": 11.9404, "lon": 108.4583,
    "hubs": {"may-bay": {"name": "Sân bay Liên Khương", "lat": 11.7503, "lon": 108.3674},
             "xe-khach": {"name": "Bến xe liên tỉnh Đà Lạt", "lat": 11.9276, "lon": 108.4459}}},
```

- [ ] **Step 4: Run tests**

Run: `cd server && uv run pytest -q`
Expected: toàn bộ PASS.

- [ ] **Step 5: Commit**

```bash
git add server/app/schema.sql server/app/places.py server/scripts/import_places.py data/places/da-lat.json server/tests/test_import_places.py
git commit -m "feat(data): Hub (sân bay/bến xe) cho Destination

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Agent — parse trường mới, missing_questions, apply_answers, brief có giờ/Hub

**Files:**
- Modify: `server/app/agent.py`
- Test: `server/tests/test_parse_trip.py`, `server/tests/test_clarify.py` (mới), `server/tests/test_plan.py`

**Interfaces:**
- Consumes: Task 1 (`TravelMode`, `ArrivalMode`, `TripAnswers`, `Hub`, `DEFAULT_TRAVEL_MODE`, `HHMM`), Task 2 (`build_itinerary(..., hub=)`, `ARRIVAL_BUFFER_MIN`, `DEPARTURE_BUFFER_MIN`).
- Produces:
  - `missing_questions(trip: Trip) -> list[dict]` — mỗi phần tử `{"field": "travel_mode" | "arrival", "text": str, "options": [{"value": str, "label": str}]}`.
  - `apply_answers(trip: Trip, answers: TripAnswers) -> Trip` — raise `pydantic.ValidationError` nếu kết quả không hợp lệ.
  - `trip_brief(trip, rain, hub: Hub | None = None) -> str`
  - `plan(conn, client, model, trip, embed_fn, rain, hub: Hub | None = None)`

- [ ] **Step 1: Write the failing tests**

Thêm vào `server/tests/test_parse_trip.py`:

```python
def test_parses_arrival_and_own_car():
    t = run({"destination": "da-lat", "days": 2, "budget": 1, "travel_mode": "o-to-rieng",
             "origin_city": "TP.HCM", "arrival_mode": "tu-lai", "arrival_time": "14:00", "departure_time": "16:00"})
    assert (t.travel_mode, t.origin_city, t.arrival_mode, t.arrival_time, t.departure_time) == (
        "o-to-rieng", "TP.HCM", "tu-lai", "14:00", "16:00")


def test_unstated_travel_mode_stays_none():
    assert run({"destination": "da-lat", "days": 2, "budget": 1}).travel_mode is None


def test_malformed_time_from_llm_is_dropped():
    t = run({"destination": "da-lat", "days": 2, "budget": 1, "arrival_time": "2pm", "departure_time": "14h"})
    assert (t.arrival_time, t.departure_time) == (None, None)
```

Tạo `server/tests/test_clarify.py`:

```python
import datetime as dt

import pytest
from pydantic import ValidationError

from app.agent import apply_answers, missing_questions
from app.domain import Trip, TripAnswers

BASE = {"destination": "da-lat", "days": 2, "budget": 1}
DATE = dt.date(2026, 10, 3)


def fields(trip):
    return [q["field"] for q in missing_questions(trip)]


def test_asks_travel_mode_when_unstated():
    qs = missing_questions(Trip(**BASE))
    assert [q["field"] for q in qs] == ["travel_mode"]
    assert {o["value"] for o in qs[0]["options"]} == {"xe-may", "grab", "xe-may-rieng", "o-to-rieng"}


def test_asks_arrival_only_with_start_date():
    assert fields(Trip(**BASE, travel_mode="grab")) == []
    assert fields(Trip(**BASE, travel_mode="grab", start_date=DATE)) == ["arrival"]


def test_known_arrival_is_not_asked():
    assert fields(Trip(**BASE, travel_mode="grab", start_date=DATE, arrival_time="14:00")) == []


def test_apply_answers_fills_and_defaults_travel_mode():
    t = apply_answers(Trip(**BASE), TripAnswers(arrival_time="14:00", arrival_mode="may-bay"))
    assert (t.travel_mode, t.arrival_time, t.arrival_mode) == ("xe-may", "14:00", "may-bay")


def test_apply_answers_sets_chosen_mode():
    assert apply_answers(Trip(**BASE), TripAnswers(travel_mode="o-to-rieng")).travel_mode == "o-to-rieng"


def test_apply_answers_revalidates_times():
    with pytest.raises(ValidationError, match="Giờ về phải sau giờ đến"):
        apply_answers(Trip(destination="da-lat", days=1, budget=1),
                      TripAnswers(arrival_time="15:00", departure_time="10:00"))
```

Thêm vào `server/tests/test_plan.py` (sửa import thành `from app.agent import MAX_STEPS, plan, trip_brief` và `from app.domain import Hub, Trip`):

```python
def test_brief_mentions_times_and_hub():
    trip = Trip(destination="da-lat", days=1, budget=1, arrival_time="14:00", departure_time="20:00")
    text = trip_brief(trip, None, Hub(name="Sân bay Liên Khương", lat=11.75, lon=108.37))
    assert "14:00" in text and "20:00" in text and "Sân bay Liên Khương" in text
    assert "Travel Mode: xe-may" in text  # chưa nói → mặc định
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd server && uv run pytest tests/test_parse_trip.py tests/test_clarify.py tests/test_plan.py -q`
Expected: FAIL — `ImportError: cannot import name 'apply_answers'`.

- [ ] **Step 3: Implement** — `server/app/agent.py`:

Import:

```python
import datetime as dt
import json
import re
from collections.abc import Iterator
from typing import get_args

from pydantic import ValidationError

from app.domain import (DEFAULT_TRAVEL_MODE, HHMM, KINDS, PACE_HOURS, PACE_STOPS, TAGS, ArrivalMode, Draft, Hub,
                        Itinerary, Place, TravelMode, Trip, TripAnswers)
from app.places import search_places
from app.rules import ARRIVAL_BUFFER_MIN, DEPARTURE_BUFFER_MIN, InvalidDraft, build_itinerary, vnd
```

Thêm 2 dòng cuối `PARSE_PROMPT`:

```python
PARSE_PROMPT = """Hôm nay là {today}. Chuyển yêu cầu du lịch của người dùng thành Trip bằng tool record_trip.
Destination hỗ trợ: {dests}. Nếu người dùng muốn đi nơi khác, destination = "unsupported".
Budget tính bằng VND cho cả nhóm ("3 triệu" = 3000000). Nếu không nói, ước lượng 1500000 × số người × số ngày.
Chỉ điền start_date (YYYY-MM-DD) khi người dùng nói rõ ngày đi.
Pace: "nhẹ nhàng/thong thả" = thong-tha, "đi nhiều/khám phá hết" = day, còn lại = vua.
Chỉ dùng Tag trong danh sách cho phép; Tag người dùng nói không muốn → avoided_tags.
Travel Mode (đi lại trong thành phố): thuê xe máy = xe-may, Grab/taxi = grab, xe máy của mình = xe-may-rieng, ô tô của mình = o-to-rieng.
Chỉ điền travel_mode, origin_city, arrival_mode, arrival_time, departure_time khi người dùng nói rõ; không đoán."""
```

Trong `_trip_tool`, thay dòng `"travel_mode"` và thêm trường:

```python
            "travel_mode": {"type": "string", "enum": list(get_args(TravelMode))},
            "origin_city": {"type": "string", "description": "Thành phố người dùng đi từ đó tới"},
            "arrival_mode": {"type": "string", "enum": list(get_args(ArrivalMode))},
            "arrival_time": {"type": "string", "description": "HH:MM, giờ tới Destination ngày 1"},
            "departure_time": {"type": "string", "description": "HH:MM, giờ rời Destination ngày cuối"},
```

Trong `parse_trip`, ngay sau `args = json.loads(...)` (khối try) và trước kiểm tra destination:

```python
    for k in ("arrival_time", "departure_time"):
        if not re.fullmatch(HHMM, str(args.get(k) or "")):
            args.pop(k, None)  # LLM có thể trả "2pm"/"14h" → coi như chưa nói
```

và sửa lời nhắn ValidationError:

```python
        raise TripParseError(
            "Chưa lập được Trip: hỗ trợ 1–7 ngày, 1–10 người, ngân sách lớn hơn 0 và giờ về phải sau giờ đến.") from e
```

Thêm sau `parse_trip`:

```python
TRAVEL_MODE_LABELS = {"xe-may": "Thuê xe máy", "grab": "Grab/taxi", "xe-may-rieng": "Xe máy riêng",
                      "o-to-rieng": "Ô tô riêng"}
ARRIVAL_MODE_LABELS = {"may-bay": "Máy bay", "xe-khach": "Xe khách", "tau": "Tàu hoả", "tu-lai": "Tự lái"}


def _options(labels: dict[str, str]) -> list[dict]:
    return [{"value": v, "label": label} for v, label in labels.items()]


def missing_questions(trip: Trip) -> list[dict]:
    """Câu hỏi lại cho thông tin người dùng chưa nói (spec §3). Code quyết định, không phải LLM."""
    qs = []
    if trip.travel_mode is None:
        qs.append({"field": "travel_mode", "text": "Bạn đi lại trong thành phố bằng gì?",
                   "options": _options(TRAVEL_MODE_LABELS)})
    if trip.start_date and not (trip.arrival_time or trip.departure_time):
        qs.append({"field": "arrival", "text": "Bạn tới bằng gì, mấy giờ tới và mấy giờ về?",
                   "options": _options(ARRIVAL_MODE_LABELS)})
    return qs


def apply_answers(trip: Trip, answers: TripAnswers) -> Trip:
    """Áp câu trả lời clarify vào Trip; Travel Mode vẫn trống → mặc định. Validate lại (giờ về > giờ đến)."""
    data = trip.model_dump() | answers.model_dump(exclude_none=True)
    data["travel_mode"] = data["travel_mode"] or DEFAULT_TRAVEL_MODE
    return Trip.model_validate(data)
```

Thay `trip_brief`:

```python
def trip_brief(trip: Trip, rain: list[int | None] | None, hub: Hub | None = None) -> str:
    lo, hi = PACE_STOPS[trip.pace]
    start, end = PACE_HOURS[trip.pace]
    when = f", bắt đầu {trip.start_date.isoformat()}" if trip.start_date else ""
    lines = [
        f"Destination: {trip.destination}",
        f"Số ngày: {trip.days}{when}",
        f"Số người: {trip.travelers}",
        f"Budget: {vnd(trip.budget)}",
        f"Pace: {lo}-{hi} Stop/ngày, từ {start} đến {end}",
        f"Travel Mode: {trip.travel_mode or DEFAULT_TRAVEL_MODE}",
        f"Tag bắt buộc: {', '.join(trip.required_tags) or 'không'}",
        f"Tag ưu tiên: {', '.join(trip.preferred_tags) or 'không'}",
        f"Tag cần tránh: {', '.join(trip.avoided_tags) or 'không'}",
    ]
    if trip.arrival_time:
        lines.append(f"Giờ tới ngày 1: {trip.arrival_time} — Stop đầu ngày 1 bắt đầu sau ít nhất {ARRIVAL_BUFFER_MIN} phút")
    if trip.departure_time:
        lines.append(f"Giờ về ngày cuối: {trip.departure_time} — Stop cuối ngày cuối kết thúc trước ít nhất "
                     f"{DEPARTURE_BUFFER_MIN} phút")
    if hub:
        lines.append(f"Ngày 1 xuất phát từ {hub.name}; ngày cuối kết thúc tại {hub.name}")
    if rain:
        chances = ", ".join(f"ngày {i + 1}: {'?' if r is None else str(r) + '%'}" for i, r in enumerate(rain))
        lines.append(f"Khả năng mưa: {chances}")
    return "\n".join(lines)
```

Trong `plan`: đổi chữ ký thành `def plan(conn, client, model: str, trip: Trip, embed_fn, rain: list[int | None] | None, hub: Hub | None = None) -> Iterator[dict]:`, dòng user message thành `{"role": "user", "content": trip_brief(trip, rain, hub)}`, và lời gọi `build_itinerary(trip, Draft.model_validate(args), seen, rain, hub)`.

- [ ] **Step 4: Run tests**

Run: `cd server && uv run pytest -q`
Expected: toàn bộ PASS (`test_trips_api.py` chưa đổi và vẫn xanh vì `trips.py` chưa gọi `missing_questions` — Task 5 mới thêm).

- [ ] **Step 5: Commit**

```bash
git add server/app/agent.py server/tests/test_parse_trip.py server/tests/test_clarify.py server/tests/test_plan.py
git commit -m "feat(agent): parse giờ đến/về & xe riêng, missing_questions, apply_answers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: API — event `clarify` và `POST /trips/{id}/plan`

**Files:**
- Modify: `server/app/trips.py`
- Test: `server/tests/test_trips_api.py`

**Interfaces:**
- Consumes: `missing_questions`, `apply_answers`, `plan(..., hub)` (Task 4); `TripAnswers`, `Hub` (Task 1); `list_destinations` trả `hubs` (Task 3).
- Produces:
  - Event SSE `{"type": "clarify", "trip_id": int, "questions": [...]}` — là event cuối của `POST /trips` khi thiếu thông tin.
  - `POST /trips/{trip_id}/plan`, body `TripAnswers` (`{}` = "Bỏ qua") → SSE `trip`, `tool_call`…, `itinerary` | `error`. 404 Trip không thuộc User; 409 đã có Itinerary; 422 câu trả lời không hợp lệ (`detail` là câu tiếng Việt).
  - `_hub(dest: dict, trip: Trip) -> Hub | None`

- [ ] **Step 1: Write the failing tests** — `server/tests/test_trips_api.py`:

Sửa `happy()` để Trip không bị hỏi lại (thêm `travel_mode`):

```python
def happy(pid):
    return [reply(("record_trip", {"destination": "da-lat", "days": 1, "budget": 2_000_000, "travel_mode": "grab"})),
            reply(("search_places", {"query": "cafe"})),
            reply(("submit_itinerary", {"summary": "ok", "days": [{"stops": [
                {"place_id": pid, "start_time": "09:00", "duration_min": 60, "reason": "cafe-chill"}]}]}))]


def ask_first(conn, client, monkeypatch, record=None):
    """POST /trips với câu thiếu Travel Mode → trả (headers, events)."""
    use_llm(monkeypatch, [reply(("record_trip", record or {"destination": "da-lat", "days": 1, "budget": 2_000_000}))])
    h = auth(client)
    return h, events(client.post("/trips", json={"message": "Đà Lạt 1 ngày"}, headers=h))
```

Thêm import `from app.domain import Trip` và các test:

```python
def test_missing_info_ends_with_clarify(client, conn, monkeypatch):
    add_place(conn)
    _, evs = ask_first(conn, client, monkeypatch)
    assert [e["type"] for e in evs] == ["thinking", "trip", "clarify"]
    assert [q["field"] for q in evs[-1]["questions"]] == ["travel_mode"]
    assert evs[-1]["trip_id"] == evs[1]["trip_id"]


def test_plan_applies_answers_and_persists(client, conn, monkeypatch):
    pid = add_place(conn, kind="cafe")
    h, evs = ask_first(conn, client, monkeypatch)
    trip_id = evs[-1]["trip_id"]
    use_llm(monkeypatch, happy(pid)[1:])
    evs = events(client.post(f"/trips/{trip_id}/plan", json={"travel_mode": "o-to-rieng"}, headers=h))
    assert [e["type"] for e in evs] == ["trip", "tool_call", "itinerary"]
    assert evs[0]["trip"]["travel_mode"] == "o-to-rieng"
    assert client.get(f"/trips/{trip_id}", headers=h).json()["trip"]["travel_mode"] == "o-to-rieng"


def test_plan_skip_uses_default_travel_mode(client, conn, monkeypatch):
    pid = add_place(conn)
    h, evs = ask_first(conn, client, monkeypatch)
    use_llm(monkeypatch, happy(pid)[1:])
    evs = events(client.post(f"/trips/{evs[-1]['trip_id']}/plan", json={}, headers=h))
    assert evs[0]["trip"]["travel_mode"] == "xe-may"


def test_plan_twice_is_409(client, conn, monkeypatch):
    pid = add_place(conn)
    use_llm(monkeypatch, happy(pid))
    h = auth(client)
    trip_id = events(client.post("/trips", json={"message": "x"}, headers=h))[-1]["trip_id"]
    assert client.post(f"/trips/{trip_id}/plan", json={}, headers=h).status_code == 409


def test_plan_other_users_trip_is_404(client, conn, monkeypatch):
    add_place(conn)
    _, evs = ask_first(conn, client, monkeypatch)
    other = auth(client, "binh@example.com")
    assert client.post(f"/trips/{evs[-1]['trip_id']}/plan", json={}, headers=other).status_code == 404


def test_plan_bad_times_is_422_in_vietnamese(client, conn, monkeypatch):
    add_place(conn)
    h, evs = ask_first(conn, client, monkeypatch)
    r = client.post(f"/trips/{evs[-1]['trip_id']}/plan",
                    json={"arrival_time": "15:00", "departure_time": "10:00"}, headers=h)
    assert r.status_code == 422 and r.json()["detail"] == "Giờ về phải sau giờ đến"


def test_arrival_hub_starts_day_one(client, conn, monkeypatch):
    pid = add_place(conn)
    conn.execute("""UPDATE destinations SET hubs = '{"may-bay": {"name": "Sân bay", "lat": 11.75, "lon": 108.37}}'""")
    record = {"destination": "da-lat", "days": 1, "budget": 2_000_000, "travel_mode": "grab", "arrival_mode": "may-bay"}
    use_llm(monkeypatch, [reply(("record_trip", record)), *happy(pid)[1:]])
    evs = events(client.post("/trips", json={"message": "x"}, headers=auth(client)))
    assert evs[-1]["itinerary"]["days"][0]["legs"][0]["from_place_id"] is None


def test_hub_missing_for_arrival_mode_falls_back():
    trip = Trip(destination="da-lat", days=1, budget=1, arrival_mode="tau")
    assert trips._hub({"hubs": {"may-bay": {"name": "x", "lat": 1, "lon": 1}}}, trip) is None
    assert trips._hub({"hubs": {}}, Trip(destination="da-lat", days=1, budget=1)) is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd server && uv run pytest tests/test_trips_api.py -q`
Expected: FAIL — không có event `clarify`, `/plan` trả 404/405, `trips._hub` không tồn tại.

- [ ] **Step 3: Implement** — thay phần dưới `sse()` trong `server/app/trips.py` (giữ `destinations`, `list_trips`, `get_trip` như cũ):

Import thêm:

```python
from pydantic import BaseModel, Field, ValidationError

from app.agent import TripParseError, UnsupportedDestination, apply_answers, missing_questions, parse_trip, plan
from app.domain import Hub, Trip, TripAnswers
```

Thay `create_trip` và `_run`:

```python
def _stream(run) -> StreamingResponse:
    """Chạy generator `run(conn)` trong SSE; lỗi → event error tiếng Việt."""
    def events():
        with stream_conn() as conn:
            try:
                yield from run(conn)
            except openai.OpenAIError:
                logger.exception("Lỗi gọi AI khi lập lịch trình")
                yield sse({"type": "error", "message": "Không kết nối được AI, kiểm tra mạng rồi thử lại nhé."})
            except Exception:
                logger.exception("Lỗi không lường trước khi lập lịch trình")
                yield sse({"type": "error", "message": "Có lỗi khi lập lịch trình, bạn thử lại nhé."})

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/trips")
def create_trip(body: NewTrip, user_id: int = Depends(current_user)):
    return _stream(lambda conn: _run(conn, user_id, body.message))


def _hub(dest: dict, trip: Trip) -> Hub | None:
    h = dest["hubs"].get(trip.arrival_mode) if trip.arrival_mode else None
    return Hub.model_validate(h) if h else None


def _trip_event(trip_id: int, trip: Trip, dest: dict) -> str:
    return sse({"type": "trip", "trip_id": trip_id, "trip": trip.model_dump(mode="json"),
                "center": [dest["lon"], dest["lat"]]})


def _plan_and_save(conn, client, trip_id: int, trip: Trip, dest: dict):
    rain = forecast.get_rain_chance(dest["lat"], dest["lon"], trip.start_date, trip.days)
    for ev in plan(conn, client, settings.llm_model, trip, llm.embed, rain, _hub(dest, trip)):
        if ev["type"] == "itinerary":
            conn.execute("INSERT INTO itineraries(trip_id, version, data) VALUES (%s, 1, %s)",
                         (trip_id, Jsonb({"itinerary": ev["itinerary"], "places": ev["places"]})))
            ev = {**ev, "trip_id": trip_id, "version": 1}
        yield sse(ev)


def _run(conn, user_id: int, message: str):
    dests = {d["slug"]: d for d in list_destinations(conn)}
    client = llm.chat_client()
    yield sse({"type": "thinking", "text": "Đang đọc yêu cầu của bạn…"})
    try:
        trip = parse_trip(client, settings.llm_model, message,
                          {slug: d["name"] for slug, d in dests.items()},
                          dt.datetime.now(VN_TZ).date())
    except (UnsupportedDestination, TripParseError) as e:
        yield sse({"type": "error", "message": str(e)})
        return
    d = dests[trip.destination]
    trip_id = conn.execute("INSERT INTO trips(user_id, spec) VALUES (%s, %s) RETURNING id",
                           (user_id, Jsonb(trip.model_dump(mode="json")))).fetchone()["id"]
    yield _trip_event(trip_id, trip, d)
    questions = missing_questions(trip)
    if questions:
        yield sse({"type": "clarify", "trip_id": trip_id, "questions": questions})
        return
    yield from _plan_and_save(conn, client, trip_id, trip, d)


@router.post("/trips/{trip_id}/plan")
def plan_trip(trip_id: int, answers: TripAnswers, user_id: int = Depends(current_user), conn=Depends(get_conn)):
    row = conn.execute("SELECT spec FROM trips WHERE id = %s AND user_id = %s", (trip_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    if conn.execute("SELECT 1 FROM itineraries WHERE trip_id = %s", (trip_id,)).fetchone():
        raise HTTPException(409, "Chuyến đi đã có lịch trình")
    try:
        trip = apply_answers(Trip.model_validate(row["spec"]), answers)
    except ValidationError as e:
        raise HTTPException(422, e.errors()[0]["msg"].removeprefix("Value error, ")) from None
    conn.execute("UPDATE trips SET spec = %s WHERE id = %s", (Jsonb(trip.model_dump(mode="json")), trip_id))

    def run(c):
        dest = next(d for d in list_destinations(c) if d["slug"] == trip.destination)
        yield _trip_event(trip_id, trip, dest)
        yield from _plan_and_save(c, llm.chat_client(), trip_id, trip, dest)

    return _stream(run)
```

> Ghi chú so với spec §3: spec ghi body `{answers | skip:true}`; ở đây "Bỏ qua" = gửi `{}` — cùng hiệu ứng (mọi trường trống → mặc định), bớt một trường.

- [ ] **Step 4: Run tests**

Run: `cd server && uv run pytest -q`
Expected: toàn bộ PASS.

- [ ] **Step 5: Commit**

```bash
git add server/app/trips.py server/tests/test_trips_api.py
git commit -m "feat(api): event clarify và POST /trips/{id}/plan

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Client — thẻ hỏi lại (chip + giờ) và gọi `/plan`

**Files:**
- Modify: `client/src/api.ts`, `client/src/App.tsx`, `client/src/components/ChatPanel.tsx`, `client/src/components/MapView.tsx:46`
- Create: `client/src/components/ClarifyCard.tsx`, `client/src/api.test.ts`

**Interfaces:**
- Consumes: event `clarify`, `POST /trips/{id}/plan` (Task 5).
- Produces: `streamPlan(token, tripId, answers, onEvent)`, `toAnswers(form)`, kiểu `Question`, `Answers`.

- [ ] **Step 1: Write the failing test** — `client/src/api.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { toAnswers } from './api'

describe('toAnswers', () => {
  it('bỏ ô giờ chưa nhập và chip chưa chọn để server không trả 422', () => {
    expect(toAnswers({ travel_mode: 'grab', arrival_mode: '', arrival_time: '', departure_time: '16:00' }))
      .toEqual({ travel_mode: 'grab', departure_time: '16:00' })
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd client && npm test`
Expected: FAIL — `toAnswers` is not exported.

- [ ] **Step 3: Implement**

`client/src/api.ts` — sửa kiểu `Leg` và `AgentEvent`, thêm kiểu mới:

```ts
export type Leg = {
  from_place_id: number | null; to_place_id: number | null  // null = Hub (sân bay/bến xe)
  distance_km: number; duration_min: number; mode: string; cost: number
}
export type Question = { field: 'travel_mode' | 'arrival'; text: string; options: { value: string; label: string }[] }
export type Answers = { travel_mode?: string; arrival_mode?: string; arrival_time?: string; departure_time?: string }
export type AgentEvent =
  | { type: 'thinking'; text: string }
  | { type: 'trip'; trip_id: number; trip: { budget: number }; center: [number, number] }
  | { type: 'tool_call'; name: string; query: string; places: Place[] }
  | { type: 'clarify'; trip_id: number; questions: Question[] }
  | { type: 'itinerary'; itinerary: Itinerary; places: Record<string, Place>; trip_id: number; version: number }
  | { type: 'error'; message: string }

/** Bỏ trường rỗng (ô giờ chưa nhập, chip chưa chọn) để server không trả 422. */
export function toAnswers(form: Record<string, string>): Answers {
  return Object.fromEntries(Object.entries(form).filter(([, v]) => v !== '')) as Answers
}
```

Thay `streamTrip` bằng hàm chung + hai hàm gọi:

```ts
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
  const reader = r.body.pipeThrough(new TextDecoderStream()).getReader()
  let buf = ''
  let finished = false
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += value
    const { events, rest } = parseSSE(buf)
    buf = rest
    events.forEach((e) => {
      const ev = e as AgentEvent
      if (ev.type === 'itinerary' || ev.type === 'error' || ev.type === 'clarify') finished = true
      onEvent(ev)
    })
  }
  if (!finished) onEvent({ type: 'error', message: 'Kết nối bị ngắt giữa chừng, bạn thử lại nhé.' })
}

export const streamTrip = (token: string, message: string, onEvent: (e: AgentEvent) => void) =>
  streamSSE(token, '/trips', { message }, onEvent)

export const streamPlan = (token: string, tripId: number, answers: Answers, onEvent: (e: AgentEvent) => void) =>
  streamSSE(token, `/trips/${tripId}/plan`, answers, onEvent)
```

`client/src/components/ClarifyCard.tsx`:

```tsx
import { useState } from 'react'
import { toAnswers, type Answers, type Question } from '../api'

export default function ClarifyCard({ questions, busy, onSubmit }: {
  questions: Question[]; busy: boolean; onSubmit: (answers: Answers) => void
}) {
  const [form, setForm] = useState<Record<string, string>>({})
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }))
  const chip = (k: string, v: string, label: string) => (
    <button key={v} type="button" aria-pressed={form[k] === v} onClick={() => set(k, form[k] === v ? '' : v)}
      className={`rounded-full border px-3 py-1 text-xs ${form[k] === v
        ? 'border-emerald-700 bg-emerald-700 text-white' : 'border-stone-300 bg-white'}`}>{label}</button>
  )
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-stone-200 bg-white p-3 text-sm">
      {questions.map((q) => (
        <fieldset key={q.field} className="flex flex-col gap-2">
          <legend className="mb-1">{q.text}</legend>
          <div className="flex flex-wrap gap-1">
            {q.options.map((o) => chip(q.field === 'arrival' ? 'arrival_mode' : q.field, o.value, o.label))}
          </div>
          {q.field === 'arrival' && (
            <div className="flex gap-3 text-xs">
              <label className="flex items-center gap-1">Tới lúc
                <input type="time" className="rounded border border-stone-300 px-1"
                  value={form.arrival_time ?? ''} onChange={(e) => set('arrival_time', e.target.value)} />
              </label>
              <label className="flex items-center gap-1">Về lúc
                <input type="time" className="rounded border border-stone-300 px-1"
                  value={form.departure_time ?? ''} onChange={(e) => set('departure_time', e.target.value)} />
              </label>
            </div>
          )}
        </fieldset>
      ))}
      <div className="flex gap-2">
        <button disabled={busy} onClick={() => onSubmit(toAnswers(form))}
          className="rounded-lg bg-emerald-700 px-3 py-1.5 text-white disabled:opacity-50">Lên lịch</button>
        <button disabled={busy} onClick={() => onSubmit({})}
          className="rounded-lg border border-stone-300 px-3 py-1.5 disabled:opacity-50">Bỏ qua, cứ lên lịch</button>
      </div>
    </div>
  )
}
```

`client/src/components/ChatPanel.tsx` — thêm `children` (thẻ hỏi lại) hiển thị cuối danh sách:

```tsx
import { useState, type ReactNode } from 'react'
...
export default function ChatPanel({ items, busy, onSend, children }: {
  items: ChatItem[]; busy: boolean; onSend: (message: string) => void; children?: ReactNode
}) {
```

và ngay trước dòng `{busy && <div className="animate-pulse ...`:

```tsx
        {children}
```

`client/src/App.tsx`:

```tsx
import { useState } from 'react'
import { streamPlan, streamTrip, type AgentEvent, type Answers, type Itinerary, type Place, type Question } from './api'
import ChatPanel, { type ChatItem } from './components/ChatPanel'
import ClarifyCard from './components/ClarifyCard'
```

Trong `App`, thêm state `const [clarify, setClarify] = useState<{ tripId: number; questions: Question[] } | null>(null)` và thay hàm `send` bằng:

```tsx
  function handle(e: AgentEvent) {
    switch (e.type) {
      case 'thinking': add({ role: 'ai', text: e.text }); break
      case 'trip': setCenter(e.center); setBudget(e.trip.budget); setItinerary(null); break
      case 'tool_call':
        add({ role: 'tool', text: `Đang tìm: ${e.query} (${e.places.length} kết quả)` })
        setSearchPins((p) => [...p, ...e.places.filter((x) => !p.some((y) => y.id === x.id))])
        break
      case 'clarify': setClarify({ tripId: e.trip_id, questions: e.questions }); break
      case 'itinerary':
        setPlaces(e.places); setItinerary(e.itinerary); setSearchPins([])
        add({ role: 'ai', text: e.itinerary.summary })
        break
      case 'error': add({ role: 'error', text: e.message }); break
    }
  }

  async function run(stream: (onEvent: (e: AgentEvent) => void) => Promise<void>) {
    setBusy(true)
    setSearchPins([])
    setClarify(null)
    try {
      await stream(handle)
    } catch (err) {
      if (err instanceof Error && err.message === 'unauthorized') { saveToken(null); setToken(null) }
      else add({ role: 'error', text: 'Mất kết nối tới máy chủ. Kiểm tra server đã chạy chưa.' })
    } finally {
      setBusy(false)
    }
  }

  const send = (message: string) => {
    add({ role: 'user', text: message })
    return run((on) => streamTrip(token!, message, on))
  }
  const answer = (tripId: number, a: Answers) => run((on) => streamPlan(token!, tripId, a, on))
```

và trong JSX:

```tsx
      <ChatPanel items={chat} busy={busy} onSend={send}>
        {clarify && <ClarifyCard questions={clarify.questions} busy={busy}
          onSubmit={(a) => answer(clarify.tripId, a)} />}
      </ChatPanel>
```

`client/src/components/MapView.tsx` dòng 46 — Leg với Hub có id `null`:

```tsx
          // ponytail: Leg tới/từ Hub chưa vẽ (Hub không có trong places); thêm marker Hub khi cần
          const a = leg.from_place_id != null ? places[leg.from_place_id] : undefined
          const b = leg.to_place_id != null ? places[leg.to_place_id] : undefined
```

- [ ] **Step 4: Run tests + build**

Run: `cd client && npm test && npm run build`
Expected: `3 passed`, build OK (không lỗi TypeScript).

- [ ] **Step 5: Commit**

```bash
git add client/src
git commit -m "feat(client): thẻ hỏi lại (phương tiện, giờ đến/về) và gọi /trips/{id}/plan

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Tài liệu + kiểm thử đầu-cuối

**Files:**
- Modify: `CONTEXT.md`, `docs/PRD.md`

- [ ] **Step 1: CONTEXT.md** — sửa định nghĩa **Travel Mode** và thêm 4 thuật ngữ sau mục Travel Mode:

```markdown
**Travel Mode** (Phương tiện):
Cách di chuyển chính trong thành phố của một Trip — xe máy thuê (mặc định), taxi/Grab, xe máy riêng hoặc ô tô riêng. Xe riêng không tính tiền thuê. Leg quá ngắn luôn đi bộ bất kể Travel Mode.
_Avoid_: Transport, vehicle

**Origin** (Nơi xuất phát):
Thành phố người dùng đi từ đó tới Destination. Chỉ để hiển thị và gợi ý Arrival Mode; không tính tiền.
_Avoid_: Điểm đi, home

**Arrival / Departure** (Giờ đến / Giờ về):
Thời điểm tới Destination ngày 1 và rời Destination ngày cuối. Stop phải cách giờ đến ít nhất 60 phút và cách giờ về ít nhất 90 phút.
_Avoid_: Check-in, check-out

**Arrival Mode** (Phương tiện đến):
Cách tới Destination — máy bay, xe khách, tàu, tự lái. Khác Travel Mode (đi lại trong thành phố). Chỉ dùng để chọn Hub.
_Avoid_: Transport

**Hub** (Điểm đến nơi):
Sân bay, bến xe hoặc ga của một Destination; điểm đầu ngày 1 và điểm cuối ngày cuối khi biết Arrival Mode.
_Avoid_: Terminal, station
```

- [ ] **Step 2: PRD** — trong `docs/PRD.md`:
  - §5.3 bảng: thêm dòng `| Thiếu phương tiện / giờ đến–về → hỏi lại một vòng bằng chip (event clarify, POST /trips/{id}/plan) | ✅ |`.
  - §5.6 bảng: thêm dòng `| Xe máy riêng / ô tô riêng: không tiền thuê; ô tô 3.500đ/km + gửi xe 50.000đ/ngày | ✅ |`.
  - §6: thêm 2 gạch đầu dòng: `Stop ngày 1 cách giờ đến ≥ 60 phút; Stop ngày cuối kết thúc trước giờ về ≥ 90 phút (Conflict before_arrival / after_departure).` và `Biết Arrival Mode và Destination có Hub → ngày 1 xuất phát từ Hub, ngày cuối kết thúc tại Hub.`
  - §8 dòng "API mới dự kiến": thêm `POST /trips/{id}/plan` (đã có); dòng "Event SSE": thêm event `clarify`.

- [ ] **Step 3: Kiểm thử đầu-cuối**

```bash
cd server && uv run python -m scripts.import_places ../data/places   # nạp Hub Đà Lạt
cd .. && docker compose up -d --build api
T=$(curl -s -X POST localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"email":"demo@travility.vn","password":"demo12345"}' | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])")
curl -sN -X POST localhost:8000/trips -H "authorization: Bearer $T" -H 'content-type: application/json' \
  -d '{"message":"Thứ 7 tuần này đi Đà Lạt 2 ngày, 5 triệu, thích cafe chill"}'
```

Expected: event cuối là `clarify` với 2 câu hỏi `travel_mode` và `arrival`. Lấy `trip_id` rồi:

```bash
curl -sN -X POST localhost:8000/trips/<trip_id>/plan -H "authorization: Bearer $T" -H 'content-type: application/json' \
  -d '{"travel_mode":"o-to-rieng","arrival_mode":"may-bay","arrival_time":"14:00","departure_time":"16:00"}'
```

Expected: `trip` → các `tool_call` → `itinerary`; Leg đầu ngày 1 có `from_place_id: null` (Sân bay Liên Khương); không có tiền thuê xe; Stop ngày 1 ≥ 15:00 hoặc có Conflict `before_arrival`.

Sau đó: `cd client && npm run build`, tắt app cũ, `rm -rf ~/Library/Caches/python3` (WebKit giữ bản build cũ), `cd desktop && uv run python main.py` → gõ câu trên → thấy thẻ hỏi lại với chip và ô giờ → "Lên lịch" → có lịch trình. Thử "Bỏ qua, cứ lên lịch" với một chuyến khác.

- [ ] **Step 4: Commit**

```bash
git add CONTEXT.md docs/PRD.md
git commit -m "docs: thuật ngữ Origin/Arrival/Hub, cập nhật PRD cho lát 1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
