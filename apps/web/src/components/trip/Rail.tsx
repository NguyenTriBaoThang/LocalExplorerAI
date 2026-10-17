import { useEffect, useState } from 'react'
import { tripLabel, type TripSummary } from '../../api/trips'

const BTN = 'grid size-11 place-items-center rounded-xl text-xl text-[var(--text-main)] hover:bg-[var(--bg-surface)] hover:text-emerald-600 disabled:opacity-40'

export default function Rail({ busy, trips, currentId, onNewTrip, onOpenTrip }: {
  busy: boolean; trips: TripSummary[]; currentId: number | null
  onNewTrip?: () => void; onOpenTrip: (id: number) => void
}) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open) return
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    addEventListener('keydown', esc)
    return () => removeEventListener('keydown', esc)
  }, [open])
  return (
    <>
      <nav aria-label="Điều hướng" className="absolute inset-y-0 left-0 z-20 flex w-16 flex-col items-center gap-2 bg-[var(--bg-surface)] py-4">
        <div title="Local Explorer AI" className="mb-3 grid size-10 place-items-center rounded-xl bg-amber-400 text-[var(--text-main)]">
          <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinejoin="round">
            <path d="M4 18l5-8 3 4 3-5 5 9z M4 18h16" />
          </svg>
        </div>
        <button type="button" className={BTN} aria-label="Chuyến mới" title="Chuyến mới"
          disabled={busy || !onNewTrip} onClick={onNewTrip}>＋</button>
        <button type="button" className={`${BTN} ${open ? 'bg-emerald-700 text-white' : ''}`} aria-label="Chuyến đi của tôi"
          title="Chuyến đi của tôi" aria-expanded={open} onClick={() => setOpen((o) => !o)}>🗂</button>
        <div className="flex-1" />
      </nav>
      {open && (
        <>
          <button type="button" aria-label="Đóng danh sách" className="fixed inset-0 z-20 cursor-default" onClick={() => setOpen(false)} />
          <div role="dialog" aria-label="Chuyến đi của tôi" className="absolute left-[72px] top-24 z-30 w-72 rounded-2xl bg-[var(--bg-surface)] p-2 shadow-2xl">
            <h3 className="mx-2.5 my-1.5 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">Chuyến đi của tôi</h3>
            {trips.length === 0 ? <p className="p-2.5 text-sm text-[var(--text-muted)]">Chưa có chuyến nào.</p> : (
              <ul className="max-h-80 overflow-y-auto">
                {trips.map((t) => (
                  <li key={t.id}>
                    <button type="button" disabled={busy} onClick={() => { setOpen(false); onOpenTrip(t.id) }}
                      className={`w-full rounded-lg px-2.5 py-2 text-left text-sm hover:bg-[var(--bg-elevated)] disabled:opacity-50 ${
                        t.id === currentId ? 'bg-[var(--bg-elevated)] font-semibold' : ''}`}>
                      {tripLabel(t)}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </>
  )
}
