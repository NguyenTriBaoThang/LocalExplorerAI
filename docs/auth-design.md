# Thiết kế luồng xác thực và phân quyền (RBAC) chuẩn production

Trạng thái: **bản nháp để duyệt**, chưa có code. Làm cục bộ trên nhánh `fix/authentication-flow`.
Baseline trước khi thay đổi: `pytest` backend = **81 passed** (nhánh `main`, chưa sửa gì).

## 1. Mục tiêu và nguyên tắc
- Một thư viện nội bộ `app/auth/` chịu trách nhiệm toàn bộ xác thực và phân quyền. Lõi không phụ thuộc FastAPI hay mô hình nghiệp vụ; một lớp adapter mỏng nối vào FastAPI.
- Mọi route phải khai báo rõ `require("<permission>")` hoặc `public()`. Một test duyệt toàn bộ route sẽ fail nếu có route thiếu khai báo.
- Quyền (permission) lưu trong DB, danh mục tên quyền khai báo trong code.
- Token truy cập sống ngắn, thu hồi được ngay; refresh token xoay vòng, phát hiện đánh cắp.
- Giữ tương thích với frontend ở mức tối đa: cùng origin qua nginx, cookie `HttpOnly`, không đưa token vào JavaScript.

## 2. Các quyết định đã chốt
| Hạng mục | Quyết định |
|---|---|
| Nơi lưu quyền | Danh mục trong code, gán role → quyền trong DB |
| Token | Access JWT **RS256** 15 phút, refresh opaque 7 ngày (admin 1 ngày), giới hạn phiên tuyệt đối 30 ngày |
| Thu hồi tức thời | `users.token_version` + cache Redis |
| Tự làm mới | Trong dependency xác thực (không phải middleware): xoay vòng và đặt lại cookie khi access hết hạn hoặc còn dưới 3 phút |
| Cookie refresh | `Path=/api` |
| Provider | Claim `provider_id` trong token; thao tác ghi quan trọng (slot, booking) tra lại DB |
| `X-Admin-Key` | Thay bằng service account: chỉ quyền đọc ops/health, mỗi script một khóa, audit `system:<tên>` |
| `portal_access_key` | Giữ lớp tương thích, ghi cảnh báo mỗi lần dùng, bỏ ở bản sau |
| Hạ tầng | Redis bắt buộc ở production |
| Phạm vi | Quên mật khẩu, xác minh email, MFA TOTP, argon2id, quản lý phiên nằm trong đợt này |
| BFF | Không cần: nginx đã proxy `/api` cùng origin |

## 3. Token
**Access token (JWT, RS256)**
- Claims: `iss`, `aud`, `sub`, `iat`, `nbf`, `exp` (15 phút), `jti`, `sid` (mã phiên), `role`, `provider_id`, `ver` (token_version), `amr` (`["pwd"]`, `["pwd","otp"]`, `["google"]`).
- Không nhúng danh sách quyền (dài, dễ lỗi thời); quyền tra từ ma trận role đã cache.
- Xác minh: ghim `algorithms=["RS256"]`, bắt buộc `exp/iat/iss/aud/sub/jti`, `leeway` 10 giây, từ chối `alg: none` và HS256.
- Khóa: private key từ biến môi trường hoặc file bí mật; public key theo `kid` để xác minh token cũ trong lúc xoay khóa. Production fail-closed nếu thiếu khóa. Dev sinh khóa tạm và ghi cảnh báo.

**Refresh token**
- Chuỗi ngẫu nhiên 256-bit, chỉ lưu SHA-256 trong DB.
- TTL 7 ngày (admin 1 ngày), tối đa 30 ngày kể từ lúc đăng nhập (giới hạn tuyệt đối; **mặc định đề xuất cho admin 7 ngày, cần xác nhận**).

## 4. Cookie
| Cookie | Dùng cho | Thuộc tính |
|---|---|---|
| `__Host-le_at` | access token | `HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=900` |
| `__Secure-le_rt` | refresh token | `HttpOnly; Secure; SameSite=Lax; Path=/api; Max-Age` theo vai trò |

