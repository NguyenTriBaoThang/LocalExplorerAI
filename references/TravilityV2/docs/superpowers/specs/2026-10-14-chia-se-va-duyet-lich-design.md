# Travility — Chia sẻ lịch trình và duyệt góp ý

> Thiết kế v1 · 2026-10-14 · Trạng thái: người dùng đã duyệt đặc tả.

## 1. Mục tiêu

Người tổ chức một chuyến đi trong nước thường là người duy nhất dùng Travility để tạo và sửa lịch, trong khi cả nhóm mới là người cùng thực hiện chuyến đi. Chức năng này giúp người tổ chức chia sẻ lịch, nhận góp ý và đưa góp ý vào một version mới mà vẫn giữ quyền chốt lịch.

Đối tượng đầu tiên là người lên kế hoạch cho nhóm nhỏ. Desktop là nơi chuẩn bị chuyến đi. Ứng dụng mobile native là phần mở rộng sau; không làm web.

### Nguyên tắc

- Một người tổ chức giữ quyền sửa và áp dụng version.
- Lịch và góp ý của nhóm không được trộn với lịch sử chat riêng hay Trip khác.
- Góp ý có ngữ cảnh version; chỉnh sửa được kiểm tra bằng quy tắc của code, không để AI tự tính chi phí hoặc hợp lệ.
- Chỉ người tổ chức duyệt bản AI đề xuất mới tạo version mới.

## 2. Phạm vi theo giai đoạn

### Giai đoạn 1 — Desktop

1. Người tổ chức xuất PDF từ version đang xem.
2. PDF ghi rõ destination, ngày đi, lịch theo ngày/giờ, địa điểm, chỗ ở, tuyến đường, chi phí ước tính, xung đột hiện có, số version và thời điểm xuất.
3. Người tổ chức gửi PDF qua kênh họ đang dùng. Thành viên phản hồi bên ngoài Travility.
4. Trong Chat của Trip, người tổ chức chọn **Góp ý nhóm**, chọn version mà góp ý đang nói tới (mặc định version đang xem), rồi nhập/tóm tắt phản hồi.
5. Nếu version nguồn góp ý cũ hơn bản mới nhất, app báo rõ. AI lấy lịch mới nhất làm bản nền và giữ số version nguồn để người tổ chức đối chiếu.
6. AI tạo bản xem trước gồm tóm tắt thay đổi, các Stop liên quan, chi phí và Conflict. Bản xem trước chưa ghi version mới.
7. Người tổ chức chọn **Áp dụng** hoặc **Huỷ**. Áp dụng tạo version bất biến qua luồng lưu Itinerary hiện có. Người tổ chức có thể xuất PDF mới.

Yêu cầu sửa lịch thông thường tiếp tục theo luồng chat hiện có. Chế độ xem trước chỉ được kích hoạt rõ ràng bằng **Góp ý nhóm**.

### Giai đoạn 2 — Mobile native

1. Người tổ chức bật chia sẻ Trip và gửi link/mã mời riêng.
2. Thành viên cài và mở app mobile, nhập tên hiển thị, không cần tạo tài khoản.
3. Họ xem bản lịch đang được chia sẻ ở chế độ chỉ đọc: ngày, giờ, Stop, Stay, tuyến đường và chi phí ước tính. Không xem chat, hồ sơ người tổ chức hay Trip khác.
4. Với từng Stop, thành viên chọn **Giữ lại** hoặc **Muốn đổi**, có thể thêm ghi chú.
5. Người tổ chức xem tên và từng góp ý trên desktop; thành viên chỉ thấy tổng hợp của nhóm.
6. Góp ý gắn với version được xem. Nếu Trip đã có version mới, góp ý cũ vẫn được lưu, đánh dấu là của version trước, không tự áp lên lịch mới.
7. Người tổ chức đưa góp ý vào cùng luồng xem trước của giai đoạn 1. Khi họ áp dụng, mobile hiển thị version mới. Thiết bị đã bật thông báo nhận push.
8. Mã mời hết hạn vào ngày cuối chuyến đi; người tổ chức có thể thu hồi sớm hơn. Nếu Trip chưa có ngày đi, người tổ chức chọn ngày hết hạn khi bật chia sẻ.

## 3. Luồng duyệt góp ý

Luồng **Góp ý nhóm** sử dụng cùng Chat của Trip nhưng là một hành động riêng để phân biệt với yêu cầu sửa thông thường. AI diễn giải góp ý thành thao tác sửa; code áp thao tác lên Itinerary, tính lại chi phí/Leg và kiểm tra quy tắc. App hiển thị ứng viên, phần thay đổi và Conflict trước khi lưu.

Nếu góp ý trái chiều, AI trình bày các ý kiến để người tổ chức cân nhắc; không tự quyết theo đa số. Hủy bản xem trước không tạo version. Áp dụng tạo version tiếp theo và không ghi đè version cũ.

Khi người tổ chức mở bản xem trước trên version nền vN nhưng Trip đã chuyển sang vN+1 trước lúc áp dụng, server từ chối áp dụng bản cũ và yêu cầu tạo lại bản xem trước trên lịch mới. Góp ý tham chiếu một version cũ được giữ nguyên ngữ cảnh; người tổ chức quyết định có đưa ý đó vào bản hiện tại hay không.

## 4. Thành phần và ranh giới

### Desktop hiện tại

- App tiếp tục giữ Trip, version và trạng thái chat.
- Timeline cung cấp version đang xem và dữ liệu Itinerary cho chức năng xuất PDF.
- ChatPanel có hành động **Góp ý nhóm**; nội dung đi qua nhánh review thay vì tự lưu ngay.
- Thẻ xem trước được đặt trong luồng hiện tại, theo cách người dùng đã quen với ProposalPanel.
- PDF là snapshot của version được chọn; xuất lại sau khi có version mới để chia sẻ lịch cập nhật.

