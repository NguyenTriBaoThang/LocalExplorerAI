import { createContext, useCallback, useContext, useEffect, useState, type Dispatch, type ReactNode, type SetStateAction } from 'react'
import type { ChatConstraints } from './types'
import type { ChatTripSpec, Hub, Itinerary as ChatItinerary, Place as ChatPlace } from './api/trips'

export type SelectedExperience = { id: string; name: string; poiId: string }
export type ChatTripRouteEndpoint = { name: string; latitude: number; longitude: number; source: 'arrival_hub' | 'stay' | 'first_activity' | 'last_activity' }
export type ChatTripRouteStop = { day: number; date: string | null; placeId: number; name: string; kind: string; latitude: number; longitude: number; startTime: string; durationMin: number; costVnd: number; rankPosition: number | null; rankCandidateCount: number | null }
export type ChatTripContext = {
  tripId: number; destination: string; destinationName: string; days: number; startDate: string | null
  travelers: number; budget: number; interests: string[]; interestTags: string[]
  requiredTags: string[]; preferredTags: string[]; avoidedTags: string[]
  pace: string; travelMode: string | null; originCity: string | null; arrivalMode: string | null
  arrivalTime: string | null; departureTime: string | null; lastDayEnd: string | null
  routeStart: ChatTripRouteEndpoint | null; routeEnd: ChatTripRouteEndpoint | null; routeStops: ChatTripRouteStop[]; selectedRouteStopIds: number[]
}
export type ChatLine = {
  id: string; role: 'assistant' | 'user'; text: string; time?: string
  snapshot?: Partial<ChatConstraints>
  assistantMode?: 'openai_compatible' | 'gemini_compatible' | 'local_fallback' | 'unavailable'
}
export type TripDraft = {
  date: string; durationDays: number; startTime: string; endTime: string; groupSize: number; budget: number
  transport: string; intents: string[]; originId: string; destinationId: string
  lockedPois: string[]; selected: SelectedExperience[]; demo: boolean; modelId: string
  chatContext: ChatTripContext | null
}
type AssistantDraft = { conversationId: string; messages: ChatLine[]; constraints: ChatConstraints | null; busy: boolean }
const newId = () => globalThis.crypto?.randomUUID?.() ?? `trip-${Date.now()}`
const newTrip = (): TripDraft => {
  const tomorrow = new Date(Date.now() + 86400000)
  return { date: new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(tomorrow), durationDays: 1,
    startTime: '09:00', endTime: '16:00', groupSize: 2, budget: 1200000, transport: 'motorcycle',
    intents: ['culture'], originId: '', destinationId: '', lockedPois: [], selected: [], demo: false, modelId: 'nhathoducba', chatContext: null }
}
const newAssistant = (): AssistantDraft => ({ conversationId: newId(), messages: [], constraints: null, busy: false })
const intentMap: Record<string, string> = { 'thủ_công': 'handicraft', 'ẩm_thực': 'food', 'văn_hóa': 'culture', 'thư_giãn': 'relaxation' }
const chatTagToPlannerIntent: Record<string, string> = {
  'an-dia-phuong': 'food', 'hai-san': 'food', 'an-chay': 'food',
  'lich-su': 'culture', 'van-hoa': 'culture', 'thien-nhien': 'nature',
  'check-in': 'sightseeing', 'view-dep': 'sightseeing',
  'cafe-chill': 'coffee', 'yen-tinh': 'relaxation', 'lang-man': 'relaxation', 'thu-cong': 'handicraft',
  dem: 'entertainment', 'soi-dong': 'entertainment', 'mua-sam': 'shopping',
}
const paceHours: Record<ChatTripSpec['pace'], [string, string]> = {
  'thong-tha': ['09:00', '20:00'], vua: ['08:00', '21:00'], day: ['07:00', '22:00'],
}

function plannerTransport(value: string | null): string | null {
  if (value === 'xe-may' || value === 'xe-may-rieng') return 'motorcycle'
  if (value === 'o-to-rieng' || value === 'grab') return 'car'
  return null
}

function plannerIntents(spec: ChatTripSpec): string[] {
  const tags = [...spec.required_tags, ...spec.preferred_tags]
  return [...new Set(tags.map((tag) => chatTagToPlannerIntent[tag]).filter((intent): intent is string => Boolean(intent)))]
}