- Ở HTTP cục bộ dùng tên không tiền tố (`le_at`, `le_rt`) qua cấu hình.
- Cookie cũ `le_session` (HS256) **không còn được chấp nhận**: mọi người dùng đăng nhập lại một lần sau triển khai.
- Phản hồi các endpoint xác thực có `Cache-Control: no-store`.
- Chống CSRF: `SameSite=Lax` cộng middleware kiểm tra `Origin`/`Referer` với danh sách origin cho phép trên các phương thức thay đổi dữ liệu.

## 5. Dữ liệu mới (Alembic)
- `users`: thêm `token_version INT`, `email_verified_at`, `mfa_enabled`.
- `auth_sessions`: `id`, `user_id`, `family_id`, `refresh_hash`, `issued_at`, `expires_at`, `absolute_expires_at`, `rotated_at`, `replaced_by`, `revoked_at`, `ip`, `user_agent`, `last_used_at`, `amr`.
- `auth_tokens`: token một lần cho `reset_password` và `verify_email` (chỉ lưu băm, TTL 30 phút / 24 giờ, `used_at`).
- `user_mfa`: secret TOTP mã hóa bằng Fernet (cơ chế đã có trong dự án), `confirmed_at`; `mfa_recovery_codes`: mã khôi phục lưu băm.
- `roles`, `permissions`, `role_permissions`: ma trận quyền; role hệ thống không được xóa.
- `service_accounts`: `name`, `key_prefix`, `key_hash`, `permissions`, `last_used_at`, `revoked_at`.
- `auth_events` (hoặc dùng bảng audit hiện có): đăng nhập thành công/thất bại, làm mới, phát hiện tái sử dụng, đăng xuất, đổi role, MFA, đặt lại mật khẩu.

## 6. Các luồng
**Đăng nhập:** chuẩn hóa email → giới hạn lần thử (theo tài khoản và IP) → xác minh mật khẩu (argon2id, tự băm lại nếu đang là scrypt) → nếu có MFA trả `mfa_required` kèm `mfa_ticket` dùng một lần (Redis, 5 phút) → xác minh TOTP → tạo `auth_session` → cấp access + refresh. Lỗi trả đồng nhất, không lộ tài khoản có tồn tại hay không.

**Tự làm mới (trong dependency xác thực, không phải middleware):** nếu access hợp lệ nhưng còn dưới 3 phút (hoặc đã hết hạn nhưng refresh còn hạn) → xoay vòng refresh → ghi cặp cookie mới vào chính response.
- Xoay vòng: đánh dấu refresh cũ `rotated_at`/`replaced_by`, cấp refresh mới cùng `family_id`.
- Cửa sổ khoan hồng 10 giây (khóa Redis theo `family_id`) để các request song song không bị đăng xuất oan.
- Dùng lại refresh đã xoay **ngoài** cửa sổ → thu hồi cả họ, ghi `auth_events`, yêu cầu đăng nhập lại.
- Vượt giới hạn tuyệt đối hoặc refresh hết hạn → 401.

**Thu hồi tức thời:** mỗi request so `ver` trong token với `token_version` hiện tại (Redis `auth:ver:{user}` TTL ngắn, hụt thì đọc DB). Đổi role, khóa tài khoản, đổi mật khẩu, đăng xuất mọi thiết bị đều tăng `token_version` và xóa khóa cache. Nếu Redis chết: đọc DB trực tiếp (đúng nhưng chậm hơn).

**Đăng xuất:** thu hồi họ refresh hiện tại và xóa cookie. **Đăng xuất mọi thiết bị:** tăng `token_version`.

**Quên mật khẩu:** `POST /api/auth/password/forgot` luôn trả 202 → gửi email qua outbox hiện có (idempotency key) → `POST /api/auth/password/reset` với token một lần → băm mật khẩu mới → tăng `token_version`, thu hồi mọi phiên.

**Xác minh email:** đăng ký gửi token 24 giờ. Chính sách đề xuất: chưa xác minh vẫn duyệt và lập lịch được, nhưng **không đặt chỗ/thanh toán** (cần xác nhận).

**MFA TOTP:** đăng ký (QR + xác nhận mã), 10 mã khôi phục, tắt MFA cần mật khẩu. **Bắt buộc cho admin** (đăng nhập admin chưa có MFA bị chuyển sang bước đăng ký); tùy chọn cho người dùng khác.

**Quản lý phiên:** `GET /api/auth/sessions`, `DELETE /api/auth/sessions/{id}`, `POST /api/auth/logout-all`.

