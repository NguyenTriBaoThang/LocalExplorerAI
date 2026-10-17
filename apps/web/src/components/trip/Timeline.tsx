import { useEffect, useRef, type ReactNode } from 'react'
import { intentChips, mealOf, rainable, viewingOld, vnd, type DisruptionReq, type Itinerary, type Place } from '../../api/trips'
import type { Selected } from './place'
import PlaceThumb from './PlaceThumb'

export default function Timeline({ itinerary, places, budget, busy = false, changed = [], onDisrupt,
  versions = [], version = null, latest = null, pins = [], onView, onRestore, onPin, onExportPdf,
  selected = null, onSelect, children }: {
  itinerary: Itinerary | null; places: Record<string, Place>; budget: number | null; changed?: [number, number][]
  busy?: boolean; onDisrupt?: (d: DisruptionReq) => void
  versions?: number[]; version?: number | null; latest?: number | null; pins?: number[]
  onView?: (v: number) => void; onRestore?: () => void; onPin?: (placeId: number, pinned: boolean) => void
  onExportPdf?: () => void
  selected?: Selected; onSelect?: (s: Selected) => void
  children?: ReactNode
}) {
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {  // chọn từ bản đồ hoặc tour → cuộn Timeline tới Stop đó
    root.current?.querySelector('[data-selected]')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [selected])
  if (!itinerary) return null
  const stay = itinerary.stay_place_id != null ? places[itinerary.stay_place_id] : undefined
  const old = viewingOld(version, latest)
  return (
    <div ref={root} className="min-h-0 flex-1 overflow-y-auto p-4">
      {children}
      {(versions.length > 1 || (version != null && onExportPdf)) && (
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          {versions.length > 1 && (
            <nav aria-label="Phiên bản lịch trình" className="flex flex-wrap items-center gap-1 text-xs">
              {versions.map((v, i) => (
                <span key={v} className="flex items-center gap-1">
                  {i > 0 && <span className="text-stone-400">·</span>}
                  <button disabled={busy} aria-current={v === version ? 'true' : undefined} onClick={() => onView?.(v)}
                    className={`rounded px-1.5 py-0.5 ${v === version ? 'bg-emerald-700 text-white' : 'hover:bg-stone-200'}`}>
                    v{v}
                  </button>
                </span>
              ))}
            </nav>
          )}
          {version != null && onExportPdf && (
            <button type="button" disabled={busy} onClick={onExportPdf}
              className="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs font-medium text-[var(--text-main)] hover:bg-[var(--bg-surface)] disabled:opacity-50">
              Xuất PDF
            </button>
          )}
        </div>
      )}
      {old && (
        <div role="status" className="mb-3 flex flex-wrap items-center gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          <span>Đang xem bản {version}</span>
          <button disabled={busy} onClick={onRestore}
            className="rounded bg-amber-600 px-2 py-0.5 text-white disabled:opacity-50">Quay lại bản này</button>
          <button disabled={busy} onClick={() => latest != null && onView?.(latest)}
            className="rounded border border-amber-600 px-2 py-0.5 disabled:opacity-50">Về bản mới nhất</button>
        </div>
      )}
      <div className="mb-3 rounded-xl bg-[var(--bg-surface)] p-3 shadow-sm">
        <div className="text-sm text-[var(--text-muted)]">Tổng chi phí ước tính</div>
        <div className="text-2xl font-semibold">{vnd(itinerary.total_cost)}</div>
        {budget != null && <div className="text-xs text-[var(--text-muted)]">Budget {vnd(budget)} · chưa gồm vé đến/rời thành phố</div>}
        {stay && (
          <button type="button" onClick={() => onSelect?.('stay')}
            className={`mt-1 block text-left text-xs hover:underline ${selected === 'stay' ? 'font-semibold text-[var(--text-main)]' : ''}`}>
            Chỗ ở: {stay.name}
          </button>
        )}
        {intentChips(itinerary).length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1 text-xs">
            {intentChips(itinerary).map((c) => (
              <span key={c.label}
                className={`rounded-full px-2 py-0.5 ${c.ok ? 'bg-emerald-100 text-emerald-800' : 'bg-stone-200 text-[var(--text-muted)]'}`}>
                {c.ok ? '✓' : '✗'} {c.label}
              </span>
            ))}
            {itinerary.retention != null && (
              <span className="ml-1 text-[var(--text-muted)]">Giữ mục đích {Math.round(itinerary.retention * 100)}%</span>
            )}
          </div>
        )}
      </div>
      {itinerary.conflicts.length > 0 && (
        <ul className="mb-3 space-y-1 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {itinerary.conflicts.map((c, i) => <li key={i}>{c.message}</li>)}
        </ul>
      )}
      {itinerary.days.map((day, i) => (
        <section key={i} className="mb-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="font-semibold">
              Ngày {i + 1}{day.date && ` · ${day.date}`}{day.rain_chance != null && ` · mưa ${day.rain_chance}%`}
            </h2>
            {!old && onDisrupt && rainable(day, places, pins) && (
              <button type="button" disabled={busy} onClick={() => onDisrupt({ kind: 'rain', day_index: i })}
                className="rounded border border-sky-300 px-2 py-0.5 text-xs text-sky-800 hover:bg-sky-50 disabled:opacity-40">
                ☂ Giả sử mưa
              </button>
            )}
          </div>
          <ol className="space-y-2">
            {day.stops.map((s, j) => {
              const p = places[s.place_id]
              const meal = mealOf(p?.kind, s.start_time)
              const pinned = pins.includes(s.place_id)
              const on = selected !== null && selected !== 'stay' && selected.day === i && selected.stop === j
              return (
              <li key={j} data-selected={on || undefined} onClick={() => onSelect?.({ day: i, stop: j })}
                className={`flex cursor-pointer gap-3 rounded-xl border p-2.5 text-sm ${
                  pinned ? 'border-[var(--border)] bg-[var(--bg-surface)]' : 'border-[var(--border)] bg-[var(--bg-surface)]'} ${
                  on ? 'outline-2 outline-offset-1 outline-marigold' : ''} ${
                  changed.some(([d, k]) => d === i && k === j) ? 'ring-2 ring-amber-400' : ''}`}>
                <PlaceThumb kind={p?.kind ?? ''} photo={p?.photo_url} />
                <div className="min-w-0 flex-1">
                  {meal && <div className="mb-0.5 text-xs font-medium text-amber-700">🍜 {meal}</div>}
                  <div className="flex justify-between gap-2">
                    <button type="button" className="min-w-0 truncate text-left font-semibold"
                      onClick={(e) => { e.stopPropagation(); onSelect?.({ day: i, stop: j }) }}>
                      {s.start_time} · {p?.name}
                    </button>
                    <span className="shrink-0 tabular-nums">{vnd(s.est_cost)}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-[var(--text-muted)]">{s.reason}</p>
                  {!old && (onPin || (onDisrupt && on)) && (
                    <div className="mt-2 flex flex-wrap gap-2 text-xs" onClick={(e) => e.stopPropagation()}>
                      {onPin && (
                        <button type="button" disabled={busy} aria-pressed={pinned}
                          title={pinned ? 'Bỏ ghim' : 'Ghim: AI không được đổi Stop này'}
                          onClick={() => onPin(s.place_id, !pinned)}
                          className={`rounded border px-2 py-0.5 disabled:opacity-40 ${
                            pinned ? 'border-[var(--border)] bg-emerald-700 text-white' : 'border-stone-300 hover:bg-[var(--bg-elevated)]'}`}>
                          📌 {pinned ? 'Đã ghim' : 'Ghim'}
                        </button>
                      )}
                      {onDisrupt && on && (['closed', 'disliked'] as const).map((k) => (
                        <button key={k} type="button" disabled={busy || pinned}
                          title={pinned ? 'Bỏ ghim để đổi' : undefined}
                          onClick={() => onDisrupt({ kind: k, day_index: i, stop_index: j })}
                          className="rounded border border-stone-300 px-2 py-0.5 hover:bg-[var(--bg-elevated)] disabled:opacity-40">
                          {k === 'closed' ? 'Báo đóng cửa' : 'Đổi chỗ khác'}
                        </button>
                      ))}
                      {onDisrupt && on && (
                        <span className="flex items-center gap-1">
                          Tôi trễ
                          {[15, 30, 60].map((m) => (
                            <button key={m} type="button" disabled={busy}
                              onClick={() => onDisrupt({ kind: 'late', day_index: i, stop_index: j, minutes: m })}
                              className="rounded border border-stone-300 px-1.5 py-0.5 hover:bg-[var(--bg-elevated)] disabled:opacity-40">
                              {m}′
                            </button>
                          ))}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </li>
              )
            })}
          </ol>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            Di chuyển: {day.legs.reduce((a, l) => a + l.distance_km, 0).toFixed(1)} km · {vnd(day.legs.reduce((a, l) => a + l.cost, 0))}
          </p>
        </section>
      ))}
    </div>
  )
}
