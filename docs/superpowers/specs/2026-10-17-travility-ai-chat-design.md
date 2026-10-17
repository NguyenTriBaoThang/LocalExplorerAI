# Thiết kế: Đưa Travility vào AI Chat của LocalExplorerAI

Ngày: 2026-10-17 · Nguồn tham khảo: `references/TravilityV2/` (snapshot, chỉ đọc)

## 1. Mục đích và lý do

Trang AI Chat (`/chat`) của LocalExplorerAI hiện chỉ đọc ràng buộc rồi xếp lịch **một ngày ở Quận 1** trên 10 trải nghiệm mô phỏng. Người dùng (chủ dự án) muốn AI Chat làm được những gì TravilityV2 đang làm: nói một câu là ra **lịch trình nhiều ngày trên toàn TP.HCM**, xem lịch trên **bản đồ 3D lớn** với nút **"Xem hành trình"** cho camera bay qua từng điểm, lịch được **lưu theo tài khoản**, và **sửa lịch bằng prompt**. Lịch đang chuẩn bị đi luôn hiện ở bảng bên phải, giống Travility.

Cách làm (đã chốt với người dùng): **chuyển bộ lập lịch của Travility thành một phần riêng của LocalExplorerAI**, chạy trên 177 địa điểm thật trong `data/sai_gon_places.json`. Phần đặt trải nghiệm / khung giờ hiện có (Planner, booking, collaboration, replan-advice) **giữ nguyên, không dùng chung dữ liệu**. Không mở rộng bộ xếp lịch cũ thành nhiều ngày, vì như vậy phải bịa trải nghiệm và khung giờ cho 177 điểm.

## 2. Mục tiêu

Mang **toàn bộ** tính năng chat + lịch trình của Travility sang AI Chat (người dùng đã chốt "giữ đủ"):

1. **Lập lịch bằng một câu.** "Đi Sài Gòn 3 ngày, 5 triệu, 2 người, thích cafe và lịch sử" → lịch theo ngày, đủ 3 bữa/ngày, có chỗ ở khi > 1 ngày, vẽ trên bản đồ cùng tuyến đường.
2. **Hỏi lại một vòng** bằng thẻ chip khi thiếu phương tiện hoặc giờ đến/về (có nút "Bỏ qua").
3. **Thấy AI đang làm gì.** Mỗi lượt tìm địa điểm được phát về client ngay (SSE) và hiện thành pin nhấp nháy trên bản đồ.
4. **Xung đột do code tính, không do AI đoán:** vượt ngân sách, đóng cửa, thiếu tag, mưa + điểm ngoài trời, trước giờ đến, sau giờ về, thiếu bữa, không kịp di chuyển. Lịch luôn được trả kèm xung đột thay vì báo lỗi; xung đột được gửi lại AI sửa một lần.
5. **Sửa lịch bằng hội thoại** trên chuyến đã có lịch: AI chọn một trong ba hướng: trả lời câu hỏi (không tạo phiên bản), sửa đúng điểm liên quan (phiên bản mới), hoặc đổi cả chuyến → thẻ xác nhận "Lập lại".
6. **Tự lưu mọi phiên bản** (v1 · v2 · v3…) theo tài khoản; xem bản cũ ở chế độ chỉ đọc + nút "Quay lại bản này" (tạo phiên bản mới). Không có nút "Lưu" riêng (người dùng đã chốt).
7. **Ghim điểm** (📌) muốn giữ; sửa / lập lại / sự cố không được đụng điểm ghim.
8. **Lịch sử chat theo chuyến**; mở AI Chat tự mở chuyến gần nhất; danh sách "Lịch trình của tôi" để mở lại chuyến khác; nút "Chuyến mới".
9. **Xử lý sự cố không cần AI** trên từng điểm: "Báo đóng cửa", "Đổi chỗ khác", "☂ Giả sử mưa" (theo ngày), "Tôi trễ 15/30/60′" → tối đa 3 phương án do code tạo, có giải thích và chênh lệch chi phí/phút/mức giữ mục đích → "Áp dụng" tạo phiên bản mới.
10. **Xuất PDF** phiên bản đang xem (snapshot lịch, chỗ ở, chặng, chi phí, xung đột, số phiên bản, thời điểm xuất).
11. **Góp ý nhóm:** người tổ chức chuyển sang chế độ "Góp ý nhóm", nhập góp ý trên một phiên bản → tạo preview; chỉ người tổ chức "Áp dụng" mới thành phiên bản mới; preview cũ hơn bản mới nhất bị đánh dấu stale. Giống Travility: không có tài khoản thành viên riêng, chính người tổ chức nhập góp ý.
12. **Nút "▶ Xem hành trình"** trên bản đồ: camera bay lần lượt qua từng điểm theo thứ tự ngày → điểm, nghiêng ~60°, xoay bearing +40° mỗi điểm, hiện "Ngày N · điểm i/n · tên"; người dùng kéo bản đồ hoặc bấm dừng thì dừng; hết tour thì thu vừa toàn tuyến. Chọn điểm ở Timeline ↔ bay tới trên bản đồ; bấm pin ↔ Timeline cuộn tới.
13. **Giữ phần phiên trước còn hữu ích:** trả lời thời tiết bằng dự báo Open-Meteo thật (đã làm ở `chat_response_service.py` / `open_meteo_service.py`) và từ chối lịch sự câu hỏi ngoài du lịch. Hai việc này trở thành câu trả lời trong chat, không tạo phiên bản.

