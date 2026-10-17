import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { AlertCircle, ShieldCheck } from 'lucide-react'
import { apiErrorMessage, beginMfaSetup, disableMfa, enableMfa, getMfaStatus, regenerateRecoveryCodes } from '../../api/client'
import { useAuth } from '../../auth'
import { useTranslation } from '../../i18n'
import type { MfaSetup, MfaStatus } from '../../types'

type Mode = 'idle' | 'setup' | 'codes' | 'regenerate' | 'disable'

export function MfaCard() {
  const { t } = useTranslation()
  const { refresh } = useAuth()
  const [status, setStatus] = useState<MfaStatus | null>(null)
  const [mode, setMode] = useState<Mode>('idle')
  const [setup, setSetup] = useState<MfaSetup | null>(null)
  const [codes, setCodes] = useState<string[]>([])
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try { setStatus(await getMfaStatus()) } catch (reason) { setError(apiErrorMessage(reason)) }
  }, [])
  useEffect(() => { void load() }, [load])

  const reset = () => { setMode('idle'); setSetup(null); setCode(''); setPassword(''); setError('') }

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    try { await action() } catch (reason) { setError(apiErrorMessage(reason)) } finally { setBusy(false) }
  }

  const start = () => run(async () => { setSetup(await beginMfaSetup()); setMode('setup') })
  const confirm = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => {
      setCodes(await enableMfa(code.trim()))
      setCode('')
      setMode('codes')
      await refresh()
      await load()
    })
  }
  const regenerate = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => { setCodes(await regenerateRecoveryCodes(code.trim())); setCode(''); setMode('codes'); await load() })
  }
  const disable = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => { await disableMfa(code.trim(), password || null); reset(); await refresh(); await load() })
  }
  const download = () => {
    const link = document.createElement('a')
    link.href = URL.createObjectURL(new Blob([codes.join('\n') + '\n'], { type: 'text/plain' }))
    link.download = 'local-explorer-recovery-codes.txt'
    link.click()
    URL.revokeObjectURL(link.href)
  }

  const codeField = (
    <input aria-label={t('mfa.code')} required inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="123456" />
  )

  return (
    <section className="profile-card-3d" id="security">
      <div className="profile-card-title-row">
        <div className="profile-title-icon-box text-emerald"><ShieldCheck size={18} /></div>
        <div>
          <h2>{t('mfa.title')}</h2>
          <p>{t('mfa.desc')}</p>
        </div>
      </div>
      {status?.required && !status.enabled && <div className="inline-alert-3d" role="alert"><AlertCircle size={16} className="text-amber" /><span>{t('mfa.requiredNotice')}</span></div>}
      {error && <div className="inline-alert-3d" role="alert"><AlertCircle size={16} className="text-amber" /><span>{error}</span></div>}
      {status && mode === 'idle' && (
        <>
          <p><strong>{status.enabled ? t('mfa.statusOn') : t('mfa.statusOff')}</strong>
            {status.enabled && <span className="auth-hint-text" style={{ marginLeft: 8 }}>{t('mfa.codesLeft')}: {status.recovery_codes_remaining}</span>}</p>
          {!status.enabled && <button type="button" className="btn-secondary-3d" disabled={busy} onClick={() => void start()}>{t('mfa.enable')}</button>}
          {status.enabled && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button type="button" className="btn-secondary-3d" onClick={() => setMode('regenerate')}>{t('mfa.regenerate')}</button>
              {!status.required && <button type="button" className="btn-secondary-3d" onClick={() => setMode('disable')}>{t('mfa.disable')}</button>}
            </div>
          )}
        </>
      )}
      {mode === 'setup' && setup && (
        <form className="profile-form" onSubmit={confirm}>
          <p>{t('mfa.scan')}</p>
          <img src={setup.qr} alt="QR" width={180} height={180} style={{ background: '#fff', padding: 8, borderRadius: 8 }} />
          <code style={{ wordBreak: 'break-all' }}>{setup.secret}</code>
          <label>{t('mfa.confirm')}{codeField}</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn-secondary-3d" type="submit" disabled={busy}>{t('mfa.verify')}</button>
            <button className="btn-secondary-3d" type="button" onClick={reset}>{t('mfa.cancel')}</button>
          </div>
        </form>
      )}
      {mode === 'codes' && (
        <div className="profile-form">
          <h3>{t('mfa.recoveryTitle')}</h3>
          <p>{t('mfa.recoveryLead')}</p>
          <pre data-testid="recovery-codes">{codes.join('\n')}</pre>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn-secondary-3d" type="button" onClick={() => void navigator.clipboard?.writeText(codes.join('\n'))}>{t('mfa.copy')}</button>
            <button className="btn-secondary-3d" type="button" onClick={download}>{t('mfa.download')}</button>
            <button className="btn-secondary-3d" type="button" onClick={() => { setCodes([]); reset() }}>{t('mfa.saved')}</button>
          </div>
        </div>
      )}
      {(mode === 'regenerate' || mode === 'disable') && (
        <form className="profile-form" onSubmit={mode === 'regenerate' ? regenerate : disable}>
          <label>{t('mfa.confirmAction')}{codeField}</label>
          {mode === 'disable' && (
            <label>{t('mfa.password')}<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn-secondary-3d" type="submit" disabled={busy}>{mode === 'regenerate' ? t('mfa.regenerate') : t('mfa.disable')}</button>
            <button className="btn-secondary-3d" type="button" onClick={reset}>{t('mfa.cancel')}</button>
          </div>
        </form>
      )}
    </section>
  )
}
