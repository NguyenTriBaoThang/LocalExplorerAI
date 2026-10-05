
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
    id: 'web', label: 'Web client', sub: 'React · TypeScript · Vite · Three.js', x: 280, y: 16, w: 400, h: 58, tone: 'client',
    responsibility: 'Renders the explorer, AI chat, planner wizard, itinerary timeline, compare view, and the provider and admin portals. Role-based route guards decide what each user sees.',
    technology: 'React 18, TypeScript, Vite 6, Three.js, Leaflet with CartoDB tiles',
    input: 'User input, REST responses',
    output: 'REST requests, rendered itinerary and map',
    location: 'apps/web/src',
  },
  {
    id: 'api', label: 'FastAPI gateway', sub: 'REST · Pydantic · RBAC', x: 40, y: 112, w: 880, h: 58, tone: 'api',
    responsibility: 'Validates every request against a Pydantic schema, resolves the session cookie, and enforces roles with route dependencies before calling services.',
    technology: 'Python 3.12, FastAPI, Pydantic v2',
    input: 'HTTP requests with session cookie',
    output: 'JSON responses, error envelope',
    location: 'apps/api/app/api/routes',
  },
  {
    id: 'catalog', label: 'Catalog & search', sub: 'filters · E5 semantic', x: 40, y: 214, w: 205, h: 64, tone: 'logic',
    responsibility: 'Lists POIs, experiences and slots, applies intent, time, budget, group and radius filters, and optionally ranks by semantic similarity.',
    technology: 'SQLAlchemy 2, PostGIS, sentence-transformers (optional)',
    input: 'Query parameters',
    output: 'Experiences with slots',
    location: 'apps/api/app/services/experience_service.py, e5_search_service.py',
  },
  {
    id: 'planner', label: 'Deterministic planner', sub: 'feasibility · scheduling', x: 265, y: 214, w: 205, h: 64, tone: 'logic',
    responsibility: 'Builds an ordered itinerary: filters infeasible candidates, schedules the earliest feasible slot, inserts travel legs, and labels each stop feasible or tentative.',
    technology: 'Pure Python, no LLM in the loop',
    input: 'PlanRequest: window, group, budget, intents, locked items',
    output: 'PlanResponse: stops, routes, explanation, reason codes',
    location: 'apps/api/app/services/planner_service.py, planner_engine.py',
  },
  {
    id: 'ranker', label: 'ML ranker', sub: 'XGBoost · tie-break', x: 377, y: 312, w: 205, h: 64, tone: 'ml',
    responsibility: 'Orders tied or replacement candidates using 13 features. Hard filters stay authoritative; the planner falls back to its heuristic if the model is missing.',
    technology: 'XGBoost XGBRanker (rank:ndcg)',
    input: 'Candidate feature rows',
    output: 'Relative rank scores (not probabilities)',
    location: 'apps/api/app/services/ml_ranker_service.py, ranker_features.py',
  },
  {
    id: 'llm', label: 'Prompt runner', sub: '8 versioned prompts', x: 715, y: 214, w: 205, h: 64, tone: 'ml',
    responsibility: 'Runs the eight PRD 3.0 prompts against an OpenAI-compatible provider and validates every output with a Pydantic schema before use.',
    technology: 'Versioned markdown prompts, StructuredOutputProvider',
    input: 'Constraints text, solver-filtered candidates',
    output: 'Validated structured output',
    location: 'apps/api/app/prompts, app/services/prompt_service.py',
  },
  {
    id: 'replan', label: 'Replanning service', sub: 'events · proposals', x: 490, y: 214, w: 205, h: 64, tone: 'logic',
    responsibility: 'Reacts to SLOT_CANCELLED and WEATHER_ALERT events, finds feasible alternatives in the database, ranks them, asks the advisor prompt to explain, and writes a new version on accept.',
    technology: 'Python service over SQLAlchemy',
    input: 'Event id, itinerary',
    output: 'Replan proposals, new itinerary version',
    location: 'apps/api/app/services/replanning_service.py',
  },
  {
    id: 'routing', label: 'Routing adapter', sub: 'Goong · mock for tests', x: 152, y: 312, w: 205, h: 64, tone: 'logic',
    responsibility: 'Returns distance, duration and polyline per leg. ETAs carry source, calculation time and expiry and are not presented as real-time traffic.',
    technology: 'Goong Directions and Geocoding; mock provider for tests and demos',
    input: 'Origin and destination coordinates, travel mode',
    output: 'RouteLeg with eta_source and eta_valid_until',
    location: 'apps/api/app/services/routing_service.py',
  },
  {
    id: 'db', label: 'PostgreSQL + PostGIS', sub: 'source of truth: catalog, plans, versions, bookings', x: 40, y: 410, w: 880, h: 58, tone: 'data',
    responsibility: 'Holds users, providers, POIs (geometry point), experiences, slots, itineraries, versions, bookings, payments and audit trails. Slot rows are locked during seat holds.',
    technology: 'PostgreSQL 16, PostGIS 3.4, Alembic migrations (0001 to 0010)',
    input: 'ORM writes',
    output: 'Rows, spatial queries',
    location: 'apps/api/app/models/entities.py, apps/api/migrations',
  },
]

