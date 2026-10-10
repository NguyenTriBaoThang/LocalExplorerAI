# Thu thập và xem catalog địa điểm khu vực pilot Quận 1

`scripts/crawl_district1_places.py` truy vấn các POI có tên trên OpenStreetMap qua Overpass, rồi giữ các đối tượng có tọa độ đại diện nằm trong polygon pilot Quận 1 lịch sử của dự án. Đây là công cụ thu thập dữ liệu nguồn, không phải xác nhận “đầy đủ mọi cơ sở” ngoài thực tế.

## Chạy thu thập

Từ thư mục gốc repo:

```powershell
& ".\apps\api\.venv\Scripts\python.exe" scripts/crawl_district1_places.py --output data/raw/district1_osm_places.json
```

Mặc định công cụ tìm ảnh được liên kết rõ ràng qua `wikimedia_commons`, `image` kiểu Commons hoặc Wikidata P18. Bản ghi ảnh được lưu cùng URL trang tệp, tên giấy phép, URL giấy phép và ghi công. Nếu không tìm được ảnh phù hợp có metadata giấy phép, dữ liệu ghi `photo_status=not_found`; ứng dụng không thay bằng ảnh minh họa. Có thể bỏ qua tra ảnh khi cần chạy nhanh bằng `--skip-photos`.

Đưa JSON vào hàng chờ admin (không xuất bản POI tự động):

```powershell
Set-Location apps/api
& ".\.venv\Scripts\python.exe" scripts/import_place_candidates.py --source ../../data/raw/district1_osm_places.json --worksheet OSM --dry-run
& ".\.venv\Scripts\python.exe" scripts/import_place_candidates.py --source ../../data/raw/district1_osm_places.json --worksheet OSM
```

Admin kiểm tra từng nguồn và địa chỉ, bổ sung bằng chứng nếu cần, gửi duyệt. Việc crawl không tạo giá, trải nghiệm, lịch mở cửa, slot, sức chứa hay trạng thái xác minh. Sau khi POI được đưa vào catalog, trang `/places` liệt kê địa điểm; chọn một mục để xem `/places/{id}` gồm ảnh có attribution, địa chỉ, giờ mở cửa/website/liên hệ/phí nếu nguồn ghi nhận, tọa độ, dữ liệu OSM thô, nguồn, thời điểm ghi nhận và các trải nghiệm đã gắn với POI.

Nếu nâng schema từ bản cũ:

```powershell
Set-Location apps/api
& ".\.venv\Scripts\alembic.exe" upgrade head
```

## Nguồn, giới hạn và giấy phép

- Địa điểm/tag/tọa độ: [OpenStreetMap](https://www.openstreetmap.org/copyright), dữ liệu ODbL-1.0; giao diện phải giữ attribution “© OpenStreetMap contributors”.
- Ảnh: Wikimedia Commons API. Từng tệp có thể có giấy phép khác nhau; ứng dụng lưu và hiển thị giấy phép/ghi công từ metadata của tệp, không mặc định ảnh nào cũng cùng một license.
- Dữ liệu phụ thuộc vào mức độ cập nhật/có tag của OSM và Wikidata. Polygon là ranh pilot Quận 1 lịch sử theo cấu hình repo, không biểu thị đơn vị hành chính hiện hành. Các đối tượng dạng way/relation được lọc theo tọa độ center từ Overpass, không phải cắt hình học chính xác theo polygon.
- “Tất cả địa điểm” chỉ có thể diễn đạt trung thực là tất cả bản ghi phù hợp truy vấn nguồn tại thời điểm crawl; không cam kết mọi cửa hàng/cơ sở có thật đều được bản đồ cộng đồng ghi lại.
- Ảnh thiếu link nguồn hoặc license không được thêm vào danh sách ảnh hiển thị. Trường vắng trong nguồn được để trống/chưa có, không suy diễn.
- Chưa thể coi OSM listing là xác nhận trực tiếp từ cơ sở. Booking, giá, giờ/slot và sức chứa vẫn cần xác minh riêng với đơn vị vận hành.
