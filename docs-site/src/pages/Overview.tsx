import { ArrowRight, Github, CheckCircle2, ShieldCheck, Database, Cpu, Layers, Terminal } from 'lucide-react'
import { CAPABILITIES } from '../data/capabilities'
import { REPO_URL, SRC } from '../data/site'
import { StatusBadge, Src, Callout } from '../components/ui'

function HeroViz() {
  const pois: [number, number][] = [[90, 60], [210, 110], [310, 70], [150, 200], [280, 220], [60, 170]]
  const route = 'M90 60 L210 110 L280 220 L150 200 L60 170'
  return (
    <svg className="hero-viz" viewBox="0 0 400 280" role="img" aria-label="Schematic city grid with points of interest joined by a route">
      <defs>
        <pattern id="g" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="var(--line)" strokeWidth="1" /></pattern>
      </defs>
      <rect width="400" height="280" fill="url(#g)" />
      <path d="M-10 150 C90 120 140 190 230 160 S360 120 420 150" className="river" />
      <path d={route} className="route" />
      {pois.map(([x, y], i) => (
        <g key={i} transform={`translate(${x} ${y})`}>
          <circle r="12" className="pulse" style={{ animationDelay: `${i * 0.5}s` }} />
          <circle r="4.5" className="node" />
        </g>
      ))}
      <circle r="3" className="runner"><animateMotion dur="9s" repeatCount="indefinite" path={route} /></circle>
    </svg>
  )
}

