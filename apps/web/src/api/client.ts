import axios from 'axios'
import { t } from '../i18n'
import type { AuthUser, MfaChallenge, MfaSetup, MfaStatus, Booking, ChatReply, ChatServiceStatus, Experience, GeocodeResponse, GoogleOAuthStatus, Itinerary, POI, POIDetail, RoutingCapabilities, SessionInfo } from '../types'

export const api = axios.create({ baseURL: '/api', timeout: 30000, withCredentials: true })

export type WebPushStatus = { configured: boolean; enabled: boolean; device_count: number }

export async function getWebPushStatus(): Promise<WebPushStatus> {
  return (await api.get<WebPushStatus>('/notifications/push/status')).data
}

export async function getWebPushPublicKey(): Promise<string> {
  return (await api.get<{ public_key: string }>('/notifications/push/vapid-public-key')).data.public_key
}

export async function saveWebPushSubscription(payload: { endpoint: string; keys: { p256dh: string; auth: string } }): Promise<void> {
  await api.post('/notifications/push/subscriptions', payload)
}

export async function deleteWebPushSubscription(endpoint: string): Promise<void> {
  await api.delete('/notifications/push/subscriptions', { data: { endpoint } })
}

/** Fired when the server says the session is over (the access token is refreshed transparently, so a 401 here is final). */
export const AUTH_EXPIRED_EVENT = 'auth:expired'
api.interceptors.response.use(
  (response) => response,
  (error: { response?: { status?: number; data?: { error?: { code?: string } } }; config?: { url?: string } }) => {
    const url = error.config?.url ?? ''
    if (error.response?.status === 401 && !url.startsWith('/auth/')) window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
    // An administrator without a second factor is sent to the page where one is set up.
    if (error.response?.status === 403 && error.response.data?.error?.code === 'MFA_REQUIRED' && !window.location.pathname.startsWith('/profile')) {
      window.location.assign('/profile')
    }
    return Promise.reject(error)
  },
)

export function isMfaChallenge(value: AuthUser | MfaChallenge): value is MfaChallenge {
  return (value as MfaChallenge).mfa_required === true
}

/** Resolves to the user, or to a challenge when the account has two-factor authentication (finish with `loginMfa`). */
export async function login(email: string, password: string): Promise<AuthUser | MfaChallenge> {
  const { data } = await api.post<AuthUser | MfaChallenge>('/auth/login', { email, password })
  return data
}

export async function loginMfa(mfa_ticket: string, code: string): Promise<AuthUser> {
  const { data } = await api.post<AuthUser>('/auth/login/mfa', { mfa_ticket, code })
  return data
}

export async function getMfaStatus(): Promise<MfaStatus> {
  return (await api.get<MfaStatus>('/auth/mfa')).data
}

export async function beginMfaSetup(): Promise<MfaSetup> {
  return (await api.post<MfaSetup>('/auth/mfa/setup')).data
}

export async function enableMfa(code: string): Promise<string[]> {
  return (await api.post<{ recovery_codes: string[] }>('/auth/mfa/enable', { code })).data.recovery_codes
}

export async function regenerateRecoveryCodes(code: string): Promise<string[]> {
  return (await api.post<{ recovery_codes: string[] }>('/auth/mfa/recovery-codes', { code })).data.recovery_codes
}

export async function disableMfa(code: string, password: string | null): Promise<void> {
  await api.post('/auth/mfa/disable', { code, password })
}

export async function registerAccount(email: string, display_name: string, password: string): Promise<AuthUser> {
  const { data } = await api.post<AuthUser>('/auth/register', { email, display_name, password })
  return data
}

export async function getCurrentUser(): Promise<AuthUser> {
  const { data } = await api.get<{ user: AuthUser | null }>('/auth/session')
  if (!data.user) throw new Error('No active session')
  return data.user
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout')
}

