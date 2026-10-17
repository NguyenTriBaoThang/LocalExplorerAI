import { Fragment, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, CalendarCheck, ClipboardCheck, Eye, Timer, UserPlus, Users } from 'lucide-react'
import { BarChart, BarList, Delta, Legend, LineChart, ShareBar, SERIES_COLORS } from '../../components/charts'
import { Avatar, Button, Card, CardHeader, EmptyState, PageHeader, Spinner, StatCard, Tabs } from '../../components/ui'
import { adminApi } from '../../lib/api'
import { BUSINESS_TYPES, timeAgo } from '../../lib/format'
import type { AdminAnalytics, AdminDashboard, AdminProvider } from '../../lib/types'

type Range = '7' | '30' | '90'
const number = new Intl.NumberFormat('vi-VN')
const WEEKDAYS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']

export function AdminOverviewPage() {
  const [range, setRange] = useState<Range>('30')
  const [analytics, setAnalytics] = useState<AdminAnalytics | null>(null)
  const [stats, setStats] = useState<AdminDashboard | null>(null)
  const [queue, setQueue] = useState<AdminProvider[]>([])

  useEffect(() => {
    adminApi.dashboard().then(setStats).catch(() => undefined)
    adminApi.providers({ status: 'pending', limit: 5, offset: 0 }).then((page) => setQueue(page.items)).catch(() => undefined)
  }, [])
  useEffect(() => { setAnalytics(null); adminApi.analytics(Number(range)).then(setAnalytics).catch(() => undefined) }, [range])

  const traffic = analytics ? [
    { name: 'Lượt xem trang', values: analytics.series.map((p) => p.pageviews) },
    { name: 'Khách truy cập', values: analytics.series.map((p) => p.visitors) },
  ] : []

  return (
    <>
      <PageHeader title="Tổng quan" description="Lưu lượng truy cập, người dùng và hoạt động trên toàn hệ thống."
        actions={<><Tabs value={range} onChange={setRange} items={[{ value: '7', label: '7 ngày' }, { value: '30', label: '30 ngày' }, { value: '90', label: '90 ngày' }]} /></>} />

      {!analytics ? <Spinner /> : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            <StatCard label="Khách truy cập" value={number.format(analytics.totals.visitors)} icon={Users} hint={<Delta value={analytics.change.visitors} />} />
            <StatCard label="Lượt xem trang" value={number.format(analytics.totals.pageviews)} icon={Eye} tone="violet" hint={<Delta value={analytics.change.pageviews} />} />
            <StatCard label="Người dùng mới" value={number.format(analytics.totals.new_users)} icon={UserPlus} tone="green" hint={<Delta value={analytics.change.new_users} />} />
            <StatCard label="Đặt chỗ" value={number.format(analytics.totals.bookings)} icon={CalendarCheck} tone="amber" hint={<Delta value={analytics.change.bookings} />} />
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader title="Lưu lượng truy cập" description={`${range} ngày gần nhất`} actions={<Legend series={traffic} />} />
              <div className="px-3 pb-4 pt-2"><LineChart labels={analytics.series.map((p) => p.label)} series={traffic} height={280} /></div>
            </Card>
            <Card>
              <CardHeader title="Chỉ số phiên" />
              <div className="space-y-5 p-5">
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-700"><Timer className="h-5 w-5" /></span>
                  <div>
                    <p className="text-xs text-slate-500">Thời gian trung bình / phiên</p>
                    <p className="text-lg font-semibold text-slate-900">{Math.floor(analytics.totals.avg_session_seconds / 60)} phút {analytics.totals.avg_session_seconds % 60} giây</p>
                  </div>
                </div>
                <div>
                  <p className="mb-2 text-xs font-medium text-slate-500">Thiết bị</p>
                  <ShareBar parts={analytics.devices} showCounts={false} />
                </div>
                <div>
                  <p className="mb-2 text-xs font-medium text-slate-500">Nguồn truy cập</p>
                  <ShareBar parts={analytics.sources} showCounts={false} />
                </div>
              </div>
            </Card>
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader title="Người dùng mới mỗi ngày" />
              <div className="px-3 pb-4 pt-2"><BarChart name="Người dùng mới" labels={analytics.series.map((p) => p.label)} values={analytics.series.map((p) => p.new_users)} color={SERIES_COLORS[2]} /></div>
            </Card>
            <Card>
              <CardHeader title="Truy cập theo giờ trong ngày" description="Trung bình lượt xem theo khung giờ" />
              <div className="px-3 pb-4 pt-2"><BarChart name="Lượt xem" labels={analytics.hours.map((_, h) => `${h}h`)} values={analytics.hours} /></div>
            </Card>
          </div>

          <Card className="mt-6">
            <CardHeader title="Đặt chỗ theo thứ và giờ" description={`Số booking được tạo trong ${range} ngày gần nhất · giờ Việt Nam (UTC+7)`} />
            <div className="overflow-x-auto px-5 pb-5">
              <div className="min-w-[650px]">
                <div className="grid gap-1" style={{ gridTemplateColumns: '42px repeat(24, minmax(18px, 1fr))' }}>
                  <span aria-hidden="true" />
                  {Array.from({ length: 24 }, (_, hour) => <span key={hour} className="text-center text-[10px] text-slate-500">{hour % 3 === 0 ? `${String(hour).padStart(2, '0')}h` : ''}</span>)}
                  {analytics.booking_heatmap.map((hours, weekday) => <Fragment key={`day-${weekday}`}>
                    <span className="flex items-center text-xs font-medium text-slate-500">{WEEKDAYS[weekday]}</span>
                    {hours.map((count, hour) => {
                      const intensity = analytics.booking_heatmap_max ? count / analytics.booking_heatmap_max : 0
                      return <span key={`${weekday}-${hour}`} title={`${WEEKDAYS[weekday]} ${String(hour).padStart(2, '0')}:00 · ${number.format(count)} booking`} aria-label={`${WEEKDAYS[weekday]} ${hour}:00, ${count} booking`}
                        className="h-6 rounded-sm border border-white/5"
                        style={{ backgroundColor: count === 0 ? 'rgba(148, 163, 184, 0.08)' : `rgba(16, 185, 129, ${0.2 + intensity * 0.75})` }} />
                    })}
                  </Fragment>)}
                </div>
                <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500">
                  <span>Ít booking</span>
                  <span>Nhiều booking</span>
                </div>
              </div>
            </div>
          </Card>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader title="Trang được xem nhiều" />
              <div className="p-5">{analytics.top_pages.length === 0 ? <p className="py-6 text-center text-sm text-slate-500">Chưa có lượt xem nào.</p> : <BarList items={analytics.top_pages.map((page) => ({ label: <><span className="font-medium">{page.title}</span> <span className="text-slate-400">{page.path}</span></>, value: page.views }))} />}</div>
            </Card>
            <Card>
              <CardHeader title="Địa điểm được xem nhiều" actions={<Link to="/admin/places" className="text-sm font-medium text-brand-600 hover:text-brand-700">Quản lý</Link>} />
              <div className="p-5">{analytics.top_places.length === 0 ? <p className="py-6 text-center text-sm text-slate-500">Chưa có lượt xem địa điểm nào.</p> : <BarList color={SERIES_COLORS[1]} items={analytics.top_places.map((place) => ({ label: <><span className="font-medium">{place.name}</span> <span className="text-slate-400">· {place.district}</span></>, value: place.views }))} />}</div>
            </Card>
          </div>
        </>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Card>
          <CardHeader title="Hàng chờ duyệt đối tác" description="Hồ sơ gửi sớm nhất hiển thị trước."
            actions={<Link to="/admin/partners"><Button size="sm" variant="secondary">Xem tất cả <ArrowRight className="h-4 w-4" /></Button></Link>} />
          {queue.length === 0 ? (
            <EmptyState icon={ClipboardCheck} title="Không còn hồ sơ nào chờ duyệt" />
          ) : (
            <ul className="divide-y divide-slate-100">
              {queue.map((provider) => (
                <li key={provider.id}>
                  <Link to={`/admin/partners?status=pending&open=${provider.id}`} className="flex items-center gap-4 px-5 py-3.5 transition hover:bg-slate-50">
                    <Avatar name={provider.name} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-900">{provider.name}</p>
                      <p className="truncate text-xs text-slate-500">{provider.business_type ? BUSINESS_TYPES[provider.business_type] : 'Đối tác'} · {provider.contact_email}</p>
                    </div>
                    <span className="hidden text-xs text-slate-500 sm:block">Gửi {timeAgo(provider.applied_at)}</span>
                    <ArrowRight className="h-4 w-4 text-slate-400" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <CardHeader title="Hệ thống" description="Số liệu thật từ cơ sở dữ liệu" />
          {!stats ? <Spinner /> : (
            <dl className="divide-y divide-slate-100 text-sm">
              {([
                ['Người dùng', stats.users], ['Đối tác', stats.providers], ['Hồ sơ đối tác chờ duyệt', stats.pending_partner_applications],
                ['Trải nghiệm chờ kiểm duyệt', stats.pending_experiences], ['Địa điểm chờ kiểm duyệt', stats.pending_pois], ['Minh chứng chờ duyệt', stats.pending_evidence],
              ] as Array<[string, number]>).map(([label, value]) => (
                <div key={label} className="flex items-center justify-between px-5 py-2.5"><dt className="text-slate-500">{label}</dt><dd className="font-semibold text-slate-900">{number.format(value)}</dd></div>
              ))}
            </dl>
          )}
        </Card>
      </div>
    </>
  )
}
