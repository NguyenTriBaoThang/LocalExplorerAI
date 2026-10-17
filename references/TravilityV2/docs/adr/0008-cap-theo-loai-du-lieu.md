# Khi node chết: ghi ưu tiên nhất quán, đọc ưu tiên sẵn sàng; không tự động failover

Mỗi loại dữ liệu có một lựa chọn riêng khi mạng chia cắt hoặc node chết. Ghim, version Itinerary, áp dụng Proposal và đăng ký tài khoản chỉ ghi vào node chính; node chính chết thì từ chối kèm thông báo rõ, không ghi tạm ở nơi khác. Place, Destination và đăng nhập được đọc từ bản sao khi cần, chấp nhận dữ liệu trễ. Cache và bộ đếm rate limit hỏng thì bỏ qua, không chặn người dùng. Node chết được bật lại bằng tay.

Lý do: sai version hoặc mất một lần ghim là lỗi người dùng nhìn thấy và không tự sửa được, còn Place trễ vài giây thì vô hại vì gần như không đổi. Tự động bầu node chính (Patroni + etcd) thêm 3–4 container và là nguồn lỗi lớn nhất ngay trước buổi demo.

## Consequences

- Node chính của database chung chết: không đăng ký được, nhưng đăng nhập, tìm Place, lập lịch và sửa lịch vẫn chạy (Trip nằm ở shard).
- Một shard chết: chỉ User của shard đó bị ảnh hưởng, và bị ảnh hưởng hoàn toàn cho tới khi bật lại — shard không có bản sao.
- Trip luôn đọc từ node chính của shard, nên không có cảnh vừa ghi xong đọc lại ra dữ liệu cũ.
- Bảng hành vi đầy đủ: [spec §10](../superpowers/specs/2026-10-01-scale-he-phan-tan-design.md).