## 3. Ngoài phạm vi

- Chạy cụm phân tán của Travility: `llm-gateway`, hàng đợi Redis Streams, worker `planner`, đa agent (`PLANNER_MODE=multi`), shard / bản sao đọc, service `places` riêng, trang "Hệ thống", load test. Lập lịch chạy ngay trong request của API như chế độ một tiến trình của Travility.
- App desktop pywebview, màn đăng nhập riêng của Travility (dùng đăng nhập sẵn có của LocalExplorerAI).
- Điểm đến ngoài TP.HCM.
- Thay đổi bộ xếp lịch trải nghiệm / khung giờ, booking, thanh toán, trang Planner, collaboration hiện có.
- Các việc Travility còn chưa làm (lát D–F, ranker học máy, giọng nói, recap…).

## 4. Điều không được xảy ra (anti-goal)

- AI đưa vào lịch một địa điểm **không có** trong 177 điểm, hoặc chưa được trả về từ công cụ tìm kiếm trong lượt đó (ADR-0001 của Travility: lịch có địa điểm lạ bị từ chối).
- Tiền, quãng đường, giờ, xung đột do LLM tự ghi ra thay vì code tính.
- Câu hỏi thời tiết / ngoài lề làm đổi dữ liệu chuyến hoặc tạo phiên bản mới.
- Người dùng này đọc / sửa được chuyến của người khác (phải trả 404 như Travility).
- Làm hỏng trang Planner, booking hoặc các endpoint `/itineraries/plan|preview|confirm` đang có.
- Nhìn như một app khác dán vào: màu, font, thanh menu phải đồng bộ LocalExplorerAI.

## 5. Ràng buộc đã biết

