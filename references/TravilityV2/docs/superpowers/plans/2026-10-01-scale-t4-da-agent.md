# Scale T4 — Lập lịch đa agent sau cờ `PLANNER_MODE` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khi `PLANNER_MODE=multi`, ba agent chuyên gia (`an-uong`, `tham-quan`, `cho-o`) tìm Place song song và nộp danh sách ngắn; agent tổng hợp (`agent.plan` hiện có) xếp thành Itinerary. Một agent lỗi hoặc quá 45 giây thì quay về agent đơn. Có script golden set so `single` với `multi` (#50).

**Architecture:** `app/multi.py` chứa chuyên gia (`shortlist`), phần gom kết quả (`gather`) và `plan` cùng chữ ký với `agent.plan`. Không có Redis: mỗi chuyên gia một thread trong tiến trình. Có Redis: điều phối `XADD` vào stream `agent_jobs`, worker `planner-agent` chạy chuyên gia và `RPUSH` event + kết quả về một khoá riêng của lần chạy. `trips._plan_and_save` là chỗ duy nhất chọn `single` hay `multi`.

**Tech Stack:** FastAPI, psycopg3, `redis` (redis-py 8, đồng bộ), `threading` + `queue`, React + vitest, docker compose, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-scale-he-phan-tan-design.md` — đọc §2 (S22–S25), §4, §7, §13, §14.

## Global Constraints

- Thiếu `PLANNER_MODE` (hoặc để trống) → `single`. 283 test hiện có phải xanh, **không sửa assert**.
- **Không sửa logic** `rules.py`, `replan.py`, `followup.py`, `llm.py`. `agent.plan` chỉ thêm ba tham số tuỳ chọn; gọi không truyền thì hành vi y nguyên.
- ADR-0001: Itinerary chỉ gồm Place đã nhận từ `search_places` (của chuyên gia hoặc của agent tổng hợp) hoặc có trong lịch cũ. Code ép, không tin LLM.
- Không thêm dependency. Test dùng Redis thật qua fixture `rds`; không dùng thư viện giả lập.
- Thông báo hướng tới người dùng là tiếng Việt.
- Tên Redis: stream `agent_jobs`, group `agents`, khoá `agent:{uuid}` (list, TTL 300 giây).
- Hằng số: `AGENT_WAIT_S = 45`, `MAX_SEARCHES = 4` (chuyên gia), agent tổng hợp `max_searches=2`.
- Lệnh test: `docker compose up -d db redis && cd server && uv run pytest` · `cd client && npm test && npm run build`.
- Commit message kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Chuyên gia nộp Place ngoài role hoặc `place_id` bịa.** Phải bị bỏ khỏi danh sách; danh sách rỗng là lỗi (Task 2 có test).
2. **Một chuyên gia treo.** Điều phối không chờ vô hạn: hết 45 giây thì chạy agent đơn (Task 3 có test).
3. **Redis chết hoặc không có `planner-agent` nào chạy.** Vẫn ra Itinerary bằng agent đơn (Task 4 có test).
4. **`PLANNER_MODE=` để trống trong `.env`.** Không được làm app chết lúc khởi động; coi như `single` (Task 3 có test).
5. **Việc agent xếp hàng quá lâu.** Agent không chạy việc mà điều phối đã bỏ cuộc (Task 4 có test).

## File Structure

| File | Trách nhiệm |
|---|---|
| `server/app/agent.py` | `plan` thêm `seeded`, `notes`, `max_searches`; `run_search` thêm `kinds`; `_for_llm` đổi tên `for_llm` |
| `server/app/multi.py` (mới) | Role, chuyên gia `shortlist`, `gather`, phát việc bằng thread / Redis, `plan`, `serve` (phía worker agent) |
| `server/app/config.py` | `planner_mode` |
| `server/app/trips.py` | `_plan_and_save` chọn planner |
| `server/app/worker.py` | `ensure_group` nhận stream/group; `agent_step`; `main --stream` |
| `server/scripts/golden.py` (mới) | 8 prompt, đo `single` / `multi`, in bảng |
| `client/src/api.ts`, `client/src/App.tsx` | `searchLine` ghép nhãn agent |
| `docker-compose.cluster.yml`, `server/.env.example` | service `planner-agent`, biến `PLANNER_MODE` |
| `server/tests/fakes.py` | `RoleClient` |
| `server/tests/test_multi.py` (mới), `test_golden.py` (mới) | test đa agent, test bảng tổng kết |

---

### Task 1: `agent.plan` nhận Place nạp sẵn

**Files:**
- Modify: `server/app/agent.py` (`_for_llm`, `run_search`, `plan`)
- Test: `server/tests/test_plan.py`

**Interfaces:**
- Produces:
  - `agent.for_llm(p: Place) -> dict` (đổi tên từ `_for_llm`)
  - `agent.run_search(conn, trip, embed_fn, args, seen, kinds: tuple[str, ...] | None = None) -> tuple[dict, str]` — có `kinds` thì chỉ giữ Place thuộc các kind đó
  - `agent.plan(..., previous=None, seeded: dict[int, Place] | None = None, notes: str = "", max_searches: int | None = None)`

- [ ] **Step 1: Viết test đỏ** — thêm vào cuối `server/tests/test_plan.py`:

```python
def test_seeded_places_usable_without_search(conn):
    pid = add_place(conn, "Cafe A", "cafe")
    client = FakeClient([reply(("submit_itinerary", stops(pid)))])
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, travel_mode="grab")
    events = list(plan(conn, client, "m", trip, fake_embed, None, seeded=get_places(conn, [pid]),
                       notes="Chuyên gia đã chọn: Cafe A"))
    assert [e["type"] for e in events] == ["itinerary"]
    assert "Chuyên gia đã chọn: Cafe A" in client.calls[0]["messages"][1]["content"]


def test_max_searches_refuses_extra_search(conn):
    pid = add_place(conn, "Cafe A", "cafe")
    client = FakeClient([reply(("search_places", {"query": "a"})), reply(("search_places", {"query": "b"})),
                         reply(("submit_itinerary", stops(pid)))])
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, travel_mode="grab")
    events = list(plan(conn, client, "m", trip, fake_embed, None, max_searches=1))
    assert [e["type"] for e in events] == ["tool_call", "itinerary"]
    assert "hết lượt tìm" in tool_messages(client)[1]


def test_place_outside_seeded_still_rejected(conn):
    a, b = add_place(conn, "A", "cafe"), add_place(conn, "B", "cafe")
    client = FakeClient([reply(("submit_itinerary", stops(b))), reply(("submit_itinerary", stops(a)))])
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, travel_mode="grab")
    events = list(plan(conn, client, "m", trip, fake_embed, None, seeded=get_places(conn, [a])))
    assert [s["place_id"] for s in events[-1]["itinerary"]["days"][0]["stops"]] == [a]
    assert tool_messages(client)[0].startswith("Lỗi")


def test_run_search_keeps_only_allowed_kinds(conn):
    from app.agent import run_search
    cafe = add_place(conn, "Cafe", "cafe")
    add_place(conn, "Quán", "an-uong")
    trip = Trip(destination="da-lat", days=1, budget=10_000_000, travel_mode="grab")
    seen = {}
    ev, result = run_search(conn, trip, fake_embed, {"query": "x"}, seen, kinds=("cafe",))
    assert list(seen) == [cafe] and [p["id"] for p in ev["places"]] == [cafe]
    assert "Quán" not in result
```

- [ ] **Step 2: Chạy, thấy đỏ**

Run: `cd server && uv run pytest tests/test_plan.py -q`
Expected: 4 FAIL — `TypeError: plan() got an unexpected keyword argument 'seeded'` / `'max_searches'` / `run_search() got an unexpected keyword argument 'kinds'`.

- [ ] **Step 3: Sửa `server/app/agent.py`**

Đổi tên `_for_llm` → `for_llm` (định nghĩa và chỗ gọi trong `run_search`). Sửa `run_search`:

```python
def run_search(conn, trip: Trip, embed_fn, args: dict, seen: dict[int, Place],
               kinds: tuple[str, ...] | None = None) -> tuple[dict, str]:
    """Tool search_places: thêm kết quả vào `seen`, trả (event tool_call, kết quả cho LLM).

    `kinds`: chỉ giữ Place thuộc các kind này (agent chuyên gia, spec scale §7).
    """
    query = str(args.get("query", ""))
    found = search_places(
        conn, trip.destination, embed_fn([query])[0],
        kind=args.get("kind") if args.get("kind") in KINDS else None,
        must_have_tags=[t for t in (args.get("must_have_tags") or []) if t in TAGS],
        exclude_tags=trip.avoided_tags)
    if kinds:
        found = [p for p in found if p.kind in kinds]
    seen.update({p.id: p for p in found})
    return ({"type": "tool_call", "name": "search_places", "query": query, "places": [place_brief(p) for p in found]},
            json.dumps([for_llm(p) for p in found], ensure_ascii=False))
