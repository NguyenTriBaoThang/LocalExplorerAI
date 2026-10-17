      # Flow quay video demo — Local Explorer AI

**Đối tượng:** Ban giám khảo / hội đồng  
**Thời lượng đề xuất:** 4 phút cho mạch chính; 5–7 phút nếu thêm nhánh đối tác đã rehearsal  
**Thông điệp:** Từ mong muốn tự nhiên của du khách, Concierge trích xuất điều kiện chuyến đi, kiểm tra các điểm đầu/cuối, rồi chuyển sang một lịch trình có timeline, bản đồ và giải thích rõ độ chắc chắn.

> Kịch bản này được viết sau khi duyệt giao diện đang chạy bằng Playwright. Dữ liệu danh mục và chuyến đi trong phiên hiện tại được gắn nhãn mô phỏng. Hãy gọi chúng là dữ liệu demo, không gọi là địa điểm/slot đã xác minh ngoài đời.

## Flow quay chính — khoảng 4 phút

| Thời gian | Màn hình và thao tác | Lời dẫn gợi ý | Nối mạch |
|---|---|---|---|
| **0:00–0:20** | Trang chủ `/`. Giữ chuột yên trên hero 3D, sau đó chỉ nhanh hai CTA **Trò chuyện với AI Concierge** và **Khám phá trải nghiệm**. | “Một điểm đến hiện trên bản đồ chưa chắc phù hợp với thời gian, ngân sách và trải nghiệm du khách muốn. Local Explorer AI gom các điều kiện đó vào một kế hoạch trong ngày.” | Mở Chat từ CTA trên trang chủ. |
| **0:20–0:55** | `/chat`. Chọn gợi ý workshop hoặc nhập câu: **“Nhóm mình đi 2 người, muốn kết hợp một workshop thủ công với ẩm thực địa phương, từ 09:00 đến 16:00, tổng ngân sách 1.200.000₫, di chuyển bằng xe máy.”** Bấm **Gửi**. | “Du khách có thể kể theo cách tự nhiên. Concierge chuyển lời nhắn thành quy mô nhóm, khung giờ, ngân sách, sở thích và phương tiện.” | Chờ phản hồi; chuyển mắt sang Trip HUD bên phải. |
| **0:55–1:35** | Kiểm tra các điều kiện AI trích xuất. Ở **Tuyến đường & Mốc thời gian**, chọn điểm A và điểm B; gợi ý dùng **Điểm demo 01: Góc thủ công giấy** và **Điểm demo 03: Bếp món Nam bộ**. Giữ ngày ở tương lai. | “Tôi kiểm tra lại các ràng buộc trước khi tạo lịch. Bốn tiêu chí trong HUD là điều kiện AI đọc được; điểm xuất phát và điểm phải quay về là hai lựa chọn riêng, cũng cần chọn để nút tạo lịch sẵn sàng.” | Khi nút **Tạo lịch trình ngay** sáng lên, bấm một lần. |
| **1:35–2:55** | `/itinerary/:id`. Chỉ vào badge **Dữ liệu mô phỏng**, các KPI, timeline bên trái và bản đồ bên phải. Đọc số liệu đang có trên màn hình, không học thuộc số của ảnh mẫu. | “Các trải nghiệm được xếp thành một timeline; bên cạnh là tổng thời lượng, chi phí ước tính, số điểm dừng và các chặng đường. Đây là một bản kế hoạch để xem xét, chưa phải xác nhận đặt chỗ.” | Cuộn vừa đủ xuống phần minh bạch. |
| **2:55–3:35** | Chỉ vào **Vì sao lịch trình này được đề xuất?** và ghi chú ETA trên bản đồ/chặng. | “Phần giải thích nêu các yếu tố phù hợp và những gì chỉ là ước tính. Trong môi trường demo này, tuyến do provider `mock` tính; ETA không phải dữ liệu giao thông trực tiếp.” | Giữ trên trang itinerary; tránh mở thêm màn hình. |
| **3:35–4:00** | Dừng ở timeline và bản đồ; kết thúc bằng một câu. | “Mạch chính là một chuyến đi liền nhau: nói nhu cầu, xác nhận điều kiện, rồi xem một lịch trình có thể giải thích. Khi dữ liệu đối tác sẵn sàng, cùng lịch này có thể là điểm bắt đầu cho nhánh xử lý thay đổi.” | Kết video ở itinerary. |

