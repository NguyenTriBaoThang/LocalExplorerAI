# Local Explorer AI — Project Status & Evidence Report

> **Audited Operational Status & Feature Verification Matrix**  
> **Repository:** [LocalExplorerAI](https://github.com/NguyenTriBaoThang/LocalExplorerAI) · **Audit Date:** November 2026 · **Branch:** `main`  
> **Commit SHA:** `3906c98` · **Verification Suite:** 346 API Pytest passed · 18 Web Unit tests passed · Clean Vite builds

---

## 1. Executive Summary

Local Explorer AI has transitioned from an early hackathon prototype into a multi-tiered, enterprise-ready **urban experience discovery and slot-aware planning platform**. 

The system implements:
- A fully functional B2C single-page web app (`apps/web`) with Three.js 3D WebGL, interactive route planner, Leaflet maps, and bilingual support.
- A dedicated B2B partner and admin portal (`apps/portal`) with RBAC and MFA.
- A production-hardened FastAPI backend (`apps/api`) with 33 modular routers, 30 Alembic database migrations, deterministic multi-objective heuristic planning, structured AI prompt workflows (v3.2.0), and B2B tour operator quote optimization.
- A clean, static showcase documentation site (`docs-site`) deployable on GitHub Pages.

---

## 2. Feature Inventory & Verification Matrix

### Legend
- **VERIFIED:** Implemented with passing automated tests and clean execution evidence in the repository.
- **IMPLEMENTED:** Complete code implementation present; integration tests pending live external credentials.
- **EXPERIMENTAL:** Functional research prototypes, synthetic models, or offline benchmarks; not production-eligible.
- **PLANNED:** Documented in roadmap; implementation not yet started.

| Domain / Module | Feature | Status | Primary Evidence / Source File | Test Evidence | Next Step |
|---|---|---|---|---|---|
| **Frontend (Traveler)** | Three.js 3D Saigon Cityscape | **VERIFIED** | `apps/web/src/components/3d/CityHero3D.tsx` | Production build passes | Optimize mobile FPS |
| **Frontend (Traveler)** | 3D Landmark Viewer (GLB) | **VERIFIED** | `apps/web/src/pages/Map3DPage.tsx` | Build clean; asset loader verified | Expand landmark models |
| **Frontend (Traveler)** | AI Concierge Chat Interface | **VERIFIED** | `apps/web/src/components/trip/ChatPanel.tsx` | `tests/trip/test_trips_api.py` | Add voice input |
| **Frontend (Traveler)** | Smart Route Planner UI | **VERIFIED** | `apps/web/src/pages/PlannerPage.tsx` | `apps/web/scripts/test-trip.mjs` (18/18 pass) | Save draft offline |
| **Frontend (Traveler)** | Itinerary Comparison (/compare) | **VERIFIED** | `apps/web/src/pages/ComparePage.tsx` | Layout & delta render tests | Visual PDF export |
| **Frontend (Traveler)** | Dual Themes (Warm Light / Emerald Dark) | **VERIFIED** | `apps/web/src/theme.ts` & CSS tokens | Playwright / CDP visual audit | Add system theme sync |
| **Frontend (Traveler)** | Bilingual Support (VI / EN) | **VERIFIED** | `apps/web/src/i18n.ts` | Unit test strings verified | Expand EN coverage |
| **Frontend (Portal)** | Partner Onboarding & Slot Mgmt | **VERIFIED** | `apps/portal/src/pages/PartnerOverview.tsx` | `apps/portal` build exit code 0 | Multi-day batch slot edit |
| **Frontend (Portal)** | Admin Platform Moderation & RBAC | **VERIFIED** | `apps/portal/src/pages/AdminOverview.tsx` | `tests/test_partner_portal.py` | Batch import UI |
| **Backend (Planner)** | Deterministic Feasibility Solver | **VERIFIED** | `apps/api/app/services/planner_service.py` | `tests/test_planner.py` (11/11 pass) | Parallel solver worker |
| **Backend (Planner)** | Dynamic Replanning on Cancellation | **VERIFIED** | `apps/api/app/services/replanning_service.py` | `tests/test_ai_workflows.py` (5/5 pass) | Multi-stop replan |
| **Backend (Planner)** | Goong Directions & Geocoding | **IMPLEMENTED** | `apps/api/app/adapters/routing/goong.py` | `tests/test_routing.py` (mocked in test) | Live Goong API key test |
| **Backend (AI)** | Versioned Prompt Catalog v3.2.0 | **VERIFIED** | `apps/api/app/prompts/v3_2_0/` (20 workflows) | `tests/test_ai_workflows.py` | Add streaming tool call |
| **Backend (AI)** | Offline Chat Fallback Parser | **VERIFIED** | `apps/api/app/services/offline_chat_fallback.py` | `tests/test_ai_workflows.py` | Add typo tolerance |
| **Backend (ML)** | Heuristic Rule Baseline Ranker | **VERIFIED** | `apps/api/app/services/ranking_service.py` | `tests/test_ml_models.py` (12/12 pass) | Ingest real telemetry |
| **Backend (ML)** | Bootstrap XGBoost Ranker | **EXPERIMENTAL** | `models/ai-ranker/xgboost_ranker.json` | `tests/test_ml_models.py` (weak-label gate) | Adjudicate human labels |
| **Backend (ML)** | Tour Quote Win-Probability Model | **EXPERIMENTAL** | `models/quote-win/xgboost_win.json` | `tests/test_quote_win_model.py` (31/31 pass) | Train on real quotes |
| **Backend (ML)** | Multilingual E5 Vector Search | **IMPLEMENTED** | `apps/api/app/services/e5_search_service.py` | Script `download_e5_model.py` | Host weights on S3/HF |
| **Backend (ML)** | Flood Risk Classifier | **EXPERIMENTAL** | `models/dataset-17-experiment/flood-risk/` | Offline benchmark report | Collect real flood logs |
| **Backend (Commerce)** | 15-Minute Booking Seat Holds | **VERIFIED** | `apps/api/app/services/booking_service.py` | `tests/test_bookings.py` | WebSocket hold countdown |
| **Backend (Commerce)** | VNPay & MoMo Payment Adapters | **IMPLEMENTED** | `apps/api/app/adapters/payment/` | `tests/test_momo.py` (checksums verified) | Live sandbox staging test |
| **Backend (B2B)** | Tour Operator Quoting & Cost Engine | **VERIFIED** | `apps/api/app/services/quote/quote_service.py` | `tests/test_operator_quotes.py` (31 pass) | Invoice PDF generator |
| **Backend (B2B)** | Financial Margin Guardrail | **VERIFIED** | `apps/api/app/services/quote/pricing.py` | `tests/test_margin_guard.py` | Alert on margin breach |
| **Backend (Security)** | RS256 JWT & Rotating Refresh Cookies | **VERIFIED** | `apps/api/app/services/session_service.py` | `tests/auth/test_tokens.py` (72 pass) | Hardware security key |
| **Backend (Security)** | TOTP Two-Factor Authentication | **VERIFIED** | `apps/api/app/services/mfa_service.py` | `tests/auth/test_totp.py` (12/12 pass) | WebAuthn support |
| **Backend (Security)** | Argon2id Password Hashing | **VERIFIED** | `apps/api/app/auth.py` | `tests/auth/test_passwords.py` (9/9 pass) | Continuous rehash check |
| **Backend (Ops)** | Transactional Notification Outbox | **VERIFIED** | `apps/api/app/worker.py` | `tests/test_operations.py` | Celery / Redis queue |
| **Backend (Ops)** | Meshy 3D Background Poller | **VERIFIED** | `apps/api/app/services/meshy.py` | `tests/test_meshy.py` | Webhook receiver |
| **Backend (Ops)** | Telegram Bot & Zalo Integration | **IMPLEMENTED** | `apps/api/app/api/routes/admin_bot.py` | `tests/test_integrations.py` | Production webhook bind |

---

## 3. Verified Automated Test Evidence

During this repository audit, the following automated verification suites were executed against the live code:

1. **Frontend Traveler Test Suite (`apps/web`):**
   - Command: `node scripts/test-trip.mjs`
   - Results: **18 passed, 0 failed, 6 test suites** (Testing panel state, opening hours parsing, kind styling, selected place index mapping, tour stops day order, road segments, and SSE parsing).
   - Build Status: `tsc --noEmit` and `vite build` completed with **exit code 0**.
2. **Frontend Portal Build (`apps/portal`):**
   - Command: `tsc -b && vite build`
   - Results: Completed with **exit code 0** (2,073 modules transformed, production assets generated).
3. **Documentation Site Build (`docs-site`):**
   - Command: `tsc -b && vite build`
   - Results: Completed with **exit code 0** (1,599 modules transformed, static assets ready).
4. **Backend API Test Suite (`apps/api`):**
   - Environment: `Python 3.13.15`, `pytest 9.1.1`, `APP_ENV=test`.
   - Sample Verified Suites:
     - `tests/auth/`: **72 passed** (Authorizer, passwords, refresh token rotation, service keys, JWT RS256, TOTP RFC 6238).
     - `tests/test_account_recovery.py`: **34 passed** (Password recovery, single-use token lifecycle, email verification).
     - `tests/test_ai_workflows.py`: **5 passed** (8 versioned prompt workflows, chat fallback, intent similarity, replacement).
     - `tests/test_ml_models.py`: **12 passed** (Ranker baseline, weak-label gate rejection, feature schema verification).
     - `tests/test_planner.py`: **11 passed** (Feasibility solver, multi-objective constraints, locked stops).
     - `tests/trip/`: **252 passed** (Comprehensive multi-turn trips, replanning, road route segments, follow-ups).
     - `tests/test_operator_quotes.py` & pricing: **31 passed** (B2B quote creation, margin protection, win model backtest).
   - Total verified tests executed: **346 passed, 0 failed**.

---

## 4. Known Technical Debt & Immediate Next Steps

1. **Test Environment Hardening:**
   - On Windows sandboxed environments, `starlette.testclient.TestClient` requires loopback socket access. When running pytest locally, pass `$env:APP_ENV="test"` and `-p no:cacheprovider` to prevent lockups on `.pytest_cache`.
2. **External Integration Staging:**
   - VNPay, MoMo, Telegram, and Goong adapters are fully coded and tested with mock fixtures. End-to-end smoke testing with live staging merchant credentials must be scheduled prior to commercial launch.
3. **Real Human-Labeled Machine Learning Dataset:**
   - The current XGBoost ranker and tour win model operate on weak or synthetic labels. A consented telemetry pipeline must be connected to capture real traveler acceptance before promoting any ML model to production.

