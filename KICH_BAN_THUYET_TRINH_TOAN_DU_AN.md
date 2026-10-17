# Kịch bản thuyết trình toàn bộ dự án Local Explorer AI

**Thời lượng gợi ý:** 12–15 phút, gồm khoảng 3 phút thao tác demo.  
**Đối tượng:** giảng viên, hội đồng đánh giá hoặc đối tác.  
**Bản đối chiếu:** mã và tài liệu trong `LocalExplorerAI`, nhánh `integration/main-runtime-20261017`, ngày 17/10/2026.

> Các đoạn **Lời nói** có thể đọc gần như nguyên văn. Các đoạn **Thao tác** là lời nhắc cho người trình bày, không cần đọc thành tiếng. Các số liệu danh mục là ảnh chụp trạng thái local ngày 17/10/2026 và có thể thay đổi.

## 1. Mở đầu và bài toán (0:00–1:15)

**Trên màn hình:** Trang chủ, tên dự án và một ảnh về trải nghiệm địa phương tại TP.HCM.

**Lời nói:**

> Kính chào thầy cô và mọi người. Dự án của nhóm em là **Local Explorer AI**, một nền tảng khám phá trải nghiệm địa phương và lập lịch tham quan theo khung giờ tại Thành phố Hồ Chí Minh.
>
> Khi tìm một địa điểm trên bản đồ, chúng ta thường thấy địa chỉ và giờ mở cửa. Nhưng một nơi đang mở cửa không có nghĩa là lớp làm gốm, buổi tham quan hay hoạt động trải nghiệm tại đó đang diễn ra và còn chỗ. Nếu chỉ dựa vào danh sách địa điểm, du khách vẫn phải tự kiểm tra thời gian, chi phí, quãng đường và sức chứa. Lịch trình do chatbot tạo ra cũng có thể nghe hợp lý nhưng không khớp với dữ liệu thực tế.
>
> Local Explorer AI giải bài toán này bằng cách kết nối thông tin địa điểm, hoạt động và khung giờ cụ thể, rồi kiểm tra các ràng buộc trước khi đề xuất hành trình.

## 2. Mục tiêu, người dùng và phạm vi (1:15–2:15)

**Trên màn hình:** Ba nhóm người dùng: du khách, nhà cung cấp trải nghiệm, quản trị viên.

**Lời nói:**

> Dự án phục vụ ba nhóm. Du khách tìm trải nghiệm phù hợp với sở thích, thời gian và ngân sách. Đơn vị cung cấp quản lý hoạt động, lịch và yêu cầu đặt chỗ. Quản trị viên kiểm tra nguồn dữ liệu, phân quyền và theo dõi vận hành.
>
> Phạm vi thử nghiệm của luồng hành trình di sản tập trung ở Quận 1. Giao diện có thể cho xem mô hình 3D của những nơi khác, nhưng việc xem mô hình không đồng nghĩa với việc nơi đó đã có hoạt động đủ dữ liệu để lên lịch. Chúng em tách rõ dữ liệu trình diễn và dữ liệu đã xác minh để người xem biết mức tin cậy của kết quả.

## 3. Giải pháp và mô hình dữ liệu (2:15–3:30)

**Trên màn hình:** Sơ đồ `POI → Experience → ExperienceSlot` và một lịch trình có nhiều điểm dừng.

**Lời nói:**

> Điểm cốt lõi của hệ thống là ba tầng dữ liệu. **POI** là địa điểm, chẳng hạn một xưởng thủ công. **Experience** là hoạt động diễn ra tại đó. **ExperienceSlot** là một buổi cụ thể, có giờ bắt đầu, giờ kết thúc, trạng thái và thông tin sức chứa. Nhờ vậy, hệ thống có thể phân biệt “địa điểm đang mở” với “hoạt động này có thể tham gia vào lúc 10 giờ”.
>
> Mỗi thông tin quan trọng còn gắn với trạng thái nguồn và thời điểm kiểm tra. Nếu chưa đủ bằng chứng, giao diện phải báo rõ dữ liệu mô phỏng hoặc cần xác nhận. Hệ thống không tự suy ra rằng một khung giờ còn chỗ chỉ vì địa điểm đang mở cửa.
>
> Từ dữ liệu đó, người dùng có thể đi theo một luồng liên tục: trò chuyện về nhu cầu, xem địa danh trên bản đồ 3D, khám phá hoạt động, rồi chuyển sang bộ lập lịch. Các điều kiện như ngày đi, số người, ngân sách và trải nghiệm đã chọn được giữ trong cùng phiên làm việc.

