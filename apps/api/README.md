# API — Local Explorer AI

The FastAPI backend in apps/api/app serves the web application and catalog, planner, account/access-control, provider/admin, and booking flows. Endpoint contracts are described in [docs/api.md](../../docs/api.md).

> **Status:** This repository contains a prototype. Adapter code or configuration does not prove that Goong, OAuth, an LLM, email, or payments have passed acceptance testing in staging. The rule baseline is the default ranker; the XGBoost bootstrap artifact uses weak labels and is not a production model. E5 and flood-risk weights are not included in the repository. See the [ranking benchmark](../../docs/experience-ranker-benchmark.md) and [ML guide](../../docs/ml-training-and-data.md).

## Business boundaries

- **Framework Web**: [FastAPI 0.142+](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) (Asynchronous ASGI)
- **Cơ sở Dữ liệu & ORM**: PostgreSQL 16 + PostGIS 3.4, [SQLAlchemy 2.0](https://www.sqlalchemy.org/), [GeoAlchemy2](https://geoalchemy-2.readthedocs.io/), [Alembic](https://alembic.sqlalchemy.org/)
- **Xác thực & Bảo mật**: JWT RS256 trong cookie HTTP-only (`le_at`/`le_rt`), refresh xoay vòng, MFA TOTP cho admin, Google OAuth 2.0 PKCE, Argon2/PBKDF2 Password Hashing, Fernet AES-128-CBC encryption cho khóa tích hợp động
- **Học máy Cục bộ (Local ML)**:
  - `xgboost` (XGBRanker 13 features, NDCG@5 = 0.9516)
  - `sentence-transformers` + `multilingual-e5-small` (Vector Search chạy trên CPU)
  - `scikit-learn` + `joblib` (Saigon Flood Risk Classifier)
- **Định tuyến & Địa lý**: Goong Directions API + Goong Forward Geocoding (với cache in-memory TTL và provenance)
- **Thanh toán Trực tuyến**: Cổng VNPay (HMAC-SHA512 với sandbox/production) và Ví MoMo (HMAC-SHA256 captureWallet)
- **Vận hành & Hàng đợi**: Transactional notification outbox worker (`worker.py`) for email and opt-in Web Push, Redis Rate Limiting, HTTP structured JSON logging
- **Bot Tự Động & 3D**: Telegram Bot Webhook sync & n8n forwarding (`admin_bot.py`), 3D Digital Twin Landmark calibration service (`models_3d.py`)

- The planner checks feasibility against time, budget, locked stops, capacity, and outbound/return routes.
- The ranker only orders candidates that have passed feasibility filters; it does not confirm slots or prices and does not replace planner checks.
- POIs, experiences, and slots should be used operationally only when their provenance/evidence is suitable and current.
- Payment/provider callbacks, OAuth, email, and map APIs require credentials, a test/staging environment, HTTPS callbacks where applicable, and separately logged smoke tests.

## Run locally (PowerShell)

    cd apps/api
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    # If apps/api/.env does not exist: Copy-Item ..\..\.env.example .env
    alembic upgrade head
    python -m uvicorn app.main:app --reload --port 8000 --no-access-log --ws-max-size 65536

Do not commit environment files containing secrets. The database and integration settings may require configuration; see [authentication/search setup](../../docs/auth-and-search-setup.md), [integration settings](../../docs/integration-settings.md), and the [data model](../../docs/data-model.md).

## Tests

    pytest -q

Run from apps/api. Report the suite as passing only when the process exits normally with code 0. CI runs backend tests, lint, and Alembic history checks according to the [workflow](../../.github/workflows/ci.yml).

## Source layout

- app/api/routes/: HTTP routers.
- app/services/: planner, ranking, booking, catalog, and business logic.
- app/adapters/: external-service integrations.
- app/models/ and app/schemas/: ORM models and data contracts.
- migrations/: Alembic revisions.
- tests/: API and business-logic tests.

## Documentation

### Bước 2: Cài đặt thư viện dependencies
```powershell
# Cài đặt thư viện cốt lõi
pip install -r requirements.txt

# (Khuyên dùng) Cài đặt thư viện Học máy và Vector E5
pip install -r requirements-ml.txt
pip install -r requirements-e5.txt
```

### Bước 3: Cấu hình biến môi trường
Tạo file `.env` tại thư mục gốc repository (`g:\GITHUB\LoaclExplorerAI\.env`) theo mẫu `.env.example`. Đảm bảo các biến quan trọng sau đã được khai báo:
```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/local_explorer
# Sinh khóa: python -m scripts.generate_auth_keys
AUTH_JWT_KEY_ID=
AUTH_JWT_PRIVATE_KEY_B64=
APP_SIGNING_SECRET=your-secure-app-signing-secret
INTEGRATION_SECRETS_KEY=your-fernet-master-key-base64
ROUTING_PROVIDER=goong
GOONG_API_KEY=your-goong-api-key
```

*Mẹo sinh khóa Fernet master key cho `INTEGRATION_SECRETS_KEY`:*
```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Bước 4: Chạy Migration & Nạp dữ liệu mô phỏng
```powershell
# Nâng cấp toàn bộ lược đồ DB lên phiên bản mới nhất (0010_place_import_staging)
alembic upgrade head

# Nạp dữ liệu mô phỏng ban đầu và tài khoản thử nghiệm
python -m scripts.seed_db
```

### Bước 5: (Tùy chọn) Tải mô hình Multilingual E5 cục bộ
```powershell
python -m scripts.download_e5_model
```

### Bước 6: Khởi chạy API Server
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --no-access-log --ws-max-size 65536
```
- 🌐 **Swagger UI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 📖 **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- 🩺 **Kiểm tra Liveness**: [http://localhost:8000/health](http://localhost:8000/health)
- 🩺 **Kiểm tra Readiness**: [http://localhost:8000/ready](http://localhost:8000/ready)
- 🤖 **Telegram Bot & System Settings**: `/api/admin/bot/*`, `/api/admin/system-settings`
- 🏢 **3D Landmark Calibration**: `/api/models-3d/*`
- 📥 **Place Import Staging**: `/api/admin/staging-places/*`

### Bước 7: Khởi chạy Background Outbox Worker (Trong terminal riêng)
```powershell
python -m scripts.worker
```
*Worker tự động quét bảng `notification_deliveries` để gửi email và Web Push cho các sự kiện đặt chỗ. Web Push yêu cầu chạy migration mới nhất và cấu hình ba biến `WEB_PUSH_VAPID_*`; khóa riêng chỉ lưu trong secret manager.*

---

## 🧪 Chạy Kiểm thử Tự động (Tests)

Bộ kiểm thử được viết bằng `pytest` và kiểm thử toàn diện từ Router, Solver, ML Ranker đến Booking State Machine:
```powershell
cd apps/api
pytest -q
```
*Yêu cầu kiểm thử: Quá trình test phải hoàn tất bình thường với mã thoát **0** (exit code 0).*

---

## 🔐 Cơ chế Bảo vệ & Ranh giới Dữ liệu (Safety Boundaries)

1. **Khóa Giữ Chỗ (Seat Holds)**: Sử dụng cơ chế khóa mức hàng `SELECT ... FOR UPDATE` trên PostgreSQL, tạo phiên giữ chỗ 15 phút (`pending_provider`). Không cho phép đặt chỗ nếu dữ liệu mang nhãn `simulated` hoặc minh chứng chưa được xác minh (`verified`).
2. **Cổng Thanh toán Fail-closed**: Chỉ mở URL thanh toán khi đầy đủ chữ ký, mã merchant và webhook IPN hợp lệ. VNPay sử dụng HMAC-SHA512; MoMo sử dụng HMAC-SHA256. Webhook IPN là nguồn chân lý duy nhất để chốt trạng thái `confirmed`.
3. **Mã hóa Khóa Tích hợp (Fernet Encryption)**: Mọi thông tin nhạy cảm của cổng thanh toán và bên thứ 3 do Quản trị viên nhập vào tab `/admin` đều được mã hóa trước khi lưu vào bảng `integration_settings`.

[API](../../docs/api.md) · [Architecture](../../docs/architecture.md) · [Bookings/payments](../../docs/bookings-and-payments.md) · [Operations](../../docs/operations.md) · [Research proposal](../../docs/research-proposal.md)