```

Sửa đầu hàm `plan` và nhánh `search_places`:

```python
def plan(conn, client, model: str, trip: Trip, embed_fn, rain: list[int | None] | None,
         hub: Hub | None = None, user_messages: list[str] = (), previous: tuple[Itinerary, dict[int, Place]] | None = None,
         seeded: dict[int, Place] | None = None, notes: str = "", max_searches: int | None = None,
         ) -> Iterator[dict]:
    # chỉ Place AI đã nhận từ search_places, có trong lịch cũ, hoặc do agent chuyên gia chọn (seeded) mới hợp lệ
    seen: dict[int, Place] = {**(previous[1] if previous else {}), **(seeded or {})}
    pinned = {s.place_id for d in previous[0].days for s in d.stops if s.pinned} if previous else set()
    brief = trip_brief(trip, rain, hub, user_messages)
    if previous:
        brief += "\n\n" + previous_brief(*previous)
    if notes:
        brief += "\n\n" + notes
    messages = [{"role": "system", "content": PLAN_PROMPT}, {"role": "user", "content": brief}]
    submits = invalid = searches = 0
```

```python
            elif c.function.name == "search_places":
                searches += 1
                if max_searches is not None and searches > max_searches:
                    result = "Lỗi: hết lượt tìm. Dùng Place đã có rồi gọi submit_itinerary."
                else:
                    ev, result = run_search(conn, trip, embed_fn, args, seen)
                    yield ev
```

- [ ] **Step 4: Chạy, thấy xanh**

Run: `cd server && uv run pytest tests/test_plan.py tests/test_followup.py -q`
Expected: tất cả PASS (17 test cũ của `test_plan.py` + 4 mới; `test_followup.py` không đổi).

- [ ] **Step 5: Commit**

```bash
git add server/app/agent.py server/tests/test_plan.py
git commit -m "feat(server): agent.plan nhận Place nạp sẵn, ghi chú và giới hạn lượt tìm (#50)"
```

---

### Task 2: Agent chuyên gia `multi.shortlist`

**Files:**
- Create: `server/app/multi.py`
- Modify: `server/tests/fakes.py`
- Test: `server/tests/test_multi.py` (mới)

**Interfaces:**
- Consumes: `agent.run_search(..., kinds=)`, `agent.trip_brief`, `agent.PLAN_TOOLS`
- Produces:
  - `multi.ROLES: dict[str, tuple[str, tuple[str, ...], str]]` — role → (nhãn, các kind, việc)
  - `multi.roles_for(trip) -> list[str]`, `multi.wanted(trip, role) -> int`
  - `multi.AgentFailed(Exception)`
  - `multi.shortlist(conn, client, model, trip, role, embed_fn, rain, user_messages, emit) -> dict` — trả `{"role": str, "place_ids": list[int], "note": str}`; `emit(event)` nhận từng event `tool_call` có thêm `"agent": role`
  - `tests.fakes.RoleClient(scripts: dict[str, list])` — chọn kịch bản theo đoạn chữ có trong system prompt

- [ ] **Step 1: Thêm `RoleClient` vào cuối `server/tests/fakes.py`**

```python
class RoleClient:
    """LLM giả cho đa agent: mỗi kịch bản một hàng đợi riêng, chọn theo đoạn chữ có trong system prompt.

    Các chuyên gia chạy song song nên một hàng đợi chung (FakeClient) sẽ trả nhầm lượt.
    Phần tử là hàm thì được gọi lấy kết quả (dùng để ngủ hoặc ném lỗi muộn).
    """

    def __init__(self, scripts: dict[str, list]):
        self.scripts = {k: list(v) for k, v in scripts.items()}
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        system = kwargs["messages"][0]["content"]
        r = self.scripts[next(k for k in self.scripts if k in system)].pop(0)
        if callable(r):
            r = r()
        if isinstance(r, Exception):
            raise r
        return r

    def calls_for(self, key: str) -> list[dict]:
        return [c for c in self.calls if key in c["messages"][0]["content"]]
```

- [ ] **Step 2: Viết test đỏ** — tạo `server/tests/test_multi.py`:

```python
from contextlib import nullcontext

import pytest

from app import multi, rules
from app.domain import Trip
from tests.fakes import RoleClient, reply
from tests.helpers import add_place, unit_vec

FOOD, SIGHT, STAY = "chuyên gia Ăn uống", "chuyên gia Tham quan", "chuyên gia Chỗ ở"
SYNTH = "trợ lý lập lịch trình"
SEARCH = reply(("search_places", {"query": "x"}))


@pytest.fixture(autouse=True)
def env(conn, monkeypatch):
    monkeypatch.setattr(rules, "MEALS", ())


def fake_embed(texts):
    return [unit_vec(0) for _ in texts]


def trip(days=1):
    return Trip(destination="da-lat", days=days, budget=10_000_000, travel_mode="grab")


def pick(*ids, note="ghi chú"):
    return reply(("submit_shortlist", {"place_ids": list(ids), "note": note}))


def one(conn, role, responses):
    events, client = [], RoleClient({"chuyên gia": responses})
    return client, events, multi.shortlist(conn, client, "m", trip(), role, fake_embed, None, [], events.append)


def test_roles_skip_stay_for_one_day_trip():
    assert multi.roles_for(trip(1)) == ["an-uong", "tham-quan"]
    assert multi.roles_for(trip(2)) == ["an-uong", "tham-quan", "cho-o"]


def test_wanted_follows_meals_and_pace():
    t = trip(2)  # Pace vừa: 5 Stop/ngày, 3 bữa/ngày
    assert [multi.wanted(t, r) for r in ("an-uong", "tham-quan", "cho-o")] == [12, 8, 3]


def test_specialist_returns_places_it_searched(conn):
    food = add_place(conn, "Quán", "an-uong")
    add_place(conn, "Cafe", "cafe")
    client, events, out = one(conn, "an-uong", [SEARCH, pick(food)])
    assert out == {"role": "an-uong", "place_ids": [food], "note": "ghi chú"}
    assert events[0]["type"] == "tool_call" and events[0]["agent"] == "an-uong"
    assert [p["id"] for p in events[0]["places"]] == [food]  # code ép kind theo role
    assert "Ăn uống" in client.calls[0]["messages"][0]["content"]


def test_specialist_cannot_pick_another_roles_kind(conn):
    food, stay = add_place(conn, "Quán", "an-uong"), add_place(conn, "Khách sạn", "cho-o")
    _, _, out = one(conn, "an-uong", [reply(("search_places", {"query": "x", "kind": "cho-o"})), pick(stay, food)])
    assert out["place_ids"] == [food]


def test_sightseeing_role_takes_cafe_but_not_food(conn):
    cafe, food = add_place(conn, "Cafe", "cafe"), add_place(conn, "Quán", "an-uong")
    _, _, out = one(conn, "tham-quan", [reply(("search_places", {"query": "x", "kind": "an-uong"})), pick(cafe, food)])
    assert out["place_ids"] == [cafe]


def test_unknown_ids_dropped_and_empty_shortlist_fails(conn):
    add_place(conn, "Cafe", "cafe")
    with pytest.raises(multi.AgentFailed):
        one(conn, "tham-quan", [SEARCH] + [pick(999)] * 5)


def test_fifth_search_is_refused(conn):
    cafe = add_place(conn, "Cafe", "cafe")
    client, events, out = one(conn, "tham-quan", [SEARCH] * 5 + [pick(cafe)])
    assert len(events) == 4 and out["place_ids"] == [cafe]
    tool = [m["content"] for m in client.calls[-1]["messages"] if m.get("role") == "tool"]
    assert "hết lượt tìm" in tool[4]
```

- [ ] **Step 3: Chạy, thấy đỏ**

Run: `cd server && uv run pytest tests/test_multi.py -q`
Expected: lỗi collect `ImportError: cannot import name 'multi' from 'app'`.

- [ ] **Step 4: Tạo `server/app/multi.py`**

```python
"""Lập lịch đa agent (spec scale §7): ba chuyên gia tìm Place song song, agent tổng hợp xếp lịch."""
import copy
import json

from app.agent import PLAN_TOOLS, run_search, trip_brief
from app.domain import PACE_STOPS, Place, Trip

# role → (nhãn, các kind được chọn, việc cần làm)
ROLES = {
    "an-uong": ("Ăn uống", ("an-uong",),
                "quán ăn cho bữa sáng, trưa, tối; ưu tiên quán ăn no bụng cho bữa trưa và tối"),
    "tham-quan": ("Tham quan", ("tham-quan", "cafe", "giai-tri"),
                  "điểm tham quan, cafe, giải trí; ngày khả năng mưa cao thì ưu tiên Place trong nhà (outdoor=false)"),
    "cho-o": ("Chỗ ở", ("cho-o",), "chỗ ở hợp Budget và Tag"),
}
MAX_SEARCHES = 4

