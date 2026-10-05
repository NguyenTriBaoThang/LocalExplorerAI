import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { Building2, FileText, History, KeyRound, LayoutDashboard, MapPinned, UserCog, Users } from 'lucide-react'
import { PortalShell } from '../../components/PortalShell'
import { adminApi } from '../../lib/api'

const PendingContext = createContext<{ pending: number; refreshPending: () => void }>({ pending: 0, refreshPending: () => undefined })
export const usePendingPartners = () => useContext(PendingContext)

export function AdminLayout() {
  const [pending, setPending] = useState(0)
  const refreshPending = useCallback(() => {
    adminApi.dashboard().then((data) => setPending(data.pending_partner_applications)).catch(() => undefined)
  }, [])
  useEffect(refreshPending, [refreshPending])

  return (
    <PendingContext.Provider value={{ pending, refreshPending }}>
      <PortalShell
        area="Portal Quản trị"
        nav={[
          { items: [{ to: '/admin', label: 'Tổng quan', icon: LayoutDashboard, end: true }] },
          { title: 'Quản lý', items: [
            { to: '/admin/partners', label: 'Đối tác', icon: Building2, badge: pending },
            { to: '/admin/users', label: 'Người dùng', icon: Users },
            { to: '/admin/rbac', label: 'Phân quyền', icon: KeyRound },
          ] },
          { title: 'Nội dung', items: [
            { to: '/admin/places', label: 'Địa điểm & Danh thắng', icon: MapPinned },
            { to: '/admin/content', label: 'Nội dung website', icon: FileText },
          ] },
          { title: 'Hệ thống', items: [
            { to: '/admin/audit', label: 'Nhật ký hệ thống', icon: History },
            { to: '/admin/account', label: 'Tài khoản', icon: UserCog },
          ] },
        ]}
      />
    </PendingContext.Provider>
  )
}
