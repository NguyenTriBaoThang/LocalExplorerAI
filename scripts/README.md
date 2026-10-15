# Local Explorer AI — Thư mục Scripts Hệ thống

Thư mục `scripts/` chứa toàn bộ kịch bản tự động hóa phục vụ thu thập dữ liệu, xử lý hình ảnh, huấn luyện mô hình học máy, vận hành CSDL và kiểm thử hệ thống cho **Local Explorer AI**.

---

## 🗂️ Phân loại Scripts

### 1. Thu thập, Xử lý & Làm giàu Dữ liệu Địa danh Sài Gòn

| Script | Ngôn ngữ | Chức năng |
|---|---|---|
| `crawl_district1_places.py` | Python | Thu thập địa điểm văn hóa, lịch sử, ẩm thực Quận 1 từ nguồn mở |
| `download_district1_photos.py` | Python | Tải hình ảnh thực địa chất lượng cao cho các địa điểm Quận 1 |
| `attach_district1_photos_to_catalog.py` | Python | Gắn đường dẫn ảnh đã tải vào `data/sai_gon_places.json` |
| `generate_full_places_data.py` | Python | Hợp nhất dữ liệu đa nguồn thành file JSON hoàn chỉnh |
| `saigon_places_data_part1.py` / `part2.py` | Python | Khối dữ liệu bộ phận danh mục địa danh Sài Gòn |
| `apply_enriched_places.py` | Python | Áp dụng trường bổ sung (rating, review, open_hours) vào danh mục |
| `analyze_places_excel.py` | Python | Phân tích cấu trúc `Places/Sai_Gon_Places.xlsx` |
| `deep_check_excel.py` | Python | Kiểm tra chuyên sâu tính hợp lệ và trường thiếu trong Excel |
| `check_places_detail.py` | Python | Kiểm tra tính nhất quán danh mục JSON so với thực tế |
| `dump_sheets.py` / `dump_indexed.py` | Python | Xuất sheet và chỉ mục bảng tính để đối soát |

### 2. Huấn luyện Mô hình Học máy

| Script | Lệnh mẫu | Chức năng |
|---|---|---|
| `train_experience_ranker.py` | `python scripts/train_experience_ranker.py --mode weak_label` | Huấn luyện XGBoost & LightGBM Ranker (`ranker-features-v2`) trên weak-label data |
| `train_verified_experience_ranker.py` | `python scripts/train_verified_experience_ranker.py` | Huấn luyện Ranker trên dữ liệu gán nhãn bởi con người |
| `train_bootstrap_experience_ranker.py` | `python scripts/train_bootstrap_experience_ranker.py` | Phiên bản bootstrap thử nghiệm ban đầu |
| `verify_alignment.py` | `python scripts/verify_alignment.py` | Kiểm tra tính thẳng hàng feature contract giữa backend API và ML pipeline |
| `download_e5_model.py` | `python -m scripts.download_e5_model` (từ `apps/api`) | Tải mô hình `intfloat/multilingual-e5-base` về `models/e5/` |

### 3. Nghiên cứu Rủi ro Ngập lụt

| Script | Lệnh mẫu | Chức năng |
|---|---|---|
| `download_hcmc_flood_reports.py` | `python scripts/download_hcmc_flood_reports.py` | Tải & chuyển đổi bộ dữ liệu báo cáo ngập lịch sử TP.HCM 2002–2026 sang UTF-8 CSV |
| `build_flood_report_weak_labels.mjs` | `node scripts/build_flood_report_weak_labels.mjs` | Sinh tập 662 mẫu cân bằng cho bài toán xác suất xuất hiện báo cáo ngập công khai |
| `build_flood_report_experiment_notebook.py` | `python scripts/build_flood_report_experiment_notebook.py` | Khởi tạo notebook Colab nghiên cứu độc lập |

### 4. Vận hành, Cơ sở Dữ liệu & Môi trường Phát triển

| Script | Môi trường | Chức năng |
|---|---|---|
| `run-dev.ps1` | Windows PowerShell | Khởi động đồng thời Vite frontend + FastAPI backend trong môi trường dev |
| `production-smoke.ps1` | Windows PowerShell | Smoke test toàn diện các luồng API chính trước khi phát hành |
| `backup-postgres.ps1` / `.sh` | PowerShell / Bash | Tạo bản sao lưu PostgreSQL với timestamp |
| `restore-postgres.ps1` / `.sh` | PowerShell / Bash | Phục hồi PostgreSQL từ tập tin sao lưu |

---

## 🚀 Lệnh Thường Dùng

### Khởi động môi trường phát triển (cả frontend + backend):
```powershell
.\scripts\run-dev.ps1
```

### Smoke test trước khi deploy:
```powershell
.\scripts\production-smoke.ps1
```

### Sao lưu CSDL PostgreSQL:
```powershell
.\scripts\backup-postgres.ps1
```

### Huấn luyện Experience Ranker:
```powershell
pip install -r apps/api/requirements-ranking-training.txt
python scripts/train_experience_ranker.py --mode weak_label
```

### Kiểm tra tính nhất quán feature contract ML:
```powershell
python scripts/verify_alignment.py
```

### Tải và rebuild bộ dữ liệu flood weak labels:
```powershell
# Tải báo cáo ngập lịch sử mới nhất
python scripts/download_hcmc_flood_reports.py

# Sinh lại weak labels (cần --force nếu file đã tồn tại)
node scripts/build_flood_report_weak_labels.mjs --force
```

---

## 🔗 Liên kết Tài nguyên

- **Dữ liệu nguồn**: [`data/`](../data/README.md) — raw, experimental, training, ranking datasets
- **Mô hình ML**: [`models/`](../models/README.md) — ai-ranker, e5, flood-risk artifacts
- **API Backend**: [`apps/api/scripts/`](../apps/api/README.md) — seed_db, import_place_candidates, worker, zalo_bot_poller
- **Notebook nghiên cứu**: [`notebooks/`](../notebooks/) — Flood Report Experiment Colab
