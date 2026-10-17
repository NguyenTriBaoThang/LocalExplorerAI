import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, Eye, EyeOff, ShieldCheck } from 'lucide-react'
import { useAuth } from '../../auth/AuthContext'
import { AuthLayout } from '../../components/AuthLayout'
import { Alert, Button, Field, Input } from '../../components/ui'
import { authApi, errorMessage } from '../../lib/api'
import type { AuthUser } from '../../lib/types'

export function LoginPage() {
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [mfaTicket, setMfaTicket] = useState<string | null>(null)
  const [code, setCode] = useState('')

  const finish = (user: AuthUser) => {
    setUser(user)
    navigate((location.state as { from?: string } | null)?.from ?? '/', { replace: true })
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await authApi.login(email, password)
      if ('mfa_ticket' in result) {
        setMfaTicket(result.mfa_ticket)  // password accepted; the session starts after the second factor
        setPassword('')
      } else {
        finish(result)
      }
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const submitCode = async (event: FormEvent) => {
    event.preventDefault()
    if (!mfaTicket) return
    setBusy(true)
    setError('')
    try {
      finish(await authApi.loginMfa(mfaTicket, code.trim()))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (mfaTicket) {
    return (
      <AuthLayout title="Xác thực hai lớp" subtitle="Nhập mã 6 số từ ứng dụng xác thực, hoặc một mã khôi phục.">
        <form onSubmit={submitCode} className="space-y-5">
          {error && <Alert tone="red">{error}</Alert>}
          <Field label="Mã xác thực">
            <Input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" placeholder="123456" required minLength={6} autoFocus className="text-center font-mono text-lg tracking-[0.4em]" />
          </Field>
          <Button type="submit" size="lg" icon={ShieldCheck} loading={busy} className="w-full">Xác nhận</Button>
          <button type="button" onClick={() => { setMfaTicket(null); setCode(''); setError('') }} className="mx-auto flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-700">
            <ArrowLeft className="h-4 w-4" /> Đăng nhập bằng tài khoản khác
          </button>
        </form>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout title="Đăng nhập" subtitle="Dành cho đối tác và quản trị viên Local Explorer.">
      <form onSubmit={submit} className="space-y-5">
        {error && <Alert tone="red">{error}</Alert>}
        <Field label="Email">
          <Input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
        </Field>
        <Field label="Mật khẩu">
          <div className="relative">
            <Input type={showPassword ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required className="pr-10" />
            <button type="button" onClick={() => setShowPassword((v) => !v)} aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
              className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-slate-400 hover:text-slate-600">
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </Field>
        <div className="flex justify-end">
          <Link to="/forgot-password" className="text-sm font-medium text-brand-600 hover:text-brand-700">Quên mật khẩu?</Link>
        </div>
        <Button type="submit" size="lg" loading={busy} className="w-full">Đăng nhập</Button>
      </form>
      <p className="mt-8 text-center text-sm text-slate-500">
        Chưa có tài khoản đối tác?{' '}
        <Link to="/register" className="font-medium text-brand-600 hover:text-brand-700">Đăng ký ngay</Link>
      </p>
    </AuthLayout>
  )
}
