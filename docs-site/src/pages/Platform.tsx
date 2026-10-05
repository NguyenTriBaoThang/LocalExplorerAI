import { PLATFORM } from '../data/content'
import { PageHeader, Callout } from '../components/ui'

export default function Platform() {
  return (
    <section className="page">
      <PageHeader eyebrow="Platform" title="Three roles, one catalog" lead="Role-based access (traveler, provider, admin) is enforced by backend route dependencies; the web app adds route guards on top." />
      <div className="roles">
        {PLATFORM.map((r) => (
          <article className="card role" key={r.role}>
            <h2>{r.role}</h2>
            <dl>
              {r.items.map(([t, d]) => (<div key={t}><dt>{t}</dt><dd>{d}</dd></div>))}
            </dl>
          </article>
        ))}
      </div>
      <Callout title="Trust model">
        Data carries an explicit status. The planner labels each stop <code>verified</code>, <code>simulated</code> or <code>stale</code> from its verification state, evidence and slot freshness, and sets the itinerary <code>data_mode</code> to <code>real</code>, <code>simulated</code> or <code>mixed</code>. Providers submit evidence and admins verify it.
      </Callout>
    </section>
  )
}
