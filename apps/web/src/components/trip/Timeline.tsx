import { useEffect, useRef, type ReactNode } from 'react'
import { Pin, Utensils } from 'lucide-react'
import { intentChips, mealOf, rainable, viewingOld, type Day, type DisruptionReq, type Itinerary, type Place } from '../../api/trips'
import { useTranslation } from '../../i18n'
import type { Selected } from './place'
import PlaceThumb from './PlaceThumb'

function FloodRouteNotice({ day, places }: { day: Day; places: Record<string, Place> }) {
  const { t, locale } = useTranslation()
  const chance = day.weather_forecast?.precipitation_probability_pct ?? day.rain_chance
  const amount = day.weather_forecast?.precipitation_sum_mm
  const weatherCode = day.weather_forecast?.weather_code

  const rainCode = weatherCode != null && (weatherCode >= 51 && weatherCode <= 67 || weatherCode >= 80 && weatherCode <= 82 || weatherCode >= 95)
  const forecastKnown = day.weather_forecast != null || day.rain_chance != null
  const rainExpected = rainCode || (amount ?? 0) > 0 || (chance ?? 0) >= 40

  const segments = day.legs.map((leg, index) => {
    const from = leg.from_place_id == null ? (index === 0 ? t('tripChat.originPoint') : t('tripChat.connectionPoint'))
      : places[leg.from_place_id]?.name ?? `Stop ${leg.from_place_id}`
    const to = leg.to_place_id == null ? t('tripChat.destinationPoint')
      : places[leg.to_place_id]?.name ?? `Stop ${leg.to_place_id}`
    return `${from} → ${to}`
  })

  return (
    <div className="mt-2 rounded-lg border border-amber-500/25 bg-amber-500/5 p-2.5 text-xs">
      <div className="font-semibold text-[var(--text-main)]">{t('weather.rainRoadTitle')}</div>
      {!forecastKnown ? (
        <p className="mt-1 text-[var(--text-muted)]">{t('weather.rainRoadNoForecast')}</p>
      ) : rainExpected ? (
        <>
          <p className="mt-1 text-[var(--text-muted)]">
            {rainCode || (amount ?? 0) > 0 || (chance ?? 0) >= 50
              ? t('weather.rainForecastLikely')
              : t('weather.rainForecastPossible')}{chance != null ? ` ${chance}%` : ''}{amount != null ? t('weather.rainAmount', { amount: amount.toFixed(1) }) : ''}.
          </p>
          <div className="mt-2 space-y-1">
            {segments.length ? segments.map((segment, index) => (
              <div key={`${index}-${segment}`} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-[var(--bg-elevated)] px-2 py-1.5">
                <span>{segment}</span><span className="text-amber-700">{locale === 'en' ? 'Unverified' : 'Chưa thể dự đoán'}</span>
              </div>
            )) : <p className="text-[var(--text-muted)]">{locale === 'en' ? 'No travel segments in itinerary to inspect.' : 'Lịch trình chưa có đoạn đường để kiểm tra.'}</p>}
          </div>
          <p className="mt-2 text-[var(--text-muted)]">
            {locale === 'en'
              ? 'The flood model is trained on simulation data without per-segment ground truth verification. Flooded vs non-flooded status cannot be definitively confirmed.'
              : 'Mô hình Flood hiện có được huấn luyện từ dữ liệu mô phỏng và chưa có dữ liệu đã xác minh theo từng chặng. Vì vậy chưa thể kết luận đoạn nào ngập hoặc nói rằng không có đoạn ngập.'}
          </p>
        </>
      ) : (
        <p className="mt-1 text-[var(--text-muted)]">
          {locale === 'en'
            ? 'No rain forecast for this date. However, route safety during sudden rain cannot be guaranteed.'
            : 'Dự báo ngày này không có mưa. Điều đó không chứng minh tuyến đường sẽ an toàn nếu thời tiết chuyển mưa.'}
        </p>
      )}
    </div>
  )
}