export async function sendChatMessage(message: string, conversation_id: string, context: { previous_constraints?: ChatReply['structured_constraints'] | null; model_id?: string } = {}): Promise<ChatReply> {
  const { data } = await api.post<ChatReply>('/chat/message', { message, conversation_id, ...context }, { timeout: 65000 })
  return data
}

export async function getChatServiceStatus(): Promise<ChatServiceStatus> {
  const { data } = await api.get<ChatServiceStatus>('/chat/status')
  return data
}

export async function getGoogleOAuthStatus(): Promise<GoogleOAuthStatus> {
  const { data } = await api.get<GoogleOAuthStatus>('/auth/google/status')
  return data
}

export async function updateProfile(display_name: string, phone: string | null): Promise<AuthUser> {
  const { data } = await api.patch<AuthUser>('/auth/me', { display_name, phone })
  return data
}

export type RecommendationConsent = {
  personalization_enabled: boolean
  model_training_enabled: boolean
  admin_history_enabled: boolean
  consent_version: string
}

export type BehaviorExperimentStatus = {
  available: boolean
  model_version: string | null
  dataset_status: string
  deployment_eligible: false
  warning: string
}

export type BehaviorExperimentRankResult = {
  model_version: string | null
  dataset_status: string
  warning: string
  score_type: 'relative_ranking_score_not_probability'
  ranked_candidates: Array<{ experience_id: string; score: number }>
}

export type RecommendationInteraction = {
  event_id: string
  request_id: string
  experience_id: string
  event_type: 'impression' | 'selected' | 'dismissed'
  position?: number
  context: {
    intent_tags: string[]
    budget_band: 'under_500k' | '500k_1m' | '1m_2m' | 'over_2m'
    group_size: number
    indoor_preference: 'all' | 'indoor' | 'outdoor'
    time_bucket: 'morning' | 'afternoon' | 'evening'
  }
}

export async function getRecommendationConsent(): Promise<RecommendationConsent> {
  const { data } = await api.get<RecommendationConsent>('/recommendations/consent')
  return data
}

export async function getBehaviorExperimentStatus(): Promise<BehaviorExperimentStatus> {
  const { data } = await api.get<BehaviorExperimentStatus>('/recommendations/behavior-experiment/status')
  return data
}

export async function rankBehaviorExperiences(payload: {
  experience_ids: string[]
  intent_tags: string[]
  budget_band: RecommendationInteraction['context']['budget_band'] & string
  group_size: number
  center_latitude?: number
  center_longitude?: number
}): Promise<BehaviorExperimentRankResult> {
  const { data } = await api.post<BehaviorExperimentRankResult>(
    '/recommendations/behavior-experiment/rank',
    payload,
  )
  return data
}

export async function updateRecommendationConsent(
  personalization_enabled: boolean,
  model_training_enabled: boolean,
  admin_history_enabled: boolean,
): Promise<RecommendationConsent> {
  const { data } = await api.put<RecommendationConsent>('/recommendations/consent', {
    personalization_enabled,
    model_training_enabled,
    admin_history_enabled,
    consent_version: 'behavior-v2',
  })
  return data
}

export async function recordRecommendationInteractions(events: RecommendationInteraction[]): Promise<void> {
  if (!events.length) return
  await api.post('/recommendations/interactions', { events })
}

export async function changePassword(current_password: string | null, new_password: string): Promise<void> {
  await api.post('/auth/password', { current_password, new_password })
}

export async function getMyItineraries() {
  const { data } = await api.get<Array<{ id: string; planned_date: string | null; status: string; estimated_cost_vnd: number }>>('/me/itineraries')
  return data
}

export async function createShareLink(itineraryId: string): Promise<{ share_url: string; share_token: string }> {
  const { data } = await api.post<{ share_url: string; share_token: string }>(`/itineraries/${itineraryId}/share`)
  return data
}

export async function getSharedItinerary(token: string): Promise<Itinerary> {
  const { data } = await api.get<Itinerary>(`/shared/itineraries/${token}`)
  return data
}

