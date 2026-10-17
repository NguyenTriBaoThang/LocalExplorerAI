# Revision đầy đủ: lịch sử chat, Pinned Stop, dãy version

> 2026-09-30 · Lát T2–T3 trong [ROADMAP](../../ROADMAP.md) · Issue #17, #3, #25, #24 · PRD §5.4 (không được cắt).
> Thuật ngữ theo [CONTEXT.md](../../../CONTEXT.md).

## 1. Mục tiêu

Bước 6–7 của kịch bản demo (PRD §3.2) chạy được trọn vẹn:

1. Ghim một Stop.
2. Nhắn "ngày 2 mưa thì sao", ra v2, Stop đã ghim giữ nguyên.
3. Nhắn "bớt 500k", ra v3.
4. Bấm v1 để xem lại, rồi bấm "Quay lại bản này".
5. Tải lại app vẫn thấy Trip, hội thoại và các version.

Đã có sẵn, không làm lại: followup (answer / edit_itinerary / confirm_replan), `changed` để tô viền Stop vừa đổi, từ chối thao tác lên Stop có `pinned=True` (`followup.py` `at()`, `replan.py` `propose`), `GET /trips` và `GET /trips/{id}`.

## 2. Quyết định (chốt trong buổi grill 2026-09-30)

| # | Quyết định | Lý do |
|---|---|---|
| D1 | Thêm bảng `messages` riêng. `trips.user_messages` giữ nguyên cho parse và brief | `user_messages` chỉ chứa tin làm đổi Trip; câu hỏi và phản hồi AI không có ở đâu |
| D2 | Ghim là thuộc tính của **Trip**: lưu ở `trips.pinned_place_ids int[]`, gán vào `stop.pinned` mỗi khi load | Ghim không tạo version (PRD §5.4); không phải sửa version bất biến; 3 chỗ kiểm tra hiện có giữ nguyên |
| D3 | Version cũ chỉ để xem. Restore = chép Draft của bản cũ → `build_itinerary` với Trip hiện tại → version mới | Tính lại Conflict theo Budget hiện tại; không xoá gì |
| D4 | Restore bản không còn chứa một Place đang ghim → tự bỏ ghim Place đó và báo trong chat | Người dùng đã chủ động chọn bản cũ |
| D5 | Restore bản có số ngày khác Trip hiện tại → 422, câu báo tiếng Việt | Version không lưu spec Trip; không đoán thay người dùng |

## 3. Server

### 3.1 Schema (`server/app/schema.sql`, thêm theo kiểu `IF NOT EXISTS` như hiện có)
```sql
ALTER TABLE trips ADD COLUMN IF NOT EXISTS pinned_place_ids integer[] NOT NULL DEFAULT '{}';

CREATE TABLE IF NOT EXISTS messages (
  id serial PRIMARY KEY,
  trip_id integer NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user', 'ai')),
  text text NOT NULL,
  version integer,            -- version Itinerary mà tin này tạo ra (nếu có)
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_trip ON messages(trip_id, id);
```

### 3.2 Load Itinerary có ghim (`trips.py`)
- Tạo `load_itinerary(conn, trip_id, version=None) -> (version, Itinerary, places) | None`. Hàm này đọc bản cần xem (hoặc bản mới nhất) rồi gán `stop.pinned = stop.place_id in trips.pinned_place_ids`.
- `latest_itinerary`, `proposals.create_disruption` (hiện đọc thẳng `data`) và `get_trip` đều đi qua hàm này. Vì vậy followup, disruption và replan tự thấy ghim mà không phải sửa chỗ kiểm tra nào.

### 3.3 Lập lại phải giữ Place đã ghim
- `build_itinerary(..., pinned: set[int] = frozenset())`: Draft thiếu Place nào trong `pinned` → `InvalidDraft("Thiếu Place đã ghim: …")`. AI làm lại 1 lần như với Place lạ (cơ chế sẵn có trong `agent.plan`).
- `agent.plan` nhận thêm `pinned`. `previous_brief` ghi thêm dòng "Place đã ghim, bắt buộc giữ: …".
- Followup không cần sửa: `apply_ops` đã chặn thay, xoá hay dời Stop ghim.

### 3.4 Ghi lịch sử chat
Tạo helper `log_message(conn, trip_id, role, text, version=None)` và gọi ở:

| Chỗ gọi | role | text | version |
|---|---|---|---|
| `_run` sau khi có `trip_id` (Trip mới); đầu `_follow_up` | user | tin nhắn | — |
| `_plan_and_save` và `_follow_up` khi có event `itinerary` | ai | `itinerary.summary` | version mới |
| `_follow_up` với event `answer` / `confirm_replan` | ai | `text` | — |
| `apply_proposal` | ai | "Đã áp dụng phương án — lịch trình bản N." | N |
| `restore` | ai | "Đã quay lại bản K (thành bản N)." + tên Place bị bỏ ghim nếu có | N |

Không lưu `thinking`, `tool_call`, `clarify`, `error` vì đó là tiến trình, không phải hội thoại.

### 3.5 API mới
| Method | Path | Kết quả |
|---|---|---|
| GET | `/trips/{id}?version=N` | như hiện tại + `versions: [1..max]` + `pinned_place_ids`; `version` không có → 404 |
| GET | `/trips/{id}/messages` | `[{role, text, version, created_at}]` theo `id` tăng dần |
| PATCH | `/trips/{id}/pins` `{place_id, pinned}` | `{pinned_place_ids}`; Place không nằm trong bản mới nhất → 422 |
| POST | `/trips/{id}/restore/{version}` | JSON như `apply_proposal`: event `itinerary` `{…, version}` |

Mọi API trả 404 khi Trip thuộc User khác. Restore bản không tồn tại → 404; khác số ngày → 422 (D5).

## 4. Client

### 4.1 `api.ts`
Thêm `listTrips`, `getTrip(token, id, version?)`, `getMessages`, `setPin`, `restoreVersion`, cùng các kiểu tương ứng. Thêm hàm thuần `viewingOld(version, versions)` để test không cần DOM.

### 4.2 `App.tsx`
- Thêm state `versions: number[]` và `latest: number | null`. `version` hiện có đổi nghĩa thành bản **đang xem**.
- Sau khi đăng nhập: `listTrips` → mở Trip mới nhất (`getTrip` + `getMessages` → dựng `chat`). Chưa có Trip thì giữ empty state.
- Đặt danh sách Trip (Destination · số ngày · ngày tạo) và nút "Đăng xuất" trong ChatPanel. Sang T4 sẽ chuyển lên rail.
- Gửi chat khi đang xem bản cũ → chuyển về bản mới nhất trước rồi mới gửi.

### 4.3 `Timeline.tsx`
- Dãy `v1 · v2 · v3`. Bấm một số → `getTrip(id, n)`.
- Khi `version != latest`: hiện banner "Đang xem bản N · [Quay lại bản này] [Về bản mới nhất]", khoá nút Disruption và nút ghim.
- Mỗi Stop có nút 📌 bật/tắt (`aria-pressed`). Stop đã ghim có nền nhạt riêng.

## 5. Lỗi
- PATCH pins / restore bị 404 hoặc 422 → bong bóng đỏ trong chat (dùng `call()` sẵn có).
- Restore khi đã có bản mới hơn thì không lỗi: restore luôn tạo `max + 1`.
- Tải Trip lúc mở app mà thất bại → giữ empty state, không chặn.

## 6. Test
Server (pytest, Postgres Docker):
- `build_itinerary` từ chối Draft thiếu Place ghim.
- `plan` với fake LLM: lần 1 thiếu Place ghim → bị trả lỗi → lần 2 đúng.
- PATCH pins → followup `edit_itinerary` đụng Place đó bị từ chối; disruption trên Stop đó → 422.
- Restore: v1 → v4 có cùng Stop với v1; v2, v3 còn nguyên; Place ghim không có trong v1 → bị bỏ ghim; khác số ngày → 422.
- Messages: một lượt lập Trip + một answer + một edit → 6 dòng đúng thứ tự và `version`.
- User khác gọi 4 API mới → 404.

Client (vitest): `viewingOld`, dựng `chat` từ `messages`.

E2E thủ công bằng app desktop: chạy đúng kịch bản ở §1.

## 7. Ngoài phạm vi
- Rail, ngăn kéo đẹp, animate Stop đổi trên map: làm cùng UI mới T4 (#16, #4).
- Giới hạn độ dài lịch sử gửi LLM (PRD §15): followup chỉ gửi tin nhắn mới + dữ kiện lịch, chưa cần.
- Ghim theo ngày: ghim theo `place_id`. Khi lập lại cả lịch (replan), AI được phép xếp Place đã ghim sang ngày khác, chỉ bắt buộc Place đó còn trong lịch.
