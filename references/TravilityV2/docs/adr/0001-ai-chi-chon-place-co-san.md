# AI chỉ chọn Place có sẵn; code tính chi phí và Conflict

LLM hay bịa địa điểm, tọa độ sai, và cộng tiền sai — trên bản đồ lúc demo đó là lỗi lộ ngay. Vì vậy AI chỉ được tham chiếu Place trả về từ tool tìm kiếm trên dữ liệu nhóm tự thu thập; backend từ chối Itinerary chứa Place lạ và yêu cầu AI làm lại. Chi phí, giờ mở cửa, Tag bắt buộc và Conflict đều do code tính; AI chỉ chọn, sắp xếp và viết Reason/gợi ý.

## Considered Options

- Gọi API địa điểm live (Goong Places, Google Places): phủ rộng nhưng dữ liệu VN thưa/tốn phí, chất lượng demo khó kiểm soát.
- Để LLM tự sinh tên rồi geocode: nhanh nhất nhưng hay ra nơi sai hoặc đã đóng cửa.

## Consequences

Phạm vi app bị giới hạn bởi dữ liệu Place của từng Destination; thêm Destination = công thu thập dữ liệu, không phải công code.
