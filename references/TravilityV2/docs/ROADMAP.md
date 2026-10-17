# Travility — Roadmap

Cập nhật: **2026-10-02** (Goong Matrix #7, #39; thêm lát scale hệ phân tán + mô hình mưa; xong scale T2 #48, T3 #49, T4 #50, T5 #51, T6 #52 — kiến trúc đóng băng); kế hoạch gốc chốt 2026-09-30 sau buổi chốt kế hoạch T2→T10 (Thành + AI gánh đường găng; việc của thành viên khác là việc thêm, cắt được).
Nguồn: [PRD](PRD.md) (§5 yêu cầu, §12 lộ trình, §13 thứ tự cắt), [hiện trạng code](2026-09-25-hien-trang-app.md), GitHub Issues #2–#53.
Bảng theo dõi trên GitHub (tự tick khi đóng issue): **issue #42** (đã ghim).

Ký hiệu: `[x]` đã xong · `[ ]` chưa làm · 🟡 làm dở (ghi rõ còn thiếu gì) · ~~gạch~~ đã cắt.
Tiến độ: đang ở **tuần lịch thứ 2** (bắt đầu 2026-09-25, 10 tuần); việc trên đường găng đã xong tới hết lát **T6** của lộ trình (hạ tầng đóng băng), tiếp theo là **T7**.

## Tổng quan

| Nhóm chức năng | Xong | Tổng |
|---|---|---|
| 1. Nền tảng & tài khoản | 5 | 5 |
| 2. Lập Trip & Itinerary (lõi) | 14 | 14 |
| 3. Revision, Pinned, version | 5 | 6 |
| 4. Revision giữ mục đích (§5.11) | 3 | 7 |
| 5. Cá nhân hoá Trip | 1 | 3 |
| 6. Stay, đường đi, chi phí | 7 | 9 |
| 7. UI/UX mới | 6 | 6 |
| 8. Dữ liệu Place | 1 | 5 |
| 9. Giọng nói, recap, PDF | 0 | 4 |
| 10. Chất lượng & demo | 1 | 4 |
| 11. Hệ phân tán & AI mở rộng | 5 | 6 |

---

## 1. Nền tảng & tài khoản
- [x] Server FastAPI + Postgres/pgvector trong Docker, client React + MapLibre (Goong), app desktop pywebview
- [x] Đăng ký / đăng nhập email + mật khẩu (bcrypt, JWT 7 ngày)
- [x] Mỗi User chỉ thấy Trip của mình (Trip người khác → 404)
- [x] LLM đổi được provider: Gemini khi dev, OpenAI khi demo (ADR-0003)
- [x] Đăng xuất (nút ⎋ trên rail)
- ~~Đăng nhập Google — #12~~ (cắt 2026-09-30)
- ~~Quên mật khẩu qua email — #13~~ (cắt 2026-09-30)

## 2. Lập Trip & Itinerary (lõi)
- [x] Hiểu câu tự nhiên → Trip (Destination, số ngày, ngày đi, số người, Budget, Tag, Pace, Travel Mode)
- [x] Destination chưa hỗ trợ → báo danh sách đang có
- [x] AI tìm Place bằng pgvector (đúng Destination, đủ Tag bắt buộc, loại Tag tránh)
- [x] AI chỉ dùng Place có trong database; Place lạ → bắt làm lại (ADR-0001)
- [x] Stream tiến trình qua SSE (`thinking`, `trip`, `tool_call`, `clarify`, `itinerary`, `error`)
- [x] Thiếu phương tiện / giờ đến–về → hỏi lại một vòng bằng chip
- [x] Luôn trả Itinerary kèm Conflict thay vì báo lỗi; Conflict gửi lại AI sửa 1 lần
- [x] Conflict: vượt Budget, đóng cửa, thiếu Tag, mưa + ngoài trời, trước giờ đến, sau giờ về, thiếu bữa, không kịp di chuyển (#7)
- [x] Bắt buộc đủ 3 bữa/ngày, nhãn Bữa sáng/trưa/tối trên Timeline
- [x] Mỗi Stop có lý do chọn
- [x] Forecast Open-Meteo (ngày đi trong 16 ngày tới)
- [x] Lưu Trip + mọi version Itinerary trong DB
- [x] Mở lại Trip: mở app tự mở Trip gần nhất + danh sách "Chuyến đi của tôi" trên rail (#3)
- [x] Chặn AI xếp Place loại chỗ ở làm Stop (Draft bị từ chối, AI làm lại 1 lần) — #39

## 3. Revision, Pinned Stop, phiên bản (§5.4 — **không được cắt**)
- [x] Chat gắn với Trip đang mở + nút "Chuyến mới" (bản tạm: mỗi tin nhắn **lập lại cả lịch trình** thành version mới)
- [x] Revision thật: chỉ đổi Stop liên quan đến yêu cầu (followup: answer / edit_itinerary / confirm_replan) — #22
- [x] Pinned Stop: nút 📌 trên Stop (`PATCH /trips/{id}/pins`, lưu trên Trip, không tạo version); lập lại thiếu Place ghim → AI làm lại — #25
- [x] Dãy version `v1 · v2 · v3` trên Timeline, bản cũ chỉ xem + "Quay lại bản này" (`POST /trips/{id}/restore/{version}`) — #24
- [x] Lịch sử chat theo Trip (bảng `messages`, `GET /trips/{id}/messages`) — #17
- [ ] Tô sáng / animate Stop đã đổi sau Revision — (Nhật)

## 4. Revision giữ mục đích (§5.11, ý tưởng Local Explorer AI)
Spec: [revision-giu-muc-dich](superpowers/specs/2026-09-29-revision-giu-muc-dich-design.md) · [ADR-0006](adr/0006-thay-the-theo-muc-dich-bang-code.md)
- [x] **Lát A** — #31 — Intent + mức giữ mục đích R: chip ✓/✗ và "Giữ mục đích N%" trên Timeline
- [x] **Lát B** — #31 — "Báo đóng cửa" / "Đổi chỗ khác" trên Stop → tối đa 3 Proposal (code, không LLM) + giải thích + Δ chi phí / Δ phút / R → "Áp dụng" tạo version mới; bảng `proposals` kiêm log feedback
- [x] **Lát C** — #32 — "☂ Giả sử mưa" (một ngày) + "Tôi trễ 15/30/60′": thay Stop ngoài trời / đóng cửa, bỏ Stop không thay được hoặc quá giờ, Stop ghim giữ nguyên ([§13 spec](superpowers/specs/2026-09-29-revision-giu-muc-dich-design.md))
- [ ] **Lát D** — #33 — Bản đồ theo thời điểm: TimeSlider, Place tô màu mở + đến kịp / xa / đóng, thêm Place vào lúc HH:MM (Tùng, T6) · *cắt thứ 5*
- [ ] **Lát E1** — #34 — ~40 kịch bản cố định, bảng so sánh B0 / B1 / B2 (`uv run python -m eval.run`) (Quân, T5–T6)
- [ ] **Lát E2** — #35 — Rubric, gán nhãn 0–3, XGBRanker, chỉ bật khi thắng hàm điểm tay (NDCG@5) (Quân, T7–T8) · *cắt thứ 3*
- [ ] **Lát F** — #36 — Chat → Disruption ("ngày 2 mưa thì sao") (Thành, T9)

Việc nhỏ còn nợ của lát A+B — #37:
- [ ] Áp dụng bị 409 → đóng panel và tải lại bản mới nhất
- [ ] Spec Trip đổi số ngày sau khi lưu version → báo sự cố trả 500 (chỉ gặp khi gọi API thẳng)
- [ ] Ghi luật "kịp giờ" (nới hơn spec §4.3) và mã `INTENT_LOST` vào spec
- [ ] Thêm test: Stop kế tiếp quá xa, Stay/Hub nhiều ngày, `NEW_CONFLICT`
- [ ] Pin màu riêng cho Place thay thế (hiện dùng pin vàng)

## 5. Cá nhân hoá Trip
Spec: [ca-nhan-hoa-trip](superpowers/specs/2026-09-29-ca-nhan-hoa-trip-design.md)
- [x] **Lát 1** — hỏi lại một vòng, giờ đến/về, Hub (sân bay/bến xe), xe máy/ô tô riêng
- ~~**Lát 2** — Chỗ ở đã đặt + điểm bắt buộc ghé — #38~~ (cắt 2026-09-30)
- ~~**Lát 3** — Traveler Profile + onboarding — #18, #23~~ (cắt 2026-09-30)

## 6. Stay, đường đi, chi phí
- [x] Một Stay cho cả Trip, là điểm đầu/cuối mỗi ngày
- [x] Tiền Stay theo đêm × số phòng
- [x] Leg giữa các điểm; Leg ngắn thì đi bộ
- [x] Chi phí xe máy thuê / Grab / xe riêng / ô tô riêng
- [x] Budget = ăn + vé + Stay + Leg (không gồm liên tỉnh, ADR-0005)
- [x] Leg Hub → thành phố ngày đầu/cuối
- [ ] Tag loại chỗ ở (khách sạn, homestay, hostel, resort) + đổi Stay qua Revision — #26 (Thành)
- [x] Km + phút thật bằng Goong Distance Matrix ở server (`app/distance.py`, lỗi / không có key → chim bay × 1.3) + Conflict "không kịp di chuyển" — #7
- [ ] Bảng chi phí theo nhóm trên Timeline (ăn / vé / Stay / di chuyển) — #40 (Nhật)

## 7. UI/UX mới (§7)
- [x] Mockup UI mới: map toàn màn hình, panel nổi, tông rừng thông / dã quỳ, logo — #2 ([mockup](https://claude.ai/artifact/FqsEi2pjdHPdM2qoYD83ih))
- [x] Layout theo mockup: map toàn màn hình, Chat + Timeline là panel nổi thu gọn được, cửa sổ hẹp chỉ mở một panel — #16
- [x] Rail (＋ Chuyến mới, 🗂 danh sách Trip dạng popover, ⎋ Đăng xuất) + mở lại Trip gần nhất — #3
- [x] Map ↔ Timeline hai chiều, popup Place (ảnh giữ chỗ theo loại, giá, giờ mở, trong nhà/ngoài trời, nút Ghim) — #4
- [x] Nút "Xem hành trình" (camera bay qua Stop, bấm Dừng hoặc kéo map là dừng); có lịch trình chỉ thu vừa tuyến, không tự bay — #4
- [x] Empty state: câu chào + 3 gợi ý bấm được (ảnh thật chờ mốc dữ liệu)

## 8. Dữ liệu Place
- [x] Import JSON → DB + embedding (`scripts/import_places`)
- 🟡 Đà Lạt: **37 / 150** Place, 27 chưa kiểm chứng — #19 (Quân, **mốc cứng 15/10**; trễ thì Thành tự chạy #5, kiểm chứng tay ~40 Place lên demo) · *không được cắt*
- [ ] Script thu thập bán tự động (OSM/Goong → AI nháp → JSON) — #5 (Quân)
- ~~Đà Nẵng – Hội An ≥ 150 Place — #20~~ (cắt 2026-09-30)
- [ ] Ảnh Place lưu local phía server — #41 (Quân)
- ~~Hà Nội / Destination thứ 3 — #21~~ (cắt 2026-09-29)

## 9. Giọng nói, recap, PDF
- [ ] Nhập bằng giọng nói: mic → STT → chat — #8 (Nhật, T5)
- [ ] TTS đọc tóm tắt + nút tắt tiếng — #9 (Nhật, T5)
- [ ] Xuất PDF Itinerary + bảng chi phí — #11 (Tùng, T8)
- [ ] Cinematic recap có thuyết minh — #28 (Nhật, T8) · *cắt thứ 2*
- ~~Inspiration Photo → Suggestion trên map — #10, #27~~ (cắt 2026-09-29, nhường chỗ §5.11)

## 10. Chất lượng & demo
- [x] Test tự động: server 362, client 40; đã chạy E2E với Gemini thật
- [ ] Golden set 15 prompt × 2 provider, mục tiêu ≥ 90% Itinerary hợp lệ — #6 (Thành)
- [ ] Đóng gói PyInstaller Mac .app + Windows .exe qua GitHub Actions; app tự bật server (`/health` → `docker compose up -d`) — #15 (Thành, T10)
- [ ] Kịch bản demo + diễn tập (có một lần tắt mạng) — #29 (Thành, T10)

## 11. Hệ phân tán & AI mở rộng (mới 2026-10-01)
Spec: [scale-he-phan-tan](superpowers/specs/2026-10-01-scale-he-phan-tan-design.md) · [ADR-0007](adr/0007-cum-phan-tan-tren-docker-compose.md) · [ADR-0008](adr/0008-cap-theo-loai-du-lieu.md). Tất cả do Thành làm; chế độ `docker compose up` hiện tại vẫn chạy và là mặc định khi dev.
- [x] **T2** — #48 — Redis + `llm-gateway`: cache LLM/embedding, chế độ `replay` cho demo mất mạng (gộp demo_cache #14), giới hạn theo provider, chuyển Gemini ↔ OpenAI; cache Goong + dự báo mưa sang Redis; `DEMO_TODAY` đóng băng ngày cho bản ghi ([runbook](runbook-cum.md)) · *caching, rate limit*
- [x] **T3** — #49 — Queue Redis Streams + worker `planner` (mỗi việc một transaction, nhịp tim, nhận lại việc sau 20 giây), SSE qua Redis, `nginx` + 2 bản `api`, rate limit theo User `PLAN_RPM`, `GET /jobs/{id}/events` ([runbook](runbook-cum.md)). Cụm 8 container dùng khoảng 570 MB RAM · *message queue, load balancing*
- [x] **T4** — #50 — Lập lịch đa agent sau cờ `PLANNER_MODE`: 3 chuyên gia song song (thread, hoặc `planner-agent` × 3 qua stream `agent_jobs`) + agent tổng hợp; agent lỗi hoặc quá 45 giây thì về agent đơn; nhãn agent trong Chat. Golden set 8 prompt: cả hai chế độ 100% hợp lệ, `multi` tốn 15 lượt LLM so với 6, chậm hơn khoảng 4,5 giây (trung vị) và nhiều Conflict hơn → giữ `single` làm mặc định ([runbook](runbook-cum.md)). Cụm 11 container dùng khoảng 850 MB RAM · *AI, distributed*
- [x] **T5** — #51 — Service `places` (tìm vector, Place tương tự, km Goong) đọc bản sao `pg-catalog-replica`, bản sao chết thì đọc node chính; Trip chia 2 shard theo `user_id % 2`, shard chết chỉ User của shard đó nhận 503; `places` chết thì Trip cũ vẫn mở được; `seed_users` ([runbook](runbook-cum.md)). Cụm 15 container dùng khoảng 1.065 MB RAM · *microservice, replication, sharding*
- [x] **T6** — #52 — Trang "Hệ thống" (🖥 trên rail, `GET /system/status`: node một bản được dò, `api` / `planner` báo nhịp tim qua Redis); `pg-catalog` chính chết thì đăng nhập đọc bản sao, đăng ký 503, cụm vẫn khởi động; client nối lại luồng lập lịch bằng `job_id` khi một bản `api` chết; `scripts.loadtest` và `scripts/smoke_cluster.sh` ([runbook](runbook-cum.md) có bảng trình diễn và số đo: lập lịch 8,5–11,6 giây khi cache tắt, khoảng 0,5 giây khi trúng cache; 2 bản `api` không nhanh hơn 1 bản trên một laptop). **Kiến trúc đóng băng từ 2026-10-02** · *CAP, bằng chứng*
- [ ] **T7** — #53 — Mô hình dự đoán mưa cho Trip xa hơn 16 ngày, kèm giải thích · *AI tự train*

---

## Lộ trình theo tuần (chốt 2026-09-30, chỉnh 2026-10-01)

Máy demo: Mac của Thành. Windows: build .exe qua CI + smoke test một lần.

| Tuần | Nội dung | Trạng thái |
|---|---|---|
| T1 | Nền tảng + AI Trip Planner lõi; cá nhân hoá lát 1; Revision giữ mục đích lát A+B | ✅ |
| T2–T3 (→15/10) | Revision đầy đủ: mở lại Trip + lịch sử chat (#17, #3) → Pinned (#25) → version + quay lại (#24) | ✅ |
| T2 | **Scale:** Redis + `llm-gateway` (#48, gộp #14) | ✅ |
| T3 | **Scale:** queue + `planner` + `nginx` + rate limit (#49) ✅; kiểm mốc dữ liệu 15/10 | ⏳ |
| T4 | UI mới (#2, #16, #4) ✅; #39 ✅ · **Scale:** đa agent (#50) ✅ | ✅ |
| T5–T6 | Lát C mưa + trễ (#32) ✅; Goong Matrix (#7) ✅ · **Scale:** `places` + bản sao + shard (#51) ✅, trang Hệ thống + load test + đóng băng (#52) ✅ · Quân E1 (#34) · Tùng lát D (#33) | ⏳ |
| T7 | Mô hình dự đoán mưa (#53) · Nhật giọng nói (#8, #9), bảng chi phí (#40) | ⏳ |
| T8 | Nợ kỹ thuật (#37) + Tag chỗ ở + đổi Stay (#26, cắt đầu tiên nếu trễ); PDF (#11); recap (#28); ranker (#35) | ⏳ |
| T9 | Chuyển OpenAI, golden set (#6), lát F (#36) | ⏳ |
| T10 | PyInstaller + CI (#15), diễn tập có tắt mạng và tắt node (#29) | ⏳ |

Đã cắt 2026-09-30: #12, #13, #18, #23, #38, #20.

## Việc cần làm ngay
1. ✅ Revision đầy đủ (#17, #25, #24), ✅ UI mới (#2, #16, #4), ✅ lát C mưa + trễ (#32) xong 2026-09-30; ✅ #39, ✅ Goong Matrix (#7) xong 2026-10-01. ✅ scale T2 (#48, gộp #14), T3 (#49) và T4 (#50) xong 2026-10-01. ✅ T5 (#51) xong 2026-10-01. ✅ T6 (#52) xong 2026-10-02 ([plan](superpowers/plans/2026-10-02-scale-t6-he-thong.md)); kiến trúc đóng băng. Tiếp: mô hình mưa T7 (#53) — lên plan khi bắt đầu; #37 và #26 dời sang T8.
2. #19 — Quân đưa Đà Lạt lên 150 Place trước 15/10 (kèm `photo_url` để popup có ảnh thật).
3. Nhật: bảng chi phí (#40), giọng nói (#8/#9) — cắm vào panel Timeline / ô chat hiện có.
