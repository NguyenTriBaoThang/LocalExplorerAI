export type Role = 'traveler' | 'provider' | 'admin'

export type AuthUser = {
  id: string
  email: string
  display_name: string
  role: Role
  provider_id: string | null
  phone: string | null
  is_active: boolean
  email_verified_at: string | null
  mfa_enabled: boolean
  created_at: string
}

export type ProviderStatus = 'pending' | 'verified' | 'rejected' | 'suspended' | 'mock' | 'simulated'
export type BusinessType = 'household' | 'company' | 'cooperative' | 'individual' | 'other'

export type PartnerApplication = {
  business_name: string
  business_type: BusinessType
  description: string
  contact_phone: string
  address: string
  tax_code: string | null
  business_license_no: string | null
  website: string | null
  document_urls: string[]
  application_note: string
}

export type ProviderProfile = {
  id: string
  name: string
  slug: string
  description: string
  contact_phone: string | null
  contact_email: string | null
  address: string
  verification_status: ProviderStatus
  is_active: boolean
  can_publish: boolean
  business_type: BusinessType | null
  tax_code: string | null
  business_license_no: string | null
  website: string | null
  document_urls: string[]
  application_note: string
  applied_at: string | null
  review_note: string
  reviewed_at: string | null
}

export type Slot = {
  id: string
  start_at: string
  end_at: string
  capacity_total: number | null
  available_reported: number | null
  confirmed_at: string | null
  expires_at: string | null
  status: string
  version: number
}

export type Intent = 'thủ_công' | 'ẩm_thực' | 'văn_hóa' | 'thư_giãn'

export type Experience = {
  id: string
  poi_id: string
  poi_name: string
  title: string
  description: string
  primary_intent: Intent | null
  intent_tags: string[]
  is_hands_on: boolean
  is_indoor: boolean
  duration_min: number
  price_vnd: number
  price_basis: 'per_person' | 'per_group'
  verification_status: string
  slots: Slot[]
}

export type ExperienceDraft = Omit<Experience, 'id' | 'poi_name' | 'verification_status' | 'slots' | 'primary_intent'> & { primary_intent: Intent }

export type Poi = {
  id: string
  name: string
  description: string
  district: string | null
  latitude: number
  longitude: number
  category: string
  address: string
  verification_status: string
}

export type PoiDraft = Omit<Poi, 'id' | 'verification_status'>

export type Booking = {
  id: string
  experience_id: string
  experience_title: string
  slot_id: string
  slot_status: string
  slot_start_at: string | null
  quantity: number
  amount_vnd: number
  currency: string
  status: string
  payment_status: string | null
  hold_expires_at: string | null
  cancellation_reason: string | null
  created_at: string
}

export type AdminUser = {
  id: string
  email: string
  display_name: string
  role: Role
  provider_id: string | null
  provider_name: string | null
  phone: string | null
  is_active: boolean
  email_verified_at: string | null
  mfa_enabled: boolean
  created_at: string
}

export type AuditEntry = {
  action: string
  target_type: string
  target_id: string
  actor_id: string | null
  details: Record<string, unknown>
  created_at: string
}

export type AdminUserDetail = AdminUser & { active_sessions: number; audit: AuditEntry[] }

export type AdminProvider = {
  id: string
  name: string
  slug: string
  verification_status: ProviderStatus
  is_active: boolean
  business_type: BusinessType | null
  contact_email: string | null
  contact_phone: string | null
  address: string
  applied_at: string | null
  reviewed_at: string | null
  created_at: string
  user_count: number
  experience_count: number
}

export type AdminProviderDetail = ProviderProfile & {
  created_at: string
  reviewed_by: string | null
  users: AdminUser[]
  experiences: Array<{
    id: string
    title: string
    verification_status: string
    price_vnd: number
    duration_min: number
    slot_count: number
    open_slot_count: number
  }>
}

