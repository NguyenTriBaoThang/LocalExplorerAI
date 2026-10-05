// Endpoints below were extracted from the @router decorators in apps/api/app/api/routes/*.py
// (plus app/main.py). Request bodies follow the Pydantic schemas in apps/api/app/schemas/*.
// Response bodies are abbreviated: only fields that exist in the schema are shown.

export type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface Endpoint {
  method: Method
  path: string
  summary: string
  /** Who may call it, as enforced by the route dependencies. */
  access?: 'public' | 'optional' | 'session' | 'traveler' | 'provider' | 'admin'
  source: string
  request?: string
  response?: string
}

export interface EndpointGroup {
  id: string
  title: string
  endpoints: Endpoint[]
}

const planRequest = `{
  "start_at": "2026-10-06T09:00:00+07:00",
  "end_at": "2026-10-06T16:00:00+07:00",
  "group_size": 2,
  "budget_vnd": 1000000,
  "transport_mode": "motorcycle",
  "intent_weights": { "craft": 0.6, "food": 0.4 },
  "locked_experience_ids": []
}`

const planResponse = `{
  "request_id": "...",
  "itinerary_id": "...",
  "data_mode": "simulated",
  "feasibility_status": "feasible",
  "estimated_cost_vnd": 0,
  "total_travel_min": 0,
  "stops": [
    {
      "experience_id": "...",
      "slot_id": "...",
      "position": 1,
      "arrival_at": "...",
      "start_at": "...",
      "end_at": "...",
      "availability_status": "open",
      "data_status": "simulated"
    }
  ],
  "routes": [
    { "distance_m": 0, "duration_min": 0, "provider": "goong", "is_realtime": false, "eta_valid_until": "..." }
  ],
  "explanation": { "reason_codes": ["..."], "uncertainty": [], "ranking_model_version": null }
}`

const rankRequest = `{
  "query": {
    "user_intent_text": "pottery workshop, indoor",
    "user_intent_tags": ["craft", "indoor"],
    "remaining_time_min": 180,
    "group_size": 2,
    "budget_remaining_vnd": 600000
  },
  "candidates": [
    {
      "candidate_experience_id": "exp-1",
      "candidate_name": "Ceramics studio",
      "candidate_tags": ["craft"],
      "duration_min": 90,
      "price_vnd_per_person": 250000,
      "is_hands_on": true,
      "is_indoor": true,
      "eta_min": 15,
      "hard_feasible": true
    }
  ]
}`

const chatRequest = `{
  "message": "Nhóm mình 2 người, đi từ 08:30 đến 16:30, ngân sách 800.000đ bằng xe máy",
  "conversation_id": null
}`

const chatResponse = `{
  "status": "parsed",
  "assistant_mode": "openai_compatible",
  "conversation_id": null,
  "prompt_version": "3.0.0",
  "reply": "...",
  "structured_constraints": { }
}`

const chatFallback = `{
  "status": "fallback",
  "assistant_mode": "local_fallback",
  "fallback_version": "1.0.0",
  "fallback_reason": "...",
  "reply": "...",
  "structured_constraints": { }
}`

const holdRequestNote = `// Request schema: apps/api/app/schemas/booking.py
// Creates a time-limited seat hold with a row lock on the slot.`

