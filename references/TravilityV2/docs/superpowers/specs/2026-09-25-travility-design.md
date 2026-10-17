# Travility — Design Spec (2026-09-25, rev 2)

> Spec gốc, giữ làm thiết kế kỹ thuật (Stack, Kiến trúc). Yêu cầu sản phẩm, lộ trình, phân vai, thứ tự cắt: xem [docs/PRD.md](../../PRD.md) — khi mâu thuẫn, PRD thắng.

Thuật ngữ in đậm theo [CONTEXT.md](../../../CONTEXT.md). Quyết định kiến trúc ở [docs/adr/](../../adr/).

## Context
Đồ án nhóm (3–4 người, ~8–10 tuần): app desktop du lịch + bản đồ cho người Việt, dùng AI càng nhiều càng tốt, demo phải "wow" trước giảng viên (demo trực tiếp 10–15 phút trên 1 laptop).

## Sản phẩm
**Lõi — AI Trip Planner:** User gõ/nói "Đi Đà Lạt 3 ngày, 3 triệu, thích cafe chill" → AI dựng **Trip** (Destination, số ngày, ngày đi nếu có, số người, Budget, Preference, Pace, Travel Mode) → gọi tool tìm **Place** thật, tính **Leg**, **Forecast**, chi phí → **Itinerary** theo ngày hiện lên timeline + tuyến đường trên map 3D, camera bay qua từng **Stop**. Mỗi Stop có **Reason**. Trong lúc AI "nghĩ", map hiện live các bước (pin nhấp nháy) — khoảnh khắc wow chính. Itinerary luôn được tạo, kèm danh sách **Conflict** + gợi ý nếu không thỏa hết.

**Vệ tinh (thứ tự ưu tiên):**
1. **Revision** bằng hội thoại — "ngày 2 mưa thì sao?", "bớt 500k" → chỉ Stop liên quan thay đổi, **Pinned Stop** bất khả xâm phạm; map animate Stop đổi; undo về phiên bản Itinerary trước.
2. Giọng nói tiếng Việt — mic → STT → AI; trả lời bằng TTS.
3. **Inspiration Photo** — vision mô tả không khí → embedding → 3–5 **Suggestion** trên map; chấp nhận = một Revision.
4. Cinematic recap + xuất PDF — camera bay toàn tuyến kèm thuyết minh TTS; PDF Itinerary + bảng chi phí (cách chia sẻ Trip duy nhất).

**Tài khoản:** đăng ký/đăng nhập email + mật khẩu, đăng nhập Google, quên mật khẩu, **Traveler Profile** (chép vào Trip mới). Trip riêng tư, không chia sẻ trong app.

**Thứ tự cắt nếu trễ:** xem PRD §13.

## Quy tắc nghiệp vụ (code thực thi, không phải prompt)
- AI chỉ tham chiếu Place trả về từ tool; Place lạ → từ chối, AI làm lại 1 lần (ADR-0001).
- Budget = ăn + vé + Stay + chi phí Leg; không gồm di chuyển liên tỉnh (ADR-0005).
- Một Stay cho cả Trip (bắt buộc khi Trip > 1 ngày), tính theo đêm × số phòng (2 người/phòng), là điểm đầu/cuối mỗi ngày; không phải Stop.
- Chi phí Stop = giá Place × số người; xe máy thuê tính theo ngày × số xe (2 người/xe).
- Travel Mode mỗi Trip: xe máy thuê (mặc định) hoặc Grab; Leg < ~800 m đi bộ. Chi phí Leg theo công thức cố định.
- Pace: thong thả 3–4 Stop (9h–20h) · vừa 5 (8h–21h) · dày 6–7 (7h–22h).
- Conflict phát hiện bằng code: vượt Budget, ngoài giờ mở cửa (theo thứ trong tuần nếu có ngày đi), thiếu Tag bắt buộc, Stop ngoài trời vào ngày dự báo mưa.
- Revision không được sửa/xoá Pinned Stop.
- Trip có ngày đi trong 16 ngày tới mới có Forecast (Open-Meteo).

