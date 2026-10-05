import { useState } from 'react'
import { RotateCcw, Zap } from 'lucide-react'
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
      <PageHeader eyebrow="Planning" title="From intent to a feasible itinerary" lead="Each step narrows the options. Steps that can be wrong, like language or ML, sit before or beside hard checks, never in place of them." />
      <h2>Planning pipeline</h2>
      <Pipeline />
      <Callout title="Reading the pipeline">
        Steps 1–2 use language understanding; step 3 can use E5; steps 4–7 are ordinary code with an optional ML tie-break (travel time calls the routing provider). No LLM call is made while the itinerary is built. Sources: <Src path="apps/api/app/services/planner_service.py" /> and <Src path="apps/api/app/services/planner_engine.py" />.
      </Callout>

      <h2>Dynamic replanning</h2>
      <p className="lead">When a provider cancels a slot, or a weather alert is raised, the repository creates an event and proposes replacements from candidates the database and solver already accepted.</p>
      <DemoLabel>the production backend is not running</DemoLabel>
      <Replan />
      <ul className="plain">
        <li>Events: <code>SLOT_CANCELLED</code> and <code>WEATHER_ALERT</code> (<Src path="apps/api/app/services/replanning_service.py" />).</li>
        <li><code>POST /api/itineraries/{'{id}'}/replan-advice</code> returns proposals; the <code>REPLAN_ADVISOR</code> prompt only chooses among filtered candidates and <code>XAI_EXPLANATION</code> explains the choice.</li>
        <li><code>POST …/replan-advice/accept</code> applies a proposal and writes a new itinerary version.</li>
      </ul>
    </section>
  )
}
