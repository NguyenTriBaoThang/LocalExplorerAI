import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { Activity, Bot, Building2, CloudRain, FileText, History, KeyRound, LayoutDashboard, MapPinned, PlugZap, UserCog, Users } from 'lucide-react'
import { FileInput } from 'lucide-react'
import { BrandLogo } from '../../components/Brand'
import { MfaCard } from '../../components/MfaCard'
import { PortalShell } from '../../components/PortalShell'
import { Spinner } from '../../components/ui'
import { UserMenu } from '../../components/UserMenu'
import { useAuth } from '../../auth/AuthContext'
import { adminApi, authApi } from '../../lib/api'
import type { NavGroup } from '../../components/PortalShell'

const PendingContext = createContext<{ pending: number; refreshPending: () => void }>({ pending: 0, refreshPending: () => undefined })
export const usePendingPartners = () => useContext(PendingContext)

export function AdminLayout() {
  const [pending, setPending] = useState(0)
  const { can } = useAuth()
  // When the server requires two-factor authentication for administrators, nothing else works until it is on.
  const [mfaGate, setMfaGate] = useState<boolean | null>(null)
  useEffect(() => { authApi.mfaStatus().then((s) => setMfaGate(s.required && !s.enabled)).catch(() => setMfaGate(false)) }, [])
  const refreshPending = useCallback(() => {
    if (!can('admin:dashboard')) return
    adminApi.dashboard().then((data) => setPending(data.pending_partner_applications)).catch(() => undefined)
  }, [can])
  useEffect(() => { if (mfaGate === false) refreshPending() }, [mfaGate, refreshPending])

  if (mfaGate === null) return <div className="min-h-screen"><Spinner /></div>
  if (mfaGate) {
    return (
      <div className="min-h-screen">
        <header className="relative z-30 border-b border-slate-200 bg-white">
          <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4"><BrandLogo subtitle="Portal Quản trị" /><UserMenu /></div>
        </header>
        <main className="mx-auto max-w-3xl px-4 py-10">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Bảo vệ tài khoản quản trị</h1>
          <p className="mb-6 mt-1 text-sm text-slate-500">Hệ thống yêu cầu quản trị viên bật xác thực hai lớp trước khi vào khu vực quản trị.</p>
          <MfaCard onEnabled={() => setMfaGate(false)} />
        </main>
      </div>
    )
  }

  return (
    <PendingContext.Provider value={{ pending, refreshPending }}>
      <PortalShell
        area="Portal Quản trị"
        nav={visibleNav(can, [
          { items: [{ to: '/admin', label: 'Tổng quan', icon: LayoutDashboard, end: true, perm: 'admin:dashboard' }] },
          { title: 'Quản lý', items: [
            { to: '/admin/partners', label: 'Đối tác', icon: Building2, badge: pending, perm: 'admin:providers' },
            { to: '/admin/users', label: 'Người dùng', icon: Users, perm: 'admin:users' },
            { to: '/admin/rbac', label: 'Phân quyền', icon: KeyRound, perm: 'admin:rbac' },
          ] },
          { title: 'Nội dung', items: [
            { to: '/admin/places', label: 'Địa điểm & Danh thắng', icon: MapPinned, perm: 'admin:places' },
            { to: '/admin/content', label: 'Nội dung website', icon: FileText, perm: 'admin:content' },
            { to: '/admin/imports', label: 'Nhập địa điểm & Trùng lặp', icon: FileInput, perm: ['admin:place_import', 'admin:duplicates'] },
          ] },
          { title: 'Hệ thống', items: [
            { to: '/admin/operations', label: 'Vận hành', icon: Activity, perm: 'ops:read' },
            { to: '/admin/integrations', label: 'Tích hợp & API keys', icon: PlugZap, perm: 'admin:integrations' },
            { to: '/admin/ai-tools', label: 'Công cụ AI', icon: Bot, perm: 'admin:ai_tools' },
            { to: '/admin/flood-risk', label: 'Rủi ro ngập', icon: CloudRain },
            { to: '/admin/audit', label: 'Nhật ký hệ thống', icon: History, perm: 'admin:audit' },
            { to: '/admin/account', label: 'Tài khoản', icon: UserCog },
          ] },
        ])}
      />
    </PendingContext.Provider>
  )
}

type GatedItem = NavGroup['items'][number] & { perm?: string | string[] }
type GatedGroup = { title?: string; items: GatedItem[] }

/** Drops nav entries the signed-in role may not use, and groups left empty. */
function visibleNav(can: (permission: string) => boolean, groups: GatedGroup[]): NavGroup[] {
  return groups
    .map((group) => ({
      title: group.title,
      items: group.items
        .filter((item) => !item.perm || [item.perm].flat().some(can))
        .map(({ perm: _perm, ...item }) => item),
    }))
    .filter((group) => group.items.length > 0)
}
