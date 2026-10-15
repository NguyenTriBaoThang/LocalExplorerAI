# Thực nghiệm weak-label cho xếp hạng trải nghiệm

## Dữ liệu

ranking_candidates_labeled.csv có 3.828 dòng: 638 địa điểm ứng viên OSM × 6 intent profiles giả định. Nhãn là quy tắc phân loại/điểm do pipeline tạo, không phải đánh giá của khách thật. Một số giá, thời lượng và ETA là ước tính; xem estimation_parameters.json và source_audit.json.

Không có bằng chứng slot, capacity, quyết định planner thật hay trạng thái verified. Không nhân bản query để làm lớn mẫu. Phép thử giữ POI tách biệt giữa các split nhưng không đo được tổng quát hóa sang ý định mới.

## Benchmark hiện có

Thư mục colab-results/ lưu metadata, metric, schema, preprocessing, model card, dự đoán test và so sánh validation được cung cấp. Diễn giải đúng theo benchmark weak-label; không dùng chỉ số để tuyên bố chất lượng gợi ý cho người thật.

Rule baseline là phương án ranking mặc định của API. Artifact bootstrap không production-eligible. Dùng notebook/script được dẫn ở [benchmark guide](../../../docs/experience-ranker-benchmark.md) để tái lập và ghi rõ dependency/version/hash.