**Dữ liệu**
- `data/sai_gon_places.json`: 177 điểm, đều `verified: true`, toạ độ trải toàn thành phố (lat 10.72–11.14, lon 106.46–106.80). `kind`: `tham-quan` 52, `an-uong` 46, `cafe` 29, `giai-tri` 25, `cho-o` 25. Trường: `id` (chuỗi slug), `name`, `kind`, `lat`, `lon`, `price_vnd`, `open_hours` (chuỗi JSON `{"open","close","days"}`), `outdoor`, `tags`, `description`, `photo_url`, `source`, `note`, `address`. Định dạng gần như trùng `data/places/*.json` của Travility; bước import phải đọc file này như nguồn duy nhất, upsert theo `id` (tương đương `ext_id`).
- Travility cần **Hub** (sân bay / bến xe / ga) theo Arrival Mode. File trên không có hub → thêm vài hub TP.HCM với toạ độ thật: Sân bay Tân Sơn Nhất, Ga Sài Gòn, Bến xe Miền Đông (mới), Bến xe Miền Tây. *(quyết định của Claude)*
- Database hiện là `postgis/postgis:16-3.4`, **không có pgvector**. Với 177 điểm, lưu embedding trong một cột mảng float / JSON và tính cosine trong Python là đủ. *(quyết định của Claude)*

**Backend LocalExplorerAI**
- FastAPI + SQLAlchemy + Alembic (`apps/api/migrations/versions/`, mới nhất `0019_itinerary_collaboration`). Bảng mới phải đi qua migration Alembic, không dùng `CREATE TABLE IF NOT EXISTS` lúc khởi động như Travility.
- Quyền đi qua RBAC: `require_user(P.<PERMISSION>)` trong `app/api/guards.py`. Cần thêm permission cho các route chuyến đi và gán cho vai trò traveler; route nào public phải khai báo `public(...)` như route khác.
- LLM: đã cấu hình Gemini qua giao thức OpenAI (`gemini_base_url`, `gemini_model`, `llm_provider`) trong `app/core/config.py`. `StructuredOutputProvider` hiện chỉ có `generate(system, input, schema)`, **không có vòng lặp tool-calling**. Agent của Travility (`agent.py`, `followup.py`, `llm.py`) cần tool-calling nhiều lượt → phải thêm một client tool-calling dùng chung cấu hình LLM sẵn có (không thêm biến môi trường LLM mới).
- Prompt có phiên bản: `app/prompts/<version>/` + `manifest.json`, **file của phiên bản đang active là bất biến**. Prompt của Travility (đang viết thẳng trong code) phải đưa vào một thư mục phiên bản prompt mới và cập nhật manifest + `docs/ai-prompt-catalog.md`.
- Embedding: mô hình E5 cục bộ **không có** trong image hiện tại (`models/e5/` chỉ có `.gitkeep`, `INSTALL_E5=false`, không cài `sentence-transformers`). Dùng **Gemini embedding** (giống Travility, `gemini-embedding-001`) qua cấu hình `gemini_*` sẵn có: tính embedding 177 điểm lúc import, lưu vào bảng; embed câu truy vấn mỗi lượt `search_places`. Gemini embedding lỗi → lùi về tìm theo `kind` + tag bắt buộc/tránh + từ khoá trên tên/mô tả bằng code, vẫn chỉ trả điểm trong bảng. *(quyết định của Claude, sửa sau builder check)*
- Khoảng cách: Goong đã cấu hình (`GOONG_API_KEY`, `app/adapters/routing/goong.py`), nhưng adapter mới chỉ có `get_route`, chưa có Distance Matrix → thêm lời gọi Distance Matrix cạnh nó. Travility gọi Goong Distance Matrix một request/ngày và lùi về chim bay × 1.3 khi lỗi → tái dùng adapter / cấu hình Goong sẵn có, giữ hành vi lùi.
- Thời tiết: `open_meteo_service.py` đã có dự báo theo ngày (phiên trước thêm). Lập lịch dùng nó cho khả năng mưa (ngày đi trong 16 ngày tới; lỗi thì bỏ qua).
- Múi giờ `Asia/Ho_Chi_Minh` cho mọi "hôm nay", giờ mở cửa, giờ đến/về.

