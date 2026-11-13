import { type GroupReview } from '../../api/trips'
import { useTranslation } from '../../i18n'

export default function GroupReviewPanel({ review, busy, stale = false, onApply, onCancel }: {
  review: GroupReview; busy: boolean; stale?: boolean; onApply: () => void; onCancel: () => void
}) {
  const { t, formatCurrency } = useTranslation()

  const changedStops = review.changed.map(([dayIndex, stopIndex]) => {
    const stop = review.itinerary.days[dayIndex]?.stops[stopIndex]
    const place = stop ? review.places[stop.place_id] : undefined
    return stop ? `${t('tripChat.dayTitle', { day: dayIndex + 1 })} · ${stop.start_time} · ${place?.name ?? `Stop ${stop.place_id}`}` : null
  }).filter((label): label is string => label != null)

  return (
    <section aria-label={t('tripChat.groupReviewTitle')} className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)]/50 p-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-[var(--text-main)]">{t('tripChat.groupReviewTitle')}</h3>
          <p className="mt-0.5 text-xs text-[var(--text-muted)]">
            {t('tripChat.sourceBase', { source: review.source_version, base: review.base_version })}
          </p>
        </div>
        {review.source_is_old && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] text-amber-900">{t('tripChat.outdatedBase')}</span>}
      </div>
      {stale && (
        <p role="status" className="mt-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-900">
          {t('tripChat.outdatedBaseWarning')}
        </p>
      )}
      <p className="mt-2">{review.summary}</p>
      <div className="mt-3 grid gap-2">
        <div>
          <h4 className="text-xs font-semibold text-[var(--text-muted)]">{t('tripChat.changedStops')}</h4>
          {changedStops.length > 0
            ? <ul className="mt-1 list-disc pl-5">{changedStops.map((label) => <li key={label}>{label}</li>)}</ul>
            : <p className="mt-1 text-xs text-[var(--text-muted)]">{t('tripChat.noChangedStops')}</p>}
        </div>
        {review.unresolved_feedback.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-amber-800">{t('tripChat.unresolvedDiscussions')}</h4>
            <ul className="mt-1 list-disc pl-5 text-xs text-amber-900">
              {review.unresolved_feedback.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}
            </ul>
          </div>
        )}
        <div className="rounded-lg bg-[var(--bg-surface)] p-2">
          <div className="flex justify-between gap-2 text-xs text-[var(--text-muted)]">
            <span>{t('tripChat.projectedTotalCost')}</span><span className="font-semibold text-[var(--text-main)]">{formatCurrency(review.itinerary.total_cost)}</span>
          </div>
          <div className="mt-2 text-xs">
            <h4 className="font-semibold text-[var(--text-muted)]">Conflict</h4>
            {review.itinerary.conflicts.length > 0
              ? <ul className="mt-1 list-disc pl-5 text-red-700">
                {review.itinerary.conflicts.map((conflict, index) => <li key={`${index}-${conflict.message}`}>{conflict.message}</li>)}
              </ul>
              : <p className="mt-1 text-[var(--text-muted)]">{t('tripChat.noConflicts')}</p>}
          </div>
        </div>
      </div>
      <div className="mt-3 flex justify-end gap-2">
        <button type="button" disabled={busy} onClick={onCancel}
          className="rounded-lg border border-stone-300 bg-[var(--bg-surface)] px-3 py-1.5 text-xs font-semibold disabled:opacity-50">
          {t('common.cancel')}
        </button>
        <button type="button" disabled={busy || stale} onClick={onApply}
          className="rounded-lg bg-[var(--bg-surface)] px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50">
          {t('itinerary.applyProposal')}
        </button>
      </div>
    </section>
  )
}
