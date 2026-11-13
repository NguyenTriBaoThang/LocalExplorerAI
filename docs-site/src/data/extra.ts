import type { Status } from './site'

/* Demo walkthrough: order and content follow DEMO_SCRIPT.md (5–7 minute live demo). */
export const DEMO_STEPS = [
  { time: '0:00–0:45', title: 'Introduction', action: 'Open the home page.', point: 'A POI being open does not mean the experience is running when you arrive. Goal: find the right experience at the right time.' },
  { time: '0:45–2:00', title: 'Digital Twin', action: 'Move the mouse over the 3D city, hover POI pins, toggle night and day.', point: 'A Three.js city with a river, buildings and radar-pulse pins; the camera shifts with the pointer.' },
  { time: '2:00–3:30', title: 'Explore', action: 'Open /explore, pick a craft tag, adjust budget and group size.', point: 'Experience cards with a tilt effect; the CartoDB map flies to the selected location.' },
  { time: '3:30–4:45', title: 'Planning', action: 'Open /planner: tomorrow 09:00–16:00, 2 people, 1,200,000 VND, food and craft.', point: 'A live preview recomputes hours, per-person cost and transport as the form changes.' },
  { time: '4:45–5:45', title: 'Itinerary & reasons', action: 'Generate the itinerary and open /itinerary/:id.', point: 'KPI cards, a timeline, travel time between stops, reason codes, and stops flagged tentative when confirmation is needed.' },
  { time: '5:45–6:30', title: 'Provider & Operator Portal', action: 'Open the partner workspace.', point: 'Providers manage slots; tour operators generate quotes and configure rate cards.' },
]

export const GALLERY = [
  { file: 'home_3d.webp', title: '3D Saigon cityscape', feature: 'Digital Twin', text: 'WebGL city hero with buildings, river and POI pins, plus night and day themes.' },
  { file: 'explore.webp', title: 'Explore', feature: 'Search & filters', text: 'Experience cards with filters for intent, budget, group size and distance.' },
  { file: 'planner.webp', title: 'Planner wizard', feature: 'Slot-aware planning', text: 'Three-step form with a live day preview.' },
  { file: 'map_3d.webp', title: '3D vector map', feature: 'Digital Twin', text: 'Map view with radar-style pins.' },
  { file: 'provider.webp', title: 'Provider workspace', feature: 'Provider portal', text: 'Slot and booking management for local partners.' },
]

/* Project story: from COMPETITION_SUBMISSION.md. */
export const STORY = [
  { label: 'Problem', text: 'Map apps show static places and generic opening hours. A pottery workshop or cooking class does not run all day, so visitors arrive to a closed session or a full class.' },
  { label: 'Existing limitation', text: 'Using a general chatbot for itineraries tends to produce unverifiable plans: invented addresses, wrong travel times and inaccurate prices.' },
  { label: 'Approach', text: 'Separate place, activity and session (POI, Experience, Slot). Let a deterministic planner own feasibility, and use language and ML models only where they are checked.' },
  { label: 'Technical innovation', text: 'Slot-aware planning, schema-validated LLM output, local E5 retrieval, an XGBoost tie-break ranker, event-driven replanning, B2B tour pricing optimizer, and explicit data status labels.' },
  { label: 'User impact', text: 'Travelers get plans that respect time and budget; local providers publish real capacity; tour operators generate margin-protected quotes.' },
]

