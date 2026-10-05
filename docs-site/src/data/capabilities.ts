import { SRC, type Status } from './site'

export interface Capability {
  title: string
  status: Status
  body: string
  evidence: string
  caveat?: string
}

export const CAPABILITIES: Capability[] = [
  {
    title: 'POI → Experience → Slot model',
    status: 'implemented',
    body: 'Places, the activities hosted there, and the time-boxed, capacity-limited sessions of each activity are separate entities. Itinerary stops reference a slot, not just a place.',
    evidence: SRC.entities,
  },
  {
    title: 'Slot-aware planner',
    status: 'implemented',
    body: 'A deterministic planner schedules the earliest feasible slot at each step. Budget, time window, return deadline and locked experiences are enforced; a slot with unreported capacity makes the plan tentative.',
    evidence: SRC.planner,
  },
  {
    title: 'AI Concierge',
    status: 'partial',
    body: 'Turns free text into structured trip constraints through the CONVERSATION_PARSER prompt. With no LLM configured it answers from a local heuristic fallback.',
    evidence: 'apps/api/app/api/routes/chat.py',
    caveat: 'LLM mode needs an OpenAI-compatible key; the fallback is a heuristic, not a model.',
  },
  {
    title: 'Semantic search (E5)',
    status: 'partial',
    body: 'GET /api/experience-search?semantic=true ranks experiences with a multilingual E5 model loaded from a local directory on CPU. Model loading cannot use the network.',
    evidence: SRC.e5,
    caveat: 'Needs optional dependencies and a locally installed model (E5_MODEL_PATH). Model files are not committed.',
  },
  {
    title: 'XGBoost ranking',
    status: 'partial',
    body: 'An XGBRanker with 13 deterministic features breaks ties among candidates at the earliest feasible time and ranks replacement candidates during replanning.',
    evidence: SRC.ranker,
    caveat: 'Falls back to the heuristic when no bundle is present. The training data is unverified, so production refuses to load it by default.',
  },
  {
    title: 'Dynamic replanning',
    status: 'implemented',
    body: 'A cancelled slot (SLOT_CANCELLED) or weather alert (WEATHER_ALERT) creates an event. Solver-filtered candidates go to the REPLAN_ADVISOR prompt; accepting a proposal writes a new itinerary version.',
    evidence: SRC.replan,
  },
  {
    title: 'Flood risk model',
    status: 'partial',
    body: 'POST /api/ml/flood-risk serves batch inference from a local model bundle. Missing observations stay unknown rather than being treated as safe.',
    evidence: SRC.flood,
    caveat: 'No flood bundle is committed, and predictions are not used in routing.',
  },
  {
    title: 'Weather and AQI advisory',
    status: 'implemented',
    body: 'The WEATHER_AQI_ADVISOR prompt assesses rain and PM2.5 impact on outdoor stops and can raise a WEATHER_ALERT event.',
    evidence: 'apps/api/app/api/routes/ai.py',
    caveat: 'The endpoint is admin-only in the current code.',
  },
  {
    title: 'Bookings and payments',
    status: 'implemented',
    body: 'Row-locked seat holds with expiry, provider accept/reject, VNPay and MoMo checkout with server-to-server IPN confirmation, and a transactional email outbox.',
    evidence: 'apps/api/app/api/routes/bookings.py',
    caveat: 'Gateways are configured for sandbox by default.',
  },
  {
    title: 'Provider portal',
    status: 'implemented',
    body: 'Providers manage POIs, experiences, slots (optimistic locking via expected_version), evidence, bookings, and use a two-step signed slot assistant.',
    evidence: 'apps/api/app/api/routes/provider.py',
  },
  {
    title: 'Admin portal and RBAC',
    status: 'implemented',
    body: 'Roles traveler, provider and admin enforced by route dependencies. Admin gets moderation, duplicate-POI merge, user management, integrations, imports, operations and an audit log.',
    evidence: 'apps/api/app/api/routes/admin.py',
  },
  {
    title: 'Itinerary versioning',
    status: 'partial',
    body: 'Itineraries snapshot into versions that can be listed, and accepting a replan proposal creates a new version. Two itineraries can be compared side by side.',
    evidence: 'apps/api/app/api/routes/planner.py',
    caveat: 'The README mentions rollback, but no rollback code was found in the repository.',
  },
  {
    title: '3D digital twin',
    status: 'implemented',
    body: 'The product app renders a Three.js city with a river, buildings and radar-pulse POI pins, plus a GLB landmark viewer.',
    evidence: 'apps/web/src/components/3d/',
    caveat: 'This docs site uses a lightweight SVG visualization instead of loading Three.js.',
  },
]