**Frontend LocalExplorerAI**
- React 18 + Vite + Tailwind 3, `axios` client trong `src/api/client.ts`, i18n `src/i18n.ts`, router `src/router.tsx` (`/chat` → `ChatPage`), layout `AppLayout` có thanh menu trên cùng (~64px).
- Bản đồ 3D: `src/components/3d/Map3DLandmarkViewer.tsx` dùng **`@goongmaps/goong-js`** (fork mapbox-gl) + three.js custom layer để đặt mô hình GLB landmark (calibration lấy từ `/models-3d/calibration`, mặc định trong `landmark/types.ts`). Travility dùng `maplibre-gl` + `react-map-gl`; **không thêm hai thư viện đó**, chuyển logic MapView của Travility sang goong-js đang có (flyTo, pitch, bearing, source/layer GeoJSON cho tuyến, marker).
- Màu / phong cách: nền tối slate (`--bg-deep #080c14`, `--bg-surface #0f172a`, card kính `rgba(15,23,42,.75)`), điểm nhấn `--emerald #10b981`, `--cyan #06b6d4`, `--amber #f59e0b`, `--rose #f43f5e`; font Be Vietnam Pro; bo góc theo `--radius-*`. Thay bảng màu `pine` / `marigold` / `stone` của Travility bằng các token này.
- Không có thư viện test frontend trong `apps/web` (không vitest). Test của client Travility (`*.test.ts`) chỉ là tham khảo.

**Repo**
- Đang ở nhánh `uat`, có 15 file sửa + vài file mới **chưa commit** của phiên "travel chat routing" (spec `2026-10-17-travel-chat-routing-design.md`, plan đã tick đủ 43 bước). Việc này xây tiếp trên nền đó, không revert.
- Không động vào `.DS_Store`, `.playwright-mcp/` chưa track.

## 6. Những phần đã quyết

**Kiến trúc**
- Một module "trip" mới trong `apps/api` là bản port của Travility: tương đương `trips.py`, `agent.py`, `followup.py`, `rules.py`, `domain.py`, `versions.py`, `proposals.py`, `replan.py`, `group_reviews.py`, `forecast.py` (dùng Open-Meteo sẵn có), `distance.py` (dùng Goong sẵn có), `places.py` (tìm kiếm E5 trên bảng mới). Bỏ `gateway.py`, `jobs.py`, `worker.py`, `multi.py`, `system.py`, `nodes.py`, `places_service.py`, `places_client.py`, `kv.py`, `auth.py`, `db.py` (thay bằng session SQLAlchemy và auth của LocalExplorerAI).
- Bảng mới (qua Alembic), theo schema Travility: `trip_places` (177 điểm + embedding) và hub, `trips` (user_id → users của LocalExplorerAI, `spec`, `user_messages`, `pending_replan`, `pinned_place_ids`), `trip_itineraries` (trip_id, version, data JSON, unique (trip_id, version)), `trip_proposals`, `trip_group_reviews`, `trip_messages`. Tên bảng có tiền tố để không trùng `itineraries` / `itinerary_versions` đang có. *(đặt tên: quyết định của Claude)*
- Import 177 điểm được `apps/api/scripts/` thực hiện; hub TP.HCM được thêm vào cùng bước import.
- Hợp đồng HTTP + SSE giữ như Travility (đổi prefix cho hợp với router LocalExplorerAI): `POST /trips` (SSE: `thinking`, `trip`, `tool_call`, `clarify`, `itinerary`, `answer`, `confirm_replan`, `error`), `POST /trips/{id}/plan`, `POST /trips/{id}/replan`, `GET /trips`, `GET /trips/{id}?version=N`, `PATCH /trips/{id}/pins`, `GET /trips/{id}/messages`, `POST /trips/{id}/restore/{version}`, `POST /trips/{id}/disruptions`, `POST /trips/{id}/proposals/{pid}/apply`, `POST /trips/{id}/group-reviews` (SSE), `.../apply`, `.../cancel`.
- Phạm vi điểm đến: chỉ TP.HCM. Yêu cầu nơi khác → AI báo hiện chỉ hỗ trợ TP.HCM (tương đương "Destination chưa hỗ trợ" của Travility).
- **Chỉ tiếng Việt** (người dùng đã chốt): prompt, chữ do code sinh (xung đột, phương án, nhãn bữa, PDF) và UI của trang chat mới giữ tiếng Việt như Travility; khi site đang ở `en`, trang chat vẫn hiện tiếng Việt.
- Lưu yêu cầu đăng nhập. Chưa đăng nhập vào `/chat` → mời đăng nhập (dùng trang auth sẵn có). *(quyết định của Claude)*

