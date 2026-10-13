# Local Explorer AI — Thư mục Scripts Hệ thống

Thư mục `scripts/` chứa toàn bộ các kịch bản tự động hóa (scripts) phục vụ quy trình thu thập dữ liệu, xử lý hình ảnh, huấn luyện mô hình học máy, vận hành CSDL và kiểm thử hệ thống cho **Local Explorer AI**.

---

## 🗂️ Phân loại Các Nhóm Scripts

### 1. Thu thập, Xử lý & Làm giàu Dữ liệu Địa danh Sài Gòn & Quận 1
| Script | Ngôn ngữ | Chức năng & Mục đích |
|---|---|---|
| `crawl_district1_places.py` | Python | Thu thập thông tin địa điểm văn hóa, lịch sử và ẩm thực trọng điểm tại Quận 1 |
| `download_district1_photos.py` | Python | Tải hình ảnh thực địa chất lượng cao cho các địa điểm Quận 1 |
| `attach_district1_photos_to_catalog.py` | Python | Gắn đường dẫn hình ảnh đã tải vào danh mục `data/sai_gon_places.json` |
| `generate_full_places_data.py` | Python | Hợp nhất dữ liệu tổng hợp địa điểm Sài Gòn từ các nguồn |
| `saigon_places_data_part1.py` / `part2.py` | Python | Các khối dữ liệu bộ phận cho danh mục địa danh Sài Gòn |
| `apply_enriched_places.py` | Python | Áp dụng các trường dữ liệu bổ sung (rating, review, open_hours) vào danh mục |
| `analyze_places_excel.py` | Python | Phân tích cấu trúc bảng tính `Places/Sai_Gon_Places.xlsx` |
| `deep_check_excel.py` | Python | Kiểm tra chuyên sâu tính hợp lệ và các trường thiếu trong file Excel |
| `check_places_detail.py` | Python | Kiểm tra chi tiết tính nhất quán của danh mục JSON so với thực tế |
| `dump_sheets.py` / `dump_indexed.py` | Python | Xuất các sheet và chỉ mục bảng tính phục vụ đối soát |

### 2. Huấn luyện Mô hình Học máy (Machine Learning Training)
| Script | Lệnh chạy mẫu | Chức năng & Mục đích |
|---|---|---|
| `train_experience_ranker.py` | `python scripts/train_experience_ranker.py --mode weak_label` | Huấn luyện và đánh giá mô hình XGBoost & LightGBM Ranker (`ranker-features-v2`) trên dữ liệu weak-label |
| `train_verified_experience_ranker.py` | `python scripts/train_verified_experience_ranker.py` | Huấn luyện mô hình Ranker có kiểm chứng trên dữ liệu gán nhãn của con người |
| `train_bootstrap_experience_ranker.py` | `python scripts/train_bootstrap_experience_ranker.py` | Huấn luyện bản thử nghiệm bootstrap ban đầu cho Experience Ranker |
| `verify_alignment.py` | `python scripts/verify_alignment.py` | Kiểm tra tính thẳng hàng giữa feature contract của backend API và pipeline ML |

### 3. Nghiên cứu Rủi ro Ngập lụt (Flood Risk Research)
| Script | Lệnh chạy mẫu | Chức năng & Mục đích |
|---|---|---|
| `download_hcmc_flood_reports.py` | `python scripts/download_hcmc_flood_reports.py` | Tải và chuyển đổi bộ dữ liệu báo cáo ngập lịch sử TP.HCM 2002–2026 từ DataSuds sang UTF-8 CSV |
| `build_flood_report_weak_labels.mjs` | `node scripts/build_flood_report_weak_labels.mjs` | Sinh tập dữ liệu 662 mẫu cân bằng cho bài toán xác suất xuất hiện báo cáo ngập công khai |
| `build_flood_report_experiment_notebook.py` | `python scripts/build_flood_report_experiment_notebook.py` | Khởi tạo notebook thực nghiệm Colab phục vụ nghiên cứu độc lập |

### 4. Vận hành, Cơ sở Dữ liệu & Môi trường Phát triển
| Script | Môi trường | Chức năng & Mục đích |
|---|---|---|
| `run-dev.ps1` | Windows PowerShell | Khởi động đồng thời cả frontend Vite và backend FastAPI trong môi trường dev |
| `production-smoke.ps1` | Windows PowerShell | Kịch bản kiểm thử khói (Smoke Test) toàn diện các luồng API chính trước khi phát hành |
| `backup-postgres.ps1` / `.sh` | PowerShell / Bash | Tự động tạo bản sao lưu cơ sở dữ liệu PostgreSQL kèm timestamp |
| `restore-postgres.ps1` / `.sh` | PowerShell / Bash | Phục hồi cơ sở dữ liệu PostgreSQL từ tập tin sao lưu |

---

## 🚀 Hướng dẫn Sử dụng Thường dùng

### Chạy kiểm thử khói môi trường phát triển:
```powershell
.\scripts\production-smoke.ps1
```

### Sao lưu CSDL PostgreSQL:
```powershell
.\scripts\backup-postgres.ps1
```

### Chạy huấn luyện Ranker cục bộ:
```powershell
python -m pip install -r apps/api/requirements-ranking-training.txt
python scripts/train_experience_ranker.py --mode weak_label
```