**Google OAuth:** giữ PKCE; chỉ liên kết với tài khoản có sẵn khi `email_verified` từ Google là true; kiểm `state`/`nonce`. *Cần rà lại phần callback hiện tại trước khi sửa.*

## 7. Mật khẩu
- argon2id (đề xuất `m=64 MiB, t=3, p=1`), băm lại tự động khi đăng nhập nếu tham số đổi hoặc đang là scrypt.
- Độ dài tối thiểu 12 ký tự; từ chối danh sách mật khẩu phổ biến (ngoại tuyến).

## 8. Phân quyền (RBAC trong DB)
- `Principal(id, kind=user|service, role, provider_id, amr)`.
- Danh mục quyền khai báo trong code (`slot:update`, `itinerary:read`...). Khi khởi động, đồng bộ danh mục vào bảng `permissions` (chỉ thêm, không tự cấp). Migration seed ma trận mặc định cho `traveler`, `provider`, `admin`.
- Ma trận role → quyền được cache trong tiến trình và làm mới theo số phiên bản trong Redis (`auth:perm_ver`) khi admin thay đổi.
- Chính sách theo đối tượng (ownership): `authorize(principal, "slot:update", slot)`; provider chỉ sửa tài nguyên có `provider_id` của mình. Thao tác ghi slot/booking tra lại DB.
- Bảo vệ chống tự khóa: không được gỡ quyền quản trị quyền của role `admin`, không tự hạ quyền của chính mình. Mọi thay đổi ma trận được audit.
- **Service account:** `Authorization: Bearer lek_<id>_<secret>`, chỉ lưu băm; mỗi script một khóa; quyền đọc ops/health; audit actor `system:<tên>`.
- Test duyệt toàn bộ route: mỗi route phải có `require(...)` hoặc `public()` rõ ràng; danh sách route công khai là một danh sách tường minh được review.

## 9. Redis
| Khóa | Dùng cho |
|---|---|
| `auth:ver:{user_id}` | cache `token_version`/`is_active` (TTL ngắn) |
| `auth:perm_ver` | số phiên bản ma trận quyền để làm mới cache |
| `auth:rot:{family_id}` | cửa sổ khoan hồng khi xoay vòng refresh |
| `auth:mfa:{ticket}` | vé MFA dùng một lần |
| `auth:rl:*` | giới hạn thử đăng nhập, khóa tạm |

Ở production Redis là bắt buộc. Khi Redis không sẵn sàng: `ver` đọc từ DB; giới hạn tốc độ rơi về bộ đếm trong tiến trình.

## 10. Sửa lỗi đã phát hiện trong review
- `POST /api/auth/claim-ticket`: dùng **claim token riêng dùng một lần**, tách khỏi `share_token` công khai; chỉ cho claim khi lịch trình chưa có chủ hoặc thuộc tài khoản bóng Zalo; không ghi đè email/mật khẩu của tài khoản đã có chủ thật; thêm test.
- Rate limit bật mặc định ở production, kèm giới hạn riêng cho các endpoint tốn chi phí (`/api/chat`, `/api/geocoding`, `/api/ml/*`).
- Hợp nhất hai cơ chế admin (`require_roles` và `require_admin`) thành `require()`.

## 11. Frontend
- Giữ `withCredentials: true`; không lưu token trong JavaScript.
- Thêm interceptor: 401 → chuyển về đăng nhập; bắt `mfa_required`.
- Trang mới: quên mật khẩu, đặt lại mật khẩu, xác minh email, đăng ký MFA, quản lý phiên.
- Giữ nguyên các mã lỗi hiện có (`ROLE_FORBIDDEN`, `ITINERARY_FORBIDDEN`...) và thêm mã mới.

## 12. Lộ trình
| Giai đoạn | Nội dung | Điều kiện hoàn thành |
|---|---|---|
| 0 | Baseline | 81 test pass (đã có) |
| 1 | Gói `app/auth/` (token RS256, argon2id, Principal, permission, service account, adapter Redis) + migration khung + test riêng | Test lõi pass, chưa động tới route |
| 2 | Phiên, refresh xoay vòng, cookie, middleware tự làm mới, login/refresh/logout | Test tái sử dụng refresh, hết hạn, thu hồi bằng `ver` |
| 3 | Chuyển route sang `require()`, fixture đăng nhập admin thật thay `X-Admin-Key`, test duyệt route | 81 test cũ vẫn pass; không route nào thiếu khai báo |
| 4 | Quên mật khẩu, xác minh email, quản lý phiên, sửa `claim-ticket` | Test từng luồng |
| 5 | MFA TOTP (bắt buộc cho admin) | Test đăng ký, đăng nhập, mã khôi phục |
| 6 | Hardening: rate limit, header, tài liệu, gỡ lớp tương thích cũ theo kế hoạch | Rà soát cuối |

