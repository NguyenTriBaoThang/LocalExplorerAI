# Web application — Local Explorer AI

Frontend là SPA React + TypeScript chạy bằng Vite. Ứng dụng gọi API qua các đường dẫn tương đối /api; cấu hình Vite local proxy API và health checks sang http://127.0.0.1:8000.

## Chạy local

    cd apps/web
    npm ci
    npm run dev

Mở http://localhost:8080. Chạy backend riêng ở cổng 8000; cấu hình môi trường backend theo file .env.example ở thư mục gốc và tài liệu API. Không đưa API secret vào frontend vì giá trị phía client có thể bị người dùng xem.

## Kiểm tra và build

    npm run lint
    npm run build
    npm run preview

## Giao diện

Web có các luồng khám phá địa điểm, chat/trợ lý, lập lịch, chia sẻ/so sánh lịch và các khu vực theo vai trò. Tính khả dụng thực tế phụ thuộc API, dữ liệu đã được duyệt và cấu hình tích hợp. Placeholder, candidate import và dữ liệu thử nghiệm không được xem là catalog đã xác minh.

## Tài liệu liên quan

[API](../../docs/api.md) · [kiến trúc](../../docs/architecture.md) · [cấu hình đăng nhập/tìm kiếm](../../docs/auth-and-search-setup.md) · [proposal nghiên cứu](../../docs/research-proposal.md)