export interface RoadItem { text: string; status: Status; note?: string }
/* Full project roadmap (Phase 0–15); audited against actual codebase. */
export const ROADMAP: RoadItem[] = [
  { text: 'Phase 0: foundation architecture, PostGIS schema, sample data', status: 'implemented' },
  { text: 'Phase 1: explore UI, search filters, Leaflet map', status: 'implemented' },
  { text: 'Phase 2: heuristic planner and itinerary timeline', status: 'implemented' },
  { text: 'Phase 2.5: Three.js 3D city, tilt cards, CartoDB map, offline fallback engine', status: 'implemented' },
  { text: 'Phase 3: local multilingual E5 semantic search', status: 'implemented', note: 'Weights downloadable via scripts/download_e5_model.py.' },
  { text: 'Phase 4: dynamic replanning and itinerary versioning & rollback', status: 'implemented', note: 'Rollback verified at POST /api/trips/{id}/restore/{version}.' },
  { text: 'Phase 5: provider portal and signed two-step slot assistant', status: 'implemented' },
  { text: 'Phase 6: candidate ranker (baseline & XGBoost)', status: 'implemented', note: 'rule-baseline-v1 active default; XGBoost pilot requires ALLOW_UNVERIFIED_RANKER=true.' },
  { text: 'Phase 7: flood-risk model and weather/AQI advisory', status: 'implemented', note: 'Advisory active; flood model is an offline research prototype.' },
  { text: 'Phase 8: admin portal, moderation, duplicate merge, audit logs', status: 'implemented' },
  { text: 'Phase 9: AI Concierge chat, streaming trips, compare view', status: 'implemented' },
  { text: 'Phase 10: Goong routing, seat holds, VNPay and MoMo, encrypted integrations, outbox, VI/EN', status: 'implemented' },
  { text: 'Phase 11: IoT flood sensor data, PWA with offline tickets, voice concierge', status: 'planned', note: 'Active research track.' },
  { text: 'Phase 12: B2B Tour Operator Quoting & Pricing Optimizer', status: 'implemented', note: 'Rate cards, cost rollups, win-rate model, and margin protection guard.' },
  { text: 'Phase 13: Prompt Catalog v3.2.0 (20 specialized workflows)', status: 'implemented', note: 'Strict Pydantic structured output validation with heuristic fallback.' },
  { text: 'Phase 14: Partner & Operator Multi-Tenant Portal (apps/portal)', status: 'implemented', note: 'React 18 + Tailwind workspace for providers, tour operators, and admins.' },
  { text: 'Phase 15: Meshy 3D generative model worker & landmark stories', status: 'implemented', note: 'Background task polling, GLB caching, and audio narration streaming.' },
]

/* Planning pipeline. Steps map to the real code paths. */
export const PIPELINE = [
  { id: 'intent', title: 'User intent', where: 'Chat or planner form', text: 'A free-text message or a form produces a window, group size, budget, travel mode and intent weights.' },
  { id: 'extract', title: 'Constraint extraction', where: 'CONVERSATION_PARSER, chat.py', text: 'An LLM (or the local fallback) fills a structured constraints object. Output is schema-validated; invalid output is rejected.' },
  { id: 'retrieve', title: 'Candidate retrieval', where: 'catalog.py, experience_service.py', text: 'Experiences and their slots are read from PostgreSQL. Keyword search or E5 semantic ranking can narrow the set.' },
  { id: 'feasible', title: 'Availability validation', where: 'planner_service.py, availability_service.py', text: 'Candidates that exceed the remaining budget, fall outside the window or cannot finish before the return deadline are skipped; locked experiences are preserved. If a slot’s capacity is not reported, the plan is marked tentative.' },
  { id: 'travel', title: 'Travel time', where: 'routing_service.py', text: 'Distance, duration and geometry per leg from Goong (mock in tests). ETAs carry a source, calculation time, and an expiry.' },
  { id: 'rank', title: 'Tie-break ranking', where: 'ml_ranker_service.py', text: 'Among candidates at the earliest feasible time, candidate fit scores order ties (rule-baseline-v1 active default; XGBoost pilot when enabled).' },
  { id: 'build', title: 'Itinerary construction', where: 'planner_engine.py, planner_service.py', text: 'At each step the earliest feasible slot is scheduled; the return deadline is checked including the last leg.' },
  { id: 'final', title: 'Final itinerary', where: 'PlanResponse', text: 'Stops, routes, a feasibility status (feasible or tentative), reason codes and uncertainty notes.' },
]

