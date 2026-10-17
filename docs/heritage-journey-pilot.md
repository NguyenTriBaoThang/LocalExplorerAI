# Pilot hành trình di sản: Chat → Map 3D → Khám phá → Planner

Kiểm tra trên bản làm việc local ngày 14/10/2026. Các số liệu dưới đây là ảnh chụp trạng thái dữ liệu tại thời điểm kiểm tra, không phải cam kết dữ liệu luôn sẵn có.

## Phạm vi và trạng thái

- Pilot: vùng Quận 1 theo bộ lọc địa lý hiện có của dự án.
- Hội An, Vũng Tàu và địa danh ngoài vùng pilot chỉ dùng để xem mô hình. Không tự suy ra trải nghiệm, lịch mở cửa hoặc tuyến tham quan tại đó.
- Database local có 187 POI, 187 trải nghiệm, 1.296 khung giờ và **0 bản ghi Evidence**. Có 124 trải nghiệm trong vùng pilot; 7 trải nghiệm demo có khung giờ tương lai tại thời điểm kiểm kê.
- Vì chưa có nguồn đã được duyệt theo hợp đồng dữ liệu, luồng mặc định chỉ dùng dữ liệu xác minh sẽ hiện danh sách trống kèm lý do. Không tự chuyển sang demo.
- Người dùng có thể bật **Thử demo** để kiểm tra luồng với dữ liệu và tuyến mô phỏng. Demo không xác nhận giá, chỗ còn lại hoặc chỉ đường thực tế. `REAL_DATA_ONLY=true` chặn chế độ này ở backend.

## Những điểm đứt luồng đã xử lý

1. Hai khung chat ở `/chat` và `/map-3d` dùng chung hội thoại và điều kiện đã trích xuất. Khi sửa ngân sách ở lượt tiếp theo, bộ phân tích dự phòng giữ các thông tin trước đó. Số tiền dạng `1.200.000 đồng` được đọc đúng; không tự coi ngân sách mỗi người là ngân sách nhóm.
2. `JourneyProvider` giữ ngày, giờ, số người, tổng ngân sách, phương tiện, sở thích, điểm đi/về và tối đa 6 trải nghiệm đã chọn. Lựa chọn lưu trong sessionStorage theo tài khoản; nội dung hội thoại chỉ giữ trong bộ nhớ tab. Khi đổi tài khoản, context được tạo lại.
3. Map 3D đối chiếu mô hình với POI theo ID hoặc tên chuẩn hóa trùng khớp, đồng thời cách nhau không quá 250 m. Trường hợp nhiều ứng viên hoặc chưa khớp được sẽ hiện chưa liên kết. Không tự chọn công trình gần nhất.
4. Địa danh đã liên kết dẫn đến Khám phá qua `poi_id`. Nút chọn trải nghiệm thêm đúng ID catalog vào hành trình.
5. Khám phá sử dụng phạm vi pilot và thực sự truyền ngày, giờ bắt đầu/kết thúc, số người, tổng ngân sách, POI và bộ lọc xuống API. Trải nghiệm không còn khung giờ phù hợp bị loại. Giá theo người được nhân số người khi kiểm tra ngân sách nhóm.
6. Planner nhận các trải nghiệm đã chọn qua `pinned_experience_ids`, tái sử dụng thuật toán ràng buộc hiện có, kiểm tra cả chặng về. Màn hình kết quả hiển thị tuyến, chi phí, nguồn và mã lý do của bộ lập lịch.
7. Chế độ routing demo được lưu vào lịch trình để tải lại vẫn dùng đúng tuyến mô phỏng. Không âm thầm đổi sang nhà cung cấp thật sau khi tải lại.
8. Khi GLB lỗi, mô hình thay thế Nhà thờ Đức Bà chỉ được dùng cho chính Nhà thờ Đức Bà và có nhãn xấp xỉ; các địa danh khác không còn bị thay bằng nhà thờ.

## Hợp đồng API được bổ sung

- `GET /api/journey/pilot`: số liệu sẵn sàng, số trải nghiệm có nguồn/khung giờ, khả năng dùng demo.
- `GET /api/journey/landmarks/{model_id}?demo=false`: liên kết POI, phạm vi pilot, tọa độ, nguồn có thời điểm kiểm tra và trải nghiệm hợp lệ.
- `POST /api/chat/message`: thêm `previous_constraints` và `model_id`; trả lời về địa danh chỉ lấy từ danh mục có bằng chứng phù hợp. Nội dung mô tả cần Evidence bao phủ trường `description`.
- `GET /api/pois`: thêm `verified_only`.
- `GET /api/experiences` và `/api/experience-search`: thêm `verified_only`, `poi_id`, `total_budget_vnd`; luồng mới sử dụng `scope=pilot`.
- Request lập lịch thêm `require_verified` và `routing_mode` (`configured` hoặc `demo`). Các client cũ giữ giá trị mặc định cũ; giao diện hành trình mới gửi lựa chọn rõ ràng.

