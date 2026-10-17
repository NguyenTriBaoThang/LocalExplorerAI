import { useEffect, useState } from 'react'
import { Check, Copy, Link2, Users, X } from 'lucide-react'
import { getExperiences } from '../../api/client'
import { useTranslation } from '../../i18n'
import type { Itinerary, ItineraryEditProposal } from '../../types'
import type { CollaborationConnectionState } from '../../hooks/useItineraryCollaboration'

interface CollaborationPanelProps {
  itinerary: Itinerary
  currentVersion: number
  proposals: ItineraryEditProposal[]
  inviteActive: boolean
  inviteUrl: string
  connectionState: CollaborationConnectionState
  presenceCount: number
  onCreateInvite: () => Promise<void>
  onRevokeInvite: () => Promise<void>
  onReview: (proposalId: string, decision: 'approve' | 'reject') => boolean
}

const statusStyles: Record<ItineraryEditProposal['status'], string> = {
  pending: 'text-amber',
  approved: 'text-emerald',
  rejected: 'text-rose',
  stale: 'text-slate',
}

export function CollaborationPanel({
  itinerary,
  currentVersion,
  proposals,
  inviteActive,
  inviteUrl,
  connectionState,
  presenceCount,
  onCreateInvite,
  onRevokeInvite,
  onReview,
}: CollaborationPanelProps) {
  const { t, locale } = useTranslation()
  const [names, setNames] = useState<Record<string, string>>({})
  const [slotTimes, setSlotTimes] = useState<Record<string, { start_at: string; end_at: string }>>({})
  const [busy, setBusy] = useState(false)
  const [reviewing, setReviewing] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let active = true
    getExperiences({
      ...(itinerary.start_at ? { start_at: itinerary.start_at } : {}),
      ...(itinerary.return_deadline ? { end_at: itinerary.return_deadline } : {}),
      ...(itinerary.group_size ? { group_size: itinerary.group_size } : {}),
    }).then((items) => {
      if (active) {
        setNames(Object.fromEntries(items.map((item) => [item.id, item.name])))
        const slotTimeEntries = items.flatMap((item) => item.slots.map((slot) => [slot.id, {
          start_at: slot.start_at,
          end_at: slot.end_at,
        }] as const))
        setSlotTimes(Object.fromEntries(slotTimeEntries))
      }
    }).catch(() => undefined)
    return () => { active = false }
  }, [itinerary.itinerary_id, itinerary.start_at, itinerary.return_deadline, itinerary.group_size])

  const currentIds = itinerary.stops.map((stop) => stop.experience_id)
  const displayName = (experienceId: string) =>
    names[experienceId] ?? itinerary.stops.find((stop) => stop.experience_id === experienceId)?.name ?? experienceId.slice(0, 10)
  const displaySlot = (slotId: string) => {
    const slot = slotTimes[slotId]
    if (!slot) return slotId.slice(0, 8)
    const formatter = new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'vi-VN', {
      hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Ho_Chi_Minh',
    })
    return `${formatter.format(new Date(slot.start_at))}–${formatter.format(new Date(slot.end_at))}`
  }

  async function createInvite() {
    setBusy(true)
    try {
      await onCreateInvite()
    } finally {
      setBusy(false)
    }
  }

  async function revokeInvite() {
    setBusy(true)
    try {
      await onRevokeInvite()
    } finally {
      setBusy(false)
    }
  }

  async function copyInvite() {
    try {
      await navigator.clipboard.writeText(inviteUrl)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      // The field remains selectable when clipboard permissions are unavailable.
    }
  }

  function review(proposalId: string, decision: 'approve' | 'reject') {
    setReviewing(proposalId)
    const sent = onReview(proposalId, decision)
    if (!sent) setReviewing('')
    else window.setTimeout(() => setReviewing(''), 1500)
  }

  return (
    <section className="version-diff-card collaboration-panel animate-fadeIn" aria-labelledby="collaboration-heading">
      <div className="version-diff-header">
        <Link2 size={19} className="text-cyan" />
        <div style={{ flex: 1 }}>
          <h3 id="collaboration-heading">{t('collaboration.ownerTitle')}</h3>
          <p>{t('collaboration.ownerDescription')}</p>
        </div>
        <div className="collaboration-live-status" title={t(`collaboration.connection.${connectionState}`)}>
          <span className={`eyebrow-dot ${connectionState === 'connected' ? 'collaboration-dot-online' : ''}`} />
          <span>{t(`collaboration.connection.${connectionState}`)}</span>
          <Users size={14} /> {presenceCount}
        </div>
      </div>

      <div className="collaboration-invite-row">
        <div>
          <strong>{inviteActive ? t('collaboration.inviteActive') : t('collaboration.inviteInactive')}</strong>
          <p>{t('collaboration.inviteExplanation')}</p>
        </div>
        <div className="collaboration-actions">
          <button type="button" className="btn-primary-3d btn-sm" disabled={busy} onClick={() => void createInvite()}>
            <Link2 size={14} />
            {inviteActive ? t('collaboration.rotateInvite') : t('collaboration.createInvite')}
          </button>
          {inviteActive && (
            <button type="button" className="btn-ghost-sm text-rose" disabled={busy} onClick={() => void revokeInvite()}>
              <X size={14} /> {t('collaboration.revokeInvite')}
            </button>
          )}
        </div>
      </div>

      {inviteActive && inviteUrl && (
        <div className="share-input-group collaboration-link-field">
          <input readOnly value={inviteUrl} onFocus={(event) => event.currentTarget.select()} className="share-url-field" aria-label={t('collaboration.inviteLink')} />
          <button type="button" className="btn-secondary-3d btn-sm" onClick={() => void copyInvite()}>
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? t('itinerary.copiedShort') : t('itinerary.copy')}
          </button>
        </div>
      )}

      <div className="collaboration-proposals-heading">
        <h4>{t('collaboration.proposalsTitle')}</h4>
        <span>{proposals.filter((proposal) => proposal.status === 'pending').length} {t('collaboration.pending')}</span>
      </div>
      {proposals.length === 0 ? (
        <p className="collaboration-empty">{t('collaboration.noProposals')}</p>
      ) : (
        <div className="collaboration-proposal-list">
          {proposals.map((proposal) => {
            const proposedIds = proposal.proposed_stops.map((stop) => stop.experience_id)
            const added = proposal.proposed_stops.filter((stop) => !currentIds.includes(stop.experience_id))
            const removed = itinerary.stops.filter((stop) => !proposedIds.includes(stop.experience_id))
            const orderChanged = proposedIds.some((id, index) => currentIds[index] !== id)
            const stale = proposal.status === 'pending' && proposal.base_version !== currentVersion
            return (
              <article className="collaboration-proposal" key={proposal.id}>
                <div className="collaboration-proposal-topline">
                  <strong>{proposal.proposer_name || t('collaboration.traveler')}</strong>
                  <span className={statusStyles[stale ? 'stale' : proposal.status]}>
                    {t(`collaboration.status.${stale ? 'stale' : proposal.status}`)}
                  </span>
                  <small>{t('collaboration.baseVersion', { version: proposal.base_version })}</small>
                </div>
                <div className="collaboration-diff-grid">
                  <div>
                    <strong>{t('collaboration.proposedOrder')}</strong>
                    <ol>
                      {proposal.proposed_stops.map((stop, index) => (
                        <li key={`${stop.experience_id}:${stop.slot_id}`}>
                          <span>{index + 1}. {displayName(stop.experience_id)}</span>
                          <small>{displaySlot(stop.slot_id)}</small>
                        </li>
                      ))}
                    </ol>
                  </div>
                  <div className="collaboration-diff-summary">
                    {added.length > 0 && <p><strong>{t('collaboration.addedStops')}:</strong> {added.map((stop) => displayName(stop.experience_id)).join(', ')}</p>}
                    {removed.length > 0 && <p><strong>{t('collaboration.removedStops')}:</strong> {removed.map((stop) => stop.name).join(', ')}</p>}
                    {orderChanged && added.length === 0 && removed.length === 0 && <p>{t('collaboration.orderChanged')}</p>}
                    {added.length === 0 && removed.length === 0 && !orderChanged && <p>{t('collaboration.noStopChanges')}</p>}
                  </div>
                </div>
                {proposal.status === 'pending' && (
                  <div className="collaboration-review-actions">
                    <button
                      type="button"
                      className="btn-primary-3d btn-sm"
                      disabled={reviewing === proposal.id || connectionState !== 'connected' || stale}
                      onClick={() => void review(proposal.id, 'approve')}
                    >
                      {t('collaboration.approve')}
                    </button>
                    <button
                      type="button"
                      className="btn-ghost-sm text-rose"
                      disabled={reviewing === proposal.id || connectionState !== 'connected'}
                      onClick={() => void review(proposal.id, 'reject')}
                    >
                      {t('collaboration.reject')}
                    </button>
                    {stale && <small>{t('collaboration.staleHelp')}</small>}
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}
      <p className="collaboration-security-note">{t('collaboration.ownerSecurity')}</p>
    </section>
  )
}
