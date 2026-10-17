# Chia sẻ lịch trình và duyệt góp ý Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hoàn thành vòng desktop “xuất PDF → nhập góp ý nhóm trong Trip Chat → xem trước → áp dụng thành version mới” mà người tổ chức luôn giữ quyền chốt.

**Architecture:** Dùng bản Itinerary đang xem để dựng trang in PDF ở client. Nhánh **Góp ý nhóm** đi qua SSE/job pipeline đang dùng cho AI trong Chat để phát trạng thái, lượt tìm Place và preview. Server đưa version nguồn cùng version latest vào AI, áp thao tác lên latest bằng `build_itinerary`, rồi lưu candidate trong bảng proposal của Trip shard. Chỉ endpoint apply mới gọi `save_itinerary`; yêu cầu sửa thông thường tiếp tục theo đường Chat hiện có.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, PostgreSQL/psycopg theo Trip shard, React 19, TypeScript, Vite, Tailwind CSS, Vitest, pytest; PDF dùng trang in và print dialog của desktop WebView, không thêm thư viện PDF. `window.print()` mở print dialog theo [MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/API/Window/print); cần xác nhận lựa chọn lưu PDF trong runtime pywebview thực tế.

**Spec:** `docs/superpowers/specs/2026-10-14-chia-se-va-duyet-lich-design.md`

## Global Constraints

- “Một người tổ chức giữ quyền sửa và áp dụng version.”
- “Lịch và góp ý của nhóm không được trộn với lịch sử chat riêng hay Trip khác.”
- “Góp ý có ngữ cảnh version; chỉnh sửa được kiểm tra bằng quy tắc của code, không để AI tự tính chi phí hoặc hợp lệ.”
- “Chỉ người tổ chức duyệt bản AI đề xuất mới tạo version mới.”
- “Kế hoạch triển khai đầu tiên chỉ bao gồm giai đoạn 1 trên desktop.”
- “Giai đoạn mobile native là dự án triển khai riêng sau đó; framework, push provider và phát hành store sẽ được quyết định trong kế hoạch riêng, không phải điều kiện để hoàn tất giai đoạn desktop.”
- Không triển khai web app, đồng chỉnh sửa, tự quyết theo đa số, đặt vé/phòng, thanh toán hoặc xác minh danh tính khách mời.

## Review Focus

- Góp ý chọn version cũ nhưng Trip đã có version mới trước lúc tạo candidate: candidate dùng latest làm `base_version`, giữ `source_version` để đối chiếu; ghim hành vi bằng test trong Task 2.
- Một chỉnh sửa khác tạo version mới sau lúc candidate hình thành: apply phải trả 409 và không ghi version; ghim hành vi bằng test cạnh tranh version trong Task 3.
- Góp ý nhóm có yêu cầu trái chiều: kết quả phải đưa ý chưa thống nhất vào `unresolved_feedback`, không tự chọn theo đa số; ghim hành vi bằng test trong Task 2.
- AI trả Stop/place/op không hợp lệ hoặc lịch vi phạm luật cứng: code từ chối candidate và không lưu proposal/version; ghim hành vi bằng test trong Task 2.
- AI đề xuất chi phí/Conflict khác với kết quả tính của app: chỉ dữ liệu do `build_itinerary` tính được lưu và hiển thị; ghim hành vi bằng test trong Task 2.

---

## Bản đồ file và trách nhiệm

| File | Trách nhiệm trong kế hoạch |
|---|---|
| `server/app/schema_shard.sql` | Lưu group review proposal cùng shard với Trip. |
| `server/app/followup.py` | Thêm prompt/tool riêng cho góp ý nhóm; tái dùng `run_search`, `apply_ops`, `build_itinerary`. |
| `server/app/group_reviews.py` | Tạo preview, apply và cancel; xác thực quyền Trip, quản lý trạng thái proposal và kiểm tra version nền. |
| `server/app/main.py` | Đăng ký router group reviews. |
| `server/app/trips.py` | Đăng ký job group review trong SSE pipeline và tuần tự hoá lưu version bằng lock Trip row. |
| `server/tests/test_group_reviews_api.py` | Kiểm thử luồng tạo, apply, cancel, stale-version và quyền sở hữu. |
| `server/tests/test_followup.py` | Kiểm thử prompt/tool review và kết quả code dựng lại lịch. |
| `server/tests/test_shards.py` | Xác nhận bảng mới hiện diện ở Trip shard. |
| `server/tests/test_versions_api.py` | Kiểm thử hai writer đồng thời không cấp trùng số version. |
| `server/tests/test_worker.py` | Xác nhận group-review job chạy được qua Redis worker. |
| `client/src/api.ts` | Kiểu dữ liệu, SSE preview và request apply/cancel. |
| `client/src/components/ChatPanel.tsx` | Chuyển giữa chat thường và chế độ **Góp ý nhóm**, chọn source version và nhập nội dung. |
| `client/src/components/GroupReviewPanel.tsx` | Hiển thị summary, Stop đổi, unresolved feedback, chi phí/Conflict và Apply/Cancel. |
| `client/src/App.tsx` | Quản lý candidate, gọi endpoint, xử lý apply/cancel/stale và cập nhật Timeline/Chat. |
| `client/src/components/Timeline.tsx` | Đặt nút xuất PDF cạnh lịch/version đang xem. |
| `client/src/tripPrint.ts` | Dựng model in từ Trip summary, version, Itinerary và Place hiện có. |
| `client/src/components/TripPrintView.tsx` | Render snapshot lịch trình dành riêng cho in. |
| `client/src/index.css` | Quy tắc `@media print` để chỉ in snapshot. |
| `client/src/api.test.ts`, `client/src/tripPrint.test.ts` | Kiểm thử request và dữ liệu snapshot in. |
| `README.md` | Cập nhật danh sách chức năng sau khi hoàn thành. |

### Hợp đồng dữ liệu và endpoint

