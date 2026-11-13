
/* ───────────────────────── Architecture ───────────────────────── */

export interface ArchNode {
  id: string
  label: string
  sub: string
  x: number
  y: number
  w: number
  h: number
  tone: 'client' | 'api' | 'logic' | 'ml' | 'data'
  responsibility: string
  technology: string
  input: string
  output: string
  location: string
}

export const ARCH_NODES: ArchNode[] = [
  {
    id: 'web', label: 'Web client', sub: 'React · TypeScript · Vite · Three.js', x: 60, y: 16, w: 400, h: 58, tone: 'client',
    responsibility: 'Traveler-facing application: 3D city hero, AI chat concierge, multi-step planner wizard, interactive Leaflet/CartoDB map, itinerary timeline, version comparison, and checkout.',
    technology: 'React 18, TypeScript, Vite 6, Three.js, Leaflet with CartoDB tiles',
    input: 'User interactions, REST responses, Server-Sent Events',
    output: 'REST requests, SSE subscriptions, rendered itinerary & 3D scene',
    location: 'apps/web/src',
  },
  {
    id: 'portal', label: 'Partner & Operator Portal', sub: 'React 18 · Tailwind · Multi-tenant', x: 500, y: 16, w: 420, h: 58, tone: 'client',
    responsibility: 'Operational workspace for Experience Providers, B2B Tour Operators, and Admins: slot scheduling, rate-card configuration, quote optimizer, margin guards, and supplier reconciliation.',
    technology: 'React 18, TypeScript, Tailwind CSS, Lucide icons',
    input: 'Partner credentials, rate cards, quote parameters',
    output: 'B2B quotes, rate card updates, slot capacity modifications',
    location: 'apps/portal/src',
  },
  {
    id: 'api', label: 'FastAPI gateway', sub: 'REST · SSE · Pydantic v2 · RBAC (33 router modules)', x: 40, y: 112, w: 880, h: 58, tone: 'api',
    responsibility: 'Central API gateway: validates requests with Pydantic v2, enforces 4-tier RBAC dependencies (Traveler, Provider, Operator, Admin), handles session cookies & RS256 JWTs, streams trip generation via SSE.',
    technology: 'Python 3.12/3.13, FastAPI, Pydantic v2, Starlette SSE',
    input: 'HTTP requests with session cookie or Bearer token',
    output: 'JSON responses, SSE event streams, RFC 7807 error envelopes',
    location: 'apps/api/app/api/routes',
  },
  {
    id: 'catalog', label: 'Catalog & search', sub: 'filters · E5 semantic', x: 40, y: 214, w: 165, h: 64, tone: 'logic',
    responsibility: 'Lists POIs, experiences and slots, applies intent, time, budget, group and radius filters, and optionally ranks by multilingual semantic similarity.',
    technology: 'SQLAlchemy 2, PostGIS, sentence-transformers (multilingual-e5-base)',
    input: 'Query parameters, spatial bounds',
    output: 'Experiences with active slots & reported availability',
    location: 'apps/api/app/services/experience_service.py, e5_search_service.py',
  },
  {
    id: 'planner', label: 'Deterministic planner', sub: 'feasibility · scheduling', x: 220, y: 214, w: 165, h: 64, tone: 'logic',
    responsibility: 'Builds an ordered itinerary: filters infeasible candidates, schedules the earliest feasible slot, inserts travel legs, preserves locked stops, and labels each stop feasible or tentative.',
    technology: 'Pure Python, deterministic heuristic (no LLM in the loop)',
    input: 'PlanRequest: window, group, budget, intents, locked stops',
    output: 'PlanResponse: stops, routes, explanation, reason codes',
    location: 'apps/api/app/services/planner_service.py, planner_engine.py',
  },
  {
    id: 'replan', label: 'Dynamic replanner', sub: 'events · proposals', x: 400, y: 214, w: 165, h: 64, tone: 'logic',
    responsibility: 'Reacts to SLOT_CANCELLED and WEATHER_ALERT events, queries database for feasible alternatives, ranks replacements, and writes a new immutable version on acceptance.',
    technology: 'Python service over SQLAlchemy, event-driven',
    input: 'Event id, active itinerary state',
    output: 'Replan proposals, updated itinerary version',
    location: 'apps/api/app/services/replanning_service.py',
  },
  {
    id: 'operator', label: 'Quoting engine', sub: 'rate cards · margin guard', x: 580, y: 214, w: 165, h: 64, tone: 'logic',
    responsibility: 'B2B tour quoting: calculates cost rollups from supplier rate cards, models client win probability, enforces corporate margin floors, and performs post-tour reconciliation.',
    technology: 'Python service, rate-card matrix, margin guardrail',
    input: 'Group size, tour itinerary, client tier, discount',
    output: 'Quote proposals, win probability, margin audit status',
    location: 'apps/api/app/services/quote/',
  },
  {
    id: 'llm', label: 'Prompt runner', sub: '20 versioned workflows', x: 760, y: 214, w: 160, h: 64, tone: 'ml',
    responsibility: 'Executes the 20 catalog v3.2.0 prompts against OpenAI-compatible LLMs with structured output validation; falls back to deterministic heuristics when no API key is set.',
    technology: 'Versioned markdown prompts v3.2.0, StructuredOutputProvider',
    input: 'Constraints text, candidate lists, itinerary context',
    output: 'Validated Pydantic structured output',
    location: 'apps/api/app/prompts/v3_2_0/, app/services/prompt_service.py',
  },
  {
    id: 'routing', label: 'Routing adapter', sub: 'Goong · road legs', x: 40, y: 312, w: 200, h: 64, tone: 'logic',
    responsibility: 'Computes road distance, travel duration and encoded polylines per leg. ETAs carry calculation time, expiry timestamp, and data source.',
    technology: 'Goong Directions & Geocoding APIs; deterministic mock for tests',
    input: 'Origin/destination coords, travel mode (motorcycle, car, walk)',
    output: 'RouteLeg with distance_m, duration_min, polyline, eta_valid_until',
    location: 'apps/api/app/services/routing_service.py',
  },
  {
    id: 'ranker', label: 'Candidate ranker', sub: '15 features · baseline default', x: 260, y: 312, w: 200, h: 64, tone: 'ml',
    responsibility: 'Breaks ties among feasible candidates at the earliest available time. Default production active model is rule-baseline-v1; XGBoost model is quarantined as an experimental pilot.',
    technology: 'rule-baseline-v1 (default) / XGBRanker (ranker-features-v2)',
    input: '15 candidate feature rows',
    output: 'Relative rank scores (never overrides feasibility)',
    location: 'apps/api/app/services/ml_ranker_service.py, ranker_features.py',
  },
  {
    id: 'quotewin', label: 'Quote win model', sub: '18 features · synthetic pilot', x: 480, y: 312, w: 200, h: 64, tone: 'ml',
    responsibility: 'Predicts client quote acceptance probability across 18 features (lead time, margin, season, group size). Backtest shows +9.5% profit gain; bounded by MarginGuard.',
    technology: 'XGBoost binary classifier (binary:logistic, quote-win-features-v1)',
    input: '18 quote feature parameters',
    output: 'P(win) win probability score (0.0 to 1.0)',
    location: 'apps/api/app/services/quote/win_model.py, models/quote-win/',
  },
  {
    id: 'meshy', label: '3D Meshy worker', sub: 'generative mesh pipeline', x: 700, y: 312, w: 220, h: 64, tone: 'logic',
    responsibility: 'Background pipeline connecting to Meshy API for text/image-to-3D asset generation; manages task polling, local caching, and 3D landmark calibration.',
    technology: 'Async HTTP, Meshy API client, GLB asset cache',
    input: 'Prompt description or landmark reference image',
    output: 'Optimized GLB 3D model with calibration transform',
    location: 'apps/api/app/services/meshy_service.py',
  },
  {
    id: 'db', label: 'PostgreSQL 16 + PostGIS 3.4', sub: '30 Alembic revisions (0001–0030) · row-locked slots · quotes & audit trail', x: 40, y: 410, w: 880, h: 58, tone: 'data',
    responsibility: 'Primary source of truth: POIs with spatial geometry, experiences, capacity slots, itineraries, version snapshots, B2B quotes & rate cards, bookings, and full audit logs.',
    technology: 'PostgreSQL 16, PostGIS 3.4, SQLAlchemy 2, Alembic (30 revisions: 0001 to 0030)',
    input: 'ORM queries and transactional writes',
    output: 'Persistent relational & spatial records, row-level locks',
    location: 'apps/api/app/models/entities.py, apps/api/migrations/versions/',
  },
]

