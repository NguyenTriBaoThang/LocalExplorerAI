# Model artifacts

Thư mục này lưu model artifacts và metadata. Có artifact trong Git không đồng nghĩa artifact được API chấp nhận hoặc đã đánh giá production.

## Trạng thái hiện tại

- ai-ranker/: có XGBoost ranker bootstrap và metadata đi kèm; nguồn nhãn là weak-label/bootstrap. API mặc định dùng rule baseline và chặn model không đủ điều kiện. Không promote artifact này thành production model.
- e5/: hiện chỉ có placeholder; weights chưa được đưa vào repo.
- flood-risk/: hiện chỉ có placeholder; chưa có model dự báo ngập tuyến đường được train từ nhãn quan trắc phù hợp.
- Flood report experiment nếu có nằm trong data/experimental/, là bài toán riêng và không phải model flood-risk.

## Nguyên tắc promotion

Kiểm tra model card, dataset provenance, schema, preprocessing, checksum, split và metrics. Ranking production cần dữ liệu có nhãn phù hợp, query-disjoint evaluation, so sánh công bằng với baseline và phê duyệt rõ ràng. Mọi model chỉ sắp xếp ứng viên đã qua hard feasibility checks của planner.

Xem [benchmark ranker](../docs/experience-ranker-benchmark.md), [hướng dẫn train](../docs/ml-training-and-data.md) và [model versioning](../MODEL_VERSIONING.md).
