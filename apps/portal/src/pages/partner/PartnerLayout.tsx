import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { BarChart3, CalendarCheck, CalendarDays, Compass, History, LayoutDashboard, MapPin, Star, UserCog, UserRound } from 'lucide-react'
import { PortalShell } from '../../components/PortalShell'
import { Alert, Button, Spinner, StatusBadge } from '../../components/ui'
import { errorMessage, partnerApi } from '../../lib/api'
import type { ProviderProfile } from '../../lib/types'

type PartnerContextValue = { profile: ProviderProfile; reload: () => Promise<void> }
const PartnerContext = createContext<PartnerContextValue | null>(null)

export function usePartner() {
  const value = useContext(PartnerContext)
  if (!value) throw new Error('usePartner must be used inside PartnerLayout')
  return value
}

export function PartnerLayout() {
  const [profile, setProfile] = useState<ProviderProfile | null>(null)
  const [error, setError] = useState('')
  const location = useLocation()

  const reload = useCallback(async () => {
    try {
      setProfile(await partnerApi.profile())
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [])
  useEffect(() => { void reload() }, [reload])

  if (error) return <div className="mx-auto max-w-lg p-8"><Alert tone="red" title="Không tải được hồ sơ đối tác">{error}</Alert></div>
  if (!profile) return <div className="min-h-screen"><Spinner /></div>

  return (
    <PartnerContext.Provider value={{ profile, reload }}>
      <PortalShell
        area="Portal Đối tác"
        nav={[
          { items: [
            { to: '/partner', label: 'Tổng quan', icon: LayoutDashboard, end: true },
            { to: '/partner/analytics', label: 'Thống kê', icon: BarChart3 },
          ] },
          { title: 'Kinh doanh', items: [
            { to: '/partner/experiences', label: 'Trải nghiệm & Slot', icon: Compass },
            { to: '/partner/calendar', label: 'Lịch slot', icon: CalendarDays },
            { to: '/partner/bookings', label: 'Đặt chỗ', icon: CalendarCheck },
            { to: '/partner/places', label: 'Địa điểm của tôi', icon: MapPin },
            { to: '/partner/reviews', label: 'Đánh giá', icon: Star },
          ] },
          { title: 'Tài khoản', items: [
            { to: '/partner/profile', label: 'Hồ sơ đối tác', icon: UserRound },
            { to: '/partner/activity', label: 'Nhật ký hoạt động', icon: History },
            { to: '/partner/account', label: 'Tài khoản', icon: UserCog },
          ] },
        ]}
        banner={!profile.can_publish && location.pathname !== '/partner/profile' ? <StatusBanner profile={profile} /> : undefined}
        sidebarFooter={
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="truncate text-sm font-medium text-slate-900">{profile.name}</p>
            <div className="mt-1.5"><StatusBadge status={profile.verification_status} /></div>
          </div>
        }
      />
    </PartnerContext.Provider>
  )
}

function StatusBanner({ profile }: { profile: ProviderProfile }) {
  const content = {
    pending: { tone: 'amber' as const, title: 'Hồ sơ đang chờ duyệt', text: 'Bạn có thể xem portal nhưng chưa thể tạo trải nghiệm hoặc mở slot cho đến khi hồ sơ được duyệt.' },
    rejected: { tone: 'red' as const, title: 'Hồ sơ chưa được duyệt', text: profile.review_note || 'Vui lòng cập nhật hồ sơ và gửi lại.' },
    suspended: { tone: 'red' as const, title: 'Tài khoản đối tác đang bị tạm khóa', text: profile.review_note || 'Trải nghiệm của bạn tạm thời không hiển thị với khách.' },
  }[profile.verification_status as 'pending' | 'rejected' | 'suspended']
  if (!content) return null
  return (
    <Alert tone={content.tone} title={content.title}
      action={profile.verification_status === 'rejected' ? <Link to="/partner/profile"><Button size="sm" variant="secondary">Cập nhật hồ sơ</Button></Link> : undefined}>
      {content.text}
    </Alert>
  )
}
