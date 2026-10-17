import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, CalendarCheck, CalendarClock, CheckCircle2, Circle, Clock, Compass, Inbox } from 'lucide-react'
import { Card, CardHeader, cx, EmptyState, PageHeader, Spinner, StatCard, StatusBadge, Button } from '../../components/ui'
import { partnerApi } from '../../lib/api'
import { formatDateTime, formatMoney } from '../../lib/format'
import type { Booking, Experience } from '../../lib/types'
import { usePartner } from './PartnerLayout'

export function PartnerOverviewPage() {
  const { profile } = usePartner()
  const [experiences, setExperiences] = useState<Experience[] | null>(null)
  const [bookings, setBookings] = useState<Booking[]>([])

  useEffect(() => {
    partnerApi.experiences().then(setExperiences).catch(() => setExperiences([]))
    if (profile.can_publish) partnerApi.bookings().then(setBookings).catch(() => setBookings([]))
  }, [profile.can_publish])

  const upcomingSlots = useMemo(() => (experiences ?? [])
    .flatMap((experience) => experience.slots.map((slot) => ({ ...slot, title: experience.title })))
    .filter((slot) => new Date(slot.start_at).getTime() > Date.now() && slot.status !== 'cancelled')
    .sort((a, b) => a.start_at.localeCompare(b.start_at)), [experiences])
  const pendingBookings = bookings.filter((booking) => booking.status === 'pending_provider' || booking.status === 'cancellation_requested')

  if (!experiences) return <Spinner />

  return (
    <>
      <PageHeader title={`Chào mừng, ${profile.name}`} description="Tổng quan hoạt động của cơ sở bạn trên Local Explorer." />
      {!profile.can_publish && <OnboardingChecklist status={profile.verification_status} hasExperience={experiences.length > 0} />}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard label="Trải nghiệm" value={experiences.length} icon={Compass} hint={`${experiences.filter((e) => e.verification_status === 'verified').length} đã duyệt`} />
        <StatCard label="Slot sắp tới" value={upcomingSlots.length} icon={CalendarClock} tone="violet" />
        <StatCard label="Cần xử lý" value={pendingBookings.length} icon={Inbox} tone="amber" hint="Yêu cầu đặt chỗ / hủy" />
        <StatCard label="Đã xác nhận" value={bookings.filter((b) => b.status === 'confirmed').length} icon={CalendarCheck} tone="green" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Slot sắp tới" actions={<Link to="/partner/experiences" className="text-sm font-medium text-brand-600 hover:text-brand-700">Quản lý</Link>} />
          {upcomingSlots.length === 0
            ? <EmptyState icon={CalendarClock} title="Chưa có slot nào" description="Mở slot để khách có thể đặt chỗ trải nghiệm của bạn." />
            : (
              <ul className="divide-y divide-slate-100">
                {upcomingSlots.slice(0, 6).map((slot) => (
                  <li key={slot.id} className="flex items-center justify-between gap-4 px-5 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-900">{slot.title}</p>
                      <p className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500"><Clock className="h-3.5 w-3.5" /> {formatDateTime(slot.start_at)}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-slate-600">{slot.available_reported ?? '?'}/{slot.capacity_total ?? '?'}</span>
                      <StatusBadge status={slot.status} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
        </Card>
        <Card>
          <CardHeader title="Yêu cầu cần xử lý" actions={<Link to="/partner/bookings" className="text-sm font-medium text-brand-600 hover:text-brand-700">Xem tất cả</Link>} />
          {pendingBookings.length === 0
            ? <EmptyState icon={Inbox} title="Không có yêu cầu nào" description="Yêu cầu đặt chỗ mới sẽ xuất hiện ở đây." />
            : (
              <ul className="divide-y divide-slate-100">
                {pendingBookings.slice(0, 6).map((booking) => (
                  <li key={booking.id} className="flex items-center justify-between gap-4 px-5 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-900">{booking.experience_title}</p>
                      <p className="mt-0.5 text-xs text-slate-500">{booking.quantity} khách · {formatMoney(booking.amount_vnd)} · {formatDateTime(booking.slot_start_at)}</p>
                    </div>
                    <StatusBadge status={booking.status} />
                  </li>
                ))}
              </ul>
            )}
        </Card>
      </div>
    </>
  )
}

function OnboardingChecklist({ status, hasExperience }: { status: string; hasExperience: boolean }) {
  const steps = [
    { label: 'Tạo tài khoản & gửi hồ sơ', done: true },
    { label: 'Đội ngũ Local Explorer duyệt hồ sơ', done: !['pending', 'rejected', 'suspended'].includes(status), current: status === 'pending' || status === 'rejected' },
    { label: 'Tạo trải nghiệm đầu tiên', done: hasExperience },
    { label: 'Mở slot để nhận khách', done: false },
  ]
  return (
    <Card className="mb-6 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">Bắt đầu với Local Explorer</p>
          <p className="mt-0.5 text-sm text-slate-500">Hoàn thành các bước sau để trải nghiệm của bạn xuất hiện với du khách.</p>
        </div>
        {status === 'rejected' && <Link to="/partner/profile"><Button size="sm" variant="secondary">Cập nhật hồ sơ <ArrowRight className="h-4 w-4" /></Button></Link>}
      </div>
      <ol className="mt-5 grid gap-3 sm:grid-cols-4">
        {steps.map((step, index) => (
          <li key={step.label} className={cx('flex items-start gap-2.5 rounded-lg border p-3 text-sm',
            step.done ? 'border-emerald-200 bg-emerald-50/60' : step.current ? 'border-amber-200 bg-amber-50/60' : 'border-slate-200')}>
            {step.done ? <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" /> : <Circle className={cx('h-5 w-5 shrink-0', step.current ? 'text-amber-500' : 'text-slate-300')} />}
            <span className={step.done ? 'text-slate-700' : 'text-slate-600'}><span className="font-medium">Bước {index + 1}.</span> {step.label}</span>
          </li>
        ))}
      </ol>
    </Card>
  )
}