## 13. Rủi ro và phụ thuộc
- Thư viện mới: `PyJWT`, `cryptography`, `argon2-cffi`, `pyotp`.
- Redis bắt buộc ở production; cần cập nhật `docker-compose.prod.yml` và `.env.example` (khóa RSA, ngưỡng TTL, danh sách origin).
- Đổi cơ chế token nên người dùng phải đăng nhập lại một lần.
- Bề mặt thay đổi lớn (khoảng 110 route); làm theo giai đoạn và giữ `require_roles` làm lớp tương thích tới Giai đoạn 3.

## 14. Quyết định cuối (đã chốt)
1. **Phiên admin:** refresh 1 ngày, giới hạn tuyệt đối **7 ngày**.
2. **Xác minh email:** bắt buộc trước khi đặt chỗ/thanh toán. Tài khoản có sẵn được coi là đã xác minh (migration 0011 backfill từ `created_at`).
3. **MFA:** bắt buộc với admin. **Admin chỉ đăng nhập bằng email + mật khẩu (+ MFA), không dùng Google**: callback Google phải từ chối tài khoản admin và không được liên kết/nâng quyền thành admin.
4. **Khóa RS256:** biến môi trường, PEM mã hóa base64 (`AUTH_JWT_PRIVATE_KEY_B64`, `AUTH_JWT_KEY_ID`); khóa cũ đã nghỉ giữ trong `AUTH_JWT_PUBLIC_KEYS_B64` cho tới khi token cuối cùng ký bằng nó hết hạn. Chu kỳ xoay khóa đề xuất 90 ngày (chưa được xác nhận).
5. **Môi trường dev giống production:** không sinh khóa tạm. Mọi môi trường đều phải cấu hình khóa, sinh bằng `python -m scripts.generate_auth_keys`. Test tự sinh cặp khóa riêng trong fixture.

## 15. Tiến độ
| Giai đoạn | Trạng thái |
|---|---|
| 0 Baseline | Xong: 81 passed |
| 1 Gói `app/auth/` + migration + test | **Xong**: 139 passed (81 cũ + 58 mới). Chưa nối vào route nào |
| 2 Phiên, refresh xoay vòng, cookie, tự làm mới, login/refresh/logout | **Xong**: 164 passed (81 gốc + 58 lõi + 23 phiên + 2 cache). Token cũ `le_session` không còn được chấp nhận |
| 3 Danh mục quyền, ma trận trong DB, `require()`, service account, test duyệt route | **Xong**: 182 passed. `X-Admin-Key`, `require_roles`, `require_admin` đã gỡ |
| 4 Quên mật khẩu, xác minh email, quản lý phiên, sửa `claim-ticket`, chính sách mật khẩu | **Xong, chưa commit**: 216 passed. Đã kiểm tra trên PostgreSQL thật (migration 0011–0013) và trình duyệt thật (32/32 kiểm tra E2E). Frontend đã làm (trang quên/đặt lại mật khẩu, xác minh email, thiết bị đăng nhập, banner, form nhận vé) |
| 5 MFA TOTP (bắt buộc cho admin, có công tắc `ADMIN_MFA_REQUIRED`) | **Xong**: backend (31 ca test), frontend, E2E trình duyệt 13/13, migration 0014 chạy được trên PostgreSQL thật (bảng nền dựng sẵn) |
| 6 Hardening: rate limit mặc định (production), nhóm `costly`, chặn đoán mật khẩu theo email/IP (429 `LOGIN_THROTTLED`), header bảo mật + `no-store` cho `/api/auth/*`, HSTS ở production, gỡ `AUTH_SECRET`/`create_session_token`, `ALLOW_PROVIDER_ACCESS_KEY` (tắt ở production) | **Xong phần backend** (269 passed) |

