import { ROADMAP } from '../data/extra'
import { PageHeader, Callout } from '../components/ui'
import type { Status } from '../data/site'

const COLS: { status: Status; title: string }[] = [
  { status: 'implemented', title: 'Implemented' },
  { status: 'partial', title: 'In progress' },
  { status: 'planned', title: 'Planned' },
]

export default function Roadmap() {
  return (
    <section className="page">
      <PageHeader eyebrow="Roadmap" title="Where the project stands" lead="Taken from the README roadmap (Phases 0–11). Notes mark where the code shows a caveat." />
      <div className="road">
        {COLS.map((c) => {
          const items = ROADMAP.filter((r) => r.status === c.status)
          return (
            <section key={c.status} className="card" aria-labelledby={`r-${c.status}`}>
              <h2 id={`r-${c.status}`}>{c.title} <span className="mono dim">{items.length}</span></h2>
              {items.length ? (
                <ul className="plain">{items.map((r) => (<li key={r.text}>{r.text}{r.note && <small className="caveat"> {r.note}</small>}</li>))}</ul>
              ) : <p className="dim">The README lists nothing in progress.</p>}
            </section>
          )
        })}
      </div>
      <Callout title="Not invented">No items were added beyond the README. The in-progress column is empty because the README marks every phase as done except Phase 11.</Callout>
    </section>
  )
}