export const ARCH_EDGES: [string, string][] = [
  ['web', 'api'],
  ['portal', 'api'],
  ['api', 'catalog'],
  ['api', 'planner'],
  ['api', 'replan'],
  ['api', 'operator'],
  ['api', 'llm'],
  ['api', 'meshy'],
  ['planner', 'routing'],
  ['planner', 'ranker'],
  ['replan', 'ranker'],
  ['operator', 'quotewin'],
]

/* ───────────────────────── Data model ───────────────────────── */

export interface Entity {
  name: string
  table: string
  note: string
  fields: string[]
}

export const ENTITIES: Entity[] = [
  { name: 'POI', table: 'pois', note: 'A physical place with a PostGIS point. Existing and being open says nothing about what can be done there.', fields: ['name', 'district', 'latitude / longitude', 'geom', 'verification_status'] },
  { name: 'Experience', table: 'experiences', note: 'An activity hosted at a POI by a provider, with intent tags, duration and price.', fields: ['poi_id', 'provider_id', 'intent_tags', 'is_hands_on', 'is_indoor', 'duration_min', 'price_vnd'] },
  { name: 'ExperienceSlot', table: 'experience_slots', note: 'A dated session of an experience with capacity and reported availability. This is what an itinerary stop actually consumes.', fields: ['start_at', 'end_at', 'capacity_total', 'available_reported', 'status', 'version'] },
  { name: 'Itinerary', table: 'itineraries', note: 'A plan for a time window, group and budget, with immutable versions and a share token.', fields: ['start_time', 'return_deadline', 'group_size', 'budget_vnd', 'current_version', 'share_token'] },
  { name: 'ItineraryStop', table: 'itinerary_stops', note: 'One ordered stop linking an itinerary to an experience, a slot and a POI.', fields: ['stop_order', 'arrival_at', 'cost_vnd', 'is_locked'] },
  { name: 'Booking', table: 'bookings', note: 'A seat hold on a slot with expiry, a provider decision and payment transactions.', fields: ['slot_id', 'quantity', 'status', 'hold_expires_at', 'amount_vnd'] },
  { name: 'OperatorOrg', table: 'operator_orgs', note: 'A registered B2B tour operator organization with margin guard thresholds and billing details.', fields: ['name', 'license_number', 'margin_floor_pct', 'is_active'] },
  { name: 'RateCard', table: 'rate_cards', note: 'Supplier contract rates for experiences, transport, guides, and hotels with tiered volume pricing.', fields: ['operator_id', 'supplier_id', 'service_type', 'unit_cost_vnd', 'valid_from', 'valid_to'] },
  { name: 'Quote', table: 'quotes', note: 'A B2B tour quotation generated for a client group with dynamic margin optimization and public share token.', fields: ['operator_id', 'client_name', 'total_cost_vnd', 'final_price_vnd', 'margin_pct', 'p_win', 'status'] },
  { name: 'MeshyJob', table: 'meshy_jobs', note: 'A 3D generative reconstruction job tracked from prompt submission to GLB artifact caching.', fields: ['task_id', 'prompt', 'status', 'progress', 'glb_path', 'created_at'] },
]

