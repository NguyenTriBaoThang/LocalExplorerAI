import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CalendarPlus, ChevronLeft, ChevronRight, Users } from 'lucide-react'
import { Button, Card, cx, IconButton, PageHeader, Spinner, StatusBadge } from '../../components/ui'
import { partnerApi } from '../../lib/api'
import type { Experience } from '../../lib/types'

const ROW = 48
const WEEKDAYS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']
const TONE: Record<string, string> = {
  open: 'border-brand-300 bg-brand-50 text-brand-900', available: 'border-brand-300 bg-brand-50 text-brand-900',
  full: 'border-amber-300 bg-amber-50 text-amber-900', cancelled: 'border-slate-200 bg-slate-50 text-slate-400 line-through',
}

function startOfWeek(date: Date) {
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7))
  return d
}

export function PartnerCalendarPage() {
  const [experiences, setExperiences] = useState<Experience[] | null>(null)
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()))
  useEffect(() => { partnerApi.experiences().then(setExperiences).catch(() => setExperiences([])) }, [])

  const days = Array.from({ length: 7 }, (_, i) => new Date(weekStart.getTime() + i * 86_400_000))
  const slots = useMemo(() => (experiences ?? []).flatMap((experience) => experience.slots.map((slot) => ({ ...slot, title: experience.title }))), [experiences])
  // 07:00–21:00 by default, widened so early or late slots are never hidden.
  const HOURS = useMemo(() => {
    const week = slots.filter((slot) => { const t = new Date(slot.start_at).getTime(); return t >= weekStart.getTime() && t < weekStart.getTime() + 7 * 86_400_000 })
    const first = Math.min(7, ...week.map((slot) => new Date(slot.start_at).getHours()))
    const last = Math.max(21, ...week.map((slot) => { const end = new Date(slot.end_at); return Math.min(23, end.getHours() - (end.getMinutes() === 0 ? 1 : 0)) }))
    return Array.from({ length: last - first + 1 }, (_, i) => i + first)
  }, [slots, weekStart])
  const shift = (weeks: number) => setWeekStart(new Date(weekStart.getTime() + weeks * 7 * 86_400_000))
  const today = new Date().toDateString()
  const range = `${days[0].toLocaleDateString('vi-VN', { day: 'numeric', month: 'short' })} – ${days[6].toLocaleDateString('vi-VN', { day: 'numeric', month: 'short', year: 'numeric' })}`
  const weekCount = slots.filter((slot) => { const t = new Date(slot.start_at).getTime(); return t >= weekStart.getTime() && t < weekStart.getTime() + 7 * 86_400_000 }).length

  return (
    <>
      <PageHeader title="Lịch slot" description="Xem các khung giờ đã mở theo tuần."
        actions={<Link to="/partner/experiences"><Button icon={CalendarPlus}>Mở slot</Button></Link>} />
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3">
          <div className="flex items-center gap-2">
            <IconButton icon={ChevronLeft} label="Tuần trước" onClick={() => shift(-1)} />
            <IconButton icon={ChevronRight} label="Tuần sau" onClick={() => shift(1)} />
            <Button size="sm" variant="secondary" onClick={() => setWeekStart(startOfWeek(new Date()))}>Hôm nay</Button>
            <p className="ml-2 text-sm font-semibold text-slate-900">{range}</p>
          </div>
          <p className="text-sm text-slate-500">{weekCount} slot trong tuần</p>
        </div>
        {!experiences ? <Spinner /> : (
          <div className="overflow-x-auto">
            <div className="grid min-w-[860px]" style={{ gridTemplateColumns: '56px repeat(7, minmax(0, 1fr))' }}>
              <div />
              {days.map((day, i) => (
                <div key={i} className={cx('border-l border-slate-100 py-2.5 text-center', day.toDateString() === today && 'bg-brand-50/60')}>
                  <p className="text-xs text-slate-500">{WEEKDAYS[i]}</p>
                  <p className={cx('mx-auto mt-0.5 flex h-7 w-7 items-center justify-center rounded-full text-sm font-semibold', day.toDateString() === today ? 'bg-brand-600 text-white' : 'text-slate-900')}>{day.getDate()}</p>
                </div>
              ))}
              <div className="relative border-t border-slate-100">
                {HOURS.map((hour) => <div key={hour} style={{ height: ROW }} className="pr-2 text-right text-[11px] text-slate-400"><span className="relative -top-2">{hour}:00</span></div>)}
              </div>
              {days.map((day, i) => {
                const daySlots = slots.filter((slot) => new Date(slot.start_at).toDateString() === day.toDateString())
                return (
                  <div key={i} className={cx('relative border-l border-t border-slate-100', day.toDateString() === today && 'bg-brand-50/30')}>
                    {HOURS.map((hour) => <div key={hour} style={{ height: ROW }} className="border-b border-dashed border-slate-100" />)}
                    {daySlots.map((slot) => {
                      const start = new Date(slot.start_at)
                      const end = new Date(slot.end_at)
                      const top = ((start.getHours() + start.getMinutes() / 60) - HOURS[0]) * ROW
                      const height = Math.max(((end.getTime() - start.getTime()) / 3_600_000) * ROW - 3, 26)
                      if (top < 0 || top > HOURS.length * ROW) return null
                      return (
                        <div key={slot.id} title={`${slot.title} · ${slot.available_reported ?? '?'}/${slot.capacity_total ?? '?'} chỗ`}
                          className={cx('absolute inset-x-1 overflow-hidden rounded-md border px-2 py-1 text-xs shadow-sm', TONE[slot.status] ?? 'border-slate-200 bg-white')}
                          style={{ top: top + 1, height }}>
                          <p className="truncate font-semibold">{slot.title}</p>
                          <p className="flex items-center gap-1 opacity-80">{start.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })} · <Users className="h-3 w-3" />{slot.available_reported ?? '?'}/{slot.capacity_total ?? '?'}</p>
                        </div>
                      )
                    })}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </Card>
      <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1.5"><StatusBadge status="open" /> còn chỗ</span>
        <span className="inline-flex items-center gap-1.5"><StatusBadge status="full" /> hết chỗ</span>
        <span className="inline-flex items-center gap-1.5"><StatusBadge status="cancelled" /> đã hủy</span>
      </div>
    </>
  )
}
