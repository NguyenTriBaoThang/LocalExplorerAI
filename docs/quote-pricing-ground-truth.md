# Quote pricing: ground truth của dữ liệu giả lập

> **SYNTHETIC / DỮ LIỆU GIẢ LẬP.** Toàn bộ file `data/training/quote_win_synthetic.csv` do
> `apps/api/scripts/generate_quote_history.py` sinh ra từ các quy luật bên dưới. Không có khách hàng, đối thủ hay
> báo giá thật. Mô hình huấn luyện trên đó (`models/quote-win/`) chỉ khôi phục lại chính các quy luật này
> (`deployment_eligible=false`). Mọi hệ số nằm trong `TRUE_BETA` của script; tài liệu này phải khớp với nó.

Chạy lại: `python -m scripts.generate_quote_history --seed 42 --start 2023-01-01 --years 3` (xác định theo seed).

## Giá vốn
- Dùng `compute_cost` thật (M4) với bảng giá seed `scripts/seed_operator_demo.CARDS` (không sao chép số), nhân nhiễu đều ±5%.
- Lịch trình theo điểm đến (km ngày 1 / ngày sau, vé ngày 1): cu_chi 70/40 + vé Củ Chi; mekong 160/40 + vé thuyền; can_gio 120/40 + vé Cần Giờ; vung_tau 250/60; city 40/40. Số bữa/khách = max(1, 2*ngày-1).
- Giá chào/khách = vốn/khách x (1 + markup), markup ~ U(5%, 60%), làm tròn LÊN 10.000 VND.

## Biến đầu vào
| Biến | Cách sinh |
|---|---|
| segment | family 40%, corporate 30%, school 30% |
| pax | family U{4..15}; corporate tam giác(15, 60, mode 25); school tam giác(25, 60, mode 40) |
| destination | trọng số theo segment (family .20/.25/.15/.20/.20; corporate .10/.15/.20/.35/.20; school .35/.25/.20/.05/.15 cho cu_chi/mekong/can_gio/vung_tau/city) |
| days | 1-3, trọng số theo điểm đến |
| lead_days | lognormal(mu 3.3, sigma 0.7) cắt [3, 120] |
| cờ weekend/holiday/tet/month | `vn_calendar.day_flags` của NGÀY KHỞI HÀNH |
| competitor_price_index | AR(1) theo tháng: x_t = 0.8 x_{t-1} + N(0, 0.04), chỉ số = 1 + x_t, cắt [0.8, 1.25] |
| rain_prob | khí hậu TP.HCM theo tháng khởi hành (T1..T12: .10 .05 .08 .18 .55 .75 .78 .78 .80 .75 .45 .20) + N(0, 0.05) |
| response_time_h | lognormal(1.2, 0.8) cắt 72 giờ |

Chỉ số giá đối thủ và rain_prob được coi là đã biết lúc báo giá.

## P(chốt) thật
Giá tham chiếu/khách: `ref = vốn/khách x 1.25 x competitor_index`; `rel = giá/ref - 1`.

`season_level` = max(Tết 1.0, lễ 0.8, mùa khô T12-T4 0.5, cuối tuần 0.3, 0).
Độ nhạy giá: `sens = beta_seg x (1 - 0.35 x season_level)` (mùa cao điểm làm khách bớt nhạy giá).

```
z = b0 + icpt_segment + icpt_dest
    - sens * rel
    + 0.25 * clip(ln(lead/14), -1.5, 1.5)
    + 0.3  * season_level
    - 0.35 * ln(1 + response_time_h)
    + 1.0  * (competitor_index - 1)
    - 0.25 * ln(pax/20)
    - 0.15 * (days - 1)
    - 0.8  * rain_prob            (chỉ mekong, can_gio)
P = sigmoid(z);  won ~ Bernoulli(P)
```

| Hệ số | Giá trị |
|---|---|
| b0 | 0.3 |
| beta_seg (độ nhạy giá) | family 6.0, corporate 3.5 (ít nhạy nhất), school 9.0 (nhạy nhất) |
| icpt_segment | family 0.0, corporate +0.2, school -0.2 |
| icpt_dest | cu_chi +0.2, mekong +0.1, can_gio -0.1, vung_tau -0.2, city +0.1 |
| giảm nhạy giá cao điểm | 0.35 |
| beta_season | 0.3 |
| beta_lead | 0.25 (lead lâu thì dễ chốt hơn; hàm cắt ở ±1.5) |
| beta_resp | 0.35 |
| beta_comp | 1.0 |
| beta_pax | 0.25 |
| beta_days | 0.15 |
| beta_rain | 0.8 |

Kết quả với seed 42: 21.980 báo giá, tỉ lệ chốt ~37%.
