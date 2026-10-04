import axios from 'axios'
import type { AuthUser, Booking, ChatReply, ChatServiceStatus, Experience, GeocodeResponse, GoogleOAuthStatus, Itinerary, POI, RoutingCapabilities } from '../types'

export const api = axios.create({ baseURL: '/api', timeout: 30000, withCredentials: true })

export async function login(email: string, password: string): Promise<AuthUser> {
  const { data } = await api.post<AuthUser>('/auth/login', { email, password })
  return data
}

export async function registerAccount(email: string, display_name: string, password: string): Promise<AuthUser> {
  const { data } = await api.post<AuthUser>('/auth/register', { email, display_name, password })
  return data
}

export async function getCurrentUser(): Promise<AuthUser> {
  const { data } = await api.get<AuthUser>('/auth/me')
  return data
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout')
}

export async function sendChatMessage(message: string, conversation_id: string): Promise<ChatReply> {
  const { data } = await api.post<ChatReply>('/chat/message', { message, conversation_id })
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
  share_token: string
  email: string
  password: string
  display_name?: string
}): Promise<AuthUser> {
  const { data } = await api.post<AuthUser>('/auth/claim-ticket', payload)
  return data
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

export const providerApi = {
  profile: async () => (await api.get('/provider/me')).data,
  experiences: async () => (await api.get('/provider/experiences')).data,
  pois: async () => (await api.get<Array<POI & { data_revision: number }>>('/provider/pois')).data,
  createPOI: async (payload: Record<string, unknown>) => (await api.post('/provider/pois', payload)).data,
  updatePOI: async (id: string, payload: Record<string, unknown>) => (await api.patch(`/provider/pois/${id}`, payload)).data,
  createExperience: async (payload: Record<string, unknown>) => (await api.post('/provider/experiences', payload)).data,
  updateExperience: async (id: string, payload: Record<string, unknown>) => (await api.patch(`/provider/experiences/${id}`, payload)).data,
  hideExperience: async (id: string) => (await api.delete(`/provider/experiences/${id}`)).data,
  createSlot: async (id: string, payload: Record<string, unknown>) => (await api.post(`/provider/experiences/${id}/slots`, payload)).data,
  updateSlot: async (id: string, payload: Record<string, unknown>) => (await api.patch(`/provider/slots/${id}`, payload)).data,
  submitEvidence: async (payload: Record<string, unknown>) => (await api.post('/provider/evidence', payload)).data,
  audit: async () => (await api.get('/provider/audit')).data,
  evidence: async () => (await api.get('/provider/evidence')).data,
  bookings: async () => (await api.get<Booking[]>('/provider/me/bookings')).data,
  decideBooking: async (id: string, action: 'accept' | 'reject', note = '') =>
    (await api.post<Booking>(`/provider/me/bookings/${id}/decision`, { action, note })).data,
  decideBookingCancellation: async (id: string, action: 'approve' | 'reject', note = '') =>
    (await api.post<Booking>(`/provider/me/bookings/${id}/cancellation-decision`, { action, note })).data,
  previewSlotAssistant: async (providerId: string, message: string, slotIds: string[]) =>
    (await api.post(`/providers/${providerId}/slot-assistant/preview`, { message, slot_ids: slotIds })).data,
  confirmSlotAssistant: async (providerId: string, confirmationToken: string, expiresAt?: string) =>
    (await api.post(`/providers/${providerId}/slot-assistant/confirm`, {
      confirmation_token: confirmationToken,
      ...(expiresAt ? { expires_at: expiresAt } : {}),
    })).data,
}

export const adminApi = {
  dashboard: async () => (await api.get('/admin/dashboard')).data,
  users: async () => (await api.get('/admin/users')).data,
  providers: async () => (await api.get('/admin/providers')).data,
  placeImports: async () => (await api.get('/admin/place-imports')).data,
  placeImportCandidates: async (batchId: string) => (await api.get(`/admin/place-imports/${batchId}/candidates`)).data,
  promotePlaceCandidate: async (batchId: string, candidateId: string, payload: Record<string, unknown>) =>
    (await api.post(`/admin/place-imports/${batchId}/candidates/${candidateId}/promote`, payload)).data,
  aiTargets: async () => (await api.get('/admin/ai/targets')).data,
  operationsStatus: async () => (await api.get('/ops/status')).data,
  operationsJobs: async () => (await api.get('/ops/jobs')).data,
  operationsEvents: async () => (await api.get('/ops/events')).data,
  operationsNotifications: async () => (await api.get('/ops/notifications')).data,
  promptCatalog: async () => (await api.get('/ai/prompts')).data,
  tagExperience: async (experienceId: string, additional_context: string) =>
    (await api.post(`/experiences/${experienceId}/ai-tag`, { additional_context })).data,
  compareIntent: async (experience_a_id: string, experience_b_id: string) =>
    (await api.post('/ai/intent-similarity', { experience_a_id, experience_b_id })).data,
  labelFeedback: async (itineraryId: string, review_text: string, rating: number | null) =>
    (await api.post(`/itineraries/${itineraryId}/feedback/label`, { review_text, rating })).data,
  weatherAdvisory: async (itineraryId: string, payload: Record<string, unknown>) =>
    (await api.post(`/itineraries/${itineraryId}/weather-advisory`, payload)).data,
  updateUser: async (id: string, payload: Record<string, unknown>) => (await api.patch(`/admin/users/${id}`, payload)).data,
  createProvider: async (payload: Record<string, unknown>) => (await api.post('/admin/providers', payload)).data,
  moderation: async (status = 'pending') => (await api.get('/admin/moderation', { params: { status } })).data,
  review: async (kind: string, id: string, action: string, note = '') => (await api.patch(`/admin/moderation/${kind}/${id}`, { action, note })).data,
  duplicates: async () => (await api.get('/admin/duplicates/pois')).data,
  mergeDuplicate: async (keep_id: string, duplicate_id: string, reason: string) => (await api.post('/admin/duplicates/pois/merge', { keep_id, duplicate_id, reason })).data,
  audit: async () => (await api.get('/admin/audit')).data,
  integrations: async () => (await api.get('/admin/integrations')).data,
  updateIntegration: async (service: string, values: Record<string, string>, remove_keys: string[] = []) =>
    (await api.put('/admin/integrations/' + encodeURIComponent(service), { values, remove_keys })).data,
  testIntegration: async (service: string) =>
    (await api.post<{ service: string; status: string; ok: boolean; message_vi: string }>(`/admin/integrations/${encodeURIComponent(service)}/test`)).data,
}

export const mlApi = {
  status: async () => (await api.get('/ml/status')).data,
  predictFloodRisk: async (samples: Array<Record<string, string | number>>) =>
    (await api.post('/ml/flood-risk', { samples })).data,
}

export async function getExperiences(params?: Record<string, string | number | boolean>): Promise<Experience[]> {
  const { data } = await api.get<Experience[]>('/experiences', { params })
  return data
}

export async function getPOIs(): Promise<POI[]> {
  const { data } = await api.get<POI[]>('/pois')
  return data
}

export async function createItinerary(payload: {
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
}): Promise<Itinerary> {
  const { data } = await api.post<Itinerary>('/itineraries/plan', payload)
  return data
}

export async function getItinerary(id: string): Promise<Itinerary> {
  const { data } = await api.get<Itinerary>(`/itineraries/${id}`)
  return data
}
export function apiErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { error?: { message?: string }; detail?: string | { message?: string } } } }).response
    const detail = response?.data?.detail
    return response?.data?.error?.message ?? (typeof detail === 'string' ? detail : detail?.message) ?? 'Đang hiển thị chế độ mô phỏng trực tuyến.'
  }
  if (error instanceof Error && error.message) return error.message
  return 'Đang hiển thị chế độ mô phỏng trực tuyến.'
}

