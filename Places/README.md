# Local Explorer AI — Thư mục Places

Thư mục `Places/` lưu trữ bảng tính khảo sát thực địa gốc về danh mục địa điểm du lịch, văn hóa, ẩm thực và workshop nghệ thuật tại TP. Hồ Chí Minh.

---

## 📄 Tập tin: `Sai_Gon_Places.xlsx`

| Thuộc tính | Chi tiết |
|---|---|
| **File** | `Places/Sai_Gon_Places.xlsx` |
| **Mục đích** | Bảng dữ liệu khảo sát thực địa gốc — danh sách địa điểm văn hóa, di sản, quán ăn tiêu biểu và workshop thủ công (trọng điểm Quận 1, Quận 3, Chợ Lớn) |
| **Định dạng** | Microsoft Excel (.xlsx) — dữ liệu gốc trước khi xử lý vào JSON |

### Các trường thuộc tính chính:

| Trường | Mô tả |
|---|---|
| `ext_id` | Mã định danh mở rộng của địa điểm |
| `name` | Tên địa danh (tiếng Việt có dấu) |
| `kind` | Thể loại: `heritage`, `culture`, `food`, `workshop`, `nature`, `relaxation` |
| `lat`, `lon` | Tọa độ địa lý GPS thực tế |
| `price_vnd` | Giá vé / chi phí tham khảo (VND) |
| `open_hours` | Khung giờ mở cửa hàng tuần |
| `outdoor` | Ngoài trời (`true`) hoặc trong nhà (`false`) |
| `tags` | Từ khóa đặc trưng phục vụ tìm kiếm & so khớp sở thích |
| `description` | Mô tả chi tiết lịch sử, kiến trúc, giá trị trải nghiệm |
| `photo_url` | Đường dẫn hình ảnh thực địa |
| `verified` | Trạng thái xác thực nguồn |
| `source` | Nguồn tham chiếu dữ liệu |

---

## 🔄 Quy trình Nhập & Phê duyệt Dữ liệu (Staging Workflow)

Theo nguyên tắc **fail-closed**, bảng tính này không được nạp trực tiếp vào database vận hành — phải qua quy trình Staging & kiểm duyệt:

### Bước 1: Nạp vào vùng đệm Staging
```powershell
cd apps/api

# Xem trước (dry-run) số bản ghi sẽ được import:
python -m scripts.import_place_candidates --dry-run

# Thực thi nạp vào bảng đệm place_import_candidates:
python -m scripts.import_place_candidates
```

### Bước 2: Kiểm duyệt & Phê duyệt (Moderation)
- Admin truy cập `/admin` (tab **Staging Places** hoặc API `/api/admin/staging-places/*`).
- Hệ thống tự động phát hiện trùng lặp bằng **Fuzzy String Similarity** (threshold ≥ 0.88).
- Kiểm tra tính hợp lệ tọa độ GPS và giờ mở cửa.
- Phê duyệt đơn lẻ hoặc hàng loạt → chuyển vào bảng `pois` chính thức.

### Bước 3: Làm giàu dữ liệu (Enrichment)
```powershell
# Thu thập và gắn ảnh thực địa vào danh mục:
python scripts/crawl_district1_places.py
python scripts/download_district1_photos.py
python scripts/attach_district1_photos_to_catalog.py

# Kiểm tra toàn vẹn dữ liệu:
python scripts/deep_check_excel.py
python scripts/check_places_detail.py
```

---

## 🔗 Liên kết với Tài nguyên Khác

| Tài nguyên | Đường dẫn |
|---|---|
| Danh mục JSON hoàn chỉnh | `data/sai_gon_places.json` |
| Giao diện hiển thị người dùng | Tuyến `/places` và `/places/:id` |
| 3D Landmark Viewer | Tuyến `/map-3d` — mô hình GLB landmark |
| Scripts xử lý | `scripts/` — crawl, download, attach, generate, check |
| API Backend | `apps/api/app/api/routes/catalog.py` — `/api/pois`, `/api/experiences` |