export const API_GROUPS: EndpointGroup[] = [
  {
    id: 'system',
    title: 'Health & system',
    endpoints: [
      { method: 'GET', path: '/health', summary: 'Liveness probe.', access: 'public', source: 'routes/health.py' },
      { method: 'GET', path: '/ready', summary: 'Readiness probe (database and cache checks).', access: 'public', source: 'routes/health.py' },
      { method: 'GET', path: '/', summary: 'Basic API information.', access: 'public', source: 'app/main.py' },
    ],
  },
  {
    id: 'auth',
    title: 'Authentication',
    endpoints: [
      { method: 'POST', path: '/api/auth/register', summary: 'Register a traveler account and set the session cookie.', access: 'public', source: 'routes/auth.py' },
      { method: 'POST', path: '/api/auth/login', summary: 'Email and password login.', access: 'public', source: 'routes/auth.py' },
      { method: 'POST', path: '/api/auth/logout', summary: 'Clear the session cookie.', access: 'public', source: 'routes/auth.py' },
      { method: 'GET', path: '/api/auth/me', summary: 'Current user profile.', access: 'session', source: 'routes/auth.py' },
      { method: 'PATCH', path: '/api/auth/me', summary: 'Update display name and phone.', access: 'session', source: 'routes/auth.py' },
      { method: 'POST', path: '/api/auth/password', summary: 'Change password.', access: 'session', source: 'routes/auth.py' },
      { method: 'GET', path: '/api/auth/google/start', summary: 'Start Google OAuth with PKCE.', access: 'public', source: 'routes/auth.py' },
      { method: 'GET', path: '/api/auth/google/status', summary: 'Whether Google login is configured.', access: 'public', source: 'routes/auth.py' },
      { method: 'GET', path: '/api/auth/google/callback', summary: 'OAuth callback; establishes the session.', access: 'public', source: 'routes/auth.py' },
      { method: 'POST', path: '/api/auth/claim-ticket', summary: 'Attach a shared itinerary (share_token) to an account by email and password, creating the account if needed, and start a session.', access: 'public', source: 'routes/auth.py' },
    ],
  },
  {
    id: 'catalog',
    title: 'Catalog & search',
    endpoints: [
      { method: 'GET', path: '/api/pois', summary: 'List points of interest with coordinates and district.', access: 'public', source: 'routes/catalog.py' },
      { method: 'GET', path: '/api/pois/{poi_id}', summary: 'One POI.', access: 'public', source: 'routes/catalog.py' },
      { method: 'GET', path: '/api/experiences', summary: 'List experiences, filterable by intent, time, budget, group size and radius.', access: 'public', source: 'routes/catalog.py' },
      { method: 'GET', path: '/api/experiences/{experience_id}', summary: 'One experience.', access: 'public', source: 'routes/catalog.py' },
      { method: 'GET', path: '/api/experiences/{experience_id}/slots', summary: 'Slots of an experience with reported availability.', access: 'public', source: 'routes/catalog.py' },
      {
        method: 'GET',
        path: '/api/experience-search',
        summary: 'Keyword search, or local E5 semantic ranking when semantic=true. Requires a local E5 model directory for the semantic mode.',
        access: 'public',
        source: 'routes/catalog.py',
        request: 'GET /api/experience-search?q=pottery%20workshop&semantic=true',
        response: '// A list of experiences. Semantic mode is unavailable (E5NotConfigured)\n// until E5_MODEL_PATH points at a locally installed model.',
      },
    ],
  },
  {
    id: 'routing',
    title: 'Routing & geocoding',
    endpoints: [
      { method: 'GET', path: '/api/routing/capabilities', summary: 'Supported travel modes and routing provider state.', access: 'public', source: 'routes/routing.py' },
      { method: 'GET', path: '/api/geocoding/forward', summary: 'Address to coordinates (Goong forward geocoding when configured).', access: 'public', source: 'routes/routing.py' },
    ],
  },
  {
    id: 'planner',
    title: 'Planner & itineraries',
    endpoints: [
      {
        method: 'POST',
        path: '/api/itineraries/plan',
        summary: 'Build an itinerary with the deterministic planner. The ML ranker is used only as a tie-break.',
        access: 'optional',
        source: 'routes/planner.py · schemas/planner.py',
        request: planRequest,
        response: planResponse,
      },
      { method: 'GET', path: '/api/itineraries/{itinerary_id}', summary: 'A saved itinerary.', access: 'optional', source: 'routes/planner.py' },
      { method: 'GET', path: '/api/me/itineraries', summary: 'Itineraries of the signed-in traveler.', access: 'traveler', source: 'routes/planner.py' },
      { method: 'GET', path: '/api/itineraries/{itinerary_id}/versions', summary: 'Version snapshots of an itinerary.', access: 'traveler', source: 'routes/planner.py' },
      { method: 'GET', path: '/api/itinerary-comparisons', summary: 'Compare two itineraries (first_id, second_id).', access: 'traveler', source: 'routes/planner.py' },
      { method: 'POST', path: '/api/itineraries/{itinerary_id}/share', summary: 'Create a share token.', access: 'traveler', source: 'routes/planner.py' },
      { method: 'DELETE', path: '/api/itineraries/{itinerary_id}/share', summary: 'Revoke the share token.', access: 'traveler', source: 'routes/planner.py' },
      { method: 'GET', path: '/api/shared/itineraries/{share_token}', summary: 'Read a shared itinerary.', access: 'public', source: 'routes/planner.py' },
      { method: 'POST', path: '/api/itineraries/{itinerary_id}/feedback', summary: 'Submit a rating and comment.', access: 'traveler', source: 'routes/planner.py' },
      { method: 'GET', path: '/api/itineraries/{itinerary_id}/feedback', summary: 'List feedback.', access: 'traveler', source: 'routes/planner.py' },
      { method: 'GET', path: '/api/notifications', summary: 'Slot-cancellation notices for the traveler.', access: 'traveler', source: 'routes/planner.py' },
    ],
  },
  {
    id: 'ai',
    title: 'AI workflows',
    endpoints: [
      {
        method: 'POST',
        path: '/api/chat/message',
        summary: 'AI Concierge turn. Extracts structured constraints; falls back to a local heuristic when no LLM is configured.',
        access: 'optional',
        source: 'routes/chat.py',
        request: chatRequest,
        response: `${chatResponse}\n\n// With no LLM key and LLM_FALLBACK_ENABLED:\n${chatFallback}`,
      },
      { method: 'GET', path: '/api/chat/status', summary: 'Whether the concierge is LLM-backed or on the local fallback.', access: 'public', source: 'routes/chat.py' },
      { method: 'GET', path: '/api/ai/prompts', summary: 'Prompt manifest (version 3.0.0, eight prompt ids).', access: 'public', source: 'routes/ai.py' },
      { method: 'POST', path: '/api/itineraries/{itinerary_id}/replan-advice', summary: 'Propose replacements after a cancelled slot or weather alert.', access: 'optional', source: 'routes/ai.py' },
      { method: 'POST', path: '/api/itineraries/{itinerary_id}/replan-advice/accept', summary: 'Accept a proposal and write a new itinerary version.', access: 'optional', source: 'routes/ai.py' },
      { method: 'POST', path: '/api/providers/{provider_id}/slot-assistant/preview', summary: 'Preview a slot change from natural language; returns a signed confirmation token. Authenticates by provider session or X-Provider-Access-Key.', access: 'provider', source: 'routes/ai.py' },
      { method: 'POST', path: '/api/providers/{provider_id}/slot-assistant/confirm', summary: 'Apply the previewed change using the signed token.', access: 'provider', source: 'routes/ai.py' },
      { method: 'POST', path: '/api/experiences/{experience_id}/ai-tag', summary: 'AI tagging of an experience.', access: 'admin', source: 'routes/ai.py' },
      { method: 'POST', path: '/api/ai/intent-similarity', summary: 'Intent similarity between two experiences.', access: 'admin', source: 'routes/ai.py' },
      { method: 'POST', path: '/api/itineraries/{itinerary_id}/feedback/label', summary: 'Label feedback with the grading rubric.', access: 'admin', source: 'routes/ai.py' },
      { method: 'POST', path: '/api/itineraries/{itinerary_id}/weather-advisory', summary: 'Weather / AQI impact on outdoor stops.', access: 'admin', source: 'routes/ai.py' },
    ],
  },
  {
    id: 'ml',
    title: 'Local ML',
    endpoints: [
      { method: 'GET', path: '/api/ml/status', summary: 'Which local model bundles are loaded and their provenance state.', access: 'public', source: 'routes/ml.py' },
      {
        method: 'POST',
        path: '/api/ml/rank-experiences',
        summary: 'Rank candidates with the XGBoost ranker. Hard-infeasible and over-budget candidates are filtered first. The score is not a probability.',
        access: 'public',
        source: 'routes/ml.py · schemas/ml.py',
        request: rankRequest,
        response: '// Candidates ordered by rank_score; the response is produced by\n// ml_ranker_service.py and is unavailable when no ranker bundle is loaded.',
      },
      { method: 'POST', path: '/api/ml/flood-risk', summary: 'Batch flood-risk inference. Returns risk_state=unknown when coverage_ratio is absent.', access: 'public', source: 'routes/ml.py · schemas/ml.py' },
    ],
  },
  {
    id: 'bookings',
    title: 'Bookings & payments',
    endpoints: [
      { method: 'POST', path: '/api/bookings', summary: 'Create a time-limited seat hold (row-locked slot).', access: 'traveler', source: 'routes/bookings.py', request: holdRequestNote },
      { method: 'GET', path: '/api/bookings', summary: 'Bookings of the signed-in traveler.', access: 'session', source: 'routes/bookings.py' },
      { method: 'POST', path: '/api/bookings/{booking_id}/cancel', summary: 'Cancel an unpaid booking.', access: 'traveler', source: 'routes/bookings.py' },
      { method: 'POST', path: '/api/bookings/{booking_id}/checkout', summary: 'Start a VNPay or MoMo checkout.', access: 'traveler', source: 'routes/bookings.py' },
      { method: 'GET', path: '/api/bookings/{booking_id}/history', summary: 'Status-change history.', access: 'session', source: 'routes/bookings.py' },
      { method: 'GET', path: '/api/payments/status', summary: 'Gateway readiness.', access: 'public', source: 'routes/bookings.py' },
      { method: 'GET', path: '/api/provider/me/bookings', summary: 'Booking requests addressed to the provider.', access: 'provider', source: 'routes/bookings.py' },
      { method: 'POST', path: '/api/provider/me/bookings/{booking_id}/decision', summary: 'Accept or reject a request.', access: 'provider', source: 'routes/bookings.py' },
      { method: 'POST', path: '/api/provider/me/bookings/{booking_id}/cancellation-decision', summary: 'Decide a cancellation request.', access: 'provider', source: 'routes/bookings.py' },
    ],
  },
  {
    id: 'provider',
    title: 'Provider portal',
    endpoints: [
      { method: 'GET', path: '/api/provider/me', summary: 'Provider profile.', access: 'provider', source: 'routes/provider.py' },
      { method: 'GET', path: '/api/provider/experiences', summary: 'Experiences and slots managed by the provider.', access: 'provider', source: 'routes/provider.py' },
      { method: 'POST', path: '/api/provider/experiences', summary: 'Create an experience draft.', access: 'provider', source: 'routes/provider.py' },
      { method: 'PATCH', path: '/api/provider/experiences/{experience_id}', summary: 'Update an experience.', access: 'provider', source: 'routes/provider.py' },
      { method: 'DELETE', path: '/api/provider/experiences/{experience_id}', summary: 'Hide an experience.', access: 'provider', source: 'routes/provider.py' },
      { method: 'POST', path: '/api/provider/experiences/{experience_id}/slots', summary: 'Open a new slot.', access: 'provider', source: 'routes/provider.py' },
      { method: 'PATCH', path: '/api/provider/slots/{slot_id}', summary: 'Update capacity or status; uses expected_version for optimistic locking.', access: 'provider', source: 'routes/provider.py' },
      { method: 'GET', path: '/api/provider/pois', summary: 'POIs owned by the provider.', access: 'provider', source: 'routes/provider.py' },
      { method: 'POST', path: '/api/provider/pois', summary: 'Register a POI.', access: 'provider', source: 'routes/provider.py' },
      { method: 'PATCH', path: '/api/provider/pois/{poi_id}', summary: 'Update a POI.', access: 'provider', source: 'routes/provider.py' },
      { method: 'GET', path: '/api/provider/evidence', summary: 'Submitted evidence.', access: 'provider', source: 'routes/provider.py' },
      { method: 'POST', path: '/api/provider/evidence', summary: 'Submit evidence for a POI, experience or slot.', access: 'provider', source: 'routes/provider.py' },
      { method: 'GET', path: '/api/provider/audit', summary: 'Provider audit log.', access: 'provider', source: 'routes/provider.py' },
    ],
  },
  {
    id: 'admin',
    title: 'Admin portal',
    endpoints: [
      { method: 'GET', path: '/api/admin/dashboard', summary: 'Counts and moderation queue size.', access: 'admin', source: 'routes/admin.py' },
      { method: 'GET', path: '/api/admin/users', summary: 'Users.', access: 'admin', source: 'routes/admin.py' },
      { method: 'PATCH', path: '/api/admin/users/{user_id}', summary: 'Change role or active flag.', access: 'admin', source: 'routes/admin.py' },
      { method: 'GET', path: '/api/admin/providers', summary: 'Providers.', access: 'admin', source: 'routes/admin.py' },
      { method: 'POST', path: '/api/admin/providers', summary: 'Create a provider.', access: 'admin', source: 'routes/admin.py' },
      { method: 'GET', path: '/api/admin/moderation', summary: 'Moderation queue (POI, experience, evidence).', access: 'admin', source: 'routes/admin.py' },
      { method: 'PATCH', path: '/api/admin/moderation/{entity_type}/{entity_id}', summary: 'Verify, reject or hide an entity.', access: 'admin', source: 'routes/admin.py' },
      { method: 'GET', path: '/api/admin/duplicates/pois', summary: 'Suspected duplicate POIs.', access: 'admin', source: 'routes/admin.py' },
      { method: 'POST', path: '/api/admin/duplicates/pois/merge', summary: 'Merge two POIs.', access: 'admin', source: 'routes/admin.py' },
      { method: 'GET', path: '/api/admin/place-imports', summary: 'Place import batches (staging).', access: 'admin', source: 'routes/admin.py' },
      { method: 'GET', path: '/api/admin/place-imports/{batch_id}/candidates', summary: 'Candidates in a batch.', access: 'admin', source: 'routes/admin.py' },
      { method: 'POST', path: '/api/admin/place-imports/{batch_id}/candidates/{candidate_id}/promote', summary: 'Promote a staged candidate into the catalog.', access: 'admin', source: 'routes/admin.py' },
      { method: 'GET', path: '/api/admin/integrations', summary: 'Integration configuration status.', access: 'admin', source: 'routes/admin.py' },
      { method: 'PUT', path: '/api/admin/integrations/{service}', summary: 'Store integration settings (encrypted at rest).', access: 'admin', source: 'routes/admin.py' },
      { method: 'POST', path: '/api/admin/integrations/{service}/test', summary: 'Test an integration.', access: 'admin', source: 'routes/admin.py' },
      { method: 'GET', path: '/api/admin/audit', summary: 'System audit log.', access: 'admin', source: 'routes/admin.py' },
      { method: 'GET', path: '/api/admin/ai/targets', summary: 'Targets for the admin AI tools.', access: 'admin', source: 'routes/admin.py' },
    ],
  },
  {
    id: 'ops',
    title: 'Operations & bot',
    endpoints: [
      { method: 'GET', path: '/api/ops/status', summary: 'Outbox, SMTP and worker overview.', access: 'admin', source: 'routes/ops.py' },
      { method: 'GET', path: '/api/ops/jobs', summary: 'Background jobs.', access: 'admin', source: 'routes/ops.py' },
      { method: 'GET', path: '/api/ops/events', summary: 'Business events.', access: 'admin', source: 'routes/ops.py' },
      { method: 'GET', path: '/api/ops/notifications', summary: 'Notification counts by status.', access: 'admin', source: 'routes/ops.py' },
      { method: 'GET', path: '/api/admin/bot/config', summary: 'Chat-bot configuration.', access: 'admin', source: 'routes/admin_bot.py' },
      { method: 'POST', path: '/api/admin/system/settings', summary: 'Update system settings.', access: 'admin', source: 'routes/admin_bot.py' },
      { method: 'GET', path: '/api/models-3d/calibration', summary: '3D landmark calibration data (reading is open; writing a calibration requires admin).', access: 'public', source: 'routes/models_3d.py' },
    ],
  },
]

export const ALL_ENDPOINTS = API_GROUPS.flatMap((g) => g.endpoints.map((e) => ({ ...e, group: g.title })))
