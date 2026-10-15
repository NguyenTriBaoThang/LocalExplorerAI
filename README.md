<div align="center">

<p align="center">
  <img src="./assets/images/logo.png" alt="Local Explorer AI Logo" height="200" />
</p>

<h1 align="center">Local Explorer AI</h1>

<p align="center">
  <b>An intelligent urban discovery platform — AI Concierge · Slot-aware itinerary planning · 3D WebGL Digital Twin · Local ML (XGBoost + E5) · Goong Maps routing · Booking holds and VNPay / MoMo payment integrations for Ho Chi Minh City</b>
</p>

<p align="center">
  <a href="https://nguyentribaothang.github.io/LocalExplorerAI/">
    <img src="./assets/images/btn-technical-document.svg" alt="Technical documentation: architecture, AI and ML, planning, API, demo" width="440"/>
  </a>
</p>

<p align="center">
  <a href="https://github.com/NguyenTriBaoThang/LoaclExplorerAI/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/NguyenTriBaoThang/LoaclExplorerAI/ci.yml?label=CI" alt="CI Status"/>
  </a>
  <a href="https://github.com/NguyenTriBaoThang/LoaclExplorerAI/stargazers">
    <img src="https://img.shields.io/github/stars/NguyenTriBaoThang/LoaclExplorerAI?style=social" alt="GitHub stars"/>
  </a>
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License"/>
  </a>
  <a href="./.github/SECURITY.md">
    <img src="https://img.shields.io/badge/Security-Policy-red?logo=shield" alt="Security Policy"/>
  </a>
  <img src="https://img.shields.io/badge/PRD-3.0-blueviolet" alt="PRD 3.0"/>
  <img src="https://img.shields.io/badge/ML_Ranker-Weak_Label_Experiment-orange" alt="ML Ranker status"/>
  <img src="https://img.shields.io/badge/Maps-Goong_Directions_%26_Geocoding-orange" alt="Goong API"/>
  <img src="https://img.shields.io/badge/3D_Digital_Twin-GLB_Landmarks-purple" alt="3D Landmarks"/>
  <img src="https://img.shields.io/badge/i18n-Bilingual_VI_%7C_EN-indigo" alt="Bilingual"/>
</p>

<p align="center">
  <b>3D WebGL Digital Twin · 3D Landmark Viewer (GLB) · Saigon tourist places · AI Concierge Chat · Local E5 semantic search · XGBoost ML Ranker · Dynamic replanning · Goong Directions and Geocoding · Booking holds and VNPay / MoMo · Telegram Bot and Zalo Poller · Provider and Admin portals · Bilingual VI/EN · Operations outbox</b><br/>
  React 18.3 + TypeScript 5.6 · Three.js · Vite 6 · FastAPI · Python 3.12+ · PostgreSQL + PostGIS · Goong API · Docker Compose
</p>

<p align="center">
  <a href="http://localhost:8080/"><strong>Explore 3D Dashboard</strong></a>
  &nbsp;|&nbsp;
  <a href="http://localhost:8080/places"><strong>Saigon Places</strong></a>
  &nbsp;|&nbsp;
  <a href="http://localhost:8080/map-3d"><strong>3D Landmark Viewer</strong></a>
  &nbsp;|&nbsp;
  <a href="http://localhost:8080/chat"><strong>AI Concierge</strong></a>
  &nbsp;|&nbsp;
  <a href="./DEMO_SCRIPT.md">Demo Script</a>
  &nbsp;|&nbsp;
  <a href="./ARCHITECTURE.md">System Architecture</a>
  &nbsp;|&nbsp;
  <a href="./docs/api.md">API Reference</a>
  &nbsp;|&nbsp;
  <a href="./docs/bookings-and-payments.md">Bookings and Payments</a>
  &nbsp;|&nbsp;
  <a href="./docs/ml-training-and-data.md">ML Training</a>
  &nbsp;|&nbsp;
  <a href="./apps/api/README.md">Backend</a>
  &nbsp;|&nbsp;
  <a href="./apps/web/README.md">Frontend</a>
  &nbsp;|&nbsp;
  <a href="./data/README.md">Data</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/React-18.3-61DAFB?logo=react" alt="React 18"/>
  <img src="https://img.shields.io/badge/TypeScript-5.6-3178C6?logo=typescript" alt="TypeScript 5.6"/>
  <img src="https://img.shields.io/badge/Three.js-WebGL_3D-black?logo=threedotjs" alt="Three.js"/>
  <img src="https://img.shields.io/badge/Vite-6.0-646CFF?logo=vite" alt="Vite 6"/>
  <img src="https://img.shields.io/badge/FastAPI-0.142+-009688?logo=fastapi" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/PostgreSQL-16_+_PostGIS_3.4-336791?logo=postgresql" alt="PostGIS"/>
  <img src="https://img.shields.io/badge/XGBoost-Ranker-FF6600" alt="XGBoost"/>
  <img src="https://img.shields.io/badge/Sentence_Transformers-E5_Multilingual-FFD21E?logo=huggingface" alt="E5"/>
  <img src="https://img.shields.io/badge/Docker-Compose_v2-2496ED?logo=docker" alt="Docker"/>
</p>

<img src="./assets/images/banner.png" alt="Local Explorer AI Banner" width="100%"/>

</div>

---

## 🎖️ Project Objective and Positioning

**Core objective:** Build a next-generation smart urban tourism and experience platform for Ho Chi Minh City, addressing a common gap: **a place being present on a map does not mean a visitor can take part in an experience there at the time they arrive.**

Local Explorer AI moves beyond static map pins to **slot-aware itinerary planning**, combining a deterministic multi-objective planner, machine learning (ML), and artificial intelligence (AI):

- **Will this activity actually be available when I arrive?**
- **What travel order helps avoid excessive travel time in city traffic and peak heat?**
- **How can AI understand natural-language travel requests in Vietnamese without a complicated form?**
- **If a session is cancelled or heavy rain starts, how can the itinerary be adjusted without ruining the whole day?**
- **How can a traveler request a 15-minute booking hold and pay securely through VNPay or MoMo?**

