# Local Explorer AI — Thư mục Data

Thư mục `data/` chứa toàn bộ dữ liệu mô phỏng demo, dữ liệu thực nghiệm nghiên cứu và tập dữ liệu huấn luyện mô hình học máy của hệ thống **Local Explorer AI**.

---

## 1. Dữ liệu Mô phỏng Demo

Sinh tự động qua script `apps/api/scripts/seed_db.py`.

### Nội dung dữ liệu mô phỏng:
- **10 POI (Địa điểm) Sài Gòn mô phỏng**: Tọa độ thực tế Quận 1 & trung tâm, gắn cờ `verification_status = 'simulated'`.
- **01 Provider mẫu (Synthetic)**: Kiểm thử Provider Portal & phân quyền sở hữu.
- **10 Hoạt động trải nghiệm (Experiences)**: Đa dạng — thủ công mỹ nghệ, ẩm thực Nam Bộ, văn hóa di sản, thiên nhiên phố thị, thư giãn.
- **Slots 30 ngày**: 3 ca/ngày (09:00, 11:30, 14:30) với trạng thái `open` / `full` / `tentative`.
- **Tài khoản dev** (khi `APP_ENV=development`):
  - Admin: `admin@localexplorer.ai`
  - Traveler: `traveler@localexplorer.ai`

> [!IMPORTANT]
> **Ranh giới Dữ liệu Mô phỏng:** Dữ liệu `simulated` **tuyệt đối không thể đặt chỗ/thanh toán thật** qua VNPay/MoMo. Để thử nghiệm đặt chỗ thực, dữ liệu phải được khởi tạo từ đối tác thật và được Admin duyệt `verified` kèm Evidence còn hiệu lực.

```powershell
# Từ apps/api (sau alembic upgrade head):
python -m scripts.seed_db
```
*Script an toàn khi chạy lại nhiều lần (idempotent).*

---

## 2. Báo cáo Ngập lụt Lịch sử TP.HCM — `data/raw/`