SPECIALIST_PROMPT = """Bạn là chuyên gia {label} trong nhóm lập lịch du lịch cho người Việt.
Việc của bạn: chọn danh sách ngắn khoảng {n} Place — {task}. Một agent khác sẽ xếp lịch từ danh sách này.
Quy tắc:
- Chỉ dùng place_id nhận được từ search_places. Không bao giờ tự nghĩ ra địa điểm.
- Gọi search_places tối đa {max} lần, mỗi lần cho một nhu cầu khác nhau.
- Tôn trọng Tag bắt buộc, tránh Tag cần tránh, cân Budget của cả chuyến.
- Xong thì gọi submit_shortlist. note: 1 câu tiếng Việt gợi ý cách dùng danh sách (vd quán nào hợp bữa nào)."""


class AgentFailed(Exception):
    pass


def roles_for(trip: Trip) -> list[str]:
    return [r for r in ROLES if r != "cho-o" or trip.days > 1]


def wanted(trip: Trip, role: str) -> int:
    """Cỡ danh sách ngắn (spec §7): 2 × số bữa; 2 × số Stop còn lại theo Pace; 3 chỗ ở."""
    meals = 3 * trip.days
    if role == "an-uong":
        return 2 * meals
    if role == "cho-o":
        return 3
    return 2 * max(PACE_STOPS[trip.pace][1] * trip.days - meals, trip.days)


def _tools(kinds: tuple[str, ...]) -> list[dict]:
    search = copy.deepcopy(PLAN_TOOLS[0])
    search["function"]["parameters"]["properties"]["kind"]["enum"] = list(kinds)
    return [search, {"type": "function", "function": {
        "name": "submit_shortlist", "description": "Nộp danh sách ngắn các Place đã chọn.",
        "parameters": {"type": "object", "properties": {
            "place_ids": {"type": "array", "items": {"type": "integer"}},
            "note": {"type": "string"},
        }, "required": ["place_ids", "note"]},
    }}]


def shortlist(conn, client, model: str, trip: Trip, role: str, embed_fn, rain, user_messages: list[str], emit) -> dict:
    """Một chuyên gia: tìm Place trong các kind của role rồi nộp danh sách ngắn {"role", "place_ids", "note"}.

    Mỗi lượt tìm gọi emit(event tool_call kèm agent=role). Không nộp được danh sách hợp lệ → AgentFailed.
    """
    label, kinds, task = ROLES[role]
    seen: dict[int, Place] = {}
    messages = [{"role": "system", "content": SPECIALIST_PROMPT.format(label=label, n=wanted(trip, role), task=task,
                                                                      max=MAX_SEARCHES)},
                {"role": "user", "content": trip_brief(trip, rain, None, user_messages)}]
    searches = 0
    for _ in range(MAX_SEARCHES + 2):
        r = client.chat.completions.create(model=model, messages=messages, tools=_tools(kinds), tool_choice="required")
        msg = r.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))  # nguyên message: Gemini cần thought_signature
        for c in msg.tool_calls or []:
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                args = None
            if not isinstance(args, dict):
                result = "Lỗi: arguments không phải JSON object hợp lệ."
            elif c.function.name == "search_places":
                searches += 1
                if searches > MAX_SEARCHES:
                    result = "Lỗi: hết lượt tìm. Gọi submit_shortlist với Place đã có."
                else:  # ADR-0001: code ép kind theo role, không tin LLM
                    kind = kinds[0] if len(kinds) == 1 else args.get("kind") if args.get("kind") in kinds else None
                    ev, result = run_search(conn, trip, embed_fn, {**args, "kind": kind}, seen, kinds)
                    emit({**ev, "agent": role})
            elif c.function.name == "submit_shortlist":
                ids = [i for i in dict.fromkeys(args.get("place_ids") or []) if i in seen]
                if ids:
                    return {"role": role, "place_ids": ids, "note": str(args.get("note") or "")}
                result = "Lỗi: danh sách rỗng. Chỉ dùng place_id đã nhận từ search_places."
            else:
                result = f"Lỗi: không có tool {c.function.name}."
            messages.append({"role": "tool", "tool_call_id": c.id, "content": result})
    raise AgentFailed(f"agent {role} không nộp được danh sách ngắn")
```

- [ ] **Step 5: Chạy, thấy xanh**

Run: `cd server && uv run pytest tests/test_multi.py -q`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add server/app/multi.py server/tests/fakes.py server/tests/test_multi.py
git commit -m "feat(server): agent chuyên gia chọn danh sách ngắn theo role, code ép kind (#50)"
```

---

### Task 3: `multi.plan` bằng thread, dự phòng, cờ `PLANNER_MODE`

**Files:**
- Modify: `server/app/multi.py`, `server/app/config.py`, `server/app/trips.py:107-115`, `server/tests/conftest.py`
- Test: `server/tests/test_multi.py`, `server/tests/test_config.py`, `server/tests/test_trips_api.py`

**Interfaces:**
- Consumes: `multi.shortlist`, `agent.plan(seeded=, notes=, max_searches=)`, `agent.for_llm`, `places.get_places`
- Produces:
  - `settings.planner_mode: Literal["single", "multi"]` (trống → `single`)
  - `multi.AGENT_WAIT_S = 45`, `multi.FALLBACK_TEXT`, `multi.agent_conn` (hàm mở kết nối, test thay)
  - `multi._work(put, client, model, trip, role, embed_fn, rain, user_messages) -> None` — event, kết quả `{"role","place_ids","note"}` hoặc lỗi `{"role","error"}` đều qua `put`
  - `multi._local(client, model, trip, embed_fn, rain, user_messages, roles) -> recv`, với `recv(timeout: float) -> dict | None`
  - `multi.gather(recv, roles)` — generator: yield event, `return` danh sách kết quả hoặc `None`
  - `multi.plan(conn, client, model, trip, embed_fn, rain, hub=None, user_messages=(), previous=None, local=False) -> Iterator[dict]`

- [ ] **Step 1: Viết test đỏ**

Thêm vào `server/tests/conftest.py` cạnh các dòng `os.environ[...]` đầu file:

```python
os.environ["PLANNER_MODE"] = ""  # máy dev có thể đặt multi trong .env — test mặc định chạy agent đơn
```

Thêm vào `server/tests/test_config.py`:

```python
def test_planner_mode_blank_is_single():
    assert Settings(_env_file=None, planner_mode="").planner_mode == "single"
    assert Settings(_env_file=None).planner_mode == "single"


def test_planner_mode_multi_accepted_and_garbage_rejected():
    assert Settings(_env_file=None, planner_mode="multi").planner_mode == "multi"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, planner_mode="nhieu")
```

Trong `server/tests/test_multi.py`: thêm `import time`, thêm dòng vào fixture `env`:

```python
    monkeypatch.setattr(multi, "agent_conn", lambda: nullcontext(conn))
```

và thêm các test:

```python
def stops(*ids):
    return {"summary": "Lịch trình thử", "days": [{"stops": [
        {"place_id": pid, "start_time": f"{9 + i:02d}:00", "duration_min": 60, "reason": "hợp sở thích"}
        for i, pid in enumerate(ids)]}]}


def used(events):
    return [s["place_id"] for s in events[-1]["itinerary"]["days"][0]["stops"]]


def test_multi_plan_builds_itinerary_from_shortlists(conn):
    food, cafe = add_place(conn, "Quán Bà Tư", "an-uong"), add_place(conn, "Cafe Tùng", "cafe")
    rc = RoleClient({FOOD: [SEARCH, pick(food, note="hợp bữa trưa")], SIGHT: [SEARCH, pick(cafe)],
                     SYNTH: [reply(("submit_itinerary", stops(food, cafe)))]})
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None))
    assert events[0] == {"type": "thinking", "text": "Các chuyên gia đang tìm địa điểm…"}
    assert {e["agent"] for e in events if e["type"] == "tool_call"} == {"an-uong", "tham-quan"}
    assert used(events) == [food, cafe]
    brief = rc.calls_for(SYNTH)[0]["messages"][1]["content"]
    assert "Quán Bà Tư" in brief and "hợp bữa trưa" in brief and "Cafe Tùng" in brief
    assert not rc.calls_for(STAY)  # Trip 1 ngày không gọi agent chỗ ở


def test_synthesizer_still_rejects_place_outside_shortlists(conn):
    food, cafe, other = add_place(conn, "Quán", "an-uong"), add_place(conn, "Cafe", "cafe"), add_place(conn, "Lạ", "cafe")
    # "Lạ" có thật và chuyên gia đã thấy khi tìm, nhưng không được chọn vào danh sách ngắn
    rc = RoleClient({FOOD: [SEARCH, pick(food)], SIGHT: [SEARCH, pick(cafe)],
                     SYNTH: [reply(("submit_itinerary", stops(other))), reply(("submit_itinerary", stops(cafe)))]})
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None))
    assert used(events) == [cafe]
    tool = [m["content"] for m in rc.calls_for(SYNTH)[-1]["messages"] if m.get("role") == "tool"]
    assert tool[0].startswith("Lỗi")


def test_agent_error_falls_back_to_single(conn):
    cafe = add_place(conn, "Cafe", "cafe")
    rc = RoleClient({FOOD: [RuntimeError("boom")], SIGHT: [SEARCH, pick(cafe)],
                     SYNTH: [SEARCH, reply(("submit_itinerary", stops(cafe)))]})
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None))
    assert {"type": "thinking", "text": multi.FALLBACK_TEXT} in events
    assert used(events) == [cafe]
    assert "Các chuyên gia đã chọn" not in rc.calls_for(SYNTH)[0]["messages"][1]["content"]


def test_slow_agent_falls_back_after_deadline(conn, monkeypatch):
    monkeypatch.setattr(multi, "AGENT_WAIT_S", 0.3)
    cafe = add_place(conn, "Cafe", "cafe")

    def slow():
        time.sleep(0.8)
        raise RuntimeError("muộn")

    rc = RoleClient({FOOD: [slow], SIGHT: [SEARCH, pick(cafe)],
                     SYNTH: [SEARCH, reply(("submit_itinerary", stops(cafe)))]})
    t0 = time.monotonic()
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None))
    assert time.monotonic() - t0 < 0.8  # không chờ agent chậm
    assert {"type": "thinking", "text": multi.FALLBACK_TEXT} in events and used(events) == [cafe]
    time.sleep(0.7)  # để thread chậm kết thúc trước khi fixture đóng kết nối
```

Thêm vào `server/tests/test_trips_api.py` (import thêm `multi` trong dòng `from app import …` và `RoleClient` từ `tests.fakes`):

```python
def test_multi_mode_plans_with_specialists_in_threads(client, conn, monkeypatch):
    monkeypatch.setattr(settings, "planner_mode", "multi")
    monkeypatch.setattr(multi, "agent_conn", lambda: nullcontext(conn))
    food, cafe = add_place(conn, "Quán", "an-uong"), add_place(conn, "Cafe", "cafe")
    search = reply(("search_places", {"query": "x"}))
    rc = RoleClient({
        "record_trip": [reply(("record_trip", {"destination": "da-lat", "days": 1, "budget": 2_000_000,
                                               "travel_mode": "grab"}))],
        "chuyên gia Ăn uống": [search, reply(("submit_shortlist", {"place_ids": [food], "note": "n"}))],
        "chuyên gia Tham quan": [search, reply(("submit_shortlist", {"place_ids": [cafe], "note": "n"}))],
        "trợ lý lập lịch trình": [reply(("submit_itinerary", {"summary": "ok", "days": [{"stops": [
            {"place_id": cafe, "start_time": "09:00", "duration_min": 60, "reason": "cafe"}]}]}))]})
    monkeypatch.setattr(llm, "chat_client", lambda: rc)
    h = auth(client)
    evs = events(client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h))
    assert {e.get("agent") for e in evs if e["type"] == "tool_call"} == {"an-uong", "tham-quan"}
    assert evs[-1]["type"] == "itinerary" and evs[-1]["version"] == 1
    assert client.get(f"/trips/{evs[-1]['trip_id']}", headers=h).json()["version"] == 1
```

(`PARSE_PROMPT` có chữ "record_trip", nên khoá `"record_trip"` chọn đúng kịch bản cho lượt `parse_trip`.)

- [ ] **Step 2: Chạy, thấy đỏ**

Run: `cd server && uv run pytest tests/test_multi.py tests/test_config.py tests/test_trips_api.py -q`
Expected: 2 FAIL ở `test_config.py` (`AttributeError: 'Settings' object has no attribute 'planner_mode'`); mọi test của `test_multi.py` ERROR ở fixture `env` (`AttributeError: … has no attribute 'agent_conn'`); 1 FAIL ở `test_trips_api.py` (`AttributeError` ở `planner_mode`).

- [ ] **Step 3: `server/app/config.py`** — thêm trường sau `plan_rpm` và validator:

```python
    planner_mode: Literal["single", "multi"] = "single"  # multi = 3 agent chuyên gia + tổng hợp (spec §7)
```

```python
    @field_validator("planner_mode", mode="before")
    @classmethod
    def _blank_is_single(cls, v):
        return v or "single"
```

- [ ] **Step 4: `server/app/multi.py`** — sửa import đầu file thành:

```python
import copy
import json
import logging
import queue
import threading
import time
from collections.abc import Iterator

from app import agent
from app.agent import PLAN_TOOLS, for_llm, run_search, trip_brief
from app.db import connect
from app.domain import PACE_STOPS, Place, Trip
from app.places import get_places

logger = logging.getLogger(__name__)
_now = time.monotonic
agent_conn = connect  # mỗi chuyên gia một kết nối riêng; test thay bằng kết nối test
AGENT_WAIT_S = 45  # chờ đủ danh sách tối đa bấy nhiêu giây rồi quay về agent đơn
FALLBACK_TEXT = "Chuyển sang lập lịch thường…"
```

và thêm vào cuối file:

```python
def _work(put, client, model: str, trip: Trip, role: str, embed_fn, rain, user_messages: list[str]) -> None:
    """Chạy một chuyên gia; event, kết quả hoặc lỗi {"role", "error"} đều đi qua put."""
    try:
        with agent_conn() as conn:
            put(shortlist(conn, client, model, trip, role, embed_fn, rain, user_messages, put))
    except Exception as e:  # lỗi nào cũng thành "agent lỗi": điều phối quay về agent đơn
        logger.warning("agent %s lỗi: %s", role, e)
        put({"role": role, "error": str(e)})


def _local(client, model: str, trip: Trip, embed_fn, rain, user_messages: list[str], roles: list[str]):
    """Không có Redis: mỗi chuyên gia một thread trong tiến trình, thông điệp về qua Queue.

    ponytail: thread quá hạn không huỷ được, chạy nền tới khi xong rồi kết quả bị bỏ.
    """
    q: queue.Queue = queue.Queue()
    for role in roles:
        threading.Thread(target=_work, args=(q.put, client, model, trip, role, embed_fn, rain, user_messages),
                         daemon=True).start()

    def recv(timeout: float) -> dict | None:
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return None

    return recv


def gather(recv, roles: list[str]):
    """Phát lại event của các chuyên gia; return danh sách kết quả, hoặc None khi có agent lỗi hay quá hạn."""
    deadline, results = _now() + AGENT_WAIT_S, []
    while len(results) < len(roles):
        left = deadline - _now()
        if left <= 0:
            return None
        m = recv(min(left, 0.5))
        if m is None:
            continue
        if "type" in m:
            yield m
        elif "error" in m:
            return None
        else:
            results.append(m)
    return results


def _notes(results: list[dict], places: dict[int, Place]) -> str:
    lines = ["Các chuyên gia đã chọn sẵn Place dưới đây (place_id dùng được luôn). Ưu tiên dùng các Place này; "
             "chỉ gọi search_places khi còn thiếu, tối đa 2 lần."]
    for r in results:
        lines.append(f"{ROLES[r['role']][0]} — {r['note']}")
        lines.append(json.dumps([for_llm(places[i]) for i in r["place_ids"] if i in places], ensure_ascii=False))
    return "\n".join(lines)


def plan(conn, client, model: str, trip: Trip, embed_fn, rain, hub=None, user_messages: list[str] = (),
         previous=None, local: bool = False) -> Iterator[dict]:
    """Cùng hợp đồng với agent.plan. Thiếu danh sách của bất kỳ chuyên gia nào → agent đơn nguyên bản (spec §7)."""
    roles = roles_for(trip)
    yield {"type": "thinking", "text": "Các chuyên gia đang tìm địa điểm…"}
    recv = _local(client, model, trip, embed_fn, rain, list(user_messages), roles)
    results = yield from gather(recv, roles)
    if results is None:
        yield {"type": "thinking", "text": FALLBACK_TEXT}
        yield from agent.plan(conn, client, model, trip, embed_fn, rain, hub, user_messages, previous)
        return
    seeded = get_places(conn, [i for r in results for i in r["place_ids"]])
    yield from agent.plan(conn, client, model, trip, embed_fn, rain, hub, user_messages, previous,
                          seeded=seeded, notes=_notes(results, seeded), max_searches=2)
```

(`local` chưa dùng ở task này; Task 4 dùng để chọn đường Redis.)