- `POST /trips/{trip_id}/group-reviews` nhận `{source_version: number, feedback: string}`; `source_version >= 1`, feedback sau trim không rỗng và tối đa 2000 ký tự như chat hiện tại. Trả SSE giống job Chat, phát `thinking`/`tool_call` rồi event cuối `{type: "group_review_preview", review: {review_id, source_version, base_version, source_is_old, feedback, summary, unresolved_feedback, changed, itinerary, places}}`. `source_version` phải tồn tại; `base_version` là latest tại lúc tạo candidate. Nếu latest đổi trong lúc AI đang tạo candidate, kết thúc bằng `error` event có `code: "stale_base"`; không lưu proposal/message.
- `POST /trips/{trip_id}/group-reviews/{review_id}/apply` nhận `{}`; trả Itinerary event có `trip_id` và `version`. Gọi lặp cùng review trả lại version đã áp dụng, không sinh version trùng.
- `POST /trips/{trip_id}/group-reviews/{review_id}/cancel` nhận `{}`; chuyển proposal `pending` sang `cancelled`, không ghi Itinerary version.
- Bảng `group_review_proposals` lưu `trip_id`, `source_version`, `base_version`, feedback, candidate JSON (`itinerary`, `places`, `summary`, `changed`, `unresolved_feedback`), trạng thái `pending|applied|cancelled`, `applied_version`, `created_at`.
- Chat thường tiếp tục gọi `/trips` như hiện tại. Góp ý nhóm không đi qua nhánh auto-save của `_follow_up`.

### Thứ tự phụ thuộc

```text
Task 1 schema ──► Task 2 tạo SSE preview ──► Task 3 apply/cancel ──► Task 4 Chat flow
                                                                        │
                                                                        ▼
                                                                  Task 5 PDF flow
                                                                        │
                                                                        ▼
                                                                  Task 6 acceptance
```

---

### Task 1: Lưu proposal trên Trip shard

**Files:**
- Modify: `server/app/schema_shard.sql`
- Test: `server/tests/test_shards.py`

**Interfaces:**
- Produces: bảng `group_review_proposals` có `source_version`, `base_version`, `feedback`, `candidate`, `status`, `applied_version`, `created_at`.
- Schema được khởi tạo qua `db.apply_schema`; không thêm migration runner mới.

- [ ] **Step 1: Viết test thất bại cho bảng trên các shard**

Thêm test này vào `server/tests/test_shards.py`:

```python
def test_group_review_proposals_table_on_each_shard(shards):
    for url in shards:
        with db._open(url) as shard:
            row = shard.execute(
                "SELECT to_regclass('public.group_review_proposals') AS table_name"
            ).fetchone()
            assert row["table_name"] is not None
```

Dùng `db` import hiện có ở đầu file.

- [ ] **Step 2: Chạy test để xác nhận thiếu bảng**

Run từ `server/`:

```bash
uv run pytest tests/test_shards.py::test_group_review_proposals_table_on_each_shard -q
```

Expected: FAIL vì `to_regclass` trả `None` trên shard.

- [ ] **Step 3: Thêm bảng và ràng buộc**

Trong `schema_shard.sql`, thêm bảng sau sau `proposals`; cột version tham chiếu cùng Trip/version để candidate không thể trỏ sang lịch của Trip khác:

```sql
CREATE TABLE IF NOT EXISTS group_review_proposals (
  id serial PRIMARY KEY,
  trip_id integer NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  source_version integer NOT NULL,
  base_version integer NOT NULL,
  feedback text NOT NULL,
  candidate jsonb NOT NULL,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'applied', 'cancelled')),
  applied_version integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (trip_id, source_version) REFERENCES itineraries(trip_id, version),
  FOREIGN KEY (trip_id, base_version) REFERENCES itineraries(trip_id, version),
  FOREIGN KEY (trip_id, applied_version) REFERENCES itineraries(trip_id, version)
);
CREATE INDEX IF NOT EXISTS group_review_proposals_trip
  ON group_review_proposals(trip_id, id DESC);
```

- [ ] **Step 4: Chạy test schema mới**

Run: `cd server && uv run pytest tests/test_shards.py::test_group_review_proposals_table_on_each_shard -q`

Expected: PASS; bảng được tạo trên cả hai shard test.

- [ ] **Step 5: Rà soát schema diff**

Run: `git diff --check`

Expected: không có whitespace error; schema tiếp tục được áp dụng qua `db.init_schemas()` hiện có.

---

### Task 2: Tạo preview góp ý bằng AI và kiểm tra bằng code

**Files:**
- Modify: `server/app/followup.py`
- Create: `server/app/group_reviews.py`
- Modify: `server/app/main.py`
- Modify: `server/app/trips.py`
- Create: `server/tests/test_group_reviews_api.py`
- Modify: `server/tests/test_followup.py`
- Modify: `server/tests/test_worker.py`

**Interfaces:**
- Consumes: bảng `group_review_proposals` từ Task 1; `load_itinerary`, `itinerary_places`, `run_search`, `apply_ops`, `build_itinerary`, `hub_for`, `current_user`, `get_shard` hiện có.
- Produces: `GroupReviewIn(source_version: int = Field(ge=1), feedback: str = Field(min_length=1, max_length=2000))` với validator trim để từ chối chuỗi chỉ có khoảng trắng; `JOBS["group_review"]`; SSE `group_review_preview` event theo hợp đồng ở đầu kế hoạch.
- AI tool tên `review_group_feedback` trả `summary`, `ops` theo các loại hiện có trong `EDIT_TOOL`, và `unresolved_feedback: string[]`. `changed`, tiền, Leg và Conflict đều do code tính.

- [ ] **Step 1: Viết test đỏ cho source version cũ, unresolved và candidate chưa tạo version**

Trong `server/tests/test_group_reviews_api.py`, import `auth`, `events`, `no_meal_rule`, `trip_with_itinerary`, `use_llm` từ `tests.test_trips_api`, `two_versions` từ `tests.test_versions_api`, và `reply` từ `tests.fakes`; dùng fixture `client`, `conn`, `monkeypatch`. `no_meal_rule` giữ các test này theo cùng fixture môi trường như các Trip API test hiện có. Sau khi chuẩn bị Trip ở v2, giả lập tool response và ghim các hành vi sau:

