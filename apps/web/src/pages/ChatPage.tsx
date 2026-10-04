import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import {
  ArrowRight,
  Bot,
  CalendarDays,
  Check,
  CircleHelp,
  LoaderCircle,
  MapPin,
  RotateCcw,
  Send,
  Sparkles,
  Users,
  Wallet,
  Clock,
  Bike,
  Car,
  Footprints,
  Bus,
  CheckCircle2,
  AlertCircle,
  Lock,
  Layers,
  Zap,
  Info,
  ChevronDown,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { api, apiErrorMessage, createItinerary, getChatServiceStatus, getRoutingCapabilities, sendChatMessage } from '../api/client'
import type { ChatConstraints, ChatServiceStatus, POI, RoutingCapabilities } from '../types'
import { useTranslation } from '../i18n'

type ChatLine = {
  id: string
  role: 'assistant' | 'user'
  text: string
  time?: string
  snapshot?: Partial<ChatConstraints>
  assistantMode?: 'openai_compatible' | 'local_fallback'
}

const localDate = (date: Date) =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(date)

function formatTimeOnly(date: Date, locale: string) {
  return new Intl.DateTimeFormat(locale === 'vi' ? 'vi-VN' : 'en-US', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function makeConversationId() {
  return globalThis.crypto?.randomUUID?.() ?? `chat-${Date.now()}`
}

function foldPlaceName(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLocaleLowerCase('vi-VN')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

function findMatchingPoi(name: string, pois: POI[]) {
  const needle = foldPlaceName(name)
  if (needle.length < 3) return undefined
  return pois.find((poi) => {
    const candidate = foldPlaceName(poi.name)
    return candidate === needle || (needle.length >= 5 && (candidate.includes(needle) || needle.includes(candidate)))
  })
}

function formatMoney(value: number) {
  return `${new Intl.NumberFormat('vi-VN').format(value)} ₫`
}

function calculateDurationHours(start?: string | null, end?: string | null, unit: string = 'giờ'): string | null {
  if (!start || !end) return null
  try {
    const [sh, sm] = start.split(':').map(Number)
    const [eh, em] = end.split(':').map(Number)
    const diffMin = (eh * 60 + em) - (sh * 60 + sm)
    if (diffMin <= 0) return null
    const hours = (diffMin / 60).toFixed(1).replace('.0', '')
    return `${hours} ${unit}`
  } catch {
    return null
  }
}

function getChatError(reason: unknown) {
  if (typeof reason === 'object' && reason !== null && 'response' in reason) {
    const response = (reason as { response?: unknown }).response
    if (response) return apiErrorMessage(reason)
  }
  if (reason instanceof Error && reason.message && reason.message !== 'Network Error') return reason.message
  return 'Không kết nối được API. Kiểm tra máy chủ rồi thử lại.'
}

/** Formats simple markdown bold (**text**) and line breaks into JSX */
function FormattedChatMessage({ content }: { content: string }) {
  const lines = content.split('\n')
  return (
    <div className="chat-rich-text">
      {lines.map((line, lIdx) => {
        const trimmed = line.trim()
        const isBullet = trimmed.startsWith('- ') || trimmed.startsWith('• ')
        const text = isBullet ? trimmed.replace(/^[-•]\s*/, '') : line

        // Parse bold segments
        const parts = text.split(/(\*\*[^*]+\*\*)/g)
        const rendered = parts.map((part, pIdx) => {
          if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={pIdx}>{part.slice(2, -2)}</strong>
          }
          return part
        })

        if (isBullet) {
          return (
            <div key={lIdx} className="chat-bullet-row">
              <span className="chat-bullet-dot" />
              <span>{rendered}</span>
            </div>
          )
        }

        return (
          <p key={lIdx} className={line === '' ? 'chat-p-blank' : 'chat-p'}>
            {rendered}
          </p>
        )
      })}
    </div>
  )
}

export function ChatPage() {
  const { t, locale } = useTranslation()
  const navigate = useNavigate()

  const initialMessage = useMemo<ChatLine>(() => ({
    id: 'welcome',
    role: 'assistant',
    text: t('chat.welcome'),
    time: t('chat.justNow'),
  }), [t])

  const [conversationId, setConversationId] = useState(makeConversationId)
  const [messages, setMessages] = useState<ChatLine[]>([initialMessage])
  const [userTurns, setUserTurns] = useState<string[]>([])
  const [constraints, setConstraints] = useState<ChatConstraints | null>(null)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [pois, setPois] = useState<POI[]>([])
  const [poiError, setPoiError] = useState('')
  const [routingCapabilities, setRoutingCapabilities] = useState<RoutingCapabilities | null>(null)
  const [chatServiceStatus, setChatServiceStatus] = useState<ChatServiceStatus | null>(null)
  const [date, setDate] = useState(() => {
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    return localDate(tomorrow)
  })
  const [originId, setOriginId] = useState('')
  const [destinationId, setDestinationId] = useState('')
  const [lockedOverrides, setLockedOverrides] = useState<Record<number, string>>({})
  const feedContainerRef = useRef<HTMLDivElement>(null)
  const feedEndRef = useRef<HTMLDivElement>(null)
  const [isAtBottom, setIsAtBottom] = useState(true)

  const scrollToBottom = (smooth = true) => {
    const el = feedContainerRef.current
    if (!el) return
    el.scrollTo({
      top: el.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto',
    })
    setIsAtBottom(true)
  }

  const handleFeedScroll = () => {
    const el = feedContainerRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    setIsAtBottom(distanceFromBottom < 75)
  }

  // Update initial message on locale change if conversation has not started
  useEffect(() => {
    if (userTurns.length === 0) {
      setMessages([initialMessage])
    }
  }, [initialMessage, userTurns.length])

  useEffect(() => {
    let active = true
    api.get<POI[]>('/pois')
      .then(({ data }) => { if (active) setPois(data) })
      .catch((reason: unknown) => { if (active) setPoiError(getChatError(reason)) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    void getChatServiceStatus()
      .then((status) => { if (active) setChatServiceStatus(status) })
      .catch(() => { if (active) setChatServiceStatus(null) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    void getRoutingCapabilities()
      .then((capabilities) => { if (active) setRoutingCapabilities(capabilities) })
      .catch(() => { if (active) setRoutingCapabilities(null) })
    return () => { active = false }
  }, [])

  // Auto-scroll inside feed container only when user is near bottom or messages change
  useEffect(() => {
    if (isAtBottom && feedContainerRef.current) {
      feedContainerRef.current.scrollTo({
        top: feedContainerRef.current.scrollHeight,
        behavior: 'smooth',
      })
    }
  }, [messages, busy, isAtBottom])

  const lockedPlaces = useMemo(() => (constraints?.locked_pois ?? []).map((name, index) => ({
    name,
    poiId: lockedOverrides[index] !== undefined
      ? lockedOverrides[index]
      : findMatchingPoi(name, pois)?.id ?? '',
  })), [constraints, lockedOverrides, pois])

  const unresolvedLockedPlaces = lockedPlaces.filter((place) => !place.poiId)
  const plannerTravelMode = constraints?.travel_mode === 'car' ? 'car' : constraints?.travel_mode
  const unsupportedTravelMode = Boolean(
    routingCapabilities && plannerTravelMode && !routingCapabilities.supported_modes.includes(plannerTravelMode),
  )
  const routingUnavailable = routingCapabilities?.configured === false
  const canCreateItinerary = Boolean(
    constraints?.is_complete && originId && destinationId && !poiError &&
    unresolvedLockedPlaces.length === 0 && !unsupportedTravelMode && !routingUnavailable && !busy && !creating,
  )

  const criteriaStatus = useMemo(() => {
    const hasGroup = Boolean(constraints?.group_size)
    const hasTime = Boolean(constraints?.start_time && constraints?.return_deadline)
    const hasBudget = Boolean(constraints?.budget_vnd)
    const hasIntents = Boolean(
      constraints?.intent_weights &&
      Object.values(constraints.intent_weights).some((w) => w > 0)
    )

    const totalCriteria = 4
    let metCriteria = 0
    if (hasGroup) metCriteria++
    if (hasTime) metCriteria++
    if (hasBudget) metCriteria++
    if (hasIntents) metCriteria++

    const percentage = Math.round((metCriteria / totalCriteria) * 100)
    return {
      hasGroup,
      hasTime,
      hasBudget,
      hasIntents,
      percentage,
      metCriteria,
      totalCriteria,
    }
  }, [constraints])

  const durationStr = useMemo(() => {
    return calculateDurationHours(
      constraints?.start_time,
      constraints?.return_deadline,
      locale === 'en' ? 'hrs' : 'giờ'
    )
  }, [constraints?.start_time, constraints?.return_deadline, locale])

  const quickPresets = useMemo(() => [
    {
      icon: '🍜',
      title: t('chat.presetFoodTitle'),
      prompt: t('chat.presetFoodPrompt'),
    },
    {
      icon: '🎨',
      title: t('chat.presetCraftTitle'),
      prompt: t('chat.presetCraftPrompt'),
    },
    {
      icon: '🏛️',
      title: t('chat.presetCultureTitle'),
      prompt: t('chat.presetCulturePrompt'),
    },
    {
      icon: '⛵',
      title: t('chat.presetNightTitle'),
      prompt: t('chat.presetNightPrompt'),
    },
  ], [t])

  const intentConfigs: Record<string, { label: string; icon: string; color: string; barClass: string }> = useMemo(() => ({
    'thủ_công': { label: t('home.catCraft'), icon: '🎨', color: '#f59e0b', barClass: 'intent-bar-craft' },
    'ẩm_thực': { label: t('home.catFood'), icon: '🍜', color: '#f97316', barClass: 'intent-bar-food' },
    'văn_hóa': { label: t('home.catCulture'), icon: '🏛️', color: '#10b981', barClass: 'intent-bar-culture' },
    'thư_giãn': { label: t('home.catNature'), icon: '🌿', color: '#06b6d4', barClass: 'intent-bar-relax' },
  }), [t])

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || busy) return

    const nextTurns = [...userTurns, text]
    const transcript = nextTurns.map((turn, index) => `Tin nhắn ${index + 1} của du khách: ${turn}`).join('\n')
    if (transcript.length > 3900) {
      setError(locale === 'en'
        ? 'Conversation is very long. Please start a new chat to prevent dropping earlier constraints.'
        : 'Cuộc trò chuyện đã dài. Hãy bắt đầu cuộc trò chuyện mới để tránh bỏ sót ràng buộc cũ.')
      return
    }

    const nowStr = formatTimeOnly(new Date(), locale)
    setDraft('')
    setError('')
    setUserTurns(nextTurns)
    setMessages((current) => [...current, { id: `user-${Date.now()}`, role: 'user', text, time: nowStr }])
    setBusy(true)

    try {
      const result = await sendChatMessage(transcript, conversationId)
      setConstraints(result.structured_constraints)
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          text: result.reply || result.structured_constraints.clarification_question_vi || t('chat.constraintsDesc'),
          time: formatTimeOnly(new Date(), locale),
          snapshot: result.structured_constraints,
          assistantMode: result.assistant_mode,
        },
      ])
    } catch (reason) {
      setError(getChatError(reason))
      setMessages((current) => [
        ...current,
        {
          id: `error-${Date.now()}`,
          role: 'assistant',
          text: locale === 'en'
            ? 'Unable to connect to semantic parsing engine. Please check API server connection.'
            : 'Mình chưa kết nối được bộ phân tích ngôn ngữ. Bạn vui lòng kiểm tra kết nối API và khóa cấu hình mô hình nhé.',
          time: formatTimeOnly(new Date(), locale),
        },
      ])
    } finally {
      setBusy(false)
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  function startNewConversation() {
    setConversationId(makeConversationId())
    setMessages([initialMessage])
    setUserTurns([])
    setConstraints(null)
    setDraft('')
    setError('')
    setLockedOverrides({})
  }

  function selectPreset(promptText: string) {
    setDraft(promptText)
  }

  async function createFromChat() {
    if (!constraints?.is_complete || !originId || !destinationId || unresolvedLockedPlaces.length) return
    setError('')
    setCreating(true)
    try {
      const startAt = new Date(`${date}T${constraints.start_time}:00+07:00`)
      const returnAt = new Date(`${date}T${constraints.return_deadline}:00+07:00`)
      if (startAt.getTime() <= Date.now()) {
        throw new Error(locale === 'en'
          ? 'Start time has passed. Please select a future date or adjust the start time.'
          : 'Giờ bắt đầu đã qua. Hãy chọn ngày đi khác hoặc điều chỉnh giờ bắt đầu.')
      }
      if (returnAt <= startAt) {
        throw new Error(locale === 'en'
          ? 'Return time must be after start time on the same date.'
          : 'Giờ về phải sau giờ bắt đầu trong cùng ngày. Hãy điều chỉnh giờ trong cuộc trò chuyện.')
      }

      const origin = pois.find((poi) => poi.id === originId)
      const destination = pois.find((poi) => poi.id === destinationId)
      if (!origin || !destination) {
        throw new Error(locale === 'en'
          ? 'Departure or destination landmark not found in catalog.'
          : 'Không tìm thấy điểm xuất phát hoặc điểm về trong danh mục.')
      }
      if (routingCapabilities && !routingCapabilities.supported_modes.includes(constraints.travel_mode)) {
        throw new Error(locale === 'en'
          ? `${constraints.travel_mode} routing is not supported by ${routingCapabilities.provider}. Choose motorcycle, walking, or car in the chat.`
          : `${routingCapabilities.provider} chưa hỗ trợ phương tiện “${constraints.travel_mode}”. Hãy nhắn lại để chọn xe máy, đi bộ hoặc ô tô.`)
      }
      if (routingUnavailable) {
        throw new Error(locale === 'en'
          ? `Routing provider ${routingCapabilities?.provider} is not configured. Set its API key before planning.`
          : `Chưa cấu hình khóa API cho nhà cung cấp tuyến đường ${routingCapabilities?.provider}.`)
      }

      const result = await createItinerary({
        start_at: startAt.toISOString(),
        end_at: returnAt.toISOString(),
        group_size: constraints.group_size!,
        budget_vnd: constraints.budget_vnd!,
        transport_mode: constraints.travel_mode,
        intent_weights: constraints.intent_weights,
        locked_experience_ids: [],
        locked_poi_ids: lockedPlaces.map((place) => place.poiId),
        origin_latitude: origin.latitude,
        origin_longitude: origin.longitude,
        origin_label: origin.name,
        destination_latitude: destination.latitude,
        destination_longitude: destination.longitude,
        destination_label: destination.name,
      })
      navigate(`/itinerary/${result.itinerary_id}`, { state: { itinerary: result } })
    } catch (reason) {
      setError(getChatError(reason))
    } finally {
      setCreating(false)
    }
  }

  const travelModeIcons = {
    motorcycle: <Bike size={15} />,
    car: <Car size={15} />,
    walking: <Footprints size={15} />,
    transit: <Bus size={15} />,
  }

  const modeLabels: Record<ChatConstraints['travel_mode'], string> = {
    motorcycle: locale === 'en' ? 'Motorbike' : 'Xe máy',
    walking: locale === 'en' ? 'Walking' : 'Đi bộ',
    car: locale === 'en' ? 'Car / Taxi' : 'Ô tô',
    transit: locale === 'en' ? 'Bus / Transit' : 'Xe buýt / Công cộng',
  }

  return (
    <div className="page-wrap chat-page">
      {/* Page Header */}
      <header className="chat-page-heading">
        <div className="chat-heading-left">
          <div className="chat-badge-live">
            <span className="live-dot-pulse" />
            <span>{t('chat.tagline')}</span>
          </div>
          <h1 className="page-heading-3d">
            {t('chat.heading1')} <span className="gradient-text-emerald">{t('chat.headingHighlight')}</span>
          </h1>
          <p className="page-subtext-3d">
            {t('chat.subtext')}
          </p>
        </div>

        <div className="chat-heading-actions">
          <button
            type="button"
            className="chat-reset-button"
            onClick={startNewConversation}
            disabled={busy || creating}
            title={t('chat.resetChat')}
          >
            <RotateCcw size={15} />
            <span>{t('chat.newChatBtn')}</span>
          </button>
        </div>
      </header>

      {/* Main Grid Workspace */}
      <div className="chat-workspace">
        {/* Left Side: Interactive Chat Panel */}
        <section className="chat-panel" aria-label="AI Chat Panel">
          <div className="chat-panel-topbar">
            <div className="chat-avatar-ring">
              <Bot size={22} className="chat-assistant-bot" />
            </div>
            <div className="chat-topbar-meta">
              <div className="chat-assistant-name-row">
                <strong>Local Explorer Concierge</strong>
                <span className="chat-status-pill">
                  <span className="chat-online-dot" /> {t('chat.online')}
                </span>
              </div>
              <span className="chat-subtitle-note">
                {t('chat.solverSub')}
              </span>
            </div>
            <div className="chat-topbar-badges">
              <span className="chat-prompt-version">
                {chatServiceStatus?.assistant_mode === 'openai_compatible' || chatServiceStatus?.assistant_mode === 'gemini_compatible'
                  ? (chatServiceStatus.assistant_mode === 'gemini_compatible'
                    ? 'LLM · Gemini'
                    : (locale === 'en' ? 'LLM · OpenAI-compatible' : 'LLM · OpenAI-compatible'))
                  : chatServiceStatus?.fallback_available
                    ? (locale === 'en' ? 'Offline fallback available' : 'Có dự phòng ngoại tuyến')
                    : chatServiceStatus
                      ? (locale === 'en' ? 'AI parsing unavailable' : 'Bộ phân tích AI chưa sẵn sàng')
                      : (locale === 'en' ? 'AI status unknown' : 'Chưa xác định trạng thái AI')}
              </span>
            </div>
          </div>

          {/* Messages Feed */}
          <div
            className="chat-message-feed"
            ref={feedContainerRef}
            onScroll={handleFeedScroll}
            aria-live="polite"
            aria-relevant="additions text"
          >
            {messages.map((message) => (
              <div
                key={message.id}
                className={`chat-message-row ${message.role === 'user' ? 'chat-message-user' : 'chat-message-assistant'}`}
              >
                {message.role === 'assistant' && (
                  <div className="chat-message-avatar">
                    <Bot size={16} />
                  </div>
                )}

                <div className="chat-bubble-container">
                  <div className={`chat-bubble ${message.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'}`}>
                    <FormattedChatMessage content={message.text} />
                  </div>

                  {message.assistantMode === 'local_fallback' && (
                    <span className="chat-prompt-version">
                      {locale === 'en' ? 'Offline rule-based fallback · verify extracted values' : 'Dự phòng bằng quy tắc ngoại tuyến · hãy kiểm tra dữ liệu'}
                    </span>
                  )}

                  {/* AI Snapshot Pills if constraints detected on assistant turn */}
                  {message.role === 'assistant' && message.snapshot && (
                    <div className="chat-snapshot-bar">
                      <span className="snapshot-label">
                        <Sparkles size={11} className="text-amber" /> {t('chat.extractedLabel')}
                      </span>
                      {message.snapshot.group_size && (
                        <span className="snapshot-tag">
                          <Users size={11} /> {message.snapshot.group_size} {t('chat.peopleUnit')}
                        </span>
                      )}
                      {message.snapshot.start_time && message.snapshot.return_deadline && (
                        <span className="snapshot-tag">
                          <Clock size={11} /> {message.snapshot.start_time} - {message.snapshot.return_deadline}
                        </span>
                      )}
                      {message.snapshot.budget_vnd != null && (
                        <span className="snapshot-tag">
                          <Wallet size={11} /> {formatMoney(message.snapshot.budget_vnd)}
                        </span>
                      )}
                      {message.snapshot.travel_mode && (
                        <span className="snapshot-tag">
                          {travelModeIcons[message.snapshot.travel_mode]} {modeLabels[message.snapshot.travel_mode]}
                        </span>
                      )}
                    </div>
                  )}

                  {message.time && <span className="chat-time-tag">{message.time}</span>}
                </div>
              </div>
            ))}

            {busy && (
              <div className="chat-message-row chat-message-assistant">
                <div className="chat-message-avatar">
                  <Bot size={16} />
                </div>
                <div className="chat-bubble chat-bubble-assistant chat-thinking">
                  <div className="chat-pulse-dots">
                    <span />
                    <span />
                    <span />
                  </div>
                  <span>{t('chat.thinkingLong')}</span>
                </div>
              </div>
            )}
            <div ref={feedEndRef} />
          </div>

          {/* Quick Preset Starters */}
          {!userTurns.length && (
            <div className="chat-starter-container">
              <div className="starter-header">
                <Sparkles size={13} className="text-amber" />
                <span>{t('chat.startersTitle')}</span>
              </div>
              <div className="starter-grid">
                {quickPresets.map((preset, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="starter-card"
                    onClick={() => selectPreset(preset.prompt)}
                  >
                    <div className="starter-card-top">
                      <span className="starter-emoji">{preset.icon}</span>
                      <strong className="starter-title">{preset.title}</strong>
                    </div>
                    <p className="starter-desc">{preset.prompt}</p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Floating Jump to Bottom Button */}
          {!isAtBottom && (
            <button
              type="button"
              className="chat-scroll-bottom-btn"
              onClick={() => scrollToBottom(true)}
              aria-label={locale === 'en' ? 'Scroll to bottom' : 'Cuộn xuống tin nhắn mới nhất'}
              title={locale === 'en' ? 'Scroll to bottom' : 'Cuộn xuống tin nhắn mới nhất'}
            >
              <ChevronDown size={15} />
              <span>{locale === 'en' ? 'Latest messages' : 'Tin nhắn mới nhất'}</span>
            </button>
          )}

          {/* Composer Form */}
          <form className="chat-composer" onSubmit={submitMessage}>
            <label className="sr-only" htmlFor="chat-message">
              {t('chat.placeholder')}
            </label>
            <textarea
              id="chat-message"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder={t('chat.composerPlaceholder')}
              maxLength={1000}
              rows={2}
              disabled={busy}
            />
            <div className="chat-composer-bottom">
              <div className="chat-composer-hint">
                {t('chat.composerHint')}
              </div>
              <button
                type="submit"
                className="chat-send-button"
                disabled={!draft.trim() || busy}
                aria-label={t('chat.send')}
              >
                {busy ? <LoaderCircle size={18} className="chat-spinner" /> : <Send size={16} />}
              </button>
            </div>
          </form>

          <p className="chat-model-note">
            <Info size={13} className="inline mr-1 text-cyan" />
            {t('chat.modelNote')}
          </p>
        </section>

        {/* Right Side: Trip Dashboard & Constraints HUD */}
        <aside className="chat-trip-sidebar">
          {/* Realtime Progress & HUD Card */}
          <section className="chat-sidebar-card hud-progress-card">
            <div className="chat-sidebar-title">
              <Sparkles size={17} className="text-emerald" />
              <h2>{t('chat.conditionsCardTitle')}</h2>
              <span className={`hud-state-pill ${constraints?.is_complete ? 'is-complete' : ''}`}>
                {constraints?.is_complete ? (
                  <>
                    <Check size={12} /> {t('chat.complete100')}
                  </>
                ) : (
                  <>
                    <CircleHelp size={12} /> {t('chat.criteriaMet', { met: criteriaStatus.metCriteria, total: criteriaStatus.totalCriteria })}
                  </>
                )}
              </span>
            </div>

            {/* Completeness progress bar */}
            <div className="hud-progress-meter">
              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{ width: `${criteriaStatus.percentage}%` }}
                />
              </div>
              <div className="progress-labels">
                <span>{t('chat.completenessMeter')}</span>
                <strong>{criteriaStatus.percentage}%</strong>
              </div>
            </div>

            {/* 4 Essential Parameter Grid */}
            <div className="hud-param-grid">
              {/* Group Size */}
              <div className={`param-cell ${criteriaStatus.hasGroup ? 'param-active' : ''}`}>
                <div className="param-header">
                  <Users size={14} className="text-cyan" />
                  <span>{t('chat.scaleLabel')}</span>
                </div>
                <div className="param-val">
                  {constraints?.group_size ? `${constraints.group_size} ${t('chat.peopleUnit')}` : '—'}
                </div>
                <div className="param-sub">
                  {constraints?.group_size ? t('chat.privateGroup') : t('chat.unspecified')}
                </div>
              </div>

              {/* Time Window */}
              <div className={`param-cell ${criteriaStatus.hasTime ? 'param-active' : ''}`}>
                <div className="param-header">
                  <Clock size={14} className="text-emerald" />
                  <span>{t('chat.timeWindow')}</span>
                </div>
                <div className="param-val">
                  {constraints?.start_time && constraints?.return_deadline
                    ? `${constraints.start_time} - ${constraints.return_deadline}`
                    : '—'}
                </div>
                <div className="param-sub">
                  {durationStr ? t('chat.durationPrefix', { duration: durationStr }) : t('chat.unspecified')}
                </div>
              </div>

              {/* Budget */}
              <div className={`param-cell ${criteriaStatus.hasBudget ? 'param-active' : ''}`}>
                <div className="param-header">
                  <Wallet size={14} className="text-amber" />
                  <span>{t('chat.budget')}</span>
                </div>
                <div className="param-val">
                  {constraints?.budget_vnd != null ? formatMoney(constraints.budget_vnd) : '—'}
                </div>
                <div className="param-sub">
                  {constraints?.budget_vnd && constraints?.group_size
                    ? `~${formatMoney(Math.round(constraints.budget_vnd / constraints.group_size))}/${locale === 'en' ? 'person' : 'người'}`
                    : t('chat.totalFund')}
                </div>
              </div>

              {/* Travel Mode */}
              <div className="param-cell param-active">
                <div className="param-header">
                  {travelModeIcons[constraints?.travel_mode ?? 'motorcycle']}
                  <span>{t('chat.transport')}</span>
                </div>
                <div className="param-val">
                  {modeLabels[constraints?.travel_mode ?? 'motorcycle']}
                </div>
                <div className={`param-sub ${unsupportedTravelMode ? 'text-amber' : ''}`}>
                  {routingUnavailable
                    ? (locale === 'en' ? `API key missing for ${routingCapabilities?.provider}.` : `Thiếu khóa API ${routingCapabilities?.provider}.`)
                    : unsupportedTravelMode
                      ? (locale === 'en' ? `Unsupported by ${routingCapabilities?.provider}; choose motorcycle, walking, or car.` : `Nhà cung cấp ${routingCapabilities?.provider} chưa hỗ trợ; hãy chọn xe máy, đi bộ hoặc ô tô.`)
                      : t('chat.autoEta')}
                </div>
              </div>
            </div>

            {/* Missing Fields Checklist */}
            {constraints && !constraints.is_complete && (
              <div className="hud-missing-checklist">
                <span className="checklist-title">{t('chat.missingTitle')}</span>
                <div className="checklist-items">
                  {!criteriaStatus.hasGroup && (
                    <span className="missing-badge">👥 {t('chat.group')}</span>
                  )}
                  {!criteriaStatus.hasTime && (
                    <span className="missing-badge">⏰ {t('chat.timeWindow')}</span>
                  )}
                  {!criteriaStatus.hasBudget && (
                    <span className="missing-badge">💰 {t('chat.budget')}</span>
                  )}
                  {!criteriaStatus.hasIntents && (
                    <span className="missing-badge">🏷️ {t('chat.intents')}</span>
                  )}
                </div>
              </div>
            )}

            {/* Intent Distribution Bars */}
            <div className="chat-intent-summary">
              <span className="intent-section-title">
                <Layers size={13} className="text-cyan" /> {t('chat.intentDistribution')}
              </span>
              <div className="intent-bars-list">
                {Object.entries(intentConfigs).map(([key, cfg]) => {
                  const weight = constraints?.intent_weights?.[key] ?? 0
                  const pct = Math.round(weight * 100)
                  return (
                    <div key={key} className="intent-bar-row">
                      <div className="intent-row-label">
                        <span>
                          {cfg.icon} {cfg.label}
                        </span>
                        <strong>{pct}%</strong>
                      </div>
                      <div className="intent-track">
                        <div
                          className={`intent-fill ${cfg.barClass}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </section>

          {/* Route Terminals (Điểm đi & Điểm về) */}
          <section className="chat-sidebar-card chat-location-card">
            <div className="chat-sidebar-title">
              <MapPin size={17} className="text-amber" />
              <h2>{t('chat.routeSectionTitle')}</h2>
            </div>
            <p className="card-desc-text">
              {t('chat.routeSectionDesc')}
            </p>

            {poiError ? (
              <div className="chat-inline-error">{poiError}</div>
            ) : (
              <div className="location-inputs-wrapper">
                {/* Origin */}
                <div className="location-field-group">
                  <div className="pin-indicator pin-origin">
                    <span>A</span>
                  </div>
                  <div className="location-field-inner">
                    <label htmlFor="origin-poi-select">{t('chat.originRequired')}</label>
                    <select
                      id="origin-poi-select"
                      value={originId}
                      onChange={(event) => setOriginId(event.target.value)}
                      disabled={!pois.length}
                    >
                      <option value="">{t('chat.originSelectPrompt')}</option>
                      {pois.map((poi) => (
                        <option key={poi.id} value={poi.id}>
                          {poi.name} {poi.district ? `(${poi.district})` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Vertical connector line */}
                <div className="location-route-line" />

                {/* Destination */}
                <div className="location-field-group">
                  <div className="pin-indicator pin-dest">
                    <span>B</span>
                  </div>
                  <div className="location-field-inner">
                    <label htmlFor="destination-poi-select">{t('chat.destRequired')}</label>
                    <select
                      id="destination-poi-select"
                      value={destinationId}
                      onChange={(event) => setDestinationId(event.target.value)}
                      disabled={!pois.length}
                    >
                      <option value="">{t('chat.destSelectPrompt')}</option>
                      {pois.map((poi) => (
                        <option key={poi.id} value={poi.id}>
                          {poi.name} {poi.district ? `(${poi.district})` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Date Picker */}
                <div className="date-picker-row">
                  <label htmlFor="trip-date-input">
                    <CalendarDays size={14} className="text-cyan" /> {t('chat.tripDateLabel')}
                  </label>
                  <input
                    id="trip-date-input"
                    type="date"
                    value={date}
                    min={localDate(new Date())}
                    onChange={(event) => setDate(event.target.value)}
                  />
                </div>
              </div>
            )}
          </section>

          {/* Locked POIs */}
          {constraints?.locked_pois?.length ? (
            <section className="chat-sidebar-card">
              <div className="chat-sidebar-title">
                <Lock size={16} className="text-rose" />
                <h2>{t('chat.pinnedHeading', { count: constraints.locked_pois.length })}</h2>
              </div>
              <p className="card-desc-text">
                {t('chat.pinnedDesc')}
              </p>
              <div className="chat-lock-list">
                {constraints.locked_pois.map((name, index) => {
                  const place = lockedPlaces[index]
                  const isMatched = Boolean(place?.poiId)
                  return (
                    <div key={`${index}-${name}`} className="lock-item-card">
                      <div className="lock-item-header">
                        <span className="lock-name">{name}</span>
                        {isMatched ? (
                          <span className="lock-badge-ok">
                            <Check size={11} /> {t('chat.matchedPoi')}
                          </span>
                        ) : (
                          <span className="lock-badge-warn">
                            <AlertCircle size={11} /> {t('chat.selectPoi')}
                          </span>
                        )}
                      </div>
                      <select
                        value={place?.poiId ?? ''}
                        onChange={(event) =>
                          setLockedOverrides((current) => ({ ...current, [index]: event.target.value }))
                        }
                      >
                        <option value="">-- {t('chat.selectPoi')} --</option>
                        {pois.map((poi) => (
                          <option key={poi.id} value={poi.id}>
                            {poi.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  )
                })}
              </div>
            </section>
          ) : null}

          {/* Error Banner */}
          {error && (
            <div className="chat-error-banner" role="alert">
              <AlertCircle size={16} className="flex-shrink-0 text-rose" />
              <span>{error}</span>
            </div>
          )}

          {/* Create Itinerary Launch Action */}
          <div className="chat-launch-area">
            <button
              type="button"
              className="chat-create-button"
              onClick={() => void createFromChat()}
              disabled={!canCreateItinerary}
            >
              {creating ? (
                <>
                  <LoaderCircle size={18} className="chat-spinner" />
                  <span>{t('chat.computingHeuristic')}</span>
                </>
              ) : (
                <>
                  <Zap size={18} className="text-amber fill-amber" />
                  <span>{t('chat.createScheduleNow')}</span>
                  <ArrowRight size={18} />
                </>
              )}
            </button>

            {/* Launch Checklist */}
            <div className="chat-launch-checklist">
              <div className={`chk-item ${constraints?.is_complete ? 'chk-done' : ''}`}>
                {constraints?.is_complete ? <CheckCircle2 size={13} /> : <CircleHelp size={13} />}
                <span>{t('chat.chkAiDone')}</span>
              </div>
              <div className={`chk-item ${originId && destinationId ? 'chk-done' : ''}`}>
                {originId && destinationId ? <CheckCircle2 size={13} /> : <CircleHelp size={13} />}
                <span>{t('chat.chkEndpoints')}</span>
              </div>
              <div className={`chk-item ${unresolvedLockedPlaces.length === 0 ? 'chk-done' : ''}`}>
                {unresolvedLockedPlaces.length === 0 ? <CheckCircle2 size={13} /> : <CircleHelp size={13} />}
                <span>{t('chat.chkPinned')}</span>
              </div>
            </div>
          </div>

          <div className="chat-sidebar-footnote">
            {t('chat.sidebarFootnote')}
          </div>
        </aside>
      </div>
    </div>
  )
}
