# Dữ liệu nguồn thô

File ở đây là nguồn hoặc candidate để đối soát, không tự động là dữ liệu vận hành.

## Nội dung hiện có

- district1_osm_places.json: candidate OSM được thu thập theo polygon pilot lịch sử Quận 1. Không phải danh sách đầy đủ mọi địa điểm, cũng không xác nhận venue còn hoạt động/giá/giờ/slot.
- district1_osm_photos_manifest.json và district1_osm_places_with_local_photos.json: metadata ảnh/candidate ảnh. Chỉ sử dụng ảnh nếu truy được trang nguồn, giấy phép và credit cho từng file; không bảo đảm mọi địa điểm có ảnh.
- Sai_Gon_Places.xlsx: workbook do dự án cung cấp. 177 dòng cần rà soát nguồn và bằng chứng theo trường trước khi duyệt.
- hcmc_flood_reports_2002_2026.csv: chuyển đổi báo cáo lịch sử từ DataSuds, không có negative dry windows hay road-edge labels cần thiết cho dự báo ngập.
- flood_training.csv: không được mặc định là tập train hợp lệ. Kiểm tra schema/provenance; không tổng hợp nhãn không ngập hay thời gian quan sát.

## Xử lý và cấp phép

Giữ nguyên bản nguồn để tái lập, ghi hash và ngày thu thập ở manifest/báo cáo. Tuân thủ điều khoản/giấy phép của nhà cung cấp. Dữ liệu OSM yêu cầu attribution và nghĩa vụ ODbL tương ứng. Ảnh Wikimedia có license riêng từng file.

Chi tiết về báo cáo ngập: [mô tả bộ dữ liệu](../../docs/ml-training-and-data.md). Chi tiết workflow nhập POI: [place import staging](../../docs/place-import-staging.md)
