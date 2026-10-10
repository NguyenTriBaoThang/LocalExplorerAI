import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'
import { AUTH_EXPIRED_EVENT, getCurrentUser } from './api/client'
import type { AuthUser } from './types'

type AuthContextValue = {
  user: AuthUser | null
  loading: boolean
  refresh: () => Promise<void>
  setUser: (user: AuthUser | null) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const refresh = async () => {
    try {
      setUser(await getCurrentUser())
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { void refresh() }, [])
  // The server ended the session (sign-out elsewhere, revoked device, password reset): drop the stale user so guards redirect.
  useEffect(() => {
    const expired = () => setUser(null)
    window.addEventListener(AUTH_EXPIRED_EVENT, expired)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, expired)
  }, [])
  const value = useMemo(() => ({ user, loading, refresh, setUser }), [user, loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}

export function RoleRoute({ roles }: { roles: AuthUser['role'][] }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="page-wrap page-loading-3d"><span className="loader-orbit" /><p>Đang kiểm tra phiên đăng nhập…</p></div>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (!roles.includes(user.role)) return <Navigate to={roleHome(user.role)} replace />
  return <Outlet />
}

/** Traveler-only features (chat, planner, itineraries). Staff may browse the public site but get an explanation here. */
export function CustomerRoute() {
  const { user, loading } = useAuth()
  if (loading) return <div className="page-wrap page-loading-3d"><span className="loader-orbit" /><p>Đang kiểm tra phiên đăng nhập…</p></div>
  if (user?.role === 'admin' || user?.role === 'provider') {
    return (
      <div className="page-wrap" style={{ maxWidth: 560, textAlign: 'center', paddingTop: 80 }}>
        <h1 className="page-heading-3d" style={{ fontSize: 26 }}>Tính năng dành cho du khách</h1>
        <p className="page-subtext-3d">
          Bạn đang đăng nhập bằng tài khoản {user.role === 'admin' ? 'quản trị' : 'đối tác'}. Lập lịch trình và trò chuyện với trợ lý cần tài khoản du khách.
          Bạn vẫn có thể xem trang công khai, hoặc quay lại portal để làm việc.
        </p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 20, flexWrap: 'wrap' }}>
          <Link to="/" className="btn-secondary-3d">Về trang chủ</Link>
          <Link to={roleHome(user.role)} className="btn-primary-3d">Vào Portal</Link>
        </div>
      </div>
    )
  }
  return <Outlet />
}

export function GuestRoute() {
  const { user, loading } = useAuth()
  if (loading) return <div className="page-wrap page-loading-3d"><span className="loader-orbit" /><p>Đang kiểm tra phiên đăng nhập…</p></div>
  if (user) return <Navigate to={roleHome(user.role)} replace />
  return <Outlet />
}

/** The home page is public. Staff stay on it: only signing in (GuestRoute) sends them to the portal. */
export function RoleHome({ children }: { children: ReactNode }) {
  const { loading } = useAuth()
  if (loading) return <div className="page-wrap page-loading-3d"><span className="loader-orbit" /><p>Đang kiểm tra phiên đăng nhập…</p></div>
  return <>{children}</>
}

function roleHome(role: AuthUser['role']) {
  return role === 'admin' ? '/admin' : role === 'provider' ? '/provider-portal' : '/explore'
}