## 4. Luồng dành cho du khách (3:30–4:45)

**Trên màn hình:** Ảnh hoặc các màn hình Chat, Map 3D, Khám phá, Planner, lịch trình.

**Lời nói:**

> Ở trang Chat, du khách có thể nhập yêu cầu bằng ngôn ngữ tự nhiên. Hệ thống trích xuất các điều kiện và hiển thị lại để người dùng kiểm tra. Khi dịch vụ AI bên ngoài không sẵn sàng, phần chat có bộ quy tắc dự phòng và hiển thị trạng thái tương ứng.
>
> Ở Map 3D, người dùng khám phá các địa danh và mở thông tin đã liên kết với danh mục. Tại trang Khám phá, họ lọc theo ngày, giờ, quy mô nhóm, ngân sách tổng và sở thích, rồi chọn hoạt động muốn đưa vào hành trình. Planner dùng các lựa chọn ấy để đề xuất tối đa năm phương án, kèm thời gian, chi phí, tuyến di chuyển và lý do khi một hoạt động không thể xếp lịch. Người dùng có thể lưu, so sánh hoặc chia sẻ lịch trình tùy quyền truy cập.

## 5. Cách lập lịch và vai trò của AI (4:45–6:15)

**Trên màn hình:** Sơ đồ ngắn: nhập điều kiện → lọc khả thi → tính tuyến → xếp hạng → giải thích.

**Lời nói:**

> Thuật toán lập lịch bắt đầu bằng các điều kiện cứng. Nó kiểm tra ngày giờ của buổi trải nghiệm, số người, ngân sách, điểm đã chọn trước và cả thời gian quay về. Ứng viên không đáp ứng điều kiện sẽ bị loại trước khi xếp hạng. Sau đó hệ thống ước tính chặng di chuyển bằng dịch vụ định tuyến khi được cấu hình, hoặc dùng chế độ demo có nhãn rõ ràng. Kết quả cho biết vì sao một điểm được chọn hoặc vì sao không thể xếp vào lịch.
>
> Phần xếp hạng đang phục vụ bằng **bộ quy tắc có phiên bản**. Dự án có các thử nghiệm XGBoost và LightGBM, nhưng dữ liệu nhãn hiện chủ yếu là dữ liệu giả lập hoặc nhãn yếu. Vì chưa chứng minh được lợi ích với đánh giá của du khách thật, các mô hình này chưa được bật làm mô hình sản xuất. AI hỗ trợ hiểu yêu cầu, tìm kiếm và giải thích; tính khả thi của lịch trình vẫn do các điều kiện dữ liệu và thuật toán kiểm tra.
>
> Dự án còn có tìm kiếm ngữ nghĩa E5 khi cài đủ mô hình và phụ thuộc. Nếu chưa có, ứng dụng dùng phương án tìm kiếm dự phòng. Phần tư vấn thời tiết sử dụng dữ liệu bên ngoài để hỗ trợ quyết định, không đóng vai trò cảnh báo khẩn cấp. Mô hình dự báo ngập đường chưa được bật vì còn thiếu quan sát không ngập đã xác minh.

## 6. Cổng đối tác, quản trị và kiến trúc (6:15–7:45)

**Trên màn hình:** Portal đối tác, Portal quản trị và sơ đồ kiến trúc ba lớp.

**Lời nói:**

> Với đối tác, Portal cho phép quản lý địa điểm, trải nghiệm, lịch, bằng chứng nguồn và yêu cầu đặt chỗ. Trợ lý khung giờ hỗ trợ soạn thay đổi, nhưng người có quyền vẫn phải xem trước và xác nhận. Với quản trị viên, Portal có chức năng duyệt danh mục, quản lý tài khoản và quyền, kiểm tra nhật ký, cấu hình tích hợp và nội dung địa danh 3D.
>
> Về kỹ thuật, giao diện du khách và Portal được xây bằng React và TypeScript; phần 3D dùng Three.js. FastAPI xử lý nghiệp vụ, xác thực, lập lịch và API. PostgreSQL cùng PostGIS lưu địa điểm và dữ liệu không gian; Alembic quản lý thay đổi cấu trúc cơ sở dữ liệu. Các dịch vụ như Goong, Gemini, VNPay, MoMo, Meshy và E5 nằm sau các lớp tích hợp tương ứng, nên tính năng phụ thuộc vào cấu hình và kiểm thử của từng môi trường.
>
> Hệ thống đã có luồng giữ chỗ, xử lý thanh toán qua cổng và tiếp nhận callback trong mã nguồn. Tuy nhiên, một giao dịch thanh toán thật chỉ nên được khẳng định sau khi kiểm thử sandbox, callback và đối soát trên môi trường phù hợp. Tương tự, mô hình 3D tạo bởi Meshy cần người quản trị duyệt và xuất bản; mô hình do AI tạo không tự xác nhận độ chính xác kiến trúc.