- [ ] **Step 5: `server/app/trips.py`** — đổi `from app import forecast, jobs, llm` thành `from app import forecast, jobs, llm, multi` và sửa `_plan_and_save`:

```python
def _plan_and_save(conn, client, trip_id: int, trip: Trip, dest: dict, user_messages: list[str], previous=None):
    rain = forecast.get_rain_chance(dest["lat"], dest["lon"], trip.start_date, trip.days, today=_today())
    planner = multi.plan if settings.planner_mode == "multi" else plan
    for ev in planner(conn, client, settings.llm_model, trip, llm.embed, rain, hub_for(dest, trip), user_messages,
                      previous):
```

(phần thân vòng lặp giữ nguyên.)

- [ ] **Step 6: Chạy, thấy xanh**

Run: `cd server && uv run pytest -q`
Expected: toàn bộ PASS (283 cũ + 4 Task 1 + 7 Task 2 + 7 Task 3 = 301).

- [ ] **Step 7: Commit**

```bash
git add server/app/multi.py server/app/config.py server/app/trips.py server/tests
git commit -m "feat(server): PLANNER_MODE=multi — chuyên gia chạy song song bằng thread, lỗi hoặc quá 45 giây thì về agent đơn (#50)"
```

---

### Task 4: Phát việc qua Redis, worker `--stream agent_jobs`

**Files:**
- Modify: `server/app/multi.py`, `server/app/worker.py`
- Test: `server/tests/test_multi.py`, `server/tests/test_worker.py`, `server/tests/test_trips_api.py`

**Interfaces:**
- Consumes: `multi._work`, `multi.gather`, `kv.client()`, `worker.ensure_group`
- Produces:
  - `multi.AGENT_STREAM = "agent_jobs"`, `multi.AGENT_GROUP = "agents"`, `multi.KEY_TTL_S = 300`
  - `multi._remote(trip, rain, user_messages, roles) -> recv` — `XADD` mỗi role một việc `{key, role, trip, rain, user_messages}`
  - `multi.serve(c, f: dict) -> None` — phía worker: chạy chuyên gia cho việc `f`, `RPUSH` vào `f["key"]`
  - `worker.ensure_group(c, stream=jobs.STREAM, group=jobs.GROUP)`
  - `worker.agent_step(c, me: str) -> bool`
  - `python -m app.worker --stream agent_jobs`

- [ ] **Step 1: Viết test đỏ**

`server/tests/test_multi.py` — thêm import `from app import kv` và `from app.config import settings`, rồi:

```python
def test_remote_without_agent_worker_falls_back(conn, rds, monkeypatch):
    monkeypatch.setattr(multi, "AGENT_WAIT_S", 0.6)
    cafe = add_place(conn, "Cafe", "cafe")
    rc = RoleClient({SYNTH: [SEARCH, reply(("submit_itinerary", stops(cafe)))]})
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None))
    assert {"type": "thinking", "text": multi.FALLBACK_TEXT} in events and used(events) == [cafe]
    assert rds.xlen(multi.AGENT_STREAM) == 2  # việc đã gửi, không ai nhận


def test_remote_redis_down_falls_back_at_once(conn, monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")
    monkeypatch.setattr(kv, "_client", None)
    cafe = add_place(conn, "Cafe", "cafe")
    rc = RoleClient({SYNTH: [SEARCH, reply(("submit_itinerary", stops(cafe)))]})
    t0 = time.monotonic()
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None))
    assert time.monotonic() - t0 < 5 and used(events) == [cafe]
    monkeypatch.setattr(kv, "_client", None)


def test_local_flag_uses_threads_even_with_redis(conn, rds):
    food, cafe = add_place(conn, "Quán", "an-uong"), add_place(conn, "Cafe", "cafe")
    rc = RoleClient({FOOD: [SEARCH, pick(food)], SIGHT: [SEARCH, pick(cafe)],
                     SYNTH: [reply(("submit_itinerary", stops(cafe)))]})
    events = list(multi.plan(conn, rc, "m", trip(), fake_embed, None, local=True))
    assert used(events) == [cafe] and rds.xlen(multi.AGENT_STREAM) == 0
```

`server/tests/test_worker.py` — thêm import `from contextlib import nullcontext`, `from app import multi`, `from app.domain import Trip`, rồi:

```python
def agent_job(rds, monkeypatch, conn, role="tham-quan"):
    monkeypatch.setattr(multi, "agent_conn", lambda: nullcontext(conn))
    trip = Trip(destination="da-lat", days=1, budget=2_000_000, travel_mode="grab")
    recv = multi._remote(trip, None, [], [role])
    worker.ensure_group(rds, multi.AGENT_STREAM, multi.AGENT_GROUP)
    return recv


def agent_pending(rds):
    return rds.xpending(multi.AGENT_STREAM, multi.AGENT_GROUP)["pending"]


def test_agent_step_runs_specialist_and_pushes_result(conn, rds, monkeypatch):
    pid = add_place(conn, "Cafe", "cafe")
    use_llm(monkeypatch, [reply(("search_places", {"query": "cafe"})),
                          reply(("submit_shortlist", {"place_ids": [pid], "note": "n"}))])
    recv = agent_job(rds, monkeypatch, conn)
    assert worker.agent_step(rds, "a1") is True
    assert 0 < rds.ttl(rds.keys("agent:*")[0]) <= multi.KEY_TTL_S
    ev = recv(0.5)
    assert ev["type"] == "tool_call" and ev["agent"] == "tham-quan"
    assert recv(0.5) == {"role": "tham-quan", "place_ids": [pid], "note": "n"}
    assert agent_pending(rds) == 0


def test_agent_step_error_pushes_error_and_acks(conn, rds, monkeypatch):
    use_llm(monkeypatch, [RuntimeError("boom")])
    recv = agent_job(rds, monkeypatch, conn)
    assert worker.agent_step(rds, "a1") is True
    assert recv(0.5) == {"role": "tham-quan", "error": "boom"}
    assert agent_pending(rds) == 0


def test_agent_step_drops_job_older_than_coordinator_wait(conn, rds, monkeypatch):
    use_llm(monkeypatch, [])  # gọi LLM là IndexError → test đỏ
    monkeypatch.setattr(multi, "agent_conn", lambda: nullcontext(conn))
    worker.ensure_group(rds, multi.AGENT_STREAM, multi.AGENT_GROUP)
    old = f"{int((time.time() - multi.AGENT_WAIT_S - 5) * 1000)}-0"
    rds.xadd(multi.AGENT_STREAM, {"key": "agent:cu", "role": "tham-quan", "trip": "{}", "rain": "null",
                                  "user_messages": "[]"}, id=old)
    assert worker.agent_step(rds, "a1") is True
    assert rds.llen("agent:cu") == 0 and agent_pending(rds) == 0


def test_agent_step_idle_returns_false(rds):
    worker.ensure_group(rds, multi.AGENT_STREAM, multi.AGENT_GROUP)
    assert worker.agent_step(rds, "a1") is False


def test_coordinator_never_takes_agent_jobs(conn, rds, monkeypatch):
    """Hai stream tách nhau (spec §7): worker điều phối bận hết thì agent vẫn có người chạy."""
    use_llm(monkeypatch, [RuntimeError("x")])
    recv = agent_job(rds, monkeypatch, conn)
    assert worker.step(conn, rds, "w1") is False
    assert rds.xlen(multi.AGENT_STREAM) == 1 and recv(0.1) is None
    assert worker.agent_step(rds, "a1") is True
```

`server/tests/test_trips_api.py` — thêm fixture và test:

```python
@pytest.fixture
def agents(conn, rds, monkeypatch):
    """Một planner-agent chạy trong thread, dùng chung kết nối test."""
    monkeypatch.setattr(multi, "agent_conn", lambda: nullcontext(conn))
    worker.ensure_group(rds, multi.AGENT_STREAM, multi.AGENT_GROUP)
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            worker.agent_step(rds, "a1")

    t = threading.Thread(target=loop)
    t.start()
    yield
    stop.set()
    t.join()


def test_queue_mode_multi_runs_specialists_on_agent_worker(client, conn, monkeypatch, planner, agents):
    monkeypatch.setattr(settings, "planner_mode", "multi")
    food, cafe = add_place(conn, "Quán", "an-uong"), add_place(conn, "Cafe", "cafe")
    search = reply(("search_places", {"query": "x"}))
    rc = RoleClient({
        "record_trip": [reply(("record_trip", {"destination": "da-lat", "days": 1, "budget": 2_000_000,
                                               "travel_mode": "grab"}))],
        "chuyên gia Ăn uống": [search, reply(("submit_shortlist", {"place_ids": [food], "note": "n"}))],
        "chuyên gia Tham quan": [search, reply(("submit_shortlist", {"place_ids": [cafe], "note": "n"}))],
        "trợ lý lập lịch trình": [reply(("submit_itinerary", {"summary": "ok", "days": [{"stops": [
            {"place_id": cafe, "start_time": "09:00", "duration_min": 60, "reason": "cafe"}]}]}))]})
    monkeypatch.setattr(llm, "chat_client", lambda: rc)
    h = auth(client)
    r = client.post("/trips", json={"message": "Đà Lạt 1 ngày 2 triệu"}, headers=h)
    evs = events(r)
    assert {e.get("agent") for e in evs if e["type"] == "tool_call"} == {"an-uong", "tham-quan"}
    assert evs[-1]["type"] == "itinerary"
    assert rds.xpending(multi.AGENT_STREAM, multi.AGENT_GROUP)["pending"] == 0
```