export default function Timeline({ itinerary, places, budget, busy = false, changed = [], onDisrupt,
  versions = [], version = null, latest = null, pins = [], onView, onRestore, onPin, onExportPdf,
  onOpenPlanner, selected = null, onSelect, children }: {
  itinerary: Itinerary | null; places: Record<string, Place>; budget: number | null; changed?: [number, number][]
  busy?: boolean; onDisrupt?: (d: DisruptionReq) => void
  versions?: number[]; version?: number | null; latest?: number | null; pins?: number[]
  onView?: (v: number) => void; onRestore?: () => void; onPin?: (placeId: number, pinned: boolean) => void
  onExportPdf?: () => void
  onOpenPlanner?: () => void
  selected?: Selected; onSelect?: (s: Selected) => void
  children?: ReactNode
}) {
  const { t, locale, formatCurrency } = useTranslation()
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    root.current?.querySelector('[data-selected]')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [selected])
  if (!itinerary) return null
  const stay = itinerary.stay_place_id != null ? places[itinerary.stay_place_id] : undefined
  const old = viewingOld(version, latest)

  const getWeatherLabel = (code: number | null | undefined) => {
    if (code == null) return t('weather.conditionSky')
    const key = `weather.code${code}`
    const res = t(key)
    return res !== key ? res : `${t('weather.conditionSky')} ${code}`
  }

  return (
    <div ref={root} className="min-h-0 flex-1 overflow-y-auto p-4">
      {children}
      {(versions.length > 1 || (version != null && onExportPdf)) && (
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          {versions.length > 1 && (
            <nav aria-label={t('itinerary.versionHistory')} className="flex flex-wrap items-center gap-1 text-xs">
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
              {t('quote.print')}
            </button>
          )}
        </div>
      )}
      {old && (
        <div role="status" className="mb-3 flex flex-wrap items-center gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          <span>{locale === 'en' ? `Viewing version ${version}` : `Đang xem bản ${version}`}</span>
          <button disabled={busy} onClick={onRestore}
            className="rounded bg-amber-600 px-2 py-0.5 text-white disabled:opacity-50">
            {locale === 'en' ? 'Restore this version' : 'Quay lại bản này'}
          </button>
          <button disabled={busy} onClick={() => latest != null && onView?.(latest)}
            className="rounded border border-amber-600 px-2 py-0.5 disabled:opacity-50">
            {locale === 'en' ? 'To latest version' : 'Về bản mới nhất'}
          </button>
        </div>
      )}
      <div className="mb-3 rounded-xl bg-[var(--bg-surface)] p-3 shadow-sm">
        <div className="text-sm text-[var(--text-muted)]">{t('chat.estTotalCost')}</div>
        <div className="text-2xl font-semibold">{formatCurrency(itinerary.total_cost)}</div>
        {budget != null && <div className="text-xs text-[var(--text-muted)]">{t('tripChat.budget', { amount: formatCurrency(budget) })} · {locale === 'en' ? 'excludes city transit' : 'chưa gồm vé đến/rời thành phố'}</div>}
        {stay && (
          <button type="button" onClick={() => onSelect?.('stay')}
            className={`mt-1 block text-left text-xs hover:underline ${selected === 'stay' ? 'font-semibold text-[var(--text-main)]' : ''}`}>
            {t('tripChat.accommodation', { name: stay.name })}
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
              <span className="ml-1 text-[var(--text-muted)]">{t('tripChat.retainGoal', { pct: Math.round(itinerary.retention * 100) })}</span>
            )}
          </div>
        )}
        {onOpenPlanner && (
          <button type="button" onClick={onOpenPlanner}
            className="mt-3 inline-flex items-center gap-2 rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-800">
            {t('tripChat.openInPlanner')}
          </button>
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
              {t('tripChat.dayTitle', { day: i + 1 })}{day.date && ` · ${day.date}`}{day.rain_chance != null && ` · ${locale === 'en' ? `rain ${day.rain_chance}%` : `mưa ${day.rain_chance}%`}`}
            </h2>
            {!old && onDisrupt && rainable(day, places, pins) && (
              <button type="button" disabled={busy} onClick={() => onDisrupt({ kind: 'rain', day_index: i })}
                className="rounded border border-sky-300 px-2 py-0.5 text-xs text-sky-800 hover:bg-sky-50 disabled:opacity-40">
                {t('weather.rainSimulation')}
              </button>
            )}
          </div>
          <div className="mb-2 rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] p-3 text-xs">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-semibold text-[var(--text-main)]">
                  {t('weather.forecastTitle')}{day.weather_forecast?.location && ` · ${day.weather_forecast.location}`}
                </div>
                {day.weather_forecast ? (
                  <p className="mt-1 text-[var(--text-muted)]">
                    {getWeatherLabel(day.weather_forecast.weather_code)}
                    {day.weather_forecast.temperature_2m_min_c != null && day.weather_forecast.temperature_2m_max_c != null
                      && ` · ${Math.round(day.weather_forecast.temperature_2m_min_c)}–${Math.round(day.weather_forecast.temperature_2m_max_c)}°C`}
                    {' · '}{locale === 'en' ? `rain ${day.weather_forecast.precipitation_probability_pct}%` : `mưa ${day.weather_forecast.precipitation_probability_pct}%`}
                    {day.weather_forecast.precipitation_sum_mm != null && (locale === 'en' ? ` · approx ${day.weather_forecast.precipitation_sum_mm.toFixed(1)} mm` : ` · khoảng ${day.weather_forecast.precipitation_sum_mm.toFixed(1)} mm`)}
                  </p>
                ) : !day.date ? (
                  <p className="mt-1 text-[var(--text-muted)]">
                    {t('weather.forecastNoDate')}
                  </p>
                ) : day.rain_chance != null ? (
                  <p className="mt-1 text-[var(--text-muted)]">{t('weather.rainChanceOnly', { chance: day.rain_chance })}</p>
                ) : (
                  <p className="mt-1 text-[var(--text-muted)]">{t('weather.forecastUnavailable')}</p>
                )}
              </div>
            </div>
            <FloodRouteNotice day={day} places={places} />
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
                  {meal && <div className="mb-0.5 inline-flex items-center gap-1.5 text-xs font-medium text-amber-700"><Utensils size={13} aria-hidden="true" /> {meal}</div>}
                  <div className="flex justify-between gap-2">
                    <button type="button" className="min-w-0 truncate text-left font-semibold"
                      onClick={(e) => { e.stopPropagation(); onSelect?.({ day: i, stop: j }) }}>
                      {s.start_time} · {p?.name}
                    </button>
                    <span className="shrink-0 tabular-nums">{formatCurrency(s.est_cost)}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-[var(--text-muted)]">{s.reason}</p>
                  {p && (
                    <div className="mt-2">
                      <span className="inline-flex rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                        Ranker: {p.rank_position != null
                          ? t('tripChat.rankPosition', { rank: p.rank_position, total: p.rank_candidate_count ?? '—' })
                          : t('tripChat.unranked')}
                      </span>
                    </div>
                  )}
                  {!old && (onPin || (onDisrupt && on)) && (
                    <div className="mt-2 flex flex-wrap gap-2 text-xs" onClick={(e) => e.stopPropagation()}>
                      {onPin && (
                        <button type="button" disabled={busy} aria-pressed={pinned}
                          title={pinned ? t('tripChat.unpinTooltip') : t('tripChat.pinTooltip')}
                          onClick={() => onPin(s.place_id, !pinned)}
                          className={`rounded border px-2 py-0.5 disabled:opacity-40 ${
                            pinned ? 'border-[var(--border)] bg-emerald-700 text-white' : 'border-stone-300 hover:bg-[var(--bg-elevated)]'}`}>
                          <Pin size={13} aria-hidden="true" /> {pinned ? t('tripChat.pinned') : t('tripChat.pin')}
                        </button>
                      )}
                      {onDisrupt && on && (['closed', 'disliked'] as const).map((k) => (
                        <button key={k} type="button" disabled={busy || pinned}
                          title={pinned ? (locale === 'en' ? 'Unpin to swap' : 'Bỏ ghim để đổi') : undefined}
                          onClick={() => onDisrupt({ kind: k, day_index: i, stop_index: j })}
                          className="rounded border border-stone-300 px-2 py-0.5 hover:bg-[var(--bg-elevated)] disabled:opacity-40">
                          {k === 'closed' ? t('tripChat.reportClosed') : t('tripChat.swapPlace')}
                        </button>
                      ))}
                      {onDisrupt && on && (
                        <span className="flex items-center gap-1">
                          {t('tripChat.imLate')}
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
            {t('tripChat.travelSummary', {
              dist: `${day.legs.reduce((a, l) => a + l.distance_km, 0).toFixed(1)} km`,
              cost: formatCurrency(day.legs.reduce((a, l) => a + l.cost, 0)),
            })}
          </p>
        </section>
      ))}
    </div>
  )
}