## 7. Demo trực tiếp: một hành trình Quận 1 (7:45–10:45)

**Chuẩn bị trước:** Đăng nhập sẵn bằng tài khoản du khách; kiểm tra API và web đang chạy. Dùng một ngày tương lai có khung giờ demo phù hợp thay vì cố định ngày 17/10/2026. Bật **Thử demo** khi dữ liệu đã xác minh chưa đủ. Không gọi đó là giá hoặc chỗ còn lại thực tế.

### Bước A: Chat và Map 3D (khoảng 50 giây)

**Thao tác:** Vào `/chat`, nhập: “Mình muốn tham quan Quận 1 từ 9 giờ đến 16 giờ, nhóm 2 người, tổng ngân sách 1.200.000 đồng, thích văn hóa và ẩm thực.” Chỉ vào bảng điều kiện đã trích xuất. Nếu có sẵn địa danh liên kết, mở `/map-3d` và chọn địa danh trong vùng pilot.

**Lời nói:**

> Ở đây hệ thống nhận một yêu cầu thường ngày và chuyển thành các điều kiện có thể kiểm tra. Em có thể sửa điều kiện nếu hệ thống hiểu chưa đúng. Trên bản đồ 3D, địa danh đã liên kết dẫn tiếp đến hoạt động trong danh mục; những mô hình chưa có liên kết sẽ được ghi rõ.

### Bước B: Khám phá và lập lịch (khoảng 80 giây)

**Thao tác:** Mở `/explore`, giữ các bộ lọc được chuyển tiếp, chọn một trải nghiệm đủ điều kiện, sang `/planner` và tạo gợi ý. Nếu một lựa chọn không khả thi, chỉ vào phần lý do.

**Lời nói:**

> Bộ lọc đang xét thời gian, số người và ngân sách của cả nhóm. Em chọn trải nghiệm này để giữ nó trong kế hoạch. Khi tạo lịch, hệ thống kiểm tra từng khung giờ và quãng di chuyển, kể cả chặng trở về. Kết quả hiển thị rõ thời gian, chi phí ước tính, nguồn dữ liệu và các điều kiện cần xác nhận.

### Bước C: Kết quả và Portal (khoảng 50 giây)

**Thao tác:** Mở một phương án và chỉ vào các điểm dừng, nhãn demo/nguồn và phần giải thích. Sau đó chuyển nhanh sang Portal đã đăng nhập sẵn để cho xem lịch của đối tác hoặc màn hình duyệt dữ liệu của quản trị viên. Không tạo giao dịch trả phí trong buổi demo.

**Lời nói:**

> Lịch trình này là kết quả từ dữ liệu demo, nên em không trình bày nó như một xác nhận đặt chỗ. Khi đối tác cập nhật lịch và cung cấp bằng chứng, quản trị viên có thể duyệt dữ liệu. Đây là hai phía cùng tham gia để lịch trình trong tương lai có cơ sở đáng tin hơn.

**Nếu demo bị gián đoạn:** Mở ảnh chụp màn hình đã chuẩn bị, giải thích bước đang trình bày và tiếp tục. Không nói API hay cổng thanh toán đã hoạt động nếu buổi demo chưa kiểm tra được.

## 8. Kết quả hiện tại và giới hạn (10:45–12:15)

**Trên màn hình:** Ba nhóm: đã triển khai, đã kiểm thử, còn cần xác minh.

**Lời nói:**