/* Illustrative demo data for the client-side concierge demo. */
export const CHAT_EXAMPLES = [
  {
    id: 'afternoon', label: 'Afternoon of culture',
    prompt: 'Tôi có một buổi chiều ở Sài Gòn, thích văn hóa và cà phê, ngân sách khoảng 800k.',
    reply: 'Mình ghi nhận: khoảng 4 giờ, ngân sách 800.000đ, ưu tiên văn hóa và cà phê. Bạn đi mấy người, và bằng phương tiện gì?',
    constraints: [['Duration', '4h'], ['Budget', '800,000 VND'], ['Location', 'District 1'], ['Interest', 'Culture'], ['Interest', 'Coffee'], ['Missing', 'Group size, transport']],
  },
  {
    id: 'craft', label: 'Craft day, two people',
    prompt: 'Nhóm mình 2 người, đi từ 08:30 đến 16:30, thích làm gốm và ẩm thực, ngân sách 1 triệu bằng xe máy.',
    reply: 'Đã đủ thông tin cơ bản. Mình sẽ tìm các ca còn chỗ trong khung 08:30–16:30 và ghép lịch trình.',
    constraints: [['Window', '08:30 – 16:30'], ['Group', '2 people'], ['Budget', '1,000,000 VND'], ['Transport', 'Motorcycle'], ['Interest', 'Craft'], ['Interest', 'Food']],
  },
  {
    id: 'rain', label: 'Rainy day, indoor',
    prompt: 'Hôm nay trời mưa, mình đi 3 người, 6 tiếng ở Quận 1, muốn hoạt động trong nhà, tầm 1 triệu.',
    reply: 'Mình sẽ ưu tiên hoạt động trong nhà. Bạn muốn xuất phát lúc mấy giờ?',
    constraints: [['Duration', '6h'], ['Group', '3 people'], ['Budget', '1,000,000 VND'], ['Location', 'District 1'], ['Preference', 'Indoor'], ['Missing', 'Start time']],
  },
]

/* Replanning demo: illustrative sample data, not backend output. */
export const REPLAN_BEFORE = [
  { time: '09:00', name: 'Coffee tasting', kind: 'Coffee', slot: 'Slot A · 6/10 left' },
  { time: '10:30', name: 'City museum', kind: 'Museum', slot: 'Slot B · open' },
  { time: '13:00', name: 'Lacquer workshop', kind: 'Local workshop', slot: 'Slot C · 3/8 left' },
  { time: '15:00', name: 'Riverside walk', kind: 'Riverside', slot: 'Slot D · open' },
]
export const REPLAN_AFTER = { time: '13:00', name: 'Ceramics studio', kind: 'Alternative experience', slot: 'Slot E · 4/6 left' }

/* Candidate ranker features (15 features in ranker-features-v2). */
export const FEATURES: [string, string][] = [
  ['tag_jaccard', 'Jaccard similarity between user intent tags and experience tags'],
  ['intent_match', 'Direct match score against primary user intent'],
  ['is_hands_on', 'Whether the activity is hands-on / workshop'],
  ['is_indoor', 'Whether the activity takes place indoors'],
  ['duration_ratio', 'Experience duration relative to available time window'],
  ['eta_ratio', 'Travel duration relative to experience duration'],
  ['total_time_ratio', 'Share of remaining schedule window consumed'],
  ['group_cost_ratio', 'Total group cost relative to remaining budget'],
  ['rain_mm', 'Predicted precipitation at scheduled stop time'],
  ['outdoor_rain_mm', 'Rainfall penalty applied specifically to outdoor activities'],
  ['temperature_c', 'Ambient temperature (°C) at scheduled stop time'],
  ['pm2_5', 'Predicted PM2.5 air pollution level'],
  ['european_aqi', 'European Air Quality Index rating'],
  ['is_hands_on_known', 'Flag indicating whether hands-on attribute is verified (prevents missing-data skew)'],
  ['is_indoor_known', 'Flag indicating whether indoor attribute is verified (prevents missing-data skew)'],
]

/* B2B Quote Win Model features (18 features in quote-win-features-v1). */
export const QUOTE_WIN_FEATURES: [string, string][] = [
  ['pax', 'Number of guests in the tour group'],
  ['days', 'Total duration of the tour in days'],
  ['lead_days', 'Advance booking notice before tour departure'],
  ['seg_family / corporate / school', 'Target client customer segment one-hot flags'],
  ['dest_cu_chi / mekong / can_gio / vung_tau / city', 'Destination region category one-hot flags'],
  ['weekend', 'Flag indicating whether tour dates overlap Saturday/Sunday'],
  ['holiday', 'Flag indicating Vietnamese national public holidays'],
  ['tet', 'Flag indicating Lunar New Year peak holiday window'],
  ['month', 'Calendar month of tour departure (1–12)'],
  ['competitor_price_index', 'Normalized competitor market price index at quotation time'],
  ['rain_prob', 'Historical / forecast probability of rain during tour window'],
  ['response_time_h', 'Hours elapsed between client inquiry and operator quote dispatch'],
  ['cost_per_pax', 'Base supplier cost per guest in VND'],
  ['price_ratio_cost', 'Quoted price divided by cost per guest (monotone negative constraint)'],
  ['price_ratio_comp', 'Quoted price relative to competitor price index (monotone negative constraint)'],
]

