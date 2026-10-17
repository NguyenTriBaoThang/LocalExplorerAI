import type { Itinerary, Place } from './api'

const WEEKDAYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']  // theo Date.getUTCDay(), khoá giống server
const span = (h: [string, string]) => (h[0] === '00:00' && h[1] === '24:00' ? null : `${h[0]}–${h[1]}`)

/** Dòng giờ mở cho popup; null = không đủ dữ kiện, ẩn dòng. */
export function openToday(hours: Place['open_hours'], date: string | null): string | null {
  if (!hours) return null
  if (Object.keys(hours).length === 0) return 'Mở cả ngày'
  if (date) {
    const h = hours[WEEKDAYS[new Date(date + 'T00:00:00Z').getUTCDay()]]
    if (h === undefined) return null
    if (h === null) return 'Hôm nay đóng cửa'
    const s = span(h)
    return s ? `Mở hôm nay ${s}` : 'Mở cả ngày'
  }
  const all = WEEKDAYS.map((d) => hours[d])
  const first = all[0]
  if (!first || all.some((h) => !h || h[0] !== first[0] || h[1] !== first[1])) return null
  const s = span(first)
  return s ? `Mở ${s}` : 'Mở cả ngày'
}

const KINDS: Record<string, { label: string; icon: string; className: string }> = {
  cafe: { label: 'Cafe', icon: '☕', className: 'from-amber-900 to-amber-600' },
  'an-uong': { label: 'Ăn uống', icon: '🍜', className: 'from-red-800 to-orange-500' },
  'tham-quan': { label: 'Tham quan', icon: '🏞', className: 'from-emerald-900 to-emerald-500' },
  'cho-o': { label: 'Chỗ ở', icon: '🛏', className: 'from-slate-700 to-slate-500' },
  'giai-tri': { label: 'Giải trí', icon: '🎶', className: 'from-violet-800 to-fuchsia-500' },
}
const OTHER = { label: 'Địa điểm', icon: '📍', className: 'from-stone-600 to-stone-400' }
export const kindStyle = (kind: string) => KINDS[kind] ?? OTHER

export type Selected = { day: number; stop: number } | 'stay' | null

export function selectedPlace(it: Itinerary | null, sel: Selected): number | null {
  if (!it || sel == null) return null
  if (sel === 'stay') return it.stay_place_id
  return it.days[sel.day]?.stops[sel.stop]?.place_id ?? null
}

export const tourStops = (it: Itinerary) =>
  it.days.flatMap((d, day) => d.stops.map((_, stop) => ({ day, stop })))
