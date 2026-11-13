import { useState } from 'react'
import { RotateCcw, Zap, Lock, ShieldCheck, History, Check } from 'lucide-react'
import { PIPELINE, REPLAN_AFTER, REPLAN_BEFORE } from '../data/extra'
import { DemoLabel, PageHeader, Callout, Src } from '../components/ui'

function Pipeline() {
  const [id, setId] = useState(PIPELINE[0].id)
  const step = PIPELINE.find((p) => p.id === id)!
  return (
    <div className="pipe">
      <ol className="pipe-steps">
        {PIPELINE.map((p, i) => (
          <li key={p.id}>
            <button type="button" className={p.id === id ? 'on' : ''} aria-pressed={p.id === id} onClick={() => setId(p.id)} style={{ ['--i' as string]: i }}>
              <span className="mono">{String(i + 1).padStart(2, '0')}</span>{p.title}
            </button>
          </li>
        ))}
      </ol>
      <aside className="detail" aria-live="polite">
        <h3>{step.title}</h3>
        <p>{step.text}</p>
        <p><span className="mono dim">Where </span><Src path={step.where} /></p>
      </aside>
    </div>
  )
}

function Replan() {
  const [cancelled, setCancelled] = useState(false)
  const rows = REPLAN_BEFORE.map((r) => (cancelled && r.time === REPLAN_AFTER.time ? { ...REPLAN_AFTER, swapped: true } : { ...r, swapped: false }))
  return (
    <div className="replan">
      <ul className="timeline">
        {rows.map((r) => (
          <li key={r.time} className={r.swapped ? 'swapped' : ''}>
            <span className="mono time">{r.time}</span>
            <div><strong>{r.name}</strong><small>{r.kind} · {r.slot}</small></div>
          </li>
        ))}
      </ul>
      <div className="replan-side">
        {!cancelled ? (
          <button type="button" className="btn primary" onClick={() => setCancelled(true)}><Zap size={16} aria-hidden /> Simulate Slot Cancellation</button>
        ) : (
          <>
            <p className="notice" role="status">Original experience became unavailable.<br />The planner searched for a feasible alternative.</p>
            <button type="button" className="btn" onClick={() => setCancelled(false)}><RotateCcw size={16} aria-hidden /> Reset</button>
          </>
        )}
      </div>
    </div>
  )
}

export default function Planning() {
  return (
    <section className="page">
      <PageHeader eyebrow="Planning" title="From intent to a feasible itinerary" lead="Each step narrows the candidate space. Deterministic rules strictly enforce physical feasibility (time, opening hours, capacity, budget, return deadlines); machine learning and LLMs only advise or break ties." />

      <h2>Planning pipeline</h2>
      <Pipeline />
      <Callout title="Guaranteed Non-Hallucination">
        Steps 1–2 parse user intent into typed Pydantic parameters; step 3 retrieves database records via keyword or E5 vector similarity; steps 4–7 execute pure deterministic scheduling. No probabilistic model or LLM is ever called while an itinerary is built. Sources: <Src path="apps/api/app/services/planner_service.py" /> and <Src path="apps/api/app/services/planner_engine.py" />.
      </Callout>

      <h2>Mathematical feasibility constraints</h2>
      <p className="lead">The deterministic scheduling engine treats travel planning as a constrained sequential selection problem with 6 hard invariant checks:</p>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
        <article className="card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--cyan)' }}>
            <Check size={16} /> 1. Temporal Feasibility
          </h3>
          <p className="small">Each scheduled slot <code>s</code> at stop <code>i</code> must start after the arrival time from stop <code>i-1</code>:</p>
          <code className="mono small">arrival(i) = depart(i-1) + ETA(i-1, i) ≤ start_at(s)</code>
        </article>
        <article className="card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--cyan)' }}>
            <Check size={16} /> 2. Return Deadline Feasibility
          </h3>
          <p className="small">The final itinerary stop must allow sufficient return travel time before the user's hard deadline:</p>
          <code className="mono small">end_at(s_last) + ETA(last, origin) ≤ return_deadline</code>
        </article>
        <article className="card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--green)' }}>
            <Check size={16} /> 3. Budget Envelope
          </h3>
          <p className="small">Total accumulated cost across all stops must never exceed the specified maximum budget:</p>
          <code className="mono small">Σ (price_vnd × group_size) + Σ travel_cost ≤ budget_vnd</code>
        </article>
        <article className="card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--green)' }}>
            <Check size={16} /> 4. Real Capacity Feasibility
          </h3>
          <p className="small">Slots must have verified open seats. If capacity is unreported, the stop is flagged tentative:</p>
          <code className="mono small">available_reported ≥ group_size</code>
        </article>
        <article className="card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--amber)' }}>
            <Lock size={16} /> 5. Locked Stops Preservation
          </h3>
          <p className="small">Stops pinned by the traveler (<Src path="is_locked=True" />) remain strictly fixed in order and timing during replanning; only flexible stops are altered.</p>
        </article>
        <article className="card">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--amber)' }}>
            <ShieldCheck size={16} /> 6. Road Route Accuracy
          </h3>
          <p className="small">Travel legs use actual Goong road routing metrics (motorcycle, car, taxi, walking) rather than straight-line distance, including polyline coordinates.</p>
        </article>
      </div>

      <h2>Dynamic replanning & Event reaction</h2>
      <p className="lead">When a provider cancels a slot or severe weather impacts an outdoor stop, the system dispatches an operational event and proposes valid alternatives from the database.</p>
      <DemoLabel>the production backend is not running</DemoLabel>
      <Replan />
      <ul className="plain">
        <li><strong>Supported Events:</strong> <code>SLOT_CANCELLED</code> and <code>WEATHER_ALERT</code> (<Src path="apps/api/app/services/replanning_service.py" />).</li>
        <li><strong>Proposal Selection:</strong> <code>POST /api/itineraries/{'{id}'}/replan-advice</code> queries feasible database alternatives; the <code>REPLAN_ADVISOR</code> prompt recommends the best contextual choice and <code>XAI_EXPLANATION</code> provides a human-readable justification.</li>
        <li><strong>Immutable Version Commit:</strong> <code>POST …/replan-advice/accept</code> creates a new sequential version snapshot.</li>
      </ul>

      <h2>Itinerary versioning & Atomic rollback</h2>
      <p className="lead">Every modification generates an immutable version snapshot, preserving complete audit history and enabling instant rollback.</p>
      <div className="card" style={{ background: 'var(--panel2)' }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--cyan)' }}>
          <History size={18} /> Verified Rollback Endpoint: <code>POST /api/trips/{'{id}'}/restore/{'{version}'}</code>
        </h3>
        <p>When restoring an earlier version, the API copies the historical snapshot into a new active version, automatically re-verifies pricing against current rate cards, and reports any newly emerged slot conflicts.</p>
        <Src path="apps/api/app/api/routes/trips.py" />
      </div>
    </section>
  )
}