function offsetTime(value: string | null, offsetMinutes: number): string | null {
  if (!value) return null
  const [hour, minute] = value.split(':').map(Number)
  if (!Number.isInteger(hour) || !Number.isInteger(minute)) return null
  const shifted = hour * 60 + minute + offsetMinutes
  const bounded = Math.max(0, Math.min(23 * 60 + 59, shifted))
  return `${String(Math.floor(bounded / 60)).padStart(2, '0')}:${String(bounded % 60).padStart(2, '0')}`
}

function isChatTripContext(value: unknown): value is ChatTripContext {
  if (!value || typeof value !== 'object') return false
  const context = value as Partial<ChatTripContext>
  return Number.isInteger(context.tripId) && typeof context.destination === 'string'
    && typeof context.destinationName === 'string' && Number.isInteger(context.days)
    && (context.startDate === null || typeof context.startDate === 'string')
    && Number.isInteger(context.travelers) && typeof context.budget === 'number'
    && Array.isArray(context.interests) && Array.isArray(context.interestTags)
    && Array.isArray(context.requiredTags) && Array.isArray(context.preferredTags) && Array.isArray(context.avoidedTags)
    && (context.routeStops == null || Array.isArray(context.routeStops))
    && typeof context.pace === 'string'
}

function transferChatRoute(itinerary: ChatItinerary | null, places: Record<string, ChatPlace>, hub: Hub | null) {
  const routeStops: ChatTripRouteStop[] = itinerary?.days.flatMap((day, dayIndex) => day.stops.flatMap((stop) => {
    const place = places[String(stop.place_id)]
    return place ? [{
      day: dayIndex + 1, date: day.date, placeId: stop.place_id, name: place.name, kind: place.kind,
      latitude: place.lat, longitude: place.lon,
      startTime: stop.start_time, durationMin: stop.duration_min, costVnd: stop.est_cost,
      rankPosition: place.rank_position ?? null, rankCandidateCount: place.rank_candidate_count ?? null,
    }] : []
  })) ?? []
  const stay = itinerary?.stay_place_id == null ? undefined : places[String(itinerary.stay_place_id)]
  const first = routeStops[0]
  const last = routeStops[routeStops.length - 1]
  const routeStart: ChatTripRouteEndpoint | null = hub
    ? { name: hub.name, latitude: hub.lat, longitude: hub.lon, source: 'arrival_hub' }
    : stay ? { name: stay.name, latitude: stay.lat, longitude: stay.lon, source: 'stay' }
      : first ? { name: first.name, latitude: places[String(first.placeId)].lat, longitude: places[String(first.placeId)].lon, source: 'first_activity' } : null
  const routeEnd: ChatTripRouteEndpoint | null = hub
    ? { name: hub.name, latitude: hub.lat, longitude: hub.lon, source: 'arrival_hub' }
    : stay ? { name: stay.name, latitude: stay.lat, longitude: stay.lon, source: 'stay' }
      : last ? { name: last.name, latitude: places[String(last.placeId)].lat, longitude: places[String(last.placeId)].lon, source: 'last_activity' } : null
  return { routeStart, routeEnd, routeStops }
}

export function chatContext(trip: TripDraft, previous: ChatConstraints | null): ChatConstraints | null {
  if (!previous) return null
  const weights: Record<string, number> = { 'thủ_công': 0, 'ẩm_thực': 0, 'văn_hóa': 0, 'thư_giãn': 0 }
  for (const intent of trip.intents) {
    const key = Object.keys(intentMap).find((item) => intentMap[item] === intent) || (intent === 'nature' ? 'thư_giãn' : '')
    if (key) weights[key] += 1
  }
  const total = Object.values(weights).reduce((sum, weight) => sum + weight, 0)
  return { ...previous,
    group_size: previous.group_size === null ? null : trip.groupSize,
    budget_vnd: previous.budget_vnd === null ? null : trip.budget,
    start_time: previous.start_time === null ? null : trip.startTime,
    return_deadline: previous.return_deadline === null ? null : trip.endTime,
    travel_mode: ['motorcycle', 'walking', 'car', 'transit'].includes(trip.transport) ? trip.transport as ChatConstraints['travel_mode'] : previous.travel_mode,
    intent_weights: total ? Object.fromEntries(Object.entries(weights).map(([key, value]) => [key, value / total])) : previous.intent_weights,
  }
}
const Context = createContext<{
  trip: TripDraft; setTrip: Dispatch<SetStateAction<TripDraft>>
  assistant: AssistantDraft; setAssistant: Dispatch<SetStateAction<AssistantDraft>>
  applyConstraints: (constraints: ChatConstraints) => void
  syncChatTrip: (tripId: number, spec: ChatTripSpec, destinationName?: string | null) => void
  syncChatItinerary: (itinerary: ChatItinerary | null, places: Record<string, ChatPlace>, hub?: Hub | null) => void
  toggleChatRouteStop: (placeId: number) => void
  toggleExperience: (item: SelectedExperience) => void; reset: () => void
} | null>(null)