### Server giai đoạn 1

- Nhánh review tạo candidate Itinerary và kiểm tra bằng build_itinerary.
- Candidate được lưu tạm như một revision proposal có trip_id, source_version, base_version, bản Itinerary đã tính, Stop thay đổi, phần tóm tắt, Conflict và trạng thái.
- Chỉ endpoint apply mới gọi đường lưu Itinerary/version; apply phải kiểm tra base_version còn là version mới nhất.
- Tin nhắn góp ý và kết quả áp dụng được ghi vào lịch sử Trip hiện có.

### Mobile và server giai đoạn 2

- Dữ liệu share và guest feedback được lưu cùng shard của Trip.
- Share token ngẫu nhiên, khó đoán; server lưu dạng hash. Token chỉ mở đúng Trip được chia sẻ và cho phép đọc/gửi feedback, không truy cập chat hay các Trip khác.
- Feedback gắn với Trip, version, ngày/Stop, tên hiển thị, lựa chọn keep/change, ghi chú và mã submission để chống gửi trùng.
- Guest name là tên tự khai, không phải xác minh danh tính. Link là bearer secret: ai có link đều có thể vào cho đến khi hết hạn/thu hồi.
- Push chỉ gửi đến thiết bị đã bật thông báo; tắt thông báo không ảnh hưởng việc xem version mới khi mở Trip.

## 5. Dữ liệu và hành vi chia sẻ

- Trip và Itinerary hiện có tiếp tục là nguồn sự thật; bản mobile không tạo bản sao lịch có thể chỉnh độc lập.
- PDF hiển thị rõ version và thời điểm xuất. PDF cũ vẫn là snapshot; người tổ chức xuất lại để phát hành lịch mới.
- Guest chỉ đọc version hiện được chia sẻ. Feedback cũ được lưu theo version; người tổ chức thấy tên và ghi chú, nhóm chỉ thấy tổng hợp lựa chọn.
- Thu hồi hoặc hết hạn token ngăn mọi lần đọc/gửi tiếp theo. Những bản PDF đã tải xuống là bản tĩnh do người nhận giữ.

## 6. Xử lý lỗi và xung đột

- Draft sai cấu trúc hoặc vi phạm luật cứng không thể áp dụng; người tổ chức nhận lỗi rõ ràng và có thể tạo lại preview.
- Conflict nghiệp vụ như vượt Budget vẫn hiển thị trong preview. Người tổ chức quyết định áp dụng hay huỷ, phù hợp nguyên tắc Travility luôn trả lịch kèm Conflict.
- Nếu Trip đổi sang version mới sau khi preview được tạo, thao tác áp dụng bị từ chối; app tải version mới và yêu cầu người tổ chức tạo lại preview. Nếu ngay từ đầu góp ý tham chiếu version cũ, app cảnh báo trước khi tạo preview và dùng version mới nhất làm bản nền.
- Feedback gửi từ màn hình cũ được giữ với nhãn version cũ thay vì lặng lẽ gắn sang version mới.
- Link hết hạn/thu hồi hiện trạng thái không còn quyền truy cập, không trả dữ liệu Trip.
- Mất mạng khi xuất PDF hoặc gửi feedback báo rõ thao tác chưa hoàn tất; gửi lại cùng submission không tạo feedback trùng.

## 7. Tiêu chí chấp nhận và đánh giá

### Desktop

- PDF khớp chính xác version đang xem và ghi rõ số version.
- Gửi góp ý nhóm tạo preview, không tạo version trước khi bấm **Áp dụng**.
- **Huỷ** giữ nguyên lịch và lịch sử version.
- **Áp dụng** tạo version mới, giữ version trước và kiểm tra version nền chưa bị thay đổi.
- Người tổ chức có thể xuất PDF mới sau khi duyệt lịch.

### Mobile — giai đoạn sau

- Guest chỉ đọc được Trip từ token hợp lệ; không truy cập chat/Trip khác.
- Feedback có tên hiển thị và gắn đúng version/Stop; nhóm chỉ thấy tổng hợp.
- Thu hồi/hết hạn token chặn đọc và gửi feedback; push chỉ đến người đã bật.

### Thử nghiệm người dùng

Thử với một nhóm nhỏ người thường đứng ra lên kế hoạch. Đo tỷ lệ hoàn thành vòng chia sẻ → nhận góp ý → duyệt version và thời gian đến lịch được nhóm thống nhất. Chưa đặt ngưỡng số trước khi có baseline.

## 8. Ngoài phạm vi

- Web app.
- Nhiều người cùng sửa một Itinerary hoặc tự áp dụng thay đổi.
- Bỏ phiếu để tự động quyết định theo đa số.
- Đặt vé, đặt phòng, thanh toán hoặc xác minh danh tính khách mời.

## 9. Các điểm kỹ thuật cần giữ

- Kiến trúc Trip hiện tại đã phân shard; dữ liệu share/feedback phải được định tuyến theo shard của Trip.
- Tài liệu hiện trạng ghi kiến trúc đóng băng từ 2026-10-02. Thay đổi backend/mobile cần được thiết kế thành giai đoạn riêng, không làm rộng thêm hạ tầng trong lúc triển khai desktop phase 1.
- Kế hoạch triển khai đầu tiên chỉ bao gồm giai đoạn 1 trên desktop. Giai đoạn mobile native là dự án triển khai riêng sau đó; framework, push provider và phát hành store sẽ được quyết định trong kế hoạch riêng, không phải điều kiện để hoàn tất giai đoạn desktop.
