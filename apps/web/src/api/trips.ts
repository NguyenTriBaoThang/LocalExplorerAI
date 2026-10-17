export { mealOf, clarifyAfter, confirmAfter, viewingOld, toAnswers } from '../components/trip/tripState'
import { parseSSE } from '../components/trip/sse'
import { api, AUTH_EXPIRED_EVENT } from './client'
import axios from 'axios'

const API = String(api.defaults.baseURL || '/api')

export type Place = {
  id: number; name: string; kind: string; lat: number; lon: number
  photo_url: string | null; outdoor: boolean; price: number
  open_hours?: Record<string, [string, string] | null>; description?: string  // thiếu ở Itinerary lưu trước T4
}
export type Stop = {
  place_id: number; start_time: string; duration_min: number; reason: string; pinned: boolean; est_cost: number
}
export type Leg = {
  from_place_id: number | null; to_place_id: number | null  // null = Hub (sân bay/bến xe)
  distance_km: number; duration_min: number; mode: string; cost: number
}
export type Question = { field: 'travel_mode' | 'arrival'; text: string; options: { value: string; label: string }[] }
export type Answers = { travel_mode?: string; arrival_mode?: string; arrival_time?: string; departure_time?: string }
export type Day = { date: string | null; stops: Stop[]; legs: Leg[]; rain_chance: number | null }
export type Conflict = { kind: string; message: string; day_index: number | null; place_id: number | null }
export type Itinerary = {
  stay_place_id: number | null; days: Day[]; total_cost: number; conflicts: Conflict[]; summary: string
  intents?: Record<string, boolean>; retention?: number | null  // thiếu ở Itinerary lưu trước lát A
}
export type GroupReview = {
  review_id: number; source_version: number; base_version: number; source_is_old: boolean
  feedback: string; summary: string; unresolved_feedback: string[]; changed: [number, number][]
  itinerary: Itinerary; places: Record<string, Place>
}
export type AgentEvent =
  | { type: 'thinking'; text: string }
  | { type: 'trip'; trip_id: number; trip: { budget: number }; center: [number, number] }
  | { type: 'tool_call'; name: string; query: string; places: Place[]; agent?: string }  // agent: role chuyên gia khi lập lịch đa agent
  | { type: 'clarify'; trip_id: number; questions: Question[] }
  | {
    type: 'itinerary'; itinerary: Itinerary; places: Record<string, Place>; trip_id: number; version: number
    changed?: [number, number][]  // [ngày, Stop] vừa đổi khi sửa lịch; lập mới thì không có
  }
  | { type: 'group_review_preview'; review: GroupReview }
  | { type: 'answer'; text: string }  // trả lời câu hỏi trên Trip đang mở, không đổi lịch trình
  | { type: 'confirm_replan'; trip_id: number; text: string; changes: Record<string, unknown>; message: string }
  | { type: 'error'; message: string; code?: 'stale_base' | 'http_error'; status?: number }

// Khớp MEALS ở server/app/rules.py: Stop an-uong bắt đầu trong khung giờ = bữa đó
export const vnd = (n: number) => n.toLocaleString('vi-VN') + 'đ'

// Khớp INTENT_LABELS ở server/app/domain.py
export const INTENT_LABELS: Record<string, string> = {
  'am-thuc': 'Ẩm thực', 'thien-nhien': 'Thiên nhiên', 'van-hoa': 'Văn hoá', 'thu-gian': 'Thư giãn', 'vui-choi': 'Vui chơi',
}

export function intentChips(it: Itinerary): { label: string; ok: boolean }[] {
  return Object.entries(it.intents ?? {}).map(([k, ok]) => ({ label: INTENT_LABELS[k] ?? k, ok }))
}

export type Clarify = { tripId: number; questions: Question[] }

/** Thẻ hỏi lại chỉ mất khi đã có lịch trình — /plan lỗi (422, AI lỗi) thì giữ để người dùng sửa hoặc thử lại. */
const AGENT_LABELS: Record<string, string> = { 'an-uong': 'Ăn uống', 'tham-quan': 'Tham quan', 'cho-o': 'Chỗ ở' }

