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
}

export const adminApi = {
  dashboard: async () => (await api.get('/admin/dashboard')).data,
  users: async () => (await api.get('/admin/users')).data,
  providers: async () => (await api.get('/admin/providers')).data,
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
}

// Rich simulated Saigon demo data
const DEMO_POIS: POI[] = [
  {
    id: 'poi-1',
    name: 'Góc thủ công giấy Dó Sài Gòn',
    description: 'Không gian trải nghiệm làm sổ tay giấy dó truyền thống và vẽ thư họa.',
    latitude: 10.7752,
    longitude: 106.7018,
    category: 'handicraft',
    address: 'Đường Nguyễn Du, Bến Nghé, Quận 1, TP. Hồ Chí Minh',
    verification_status: 'simulated',
    data_mode: 'simulated',
  },
  {
    id: 'poi-2',
    name: 'Xưởng Gốm Thủ Công Sài Gòn Art',
    description: 'Bàn xoay gốm thủ công kết hợp men màu bản địa Nam Bộ.',
    latitude: 10.7791,
    longitude: 106.6957,
    category: 'handicraft',
    address: 'Đường Pasteur, Phường 6, Quận 3, TP. Hồ Chí Minh',
    verification_status: 'simulated',
    data_mode: 'simulated',
  },
  {
    id: 'poi-3',
    name: 'Bếp Cơm Niêu & Bánh Nam Bộ',
    description: 'Học chế biến và thưởng thức các món bánh dân gian Nam Bộ nóng hổi.',
    latitude: 10.7715,
    longitude: 106.6981,
    category: 'food',
    address: 'Đường Nam Kỳ Khởi Nghĩa, Quận 1, TP. Hồ Chí Minh',
    verification_status: 'simulated',
    data_mode: 'simulated',
  },
  {
    id: 'poi-4',
    name: 'Cà Phê Vợt Ba Lù & Chuyện Hẻm Xưa',
    description: 'Trải nghiệm rang xay và pha cà phê bít tất truyền thống trong khu phố người Hoa.',
    latitude: 10.7682,
    longitude: 106.7040,
    category: 'food',
    address: 'Chợ Phùng Hưng, Phường 14, Quận 5, TP. Hồ Chí Minh',
    verification_status: 'simulated',
    data_mode: 'simulated',
  },
  {
    id: 'poi-5',
    name: 'Ký Ức Đô Thị & Triển Lãm Ảnh Phố',
    description: 'Khám phá kiến trúc cổ điển Sài Gòn qua lăng kính nhiếp ảnh ký sự.',
    latitude: 10.7797,
    longitude: 106.7004,
    category: 'culture',
    address: 'Đường Lý Tự Trọng, Bến Nghé, Quận 1, TP. Hồ Chí Minh',
    verification_status: 'simulated',
    data_mode: 'simulated',
  },
  {
    id: 'poi-6',
    name: 'Bảo Tàng Mỹ Thuật & Không Gian Di Sản',
    description: 'Chiêm ngưỡng kiến trúc Art Deco kết hợp hoa văn Á Đông đặc sắc.',
    latitude: 10.7733,
    longitude: 106.6918,
    category: 'culture',
    address: '97A Phó Đức Chính, Phường Nguyễn Thái Bình, Quận 1',
    verification_status: 'simulated',
    data_mode: 'simulated',
  },
  {
    id: 'poi-7',
    name: 'Vườn Xanh Thảo Cầm Viên & Cổ Thụ',
    description: 'Đi bộ quan sát hệ sinh thái thực vật cổ thụ hơn 100 năm tuổi giữa lòng thành phố.',
    latitude: 10.7820,
    longitude: 106.7060,
    category: 'nature',
    address: 'Số 2 Nguyễn Bỉnh Khiêm, Bến Nghé, Quận 1',
    verification_status: 'simulated',
    data_mode: 'simulated',
  },
  {
    id: 'poi-8',
    name: 'Thuyền Hoàng Hôn Sông Sài Gòn',
    description: 'Ngắm nhìn thành phố lên đèn từ mặt nước sông Sài Gòn lộng gió.',
    latitude: 10.7676,
    longitude: 106.6962,
    category: 'nature',
    address: 'Bến Bạch Đằng, Tôn Đức Thắng, Quận 1',
    verification_status: 'simulated',
    data_mode: 'simulated',
  },
  {
    id: 'poi-9',
    name: 'Trà Thảo Mộc & Thư Giãn Chuông Xoay',
    description: 'Thưởng trà thảo mộc organic và lắng đọng với liệu pháp âm thanh chuông xoay.',
    latitude: 10.7812,
    longitude: 106.6909,
    category: 'relaxation',
    address: 'Đường Điện Biên Phủ, Phường Đa Kao, Quận 1',
    verification_status: 'simulated',
    data_mode: 'simulated',
  },
  {
    id: 'poi-10',
    name: 'Workshop Nước Hoa Bản Địa Sài Gòn',
    description: 'Tự pha chế mùi hương đặc trưng từ hoa lài, vỏ bưởi và gỗ trầm hương.',
    latitude: 10.7697,
    longitude: 106.7072,
    category: 'handicraft',
    address: 'Đường Nguyễn Thị Minh Khai, Quận 1',
    verification_status: 'simulated',
    data_mode: 'simulated',
  },
]