export async function claimTicket(payload: {
  claim_token: string
  email: string
  password: string
  display_name?: string
}): Promise<AuthUser> {
  const { data } = await api.post<AuthUser>('/auth/claim-ticket', payload)
  return data
}

export async function forgotPassword(email: string): Promise<void> {
  await api.post('/auth/password/forgot', { email })
}

export async function resetPassword(token: string, new_password: string): Promise<void> {
  await api.post('/auth/password/reset', { token, new_password })
}

export async function verifyEmail(token: string): Promise<void> {
  await api.post('/auth/email/verify', { token })
}

export async function resendVerification(): Promise<{ already_verified?: boolean; email_queued?: boolean }> {
  const { data } = await api.post('/auth/email/verify/resend')
  return data
}

export async function listSessions(): Promise<SessionInfo[]> {
  const { data } = await api.get<SessionInfo[]>('/auth/sessions')
  return data
}

export async function revokeSession(id: string): Promise<void> {
  await api.delete(`/auth/sessions/${encodeURIComponent(id)}`)
}

export async function logoutAllDevices(): Promise<void> {
  await api.post('/auth/logout-all')
}

export async function submitFeedback(itineraryId: string, rating: number, review_text: string) {
  const { data } = await api.post(`/itineraries/${itineraryId}/feedback`, { rating, review_text })
  return data
}

export async function getMyBookings(itineraryId?: string): Promise<Booking[]> {
  const { data } = await api.get<Booking[]>('/bookings', { params: itineraryId ? { itinerary_id: itineraryId } : {} })
  return data
}

export async function requestBooking(itineraryId: string, stopId: string, quantity: number): Promise<Booking> {
  const { data } = await api.post<Booking>('/bookings', {
    itinerary_id: itineraryId,
    itinerary_stop_id: stopId,
    quantity,
  })
  return data
}

export async function cancelBooking(bookingId: string, reason = ''): Promise<Booking> {
  const { data } = await api.post<Booking>(`/bookings/${bookingId}/cancel`, { reason })
  return data
}

export async function beginBookingCheckout(bookingId: string): Promise<{ checkout_url: string }> {
  const { data } = await api.post<{ checkout_url: string }>(`/bookings/${bookingId}/checkout`)
  return data
}

export async function searchExperiences(q: string, params: Record<string, string | number | boolean>, semantic = false): Promise<Experience[]> {
  const { data } = await api.get<{ items: Experience[] }>('/experience-search', { params: { ...params, q, semantic } })
  return data.items
}

export async function geocodeAddress(address: string): Promise<GeocodeResponse> {
  const { data } = await api.get<GeocodeResponse>('/geocoding/forward', { params: { address } })
  return data
}

export async function getRoutingCapabilities(): Promise<RoutingCapabilities> {
  const { data } = await api.get<RoutingCapabilities>('/routing/capabilities')
  return data
}

export async function getNotifications() {
  const { data } = await api.get<Array<{ event_id: string; itinerary_id: string; stop_id: string; slot_id: string; message: string }>>('/notifications')
  return data
}

export async function requestReplanAdvice(itineraryId: string, eventId: string) {
  const { data } = await api.post<Record<string, unknown>>(`/itineraries/${itineraryId}/replan-advice`, { event_id: eventId })
  return data
}

export async function acceptReplan(itineraryId: string, payload: Record<string, string | number>) {
  const { data } = await api.post<Record<string, unknown>>(`/itineraries/${itineraryId}/replan-advice/accept`, payload)
  return data
}

export async function getItineraryVersions(itineraryId: string) {
  const { data } = await api.get<Array<{ version: number; stops: Array<{ experience_id: string; name: string; stop_order: number; cost_vnd: number; arrival_at?: string; departure_at?: string }>; total_cost_vnd: number; total_travel_time_s: number; created_at: string }>>(`/itineraries/${itineraryId}/versions`)
  return data
}

