# Quote win model (SYNTHETIC)

> **DỮ LIỆU GIẢ LẬP.** Mô hình này chỉ học từ lịch sử báo giá sinh bằng `scripts/generate_quote_history.py`
> (xem `docs/quote-pricing-ground-truth.md`). `dataset_status=synthetic`, `deployment_eligible=false`.
> Xác suất chốt tour ở đây KHÔNG phải bằng chứng thị trường; chỉ dùng để demo và kiểm thử optimizer.

- Phiên bản: `quote-win-xgb-synthetic-20261112T144400Z` (XGBoost, `quote-win-features-v1`), sha256 `4c1ae39386d3893f...`
- Mục tiêu: dự đoán P(chốt) cho một báo giá tại một mức giá; đầu vào chỉ gồm thông tin có tại thời điểm báo giá
  (đoàn, ngày đi, lead time, cờ lễ/Tết/cuối tuần, chỉ số giá đối thủ, xác suất mưa, thời gian phản hồi, giá/giá vốn).
  Chỉ số giá đối thủ và xác suất mưa được coi là đã biết lúc báo giá.
- Ràng buộc đơn điệu: P giảm khi `price_ratio_cost`, `price_ratio_comp` tăng.
- Chia theo thời gian (không xáo trộn): train 2023-01-01..2025-01-01 (14772 dòng),
  validation ..2025-07-01 (3586), test ..2025-12-31 (3622).
  Tham số chọn theo log loss trên validation: {'max_depth': 2, 'min_child_weight': 30, 'n_estimators': 394}.

## Kết quả trên tập test
| | AUC | Brier | Log loss | |p_hat - p_thật| |
|---|---|---|---|---|
| Mô hình | 0.7372 | 0.1721 | 0.5174 | 0.0391 |
| Oracle (P thật) | 0.7450 | 0.1696 | 0.5092 | 0 |

Bảng calibration 10 bin nằm trong `metrics.json`.

## Hạn chế
- P thật do chúng tôi tự đặt (hàm sigmoid có hệ số cố định); mô hình chỉ khôi phục lại chính quy luật đó.
- Không có hành vi khách thật, không có đối thủ thật, giá vốn lấy từ bảng giá seed.
- Không được dùng để ra quyết định giá thật cho tới khi huấn luyện lại bằng lịch sử báo giá thật của nhà điều hành.

<!-- backtest -->
## Backtest (tập test, P thật của dữ liệu giả lập)

3622 báo giá, sàn markup 10%. Kỳ vọng tính bằng P thật nên phản thực tế là chính xác.

| Chiến lược | Lợi nhuận kỳ vọng (VND) | so với markup 25% | Tỉ lệ chốt kỳ vọng | Biên TB chào giá | Biên TB khi chốt |
|---|---|---|---|---|---|
| fixed_25pct_markup | 5,449,526,147 | +0.0% | 31.7% | 20.5% | 20.5% |
| optimizer_balanced | 5,968,957,526 | +9.5% | 24.6% | 26.6% | 25.4% |
| optimizer_max_profit | 5,846,774,251 | +7.3% | 20.9% | 29.4% | 27.9% |
| oracle_max_profit_true_p | 6,273,466,859 | +15.1% | 27.4% | 24.2% | 24.6% |
| legacy_balanced_grid_1.80_unsupported | 5,125,439,092 | -5.9% | 16.3% | 34.9% | 28.5% |
| legacy_max_profit_grid_1.80_unsupported | 4,809,932,559 | -11.7% | 13.4% | 37.6% | 31.2% |

Optimizer mặc định giới hạn lưới giá ở `price_support.price_ratio_cost_max` (giá/vốn lớn nhất trong tập train). Hai dòng `legacy_*_grid_1.80_unsupported` là phiên bản đầu dùng lưới tới x1,8: nó THUA markup cố định 25% vì dữ liệu huấn luyện chỉ có markup 5-60%; ngoài vùng đó cây quyết định ngoại suy phẳng và đánh giá P quá cao (`model_estimated_profit_vnd` gần gấp đôi lợi nhuận thật ở chế độ max_profit). Nguyên nhân gốc là ngoại suy, nên optimizer không bao giờ chào giá ngoài vùng hỗ trợ. Chế độ cân bằng: trong các mức giá giữ được >= 95% lợi nhuận kỳ vọng tối đa, chọn mức có P chốt cao nhất.