function generateMockExperiences(): Experience[] {
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date())
  return DEMO_POIS.map((poi, idx) => {
    const duration = [75, 90, 90, 60, 60, 75, 60, 75, 60, 105][idx] || 60
    const price = [120000, 180000, 220000, 160000, 90000, 110000, 80000, 150000, 100000, 250000][idx] || 150000
    const tags = [
      ['handicraft', 'hands_on', 'local_life'],
      ['handicraft', 'hands_on', 'relaxation'],
      ['food', 'hands_on', 'local_life'],
      ['food', 'culture'],
      ['culture', 'local_life'],
      ['culture', 'relaxation'],
      ['nature', 'relaxation'],
      ['nature', 'local_life'],
      ['relaxation', 'food'],
      ['handicraft', 'hands_on', 'culture'],
    ][idx] || ['culture']

    const times = ['09:00', '11:30', '14:30', '16:30']
    const slots = times.map((t, sIdx) => {
      const startAt = `${today}T${t}:00+07:00`
      const startDate = new Date(startAt)
      const endDate = new Date(startDate.getTime() + duration * 60000)
      return {
        id: `slot-${idx + 1}-${sIdx + 1}`,
        start_at: startDate.toISOString(),
        end_at: endDate.toISOString(),
        capacity_total: 10,
        available_reported: sIdx === 1 ? null : 8 - sIdx * 2,
        status: sIdx === 1 ? 'tentative' : 'available',
        version: 1,
        data_mode: 'simulated' as const,
      }
    })

    return {
      id: `exp-${idx + 1}`,
      poi_id: poi.id,
      provider_id: 'provider-1',
      name: poi.name,
      description: poi.description,
      intent_tags: tags,
      duration_min: duration,
      indoor: idx % 2 === 0,
      price_basis: 'per_person',
      price_vnd: price,
      verification_status: 'simulated',
      poi,
      slots,
      data_mode: 'simulated',
    }
  })
}

const mockExperiencesStore = generateMockExperiences()
const mockItineraryStore = new Map<string, Itinerary>()

export async function getExperiences(params?: Record<string, string | number | boolean>): Promise<Experience[]> {
  try {
    const { data } = await api.get<Experience[]>('/experiences', { params })
    return data
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) throw error
    let result = [...mockExperiencesStore]
    if (params?.intent) {
      result = result.filter((e) => e.poi.category === params.intent || e.intent_tags.includes(String(params.intent)))
    }
    if (params?.max_price) {
      result = result.filter((e) => e.price_vnd <= Number(params.max_price))
    }
    if (typeof params?.is_indoor === 'boolean') result = result.filter((e) => e.indoor === params.is_indoor)
    if (params?.query) result = result.filter((e) => `${e.name} ${e.description} ${e.poi.name}`.toLowerCase().includes(String(params.query).toLowerCase()))
    return result
  }
}

