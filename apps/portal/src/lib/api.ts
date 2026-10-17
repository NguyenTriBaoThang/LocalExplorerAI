import axios, { AxiosError } from 'axios'
import type {
  AdminCustomerHistory, AdminDashboard, AdminProvider, AdminProviderDetail, AdminUser, AdminUserDetail, AuthUser, Booking, Experience,
  AdminAnalytics, AdminPlace, Article, AuditLog, Banner, Collection, ExperienceDraft, ModerationQueue, PartnerAnalytics, PlaceDraft, Review, Page, PartnerApplication, Poi, PoiDraft, ProviderProfile, RbacMatrix, Role,
  MfaChallenge, MfaSetup, MfaStatus, ServiceAccount, SessionInfo,
} from './types'

export const http = axios.create({ baseURL: '/api', timeout: 30000, withCredentials: true })

type ApiErrorBody = { error?: { code?: string; message?: string; details?: Array<{ field: string; message: string }> } }

const MESSAGES: Record<string, string> = {
  INVALID_CREDENTIALS: 'Email hoặc mật khẩu không đúng.',
  EMAIL_IN_USE: 'Email này đã được đăng ký.',
  EMAIL_RESERVED: 'Không thể dùng địa chỉ email này.',
  WEAK_PASSWORD: 'Mật khẩu chưa đủ mạnh.',
  SOURCE_REQUIRED: 'Cần đường dẫn nguồn HTTPS để xuất bản địa điểm.',
  REVIEW_NOT_ALLOWED: 'Chỉ đánh giá được sau khi đã tham gia booking đã xác nhận.',
  PROVIDER_NOT_APPROVED: 'Hồ sơ đối tác chưa được duyệt nên chưa thể thực hiện thao tác này.',
  PROVIDER_PROFILE_REQUIRED: 'Tài khoản chưa gắn với hồ sơ đối tác đang hoạt động.',
  REASON_REQUIRED: 'Vui lòng nhập lý do để gửi cho đối tác.',
  INVALID_PROVIDER_TRANSITION: 'Không thể chuyển trạng thái này từ trạng thái hiện tại.',
  SELF_LOCKOUT: 'Bạn không thể tự khóa hoặc hạ quyền tài khoản của chính mình.',
  ALREADY_STAFF: 'Tài khoản này đã là đối tác hoặc quản trị viên.',
  SLOT_VERSION_CHANGED: 'Slot vừa được cập nhật ở nơi khác. Hãy tải lại rồi thử lại.',
  TOKEN_INVALID: 'Liên kết không hợp lệ, đã hết hạn hoặc đã được dùng.',
  MFA_REQUIRED: 'Quản trị viên cần bật xác thực hai lớp trước khi tiếp tục.',
  MFA_CODE_INVALID: 'Mã xác thực không đúng.',
  MFA_LOCKED: 'Nhập sai mã quá nhiều lần. Vui lòng thử lại sau 15 phút.',
  MFA_NOT_CONFIGURED: 'Máy chủ chưa cấu hình xác thực hai lớp (INTEGRATION_SECRETS_KEY).',
  MFA_REQUIRED_FOR_ROLE: 'Quản trị viên bắt buộc giữ xác thực hai lớp.',
  LOGIN_THROTTLED: 'Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau ít phút.',
  RATE_LIMITED: 'Bạn thao tác quá nhanh, vui lòng thử lại sau ít phút.',
}

