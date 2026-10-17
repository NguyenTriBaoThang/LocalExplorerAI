import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { authApi } from '../lib/api'
import type { AuthUser } from '../lib/types'

type AuthContextValue = {
  user: AuthUser | null
  loading: boolean
  setUser: (user: AuthUser | null) => void
  /** True when the signed-in role holds the permission. Unknown (permissions not loaded yet) counts as allowed. */
  can: (permission: string) => boolean
  /** True while the permission list of the signed-in user is still being fetched. */
  permissionsPending: boolean
  refresh: () => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      setUserState(await authApi.me())
    } catch {
      setUserState(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const signOut = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      setUserState(null)
    }
  }, [])

  // Only /auth/me carries authoritative permissions. Mutation responses include a
  // default empty array, which must not be mistaken for the user's actual grants.
  const setUser = useCallback((next: AuthUser | null) => {
    if (!next) { setUserState(null); return }
    setUserState((prev) => {
      if (prev && prev.id === next.id && prev.role === next.role && Array.isArray(prev.permissions)) return { ...next, permissions: prev.permissions }
      return { ...next, permissions: undefined }
    })
    void refresh()
  }, [refresh])

  useEffect(() => { void refresh() }, [refresh])

  const permissionsPending = !!user && !Array.isArray(user.permissions)
  const can = useCallback((permission: string) => !user || !Array.isArray(user.permissions) || user.permissions.includes(permission), [user])
  const value = useMemo(() => ({ user, loading, setUser, can, permissionsPending, refresh, signOut }), [user, loading, setUser, can, permissionsPending, refresh, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
