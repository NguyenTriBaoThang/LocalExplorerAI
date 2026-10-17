import { parseSSE } from './sse'

const API = import.meta.env.VITE_API_URL as string

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
const MEALS: [string, string, string][] = [['Bữa sáng', '06:00', '10:00'], ['Bữa trưa', '11:00', '14:00'], ['Bữa tối', '17:00', '21:00']]

export function mealOf(kind: string | undefined, startTime: string): string | null {
  if (kind !== 'an-uong') return null
  return MEALS.find(([, lo, hi]) => lo <= startTime && startTime < hi)?.[0] ?? null
}

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
export function clarifyAfter(current: Clarify | null, e: AgentEvent): Clarify | null {
  if (e.type === 'clarify') return { tripId: e.trip_id, questions: e.questions }
  if (e.type === 'itinerary') return null
  return current
}

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
export function confirmAfter(current: ConfirmReplan | null, e: AgentEvent): ConfirmReplan | null {
  if (e.type === 'confirm_replan') return { tripId: e.trip_id, text: e.text, changes: e.changes, message: e.message }
  if (e.type === 'thinking' || e.type === 'tool_call') return current
  return null
}

/** Bỏ trường rỗng (ô giờ chưa nhập, chip chưa chọn) để server không trả 422. */
export function toAnswers(form: Record<string, string>): Answers {
  return Object.fromEntries(Object.entries(form).filter(([, v]) => v !== '')) as Answers
}

export async function authRequest(path: '/auth/login' | '/auth/register', email: string, password: string) {
  const r = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  const body = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Email hoặc mật khẩu không hợp lệ (mật khẩu tối thiểu 8 ký tự)')
  return body.token as string
}

const RECONNECTS = 2  // spec scale S34
const RECONNECT_MS = 1000  // đủ để nginx bỏ bản api vừa chết

/** Đọc một phản hồi SSE tới khi đóng hoặc đứt; bỏ qua `skip` event đầu (đã phát ở lần nối trước). */
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

async function streamSSE(token: string, path: string, body: unknown, onEvent: (e: AgentEvent) => void) {
  const r = await fetch(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  })
  if (r.status === 401) throw new Error('unauthorized')
  if (!r.ok || !r.body) {
    const detail = (await r.json().catch(() => ({}))).detail
    onEvent({ type: 'error', code: 'http_error', status: r.status,
      message: typeof detail === 'string' ? detail : `Lỗi máy chủ (${r.status})` })
    return
  }
  // Có X-Job-Id = việc chạy trong planner và sống tiếp khi bản api này chết: nối lại ở bản api khác (spec §10).
  const jobId = r.headers.get('X-Job-Id')
  let { count: seen, finished } = await readEvents(r, 0, onEvent)
  for (let i = 0; !finished && jobId && i < RECONNECTS; i++) {
    await new Promise((ok) => setTimeout(ok, RECONNECT_MS))
    const again = await fetch(`${API}/jobs/${jobId}/events`, { headers: { Authorization: `Bearer ${token}` } })
      .catch(() => null)
    if (!again?.ok || !again.body) continue
    const got = await readEvents(again, seen, onEvent)
    seen = Math.max(seen, got.count)
    finished = got.finished
  }
  if (!finished) onEvent({ type: 'error', message: 'Kết nối bị ngắt giữa chừng, bạn thử lại nhé.' })
}

/** tripId có → tin nhắn tiếp theo của Trip đang mở; null → chuyến mới. */
export const streamTrip = (token: string, message: string, tripId: number | null, onEvent: (e: AgentEvent) => void) =>
  streamSSE(token, '/trips', { message, trip_id: tripId }, onEvent)

export const streamPlan = (token: string, tripId: number, answers: Answers, onEvent: (e: AgentEvent) => void) =>
  streamSSE(token, `/trips/${tripId}/plan`, answers, onEvent)

export const streamReplan = (token: string, c: ConfirmReplan, onEvent: (e: AgentEvent) => void) =>
  streamSSE(token, `/trips/${c.tripId}/replan`, { changes: c.changes, message: c.message }, onEvent)

export const streamGroupReview = (token: string, tripId: number, sourceVersion: number, feedback: string,
  onEvent: (e: AgentEvent) => void) =>
  streamSSE(token, `/trips/${tripId}/group-reviews`, { source_version: sourceVersion, feedback }, onEvent)

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

