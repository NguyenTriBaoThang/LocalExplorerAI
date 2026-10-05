import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Spinner } from '../components/ui'
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