export function errorMessage(error: unknown, fallback = 'Đã có lỗi xảy ra. Vui lòng thử lại.'): string {
  if (error instanceof AxiosError) {
    const body = error.response?.data as ApiErrorBody | undefined
    const code = body?.error?.code
    if (code === 'VALIDATION_ERROR' && body?.error?.details?.length) {
      const first = body.error.details[0]
      return `Dữ liệu chưa hợp lệ (${first.field.replace(/^body\./, '')}): ${first.message}`
    }
    if (code && MESSAGES[code]) return MESSAGES[code]
    if (body?.error?.message) return body.error.message
    const detail = (body as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    if (error.code === 'ECONNABORTED') return 'Máy chủ mất quá nhiều thời gian phản hồi. Vui lòng thử lại.'
    if ([502, 503, 504].includes(error.response?.status ?? 0)) return 'Dịch vụ tạm thời không phản hồi. Vui lòng thử lại sau.'
    if (!error.response) return 'Không kết nối được máy chủ.'
  }
  return fallback
}

export function errorCode(error: unknown): string | undefined {
  return error instanceof AxiosError ? (error.response?.data as ApiErrorBody | undefined)?.error?.code : undefined
}

function paged<T>(data: T[], headers: Record<string, unknown>): Page<T> {
  return { items: data, total: Number(headers['x-total-count'] ?? data.length) }
}

export const authApi = {
  me: async () => (await http.get<AuthUser>('/auth/me')).data,
  /** The user, or a challenge when the account has two-factor authentication (finish with `loginMfa`). */
  login: async (email: string, password: string) => (await http.post<AuthUser | MfaChallenge>('/auth/login', { email, password })).data,
  loginMfa: async (mfa_ticket: string, code: string) => (await http.post<AuthUser>('/auth/login/mfa', { mfa_ticket, code })).data,
  mfaStatus: async () => (await http.get<MfaStatus>('/auth/mfa')).data,
  mfaSetup: async () => (await http.post<MfaSetup>('/auth/mfa/setup')).data,
  mfaEnable: async (code: string) => (await http.post<{ recovery_codes: string[] }>('/auth/mfa/enable', { code })).data.recovery_codes,
  mfaRegenerate: async (code: string) => (await http.post<{ recovery_codes: string[] }>('/auth/mfa/recovery-codes', { code })).data.recovery_codes,
  mfaDisable: async (code: string, password: string | null) => { await http.post('/auth/mfa/disable', { code, password }) },
  logout: async () => { await http.post('/auth/logout') },
  registerPartner: async (payload: { email: string; display_name: string; password: string; application: PartnerApplication }) =>
    (await http.post<AuthUser>('/auth/partner/register', payload)).data,
  applyAsPartner: async (application: PartnerApplication) => (await http.post<AuthUser>('/auth/partner/apply', application)).data,
  forgotPassword: async (email: string) => { await http.post('/auth/password/forgot', { email }) },
  resetPassword: async (token: string, new_password: string) => { await http.post('/auth/password/reset', { token, new_password }) },
  verifyEmail: async (token: string) => { await http.post('/auth/email/verify', { token }) },
  resendVerification: async () => { await http.post('/auth/email/verify/resend') },
  updateProfile: async (display_name: string, phone: string | null) => (await http.patch<AuthUser>('/auth/me', { display_name, phone })).data,
  changePassword: async (current_password: string, new_password: string) => { await http.post('/auth/password', { current_password, new_password }) },
  sessions: async () => (await http.get<SessionInfo[]>('/auth/sessions')).data,
  revokeSession: async (id: string) => { await http.delete(`/auth/sessions/${id}`) },
  logoutAll: async () => { await http.post('/auth/logout-all') },
}

export const partnerApi = {
  profile: async () => (await http.get<ProviderProfile>('/provider/me')).data,
  updateApplication: async (application: PartnerApplication) => (await http.put<ProviderProfile>('/provider/me/application', application)).data,
  experiences: async () => (await http.get<Experience[]>('/provider/experiences')).data,
  createExperience: async (draft: ExperienceDraft) => (await http.post<{ id: string }>('/provider/experiences', draft)).data,
  updateExperience: async (id: string, draft: ExperienceDraft) => (await http.patch<{ id: string; evidence_invalidated?: boolean }>(`/provider/experiences/${id}`, draft)).data,
  hideExperience: async (id: string) => (await http.delete(`/provider/experiences/${id}`)).data,
  pois: async () => (await http.get<Poi[]>('/provider/pois')).data,
  createPoi: async (draft: PoiDraft) => (await http.post<{ id: string }>('/provider/pois', draft)).data,
  updatePoi: async (id: string, draft: PoiDraft) => (await http.patch<{ id: string; evidence_invalidated?: boolean }>(`/provider/pois/${id}`, draft)).data,
  audit: async () => (await http.get<AuditLog[]>('/provider/audit')).data,
  analytics: async (days: number) => (await http.get<PartnerAnalytics>('/provider/me/analytics', { params: { days } })).data,
  reviews: async () => (await http.get<Review[]>('/provider/me/reviews')).data,
  replyReview: async (id: string, reply: string) => (await http.post<Review>(`/provider/me/reviews/${id}/reply`, { reply })).data,
  createSlot: async (experienceId: string, payload: { start_at: string; end_at: string; capacity_total: number; available_reported: number; expires_at: string }) =>
    (await http.post(`/provider/experiences/${experienceId}/slots`, payload)).data,
  updateSlot: async (slotId: string, payload: { expected_version: number; status: 'open' | 'full' | 'cancelled'; available_reported?: number | null; capacity_total?: number | null; expires_at?: string | null }) =>
    (await http.patch(`/provider/slots/${slotId}`, payload)).data,
  bookings: async () => (await http.get<Booking[]>('/provider/me/bookings')).data,
  decideBooking: async (id: string, action: 'accept' | 'reject', note = '') =>
    (await http.post<Booking>(`/provider/me/bookings/${id}/decision`, { action, note })).data,
  decideCancellation: async (id: string, action: 'approve' | 'reject', note = '') =>
    (await http.post<Booking>(`/provider/me/bookings/${id}/cancellation-decision`, { action, note })).data,
}

export const adminApi = {
  customerHistory: async (id: string, limit = 40) =>
    (await http.get<AdminCustomerHistory>(`/admin/users/${encodeURIComponent(id)}/history`, { params: { limit } })).data,
  dashboard: async () => (await http.get<AdminDashboard>('/admin/dashboard')).data,
  users: async (params: { q?: string; role?: Role | ''; active?: boolean | ''; limit: number; offset: number }) => {
    const clean = Object.fromEntries(Object.entries(params).filter(([, value]) => value !== '' && value !== undefined))
    const response = await http.get<AdminUser[]>('/admin/users', { params: clean })
    return paged(response.data, response.headers)
  },
  user: async (id: string) => (await http.get<AdminUserDetail>(`/admin/users/${id}`)).data,
  updateUser: async (id: string, payload: { role: Role; is_active: boolean; provider_id?: string | null }) =>
    (await http.patch(`/admin/users/${id}`, payload)).data,
  revokeSessions: async (id: string) => { await http.post(`/admin/users/${id}/revoke-sessions`) },
  providerCounts: async () => (await http.get<Record<'pending' | 'verified' | 'rejected' | 'suspended' | 'all', number>>('/admin/providers/counts')).data,
  providers: async (params: { q?: string; status?: string; limit: number; offset: number }) => {
    const clean = Object.fromEntries(Object.entries(params).filter(([, value]) => value !== '' && value !== undefined))
    const response = await http.get<AdminProvider[]>('/admin/providers', { params: clean })
    return paged(response.data, response.headers)
  },
  provider: async (id: string) => (await http.get<AdminProviderDetail>(`/admin/providers/${id}`)).data,
  decideProvider: async (id: string, action: 'approve' | 'reject' | 'suspend' | 'reactivate', note: string) =>
    (await http.post<AdminProvider>(`/admin/providers/${id}/decision`, { action, note })).data,
  analytics: async (days: number) => (await http.get<AdminAnalytics>('/admin/analytics', { params: { days } })).data,
  places: async () => (await http.get<AdminPlace[]>('/admin/places', { params: { limit: 500 } })).data,
  place: async (id: string) => (await http.get<AdminPlace>(`/admin/places/${id}`)).data,
  createPlace: async (draft: PlaceDraft, publish = false) => (await http.post<AdminPlace>('/admin/places', draft, { params: { publish } })).data,
  updatePlace: async (id: string, draft: PlaceDraft) => (await http.patch<AdminPlace>(`/admin/places/${id}`, draft)).data,
  setPlaceStatus: async (id: string, action: 'publish' | 'hide' | 'draft', source_url?: string | null) =>
    (await http.post<AdminPlace>(`/admin/places/${id}/status`, { action, source_url: source_url || null })).data,
  banners: async () => (await http.get<Banner[]>('/admin/content/banners')).data,
  saveBanner: async ({ id, updated_at: _ignored, ...payload }: Banner) =>
    (id ? await http.put<Banner>(`/admin/content/banners/${id}`, payload) : await http.post<Banner>('/admin/content/banners', payload)).data,
  deleteBanner: async (id: string) => { await http.delete(`/admin/content/banners/${id}`) },
  articles: async () => (await http.get<Article[]>('/admin/content/articles')).data,
  article: async (id: string) => (await http.get<Article>(`/admin/content/articles/${id}`)).data,
  saveArticle: async (article: Article) => {
    const payload = { title: article.title, slug: article.slug, excerpt: article.excerpt, body: article.body ?? '', cover_url: article.cover_url, category: article.category, status: article.status }
    return (article.id ? await http.put<Article>(`/admin/content/articles/${article.id}`, payload) : await http.post<Article>('/admin/content/articles', payload)).data
  },
  deleteArticle: async (id: string) => { await http.delete(`/admin/content/articles/${id}`) },
  collections: async () => (await http.get<Collection[]>('/admin/content/collections')).data,
  saveCollection: async ({ id, ...payload }: Collection) =>
    (id ? await http.put<Collection>(`/admin/content/collections/${id}`, payload) : await http.post<Collection>('/admin/content/collections', payload)).data,
  deleteCollection: async (id: string) => { await http.delete(`/admin/content/collections/${id}`) },
  rbac: async () => (await http.get<RbacMatrix>('/admin/rbac')).data,
  setRolePermissions: async (role: string, permissions: string[]) =>
    (await http.put<{ role: string; added: string[]; removed: string[] }>(`/admin/rbac/roles/${role}/permissions`, { permissions })).data,
  serviceAccounts: async () => (await http.get<ServiceAccount[]>('/admin/service-accounts')).data,
  createServiceAccount: async (name: string, permissions: string[]) =>
    (await http.post<ServiceAccount & { key: string }>('/admin/service-accounts', { name, permissions })).data,
  revokeServiceAccount: async (id: string) => { await http.delete(`/admin/service-accounts/${id}`) },
  audit: async (limit = 200) => (await http.get<AuditLog[]>('/admin/audit', { params: { limit } })).data,
  moderation: async (status: string) => (await http.get<ModerationQueue>('/admin/moderation', { params: { status } })).data,
  moderate: async (type: 'poi' | 'experience' | 'evidence', id: string, action: 'approve' | 'reject' | 'hide', note = '') =>
    (await http.patch(`/admin/moderation/${type}/${id}`, { action, note })).data,
  createProvider: async (payload: { name: string; email: string; password: string; contact_phone?: string; address?: string }) =>
    (await http.post('/admin/providers', payload)).data,
}