### 💡 Core technology

- 🌆 **3D WebGL Saigon Digital Twin (Three.js):** Neon-lit high-rises, a reflective Saigon River, parallax camera movement, and radar-pulse POI markers.
- 💬 **Multi-turn AI Concierge Chat (/chat):** Natural Vietnamese conversation, constraint extraction through CONVERSATION_PARSER, a live constraints inspector, offline chat fallback, and one-click itinerary creation.
- ⏱️ **Three-level data model (POI → Experience → Slot + Evidence):** Separates the physical place, the activity offered there, its dated capacity, and the evidence used for review.
- 🧮 **Deterministic heuristic planner:** Uses explicit feasibility checks rather than asking an LLM to invent an itinerary.
- 🗺️ **Goong routing:** Goong Directions and Forward Geocoding provide route distance, ETA, and route geometry when configured. ETA is not live traffic data.
- 🤖 **Local ML (XGBoost Ranker + E5 semantic search):** Learning-to-rank feature contract ranker-features-v2 and multilingual E5 vector search. The current ranker artifact is a weak-label bootstrap experiment, not production-eligible; E5 weights are not included in the repository.
- 💳 **Booking and payment integrations (VNPay / MoMo):** Booking holds and provider decisions are implemented in the codebase. External gateway acceptance and real transactions still require valid staging credentials and end-to-end tests.
- 🔄 **Dynamic replanning:** SLOT_CANCELLED / WEATHER_ALERT events can lead to solver-filtered alternatives, REPLAN_ADVISOR recommendations, and XAI explanations.
- 📜 **Itinerary versioning and comparison (/compare):** Version history and side-by-side comparison of costs, stops, and schedule changes.
- 🤖 **Multi-platform bots (Telegram + Zalo):** Telegram webhook and n8n forwarding; Zalo Poller integration.
- 🔐 **Encrypted integration settings:** Integration secrets are encrypted at rest when the vault is configured; this does not replace deployment secret-management practices.
- 🌐 **Vietnamese/English interface and two themes:** Warm Light and Nocturnal Emerald Dark.
- 🏛️ **3D Landmark Viewer (/map-3d):** GLB landmark models, with heading/altitude/scale calibration through the API.
- 📥 **Place import staging:** Bulk CSV/XLSX candidates enter a review queue and can be checked for fuzzy duplicates before promotion.
- 🌧️ **Flood risk and AQI:** Weather/AQI advisory workflows exist. A production road-flood model trained on suitable observed labels is not included.

> **Data and deployment status:** The application is a prototype. The 177-row workbook is an import source, not a publishable operational catalog. Integrations need staging validation, and the bootstrap ranker / flood-report experiment must not be represented as production models. See [end-to-end rollout](./docs/end-to-end-rollout.md).

---

## 📸 Interface screenshots

<table align="center">
<tr>
<td align="center" width="33%">
<img src="./assets/screenshots/home_3d.png" width="100%"/>
<b>3D WebGL Saigon Cityscape</b>
</td>
<td align="center" width="33%">
<img src="./assets/screenshots/explore.png" width="100%"/>
<b>Explore and 3D Tilt Card</b>
</td>
<td align="center" width="33%">
<img src="./assets/screenshots/planner.png" width="100%"/>
<b>Itinerary Planner and 3D Preview</b>
</td>
</tr>
<tr>
<td align="center" width="33%">
<img src="./assets/screenshots/itinerary.png" width="100%"/>
<b>Laser Timeline and KPIs</b>
</td>
<td align="center" width="33%">
<img src="./assets/screenshots/map_3d.png" width="100%"/>
<b>3D Landmark Viewer GLB</b>
</td>
<td align="center" width="33%">
<img src="./assets/screenshots/provider.png" width="100%"/>
<b>Provider Portal and Slot Management</b>
</td>
</tr>
</table>

---

## 📑 Table of contents

