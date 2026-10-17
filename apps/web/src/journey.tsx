import { createContext, useCallback, useContext, useEffect, useState, type Dispatch, type ReactNode, type SetStateAction } from 'react'
import type { ChatConstraints } from './types'

export type SelectedExperience = { id: string; name: string; poiId: string }
export type ChatLine = {
  id: string; role: 'assistant' | 'user'; text: string; time?: string
  snapshot?: Partial<ChatConstraints>
  assistantMode?: 'openai_compatible' | 'gemini_compatible' | 'local_fallback'
}
export type TripDraft = {
  date: string; startTime: string; endTime: string; groupSize: number; budget: number
  transport: string; intents: string[]; originId: string; destinationId: string
  lockedPois: string[]; selected: SelectedExperience[]; demo: boolean; modelId: string
}
type AssistantDraft = { conversationId: string; messages: ChatLine[]; constraints: ChatConstraints | null; busy: boolean }
const newId = () => globalThis.crypto?.randomUUID?.() ?? `trip-${Date.now()}`
const newTrip = (): TripDraft => {
  const tomorrow = new Date(Date.now() + 86400000)
  return { date: new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(tomorrow),
    startTime: '09:00', endTime: '16:00', groupSize: 2, budget: 1200000, transport: 'motorcycle',
    intents: ['culture'], originId: '', destinationId: '', lockedPois: [], selected: [], demo: false, modelId: 'nhathoducba' }
}
const newAssistant = (): AssistantDraft => ({ conversationId: newId(), messages: [], constraints: null, busy: false })
const intentMap: Record<string, string> = { 'thủ_công': 'handicraft', 'ẩm_thực': 'food', 'văn_hóa': 'culture', 'thư_giãn': 'relaxation' }
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
  toggleExperience: (item: SelectedExperience) => void; reset: () => void
} | null>(null)

export function JourneyProvider({ children, owner }: { children: ReactNode; owner: string }) {
  const storageKey = `local-explorer:journey:v1:${owner}`
  const [trip, setTrip] = useState<TripDraft>(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null')
      // Accept only our versioned form shape. Ignore stale or damaged browser data.
      if (saved && typeof saved.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(saved.date)
        && Number.isFinite(Date.parse(`${saved.date}T00:00:00+07:00`))
        && /^([01]\d|2[0-3]):[0-5]\d$/.test(saved.startTime) && /^([01]\d|2[0-3]):[0-5]\d$/.test(saved.endTime)
        && Number.isInteger(saved.groupSize) && saved.groupSize >= 1 && saved.groupSize <= 50
        && Number.isFinite(saved.budget) && saved.budget >= 0 && ['walking', 'motorcycle', 'car', 'transit'].includes(saved.transport)
        && typeof saved.originId === 'string' && typeof saved.destinationId === 'string' && typeof saved.modelId === 'string'
        && Array.isArray(saved.intents) && saved.intents.every((i: unknown) => typeof i === 'string')
        && Array.isArray(saved.lockedPois) && saved.lockedPois.every((i: unknown) => typeof i === 'string')
        && Array.isArray(saved.selected) && saved.selected.length <= 6 && saved.selected.every((i: SelectedExperience) => i && typeof i.id === 'string' && typeof i.name === 'string' && typeof i.poiId === 'string')) {
        return { ...newTrip(), ...saved, demo: saved.demo === true }
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
  const toggleExperience = useCallback((item: SelectedExperience) => setTrip((current) => ({ ...current,
    selected: current.selected.some((selected) => selected.id === item.id)
      ? current.selected.filter((selected) => selected.id !== item.id)
      : [...current.selected, item].slice(0, 6),
  })), [])
  const reset = useCallback(() => { setTrip(newTrip()); setAssistant(newAssistant()) }, [])
  return <Context.Provider value={{ trip, setTrip, assistant, setAssistant, applyConstraints, toggleExperience, reset }}>{children}</Context.Provider>
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
