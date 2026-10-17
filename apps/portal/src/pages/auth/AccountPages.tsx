import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CheckCircle2, MailCheck, XCircle } from 'lucide-react'
import { AuthLayout } from '../../components/AuthLayout'
import { Alert, Button, Field, Input, Spinner } from '../../components/ui'
import { authApi, errorMessage } from '../../lib/api'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await authApi.forgotPassword(email)
      setSent(true)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout title="Quên mật khẩu" subtitle="Nhập email đăng nhập, chúng tôi sẽ gửi liên kết đặt lại mật khẩu.">
      {sent ? (
        <div className="space-y-6">
          <Alert tone="green" title="Đã gửi yêu cầu">Nếu email tồn tại trong hệ thống, bạn sẽ nhận được liên kết đặt lại mật khẩu trong vài phút.</Alert>
          <Link to="/login" className="block text-center text-sm font-medium text-brand-600 hover:text-brand-700">Quay lại đăng nhập</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          {error && <Alert tone="red">{error}</Alert>}
          <Field label="Email"><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus /></Field>
          <Button type="submit" size="lg" loading={busy} className="w-full">Gửi liên kết</Button>
          <Link to="/login" className="block text-center text-sm font-medium text-slate-500 hover:text-slate-700">Quay lại đăng nhập</Link>
        </form>
      )}
    </AuthLayout>
  )
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const [password, setPassword] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await authApi.resetPassword(params.get('token') ?? '', password)
      setDone(true)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout title="Đặt lại mật khẩu">
      {done ? (
        <div className="space-y-6">
          <Alert tone="green" title="Đã đổi mật khẩu">Mọi phiên đăng nhập cũ đã được đăng xuất. Hãy đăng nhập lại bằng mật khẩu mới.</Alert>
          <Link to="/login"><Button size="lg" className="w-full">Đăng nhập</Button></Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          {error && <Alert tone="red">{error}</Alert>}
          <Field label="Mật khẩu mới" hint="Tối thiểu 12 ký tự.">
            <Input type="password" autoComplete="new-password" minLength={12} value={password} onChange={(e) => setPassword(e.target.value)} required autoFocus />
          </Field>
          <Button type="submit" size="lg" loading={busy} className="w-full">Cập nhật mật khẩu</Button>
        </form>
      )}
    </AuthLayout>
  )
}

export function VerifyEmailPage() {
  const [params] = useSearchParams()
  const [state, setState] = useState<'loading' | 'ok' | 'error'>('loading')
  const [error, setError] = useState('')
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return  // the token is single-use; StrictMode would otherwise submit it twice
    started.current = true
    authApi.verifyEmail(params.get('token') ?? '')
      .then(() => setState('ok'))
      .catch((err) => { setError(errorMessage(err)); setState('error') })
  }, [params])

  return (
    <AuthLayout title="Xác minh email">
      {state === 'loading' && <Spinner label="Đang xác minh…" />}
      {state === 'ok' && (
        <div className="text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" />
          <p className="mt-4 font-medium text-slate-900">Email đã được xác minh</p>
          <Link to="/" className="mt-6 inline-block"><Button icon={MailCheck}>Vào portal</Button></Link>
        </div>
      )}
      {state === 'error' && (
        <div className="text-center">
          <XCircle className="mx-auto h-12 w-12 text-rose-500" />
          <p className="mt-4 text-sm text-slate-600">{error}</p>
          <Link to="/" className="mt-6 inline-block text-sm font-medium text-brand-600">Về trang chủ portal</Link>
        </div>
      )}
    </AuthLayout>
  )
}
