import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AlertCircle, ArrowRight, CheckCircle2, Lock, Mail } from 'lucide-react'
import { apiErrorMessage, forgotPassword, resetPassword, verifyEmail } from '../api/client'
import { useAuth } from '../auth'
import { useTranslation } from '../i18n'

function Shell({ title, lead, children }: { title: string; lead?: string; children: ReactNode }) {
  return (
    <div className="auth-page-container">
      <div className="auth-glow-orb-1" />
      <div className="auth-glow-orb-2" />
      <div className="auth-card-wrapper animate-fadeIn">
        <div className="auth-brand-header">
          <Link to="/" className="auth-brand-logo">
            <div className="brand-gem-3d">
              <img src="/logo-icon.png" alt="Local Explorer AI" className="brand-logo-img" />
              <div className="gem-glow" />
            </div>
          </Link>
          <h1 className="auth-heading">{title}</h1>
          {lead && <p className="auth-subtext">{lead}</p>}
        </div>
        {children}
      </div>
    </div>
  )
}

function Alert({ children, ok = false }: { children: ReactNode; ok?: boolean }) {
  return (
    <div className={ok ? 'inline-alert-3d alert-success' : 'auth-alert-banner'} role={ok ? 'status' : 'alert'}>
      {ok ? <CheckCircle2 size={16} className="text-emerald flex-shrink-0" /> : <AlertCircle size={16} className="text-amber flex-shrink-0" />}
      <span>{children}</span>
    </div>
  )
}

export function ForgotPasswordPage() {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await forgotPassword(email.trim())
      setSent(true) // identical outcome whether or not the account exists
    } catch (reason) {
      setError(apiErrorMessage(reason))
    } finally {
      setBusy(false)
    }
  }

  if (sent) {
    return (
      <Shell title={t('recovery.sentTitle')}>
        <Alert ok>{t('recovery.sentBody')}</Alert>
        <Link className="btn-auth-submit" to="/login" style={{ textDecoration: 'none', marginTop: 16 }}>
          <span>{t('recovery.backToLogin')}</span>
          <ArrowRight size={17} />
        </Link>
      </Shell>
    )
  }

  return (
    <Shell title={t('recovery.forgotTitle')} lead={t('recovery.forgotLead')}>
      {error && <Alert>{error}</Alert>}
      <form onSubmit={submit} className="auth-form-body">
        <div className="auth-field-group">
          <label htmlFor="forgot-email">Email</label>
          <div className="auth-input-shell">
            <Mail size={16} className="auth-input-icon" />
            <input id="forgot-email" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
        </div>
        <button className="btn-auth-submit" type="submit" disabled={busy}>
          <span>{t('recovery.sendLink')}</span>
          <ArrowRight size={17} />
        </button>
      </form>
      <p className="auth-hint-text" style={{ textAlign: 'center', marginTop: 16 }}>
        <Link to="/login">{t('recovery.backToLogin')}</Link>
      </p>
    </Shell>
  )
}

export function ResetPasswordPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')
  const { setUser } = useAuth()

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await resetPassword(token, password)
      setUser(null) // every session of this account was just revoked
      setDone(true)
    } catch (reason) {
      setError(apiErrorMessage(reason))
    } finally {
      setBusy(false)
    }
  }

  if (!token) {
    return (
      <Shell title={t('recovery.resetTitle')}>
        <Alert>{t('recovery.missingToken')}</Alert>
        <Link className="btn-auth-submit" to="/forgot-password" style={{ textDecoration: 'none', marginTop: 16 }}>
          <span>{t('recovery.requestNew')}</span>
          <ArrowRight size={17} />
        </Link>
      </Shell>
    )
  }

  if (done) {
    return (
      <Shell title={t('recovery.resetTitle')}>
        <Alert ok>{t('recovery.resetDone')}</Alert>
        <Link className="btn-auth-submit" to="/login" style={{ textDecoration: 'none', marginTop: 16 }}>
          <span>{t('recovery.backToLogin')}</span>
          <ArrowRight size={17} />
        </Link>
      </Shell>
    )
  }

  return (
    <Shell title={t('recovery.resetTitle')} lead={t('recovery.resetLead')}>
      {error && <Alert>{error}</Alert>}
      <form onSubmit={submit} className="auth-form-body">
        <div className="auth-field-group">
          <div className="field-label-split">
            <label htmlFor="reset-password">{t('recovery.newPassword')}</label>
            <span className="auth-hint-text">{t('auth.passMin12')}</span>
          </div>
          <div className="auth-input-shell">
            <Lock size={16} className="auth-input-icon" />
            <input id="reset-password" type="password" required minLength={12} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
        </div>
        <button className="btn-auth-submit" type="submit" disabled={busy}>
          <span>{t('recovery.resetBtn')}</span>
          <ArrowRight size={17} />
        </button>
      </form>
    </Shell>
  )
}

export function VerifyEmailPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const { refresh, user } = useAuth()
  const [state, setState] = useState<'working' | 'done' | 'failed'>(token ? 'working' : 'failed')
  const started = useRef(false)

  useEffect(() => {
    // StrictMode runs effects twice in development, and the link is single-use: call the API exactly once.
    if (!token || started.current) return
    started.current = true
    verifyEmail(token)
      .then(async () => {
        setState('done')
        if (user) await refresh() // update the banner for a signed-in visitor
      })
      .catch(() => setState('failed'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  return (
    <Shell title={t('verify.title')}>
      {state === 'working' && <p className="auth-subtext" role="status">{t('verify.working')}</p>}
      {state === 'done' && <Alert ok>{t('verify.done')}</Alert>}
      {state === 'failed' && <Alert>{t('verify.failed')}</Alert>}
      {state !== 'working' && (
        <Link className="btn-auth-submit" to={user ? '/' : '/login'} style={{ textDecoration: 'none', marginTop: 16 }}>
          <span>{user ? t('nav.explore') : t('recovery.backToLogin')}</span>
          <ArrowRight size={17} />
        </Link>
      )}
    </Shell>
  )
}
