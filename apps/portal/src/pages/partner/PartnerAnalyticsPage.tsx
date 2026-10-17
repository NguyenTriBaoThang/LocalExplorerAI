import { useEffect, useMemo, useState } from 'react'
import { Banknote, Eye, MousePointerClick, Star } from 'lucide-react'
import { BarList, Legend, LineChart, ShareBar } from '../../components/charts'
import { Card, CardHeader, EmptyState, PageHeader, Spinner, StatCard, Tabs } from '../../components/ui'
import { partnerApi } from '../../lib/api'
import { formatMoney } from '../../lib/format'
import type { Booking, PartnerAnalytics } from '../../lib/types'
import { usePartner } from './PartnerLayout'

type Range = '7' | '30' | '90'
const PAID = new Set(['confirmed', 'completed'])

export function PartnerAnalyticsPage() {
  const { profile } = usePartner()
  const [range, setRange] = useState<Range>('30')
  const [traffic, setTraffic] = useState<PartnerAnalytics | null>(null)
  const [bookings, setBookings] = useState<Booking[] | null>(null)

  useEffect(() => { setTraffic(null); partnerApi.analytics(Number(range)).then(setTraffic).catch(() => setTraffic({ series: [], totals: { views: 0, booking_requests: 0, conversion: 0, rating: null, reviews: 0 } })) }, [range])
  useEffect(() => { if (profile.can_publish) partnerApi.bookings().then(setBookings).catch(() => setBookings([])); else setBookings([]) }, [profile.can_publish])

  const since = Date.now() - Number(range) * 86_400_000
  const inRange = useMemo(() => (bookings ?? []).filter((b) => new Date(b.created_at).getTime() >= since), [bookings, since])
  const revenue = inRange.filter((b) => PAID.has(b.status)).reduce((sum, b) => sum + b.amount_vnd, 0)
  const byExperience = useMemo(() => {
    const map = new Map<string, number>()
    for (const b of inRange.filter((item) => PAID.has(item.status))) map.set(b.experience_title, (map.get(b.experience_title) ?? 0) + b.amount_vnd)
    return [...map.entries()].sort((a, b) => b[1] - a[1]).map(([label, value]) => ({ label, value }))
  }, [inRange])
  const outcome = [
    { label: 'Xác nhận', value: inRange.filter((b) => PAID.has(b.status) || b.status === 'awaiting_payment').length },
    { label: 'Từ chối / hủy', value: inRange.filter((b) => b.status === 'rejected' || b.status === 'cancelled').length },
    { label: 'Hết hạn', value: inRange.filter((b) => b.status === 'expired').length },
  ]

  return (
    <>
      <PageHeader title="Thống kê" description="Mức độ quan tâm của du khách và kết quả kinh doanh."
        actions={<Tabs value={range} onChange={setRange} items={[{ value: '7', label: '7 ngày' }, { value: '30', label: '30 ngày' }, { value: '90', label: '90 ngày' }]} />} />
      {!traffic || !bookings ? <Spinner /> : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            <StatCard label="Lượt xem trải nghiệm" value={traffic.totals.views.toLocaleString('vi-VN')} icon={Eye} hint="Lượt xem trang trải nghiệm trên web" />
            <StatCard label="Yêu cầu đặt chỗ" value={traffic.totals.booking_requests} icon={MousePointerClick} tone="violet" hint={`Tỷ lệ chuyển đổi ${traffic.totals.conversion.toFixed(1)}%`} />
            <StatCard label="Doanh thu" value={formatMoney(revenue)} icon={Banknote} tone="green" hint="Từ booking đã xác nhận" />
            <StatCard label="Đánh giá trung bình" value={traffic.totals.rating === null ? '—' : `${traffic.totals.rating} ★`} icon={Star} tone="amber" hint={`${traffic.totals.reviews} đánh giá`} />
          </div>
          <Card className="mt-6">
            <CardHeader title="Lượt xem & yêu cầu đặt chỗ"
              actions={<Legend series={[{ name: 'Lượt xem', values: [] }, { name: 'Yêu cầu đặt chỗ', values: [] }]} />} />
            <div className="px-3 pb-4 pt-2">
              <LineChart labels={traffic.series.map((p) => p.label)} series={[
                { name: 'Lượt xem', values: traffic.series.map((p) => p.views) },
                { name: 'Yêu cầu đặt chỗ', values: traffic.series.map((p) => p.booking_requests) },
              ]} />
            </div>
          </Card>
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader title="Doanh thu theo trải nghiệm" />
              <div className="p-5">
                {byExperience.length === 0 ? <EmptyState icon={Banknote} title="Chưa có doanh thu trong kỳ" /> : <BarList items={byExperience} format={formatMoney} />}
              </div>
            </Card>
            <Card>
              <CardHeader title="Kết quả yêu cầu đặt chỗ" description={`${inRange.length} yêu cầu trong kỳ`} />
              <div className="p-5">{inRange.length === 0 ? <EmptyState icon={MousePointerClick} title="Chưa có yêu cầu" /> : <ShareBar parts={outcome} />}</div>
            </Card>
          </div>
        </>
      )}
    </>
  )
}
