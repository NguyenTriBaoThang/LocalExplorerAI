# Travility — Hiện trạng app (cập nhật 2026-10-05, sau scale T6)

> Ảnh chụp hiện trạng code, dùng làm phụ lục cho [PRD.md](PRD.md). Quyết định và lộ trình nằm trong PRD; tài liệu này chỉ mô tả code **đang chạy thế nào**. Bản đầu viết 2026-09-25 sau Plan 1; bản này theo `main` sau khi merge scale T6 (PR #59). Danh sách việc theo từng issue: [ROADMAP.md](ROADMAP.md).

Thuật ngữ in đậm theo [CONTEXT.md](../CONTEXT.md). Spec gốc: [travility-design.md](superpowers/specs/2026-09-25-travility-design.md).

## 1. Tiến độ

- **Plan 1** (nền tảng + AI Trip Planner lõi): ✅ merge `main` (PR #1).
- **Cá nhân hoá lát 1** ✅: hỏi lại một vòng, giờ đến/về, **Hub**, xe riêng, đủ 3 bữa/ngày, thêm 27 Place.
- **Revision đầy đủ** ✅ (#22, #25, #24, #17): tin nhắn trên Trip đã có lịch → trả lời / sửa đúng Stop liên quan / xác nhận lập lại; Pinned Stop; dãy version + "Quay lại bản này"; lịch sử chat theo Trip.
- **Revision giữ mục đích lát A+B+C** ✅ (#31, #32): chip Intent + R trên Timeline; "Báo đóng cửa" / "Đổi chỗ khác" trên Stop → tối đa 3 Proposal do code tạo (không LLM) → "Áp dụng" tạo version mới; "☂ Giả sử mưa" trên header ngày (thay Stop ngoài trời chưa ghim bằng Place trong nhà, thiếu thì bỏ; không ghi `rain_chance`) và "Tôi trễ 15/30/60′" trên Stop (dời giờ, thay Stop đóng cửa ở giờ mới, bỏ Stop vượt giờ Pace / giờ về; Stop ghim chỉ bị dời). Chưa có: bản đồ theo thời điểm, đánh giá B0/B1/B2, ranker, chat → Disruption (lát D–F).
- **UI mới** ✅ (#2, #16, #3, #4): map toàn màn hình, rail, panel nổi, map ↔ Timeline hai chiều, "Xem hành trình".
- **Km thật** ✅ (#7, #39): Goong Distance Matrix ở server + Conflict "không kịp di chuyển"; từ chối Draft xếp chỗ ở làm Stop.
- **Scale T2–T6** ✅ (#48–#52): `llm-gateway` + Redis, queue + `planner` + `nginx`, đa agent, service `places` + bản sao đọc + 2 shard, trang "Hệ thống" + load test. Kiến trúc đóng băng từ 2026-10-02.
- Test: server 362, client 40 (pytest + Postgres Docker; vitest).
- **Đã chạy E2E** với Gemini thật qua app desktop (`gemini-3.5-flash-lite`, embedding `gemini-embedding-001`).
- **Dữ liệu:** 37 Place Đà Lạt, trong đó 27 gắn `"unverified": true` chờ kiểm chứng, chưa Place nào có `photo_url` (mốc cứng: ≥ 150 Place Đà Lạt trước 15/10, #19).
- **Chưa làm:** mô hình dự đoán mưa (#53), Tag chỗ ở + đổi Stay (#26), nợ lát A+B (#37), lát D–F (#33–#36), bảng chi phí trên Timeline (#40), giọng nói (#8, #9), PDF (#11), recap (#28), script thu thập + ảnh Place (#5, #41), golden set 2 provider (#6), đóng gói (#15), diễn tập demo (#29).
- **Đã cắt:** Google login, quên mật khẩu, Traveler Profile, chỗ ở đã đặt + điểm bắt buộc ghé, Inspiration Photo, Đà Nẵng – Hội An, Hà Nội.

## 2. Luồng hoạt động

### 2.0 Chuẩn bị dữ liệu (ngoài app, chạy lại khi sửa JSON)
```
data/places/da-lat.json ──► scripts/import_places.py ──► Postgres (destinations + hubs, places)
                               │ kiểm tra tag/kind/hub hợp lệ
                               └ embedding mỗi Place → vector(768)
```
File JSON là nguồn dữ liệu duy nhất; import upsert theo `ext_id`. `destination.hubs` (tuỳ chọn) khai báo sân bay/bến xe/ga theo **Arrival Mode**.

### 2.1 Mở app + đăng nhập
- `desktop/main.py` mở cửa sổ pywebview với `client/dist/index.html` qua HTTP server nội bộ (cổng 42001), hoặc `localhost:5173` khi dev.
- Chưa có token → màn Login → `POST /auth/register` hoặc `/auth/login` → bcrypt + JWT 7 ngày → client lưu `localStorage`.
- Có token → màn chính: bản đồ toàn màn hình + rail + panel Chat và Timeline nổi (§3.2). Server trả 401 → quay về Login.
- Lưu ý: WebKit giữ cache bản build cũ ở `~/Library/Caches/python3` → build client xong mà app trắng thì xoá thư mục đó.

### 2.2 Luồng chính: tin nhắn → Itinerary (`server/app/trips.py`)
```
Client streamTrip(message, tripId) — POST /trips {message, trip_id?} (Bearer JWT), đọc SSE
  ├─ trip_id của User khác → 404 (trước khi mở stream)
  ├─① "thinking"  "Đang đọc yêu cầu…"
  ├─② agent.parse_trip — LLM, bắt buộc tool record_trip, đọc TOÀN BỘ tin nhắn của Trip
  │     → Trip {destination, days, start_date, budget, travelers, tags, pace,
  │             travel_mode?, origin_city?, arrival_mode?, arrival_time?, departure_time?}
  │     trường người dùng không nói = để trống; giờ sai định dạng ("2pm") bị bỏ
  │     tin nhắn tiếp theo: merge_trip giữ câu trả lời cũ, trống thì mặc định (xe-may)
  │     → INSERT/UPDATE trips (spec, user_messages) → "trip" {trip_id, trip, center}
  ├─③ Trip mới + missing_questions() khác rỗng?
  │     → "clarify" {trip_id, questions} rồi ĐÓNG stream          (hỏi tối đa 1 vòng)
  │       câu hỏi: travel_mode (nếu chưa nói); arrival (nếu có ngày đi mà chưa biết giờ)
  │       client: POST /trips/{id}/plan {travel_mode?, arrival_*?}  ({} = "Bỏ qua")
  │         → apply_answers bằng code (không gọi LLM) → 404/409/422 trước khi stream
  │         → "trip" rồi tiếp tục ④⑤
  ├─④ forecast.get_rain_chance — Open-Meteo (chỉ khi có ngày đi trong 16 ngày; lỗi thì bỏ qua)
  └─⑤ agent.plan — vòng lặp tool-calling, tối đa 12 lượt
        brief: Trip + giờ đến/về + Hub + khả năng mưa + NGUYÊN VĂN tin nhắn người dùng
        search_places(query, kind, tags)
          → embed(query) → pgvector: đúng Destination, đủ tag bắt buộc, loại tag cần tránh, top 8
          → "tool_call" {places} ⇒ pin vàng nhấp nháy trên map
        submit_itinerary(draft)
          → rules.build_itinerary:
               • kiểm tra Place đã được search, đủ số ngày, có Stay nếu > 1 ngày
               • route mỗi ngày: [Hub ngày 1 | Stay] → Stop… → [Hub ngày cuối | Stay]
               • Leg: km + phút từ Goong Distance Matrix (app/distance.py, 1 request/ngày, cache trong tiến trình + Redis khi có REDIS_URL);
                 không có GOONG_API_KEY hoặc Goong lỗi → chim bay × 1.3 (lỗi thì nghỉ gọi 60s);
                 < 0.8 km đi bộ; xe máy thuê / riêng, ô tô riêng, Grab
               • find_conflicts: vượt Budget, đóng cửa, thiếu tag, mưa + ngoài trời,
                 before_arrival, after_departure, missing_meal,
                 no_travel_time (Leg dài hơn khoảng trống giữa hai Stop + 5′; Conflict mềm với engine thay thế)
          → sai: cho LLM làm lại 1 lần
          → có Conflict: gửi lại cho LLM sửa 1 lần, lần submit thứ 2 được chấp nhận
        → INSERT itineraries (version = max + 1) → "itinerary" {itinerary, places, trip_id, version}
```

Tin nhắn tiếp theo trên Trip **đã có** lịch trình (`server/app/followup.py`, SSE, #22):
```
POST /trips {message, trip_id} → có Itinerary → followup (không parse_trip, không lập lại)
  → LLM nhận trip_brief + itinerary_facts (km/phút/tiền từng ngày, chi phí theo nhóm, mưa, [ngày.stop] từ 1)
  → chọn 1 tool:
      answer(text)              → "answer" {text}; không version mới, câu hỏi không vào user_messages
      edit_itinerary(ops)       → apply_ops (thay/xoá/thêm/dời Stop, đổi chỗ ở; Stop không nhắc giữ nguyên, pinned bị từ chối)
                                  → build_itinerary → Conflict mới: sửa 1 lần → lưu version → "itinerary" {…, changed}
      change_trip(changes,text) → "confirm_replan"; người dùng bấm "Lập lại" → POST /trips/{id}/replan
                                  → lập lại, lịch cũ + Place cũ đưa vào làm gợi ý
```

Ghim, version, lịch sử chat (`server/app/versions.py`, JSON thường, #25 #24 #17):
```
PATCH /trips/{id}/pins {place_id, pinned} → trips.pinned_place_ids (không tạo version; Place không có trong bản mới nhất → 422)
  mọi lần đọc lịch (load_itinerary) gán stop.pinned = place_id ∈ pinned_place_ids → followup/disruption tự chặn Stop ghim
  lập lại (replan): Draft thiếu Place ghim → InvalidDraft, AI làm lại 1 lần
GET /trips/{id}?version=N → bản bất kỳ + versions[] + pinned_place_ids + center
POST /trips/{id}/restore/{version} → to_draft(bản cũ) → build_itinerary theo Trip hiện tại → version mới
  khác số ngày → 422; Place ghim không có trong bản cũ → tự bỏ ghim, báo trong chat
GET /trips/{id}/messages → bảng messages: tin user + phản hồi cuối của AI (answer, tóm tắt, confirm_replan, áp dụng, quay lại)
```

Sự cố trên một Stop (`server/app/proposals.py`, JSON thường, không SSE):
```
POST /trips/{id}/disruptions {version, kind: closed|disliked|rain|late, day_index, stop_index?, minutes?}  # rain: không stop_index; late: minutes 5–240
  → version khác bản mới nhất: 409 · Stop đã ghim / không tồn tại: 422 · Trip của User khác: 404
  → replan.propose: ứng viên = similar_places (embedding đã lưu, cùng kind, bỏ Place đã dùng + Tag tránh)
      → distance.prefetch chặng tới/rời từng ứng viên (km thật)
      → lọc is_open + kịp giờ (make_leg) → xếp theo score(features) → build_itinerary
      → loại phương án sinh Conflict cứng mới → tối đa 3 Proposal + metrics + reason_codes + câu giải thích
  → INSERT proposals (kiêm log feedback) → {proposal_id, options} hoặc {proposal_id, no_feasible}
POST /trips/{id}/proposals/{pid}/apply {option}
  → khoá dòng proposals; đã áp dụng cùng option → trả version cũ (idempotent), option khác → 409
  → save_itinerary (version = max + 1), lưu chosen_index → "itinerary" {…, version}
```

`llm-gateway` (`server/app/gateway.py`, chỉ chạy trong cụm `docker-compose.cluster.yml`, #48):
```
api ──LLM_BASE_URL / EMBED_BASE_URL──► llm-gateway /v1/chat/completions, /v1/embeddings ──► Gemini / OpenAI
  cache Redis theo hash(request): GATEWAY_CACHE = off | on | replay (replay trượt → 503, dùng cho demo mất mạng)
  chat: giới hạn LLM_RPM (hết lượt thì chờ ≤ 30s), provider chính 429/5xx/timeout → provider phụ LLM2_*
  DEMO_TODAY đóng băng "hôm nay" ở parse_trip + forecast để bản ghi trúng cache ở ngày khác
```
Queue lập lịch (`server/app/jobs.py`, `server/app/worker.py`, chỉ khi có `REDIS_URL`, #49):
```
client ─► nginx ─► api ×2 ──XADD jobs──► planner ×2 (python -m app.worker)
                    ▲                        │ chạy trips.JOBS[kind] trong một transaction
                    └──XREAD events:{job_id}─┘ XADD events:{job_id}; nhịp tim 5 s, nhận lại sau 20 s im lặng
  rate limit theo User: rl:{user_id}:{phút} ≤ PLAN_RPM → 429 + Retry-After
  GET /jobs/{job_id}/events: phát lại tiến trình (header X-Job-Id)
```
Thiếu `REDIS_URL`: việc chạy ngay trong request như trước.

Lập lịch đa agent (`server/app/multi.py`, chỉ khi `PLANNER_MODE=multi`, #50):
```
planner (điều phối) ──XADD agent_jobs × 3 {key, role, trip}──► planner-agent ×3 (python -m app.worker --stream agent_jobs)
        ▲                                                         │ multi.shortlist: ≤ 4 lượt search_places, code ép kind theo role
        └──BLPOP agent:{uuid}: event tool_call (agent=role) + {role, place_ids, note}──┘
  đủ danh sách → agent.plan(seeded=…, max_searches=2); agent lỗi / Redis lỗi / quá 45 s → agent.plan đơn
  thiếu REDIS_URL → ba chuyên gia chạy bằng 3 thread trong tiến trình
```
`server/scripts/golden.py` đo `single` và `multi` trên 8 prompt (bảng ở runbook).

Trang "Hệ thống" và chế độ chỉ đọc (`server/app/system.py`, `server/app/nodes.py`, #52):
```
GET /system/status (cần đăng nhập) → {nodes[], served_by, my_shard, planner_mode, stats}
  node một bản (4 Postgres, redis, llm-gateway, places): bản api đang trả lời dò song song, hạn 2 s
  api / planner / planner-agent: nhịp tim ZADD nodes mỗi 2 s; im quá 6 s = chết; Redis chết → "unknown"
  stats: số trúng / trượt cache, lượt gọi / chờ / chuyển provider, lượt bị rate limit, việc chờ / đang chạy
  chế độ một tiến trình: chỉ có bản api này và database, stats = null
pg-catalog chính chết: db.get_conn lùi về bản sao → đăng nhập vẫn chạy, đăng ký 503 "chế độ chỉ đọc";
  api / planner vẫn khởi động được khi có SHARD_URLS (init_schemas chỉ cảnh báo)
```
`server/scripts/loadtest.py` in bảng p50 / p95 / lượt mỗi giây; `scripts/smoke_cluster.sh` dựng cụm và kiểm 15 node sống (số đo và bảng trình diễn ở runbook).

Cách dựng cụm, ghi → phát lại kịch bản demo, tắt `planner`, xoá cache: [runbook-cum.md](runbook-cum.md). Chế độ `docker compose up` (một tiến trình, không gateway) vẫn là mặc định khi dev.

### 2.3 Nguyên tắc cần giữ khi mở rộng
- **LLM chỉ chọn Place và xếp giờ; tiền và Conflict do code tính** (`server/app/rules.py`).
- **AI chỉ được dùng Place đã có trong kết quả search** (biến `seen` trong `agent.plan`, ADR-0001).
- **Code quyết định có hỏi lại hay không** (`missing_questions`), không phải LLM; câu trả lời chip áp bằng code (`apply_answers`).
- SSE có 8 event: `thinking`, `trip`, `tool_call`, `clarify`, `itinerary`, `answer`, `confirm_replan`, `error`. Thêm event mới thì sửa cả server và `AgentEvent` trong `client/src/api.ts`.
- Agent gửi lại nguyên message của LLM (`model_dump`) — Gemini 3 cần `thought_signature` trong tool_calls.
- Khung giờ bữa ăn (`MEALS`) có ở cả `rules.py` và `client/src/api.ts` — đổi thì đổi cả hai.
- **Proposal do code tạo, không gọi LLM** (ADR-0006). Bảng `INTENT_LABELS` có ở cả `domain.py` và `client/src/api.ts` — đổi thì đổi cả hai.

### 2.4 Chỗ hổng và điểm nối cho tính năng tiếp theo
| Hiện trạng | Hệ quả / hướng mở rộng |
|---|---|
| AI có thể xếp Place `cho-o` làm Stop → tiền phòng tính 2 lần | Từ chối trong `_check_draft` |
| Kem/ăn vặt (kind `an-uong`) vẫn tính là bữa chính | Tag `an-vat` không tính là bữa |
| Vượt Budget chỉ báo một dòng, không có bảng chi phí | Gửi breakdown cho AI + hiện trên Timeline |
| Leg Hub → thành phố tính theo Travel Mode | Tính theo Arrival Mode |
| Server tính Leg theo xe của Travel Mode (bike/car), map luôn vẽ `vehicle=bike` | Grab / ô tô riêng có thể lệch nhẹ với tuyến vẽ → truyền Travel Mode cho `MapView` |
| Mỗi lần search gọi embedding một lần; Gemini free giới hạn request/phút | `llm-gateway` cache + giới hạn theo provider (#48): chạy cụm `docker-compose.cluster.yml` |
| Chưa có Traveler Profile, chỗ ở đã đặt, điểm bắt buộc ghé | Lát 2–3 của spec cá nhân hoá (#18) |
| Dữ liệu 37 Place, 27 chưa kiểm chứng | #19 |

## 3. UI/UX hiện tại

Theo [mockup #2](https://claude.ai/artifact/FqsEi2pjdHPdM2qoYD83ih) và [spec UI mới](superpowers/specs/2026-09-30-ui-moi-design.md) (2026-09-30). Tông rừng thông `pine` + dã quỳ `marigold` (`@theme` trong `client/src/index.css`), font Be Vietnam Pro.

### 3.1 Luồng màn hình
```
Mở app ──► có token? ──không──► [Login] (một form, nút đổi Đăng nhập/Đăng ký)
              │ có                   │ thành công → lưu token
              ▼                      ▼
        [Màn chính] ◄────────────────┘   tự mở Trip gần nhất; chưa có → câu chào + 3 gợi ý bấm được
```

### 3.2 Bố cục màn chính
```
┌──┬──────────────────────────────────────────────────────────────┐
│🟡│ ╭ Chat (340px) ╮        BẢN ĐỒ TOÀN MÀN          ╭ Lịch trình ╮│
│＋│ │ Destination ·│   pin số màu ngày, "Chỗ ở",      │ v1·v2·v3   ││
│🗂│ │ ngân sách    │   tuyến Goong, popup Place        │ chi phí,   ││
│  │ │ bong bóng…   │                                   │ Conflict,  ││
│  │ │ [ô nhập][Gửi]│      [▶ Xem hành trình]           │ thẻ Stop   ││
│⎋ │ ╰──────────────╯                                   ╰────────────╯│
└──┴──────────────────────────────────────────────────────────────┘
```
- **Rail** (`Rail.tsx`): logo, ＋ Chuyến mới, 🗂 popover "Chuyến đi của tôi" (Esc/bấm ra ngoài để đóng), 🖥 Hệ thống, ⎋ Đăng xuất.
- **Trang "Hệ thống"** (`SystemPage.tsx`): lớp phủ bên phải rail, node xếp theo tầng (`tiers` ở `api.ts`), xanh / đỏ / xám, tự làm mới 2 giây sau mỗi phản hồi, Esc đóng.
- **Nối lại luồng lập lịch** (`streamSSE` ở `api.ts`): luồng đứt khi chưa có event kết thúc và có header `X-Job-Id` → gọi `GET /jobs/{id}/events` tối đa 2 lần, bỏ qua event đã hiện.
- **Panel nổi** (`FloatingPanel.tsx`): thu gọn thành nút; Chat thu gọn có badge số tin mới. Cửa sổ < 1100px chỉ mở một panel (`layout.ts` `setPanel`). Timeline chỉ hiện khi có Itinerary và tự mở khi có lịch mới.
- **Stop đang chọn** (`selected` ở `App`, kiểu `Selected` trong `place.ts`): bấm thẻ Stop → bản đồ bay tới + `PlacePopup`; bấm pin → Timeline cuộn tới thẻ, viền vàng. Nút "Báo đóng cửa" / "Đổi chỗ khác" chỉ hiện trên Stop đang chọn. Itinerary đổi → bỏ chọn.
- **PlacePopup**: ảnh (`photo_url`, chưa có thì ô màu + icon theo kind — `PlaceThumb`), loại, giá, trong nhà/ngoài trời, giờ mở hôm đó (`openToday`), mô tả, nút Ghim. Itinerary lưu trước 2026-09-30 không có `open_hours`/`description` → popup ẩn hai dòng đó.
- **Camera**: có Itinerary → `fitBounds` mọi Stop + Stay (chừa chỗ panel, `pitch: 0`), không tự bay. "Xem hành trình" bay qua từng Stop (`tourStops`), bấm Dừng / kéo map / lịch đổi → dừng ngay. `prefers-reduced-motion` → không animate.
- **Tuyến**: gọi Goong Direction song song, timeout 5s mỗi Leg, lỗi → đường thẳng (trước đây gọi tuần tự không timeout, một request treo là tuyến không bao giờ hiện).

### 3.3 Trải nghiệm theo event SSE
| Thời điểm | Chat | Map | Timeline |
|---|---|---|---|
| Chưa gõ | Câu chào + 3 gợi ý bấm được | Đà Lạt, nghiêng 45° | Ẩn |
| Vừa gửi | Bong bóng user, "AI đang lên lịch trình…", khoá nút Gửi | Xoá pin cũ | — |
| `trip` | Nhớ `tripId` → tin sau thuộc Trip này; hiện nút "Chuyến mới" | Bay tới thành phố | Xoá lịch trình cũ |
| `clarify` | Thẻ hỏi lại: chip phương tiện, chip phương tiện đến + ô giờ tới/về, "Lên lịch" / "Bỏ qua, cứ lên lịch". Gõ tay vào ô chat cũng được | — | — |
| `tool_call` | "Đang tìm: … (n kết quả)" | Pin vàng nhấp nháy dồn dần | — |
| `itinerary` | Tóm tắt của AI; thẻ hỏi lại biến mất | Vẽ tuyến Goong theo màu ngày, pin số; thu vừa toàn tuyến (không tự bay) | Panel tự mở: tổng tiền, Conflict, từng ngày/Stop, nhãn Bữa sáng/trưa/tối |
| `answer` | Câu trả lời của AI (số liệu do code tính) | — | Không đổi |
| `confirm_replan` | Câu hỏi xác nhận + thẻ "Lập lại" / "Giữ nguyên" | — | Không đổi cho tới khi bấm "Lập lại" |
| `itinerary` sau khi sửa | Câu tóm tắt thay đổi | Vẽ lại tuyến | Stop vừa đổi có viền vàng |
| `error` | Bong bóng đỏ, lời nhắn tiếng Việt; thẻ hỏi lại **vẫn giữ** để sửa/thử lại | — | — |
| "＋ Chuyến mới" | Xoá chat, thẻ hỏi lại, `tripId` | Xoá pin | Xoá lịch trình |
| "Báo đóng cửa" / "Đổi chỗ khác" trên Stop (khoá khi Stop đã ghim) | Lỗi 409/422 hiện bong bóng đỏ | Pin vàng tại Place thay thế | Panel "Phương án thay thế": ≤ 3 thẻ, câu giải thích, Δ chi phí / Δ phút / R; hoặc lý do không có phương án |
| "Áp dụng" | "Đã áp dụng phương án — lịch trình bản N." | Xoá pin vàng, vẽ lại tuyến | Lịch trình bản mới, panel đóng |

### 3.4 Lựa chọn thiết kế có chủ đích
- **Hiện tiến trình thay vì spinner:** AI chạy 10–30 giây, người xem thấy AI "đang tìm gì".
- **Luôn có Itinerary kèm Conflict** thay vì báo lỗi.
- **Hỏi lại tối đa một vòng, luôn bỏ qua được** — không chặn người dùng bằng form.
- **Lỗi mạng không chặn demo:** Goong lỗi thì vẽ đường thẳng; stream đứt thì báo trong chat.
- **Tối giản:** tông stone + emerald, Tailwind; `aria-live` cho chat, `aria-pressed` cho chip, `role="alert"` cho lỗi đăng nhập.

### 3.5 Điểm yếu UX cần xử lý
1. ~~Chưa xem/khôi phục được version cũ~~ — xong 2026-09-30 (dãy v1·v2·v3, bản cũ chỉ xem, "Quay lại bản này").
2. ~~Timeline và map không liên kết~~ — xong 2026-09-30 (#4). Ảnh Place thật chờ dữ liệu có `photo_url` (#19, #41).
3. ~~Không bỏ qua được đoạn camera bay~~ — xong 2026-09-30: không tự bay nữa, "Xem hành trình" dừng được.
4. ~~Không có lịch sử chuyến đi / đăng xuất~~ — xong 2026-09-30 (rail).
5. ~~Bố cục 3 cột cố định~~ — xong 2026-09-30 (#2, #16).
6. **Không thấy tiền đi đâu:** Timeline chỉ có tổng và từng Stop, chưa có bảng chi phí theo nhóm.