/* ───────────────────────── Technical decisions ───────────────────────── */

export const DECISIONS = [
  {
    component: 'LLM (Catalog v3.2.0)',
    owns: 'Natural language understanding and explanations.',
    detail: 'Extracts constraints from chat across 20 specialized workflows, formats structured replacement proposals, and generates multilingual explanations. Outputs are strictly schema-validated via Pydantic.',
    never: 'Never invents places, coordinates, slots or prices, and is never invoked during core itinerary scheduling.',
    where: 'app/prompts/v3_2_0/, app/services/prompt_service.py',
  },
  {
    component: 'Deterministic Planner',
    owns: 'Feasibility constraints and itinerary sequencing.',
    detail: 'Enforces hard constraints: operating windows, return deadlines, slot capacities, group size, and user budget. Unreported capacity marks the stop tentative. Supports locked stops and atomic version restore.',
    never: 'Never relies on an LLM or probabilistic model to determine feasibility.',
    where: 'app/services/planner_engine.py, app/api/routes/trips.py',
  },
  {
    component: 'ML Candidate Ranker',
    owns: 'Tie-breaking candidate order.',
    detail: 'Breaks ties among candidates at the earliest feasible time slot using 15 deterministic features. Quarantined in staging; production defaults to rule-baseline-v1.',
    never: 'Cannot override hard feasibility filters; fallback heuristics activate automatically if model files are absent.',
    where: 'app/services/ml_ranker_service.py, app/services/ranker_features.py',
  },
  {
    component: 'B2B Quoting & Margin Guard',
    owns: 'Tour operator quotation and margin protection.',
    detail: 'Calculates cost rollups from supplier rate cards, models client win probability, and enforces corporate margin floors. Alerts if requested discounts breach safety thresholds.',
    never: 'Never permits price quotation below the operator margin floor without explicit admin override.',
    where: 'app/services/quote/margin_guard.py, app/services/quote/pricing_optimizer.py',
  },
  {
    component: 'Semantic Search (E5)',
    owns: 'Multilingual vector candidate retrieval.',
    detail: 'Multilingual-e5-base embeddings run locally on CPU, ensuring zero traveler query leakage to external cloud APIs.',
    never: 'Does not decide schedule feasibility or pricing.',
    where: 'app/services/e5_search_service.py',
  },
  {
    component: 'Session Security & RBAC',
    owns: 'Authentication, identity, and authorization.',
    detail: 'Argon2id password hashing, RS256 JWT tokens, secure HTTP-only session cookies, TOTP MFA, and 4-tier RBAC (Traveler, Provider, Operator, Admin).',
    never: 'Never stores plaintext passwords or shared secrets unencrypted.',
    where: 'app/api/permissions.py, app/services/rbac_service.py',
  },
  {
    component: 'Database (PostgreSQL + PostGIS)',
    owns: 'Single source of truth.',
    detail: 'Relational data and spatial geometries managed across 30 Alembic migrations. Row-level locks safeguard seat holds, and optimistic concurrency protects slot capacity edits.',
    never: 'Model predictions are never written directly to production tables without schema validation.',
    where: 'app/models/entities.py, apps/api/migrations/versions/',
  },
]

