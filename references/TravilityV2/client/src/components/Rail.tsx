import { useEffect, useState } from 'react'
import { tripLabel, type TripSummary } from '../api'

const BTN = 'grid size-11 place-items-center rounded-xl text-xl text-white/75 hover:bg-white/10 hover:text-white disabled:opacity-40'

export default function Rail({ busy, trips, currentId, systemOpen, onNewTrip, onOpenTrip, onSystem, onLogout }: {
  busy: boolean; trips: TripSummary[]; currentId: number | null; systemOpen: boolean
  onNewTrip?: () => void; onOpenTrip: (id: number) => void; onSystem: () => void; onLogout: () => void
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
      <nav aria-label="Điều hướng" className="absolute inset-y-0 left-0 z-20 flex w-16 flex-col items-center gap-2 bg-pine py-4">
        <div title="Travility" className="mb-3 grid size-10 place-items-center rounded-xl bg-marigold text-pine">
          <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinejoin="round">
            <path d="M4 18l5-8 3 4 3-5 5 9z M4 18h16" />
          </svg>
        </div>
        <button type="button" className={BTN} aria-label="Chuyến mới" title="Chuyến mới"
          disabled={busy || !onNewTrip} onClick={onNewTrip}>＋</button>
        <button type="button" className={`${BTN} ${open ? 'bg-white/15 text-white' : ''}`} aria-label="Chuyến đi của tôi"
          title="Chuyến đi của tôi" aria-expanded={open} onClick={() => setOpen((o) => !o)}>🗂</button>
        <div className="flex-1" />
        <button type="button" className={`${BTN} ${systemOpen ? 'bg-white/15 text-white' : ''}`} aria-label="Hệ thống"
          title="Hệ thống" aria-pressed={systemOpen} onClick={onSystem}>🖥</button>
        <button type="button" className={BTN} aria-label="Đăng xuất" title="Đăng xuất" onClick={onLogout}>⎋</button>
      </nav>
      {open && (
        <>
          <button type="button" aria-label="Đóng danh sách" className="fixed inset-0 z-20 cursor-default" onClick={() => setOpen(false)} />
          <div role="dialog" aria-label="Chuyến đi của tôi" className="absolute left-[72px] top-24 z-30 w-72 rounded-2xl bg-white p-2 shadow-2xl">
            <h3 className="mx-2.5 my-1.5 text-xs font-semibold uppercase tracking-wider text-stone-500">Chuyến đi của tôi</h3>
            {trips.length === 0 ? <p className="p-2.5 text-sm text-stone-500">Chưa có chuyến nào.</p> : (
              <ul className="max-h-80 overflow-y-auto">
                {trips.map((t) => (
                  <li key={t.id}>
                    <button type="button" disabled={busy} onClick={() => { setOpen(false); onOpenTrip(t.id) }}
                      className={`w-full rounded-lg px-2.5 py-2 text-left text-sm hover:bg-mist disabled:opacity-50 ${
                        t.id === currentId ? 'bg-mist font-semibold' : ''}`}>
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
