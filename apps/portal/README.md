# Local Explorer Portal

Cổng dùng chung cho **đối tác** và **quản trị viên** (React + Vite + Tailwind, light mode), tách khỏi web khách (`apps/web`).

## Luồng

1. Đăng nhập (`/login`) hoặc đăng ký đối tác (`/register`, form 4 bước).
2. Vào Home (`/`) có 2 widget **Portal Đối tác** và **Portal Quản trị**. Bấm vào thì mới kiểm tra quyền theo `role`:
   - `provider` → `/partner`
   - `admin` → `/admin`
   - `traveler` bấm Portal Đối tác → được mời gửi hồ sơ đối tác (`POST /api/auth/partner/apply`).
3. Đối tác `pending` / `rejected` / `suspended` xem được portal nhưng **không ghi được** (API trả `PROVIDER_NOT_APPROVED`).

| Khu vực | Trang |
|---|---|
| Đối tác | Tổng quan, Trải nghiệm & Slot (mở slot lặp nhiều ngày, cập nhật số chỗ), Đặt chỗ, Hồ sơ (gửi lại khi bị từ chối) |
| Quản trị | Tổng quan, Đối tác (hàng chờ duyệt, duyệt / từ chối / tạm khóa / mở lại), Người dùng (tìm kiếm, đổi vai trò, khóa, đăng xuất mọi thiết bị) |

## Chạy

```bash
npm install
npm run dev            # http://localhost:8081, proxy /api -> http://127.0.0.1:8000
API_PROXY_TARGET=http://127.0.0.1:8010 npm run dev   # API ở cổng khác
npm run build
```

Docker: service `portal` trong `docker-compose.yml` (cổng `PORTAL_PORT`, mặc định 5174). Nginx proxy `/api` cùng origin
nên cookie đăng nhập là host-only và tách biệt với web khách.

API cần `PORTAL_APP_URL` để link trong email (xác minh, đặt lại mật khẩu) của tài khoản đối tác/quản trị trỏ về portal
và để origin của portal qua được kiểm tra CSRF.