export const ARCH_EDGES: [string, string][] = [
  ['web', 'api'], ['api', 'catalog'], ['api', 'planner'], ['api', 'replan'], ['api', 'llm'],
  ['planner', 'routing'], ['planner', 'ranker'], ['replan', 'ranker'],
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
  { name: 'Itinerary', table: 'itineraries', note: 'A plan for a time window, group and budget, with versions and a share token.', fields: ['start_time', 'return_deadline', 'group_size', 'budget_vnd', 'current_version', 'share_token'] },
  { name: 'ItineraryStop', table: 'itinerary_stops', note: 'One ordered stop linking an itinerary to an experience, a slot and a POI.', fields: ['stop_order', 'arrival_at', 'cost_vnd', 'is_locked'] },
  { name: 'Booking', table: 'bookings', note: 'A seat hold on a slot with expiry, a provider decision and payment transactions.', fields: ['slot_id', 'quantity', 'status', 'hold_expires_at', 'amount_vnd'] },
]

/* ───────────────────────── Technical decisions ───────────────────────── */

export const DECISIONS = [
  {
    component: 'LLM',
    owns: 'Understand intent and explain.',
    detail: 'Extracts constraints from chat, proposes and explains replacements from a candidate list the solver already filtered, labels feedback. Every output is validated against a Pydantic schema and rejected if invalid.',
    never: 'Never invents places, slots or prices, and is not called while the planner builds an itinerary.',
    where: 'app/services/prompt_service.py',
  },
  {
    component: 'Semantic search',
    owns: 'Retrieve relevant experiences.',
    detail: 'E5 embeddings run locally on CPU, so queries are not sent to a third party.',
    never: 'Does not decide feasibility.',
    where: 'app/services/e5_search_service.py',
  },
  {
    component: 'ML ranker',
    owns: 'Order candidates.',
    detail: 'Breaks ties among candidates at the earliest feasible time and orders replacement candidates.',
    never: 'Cannot override hard filters; if absent the planner keeps its heuristic.',
    where: 'app/services/ml_ranker_service.py',
  },
  {
    component: 'Deterministic planner',
    owns: 'Feasibility and itinerary construction.',
    detail: 'Budget, time window, return deadline and locked experiences are enforced, and unreported capacity downgrades the plan to tentative. Planning itself makes no LLM call.',
    never: 'Does not call an LLM.',
    where: 'app/services/planner_engine.py',
  },
  {
    component: 'Database',
    owns: 'Source of truth.',
    detail: 'Slots, bookings and versions live in PostgreSQL. Seat holds lock the slot row; slot edits use an expected_version check.',
    never: 'Model output is not trusted into the database without validation.',
    where: 'app/models/entities.py',
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
    name: 'apps', note: 'Application code', children: [
      {
        name: 'api', note: 'FastAPI backend', children: [
          { name: 'app', note: 'Package: routes, services, models, schemas, prompts', children: [
            { name: 'api/routes', note: '14 router modules (admin, admin_bot, ai, auth, bookings, catalog, chat, health, ml, models_3d, ops, planner, provider, routing)' },
            { name: 'services', note: 'Planner, replanning, ranker, E5 search, flood model, routing, payments' },
            { name: 'models', note: 'SQLAlchemy entities (entities.py)' },
            { name: 'prompts', note: 'Versioned prompt catalog v3_0_0 with manifest.json' },
            { name: 'schemas', note: 'Pydantic request and response models' },
            { name: 'adapters', note: 'LLM provider adapters' },
          ] },
          { name: 'migrations', note: 'Alembic migrations 0001 to 0010' },
          { name: 'scripts', note: 'seed_db, worker (outbox), download_e5_model, place import' },
          { name: 'tests', note: 'pytest suite' },
        ],
      },
      { name: 'web', note: 'React + Vite product app', children: [
        { name: 'src/components/3d', note: 'CityHero3D, Map3DLandmarkViewer, TiltCard3D' },
        { name: 'src/pages', note: 'Home, Chat, Explore, Planner, Itinerary, Compare, Provider portal, Admin' },
      ] },
      { name: 'models_3d', note: '3D landmark calibration' },
    ],
  },
  { name: 'assets', note: 'Screenshots, banner and logos' },
  { name: 'data', note: 'Seed places JSON, ranking dataset, raw flood reports and experimental labels' },
  { name: 'docs', note: 'API, architecture, data model, ML training, operations, payments and more' },
  { name: 'models', note: 'Model artifact directories (ai-ranker, e5, flood-risk); weights are git-ignored' },
  { name: 'scripts', note: 'Backup and restore for Postgres, smoke test, data utilities' },
  { name: '.github/workflows', note: 'CI, commitlint, labeler (and this site’s Pages deploy)' },
  { name: 'docs-site', note: 'This documentation site (React + Vite, static)' },
  { name: 'docker-compose.yml', note: 'API, web, PostGIS and Redis' },
]

