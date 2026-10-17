# Giai đoạn 4: ghi chú bàn giao (đang làm dở)

Nhánh: `fix/authentication-flow`. Thiết kế tổng: `docs/auth-design.md`, mục 6, 10 và 12.
Trạng thái lúc bàn giao (2026-10-05): backend gần xong, chưa có test riêng cho giai đoạn 4, chưa đụng frontend (183 passed).
**Cập nhật 2026-10-06: các mục 1–4 trong "Còn lại" đã xong** (216 passed, PostgreSQL thật, E2E trình duyệt 32/32); xem `docs/auth-design.md`, mục "Ghi chú Giai đoạn 4".

## Đã làm

| Hạng mục | File chính | Ghi chú |
|---|---|---|
| Migration `0013_account_recovery` | `migrations/versions/0013_account_recovery.py` | Bảng `itinerary_claim_tokens` + quyền `account:sessions` cấp cho cả 3 role. **Chưa chạy trên PostgreSQL thật.** |
| Model claim token | `app/models/entities.py` (`ItineraryClaimToken`) | Chỉ lưu SHA-256 |
| Quyền mới | `app/api/permissions.py` (`P.ACCOUNT_SESSIONS`) | Có trong `_ACCOUNT` |
| Token dùng một lần | `app/services/account_tokens.py` | reset 30 phút, verify 24 giờ, claim 7 ngày; tiêu thụ nguyên tử (`UPDATE ... WHERE used_at IS NULL`); phát token mới thì hủy token cũ cùng mục đích; giới hạn gửi lại 60 giây |
| Email qua outbox | `app/services/notifications.py` (`queue_account_link`) | Link `{WEB_APP_URL}/reset-password?token=` và `/verify-email?token=`; idempotency key `auth:<purpose>:<id>` |
| Xóa link bí mật khỏi outbox | `scripts/worker.py` | Row `auth:*` đã `sent`/`failed` thì body bị thay bằng `[redacted after delivery]` |
| Thu hồi phiên tức thì | `app/api/authn.py` | Mỗi request tra `auth_sessions` theo `sid`; phiên bị thu hồi thì access token chết ngay (trước đây sống thêm tới 15 phút). Có thêm `current_session_id(request)` |
| Endpoint mới | `app/api/routes/auth.py` | Xem bảng dưới |
| Chính sách mật khẩu | `validate_password_policy` | Áp dụng khi đăng ký, đổi mật khẩu, đặt lại mật khẩu, claim tạo tài khoản mới (lỗi `WEAK_PASSWORD` 422) |
| Chặn email tài khoản bóng | `app/services/ticket_service.py` (`is_shadow_email`) | `zalo_*@localexplorer.site` không thể đăng ký/claim (`EMAIL_RESERVED`) |
| Bắt buộc xác minh email | `app/api/routes/bookings.py` (`_require_verified_email`) | `POST /api/bookings` và `/checkout` trả `403 EMAIL_NOT_VERIFIED` |
| Google đánh dấu đã xác minh | callback Google | Chỉ khi email Google trùng email tài khoản |
| Tài khoản demo | `scripts/seed_db.py` | Tạo sẵn `email_verified_at` |
| Sửa `claim-ticket` | `routes/auth.py`, `ticket_service.py`, `scripts/zalo_bot_poller.py` | Xem mục dưới |
| Test cũ cập nhật | `tests/helpers.py` (`make_user` mặc định đã xác minh), `tests/test_bookings.py`, `tests/test_rbac.py` | Thêm 3 route public vào `PUBLIC_ROUTES`; test seed chạy `0012` + `0013` |

### Endpoint mới
| Method | Path | Bảo vệ | Kết quả |
|---|---|---|---|
| POST | `/api/auth/password/forgot` | public | Luôn `202 {"accepted": true}`; không lộ tài khoản có tồn tại hay không |
| POST | `/api/auth/password/reset` | public (token email) | Đổi mật khẩu, tăng `token_version` (đăng xuất mọi thiết bị), xóa cookie, không tự đăng nhập |
| POST | `/api/auth/email/verify` | public (token email) | Đặt `email_verified_at` |
| POST | `/api/auth/email/verify/resend` | `account:update` | 202; `429 VERIFICATION_RECENTLY_SENT` nếu vừa gửi |
| GET | `/api/auth/sessions` | `account:sessions` | Mỗi họ refresh token là một phiên; `id` = `family_id`, có cờ `current` |
| DELETE | `/api/auth/sessions/{id}` | `account:sessions` | Thu hồi phiên; nếu là phiên hiện tại thì xóa cookie; của người khác thì `404` |
| POST | `/api/auth/logout-all` | `account:sessions` | Thu hồi mọi phiên và xóa cookie |

### `claim-ticket` (lỗ hổng đã sửa)
- **Trước:** dùng `share_token` công khai làm credential; mã vé `SG-PASS-XXXXXX` chỉ có 24 bit nên đoán được; ai có link đều chuyển được quyền sở hữu bất kỳ lịch trình nào, kể cả lịch trình của người dùng thật.
- **Sau:**
  - Request mới: `{claim_token, email, password, display_name?}`. **Body cũ có `share_token` giờ trả 422.**
  - `share_token` của vé Zalo đổi thành `token_urlsafe(32)`; `SG-PASS-…` chỉ còn để hiển thị, lưu ở `constraints.ticket_code`.
  - Claim token riêng, dùng một lần, hạn 7 ngày; bot gửi `claim_url_prod` = `/shared/{share}?claim={token}`.
  - Chỉ claim được khi lịch trình chưa có chủ hoặc chủ là tài khoản bóng Zalo; còn lại trả `409 TICKET_ALREADY_CLAIMED`.
  - Email đã có tài khoản: chỉ đăng nhập bằng mật khẩu, không sửa gì tài khoản đó; chỉ role `traveler` (`403 CLAIM_ROLE_FORBIDDEN`); sai mật khẩu trả 401 và token **không** bị tiêu thụ.
  - Email mới: tạo traveler mới (không chiếm tài khoản bóng), gửi email xác minh.
  - Vé tạo trước migration `0013` không có claim token nên vẫn xem được nhưng không claim được nữa.

## Còn lại (theo thứ tự)
1. ~~Viết `tests/test_account_recovery.py`~~ **Xong**: 33 ca, kiểm tra đột biến cho 8 cơ chế bảo mật.
2. ~~Chạy migration trên PostgreSQL thật~~ **Xong cho 0011–0013** (dựng sẵn hai bảng nền). Phát hiện: chuỗi migration gốc không chạy từ đầu được (`0002`) và `create_all` cũng lỗi trên PostgreSQL; hai lỗi này có sẵn trên `main`, chưa sửa.
3. ~~Frontend~~ **Xong**: `SharedItineraryPage` dùng `?claim=` và `claim_token`; trang `/forgot-password`, `/reset-password`, `/verify-email`; danh sách thiết bị trong Profile; banner xác minh email; xử lý 401 khi phiên bị thu hồi.
4. ~~Cập nhật `docs/api.md`, `.env.example`, `docs/auth-design.md`~~ **Xong**.
5. Cân nhắc sau: rate limit riêng cho `/password/forgot` theo email và theo IP (Giai đoạn 6). MFA (Giai đoạn 5) phải chặn việc đặt lại mật khẩu bỏ qua MFA của admin.

## Chạy test
```bash
cd apps/api
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```
