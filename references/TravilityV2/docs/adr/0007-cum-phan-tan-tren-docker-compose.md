# Server là một cụm 4 service trên docker compose; chế độ một tiến trình vẫn giữ

Server tách thành 4 service theo loại tải — `api` (request nhẹ), `planner` (việc LLM chạy lâu, nhận từ Redis Streams), `llm-gateway` (mọi lời gọi LLM/embedding), `places` (tìm vector, km Goong) — sau một `nginx`, với database chung có bản sao đọc và dữ liệu người dùng chia 2 shard theo `user_id`. Tất cả chạy bằng `docker-compose.cluster.yml` trên một laptop. Thay phần "một server" của [ADR-0002](0002-postgres-tu-host-app-desktop-la-client.md); phần "Postgres tự host, app desktop là client" vẫn đúng. Chi tiết: [spec](../superpowers/specs/2026-10-01-scale-he-phan-tan-design.md).

Lý do: đồ án được chấm theo việc áp dụng và trình diễn được các kỹ thuật hệ phân tán, và app có vấn đề thật để mỗi kỹ thuật giải (lập lịch 10–30 giây giữ kết nối, quota LLM, một tiến trình Python một nhân CPU).

## Considered Options

- Tách đầy đủ 7–8 service, mỗi service một database: đúng sách hơn, nhưng 5 tuần chỉ đủ nối dây và phải viết lại phần lớn test.
- Giữ một khối + worker: ít rủi ro nhất, nhưng không trình bày được là microservice.
- Triển khai cloud nhiều máy thật: thuyết phục hơn về "phân tán", nhưng tốn tiền và buổi demo phụ thuộc mạng.

## Consequences

- Các service dùng chung một codebase và một image, khác nhau ở lệnh khởi động. Không deploy độc lập từng service; đổi lại giữ được `rules`, `domain` và bộ test dùng chung.
- Mỗi thành phần phân tán bật bằng một biến môi trường. Thiếu biến thì chạy như cũ, nên `docker compose up` hiện tại vẫn là cách chạy mặc định khi dev và là đường lui khi demo.
- Bảng người dùng và bảng chung nằm ở database khác nhau: mất khoá ngoại `trips.user_id → users`, không còn JOIN giữa hai nhóm bảng.
- Số shard cố định bằng 2 (phép chia dư). Thêm shard đòi chuyển dữ liệu; không làm.
- Ngữ nghĩa giao việc là "ít nhất một lần"; có khe hở hiếm gặp sinh hai version Itinerary giống nhau.