Giai đoạn 1 đã kiểm tra: test lõi (kể cả các tấn công `alg: none`, nhầm thuật toán HS256 bằng khóa công khai, kid lạ, token bị sửa), kiểm tra đột biến (bỏ kiểm tra `iss`/`aud`/`exp` thì test fail), migration nâng và hạ cấp trên SQLite, so khớp cột/index với model, và xuất SQL PostgreSQL ở chế độ offline. Migration 0011–0013 đã được chạy trên PostgreSQL 16 thật ở Giai đoạn 4 (xem ghi chú bên dưới).

### Ghi chú Giai đoạn 2
- Đã nối vào: `register`, `login`, `refresh` (mới), `logout`, đổi mật khẩu, callback Google, `claim-ticket`; `get_current_user`, `get_optional_user`, `require_admin`.
- Admin đổi role hoặc khóa tài khoản sẽ tăng `token_version` và thu hồi mọi phiên của người đó ngay.
- Đổi mật khẩu đăng xuất các thiết bị khác nhưng giữ thiết bị đang đổi.
- Google không còn đăng nhập hay liên kết được với tài khoản admin.
- Chặn `Origin` lạ cho các request thay đổi dữ liệu có cookie xác thực (bỏ qua nếu dùng Bearer hoặc không có Origin).
- API từ chối khởi động nếu thiếu khóa RS256; `docker-compose.yml` truyền `AUTH_JWT_*` (bản prod bắt buộc).
- Vẫn còn dùng lớp tương thích: `X-Admin-Key`, `require_roles`, hàm `create_session_token` cũ (không còn được route nào gọi).
- Chưa làm: phát hiện chính sách mật khẩu 12 ký tự (Giai đoạn 4), sửa `claim-ticket` (Giai đoạn 4), service account (Giai đoạn 3).

### Ghi chú Giai đoạn 3
- **116 route**, mỗi route khai báo đúng một chính sách (`public(lý do)` hoặc `require(quyền)`); 34 route công khai nằm trong danh sách duyệt `PUBLIC_ROUTES` của `tests/test_rbac.py`. Thêm route công khai mà không sửa danh sách này làm test fail.
- **43 quyền** khai báo trong `app/api/permissions.py`; ma trận role → quyền nằm trong DB (migration `0011` tạo bảng, `0012_rbac_seed` nạp dữ liệu), cache 60 giây hoặc làm mới khi worker khác sửa (Redis `auth:perm_ver`). Sửa ma trận có hiệu lực ngay, không cần đăng nhập lại.
- Quyền mới thêm vào code được đưa vào DB bằng `python -m scripts.sync_rbac` (chỉ cấp mặc định cho quyền **mới**, không khôi phục quyền admin đã chủ động gỡ).
- Endpoint mới: `GET /api/admin/rbac`, `PUT /api/admin/rbac/roles/{role}/permissions`, `GET/POST/DELETE /api/admin/service-accounts`. Role `admin` không thể bị gỡ `admin:rbac`, `admin:users`, `admin:service_accounts`.
- **Service account** (`Authorization: Bearer lek_...`) thay `X-Admin-Key`: chỉ giữ được `ops:read`, chỉ lưu băm của khóa, thấy khóa đúng một lần, ghi `last_used_at`, thu hồi được.
- `require_user()` luôn trả về người dùng thật (khóa API bị từ chối); `require()` nhận cả hai.
- Còn lại cho giai đoạn sau: `X-Provider-Access-Key` vẫn dùng được (tương thích, sẽ bỏ), `claim-ticket` còn công khai (Giai đoạn 4), chính sách mật khẩu 12 ký tự (Giai đoạn 4).

