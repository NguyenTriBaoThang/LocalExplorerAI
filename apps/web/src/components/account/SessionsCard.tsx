import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, MonitorSmartphone } from 'lucide-react'
import { apiErrorMessage, listSessions, logoutAllDevices, revokeSession } from '../../api/client'
import { useAuth } from '../../auth'
import { useTranslation } from '../../i18n'
import type { SessionInfo } from '../../types'

/** Short, readable device label from a User-Agent string (never trust or render it as HTML). */
function deviceLabel(agent: string | null, fallback: string): string {
  if (!agent) return fallback
  const browser = /Edg\//.test(agent) ? 'Edge' : /Chrome\//.test(agent) ? 'Chrome' : /Firefox\//.test(agent) ? 'Firefox' : /Safari\//.test(agent) ? 'Safari' : ''
  const os = /Windows/.test(agent) ? 'Windows' : /Android/.test(agent) ? 'Android' : /iPhone|iPad/.test(agent) ? 'iOS' : /Mac OS X/.test(agent) ? 'macOS' : /Linux/.test(agent) ? 'Linux' : ''
  return [browser, os].filter(Boolean).join(' · ') || fallback
}

export function SessionsCard() {
  const { t, locale } = useTranslation()
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<SessionInfo[] | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      setSessions(await listSessions())
    } catch (reason) {
      setError(apiErrorMessage(reason))
    }
  }, [])
  useEffect(() => { void load() }, [load])

  const endedHere = () => {
    setUser(null)
    navigate('/login', { replace: true })
  }

  async function remove(session: SessionInfo) {
    setBusy(true)
    setError('')
    try {
      await revokeSession(session.id)
      if (session.current) endedHere()
      else await load()
    } catch (reason) {
      setError(apiErrorMessage(reason))
    } finally {
      setBusy(false)
    }
  }

  async function removeAll() {
    setBusy(true)
    setError('')
    try {
      await logoutAllDevices()
      endedHere()
    } catch (reason) {
      setError(apiErrorMessage(reason))
      setBusy(false)
    }
  }

  const when = (value: string | null) => (value ? new Date(value).toLocaleString(locale === 'en' ? 'en-US' : 'vi-VN') : '—')

  return (
    <section className="profile-card-3d">
      <div className="profile-card-title-row">
        <div className="profile-title-icon-box text-emerald"><MonitorSmartphone size={18} /></div>
        <div>
          <h2>{t('sessions.title')}</h2>
          <p>{t('sessions.desc')}</p>
        </div>
      </div>
      {error && (
        <div className="inline-alert-3d" role="alert">
          <AlertCircle size={16} className="text-amber" />
          <span>{error}</span>
        </div>
      )}
      {sessions && sessions.length === 0 && <p>{t('sessions.empty')}</p>}
      <ul className="profile-form" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {(sessions ?? []).map((session) => (
          <li key={session.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
            <div>
              <strong>{deviceLabel(session.user_agent, t('sessions.unknownDevice'))}</strong>
              {session.current && <span className="auth-hint-text" style={{ marginLeft: 8 }}>{t('sessions.current')}</span>}
              <div className="auth-hint-text">
                {session.ip ?? '—'} · {t('sessions.lastUsed')}: {when(session.last_used_at)}
              </div>
            </div>
            <button type="button" className="btn-secondary-3d btn-sm" disabled={busy} onClick={() => void remove(session)}>
              {t('sessions.revoke')}
            </button>
          </li>
        ))}
      </ul>
      {sessions && sessions.length > 0 && (
        <button type="button" className="btn-secondary-3d" disabled={busy} onClick={() => void removeAll()} style={{ marginTop: 12 }}>
          {t('sessions.revokeAll')}
        </button>
      )}
    </section>
  )
}