| Thuộc tính | Chi tiết |
|---|---|
| **File** | `data/raw/hcmc_flood_reports_2002_2026.csv` |
| **Nguồn** | Hardy, Sebastien; Radziute, Gintarė (2026). *Historical database of urban flooding in Ho Chi Minh City, Vietnam (2002–2026)*. DataSuds. DOI: [10.23708/8Y16HU](https://doi.org/10.23708/8Y16HU) |
| **Quy mô** | 425 quan trắc, 22 cột thuộc tính gốc, UTF-8 |
| **Bản quyền** | CC BY-NC 4.0 (Phi thương mại, ghi nhận tác giả) |
| **MD5** | `39de82a4ff2401e527a6dc5be13b25f0` (verified by `download_hcmc_flood_reports.py`) |

> [!WARNING]
> File này là dữ liệu thô. **Chưa sẵn sàng** nạp trực tiếp vào notebook huấn luyện Flood Colab — thiếu dữ liệu âm bản đối chứng và `edge_id` của dự án.

Xem chi tiết: [data/raw/README.md](./raw/README.md)

---

## 3. Nhãn Thực nghiệm Xuất hiện Báo cáo Ngập — `data/experimental/`

| Thuộc tính | Chi tiết |
|---|---|
| **File** | `data/experimental/flood_training_weak_labels.csv` |
| **Mục đích** | Nghiên cứu **xác suất xuất hiện bản ghi báo cáo ngập công khai** theo tháng & địa danh — KHÔNG dự đoán ngập vật lý tuyến đường |
| **Quy mô** | 662 hàng cân bằng (331 dương bản + 331 âm bản giả định có trọng số sampling) |
| **Script tái tạo** | `node scripts/build_flood_report_weak_labels.mjs` |

Xem chi tiết: [data/experimental/README.md](./experimental/README.md)

---

## 4. Tập Dữ liệu Xếp hạng Trải nghiệm — `data/experimental/ranking/`

| File | Mô tả |
|---|---|
| `data/experimental/ranking/ranking_candidates_labeled.csv` | 3,828 hàng OSM — dữ liệu yếu cho Ranker training |
| `data/dataset_ranking_tphcm.csv` | Kịch bản truy vấn & ứng viên với đặc trưng ngữ cảnh (thời gian, chi phí, thời tiết, sở thích) |
| `data/dataset_ranking_tphcm.jsonl` | JSON Lines cho pipeline huấn luyện nhanh |
| `data/training/experience_ranker_verified_template.csv` | Biểu mẫu chuẩn thu thập nhãn xếp hạng từ chuyên gia (Human preference verified) |

**Kết quả model**: XGBoost/LightGBM Ranker `ranker-features-v2` — **NDCG@5 = 0.9516**

Xem chi tiết: [data/experimental/ranking/README.md](./experimental/ranking/README.md)

---

## 5. Danh mục Địa điểm Du lịch Sài Gòn & Quận 1

| File | Mô tả |
|---|---|
| `data/sai_gon_places.json` | Danh mục JSON hoàn chỉnh các địa điểm văn hóa, lịch sử, ẩm thực, workshop tại TP.HCM (trọng điểm Quận 1, Quận 3, Chợ Lớn) |
| `Places/Sai_Gon_Places.xlsx` | Bảng tính khảo sát thực địa gốc |

**Mỗi địa điểm bao gồm**: Tên, loại (`kind`), địa chỉ chuẩn hóa, tọa độ GPS, giờ mở cửa, giá vé, in/outdoor, tags, mô tả lịch sử/kiến trúc, ảnh thực địa, đánh giá từ du khách.

**Quy trình thu thập**:
```text
crawl_district1_places.py → download_district1_photos.py → attach_district1_photos_to_catalog.py
→ generate_full_places_data.py → apply_enriched_places.py
→ deep_check_excel.py / check_places_detail.py (kiểm tra toàn vẹn)
```

---

## 6. Dữ liệu Hiệu chuẩn 3D Digital Twin — `models_3d/`

| File | Mô tả |
|---|---|
| `models_3d/calibration.json` | Thông số hiệu chuẩn không gian thực địa cho 3D Landmark Viewer |

**Ví dụ**: `nhathoducba` (Nhà thờ Đức Bà Sài Gòn) — tọa độ (10.7797, 106.6990), heading `312.5°`, cao độ `0.0m`, scale `77.5m`, POI ID `exp-sai-gon-nha-tho-uc-ba-sai-gon`.

**Cập nhật qua API**: `PUT /api/models-3d/{model_id}/calibration` (Admin).

---

## 7. Vùng Đệm Nhập Địa Điểm (Place Import Staging)

- **Migration**: `0010_place_import_staging` — bảng `place_import_candidates`
- **API**: `/api/admin/staging-places/*`
- **Quy trình**:
  1. Import XLSX/JSON/CSV vào vùng đệm: `python -m scripts.import_place_candidates --dry-run` → `python -m scripts.import_place_candidates`
  2. Kiểm duyệt tại trang `/admin` (tab Staging Places): validate tọa độ, fuzzy duplicate detection
  3. Phê duyệt → chuyển vào bảng `pois` chính thức

---

## 8. Cơ chế Cách ly Dữ liệu Mô phỏng

```powershell
# Xem trước (thống kê số lượng, không thay đổi):
python -m scripts.quarantine_simulated_data

# Áp dụng cách ly (ẩn dữ liệu simulated):
python -m scripts.quarantine_simulated_data --apply
```
*Mọi thao tác được ghi vào bảng `audit_logs`.*

---

## 🔗 Liên kết

- **Mô hình ML sử dụng dữ liệu này**: [`models/`](../models/README.md)
- **Scripts xử lý dữ liệu**: [`scripts/`](../scripts/README.md)
- **API Backend**: [`apps/api/`](../apps/api/README.md)
