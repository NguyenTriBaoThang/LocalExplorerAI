# Giai đoạn 4: ghi chú bàn giao (đang làm dở)

Nhánh: `fix/authentication-flow`. Thiết kế tổng: `docs/auth-design.md`, mục 6, 10 và 12.
Trạng thái lúc dừng (2026-10-05): **backend gần xong, chưa có test riêng cho giai đoạn 4, chưa đụng frontend**.
`pytest` backend: **183 passed** (bằng baseline; các test cũ đã được cập nhật theo quy tắc mới).

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
1. **Viết `tests/test_account_recovery.py`.** Để lấy raw token, monkeypatch `app.api.routes.auth.queue_account_link` (outbox chỉ ghi row khi SMTP được cấu hình). Các ca cần có:
   - **Quên mật khẩu:** email lạ vẫn 202 và không tạo token; gọi lần 2 trong 60 giây không tạo token mới; tài khoản bóng và tài khoản bị khóa không nhận token.
   - **Đặt lại mật khẩu:**
     - thành công: mật khẩu mới đăng nhập được, phiên cũ chết ngay;
     - token chỉ dùng được một lần;
     - mật khẩu yếu trả 422 và token vẫn dùng lại được;
     - token hết hạn, hoặc token verify đem đi dùng cho reset, đều trả 400.
   - **Xác minh email:**
     - đăng ký có gửi email xác minh;
     - `POST /api/bookings` của người chưa xác minh trả `EMAIL_NOT_VERIFIED`; sau khi verify thì qua được bước kiểm tra này (ví dụ chuyển sang `404 ITINERARY_NOT_FOUND`);
     - gửi lại: đã xác minh thì trả `already_verified`, gửi lại liên tục thì 429.
   - **Đăng ký:** mật khẩu phổ biến trả `WEAK_PASSWORD`; email bóng trả `EMAIL_RESERVED`.
   - **Quản lý phiên:**
     - list có đúng cờ `current`;
     - xóa phiên khác chỉ phiên đó mất;
     - xóa phiên hiện tại thì cookie bị xóa và access token bị từ chối ngay;
     - id phiên của người khác trả 404;
     - `logout-all` làm chết mọi token;
     - sau `logout`, access token cũ bị từ chối.
   - **Claim:**
     - email mới: tạo tài khoản, token thành đã dùng, claim lần 2 trả 400;
     - email cũ đúng mật khẩu: lịch trình chuyển chủ, tài khoản giữ nguyên;
     - sai mật khẩu: 401 và token còn dùng được;
     - lịch trình đã có chủ thật: 409;
     - tài khoản admin: 403;
     - token hết hạn: 400;
     - body cũ chỉ có `share_token`: 422.
2. Chạy `alembic upgrade head` rồi `downgrade` về `0012` trên **PostgreSQL thật** (cả 0011–0013 chưa từng chạy trên PG). Có thể dùng container `db` trong `docker-compose.yml`.
3. **Frontend** (design mục 11):
   - Bắt buộc: `SharedItineraryPage.tsx` đọc `?claim=` và gửi `claim_token`, mật khẩu tối thiểu 12 ký tự, chỉ hiện form claim khi có `claim`. Hiện trang này đang gửi `share_token` nên **sẽ bị 422**.
   - Cần thêm: trang `/forgot-password`, `/reset-password`, `/verify-email`; danh sách phiên trong Profile; xử lý mã `EMAIL_NOT_VERIFIED`, `WEAK_PASSWORD`.
4. Cập nhật `docs/api.md`, `.env.example` (`WEB_APP_URL` và SMTP bắt buộc cho reset/verify), rồi mục 15 của `docs/auth-design.md`.
5. Cân nhắc sau: rate limit riêng cho `/password/forgot` theo email (hiện chỉ có giới hạn 60 giây mỗi tài khoản cộng rate limit chung `/api/auth` theo IP khi bật).

## Chạy test
```bash
cd apps/api
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```
