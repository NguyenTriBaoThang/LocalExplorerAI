import { ArrowRight, Github } from 'lucide-react'
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
          <p className="eyebrow mono">Technical documentation · Ho Chi Minh City</p>
          <h1>LocalExplorerAI</h1>
          <p className="tagline">Explore Saigon. Plan smarter. Experience more.</p>
          <p className="lead">AI-assisted urban experience discovery that combines semantic search, machine-learning ranking, slot-level availability and deterministic itinerary planning.</p>
          <div className="cta">
            <a className="btn primary" href="#/architecture">Explore Architecture <ArrowRight size={16} aria-hidden /></a>
            <a className="btn" href={REPO_URL} target="_blank" rel="noreferrer"><Github size={16} aria-hidden /> View on GitHub</a>
          </div>
        </div>
        <HeroViz />
      </section>

      <section className="page">
        <h2>What is LocalExplorerAI?</h2>
        <div className="two">
          <div>
            <p>Travel search usually asks <em>“where can I go?”</em> LocalExplorerAI asks a narrower question: <em>what can I actually do, given my time, preferences, budget and what is really available?</em></p>
            <p>A POI being open does not mean a given activity is running. A pottery class has sessions with limited seats, so the system models the place, the activity and the session separately and plans over sessions.</p>
            <Callout title="Architectural principle, confirmed in code">
              Itinerary stops reference an <Src path="ExperienceSlot" />, not just a place. Planning works over slots: it skips candidates that break the window, budget or return deadline, and marks the plan tentative when capacity is not reported. See <Src path={SRC.entities} />.
            </Callout>
          </div>
          <ol className="chain" aria-label="From place to itinerary">
            {[['POI', 'A place with coordinates'], ['Experience', 'An activity hosted there'], ['Available Slot', 'A session with capacity'], ['Feasible Itinerary', 'Ordered stops that fit time and budget']].map(([a, b], i) => (
              <li key={a}><span className="mono">0{i + 1}</span><strong>{a}</strong><small>{b}</small></li>
            ))}
          </ol>
        </div>
      </section>

      <section className="page">
        <h2>Core capabilities</h2>
        <p className="lead">Only what the repository contains. Each card names its source file and any caveat.</p>
        <div className="grid">
          {CAPABILITIES.map((c) => (
            <article className="card" key={c.title}>
              <div className="card-head"><h3>{c.title}</h3><StatusBadge status={c.status} /></div>
              <p>{c.body}</p>
              {c.caveat && <p className="caveat">Caveat: {c.caveat}</p>}
              <Src path={c.evidence} />
            </article>
          ))}
        </div>
      </section>
    </>
  )
}