**Định tuyến tin nhắn**
- Chuyến **chưa có lịch**: câu hỏi thời tiết / thông tin du lịch / ngoài lề đi qua `route_chat_message` hiện có (trả lời, không tạo chuyến); còn lại vào luồng lập lịch Travility (`parse_trip` → clarify → plan).
- Chuyến **đã có lịch**: đi luồng followup của Travility (`answer` / `edit_itinerary` / `change_trip`). Câu hỏi thời tiết trong followup trả lời bằng dự báo Open-Meteo thật, không để LLM tự nói mưa nắng.
- Luồng "Xem trước → Lưu lịch trình" của phiên trước được **gỡ khỏi trang chat**; các endpoint `/itineraries/preview` và `/itineraries/confirm` vẫn giữ cho caller khác.

**Giao diện `/chat`** (theo bố cục Travility, màu LocalExplorerAI)
- Giữ thanh menu trên cùng của site; phần còn lại là **bản đồ 3D goong-js toàn khung**, có mô hình GLB landmark như trang Map 3D, nghiêng camera.
- **Rail** dọc hẹp bên trái: "Chuyến mới", "Lịch trình của tôi" (popover danh sách chuyến).
- **Bảng nổi trái — Chat:** tiêu đề tên chuyến + ngân sách; tin nhắn; dòng tool ("Tìm cafe…"); thẻ Clarify, thẻ xác nhận lập lại, chế độ Góp ý nhóm + panel preview; badge tin chưa đọc khi thu gọn.
- **Bảng nổi phải — Lịch trình:** dãy phiên bản, tổng chi phí so ngân sách, theo ngày → điểm (giờ, tên, nhãn bữa, chi phí, chip mục đích, lý do chọn, chặng km/phút, xung đột), nút 📌, nút sự cố, "☂ Giả sử mưa" trên header ngày, "Xuất PDF", panel phương án sự cố.
- Hai bảng thu gọn được; màn hẹp (< 1100px) chỉ mở một bảng một lúc (như `layout.ts`).
- Đường đi vẽ theo màu từng ngày; pin đánh số; pin vàng nhấp nháy khi AI đang tìm.

## 7. Để lại cho người làm

- Chia lát (slice) và thứ tự làm; cách cắt để mỗi lát chạy được đầu–cuối.
- Cách bọc SSE trong FastAPI + cách đọc SSE bằng `fetch` ở client (axios không stream) — có thể port `sse.ts` của Travility.
- Cấu trúc thư mục / tên file / tên permission trong LocalExplorerAI.
- Cách lưu embedding (cột ARRAY float, JSON, hay cache trong RAM khi khởi động) và lúc nào tính (lúc import).
- Script import (`apps/api/scripts/…`) và cách chạy trong Docker; có tự import khi khởi động hay không.
- Port test pytest của Travility nào (ưu tiên `rules`, `domain`, `replan`, `versions`, `proposals` vì chạy thuần code), cách giả LLM trong test.
- Chi tiết UI ngoài những gì mục 6 đã nêu, miễn đúng bố cục và token màu.
- Xử lý lỗi LLM / Goong / Open-Meteo theo đúng hành vi lùi của Travility.
- Có thay `ChatPage.tsx` tại chỗ hay tạo trang/component mới rồi trỏ route `/chat` vào.
