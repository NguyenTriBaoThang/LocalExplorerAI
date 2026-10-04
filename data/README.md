# Local Explorer AI — Dữ liệu Dự án & Thư mục Data

Thư mục `data/` chứa toàn bộ dữ liệu mô phỏng, dữ liệu thực nghiệm và tài liệu nguồn phục vụ cho quá trình phát triển, kiểm thử và huấn luyện mô hình học máy của hệ thống **Local Explorer AI**.

---

## 1. Dữ liệu Mô phỏng Demo (Demonstration Data)

Tập dữ liệu demo được sinh tự động thông qua script nạp cơ sở dữ liệu `apps/api/scripts/seed_db.py`.

### Đặc điểm dữ liệu mô phỏng:
- **10 Địa điểm (POI) TP. Hồ Chí Minh mô phỏng**: Tọa độ thực tế tại Quận 1 và khu vực trung tâm, được gắn cờ `verification_status = 'simulated'`.
- **01 Nhà cung cấp đối tác mẫu (Synthetic Provider)**: Dùng để kiểm thử giao diện Provider Portal và phân quyền sở hữu địa điểm.
- **10 Hoạt động trải nghiệm (Experiences)**: Đa dạng thể loại (*Thủ công mỹ nghệ*, *Ẩm thực Nam Bộ*, *Văn hóa di sản*, *Thiên nhiên phố thị*, *Thư giãn*), có phân định hoạt động trong nhà (`is_indoor`) và thực hành (`is_hands_on`).
- **Khung giờ trải nghiệm (Slots) 30 ngày**: 3 ca mỗi ngày (09:00, 11:30, 14:30) với các trạng thái thực tế:
  - `open`: Còn chỗ trống (mặc định 8/10 chỗ).
  - `full`: Đã kín chỗ (0 chỗ trống).
  - `tentative`: Cần liên hệ xác nhận trước (chưa chốt sức chứa).
- **Tài khoản nhà phát triển mặc định (khi `APP_ENV=development`)**:
  - Quản trị viên (`admin`): `admin@localexplorer.ai` (hoặc cấu hình từ `.env`).
  - Du khách (`traveler`): `traveler@localexplorer.ai` (hoặc cấu hình từ `.env`).

> [!IMPORTANT]
> **Ranh giới Dữ liệu Mô phỏng & Đặt chỗ Thực tế:**
> Mọi dữ liệu do seed script sinh ra đều mang trạng thái `simulated`. Hệ thống áp dụng cơ chế bảo vệ nghiêm ngặt (*fail-closed*): **Dữ liệu `simulated` tuyệt đối không thể đặt chỗ thanh toán thật** qua VNPay/MoMo. Để thử nghiệm quy trình đặt chỗ thực tế, dữ liệu phải được khởi tạo từ đối tác thật và được Quản trị viên duyệt xác minh (`verified`) kèm tài liệu minh chứng (`Evidence`) còn hiệu lực.

### Hướng dẫn chạy nạp dữ liệu:
Từ thư mục `apps/api` (sau khi đã áp dụng toàn bộ migration `alembic upgrade head`):
```powershell
python -m scripts.seed_db
```
*Script an toàn khi chạy lại nhiều lần (idempotent): Nếu đã có dữ liệu trong database, script sẽ giữ nguyên dữ liệu hiện có.*

---

## 2. Báo cáo Ngập lụt Lịch sử TP.HCM — Dữ liệu Thô (`data/raw/`)

- **Tập tin**: [`data/raw/hcmc_flood_reports_2002_2026.csv`](file:///g:/GITHUB/LoaclExplorerAI/data/raw/hcmc_flood_reports_2002_2026.csv)
- **Nguồn gốc**: Hardy, Sebastien; Radziute, Gintarė (2026), *Historical database of urban flooding in Ho Chi Minh City, Vietnam (2002–2026)*, DataSuds, DOI: [10.23708/8Y16HU](https://doi.org/10.23708/8Y16HU).
- **Quy mô**: 425 hàng quan trắc, 22 cột thuộc tính gốc, mã hóa UTF-8.
- **Bản quyền**: CC BY-NC 4.0 (Phi thương mại, ghi nhận tác giả).
- Xem chi tiết tại [data/raw/README.md](file:///g:/GITHUB/LoaclExplorerAI/data/raw/README.md).

---

## 3. Nhãn Thực nghiệm Xuất hiện Báo cáo Ngập (`data/experimental/`)

- **Tập tin**: [`data/experimental/flood_training_weak_labels.csv`](file:///g:/GITHUB/LoaclExplorerAI/data/experimental/flood_training_weak_labels.csv)
- **Mục đích**: Tập dữ liệu thực nghiệm nghiên cứu xác suất xuất hiện báo cáo ngập công khai theo tháng và địa điểm (Weak pseudo-negatives sampling).
- **Quy mô**: 662 hàng cân bằng (331 quan sát dương bản + 331 giả định âm bản có trọng số).
- **Script tái tạo**: `node scripts/build_flood_report_weak_labels.mjs`
- Xem chi tiết tại [data/experimental/README.md](file:///g:/GITHUB/LoaclExplorerAI/data/experimental/README.md).

---

## 4. Liên kết với các Mô hình Học máy (`models/`)

Dữ liệu trong thư mục này được liên kết trực tiếp với các mô hình AI/ML chạy cục bộ:
1. `models/ai-ranker/`: Sử dụng đặc trưng trải nghiệm, thời tiết và người dùng để huấn luyện mô hình XGBRanker (NDCG@5 = 0.9516).
2. `models/flood-risk/`: Mô hình Scikit-learn đánh giá rủi ro ngập lụt đô thị khi lập tuyến đường di chuyển.
3. `models/e5/`: Mô hình vector Multilingual E5 phục vụ tìm kiếm ngữ nghĩa văn bản tiếng Việt cho các hoạt động trong catalog.
