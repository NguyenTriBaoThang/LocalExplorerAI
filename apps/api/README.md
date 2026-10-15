# API — Local Explorer AI

Backend FastAPI trong apps/api/app phục vụ ứng dụng web và các luồng catalog, planner, tài khoản/phân quyền, provider/admin và booking. Hợp đồng endpoint được mô tả trong [docs/api.md](../../docs/api.md).

> **Trạng thái:** Đây là prototype trong repository. Mã adapter/cấu hình không chứng minh Goong, OAuth, LLM, email hay payment đã được nghiệm thu trên staging. Rule baseline là ranker mặc định; artifact XGBoost bootstrap dùng nhãn yếu và không phải model production. E5 và flood-risk weights chưa có trong repo. Chi tiết xem [benchmark ranking](../../docs/experience-ranker-benchmark.md) và [hướng dẫn ML](../../docs/ml-training-and-data.md).

## Ranh giới nghiệp vụ

- Planner kiểm tra khả thi theo thời gian, ngân sách, điểm khóa, sức chứa và tuyến đi-về.
- Ranker chỉ sắp xếp ứng viên đã qua bộ lọc khả thi, không xác nhận slot/giá hoặc thay thế kiểm tra planner.
- POI, experience và slot chỉ nên vận hành khi có provenance/evidence phù hợp và còn hiệu lực.
- Payment/provider callback, OAuth, email và API bản đồ cần credential, môi trường test/staging, HTTPS callback khi áp dụng và smoke test có log riêng.

## Chạy local (PowerShell)

    cd apps/api
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    # Nếu apps/api/.env chưa có: Copy-Item ..\\..\\.env.example .env
    alembic upgrade head
    python -m uvicorn app.main:app --reload --port 8000

Không commit file môi trường chứa secret. Database và integration settings có thể cần cấu hình; xem [auth/search setup](../../docs/auth-and-search-setup.md), [integration settings](../../docs/integration-settings.md) và [data model](../../docs/data-model.md).

## Kiểm thử

    pytest -q

Chạy từ thư mục apps/api. Chỉ báo suite pass khi tiến trình kết thúc tự nhiên với exit code 0. CI chạy backend tests, lint và kiểm tra Alembic history theo [workflow](../../.github/workflows/ci.yml).

## Cấu trúc mã nguồn

- app/api/routes/: router HTTP.
- app/services/: planner, ranking, booking, catalog và logic nghiệp vụ.
- app/adapters/: tích hợp với dịch vụ ngoài.
- app/models/ và app/schemas/: ORM và contract dữ liệu.
- migrations/: Alembic revisions.
- tests/: kiểm thử API và logic nghiệp vụ.

## Tài liệu

[API](../../docs/api.md) · [architecture](../../docs/architecture.md) · [booking/payment](../../docs/bookings-and-payments.md) · [operations](../../docs/operations.md) · [proposal nghiên cứu](../../docs/research-proposal.md)