### Câu kết ngắn

> “Local Explorer AI nối nhu cầu của du khách với một lịch trình có thời gian, điểm dừng và tuyến đường rõ ràng; đồng thời cho biết đâu là dữ liệu mô phỏng và đâu là ước tính cần kiểm tra thêm.”

## Chuẩn bị để quay liền mạch

1. Mở sẵn `http://localhost:5173/`, đặt trình duyệt tiếng Việt, giao diện sáng, zoom khoảng 90% và khung hình 16:9. Ẩn tab thừa, bookmark bar và DevTools.
2. Chọn ngày đi ở tương lai. Ảnh chụp hiện tại dùng ngày **16/10/2026**; ngày mặc định sẽ đổi theo ngày hệ thống.
3. Dùng một câu hỏi có ghi rõ phương tiện. Trong lần kiểm tra, câu hỏi không nêu phương tiện nhưng AI tự điền **Ô tô**. Vì vậy hãy kiểm tra lại phương tiện nhận diện trước khi tạo lịch.
4. Chọn cả điểm A và điểm B trong Chat. Chỉ báo **100%** nghĩa là đủ bốn tiêu chí AI; nó không thay cho hai điểm tuyến đường bắt buộc.
5. Chờ phản hồi AI và dữ liệu bản đồ tải xong trước khi bấm quay. Trên trang `/map-3d`, chờ mô hình hiện ra; ảnh tải xong tham khảo là [02-map-3d-loaded.png](artifacts/presentation-video/02-map-3d-loaded.png).
6. Không để lộ `.env`, API key, cửa sổ terminal hoặc nội dung đăng nhập trong video.

### Nhánh dự phòng đã rehearsal

