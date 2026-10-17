# Tích hợp phiên bản MLAI_DA — 16/10/2026

Nguồn: `D:\MyProject\MLAI_DA`, commit nền `a76bf0d40bc3ebe24ed1bdc1a35651db5fad9363`, có 43 file đã sửa và 45 file mới chưa commit.

Đích: `D:\MyProject\MLAI_DEMO_T7\LocalExplorerAI`, commit nền `b0e0248ac84190c86375f0c907580122f9064b89`.

Commit nền của nguồn là tổ tiên của bản clone. Tích hợp bằng cách ghép ba chiều các thay đổi trong thư mục làm việc của nguồn, giữ các cải tiến đã có ở bản clone. Không reset nhánh hay sao chép đè toàn bộ repository.

## Phần có ở MLAI_DA đã bổ sung

- Luồng hành trình liên kết Chat, Map 3D, Khám phá và Planner: giữ điều kiện chuyến đi, hội thoại trong tab và tối đa sáu trải nghiệm đã chọn; tách trạng thái theo tài khoản.
- Đối chiếu mô hình 3D với địa điểm theo ID/tên và tọa độ; hiển thị nguồn, trạng thái xác minh, phạm vi pilot và liên kết tới trải nghiệm. Giữ hiệu chỉnh mô hình riêng của nguồn.
- Bộ lọc theo ngày, giờ về, số người, tổng ngân sách nhóm, địa điểm và nguồn xác minh. Giữ bộ lọc danh thắng/tag và đánh giá của bản clone.
- Gợi ý tối đa năm phương án lịch trình khả thi, kiểm tra lại phương án khi chọn, giải thích khi không thể xếp lịch và prompt `ITINERARY_RANKER`. Có xếp hạng bổ sung qua Gemini khi cấu hình phù hợp.
- Lựa chọn riêng cho cá nhân hóa, dữ liệu huấn luyện và admin xem lịch sử Khám phá; ghi nhận tương tác theo consent, thu hồi từng mục đích và xóa tương tác khi tắt tất cả.
- Mô hình hành vi thử nghiệm, script xuất dữ liệu đã khử định danh và script huấn luyện. Script xuất dữ liệu dùng `APP_SIGNING_SECRET` của hệ thống mới, thay cho thuộc tính `auth_secret` đã bỏ.
- Lịch sử lịch trình, đặt chỗ, đánh giá và Khám phá của khách hàng; kiểm tra consent trước khi hiển thị hành vi và ghi nhật ký mỗi lần admin xem.
- 15 ảnh địa điểm TP.HCM cùng manifest nguồn ảnh; các script đồng bộ danh mục, tải ảnh, tạo trải nghiệm demo và tài liệu của nguồn.
- Điều chỉnh khả năng routing Goong, bộ phân tích chat ngoại tuyến và thông báo lỗi chi tiết.

## Phần đã điều chỉnh để tương thích bản clone

- Chuyển lịch sử khách hàng từ `apps/web/src/pages/AdminPage.tsx` cũ sang **Portal → Người dùng → chọn tài khoản → Xem lịch sử khách hàng**. Giữ tìm kiếm, phân trang, phân quyền và quản lý phiên đăng nhập của Portal mới.
- Dùng `require_user` và RBAC mới cho API gợi ý/lịch sử. Quyền `recommendations:use` mặc định chỉ cấp cho vai trò du khách; lịch sử khách hàng yêu cầu `admin:users`. Không mở rộng vai trò của tài khoản hiện có.
- Giữ bảo vệ CSRF, xác thực RS256, MFA, email verification, cookie/session, analytics, nội dung website và review của bản mới.
- Giữ ba migration của nguồn và thêm `0018_merge_behavior_portal` để nối nhánh recommendation với `0017_merge_main_and_portal`, tạo một head duy nhất và khai báo quyền mới. PostgreSQL local đã được nâng cấp đến head này.
- Không đưa lại yêu cầu `AUTH_SECRET` cũ vào Docker production; cấu hình hiện hành đã có `APP_SIGNING_SECRET`.

## Phạm vi dữ liệu và vận hành

Thư mục mã nguồn MLAI_DA được giữ nguyên. Không sao chép `.env`, khóa tích hợp, dữ liệu người dùng, thư mục dependencies hoặc output huấn luyện tạm từ bản nguồn. Không chạy script seed và không tự bật đồng ý thu thập dữ liệu.

