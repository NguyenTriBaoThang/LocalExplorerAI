# Local Explorer AI — Thư mục Places

Thư mục `Places/` lưu trữ bảng tính nguồn về danh mục các địa điểm du lịch, văn hóa, ẩm thực và workshop nghệ thuật tại TP. Hồ Chí Minh.

---

## 📄 Tập tin: `Sai_Gon_Places.xlsx`

- **Tên tệp**: [`Places/Sai_Gon_Places.xlsx`](file:///g:/GITHUB/LoaclExplorerAI/Places/Sai_Gon_Places.xlsx)
- **Mục đích**: Bảng dữ liệu khảo sát thực địa gốc ghi nhận danh sách các điểm đến văn hóa, di sản, quán ăn tiêu biểu và workshop thủ công (tập trung trọng điểm tại Quận 1, Quận 3 và khu vực Chợ Lớn).
- **Các trường thuộc tính chính**:
  - `ext_id`: Mã định danh mở rộng của địa điểm.
  - `name`: Tên địa danh (tiếng Việt có dấu).
  - `kind`: Thể loại địa điểm (`heritage`, `culture`, `food`, `workshop`, `nature`, `relaxation`).
  - `lat`, `lon`: Tọa độ địa lý GPS thực tế.
  - `price_vnd`: Giá vé hoặc chi phí tham khảo (VND).
  - `open_hours`: Khung giờ mở cửa hoạt động.
  - `outdoor`: Phân định không gian ngoài trời (`true`) hoặc trong nhà (`false`).
  - `tags`: Từ khóa đặc trưng phục vụ tìm kiếm và so khớp sở thích du khách.
  - `description`: Mô tả chi tiết về lịch sử, kiến trúc và giá trị trải nghiệm.
  - `photo_url`: Đường dẫn hình ảnh thực địa.
  - `verified`: Trạng thái xác thực nguồn.
  - `source`: Nguồn tham chiếu dữ liệu.

---

## 🔄 Quy trình Nhập & Phê duyệt Dữ liệu (Staging Workflow)

Để bảo đảm nguyên tắc an toàn dữ liệu (*Fail-closed*), bảng tính này không được nạp trực tiếp vào cơ sở dữ liệu vận hành mà phải đi qua quy trình Staging và kiểm duyệt:

1. **Nạp dữ liệu vào vùng đệm Staging**:
   ```powershell
   cd apps/api
   # Chạy thử nghiệm xem trước số lượng bản ghi:
   python -m scripts.import_place_candidates --dry-run

   # Thực thi nạp vào bảng đệm place_import_candidates:
   python -m scripts.import_place_candidates
   ```

2. **Kiểm duyệt & Phê duyệt (Moderation)**:
   - Quản trị viên truy cập trang `/admin` (tab *Staging Places* hoặc qua API `/api/admin/staging-places/*`).
   - Kiểm tra tính hợp lệ của tọa độ, trùng lặp tên bằng thuật toán so khớp chuỗi mờ (Fuzzy string similarity).
   - Bấm phê duyệt để chuyển các địa điểm đạt chuẩn vào bảng chính thức `pois`.

---

## 🔗 Liên kết với các Tài nguyên Khác

- **Dữ liệu JSON hoàn chỉnh**: [`data/sai_gon_places.json`](file:///g:/GITHUB/LoaclExplorerAI/data/sai_gon_places.json)
- **Giao diện hiển thị người dùng**: Tuyến đường `/places` và `/places/:id` trên ứng dụng Web Frontend.
- **Mô hình 3D Landmark tương ứng**: Tích hợp với Trình xem 3D Landmark `/map-3d`.
