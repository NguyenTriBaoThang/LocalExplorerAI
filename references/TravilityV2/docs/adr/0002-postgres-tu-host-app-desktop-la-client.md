# PostgreSQL + pgvector tự host; app desktop là client

Nhóm chọn PostgreSQL (image pgvector/pgvector) chạy bằng Docker Compose cùng FastAPI thành một server; app desktop (pywebview) chỉ là client gọi API. Lý do: có tài khoản người dùng thật, cả nhóm dùng chung dữ liệu Place, và tìm Place theo embedding ngay trong SQL bằng pgvector.

## Considered Options

- SQLite nhúng trong app: đơn giản, chạy offline, nhưng không có tài khoản dùng chung và mỗi máy một bản dữ liệu.
- Supabase (Postgres cloud có Auth sẵn): ít code auth nhất, nhưng nhóm muốn tự làm chủ database.

## Consequences

Server phải chạy thì app mới dùng được; lúc demo cả server và client chạy trên cùng một laptop. Auth (email/mật khẩu, Google, quên mật khẩu) do nhóm tự làm trong FastAPI.
