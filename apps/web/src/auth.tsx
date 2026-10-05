import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
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

export function CustomerRoute() {
  const { user, loading } = useAuth()
  if (loading) return <div className="page-wrap page-loading-3d"><span className="loader-orbit" /><p>Đang kiểm tra phiên đăng nhập…</p></div>
  if (user?.role === 'admin' || user?.role === 'provider') return <Navigate to={roleHome(user.role)} replace />
  return <Outlet />
}

export function GuestRoute() {
  const { user, loading } = useAuth()
  if (loading) return <div className="page-wrap page-loading-3d"><span className="loader-orbit" /><p>Đang kiểm tra phiên đăng nhập…</p></div>
  if (user) return <Navigate to={roleHome(user.role)} replace />
  return <Outlet />
}

export function RoleHome({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="page-wrap page-loading-3d"><span className="loader-orbit" /><p>Đang kiểm tra phiên đăng nhập…</p></div>
  if (user?.role === 'admin' || user?.role === 'provider') return <Navigate to={roleHome(user.role)} replace />
  return <>{children}</>
}

function roleHome(role: AuthUser['role']) {
  return role === 'admin' ? '/admin' : role === 'provider' ? '/provider-portal' : '/explore'
}