```python
def test_old_source_version_uses_latest_base_without_saving(client, conn, monkeypatch):
    h, tid, _, _ = two_versions(client, conn, monkeypatch)
    use_llm(monkeypatch, [reply(("review_group_feedback", {
        "summary": "Giữ quán, dời giờ",
        "ops": [{"op": "retime_stop", "day": 1, "stop": 1, "start_time": "10:00"}],
        "unresolved_feedback": ["Một người muốn ăn trưa sớm, một người muốn ăn trưa muộn"],
    }))])
    evs = events(client.post(f"/trips/{tid}/group-reviews", headers=h,
                             json={"source_version": 1, "feedback": "Nhóm góp ý cho bản 1"}))
    review = evs[-1]["review"]
    assert evs[-1]["type"] == "group_review_preview"
    assert (review["source_version"], review["base_version"], review["source_is_old"]) == (1, 2, True)
    assert review["unresolved_feedback"] == ["Một người muốn ăn trưa sớm, một người muốn ăn trưa muộn"]
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1, 2]
    saved_feedback = client.get(f"/trips/{tid}/messages", headers=h).json()[-1]
    assert (saved_feedback["role"], saved_feedback["text"], saved_feedback["version"]) == (
        "user", "Nhóm góp ý cho bản 1", 1)
```

Thêm test source version không tồn tại để route từ chối trước khi enqueue job:

```python
def test_missing_source_version_is_404(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    response = client.post(f"/trips/{tid}/group-reviews", headers=h,
                           json={"source_version": 9, "feedback": "Đổi quán"})
    assert response.status_code == 404
    assert conn.execute("SELECT count(*) AS n FROM group_review_proposals").fetchone()["n"] == 0
```

Trong cùng file, viết test invalid-place trước khi cài handler:

```python
def test_invalid_place_does_not_persist_review(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    messages_before = client.get(f"/trips/{tid}/messages", headers=h).json()
    use_llm(monkeypatch, [reply(("review_group_feedback", {
        "summary": "Đổi quán",
        "ops": [{"op": "replace_stop", "day": 1, "stop": 1, "place_id": 999_999}],
        "unresolved_feedback": [],
    }))])
    evs = events(client.post(f"/trips/{tid}/group-reviews", headers=h,
                             json={"source_version": 1, "feedback": "Đổi quán"}))
    assert evs[-1]["type"] == "error"
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1]
    assert conn.execute("SELECT count(*) AS n FROM group_review_proposals").fetchone()["n"] == 0
    assert client.get(f"/trips/{tid}/messages", headers=h).json() == messages_before
```

Thêm test scope quyền sở hữu cho route tạo:

```python
def test_group_review_create_is_trip_scoped(client, conn, monkeypatch):
    _, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    other = auth(client, "binh@example.com")
    response = client.post(f"/trips/{tid}/group-reviews", headers=other,
                           json={"source_version": 1, "feedback": "Đổi quán"})
    assert response.status_code == 404
    assert conn.execute("SELECT count(*) AS n FROM group_review_proposals").fetchone()["n"] == 0
```

Thêm test Trip đổi version trong lúc model đang tạo preview. Gắn side effect vào fake LLM trước khi nó trả tool response: đọc dữ liệu Itinerary v1 rồi gọi `save_itinerary` thêm một version mới cho Trip. Kỳ vọng event cuối là `error` với `code == "stale_base"`, version mới vẫn tồn tại, nhưng không có group-review proposal hoặc message góp ý mới. Test này ghim việc kiểm tra lại latest sau AI và trước khi lưu candidate.

Thêm test sau để kiểm tra giờ sai định dạng bị từ chối trước khi lưu proposal:

```python
def test_invalid_edit_does_not_persist_review(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    messages_before = client.get(f"/trips/{tid}/messages", headers=h).json()
    use_llm(monkeypatch, [reply(("review_group_feedback", {
        "summary": "Đổi giờ",
        "ops": [{"op": "retime_stop", "day": 1, "stop": 1, "start_time": "9h"}],
        "unresolved_feedback": [],
    }))])
    evs = events(client.post(f"/trips/{tid}/group-reviews", headers=h,
                             json={"source_version": 1, "feedback": "Đổi giờ"}))
    assert evs[-1]["type"] == "error"
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1]
    assert conn.execute("SELECT count(*) AS n FROM group_review_proposals").fetchone()["n"] == 0
    assert client.get(f"/trips/{tid}/messages", headers=h).json() == messages_before
```

Thêm test hard rule bị vi phạm: dùng `change_stay` trỏ tới Place quán cà phê hiện có trong lịch, để `build_itinerary` từ chối Place không phải chỗ ở. Xác nhận SSE kết thúc bằng `error`, version không tăng, proposal không được lưu và lịch sử chat không đổi.

- [ ] **Step 2: Viết test service cho version context, feedback trái chiều và cost**

Trong `server/tests/test_followup.py`, import `FakeClient`, `reply` và `review_group_feedback`; thêm service test dùng fixtures hiện có để ghim instructions/version context và chứng minh `build_itinerary` bỏ qua `total_cost` giả từ model:

```python
def test_group_review_uses_code_computed_cost_and_keeps_unresolved_feedback():
    base = itin()
    ops = [{"op": "retime_stop", "day": 1, "stop": 1, "start_time": "09:00"}]
    draft, _ = apply_ops(base, ops, set(PLACES))
    expected = build_itinerary(TRIP, draft, PLACES)
    fake = FakeClient([reply(("review_group_feedback", {
        "summary": "Dời giờ", "ops": ops, "unresolved_feedback": ["Ý kiến trái chiều"],
        "total_cost": 999_999_999,
    }))])
    generated = list(review_group_feedback(
        None, fake, "test-model", TRIP, 1, base, 2, base, PLACES,
        "Dời giờ", [None, None], None, lambda _texts: [],
    ))
    prompt = fake.calls[0]["messages"][0]["content"]
    assert "Version nguồn: 1" in prompt and "Version nền mới nhất: 2" in prompt
    assert "không tự chọn theo đa số" in prompt
    candidate = generated[-1]["candidate"]
    assert candidate["unresolved_feedback"] == ["Ý kiến trái chiều"]
    assert candidate["itinerary"]["total_cost"] == expected.total_cost
    assert candidate["itinerary"]["total_cost"] != 999_999_999
```

- [ ] **Step 3: Viết test job qua Redis worker**