/* ───────────────────────── Repository explorer ───────────────────────── */

export interface TreeNode {
  name: string
  note?: string
  children?: TreeNode[]
}

export const REPO_TREE: TreeNode[] = [
  {
    name: 'apps', note: 'Applications and services', children: [
      {
        name: 'api', note: 'FastAPI backend service', children: [
          { name: 'app', note: 'Application core package', children: [
            { name: 'api/routes', note: '33 router modules (admin, auth, bookings, catalog, chat, ml, models_3d, operator_quotes, trips, etc.)' },
            { name: 'services', note: 'Planner, replanning, quote engine, ranker, E5 search, flood model, routing, payments' },
            { name: 'models', note: 'SQLAlchemy entities (entities.py, quote_entities.py)' },
            { name: 'prompts', note: 'Versioned prompt catalog v3_2_0 (20 specialized workflows) with manifest.json' },
            { name: 'schemas', note: 'Pydantic v2 request and response contracts' },
            { name: 'adapters', note: 'LLM provider adapters and external service clients' },
          ] },
          { name: 'migrations', note: '30 Alembic migrations (0001 to 0030)' },
          { name: 'scripts', note: 'seed_db, worker (outbox), download_e5_model, place import' },
          { name: 'tests', note: '346+ passing pytest unit and integration test suite' },
        ],
      },
      {
        name: 'web', note: 'React + TypeScript + Vite traveler web application', children: [
          { name: 'src/components/3d', note: 'CityHero3D, Map3DLandmarkViewer, TiltCard3D' },
          { name: 'src/pages', note: 'Home, Chat, Explore, Planner, Itinerary, Compare, Profile, Checkout' },
        ],
      },
      {
        name: 'portal', note: 'React 18 + Tailwind multi-tenant Partner & Operator workspace', children: [
          { name: 'src/pages', note: 'Dashboard, Rate Cards, Quotes, Slots, Reconciliation' },
        ],
      },
      { name: 'models_3d', note: '3D landmark calibration and GLB meshes' },
    ],
  },
  { name: 'assets', note: 'Screenshots, architecture diagrams, and logos' },
  { name: 'data', note: 'Seed places JSON, ranking dataset, raw flood reports, and experimental labels' },
  { name: 'docs', note: 'Enterprise documentation (API, architecture, data model, ML training, operations, payments)' },
  { name: 'docs-site', note: 'GitHub Pages technical documentation website (React + Vite static SPA)' },
  { name: 'models', note: 'Model artifact directories (ai-ranker, quote-win, e5, flood-risk); weights git-ignored' },
  { name: 'scripts', note: 'Database backup/restore, smoke test, download utilities' },
  { name: '.github/workflows', note: 'CI test suites, commitlint, and deploy-pages.yml' },
  { name: 'docker-compose.yml', note: 'FastAPI, Web, Portal, PostgreSQL 16 PostGIS, Redis' },
]

