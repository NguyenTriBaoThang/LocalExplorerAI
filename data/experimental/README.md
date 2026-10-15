# Dữ liệu thực nghiệm

Nội dung tại đây phục vụ nghiên cứu/kiểm tra pipeline; không phải catalog vận hành hay tập huấn luyện production.

## Ranking

Xem [ranking/README.md](ranking/README.md). Hiện có dữ liệu OSM-derived với sáu intent do analyst giả định và nhãn quy tắc yếu. Kết quả phản ánh việc học lại quy tắc tạo nhãn, không phải sở thích người dùng thật.

## Flood report experiment

flood_training_weak_labels.csv là thực nghiệm về khả năng xuất hiện báo cáo công khai, gồm các nhãn âm giả định theo sampling. Nó không dự báo ngập vật lý, không xác nhận đường khô và không được dùng làm flood-risk model cho planner.

Không dùng các dữ liệu này để tạo tuyên bố production hoặc “đã xác minh”. Mọi biến ước tính và provenance cần được giữ lại.