Trong `server/tests/test_worker.py`, viết test sau. Các helper `env`, `happy`, `submit`, `use_llm`, `published`, `types` và `count` đã có trong file:

```python
def test_group_review_job_runs_and_publishes_preview(conn, rds, monkeypatch):
    use_llm(monkeypatch, happy(add_place(conn, kind="cafe")))
    plan_job = submit(conn)
    assert worker.step(conn, rds, "w1") is True
    itinerary_event = next(e for e in published(rds, plan_job)
                           if isinstance(e, dict) and e["type"] == "itinerary")
    trip_id = itinerary_event["trip_id"]
    user_id = conn.execute("SELECT user_id FROM trips WHERE id = %s", (trip_id,)).fetchone()["user_id"]

    use_llm(monkeypatch, [reply(("review_group_feedback", {
        "summary": "Dời giờ ghé quán",
        "ops": [{"op": "retime_stop", "day": 1, "stop": 1, "start_time": "10:00"}],
        "unresolved_feedback": [],
    }))])
    job_id = jobs.enqueue("group_review", user_id, {
        "trip_id": trip_id, "source_version": 1, "feedback": "Dời giờ ghé quán",
    })
    assert worker.step(conn, rds, "w1") is True
    assert types(rds, job_id) == ["thinking", "group_review_preview", "end"]
    assert count(conn, "group_review_proposals") == 1
    assert count(conn, "itineraries") == 1
```

- [ ] **Step 4: Chạy test đỏ cho route, service và worker**

Run từ `server/`:

```bash
uv run pytest tests/test_group_reviews_api.py::test_old_source_version_uses_latest_base_without_saving tests/test_group_reviews_api.py::test_missing_source_version_is_404 tests/test_group_reviews_api.py::test_group_review_create_is_trip_scoped tests/test_group_reviews_api.py::test_preview_stale_base_does_not_persist_review tests/test_group_reviews_api.py::test_invalid_place_does_not_persist_review tests/test_group_reviews_api.py::test_invalid_edit_does_not_persist_review tests/test_group_reviews_api.py::test_invalid_hard_rule_does_not_persist_review tests/test_followup.py::test_group_review_uses_code_computed_cost_and_keeps_unresolved_feedback tests/test_worker.py::test_group_review_job_runs_and_publishes_preview -q
```

Expected: FAIL do route, service hoặc job `group_review` chưa được thêm.

- [ ] **Step 5: Thêm prompt/tool riêng cho group feedback**

Trong `followup.py`, thêm `GROUP_REVIEW_PROMPT`, `GROUP_REVIEW_TOOL` và hàm:

```python
def review_group_feedback(
    conn, client, model, trip: Trip, source_version: int, source: Itinerary,
    base_version: int, base: Itinerary, places: dict[int, Place], feedback: str,
    rain: list[int | None], hub: Hub | None, embed_fn,
) -> Iterator[dict]:
    """Phát tool_call event rồi group_review_candidate đã được code kiểm tra."""
```

Prompt truyền vào AI cả source version và latest/base version; phần facts ghi chính xác `Version nguồn: N` và `Version nền mới nhất: M`. Yêu cầu dùng latest làm lịch thao tác, giữ lại ý kiến trái chiều trong `unresolved_feedback`, không bỏ Stop không liên quan, không tự chọn theo đa số. Dùng `run_search` khi cần Place mới và yield các event tìm kiếm; dùng `apply_ops` để đổi draft; sau đó dựng candidate bằng `build_itinerary(trip, draft, seen, rain, hub)`. Không nhận total cost, Leg hoặc Conflict do model tự tính. Kết thúc bằng yield `{"type": "group_review_candidate", "candidate": {"summary", "unresolved_feedback", "changed", "itinerary", "places"}}`. Nếu op/place/draft sai cấu trúc hoặc vi phạm luật cứng, ném lỗi domain để handler phát SSE error và không insert proposal.

Run từ `server/`: `uv run pytest tests/test_followup.py::test_group_review_uses_code_computed_cost_and_keeps_unresolved_feedback -q`

Expected: PASS; source/base context được gửi cho model, ý chưa thống nhất còn nguyên, cost lấy từ Itinerary đã build.

- [ ] **Step 6: Viết route xác thực và đưa request vào job pipeline**

Trong `group_reviews.py`, tạo router tương tự `proposals.py`. Route xác thực quyền sở hữu, itinerary và source version, sau đó trả qua `_stream("group_review", user_id, trip_id=..., source_version=..., feedback=...)`. Không gọi LLM trong request handler.

Đăng ký `group_reviews.router` trong `server/app/main.py` sau khi `trips` được import; `group_reviews.py` dùng `_stream` từ `trips.py`, còn `trips.py` không import router này.

- [ ] **Step 7: Thêm group-review handler vào SSE/job pipeline**

Trong `trips.py`, thêm `_job_group_review(conn, user_id, trip_id, source_version, feedback)` và `JOBS["group_review"]`. Handler chạy trong shard của user qua cùng worker/direct path như `message`; phát `thinking`, phát `tool_call` từ `run_search` và kết thúc bằng `group_review_preview`. Handler phải:

1. Recheck ownership của Trip và load source/latest Itinerary sau khi job chạy.
2. Gộp Place data từ source/base, dựng Trip/rain/Hub context và gọi `review_group_feedback`.
3. Sau khi model trả candidate, mở transaction, lock Trip row, đọc lại latest; nếu base đã thay đổi, phát error event và không ghi.
4. Nếu còn khớp, ghi row `pending` cùng user message gắn `source_version` trong transaction; phát preview event. Không gọi `save_itinerary`.

Handler bắt `InvalidEdit`/`InvalidDraft` và phát event `error` có thông điệp tiếng Việt; nếu latest đổi trong lúc model chạy, phát `error` kèm `code: "stale_base"`. LLM/search errors đi qua `guarded` hiện có. Khi nhận `group_review_candidate`, handler recheck/lock base, lưu row proposal và user message trong một transaction, rồi phát event `{type: "group_review_preview", review: ...}`. Worker và direct path cùng gọi `JOBS["group_review"]`.

- [ ] **Step 8: Chạy test backend của preview**

Run từ `server/`:

```bash
uv run pytest tests/test_group_reviews_api.py tests/test_followup.py tests/test_worker.py -q
```

Expected: PASS; SSE preview không thay đổi Itinerary version và row/message chỉ được lưu khi candidate hợp lệ, kể cả khi job chạy qua worker.

---

### Task 3: Apply có kiểm tra stale và cancel không tạo version

**Files:**
- Modify: `server/app/group_reviews.py`
- Modify: `server/app/trips.py`
- Modify: `server/app/proposals.py`
- Modify: `server/tests/test_group_reviews_api.py`
- Modify: `server/tests/test_versions_api.py`
- Modify: `server/tests/test_disruptions_api.py`

**Interfaces:**
- Consumes: `group_review_proposals` pending và candidate JSON từ Task 2.
- Produces: `POST /trips/{trip_id}/group-reviews/{review_id}/apply` và `/cancel`.
- Apply trả Itinerary event theo `ItineraryEvent` hiện có; cancel trả `{review_id, status: "cancelled"}`.

- [ ] **Step 1: Viết test apply, apply lặp, cancel và stale base**

Thêm helper tạo review pending và test API trong `test_group_reviews_api.py`:

```python
def create_pending_review(client, h, tid, monkeypatch):
    use_llm(monkeypatch, [reply(("review_group_feedback", {
        "summary": "Dời giờ ghé quán",
        "ops": [{"op": "retime_stop", "day": 1, "stop": 1, "start_time": "10:00"}],
        "unresolved_feedback": [],
    }))])
    evs = events(client.post(f"/trips/{tid}/group-reviews", headers=h,
                             json={"source_version": 1, "feedback": "Dời giờ ghé quán"}))
    return evs[-1]["review"]

def test_apply_group_review_is_idempotent(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    review = create_pending_review(client, h, tid, monkeypatch)
    path = f"/trips/{tid}/group-reviews/{review['review_id']}/apply"
    first = client.post(path, headers=h, json={})
    retry = client.post(path, headers=h, json={})
    assert first.status_code == retry.status_code == 200
    assert first.json()["version"] == retry.json()["version"] == 2
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1, 2]
    saved_result = client.get(f"/trips/{tid}/messages", headers=h).json()[-1]
    assert (saved_result["role"], saved_result["version"]) == ("ai", 2)

def test_cancel_group_review_keeps_versions(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    review = create_pending_review(client, h, tid, monkeypatch)
    path = f"/trips/{tid}/group-reviews/{review['review_id']}/cancel"
    cancelled = client.post(path, headers=h, json={})
    retry = client.post(path, headers=h, json={})
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == retry.json()["status"] == "cancelled"
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1]

def test_group_review_apply_and_cancel_are_trip_scoped(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    review = create_pending_review(client, h, tid, monkeypatch)
    other = auth(client, "binh@example.com")
    apply_path = f"/trips/{tid}/group-reviews/{review['review_id']}/apply"
    cancel_path = f"/trips/{tid}/group-reviews/{review['review_id']}/cancel"
    assert client.post(f"/trips/{tid}/group-reviews", headers=other,
                       json={"source_version": 1, "feedback": "Đổi quán"}).status_code == 404
    assert client.post(apply_path, headers=other, json={}).status_code == 404
    assert client.post(cancel_path, headers=other, json={}).status_code == 404

def test_apply_stale_group_review_returns_409(client, conn, monkeypatch):
    h, tid, _ = trip_with_itinerary(client, conn, monkeypatch)
    review = create_pending_review(client, h, tid, monkeypatch)
    path = f"/trips/{tid}/group-reviews/{review['review_id']}/apply"
    other = add_place(conn, name="Cafe rẻ hơn", kind="cafe")
    use_llm(monkeypatch, [reply(("search_places", {"query": "cafe rẻ"})),
                          reply(("edit_itinerary", {"summary": "Đổi sang quán rẻ hơn", "ops": [
                              {"op": "replace_stop", "day": 1, "stop": 1, "place_id": other}]}))])
    events(client.post("/trips", json={"message": "rẻ hơn", "trip_id": tid}, headers=h))
    stale = client.post(path, headers=h, json={})
    assert stale.status_code == 409
    assert client.get(f"/trips/{tid}", headers=h).json()["versions"] == [1, 2]
```

- [ ] **Step 2: Viết test cho Trip row lock giữa hai writer**

Trong `server/tests/test_versions_api.py`, viết test riêng cho hai writer:

```python
def test_save_itinerary_waits_for_trip_row_lock(client, conn, monkeypatch):
    _, trip_id, _ = trip_with_itinerary(client, conn, monkeypatch)
    blocker = db._open(TEST_URL)
    blocker.execute("BEGIN")
    # NO KEY UPDATE is compatible with the FK's implicit KEY SHARE, so only
    # save_itinerary's explicit FOR UPDATE should make the writer wait.
    blocker.execute("SELECT id FROM trips WHERE id = %s FOR NO KEY UPDATE", (trip_id,))
    started = threading.Event()
    saved = []
    pid = []

    def save():
        with db._open(TEST_URL) as writer:
            pid.append(writer.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"])
            started.set()
            saved.append(save_itinerary(writer, trip_id, {"summary": "writer"}, {}))

    thread = threading.Thread(target=save)
    thread.start()
    try:
        assert started.wait(timeout=2)
        deadline = time.monotonic() + 2
        blocked = False
        while time.monotonic() < deadline:
            row = conn.execute(
                "SELECT wait_event_type = 'Lock' AS blocked FROM pg_stat_activity WHERE pid = %s",
                (pid[0],),
            ).fetchone()
            if row is None or row["blocked"]:
                blocked = row is not None and row["blocked"]
                break
            time.sleep(0.01)
        assert blocked
    finally:
        blocker.commit()
        thread.join(timeout=2)
        blocker.close()
    assert not thread.is_alive() and saved == [2]
```

Chỉnh sửa Trip xen giữa dùng đường follow-up hiện tại `search_places` + `edit_itinerary`, hoàn tất sau khi review base v1 đã được lưu. Import `threading` và `time` từ standard library, `db` từ `app`, `save_itinerary` từ `app.trips`, `TEST_URL` từ `tests.conftest`, và `trip_with_itinerary` từ `tests.test_trips_api`; include fixture `client` trong chữ ký test khóa.

