import { useEffect, useMemo, useRef, useState } from 'react'
import { NAV } from '../data/site'
import { ALL_ENDPOINTS } from '../data/api'
import { CAPABILITIES } from '../data/capabilities'
import { ARCH_NODES, DECISIONS, ENTITIES } from '../data/content'
import { FEATURES, PIPELINE, PROMPTS } from '../data/extra'

interface Doc { title: string; kind: string; path: string; text: string }

const INDEX: Doc[] = [
  ...NAV.map((n) => ({ title: n.label, kind: 'Section', path: n.path, text: n.blurb })),
  ...CAPABILITIES.map((c) => ({ title: c.title, kind: 'Capability', path: '/', text: `${c.body} ${c.evidence}` })),
  ...ARCH_NODES.map((n) => ({ title: n.label, kind: 'Architecture', path: '/architecture', text: `${n.sub} ${n.responsibility} ${n.technology} ${n.location}` })),
  ...ENTITIES.map((e) => ({ title: e.name, kind: 'Data model', path: '/architecture', text: `${e.table} ${e.note} ${e.fields.join(' ')}` })),
  ...DECISIONS.map((d) => ({ title: d.component, kind: 'Decision', path: '/architecture', text: `${d.owns} ${d.detail}` })),
  ...PIPELINE.map((p) => ({ title: p.title, kind: 'Pipeline', path: '/planning', text: `${p.where} ${p.text}` })),
  ...FEATURES.map(([n, t]) => ({ title: n, kind: 'ML feature', path: '/ml', text: t })),
  ...PROMPTS.map(([n, t]) => ({ title: n, kind: 'Prompt', path: '/ml', text: t })),
  ...ALL_ENDPOINTS.map((e) => ({ title: `${e.method} ${e.path}`, kind: 'Endpoint', path: '/api', text: `${e.summary} ${e.group}` })),
]

export default function SearchDialog({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState('')
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    ref.current?.focus()
    const on = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', on)
    return () => {
      window.removeEventListener('keydown', on)
      opener?.focus?.()
    }
  }, [onClose])

  const results = useMemo(() => {
    const terms = q.toLowerCase().split(/\s+/).filter(Boolean)
    if (!terms.length) return []
    return INDEX.map((d) => {
      const title = d.title.toLowerCase()
      const hay = `${title} ${d.text.toLowerCase()} ${d.kind.toLowerCase()}`
      if (!terms.every((t) => hay.includes(t))) return null
      return { d, score: terms.reduce((s, t) => s + (title.includes(t) ? 3 : 1), 0) }
    }).filter((r): r is { d: Doc; score: number } => r !== null).sort((a, b) => b.score - a.score).slice(0, 30)
  }, [q])

  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label="Search documentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-box search">
        <input ref={ref} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search sections, technologies, endpoints…" aria-label="Search query" />
        <ul>
          {results.map(({ d }, i) => (
            <li key={i}>
              <a href={`#${d.path}`} onClick={onClose}>
                <span className="mono dim">{d.kind}</span>
                <strong>{d.title}</strong>
                <small>{d.text.slice(0, 110)}</small>
              </a>
            </li>
          ))}
          {q && !results.length && <li className="empty">No matches for “{q}”.</li>}
          {!q && <li className="empty">Try “XGBoost”, “slot”, “/api/ml”, or “replan”. Esc closes.</li>}
        </ul>
      </div>
    </div>
  )
}
