# Local Explorer AI — Backend API Service

Dịch vụ Backend trung tâm của nền tảng **Local Explorer AI**, được xây dựng trên nền tảng **FastAPI**, **Python 3.12+**, **PostgreSQL 16 + PostGIS 3.4**, **SQLAlchemy 2.0**, **Alembic**, và **Redis**. Dịch vụ cung cấp toàn bộ RESTful API phục vụ thuật toán lập lịch trình khung giờ thực (Slot-aware Planner), mô hình học máy xếp hạng cục bộ (XGBoost Ranker), tìm kiếm ngữ nghĩa (Multilingual E5), phân tích rủi ro ngập lụt Sài Gòn, định tuyến Goong Maps, giữ chỗ và thanh toán trực tuyến (VNPay & MoMo), cùng các cổng quản lý phân quyền (RBAC).

---

## 🛠️ Ngăn xếp Công nghệ (Tech Stack)

- **Framework Web**: [FastAPI 0.142+](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) (Asynchronous ASGI)
- **Cơ sở Dữ liệu & ORM**: PostgreSQL 16 + PostGIS 3.4, [SQLAlchemy 2.0](https://www.sqlalchemy.org/), [GeoAlchemy2](https://geoalchemy-2.readthedocs.io/), [Alembic](https://alembic.sqlalchemy.org/)
- **Xác thực & Bảo mật**: HTTP-only Session Cookie (`le_session`), Google OAuth 2.0 PKCE, Argon2/PBKDF2 Password Hashing, Fernet AES-128-CBC encryption cho khóa tích hợp động
- **Học máy Cục bộ (Local ML)**:
  - `xgboost` (XGBRanker 13 features, NDCG@5 = 0.9516)
  - `sentence-transformers` + `multilingual-e5-small` (Vector Search chạy trên CPU)
  - `scikit-learn` + `joblib` (Saigon Flood Risk Classifier)
- **Định tuyến & Địa lý**: Goong Directions API + Goong Forward Geocoding (với cache in-memory TTL và provenance)
- **Thanh toán Trực tuyến**: Cổng VNPay (HMAC-SHA512 với sandbox/production) và Ví MoMo (HMAC-SHA256 captureWallet)
- **Vận hành & Hàng đợi**: Transactional Email Outbox worker (`worker.py`), Redis Rate Limiting, HTTP structured JSON logging
- **Bot Tự Động & 3D**: Telegram Bot Webhook sync & n8n forwarding (`admin_bot.py`), 3D Digital Twin Landmark calibration service (`models_3d.py`)

---

## 📁 Cấu trúc Thư mục (`apps/api`)

```text
apps/api/
├── app/
│   ├── adapters/          # LLM Provider Adapters (OpenAI, Gemini compatible)
│   ├── api/routes/        # 14 modules định tuyến API:
│   │   ├── admin.py       # Dashboard KPI, Moderation, Duplicates Merge, Staging Places, Integrations, Audit
│   │   ├── admin_bot.py   # Telegram Bot Config, Webhook Sync, n8n Forwarding, Core System Settings
│   │   ├── ai.py          # AI Prompts, Replan Advice, Tagging, Similarity, XAI
│   │   ├── auth.py        # Đăng ký, Đăng nhập, Profile, Google OAuth 2.0 PKCE
│   │   ├── bookings.py    # Giữ chỗ 15p, Quyết định đối tác, VNPay & MoMo checkout & IPN
│   │   ├── catalog.py     # POI, Experience, Slots, E5 Semantic Search
│   │   ├── chat.py        # Trợ lý AI Concierge Chatbot & Constraints Parser
│   │   ├── health.py      # /health (Liveness) & /ready (Readiness PostGIS + Redis)
│   │   ├── ml.py          # /status, /rank-experiences, /flood-risk
│   │   ├── models_3d.py   # 3D Landmark Models, Toạ độ Calibrate, Cập nhật thông số 3D
│   │   ├── ops.py         # Giám sát Outbox Email, Background Jobs, Events
│   │   ├── planner.py     # Heuristic Planner, Itinerary CRUD, Versioning, Share, Feedback
│   │   ├── provider.py    # Quản lý POI, Hoạt động, Khung giờ, Evidence, Slot Assistant
│   │   └── routing.py     # Goong Routing capabilities & Forward Geocoding
│   ├── core/              # Config (pydantic-settings), Enums, Security & Fernet Vault
│   ├── db/                # SessionLocal, Base entity, Connection lifecycle
│   ├── models/            # SQLAlchemy Entities (User, Provider, POI, Slot, Itinerary, PlaceImportStaging...)
│   ├── prompts/           # Danh mục 8 prompt AI (manifest.json v3_0_0)
│   ├── repositories/      # Data Access Layer & DB Queries
│   ├── schemas/           # Pydantic Schemas xác thực dữ liệu vào/ra
│   └── services/          # Business Logic (Planner, Replanner, Ranker, VNPay, MoMo, BotService...)
├── migrations/            # Lịch sử lược đồ cơ sở dữ liệu Alembic:
│   └── versions/          # 0001_initial -> 0010_place_import_staging
├── scripts/               # Scripts tiện ích hệ thống:
│   ├── seed_db.py         # Nạp dữ liệu mô phỏng demo & tài khoản dev
│   ├── worker.py          # Background worker xử lý Email Outbox & Job nền
│   └── download_e5_model.py # Tải trọng số mô hình Multilingual E5 về local
├── tests/                 # Bộ kiểm thử tự động pytest (56+ test cases)
├── alembic.ini            # Cấu hình đường dẫn migration
├── Dockerfile             # Container build cho Backend API
├── requirements.txt       # Thư viện ứng dụng cốt lõi
├── requirements-ml.txt    # Thư viện mô hình Học máy (XGBoost, Scikit-learn)
└── requirements-e5.txt    # Thư viện Vector Embedding (Sentence-Transformers)
```

---

## 🚀 Hướng dẫn Cài đặt & Khởi chạy Cục bộ

### Bước 1: Chuẩn bị môi trường Python (3.12+)
```powershell
cd apps/api

# Khởi tạo môi trường ảo Python
python -m venv .venv

# Kích hoạt môi trường (Windows PowerShell):
.\.venv\Scripts\Activate.ps1

# Hoặc trên Linux/macOS:
# source .venv/bin/activate
```

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
AUTH_SECRET=your-secure-random-auth-secret-key-at-least-32-chars
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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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
*Worker tự động quét bảng `email_outbox` để gửi email xác nhận đặt chỗ, thông báo quyết định của nhà cung cấp và xử lý sự cố hủy ca.*

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
