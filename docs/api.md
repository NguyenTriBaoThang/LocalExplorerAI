# Local Explorer AI — API Reference & Endpoint Specification

> **Base URL:** `http://localhost:8000` (Local) · `https://api.localexplorerai.site` (Production)  
> **Interactive Swagger Documentation:** `/docs` · **OpenAPI Specification:** `/openapi.json`  
> **Conventions:** ISO 8601 timestamps (`+07:00` or UTC), VND amounts as integers, `X-Request-ID` correlation header on every request/response.

---

## 1. System Health & Telemetry

### `GET /health`
Liveness probe.
- **Access:** Public
- **Response `200 OK`:**
  ```json
  { "status": "ok" }
  ```

### `GET /ready`
Readiness probe checking database connectivity and core services.
- **Access:** Public
- **Response `200 OK`:**
  ```json
  { "status": "ready", "database": "connected", "app_env": "production" }
  ```

### `GET /ops/summary`
Operational dashboard metrics: notification outbox backlog, active holds, system error rate.
- **Access:** Admin only (`P.SYSTEM_OPS_READ`)

---

## 2. Authentication & Account Management (`/api/auth`)

Authentication utilizes stateless **RS256 JWT** tokens in HTTP-only cookies (`le_at`) and rotating refresh tokens (`le_rt`).

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/api/auth/register` | Create traveler account with password strength check | Public |
| `POST` | `/api/auth/login` | Authenticate with email/password; returns session cookies or MFA challenge | Public |
| `POST` | `/api/auth/login/mfa` | Complete login challenge using 6-digit TOTP code or backup recovery code | Public |
| `GET` | `/api/auth/session` | Inspect active session, user identity, role, and permission matrix | Public / Authenticated |
| `POST` | `/api/auth/refresh` | Rotate session cookies with cryptographic reuse detection | Public (Cookie) |
| `POST` | `/api/auth/logout` | Revoke current session and clear auth cookies | Authenticated |
| `POST` | `/api/auth/forgot-password` | Request password reset token via email | Public |
| `POST` | `/api/auth/reset-password` | Set new password using single-use verification token | Public |
| `GET` | `/api/auth/google/login` | Initiate Google OAuth 2.0 PKCE flow | Public |
| `GET` | `/api/auth/google/callback` | Google OAuth callback handler; starts authenticated session | Public |

### MFA Endpoints (`/api/auth/mfa`)
- `POST /api/auth/mfa/setup`: Generates TOTP secret and QR code URI.
- `POST /api/auth/mfa/enable`: Verifies code and enables MFA, returning 8 backup recovery codes.
- `POST /api/auth/mfa/disable`: Disables MFA with password confirmation.

---

## 3. Places & Experiences Catalog (`/api/pois`, `/api/experiences`)

### `GET /api/pois`
Lists verified points of interest in Ho Chi Minh City.
- **Query Parameters:** `district`, `category`, `search`, `scope` (`pilot` or `citywide`).
- **Response `200 OK`:**
  ```json
  [
    {
      "id": "poi_buu_dien_tphcm",
      "name": "Bưu điện Trung tâm Sài Gòn",
      "district": "Quận 1",
      "latitude": 10.7798,
      "longitude": 106.6999,
      "category": "van-hoa",
      "address": "02 Công xã Paris, Bến Nghé, Quận 1",
      "verification_status": "verified",
      "has_3d_model": true
    }
  ]
  ```

### `GET /api/pois/{id}`
Returns full POI details, current evidence provenance, operating hours, photos, and linked experiences.

### `GET /api/experiences`
Lists bookable activities offered at POIs.
- **Query Parameters:** `intent`, `is_indoor`, `is_hands_on`, `group_size`, `max_price_vnd`.

### `GET /api/experiences/{id}/slots`
Returns scheduled capacity windows for an activity within a datetime range (`start_at`, `end_at`).

---

## 4. Smart Route Planner (`/api/itineraries`)

### `POST /api/itineraries/plan`
Executes the deterministic heuristic solver to build a feasible multi-stop itinerary.
- **Request Body:**
  ```json
  {
    "start_at": "2026-11-20T09:00:00+07:00",
    "end_at": "2026-11-20T17:00:00+07:00",
    "group_size": 2,
    "budget_vnd": 1500000,
    "travel_mode": "motorcycle",
    "intent_weights": { "thủ_công": 1.0, "ẩm_thực": 0.8, "văn_hóa": 0.5 },
    "locked_experience_ids": []
  }
  ```
- **Response `200 OK`:** Returns `itinerary_id`, `feasibility_status`, total cost, stops with confirmed time windows, and Goong road route legs with encoded polylines.

### `POST /api/itineraries/{id}/replan-advice`
Triggered upon disruption (slot cancellation or adverse weather). Returns solver-feasible replacement proposals with intent-preservation metrics.

### `POST /api/itineraries/{id}/replan-advice/accept`
Applies chosen replacement proposal, incrementing itinerary version.

---

## 5. Interactive Trips & Conversational Planner (`/api/trips`)

Supports real-time conversational itinerary building with SSE streaming.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/trips/stream` | Stream chat turns and itinerary updates via Server-Sent Events (`text/event-stream`) |
| `GET` | `/api/trips/{id}` | Retrieve complete multi-version trip history and message log |
| `POST` | `/api/trips/{id}/pin` | Pin or unpin a specific stop to prevent replanning modifications |
| `POST` | `/api/trips/{id}/replan` | Request replan with natural language modifications (e.g. "thêm một quán cà phê buổi chiều") |
| `POST` | `/api/trips/{id}/versions/{version}/restore` | Rollback trip state to an earlier saved version |

