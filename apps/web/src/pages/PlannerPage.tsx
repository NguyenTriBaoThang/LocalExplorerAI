import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import {
  ArrowRight,
  CalendarDays,
  Clock3,
  MapPin,
  Minus,
  Plus,
  Users,
  Wallet,
  Sparkles,
  Navigation,
  CheckCircle2,
  Lock,
  Search,
} from 'lucide-react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { apiErrorMessage, createItinerary, geocodeAddress, getPOIs, getRoutingCapabilities, getItinerarySuggestions, type ItinerarySuggestion, type ItinerarySuggestions } from '../api/client'
import { TiltCard3D } from '../components/3d/TiltCard3D'
import type { GeocodeResponse, Itinerary, PlanRequest, POI, RoutingCapabilities } from '../types'
import { useTranslation } from '../i18n'
import { useJourney, useTripField } from '../journey'
import { ItinerarySuggestions as SuggestionsPanel } from '../components/journey/ItinerarySuggestions'
import { PlannerChatBrief } from '../components/journey/PlannerChatBrief'

const budgetPresets = [500000, 1000000, 2000000, 3500000]

const today = () =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date())

const addDays = (value: string, days: number) => {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10)
}

export function PlannerPage() {
  const { t, locale } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const { trip, setTrip, toggleChatRouteStop } = useJourney()

  const intents = useMemo(() => [
    { id: 'food', label: t('home.catFood'), glyph: '🍜', desc: t('home.catFoodDesc') },
    { id: 'coffee', label: locale === 'en' ? 'Cafe' : 'Cafe', glyph: '☕', desc: locale === 'en' ? 'Cafes and coffee stops' : 'Quán cafe và điểm dừng uống cà phê' },
    { id: 'handicraft', label: t('home.catCraft'), glyph: '🎨', desc: t('home.catCraftDesc') },
    { id: 'culture', label: t('home.catCulture'), glyph: '🏛️', desc: t('home.catCultureDesc') },
    { id: 'nature', label: t('home.catNature'), glyph: '🌿', desc: t('home.catNatureDesc') },
    { id: 'sightseeing', label: locale === 'en' ? 'Sightseeing' : 'Tham quan', glyph: '📍', desc: locale === 'en' ? 'Landmarks and photo stops' : 'Địa danh và điểm ngắm cảnh, chụp ảnh' },
    { id: 'entertainment', label: locale === 'en' ? 'Entertainment' : 'Giải trí', glyph: '🎭', desc: locale === 'en' ? 'Shows and lively activities' : 'Biểu diễn và hoạt động sôi động' },
    { id: 'shopping', label: locale === 'en' ? 'Shopping' : 'Mua sắm', glyph: '🛍️', desc: locale === 'en' ? 'Markets and shopping stops' : 'Chợ và điểm mua sắm' },
    {
      id: 'relaxation',
      label: locale === 'en' ? 'Wellness & Relaxation' : 'Thư giãn & Phục hồi',
      glyph: '🍵',
      desc: locale === 'en' ? 'Herbal tea, singing bowls' : 'Trà thảo mộc, chuông xoay Tây Tạng',
    },
  ], [t, locale])

  const transportModes = useMemo(() => [
    { id: 'motorcycle', label: locale === 'en' ? 'Motorcycle' : 'Xe máy', icon: '🛵', note: locale === 'en' ? 'Goong motorcycle profile' : 'Tuyến xe máy từ Goong' },
    { id: 'car', label: locale === 'en' ? 'Car' : 'Ô tô', icon: '🚗', note: locale === 'en' ? 'Goong car profile' : 'Tuyến ô tô từ Goong' },
    { id: 'walking', label: locale === 'en' ? 'Walking' : 'Đi bộ', icon: '🚶', note: locale === 'en' ? 'Goong walking profile' : 'Tuyến đi bộ từ Goong' },
  ], [locale])

  const [date, setDate] = useTripField('date')
  const [durationDays, setDurationDays] = useTripField('durationDays')
  const [startTime, setStartTime] = useTripField('startTime')
  const [endTime, setEndTime] = useTripField('endTime')
  const [groupSize, setGroupSize] = useTripField('groupSize')
  const [budget, setBudget] = useTripField('budget')
  const [transport, setTransport] = useTripField('transport')
  const [selectedIntents, setSelectedIntents] = useTripField('intents')
  const [pois, setPois] = useState<POI[]>([])
  const [lockedPois, setLockedPois] = useTripField('lockedPois')
  // Place and experience pages link here with ?poi=<id> so the chosen place is already on the list.
  const [searchParams] = useSearchParams()
  useEffect(() => {
    const ids = searchParams.getAll('poi')
    if (ids.length) setLockedPois((current) => [...new Set([...current, ...ids])])
  }, [searchParams, setLockedPois])
  const [poiSearch, setPoiSearch] = useState('')
  const [originId, setOriginId] = useTripField('originId')
  const [destinationId, setDestinationId] = useTripField('destinationId')
  const [originAddress, setOriginAddress] = useState('')
  const [destinationAddress, setDestinationAddress] = useState('')
  const [originGeocode, setOriginGeocode] = useState<GeocodeResponse | null>(null)
  const [destinationGeocode, setDestinationGeocode] = useState<GeocodeResponse | null>(null)
  const [originResolved, setOriginResolved] = useState<GeocodeResponse['results'][number] | null>(null)
  const [destinationResolved, setDestinationResolved] = useState<GeocodeResponse['results'][number] | null>(null)
  const [geocoding, setGeocoding] = useState<'origin' | 'destination' | null>(null)
  const [routingCapabilities, setRoutingCapabilities] = useState<RoutingCapabilities | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [suggestions, setSuggestions] = useState<{ key: string; data: ItinerarySuggestions } | null>(null)
  const [customizing, setCustomizing] = useState(false)
  const suggestionsRef = useRef<HTMLElement>(null)
  const appliedChatRouteTrip = useRef<number | null>(null)
  const autoSuggestedChatTrip = useRef<number | null>(null)
  const editSource = (location.state as { editItinerary?: Itinerary } | null)?.editItinerary
  const appliedEditId = useRef('')
  useEffect(() => {
    if (!editSource || appliedEditId.current === editSource.itinerary_id) return
    appliedEditId.current = editSource.itinerary_id
    const zone = 'Asia/Ho_Chi_Minh'
    const localDate = (value: string) => new Intl.DateTimeFormat('en-CA', { timeZone: zone }).format(new Date(value))
    const localTime = (value: string) => new Intl.DateTimeFormat('en-GB', {
      timeZone: zone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).format(new Date(value))
    const sourceStartAt = editSource.start_at ?? editSource.stops[0]?.start_at
    setDate(localDate(sourceStartAt || new Date().toISOString()))
    if (sourceStartAt) setStartTime(localTime(sourceStartAt))
    if (editSource.return_deadline) setEndTime(localTime(editSource.return_deadline))
    if (editSource.group_size) setGroupSize(editSource.group_size)
    if (editSource.budget_vnd != null) setBudget(editSource.budget_vnd)
    if (editSource.transport_mode) setTransport(editSource.transport_mode)
    if (editSource.intent_weights) setSelectedIntents(Object.entries(editSource.intent_weights).filter(([, weight]) => weight > 0).map(([intent]) => intent))
    setDurationDays(1)
    setLockedPois([])
    setTrip((current) => ({
      ...current,
      durationDays: 1,
      chatContext: null,
      demo: editSource.data_mode !== 'real',
      selected: editSource.stops.map((stop) => ({ id: stop.experience_id, name: stop.name, poiId: stop.poi.id })),
    }))
    setOriginId('')
    setDestinationId('')
    const originText = editSource.origin_label || (locale === 'en' ? 'Current trip origin' : 'Điểm xuất phát của lịch trình')
    const destinationText = editSource.destination_label || (locale === 'en' ? 'Current trip destination' : 'Điểm đến của lịch trình')
    if (editSource.origin_latitude != null && editSource.origin_longitude != null) {
      setOriginAddress(originText)
      setOriginResolved({ formatted_address: originText, latitude: editSource.origin_latitude, longitude: editSource.origin_longitude, place_id: null })
      setOriginGeocode(null)
    } else {
      setOriginAddress('')
      setOriginResolved(null)
      setOriginGeocode(null)
    }
    if (editSource.destination_latitude != null && editSource.destination_longitude != null) {
      setDestinationAddress(destinationText)
      setDestinationResolved({ formatted_address: destinationText, latitude: editSource.destination_latitude, longitude: editSource.destination_longitude, place_id: null })
      setDestinationGeocode(null)
    } else {
      setDestinationAddress('')
      setDestinationResolved(null)
      setDestinationGeocode(null)
    }
    setCustomizing(true)
    setSuggestions(null)
  }, [editSource, locale, setBudget, setDate, setDurationDays, setEndTime, setGroupSize, setLockedPois, setOriginId, setSelectedIntents, setStartTime, setDestinationId, setTransport, setTrip])
  const inputKey = JSON.stringify([trip, originAddress, destinationAddress, originResolved, destinationResolved])
  const currentSuggestions = suggestions?.key === inputKey ? suggestions.data : null
  useEffect(() => {
    if (currentSuggestions) suggestionsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [suggestions])

  async function chooseSuggestion(option: ItinerarySuggestion) {
    setLoading(true)
    setError('')
    try {
      const chosenStops = option.preview.stops
      const result = await createItinerary({
        ...option.request,
        excluded_experience_ids: [],
        locked_experience_ids: chosenStops.map((stop) => stop.experience_id),
        locked_poi_ids: [...new Set(chosenStops.map((stop) => stop.poi.id))],
        preferred_slot_ids: chosenStops.map((stop) => stop.slot_id),
      })
      navigate(`/itinerary/${result.itinerary_id}`, { state: { itinerary: result } })
    } catch (reason) {
      setError(apiErrorMessage(reason, locale))
    } finally { setLoading(false) }
  }

  function customizeSuggestion(option: ItinerarySuggestion) {
    setTrip((current) => ({ ...current, selected: option.preview.stops.map((stop) => ({ id: stop.experience_id, name: stop.name, poiId: stop.poi.id })) }))
    setCustomizing(true)
    setSuggestions(null)
    document.querySelector('.planner-form-3d')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }


  useEffect(() => {
    void getPOIs('pilot', !trip.demo).then(setPois).catch(() => setPois([]))
    void getRoutingCapabilities().then((capabilities) => {
      setRoutingCapabilities(capabilities)
      setTransport((current) => capabilities.supported_modes.includes(current)
        ? current
        : capabilities.supported_modes[0] || current)
    }).catch(() => undefined)
  }, [trip.demo])

  const visibleTransportModes = transportModes.filter((mode) =>
    !routingCapabilities || routingCapabilities.supported_modes.includes(mode.id)
  )

  const toggleIntent = (id: string) => {
    setSelectedIntents((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    )
  }

  const chooseTransport = (mode: string) => {
    setTransport(mode)
    setTrip((current) => current.chatContext
      ? { ...current, chatContext: { ...current.chatContext, travelMode: mode } }
      : current)
  }

  const toggleLockPoi = (id: string) => {
    setLockedPois((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    )
  }

  const startHour =
    parseInt(startTime.split(':')[0], 10) + parseInt(startTime.split(':')[1], 10) / 60
  const endHour =
    parseInt(endTime.split(':')[0], 10) + parseInt(endTime.split(':')[1], 10) / 60
  const totalHours = Math.max(0, Math.round(((durationDays - 1) * 24 + endHour - startHour) * 10) / 10)
  const durationLabel = durationDays > 1
    ? (locale === 'en' ? `${durationDays} days · return by ${endTime} on the final day` : `${durationDays} ngày · về trước ${endTime} ngày cuối`)
    : totalHours > 0 ? t('planner.durationHours', { hours: totalHours }) : t('planner.checkHours')
  const chatContext = trip.chatContext
  const hasOrigin = Boolean(originResolved || originId)
  const hasReturnPoint = Boolean(destinationResolved || destinationId)
  const plannerRequirements = chatContext ? [
    { id: 'date', label: locale === 'en' ? 'Departure date' : 'Ngày khởi hành', complete: Boolean(date), anchor: 'planner-trip-date' },
    { id: 'transport', label: locale === 'en' ? 'Transport mode' : 'Phương tiện', complete: Boolean(chatContext.travelMode), anchor: 'planner-transport' },
    { id: 'origin', label: locale === 'en' ? 'Start point' : 'Điểm xuất phát', complete: hasOrigin, anchor: 'planner-endpoints' },
    { id: 'return', label: locale === 'en' ? 'Return point' : 'Điểm quay về', complete: hasReturnPoint, anchor: 'planner-endpoints' },
  ] : []
  const tripEndDate = date ? addDays(date, durationDays - 1) : ''

  useEffect(() => {
    if (!chatContext?.routeStart || !chatContext.routeEnd || appliedChatRouteTrip.current === chatContext.tripId) return
    appliedChatRouteTrip.current = chatContext.tripId
    setOriginId('')
    setDestinationId('')
    setOriginAddress('')
    setDestinationAddress('')
    setOriginGeocode(null)
    setDestinationGeocode(null)
    setOriginResolved({ formatted_address: chatContext.routeStart.name, latitude: chatContext.routeStart.latitude,
      longitude: chatContext.routeStart.longitude, place_id: null })
    setDestinationResolved({ formatted_address: chatContext.routeEnd.name, latitude: chatContext.routeEnd.latitude,
      longitude: chatContext.routeEnd.longitude, place_id: null })
  }, [chatContext?.tripId, chatContext?.routeStart, chatContext?.routeEnd, setOriginId, setDestinationId])

  useEffect(() => {
    if (!chatContext || !chatContext.routeStops.length || !chatContext.routeStart || !chatContext.routeEnd
      || !originResolved || !destinationResolved || !date || date < today() || !chatContext.travelMode
      || autoSuggestedChatTrip.current === chatContext.tripId) return
    autoSuggestedChatTrip.current = chatContext.tripId
    const timer = window.setTimeout(() => (document.getElementById('planner-form') as HTMLFormElement | null)?.requestSubmit(), 0)
    return () => window.clearTimeout(timer)
  }, [chatContext, originResolved, destinationResolved, date])

  const filteredPois = pois.filter((poi) =>
    poi.name.toLowerCase().includes(poiSearch.toLowerCase()) ||
    poi.address.toLowerCase().includes(poiSearch.toLowerCase())
  )
  const filteredChatStops = (chatContext?.routeStops ?? []).filter((stop) =>
    stop.name.toLowerCase().includes(poiSearch.toLowerCase()) || stop.kind.toLowerCase().includes(poiSearch.toLowerCase())
  )

  const endpointSelectValue = (point: GeocodeResponse['results'][number] | null, side: 'origin' | 'destination') => {
    if (!chatContext || !point) return ''
    const endpoint = side === 'origin' ? chatContext.routeStart : chatContext.routeEnd
    if (endpoint && Math.abs(point.latitude - endpoint.latitude) < 0.000001 && Math.abs(point.longitude - endpoint.longitude) < 0.000001) {
      return 'chat-route-endpoint'
    }
    const stop = chatContext.routeStops.find((item) => Math.abs(point.latitude - item.latitude) < 0.000001
      && Math.abs(point.longitude - item.longitude) < 0.000001)
    return stop ? `chat-stop:${stop.placeId}` : ''
  }

  function chooseRoutePoint(side: 'origin' | 'destination', value: string) {
    const isOrigin = side === 'origin'
    const endpoint = isOrigin ? chatContext?.routeStart : chatContext?.routeEnd
    const selectedStopId = value.startsWith('chat-stop:') ? Number(value.slice('chat-stop:'.length)) : null
    const stop = selectedStopId == null ? undefined : chatContext?.routeStops.find((item) => item.placeId === selectedStopId)
    const point = value === 'chat-route-endpoint' ? endpoint : stop
    if (point) {
      const resolved = { formatted_address: point.name, latitude: point.latitude, longitude: point.longitude, place_id: null }
      if (isOrigin) {
        setOriginId(''); setOriginAddress(''); setOriginResolved(resolved); setOriginGeocode(null)
      } else {
        setDestinationId(''); setDestinationAddress(''); setDestinationResolved(resolved); setDestinationGeocode(null)
      }
      return
    }
    if (isOrigin) {
      setOriginId(value); setOriginAddress(''); setOriginResolved(null); setOriginGeocode(null)
    } else {
      setDestinationId(value); setDestinationAddress(''); setDestinationResolved(null); setDestinationGeocode(null)
    }
  }

  async function resolveAddress(which: 'origin' | 'destination') {
    const address = which === 'origin' ? originAddress.trim() : destinationAddress.trim()
    if (address.length < 3) {
      setError(locale === 'en' ? 'Enter at least 3 characters for the address.' : 'Nhập địa chỉ tối thiểu 3 ký tự.')
      return
    }
    setGeocoding(which)
    setError('')
    try {
      const result = await geocodeAddress(address)
      if (which === 'origin') {
        setOriginGeocode(result)
        setOriginResolved(null)
      } else {
        setDestinationGeocode(result)
        setDestinationResolved(null)
      }
      if (result.results.length === 0) {
        setError(locale === 'en' ? 'No address matches were returned. Refine the address.' : 'Không tìm thấy địa chỉ; hãy nhập cụ thể hơn.')
      }
    } catch (reason) {
      setError(apiErrorMessage(reason, locale))
    } finally {
      setGeocoding(null)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setSuggestions(null)
    try {
      if (chatContext && !chatContext.travelMode) {
        throw new Error(locale === 'en' ? 'Choose a transport mode before requesting route suggestions.' : 'Hãy chọn phương tiện trước khi tìm tuyến gợi ý.')
      }
      if (!date) throw new Error(locale === 'en' ? 'Choose a departure date first.' : 'Hãy chọn ngày khởi hành trước.')
      const finalDate = addDays(date, durationDays - 1)
      const toIso = (value: string, atDate: string) => new Date(`${atDate}T${value}:00+07:00`).toISOString()
      const startAt = toIso(startTime, date)
      const endAt = toIso(endTime, finalDate)
      if (new Date(endAt) <= new Date(startAt)) {
        throw new Error(locale === 'en' ? 'The return deadline must be after the trip starts.' : 'Giờ về phải sau thời điểm bắt đầu chuyến đi.')
      }
      const origin = pois.find((poi) => poi.id === originId)
      const destination = pois.find((poi) => poi.id === destinationId)
      if (originAddress.trim() && !originResolved) {
        throw new Error(locale === 'en' ? 'Choose a geocoding result for the origin address first.' : 'Hãy tìm và chọn kết quả địa chỉ điểm xuất phát trước.')
      }
      if (destinationAddress.trim() && !destinationResolved) {
        throw new Error(locale === 'en' ? 'Choose a geocoding result for the return address first.' : 'Hãy tìm và chọn kết quả địa chỉ điểm về trước.')
      }
      const originPoint = originResolved ?? origin
      const destinationPoint = destinationResolved ?? destination
      if (!originPoint || !destinationPoint) {
        throw new Error(locale === 'en'
          ? 'Choose both a departure point and a return destination so the route and return deadline can be checked.'
          : 'Hãy chọn cả điểm xuất phát và điểm về để kiểm tra đủ lộ trình và giờ về.')
      }
      const result = await getItinerarySuggestions({
        start_at: startAt,
        end_at: endAt,
        group_size: groupSize,
        budget_vnd: budget,
        transport_mode: transport as PlanRequest['transport_mode'],
        intent_weights: Object.fromEntries(selectedIntents.map((intent) => [intent, 1])),
        require_verified: !trip.demo,
        routing_mode: 'configured',
        locked_experience_ids: trip.selected.map((item) => item.id),
        locked_poi_ids: lockedPois,
        ...(originPoint
          ? {
              origin_latitude: originPoint.latitude,
              origin_longitude: originPoint.longitude,
              origin_label: 'formatted_address' in originPoint ? originPoint.formatted_address : originPoint.name,
            }
          : {}),
        ...(destinationPoint
          ? {
              destination_latitude: destinationPoint.latitude,
              destination_longitude: destinationPoint.longitude,
              destination_label: 'formatted_address' in destinationPoint ? destinationPoint.formatted_address : destinationPoint.name,
            }
          : {}),
      })
      setSuggestions({ key: inputKey, data: result })
      setCustomizing(false)
    } catch (reason) {
      setError(apiErrorMessage(reason, locale))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="planner-page-3d page-wrap">
      {/* Page Header */}
      <div className="page-title-row-3d">
        <div>
          <span className="eyebrow-3d">
            <span className="eyebrow-dot" /> {t('planner.eyebrow')}
          </span>
          <h1 className="page-heading-3d">
            {chatContext
              ? (locale === 'en' ? 'Plan your trip in' : 'Lập lịch trình tại')
              : t('planner.headingMain')} <em>{chatContext ? chatContext.destinationName : t('planner.headingHighlight')}</em>
          </h1>
          <p className="page-subtext-3d">
            {chatContext
              ? (locale === 'en'
                ? `${chatContext.days} days, ${chatContext.travelers} travelers, and your chat preferences are ready to edit.`
                : `${chatContext.days} ngày, ${chatContext.travelers} người và các sở thích từ Chat đã sẵn sàng để chỉnh sửa.`)
              : t('planner.headingLead')}
          </p>
        </div>
        <div className="planner-badge-wrap">
          <span className="planner-city-badge">
            <MapPin size={14} className="text-emerald" />
            {locale === 'en' ? 'Pilot area: District 1' : 'Khu vực pilot: Quận 1'}
          </span>
        </div>
      </div>

      {chatContext && <PlannerChatBrief context={chatContext} locale={locale} date={date} endDate={tripEndDate}
        durationDays={durationDays} startTime={startTime} endTime={endTime} durationLabel={durationLabel}
        groupSize={groupSize} budget={budget} travelModeLabel={transportModes.find((mode) => mode.id === transport)?.label ?? ''}
        requirements={plannerRequirements} onReturnChat={() => navigate('/chat')}
        onGoTo={(requirement) => document.getElementById(requirement.anchor)?.scrollIntoView({ behavior: 'smooth', block: 'center' })} />}

      {!chatContext && (
        <div className="planner-standalone-summary">
          <div>
            <strong>{locale === 'en' ? 'Start with your saved choices' : 'Bắt đầu từ lựa chọn đã lưu'}</strong>
            <p>{date || (locale === 'en' ? 'Departure date needed' : 'Chưa chọn ngày đi')} · {durationDays} {locale === 'en' ? 'days' : 'ngày'} · {startTime}–{endTime} · {groupSize} {locale === 'en' ? 'people' : 'người'} · {budget.toLocaleString('vi-VN')} ₫</p>
            <small>{locale === 'en' ? 'Compare feasible suggestions and customize the option you like.' : 'So sánh các lịch trình khả thi rồi tùy chỉnh phương án bạn thích.'}</small>
          </div>
          <span className="planner-city-badge"><MapPin size={14} />{locale === 'en' ? 'Pilot area: District 1' : 'Khu vực pilot: Quận 1'}</span>
        </div>
      )}
      {trip.selected.length > 0 && (
        <section className="mb-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-slate-800" aria-label={locale === 'en' ? 'Pinned itinerary stops' : 'Các điểm đang ghim'}>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <strong>{locale === 'en' ? 'Stops currently pinned in this itinerary' : 'Các địa điểm đang được giữ trong lịch trình'}</strong>
            <button type="button" className="text-sm font-semibold text-emerald-800 underline" onClick={() => setTrip((current) => ({ ...current, selected: [] }))}>
              {locale === 'en' ? 'Remove all pins' : 'Bỏ ghim tất cả'}
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {trip.selected.map((item) => (
              <button key={item.id} type="button" className="rounded-full border border-emerald-300 bg-white px-3 py-1.5 text-sm hover:bg-emerald-100"
                onClick={() => setTrip((current) => ({ ...current, selected: current.selected.filter((selected) => selected.id !== item.id) }))}>
                {item.name} <span aria-hidden="true">×</span><span className="sr-only">{locale === 'en' ? 'Remove stop' : 'Bỏ địa điểm'}</span>
              </button>
            ))}
          </div>
        </section>
      )}
      <div className="planner-grid-3d">
        {/* Main Form */}
        <form id="planner-form" className="planner-form-3d" onSubmit={submit}>
          {customizing && <p className="form-alert-3d" role="status">{locale === 'en' ? 'Stops from your chosen option are selected. Remove any in the journey bar above, change your criteria, then request new suggestions.' : 'Đã chọn các trải nghiệm của phương án này. Bạn có thể bỏ từng trải nghiệm trên thanh Hành trình phía trên, sửa thời gian/ngân sách rồi tìm gợi ý lại.'}</p>}
          {/* Section 01: Thời gian & Nhóm */}
          <div className="form-card-3d">
            <div className="form-card-header">
              <span className="step-num">{t('planner.step1Num')}</span>
              <div>
                <h2>{t('planner.step1Title')}</h2>
                <p>{t('planner.step1Desc')}</p>
              </div>
              <div className="duration-preview-chip">
                <Clock3 size={13} className="text-emerald" />
                <span>{durationLabel}</span>
              </div>
            </div>

            <div className="form-fields-grid-3">
              <label id="planner-trip-date" className="field-group-3d">
                <span>
                  <CalendarDays size={14} className="text-emerald" /> {t('planner.dateLabel')}
                </span>
                <input
                  required
                  type="date"
                  value={date}
                  min={today()}
                  onChange={(e) => setDate(e.target.value)}
                />
              </label>

              <label className="field-group-3d">
                <span>
                  <Clock3 size={14} className="text-amber" /> {t('planner.startTime')}
                </span>
                <input
                  required
                  type="time"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                />
              </label>

              <label className="field-group-3d">
                <span>
                  <Clock3 size={14} className="text-amber" /> {t('planner.endTime')}
                </span>
                <input
                  required
                  type="time"
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                />
              </label>
            </div>

            <div className="form-fields-grid-3">
              <div className="field-group-3d">
                <span>
                  <Users size={14} className="text-cyan" /> {t('planner.groupSize')}
                </span>
                <div className="stepper-3d">
                  <button
                    type="button"
                    onClick={() => setGroupSize(Math.max(1, groupSize - 1))}
                    aria-label="Decrease"
                  >
                    <Minus size={15} />
                  </button>
                  <span className="stepper-value">
                    {t('planner.guestsUnit', { count: groupSize })}
                  </span>
                  <button
                    type="button"
                    onClick={() => setGroupSize(Math.min(30, groupSize + 1))}
                    aria-label="Increase"
                  >
                    <Plus size={15} />
                  </button>
                </div>
              </div>

              <div className="field-group-3d">
                <span>
                  <CalendarDays size={14} className="text-cyan" /> {locale === 'en' ? 'Trip duration' : 'Thời lượng chuyến đi'}
                </span>
                <select aria-label={locale === 'en' ? 'Trip duration in days' : 'Số ngày chuyến đi'} value={durationDays}
                  onChange={(event) => setDurationDays(Number(event.target.value))}>
                  {Array.from({ length: 7 }, (_, index) => index + 1).map((days) => (
                    <option key={days} value={days}>{days} {locale === 'en' ? (days === 1 ? 'day' : 'days') : 'ngày'}</option>
                  ))}
                </select>
              </div>

              <div className="field-group-3d">
                <div className="field-label-split">
                  <span>
                    <Wallet size={14} className="text-emerald" /> {t('planner.budget')}
                  </span>
                  <span className="budget-calc-sub">
                    {t('planner.budgetPerPerson', {
                      cost: Math.floor(budget / groupSize).toLocaleString('vi-VN'),
                    })}
                  </span>
                </div>
                <input
                  required
                  type="number"
                  aria-label={t('planner.budget')}
                  min={100000}
                  step={50000}
                  value={budget}
                  onChange={(e) => setBudget(Math.max(0, Number(e.target.value)))}
                />
                <div className="budget-presets-row">
                  {budgetPresets.map((amt) => (
                    <button
                      key={amt}
                      type="button"
                      className={`preset-btn ${budget === amt ? 'preset-active' : ''}`}
                      onClick={() => setBudget(amt)}
                    >
                      {(amt / 1000000).toFixed(amt % 1000000 === 0 ? 0 : 1)}tr
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Section 02: Mục đích trải nghiệm */}
          <div className="form-card-3d">
            <div className="form-card-header">
              <span className="step-num">{t('planner.step2Num')}</span>
              <div>
                <h2>{t('planner.step2Title')}</h2>
                <p>{t('planner.step2Desc')}</p>
              </div>
            </div>

            <div className="intent-selector-grid">
              {intents.map((item) => {
                const active = selectedIntents.includes(item.id)
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`intent-btn-3d ${active ? 'intent-btn-active' : ''}`}
                    onClick={() => toggleIntent(item.id)}
                  >
                    <span className="intent-btn-glyph">{item.glyph}</span>
                    <div className="intent-btn-info">
                      <strong>{item.label}</strong>
                      <small>{item.desc}</small>
                    </div>
                    {active && <CheckCircle2 size={18} className="intent-check-icon" />}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Section 03: Phương tiện di chuyển */}
          <div id="planner-transport" className="form-card-3d scroll-mt-24">
            <div className="form-card-header">
              <span className="step-num">{t('planner.step3Num')}</span>
              <div>
                <h2>{locale === 'en' ? 'Choose how to travel between stops' : 'Chọn cách di chuyển giữa các điểm'}</h2>
                <p>{locale === 'en' ? 'This mode is used to estimate route duration for each suggested itinerary.' : 'Phương tiện này được dùng để ước tính thời gian đi giữa các điểm trong từng tuyến gợi ý.'}</p>
              </div>
            </div>

            {chatContext && <div className="planner-step-chat-note">
              <Sparkles size={15} />
              <span>{locale === 'en' ? 'Received from AI Chat' : 'Thông tin từ AI Chat'}</span>
              <strong>{transportModes.find((mode) => mode.id === transport)?.label ?? transport}</strong>
              <small>{locale === 'en' ? 'Change it here if needed.' : 'Có thể đổi trước khi tìm tuyến.'}</small>
            </div>}

            <div className="transport-mode-grid">
              {visibleTransportModes.map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  className={`transport-btn-3d ${transport === mode.id ? 'transport-active' : ''}`}
                  onClick={() => chooseTransport(mode.id)}
                >
                  <span className="transport-icon">{mode.icon}</span>
                  <div>
                    <strong>{mode.label}</strong>
                    <small>{mode.note}</small>
                  </div>
                </button>
              ))}
            </div>
            {trip.demo && <p className="routing-provider-note">{locale === 'en' ? 'Demo experiences and availability are simulated. Routes still come from the configured map routing API; ETAs are estimates, not live traffic.' : 'Trải nghiệm và tình trạng chỗ đang mô phỏng. Tuyến đường vẫn lấy từ API chỉ đường đã cấu hình; ETA là ước tính, không phải giao thông thời gian thực.'}</p>}
            {routingCapabilities && (
              <p className="routing-provider-note">
                {locale === 'en' ? 'Routing provider' : 'Nhà cung cấp tuyến đường'}: {routingCapabilities.provider}. {routingCapabilities.eta_is_realtime ? (locale === 'en' ? 'Live traffic ETA.' : 'ETA giao thông thời gian thực.') : (locale === 'en' ? 'ETAs are estimates, not live traffic.' : 'ETA là ước tính, không phải giao thông thời gian thực.')}
                {!routingCapabilities.configured && ` · ${locale === 'en' ? 'Routing provider is not configured' : 'Chưa cấu hình nhà cung cấp tuyến đường'}`}
                {routingCapabilities.geocoding_configured === false && ` · ${locale === 'en' ? `Geocoding provider/key unavailable (${routingCapabilities.geocoding_provider})` : `Nhà cung cấp/khóa geocoding chưa sẵn sàng (${routingCapabilities.geocoding_provider})`}`}
              </p>
            )}
          </div>

          {/* Section 04: Điểm xuất phát, Điểm về & Khóa POI */}
          <div id="planner-endpoints" className="form-card-3d scroll-mt-24">
            <div className="form-card-header">
              <span className="step-num">{t('planner.step4Num')}</span>
              <div>
                <h2>{locale === 'en' ? 'Set the route start, finish and stops' : 'Chọn điểm đi, điểm đến và điểm ghé'}</h2>
                <p>{locale === 'en' ? 'Start and finish define the route. Pinned places are included when the planner can fit them.' : 'Điểm đi và điểm đến tạo khung tuyến. Địa điểm được ghim sẽ được ưu tiên đưa vào nếu phù hợp thời gian.'}</p>
              </div>
            </div>

            <div className="planner-route-endpoint-flow" aria-label={locale === 'en' ? 'Route endpoints' : 'Hai đầu tuyến'}>
              <div><small>{locale === 'en' ? 'START' : 'ĐIỂM ĐI'}</small><strong>{originResolved?.formatted_address || pois.find((poi) => poi.id === originId)?.name || (originAddress.trim() || (chatContext?.originCity ? `${chatContext.originCity} · ${locale === 'en' ? 'choose exact point below' : 'chọn điểm cụ thể bên dưới'}` : (locale === 'en' ? 'Choose a start point' : 'Chưa chọn điểm đi')))}</strong>
                {chatContext?.routeStart && <small className="planner-route-source">{chatContext.routeStart.source === 'arrival_hub' ? (locale === 'en' ? 'AI Chat arrival hub' : 'Bến/sân bay từ AI Chat') : chatContext.routeStart.source === 'stay' ? (locale === 'en' ? 'AI Chat accommodation' : 'Chỗ ở từ AI Chat') : (locale === 'en' ? 'First Chat activity' : 'Hoạt động đầu từ AI Chat')}</small>}</div>
              <ArrowRight size={18} />
              <div><small>{locale === 'en' ? 'FINISH' : 'ĐIỂM ĐẾN'}</small><strong>{destinationResolved?.formatted_address || pois.find((poi) => poi.id === destinationId)?.name || (destinationAddress.trim() || (locale === 'en' ? 'Choose a finish point' : 'Chưa chọn điểm đến'))}</strong>
                {chatContext?.routeEnd && <small className="planner-route-source">{chatContext.routeEnd.source === 'arrival_hub' ? (locale === 'en' ? 'AI Chat return hub' : 'Bến/sân bay về từ AI Chat') : chatContext.routeEnd.source === 'stay' ? (locale === 'en' ? 'AI Chat accommodation' : 'Chỗ ở từ AI Chat') : (locale === 'en' ? 'Last Chat activity' : 'Hoạt động cuối từ AI Chat')}</small>}</div>
            </div>

            {chatContext && <div className="planner-chat-route-stops">
              <div className="planner-chat-route-stops-heading">
                <div><Sparkles size={15} /><strong>{locale === 'en' ? 'Stops from your AI Chat itinerary' : 'Danh sách điểm từ lịch trình AI Chat'}</strong></div>
                <span>{chatContext.routeStops.length} {locale === 'en' ? 'stops' : 'điểm ghé'}</span>
              </div>
              {chatContext.routeStops.length ? <ol>
                {chatContext.routeStops.map((stop, index) => <li key={`${stop.day}-${stop.placeId}-${index}`}>
                  <div className="planner-chat-route-stop-time"><span>{locale === 'en' ? `Day ${stop.day}` : `Ngày ${stop.day}`}{stop.date ? ` · ${stop.date.split('-').reverse().slice(0, 2).join('/')}` : ''}</span><strong>{stop.startTime}</strong></div>
                  <div className="planner-chat-route-stop-main"><strong>{stop.name}</strong><small>{stop.durationMin} {locale === 'en' ? 'min' : 'phút'} · {stop.costVnd.toLocaleString('vi-VN')} ₫</small></div>
                  {stop.rankPosition != null && <span className="planner-chat-route-rank">Ranker: {locale === 'en' ? `rank ${stop.rankPosition}/${stop.rankCandidateCount ?? '—'}` : `hạng ${stop.rankPosition}/${stop.rankCandidateCount ?? '—'}`}</span>}
                </li>)}
              </ol> : <p className="planner-chat-route-stops-empty">{locale === 'en' ? 'The current Chat itinerary has no stops to transfer.' : 'Lịch trình hiện tại trong AI Chat chưa có điểm ghé để chuyển.'}</p>}
              <small className="planner-chat-route-stops-note">{locale === 'en' ? 'These are the stops already planned in Chat. Ranked alternatives appear below after the route request.' : 'Đây là các điểm đã có trong Chat. Danh sách phương án xếp hạng sẽ hiện bên dưới sau khi Planner tính tuyến.'}</small>
            </div>}

            <div className="form-fields-grid-2">
              <div className="field-group-3d">
                <span>
                  <MapPin size={14} className="text-emerald" /> {t('planner.originLabel')}
                </span>
                <select aria-label={locale === 'en' ? 'Start point' : 'Điểm xuất phát'} value={originId || endpointSelectValue(originResolved, 'origin')} onChange={(e) => chooseRoutePoint('origin', e.target.value)}>
                  <option value="">{t('planner.originDefault')}</option>
                  {chatContext && <optgroup label={locale === 'en' ? 'From AI Chat' : 'Điểm từ AI Chat'}>
                    {chatContext.routeStart && <option value="chat-route-endpoint">{chatContext.routeStart.name} · {locale === 'en' ? 'Chat route start' : 'điểm đi từ Chat'}</option>}
                    {chatContext.routeStops.map((stop) => <option key={`origin-${stop.placeId}`} value={`chat-stop:${stop.placeId}`}>
                      {stop.name} · {locale === 'en' ? `Day ${stop.day}, ${stop.startTime}` : `Ngày ${stop.day}, ${stop.startTime}`}
                    </option>)}
                  </optgroup>}
                  <optgroup label={locale === 'en' ? 'Other places' : 'Địa điểm khác'}>
                  {pois.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                  </optgroup>
                </select>
                <div className="address-resolve-row">
                  <input aria-label={locale === 'en' ? 'Start address' : 'Địa chỉ xuất phát'} value={originAddress} placeholder={locale === 'en' ? 'Or enter a street address' : 'Hoặc nhập địa chỉ'} onChange={(event) => {
                    setOriginAddress(event.target.value)
                    setOriginId('')
                    setOriginResolved(null)
                    setOriginGeocode(null)
                  }} />
                  <button type="button" className="btn-geocode" disabled={geocoding !== null} onClick={() => void resolveAddress('origin')}>
                    <Search size={14} /> {geocoding === 'origin' ? (locale === 'en' ? 'Searching…' : 'Đang tìm…') : (locale === 'en' ? 'Find' : 'Tìm')}
                  </button>
                </div>
                {originGeocode?.results.map((result) => (
                  <button type="button" className={`address-result-item ${originResolved?.place_id === result.place_id ? 'address-result-active' : ''}`} key={result.place_id || `${result.latitude},${result.longitude}`} onClick={() => setOriginResolved(result)}>
                    {result.formatted_address}
                  </button>
                ))}
                {originResolved && originGeocode && <small className="address-source-note">{originGeocode.provider} · {locale === 'en' ? 'age' : 'tuổi'} {originGeocode.age_seconds}s · {locale === 'en' ? 'valid until' : 'hạn'} {new Date(originGeocode.valid_until).toLocaleTimeString(locale === 'en' ? 'en-US' : 'vi-VN')} · <a href={originGeocode.source_uri} target="_blank" rel="noreferrer">{locale === 'en' ? 'source' : 'nguồn'}</a></small>}
              </div>

              <div className="field-group-3d">
                <span>
                  <MapPin size={14} className="text-amber" /> {t('planner.destinationLabel')}
                </span>
                <select aria-label={locale === 'en' ? 'End point' : 'Điểm kết thúc'} value={destinationId || endpointSelectValue(destinationResolved, 'destination')} onChange={(e) => chooseRoutePoint('destination', e.target.value)}>
                  <option value="">{t('planner.destDefault')}</option>
                  {chatContext && <optgroup label={locale === 'en' ? 'From AI Chat' : 'Điểm từ AI Chat'}>
                    {chatContext.routeEnd && <option value="chat-route-endpoint">{chatContext.routeEnd.name} · {locale === 'en' ? 'Chat route finish' : 'điểm về từ Chat'}</option>}
                    {chatContext.routeStops.map((stop) => <option key={`destination-${stop.placeId}`} value={`chat-stop:${stop.placeId}`}>
                      {stop.name} · {locale === 'en' ? `Day ${stop.day}, ${stop.startTime}` : `Ngày ${stop.day}, ${stop.startTime}`}
                    </option>)}
                  </optgroup>}
                  <optgroup label={locale === 'en' ? 'Other places' : 'Địa điểm khác'}>
                  {pois.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                  </optgroup>
                </select>
                <div className="address-resolve-row">
                  <input aria-label={locale === 'en' ? 'End address' : 'Địa chỉ điểm về'} value={destinationAddress} placeholder={locale === 'en' ? 'Or enter a return address' : 'Hoặc nhập địa chỉ điểm về'} onChange={(event) => {
                    setDestinationAddress(event.target.value)
                    setDestinationId('')
                    setDestinationResolved(null)
                    setDestinationGeocode(null)
                  }} />
                  <button type="button" className="btn-geocode" disabled={geocoding !== null} onClick={() => void resolveAddress('destination')}>
                    <Search size={14} /> {geocoding === 'destination' ? (locale === 'en' ? 'Searching…' : 'Đang tìm…') : (locale === 'en' ? 'Find' : 'Tìm')}
                  </button>
                </div>
                {destinationGeocode?.results.map((result) => (
                  <button type="button" className={`address-result-item ${destinationResolved?.place_id === result.place_id ? 'address-result-active' : ''}`} key={result.place_id || `${result.latitude},${result.longitude}`} onClick={() => setDestinationResolved(result)}>
                    {result.formatted_address}
                  </button>
                ))}
                {destinationResolved && destinationGeocode && <small className="address-source-note">{destinationGeocode.provider} · {locale === 'en' ? 'age' : 'tuổi'} {destinationGeocode.age_seconds}s · {locale === 'en' ? 'valid until' : 'hạn'} {new Date(destinationGeocode.valid_until).toLocaleTimeString(locale === 'en' ? 'en-US' : 'vi-VN')} · <a href={destinationGeocode.source_uri} target="_blank" rel="noreferrer">{locale === 'en' ? 'source' : 'nguồn'}</a></small>}
              </div>
            </div>

            {chatContext ? (
              <div className="poi-lock-section">
                <div className="poi-lock-header">
                  <div className="poi-lock-title-col">
                    <span className="poi-lock-label">
                      <Lock size={14} className="text-cyan" /> {locale === 'en' ? 'Choose stops from your AI Chat itinerary' : 'Chọn điểm ghé từ lịch trình AI Chat'}
                      <span className="planner-stop-count">{chatContext.selectedRouteStopIds.length}/{chatContext.routeStops.length}</span>
                    </span>
                    <small>{locale === 'en' ? 'These options come from the itinerary above. Select the stops you want to keep.' : 'Danh sách lấy trực tiếp từ lịch trình AI Chat phía trên. Chọn các điểm bạn muốn giữ.'}</small>
                  </div>
                  {chatContext.routeStops.length > 6 && (
                    <div className="poi-search-box-mini">
                      <Search size={14} />
                      <input placeholder={locale === 'en' ? 'Search Chat stops...' : 'Tìm điểm trong Chat...'} value={poiSearch}
                        onChange={(event) => setPoiSearch(event.target.value)} />
                    </div>
                  )}
                </div>
                <div className="poi-lock-cards-grid">
                  {filteredChatStops.map((stop, index) => {
                    const selected = chatContext.selectedRouteStopIds.includes(stop.placeId)
                    return <button key={`${stop.day}-${stop.placeId}-${index}`} type="button" aria-pressed={selected}
                      className={`poi-lock-card ${selected ? 'poi-locked-active' : ''}`} onClick={() => toggleChatRouteStop(stop.placeId)}>
                      <div className="poi-lock-status">{selected ? <CheckCircle2 size={16} className="text-emerald" /> : <span className="poi-lock-empty-dot" />}</div>
                      <div className="poi-lock-info">
                        <strong>{stop.name}</strong>
                        <small>{locale === 'en' ? `Day ${stop.day} · ${stop.startTime}` : `Ngày ${stop.day} · ${stop.startTime}`} · {stop.durationMin} {locale === 'en' ? 'min' : 'phút'} · {stop.costVnd.toLocaleString('vi-VN')} ₫</small>
                      </div>
                      {stop.rankPosition != null && <span className="planner-chat-route-rank">{locale === 'en' ? `Rank ${stop.rankPosition}/${stop.rankCandidateCount ?? '—'}` : `Hạng ${stop.rankPosition}/${stop.rankCandidateCount ?? '—'}`}</span>}
                    </button>
                  })}
                  {!chatContext.routeStops.length && <p className="planner-poi-empty">{locale === 'en' ? 'No Chat stops are available to choose.' : 'AI Chat chưa chuyển qua điểm dừng nào.'}</p>}
                  {chatContext.routeStops.length > 0 && !filteredChatStops.length && <p className="planner-poi-empty">{locale === 'en' ? 'No Chat stops match this search.' : 'Không tìm thấy điểm Chat phù hợp.'}</p>}
                </div>
              </div>
            ) : (
              <div className="poi-lock-section">
                <div className="poi-lock-header">
                  <div className="poi-lock-title-col">
                    <span className="poi-lock-label"><Lock size={14} className="text-cyan" /> {locale === 'en' ? 'Places to include in the route' : 'Địa điểm muốn ghé trên tuyến'}
                      <span className="planner-stop-count">{lockedPois.length}</span>
                    </span>
                    <small>{locale === 'en' ? 'Choose optional stops. The route list will show which ones fit your time and budget.' : 'Chọn điểm ghé tùy chọn. Danh sách tuyến bên dưới sẽ cho biết điểm nào xếp được theo thời gian và ngân sách.'}</small>
                  </div>
                  {pois.length > 6 && <div className="poi-search-box-mini"><Search size={14} />
                    <input placeholder={t('planner.searchPoiPlaceholder')} value={poiSearch} onChange={(event) => setPoiSearch(event.target.value)} />
                  </div>}
                </div>
                <div className="poi-lock-cards-grid">
                  {filteredPois.slice(0, 8).map((poi) => {
                    const locked = lockedPois.includes(poi.id)
                    return <button key={poi.id} type="button" className={`poi-lock-card ${locked ? 'poi-locked-active' : ''}`} onClick={() => toggleLockPoi(poi.id)}>
                      <div className="poi-lock-status">{locked ? <CheckCircle2 size={16} className="text-emerald" /> : <span className="poi-lock-empty-dot" />}</div>
                      <div className="poi-lock-info"><strong>{poi.name}</strong><small>{poi.address}</small></div>
                    </button>
                  })}
                  {!pois.length && <p className="planner-poi-empty">{locale === 'en' ? 'No places are available for this area right now.' : 'Hiện chưa tải được danh sách địa điểm cho khu vực này.'}</p>}
                  {pois.length > 0 && filteredPois.length === 0 && <p className="planner-poi-empty">{locale === 'en' ? 'No places match this search.' : 'Không tìm thấy địa điểm phù hợp từ khóa.'}</p>}
                </div>
              </div>
            )}
          </div>

          {error && <div className="form-alert-3d">{error}</div>}

          {/* Submit Row */}
          <div className="submit-action-card">
            <div className="submit-summary-text">
              <strong>
                {t('planner.submitSummary', { intents: selectedIntents.length, group: groupSize })}
              </strong>
              <small>{t('planner.submitEngine')}</small>
            </div>
            <button className="btn-planner-submit" type="submit" disabled={loading}>
              <span>{loading ? (locale === 'en' ? 'Finding routes…' : 'Đang tìm tuyến…') : (locale === 'en' ? 'Find ranked routes' : 'Tìm tuyến đường phù hợp')}</span>
              <ArrowRight size={18} />
            </button>
          </div>
        </form>

        {/* Right Column: 3D Interactive Live Preview Card */}
        <aside className="planner-aside-3d">
          <TiltCard3D maxTilt={8} className="live-preview-card-3d">
            <div className="preview-card-header">
              <div className="preview-icon-box">
                <img src="/logo-icon.png" alt="Local Explorer AI" className="brand-logo-img" />
              </div>
              <div>
                <span className="preview-kicker">{chatContext ? (locale === 'en' ? 'AI CHAT PLAN' : 'LỊCH TRÌNH TỪ AI CHAT') : t('planner.previewKicker')}</span>
                <h3 className="preview-main-title">{chatContext?.destinationName ?? t('planner.previewMainTitle')}</h3>
              </div>
            </div>

            <div className="preview-stats-bar">
              <div className="preview-stat-cell">
                <small>{t('planner.previewDuration')}</small>
                <strong>
                  {durationDays > 1 ? `${durationDays} ${locale === 'en' ? 'days' : 'ngày'}`
                    : totalHours > 0 ? `${totalHours} ${locale === 'en' ? 'hrs' : 'giờ'}` : t('planner.checkHours')}
                </strong>
              </div>
              <div className="preview-stat-cell">
                <small>{t('planner.previewEst')}</small>
                <strong>~{Math.floor(budget / groupSize).toLocaleString('vi-VN')}₫</strong>
                <span className="stat-unit">/ {locale === 'en' ? 'person' : 'người'}</span>
              </div>
              <div className="preview-stat-cell">
                <small>{t('planner.previewGroup')}</small>
                <strong>{t('planner.guestsUnit', { count: groupSize })}</strong>
              </div>
            </div>

            <div className="preview-vibe-list">
              <span className="vibe-list-label">{t('planner.previewPriority')}</span>
              <div className="vibe-tags-wrap">
                {selectedIntents.length > 0 ? (
                  selectedIntents.map((id) => {
                    const found = intents.find((i) => i.id === id)
                    return (
                      <span key={id} className="vibe-pill-active">
                        {found?.glyph} {found?.label}
                      </span>
                    )
                  })
                ) : (
                  <span className="vibe-pill-empty">{t('planner.noIntentSelected')}</span>
                )}
              </div>
            </div>

            <div className="preview-simulation-notice">
              <Sparkles size={16} className="text-amber" />
              <p>
                {t('planner.previewHeuristicNotice')}
              </p>
            </div>

            <div className="preview-card-footer">
              <Navigation size={14} className="text-emerald" />
              <span>
                {t('planner.modeLabel', {
                  mode: transportModes.find((m) => m.id === transport)?.label || transport,
                })}
              </span>
            </div>
          </TiltCard3D>

          {/* Quick FAQ / Guarantee */}
          <div className="planner-guarantee-card">
            <h4>{t('planner.feasibilityTitle')}</h4>
            <p>
              {t('planner.feasibilityBody')}
            </p>
          </div>
        </aside>
      </div>

      <section ref={suggestionsRef} id="planner-routes" className="planner-routes-section scroll-mt-24" aria-labelledby="planner-routes-title">
        {currentSuggestions ? <SuggestionsPanel data={currentSuggestions} locale={locale} busy={loading}
          onChoose={(option) => void chooseSuggestion(option)} onCustomize={customizeSuggestion} /> : (
          <div className="planner-route-empty-state">
            <div className="planner-route-empty-copy">
              <span className="planner-route-kicker"><Navigation size={14} /> {locale === 'en' ? 'ROUTE OPTIONS' : 'TUYẾN ĐƯỜNG GỢI Ý'}</span>
              <h2 id="planner-routes-title">{locale === 'en' ? 'Your ranked routes will appear here' : 'Danh sách tuyến đường sẽ hiện ở đây'}</h2>
              <p>{locale === 'en' ? 'Choose a departure and finish point, then find feasible routes ranked by your time, group size, budget and interests.' : 'Chọn điểm đi và điểm đến, sau đó tìm các tuyến khả thi được xếp hạng theo thời gian, số người, ngân sách và sở thích.'}</p>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
