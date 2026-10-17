import { vnd, type Place } from '../api'
import { kindStyle, openToday } from '../place'
import PlaceThumb from './PlaceThumb'

const CHIP = 'rounded-full border border-stone-200 bg-mist px-2 py-0.5'

export default function PlacePopup({ place, date, pinned, onPin }: {
  place: Place; date: string | null; pinned: boolean; onPin?: (pinned: boolean) => void
}) {
  const hours = place.kind === 'cho-o' ? null : openToday(place.open_hours, date)
  return (
    <div className="w-64 bg-white font-sans text-stone-900">
      <PlaceThumb kind={place.kind} photo={place.photo_url} className="h-24 w-full text-4xl" />
      <div className="grid gap-2 p-3">
        <h3 className="text-[15px] font-bold leading-snug">{place.name}</h3>
        <div className="flex flex-wrap gap-1.5 text-xs tabular-nums">
          <span className={CHIP}>{kindStyle(place.kind).label}</span>
          <span className={CHIP}>{place.price === 0 ? 'Miễn phí' : vnd(place.price)}</span>
          <span className={CHIP}>{place.outdoor ? 'Ngoài trời' : 'Trong nhà'}</span>
          {hours && <span className={`${CHIP} border-pine/30 bg-pine-soft font-semibold text-pine`}>{hours}</span>}
        </div>
        {place.description && <p className="text-xs leading-relaxed text-stone-500">{place.description}</p>}
        {onPin && (
          <button type="button" aria-pressed={pinned} onClick={() => onPin(!pinned)}
            className={`rounded-lg border px-3 py-1.5 text-sm font-semibold ${
              pinned ? 'border-pine bg-pine text-white' : 'border-stone-300 hover:bg-mist'}`}>
            📌 {pinned ? 'Đã ghim' : 'Ghim'}
          </button>
        )}
      </div>
    </div>
  )
}