export default function Overview() {
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow mono">Enterprise Technical Documentation · Ho Chi Minh City</p>
          <h1>LocalExplorerAI</h1>
          <p className="tagline">Explore Saigon. Plan smarter. Experience more.</p>
          <p className="lead">Dual B2C & B2B GeoAI platform combining slot-level availability scheduling, deterministic heuristic itinerary planning, multilingual semantic search, ML pricing optimization, and 3D digital twins.</p>
          <div className="cta">
            <a className="btn primary" href="#/architecture">Explore Architecture <ArrowRight size={16} aria-hidden /></a>
            <a className="btn" href="#/planning">Planning Engine <ArrowRight size={16} aria-hidden /></a>
            <a className="btn" href={REPO_URL} target="_blank" rel="noreferrer"><Github size={16} aria-hidden /> View on GitHub</a>
          </div>
        </div>
        <HeroViz />
      </section>

      {/* Project Snapshot Card */}
      <section className="page" style={{ paddingTop: 0 }}>
        <div className="card" style={{ borderLeft: '4px solid var(--cyan)', background: 'var(--panel2)' }}>
          <div className="card-head" style={{ marginBottom: 12 }}>
            <h2 style={{ margin: 0, fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: 8 }}>
              <ShieldCheck size={20} color="var(--cyan)" /> Verified Project Snapshot
            </h2>
            <span className="mono dim small">Commit: 3906c98 · Audited: 2026-11-13</span>
          </div>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
            <div>
              <p className="mono dim" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}><CheckCircle2 size={13} style={{ display: 'inline', verticalAlign: '-1px', color: 'var(--green)' }} /> Verified Test Suite</p>
              <p style={{ margin: 0, fontWeight: 600 }}>346 Backend Pytest (0 fail)<br /><span className="small dim">18 Web tests · Clean Vite build</span></p>
            </div>
            <div>
              <p className="mono dim" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}><Database size={13} style={{ display: 'inline', verticalAlign: '-1px', color: 'var(--cyan)' }} /> Database Schema</p>
              <p style={{ margin: 0, fontWeight: 600 }}>PostgreSQL 16 + PostGIS 3.4<br /><span className="small dim">30 Alembic revisions (0001–0030)</span></p>
            </div>
            <div>
              <p className="mono dim" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}><Cpu size={13} style={{ display: 'inline', verticalAlign: '-1px', color: 'var(--amber)' }} /> Active ML Models</p>
              <p style={{ margin: 0, fontWeight: 600 }}>rule-baseline-v1 (Ranker active)<br /><span className="small dim">quote-win-xgb (B2B +9.5% win pilot)</span></p>
            </div>
            <div>
              <p className="mono dim" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}><Layers size={13} style={{ display: 'inline', verticalAlign: '-1px', color: 'var(--blue)' }} /> System Catalogs</p>
              <p style={{ margin: 0, fontWeight: 600 }}>Prompt Catalog v3.2.0 (20 flows)<br /><span className="small dim">33 FastAPI route modules · 4-tier RBAC</span></p>
            </div>
          </div>
        </div>
      </section>

      <section className="page">
        <h2>What is LocalExplorerAI?</h2>
        <div className="two">
          <div>
            <p>Traditional travel platforms ask <em>“where can I go?”</em> and display static listings with generic opening hours. LocalExplorerAI solves a real operational problem: <em>what experiences are actually running and have open capacity right now that fit my time, budget, and travel constraints?</em></p>
            <p>A venue being open does not guarantee an activity is happening. A pottery workshop or lacquer class runs discrete sessions with limited seats. LocalExplorerAI decomposes travel into a 3-tier hierarchy: <strong>POI → Experience → Slot</strong>, and plans strictly over available slots.</p>
            <Callout title="Core Architectural Principle (Confirmed in Code)">
              Itinerary stops reference an <Src path="ExperienceSlot" />, not just a place. The deterministic planning engine evaluates hard temporal windows, return deadlines, transport legs via Goong, and budget caps. No probabilistic model or LLM is ever allowed to hallucinate feasibility. See <Src path={SRC.entities} />.
            </Callout>
          </div>
          <ol className="chain" aria-label="From place to itinerary">
            {[
              ['POI', 'Physical place with PostGIS coordinates and verification state'],
              ['Experience', 'Activity hosted at a POI with duration, price & tags'],
              ['Available Slot', 'Specific session with capacity and reported seat availability'],
              ['Feasible Itinerary', 'Ordered schedule with road route legs, budget checks & return deadline'],
            ].map(([a, b], i) => (
              <li key={a}><span className="mono">0{i + 1}</span><strong>{a}</strong><small>{b}</small></li>
            ))}
          </ol>
        </div>
      </section>

      {/* Target User Personas */}
      <section className="page">
        <h2>Target User Personas</h2>
        <div className="grid">
          <article className="card">
            <h3 style={{ color: 'var(--cyan)' }}>Independent Traveler</h3>
            <p>Discovers curated Saigon experiences, chats with the AI Concierge, generates slot-aware single/multi-day itineraries, previews 3D city landmarks, and secures row-locked seats with VNPay/MoMo.</p>
          </article>
          <article className="card">
            <h3 style={{ color: 'var(--green)' }}>Experience Provider</h3>
            <p>Local artisans, culinary hosts, and workshop operators who manage session capacities, publish real-time slot availability, approve booking requests, and use signed AI slot assistants.</p>
          </article>
          <article className="card">
            <h3 style={{ color: 'var(--amber)' }}>B2B Tour Operator</h3>
            <p>Inbound agencies and corporate travel planners managing contracted supplier rate cards, building custom group quotations, and optimizing pricing with XGBoost win-rate models and margin guardrails.</p>
          </article>
          <article className="card">
            <h3 style={{ color: 'var(--blue)' }}>System Administrator</h3>
            <p>Platform operators managing POI verification queues, fuzzy duplicate POI detection and merging, Fernet-encrypted third-party integrations, and operational audit trails.</p>
          </article>
        </div>
      </section>

      {/* Enterprise Tech Stack Table */}
      <section className="page">
        <h2>Complete Technology Stack</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Tier</th>
                <th>Component</th>
                <th>Technologies & Libraries</th>
                <th>Repository Location</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Web App</th>
                <td>Traveler Client</td>
                <td>React 18, TypeScript, Vite 6, Three.js (WebGL), Leaflet, CartoDB tiles</td>
                <td><Src path="apps/web/src/" /></td>
              </tr>
              <tr>
                <th scope="row">Portal App</th>
                <td>Partner & Operator Portal</td>
                <td>React 18, TypeScript, Vite, Tailwind CSS, Lucide icons (Multi-tenant)</td>
                <td><Src path="apps/portal/src/" /></td>
              </tr>
              <tr>
                <th scope="row">Documentation</th>
                <td>Technical Docs Site</td>
                <td>React 18, TypeScript, Vite 6, Hash Routing (SPA deployed to GitHub Pages)</td>
                <td><Src path="docs-site/src/" /></td>
              </tr>
              <tr>
                <th scope="row">API Gateway</th>
                <td>Backend REST & SSE</td>
                <td>Python 3.12/3.13, FastAPI, Pydantic v2, Starlette SSE, Uvicorn (33 routers)</td>
                <td><Src path="apps/api/app/" /></td>
              </tr>
              <tr>
                <th scope="row">Database</th>
                <td>Relational & Spatial Core</td>
                <td>PostgreSQL 16, PostGIS 3.4, SQLAlchemy 2, Alembic (30 revisions 0001–0030)</td>
                <td><Src path="apps/api/migrations/versions/" /></td>
              </tr>
              <tr>
                <th scope="row">Geospatial Routing</th>
                <td>Road Routing Adapter</td>
                <td>Goong Directions & Geocoding REST APIs (deterministic mock provider in test)</td>
                <td><Src path="apps/api/app/services/routing_service.py" /></td>
              </tr>
              <tr>
                <th scope="row">B2B Quoting</th>
                <td>Pricing & Margin Engine</td>
                <td>Rate-card matrix rollups, MarginGuard floor protection, invoice reconciliation</td>
                <td><Src path="apps/api/app/services/quote/" /></td>
              </tr>
              <tr>
                <th scope="row">Machine Learning</th>
                <td>Ranker, E5, Win Model</td>
                <td>rule-baseline-v1, sentence-transformers (multilingual-e5-base), XGBoost</td>
                <td><Src path="models/" /></td>
              </tr>
              <tr>
                <th scope="row">Security & RBAC</th>
                <td>Auth & Encryption</td>
                <td>Argon2id passwords, RS256 JWT, TOTP MFA, Fernet encryption, 4-tier RBAC</td>
                <td><Src path="apps/api/app/api/permissions.py" /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Core Capabilities */}
      <section className="page">
        <h2>Core Capabilities & Evidence</h2>
        <p className="lead">Audited against the active repository source code. Each capability cites its implementation file, verified status, and technical constraints.</p>
        <div className="grid">
          {CAPABILITIES.map((c) => (
            <article className="card" key={c.title}>
              <div className="card-head">
                <h3 style={{ margin: 0, fontSize: '1rem' }}>{c.title}</h3>
                <StatusBadge status={c.status} />
              </div>
              <p style={{ marginTop: 8 }}>{c.body}</p>
              {c.caveat && <p className="caveat">Constraint: {c.caveat}</p>}
              <Src path={c.evidence} />
            </article>
          ))}
        </div>
      </section>

      {/* Quick Start Guide */}
      <section className="page">
        <h2>Developer Quick Start</h2>
        <div className="card" style={{ background: '#050a12', border: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Terminal size={18} color="var(--cyan)" />
            <strong className="mono" style={{ color: 'var(--text)' }}>Local Environment Setup</strong>
          </div>
          <pre className="mono small" style={{ margin: 0, overflowX: 'auto', color: '#c5d0e2', lineHeight: 1.6 }}>
{`# 1. Clone repository and start backing services
git clone https://github.com/NguyenTriBaoThang/LocalExplorerAI.git
cd LocalExplorerAI
docker-compose up -d db redis

# 2. Setup backend environment and run migrations
cd apps/api
python -m venv .venv && source .venv/bin/activate  # or .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m app.scripts.seed_db

# 3. Run backend tests (346 passing tests)
pytest tests/

# 4. Start backend API server (port 8000)
uvicorn app.main:app --reload --port 8000

# 5. In separate terminal: start Web traveler client (port 8080)
cd apps/web && npm install && npm run dev

# 6. In separate terminal: start Partner & Operator portal (port 5174)
cd apps/portal && npm install && npm run dev`}
          </pre>
        </div>
      </section>
    </>
  )
}