> Ở bản tích hợp hiện tại, cơ sở dữ liệu local có 202 địa điểm; API công khai trả 192 địa điểm và 192 trải nghiệm theo cấu hình demo lúc kiểm tra. Con số này là số bản ghi, chưa phải số trải nghiệm đã được đối tác xác minh để đặt chỗ thật. Luồng từ Chat qua Map 3D, Khám phá đến Planner đã được kiểm tra trên trình duyệt. Đợt tích hợp mới nhất ghi nhận 373 bài kiểm thử API đạt, cùng bản build thành công cho web du khách và Portal.
>
> Giới hạn lớn nhất là chất lượng dữ liệu vận hành: cần nguồn đáng tin cho giá, lịch, sức chứa và thời điểm cập nhật. Các mô hình xếp hạng học máy hiện là thử nghiệm ngoại tuyến; dự báo ngập chưa đủ dữ liệu đối chứng; thông báo web push cần khóa VAPID và HTTPS; các cổng thanh toán và dịch vụ ngoài cần kiểm thử ở môi trường staging. Vì vậy, chúng em phân biệt rõ khả năng đã có trong mã với dịch vụ đã đủ điều kiện dùng thực tế.

## 9. Hướng phát triển và kết luận (12:15–13:30)

**Trên màn hình:** Lộ trình ưu tiên ngắn gọn.

**Lời nói:**

> Bước tiếp theo là bổ sung và duyệt dữ liệu của đối tác trong phạm vi pilot, đặc biệt là khung giờ, sức chứa, giá và bằng chứng nguồn. Sau đó nhóm sẽ thử nghiệm với người dùng thật để đo khả năng hoàn thành một hành trình, điểm họ phải sửa và mức hài lòng. Khi có dữ liệu đánh giá hợp lệ và sự đồng ý của người dùng, nhóm mới so sánh mô hình học máy với bộ quy tắc hiện tại để quyết định có triển khai hay không.
>
> Tóm lại, Local Explorer AI kết nối việc khám phá địa điểm với một lịch trình có kiểm tra thời gian, chi phí và nguồn dữ liệu. Bản hiện tại chứng minh được luồng sản phẩm và kiến trúc kỹ thuật. Giá trị thực tế của nó sẽ tăng khi dữ liệu từ các đơn vị cung cấp được xác minh và các tích hợp được kiểm thử đầy đủ. Em xin cảm ơn và sẵn sàng trả lời câu hỏi.

## Câu hỏi thường gặp và câu trả lời ngắn

**“AI ở đâu nếu hệ thống đang dùng bộ quy tắc?”**  
AI hỗ trợ hiểu yêu cầu, tìm kiếm và một số bước giải thích/tư vấn khi được cấu hình. Bộ lập lịch kiểm tra điều kiện cứng. Bộ xếp hạng sản xuất hiện dùng quy tắc vì thử nghiệm ML chưa có đủ nhãn người dùng thật để chứng minh chất lượng.

**“192 địa điểm có phải đều đặt được không?”**  
Không. Đó là số bản ghi công khai trong cấu hình demo lúc kiểm tra. Đặt chỗ thật yêu cầu dữ liệu, bằng chứng và trạng thái khung giờ hợp lệ; dữ liệu mô phỏng bị chặn khỏi luồng đặt thật.

**“Điểm mới so với bản đồ hoặc chatbot thông thường?”**  
Hệ thống liên kết địa điểm với hoạt động và khung giờ cụ thể, rồi kiểm tra thời gian, ngân sách, nhóm khách và tuyến trước khi đề xuất. Mỗi kết quả có trạng thái dữ liệu và lý do lựa chọn.

**“Điều gì còn thiếu để triển khai rộng?”**  
Cần đối tác cung cấp dữ liệu có thể xác minh, kiểm thử tích hợp ngoài và thanh toán ở staging, rồi đánh giá trải nghiệm với du khách thật. Sau pilot Quận 1 mới nên mở rộng khu vực.

## Tài liệu đối chiếu nội bộ

- `README.md`: phạm vi chức năng và trạng thái các tích hợp.
- `docs/main-integration-20261017.md`: trạng thái kiểm thử và triển khai ngày 17/10/2026.
- `docs/mlai-da-integration.md`: luồng hành trình, dữ liệu danh mục và các kiểm tra local.
- `docs/heritage-journey-pilot.md`: phạm vi pilot, nhãn demo và các giới hạn dữ liệu.
- `docs/experience-ranker-benchmark.md`: quyết định dùng bộ quy tắc thay cho ML production.
- `docs/bookings-and-payments.md`, `docs/meshy-integration.md`: giới hạn tích hợp bên ngoài.
