# Local Explorer AI — System Architecture Specification

> **Living Architecture Specification (Synchronized with Repository State)**  
> **Repository:** [LocalExplorerAI](https://github.com/NguyenTriBaoThang/LocalExplorerAI) · **Last Synchronized:** November 2026 · **Branch:** `main`

---

## 1. Architecture Overview

**Local Explorer AI** is an intelligent urban discovery, slot-aware itinerary planning, and experience commerce platform focused on Ho Chi Minh City. Traditional map solutions treat places as static coordinates on a 2D map. Local Explorer AI introduces a **four-layer temporal-spatial hierarchy**:

```text
Physical POI (Geographic Point)
   └── Experience (Curated Activity)
         └── ExperienceSlot (Time Window + Capacity + Status)
               └── Itinerary / Booking (Feasible Route + 15-min Seat Hold)
```

The system operates across three core domains:
1. **B2C Traveler Discovery & Smart Planning:** Multi-turn conversational AI Concierge, deterministic heuristic route optimization, 3D WebGL Digital Twin, and secure booking holds with VNPay / MoMo payments.
2. **B2B Experience Provider & Operator Platform:** Dedicated Partner Portal, slot capacity management, AI Slot Assistant, B2B tour quote generation, rate cards, and financial margin guardrails.
3. **Platform Governance & GeoAI Intelligence:** Admin moderation, fuzzy duplicate POI detection, RBAC with MFA, audit logging, Meshy 3D generative model worker, and versioned AI prompt workflows.

---

## 2. High-Level Monorepo Structure

```text
LocalExplorerAI/
├── apps/
│   ├── web/           # Public traveler SPA (React 18.3, Vite 6, TypeScript 5.6, Leaflet, Three.js)
│   ├── portal/        # Dedicated Partner & Admin Portal (React 18.3, Vite 6, Tailwind)
│   └── api/           # Backend API (FastAPI 0.142+, Python 3.12+, Uvicorn, SQLAlchemy 2.0)
├── docs-site/         # Static documentation & showcase portal (React, Vite, GitHub Pages)
├── models/            # Versioned ML models (XGBoost Ranker, Quote Win Model, E5, Flood Risk)
├── data/              # Portable catalogs, raw datasets, experimental benchmarks
├── scripts/           # DB seed scripts, crawler, ML training pipelines, test runners
└── docker-compose.yml # Container orchestration (API, Web, Portal, PostgreSQL+PostGIS, Redis)
```

---

## 3. End-to-End System Architecture (Diagram 1)

```mermaid
flowchart TB
    subgraph Clients["Presentation Layer (Frontends)"]
        WebClient["Traveler SPA (apps/web :8080)\nReact 18.3 · Vite 6 · Three.js · Leaflet"]
        PortalClient["Partner & Admin Portal (apps/portal :8081)\nReact 18.3 · Vite 6 · Tailwind"]
        DocsClient["Docs Site (docs-site :5173)\nGitHub Pages Static Showcase"]
    end

    subgraph Security["API Gateway & Hardening (apps/api :8000)"]
        ReqIdMW["X-Request-ID Middleware & JSON Logger"]
        CorsMW["CORSMiddleware (Configured Origins)"]
        SecHeaders["Security Headers (nosniff, DENY, HSTS)"]
        CsrfMW["CSRF Origin Verification (Lax Cookies)"]
        RateLimitMW["Rate Limit Guard (Redis / Local Fallback)"]
    end

    subgraph Routers["FastAPI Routers (33 Modular Routers)"]
        AuthRouter["auth · mfa · rbac"]
        CatalogRouter["catalog · places_admin · site_content"]
        PlannerRouter["planner · routing · trips"]
        AIRouter["ai · chat · recommendations"]
        MLRouter["ml · models_3d · landmark_stories"]
        OperatorRouter["operator · operator_quotes · operator_rate_cards · operator_reconcile · public_quotes"]
        CommerceRouter["bookings · reviews · place_reviews"]
        OpsRouter["health · ops · push_notifications · meshy · admin_bot"]
    end

    subgraph CoreServices["Domain Services Layer"]
        HeuristicSolver["Deterministic Heuristic Planner\n(planner_service.py)"]
        TripRules["Trip Rules Engine & Feasibility\n(trip_rules/)"]
        PromptService["Structured Prompt Runner\n(v3.2.0 Prompt Catalog - 20 workflows)"]
        QuoteEngine["Tour Quoting & Pricing Engine\n(quote_service.py & cost_engine.py)"]
        RankerService["Active Ranker Service\n(rule-baseline-v1 & ML Gate)"]
        BookingService["Seat Hold & Ticket Engine\n(booking_service.py)"]
        SessionService["Auth & Session Runtime\n(session_service.py & RS256 JWT)"]
        MeshyWorker["Meshy 3D Asset Worker\n(background asyncio task)"]
        OutboxWorker["Notification Outbox Worker\n(worker.py: Email & Web Push)"]
    end

    subgraph Persistence["Storage & Intelligence Layer"]
        Postgres[("PostgreSQL 16 + PostGIS 3.4\n(or SQLite in local dev)")]
        RedisCache[("Redis 7.0 (Optional)\nRate Limiting & Auth State")]
        ModelStorage[("Local Model Registry\nmodels/ai-ranker, models/quote-win")]
        PromptsStorage[("Prompt Catalog\napps/api/app/prompts/v3_2_0/")]
    end

    subgraph External["External Services & Gateways"]
        GoongAPI["Goong Maps API\n(Directions & Geocoding)"]
        OpenMeteo["Open-Meteo API\n(Weather & PM2.5 AQI)"]
        LLMProvider["OpenAI / Gemini API\n(Structured JSON via Instructor)"]
        PaymentGateways["VNPay & MoMo\n(Payment IPN Gateways)"]
        TelegramZalo["Telegram Bot & Zalo Poller"]
        MeshyAI["Meshy.ai API\n(Text/Image to 3D GLB)"]
    end

    Clients --> Security
    Security --> Routers
    Routers --> CoreServices

    CoreServices --> Postgres
    CoreServices --> RedisCache
    CoreServices --> ModelStorage
    CoreServices --> PromptsStorage

    CoreServices --> GoongAPI
    CoreServices --> OpenMeteo
    CoreServices --> LLMProvider
    CoreServices --> PaymentGateways
    CoreServices --> TelegramZalo
    CoreServices --> MeshyAI
```

---

## 4. AI Concierge & Chat Workflow (Diagram 2)

The AI Concierge accepts natural Vietnamese travel prompts, extracts structured constraints using prompt-driven workflows, and seamlessly transitions into the heuristic route planner.

```mermaid
sequenceDiagram
    autonumber
    actor Traveler as Traveler
    participant Web as Web Client (/chat)
    participant ChatAPI as API (/api/chat & /api/trips)
    participant RouterPrompt as Chat Intent Router (v3.2.0)
    participant ParserPrompt as Conversation Parser (v3.2.0)
    participant Planner as Heuristic Solver
    participant DB as Database Catalog

    Traveler->>Web: Enter query (e.g. "2 người đi làm gốm Quận 1 từ 9h-16h ngân sách 1tr")
    Web->>ChatAPI: POST /api/trips/stream or /api/chat/message
    ChatAPI->>RouterPrompt: Classify message intent (planning / weather / general)
    RouterPrompt-->>ChatAPI: Intent = "planning"
    ChatAPI->>ParserPrompt: Extract constraints (group_size, budget, hours, intents, mode)
    ParserPrompt-->>ChatAPI: Structured constraints JSON
    
    alt Missing essential constraints (e.g. no time range)
        ChatAPI-->>Web: SSE Event: 'clarification' (Question in Vietnamese)
        Web-->>Traveler: Render interactive clarification chip
    else Constraints complete
        ChatAPI->>DB: Query available ExperienceSlots matching time/group
        DB-->>ChatAPI: Candidate experiences & slots
        ChatAPI->>Planner: Solve feasible itinerary matching constraints
        Planner-->>ChatAPI: Feasible stops & road legs
        ChatAPI-->>Web: SSE Event: 'plan_created' (Itinerary v1 preview)
        Web-->>Traveler: Render Itinerary, Timeline & 3D Route Map
    end
```

---

## 5. Smart Route Planning & Multi-Objective Optimization (Diagram 3)

The planning engine prioritizes **hard physical and temporal feasibility** before applying multi-objective ranking.

```mermaid
flowchart TD
    Start["User Request:\nStart time, Return deadline, Budget, Group Size, Travel Mode, Locked Stops"] --> Filter1

    subgraph Stage1["Stage 1: Hard Feasibility Filtering (Deterministic)"]
        Filter1["Filter 1: Date & Opening Hours Feasibility"] --> Filter2
        Filter2["Filter 2: Capacity & Available Slots (available_reported >= group_size)"] --> Filter3
        Filter3["Filter 3: Budget Constraint (Total Stop Cost <= budget_vnd)"] --> Filter4
        Filter4["Filter 4: Inbound & Outbound Feasibility (Arrival & Return deadlines)"]
    end

    Filter4 --> Stage2

    subgraph Stage2["Stage 2: Spatial & Distance Estimation"]
        Spatial1["Matrix Distance Calculation\n(Haversine baseline or Goong Directions cache)"]
        Spatial2["Locked Stops Preservation\n(Never reorder or prune user-pinned stops)"]
        Spatial1 --> SpatialMerge["Candidate Route Legs Formed"]
        Spatial2 --> SpatialMerge
    end

    Stage2 --> Stage3

    subgraph Stage3["Stage 3: Multi-Objective Candidate Scoring"]
        Score1["Intent Alignment Score\n(Weight matches: Culture, Food, Craft, Relaxation)"]
        Score2["Travel Friction Minimization\n(Avoid backtracking & peak heat midday travel)"]
        Score3["Active Ranker Tie-Breaking\n(rule-baseline-v1 or approved ML Ranker)"]
        Score1 --> AggregateScore["Total Candidate Utility"]
        Score2 --> AggregateScore
        Score3 --> AggregateScore
    end

    Stage3 --> Output["Generated Itinerary\n(Numbered stops, arrival/departure timestamps, road polylines, cost breakdown)"]
```

---

## 6. AI & Machine Learning Inference Architecture (Diagram 4)

Local Explorer AI separates **heuristic baseline validation** from **experimental machine learning models**. Unverified models cannot bypass hard planning constraints.

```mermaid
flowchart LR
    CandidateInput["Candidate Experiences\n(Passing Stage 1 Feasibility)"] --> FeatureExtractor

    subgraph FeatureEngineering["Feature Engineering (ranker-features-v2)"]
        FeatureExtractor["Extract 15 Features:\n- intent_match_score\n- price_ratio_budget\n- duration_fit\n- capacity_ratio\n- distance_from_prev_km\n- is_indoor / weather_match\n- provider_reputation\n- ..."]
    end

    FeatureEngineering --> GateCheck

    subgraph MLGate["Model Integrity & Safety Gate"]
        GateCheck{"Check Model Eligibility:\n1. Model SHA-256 match?\n2. dataset_status == verified_human_labeled?\n3. deployment_eligible == True?\n4. ENABLE_BOOTSTRAP_RANKER flag?"}
    end

    GateCheck -- "No / Default" --> RuleBaseline["rule-baseline-v1 (Active Production Ranker)\nDeterministic weighted scoring\nZero overhead · Fully explainable"]
    GateCheck -- "Yes & Flag Enabled" --> XGBRanker["bootstrap_xgboost_pilot (Experimental)\nXGBRanker (15 features)\nDisplays 'Weak-label pilot' badge"]

    RuleBaseline --> RankedOutput["Ranked Candidates with Provenance & XAI Explanations"]
    XGBRanker --> RankedOutput
```

---

## 7. Booking Holds & Payment Architecture (Diagram 5)

Seat reservations follow a strict two-phase commit: a **15-minute temporary hold** followed by provider approval or online payment webhook.

```mermaid
sequenceDiagram
    autonumber
    actor Traveler as Traveler
    participant Web as Web Client (/itinerary)
    participant BookingAPI as API (/api/bookings)
    participant DB as PostgreSQL Database
    participant Outbox as Notification Outbox
    participant Gateway as Payment Gateway (VNPay / MoMo)

    Traveler->>Web: Request booking for selected slot
    Web->>BookingAPI: POST /api/bookings (slot_id, group_size)
    BookingAPI->>DB: Check slot availability with optimistic concurrency (version)
    alt Slot full or locked
        BookingAPI-->>Web: HTTP 409: SLOT_UNAVAILABLE
    else Slot available
        BookingAPI->>DB: Decrement available_reported, create Booking(status='held', expires_at=now+15min)
        BookingAPI-->>Web: Booking confirmed with 15-minute countdown
    end

    Traveler->>Web: Select payment (VNPay / MoMo)
    Web->>BookingAPI: POST /api/bookings/{id}/payment-url
    BookingAPI->>Gateway: Create signed transaction (HMAC-SHA512 / HMAC-SHA256)
    Gateway-->>BookingAPI: Payment gateway redirect URL
    BookingAPI-->>Web: Redirect traveler to payment page

    Traveler->>Gateway: Complete payment
    Gateway->>BookingAPI: Asynchronous IPN Callback (POST /api/bookings/payment/vnpay-ipn)
    BookingAPI->>BookingAPI: Verify cryptographic signature
    BookingAPI->>DB: Update Booking(status='confirmed'), PaymentTransaction(status='completed')
    BookingAPI->>Outbox: Enqueue confirmation email & Web Push notification
    BookingAPI-->>Gateway: Return IPN response (RspCode: 00)
    Outbox->>Traveler: Deliver ticket & calendar hold
```

---

## 8. Core Data Model (Diagram 6)

```mermaid
erDiagram
    User ||--o{ Itinerary : owns
    User ||--o{ AuthSession : maintains
    User ||--o{ Booking : places
    User ||--o{ Review : writes
    Provider ||--o{ POI : operates
    Provider ||--o{ Experience : offers
    POI ||--o{ Experience : hosts
    Experience ||--o{ ExperienceSlot : schedules
    Itinerary ||--o{ ItineraryStop : contains
    Itinerary ||--o{ ItineraryVersion : records
    Itinerary ||--o{ Collaboration : shares
    ExperienceSlot ||--o{ ItineraryStop : allocates
    ExperienceSlot ||--o{ Booking : reserves
    Booking ||--o{ PaymentTransaction : settles
    OperatorOrg ||--o{ TourTemplate : designs
    OperatorOrg ||--o{ RateCard : maintains
    OperatorOrg ||--o{ Quote : issues
    Quote ||--o{ QuoteRevision : revisions
    POI ||--o{ MeshyJob : renders_3d

    User {
        string id PK
        string email UK
        string role "traveler | provider | admin | operator"
        string password_hash
        boolean mfa_enabled
        int token_version
    }

    Provider {
        string id PK
        string name
        string verification_status "simulated | verified | suspended"
        string portal_access_key
    }

    POI {
        string id PK
        string provider_id FK
        string name
        string district
        float latitude
        float longitude
        string category
        string verification_status
    }

    Experience {
        string id PK
        string poi_id FK
        string provider_id FK
        string title
        bigint price_vnd
        int duration_min
        boolean is_hands_on
        boolean is_indoor
        json intent_tags
    }

    ExperienceSlot {
        string id PK
        string experience_id FK
        datetime start_at
        datetime end_at
        int capacity_total
        int available_reported
        string status "open | held | booked | cancelled"
        int version "optimistic lock"
    }

    Itinerary {
        string id PK
        string user_id FK
        datetime start_at
        datetime end_at
        int group_size
        bigint budget_vnd
        string travel_mode
        string status
        int current_version
    }

    Booking {
        string id PK
        string user_id FK
        string slot_id FK
        int group_size
        string status "held | confirmed | cancelled | expired"
        datetime held_until
        bigint total_price_vnd
    }

    Quote {
        string id PK
        string operator_org_id FK
        string customer_name
        string destination
        int pax
        bigint cost_vnd
        bigint quoted_price_vnd
        string status "draft | sent | won | lost"
    }
```

---

## 9. Deployment Architecture (Diagram 7)

```mermaid
flowchart TB
    Internet["Public Internet / Client Browsers"] --> ReverseProxy

    subgraph ProductionHost["Production Host / Container Cluster (Docker Compose)"]
        ReverseProxy["Nginx Reverse Proxy / SSL Termination (:80 / :443)"]

        subgraph Containers["Application Services"]
            WebContainer["web container (:8080)\napps/web (Nginx static build)"]
            PortalContainer["portal container (:5174)\napps/portal (Nginx static build)"]
            APIContainer["api container (:8000)\napps/api (Uvicorn ASGI workers)"]
            WorkerContainer["outbox worker container\n(apps/api/app/worker.py)"]
        end

        subgraph DataStores["State & Storage"]
            PostgresDB[("postgres container (:5432)\nPostgreSQL 16 + PostGIS 3.4\nPersistent Volume: pgdata")]
            RedisDB[("redis container (:6379)\nRedis 7.0 In-Memory\nRate limiting & cache")]
        end

        ReverseProxy -- "/ (frontend)" --> WebContainer
        ReverseProxy -- "/portal" --> PortalContainer
        ReverseProxy -- "/api/*" --> APIContainer

        APIContainer --> PostgresDB
        APIContainer --> RedisDB
        WorkerContainer --> PostgresDB
    end

    subgraph CloudServices["External Cloud APIs"]
        GoongCloud["Goong Cloud API"]
        PaymentCloud["VNPay / MoMo Gateways"]
        OpenAICloud["OpenAI / Gemini LLMs"]
        MeshyCloud["Meshy.ai 3D Cloud"]
    end

    APIContainer --> GoongCloud
    APIContainer --> PaymentCloud
    APIContainer --> OpenAICloud
    APIContainer --> MeshyCloud
```

---

## 10. Security & Hardening Architecture

1. **Authentication:**
   - Stateless **RS256 JWT access tokens** (15-min TTL) in HTTP-only, `SameSite=Lax` cookies (`le_at`).
   - Sliding session **opaque refresh tokens** in HTTP-only cookies (`le_rt`) with automatic reuse detection and immediate family revocation.
   - Password hashing via **Argon2id** (`argon2-cffi`) with automatic legacy re-hash migration.
   - Two-Factor Authentication (**TOTP RFC 6238**) with encrypted backup recovery codes.
2. **Access Control (RBAC):**
   - Granular, system-defined permissions registry (`app.api.permissions.P`).
   - Role-to-permission mapping backed by database with cached matrix (`sync_catalog`).
   - Strict role isolation: `traveler`, `provider`, `operator`, `admin`.
3. **Data Protection:**
   - Integration secrets (API keys, payment secrets) encrypted at rest using **Fernet AES-128-CBC** (`INTEGRATION_SECRETS_KEY`).
   - Audit logging (`AuditLog` table) recording actor, IP, user-agent, and JSON diffs for all sensitive operations.