export function JourneyProvider({ children, owner }: { children: ReactNode; owner: string }) {
  const storageKey = `local-explorer:journey:v1:${owner}`
  const [trip, setTrip] = useState<TripDraft>(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null')
      // Accept only our versioned form shape. Ignore stale or damaged browser data.
      if (saved && typeof saved.date === 'string' && (saved.date === '' || /^\d{4}-\d{2}-\d{2}$/.test(saved.date))
        && (!saved.date || Number.isFinite(Date.parse(`${saved.date}T00:00:00+07:00`)))
        && /^([01]\d|2[0-3]):[0-5]\d$/.test(saved.startTime) && /^([01]\d|2[0-3]):[0-5]\d$/.test(saved.endTime)
        && (saved.durationDays == null || (Number.isInteger(saved.durationDays) && saved.durationDays >= 1 && saved.durationDays <= 7))
        && Number.isInteger(saved.groupSize) && saved.groupSize >= 1 && saved.groupSize <= 50
        && Number.isFinite(saved.budget) && saved.budget >= 0 && ['walking', 'motorcycle', 'car', 'transit'].includes(saved.transport)
        && typeof saved.originId === 'string' && typeof saved.destinationId === 'string' && typeof saved.modelId === 'string'
        && Array.isArray(saved.intents) && saved.intents.every((i: unknown) => typeof i === 'string')
        && Array.isArray(saved.lockedPois) && saved.lockedPois.every((i: unknown) => typeof i === 'string')
        && Array.isArray(saved.selected) && saved.selected.length <= 6 && saved.selected.every((i: SelectedExperience) => i && typeof i.id === 'string' && typeof i.name === 'string' && typeof i.poiId === 'string')) {
        const savedChatContext = isChatTripContext(saved.chatContext) ? {
          ...saved.chatContext,
          routeStart: saved.chatContext.routeStart ?? null,
          routeEnd: saved.chatContext.routeEnd ?? null,
          routeStops: saved.chatContext.routeStops ?? [],
          selectedRouteStopIds: saved.chatContext.selectedRouteStopIds ?? [],
        } : null
        return { ...newTrip(), ...saved, durationDays: saved.durationDays ?? 1,
          chatContext: savedChatContext, demo: saved.demo === true }
      }
    } catch { /* Storage may be disabled. The active trip still works in memory. */ }
    return newTrip()
  })
  // Conversations live only in this tab's memory; we persist explicit trip choices.
  const [assistant, setAssistant] = useState<AssistantDraft>(newAssistant)
  useEffect(() => { try { sessionStorage.setItem(storageKey, JSON.stringify(trip)) } catch { /* optional storage */ } }, [storageKey, trip])
  const applyConstraints = useCallback((constraints: ChatConstraints) => {
    setAssistant((current) => ({ ...current, constraints }))
    setTrip((current) => ({ ...current,
      groupSize: constraints.group_size ?? current.groupSize, budget: constraints.budget_vnd ?? current.budget,
      startTime: constraints.start_time ?? current.startTime, endTime: constraints.return_deadline ?? current.endTime,
      transport: constraints.travel_mode,
      intents: Object.entries(constraints.intent_weights).filter(([, weight]) => weight > 0).map(([key]) => intentMap[key] || key),
    }))
  }, [])
  const syncChatTrip = useCallback((tripId: number, spec: ChatTripSpec, destinationName?: string | null) => {
    const [paceStart, paceEnd] = paceHours[spec.pace] ?? paceHours.vua
    const interests = plannerIntents(spec)
    const transport = plannerTransport(spec.travel_mode)
    const resolvedName = destinationName || (spec.destination === 'tp-hcm' ? 'TP. Hồ Chí Minh' : spec.destination)
    const startTime = offsetTime(spec.arrival_time, 60) ?? paceStart
    const endTime = spec.last_day_end ?? offsetTime(spec.departure_time, -90) ?? paceEnd
    setTrip((current) => ({
      ...current,
      date: spec.start_date ?? '', durationDays: spec.days,
      startTime,
      endTime,
      groupSize: spec.travelers, budget: spec.budget,
      transport: transport ?? current.transport,
      intents: interests,
      originId: '', destinationId: '', lockedPois: [], selected: [], demo: false,
      chatContext: {
        tripId, destination: spec.destination, destinationName: resolvedName, days: spec.days,
        startDate: spec.start_date, travelers: spec.travelers, budget: spec.budget,
        interests, interestTags: [...new Set([...spec.required_tags, ...spec.preferred_tags])],
        requiredTags: spec.required_tags, preferredTags: spec.preferred_tags, avoidedTags: spec.avoided_tags,
        pace: spec.pace, travelMode: spec.travel_mode, originCity: spec.origin_city, arrivalMode: spec.arrival_mode,
        arrivalTime: spec.arrival_time, departureTime: spec.departure_time, lastDayEnd: spec.last_day_end,
        routeStart: null, routeEnd: null, routeStops: [], selectedRouteStopIds: [],
      },
    }))
  }, [])
  const syncChatItinerary = useCallback((itinerary: ChatItinerary | null, places: Record<string, ChatPlace>, hub: Hub | null = null) => {
    const route = transferChatRoute(itinerary, places, hub)
    setTrip((current) => current.chatContext
      ? { ...current, chatContext: { ...current.chatContext, ...route,
          selectedRouteStopIds: current.chatContext.routeStops.length
            ? current.chatContext.selectedRouteStopIds.filter((id) => route.routeStops.some((stop) => stop.placeId === id))
            : route.routeStops.map((stop) => stop.placeId),
        } }
      : current)
  }, [])
  const toggleChatRouteStop = useCallback((placeId: number) => setTrip((current) => {
    if (!current.chatContext) return current
    const selected = current.chatContext.selectedRouteStopIds
    return { ...current, chatContext: { ...current.chatContext,
      selectedRouteStopIds: selected.includes(placeId) ? selected.filter((id) => id !== placeId) : [...selected, placeId],
    } }
  }), [])
  const toggleExperience = useCallback((item: SelectedExperience) => setTrip((current) => ({ ...current,
    selected: current.selected.some((selected) => selected.id === item.id)
      ? current.selected.filter((selected) => selected.id !== item.id)
      : [...current.selected, item].slice(0, 6),
  })), [])
  const reset = useCallback(() => { setTrip(newTrip()); setAssistant(newAssistant()) }, [])
  return <Context.Provider value={{ trip, setTrip, assistant, setAssistant, applyConstraints, syncChatTrip, syncChatItinerary, toggleChatRouteStop, toggleExperience, reset }}>{children}</Context.Provider>
}
export function useJourney() {
  const value = useContext(Context)
  if (!value) throw new Error('JourneyProvider is required')
  return value
}
export function useTripField<K extends keyof TripDraft>(key: K): [TripDraft[K], Dispatch<SetStateAction<TripDraft[K]>>] {
  const { trip, setTrip } = useJourney()
  const setter = useCallback((value: SetStateAction<TripDraft[K]>) => setTrip((current) => ({ ...current,
    [key]: typeof value === 'function' ? (value as (previous: TripDraft[K]) => TripDraft[K])(current[key]) : value,
  })), [key, setTrip])
  return [trip[key], setter]
}
export function useAssistantField<K extends keyof AssistantDraft>(key: K): [AssistantDraft[K], Dispatch<SetStateAction<AssistantDraft[K]>>] {
  const { assistant, setAssistant } = useJourney()
  const setter = useCallback((value: SetStateAction<AssistantDraft[K]>) => setAssistant((current) => ({ ...current,
    [key]: typeof value === 'function' ? (value as (previous: AssistantDraft[K]) => AssistantDraft[K])(current[key]) : value,
  })), [key, setAssistant])
  return [assistant[key], setter]
}
