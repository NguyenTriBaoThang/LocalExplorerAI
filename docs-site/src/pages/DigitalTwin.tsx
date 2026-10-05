import { useRef, useState } from 'react'
import { Minus, Plus, RotateCcw } from 'lucide-react'
import { TWIN_EXPERIENCES, TWIN_POIS } from '../data/extra'
import { DemoLabel, PageHeader, Callout } from '../components/ui'

const W = 760, H = 380, X0 = 120, Y0 = 100
const route = TWIN_POIS.filter((p) => ['p4', 'p2', 'p5', 'p1', 'p3'].includes(p.id))
const order = ['p4', 'p2', 'p1', 'p5', 'p3']
const routePts = order.map((id) => route.find((p) => p.id === id)!)

export default function DigitalTwin() {
  const [z, setZ] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [sel, setSel] = useState<string | null>('p1')
  const [hover, setHover] = useState<string | null>(null)
  const drag = useRef<{ x: number; y: number } | null>(null)

  const zoom = (d: number) => setZ((v) => Math.min(3, Math.max(1, +(v + d).toFixed(2))))
  const reset = () => { setZ(1); setPan({ x: 0, y: 0 }) }
  const all = [...TWIN_POIS.map((p) => ({ ...p, type: 'POI' })), ...TWIN_EXPERIENCES.map((e) => ({ ...e, kind: 'Experience', type: 'Experience' }))]
  const active = all.find((a) => a.id === (hover ?? sel))

  return (
    <section className="page">
      <PageHeader eyebrow="Digital Twin" title="The city as a map of places, activities and routes" lead="The product app renders a Three.js city. To keep this site fast, the visualization below is a lightweight SVG schematic that shows the same concepts." />
      <DemoLabel>schematic layout, not surveyed coordinates</DemoLabel>
      <div className="twin">
        <div className="twin-view">
          <div className="twin-tools" role="group" aria-label="Map controls">
            <button type="button" className="icon-btn" onClick={() => zoom(0.4)} aria-label="Zoom in"><Plus size={16} aria-hidden /></button>
            <button type="button" className="icon-btn" onClick={() => zoom(-0.4)} aria-label="Zoom out"><Minus size={16} aria-hidden /></button>
            <button type="button" className="icon-btn" onClick={reset} aria-label="Reset view"><RotateCcw size={16} aria-hidden /></button>
          </div>
          <svg viewBox={`${X0} ${Y0} ${W} ${H}`} role="group" aria-label="City schematic. Use Tab to move between markers."
            onWheel={(e) => { e.preventDefault(); zoom(e.deltaY < 0 ? 0.2 : -0.2) }}
            onPointerDown={(e) => { drag.current = { x: e.clientX, y: e.clientY } }}
            onPointerMove={(e) => { if (drag.current && z > 1) { const d = drag.current; drag.current = { x: e.clientX, y: e.clientY }; setPan((p) => ({ x: p.x + (e.clientX - d.x) / z, y: p.y + (e.clientY - d.y) / z })) } }}
            onPointerUp={() => { drag.current = null }} onPointerLeave={() => { drag.current = null }}>
            <defs><pattern id="tg" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="var(--line)" /></pattern></defs>
            <rect x={X0} y={Y0} width={W} height={H} fill="url(#tg)" />
            <g transform={`translate(${X0 + W / 2} ${Y0 + H / 2}) scale(${z}) translate(${-(X0 + W / 2) + pan.x} ${-(Y0 + H / 2) + pan.y})`}>
              <path d="M-20 420 C150 380 260 470 420 430 S700 300 820 340 S980 380 1020 360" className="river wide" />
              <text x="700" y="372" className="river-label">Saigon River (schematic)</text>
              <polyline points={routePts.map((p) => `${p.x},${p.y}`).join(' ')} className="route" />
              {TWIN_EXPERIENCES.map((e) => {
                const poi = TWIN_POIS.find((p) => p.id === e.poi)!
                return <line key={e.id} x1={poi.x} y1={poi.y} x2={e.x} y2={e.y} className="tether" />
              })}
              {all.map((a) => {
                const isExp = a.type === 'Experience'
                const on = active?.id === a.id
                return (
                  <g key={a.id} transform={`translate(${a.x} ${a.y})`} className={`marker${isExp ? ' exp' : ''}${on ? ' on' : ''}`} tabIndex={0} role="button"
                    aria-label={`${a.type}: ${a.name}`} aria-pressed={sel === a.id}
                    onClick={() => setSel(a.id)} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), setSel(a.id))}
                    onPointerEnter={() => setHover(a.id)} onPointerLeave={() => setHover(null)} onFocus={() => setHover(a.id)} onBlur={() => setHover(null)}>
                    <circle r={isExp ? 9 : 14} className="halo" />
                    {isExp ? <rect x="-5" y="-5" width="10" height="10" transform="rotate(45)" /> : <circle r="6" />}
                    <text x={isExp ? 14 : 0} y={isExp ? 4 : 30} textAnchor={isExp ? 'start' : 'middle'}>{a.name}</text>
                  </g>
                )
              })}
            </g>
          </svg>
          <ul className="legend"><li><i className="lg poi" /> POI</li><li><i className="lg exp" /> Experience</li><li><i className="lg rt" /> Route</li><li><i className="lg rv" /> River</li></ul>
        </div>
        <aside className="detail" aria-live="polite">
          {active ? (
            <>
              <p className="mono dim">{active.type}{'kind' in active ? ` · ${active.kind}` : ''}</p>
              <h3>{active.name}</h3>
              <p>{active.note}</p>
            </>
          ) : <p>Select a marker.</p>}
          <p className="dim small">Scroll or use the buttons to zoom, drag to pan when zoomed, hover or focus a marker to preview it, click to pin it.</p>
        </aside>
      </div>
      <Callout title="Where the real twin lives">The Three.js scene is in <code>apps/web/src/components/3d/CityHero3D.tsx</code>, and the GLB landmark viewer with per-model calibration (<code>models_3d/calibration.json</code>, <code>/api/models-3d/*</code>) is in <code>Map3DLandmarkViewer.tsx</code>. This site does not load Three.js.</Callout>
    </section>
  )
}