## Stack
| Lớp | Chọn |
|---|---|
| Client desktop | **pywebview** + React/Vite/Tailwind build tĩnh; đóng gói **PyInstaller** |
| Server | **FastAPI** + **PostgreSQL + pgvector** trong **Docker Compose** (ADR-0002) |
| Auth | Tự làm trong FastAPI: bcrypt + JWT; Google OAuth (loopback redirect cho app desktop); reset mật khẩu qua email |
| LLM | SDK `openai`; env `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL` — dev Gemini, demo OpenAI (ADR-0003) |
| STT/TTS | OpenAI |
| Embedding | Tạo khi import Place, lưu cột `vector` pgvector; một provider embedding cố định |
| Map | **MapLibre GL JS** (`react-map-gl`) + tiles/Directions **Goong** (ADR-0004) |
| Streaming | SSE: `thinking` / `tool_call` / `itinerary` |

## Kiến trúc
```
Client: pywebview ── React UI (đăng nhập | chat | map 3D | timeline)
            │ HTTPS/HTTP + SSE, JWT
Server (docker compose)
  FastAPI ├─ auth        users, JWT, Google OAuth, reset mật khẩu
          ├─ agent       vòng lặp tool-calling → Itinerary JSON (pydantic)
          ├─ tools       search_places(destination, query, tags) · get_legs · get_forecast
          ├─ rules       tính chi phí, phát hiện Conflict, kiểm tra Pinned Stop
          ├─ voice       STT / TTS
          ├─ vision      ảnh → mô tả → embedding → Suggestion
          └─ demo_cache  record/replay theo hash(request)
  PostgreSQL+pgvector    users, traveler_profiles, places, trips, itineraries (phiên bản, bất biến)
data/places/<destination>.json   dữ liệu Place commit git (nguồn gốc duy nhất)
scripts/import_places.py         seed → Postgres + embedding (chạy lại được, idempotent)
```
Place: tọa độ, loại (có loại chỗ ở), Tag, giá, giờ mở theo thứ, trong nhà/ngoài trời, ảnh, mô tả. Không có màn hình Admin; sửa Place = sửa file seed + PR + chạy lại import.

**Itinerary:** `stay_place_id` + `days[] → {date, rain_chance, legs[], stops[] {place_id, start_time, duration_min, est_cost, reason, pinned}}` + `total_cost` + `conflicts[]`. Mỗi Revision lưu một phiên bản mới; client diff hai phiên bản để animate.

## Destination
Đà Lạt, Đà Nẵng – Hội An, Hà Nội (stretch: thêm 2). Mỗi Destination ~150–300 Place.

## Rủi ro & xử lý
- Gemini ≠ OpenAI về tool-calling → golden set ~15 prompt chạy trên cả 2; 2 tuần cuối chỉ dùng OpenAI.
- Server phải chạy khi demo → `docker compose up` trên laptop demo; checklist khởi động trong kịch bản demo.
- Mạng yếu → demo_cache replay; ảnh Place lưu local trên server.
- Tài khoản đầy đủ làm tiến độ sát → theo thứ tự cắt ở trên.
- Secrets (`.env`: LLM key, Goong key, Google OAuth, SMTP, JWT secret) không commit.

## Phân công & Mốc
Xem PRD §12 (4 vai A–D, lộ trình 10 tuần cập nhật).

## Verification
- `pytest` cho rules: tổng chi phí khớp, Conflict đúng (vượt Budget, giờ đóng cửa, mưa + ngoài trời), Revision không đụng Pinned Stop, Place lạ bị từ chối.
- `pytest` cho search_places trên Postgres test (docker): đúng Destination, Tag bắt buộc được tôn trọng.
- `pytest` auth: đăng ký/đăng nhập, User không đọc được Trip của User khác.
- Golden set script: 15 prompt × 2 provider, báo % Itinerary hợp lệ.
- Diễn tập demo end-to-end trên laptop demo, có một lần tắt mạng (replay).
