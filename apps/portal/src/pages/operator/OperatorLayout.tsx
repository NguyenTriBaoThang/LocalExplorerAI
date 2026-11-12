import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { BarChart3, FileText, LayoutDashboard, Percent, ReceiptText, Settings, Table2 } from 'lucide-react'
import { PortalShell } from '../../components/PortalShell'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Spinner } from '../../components/ui'
import { errorMessage } from '../../lib/api'
import { operatorApi, type OperatorOrg } from '../../lib/operatorApi'
import type { NavGroup } from '../../components/PortalShell'

type OperatorContextValue = { org: OperatorOrg; reload: () => Promise<void> }
const OperatorContext = createContext<OperatorContextValue | null>(null)

export function useOperator() {
  const value = useContext(OperatorContext)
  if (!value) throw new Error('useOperator must be used inside OperatorLayout')
  return value
}

export function OperatorLayout() {
  const [org, setOrg] = useState<OperatorOrg | null>(null)
  const [error, setError] = useState('')
  const { can } = useAuth()

  const reload = useCallback(async () => {
    try {
      setOrg(await operatorApi.org())
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [])
  useEffect(() => { void reload() }, [reload])

  if (error) return <div className="mx-auto max-w-lg p-8"><Alert tone="red" title="Không tải được thông tin doanh nghiệp">{error}</Alert></div>
  if (!org) return <div className="min-h-screen"><Spinner /></div>

  const groups: Array<{ title?: string; items: Array<NavGroup['items'][number] & { perm?: string }> }> = [
    { items: [
      { to: '/operator', label: 'Tổng quan', icon: LayoutDashboard, end: true },
      { to: '/operator/quotes', label: 'Báo giá', icon: FileText, perm: 'operator:quote' },
      { to: '/operator/rate-cards', label: 'Bảng giá', icon: Table2, perm: 'operator:rate_card' },
      { to: '/operator/reconcile', label: 'Đối chiếu', icon: ReceiptText, perm: 'operator:reconcile' },
      { to: '/operator/margin', label: 'Biên lợi nhuận', icon: Percent, perm: 'operator:analytics' },
      { to: '/operator/roi', label: 'ROI', icon: BarChart3, perm: 'operator:analytics' },
    ] },
    { title: 'Tài khoản', items: [
      { to: '/operator/settings', label: 'Cài đặt', icon: Settings, perm: 'operator:settings' },
    ] },
  ]
  const nav = groups
    .map((group) => ({ title: group.title, items: group.items.filter((item) => !item.perm || can(item.perm)) }))
    .filter((group) => group.items.length > 0)

  return (
    <OperatorContext.Provider value={{ org, reload }}>
      <PortalShell
        area="Portal Điều hành tour"
        nav={nav}
        sidebarFooter={<div className="rounded-lg bg-slate-50 p-3"><p className="truncate text-sm font-medium text-slate-900">{org.name}</p></div>}
      />
    </OperatorContext.Provider>
  )
}