### Ghi chú Giai đoạn 4
- Backend do một phiên trước làm dở (xem `docs/auth-phase4-handoff.md`); phiên này **viết bộ test (33 ca), kiểm tra đột biến, chạy PostgreSQL thật, làm frontend và chạy E2E trên trình duyệt**.
- **PostgreSQL thật (postgis 16, container tạm):** migration 0011 → 0013 nâng và hạ cấp sạch; seed 3 role / 44 quyền / 56 cấp quyền; backfill `email_verified_at` đúng; PostgreSQL tự từ chối `purpose` sai, trùng băm token và khóa ngoại sai; xóa user kéo theo xóa phiên; `sync_rbac` báo 0 quyền thiếu (seed khớp code). Chạy bằng cách dựng sẵn hai bảng nền (`users`, `itineraries`) vì chuỗi migration gốc không chạy được từ đầu (xem bên dưới).
- **Hai lỗi có sẵn trên `main`, không do nhánh này gây ra, chưa sửa:**
  1. Migration `0002_team_database_architecture` lỗi trên PostgreSQL sạch: `COALESCE could not convert type jsonb to json` (cột `constraints` được tạo là `json`, nhưng câu lệnh dùng `'{}'::jsonb`). Nghĩa là không dựng được database từ đầu bằng `alembic upgrade head`.
  2. `Base.metadata.create_all` cũng lỗi trên PostgreSQL với `geoalchemy2` hiện tại (`PointGeometry.load_dialect_impl` nhận `dialect=None`). Chưa có đường nào dựng schema PostgreSQL từ đầu cho dự án này.
- **E2E trên trình duyệt thật (Chrome tự động + backend + Vite, access token 20 giây để ép làm mới liên tục):** 32/32 kiểm tra qua, không có lỗi console. Gồm: cookie `HttpOnly`, refresh cookie `Path=/api`, JavaScript không đọc được token, 102 request song song trong 45 giây không mất phiên (token đổi 9 lần), thu hồi thiết bị từ xa có hiệu lực ngay, quên/đặt lại mật khẩu không lộ tài khoản, liên kết dùng một lần, claim vé, và link chia sẻ trần không hiện form claim.
- Sửa thêm trong phiên này: `make_user` của test cho phép ghi đè mọi cột; thông báo lỗi đăng nhập/token/mật khẩu yếu được dịch theo ngôn ngữ trên frontend; trang chia sẻ không còn báo "vé đã liên kết với tài khoản" cho mọi người đã đăng nhập; log cảnh báo Redis gọn một dòng thay vì traceback.
- **Còn lại:**
  - Đặt lại mật khẩu của tài khoản admin hiện không đòi MFA; Giai đoạn 5 phải chặn việc này.
  - `/api/auth/password/forgot` chỉ giới hạn 1 email/phút mỗi tài khoản; rate limit theo IP vẫn tắt mặc định (Giai đoạn 6).
  - Chân trang và vài chỗ khác của ứng dụng đang hiện nguyên khóa dịch (`footer.colExplore`, `profile.savedTrips`): thiếu khóa i18n có từ trước, chưa xử lý.

### Ghi chú Giai đoạn 5-6
- **MFA:** TOTP RFC 6238 (±1 bước, chống dùng lại mã bằng `user_mfa.last_used_step`), 10 mã khôi phục dùng một lần (băm SHA-256), seed mã hóa Fernet bằng `INTEGRATION_SECRETS_KEY`, đăng nhập hai bước (`/login` trả `mfa_ticket`, `/login/mfa` hoàn tất), khóa sau 5 lần sai trong 15 phút. Admin chưa có MFA chỉ gọi được `account:read`/`account:mfa` (403 `MFA_REQUIRED`), không tắt được MFA và không đặt lại mật khẩu qua email được. Công tắc `ADMIN_MFA_REQUIRED` mặc định bật ở production, tắt ở dev/demo; tắt thì mọi hành vi trên không áp dụng.
- **Hardening:** rate limit mặc định bật ở production, thêm nhóm `costly` (`/api/geocoding`, `/api/ml`); chặn đoán mật khẩu theo (email, IP)=5, email=20, IP=50 trong 15 phút từ `auth_events` (email lạ đếm giống email thật); header `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `no-store` cho `/api/auth/*`, HSTS ở production; gỡ `AUTH_SECRET`, `SESSION_TTL_SECONDS`, `create_session_token`, cookie `le_session`; `X-Provider-Access-Key` tắt mặc định ở production (`ALLOW_PROVIDER_ACCESS_KEY`).
- **Kiểm chứng:** 269 test backend; E2E Chrome thật 13/13 cho MFA; migration 0014 lên/xuống trên PostgreSQL 16 thật. **Chưa kiểm chứng:** Redis thật (chỉ chạy fallback DB), chuỗi migration từ đầu trên PostgreSQL (lỗi `0002` có sẵn).
- Việc `/api/auth/password/forgot` chưa có rate limit riêng theo IP ngoài nhóm `auth` chung.