- [ ] **Step 2: Chạy, thấy đỏ**

Run: `cd server && uv run pytest tests/test_multi.py tests/test_worker.py tests/test_trips_api.py -q`
Expected: FAIL với `AttributeError: module 'app.multi' has no attribute 'AGENT_STREAM'` / `'_remote'`, `TypeError: ensure_group() takes 1 positional argument`, `AttributeError: module 'app.worker' has no attribute 'agent_step'`. `test_local_flag_uses_threads_even_with_redis` cũng đỏ ở `AGENT_STREAM`.

- [ ] **Step 3: `server/app/multi.py`**

Thêm import: `import uuid`, `from redis.exceptions import RedisError`, `from app import agent, kv, llm`, `from app.config import settings`. Thêm hằng số cạnh `AGENT_WAIT_S`:

```python
AGENT_STREAM, AGENT_GROUP = "agent_jobs", "agents"
KEY_TTL_S = 300  # khoá agent:{uuid} của một lần chạy sống bấy nhiêu giây
```

Thêm sau `_local`:

```python
def _remote(trip: Trip, rain, user_messages: list[str], roles: list[str]):
    """Có Redis: mỗi role một việc trong agent_jobs; planner-agent RPUSH event và kết quả về khoá của lần chạy này.

    Việc mang nguyên Trip: điều phối đang ở trong transaction chưa commit nên agent không đọc được Trip từ database.
    Redis lỗi → thông điệp lỗi, điều phối quay về agent đơn.
    """
    c, key = kv.client(), f"agent:{uuid.uuid4().hex}"
    down = {"role": "", "error": "redis"}
    try:
        for role in roles:
            c.xadd(AGENT_STREAM, {"key": key, "role": role, "trip": trip.model_dump_json(), "rain": json.dumps(rain),
                                  "user_messages": json.dumps(user_messages, ensure_ascii=False)},
                   maxlen=1000, approximate=True)
    except RedisError:
        return lambda timeout: down

    def recv(timeout: float) -> dict | None:
        try:
            got = c.blpop(key, timeout=timeout)
        except RedisError:
            return down
        return json.loads(got[1]) if got else None

    return recv


def serve(c, f: dict) -> None:
    """Phía planner-agent: chạy chuyên gia cho việc f, đẩy event và kết quả (hoặc lỗi) vào f["key"]."""
    def push(m: dict) -> None:
        c.rpush(f["key"], json.dumps(m, ensure_ascii=False))
        c.expire(f["key"], KEY_TTL_S)

    try:
        trip = Trip.model_validate_json(f["trip"])
    except ValueError as e:  # việc hỏng: báo lỗi về điều phối thay vì để nó chờ hết 45 giây
        return push({"role": f["role"], "error": str(e)})
    _work(push, llm.chat_client(), settings.llm_model, trip, f["role"], llm.embed,
          json.loads(f["rain"]), json.loads(f["user_messages"]))
```

Trong `plan`, thay dòng `recv = _local(...)` bằng:

```python
    recv = (_local(client, model, trip, embed_fn, rain, list(user_messages), roles)
            if local or kv.client() is None else _remote(trip, rain, list(user_messages), roles))
```

- [ ] **Step 4: `server/app/worker.py`**

Sửa docstring đầu file thành:

```python
"""planner: nhận việc từ Redis Streams (spec scale §5, §7).

Chạy: python -m app.worker                      (điều phối: stream jobs, chạy các generator của app.trips)
      python -m app.worker --stream agent_jobs  (agent chuyên gia của lập lịch đa agent)
"""
```

Thêm `import argparse` và `from app import jobs, kv, multi, trips`. Sửa `ensure_group`:

```python
def ensure_group(c, stream: str = jobs.STREAM, group: str = jobs.GROUP) -> None:
    try:
        c.xgroup_create(stream, group, id="0", mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise
```

Thêm sau `step`:

```python
def agent_step(c, me: str) -> bool:
    """Vai agent: nhận và chạy tối đa một việc từ agent_jobs; True nếu có việc.

    Giao nhiều nhất một lần: XACK dù lỗi, không nhận lại. Thiếu kết quả thì điều phối tự quay về agent đơn (spec §7).
    """
    got = c.xreadgroup(multi.AGENT_GROUP, me, {multi.AGENT_STREAM: ">"}, count=1, block=500)
    if not got:
        return False
    msg_id, f = got[0][1][0]
    try:
        # Xếp hàng lâu hơn thời gian điều phối chờ: nó đã chuyển sang agent đơn → không tốn quota LLM nữa.
        if time.time() * 1000 - int(msg_id.split("-")[0]) <= multi.AGENT_WAIT_S * 1000:
            multi.serve(c, f)
            logger.info("agent %s xong việc %s", f["role"], f["key"])
    finally:
        c.xack(multi.AGENT_STREAM, multi.AGENT_GROUP, msg_id)
    return True
```

Sửa `main`:

```python
def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", choices=[jobs.STREAM, multi.AGENT_STREAM], default=jobs.STREAM)
    agent = ap.parse_args().stream == multi.AGENT_STREAM
    c, me = kv.client(), socket.gethostname()
    if c is None:
        raise SystemExit("planner cần REDIS_URL")
    with connect() as conn:
        apply_schema(conn)
    logger.info("planner %s sẵn sàng (%s)", me, "agent" if agent else "điều phối")
    conn = None
    while True:
        try:
            if agent:  # mỗi việc tự mở kết nối đọc bảng places (multi.agent_conn)
                ensure_group(c, multi.AGENT_STREAM, multi.AGENT_GROUP)
                agent_step(c, me)
                continue
            ensure_group(c)  # mỗi vòng: `redis-cli flushdb` trong runbook xoá luôn consumer group
            conn = conn or connect()
            step(conn, c, me)
        except Exception:
            logger.exception("planner lỗi, thử lại sau 1 giây")
            if conn is not None:
                conn.close()
            conn = None
            time.sleep(1)
```

- [ ] **Step 5: Chạy, thấy xanh**

Run: `cd server && uv run pytest -q`
Expected: toàn bộ PASS (301 + 3 + 5 + 1 = 310).

- [ ] **Step 6: Commit**

```bash
git add server/app/multi.py server/app/worker.py server/tests
git commit -m "feat(server): chuyên gia chạy trên planner-agent qua stream agent_jobs, tách khỏi stream điều phối (#50)"
```

---

### Task 5: Nhãn agent trong Chat

**Files:**
- Modify: `client/src/api.ts` (kiểu `AgentEvent`, thêm `searchLine`), `client/src/App.tsx:92-93`
- Test: `client/src/api.test.ts`

**Interfaces:**
- Produces: `searchLine(e: { query: string; places: unknown[]; agent?: string }): string`

- [ ] **Step 1: Viết test đỏ** — thêm `searchLine` vào danh sách import của `client/src/api.test.ts` và thêm:

```ts
describe('searchLine', () => {
  it('ghép nhãn agent chuyên gia vào dòng tìm kiếm', () => {
    expect(searchLine({ query: 'quán lẩu', places: [1, 2], agent: 'an-uong' }))
      .toBe('Ăn uống · Đang tìm: quán lẩu (2 kết quả)')
    expect(searchLine({ query: 'homestay', places: [], agent: 'cho-o' })).toBe('Chỗ ở · Đang tìm: homestay (0 kết quả)')
  })
  it('agent đơn hoặc agent lạ thì giữ dòng cũ', () => {
    expect(searchLine({ query: 'cafe', places: [1] })).toBe('Đang tìm: cafe (1 kết quả)')
    expect(searchLine({ query: 'cafe', places: [1], agent: 'la' })).toBe('Đang tìm: cafe (1 kết quả)')
  })
})
```

- [ ] **Step 2: Chạy, thấy đỏ**

Run: `cd client && npm test -- --run src/api.test.ts`
Expected: FAIL — `searchLine is not a function` (hoặc lỗi import).

- [ ] **Step 3: Sửa client**

`client/src/api.ts` — sửa dòng kiểu `tool_call`:

```ts
  | { type: 'tool_call'; name: string; query: string; places: Place[]; agent?: string }  // agent: role chuyên gia khi lập lịch đa agent
```

và thêm (cạnh `isFinal`):

```ts
const AGENT_LABELS: Record<string, string> = { 'an-uong': 'Ăn uống', 'tham-quan': 'Tham quan', 'cho-o': 'Chỗ ở' }

export function searchLine(e: { query: string; places: unknown[]; agent?: string }): string {
  const line = `Đang tìm: ${e.query} (${e.places.length} kết quả)`
  const label = e.agent && AGENT_LABELS[e.agent]
  return label ? `${label} · ${line}` : line
}
```

`client/src/App.tsx` — import `searchLine` từ `./api` và đổi dòng trong `case 'tool_call'`:

```tsx
        add({ role: 'tool', text: searchLine(e) })
```

- [ ] **Step 4: Chạy, thấy xanh**

Run: `cd client && npm test -- --run && npm run build`
Expected: toàn bộ test PASS, build xong không lỗi TypeScript.

- [ ] **Step 5: Commit**

```bash
git add client/src/api.ts client/src/api.test.ts client/src/App.tsx
git commit -m "feat(client): dòng tìm kiếm trong Chat hiện nhãn agent chuyên gia (#50)"
```

---

### Task 6: `planner-agent` trong cụm, chạy thử thật

**Files:**
- Modify: `docker-compose.cluster.yml`, `server/.env.example`

- [ ] **Step 1: `docker-compose.cluster.yml`**

Sửa dòng chú thích đầu file thành `# Cụm phân tán (spec scale §4). T4: db + redis + llm-gateway + 2 api + 2 planner + 3 planner-agent + nginx.`

Thêm vào `&app_env` (sau `PLAN_RPM`):

```yaml
      PLANNER_MODE: ${PLANNER_MODE:-single}
```

Thêm service sau `planner`:

```yaml
  planner-agent:  # agent chuyên gia của lập lịch đa agent (PLANNER_MODE=multi); đọc stream agent_jobs
    build: ./server
    command: ["uv", "run", "--no-dev", "python", "-m", "app.worker", "--stream", "agent_jobs"]
    env_file: ./server/.env
    environment: *app_env
    deploy:
      replicas: 3
    depends_on: *app_deps
```

- [ ] **Step 2: `server/.env.example`** — thêm sau khối `PLAN_RPM`:

```
# single | multi. multi = 3 agent chuyên gia tìm Place song song + agent tổng hợp; lỗi hoặc quá 45 giây thì về single
PLANNER_MODE=single
```

- [ ] **Step 3: Kiểm cấu hình compose**

Run: `docker compose -f docker-compose.cluster.yml config --services | sort`
Expected: `api db llm-gateway nginx planner planner-agent redis` (mỗi tên một dòng).

- [ ] **Step 4: Dựng cụm ở `multi` và lập một Trip thật**

```bash
docker compose down
PLANNER_MODE=multi docker compose -f docker-compose.cluster.yml up -d --build
docker compose -f docker-compose.cluster.yml ps --format '{{.Service}}' | sort | uniq -c
```
Expected: `2 api`, `1 db`, `1 llm-gateway`, `1 nginx`, `2 planner`, `3 planner-agent`, `1 redis`.

Import Place nếu volume mới (`cd server && uv run python -m scripts.import_places ../data/places`), đăng ký một User qua `curl -s localhost:8000/auth/register …`, rồi:

```bash
curl -sN -X POST localhost:8000/trips -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message":"Đà Lạt 2 ngày 3 triệu 2 người, đi Grab"}' | grep -o '"agent": *"[a-z-]*"' | sort | uniq -c
```
Expected: có dòng cho `an-uong`, `tham-quan`, `cho-o`; stream kết thúc bằng event `itinerary`.

Run: `docker compose -f docker-compose.cluster.yml logs planner-agent | grep "xong việc"`
Expected: ba dòng, mỗi role một dòng (thường ở các container khác nhau).

- [ ] **Step 5: Dự phòng và không kẹt**

```bash
docker compose -f docker-compose.cluster.yml stop planner-agent
```
Gửi lại một yêu cầu lập lịch khác câu chữ. Expected: sau khoảng 45 giây có event `thinking` "Chuyển sang lập lịch thường…", rồi `itinerary`.

```bash
docker compose -f docker-compose.cluster.yml start planner-agent
```
Gửi ba yêu cầu lập lịch cùng lúc từ ba User (`&` rồi `wait`). Expected: cả ba stream kết thúc bằng `itinerary` (có thể qua dự phòng), không stream nào kết thúc bằng `error` "Hệ thống lập lịch đang bận".

Run: `docker stats --no-stream --format '{{.Name}} {{.MemUsage}}'`
Ghi tổng RAM của 11 container để đưa vào ROADMAP (Task 8).

- [ ] **Step 6: Commit**

```bash
git add docker-compose.cluster.yml server/.env.example
git commit -m "feat: cụm thêm 3 planner-agent và biến PLANNER_MODE (#50)"
```

---

### Task 7: Golden set `single` vs `multi`

**Files:**
- Create: `server/scripts/golden.py`
- Test: `server/tests/test_golden.py` (mới)

**Interfaces:**
- Consumes: `agent.parse_trip`, `agent.apply_answers`, `agent.plan`, `multi.plan(local=True)`, `multi.FALLBACK_TEXT`, `trips.hub_for`, `trips._today`, `forecast.get_rain_chance`
- Produces: `golden.summarize(rows: list[dict]) -> dict`, `golden.table(by_mode: dict[str, dict]) -> str`, lệnh `uv run python -m scripts.golden --mode single|multi|both`

- [ ] **Step 1: Viết test đỏ** — tạo `server/tests/test_golden.py`:

```python
from scripts.golden import PROMPTS, summarize, table


def test_summarize_counts_valid_and_averages():
    rows = [{"valid": True, "conflicts": 2, "seconds": 10.0, "calls": 12, "fallback": False},
            {"valid": True, "conflicts": 0, "seconds": 20.0, "calls": 14, "fallback": True},
            {"valid": False, "conflicts": 0, "seconds": 30.0, "calls": 4, "fallback": False}]
    assert summarize(rows) == {"n": 3, "valid_pct": 67, "conflicts": 1.0, "seconds": 20.0, "calls": 10.0,
                               "fallbacks": 1}
    assert summarize([])["valid_pct"] == 0


def test_table_has_one_row_per_mode():
    s = summarize([{"valid": True, "conflicts": 1, "seconds": 9.0, "calls": 13, "fallback": False}])
    out = table({"single": s, "multi": s})
    assert out.count("\n") == 4 and "| single | 1 | 100% | 1.0 | 9.0 | 13.0 | 0 |" in out


def test_eight_prompts():
    assert len(PROMPTS) == 8 and len(set(PROMPTS)) == 8
```

- [ ] **Step 2: Chạy, thấy đỏ**

Run: `cd server && uv run pytest tests/test_golden.py -q`
Expected: lỗi collect `ModuleNotFoundError: No module named 'scripts.golden'`.

- [ ] **Step 3: Tạo `server/scripts/golden.py`**

