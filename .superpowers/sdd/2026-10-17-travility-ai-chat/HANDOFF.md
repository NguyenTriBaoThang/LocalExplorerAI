# Handoff — Travility AI Chat

Ngày chốt handoff: 2026-10-17 (+07:00)  
Nhánh bàn giao: **feat/travility-ai-chat-handoff**  
PR Draft: [#80](https://github.com/NguyenTriBaoThang/LocalExplorerAI/pull/80)  
Commit nền khi bàn giao: **c6e8fcd** — fix(trip): a new group review supersedes the pending one  
Plan: [docs/superpowers/plans/2026-10-17-travility-ai-chat.md](../../../docs/superpowers/plans/2026-10-17-travility-ai-chat.md)  
Spec: [docs/superpowers/specs/2026-10-17-travility-ai-chat-design.md](../../../docs/superpowers/specs/2026-10-17-travility-ai-chat-design.md)

## Mục tiêu

Port bộ lập lịch TravilityV2 vào AI Chat của LocalExplorerAI. Bộ lập lịch là trải nghiệm riêng trong /chat, chỉ chạy với 177 địa điểm TP. Hồ Chí Minh từ data/sai_gon_places.json; dữ liệu, API và giao diện phải bám các quyết định trong spec. Các file trong references/TravilityV2/ chỉ là nguồn đọc, không sửa.

## Trạng thái ở commit bàn giao

- **Task 1–8: hoàn tất và đã review trong SDD.** Bao gồm schema/domain/permission, nạp và tìm địa điểm, luật lập lịch, parser/agent, API SSE và lưu phiên bản, sửa lịch bằng chat, ghim/khôi phục/lịch sử/đề xuất sự cố, góp ý nhóm.
- **Task 9: đang dở.** Brief ở task-9-brief.md; test ownership đã được viết tại apps/api/tests/trip/test_ownership.py nhưng chưa được chạy/review và chưa có report. File test này sẽ được đưa vào PR để giữ lại phần đang làm; teammate cần chạy nó, sửa lỗ hổng route nếu có, rồi cập nhật report/commit Task 9. Kiểm tra không có implementer/worktree nào đang tiếp tục cùng task trước khi sửa tiếp.
- **Task 10–14: chưa làm.** Đây là phần API client + UI + smoke/review cuối; xem chi tiết bên dưới.
- Handoff này không chạy lại test. Số liệu kiểm chứng là từ report SDD của implementer, không phải kiểm chứng mới ở bước đóng gói.

## Phần đã có

### API và dữ liệu

1. Migration 0020_trip_planner, ORM cho Trip, Place, Itinerary, Message, Proposal, GroupReview; permission trip:use cấp cho traveler; domain và luật kiểm tra.
2. Import 177 địa điểm, Gemini embeddings và tìm kiếm embedding/keyword; khi embedding lỗi, tìm kiếm rơi về keyword. Lệnh import là apps/api/scripts/import_trip_places.py.
3. Logic chi phí, giờ mở cửa/xung đột, khoảng cách Goong và xác suất mưa; tiền/km/phút/xung đột do code tính, không giao cho LLM.
4. Prompt catalog phiên bản 3.2.0 và trip agent/parser/planner. Các route trip yêu cầu P.TRIP_USE; trip của tài khoản khác phải trả 404.
5. Luồng chat/SSE tạo lịch, trả lời câu hỏi du lịch/thời tiết, lưu phiên bản theo chuyến và lưu lịch sử. LLM lỗi trả SSE error, không lưu phiên bản dở.
6. Follow-up sửa lịch, xác nhận/từ chối replan; API ghim điểm, xem lịch sử, khôi phục phiên bản và đề xuất thay điểm khi có sự cố.
7. Group review tạo preview, organizer áp dụng/huỷ. Khi tạo preview mới, review pending cũ bị huỷ trong cùng transaction; đây là ruling đã chốt và test ở Task 8.

### Quyết định cần giữ khi tiếp tục

- Chỉ tiếng Việt trong mọi nội dung trip chat, kể cả khi giao diện chung ở en.
- Chỉ TP.HCM; embedding dùng Gemini. Không đưa Redis, worker, gateway, multi/node/system hay Places service của bản Travility vào sản phẩm.
- LLM chỉ chọn Place đã có từ truy vấn trong lượt đó hoặc có trong lịch cũ/đang sửa. Giữ InvalidDraft và cơ chế làm lại một lần.
- Khi có group review mới, huỷ toàn bộ review pending cũ của chuyến rồi lưu preview mới. Không khôi phục lỗi review_pending.
- Không sửa references/TravilityV2/.

## Tiếp tục theo thứ tự plan

### Task 9 — quyền sở hữu mọi route (đang dở; test chưa chạy)

Brief: task-9-brief.md. Viết apps/api/tests/trip/test_ownership.py để user B không đọc/sửa trip, version, proposal hoặc group review của user A trên tất cả endpoint được liệt kê trong brief; mọi truy cập trip không sở hữu phải là 404, GET /api/trips của B rỗng. Kiểm tra thêm role provider bị 403 ở GET /api/trips. Nếu test lộ route hở thì sửa apps/api/app/api/routes/trips.py. Chạy bộ tests API theo plan rồi commit với message: test(trip): lock trip ownership across every route.

### Task 10 — client API, SSE và helper thuần

Port API/helper từ snapshot Travility sang apps/web/src/: api/trips.ts, components/trip/sse.ts, place.ts, layout.ts, tripPrint.ts; các helper thuần dùng node:test, không thêm Vitest. Chuyển các test phù hợp, rút clarifyAfter, confirmAfter, mealOf, viewingOld ra tripState.ts; client dùng cookie/session hiện có, không port token/login riêng của Travility. Chạy npm test và npm run build trong apps/web.

### Task 11 — bản đồ TripMap

Port MapView sang components/trip/TripMap.tsx và thêm landmarkLayer.ts; dùng Goong/map adapter, route lines theo màu ngày, pin và mô hình landmark. Nút “Xem hành trình” điều khiển tour camera. Không thêm maplibre-gl hay react-map-gl. Chạy web build.

### Task 12 — panel và thẻ

Port rail, chat, timeline, clarify/confirm, popup địa điểm, proposal, group review, print view từ Travility; đổi màu theo design token LocalExplorerAI, giữ font Be Vietnam Pro. Tạo/cập nhật component trong apps/web/src/components/trip/. Chạy web build.

### Task 13 — thay trang /chat và smoke UI

Tạo TripChatPage.tsx, chuyển route /chat sang trang mới, xử lý import tham chiếu cũ. Chạy npm run build và npm test; rebuild api/web bằng Docker Compose và smoke trên http://localhost:5173/chat theo checklist ở plan: lập lịch hai ngày, clarify, sửa thành v2, xem lại v1 và tạo v3, xử lý sự cố, mưa/trễ, group review, PDF, hỏi thời tiết không tạo version, reload vẫn khôi phục chuyến/chat. Ghi lỗi quota Gemini nguyên văn nếu gặp. Ảnh smoke để ngoài repo.

### Task 14 — rà soát cuối

Chạy full API tests và web tests/build theo plan; thêm hướng dẫn import địa điểm vào README.md. Rà diff từ spec/plan bằng /code-review, sửa findings nghiêm trọng, commit tài liệu import. Trước đó cần xử lý migration/base divergence bên dưới để kết quả phản ánh target main thực tế.

## Kiểm chứng đã ghi trong SDD

- Task 1: Alembic round-trip được controller xác nhận trên dev DB tới 0020_trip_planner; các bảng trip tồn tại.
- Task 2: import thực tế 177 địa điểm và 177/177 embeddings sau lần retry Gemini quota; full API suite tại thời điểm đó: 356 passed.
- Task 3–7: reports ghi lần lượt 406, 444, 478, 497, 550 test pass (một số có 1 skip và warning Starlette/httpx có từ trước).
- Task 8 sau fix supersede: tests/trip 243 passed; full API suite 574 passed, 1 skipped, 1 warning có sẵn. SQLite bỏ qua FOR UPDATE; Postgres lock-race chưa được kiểm tra.
- Xem từng task-N-report.md và progress.md để biết test bị loại, deviation và deferred concerns. Không xem các con số trên là kết quả chạy lại trên main mới nhất.

## Cảnh báo tích hợp vào main

Đây là điểm cần người nhận PR xử lý trước khi merge:

- origin/main tại lúc handoff là c7de7a1, trong khi nhánh làm việc có chung tổ tiên với main tại 1cf0914. Nhánh hiện tại có 14 commit sau origin/uat (1ee0088), nhưng lịch sử nhánh còn có các commit nền itinerary/collaboration trước đó. Vì vậy PR base main chứa nhiều hơn riêng các commit Travility trong plan; hãy xem danh sách commit và files changed trên PR.
- Migration của main hiện có 0019_landmark_stories.py và 0020_meshy_jobs.py; nhánh này có 0019_itinerary_collaboration.py → 0020_trip_planner.py. Cần hợp nhất/re-number migration graph theo trạng thái main, kiểm tra cả downgrade/upgrade và dữ liệu, không để hai migration có cùng revision ID hoặc hai Alembic heads ngoài ý muốn.
- Main đã tiến thêm nhiều thay đổi sau điểm chung; rà xung đột/ghi đè ở main.py, API dependencies/permissions, chat/planner, models/prompts, web router/styles và Docker trước khi chuyển PR sang Ready. PR hiện để Draft để teammate hoàn thiện tích hợp và Task 9–14.

## File điều phối SDD

- progress.md: trạng thái và rulings của từng task.
- task-9-brief.md: brief đang được dispatch.
- task-1..8-report.md: kết quả, test, decisions và concerns của phần đã làm.
- review-*.diff, reviewer-rules.md, implementer-rules.md: bằng chứng/restrictions của các vòng review.
- docs/superpowers/specs/2026-10-17-travility-ai-chat-design.md: quyết định sản phẩm/thiết kế.
- docs/superpowers/plans/2026-10-17-travility-ai-chat.md: các bước thực thi đầy đủ.

## Workspace khi đóng gói

Đã có các file không thuộc tính năng chưa track (.DS_Store, .playwright-mcp/). Không đưa chúng vào commit/PR. Trước khi thêm commit mới, kiểm tra git status --short để giữ riêng các artefact cục bộ của teammate.