/* ───────────────────────── Platform ───────────────────────── */

export const PLATFORM = [
  {
    role: 'Traveler',
    route: 'traveler',
    items: [
      ['Discover experiences', 'Explore page with intent, budget, group and radius filters; semantic mode when E5 is installed.'],
      ['AI Concierge', 'Chat page with a constraints inspector and one-click planning.'],
      ['Itinerary', 'Plan, timeline, route geometry, share link, PDF print, version list and compare view.'],
      ['Saved trips', 'GET /api/me/itineraries and the profile page.'],
      ['Seat holds & payment', 'Hold a slot, wait for provider acceptance, pay with VNPay or MoMo.'],
      ['Feedback', 'Star rating and comment; an admin-only labeler grades it for training.'],
    ],
  },
  {
    role: 'Provider',
    route: 'provider',
    items: [
      ['Manage experiences', 'Create, update and hide experiences and POIs (changes return to the moderation queue).'],
      ['Manage slots', 'Open slots, change capacity or close them, with expected_version optimistic locking.'],
      ['Evidence', 'Submit licence or ownership evidence for review.'],
      ['Booking requests', 'Accept or reject holds and cancellation requests.'],
      ['Slot assistant', 'Natural-language slot changes with a preview and a signed token valid for five minutes.'],
    ],
  },
  {
    role: 'Admin',
    route: 'admin',
    items: [
      ['Moderation', 'Verify, reject or hide POIs, experiences and evidence.'],
      ['User management', 'Change roles, deactivate accounts.'],
      ['Duplicate POIs', 'Fuzzy-match detection and merge.'],
      ['Integrations', 'Goong, Gemini, Google, VNPay and MoMo settings encrypted with Fernet.'],
      ['Place import staging', 'Review and promote imported candidates.'],
      ['Operations & audit', 'Outbox status, jobs, events and the audit log.'],
    ],
  },
]
