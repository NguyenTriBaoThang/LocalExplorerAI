# Local Explorer AI — Thư mục Mô hình Học máy (Machine Learning Models)

Thư mục `models/` chứa các artifacts, metadata phiên bản, schemas đặc trưng và kết quả đánh giá thực nghiệm của các mô hình Trí tuệ nhân tạo & Học máy (AI/ML) chạy cục bộ trong hệ thống **Local Explorer AI**.

---

## 📁 Cấu trúc Thư mục `models/`

```text
models/
├── ai-ranker/                         # Mô hình Xếp hạng Trải nghiệm (Experience Ranker)
│   ├── xgboost_ranker.json            # Model binary native XGBRanker (LambdaMART / rank:ndcg)
│   ├── model_metadata.json            # Metadata phiên bản, NDCG metrics, SHA-256 checksum & config
│   ├── feature_schema.json            # Định nghĩa 15 đặc trưng đầu vào (ranker-features-v2)
│   ├── preprocessing.json             # Quy tắc chuẩn hóa và giá trị mặc định cho dữ liệu khuyết
│   ├── metrics.json                   # Kết quả đánh giá chi tiết (Train / Validation / Test NDCG)
│   ├── validation_comparison.csv       # Bảng so sánh hiệu năng giữa các thuật toán và tuning seeds
│   ├── test_predictions.csv           # Tập dự đoán kiểm thử độc lập
│   └── model_card.md                  # Thẻ mô hình chi tiết (Model Card) theo chuẩn kỹ thuật
├── flood-risk/                        # Mô hình Rủi ro Ngập lụt Tuyến đường Đô thị TP.HCM
│   └── .gitkeep                       # Lưu trữ artifacts huấn luyện từ notebook Flood Training
├── flood-report-experiment/           # Thực nghiệm Xác suất Xuất hiện Báo cáo Ngập Công khai
│   ├── report_presence_model.joblib   # Pipeline phân loại LogisticRegression / RandomForest
│   └── metadata.json                  # Metadata thực nghiệm nghiên cứu độc lập (Research-only)
└── e5/                                # Mô hình Vector Embedding Ngữ nghĩa Đa ngôn ngữ
    └── .gitkeep                       # intfloat/multilingual-e5-base (tải qua scripts/download_e5_model.py)
```

---

## 1. Mô hình Xếp hạng Trải nghiệm (`models/ai-ranker/`)

### Vai trò Kiến trúc:
- Hoạt động như bộ giải quyết hòa điểm (Tie-breaker) trong thuật toán **Heuristic Planner** và xếp hạng ưu tiên ứng viên thay thế trong **Dynamic Replanning** (`/api/ml/rank-experiences`).
- **Không bao giờ vi phạm ràng buộc cứng**: Mô hình chỉ chấm điểm và xếp hạng lại các ứng viên *đã được sàng lọc khả thi* bởi Solver toán học (thời gian, địa lý, ngân sách, sức chứa).

### Bộ 15 Đặc trưng Cốt lõi (`ranker-features-v2`):
1. `tag_jaccard`: Độ trùng lặp Jaccard giữa nhãn mong muốn và tags của hoạt động.
2. `intent_match`: Điểm khớp danh mục chính của chuyến đi.
3. `is_hands_on`: Hoạt động có tính chất thực hành/workshop thủ công.
4. `is_indoor`: Hoạt động diễn ra trong không gian kín (an toàn trước thời tiết).
5. `duration_ratio`: Tỷ lệ thời lượng hoạt động trên quỹ thời gian khả dụng.
6. `eta_ratio`: Tỷ lệ thời gian di chuyển trên thời lượng trải nghiệm.
7. `total_time_ratio`: Tỷ lệ chiếm dụng tổng thời gian chuyến đi.
8. `group_cost_ratio`: Tỷ lệ chi phí so với ngân sách của nhóm.
9. `rain_mm`: Lượng mưa dự báo tại thời điểm trải nghiệm.
10. `outdoor_rain_mm`: Lượng mưa tác động trực tiếp lên hoạt động ngoài trời.
11. `temperature_c`: Nhiệt độ môi trường đô thị (°C).
12. `pm2_5`: Nồng độ bụi mịn PM2.5 (µg/m³).
13. `european_aqi`: Chỉ số chất lượng không khí châu Âu.
14. `is_hands_on_known`: Cờ ghi nhận tính chất thực hành đã được xác minh.
15. `is_indoor_known`: Cờ ghi nhận vị trí trong nhà/ngoài trời đã được xác minh.

### Cơ chế An toàn Fail-Closed:
- API kiểm tra chữ ký số SHA-256 của file model trước khi nạp vào bộ nhớ.
- Khi cờ `deployment_eligible = false` hoặc model bị thiếu/hỏng, hệ thống tự động fallback về **Rule Baseline** (`category_rule_weak_label`) mà không gây crash API.

---

## 2. Mô hình Rủi ro Ngập lụt Đô thị (`models/flood-risk/`)

- Phân tích nguy cơ ngập lụt trên các cung đường TP. Hồ Chí Minh dựa trên dữ liệu báo cáo lịch sử 2002–2026 kết hợp chỉ số triều cường và lượng mưa.
- Phục vụ API endpoint `POST /api/ml/flood-risk`.
- **Ranh giới an toàn**: Dữ liệu chưa ghi nhận không đồng nghĩa với không ngập (`unknown ≠ no-flood`).

---

## 3. Thực nghiệm Báo cáo Ngập (`models/flood-report-experiment/`)

- **Mục tiêu nghiên cứu**: Dự đoán xác suất một địa danh xuất hiện trong báo cáo ngập công khai theo tháng dương lịch (chứ không dự đoán mức độ ngập vật lý của lòng đường).
- Được tạo bởi notebook `notebooks/LocalExplorerAI_Flood_Report_Weak_Label_Experiment_Colab.ipynb`.
- **Lưu ý**: Tệp này mang tính chất nghiên cứu khoa học độc lập, cố tình không tương thích và không được nạp vào dịch vụ API production.

---

## 4. Mô hình Vector E5 (`models/e5/`)

- Sử dụng mô hình `intfloat/multilingual-e5-base` của Microsoft/HuggingFace để chuyển đổi văn bản mô tả trải nghiệm thành vector 768 chiều.
- Chạy cục bộ hoàn toàn trên CPU thông qua `sentence-transformers`, không gửi dữ liệu ra bên ngoài.
- Tải mô hình về thư mục này bằng lệnh:
  ```powershell
  python -m scripts.download_e5_model
  ```
