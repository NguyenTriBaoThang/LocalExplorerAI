import { PLATFORM } from '../data/content'
import { PageHeader, Callout, Src } from '../components/ui'

export default function Platform() {
  return (
    <section className="page">
      <PageHeader eyebrow="Platform" title="Four roles, one unified catalog" lead="Role-based access control (Traveler, Provider, Tour Operator, Admin) is enforced by backend route dependencies (P.TRIP_USE, P.PROVIDER_WRITE, P.OPERATOR_WRITE, P.ADMIN_ALL). The web app and partner portal enforce matching route guards." />
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
      <Callout title="Trust Model & Verification States">
        Data in the catalog carries an explicit verification status. The planner labels each stop <code>verified</code>, <code>simulated</code> or <code>stale</code> based on provider verification state, evidence uploads, and slot freshness. Itineraries expose an aggregate <code>data_mode</code> (<code>real</code>, <code>simulated</code>, or <code>mixed</code>).
      </Callout>
      <Callout tone="note" title="Multi-Tenant Applications">
        Travelers interact with the public exploration app (<Src path="apps/web/src/" />). Experience Providers and B2B Tour Operators manage their businesses in the dedicated Partner Portal (<Src path="apps/portal/src/" />) with isolated tenant contexts and role-based permissions.
      </Callout>
    </section>
  )
}
