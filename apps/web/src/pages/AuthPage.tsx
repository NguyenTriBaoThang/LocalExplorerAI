import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Mail,
  Lock,
  User,
  ArrowRight,
  Eye,
  EyeOff,
  AlertCircle,
} from 'lucide-react'
import { api, apiErrorMessage, getGoogleOAuthStatus, login, registerAccount } from '../api/client'
import { useAuth } from '../auth'
import { useTranslation } from '../i18n'
import type { GoogleOAuthStatus } from '../types'

export function AuthPage({ register = false }: { register?: boolean }) {
  const { t, locale } = useTranslation()
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [googleOAuth, setGoogleOAuth] = useState<GoogleOAuthStatus | null>(null)
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const destination = (location.state as { from?: string } | null)?.from || '/'

  useEffect(() => {
    let active = true
    void getGoogleOAuthStatus()
      .then((status) => { if (active) setGoogleOAuth(status) })
      .catch(() => { if (active) setGoogleOAuth(null) })
    return () => { active = false }
  }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      setUser(
        register
          ? await registerAccount(email, name, password)
          : await login(email, password)
      )
      navigate(destination, { replace: true })
    } catch (reason) {
      setError(apiErrorMessage(reason))
    } finally {
      setBusy(false)
    }
  }

  const oauthError = searchParams.get('error')
    ? (locale === 'en'
        ? 'Google sign-in was not successful. Please check OAuth credentials.'
        : 'Đăng nhập Google chưa thành công. Vui lòng kiểm tra cấu hình OAuth.')
    : ''

  return (
    <div className="auth-page-container">
      {/* Ambient background glow orbs */}
      <div className="auth-glow-orb-1" />
      <div className="auth-glow-orb-2" />

      <div className="auth-card-wrapper animate-fadeIn">
        {/* Brand Banner */}
        <div className="auth-brand-header">
          <Link to="/" className="auth-brand-logo">
            <div className="brand-gem-3d">
              <img src="/logo-icon.png" alt="Local Explorer AI" className="brand-logo-img" />
              <div className="gem-glow" />
            </div>
          </Link>
          <h1 className="auth-heading">
            {register ? t('auth.createTravelerAccount') : t('auth.welcomeBack')}
          </h1>
          <p className="auth-subtext">
            {register ? t('auth.registerLead') : t('auth.welcomeLead')}
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="auth-tab-strip">
          <Link
            to="/login"
            className={`auth-tab-btn ${!register ? 'auth-tab-active' : ''}`}
          >
            {t('auth.tabLogin')}
          </Link>
          <Link
            to="/register"
            className={`auth-tab-btn ${register ? 'auth-tab-active' : ''}`}
          >
            {t('auth.tabRegister')}
          </Link>
        </div>

        {(error || oauthError) && (
          <div className="auth-alert-banner">
            <AlertCircle size={16} className="text-amber flex-shrink-0" />
            <span>{error || oauthError}</span>
          </div>
        )}

        <form onSubmit={submit} className="auth-form-body">
          {register && (
            <div className="auth-field-group">
              <label htmlFor="auth-name">{t('auth.fullName')}</label>
              <div className="auth-input-shell">
                <User size={16} className="auth-input-icon" />
                <input
                  id="auth-name"
                  required
                  minLength={2}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t('auth.namePlaceholder')}
                  autoComplete="name"
                />
              </div>
            </div>
          )}

          <div className="auth-field-group">
            <label htmlFor="auth-email">{t('auth.email')}</label>
            <div className="auth-input-shell">
              <Mail size={16} className="auth-input-icon" />
              <input
                id="auth-email"
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                autoComplete="email"
              />
            </div>
          </div>

          <div className="auth-field-group">
            <div className="field-label-split">
              <label htmlFor="auth-password">{t('auth.password')}</label>
              {register && (
                <span className="auth-hint-text">{t('auth.passMin12')}</span>
              )}
              {!register && (
                <Link to="/forgot-password" className="auth-hint-text">{t('recovery.forgotLink')}</Link>
              )}
            </div>
            <div className="auth-input-shell">
              <Lock size={16} className="auth-input-icon" />
              <input
                id="auth-password"
                required
                type={showPassword ? 'text' : 'password'}
                minLength={register ? 12 : 1}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={register ? t('auth.passPlaceholderRegister') : t('auth.passPlaceholderLogin')}
                autoComplete={register ? 'new-password' : 'current-password'}
              />
              <button
                type="button"
                className="toggle-password-btn"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <button className="btn-auth-submit" type="submit" disabled={busy}>
            <span>{busy ? t('auth.verifying') : register ? t('auth.createBtn') : t('auth.loginBtn')}</span>
            <ArrowRight size={17} />
          </button>
        </form>

        {/* Divider */}
        <div className="auth-divider-line">
          <span>{t('auth.orContinueWith')}</span>
        </div>

        {/* Google OAuth Button */}
        <a
          className={`google-oauth-btn ${googleOAuth?.enabled === false ? 'google-oauth-disabled' : ''}`}
          href={googleOAuth?.enabled === false ? undefined : `${api.defaults.baseURL}/auth/google/start`}
          aria-disabled={googleOAuth?.enabled === false}
          onClick={(event) => {
            if (googleOAuth?.enabled === false) event.preventDefault()
          }}
        >
          <svg className="google-icon" viewBox="0 0 24 24" width="18" height="18">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
            />
          </svg>
          <span>{t('auth.googleLogin')}</span>
        </a>
        {googleOAuth?.enabled === false && (
          <p className="auth-oauth-hint">
            {googleOAuth.configuration_message || (locale === 'en' ? 'Google sign-in is not configured.' : 'Chưa cấu hình đăng nhập Google.')}
            {' '}{locale === 'en' ? 'Callback URI:' : 'Callback URI:'}{' '}
            <code>{googleOAuth.redirect_uri}</code>
          </p>
        )}
      </div>
    </div>
  )
}