export type AdminDashboard = {
  users: number
  providers: number
  pending_partner_applications: number
  pending_experiences: number
  pending_pois: number
  pending_evidence: number
  unknown_slot_capacity: number
  [key: string]: number
}

export type Page<T> = { items: T[]; total: number }

export type RbacMatrix = {
  roles: Array<{ name: string; description: string; is_system: boolean; permissions: string[] }>
  permissions: Array<{ name: string; description: string }>
}

export type ServiceAccount = {
  id: string
  name: string
  key_id: string
  permissions: string[]
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
}

export type AuditLog = {
  id: string
  actor_id?: string | null
  actor_name?: string | null
  actor_email?: string | null
  action: string
  target_type: string
  target_id: string
  details: Record<string, unknown>
  created_at: string
}

export type ModerationQueue = {
  pois: Array<{ id: string; name: string; address: string; status: string }>
  experiences: Array<{ id: string; title: string; provider_id: string; status: string }>
  evidence: Array<{ id: string; source_uri: string; source_type: string; source_label: string | null; target_type: string | null; target_id: string | null; fields_covered: string[]; expires_at: string | null; status: string }>
}

export type SessionInfo = {
  id: string
  created_at: string
  last_used_at: string | null
  expires_at: string
  ip: string | null
  user_agent: string | null
  current: boolean
}

/* ---------- Portal platform (places, content, analytics, reviews) ---------- */

export type PlaceStatus = 'verified' | 'pending' | 'draft' | 'hidden' | 'rejected' | 'simulated'

export type PlaceDraft = {
  name: string
  category: string
  district: string | null
  address: string
  latitude: number
  longitude: number
  description: string
  image_urls: string[]
  opening_hours: string | null
  ticket_info: string | null
  tags: string[]
  is_landmark: boolean
  source_url: string | null
}

export type AdminPlace = PlaceDraft & {
  id: string
  status: PlaceStatus
  submitted_by_provider_id: string | null
  data_revision: number
  experience_count: number
  views_30d: number
  updated_at: string
}

export type Banner = {
  id: string
  title: string
  subtitle: string
  image_url: string
  link_url: string
  is_active: boolean
  sort_order: number
  starts_at: string | null
  ends_at: string | null
  updated_at?: string
}

export type Article = {
  id: string
  title: string
  slug: string
  excerpt: string
  body?: string
  cover_url: string
  category: string
  status: 'draft' | 'published'
  published_at: string | null
  updated_at: string
}

export type Collection = {
  id: string
  title: string
  description: string
  place_ids: string[]
  is_active: boolean
  sort_order: number
}

export type TrafficPoint = { date: string; label: string; visitors: number; pageviews: number; new_users: number; logins: number; bookings: number }

export type AdminAnalytics = {
  days: number
  totals: { visitors: number; pageviews: number; new_users: number; bookings: number; avg_session_seconds: number; sessions: number }
  change: { visitors: number | null; pageviews: number | null; new_users: number | null; bookings: number | null }
  series: TrafficPoint[]
  top_pages: Array<{ path: string; title: string; views: number }>
  top_places: Array<{ id: string; name: string; district: string; views: number }>
  devices: Array<{ label: string; value: number }>
  sources: Array<{ label: string; value: number }>
  hours: number[]
}

export type PartnerAnalytics = {
  series: Array<{ label: string; views: number; booking_requests: number }>
  totals: { views: number; booking_requests: number; conversion: number; rating: number | null; reviews: number }
}

export type Review = {
  id: string
  experience_id: string
  experience_title: string | null
  rating: number
  comment: string
  author: string
  reply: string | null
  replied_at: string | null
  status: 'published' | 'hidden'
  created_at: string
}

export type MfaChallenge = { mfa_required: true; mfa_ticket: string; expires_in: number }
export type MfaStatus = { enabled: boolean; required: boolean; setup_pending: boolean; recovery_codes_remaining: number }
export type MfaSetup = { secret: string; otpauth_uri: string; qr: string }