- [Why Local Explorer AI](#-why-local-explorer-ai)
- [Target users](#-target-users)
- [Core data model](#-core-data-model)
- [Feature overview](#-feature-overview)
- [AI and XAI prompt catalog](#-ai-and-xai-prompt-catalog-prd-30)
- [Local machine-learning models](#-local-machine-learning-models)
- [Heuristic planner algorithm](#-heuristic-planner-algorithm)
- [System architecture](#-system-architecture)
- [Technology stack](#-technology-stack)
- [API catalog](#-api-catalog)
- [Installation and startup](#-installation-and-startup)
- [Environment configuration](#-environment-configuration)
- [Demo scenarios](#-demo-scenarios)
- [Project directory structure](#-project-directory-structure)
- [Development roadmap](#-development-roadmap)
- [Contributing and license](#-contributing-and-license)

---

## 🧭 Why Local Explorer AI

| Limitation of conventional map apps | Local Explorer AI approach |
|---|---|
| They show static POIs | Three data levels: place → activity → specific session |
| Availability and capacity are unclear | Reported availability is shown with freshness/status context; unknown capacity is not treated as zero |
| Itineraries are assembled manually and may ignore traffic | The heuristic engine can use route estimates from Goong when configured |
| Chatbots can invent places or details | Hard feasibility checks, schema validation, provenance, and a ranking fallback constrain recommendations |
| Travelers must search through rigid forms | The AI Concierge can extract travel constraints from natural-language Vietnamese |
| A cancellation or heavy rain can disrupt a trip | Replanning and weather-advisory flows can suggest alternatives; configured data and services are required |
| Flat 2D interfaces can feel generic | Three.js WebGL, 3D cards, and multi-style maps are part of the UI |
| Small cultural providers lack tools | Provider Portal and a two-step AI Slot Assistant are available in the codebase |
| Duplicate or inaccurate catalog data is hard to manage | Admin moderation, audit logs, and duplicate POI review workflows |

---

## 👥 Target users

- 🎒 **Independent and international travelers (traveler):** Build itineraries around real time windows, chat in Vietnamese, compare and share plans.
- 👨‍👩‍👧‍👦 **Families and groups of friends:** Track group budgets and prefer indoor activities when conditions warrant it.
- 🎨 **Culture and art enthusiasts:** Search by meaning and explore craft workshops, traditional occupations, and local coffee culture.
- 🏪 **Experience providers (provider):** Use the provider portal to manage activities, report capacity, and process booking requests.
- 🛡️ **Platform and city administrators (admin):** Review submissions, find duplicates, inspect audit logs, and configure integrations.

---

## 💡 Core data model

~~~text
User (RBAC: traveler|provider|admin)
  └──> Itinerary ──> ItineraryStop <── ExperienceSlot (Optimistic Lock)
         │               │                  │
         ├── Version      └── Booking ────────┘ (15-minute hold)
         ├── Feedback          │
         └── DecisionLog  ├── PaymentTransaction (VNPay|MoMo IPN)
                          ├── BookingEvent (audit trail)
                          └── EmailOutbox (worker notification)

Provider ──> POI (PostGIS POINT) ──> Experience ──> ExperienceSlot
   └── Evidence (verified/pending/rejected/expired)

IntegrationSetting (Fernet-encrypted: vnpay|momo|goong|gemini|google)
AuditLog · PlaceImportStaging · TelegramBotConfig · SystemSettings
~~~

~~~mermaid
classDiagram
    class User {
        +String id
        +String email
        +String role (traveler|provider|admin)
        +Boolean is_active
    }
    class Provider {
        +String id
        +String name
        +String verification_status
    }
    class POI {
        +String id
        +String provider_id
        +Geometry geom (PostGIS POINT)
        +String verification_status
    }
    class Experience {
        +String id
        +Boolean is_hands_on
        +Boolean is_indoor
        +Int duration_min
        +BigInt price_vnd
    }
    class ExperienceSlot {
        +DateTime start_at
        +Int capacity_total
        +Int available_reported
        +String status (open|full|cancelled|tentative)
        +Int version
    }
    class Itinerary {
        +String user_id
        +Date planned_date
        +Int group_size
        +BigInt budget_vnd
        +String travel_mode
        +Int current_version
        +String share_token
    }
    class Booking {
        +String status (pending_provider|awaiting_payment|confirmed|cancelled)
        +DateTime hold_expires_at (15 min)
        +BigInt amount_vnd
    }
    class PaymentTransaction {
        +String gateway (vnpay|momo)
        +String status (pending|success|failed|reconciled)
    }

    User --> Itinerary : owns
    User --> Booking : books
    Provider --> POI : owns
    POI --> Experience : hosts
    Experience --> ExperienceSlot : schedules
    Itinerary --> Booking : creates hold
    Booking --> PaymentTransaction : paid through
~~~

---

## ⚡ Feature overview

> The following describes implemented code paths and UI areas. It does not imply that real partner inventory or third-party integrations have passed staging acceptance.

### 1. AI Concierge and travel chat (/chat)
- Natural-language Vietnamese conversation with preset prompts: *Food and traditional coffee*, *pottery workshop*, *District 1 heritage*, *night walking street*.
- CONVERSATION_PARSER extracts group size, time window, budget, preferences, and transport mode.
- **Live Constraints Inspector:** Displays extracted constraints.
- One-click handoff to itinerary planning without entering the same fields again.
- **Offline Chat Fallback:** Uses conservative local rules when no LLM key is configured or the service is unavailable.

### 2. Saigon 3D WebGL canvas (Three.js Digital Twin)
- Neon-lit buildings, reflective Saigon River, and radar-pulse POI markers.
- Parallax camera movement; hovering over a marker displays an activity card.
- Two visual modes: **Neon Cyber Night** and **Emerald Daytime**.

### 3. E5 semantic vector search (/explore)
- semantic=true enables multilingual E5 (intfloat/multilingual-e5-base) locally on CPU when the model and dependencies are installed.
- Filters include keyword, category, district, radius, indoor/outdoor, maximum price, and group size.
- **Current limitation:** E5 model weights are not included in the repository; the endpoint may use the configured fallback until they are installed.

### 4. 3D Tilt Cards with specular glare
- perspective: 1000px with a mouse-following glare overlay.
- Selecting a card moves the map to its coordinates.

### 5. Three-step itinerary wizard (/planner)
- **Step 1:** Date, time window, origin/destination with Goong geocoding suggestions, group size, and budget.
- **Step 2:** Experience style and locked stops (locked_experience_ids).
- **Step 3:** Transport mode (motorcycle, car, or walking where supported).
- **3D Live Day Preview:** Updates estimated total time, cost, and transport context.

### 6. 3D itinerary timeline and KPIs (/itinerary/:id)
- Four KPIs: total duration, travel time, cost, and number of stops.
- Timeline and map can display route geometry returned by Goong.
- XAI/reason-code card explains ranking choices and provides print/save options where available.

### 7. Fifteen-minute booking holds and VNPay / MoMo
- A booking hold is created with database locking and an expiry.
- Two-sided workflow: traveler submits a request; provider accepts or rejects.
- VNPay uses HMAC-SHA512; MoMo captureWallet uses HMAC-SHA256; server-to-server IPN callbacks are part of the integration code.
- **Staging boundary:** A configured gateway is not proof of a completed sandbox checkout or payment callback test.

### 8. Dynamic replanning
- Processes SLOT_CANCELLED and WEATHER_ALERT events where configured.
- Solver filters feasible candidates; REPLAN_ADVISOR suggests options and XAI explains the trade-offs.
- Applying a proposal updates the itinerary version atomically.

### 9. Itinerary versioning and comparison (/compare)
- Version history stores itinerary snapshots.
- Side-by-side comparison includes cost differences, stops added/removed, and end-time changes.

### 10. Public itinerary sharing (/shared/:token)
- Uses a random token rather than exposing personal information in the URL.
- The owner can revoke sharing.

### 11. Provider Portal (/provider-portal)
- Manage activities and create/update slots with optimistic locking (expected_version).
- **Evidence management:** Submit source/evidence for administrator review.
- Review booking requests and accept/reject them.
- **AI Slot Assistant (two-step HMAC):** Parse a natural-language command, preview a five-minute signed confirmation token, then explicitly confirm; a confirmed cancellation can emit SLOT_CANCELLED for replanning.

### 12. Admin Portal (/admin)
- **KPI dashboard:** Users, providers, pending POIs/experiences, expired evidence, and slots with unknown reported capacity.
- **Moderation queue:** Review, reject, or hide POI, experience, and evidence records.
- **Duplicate POI detection and merge:** Fuzzy similarity-based review; confirm current behavior in the application before describing it as one-click.
- **Integrations tab:** Manage Google OAuth, Goong, Gemini, VNPay, and MoMo settings; values are encrypted when the vault is configured.
- **RBAC management:** Activate/deactivate accounts and assign traveler/provider/admin roles.
- **Telegram Bot and n8n:** Configure webhook, persona, and model settings where available.
- **System settings:** Configure limits, time buffers, and maintenance mode.
- **Staging Places:** Review imported place candidates.
- Additional admin panels include AI tools, flood risk, operations, and audit logs.

### 13. Operations and email outbox
- Outbox worker (apps/api/scripts/worker.py) handles booking, decision, and cancellation notifications with retries and idempotency.
- Operations endpoints under /api/ops expose notification/task/event status when configured.
- PostgreSQL backup and restore scripts are available (backup-postgres.* and restore-postgres.*).

### 14. Vietnamese/English and dual theme
- Language switcher for interface text, notifications, and error messages.
- Warm Light and Nocturnal Emerald Dark themes.

### 15. 3D Landmark Viewer (/map-3d)
- Loads GLB landmark models such as Saigon Notre-Dame Cathedral Basilica.
- Supports heading, altitude, scale, and real-world coordinates.
- Calibration API: PUT /api/models-3d/{model_id}/calibration.

### 17. Xác Thực Người Dùng & Quản Lý Hồ Sơ
- Đăng ký và đăng nhập bằng Email/Mật khẩu với cơ chế băm mật khẩu an toàn.
- Đăng nhập một chạm bằng **Google OAuth 2.0 PKCE** với kiểm tra trạng thái kích hoạt tự động.
- Phiên đăng nhập được quản lý bằng **HTTP-only Cookie** (`le_at` access token 15 phút, `le_rt` refresh token xoay vòng), bảo vệ chống tấn công XSS và đánh cắp token.
- Trang hồ sơ cá nhân (`/profile`): Đổi tên hiển thị, số điện thoại, đổi mật khẩu và xem danh sách lịch trình đã lưu.

### 18. Role-based navigation and guards
- RoleHome routes travelers to /explore, providers to /provider-portal, and admins to /admin.
- CustomerRoute and RoleRoute protect role-specific pages.

### 17. Authentication and profiles
- Email/password authentication and Google OAuth 2.0 PKCE integration.
- HTTP-only le_session cookie is used for session handling.
- Profile page supports name, phone, password, and saved-itinerary information where enabled.

### 18. Feedback and ML training loop
- Travelers can submit a star rating and written feedback after a trip.
- FEEDBACK_LABELER can apply a 0–3 rubric to a submitted review and mark training usability.
- A review-labeling endpoint does not replace feedback collection, consent, human review, or model training.

---

## 🤖 Eight AI and XAI prompts (PRD 3.0 — prompts/manifest.json v3_0_0)

| Prompt | API endpoint | Function |
|---|---|---|
| CONVERSATION_PARSER | POST /api/chat/message | Extract trip constraints into StructuredConstraints |
| EXPERIENCE_TAGGER | POST /api/experiences/{id}/ai-tag | Label hands-on, indoor, intent, and weather sensitivity |
| INTENT_SIMILARITY | POST /api/ai/intent-similarity | Score semantic and tag similarity between two experiences |
| REPLAN_ADVISOR | POST /api/itineraries/{id}/replan-advice | Suggest alternatives when a slot is disrupted |
| XAI_EXPLANATION | Inside replan flow | Explain the decision in Vietnamese and record decision logs |
| PROVIDER_ASSISTANT | POST /api/providers/{id}/slot-assistant/preview | Preview a natural-language slot change; confirmation is a separate step |
| FEEDBACK_LABELER | POST /api/itineraries/{id}/feedback/label | Apply the 0–3 feedback rubric |
| WEATHER_AQI_ADVISOR | POST /api/itineraries/{id}/weather-advisory | Assess supplied rain/PM2.5 readings and emit WEATHER_ALERT |

---

## 🧠 Local machine-learning models

### 1. Experience Ranker — XGBoost / LightGBM (models/ai-ranker/)

The repository has reported historical benchmark metrics of NDCG@5 0.9516, NDCG@2 0.9031, and Recall@5 1.0. Those figures belong to weak/unverified ranking data and must not be interpreted as real-user performance or evidence that the current artifact should be promoted.

The 15 ranker-features-v2 features are: tag_jaccard, intent_match, is_hands_on, is_indoor, duration_ratio, eta_ratio, total_time_ratio, group_cost_ratio, rain_mm, outdoor_rain_mm, temperature_c, pm2_5, european_aqi, is_hands_on_known, and is_indoor_known.

**Fail-closed behavior:** A SHA-256 checksum is checked before a model is loaded. If deployment_eligible is false, the API falls back to the rule baseline. The bootstrap ranker remains experimental.

### 2. Saigon flood-risk classifier (models/flood-risk/)
- The raw public dataset contains 425 historical flood reports from 2002–2026 under CC BY-NC 4.0.
- API route: POST /api/ml/flood-risk.
- Principle: unknown is not the same as no flood.
- No suitable production road-flood bundle is currently included.

### 3. Multilingual E5 embeddings (models/e5/)
- Model: intfloat/multilingual-e5-base (768 dimensions).
- Intended to run locally on CPU; query text need not be sent to an external embedding service.
- API route: GET /api/experience-search?semantic=true.
- The model weights must be downloaded separately.

---

## 🧮 Heuristic planner algorithm

~~~text
Input: [T_start, T_end, Budget_VND, Group_Size, Intent_Weights, Transport_Mode, Locked_IDs, Origin/Destination]
         │
         ▼
Step 1 — Feasibility pruning:
  Remove sessions outside [T_start, T_end] or with no reported availability
  Remove experiences above the remaining budget or group capacity
  Preserve locked_experience_ids
         │
         ▼
Step 2 — Multi-objective scoring and ML tie-breaking:
  Score = w1 * intent_match + w2 * slot_freshness + w3 * cost_efficiency
  For ties → XGBoost Ranker (15 features), when eligible/enabled
  On failure → Rule Baseline
         │
         ▼
Step 3 — Sequential routing (Goong API):
  Geocode origin/destination to coordinates
  Goong Directions → ETA, distance, and route polyline geometry
  Check the return deadline, including the final leg
         │
         ▼
Output:
  Ordered ItineraryStops + Feasibility Status (feasible|tentative)
  Reason Codes + XAI Explanation + travel statistics
~~~

---

## 🏗️ System architecture

~~~mermaid
flowchart TB
    subgraph Client["SPA — React 18 + Vite 6 + TypeScript 5.6"]
        ThreeCanvas["Three.js 3D WebGL Cityscape"]
        ChatUI["AI Concierge Chat"]
        PlannerWiz["Trip Planner Wizard"]
        Itinerary["Laser Timeline & KPIs"]
        ProvPortal["Provider Portal"]
        AdminPortal["Admin Portal"]
        Map3D["3D Landmark Viewer GLB"]
        MapAdapter["Leaflet + CartoDB"]
        MockEngine["Offline Heuristic Fallback"]
    end

    subgraph Backend["FastAPI Backend — Python 3.12+"]
        AuthMW["RBAC Auth + Rate Limit Middleware"]
        Routes["API Route Modules"]
        Planner["Heuristic Planner Service"]
        Replan["Dynamic Replanning Service"]
        Prompts["Prompt Engine (PRD 3.0 — 8 prompts)"]
        LLM["LLM Adapter (OpenAI/Gemini)"]
        Ranker["XGBoost ML Ranker"]
        Flood["Flood Risk Classifier"]
        E5["Multilingual E5 Search"]
        Routing["Goong Directions & Geocoding"]
        Payment["VNPay / MoMo Gateways"]
        Bot["Telegram Bot & n8n"]
        Worker["Email Outbox Worker"]
    end

    subgraph Storage["Storage & Intelligence"]
        PG[("PostgreSQL + PostGIS")]
        Redis[("Redis — optional services")]
        Models[("ML Artifacts: XGBoost + E5 + Flood")]
        PromptCatalog[("JSON Prompts Catalog")]
    end

    Client --> AuthMW --> Routes
    Routes --> Planner --> Ranker
    Planner --> Routing
    Routes --> Replan --> Prompts --> LLM
    Replan --> Ranker
    Routes --> E5 & Flood & Payment & Bot
    Routes --> PG & Redis
    E5 & Ranker & Flood --> Models
    Prompts --> PromptCatalog
    Worker --> PG
    MockEngine -. offline .-> Client
~~~

---

## 💻 Technology stack

| Layer | Technology | Role |
|---|---|---|
| **Frontend SPA** | React 18.3, TypeScript 5.6, Vite 6.0 | Fast, type-safe single-page app |
| **3D WebGL** | Three.js | Saigon Digital Twin and GLB Landmark Viewer |
| **Styling** | Vanilla CSS, Tailwind CSS, Lucide Icons | Glassmorphism and dual themes |
| **i18n** | Custom provider + LanguageSwitcher | Vietnamese/English interface |
| **Maps** | Goong API, Leaflet, CartoDB | Route estimates and route geometry |
| **Payments** | VNPay + MoMo | HMAC-SHA512/256 and server-to-server IPN |
| **Backend API** | Python 3.12, FastAPI, Pydantic v2 | Async API route modules |
| **Database** | PostgreSQL + PostGIS / SQLite (development) | Spatial queries and geography points |
| **ORM and migrations** | SQLAlchemy 2.0, Alembic | Database schema management |
| **Security** | Fernet, HTTP-only cookie, Google OAuth PKCE | Encrypted settings and session handling |
| **Operations** | Email outbox worker, optional Redis rate limit | Transactional notifications and request limiting |
| **Bots and AI** | Telegram webhook, n8n, Zalo Poller, Gemini | Multi-platform assistant integrations |
| **Local ML** | XGBoost, LightGBM, Scikit-learn, NumPy, Pandas | Ranking experiments and model pipelines |
| **Semantic search** | Sentence-Transformers, multilingual E5 | Local vector search when weights are installed |
| **Testing** | Pytest and frontend lint/build | API tests and web checks |
| **CI/CD** | Docker Compose v2, GitHub Actions | Packaging, tests, and builds |

---

## 📡 API catalog

> Swagger UI: http://localhost:8000/docs | ReDoc: http://localhost:8000/redoc

The endpoint list below is a high-level repository reference. Check the API routers and [API documentation](./docs/api.md) for the current request/response contract and enabled routes.

### Health and operations
| Method | Path | Function |
|:---:|---|---|
| GET | /health | Liveness probe |
| GET | /ready | Readiness probe — PostgreSQL + Redis |
| GET | /api/ops/outbox/stats | Email outbox statistics |

### Authentication
| Method | Path | Function |
|:---:|---|---|
| POST | /api/auth/register | Register a traveler |
| POST | /api/auth/login | Sign in |
| POST | /api/auth/logout | Sign out |
| GET | /api/auth/me | Get the current user profile |
| PATCH | /api/auth/me | Update the profile |
| POST | /api/auth/password | Change password |
| GET | /api/auth/google/start | Start Google OAuth PKCE |
| GET | /api/auth/google/callback | OAuth callback and session |

### Catalog and semantic search
| Method | Path | Function |
|:---:|---|---|
| GET | /api/pois | List POIs and coordinates |
| GET | /api/pois/{id} | Get POI details |
| GET | /api/experiences | Filter experiences by intent, time, budget, or radius |
| GET | /api/experiences/{id} | Get experience details |
| GET | /api/experiences/{id}/slots | Get slots and reported availability |
| GET | /api/experience-search | Keyword or E5 semantic search (semantic=true) |

### Routing and geocoding
| Method | Path | Function |
|:---:|---|---|
| GET | /api/routing/capabilities | Supported travel modes and Goong status |
| GET | /api/geocoding/forward | Convert a Vietnamese address to GPS coordinates |

### Planner and itinerary
| Method | Path | Function |
|:---:|---|---|
| POST | /api/itineraries/plan | Create an itinerary (heuristic planner and ranking) |
| GET | /api/itineraries/{id} | Get itinerary and route legs |
| GET | /api/me/itineraries | List my itineraries |
| GET | /api/itineraries/{id}/versions | Get itinerary version history |
| GET | /api/itinerary-comparisons | Compare two itineraries |
| POST | /api/itineraries/{id}/share | Create a public share token |
| GET | /api/itineraries/shared/{token} | Retrieve a shared itinerary |
| POST | /api/itineraries/{id}/replan-advice | Request replacement advice (REPLAN_ADVISOR) |
| POST | /api/itineraries/{id}/feedback | Submit trip feedback |

### Bookings and payments
| Method | Path | Function |
|:---:|---|---|
| POST | /api/bookings/hold | Create a 15-minute booking hold (SELECT ... FOR UPDATE) |
| GET | /api/bookings/{id} | Get booking details |
| POST | /api/bookings/{id}/payment-link | Create a VNPay/MoMo payment URL |
| POST | /api/bookings/vnpay/ipn | VNPay IPN webhook and signature verification |
| POST | /api/bookings/momo/ipn | MoMo IPN webhook and signature verification |
| POST | /api/bookings/{id}/decision | Provider accepts or rejects a booking request |

### AI tools
| Method | Path | Function |
|:---:|---|---|
| POST | /api/chat/message | AI Concierge chat (CONVERSATION_PARSER) |
| POST | /api/experiences/{id}/ai-tag | AI activity tagging (EXPERIENCE_TAGGER) |
| POST | /api/ai/intent-similarity | Score intent similarity (INTENT_SIMILARITY) |
| POST | /api/itineraries/{id}/weather-advisory | Weather advisory (WEATHER_AQI_ADVISOR) |

### ML services
| Method | Path | Function |
|:---:|---|---|
| GET | /api/ml/status | Model status (ranker, E5, flood) |
| POST | /api/ml/rank-experiences | Rank experiences using the configured ranker/fallback |
| POST | /api/ml/flood-risk | Advisory flood-risk inference; requires a compatible eligible bundle |

### Provider Portal
| Method | Path | Function |
|:---:|---|---|
| GET | /api/providers/me | Get the current provider |
| GET/POST | /api/providers/{id}/experiences | List/create experiences |
| PATCH/DELETE | /api/providers/{id}/experiences/{exp_id} | Update/delete an experience |
| POST | /api/providers/{id}/experiences/{exp_id}/slots | Create a slot |
| POST | /api/providers/{id}/slot-assistant/preview | Preview an AI-assisted slot change |
| POST | /api/providers/{id}/slot-assistant/confirm | Confirm a change with an HMAC token |
| POST/GET | /api/providers/{id}/evidence | Submit/list evidence |

### Admin Portal
| Method | Path | Function |
|:---:|---|---|
| GET | /api/admin/kpi | Admin KPI dashboard |
| GET | /api/admin/moderation/queue | Moderation queue |
| POST | /api/admin/moderation/{id}/decision | Approve/reject/hide a record |
| GET | /api/admin/duplicate-pois | List suspected duplicate POIs |
| POST | /api/admin/duplicate-pois/merge | Merge POIs after review |
| GET/PUT | /api/admin/integrations/{service} | Read/update encrypted integration settings |
| GET | /api/admin/staging-places | List staged place candidates |
| POST | /api/admin/staging-places/{id}/approve | Approve a place into the catalog |
| GET | /api/admin/audit-logs | Read audit logs |
| GET/PUT | /api/admin/system-settings | Read/update system settings |
| GET/POST/PUT | /api/admin/bot/* | Configure Telegram Bot and n8n |

### 3D landmark models
| Method | Path | Function |
|:---:|---|---|
| GET | /api/models-3d | List 3D landmark models |
| GET | /api/models-3d/{id} | Get model details and calibration parameters |
| PUT | /api/models-3d/{id}/calibration | Update heading, altitude, scale, and coordinates |

---

## 🚀 Installation and startup

### Requirements
- Python 3.12+
- Node.js 18+ (or 20+)
- PostgreSQL 16 + PostGIS 3.4 for deployment, or SQLite 3 for development
- Redis 7+ (optional, for rate limiting)
- Docker Compose v2 for containerized services

### Quick start (development)
~~~powershell
# 1. Clone the repository
git clone https://github.com/NguyenTriBaoThang/LoaclExplorerAI.git
cd LoaclExplorerAI

# 2. Create the API environment file if it does not exist
if (-not (Test-Path apps/api/.env)) { Copy-Item .env.example apps/api/.env }
# Configure required settings; never commit this file.

# 3. Backend (from apps/api)
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate     # Linux/macOS

python -m pip install -r requirements.txt
python -m pip install -r requirements-ranking-training.txt  # Optional: ranking experiments

alembic upgrade head
# The legacy seed_db command is disabled; it must not be used to create real catalog data.
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4. Frontend (in a separate terminal)
cd apps/web
npm ci
npm run dev
~~~

### Docker Compose (production-like local setup)
~~~powershell
# Start Compose services (check the active compose file for services and settings)
docker compose up -d

# Follow API logs
docker compose logs -f api
~~~

### Combined development helper (Windows)
~~~powershell
.\scripts\run-dev.ps1
~~~

The helper starts database services and prints instructions for launching the API and frontend separately.

---

## ⚙️ Environment configuration

Create apps/api/.env from the root .env.example if it does not already exist:

| Biến môi trường | Giá trị mặc định | Giải thích |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/local_explorer` | Chuỗi kết nối PostGIS |
| `REDIS_URL` | `redis://localhost:6379/0` | Chuỗi kết nối Redis phục vụ cache và rate limit |
| `AUTH_JWT_KEY_ID`, `AUTH_JWT_PRIVATE_KEY_B64` | *(sinh bằng `python -m scripts.generate_auth_keys`)* | Khóa RS256 ký access token (base64 PEM) |
| `ADMIN_MFA_REQUIRED` | *(mặc định: bật ở production)* | Bắt buộc admin dùng MFA TOTP |
| `APP_SIGNING_SECRET` | *(chuỗi ngẫu nhiên)* | Khóa ký token xác nhận 2 bước cho Provider Slot Assistant |
| `INTEGRATION_SECRETS_KEY` | *(khóa Fernet base64)* | Master key mã hóa AES-128-CBC cho các cổng tích hợp động |
| *(đã bỏ)* `ADMIN_API_KEY` | — | Thay bằng service account: tạo khóa `lek_...` qua `POST /api/admin/service-accounts` (chỉ quyền `ops:read`) |
| `OPENAI_API_KEY` | *(tùy chọn)* | API key cho các prompt LLM (Hỗ trợ OpenAI hoặc Gemini API compatible) |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | URL endpoint của nhà cung cấp LLM |
| `ROUTING_PROVIDER` | `goong` | Nhà cung cấp tuyến đường (`goong` hoặc `mock` cho test/demo) |
| `GEOCODING_PROVIDER` | `goong` | Nhà cung cấp geocoding địa chỉ |
| `GOONG_API_KEY` | *(bắt buộc để dùng Goong)* | Key Goong chỉ được API server gửi, không lộ ra frontend |
| `GOONG_ETA_TTL_SECONDS` | `300` | Thời hạn cache ETA trong tiến trình API (5 phút) |
| `GEOCODE_CACHE_TTL_SECONDS` | `86400` | Thời hạn cache kết quả geocoding (24 giờ) |
| `PAYMENT_PROVIDER` | `vnpay` | Cổng thanh toán trực tuyến mặc định (`vnpay` hoặc `momo`) |
| `VNPAY_ENVIRONMENT` | `sandbox` | Môi trường VNPay (`sandbox` hoặc `production`) |
| `VNPAY_TMN_CODE` | *(tùy chọn)* | Mã Terminal ID do VNPay cấp |
| `VNPAY_HASH_SECRET` | *(tùy chọn)* | Khóa bí mật tạo chữ ký số HMAC-SHA512 VNPay |
| `VNPAY_PAYMENT_URL` | `https://sandbox.vnpayment.vn/paymentv2/vpcpay.html` | Endpoint thanh toán VNPay |
| `VNPAY_RETURN_URL` | `http://localhost:5173/itinerary/` | URL điều hướng hiển thị kết quả sau thanh toán |
| `VNPAY_IPN_URL` | `http://localhost:8000/api/payments/vnpay/ipn` | Webhook IPN tiếp nhận xác nhận thanh toán |
| `MOMO_ENVIRONMENT` | `sandbox` | Môi trường Ví MoMo (`sandbox` hoặc `production`) |
| `MOMO_PARTNER_CODE` | *(tùy chọn)* | Mã đối tác do MoMo cấp |
| `MOMO_ACCESS_KEY` | *(tùy chọn)* | Khóa truy cập API MoMo |
| `MOMO_SECRET_KEY` | *(tùy chọn)* | Khóa bí mật tạo chữ ký số HMAC-SHA256 MoMo |
| `SMTP_HOST` / `SMTP_PORT` | `localhost` / `587` | Cấu hình máy chủ gửi email giao dịch |
| `INSTALL_ML` | `true` | Bật tính năng nạp mô hình XGBoost Ranker & Flood Risk |
| `INSTALL_E5` | `true` | Bật tính năng tìm kiếm ngữ nghĩa cục bộ Multilingual E5 |
| `GOOGLE_CLIENT_ID` | *(tùy chọn)* | Client ID đăng nhập Google OAuth 2.0 PKCE |
| `GOOGLE_CLIENT_SECRET` | *(tùy chọn)* | Client Secret đăng nhập Google |

Keep production secrets in an appropriate secret manager. Do not commit credentials or expose them to the browser. Test external integrations in staging with the required HTTPS callbacks.

---

## 🎭 Demo scenarios

### Scenario 1: Traveler plans through AI chat
1. Open http://localhost:8080/chat.
2. Enter: “I want to explore District 1 tomorrow from 9 a.m. to 5 p.m., for two people, with a 500,000 VND budget; I like craft workshops and street food.”
3. Review the extracted parameters in the Live Constraints Inspector.
4. Select **Create itinerary now**. Route estimates depend on the configured routing service and eligible catalog data.

### Scenario 2: Booking and VNPay payment
1. Open an itinerary and select a stop → **Book**.
2. The system creates a 15-minute hold, subject to valid sourced inventory and partner configuration.
3. The provider accepts → the booking can proceed to awaiting_payment.
4. Select **Pay with VNPay** → the configured sandbox or gateway checkout.
5. A verified IPN callback updates payment status; email requires the notification service to be configured.
6. Treat the flow as a staging/demo scenario until a sandbox transaction has been completed and logged.

### Scenario 3: Replan after a slot cancellation
1. A provider cancels a session through the AI Slot Assistant: “Cancel Friday afternoon's session because the workshop is unexpectedly closed.”
2. SLOT_CANCELLED can trigger the dynamic replanning workflow.
3. Replan Advice can show alternatives and an XAI explanation when eligible replacement data and services are available.

### Scenario 4: E5 semantic discovery
1. Open http://localhost:8080/explore.
2. Search for: “a quiet indoor traditional craft experience.”
3. Enable **Semantic search**. E5 results require the model weights and dependencies to be installed; otherwise the configured fallback applies.
4. Results are ordered by the configured similarity/ranking method.

---

## 📁 Project directory structure

~~~text
LoaclExplorerAI/
├── apps/
│   ├── api/                   # FastAPI backend
│   └── web/                   # React + TypeScript frontend
├── data/
│   ├── raw/                   # Source and candidate data
│   ├── experimental/          # Research-only datasets
│   ├── training/              # Training templates
│   ├── sai_gon_places.json    # Place catalog data, when present
│   └── dataset_ranking_tphcm.*# Ranking training data
├── docs/                      # Technical documentation
│   ├── api.md                 # API reference
│   ├── architecture.md        # Architecture details
│   ├── bookings-and-payments.md
│   ├── integration-settings.md
│   ├── ml-training-and-data.md
│   ├── operations.md
│   └── sourced-catalog.md
├── docs-site/                 # Static documentation site (React + Vite)
├── models/
│   ├── ai-ranker/             # Experimental XGBoost artifacts (not production eligible)
│   ├── e5/                    # Download separately
│   ├── flood-risk/            # No production road-flood model included
│   └── flood-report-experiment/ # Separate research artifact
├── models_3d/                 # GLB landmark assets and calibration.json
├── notebooks/                 # Google Colab research notebooks
├── Places/                    # Original Sai_Gon_Places.xlsx workbook
├── scripts/                   # Root automation scripts
│   ├── train_experience_ranker.py
│   ├── build_flood_report_weak_labels.mjs
│   ├── download_hcmc_flood_reports.py
│   ├── run-dev.ps1
│   ├── production-smoke.ps1
│   └── backup/restore-postgres.*
├── assets/                    # Images, screenshots, badges, SVG buttons
├── .github/
│   └── workflows/
│       ├── ci.yml             # Pytest + lint + web build CI
│       └── deploy-pages.yml   # GitHub Pages deployment
├── docker-compose.yml         # Compose configuration
├── docker-compose.override.yml # Development overrides
├── docker-compose.prod.yml    # Production configuration
├── ARCHITECTURE.md            # System architecture description
├── COMPETITION_SUBMISSION.md  # Competition submission details
├── DEMO_SCRIPT.md             # Demo walkthrough
└── .env.example               # Environment variables template
~~~

---

## 🗺️ Development roadmap

### Current prototype capabilities (previously labeled v1.0)
- ✅ Heuristic planner and dynamic replanning code paths
- ⚠️ XGBoost ML ranker benchmark (historical NDCG@5=0.9516 on weak/unverified labels) and E5 semantic-search integration; not production-ready without artifacts/data gates
- ⚠️ VNPay and MoMo payment adapters; live/sandbox transaction flow still requires staging validation
- ⚠️ Goong Directions and forward geocoding; requires a valid key and real account smoke test
- ✅ Three.js 3D WebGL Saigon and GLB Landmark Viewer UI
- ⚠️ Telegram Bot and Zalo Poller integrations; require external configuration
- ✅ RBAC and Admin/Provider/Traveler portal code
- ✅ Alembic migrations and automated tests (use current CI results; older README claimed 12 migrations and 107 passing tests)
- ✅ Docker Compose configuration
- ✅ GitHub Actions CI/CD workflows
- ✅ Vietnamese/English UI and dual themes

### Short term (v1.1)
- 🔲 Integrate Open-Meteo or another live weather API for Weather AQI Advisor
- 🔲 Train a flood-risk model with sufficient verified negative observations
- 🔲 Mobile PWA: service worker and offline-first caching
- 🔲 Web Push notifications for booking updates
- 🔲 Booking-by-hour heatmap in the Admin Dashboard

### Medium term (v2.0)
- 🔲 Expand to multiple cities (Da Nang, Hanoi, Hoi An)
- 🔲 Real-time collaborative itinerary editing (WebSocket)
- 🔲 AI-driven photo quality scoring for Evidence management
- 🔲 Provider revenue analytics dashboard
- 🔲 Google Calendar / Apple Calendar integration

---

## 🤝 Contributing and license

### Contributing
Contributions are welcome. Please:
1. Fork the repository and create a branch from main.
2. Follow the commit conventions in commitlint.config.js (Conventional Commits).
3. Run pytest -q and npm run lint before opening a PR.
4. Read [BRANCHING.md](./BRANCHING.md) for the branching strategy.

### Security reports
See [SECURITY.md](./.github/SECURITY.md) to report a vulnerability responsibly.

### License
Software: [MIT License](./LICENSE).

Flood report data (data/raw/hcmc_flood_reports_2002_2026.csv): CC BY-NC 4.0 — Hardy, Sebastien; Radziute, Gintarė (2026). *Historical database of urban flooding in Ho Chi Minh City, Vietnam (2002–2026)*. DataSuds. DOI: [10.23708/8Y16HU](https://doi.org/10.23708/8Y16HU).

---

<div align="center">
  <p>Built with ❤️ for Ho Chi Minh City</p>
  <p><a href="https://nguyentribaothang.github.io/LocalExplorerAI/">Technical Documentation</a> · <a href="./DEMO_SCRIPT.md">Demo Script</a> · <a href="./ARCHITECTURE.md">Architecture</a></p>
</div>
