# Local Explorer AI — Backend API (`apps/api`)

> **Enterprise FastAPI Backend Application**  
> **Framework:** FastAPI 0.142+ · Python 3.12+ · SQLAlchemy 2.0 · PostgreSQL 16 + PostGIS 3.4 / SQLite · Uvicorn  
> **Port:** `8000` · **OpenAPI Documentation:** `http://localhost:8000/docs`

---

## 1. Architectural Role & Service Boundaries

`apps/api` provides the core business logic, geospatial intelligence, itinerary optimization, machine learning inference, and data governance for Local Explorer AI.

### Key Architectural Boundaries
- **Deterministic Planning Core:** Guarantees temporal and physical feasibility (opening hours, capacity, remaining budget, locked stops, travel order) before any ranking algorithm is applied.
- **Machine Learning & Heuristic Gate:** The active ranker defaults to `rule-baseline-v1`. Experimental models (XGBoost bootstrap ranker, Tour quote win model) are governed by integrity checks and explicit deployment flags.
- **Two-Phase Booking Commerce:** 15-minute optimistic seat holds with version-checked state transitions, provider approval, and cryptographically verified payment callbacks (VNPay / MoMo).
- **Hardened Security & RBAC:** RS256 JWT cookies with rotating refresh tokens, Argon2id password hashing, RFC 6238 TOTP MFA for administrators, and Fernet encryption for third-party secrets.

---

## 2. API Router Catalog (33 Modular Routers)

The API endpoints are modularized in `app/api/routes/` and registered in `app/main.py`:

| Router Domain | Prefix / Namespace | Description | Key Source File |
|---|---|---|---|
| **Authentication** | `/api/auth` | Register, login, logout, password recovery, session status, Google OAuth PKCE | `routes/auth.py` |
| **Multi-Factor Auth** | `/api/auth/mfa` | TOTP setup, QR code generation, code verification, backup recovery codes | `routes/mfa.py` |
| **Role-Based Access** | `/api/admin/rbac` | Role permissions matrix, service accounts, permission audits | `routes/rbac.py` |
| **Places & Catalog** | `/api/pois`, `/api/experiences` | Public catalog of places, activities, and dated slots with evidence provenance | `routes/catalog.py` |
| **Places Admin** | `/api/admin/places` | POI moderation, catalog updates, duplicate detection, photo reviews | `routes/places_admin.py` |
| **Itinerary Planner** | `/api/itineraries` | Deterministic multi-objective itinerary solver, replanning advice, version history | `routes/planner.py` |
| **Interactive Trips** | `/api/trips` | Multi-turn conversational planning via Server-Sent Events (SSE), follow-ups, stop pinning | `routes/trips.py` |
| **Routing & Geo** | `/api/routing`, `/api/geocoding` | Goong Directions routing, ETA calculation, road polylines, forward geocoding | `routes/routing.py` |
| **AI Workflows** | `/api/ai`, `/api/chat` | Versioned prompt catalog (v3.2.0), conversation parser, offline fallback | `routes/ai.py`, `routes/chat.py` |
| **Machine Learning** | `/api/ml` | Active ranker status, candidate experience ranking, advisory flood risk | `routes/ml.py` |
| **Operator Orgs** | `/api/operator` | Tour operator tenant profiles, company settings, member management | `routes/operator.py` |
| **Operator Quotes** | `/api/operator/quotes` | B2B customized tour quotation generator, cost breakdown, margin guard | `routes/operator_quotes.py` |
| **Operator Rate Cards**| `/api/operator/rate-cards` | Supplier rate cards (transport, guide, hotels, meals, tickets) | `routes/operator_rate_cards.py` |
| **Operator Reconcile** | `/api/operator/reconcile` | Quote-to-actual cost variance analysis, financial margin audits | `routes/operator_reconcile.py` |
| **Public Quotes** | `/api/public/quotes` | Customer-facing shareable quote landing page, hold confirmation | `routes/public_quotes.py` |
| **Booking & Seats** | `/api/bookings` | 15-minute seat holds, ticket generation, provider confirmation | `routes/bookings.py` |
| **Place Reviews** | `/api/place-reviews` | Verified traveler reviews, ratings, and moderation flags | `routes/place_reviews.py` |
| **Trip Reviews** | `/api/reviews` | Completed itinerary feedback and rubric labeling for ML training | `routes/reviews.py` |
| **Collaboration** | `/api/collaborations` | Multi-user shared itinerary collaboration and invite links | `routes/collaboration.py` |
| **3D Landmarks** | `/api/models-3d` | 3D Digital Twin GLB landmark models, scale/heading calibration | `routes/models_3d.py` |
| **Landmark Stories** | `/api/landmark-stories` | Cultural stories, historical facts, and audio narration scripts | `routes/landmark_stories.py` |
| **Meshy 3D Engine** | `/api/meshy` | Generative Text-to-3D and Image-to-3D job dispatch and GLB download | `routes/meshy.py` |
| **Web Push** | `/api/push-notifications` | Browser Web Push subscription registration and VAPID public key | `routes/push_notifications.py` |
| **Platform Ops** | `/health`, `/ready`, `/ops` | Health check, DB migration state, outbox backlog, uptime telemetry | `routes/health.py`, `routes/ops.py` |
| **Admin Bots** | `/api/admin/bot` | Telegram webhook receiver, n8n workflow sync, Zalo integration | `routes/admin_bot.py` |

