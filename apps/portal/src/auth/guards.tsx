import { ShieldOff } from 'lucide-react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { EmptyState, Spinner } from '../components/ui'
import type { Role } from '../lib/types'
import { useAuth } from './AuthContext'

/** The portal itself needs a session: guests go to the login page and come back afterwards. */
export function RequireAuth() {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="min-h-screen"><Spinner label="Đang kiểm tra phiên đăng nhập…" /></div>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}

/** A portal area (partner or admin): users without the role go back to the home widgets with an explanation. */
export function RequireRole({ role }: { role: Role }) {
  const { user } = useAuth()
  if (user?.role !== role) return <Navigate to="/" replace state={{ denied: role }} />
  return <Outlet />
}

export function GuestOnly() {
  const { user, loading } = useAuth()
  if (loading) return <div className="min-h-screen"><Spinner /></div>
  if (user) return <Navigate to="/" replace />
  return <Outlet />
}

/**
 * A single page inside a portal area. Staff whose role lacks the permission see an explanation instead of a page that
 * would only produce 403 errors. Pass `anyOf` when one page serves several permissions.
 */
export function RequirePermission({ permission, anyOf }: { permission?: string; anyOf?: string[] }) {
  const { can, permissionsPending } = useAuth()
  if (permissionsPending) return <Spinner />
  const needed = anyOf ?? (permission ? [permission] : [])
  if (needed.length && !needed.some(can)) {
    return <EmptyState icon={ShieldOff} title="Bạn không có quyền truy cập mục này" description="Vai trò của bạn chưa được cấp quyền cho mục này. Hãy liên hệ quản trị viên nếu bạn cần sử dụng nó." />
  }
  return <Outlet />
}