---

## 6. Machine Learning & Inference (`/api/ml`)

### `GET /api/ml/status`
Reports active ranker (`rule-baseline-v1`), model file integrity checksums, and deployment eligibility flags.

### `POST /api/ml/rank-experiences`
Ranks candidate experiences.
- Candidates must pass hard feasibility checks prior to submission.
- Returns candidate list ordered by computed utility score with evidence attribution.

### `POST /api/ml/flood-risk`
Advisory road-flood risk assessment based on rainfall rate (mm/h), tide level, and topography.

---

## 7. B2B Tour Operator Module (`/api/operator`, `/api/public/quotes`)

Provides tour operators with automated quotation, costing, and margin protection.

### `POST /api/operator/quotes`
Generates a customized group tour quotation from an unstructured message or structured spec.
- Computes vehicle, guide, meal, ticket, and hotel costs from active supplier rate cards.
- Evaluates client win probability $P(\text{win})$ using `quote-win-xgb-synthetic`.
- Recommends balanced markup optimizing expected profit while respecting the minimum margin floor.

### `GET /api/operator/quotes/{id}/reconcile`
Compares estimated quote costs against actual supplier invoices to detect financial leakages.

### `GET /api/public/quotes/{token}`
Public customer landing page to view quote itinerary, pricing transparency, and accept quotation with 48-hour seat hold.

---

## 8. Commerce, Seat Holds & Payments (`/api/bookings`)

### `POST /api/bookings`
Reserves a 15-minute optimistic hold on an `ExperienceSlot`.
- Verifies slot capacity with optimistic locking.
- Returns `held_until` ISO 8601 expiration timestamp.

### `POST /api/bookings/{id}/payment-url`
Generates a cryptographically signed checkout redirect URL for **VNPay** (HMAC-SHA512) or **MoMo** (HMAC-SHA256).

### `POST /api/bookings/payment/vnpay-ipn` & `POST /api/bookings/payment/momo-ipn`
Asynchronous IPN webhook receivers. Verifies gateway cryptographic signatures, transitions booking to `confirmed`, and enqueues ticket email.

---

## 9. 3D Digital Twin & Generative Meshy Engine (`/api/models-3d`, `/api/meshy`)

### `GET /api/models-3d`
Returns metadata, GPS coordinates, scale, heading, and altitude calibration for 3D landmark models (GLB).

### `POST /api/meshy/jobs`
Dispatches a background Text-to-3D or Image-to-3D reconstruction task to Meshy.ai.
- Background worker polls Meshy API safely and downloads sanitized GLBs under 50 MB into storage.

### `GET /api/meshy/jobs/{id}/asset`
Serves validated, embedded GLB binary for preview in Three.js viewport.