async function request<T>(token: string, path: string, method = 'GET', body?: unknown): Promise<T> {
  const r = await fetch(API + path, {
    method,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (r.status === 401) throw new Error('unauthorized')
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new ApiError(r.status, typeof data.detail === 'string' ? data.detail : `Lỗi máy chủ (${r.status})`)
  return data as T
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export const applyGroupReview = (token: string, tripId: number, reviewId: number) =>
  request<ItineraryEvent>(token, `/trips/${tripId}/group-reviews/${reviewId}/apply`, 'POST', {})

export const cancelGroupReview = (token: string, tripId: number, reviewId: number) =>
  request<{ review_id: number; status: 'cancelled' }>(token, `/trips/${tripId}/group-reviews/${reviewId}/cancel`, 'POST', {})

export const reportDisruption = (token: string, tripId: number, version: number, d: DisruptionReq) =>
  request<Proposal>(token, `/trips/${tripId}/disruptions`, 'POST', { version, ...d })

export const applyProposal = (token: string, tripId: number, proposalId: number, option: number) =>
  request<ItineraryEvent>(token, `/trips/${tripId}/proposals/${proposalId}/apply`, 'POST', { option })

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

export const listTrips = (token: string) => request<TripSummary[]>(token, '/trips')
export const getTrip = (token: string, id: number, version?: number) =>
  request<TripView>(token, `/trips/${id}` + (version != null ? `?version=${version}` : ''))
export const getMessages = (token: string, id: number) => request<Message[]>(token, `/trips/${id}/messages`)
export const setPin = (token: string, tripId: number, placeId: number, pinned: boolean) =>
  request<{ pinned_place_ids: number[] }>(token, `/trips/${tripId}/pins`, 'PATCH', { place_id: placeId, pinned })
export const restoreVersion = (token: string, tripId: number, version: number) =>
  request<RestoreEvent>(token, `/trips/${tripId}/restore/${version}`, 'POST', {})

/** Đang xem một bản cũ (chỉ đọc) chứ không phải bản mới nhất. */
export const viewingOld = (version: number | null, latest: number | null) =>
  version != null && latest != null && version !== latest

export function tripLabel(t: TripSummary): string {
  const d = new Date(t.created_at)
  const dd = String(d.getDate()).padStart(2, '0'), mm = String(d.getMonth() + 1).padStart(2, '0')
  return `${t.destination_name ?? t.spec.destination} · ${t.spec.days} ngày · ${dd}/${mm}`
}

export type NodeState = 'up' | 'down' | 'unknown'
export type SystemNode = { name: string; role: string; state: NodeState; lag_ms?: number | null }
export type SystemStatus = {
  nodes: SystemNode[]; served_by: string; my_shard: number | null; planner_mode: string
  stats: {
    cache_hit: number; cache_miss: number; provider_call: number; provider_wait: number
    provider_fallback: number; rate_limited: number; waiting: number; running: number
  } | null  // null: chế độ một tiến trình, hoặc Redis chết
}

export const getSystemStatus = (token: string) => request<SystemStatus>(token, '/system/status')

// Tầng của sơ đồ cụm, từ cổng vào xuống dữ liệu (spec scale §4). Role khớp server/app/system.py.
const TIERS: [string, string[]][] = [
  ['Cổng vào', ['nginx']],
  ['API', ['api']],
  ['Lập lịch', ['planner', 'planner-agent']],
  ['Dịch vụ', ['redis', 'llm-gateway', 'places']],
  ['Dữ liệu', ['pg-catalog', 'pg-catalog-replica', 'pg-shard']],
]

export function tiers(nodes: SystemNode[]): { label: string; nodes: SystemNode[] }[] {
  const known = TIERS.flatMap(([, roles]) => roles)
  const other: [string, string[]] = ['Khác', [...new Set(nodes.map((n) => n.role).filter((r) => !known.includes(r)))]]
  return [...TIERS, other]
    .map(([label, roles]) => ({ label, nodes: roles.flatMap((r) => nodes.filter((n) => n.role === r)) }))
    .filter((t) => t.nodes.length > 0)
}