```python
"""Golden set (một phần #6): đo agent đơn và đa agent trên cùng bộ prompt (spec scale §7).

Chạy: uv run python -m scripts.golden --mode both
Cần database dev đã import Place và LLM_* / EMBED_* thật trong .env. Đa agent luôn chạy bằng thread
trong tiến trình (không cần cụm). Muốn đo thời gian thật thì trỏ thẳng provider, không qua cache của llm-gateway.
"""
import argparse
import datetime as dt
import threading
import time
from functools import partial
from types import SimpleNamespace

from app import agent, forecast, llm, multi, trips
from app.config import settings
from app.db import connect
from app.domain import TripAnswers
from app.places import list_destinations

_DATE = (dt.date.today() + dt.timedelta(days=10)).isoformat()
PROMPTS = [
    "Đà Lạt 1 ngày 1 triệu cho 2 người, đi Grab",
    "Đà Lạt 2 ngày 3 triệu 2 người, thích cafe và chụp ảnh, thuê xe máy",
    "Đi Đà Lạt 3 ngày, 4 người, ngân sách 8 triệu, đi nhẹ nhàng thong thả, có ô tô riêng",
    "Đà Lạt 3 ngày 5 triệu 2 người, muốn khám phá hết, đi thật nhiều, thuê xe máy",
    "Đà Lạt 2 ngày 1,5 triệu 2 người, tiết kiệm nhất có thể, thuê xe máy",
    "Gia đình 5 người có trẻ nhỏ đi Đà Lạt 2 ngày, 6 triệu, không leo núi, đi Grab",
    f"Đà Lạt 2 ngày từ {_DATE}, 2 người 4 triệu, bay tới lúc 10:00 và bay về lúc 17:00, đi Grab",
    "Cặp đôi đi Đà Lạt 4 ngày 10 triệu, thích thiên nhiên và ẩm thực địa phương, thuê xe máy",
]


class Counting:
    """Bọc client OpenAI để đếm lượt chat (các chuyên gia gọi từ nhiều thread)."""

    def __init__(self, inner):
        self.n, self._inner, self._lock = 0, inner, threading.Lock()
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        with self._lock:
            self.n += 1
        return self._inner.chat.completions.create(**kwargs)


def run_one(conn, dests: dict, prompt: str, mode: str) -> dict:
    client = Counting(llm.chat_client())
    row = {"valid": False, "conflicts": 0, "fallback": False, "error": ""}
    t0 = time.perf_counter()
    try:
        today = trips._today()
        trip = agent.apply_answers(
            agent.parse_trip(client, settings.llm_model, prompt, {s: d["name"] for s, d in dests.items()}, today),
            TripAnswers())
        d = dests[trip.destination]
        rain = forecast.get_rain_chance(d["lat"], d["lon"], trip.start_date, trip.days, today=today)
        planner = partial(multi.plan, local=True) if mode == "multi" else agent.plan
        for ev in planner(conn, client, settings.llm_model, trip, llm.embed, rain, trips.hub_for(d, trip), [prompt]):
            if ev["type"] == "thinking" and ev["text"] == multi.FALLBACK_TEXT:
                row["fallback"] = True
            elif ev["type"] == "itinerary":
                row.update(valid=True, conflicts=len(ev["itinerary"]["conflicts"]))
            elif ev["type"] == "error":
                row["error"] = ev["message"]
    except Exception as e:  # một prompt hỏng không dừng cả lượt đo
        row["error"] = f"{type(e).__name__}: {e}"
    return {**row, "seconds": round(time.perf_counter() - t0, 1), "calls": client.n}


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["valid"]]

    def mean(xs):
        return round(sum(xs) / len(xs), 1) if xs else 0.0

    return {"n": len(rows), "valid_pct": round(100 * len(ok) / len(rows)) if rows else 0,
            "conflicts": mean([r["conflicts"] for r in ok]), "seconds": mean([r["seconds"] for r in rows]),
            "calls": mean([r["calls"] for r in rows]), "fallbacks": sum(r["fallback"] for r in rows)}


def table(by_mode: dict[str, dict]) -> str:
    lines = ["| Chế độ | Prompt | Itinerary hợp lệ | Conflict TB | Giây TB | Lượt LLM TB | Về dự phòng |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {m} | {s['n']} | {s['valid_pct']}% | {s['conflicts']} | {s['seconds']} | {s['calls']} | "
              f"{s['fallbacks']} |" for m, s in by_mode.items()]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["single", "multi", "both"], default="both")
    ap.add_argument("--pause", type=float, default=0, help="giây nghỉ giữa hai prompt (hạn mức theo phút của provider)")
    args = ap.parse_args()
    modes = ["single", "multi"] if args.mode == "both" else [args.mode]
    by_mode = {}
    with connect() as conn:
        dests = {d["slug"]: d for d in list_destinations(conn)}
        for mode in modes:
            rows = []
            for i, prompt in enumerate(PROMPTS, 1):
                r = run_one(conn, dests, prompt, mode)
                rows.append(r)
                print(f"[{mode} {i}/{len(PROMPTS)}] hợp lệ={r['valid']} conflict={r['conflicts']} "
                      f"{r['seconds']}s lượt={r['calls']} dự phòng={r['fallback']} {r['error']}", flush=True)
                time.sleep(args.pause)
            by_mode[mode] = summarize(rows)
    print(f"\nModel: {settings.llm_model}\n\n{table(by_mode)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Chạy, thấy xanh**

Run: `cd server && uv run pytest tests/test_golden.py -q`
Expected: 3 passed.

- [ ] **Step 5: Đo thật**

Dừng cụm, bật chế độ dev (`docker compose -f docker-compose.cluster.yml down && docker compose up -d db redis`), bảo đảm database dev có Place (`uv run python -m scripts.import_places ../data/places`).

Run: `cd server && uv run python -m scripts.golden --mode both --pause 5` (giữ nguyên output để chép bảng vào runbook ở Task 8)
Expected: 16 dòng tiến độ rồi một bảng 2 hàng. Nếu provider trả 429 hàng loạt, chạy lại với `--pause 20`; ghi rõ trong báo cáo lần nào bị giới hạn.

- [ ] **Step 6: Commit**

```bash
git add server/scripts/golden.py server/tests/test_golden.py
git commit -m "feat(server): golden set 8 prompt so agent đơn với đa agent (#50, một phần #6)"
```

---

### Task 8: Tài liệu

**Files:**
- Modify: `docs/runbook-cum.md`, `docs/ROADMAP.md`, `docs/2026-09-25-hien-trang-app.md`, `CLAUDE.md`

- [ ] **Step 1: `docs/runbook-cum.md`** — thêm mục `## Lập lịch đa agent (T4)` sau mục "Queue và planner (T3)" gồm:
  - Bật: `PLANNER_MODE=multi docker compose -f docker-compose.cluster.yml up -d`; chế độ đơn giản thì đặt `PLANNER_MODE=multi` trong `server/.env` (chạy bằng thread, không cần Redis).
  - Xem ba agent: `docker compose -f docker-compose.cluster.yml logs -f planner-agent`; trong Chat thấy nhãn "Ăn uống · / Tham quan · / Chỗ ở ·".
  - Demo dự phòng: `stop planner-agent` giữa lúc lập lịch → sau tối đa 45 giây "Chuyển sang lập lịch thường…".
  - Hạn mức provider: đặt `LLM_RPM` thấp hơn quota; gateway chờ thay vì lỗi, chờ lâu thì rơi về dự phòng.
  - Đo: `cd server && uv run python -m scripts.golden --mode both`, kèm **bảng kết quả thật** của Task 7 (model, ngày đo).
  - Lưu ý: `agent_jobs` giao nhiều nhất một lần; agent bỏ việc xếp hàng quá 45 giây.

- [ ] **Step 2: `docs/ROADMAP.md`** — tick dòng T4 (`- [x] **T4** — #50 — …`) kèm số đo thật: kết luận `multi` so với `single`, RAM 11 container; sửa dòng bảng tuần T4 và mục "Tiếp:" thành T5 (#51 nếu đúng số issue — kiểm bằng `gh issue list --search "Scale T5"`); cập nhật số test server.

- [ ] **Step 3: `docs/2026-09-25-hien-trang-app.md`** — thêm `multi.py`, `scripts/golden.py`, service `planner-agent`, biến `PLANNER_MODE` vào các phần tương ứng (sơ đồ queue thêm nhánh `agent_jobs`).

- [ ] **Step 4: `CLAUDE.md`** — sửa dòng lệnh cụm thành `Cụm (nginx + 2 api + 2 planner + 3 planner-agent + Redis + llm-gateway)`.

- [ ] **Step 5: Chạy lại toàn bộ**

Run: `cd server && uv run pytest -q && cd ../client && npm test -- --run && npm run build`
Expected: server 313 passed; client toàn bộ PASS, build sạch.

- [ ] **Step 6: Commit**

```bash
git add docs CLAUDE.md
git commit -m "docs: runbook đa agent, bảng golden set, ROADMAP T4 (#50)"
```

---

## Self-Review

- **Spec coverage:** §7 luồng (Task 2–4); bảng role và cỡ danh sách (Task 2 `ROLES`, `wanted`); hai stream tách nhau (Task 4, `test_coordinator_never_takes_agent_jobs`, Task 6 Step 5); ADR-0001 (Task 1 `test_place_outside_seeded_still_rejected`, Task 3 `test_synthesizer_still_rejects_place_outside_shortlists`); tổng hợp tối đa 2 lượt tìm (Task 1 `max_searches`, Task 3 truyền `2`); Place đã ghim (không đổi: `previous` vẫn truyền vào `agent.plan`); dự phòng (Task 3, 4); trường `agent` + nhãn (Task 2, 5); đánh giá (Task 7); S22 (Task 3), S23–S24 (Task 4), S25 (Task 5, 7); §13 "LLM giả cho từng role" (`RoleClient`).
- **Chưa phủ bằng test tự động:** ba việc lập lịch đồng thời trên cụm (kiểm tay ở Task 6 Step 5); chất lượng prompt chuyên gia (đo ở Task 7).
- **Type consistency:** thông điệp agent có ba dạng — event (`"type"`), kết quả (`"role"`, `"place_ids"`, `"note"`), lỗi (`"role"`, `"error"`) — dùng thống nhất ở `_work`, `gather`, `_remote`, `serve`. `recv(timeout) -> dict | None` ở cả `_local` và `_remote`.