- [ ] **Step 3: Chạy test để xác nhận apply/cancel và lock behavior chưa có**

Run từ `server/`:

```bash
uv run pytest tests/test_group_reviews_api.py tests/test_versions_api.py tests/test_disruptions_api.py::test_concurrent_apply_of_two_proposals_second_gets_409 -q
```

Expected: FAIL ở endpoint apply/cancel và test Trip row lock vì helper hiện tại chưa chờ lock Trip.

- [ ] **Step 4: Tuần tự hoá mọi lệnh lưu version**

Trong `trips.py`, đổi `save_itinerary` thành transaction nhỏ: lock Trip row trước, sau đó đọc MAX(version) và INSERT version mới trong cùng transaction. Dùng `with conn.transaction()` để helper vẫn an toàn khi connection đang autocommit và tạo savepoint khi caller đã mở transaction. Giữ cùng chữ ký và kiểu trả về hiện tại.

Run: `cd server && uv run pytest tests/test_versions_api.py::test_save_itinerary_waits_for_trip_row_lock -q`

Expected: PASS; writer thứ hai nằm ở trạng thái chờ lock đến khi transaction giữ Trip row kết thúc.

Giữ nguyên stale contract của disruption proposals khi mọi lệnh lưu Itinerary đã được tuần tự hoá: trong `test_disruptions_api.py::test_concurrent_apply_of_two_proposals_second_gets_409`, đặt barrier ở `_trip`, rồi dùng connection riêng giữ Trip bằng `FOR NO KEY UPDATE`. Ghi PID hai writer và đợi đến khi cả hai có `wait_event_type='Lock'` trong `pg_stat_activity` mới thả blocker. Không barrier ở `_latest_version`: với code cũ chưa khóa Trip trước stale check, cả hai sẽ đã đọc v1 rồi chờ bên trong `save_itinerary`; sau khi thả, chúng tạo v2 và v3. Với code mới, writer thứ hai chờ trước stale check rồi trả 409. Cách này làm regression test tất định, không phụ thuộc scheduler.

- [ ] **Step 5: Implement apply trong transaction có row lock**

Dùng `SELECT ... FOR UPDATE` cho proposal rồi Trip row. Nếu `status='applied'`, trả candidate và `applied_version` đã lưu; nếu `status='cancelled'`, trả 409. Nếu pending, so `base_version` với `MAX(version)` của Trip. Lệch version thì trả 409 trước khi lưu. Gọi `save_itinerary` trong transaction apply; bắt `UniqueViolation` còn lại và trả cùng lỗi stale 409. Sau khi lưu, set `status='applied'`, `applied_version`, và ghi summary AI vào `messages` với version mới.

Trong `proposals.py::apply_proposal`, khóa Trip row bằng `SELECT ... FOR UPDATE` trong transaction trước khi so `base_version` với latest và trước khi gọi `save_itinerary`. Nhờ vậy disruption proposal đã stale trong lúc chờ lock trả 409 như hợp đồng hiện tại; giữ thứ tự khóa proposal rồi Trip như group-review apply. Chạy regression `cd server && uv run pytest tests/test_disruptions_api.py::test_concurrent_apply_of_two_proposals_second_gets_409 -q`.

- [ ] **Step 6: Implement cancel idempotent cho proposal pending**

Chỉ chuyển `pending` sang `cancelled`; cancel lặp lại trả trạng thái cancelled. Không xóa Itinerary và không gọi `save_itinerary`. Proposal đã apply không thể cancel; trả 409.

- [ ] **Step 7: Chạy test vòng đời proposal**

Chạy:

```bash
cd server && uv run pytest tests/test_group_reviews_api.py tests/test_versions_api.py tests/test_disruptions_api.py::test_concurrent_apply_of_two_proposals_second_gets_409 -q
```

Expected: PASS cho apply/version bất biến, apply retry, cancel, stale base, writer đồng thời và quyền 404 khi người dùng khác truy cập.

---

### Task 4: Nối chế độ Góp ý nhóm vào Trip Chat

**Files:**
- Modify: `client/src/api.ts`
- Modify: `client/src/components/ChatPanel.tsx`
- Create: `client/src/components/GroupReviewPanel.tsx`
- Modify: `client/src/App.tsx`
- Modify: `client/src/api.test.ts`

**Interfaces:**
- Consumes: `POST` contracts từ Task 2–3; các state `tripId`, `version`, `versions`, `latest`, `itinerary`, `places`, `chat` hiện có.
- Produces: `streamGroupReview(token: string, tripId: number, sourceVersion: number, feedback: string, onEvent: (e: AgentEvent) => void): Promise<void>`, `applyGroupReview(token, tripId, reviewId): Promise<ItineraryEvent>`, `cancelGroupReview(token, tripId, reviewId): Promise<{review_id: number; status: 'cancelled'}>`, `GroupReview` type, `ApiError.status` cho REST 409 và `group_review_preview` AgentEvent.
- `ChatPanel` nhận `versions`, `version`, `latest`, `onGroupReview: (feedback: string, sourceVersion: number) => Promise<boolean>`; chỉ xóa feedback khi SSE kết thúc bằng preview thành công. Chat thường vẫn gọi `onSend` không đổi.

- [ ] **Step 1: Viết SSE và REST wrapper test thất bại**

Trong `client/src/api.test.ts`, mock `fetch`, gọi `streamGroupReview` và ghim method/path/body:

```ts
const review = { review_id: 4, source_version: 2, base_version: 3, source_is_old: true,
  feedback: 'Giữ quán cũ', summary: 'Giữ quán', unresolved_feedback: [], changed: [],
  itinerary: {}, places: {} }
const fetchMock = vi.fn().mockResolvedValue(new Response(
  `data: ${JSON.stringify({ type: 'group_review_preview', review })}\n\n`,
  { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
))
vi.stubGlobal('fetch', fetchMock)
const received: AgentEvent[] = []
await streamGroupReview('token', 7, 2, 'Giữ quán cũ', (event) => received.push(event))
expect(received).toEqual([{ type: 'group_review_preview', review }])
expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/trips/7/group-reviews'),
  expect.objectContaining({ method: 'POST', body: JSON.stringify({ source_version: 2, feedback: 'Giữ quán cũ' }) }))
```

