import { useMemo, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { API_GROUPS, type Endpoint } from '../data/api'
import { CodeBlock } from '../components/CodeBlock'
import { PageHeader, Callout } from '../components/ui'

const ACCESS: Record<string, string> = {
  public: 'No auth dependency',
  optional: 'Optional session',
  session: 'Signed-in user',
  traveler: 'Traveler role',
  provider: 'Provider role',
  admin: 'Admin role',
}

function Row({ e }: { e: Endpoint }) {
  const [open, setOpen] = useState(false)
  const expandable = Boolean(e.request || e.response)
  return (
    <li className="ep">
      <button type="button" className="ep-head" onClick={() => expandable && setOpen(!open)} aria-expanded={expandable ? open : undefined} disabled={!expandable}>
        <span className={`method m-${e.method}`}>{e.method}</span>
        <code className="path">{e.path}</code>
        {e.access && <span className="acc mono">{ACCESS[e.access]}</span>}
        {expandable && <ChevronDown size={16} className={open ? 'rot' : ''} aria-hidden />}
      </button>
      <p className="ep-sum">{e.summary} <span className="mono dim">{e.source}</span></p>
      {open && (
        <div className="ep-body">
          {e.request && <CodeBlock label="Request" code={e.request} />}
          {e.response && <CodeBlock label="Response" code={e.response} />}
        </div>
      )}
    </li>
  )
}

export default function ApiExplorer() {
  const [group, setGroup] = useState('all')
  const [q, setQ] = useState('')
  const groups = useMemo(() => API_GROUPS.map((g) => ({
    ...g,
    endpoints: g.endpoints.filter((e) => (group === 'all' || group === g.id) && `${e.method} ${e.path} ${e.summary}`.toLowerCase().includes(q.toLowerCase())),
  })).filter((g) => g.endpoints.length), [group, q])
  const total = API_GROUPS.reduce((n, g) => n + g.endpoints.length, 0)

  return (
    <section className="page">
      <PageHeader eyebrow="API" title="Endpoint reference" lead={`${total} endpoints extracted from the FastAPI routers. This is documentation only: nothing on this page calls a server.`} />
      <Callout title="Source of truth">
        Paths come from the <code>@router</code> decorators in <code>apps/api/app/api/routes/</code>; request bodies from <code>apps/api/app/schemas/</code>. Responses are abbreviated to fields that exist in the schemas. When the API is running, the full OpenAPI document is served at <code>/docs</code>. Payment IPN and return callbacks are excluded from the schema and omitted here.
      </Callout>
      <div className="filters">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter endpoints…" aria-label="Filter endpoints" />
        <div className="chips" role="group" aria-label="Group">
          {[{ id: 'all', title: 'All' }, ...API_GROUPS].map((g) => (
            <button key={g.id} type="button" className={group === g.id ? 'chip on' : 'chip'} aria-pressed={group === g.id} onClick={() => setGroup(g.id)}>{g.title}</button>
          ))}
        </div>
      </div>
      {groups.map((g) => (
        <div key={g.id}>
          <h2>{g.title}</h2>
          <ul className="eps">{g.endpoints.map((e) => <Row key={e.method + e.path} e={e} />)}</ul>
        </div>
      ))}
      {!groups.length && <p>No endpoints match.</p>}
    </section>
  )
}
