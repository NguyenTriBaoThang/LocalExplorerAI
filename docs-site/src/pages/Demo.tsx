import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { DEMO_STEPS, GALLERY, STORY } from '../data/extra'
import { PageHeader } from '../components/ui'

function Lightbox({ i, onClose }: { i: number; onClose: () => void }) {
  const g = GALLERY[i]
  const btn = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    btn.current?.focus()
    const on = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [onClose])
  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label={g.title} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <figure className="lightbox">
        <button ref={btn} type="button" className="icon-btn close" onClick={onClose} aria-label="Close image"><X size={18} aria-hidden /></button>
        <img src={`./img/${g.file}`} alt={`${g.title}: ${g.text}`} />
        <figcaption><strong>{g.title}</strong> <span className="mono dim">{g.feature}</span><br />{g.text}</figcaption>
      </figure>
    </div>
  )
}

export default function Demo() {
  const [open, setOpen] = useState<number | null>(null)
  return (
    <section className="page">
      <PageHeader eyebrow="Demo" title="A seven-minute walkthrough" lead="Order and content follow DEMO_SCRIPT.md in the repository. It runs against the product app (npm run dev on port 5173), not this site." />
      <ol className="steps">
        {DEMO_STEPS.map((s, i) => (
          <li key={s.title}>
            <span className="mono n">{String(i + 1).padStart(2, '0')}</span>
            <div><h3>{s.title} <small className="mono dim">{s.time}</small></h3><p><strong>Do:</strong> {s.action}</p><p>{s.point}</p></div>
          </li>
        ))}
      </ol>

      <h2>Screenshots</h2>
      <div className="gallery">
        {GALLERY.map((g, i) => (
          <button type="button" key={g.file} className="shot" onClick={() => setOpen(i)} aria-label={`Open ${g.title}`}>
            <img src={`./img/${g.file}`} alt={`${g.title} screenshot`} loading="lazy" width={1365} height={599} />
            <span><strong>{g.title}</strong><small className="mono dim">{g.feature}</small><em>{g.text}</em></span>
          </button>
        ))}
      </div>

      <h2>Project story</h2>
      <ol className="story">
        {STORY.map((s) => (<li key={s.label}><strong className="mono">{s.label}</strong><p>{s.text}</p></li>))}
      </ol>
      {open !== null && <Lightbox i={open} onClose={() => setOpen(null)} />}
    </section>
  )
}
