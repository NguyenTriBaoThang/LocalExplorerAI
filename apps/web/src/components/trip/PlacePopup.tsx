import { vnd, type Place } from '../../api/trips'
import { kindStyle, openToday } from './place'
import PlaceThumb from './PlaceThumb'
import LocationConditions from './LocationConditions'

const CHIP = 'rounded-full border border-[var(--border)] bg-[var(--bg-elevated)] px-2 py-0.5'

export default function PlacePopup({ place, date, pinned, onPin }: {
  place: Place; date: string | null; pinned: boolean; onPin?: (pinned: boolean) => void
}) {
  const hours = place.kind === 'cho-o' ? null : openToday(place.open_hours, date)
  return (
    <div className="max-h-[70vh] w-[min(22rem,calc(100vw-2rem))] overflow-y-auto bg-[var(--bg-surface)] font-sans text-[var(--text-main)]">
      <PlaceThumb kind={place.kind} photo={place.photo_url} className="h-24 w-full text-4xl" />
      <div className="grid gap-2 p-3">
        <h3 className="text-[15px] font-bold leading-snug">{place.name}</h3>
        <div className="flex flex-wrap gap-1.5 text-xs tabular-nums">
          <span className={CHIP}>{kindStyle(place.kind).label}</span>
          <span className={CHIP}>{place.price === 0 ? 'Miễn phí' : vnd(place.price)}</span>
          <span className={CHIP}>{place.outdoor ? 'Ngoài trời' : 'Trong nhà'}</span>
          {hours && <span className={`${CHIP} border-[var(--border)] bg-[var(--bg-surface)] font-semibold text-[var(--text-main)]`}>{hours}</span>}
        </div>
        {place.description && <p className="text-xs leading-relaxed text-[var(--text-muted)]">{place.description}</p>}
        <LocationConditions latitude={place.lat} longitude={place.lon} />
        <div className="flex items-center">
          <span className="inline-flex rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-700">
            Ranker: {place.rank_position != null
              ? `hạng ${place.rank_position}/${place.rank_candidate_count ?? '—'}`
              : 'chưa xếp hạng'}
          </span>
        </div>
        {onPin && (
          <button type="button" aria-pressed={pinned} onClick={() => onPin(!pinned)}
            className={`rounded-lg border px-3 py-1.5 text-sm font-semibold ${
              pinned ? 'border-[var(--border)] bg-emerald-700 text-white' : 'border-stone-300 hover:bg-[var(--bg-elevated)]'}`}>
            📌 {pinned ? 'Đã ghim' : 'Ghim'}
          </button>
        )}
      </div>
    </div>
  )
}