---

## 3. Database Architecture & Migrations

The database layer utilizes **SQLAlchemy 2.0** with **Alembic** for schema versioning. It supports PostgreSQL 16 + PostGIS 3.4 for production and SQLite for lightweight local development.

### Migration Sequence (30 Revisions)
Revisions are located in `apps/api/migrations/versions/`:
- `0001_initial` to `0010_place_import_staging`: Core entities (User, Provider, POI, Experience, Slot, Evidence, AuditLog).
- `0011_auth_foundation` to `0015_partner_onboarding`: RS256 Auth, RBAC permissions, MFA TOTP, password recovery.
- `0016_portal_platform` to `0018_web_push_notifications`: Dedicated portal multi-tenancy, Web Push subscriptions.
- `0019_itinerary_collaboration` to `0024_itinerary_completion`: Group sharing, landmark stories, place reviews, Meshy jobs.
- `0025_operator_orgs` to `0030_quote_channel_msg`: B2B Tour Operator module (OperatorOrg, TourTemplate, RateCard, Quote, QuoteRevision, CostActual).

To run migrations:
```bash
alembic upgrade head
```

---

## 4. Machine Learning & Heuristic Services

1. **Active Production Ranker (`rule-baseline-v1`):**
   - Implemented in `app/services/ranking_service.py`.
   - Deterministic utility function balancing user intent weights, weather conditions, indoor suitability, and travel distance.
   - Zero load overhead, 100% explainable, active by default.
2. **Bootstrap XGBoost Ranker (`models/ai-ranker/`):**
   - XGBRanker model trained on weak scenario labels (`ranker-features-v2`, 15 features).
   - Blocked from production by default (`deployment_eligible=false`). Enabled only when `ENABLE_BOOTSTRAP_RANKER=true` is set.
3. **Tour Quote Win Optimizer (`models/quote-win/`):**
   - XGBoost classifier trained on 21,980 synthetic quote history records (`quote-win-features-v1`, 18 features).
   - Monotonic price constraints ensure reasonable price sensitivity. Backtest demonstrates +9.5% profit on balanced strategy.
4. **Multilingual Semantic Search (`models/e5/`):**
   - Dense vector embeddings via `intfloat/multilingual-e5-small`. Weights excluded from git to keep repo lean.

---

## 5. Security Architecture & Hardening

1. **Token Authentication:**
   - Access Token: RS256 JWT signed with private key (`AUTH_JWT_PRIVATE_KEY_B64`), 15-minute lifetime, stored in HTTP-only cookie (`le_at`).
   - Refresh Token: High-entropy opaque string, stored in HTTP-only cookie (`le_rt`), hashed in database (`refresh_hash`) with automatic replay detection.
2. **Password Security:**
   - Hashed using **Argon2id** (`argon2-cffi`). Passwords meeting legacy hash formats are seamlessly upgraded upon login.
3. **Multi-Factor Authentication:**
   - RFC 6238 TOTP with encrypted backup recovery codes. Enforced for administrators in production (`ADMIN_MFA_REQUIRED=true`).
4. **Integration Secrets Vault:**
   - External API keys (Goong, VNPay, MoMo, OpenAI, Meshy) stored in database are encrypted at rest using **Fernet AES-128-CBC** (`INTEGRATION_SECRETS_KEY`).
5. **CSRF Protection:**
   - State-changing HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`) with cookie authentication require explicit Origin matching against `CORS_ORIGINS`.

---

## 6. Local Setup & Testing

### 6.1. Environment Setup
```powershell
cd apps/api

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install core dependencies
pip install -r requirements.txt

# (Optional) Install ML and Vector dependencies
pip install -r requirements-ml.txt
pip install -r requirements-e5.txt
```

### 6.2. Configuration
Copy the template `.env.example` from repository root or configure `apps/api/.env`:
```env
APP_ENV=development
DATABASE_URL=sqlite:///local_explorer.sqlite3
ROUTING_PROVIDER=goong
GOONG_API_KEY=your-goong-api-key
AUTH_JWT_KEY_ID=dev-key
AUTH_JWT_PRIVATE_KEY_B64=your-base64-rsa-private-key
APP_SIGNING_SECRET=your-secure-app-signing-secret
INTEGRATION_SECRETS_KEY=your-fernet-master-key-base64
```

*Generate RS256 Auth Keys:*
```powershell
python -m scripts.generate_auth_keys
```

*Generate Fernet Secret Key:*
```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 6.3. Run Migrations & Start Server
```powershell
# Upgrade database schema
alembic upgrade head

# Start API server with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --no-access-log --ws-max-size 65536
```

### 6.4. Running Tests
Run the test suite using pytest. On Windows, explicitly pass `APP_ENV=test` and disable cacheprovider to avoid file permission conflicts:
```powershell
$env:APP_ENV="test"
pytest -p no:cacheprovider -q
```
*(346+ core tests pass with 0 failures).*