export function searchLine(e: { query: string; places: unknown[]; agent?: string }): string {
  const line = `Đang tìm: ${e.query} (${e.places.length} kết quả)`
  const label = e.agent && AGENT_LABELS[e.agent]
  return label ? `${label} · ${line}` : line
}

/** Event kết thúc một lượt; thêm event mới ở server thì cân nhắc thêm vào đây. */
export const isFinal = (e: AgentEvent) => !['thinking', 'trip', 'tool_call'].includes(e.type)

export type ConfirmReplan = { tripId: number; text: string; changes: Record<string, unknown>; message: string }

/** Thẻ "đổi Trip sẽ lập lại, tiếp tục?": hiện khi server hỏi, ẩn khi có kết quả khác (trừ lúc đang nghĩ/tìm). */
async function readEvents(r: Response, skip: number, onEvent: (e: AgentEvent) => void) {
  const reader = r.body!.pipeThrough(new TextDecoderStream()).getReader()
  let buf = ''
  let count = 0
  let finished = false
  for (;;) {
    // Chỉ lỗi đọc mạng mới coi như luồng đóng sớm; lỗi lúc xử lý event phải ném ra để App báo.
    const chunk = await reader.read().catch(() => null)
    if (!chunk || chunk.done) break
    buf += chunk.value
    const { events, rest } = parseSSE(buf)
    buf = rest
    for (const e of events) {
      count += 1
      if (count <= skip) continue
      const ev = e as AgentEvent
      if (isFinal(ev)) finished = true
      onEvent(ev)
    }
  }
  return { count, finished }
}

async function streamSSE(path: string, body: unknown, onEvent: (e: AgentEvent) => void) {
  const r = await fetch(API + path, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (r.status === 401) { window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT)); throw new Error('unauthorized') }
  if (!r.ok || !r.body) {
    const body = await r.json().catch(() => ({}))
    const detail = body.detail ?? body.error?.message
    onEvent({ type: 'error', code: 'http_error', status: r.status,
      message: typeof detail === 'string' ? detail : `Lỗi máy chủ (${r.status})` })
    return
  }
  const { finished } = await readEvents(r, 0, onEvent)
  if (!finished) onEvent({ type: 'error', message: 'Kết nối bị ngắt giữa chừng, bạn thử lại nhé.' })
}

/** tripId có → tin nhắn tiếp theo của Trip đang mở; null → chuyến mới. */
export const streamTrip = (message: string, tripId: number | null, onEvent: (e: AgentEvent) => void) =>
  streamSSE('/trips', { message, trip_id: tripId }, onEvent)

export const streamPlan = (tripId: number, answers: Answers, onEvent: (e: AgentEvent) => void) =>
  streamSSE(`/trips/${tripId}/plan`, answers, onEvent)

export const streamReplan = (c: ConfirmReplan, onEvent: (e: AgentEvent) => void) =>
  streamSSE(`/trips/${c.tripId}/replan`, { changes: c.changes, message: c.message }, onEvent)

export const streamGroupReview = (tripId: number, sourceVersion: number, feedback: string,
  onEvent: (e: AgentEvent) => void) =>
  streamSSE(`/trips/${tripId}/group-reviews`, { source_version: sourceVersion, feedback }, onEvent)

export type DisruptionKind = 'closed' | 'disliked' | 'rain' | 'late'
export type DisruptionReq = { kind: DisruptionKind; day_index: number; stop_index?: number; minutes?: number }
export type ItineraryEvent = Extract<AgentEvent, { type: 'itinerary' }>
export type ProposalOption = {
  itinerary: Itinerary; places: Record<string, Place>; changed: [number, number][]
  metrics: {
    cost_delta: number; travel_min_delta: number; day_end_after: string; retention_after: number | null
    intents_kept: string[]; intents_lost: string[]
  }
  reason_codes: string[]; explanation: string; title: string; added: number[]
}
export type Proposal = { proposal_id: number; options?: ProposalOption[]; no_feasible?: string[] }

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  try {
    const response = await api.request<T>({ url: path, method, data: body })
    return response.data
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 401) throw new Error('unauthorized')
      const detail = error.response?.data?.detail ?? error.response?.data?.error?.message
      throw new ApiError(error.response?.status ?? 0, typeof detail === 'string' ? detail : detail?.message ?? 'Không kết nối được máy chủ.')
    }
    throw error
  }
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export const applyGroupReview = (tripId: number, reviewId: number) =>
  request<ItineraryEvent>(`/trips/${tripId}/group-reviews/${reviewId}/apply`, 'POST', {})

