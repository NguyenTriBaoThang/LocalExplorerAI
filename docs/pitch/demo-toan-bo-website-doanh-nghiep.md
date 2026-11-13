# Kịch bản demo toàn bộ Local Explorer AI theo bài toán doanh nghiệp

**Thời lượng:** 12–15 phút
**Đối tượng:** doanh nghiệp du lịch, đơn vị tổ chức tour, đối tác cung cấp trải nghiệm
**Thông điệp chính:** Local Explorer AI kết nối dữ liệu điểm đến, tư vấn khách, lập lịch trình và vận hành tour trong một luồng có thể kiểm tra.

## 1. Mở đầu: Bài toán doanh nghiệp (1 phút)

**Màn hình:** Trang chủ — http://localhost:8080/

**Người thuyết trình nói:**

> Một doanh nghiệp du lịch địa phương có thể biết rất nhiều địa điểm hấp dẫn, nhưng thông tin thường nằm rải rác: địa chỉ ở bản đồ, giá trong bảng tính, giờ hoạt động ở một nguồn khác, còn tình trạng chỗ trống phải hỏi lại đối tác. Nhân viên mất thời gian ghép các thông tin này để tư vấn khách. Nếu giá hoặc lịch thay đổi, lịch trình và báo giá cũng phải làm lại.
>
> Local Explorer AI xây dựng một luồng thống nhất: quản lý dữ liệu địa điểm và trải nghiệm, giúp khách khám phá bằng bản đồ 3D và AI, lập lịch trình theo điều kiện thực tế, đồng thời hỗ trợ doanh nghiệp điều hành tour và kiểm soát biên lợi nhuận.

**Chuyển ý:** Bắt đầu từ trải nghiệm của khách du lịch.

## 2. Khách hàng khám phá địa điểm và trải nghiệm (3 phút)

**Màn hình:** `/places` → `/explore` → trang chi tiết địa điểm.

**Thao tác:** Mở danh sách địa điểm, tìm một điểm tham quan, vào trang chi tiết và chỉ ra thông tin mô tả, vị trí, trải nghiệm liên quan.

**Người thuyết trình nói:**

> Thay vì chỉ đặt một ghim trên bản đồ, hệ thống phân biệt địa điểm, trải nghiệm tại địa điểm và khung giờ tham gia. Khách có thể tìm hiểu nội dung trước khi đưa vào kế hoạch. Với doanh nghiệp, cấu trúc này giúp quản lý dịch vụ rõ ràng hơn và biết thông tin nào cần được đối tác xác nhận.

**Màn hình:** `/map-3d`.

**Thao tác:** Chọn Nhà thờ Đức Bà, xem mô hình 3D và chuyển sang chế độ đi bên trong. Có thể chọn thêm một công trình khác để cho thấy danh mục mô hình.

**Người thuyết trình nói:**

> Bản đồ 3D giúp khách hình dung điểm đến trước chuyến đi. Doanh nghiệp cũng có thể giới thiệu di sản và trải nghiệm trực quan hơn so với một danh sách địa điểm thông thường.

**Lướt nhanh:** `/guides` và `/about` để giới thiệu nội dung cẩm nang và định vị sản phẩm.

## 3. AI tiếp nhận nhu cầu và lập lịch trình (3 phút)

**Màn hình:** Đăng nhập tài khoản du khách → `/chat`.

**Tin nhắn mẫu:**

> Tôi muốn đi chơi ở TP.HCM ngày mai trong 1 ngày, nhóm 2 người. Tôi thích địa điểm văn hóa và ăn uống, muốn di chuyển hợp lý và không về quá muộn.

**Thao tác:** Gửi tin nhắn, trả lời các câu hỏi bổ sung về ngân sách hoặc phương tiện nếu hệ thống hỏi, sau đó mở lịch trình hoặc `/planner`.

**Người thuyết trình nói:**

> Khách không cần tự điền một biểu mẫu dài. AI đọc yêu cầu bằng ngôn ngữ tự nhiên, nhận diện thời gian, số người, sở thích và những thông tin còn thiếu để hỏi tiếp. Yêu cầu sau đó được chuyển thành dữ liệu có cấu trúc cho bộ lập lịch.
>
> Lịch trình cần xét thời gian di chuyển, ngân sách, điểm dừng và điều kiện của trải nghiệm. AI hỗ trợ hiểu yêu cầu và giải thích; giá, sức chứa và khả năng đặt chỗ phải dựa trên dữ liệu được quản lý.

**Nếu có lịch trình mẫu:** Mở `/history`, chọn một lịch trình và vào `/compare` để minh họa cách xem lại phương án khi kế hoạch thay đổi.