export async function getPOIs(): Promise<POI[]> {
  try {
    const { data } = await api.get<POI[]>('/pois')
    return data
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) throw error
    return DEMO_POIS
  }
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
}, options: { allowSimulation?: boolean } = {}): Promise<Itinerary> {
  try {
    const { data } = await api.post<Itinerary>('/itineraries/plan', payload)
    return data
  } catch (error) {
    if ((axios.isAxiosError(error) && error.response) || options.allowSimulation === false) throw error
    // Generate intelligent client-side simulated itinerary
    const selectedIntents = Object.keys(payload.intent_weights)
    let candidates = mockExperiencesStore.filter((exp) => {
      if (selectedIntents.length === 0) return true
      return selectedIntents.includes(exp.poi.category) || exp.intent_tags.some((t) => selectedIntents.includes(t))
    })

    if (candidates.length < 2) {
      candidates = mockExperiencesStore
    }

    const chosen = candidates.slice(0, 3)
    const startDate = new Date(payload.start_at)
    let currentCursor = new Date(startDate)

    const stops = chosen.map((exp, index) => {
      const arrival = new Date(currentCursor)
      const slotStart = new Date(currentCursor)
      const slotEnd = new Date(slotStart.getTime() + exp.duration_min * 60000)
      currentCursor = new Date(slotEnd.getTime() + 25 * 60000) // travel time 25m

      return {
        id: `stop-${index + 1}`,
        experience_id: exp.id,
        slot_id: exp.slots[0]?.id || `slot-${index}`,
        position: index + 1,
        name: exp.name,
        category: exp.poi.category,
        arrival_at: arrival.toISOString(),
        start_at: slotStart.toISOString(),
        end_at: slotEnd.toISOString(),
        duration_min: exp.duration_min,
        cost_vnd: exp.price_vnd,
        locked: false,
        availability_status: index === 1 ? 'tentative' : 'available',
        availability_known: index !== 1,
        data_status: 'simulated' as const,
        slot_confirmed_at: null,
        slot_expires_at: null,
        source_evidence: [],
        slot_source_evidence: [],
        poi: exp.poi,
      }
    })

    const totalCost = stops.reduce((sum, s) => sum + s.cost_vnd, 0) * payload.group_size
    const totalTravel = (stops.length - 1) * 20

    const mockItinerary: Itinerary = {
      request_id: `req-${Date.now()}`,
      itinerary_id: `itin-${Date.now().toString(36)}`,
      data_mode: 'simulated',
      data_as_of: new Date().toISOString(),
      feasibility_status: 'feasible',
      estimated_cost_vnd: totalCost,
      total_travel_min: totalTravel,
      stops,
      routes: stops.slice(1).map((stop, i) => ({
        from_experience_id: stops[i].experience_id,
        to_experience_id: stop.experience_id,
        distance_m: 2400,
        duration_min: 20,
        provider: 'mock_haversine',
        is_realtime: false,
      })),
      explanation: {
        preserved_intents: selectedIntents,
        lost_intents: [],
        reason_codes: ['INTENT_MATCH', 'WITHIN_BUDGET', 'SLOT_AVAILABLE', 'MOCK_ROUTING'],
        evidence_refs: ['simulated_catalog', 'haversine_matrix'],
        uncertainty: ['capacity_unconfirmed_for_stop_2'],
      },
    }

    mockItineraryStore.set(mockItinerary.itinerary_id, mockItinerary)
    return mockItinerary
  }
}

export async function getItinerary(id: string): Promise<Itinerary> {
  try {
    const { data } = await api.get<Itinerary>(`/itineraries/${id}`)
    return data
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) throw error
    const found = mockItineraryStore.get(id)
    if (found) return found
    throw error
  }
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

