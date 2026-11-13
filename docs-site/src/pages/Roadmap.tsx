import { ROADMAP } from '../data/extra'
import { PageHeader, Callout } from '../components/ui'
import type { Status } from '../data/site'

const COLS: { statuses: Status[]; title: string }[] = [
  { statuses: ['implemented', 'verified'], title: 'Implemented & Verified' },
  { statuses: ['partial', 'experimental'], title: 'In Progress / Research' },
  { statuses: ['planned'], title: 'Planned Roadmap' },
]

export default function Roadmap() {
  return (
    <section className="page">
      <PageHeader eyebrow="Roadmap" title="Project development progress" lead="Complete roadmap covering Phases 0 through 15. Every item reflects verified implementations in the repository." />
      <div className="road">
        {COLS.map((c) => {
          const items = ROADMAP.filter((r) => c.statuses.includes(r.status))
          return (
            <section key={c.title} className="card" aria-labelledby={`r-${c.title}`}>
              <h2 id={`r-${c.title}`}>{c.title} <span className="mono dim">{items.length}</span></h2>
              {items.length ? (
                <ul className="plain">{items.map((r) => (<li key={r.text}>{r.text}{r.note && <small className="caveat"> {r.note}</small>}</li>))}</ul>
              ) : <p className="dim">No active items in this category.</p>}
            </section>
          )
        })}
      </div>
      <Callout title="Honest Delivery Gaps">
        The project strictly segregates production-verified functionality from research prototypes. The XGBoost candidate ranker and flood risk classifier are flagged as research prototypes; live routing uses Goong and the deterministic heuristic planner.
      </Callout>
    </section>
  )
}