export async function compareItineraries(firstId: string, secondId: string) {
  const { data } = await api.get<Record<string, unknown>>('/itinerary-comparisons', { params: { first_id: firstId, second_id: secondId } })
  return data
}

export async function getExperiences(params?: Record<string, string | number | boolean>): Promise<Experience[]> {
  const { data } = await api.get<Experience[]>('/experiences', { params })
  return data
}

export async function getPOIs(scope: 'pilot' | 'citywide' = 'pilot', verifiedOnly = false): Promise<POI[]> {
  const { data } = await api.get<POI[]>('/pois', { params: { scope, verified_only: verifiedOnly } })
  return data
}

export async function getPOI(id: string): Promise<POIDetail> {
  const { data } = await api.get<POIDetail>(`/pois/${encodeURIComponent(id)}?scope=citywide`)
  return data
}

export type PlanPayload = {
  planning_style?: string
  excluded_experience_ids?: string[]
  preferred_slot_ids?: string[]
  require_verified?: boolean
  routing_mode?: 'configured' | 'demo'
  start_at: string
  end_at: string
  group_size: number
  budget_vnd: number
  transport_mode: string
  intent_weights: Record<string, number>
  locked_experience_ids: string[]
  locked_poi_ids?: string[]
  origin_latitude?: number
  origin_longitude?: number
  origin_label?: string
  destination_latitude?: number
  destination_longitude?: number
  destination_label?: string
}

export type ItinerarySuggestion = { style: string; relaxed_experience_names?: string[]; relaxed_poi_names?: string[]; recommendation_reason?: string | null; request: PlanPayload; preview: Itinerary }
export type ItinerarySuggestions = { options: ItinerarySuggestion[]; requested_count: number; returned_count: number; ranking_source?: 'gemini' | 'heuristic' }

export async function getItinerarySuggestions(payload: PlanPayload): Promise<ItinerarySuggestions> {
  const { data } = await api.post<ItinerarySuggestions>('/itineraries/suggestions', payload, { timeout: 180000 })
  return data
}

export async function createItinerary(payload: PlanPayload): Promise<Itinerary> {
  const { data } = await api.post<Itinerary>('/itineraries/plan', payload, { timeout: 120000 })
  return data
}

export async function getItinerary(id: string): Promise<Itinerary> {
  const { data } = await api.get<Itinerary>(`/itineraries/${id}`)
  return data
}
/** The server states password-policy failures in English; show them in the visitor's language. */
const PASSWORD_REASONS: Array<[RegExp, string]> = [
  [/at least \d+ characters/, 'password.reason.short'],
  [/at most \d+ characters/, 'password.reason.long'],
  [/commonly used/, 'password.reason.common'],
  [/too repetitive/, 'password.reason.repetitive'],
  [/email name/, 'password.reason.email'],
]
/** Error codes whose text is translated on the client (the server's messages are English). */
const ERROR_CODES = new Set(['TOKEN_INVALID', 'INVALID_CREDENTIALS', 'EMAIL_IN_USE', 'EMAIL_RESERVED', 'VERIFICATION_RECENTLY_SENT', 'SESSION_NOT_FOUND', 'AUTH_REQUIRED', 'INVALID_SESSION', 'ACCOUNT_DISABLED', 'LOGIN_THROTTLED', 'MFA_CODE_INVALID', 'MFA_LOCKED', 'MFA_NOT_CONFIGURED', 'MFA_REQUIRED_FOR_ROLE', 'MFA_ALREADY_ENABLED', 'MFA_NOT_ENABLED', 'MFA_SETUP_REQUIRED', 'ADMIN_RESET_FORBIDDEN'])
function weakPasswordMessage(serverMessage: string): string {
  const reasons = PASSWORD_REASONS.filter(([pattern]) => pattern.test(serverMessage)).map(([, key]) => t(key))
  return reasons.length ? `${t('password.weak')}: ${reasons.join('; ')}.` : t('password.weak')
}

