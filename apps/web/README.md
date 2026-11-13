# Local Explorer AI — Traveler Web Application (`apps/web`)

> **Public Traveler Frontend Application**  
> **Framework:** React 18.3 · TypeScript 5.6 · Vite 6 · Three.js · Leaflet · Tailwind CSS  
> **Port:** `8080` (Proxies `/api` to backend `http://127.0.0.1:8000`)

---

## 1. Overview & Architectural Role

`apps/web` is the primary B2C single-page application (SPA) for Local Explorer AI. It delivers a modern, human-centered travel exploration experience that combines:
- **Spatial Exploration:** A 3D WebGL Digital Twin of Saigon and interactive 3D landmark viewer (GLB).
- **Conversational Intelligence:** An AI Concierge chat that understands natural-language travel requests in Vietnamese and extracts structured itinerary constraints.
- **Slot-Aware Trip Planning:** A deterministic heuristic planner that balances time, budget, opening hours, capacity, and route travel times.
- **Offline & PWA Readiness:** Service Worker caching of the application shell and catalog for offline browsing, coupled with client-side heuristic chat fallbacks.

---

## 2. Technology Stack & Key Dependencies

| Technology | Version | Purpose |
|---|---|---|
| **React** | `18.3.1` | Declarative component UI and concurrent rendering |
| **TypeScript** | `5.6.3` | Type safety and domain contracts |
| **Vite** | `6.0.5` | Fast HMR dev server and optimized Rollup production builds |
| **Three.js** | `0.162.0` | 3D WebGL city rendering, lighting, materials, and GLB loading |
| **Leaflet & React-Leaflet** | `1.9.4` / `4.2.1` | 2D/2.5D interactive maps with custom marker pulses and polylines |
| **Lucide React** | `1.49.0` | Accessible, modern iconography |
| **Tailwind CSS** | `3.4.16` | Utility classes and design tokens |
| **Axios** | `1.7.9` | HTTP client with request ID propagation and error handling |

---

## 3. Routes & Page Catalog

| Path | Component | Description | Access |
|---|---|---|---|
| `/` | `HomePage.tsx` | Landing page featuring Three.js 3D Saigon Cityscape, search bar, and curated categories | Public |
| `/explore` | `ExplorePage.tsx` | Category browsing with 3D TiltCards and quick-filter chips | Public |
| `/places` | `PlacesPage.tsx` | Verified Saigon POI catalog with search, tags, and district filtering | Public |
| `/places/:id` | `PlaceDetailPage.tsx` | Rich place profile, operating hours, experience cards, and directions link | Public |
| `/planner` | `PlannerPage.tsx` | Multi-step smart route planner with feasibility constraints and live map preview | Public |
| `/itinerary/:id` | `ItineraryPage.tsx` | Detailed trip timeline, KPI cards, road segments, and booking hold triggers | Public |
| `/compare` | `ComparePage.tsx` | Side-by-side comparison of multiple itinerary versions | Public |
| `/chat` | `TripChatPage.tsx` | Multi-turn conversational AI Concierge with streaming SSE events | Public |
| `/history` | `TripHistoryPage.tsx` | User trip history and saved itinerary versions | Authenticated |
| `/map-3d` | `Map3DPage.tsx` | 3D Digital Twin Landmark Viewer with GLB model inspection | Public |
| `/guides` | `GuidesPage.tsx` | Local neighborhood travel guides and cultural tips | Public |
| `/provider` | `ProviderPage.tsx` | Information page for local cultural experience providers | Public |
| `/about` | `AboutPage.tsx` | Platform mission, data architecture, and verification manifesto | Public |
| `/login` | `LoginPage.tsx` | Traveler authentication with password and Google OAuth PKCE | Public |
| `/register` | `RegisterPage.tsx` | Account registration with password strength meter | Public |

---

## 4. Key Component Architecture

```text
apps/web/src/
├── api/                  # Axios HTTP client and API endpoints
├── components/
│   ├── 3d/               # Three.js CityHero3D, TiltCard3D, Landmark guides
│   ├── content/          # Content layouts, badges, and cards
│   ├── experience/       # Experience cards and pricing chips
│   ├── journey/          # Itinerary suggestions and journey bar
│   ├── map/              # Leaflet MapAdapter, tile presets, route overlays
│   └── trip/             # ChatPanel, Timeline, LocationConditions, Rail
├── layouts/              # AppLayout (Header, Navigation drawer, Footer, MapBot widget)
├── pages/                # Route views listed in table above
├── i18n.ts               # Bilingual VI/EN translation dictionary
├── theme.ts              # Theme management (Warm Light / Emerald Dark)
├── main.tsx              # Application entry point and session bootstrapper
└── styles.css            # Base stylesheet, CSS variables, and design tokens
```

---

## 5. Core Workflows & Data Flow

### 5.1. AI Chat to Itinerary Planning
1. **Chat Interaction:** `ChatPanel.tsx` communicates with `/api/trips/stream` via Server-Sent Events (SSE).
2. **Intent Parsing:** If the user supplies incomplete information, the backend returns a `clarification` event, rendered as interactive response chips.
3. **Plan Generation:** Once constraints are complete, the backend solves a feasible plan and streams a `plan_created` event with itinerary ID.
4. **State Transition:** The web app seamlessly mounts the resulting itinerary into the Laser Timeline view without losing chat context.

### 5.2. Map Visualization (`MapAdapter.tsx`)
- Supports dynamic layer switching: **Bản đồ HD** (CartoDB Voyager), **Google Maps** (or satellite hybrid), and **Bản đồ tối** (CartoDB Dark Matter).
- Renders turn-by-turn road routes decoded from Goong Directions polylines.
- Highlights active stops and opening hour indicators directly on map popups.

### 5.3. 3D WebGL Digital Twin (`CityHero3D.tsx`)
- Built on Three.js: procedural buildings, glowing windows, specular water reflections for the Saigon River, and animated radar markers over District 1 landmarks.
- Hardware-accelerated with fallback to static illustration for low-power mobile GPUs.

---

## 6. Authentication & Session Security

- **Session Handling:** Handled via HTTP-only cookies (`le_at` access token, `le_rt` refresh token). The frontend JavaScript never directly handles raw tokens, mitigating XSS risks.
- **CSRF Protection:** Browser requests enforce `SameSite=Lax` cookies with strict origin validation headers.
- **Cold Boot:** `main.tsx` performs an initial session check against `/api/auth/session` with a 6-second timeout, falling back gracefully to unauthenticated state.

---

## 7. Local Development & Verification

### Prerequisites
- Node.js `20.x` or higher
- npm `10.x` or higher

### Commands
```bash
# Navigate to web app
cd apps/web

# Install dependencies
npm ci

# Run development server (runs on port 8080)
npm run dev

# Run TypeScript typecheck & linter
npm run lint

# Run unit tests (18 tests covering trip state, road routes, SSE parsing)
npm run test

# Production build
npm run build

# Preview production build locally
npm run preview
```

### Environment Configuration
The frontend uses standard Vite configuration in `vite.config.ts`. By default, it proxies `/api` and `/health` requests to `http://127.0.0.1:8000`. To override:
```bash
API_PROXY_TARGET=http://127.0.0.1:8000 npm run dev
```
