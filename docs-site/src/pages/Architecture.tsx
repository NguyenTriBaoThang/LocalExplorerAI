import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { ARCH_EDGES, ARCH_NODES, DECISIONS, ENTITIES, REPO_TREE, type TreeNode } from '../data/content'
import { PageHeader, Src, Callout } from '../components/ui'

const byId = (id: string) => ARCH_NODES.find((x) => x.id === id)!

/** Orthogonal connector from the bottom of one node to the top of the next. */
function edgePath(a: string, b: string) {
  const A = byId(a), B = byId(b)
  const x1 = A.x + A.w / 2, y1 = A.y + A.h
  const x2 = B.x + B.w / 2, y2 = B.y
  const mid = (y1 + y2) / 2
  return `M${x1} ${y1} V${mid} H${x2} V${y2}`
}

function Diagram() {
  const [sel, setSel] = useState('planner')
  const node = ARCH_NODES.find((n) => n.id === sel)!
  return (
    <div className="arch">
      <div className="arch-scroll">
        <svg viewBox="0 0 960 484" role="group" aria-label="System architecture diagram. Select a component for details.">
          <defs>
            <marker id="ar" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L8 4L0 8z" fill="var(--muted)" /></marker>
          </defs>
          {ARCH_EDGES.map(([a, b]) => (
            <path key={a + b} d={edgePath(a, b)} className={`edge${sel === a || sel === b ? ' hot' : ''}`} markerEnd="url(#ar)" />
          ))}
          {ARCH_NODES.map((n) => (
            <g key={n.id} className={`anode tone-${n.tone}${sel === n.id ? ' sel' : ''}`} transform={`translate(${n.x} ${n.y})`}
              tabIndex={0} role="button" aria-pressed={sel === n.id} aria-label={`${n.label}: ${n.sub}`}
              onClick={() => setSel(n.id)} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), setSel(n.id))}>
              <rect width={n.w} height={n.h} rx="6" />
              <text x="14" y="25" className="t1">{n.label}</text>
              <text x="14" y="45" className="t2">{n.sub}</text>
            </g>
          ))}
        </svg>
      </div>
      <aside className="detail" aria-live="polite">
        <h3>{node.label}</h3>
        <dl>
          <dt>Responsibility</dt><dd>{node.responsibility}</dd>
          <dt>Technology</dt><dd>{node.technology}</dd>
          <dt>Input</dt><dd>{node.input}</dd>
          <dt>Output</dt><dd>{node.output}</dd>
          <dt>Repository location</dt><dd><Src path={node.location} /></dd>
        </dl>
      </aside>
    </div>
  )
}

function Tree({ nodes, depth = 0 }: { nodes: TreeNode[]; depth?: number }) {
  return (
    <ul className="tree" style={{ ['--d' as string]: depth }}>
      {nodes.map((n) => <TreeItem key={n.name} n={n} depth={depth} />)}
    </ul>
  )
}
function TreeItem({ n, depth }: { n: TreeNode; depth: number }) {
  const [open, setOpen] = useState(depth < 1)
  return (
    <li>
      {n.children ? (
        <button type="button" className="tree-row" onClick={() => setOpen(!open)} aria-expanded={open}>
          <ChevronRight size={14} className={open ? 'rot' : ''} aria-hidden /><span className="mono">{n.name}/</span><small>{n.note}</small>
        </button>
      ) : (
        <div className="tree-row leaf"><span className="spacer" /><span className="mono">{n.name}</span><small>{n.note}</small></div>
      )}
      {n.children && open && <Tree nodes={n.children} depth={depth + 1} />}
    </li>
  )
}

export default function Architecture() {
  return (
    <section className="page">
      <PageHeader eyebrow="Architecture" title="How the system fits together" lead="Select a component to see its responsibility, technology, input, output and where it lives. The diagram is drawn in SVG from the repository’s actual modules." />
      <Diagram />
      <Callout tone="warn" title="Where the existing docs disagree">
        <code>ARCHITECTURE.md</code> describes a Haversine routing adapter and no LLM; the README and code describe Goong routing with a mock provider for tests. This site follows the code: <Src path="apps/api/app/services/routing_service.py" />.
      </Callout>

      <h2 id="data-model">Core data model</h2>
      <p className="lead">Place, activity and session are separate so availability can be tracked where it actually changes: at the slot.</p>
      <div className="model">
        {ENTITIES.map((e, i) => (
          <div className="entity" key={e.name} style={{ marginLeft: Math.min(i, 3) * 14 }}>
            <h3>{e.name} <span className="mono dim">{e.table}</span></h3>
            <p>{e.note}</p>
            <p className="fields mono">{e.fields.join(' · ')}</p>
          </div>
        ))}
      </div>

      <h2 id="decisions">Technical decisions</h2>
      <p className="lead">Each component has one job, and the ones that can be wrong are never allowed to decide feasibility.</p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Component</th><th>Responsibility</th><th>How it is bounded</th><th>Source</th></tr></thead>
          <tbody>
            {DECISIONS.map((d) => (
              <tr key={d.component}>
                <th scope="row">{d.component}</th>
                <td><strong>{d.owns}</strong><br />{d.detail}</td>
                <td>{d.never}</td>
                <td><Src path={d.where} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 id="repo">Repository explorer</h2>
      <Tree nodes={REPO_TREE} />
    </section>
  )
}