export const cancelGroupReview = (tripId: number, reviewId: number) =>
  request<{ review_id: number; status: 'cancelled' }>(`/trips/${tripId}/group-reviews/${reviewId}/cancel`, 'POST', {})

export const reportDisruption = (tripId: number, version: number, d: DisruptionReq) =>
  request<Proposal>(`/trips/${tripId}/disruptions`, 'POST', { version, ...d })

export const applyProposal = (tripId: number, proposalId: number, option: number) =>
  request<ItineraryEvent>(`/trips/${tripId}/proposals/${proposalId}/apply`, 'POST', { option })

const NO_FEASIBLE_TEXT: Record<string, string> = {
  NO_CANDIDATE: 'Chưa có Place nào cùng loại để thay.',
  NO_OPEN_CANDIDATE: 'Các Place tương tự đều đóng cửa vào giờ này.',
  NOT_REACHABLE_IN_TIME: 'Các Place tương tự quá xa, không kịp giờ Stop kế tiếp.',
  OVER_BUDGET: 'Thay thế sẽ vượt Budget.',
  NEW_CONFLICT: 'Thay thế sẽ làm lịch trình phát sinh xung đột mới.',
  NOTHING_OUTDOOR: 'Ngày này không có Stop ngoài trời nào cần đổi.',
  NO_INDOOR_CANDIDATE: 'Không có Place trong nhà nào thay được.',
}
export const noFeasibleText = (codes: string[]) => codes.map((c) => NO_FEASIBLE_TEXT[c] ?? c)

export const optionPlaces = (o: ProposalOption): Place[] =>
  o.added.map((id) => o.places[id]).filter((p): p is Place => p !== undefined)

export const rainable = (day: Day, places: Record<string, Place>, pins: number[]) =>
  day.stops.some((s) => places[s.place_id]?.outdoor && !pins.includes(s.place_id))

export const signed = (n: number, unit: (x: number) => string) =>
  n === 0 ? 'như cũ' : (n > 0 ? '+' : '−') + unit(Math.abs(n))

export type TripSummary = {
  id: number; spec: { destination: string; days: number }; created_at: string; destination_name: string | null
}
export type TripView = {
  trip_id: number; trip: { budget: number }; center: [number, number]; version: number | null
  itinerary: Itinerary | null; places: Record<string, Place>; versions: number[]; pinned_place_ids: number[]
}
export type Message = { role: 'user' | 'ai'; text: string; version: number | null }
export type RestoreEvent = ItineraryEvent & { pinned_place_ids: number[] }

export const listTrips = () => request<TripSummary[]>('/trips')
export const getTrip = (id: number, version?: number) =>
  request<TripView>(`/trips/${id}` + (version != null ? `?version=${version}` : ''))
export const getMessages = (id: number) => request<Message[]>(`/trips/${id}/messages`)
export const setPin = (tripId: number, placeId: number, pinned: boolean) =>
  request<{ pinned_place_ids: number[] }>(`/trips/${tripId}/pins`, 'PATCH', { place_id: placeId, pinned })
export const restoreVersion = (tripId: number, version: number) =>
  request<RestoreEvent>(`/trips/${tripId}/restore/${version}`, 'POST', {})

/** Đang xem một bản cũ (chỉ đọc) chứ không phải bản mới nhất. */
export function tripLabel(t: TripSummary): string {
  const d = new Date(t.created_at)
  const dd = String(d.getDate()).padStart(2, '0'), mm = String(d.getMonth() + 1).padStart(2, '0')
  return `${t.destination_name ?? t.spec.destination} · ${t.spec.days} ngày · ${dd}/${mm}`
}

