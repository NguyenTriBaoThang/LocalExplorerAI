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
    status: 'verified',
    body: 'Places, the activities hosted there, and the time-boxed, capacity-limited sessions of each activity are separate entities. Itinerary stops reference a slot, not just a place.',
    evidence: SRC.entities,
  },
  {
    title: 'Slot-aware deterministic planner',
    status: 'verified',
    body: 'A deterministic scheduler filters infeasible candidates and schedules the earliest feasible slot. Hard constraints (budget, time window, return deadline, opening hours, capacity, locked stops) are strictly enforced.',
    evidence: SRC.planner,
  },
  {
    title: 'B2B Tour Operator Quoting & Pricing',
    status: 'verified',
    body: 'Generates professional tour quotations for corporate & agency clients with rate-card integration, cost rollups, automated profit margin optimization, and post-tour invoice reconciliation.',
    evidence: SRC.quote,
  },
  {
    title: 'Margin Protection Guardrail',
    status: 'verified',
    body: 'Strict margin guardrail prevents tour quotes from breaching corporate floor percentages. Automatically computes the minimal price restoring margin feasibility.',
    evidence: 'apps/api/app/services/quote/margin_guard.py',
  },
  {
    title: 'AI Concierge (Catalog v3.2.0)',
    status: 'verified',
    body: 'Extracts structured trip constraints from free-form Vietnamese and English chat across 20 specialized workflows. With no LLM configured, it responds via a deterministic local heuristic fallback.',
    evidence: 'apps/api/app/api/routes/chat.py',
    caveat: 'LLM mode requires an OpenAI-compatible API key; local fallback provides deterministic heuristic extraction.',
  },
  {
    title: 'Semantic search (Multilingual E5)',
    status: 'partial',
    body: 'GET /api/experience-search?semantic=true embeds queries and descriptions locally on CPU using multilingual-e5-base without external network calls.',
    evidence: SRC.e5,
    caveat: 'Model weights are downloadable via scripts/download_e5_model.py; offline fallback performs fast keyword matching.',
  },
  {
    title: 'XGBoost ranking (Experimental pilot)',
    status: 'experimental',
    body: '15 deterministic features (ranker-features-v2) score candidate fit to break ties. Production defaults to rule-baseline-v1; XGBoost pilot requires ALLOW_UNVERIFIED_RANKER=true due to weak synthetic labels.',
    evidence: SRC.ranker,
    caveat: 'Default production model is rule-baseline-v1; XGBoost model is quarantined as an experimental pilot.',
  },
  {
    title: 'Dynamic replanning',
    status: 'verified',
    body: 'Reacts to SLOT_CANCELLED or WEATHER_ALERT events. Solver-filtered candidates pass to the REPLAN_ADVISOR prompt; accepted proposals generate a new immutable itinerary version.',
    evidence: SRC.replan,
  },
  {
    title: 'Itinerary versioning & Rollback',
    status: 'verified',
    body: 'Itineraries maintain immutable version snapshots. Clients can list versions, inspect side-by-side diffs, and perform atomic rollback via POST /api/trips/{id}/restore/{version}.',
    evidence: 'apps/api/app/api/routes/trips.py',
  },
  {
    title: 'Flood risk model',
    status: 'experimental',
    body: 'POST /api/ml/flood-risk serves batch segment predictions from historical flood reports. Missing sensor observations return unknown rather than assuming safe conditions.',
    evidence: SRC.flood,
    caveat: 'Offline research prototype; not currently integrated into active road routing graph.',
  },
  {
    title: 'Weather and AQI advisory',
    status: 'verified',
    body: 'The WEATHER_AQI_ADVISOR prompt analyzes live rainfall, temperature, and PM2.5 levels to proactively recommend indoor switches for outdoor itinerary legs.',
    evidence: 'apps/api/app/api/routes/ai.py',
  },
  {
    title: 'Bookings and payments',
    status: 'verified',
    body: 'Row-locked seat holds with automatic expiration, provider accept/reject lifecycle, VNPay & MoMo sandbox integrations, and a transactional email outbox.',
    evidence: 'apps/api/app/api/routes/bookings.py',
  },
  {
    title: 'Partner & Operator Portal',
    status: 'verified',
    body: 'Dedicated multi-tenant React 18 application for Experience Providers and B2B Tour Operators to manage rate cards, draft quotes, update slots, and track reconciliation.',
    evidence: SRC.portal,
  },
  {
    title: 'Admin portal & 4-Tier RBAC',
    status: 'verified',
    body: 'Fine-grained RBAC enforcing traveler, provider, operator, and admin roles. Includes POI verification, duplicate merge, encrypted integrations, and audit trail.',
    evidence: 'apps/api/app/api/routes/admin.py',
  },
  {
    title: '3D Digital Twin & Generative Meshy',
    status: 'verified',
    body: 'Three.js interactive city hero with radar-pulse pins, GLB landmark viewer with spatial calibration, and background Meshy 3D text/image-to-mesh generation worker.',
    evidence: 'apps/web/src/components/3d/',
  },
]
