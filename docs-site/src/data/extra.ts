import type { Status } from './site'

/* Demo walkthrough: order and content follow DEMO_SCRIPT.md (5–7 minute live demo). */
export const DEMO_STEPS = [
  { time: '0:00–0:45', title: 'Introduction', action: 'Open the home page.', point: 'A POI being open does not mean the experience is running when you arrive. Goal: find the right experience at the right time.' },
  { time: '0:45–2:00', title: 'Digital Twin', action: 'Move the mouse over the 3D city, hover POI pins, toggle night and day.', point: 'A Three.js city with a river, buildings and radar-pulse pins; the camera shifts with the pointer.' },
  { time: '2:00–3:30', title: 'Explore', action: 'Open /explore, pick a craft tag, adjust budget and group size.', point: 'Experience cards with a tilt effect; the CartoDB map flies to the selected location.' },
  { time: '3:30–4:45', title: 'Planning', action: 'Open /planner: tomorrow 09:00–16:00, 2 people, 1,200,000 VND, food and craft.', point: 'A live preview recomputes hours, per-person cost and transport as the form changes.' },
  { time: '4:45–5:45', title: 'Itinerary & reasons', action: 'Generate the itinerary and open /itinerary/:id.', point: 'KPI cards, a timeline, travel time between stops, reason codes, and stops flagged tentative when confirmation is needed.' },
  { time: '5:45–6:30', title: 'Provider portal & close', action: 'Open the provider workspace.', point: 'Providers manage slots; the platform serves both travelers and local craft businesses.' },
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
  { label: 'Technical innovation', text: 'Slot-aware planning, schema-validated LLM output, local E5 retrieval, an XGBoost tie-break ranker, event-driven replanning and explicit data status labels.' },
  { label: 'User impact', text: 'Travelers get plans that respect time and budget; local providers get a way to publish real capacity and receive guests at the right time.' },
]

export interface RoadItem { text: string; status: Status; note?: string }
/* From the README roadmap (Phase 0–11); statuses adjusted to what the code shows. */
export const ROADMAP: RoadItem[] = [
  { text: 'Phase 0: foundation architecture, PostGIS schema, sample data', status: 'implemented' },
  { text: 'Phase 1: explore UI, search filters, Leaflet map', status: 'implemented' },
  { text: 'Phase 2: heuristic planner and itinerary timeline', status: 'implemented' },
  { text: 'Phase 2.5: Three.js 3D city, tilt cards, CartoDB map, offline fallback engine', status: 'implemented' },
  { text: 'Phase 3: local multilingual E5 semantic search', status: 'implemented', note: 'Needs a locally installed model.' },
  { text: 'Phase 4: dynamic replanning and itinerary versioning', status: 'implemented', note: 'Versions can be listed; no rollback code found.' },
  { text: 'Phase 5: provider portal and signed two-step slot assistant', status: 'implemented' },
  { text: 'Phase 6: XGBoost ranker', status: 'implemented', note: 'Training dataset is unverified; artifacts are not committed.' },
  { text: 'Phase 7: flood-risk model and weather/AQI advisory', status: 'implemented', note: 'No flood bundle committed; not used in routing.' },
  { text: 'Phase 8: admin portal, moderation, duplicate merge, audit logs', status: 'implemented' },
  { text: 'Phase 9: AI Concierge chat and compare view', status: 'implemented' },
  { text: 'Phase 10: Goong routing, seat holds, VNPay and MoMo, encrypted integrations, outbox, VI/EN', status: 'implemented' },
  { text: 'Phase 11: IoT flood sensor data, PWA with offline tickets, voice concierge', status: 'planned', note: 'Unchecked in the README; no code found.' },
]

/* Planning pipeline. Steps map to the real code paths; the last two are described in README. */
export const PIPELINE = [
  { id: 'intent', title: 'User intent', where: 'Chat or planner form', text: 'A free-text message or a form produces a window, group size, budget, travel mode and intent weights.' },
  { id: 'extract', title: 'Constraint extraction', where: 'CONVERSATION_PARSER, chat.py', text: 'An LLM (or the local fallback) fills a structured constraints object. Output is schema-validated; invalid output is rejected.' },
  { id: 'retrieve', title: 'Candidate retrieval', where: 'catalog.py, experience_service.py', text: 'Experiences and their slots are read from PostgreSQL. Keyword search or E5 semantic ranking can narrow the set.' },
  { id: 'feasible', title: 'Availability validation', where: 'planner_service.py, availability_service.py', text: 'Candidates that exceed the remaining budget, fall outside the window or cannot finish before the return deadline are skipped; locked experiences are kept. If a slot’s capacity is not reported, the plan is marked tentative. Each stop also gets a data status (verified, simulated or stale) from its evidence and slot freshness.' },
  { id: 'travel', title: 'Travel time', where: 'routing_service.py', text: 'Distance, duration and geometry per leg from Goong (mock in tests). ETAs carry a source and an expiry.' },
  { id: 'rank', title: 'Tie-break ranking', where: 'ml_ranker_service.py', text: 'Among candidates at the earliest feasible time, the XGBoost ranker orders ties; without it the planner uses intent fit.' },
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

/* ML */
export const FEATURES: [string, string][] = [
  ['tag_jaccard', 'Overlap between the user’s intent tags and the experience tags'],
  ['intent_match', 'Match against the main intent'],
  ['is_hands_on', 'Hands-on or workshop activity'],
  ['is_indoor', 'Takes place indoors'],
  ['duration_ratio', 'Duration relative to available time'],
  ['eta_ratio', 'Travel time relative to activity duration'],
  ['total_time_ratio', 'Share of remaining time consumed'],
  ['group_cost_ratio', 'Group cost relative to remaining budget'],
  ['rain_mm', 'Rainfall at the time'],
  ['outdoor_rain_mm', 'Rainfall applied to outdoor activities'],
  ['temperature_c', 'Temperature'],
  ['pm2_5', 'PM2.5'],
  ['european_aqi', 'European AQI'],
]

export const PROMPTS = [
  ['CONVERSATION_PARSER', 'Extract trip constraints from chat'],
  ['EXPERIENCE_TAGGER', 'Tag experiences (hands-on, indoor, intents)'],
  ['INTENT_SIMILARITY', 'Similarity of two experiences'],
  ['REPLAN_ADVISOR', 'Pick and justify replacements from solver candidates'],
  ['XAI_EXPLANATION', 'Explain a decision in Vietnamese'],
  ['PROVIDER_ASSISTANT', 'Slot changes by natural language, two-step confirm'],
  ['FEEDBACK_LABELER', 'Grade feedback 0–3 for training data'],
  ['WEATHER_AQI_ADVISOR', 'Weather and AQI impact on outdoor stops'],
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
