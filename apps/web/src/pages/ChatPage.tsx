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
  Compass,
  MessageSquareText,
  X,
} from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, apiErrorMessage, confirmItinerary, getChatServiceStatus, getRoutingCapabilities, previewItinerary, sendChatMessage } from '../api/client'
import type { ChatConstraints, ChatServiceStatus, PlanPreview, PlanRequest, POI, RoutingCapabilities } from '../types'
import { useTranslation } from '../i18n'
import { useJourney, useTripField, useAssistantField, chatContext } from '../journey'
import { TiltCard3D } from '../components/3d/TiltCard3D'
import { LEG_COLORS, MapAdapter, type MapPoint, type MapRoute } from '../components/map/MapAdapter'

type ChatLine = {
  id: string
  role: 'assistant' | 'user'
  text: string
  time?: string
  snapshot?: Partial<ChatConstraints>
  assistantMode?: 'openai_compatible' | 'local_fallback' | 'gemini_compatible' | 'unavailable'
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

function getChatError(reason: unknown, locale: 'vi' | 'en') {
  if (typeof reason === 'object' && reason !== null && 'response' in reason) {
    const response = (reason as { response?: unknown }).response
    if (response) return apiErrorMessage(reason, locale)
  }
  if (reason instanceof Error && reason.message && reason.message !== 'Network Error') return reason.message
  if (locale === 'en') return 'Could not connect to the API. Check that the server is running and try again.'
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
  const { trip, applyConstraints } = useJourney()

  const initialMessage = useMemo<ChatLine>(() => ({
    id: 'welcome',
    role: 'assistant',
    text: t('chat.welcome'),
    time: t('chat.justNow'),
  }), [t])

  const [conversationId, setConversationId] = useAssistantField('conversationId')
  const [messages, setMessages] = useAssistantField('messages')
  const userTurns = messages.filter((message) => message.role === 'user').map((message) => message.text)
  const [planningTurns, setPlanningTurns] = useState<string[]>([])
  const [storedConstraints, setConstraints] = useAssistantField('constraints')
  const constraints = chatContext(trip, storedConstraints)
  const [busy, setBusy] = useAssistantField('busy')
  // Place and experience pages link here with ?q=<question> to start the conversation about that place.
  const [searchParams] = useSearchParams()
  const [draft, setDraft] = useState(() => (searchParams.get('q') ?? '').slice(0, 500))
  const [creating, setCreating] = useState(false)
  const [savingPreview, setSavingPreview] = useState(false)
  const [error, setError] = useState('')
  const [pois, setPois] = useState<POI[]>([])
  const [poiError, setPoiError] = useState('')
  const [routingCapabilities, setRoutingCapabilities] = useState<RoutingCapabilities | null>(null)
  const [chatServiceStatus, setChatServiceStatus] = useState<ChatServiceStatus | null>(null)
  const [date, setDate] = useTripField('date')
  const [originId, setOriginId] = useTripField('originId')
  const [destinationId, setDestinationId] = useTripField('destinationId')
  const [lockedOverrides, setLockedOverrides] = useState<Record<number, string>>({})
  const [mobileTab, setMobileTab] = useState<'chat' | 'preview' | 'hud'>('chat')
  const [planPreview, setPlanPreview] = useState<PlanPreview | null>(null)
  const [previewRequest, setPreviewRequest] = useState<PlanRequest | null>(null)
  const [previewSelectedId, setPreviewSelectedId] = useState('')
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
      setMessages([{
        id: 'welcome',
        role: 'assistant',
        text: t('chat.welcome'),
        time: t('chat.justNow'),
      }])
    }
  }, [locale, userTurns.length, t])

  useEffect(() => {
    let active = true
    api.get<POI[]>('/pois')
      .then(({ data }) => { if (active) setPois(data) })
      .catch((reason: unknown) => { if (active) setPoiError(getChatError(reason, locale)) })
    return () => { active = false }
  }, [locale])

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
  const routeInputsReady = Boolean(
    date && originId && destinationId && constraints?.travel_mode_confirmed &&
    routingCapabilities?.configured && !poiError && unresolvedLockedPlaces.length === 0 &&
    !unsupportedTravelMode && !routingUnavailable,
  )
  const canPreviewItinerary = Boolean(constraints?.is_complete && routeInputsReady && !busy && !creating)
  const canSavePreview = Boolean(planPreview && previewRequest && !busy && !creating)

  const previewMapPoints = useMemo<MapPoint[]>(() => {
    if (!planPreview) return []
    const points: MapPoint[] = []
    if (planPreview.origin_latitude != null && planPreview.origin_longitude != null) {
      points.push({
        id: 'preview-origin',
        latitude: planPreview.origin_latitude,
        longitude: planPreview.origin_longitude,
        name: planPreview.origin_label || (locale === 'en' ? 'Trip origin' : 'Điểm xuất phát'),
        category: locale === 'en' ? 'Origin' : 'Điểm đi',
        type: 'origin',
      })
    }
    for (const stop of planPreview.stops) {
      points.push({
        id: stop.experience_id,
        placeId: stop.poi.id,
        latitude: stop.poi.latitude,
        longitude: stop.poi.longitude,
        name: stop.poi.name || stop.name,
        category: stop.category,
        number: stop.position,
        time: formatTimeOnly(new Date(stop.start_at), locale),
        type: 'stop',
        address: stop.poi.address,
      })
    }
    if (planPreview.destination_latitude != null && planPreview.destination_longitude != null) {
      points.push({
        id: 'preview-destination',
        latitude: planPreview.destination_latitude,
        longitude: planPreview.destination_longitude,
        name: planPreview.destination_label || (locale === 'en' ? 'Return point' : 'Điểm quay về'),
        category: locale === 'en' ? 'Destination' : 'Điểm về',
        type: 'destination',
      })
    }
    return points
  }, [planPreview, locale])

  const previewMapRoutes = useMemo<MapRoute[]>(() => (planPreview?.routes ?? [])
    .filter((route) => route.geometry && route.geometry.length > 1)
    .map((route, index) => ({
      id: `${route.from_experience_id ?? 'origin'}-${route.to_experience_id ?? 'destination'}-${index}`,
      coordinates: route.geometry!,
      color: LEG_COLORS[index % LEG_COLORS.length],
      fromName: route.from_label ?? undefined,
      toName: route.to_label ?? undefined,
      legIndex: index + 1,
      durationMin: route.duration_min,
      distanceM: route.distance_m,
    })), [planPreview])

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
      tag: locale === 'en' ? 'Culinary & Cafe' : 'Ẩm thực & Cafe',
    },
    {
      icon: '🎨',
      title: t('chat.presetCraftTitle'),
      prompt: t('chat.presetCraftPrompt'),
      tag: locale === 'en' ? 'Craft & Workshop' : 'Thủ công & Workshop',
    },
    {
      icon: '🏛️',
      title: t('chat.presetCultureTitle'),
      prompt: t('chat.presetCulturePrompt'),
      tag: locale === 'en' ? 'Heritage & History' : 'Văn hóa & Di sản',
    },
    {
      icon: '⛵',
      title: t('chat.presetNightTitle'),
      prompt: t('chat.presetNightPrompt'),
      tag: locale === 'en' ? 'Sunset & Nightwalk' : 'Hoàng hôn & Phố đêm',
    },
  ], [t, locale])

  // Contextual smart quick reply chips
  const quickSuggestions = useMemo(() => {
    const list: { label: string; text: string }[] = []
    if (!criteriaStatus.hasGroup) {
      list.push({ label: '👥 2 người', text: locale === 'en' ? 'Our group has 2 people.' : 'Nhóm mình đi 2 người.' })
      list.push({ label: '👥 4 người', text: locale === 'en' ? 'Our group has 4 people.' : 'Nhóm mình đi 4 người.' })
    }
    if (!criteriaStatus.hasTime) {
      list.push({ label: '⏰ 08:30 - 17:30', text: locale === 'en' ? 'We want to travel from 08:30 to 17:30.' : 'Tụi mình muốn đi từ 08:30 đến 17:30.' })
      list.push({ label: '⏰ 14:00 - 21:30', text: locale === 'en' ? 'We want to travel from 14:00 to 21:30.' : 'Tụi mình muốn đi từ 14:00 đến 21:30.' })
    }
    if (!criteriaStatus.hasBudget) {
      list.push({ label: '💰 500k/người', text: locale === 'en' ? 'Budget is around 500,000 VND per person.' : 'Ngân sách khoảng 500.000₫ mỗi người.' })
      list.push({ label: '💰 1.200.000₫ tổng', text: locale === 'en' ? 'Total group budget is 1,200,000 VND.' : 'Tổng ngân sách của nhóm là 1.200.000₫.' })
    }
    if (!constraints?.travel_mode_confirmed || unsupportedTravelMode) {
      list.push({ label: '🛵 Xe máy', text: locale === 'en' ? 'We will travel by motorbike.' : 'Phương tiện di chuyển bằng xe máy.' })
      list.push({ label: '🚗 Ô tô / Taxi', text: locale === 'en' ? 'We will travel by car or taxi.' : 'Phương tiện di chuyển bằng ô tô hoặc taxi.' })
    }
    if (!criteriaStatus.hasIntents) {
      list.push({ label: '🍜 Ẩm thực & Cafe', text: locale === 'en' ? 'We want to focus on authentic street food and specialty cafes.' : 'Mình muốn ưu tiên ăn uống đặc sản và cà phê.' })
      list.push({ label: '🎨 Thủ công & Gốm', text: locale === 'en' ? 'We love hands-on pottery workshops and craft studios.' : 'Mình thích làm gốm và các xưởng thủ công.' })
    }
    return list.slice(0, 5)
  }, [criteriaStatus, constraints?.travel_mode_confirmed, locale, unsupportedTravelMode])

  const intentConfigs: Record<string, { label: string; icon: string; color: string; barClass: string }> = useMemo(() => ({
    'thủ_công': { label: t('home.catCraft'), icon: '🎨', color: '#f59e0b', barClass: 'intent-bar-craft' },
    'ẩm_thực': { label: t('home.catFood'), icon: '🍜', color: '#f97316', barClass: 'intent-bar-food' },
    'văn_hóa': { label: t('home.catCulture'), icon: '🏛️', color: '#10b981', barClass: 'intent-bar-culture' },
    'thư_giãn': { label: t('home.catNature'), icon: '🌿', color: '#06b6d4', barClass: 'intent-bar-relax' },
  }), [t])

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || busy || creating) return

    const nextTurns = [...userTurns, text]
    if (nextTurns.reduce((total, turn) => total + turn.length, 0) > 3900) {
      setError(locale === 'en'
        ? 'Conversation is very long. Please start a new chat to prevent dropping earlier constraints.'
        : 'Cuộc trò chuyện đã dài. Hãy bắt đầu cuộc trò chuyện mới để tránh bỏ sót ràng buộc cũ.')
      return
    }

    const nowStr = formatTimeOnly(new Date(), locale)
    setDraft('')
    setError('')
    setMessages((current) => [...current, { id: `user-${Date.now()}`, role: 'user', text, time: nowStr }])
    setBusy(true)

    try {
      const selectedDestination = pois.find((poi) => poi.id === destinationId)
      const result = await sendChatMessage({
        message: text,
        language: locale,
        prior_user_messages: planningTurns.slice(-30),
        conversation_id: conversationId,
        model_id: trip.modelId || undefined,
        trip_context: {
          trip_date: date || null,
          has_planning_context: Boolean(constraints),
          planner_constraints: constraints,
          destination: selectedDestination
            ? { name: selectedDestination.name, latitude: selectedDestination.latitude, longitude: selectedDestination.longitude }
            : null,
        },
      })
      if (result.intent === 'planning') {
        setPlanningTurns((current) => [...current, text])
      }
      const planningConstraints = result.intent === 'planning' ? result.structured_constraints : null
      const effectiveDate = planningConstraints?.trip_date || date
      if (planningConstraints) {
        applyConstraints(planningConstraints)
        if (planningConstraints.trip_date) setDate(planningConstraints.trip_date)
        setPlanPreview(null)
        setPreviewRequest(null)
      }
      const missingRouteInputs = planningConstraints ? [
        !effectiveDate ? (locale === 'en' ? 'trip date' : 'ngày đi') : '',
        !originId ? (locale === 'en' ? 'starting point' : 'điểm xuất phát') : '',
        !destinationId ? (locale === 'en' ? 'return point' : 'điểm quay về') : '',
        !planningConstraints.travel_mode_confirmed ? (locale === 'en' ? 'travel mode' : 'phương tiện di chuyển') : '',
      ].filter(Boolean) : []
      const routeInstructions = planningConstraints ? [
        !effectiveDate ? (locale === 'en' ? 'Choose the trip date in the Route panel.' : 'Chọn ngày đi trong khung Tuyến đường.') : '',
        !originId ? (locale === 'en' ? 'Choose a starting point there.' : 'Chọn điểm xuất phát tại đó.') : '',
        !destinationId ? (locale === 'en' ? 'Choose a return point there.' : 'Chọn điểm quay về tại đó.') : '',
        !planningConstraints.travel_mode_confirmed ? (locale === 'en' ? 'Tell me your travel mode here.' : 'Nhắn phương tiện bạn sẽ dùng tại đây.') : '',
      ].filter(Boolean) : []
      const routeQuestion = missingRouteInputs.length
        ? (locale === 'en'
          ? `To choose a suitable route, please provide ${missingRouteInputs.join(', ')}. ${routeInstructions.join(' ')}`
          : `Để chọn tuyến đường phù hợp, bạn bổ sung giúp mình ${missingRouteInputs.join(', ')} nhé. ${routeInstructions.join(' ')}`)
        : ''
      const assistantText = [result.reply || t('chat.constraintsDesc'), routeQuestion].filter(Boolean).join('\n\n')
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          text: assistantText,
          time: formatTimeOnly(new Date(), locale),
          snapshot: planningConstraints ?? undefined,
          assistantMode: result.assistant_mode,
        },
      ])
    } catch (reason) {
      setError(getChatError(reason, locale))
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
    setPlanningTurns([])
    setConstraints(null)
    setDraft('')
    setError('')
    setLockedOverrides({})
    setDate('')
    setOriginId('')
    setDestinationId('')
    setPlanPreview(null)
    setPreviewRequest(null)
  }

  function selectPreset(promptText: string) {
    setDraft(promptText)
    const textarea = document.getElementById('chat-message') as HTMLTextAreaElement | null
    textarea?.focus()
  }

  function applySuggestion(suggestionText: string) {
    setDraft(suggestionText)
    const textarea = document.getElementById('chat-message') as HTMLTextAreaElement | null
    textarea?.focus()
  }

  function invalidatePreview() {
    setPlanPreview(null)
    setPreviewRequest(null)
  }

  function buildPlanRequest(): PlanRequest {
    if (!constraints?.is_complete || !date || !originId || !destinationId || !constraints.travel_mode_confirmed || unresolvedLockedPlaces.length) {
      throw new Error(locale === 'en'
        ? 'Please complete the trip details, choose a date and both route points, and tell me your travel mode.'
        : 'Bạn hãy bổ sung ràng buộc chuyến đi, chọn ngày và hai điểm tuyến đường, đồng thời cho biết phương tiện.')
    }
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

      return {
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
      }
  }

  async function createPreview() {
    if (!canPreviewItinerary) return
    setError('')
    setCreating(true)
    try {
      const request = buildPlanRequest()
      const result = await previewItinerary(request)
      setPreviewRequest(request)
      setPlanPreview(result)
      setPreviewSelectedId(result.stops[0]?.experience_id ?? '')
      setMobileTab('preview')
    } catch (reason) {
      setError(getChatError(reason, locale))
    } finally {
      setCreating(false)
    }
  }

  async function savePreview() {
    if (!canSavePreview || !planPreview || !previewRequest) return
    setError('')
    setCreating(true)
    setSavingPreview(true)
    try {
      const result = await confirmItinerary(previewRequest, planPreview.confirmation_token)
      navigate(`/itinerary/${result.itinerary_id}`, { state: { itinerary: result } })
    } catch (reason) {
      const detail = (reason as { response?: { status?: number; data?: { detail?: { code?: string; message?: string; preview?: PlanPreview } } } })?.response?.data?.detail
      if (detail?.preview) {
        setPlanPreview(detail.preview)
        setPreviewSelectedId(detail.preview.stops[0]?.experience_id ?? '')
        setMobileTab('preview')
        setError(locale === 'en'
          ? 'Availability changed. Review the updated route, then save it again.'
          : 'Tình trạng chỗ hoặc tuyến đã thay đổi. Hãy xem lại lịch trình mới rồi xác nhận lưu lần nữa.')
      } else if (detail?.code === 'PREVIEW_INVALID' || detail?.code === 'PREVIEW_STALE') {
        setPlanPreview(null)
        setPreviewRequest(null)
        setError(locale === 'en'
          ? 'This preview expired or is no longer available. Generate a new preview to continue.'
          : 'Bản xem trước đã hết hạn hoặc không còn khả dụng. Hãy tạo bản xem trước mới để tiếp tục.')
      } else {
        setError(getChatError(reason, locale))
      }
    } finally {
      setCreating(false)
      setSavingPreview(false)
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
          <div className="chat-model-indicator">
            <span className="model-dot-live" />
            <span className="model-name">
              {chatServiceStatus?.assistant_mode === 'gemini_compatible'
                ? 'Gemini 1.5 Flash'
                : chatServiceStatus?.assistant_mode === 'openai_compatible'
                  ? 'OpenAI-compatible LLM'
                  : chatServiceStatus?.fallback_available
                    ? (locale === 'en' ? 'Offline Fallback Engine' : 'Quy tắc ngoại tuyến')
                    : (locale === 'en' ? 'AI Offline' : 'AI Ngoại tuyến')}
            </span>
          </div>
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

      {/* Mobile Tab Switcher */}
      <div className="chat-mobile-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={mobileTab === 'chat'}
          className={`chat-mobile-tab-btn ${mobileTab === 'chat' ? 'active' : ''}`}
          onClick={() => setMobileTab('chat')}
        >
          <MessageSquareText size={15} />
          <span>{t('chat.tabChat')}</span>
          <span className="tab-counter-badge">{messages.length}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mobileTab === 'preview'}
          className={`chat-mobile-tab-btn ${mobileTab === 'preview' ? 'active' : ''}`}
          onClick={() => setMobileTab('preview')}
        >
          <MapPin size={15} />
          <span>{t('chat.tabPreview')}</span>
          <span className={`tab-progress-badge ${planPreview ? 'ready' : ''}`}>{planPreview?.stops.length ?? 0}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mobileTab === 'hud'}
          className={`chat-mobile-tab-btn ${mobileTab === 'hud' ? 'active' : ''}`}
          onClick={() => setMobileTab('hud')}
        >
          <Compass size={15} />
          <span>{t('chat.tabHud')}</span>
          <span className={`tab-progress-badge ${criteriaStatus.percentage === 100 ? 'ready' : ''}`}>
            {criteriaStatus.percentage}%
          </span>
        </button>
      </div>

      {/* Main Grid Workspace */}
      <div className={`chat-workspace ${planPreview ? 'has-preview' : ''} mobile-view-${mobileTab}`}>
        {/* Left Side: Interactive Chat Panel */}
        <section className="chat-panel" aria-label="AI Chat Panel">
          <div className="chat-panel-topbar">
            <div className="chat-avatar-ring">
              <Bot size={22} className="chat-assistant-bot" />
              <div className="avatar-radar-wave" />
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
                    : 'LLM · OpenAI')
                  : chatServiceStatus?.fallback_available
                    ? (locale === 'en' ? 'Offline rule engine' : 'Bộ quy tắc ngoại tuyến')
                    : (locale === 'en' ? 'AI parsing offline' : 'Bộ phân tích AI chưa sẵn sàng')}
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
            {/* Welcoming Hero Banner when no user turns yet */}
            {userTurns.length === 0 && (
              <div className="chat-welcome-hero">
                <div className="welcome-hero-badge">
                  <Sparkles size={14} className="text-amber" />
                  <span>{locale === 'en' ? 'AI TRAVEL ARCHITECT' : 'TRỢ LÝ THIẾT KẾ DU LỊCH'}</span>
                </div>
                <h3>{locale === 'en' ? 'Ready to explore Ho Chi Minh City?' : 'Sẵn sàng trải nghiệm Sài Gòn theo cách của bạn?'}</h3>
                <p>
                  {locale === 'en'
                    ? 'Tell me your group size, free time window, budget, and passions. I will automatically match real-time venues and compute the optimal itinerary.'
                    : 'Hãy chia sẻ số lượng người, khung giờ bạn rảnh, ngân sách và sở thích. Mình sẽ tự động bắt cặp địa điểm thực tế và tính toán lộ trình tối ưu nhất.'}
                </p>
              </div>
            )}

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
                  <div className="chat-waveform">
                    <span />
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
                  <TiltCard3D
                    key={idx}
                    maxTilt={9}
                    scale={1.03}
                    className="starter-card starter-card-3d"
                    onClick={() => selectPreset(preset.prompt)}
                  >
                    <div className="starter-card-top">
                      <span className="starter-emoji">{preset.icon}</span>
                      <strong className="starter-title">{preset.title}</strong>
                      <span className="starter-tag-pill">{preset.tag}</span>
                    </div>
                    <p className="starter-desc">{preset.prompt}</p>
                  </TiltCard3D>
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

          {/* Contextual Smart Quick Reply Chips Bar */}
          {/* Before the first user turn the starter cards already offer suggestions; showing both crowds the panel. */}
          {userTurns.length > 0 && quickSuggestions.length > 0 && (
            <div className="chat-quick-suggestions-bar">
              <div className="suggestions-header">
                <Sparkles size={11} className="text-amber" />
                <span>{t('chat.tapToAnswer')}</span>
              </div>
              <div className="suggestions-chips-scroll">
                {quickSuggestions.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="suggestion-chip"
                    onClick={() => applySuggestion(item.text)}
                    title={item.text}
                  >
                    <span>{item.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Composer Form */}
          <form className="chat-composer" onSubmit={submitMessage}>
            <label className="sr-only" htmlFor="chat-message">
              {t('chat.placeholder')}
            </label>
            <div className="chat-composer-input-row">
              <textarea
                id="chat-message"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder={t('chat.composerPlaceholder')}
                maxLength={1000}
                rows={2}
                disabled={busy || creating}
              />
              {draft.trim() && (
                <button
                  type="button"
                  className="chat-clear-draft-btn"
                  onClick={() => setDraft('')}
                  title={t('chat.clearDraft')}
                  aria-label={t('chat.clearDraft')}
                >
                  <X size={14} />
                </button>
              )}
            </div>
            <div className="chat-composer-bottom">
              <div className="chat-composer-hint">
                <span>{t('chat.composerHint')}</span>
                <span className="composer-char-count">{draft.length}/1000</span>
              </div>
              <button
                type="submit"
                className="chat-send-button"
                disabled={!draft.trim() || busy || creating}
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

        {/* Live itinerary preview, positioned beside the chat after a read-only solve. */}
        <section className="chat-preview-column" aria-label={locale === 'en' ? 'Itinerary preview' : 'Bản xem trước lịch trình'}>
          {planPreview ? (
            <>
            <div className="chat-sidebar-card chat-preview-card">
              <div className="chat-sidebar-title">
                <div className="title-icon-badge">
                  <MapPin size={16} className="text-cyan" />
                </div>
                <h2>{locale === 'en' ? 'Route preview' : 'Xem trước lộ trình'}</h2>
                <span className="hud-state-pill is-complete">
                  {planPreview.stops.length} {locale === 'en' ? 'stops' : 'điểm dừng'}
                </span>
              </div>
              <p className="card-desc-text">
                {locale === 'en'
                  ? 'Review the places and order before saving this itinerary.'
                  : 'Xem các địa điểm và thứ tự ghé trước khi lưu lịch trình.'}
              </p>
              <MapAdapter
                points={previewMapPoints}
                selectedId={previewSelectedId}
                onSelect={setPreviewSelectedId}
                routes={previewMapRoutes}
                compact
                pointSourceLabel={locale === 'en' ? 'Preview stops from the itinerary planner' : 'Điểm dừng xem trước từ bộ lập lịch'}
                mapFooterLabel={locale === 'en' ? 'Preview only · not yet saved' : 'Bản xem trước · chưa lưu lịch trình'}
              />
              {!previewMapRoutes.length && (
                <p className="chat-preview-note">
                  {locale === 'en'
                    ? 'The route provider did not return drawable road geometry; numbered stops are still shown.'
                    : 'Nhà cung cấp tuyến chưa trả hình học đường đi; bản đồ vẫn đánh dấu các điểm dừng theo thứ tự.'}
                </p>
              )}
              <div className="chat-preview-summary">
                <span>{locale === 'en' ? 'Estimated group total' : 'Tổng chi phí ước tính'}</span>
                <strong>{formatMoney(planPreview.estimated_cost_vnd)}</strong>
              </div>
              <ol className="chat-preview-stop-list">
                {planPreview.stops.map((stop) => (
                  <li key={`${stop.experience_id}-${stop.slot_id}`}>
                    <button
                      type="button"
                      className={`chat-preview-stop ${previewSelectedId === stop.experience_id ? 'selected' : ''}`}
                      onClick={() => setPreviewSelectedId(stop.experience_id)}
                      aria-pressed={previewSelectedId === stop.experience_id}
                    >
                      <span className="chat-preview-stop-number">{stop.position}</span>
                      <span className="chat-preview-stop-copy">
                        <strong>{stop.poi.name || stop.name}</strong>
                        <small>{formatTimeOnly(new Date(stop.start_at), locale)} · {stop.duration_min} {locale === 'en' ? 'min' : 'phút'}</small>
                      </span>
                      <span className="chat-preview-stop-cost">{formatMoney(stop.cost_vnd)}</span>
                    </button>
                  </li>
                ))}
              </ol>
              <button
                type="button"
                className="chat-save-preview-button"
                onClick={() => void savePreview()}
                disabled={!canSavePreview}
              >
                {savingPreview ? <LoaderCircle size={17} className="chat-spinner" /> : <CheckCircle2 size={17} />}
                <span>{locale === 'en' ? 'Save itinerary' : 'Xác nhận lưu lịch trình'}</span>
              </button>
            </div>
            </>
          ) : (
            <div className="chat-sidebar-card chat-preview-empty">
              <div className="title-icon-badge"><MapPin size={16} className="text-cyan" /></div>
              <h2>{locale === 'en' ? 'Your route will appear here' : 'Lộ trình sẽ hiện ở đây'}</h2>
              <p>{locale === 'en'
                ? 'Tell me your trip details, choose a date and route points, then preview the stops before saving.'
                : 'Hãy cung cấp thông tin chuyến đi, chọn ngày và hai đầu tuyến. Bản đồ cùng thứ tự điểm dừng sẽ hiện tại đây trước khi lưu.'}</p>
            </div>
          )}
        </section>

        {/* Right Side: Trip Dashboard & Constraints HUD */}
        <aside className="chat-trip-sidebar" aria-label="Trip HUD Sidebar">
          {/* Realtime Progress & HUD Cockpit Card */}
          <section className="chat-sidebar-card hud-progress-card">
            <div className="chat-sidebar-title">
              <div className="title-icon-badge">
                <Sparkles size={16} className="text-emerald" />
              </div>
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

            {/* Dynamic Readiness Banner */}
            {constraints?.is_complete ? (
              <div className="hud-ready-banner">
                <CheckCircle2 size={15} className="text-emerald" />
                <span>{t('chat.readyToLaunch')} · {locale === 'en' ? 'All core constraints matched' : 'Đã đủ ràng buộc AI'}</span>
              </div>
            ) : (
              <div className="hud-pending-banner">
                <Info size={14} className="text-amber" />
                <span>{t('chat.inProgress')} ({criteriaStatus.metCriteria}/4)</span>
              </div>
            )}

            {/* 4 Essential Parameter Grid */}
            <div className="hud-param-grid">
              {/* Group Size */}
              <div
                className={`param-cell ${criteriaStatus.hasGroup ? 'param-active' : ''}`}
                onClick={() => !criteriaStatus.hasGroup && applySuggestion(locale === 'en' ? 'Our group has 2 people.' : 'Nhóm mình đi 2 người.')}
                role="button"
                tabIndex={0}
                title={criteriaStatus.hasGroup ? '' : (locale === 'en' ? 'Click to suggest' : 'Nhấn để bổ sung nhanh')}
              >
                <div className="param-header">
                  <Users size={14} className="text-cyan" />
                  <span>{t('chat.scaleLabel')}</span>
                  {criteriaStatus.hasGroup && <span className="param-check-dot" />}
                </div>
                <div className="param-val">
                  {constraints?.group_size ? `${constraints.group_size} ${t('chat.peopleUnit')}` : '—'}
                </div>
                <div className="param-sub">
                  {constraints?.group_size ? t('chat.privateGroup') : t('chat.unspecified')}
                </div>
              </div>

              {/* Time Window */}
              <div
                className={`param-cell ${criteriaStatus.hasTime ? 'param-active' : ''}`}
                onClick={() => !criteriaStatus.hasTime && applySuggestion(locale === 'en' ? 'We want to travel from 08:30 to 17:30.' : 'Tụi mình muốn đi từ 08:30 đến 17:30.')}
                role="button"
                tabIndex={0}
                title={criteriaStatus.hasTime ? '' : (locale === 'en' ? 'Click to suggest' : 'Nhấn để bổ sung nhanh')}
              >
                <div className="param-header">
                  <Clock size={14} className="text-emerald" />
                  <span>{t('chat.timeWindow')}</span>
                  {criteriaStatus.hasTime && <span className="param-check-dot" />}
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
              <div
                className={`param-cell ${criteriaStatus.hasBudget ? 'param-active' : ''}`}
                onClick={() => !criteriaStatus.hasBudget && applySuggestion(locale === 'en' ? 'Budget is around 500,000 VND per person.' : 'Ngân sách khoảng 500.000₫ mỗi người.')}
                role="button"
                tabIndex={0}
                title={criteriaStatus.hasBudget ? '' : (locale === 'en' ? 'Click to suggest' : 'Nhấn để bổ sung nhanh')}
              >
                <div className="param-header">
                  <Wallet size={14} className="text-amber" />
                  <span>{t('chat.budget')}</span>
                  {criteriaStatus.hasBudget && <span className="param-check-dot" />}
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
              <div className={`param-cell ${constraints?.travel_mode_confirmed ? 'param-active' : ''}`}>
                <div className="param-header">
                  {travelModeIcons[constraints?.travel_mode ?? 'motorcycle']}
                  <span>{t('chat.transport')}</span>
                  {constraints?.travel_mode_confirmed && <span className="param-check-dot" />}
                </div>
                <div className="param-val">
                  {constraints?.travel_mode_confirmed ? modeLabels[constraints.travel_mode] : '—'}
                </div>
                <div className={`param-sub ${unsupportedTravelMode ? 'text-amber' : ''}`}>
                  {!constraints?.travel_mode_confirmed
                    ? (locale === 'en' ? 'Tell me how you will travel.' : 'Hãy cho mình biết phương tiện di chuyển.')
                    : routingUnavailable
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
                <div className="checklist-header-row">
                  <span className="checklist-title">{t('chat.missingTitle')}</span>
                  <small className="checklist-hint">{locale === 'en' ? 'Tap to answer' : 'Nhấn để trả lời nhanh'}</small>
                </div>
                <div className="checklist-items">
                  {!criteriaStatus.hasGroup && (
                    <button
                      type="button"
                      className="missing-badge-btn"
                      onClick={() => applySuggestion(locale === 'en' ? 'Our group has 2 people.' : 'Nhóm mình đi 2 người.')}
                    >
                      👥 {t('chat.group')}
                    </button>
                  )}
                  {!criteriaStatus.hasTime && (
                    <button
                      type="button"
                      className="missing-badge-btn"
                      onClick={() => applySuggestion(locale === 'en' ? 'We want to travel from 08:30 to 17:30.' : 'Tụi mình muốn đi từ 08:30 đến 17:30.')}
                    >
                      ⏰ {t('chat.timeWindow')}
                    </button>
                  )}
                  {!criteriaStatus.hasBudget && (
                    <button
                      type="button"
                      className="missing-badge-btn"
                      onClick={() => applySuggestion(locale === 'en' ? 'Budget is around 500,000 VND per person.' : 'Ngân sách khoảng 500.000₫ mỗi người.')}
                    >
                      💰 {t('chat.budget')}
                    </button>
                  )}
                  {!criteriaStatus.hasIntents && (
                    <button
                      type="button"
                      className="missing-badge-btn"
                      onClick={() => applySuggestion(locale === 'en' ? 'We love authentic food and pottery craft workshops.' : 'Mình thích ăn uống và làm gốm thủ công.')}
                    >
                      🏷️ {t('chat.intents')}
                    </button>
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
              <div className="title-icon-badge">
                <MapPin size={16} className="text-amber" />
              </div>
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
                      onChange={(event) => { invalidatePreview(); setOriginId(event.target.value) }}
                      disabled={!pois.length || creating}
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
                <div className="location-route-line">
                  <span className="route-pulse-orb" />
                </div>

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
                      onChange={(event) => { invalidatePreview(); setDestinationId(event.target.value) }}
                      disabled={!pois.length || creating}
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
                    disabled={creating}
                    onChange={(event) => { invalidatePreview(); setDate(event.target.value) }}
                  />
                </div>
              </div>
            )}
          </section>

          {/* Locked POIs */}
          {constraints?.locked_pois?.length ? (
            <section className="chat-sidebar-card">
              <div className="chat-sidebar-title">
                <div className="title-icon-badge">
                  <Lock size={15} className="text-rose" />
                </div>
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
                        disabled={creating}
                        onChange={(event) =>
                          { invalidatePreview(); setLockedOverrides((current) => ({ ...current, [index]: event.target.value })) }
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
              className={`chat-create-button ${canPreviewItinerary ? 'chat-create-button-ready' : ''}`}
              onClick={() => void createPreview()}
              disabled={!canPreviewItinerary}
            >
                {creating ? (
                <>
                  <LoaderCircle size={18} className="chat-spinner" />
                  <span>{t('chat.computingHeuristic')}</span>
                </>
              ) : (
                <>
                  <Zap size={18} className="text-amber fill-amber" />
                    <span>{locale === 'en' ? 'Preview route' : 'Xem trước lộ trình'}</span>
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
              <div className={`chk-item ${routeInputsReady ? 'chk-done' : ''}`}>
                {routeInputsReady ? <CheckCircle2 size={13} /> : <CircleHelp size={13} />}
                <span>{locale === 'en' ? 'Date, endpoints & travel mode' : 'Ngày đi, hai đầu tuyến & phương tiện'}</span>
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