Thêm test cho apply/cancel path; để apply trả 409 `{detail: 'Lịch trình đã có bản mới hơn'}` và assert lỗi là `ApiError`, có `status === 409` và giữ đúng detail.

- [ ] **Step 2: Chạy test API để xác nhận wrapper chưa có**

Run từ `client/`: `npm test -- --run src/api.test.ts`

Expected: FAIL vì các hàm/type group review chưa được export.

- [ ] **Step 3: Thêm AgentEvent, lỗi có status và API functions**

Trong `api.ts`, thêm type và hàm theo hợp đồng:

```ts
export type GroupReview = {
  review_id: number; source_version: number; base_version: number; source_is_old: boolean
  feedback: string; summary: string; unresolved_feedback: string[]; changed: [number, number][]
  itinerary: Itinerary; places: Record<string, Place>
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = 'ApiError' }
}
```

Thêm nhánh `AgentEvent` `{type: 'group_review_preview'; review: GroupReview}`. `streamGroupReview()` dùng `streamSSE()` với body `{source_version, feedback}`. Error event nhận `code?: 'stale_base' | 'http_error'` và `status?: number`; khi phản hồi mở stream không thành công, giữ HTTP status trong event để App tải lại version khi cần. `request<T>` ném `ApiError` cho apply/cancel HTTP failures và vẫn giữ nguyên `message` cho `App.call`.

- [ ] **Step 4: Thêm chế độ nhập feedback tách khỏi chat thường**

Trong `ChatPanel.tsx`, thêm action **Góp ý nhóm** khi Trip có itinerary/version. Mỗi lần bật mode, mặc định source version là version đang xem; người tổ chức có thể đổi trong danh sách `versions`. Khi source khác latest, hiện cảnh báo ghi rõ hai version. Nút gửi trong mode này await `onGroupReview`; chỉ xóa input khi kết quả là `true`. Nếu stream lỗi hoặc bị stale, giữ nguyên text để thử lại. Nút gửi mode thường tiếp tục gọi `onSend` và giữ hành vi xóa input hiện tại.

- [ ] **Step 5: Nối state tạo preview trong App**

Trong `App.tsx`, thêm `groupReview` state. `onGroupReview` thêm feedback bubble vào Chat kèm `version=source_version` trước khi stream (giống vị trí tin nhắn user trong chat thường), sau đó gọi `streamGroupReview` qua `run`; trả `true` chỉ khi nhận `group_review_preview`, lỗi event trả `false`. Khi nhận preview, `handle()` lưu candidate. Nạp `getMessages()` cũng giữ `version` trong ChatItem để bubble góp ý có nhãn đúng ngữ cảnh. Xoá candidate khi `newTrip`, `openTrip` đổi Trip hoặc nhận event `trip` cho Trip khác; đặt `key={tripId ?? 'new'}` cho `ChatPanel` để form/mode không rò sang Trip khác. Không thay đổi `send()` hoặc `streamTrip` cho chat thường.

- [ ] **Step 6: Hiển thị candidate và thao tác Apply/Cancel**

Tạo `GroupReviewPanel.tsx` đặt qua `ChatPanel` prop `children`, không đưa preview lên Timeline. Card hiển thị source/base version, summary, Stop đổi (dùng `changed` indexes và `places`), unresolved feedback, tổng chi phí candidate và Conflict; có nút **Áp dụng** và **Huỷ**.

Apply thành công thì lấy Itinerary event để cập nhật `itinerary`, `places`, `version`, `latest`, `versions`, đóng card và thêm tin AI kèm version mới. Cancel gọi endpoint rồi đóng card, không thay state Itinerary.

- [ ] **Step 7: Xử lý preview stale ngay trong luồng Chat**

Nếu server phát error event `code: 'stale_base'` trong lúc tạo preview, hoặc apply ném `ApiError` status 409, gọi `getTrip` lấy latest nhưng giữ Chat, feedback draft và source version. Với stale lúc tạo preview chưa có candidate, hiện thông báo stale cùng action **Tạo lại preview** dùng feedback/source vừa gửi; với stale lúc apply, đánh dấu candidate hiện có là stale rồi dùng cùng action. Khi apply thành công gọi `getTrip` để đồng bộ versions thay vì tự nối một version có thể trùng do writer khác. Không tự apply candidate cũ. Lỗi 401 tiếp tục đi qua xử lý logout hiện có.

- [ ] **Step 8: Chạy test API và build client**

Run từ `client/`:

```bash
npm test -- --run src/api.test.ts
npm run build
```

Expected: tests PASS, TypeScript/Vite build PASS; tương tác Chat thường vẫn hoạt động qua `streamTrip` như trước.

---

### Task 5: Xuất PDF từ version đang xem

**Files:**
- Create: `client/src/tripPrint.ts`
- Create: `client/src/tripPrint.test.ts`
- Create: `client/src/components/TripPrintView.tsx`
- Modify: `client/src/components/Timeline.tsx`
- Modify: `client/src/App.tsx`
- Modify: `client/src/index.css`

**Interfaces:**
- Consumes: Trip summary hiện tại, `version`, `Itinerary`, `places`, `budget`; không gọi server và không thay đổi lịch.
- Produces: `buildTripPrintModel(trip, version, itinerary, places, budget, exportedAt)` và `TripPrintView({model})`.
- Click **Xuất PDF** dựng model từ đúng state version đang xem rồi gọi `window.print()`; native print dialog cho phép chọn lưu thành PDF.

- [ ] **Step 1: Viết test đỏ cho model snapshot**

Trong `tripPrint.test.ts`, khai báo fixture đủ kiểu `TripSummary`, `Itinerary`, `Place` cho một ngày có Stay, một Stop, Leg từ Hub (`null`) tới Stop, budget và Conflict. Ghim contract bằng các assertion cụ thể:

```ts
const model = buildTripPrintModel(trip, 3, itinerary, places, 2_000_000, '2026-10-14T10:00:00+07:00')
expect(model.destination).toBe('Đà Lạt')
expect(model.version).toBe(3)
expect(model.days[0].stops[0]).toMatchObject({ startTime: '09:00', placeName: 'Cà phê Tùng' })
expect(model.days[0].legs[0]).toMatchObject({ fromLabel: 'Bến/sân bay', toLabel: 'Cà phê Tùng', mode: 'car' })
expect(model.conflicts).toEqual(['Vượt ngân sách'])
expect(model.exportedAt).toBe('2026-10-14T10:00:00+07:00')
```

- [ ] **Step 2: Chạy test để xác nhận builder chưa có**

Run từ `client/`: `npm test -- --run src/tripPrint.test.ts`

Expected: FAIL vì `tripPrint.ts` chưa tồn tại.

- [ ] **Step 3: Viết builder thuần từ dữ liệu đang hiển thị**

Thêm type và chữ ký sau trong `tripPrint.ts`:

```ts
export type TripPrintModel = {
  destination: string; version: number; exportedAt: string; stayName: string | null
  budget: number | null; totalCost: number; conflicts: string[]
  days: Array<{
    date: string | null
    stops: Array<{ startTime: string; placeName: string; reason: string; cost: number }>
    legs: Array<{ fromLabel: string; toLabel: string; mode: string; distanceKm: number; durationMin: number; cost: number }>
  }>
}

export function buildTripPrintModel(
  trip: TripSummary, version: number, itinerary: Itinerary, places: Record<string, Place>,
  budget: number | null, exportedAt: string,
): TripPrintModel
```

Tạo nhãn đầu/cuối Leg dễ hiểu khi `from_place_id` hoặc `to_place_id` là Hub (`null`); không đoán thông tin Place thiếu. Dùng `day.date`, `Stop.start_time`, `Place.name`, `Leg` và các cost đã có; không gọi AI hay tính lại các số.

- [ ] **Step 4: Render trang in độc lập với màn hình ứng dụng**

Tạo `TripPrintView.tsx` với destination, ngày đi theo từng ngày, Stay, lịch Stop, tuyến Leg, cost ước tính, warnings/conflicts, `vN` và thời điểm xuất theo locale `vi-VN`. Trong `App.tsx`, render view từ `printModel` tách khỏi nội dung chat/map; tạo một snapshot model cùng timestamp khi người dùng bấm **Xuất PDF**, gọi `window.print()` trong `useEffect` sau khi React đã render model, rồi dọn state print khi nhận `afterprint` để không giữ bản cũ.

- [ ] **Step 5: Nối nút xuất trên Timeline và CSS phân trang**

Thêm `onExportPdf` cho `Timeline`; chỉ hiện **Xuất PDF** khi đang có Itinerary và version. Trong `index.css`, `@media print` ẩn shell/map/chat/controls, chỉ hiện `.trip-print`, dùng nền trắng, màu chữ tương phản và tránh ngắt trang giữa tiêu đề ngày với danh sách Stop.

- [ ] **Step 6: Chạy test builder và build**

Run từ `client/`: `npm test -- --run src/tripPrint.test.ts && npm run build`

Expected: PASS; output print model có cùng `version` với Timeline hiện đang xem.

---

### Task 6: Hoàn tất acceptance flow desktop và ghi chú phát hành

**Files:**
- Modify: `README.md`
- Test/verification: các test backend/client từ Task 1–5; chạy desktop pywebview thủ công.

**Interfaces:**
- Consumes: preview/apply/cancel và print view đã tích hợp.
- Produces: tài liệu tính năng cập nhật và checklist nghiệm thu vòng chia sẻ → góp ý → duyệt version.

- [ ] **Step 1: Cập nhật README tính năng**

Trong `README.md` mục `## Tính năng`, thêm hai ý: xuất PDF snapshot version đang xem; góp ý nhóm trong Chat tạo preview và chỉ người tổ chức apply thành version mới. Không ghi mobile/web như đã phát hành.

- [ ] **Step 2: Chạy bộ test tính năng phía server**

Run từ `server/`:

```bash
uv run pytest tests/test_group_reviews_api.py tests/test_followup.py tests/test_shards.py -q
```

Expected: PASS; proposal chỉ tồn tại trên đúng shard và stale candidate không làm tăng version.

- [ ] **Step 3: Chạy test/build client**

Run từ `client/`:

```bash
npm test -- --run src/api.test.ts src/tripPrint.test.ts
npm run build
```

Expected: PASS; TypeScript không có lỗi và client build được cho desktop.

- [ ] **Step 4: Thử luồng trên pywebview**

Chạy `cd client && npm run build`, sau đó `cd desktop && uv run python main.py`. Mở một Trip, xuất PDF từ version đang xem và xác nhận print dialog của runtime cho phép lưu PDF; mở file kiểm tra lịch, Stay, Leg, cost, warnings, version và timestamp. Sau đó gửi góp ý nhóm, thử cancel, tạo preview khác rồi apply; xác nhận version chỉ tăng ở Apply và PDF mới ghi version mới.

- [ ] **Step 5: Ghi nhận pilot thủ công**

Thử với nhóm nhỏ người thường đứng ra lên kế hoạch; ghi tỷ lệ hoàn thành vòng chia sẻ → góp ý → duyệt version và thời gian đến lịch nhóm thống nhất. Thu baseline trước khi đặt mục tiêu số; không thêm analytics service cho đợt này.

---

## Tự rà soát kế hoạch theo spec

- PDF đúng version đang xem, có lịch theo ngày/giờ, Stay, Leg, cost, warnings, version và thời điểm: Task 5.
- Chat thường giữ hành vi hiện tại; chỉ action **Góp ý nhóm** mở preview: Task 4.
- Preview chưa tạo Itinerary version; candidate tính lại qua code: Tasks 1–2.
- Apply/cancel, version bất biến, stale base và apply retry: Task 3.
- Source version cũ có cảnh báo và vẫn gắn đúng feedback: Tasks 2 và 4.
- Feedback và kết quả apply ở Trip Chat history: Tasks 2–3.
- Mobile native, link guest, push và web đều ngoài kế hoạch này: Global Constraints.
- Placeholder/step chưa rõ: không còn; plan dùng schema, endpoint, component, lệnh test và hành vi dự kiến cụ thể.
