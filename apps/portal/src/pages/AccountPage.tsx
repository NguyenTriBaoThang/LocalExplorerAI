import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { KeyRound, LogOut, Monitor, Save, Smartphone } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { Alert, Avatar, Badge, Button, Card, CardHeader, Field, Input, PageHeader, Spinner, useToast } from '../components/ui'
import { authApi, errorMessage } from '../lib/api'
import { MfaCard } from '../components/MfaCard'
import { formatDateTime, ROLES, timeAgo } from '../lib/format'
import type { SessionInfo } from '../lib/types'

export function AccountPage() {
  const { user, setUser, signOut } = useAuth()
  const toast = useToast()
  const [profile, setProfile] = useState({ display_name: user?.display_name ?? '', phone: user?.phone ?? '' })
  const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' })
  const [sessions, setSessions] = useState<SessionInfo[] | null>(null)
  const [busy, setBusy] = useState<'profile' | 'password' | null>(null)
  const [passwordError, setPasswordError] = useState('')

  const loadSessions = useCallback(() => { authApi.sessions().then(setSessions).catch(() => setSessions([])) }, [])
  useEffect(loadSessions, [loadSessions])
  if (!user) return null

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault()
    setBusy('profile')
    try {
      setUser(await authApi.updateProfile(profile.display_name, profile.phone || null))
      toast.success('Đã lưu thông tin cá nhân.')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const savePassword = async (event: FormEvent) => {
    event.preventDefault()
    setPasswordError('')
    if (passwords.next !== passwords.confirm) return setPasswordError('Mật khẩu nhập lại không khớp.')
    setBusy('password')
    try {
      await authApi.changePassword(passwords.current, passwords.next)
      toast.success('Đã đổi mật khẩu. Vui lòng đăng nhập lại.')
      await signOut()
    } catch (err) {
      setPasswordError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const revoke = async (session: SessionInfo) => {
    try {
      await authApi.revokeSession(session.id)
      toast.success('Đã đăng xuất phiên này.')
      loadSessions()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <>
      <PageHeader title="Tài khoản" description="Thông tin cá nhân, mật khẩu và các thiết bị đang đăng nhập." />
      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <Card className="h-fit p-6 text-center">
          <div className="flex justify-center"><Avatar name={user.display_name || user.email} size="lg" /></div>
          <p className="mt-3 font-semibold text-slate-900">{user.display_name || user.email}</p>
          <p className="text-sm text-slate-500">{user.email}</p>
          <div className="mt-3 flex justify-center gap-2">
            <Badge tone="brand">{ROLES[user.role]}</Badge>
            {user.email_verified_at ? <Badge tone="green">Email đã xác minh</Badge> : <Badge tone="amber">Chưa xác minh email</Badge>}
          </div>
          <p className="mt-4 text-xs text-slate-400">Tham gia {formatDateTime(user.created_at)}</p>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Thông tin cá nhân" />
            <form onSubmit={saveProfile} className="grid gap-5 p-5 sm:grid-cols-2">
              <Field label="Họ tên"><Input value={profile.display_name} onChange={(e) => setProfile({ ...profile, display_name: e.target.value })} required /></Field>
              <Field label="Số điện thoại"><Input value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} /></Field>
              <div className="sm:col-span-2 flex justify-end"><Button type="submit" icon={Save} loading={busy === 'profile'}>Lưu thay đổi</Button></div>
            </form>
          </Card>

          <Card>
            <CardHeader title="Đổi mật khẩu" description="Sau khi đổi, mọi thiết bị sẽ bị đăng xuất." />
            <form onSubmit={savePassword} className="grid gap-5 p-5 sm:grid-cols-3">
              {passwordError && <div className="sm:col-span-3"><Alert tone="red">{passwordError}</Alert></div>}
              <Field label="Mật khẩu hiện tại"><Input type="password" autoComplete="current-password" value={passwords.current} onChange={(e) => setPasswords({ ...passwords, current: e.target.value })} required /></Field>
              <Field label="Mật khẩu mới" hint="Tối thiểu 12 ký tự"><Input type="password" autoComplete="new-password" minLength={12} value={passwords.next} onChange={(e) => setPasswords({ ...passwords, next: e.target.value })} required /></Field>
              <Field label="Nhập lại"><Input type="password" autoComplete="new-password" value={passwords.confirm} onChange={(e) => setPasswords({ ...passwords, confirm: e.target.value })} required /></Field>
              <div className="sm:col-span-3 flex justify-end"><Button type="submit" icon={KeyRound} loading={busy === 'password'}>Đổi mật khẩu</Button></div>
            </form>
          </Card>

          <div id="security"><MfaCard /></div>

          <Card>
            <CardHeader title="Thiết bị đang đăng nhập"
              actions={<Button size="sm" variant="secondary" icon={LogOut} onClick={async () => { await authApi.logoutAll().catch(() => undefined); await signOut() }}>Đăng xuất tất cả</Button>} />
            {!sessions ? <Spinner /> : (
              <ul className="divide-y divide-slate-100">
                {sessions.map((session) => {
                  const mobile = /mobile|android|iphone/i.test(session.user_agent ?? '')
                  const Icon = mobile ? Smartphone : Monitor
                  return (
                    <li key={session.id} className="flex items-center gap-4 px-5 py-3.5">
                      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-500"><Icon className="h-[18px] w-[18px]" /></span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-slate-900">{describeAgent(session.user_agent)} {session.current && <Badge tone="green">Thiết bị này</Badge>}</p>
                        <p className="text-xs text-slate-500">{session.ip ?? 'IP ẩn'} · hoạt động {timeAgo(session.last_used_at ?? session.created_at)}</p>
                      </div>
                      {!session.current && <Button size="sm" variant="ghost" onClick={() => revoke(session)}>Đăng xuất</Button>}
                    </li>
                  )
                })}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  )
}

function describeAgent(agent: string | null): string {
  if (!agent) return 'Thiết bị không xác định'
  const browser = /edg\//i.test(agent) ? 'Edge' : /chrome\//i.test(agent) ? 'Chrome' : /firefox\//i.test(agent) ? 'Firefox' : /safari\//i.test(agent) ? 'Safari' : 'Trình duyệt'
  const os = /windows/i.test(agent) ? 'Windows' : /mac os/i.test(agent) ? 'macOS' : /android/i.test(agent) ? 'Android' : /iphone|ipad/i.test(agent) ? 'iOS' : /linux/i.test(agent) ? 'Linux' : ''
  return os ? `${browser} trên ${os}` : browser
}