Nếu Gemini phản hồi chậm/lỗi, chuyển thẳng sang `/planner`. Form hiện có sẵn 2 khách, 09:00–16:00, ngân sách 1.200.000₫, hai sở thích ẩm thực + thủ công và xe máy. Chọn điểm xuất phát **Điểm demo 01: Góc thủ công giấy**, điểm về **Điểm demo 03: Bếp món Nam bộ**, rồi bấm **Tạo Lịch Trình Ngay**. Mình đã chạy đường này thành công trong môi trường hiện tại; lịch mẫu nằm tại [http://localhost:5173/itinerary/8416b0fa-08eb-4843-958b-e4bbc0f6debc](http://localhost:5173/itinerary/8416b0fa-08eb-4843-958b-e4bbc0f6debc).

Ảnh kết quả mẫu được tạo từ Planner, nên số KPI/timeline của chuyến Chat có thể khác. Khi quay, hãy đọc số đang hiển thị thay vì đọc số cố định trong tài liệu.

## Nhánh đối tác → đổi lịch — chỉ thêm khi đã chuẩn bị tài khoản

Đây là phần mở rộng cho video 5–7 phút, nối với itinerary hiện tại:

1. Giữ nguyên mã itinerary của du khách và mở một hồ sơ trình duyệt thứ hai đã đăng nhập vai trò đối tác.
2. Tìm đúng ca đang được itinerary sử dụng, cập nhật/hủy ca đó trong `/provider-portal`.
3. Quay lại hồ sơ du khách, mở cảnh báo thay đổi, yêu cầu phương án thay thế, xem lý do, rồi chấp nhận và xác nhận phiên bản lịch mới.

**Chỉ quay nhánh này sau khi rehearsal đầu-cuối thành công.** Trong phiên khách được kiểm tra, `/provider-portal` chuyển về `/login`; nút **Thêm trải nghiệm** ở trang `/provider` bật thông báo yêu cầu tài khoản nhà cung cấp. Chưa có tài khoản/slot đối tác phù hợp để ghi nhận thao tác hủy và replan trực tiếp. Nếu chưa chuẩn bị đủ, kết thúc ở itinerary; không dựng cảnh như thể thay đổi đã chạy.

## Những điểm cần nói đúng khi thuyết trình

- `/places` và `/explore` đang ghi rõ **Dữ liệu mô phỏng**; danh sách hiện có 9 mục, dù phần giới thiệu của `/places` còn nói 124 điểm đến. Trong video, không đọc “124” như số lượng catalog thực tế.
- Chi tiết điểm demo có dòng “địa điểm hư cấu dùng để trình diễn giao diện”. Không mô tả điểm demo hoặc slot là đối tác/địa điểm đã xác minh.
- Planner và itinerary ghi provider định tuyến là **mock**; ETA chỉ là ước tính, không phải giao thông thời gian thực. Một số câu quảng bá trên Explore có thể nói khác, nên ưu tiên trạng thái ghi trong Planner/itinerary.
- Trang itinerary có nút **Chia sẻ** và **In / Lưu**, nhưng kịch bản này không khẳng định chia sẻ, giữ chỗ hay thanh toán đã chạy. Trạng thái thanh toán hiện tắt.
- CTA **Hỏi AI về địa điểm này** mở Chat kèm query trong URL, nhưng trong lần kiểm tra nội dung query không xuất hiện sẵn trong ô soạn tin. Nếu muốn giữ nhịp quay, bắt đầu từ Chat ở trang chủ hoặc chọn một thẻ gợi ý trong Chat.

## Danh mục màn hình đã chụp

Các ảnh được lưu trong `artifacts/presentation-video/`. Ảnh toàn trang hữu ích để rà nội dung; khi quay video, thao tác trong viewport 16:9 và cuộn có chủ đích.

| Route / trạng thái | Nội dung quan sát được | Ảnh |
|---|---|---|
| `/` | Hero 3D, CTA Concierge/Khám phá, danh mục, trải nghiệm nổi bật và tuyên bố sản phẩm. | [01-home.png](artifacts/presentation-video/01-home.png) |
| `/map-3d` | Goong Maps 3D, 8 landmark chọn được, camera presets và mô hình nhà thờ sau khi tải. | [02-map-3d-loaded.png](artifacts/presentation-video/02-map-3d-loaded.png), [02-map-3d.png](artifacts/presentation-video/02-map-3d.png), [02-map-3d-dinh-doc-lap.png](artifacts/presentation-video/02-map-3d-dinh-doc-lap.png) |
| `/places` | Tìm kiếm, category chips, danh sách 9 địa điểm demo. | [03-places.png](artifacts/presentation-video/03-places.png) |
| `/places/:id` | Chi tiết điểm, hoạt động, nguồn/tính minh bạch và CTA hỏi AI/lập lịch. | [09-place-detail.png](artifacts/presentation-video/09-place-detail.png) |
| `/explore` | Bộ lọc thời gian/ngân sách/nhóm, thẻ trải nghiệm và bản đồ 9 điểm neo. | [04-explore.png](artifacts/presentation-video/04-explore.png) |
| `/explore` — mở **Lọc thêm** | Chủ đề từ khóa, trong nhà/ngoài trời, bán kính và tùy chọn E5 Semantics. | [20-explore-advanced-filters.png](artifacts/presentation-video/20-explore-advanced-filters.png) |
| `/chat` | Concierge, ví dụ prompt, Trip HUD và yêu cầu chọn điểm đi/điểm về. | [05-chat.png](artifacts/presentation-video/05-chat.png) |
| `/chat` — prompt đã chọn | Thẻ gợi ý đưa câu mẫu vào ô soạn tin; chưa gửi. | [22-chat-filled-suggestion.png](artifacts/presentation-video/22-chat-filled-suggestion.png) |
| `/chat` — phản hồi AI | AI trích xuất 2 người, 09:00–17:00, ngân sách 1.500.000₫, sở thích thủ công; phương tiện được tự điền Ô tô khi câu hỏi không nói rõ. | [25-chat-response.png](artifacts/presentation-video/25-chat-response.png) |
| `/chat` — đủ điều kiện tạo | Đã chọn điểm A/B; nút tạo itinerary bật. | [26-chat-ready-to-create.png](artifacts/presentation-video/26-chat-ready-to-create.png) |
| `/planner` | Bốn nhóm trường: thời gian/nhóm, mục đích, phương tiện, điểm đầu/cuối/điểm ghim; có preview. | [06-planner.png](artifacts/presentation-video/06-planner.png) |
| `/planner` — đã chọn A/B | Form demo đã cấu hình với hai điểm mẫu. | [23-planner-configured.png](artifacts/presentation-video/23-planner-configured.png) |
| `/itinerary/:id` | KPI, timeline, map route, các chặng và phần giải thích. Lịch hiện tại được tạo từ Planner. | [24-itinerary-created.png](artifacts/presentation-video/24-itinerary-created.png) |
| Detail → Chat | CTA điều hướng tới `/chat?prompt=...`; nội dung không tự đổ vào composer. | [18-detail-to-chat.png](artifacts/presentation-video/18-detail-to-chat.png) |
| Detail → Planner | CTA mở `/planner`; các giá trị form vẫn là mặc định. | [19-detail-to-planner.png](artifacts/presentation-video/19-detail-to-planner.png) |
| `/provider` | Bảng tổng quan danh mục và khung giờ; nút thêm yêu cầu vai trò provider. | [07-provider.png](artifacts/presentation-video/07-provider.png) |
| `/about` | Mô tả mô hình dữ liệu, planner heuristic và minh bạch dữ liệu demo. | [08-about.png](artifacts/presentation-video/08-about.png) |
| `/login` | Email/password; giao diện ghi chú cấu hình Google OAuth. | [10-login.png](artifacts/presentation-video/10-login.png) |
| `/register` | Tạo tài khoản du khách; mật khẩu tối thiểu 12 ký tự. | [11-register.png](artifacts/presentation-video/11-register.png) |
| `/profile` — khách chưa đăng nhập | Redirect về `/login`. | [12-profile.png](artifacts/presentation-video/12-profile.png) |
| `/compare` — khách chưa đăng nhập | Redirect về `/login`; cần tài khoản traveler và itinerary thuộc tài khoản. | [13-compare.png](artifacts/presentation-video/13-compare.png) |
| `/provider-portal` — khách chưa đăng nhập | Redirect về `/login`; cần vai trò provider. | [14-provider-portal.png](artifacts/presentation-video/14-provider-portal.png) |
| `/admin` — khách chưa đăng nhập | Redirect về `/login`; cần vai trò admin. | [15-admin.png](artifacts/presentation-video/15-admin.png) |
| `/itinerary/demo` | Trạng thái lỗi “Chưa thể tải lịch trình / Itinerary not found”. | [16-itinerary-demo.png](artifacts/presentation-video/16-itinerary-demo.png) |
| `/shared/demo` | Mã chia sẻ không tồn tại/hết hạn. | [17-shared-demo.png](artifacts/presentation-video/17-shared-demo.png) |

## Trạng thái lịch mẫu đã tạo

Để xem được màn hình itinerary thật, mình đã tạo một lịch thử nội bộ qua Planner, dùng các điểm demo 01 và 03. Kết quả hiện có 2 trải nghiệm; ảnh chụp hiển thị 6 giờ 35 phút, 15 phút di chuyển ước tính, chi phí 560.000₫ và trạng thái khả thi cao theo khung giờ. Đây là record mô phỏng để xem giao diện; không có đặt chỗ hoặc thanh toán.