## 4. Đối tác cung cấp trải nghiệm vận hành dịch vụ (2 phút)

**Màn hình:** Portal — http://localhost:8081/ — đăng nhập bằng tài khoản provider demo.

**Thao tác:** Mở Tổng quan → Địa điểm → Trải nghiệm → Lịch/khung giờ → Yêu cầu đặt chỗ → Đánh giá.

**Người thuyết trình nói:**

> Đối tác không chỉ xuất hiện như một địa điểm trên bản đồ. Họ có nơi cập nhật hoạt động, lịch và tình trạng phục vụ. Doanh nghiệp du lịch có thể dùng thông tin đó để tư vấn chính xác hơn. Khi có yêu cầu đặt chỗ, đối tác là bên xác nhận khả năng phục vụ.

## 5. Doanh nghiệp tổ chức tour báo giá và kiểm soát lợi nhuận (3 phút)

**Màn hình:** Portal — đăng nhập bằng tài khoản operator demo.

**Thao tác:** Mở Bảng giá → Báo giá → Đối chiếu → Biên lợi nhuận → ROI.

**Người thuyết trình nói:**

> Với đơn vị tổ chức tour, một khó khăn khác là báo giá chậm và lãi thực tế lệch khỏi lãi dự kiến. Nhân viên phải đọc yêu cầu khách, tìm giá nhà xe, nhà hàng và các dịch vụ, rồi tự cộng trong bảng tính.
>
> Ở đây doanh nghiệp lưu bảng giá nhà cung cấp, tạo bản nháp báo giá từ yêu cầu của khách và xem từng khoản chi phí. Sau khi tour diễn ra, phần đối chiếu giúp so sánh chi phí dự kiến với hóa đơn thực tế. Trang biên lợi nhuận cho biết báo giá hoặc tour nào cần được xem lại.

**Điểm cần nhấn mạnh:**

> AI giúp soạn và tổng hợp thông tin. Giá vốn và biên lợi nhuận được tính từ dữ liệu, công thức và các thay đổi đã ghi nhận. Nhân viên vẫn là người kiểm tra và quyết định báo giá gửi khách.

## 6. Quản trị chất lượng dữ liệu và hệ thống (2 phút)

**Màn hình:** Portal — đăng nhập bằng tài khoản admin demo.

**Thao tác:** Mở Địa điểm → Nhập dữ liệu → Đối tác → Người dùng → Tích hợp. Nếu còn thời gian, mở Nhật ký hệ thống.

**Người thuyết trình nói:**

> Muốn tư vấn đúng thì dữ liệu đầu vào phải đáng tin. Quản trị viên có thể xem dữ liệu địa điểm, xét duyệt nguồn nhập, quản lý đối tác và cấu hình các dịch vụ tích hợp. Đây là lớp kiểm soát để doanh nghiệp không biến dữ liệu chưa xác minh thành lời hứa với khách.

## 7. Kết luận (30–45 giây)

**Người thuyết trình nói:**

> Local Explorer AI giúp doanh nghiệp đi từ dữ liệu địa điểm đến tư vấn và vận hành trải nghiệm trong một hệ thống. Khách tìm hiểu và lập kế hoạch thuận tiện hơn; đối tác cập nhật dịch vụ; đơn vị tổ chức tour báo giá nhanh hơn và theo dõi được chi phí, biên lợi nhuận. Giá trị cốt lõi là giảm thao tác thủ công và đưa ra quyết định dựa trên dữ liệu có thể kiểm tra.

## Danh sách chuẩn bị trước buổi demo

- Mở sẵn trang khách hàng `http://localhost:8080/` và Portal `http://localhost:8081/`.
- Kiểm tra Docker, API và Gemini hoạt động; thử trước đúng câu nhắn sẽ trình diễn.
- Chuẩn bị tài khoản du khách, provider, operator và admin ở các phiên trình duyệt riêng.
- Chuẩn bị địa điểm, lịch trình và báo giá mẫu có nội dung dễ giải thích.
- Dùng dữ liệu đã xác minh khi nói về khả năng đặt chỗ. Gắn nhãn rõ các bản ghi demo hoặc chưa xác minh.
- Chỉ trình diễn thanh toán thật khi đã có môi trường kiểm thử và xác nhận đầu cuối.

**Tình trạng bản local khi soạn kịch bản:** Có 202 địa điểm, tài khoản du khách và admin. Chưa có tài khoản provider/operator, chưa có báo giá mẫu và chưa có khung giờ còn chỗ. Cần chuẩn bị các phần này trước khi demo đầy đủ hai Portal và luồng đặt chỗ.