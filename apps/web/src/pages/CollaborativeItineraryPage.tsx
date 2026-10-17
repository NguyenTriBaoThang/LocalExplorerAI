import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowDown, ArrowLeft, ArrowUp, Plus, Send, Trash2, Users } from 'lucide-react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { getCollaborationInvite, getExperiences } from '../api/client'
import { useAuth } from '../auth'
import { useItineraryCollaboration } from '../hooks/useItineraryCollaboration'
import { useTranslation } from '../i18n'
import type { CollaborationInviteSnapshot, Experience, ItineraryCollaborationEvent, ItineraryProposalStop } from '../types'

const timeLabel = (value: string, locale: string) => new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'vi-VN', {
  hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Ho_Chi_Minh',
}).format(new Date(value))

function proposalStatus(status: string, t: (key: string) => string) {
  return t(`collaboration.status.${status}`)
}

export function CollaborativeItineraryPage() {
  const { token = '' } = useParams()
  const { user, loading: authLoading } = useAuth()
  const { t, locale } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const [invite, setInvite] = useState<CollaborationInviteSnapshot | null>(null)
  const [catalog, setCatalog] = useState<Experience[]>([])
  const [draftStops, setDraftStops] = useState<ItineraryProposalStop[]>([])
  const [search, setSearch] = useState('')
  const [selectedExperienceId, setSelectedExperienceId] = useState('')
  const [selectedSlotId, setSelectedSlotId] = useState('')
  const [presenceCount, setPresenceCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const refreshInvite = useCallback(() => getCollaborationInvite(token).then((snapshot) => {
    setInvite(snapshot)
    setError('')
  }), [token])

  useEffect(() => {
    if (!token) return
    let active = true
    setLoading(true)
    getCollaborationInvite(token)
      .then((snapshot) => {
        if (active) {
          setInvite(snapshot)
          setError('')
        }
      })
      .catch(() => {
        if (active) setError(t('collaboration.inviteInvalid'))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [token, user?.id, t])

  useEffect(() => {
    if (!invite) return
    setDraftStops(invite.itinerary.stops.map((stop) => ({ experience_id: stop.experience_id, slot_id: stop.slot_id })))
  }, [invite?.itinerary.itinerary_id, invite?.current_version])

  useEffect(() => {
    if (!invite) return
    let active = true
    const timer = window.setTimeout(() => {
      const params: Record<string, string | number | boolean> = {
        ...(invite.itinerary.start_at ? { start_at: invite.itinerary.start_at } : {}),
        ...(invite.itinerary.return_deadline ? { end_at: invite.itinerary.return_deadline } : {}),
        ...(invite.itinerary.group_size ? { group_size: invite.itinerary.group_size } : {}),
        ...(search.trim() ? { query: search.trim() } : {}),
      }
      getExperiences(params)
        .then((items) => { if (active) setCatalog(items) })
        .catch(() => { if (active) setCatalog([]) })
    }, 250)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [invite?.itinerary.itinerary_id, invite?.itinerary.start_at, invite?.itinerary.return_deadline, invite?.itinerary.group_size, invite?.current_version, search])

  const handleEvent = useCallback((event: ItineraryCollaborationEvent) => {
    if (event.type === 'presence') {
      setPresenceCount(event.count)
    } else if (event.type === 'proposal_created') {
      setInvite((old) => old ? {
        ...old,
        proposals: [event.proposal, ...old.proposals.filter((proposal) => proposal.id !== event.proposal.id)],
      } : old)
    } else if (event.type === 'proposal_reviewed') {
      setInvite((old) => old ? {
        ...old,
        proposals: old.proposals.map((proposal) => proposal.id === event.proposal.id ? event.proposal : proposal),
      } : old)
      if (event.error) setNotice(event.error)
      if (event.proposal.status === 'stale' && event.current_version !== invite?.current_version) {
        void refreshInvite().catch(() => setError(t('collaboration.refreshFailed')))
      }
    } else if (event.type === 'itinerary_updated') {
      if (event.itinerary) {
        setInvite((old) => old ? { ...old, itinerary: event.itinerary!, current_version: event.current_version } : old)
      } else {
        void refreshInvite().catch(() => setError(t('collaboration.refreshFailed')))
      }
    } else if (event.type === 'error') {
      const key = `collaboration.error.${event.code}`
      const translated = t(key)
      setNotice(translated === key ? event.message : translated)
      if (event.code === 'INVITE_REVOKED') setError(t('collaboration.inviteInvalid'))
    }
  }, [invite?.current_version, refreshInvite, t])

  const socket = useItineraryCollaboration({
    url: token ? '/api/collaborations/ws' : null,
    onEvent: handleEvent,
    identityKey: user?.id ?? 'anonymous',
    inviteToken: token,
  })

  useEffect(() => {
    if (socket.state !== 'connected') return
    void refreshInvite().catch(() => setError(t('collaboration.refreshFailed')))
  }, [socket.state, refreshInvite, t])

  const experienceById = useMemo(() => new Map(catalog.map((item) => [item.id, item])), [catalog])
  const currentStopByPair = useMemo(() => new Map(
    (invite?.itinerary.stops ?? []).map((stop) => [`${stop.experience_id}:${stop.slot_id}`, stop]),
  ), [invite?.itinerary.stops])
  const selectedExperience = experienceById.get(selectedExperienceId)
  const selectableSlots = (selectedExperience?.slots ?? []).filter((slot) =>
    !['full', 'unavailable', 'cancelled'].includes(slot.status)
    && (slot.available_reported === null || slot.available_reported >= (invite?.itinerary.group_size ?? 1)),
  )
  const canSubmit = Boolean(user?.role === 'traveler' && invite?.can_submit)

  function moveStop(index: number, delta: -1 | 1) {
    const target = index + delta
    if (target < 0 || target >= draftStops.length) return
    const source = draftStops[index]
    const pair = `${source.experience_id}:${source.slot_id}`
    if (currentStopByPair.get(pair)?.locked) return
    setDraftStops((old) => {
      const next = [...old]
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }

  function removeStop(index: number) {
    const stop = draftStops[index]
    if (currentStopByPair.get(`${stop.experience_id}:${stop.slot_id}`)?.locked) return
    setDraftStops((old) => old.filter((_, position) => position !== index))
  }

  function addStop() {
    if (!selectedExperience || !selectedSlotId || draftStops.length >= 6) return
    if (draftStops.some((stop) => stop.experience_id === selectedExperience.id)) {
      setNotice(t('collaboration.duplicateExperience'))
      return
    }
    setDraftStops((old) => [...old, { experience_id: selectedExperience.id, slot_id: selectedSlotId }])
    setSelectedSlotId('')
  }

  function submitProposal() {
    if (!invite || !canSubmit) return
    const sent = socket.send({ type: 'submit_proposal', base_version: invite.current_version, stops: draftStops })
    if (!sent) {
      setNotice(t('collaboration.waitForConnection'))
      return
    }
    setNotice(t('collaboration.proposalSent'))
  }

  function requestSignIn() {
    navigate('/login', { state: { from: `${location.pathname}${location.search}` } })
  }

  function requestRegistration() {
    navigate('/register', { state: { from: `${location.pathname}${location.search}` } })
  }

  if (loading || authLoading) {
    return <div className="page-wrap page-loading-3d"><span className="loader-orbit" /><p>{t('collaboration.loading')}</p></div>
  }

  if (error || !invite) {
    return (
      <div className="page-wrap not-found-3d">
        <div className="not-found-card">
          <h1>{t('collaboration.inviteTitle')}</h1>
          <p>{error || t('collaboration.inviteInvalid')}</p>
          <Link to="/explore" className="btn-primary-3d">{t('nav.explore')}</Link>
        </div>
      </div>
    )
  }

  const itinerary = invite.itinerary
  const names = new Map(itinerary.stops.map((stop) => [stop.experience_id, stop.name]))
  const displayName = (experienceId: string) => experienceById.get(experienceId)?.name ?? names.get(experienceId) ?? experienceId.slice(0, 10)

  return (
    <div className="page-wrap collaborative-itinerary-page">
      <Link to="/explore" className="btn-back-link"><ArrowLeft size={16} /> {t('nav.explore')}</Link>
      <header className="collaborative-header">
        <div>
          <span className="eyebrow-3d">{t('collaboration.inviteEyebrow')}</span>
          <h1>{t('collaboration.inviteTitle')}</h1>
          <p>{t('collaboration.inviteDescription')}</p>
        </div>
        <div className="collaboration-live-status">
          <span className={`eyebrow-dot ${socket.connected ? 'collaboration-dot-online' : ''}`} />
          {t(`collaboration.connection.${socket.state}`)}
          <Users size={15} /> {presenceCount}
        </div>
      </header>

      {notice && <div className="inline-alert-3d" role="status">{notice}</div>}

      <section className="collaborative-summary-card">
        <div>
          <strong>{t('collaboration.currentVersion', { version: invite.current_version })}</strong>
          <p>{t('collaboration.tripSummary', { stops: itinerary.stops.length, group: itinerary.group_size ?? 1 })}</p>
        </div>
        <div className="collaborative-summary-kpis">
          <span>{itinerary.estimated_cost_vnd.toLocaleString(locale === 'en' ? 'en-US' : 'vi-VN')}₫</span>
          <span>{itinerary.total_travel_min} {t('collaboration.travelMinutes')}</span>
        </div>
      </section>

      <section className="collaborative-editor-card">
        <div className="collaborative-section-heading">
          <div>
            <h2>{t('collaboration.editorTitle')}</h2>
            <p>{t('collaboration.editorDescription')}</p>
          </div>
          <span className="collaboration-count-chip">{draftStops.length}/6</span>
        </div>

        <ol className="collaborative-stop-list">
          {draftStops.map((stop, index) => {
            const existing = currentStopByPair.get(`${stop.experience_id}:${stop.slot_id}`)
            return (
              <li className="collaborative-stop-row" key={`${stop.experience_id}:${stop.slot_id}`}>
                <span className="collaborative-stop-number">{index + 1}</span>
                <div className="collaborative-stop-detail">
                  <strong>{displayName(stop.experience_id)}</strong>
                  <small>{existing ? `${timeLabel(existing.start_at, locale)} – ${timeLabel(existing.end_at, locale)}` : stop.slot_id.slice(0, 8)}</small>
                </div>
                {existing?.locked && <span className="collaboration-locked-chip">{t('collaboration.lockedStop')}</span>}
                <div className="collaborative-stop-actions">
                  <button type="button" className="btn-action-icon" aria-label={t('collaboration.moveUp')} disabled={!canSubmit || index === 0 || Boolean(existing?.locked)} onClick={() => moveStop(index, -1)}><ArrowUp size={15} /></button>
                  <button type="button" className="btn-action-icon" aria-label={t('collaboration.moveDown')} disabled={!canSubmit || index === draftStops.length - 1 || Boolean(existing?.locked)} onClick={() => moveStop(index, 1)}><ArrowDown size={15} /></button>
                  <button type="button" className="btn-action-icon text-rose" aria-label={t('collaboration.removeStop')} disabled={!canSubmit || Boolean(existing?.locked)} onClick={() => removeStop(index)}><Trash2 size={15} /></button>
                </div>
              </li>
            )
          })}
        </ol>

        <div className="collaborative-add-stop">
          <label>
            <span>{t('collaboration.searchExperience')}</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('collaboration.searchPlaceholder')} disabled={!canSubmit} />
          </label>
          <label>
            <span>{t('collaboration.chooseExperience')}</span>
            <select value={selectedExperienceId} onChange={(event) => { setSelectedExperienceId(event.target.value); setSelectedSlotId('') }} disabled={!canSubmit}>
              <option value="">{t('collaboration.chooseExperiencePlaceholder')}</option>
              {catalog.filter((item) => !draftStops.some((stop) => stop.experience_id === item.id)).map((experience) => (
                <option key={experience.id} value={experience.id}>{experience.name}</option>
              ))}
            </select>
          </label>
          <label>
            <span>{t('collaboration.chooseSlot')}</span>
            <select value={selectedSlotId} onChange={(event) => setSelectedSlotId(event.target.value)} disabled={!canSubmit || !selectedExperience}>
              <option value="">{t('collaboration.chooseSlotPlaceholder')}</option>
              {selectableSlots.map((slot) => (
                <option key={slot.id} value={slot.id}>{timeLabel(slot.start_at, locale)} – {timeLabel(slot.end_at, locale)} · {slot.status}</option>
              ))}
            </select>
          </label>
          <button type="button" className="btn-secondary-3d" disabled={!canSubmit || !selectedSlotId || draftStops.length >= 6} onClick={addStop}>
            <Plus size={15} /> {t('collaboration.addStop')}
          </button>
        </div>

        {!canSubmit ? (
          <div className="collaboration-signin-prompt">
            <p>{user ? t('collaboration.travelerAccountRequired') : t('collaboration.signInRequired')}</p>
            {!user && (
              <div className="collaboration-actions">
                <button type="button" className="btn-primary-3d" onClick={requestSignIn}>{t('collaboration.signInToPropose')}</button>
                <button type="button" className="btn-secondary-3d" onClick={requestRegistration}>{t('collaboration.registerToPropose')}</button>
              </div>
            )}
          </div>
        ) : (
          <div className="collaboration-submit-row">
            <p>{t('collaboration.ownerApprovalRequired')}</p>
            <button type="button" className="btn-primary-3d" disabled={!socket.connected || draftStops.length === 0} onClick={submitProposal}>
              <Send size={15} /> {t('collaboration.submitProposal')}
            </button>
          </div>
        )}
      </section>

      <section className="collaborative-proposals-card">
        <div className="collaborative-section-heading">
          <div><h2>{t('collaboration.proposalsTitle')}</h2><p>{t('collaboration.proposalsDescription')}</p></div>
        </div>
        {invite.proposals.length === 0 ? <p className="collaboration-empty">{t('collaboration.noProposals')}</p> : (
          <div className="collaboration-proposal-list">
            {invite.proposals.map((proposal) => (
              <article className="collaboration-proposal" key={proposal.id}>
                <div className="collaboration-proposal-topline">
                  <strong>{proposal.proposer_name || t('collaboration.traveler')}</strong>
                  <span>{proposalStatus(proposal.status, t)}</span>
                  <small>{t('collaboration.baseVersion', { version: proposal.base_version })}</small>
                </div>
                <ol>{proposal.proposed_stops.map((stop, index) => <li key={`${stop.experience_id}:${stop.slot_id}`}>{index + 1}. {displayName(stop.experience_id)}</li>)}</ol>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