export function apiErrorMessage(error: unknown, locale: 'vi' | 'en' = 'vi'): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { error?: { message?: string; code?: string; diagnostics?: {
      reason_codes?: string[]
      counts?: Record<string, number>
    } }; detail?: string | {
      code?: string
      message?: string
      diagnostics?: { reason_codes?: string[]; counts?: Record<string, number> }
    } } } }).response
    const detail = response?.data?.detail
    const detailCode = (error as { response?: { data?: { detail?: { code?: string } } } }).response?.data?.detail?.code
    const code = response?.data?.error?.code ?? detailCode
    if (code === 'WEAK_PASSWORD') return weakPasswordMessage(response?.data?.error?.message ?? '')
    if (code && ERROR_CODES.has(code)) return t(`error.${code}`)
    const diagnostics = response?.data?.error?.diagnostics
      ?? (typeof detail === 'object' && detail !== null ? detail.diagnostics : undefined)
    const reasonLabels: Record<string, string> = locale === 'en' ? {
      NO_ELIGIBLE_EXPERIENCES: 'No eligible experiences are available in the active pilot area.',
      NO_SLOTS_ON_DATE: 'No activities have bookable time slots on that date.',
      NO_SLOTS_IN_TIME_WINDOW: 'Activities have slots on that date, but none fit entirely inside the selected time window.',
      VERIFIED_CATALOG_EMPTY: 'No verified pilot experiences are available. Add source evidence or explicitly enable demo mode.',
      TRIP_TIME_INVALID: 'The trip must start in the future and end after it starts.',
      NO_BOOKABLE_SLOTS: 'The listed slots are cancelled, full, or do not have enough capacity for your group.',
      SLOTS_UNAVAILABLE: 'Some matching slots are full, cancelled, or unavailable.',
      BUDGET_TOO_LOW: 'The matching activities exceed the remaining trip budget.',
      GROUP_TOO_LARGE_FOR_CAPACITY: 'The available capacity is smaller than your group size.',
      AVAILABILITY_NEEDS_CONFIRMATION: 'Some slot availability needs provider confirmation.',
      ROUTE_UNAVAILABLE: 'No route could be found for one or more travel legs.',
      NOT_ENOUGH_TIME_TO_REACH_STOP: 'Travel time would make you arrive after an activity starts.',
      RETURN_DEADLINE_TOO_EARLY: 'The return trip would finish after your deadline.',
      PINNED_STOP_NOT_FEASIBLE: 'A pinned place cannot fit the time, route, capacity, or budget constraints.',
      PINNED_STOP_NOT_AVAILABLE: 'A pinned place is outside the active pilot catalog or has no eligible experience.',
    } : {
      NO_ELIGIBLE_EXPERIENCES: 'Không có trải nghiệm đủ điều kiện trong khu vực thử nghiệm hiện tại.',
      NO_SLOTS_ON_DATE: 'Ngày đã chọn không có ca trải nghiệm phù hợp.',
      NO_SLOTS_IN_TIME_WINDOW: 'Ngày đó có ca, nhưng không ca nào nằm trọn trong khung giờ bạn chọn.',
      VERIFIED_CATALOG_EMPTY: 'Pilot chưa có trải nghiệm đủ nguồn xác minh. Cần bổ sung nguồn, hoặc bật chế độ mô phỏng để thử luồng.',
      TRIP_TIME_INVALID: 'Giờ bắt đầu phải ở tương lai và giờ kết thúc phải sau giờ bắt đầu.',
      NO_BOOKABLE_SLOTS: 'Các ca hiện có đã hết/hủy, không nhận khách hoặc không đủ chỗ cho nhóm.',
      SLOTS_UNAVAILABLE: 'Một số ca phù hợp đã hết chỗ, bị hủy hoặc không nhận khách.',
      BUDGET_TOO_LOW: 'Chi phí các hoạt động phù hợp vượt ngân sách còn lại.',
      GROUP_TOO_LARGE_FOR_CAPACITY: 'Số chỗ còn lại ít hơn số người trong nhóm.',
      AVAILABILITY_NEEDS_CONFIRMATION: 'Một số ca cần cơ sở xác nhận lại tình trạng nhận khách.',
      ROUTE_UNAVAILABLE: 'Không tìm được đường đi cho một hoặc nhiều chặng.',
      NOT_ENOUGH_TIME_TO_REACH_STOP: 'Thời gian di chuyển khiến bạn đến sau giờ bắt đầu hoạt động.',
      RETURN_DEADLINE_TOO_EARLY: 'Chặng về khiến bạn không kịp đến điểm về trước hạn.',
      PINNED_STOP_NOT_FEASIBLE: 'Địa điểm đã ghim không thể xếp vào lịch với thời gian, đường đi, chỗ hoặc ngân sách hiện tại.',
      PINNED_STOP_NOT_AVAILABLE: 'Địa điểm đã ghim nằm ngoài danh mục thử nghiệm hiện tại hoặc chưa có trải nghiệm phù hợp.',
    }
    const reasonText = diagnostics?.reason_codes
      ?.filter((reason) => reason !== code)
      ?.map((reason) => reasonLabels[reason])
      .filter((reason): reason is string => Boolean(reason))
    const counts = diagnostics?.counts
    const checkedSummary = counts
      ? locale === 'en'
        ? ` Checked ${counts.experiences_checked ?? 0} experiences; ${counts.slots_in_requested_window ?? 0} slots fit fully inside your time window.`
        : ` Đã rà soát ${counts.experiences_checked ?? 0} trải nghiệm; ${counts.slots_in_requested_window ?? 0} ca nằm trọn trong khung giờ đã chọn.`
      : ''
    const diagnosticText = reasonText?.length
      ? `${locale === 'en' ? 'Reason:' : 'Lý do:'} ${[...new Set(reasonText)].join(' ')}${checkedSummary}`
      : ''
    if (code === 'NO_BOOKABLE_SLOTS') {
      const message = locale === 'en'
        ? 'There are no currently bookable slots on the selected date. Choose another date or ask the provider to update availability.'
        : 'Ngày đã chọn hiện không có ca đủ điều kiện nhận khách (có thể đã hủy, hết chỗ hoặc chưa được xác nhận mới). Hãy chọn ngày khác hoặc nhờ cơ sở cập nhật ca.'
      return diagnosticText ? `${message} ${diagnosticText}` : message
    }
    if (code === 'TRIP_TIME_INVALID') {
      return locale === 'en'
        ? 'The trip must start in the future and end after it starts.'
        : 'Giờ bắt đầu phải ở tương lai và giờ kết thúc phải sau giờ bắt đầu.'
    }
    if (code === 'PINNED_STOP_NOT_AVAILABLE') {
      const message = locale === 'en'
        ? 'A pinned place is outside the active pilot catalog or has no eligible experience.'
        : 'Địa điểm đã ghim nằm ngoài danh mục thử nghiệm hiện tại hoặc chưa có trải nghiệm phù hợp.'
      return diagnosticText ? `${message} ${diagnosticText}` : message
    }
    if (code === 'NO_FEASIBLE_PLAN') {
      const message = locale === 'en'
        ? 'No itinerary fits the selected time, return route, budget, and availability. Try a wider time window, another date, or a higher budget.'
        : 'Chưa tìm được lịch phù hợp với khung giờ, chặng về, ngân sách và tình trạng chỗ. Hãy thử ngày khác, nới khung giờ hoặc điều chỉnh ngân sách.'
      return diagnosticText ? `${message} ${diagnosticText}` : message
    }
    return response?.data?.error?.message ?? (typeof detail === 'string' ? detail : detail?.message) ?? 'Đang hiển thị chế độ mô phỏng trực tuyến.'
  }
  if (error instanceof Error && error.message) return error.message
  return 'Đang hiển thị chế độ mô phỏng trực tuyến.'
}

