import { useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { apiErrorMessage, resendVerification } from '../../api/client'
import { useAuth } from '../../auth'
import { useTranslation } from '../../i18n'

/** Shown to signed-in travelers whose email is not verified yet: booking and payment are blocked until it is. */
export function EmailVerificationBanner() {
  const { t } = useTranslation()
  const { user, refresh } = useAuth()
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  if (!user || user.role !== 'traveler' || user.email_verified_at) return null

  async function resend() {
    setBusy(true)
    try {
      const result = await resendVerification()
      if (result.already_verified) {
        setMessage(t('verify.already'))
        await refresh()
      } else {
        setMessage(t('verify.resent'))
      }
    } catch (reason) {
      setMessage(apiErrorMessage(reason))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="inline-alert-3d" role="status" style={{ margin: '12px auto', maxWidth: 1280, display: 'flex', alignItems: 'center', gap: '8px 12px', flexWrap: 'wrap', padding: '10px 16px' }}>
      <AlertCircle size={16} className="text-amber" />
      <span style={{ flex: '1 1 220px' }}>{message || t('verify.banner')}</span>
      <button type="button" className="btn-secondary-3d btn-sm" disabled={busy} onClick={() => void resend()}>
        {t('verify.resend')}
      </button>
    </div>
  )
}