## Kiểm kê AI và nhà cung cấp

- Chat, gắn tag trải nghiệm, tính tương đồng ý định, tư vấn đổi lịch, trợ lý cập nhật khung giờ của đối tác, gắn nhãn phản hồi và tư vấn thời tiết dùng chung provider qua `get_llm_provider` và `PromptRunner`.
- Tại thời điểm kiểm tra, provider đang chọn là OpenAI nhưng chưa có khóa cho provider này. Khóa Gemini đang lưu được thử trực tiếp và bị nhà cung cấp từ chối với `Invalid Auth key`. Chưa có LLM bên ngoài được xác nhận chạy thành công.
- Chat có bộ quy tắc ngoại tuyến và hiển thị nhãn dự phòng. Bộ quy tắc không phải mô hình hội thoại, không thay thế các workflow AI còn lại. Các workflow đó cần khóa hợp lệ và đúng vai trò tài khoản.
- Các API quản trị/đối tác tiếp tục giữ phân quyền và bước preview/confirm. Không đưa hành động quản trị vào chat du khách để né lỗi 403.
- Goong Directions chạy được với ô tô trong phép thử trực tiếp. Endpoint V2 từ chối `vehicle=foot`; đã bỏ quảng cáo hỗ trợ đi bộ của adapter Goong. Luồng thật hiện dùng xe máy/ô tô; đi bộ vẫn có thể thử trong demo mô phỏng.
- `/api/chat/status` cho biết có cấu hình provider, không phải kiểm tra sống khóa API. Chỉ phép gọi thực tế mới xác nhận khóa hoạt động.

## Dữ liệu cần bổ sung để mở pilot thật

Dùng cơ chế Evidence và duyệt dữ liệu hiện có. Không đổi cờ `verified` hàng loạt khi chưa có nguồn.

- POI: tên, địa chỉ, tọa độ, loại địa điểm; thêm nguồn lịch sử/mô tả nếu cần trợ lý kể về địa danh.
- Trải nghiệm: nội dung, ý định/tag, thời lượng, giá, đơn vị tính giá, tính chất hoạt động.
- Khung giờ: thời gian bắt đầu/kết thúc, sức chứa, số chỗ được báo cáo, trạng thái. Cần xác nhận từ đơn vị có thẩm quyền; không suy ra sức chứa từ giờ mở cửa công khai.
- Evidence: URL/nhãn nguồn, các trường được chứng minh, thời điểm quan sát, thời hạn, phiên bản dữ liệu, trạng thái duyệt. Bản ghi phải còn hạn và đúng revision.
- Liên kết mô hình chưa khớp: đối chiếu POI chính xác, tọa độ và `poi_id` trong cấu hình model. Tên tương tự không đủ để tự coi là cùng địa danh.
- Cấu hình khóa AI hợp lệ cho provider muốn sử dụng, sau đó thử lại workflow theo vai trò. Không đưa khóa vào mã nguồn hoặc tài liệu.

## Kiểm tra đã thực hiện

- 57 kiểm thử tự động đạt trong các nhóm journey, AI workflows, experiences, pilot area, planner, sourced catalog, routing, role isolation và integrations. Phần kiểm thử provider dùng giả lập; không coi đây là bằng chứng LLM thật hoạt động.
- TypeScript và Vite build đã được kiểm tra. Vite vẫn cảnh báo bundle lớn; tách tải Three.js/map là việc tối ưu tiếp theo.
- Trên trình duyệt: mặc định 0 dữ liệu xác minh; bật demo; chọn Dinh Độc Lập ở Map 3D; nhắn nhóm 2 người, 09:00–16:00, 1.200.000 đồng; chuyển sang Chat vẫn giữ hội thoại; Khám phá giữ điều kiện; Planner giữ trải nghiệm và điểm đi/về.
- Lịch thử `ac9fe8b1-043f-4b6c-bd69-15e0a3b25145` được tạo trong DB local: Bưu điện → Dinh Độc Lập → Bưu điện, 160.000 đồng vé cho 2 người, về 15:05 trước hạn 16:00, hai chặng mô phỏng. Tải lại vẫn nhận đúng demo. Đây là kiểm tra kỹ thuật, chưa phải đánh giá với du khách thật.

## Đánh giá pilot tiếp theo

Sau khi đủ dữ liệu đã xác minh và API hợp lệ, cho người thử thực hiện một nhiệm vụ từ chọn sở thích tới đọc lịch trình. Ghi nhận: hoàn thành hay không, số bước/thời gian, lý do không khả thi, chi phí so với ngân sách, giờ về so với hạn, người dùng có giải thích được lý do lựa chọn hay không. Kiểm tra riêng trường hợp hết chỗ, quá ngân sách, ngoài vùng pilot, nguồn hết hạn và API chỉ đường lỗi. Chỉ mở rộng vùng hoặc cá nhân hóa sau khi có kết quả.