/* ───────────────────────── Platform ───────────────────────── */

export const PLATFORM = [
  {
    role: 'Traveler',
    route: 'traveler',
    items: [
      ['Discover experiences', 'Explore page with intent, budget, group and radius filters; semantic search mode with multilingual-e5.'],
      ['AI Concierge', 'Conversational chat with constraint extraction and one-click deterministic itinerary generation.'],
      ['Itinerary & Timeline', 'Full timeline, travel duration per leg, shareable URL, PDF export, and version comparison.'],
      ['Saved Trips & Versions', 'Browse itinerary history, inspect snapshot changes, and perform atomic rollback.'],
      ['Seat Holds & Payments', 'Row-locked seat holds with countdown expiry, provider acceptance, and VNPay/MoMo checkout.'],
      ['Reviews & Feedback', 'Submit 1-5 star ratings and reviews; automated feedback labeling for continuous improvement.'],
    ],
  },
  {
    role: 'Experience Provider',
    route: 'provider',
    items: [
      ['Manage experiences', 'Create, update and publish experiences and POIs through the moderation queue.'],
      ['Manage capacity slots', 'Open slots, set seat capacity, or close sessions with optimistic concurrency locking.'],
      ['Evidence submission', 'Upload business licenses or location verification documents for administrative review.'],
      ['Booking approvals', 'Review incoming seat holds, accept or reject booking requests, and manage cancellations.'],
      ['Slot assistant', 'Natural-language slot adjustments with preview and cryptographic signed 5-minute confirmation tokens.'],
    ],
  },
  {
    role: 'B2B Tour Operator',
    route: 'operator',
    items: [
      ['Tour Quoting Engine', 'Build customized multi-day or single-day corporate tour quotes with automated cost rollups.'],
      ['Rate-card Management', 'Maintain contracted supplier rates for transport, guides, experiences, and accommodations.'],
      ['Pricing Optimizer', 'Win-rate estimation powered by XGBoost to maximize profit while maintaining competitive win probability.'],
      ['Margin Guardrails', 'Corporate margin floor enforcement preventing accidental unprofitable quotations.'],
      ['Invoice Reconciliation', 'Batch reconcile actual supplier billing against quoted estimates to identify variances.'],
    ],
  },
  {
    role: 'Administrator',
    route: 'admin',
    items: [
      ['Catalog Moderation', 'Verify, reject, or hide POIs, experiences, and partner evidence submissions.'],
      ['4-Tier RBAC & Users', 'Manage accounts, assign roles (Traveler, Provider, Operator, Admin), and review access logs.'],
      ['Duplicate POI Merge', 'Automated fuzzy-match duplicate detection with one-click geometry and experience merging.'],
      ['Encrypted Integrations', 'Manage Goong, Gemini, Google OAuth, VNPay, and MoMo credentials encrypted with Fernet at rest.'],
      ['Staging Imports', 'Review, clean, and promote batch POI imports into the live production catalog.'],
      ['Operations & Audit', 'Monitor transactional outbox, background worker status, system events, and security audit log.'],
    ],
  },
]