/* Prompt Catalog v3.2.0: 20 specialized workflows. */
export const PROMPTS = [
  ['CONVERSATION_PARSER', 'Extract structured trip constraints from free-form chat (time, budget, group, intents)'],
  ['EXPERIENCE_TAGGER', 'Categorize and tag experiences (hands-on, indoor/outdoor, thematic intents)'],
  ['INTENT_SIMILARITY', 'Compute semantic affinity and topical similarity between two experiences'],
  ['REPLAN_ADVISOR', 'Recommend and justify optimal replacements from solver-filtered candidate pools'],
  ['XAI_EXPLANATION', 'Generate natural-language explanations in Vietnamese for algorithmic recommendations'],
  ['PROVIDER_ASSISTANT', 'Process natural-language slot management requests with two-step cryptographic tokens'],
  ['FEEDBACK_LABELER', 'Grade traveler feedback and ratings on a standardized 0–3 quality rubric for ML data'],
  ['WEATHER_AQI_ADVISOR', 'Evaluate rain, heat, and PM2.5 air pollution hazards for outdoor itinerary stops'],
  ['CHAT_INTENT_ROUTER', 'Classify conversational turns into discovery, planning, modification, or support intents'],
  ['TRAVEL_ASSISTANT', 'Interactive conversational local concierge providing cultural and navigational context'],
  ['TRIP_PARSER', 'Extract multi-day complex itinerary preferences from unstructured travel briefs'],
  ['TRIP_PLANNER', 'Draft comprehensive narrative itinerary outlines for travel planning workflows'],
  ['TRIP_FOLLOWUP', 'Generate targeted clarification questions when essential constraints are missing'],
  ['TRIP_GROUP_REVIEW', 'Synthesize and reconcile conflicting preferences from multi-traveler groups'],
  ['ITINERARY_RANKER', 'Perform semantic and contextual re-ranking across candidate trip sequences'],
  ['RATE_CARD_EXTRACTOR', 'Extract structured service rate cards and tier pricing from partner contracts'],
  ['INVOICE_EXTRACTOR', 'Parse line items and totals from supplier invoices for automated billing reconciliation'],
  ['QUOTE_REQUEST_PARSER', 'Parse corporate RFP requirements and group parameters into structured quote models'],
  ['QUOTE_EXPLAINER', 'Draft polished, value-oriented quotation proposals for prospective clients'],
  ['MARGIN_RESCUE_EXPLAINER', 'Provide business rationales and alternatives when a requested price breaches the margin floor'],
]

/* Digital twin: schematic coordinates in a 0–1000 × 0–600 space. Illustrative, not surveyed. */
export const TWIN_POIS = [
  { id: 'p1', name: 'Notre-Dame Cathedral', kind: 'Landmark', x: 360, y: 200, note: 'Landmark that has a GLB model in the product’s 3D viewer.' },
  { id: 'p2', name: 'Ben Thanh area', kind: 'Market', x: 430, y: 300, note: 'Dense food and coffee cluster.' },
  { id: 'p3', name: 'Riverside promenade', kind: 'Riverside', x: 640, y: 330, note: 'Outdoor; sensitive to rain.' },
  { id: 'p4', name: 'Craft studio', kind: 'Workshop', x: 250, y: 360, note: 'Hands-on, indoor, slot-based.' },
  { id: 'p5', name: 'City museum', kind: 'Museum', x: 520, y: 150, note: 'Indoor; opening hours and slots differ.' },
]
export const TWIN_EXPERIENCES = [
  { id: 'e1', poi: 'p4', name: 'Pottery session', x: 288, y: 336, note: 'Experience hosted at the craft studio.' },
  { id: 'e2', poi: 'p2', name: 'Coffee tasting', x: 472, y: 280, note: 'Experience hosted near Ben Thanh.' },
  { id: 'e3', poi: 'p5', name: 'Guided tour', x: 566, y: 126, note: 'Experience hosted at the museum.' },
]