Sau yêu cầu bổ sung dữ liệu, đã nhập danh mục từ `MLAI_DA/local_explorer.db` sang PostgreSQL trong một transaction: **202 địa điểm, 202 trải nghiệm, 1.296 khung giờ, 4 nhà cung cấp, 30 bản ghi nguồn tham khảo, 1 lô nhập và 177 ứng viên địa điểm**. Giữ nguyên các tài khoản và nhà cung cấp đã có ở database đích. Chuyển 85 ID quá dài sang UUID xác định và cập nhật liên kết tương ứng; JSON, datetime và tọa độ được chuyển sang kiểu dữ liệu PostgreSQL. Cả 202 geometry hợp lệ, SRID 4326. Đã đối chiếu SHA-256 của 22 ảnh local trong source, public và bản build web. Portal local chuyển tiếp đường dẫn ảnh địa điểm sang web.

Portal quản trị hiển thị đủ 202 địa điểm. Sau yêu cầu tương thích dữ liệu cũ, script `apps/api/scripts/adapt_legacy_demo_catalog.py` đã chuyển 15 POI và 15 trải nghiệm có nhãn `verified` nhưng thiếu evidence hợp lệ sang `simulated`, giữ trạng thái gốc trong `details.legacy_import`; không sửa 30 evidence `approved` thành nguồn đã xác minh. 177 bản ghi demo có sẵn tiếp tục giữ chế độ demo; 10 fixture `unverified` không đưa ra công khai. Bổ sung `source_url`, `opening_hours`, `ticket_info`, `tags` từ metadata cũ và gắn ảnh local có credit cho 37 địa điểm theo tên khớp; URL ảnh cũ được lưu lại.

Cấu hình `.env` local đã bật `REAL_DATA_ONLY=false`; mặc định trong mã và cấu hình mẫu vẫn giữ chế độ dữ liệu thật. API công khai trả **192 POI và 192 trải nghiệm**, trong đó 138 trải nghiệm thuộc pilot. Trang Khám phá cần bật **Thử demo**; với 17/10/2026 09:00–16:00, 2 người, ngân sách 1.200.000 đồng, trình duyệt hiển thị 6 trải nghiệm phù hợp. API lập lịch demo 08:00–18:00, 2 người, ngân sách 1.000.000 đồng tạo được lịch trình 3 điểm. Khung giờ không được sinh thêm: 15 trải nghiệm cũ có nhãn verified vốn có 0 slot; nguồn demo có 396 slot, 900 slot còn lại thuộc fixture ẩn. Booking thật vẫn yêu cầu xác minh đầy đủ và chặn dữ liệu mô phỏng.

Kiểm thử tương thích và sourced catalog: **4 passed**. Chạy lại script không đổi thêm bản ghi (idempotent). Bản sao lưu trước chuyển đổi: `.local-app/place-data-import-20261016/database-before-compatibility.dump` ngoài repository; kết quả API: `compatibility-check.json` cùng thư mục.

Script nhập và hồ sơ kiểm tra nằm ngoài Git: `D:\MyProject\MLAI_DEMO_T7\.local-app\import-place-data.py` và `place-data-import-20261016/result.json`. Bản sao lưu trước khi nhập: `place-data-import-20261016/database-before-catalog.dump`. Mô hình hành vi là thử nghiệm trên dữ liệu tạo sẵn, không phải mô hình production; API bên ngoài vẫn cần khóa hợp lệ.

Các file trước khi ghép và manifest so sánh nằm tại `D:\MyProject\MLAI_DEMO_T7\.local-app\merge-20261016\before` và `report.json`. Bản sao lưu PostgreSQL trước migration là `database-before-merge.dump` trong cùng thư mục. Đây là dữ liệu local ngoài Git; bản dump chứa dữ liệu tài khoản nên không đưa lên repository.

Web chạy tại `http://localhost:8080`, Portal tại `http://localhost:5174`. Web vẫn được phục vụ qua tunnel đã có. Script khởi động: `D:\MyProject\MLAI_DEMO_T7\.local-app\start-local.ps1`.

## Kiểm chứng

- Kiểm thử API: **355 passed** trong 122,32 giây, với SQLite tạm; gồm RBAC, auth, planner, journey, suggestion, consent, lịch sử khách hàng và cấu hình script xuất dữ liệu.
- TypeScript và Vite build cho cả web và Portal; còn cảnh báo bundle lớn của Vite.
- Ruff theo bộ lỗi nghiêm trọng của CI và `git diff --check`.
- PostgreSQL migration head, API health, journey, đăng nhập admin, dashboard và lịch sử khách hàng local.
- Trình duyệt: thanh hành trình và bộ lọc Khám phá; mục lịch sử khách hàng trong Portal, có trạng thái consent và thông báo dữ liệu trống.
- Artifact XGBoost thử nghiệm nạp thành công, đúng 17 đặc trưng.

Kết quả cuối: 48 file tracked thay đổi và 49 file mới. Danh sách chi tiết nằm ở `D:\MyProject\MLAI_DEMO_T7\.local-app\merge-20261016\final-files.json`.

Thay đổi được để trong working tree để xem xét; chưa commit hoặc push lên GitHub.
