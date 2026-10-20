# Dữ liệu danh mục để chạy trên máy khác

Snapshot ngày 20/10/2026: 202 địa điểm, 202 trải nghiệm, 1.296 khung giờ lịch sử,
177 địa điểm AI Chat, 1 điểm đến, 5 hồ sơ cơ sở (đã loại thông tin liên hệ/quản trị)
và 4 câu chuyện landmark đã xuất bản.

## Cài trên database mới

1. Cài dependencies theo README của API, cấu hình DATABASE_URL cho PostgreSQL + PostGIS.
2. Từ `apps/api`:

   ```powershell
   alembic upgrade head
   python -m scripts.portable_catalog import ../../data/portable/catalog.json
   ```

3. Tạo tài khoản của máy mới bằng quy trình quản trị của dự án. Cấu hình API key riêng
   cho Goong, Gemini, Meshy và các tích hợp muốn sử dụng.
4. Chạy API, web và Portal theo README.

Lệnh import chạy trong một transaction, bỏ qua khóa đã tồn tại và không ghi đè
dữ liệu máy đích. Muốn giống snapshot, sử dụng database mới.
Không gọi `seed_db` cũ để ghi đè hoặc tự xác minh dữ liệu.

## Phạm vi và giới hạn

- Đây là dữ liệu tham khảo, không phải dữ liệu đã xác minh để bán dịch vụ.
  Giữ nguyên nhãn simulated/unverified của địa điểm và trải nghiệm.
- Các khung giờ giữ ngày gốc, chuyển tentative với 0 chỗ và bỏ xác nhận.
  Hồ sơ cơ sở nhập vào ở trạng thái pending/inactive, không có quyền Portal.
  Máy mới không có slot hoạt động để đặt chỗ thật cho đến khi được cập nhật/xác minh.
- Không chứa users, password hash, token, phiên đăng nhập, integration_secrets,
  hội thoại/lịch trình cá nhân, nhật ký, thanh toán, dữ liệu xét duyệt hoặc bằng chứng
  xác minh. Không chuyển quyền xác minh của máy cũ sang máy mới.
- Không chứa tác vụ Meshy: cả 5 mô hình tại thời điểm snapshot là bản nháp riêng tư.
  Chuyển bằng gói riêng nếu chủ dữ liệu cần giữ cả bản nháp.
- Ảnh/3D là file độc lập với database. Xem `assets-manifest.json` để biết các file cần
  chuyển và SHA-256; một số file đã có trong repo, số khác phải chuyển riêng.
  Không thay link ảnh ngoài bằng ảnh minh họa và giữ nguồn/giấy phép gốc.
- Clone + import chỉ khôi phục danh mục. Để có đủ file 3D, bản nháp và dữ liệu vận hành,
  cần gói chuyển riêng; không đẩy SQL dump hay `.env` thật lên Git.

## Xuất lại danh mục

```powershell
python -m scripts.portable_catalog export ../../data/portable/catalog-new.json
```

Exporter chỉ chọn các bảng/trường được liệt kê rõ trong code và từ chối mẫu API key
phổ biến. Luôn rà soát nội dung tự do trước khi chia sẻ. Đây không phải công cụ sao lưu
toàn bộ database.
