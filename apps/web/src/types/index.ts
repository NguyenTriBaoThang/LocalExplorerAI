export type DataMode = 'real' | 'simulated' | 'replay' | 'mixed'

export interface ChatConstraints {
  group_size: number | null
  start_time: string | null
  return_deadline: string | null
  budget_vnd: number | null
  travel_mode: 'motorcycle' | 'walking' | 'car' | 'transit'
  intent_weights: Record<string, number>
  locked_pois: string[]
  is_complete: boolean
  missing_fields: string[]
  clarification_question_vi: string | null
}

export interface ChatReply {
  status: 'parsed' | 'fallback'
  assistant_mode: 'openai_compatible' | 'local_fallback'
  conversation_id: string | null
  prompt_version: string | null
  fallback_version: string | null
  fallback_reason: 'llm_not_configured' | 'llm_unavailable' | 'invalid_model_output' | null
  reply: string
  structured_constraints: ChatConstraints
}

export interface ChatServiceStatus {
  assistant_mode: 'openai_compatible' | 'gemini_compatible' | 'local_fallback' | 'unavailable'
  llm_configured: boolean
  fallback_available: boolean
  fallback_version: string | null
}

export interface GoogleOAuthStatus {
  enabled: boolean
  redirect_uri: string
  configuration_message: string | null
}

export interface AuthUser {
  id: string
  email: string
  display_name: string
  role: 'traveler' | 'provider' | 'admin'
  provider_id: string | null
  phone: string | null
  is_active: boolean
  email_verified_at?: string | null
  mfa_enabled?: boolean
  created_at: string
}

export interface MfaChallenge {
  mfa_required: true
  mfa_ticket: string
  expires_in: number
}

export interface MfaStatus {
  enabled: boolean
  required: boolean
  setup_pending: boolean
  recovery_codes_remaining: number
}

export interface MfaSetup {
  secret: string
  otpauth_uri: string
  qr: string
}

export interface SessionInfo {
  id: string
  created_at: string
  last_used_at: string | null
  expires_at: string
  absolute_expires_at: string
  ip: string | null
  user_agent: string | null
  amr: string[]
  current: boolean
}

export interface POI {
  id: string
  name: string
  description: string
  latitude: number
  longitude: number
  category: string
  address: string
  verification_status: string
  source_evidence?: SourceEvidence[]
  district?: string | null
  image_urls?: string[]
  opening_hours?: string | null
  ticket_info?: string | null
  tags?: string[]
  is_landmark?: boolean
  data_mode?: DataMode
  data_status?: 'verified' | 'stale' | 'simulated' | 'unverified'
}

export interface SourceEvidence {
  id: string
  source_uri: string
  source_type: string
  source_label?: string | null
  license?: string | null
  fields_covered: string[]
  observed_at?: string | null
  expires_at?: string | null
  verification_status: string
  target_type?: string | null
}

export interface Slot {
  id: string
  start_at: string
  end_at: string
  capacity_total: number | null
  available_reported: number | null
  status: string
  version: number
  confirmed_at?: string | null
  expires_at?: string | null
  source_evidence?: SourceEvidence[]
  data_mode?: DataMode
}

export interface Experience {
  id: string
  poi_id: string
  provider_id: string
  name: string
  description: string
  intent_tags: string[]
  duration_min: number
  indoor: boolean
  price_basis: string
  price_vnd: number
  verification_status: string
  poi: POI
  slots: Slot[]
  source_evidence?: SourceEvidence[]
  data_mode?: DataMode
  rating_average?: number | null
  rating_count?: number
  provider_name?: string | null
  provider_slug?: string | null
}

export interface PartnerSummary {
  id: string
  name: string
  slug: string
  description: string
  address: string
  website: string | null
  cover_url: string | null
  categories: string[]
  experience_count: number
  min_price_vnd: number | null
  rating_average: number | null
  rating_count: number
}

export interface RouteLeg {
  from_experience_id: string | null
  to_experience_id: string | null
  from_label?: string | null
  to_label?: string | null
  distance_m: number
  duration_min: number
  provider: string
  is_realtime: boolean
  eta_source?: string
  eta_source_uri?: string | null
  eta_calculated_at?: string | null
  eta_age_seconds?: number | null
  eta_valid_until?: string | null
  geometry?: [number, number][] | null
}

export interface GeocodeCandidate {
  formatted_address: string
  latitude: number
  longitude: number
  place_id: string | null
}

export interface GeocodeResponse {
  query: string
  provider: string
  source_uri: string
  resolved_at: string
  valid_until: string
  age_seconds: number
  results: GeocodeCandidate[]
}

export interface RoutingCapabilities {
  provider: string
  configured: boolean
  supported_modes: string[]
  eta_is_realtime: boolean
  geocoding_provider?: string
  geocoding_configured?: boolean
}

export interface ItineraryStop {
  id: string
  experience_id: string
  slot_id: string
  position: number
  name: string
  category: string
  arrival_at: string
  start_at: string
  end_at: string
  duration_min: number
  cost_vnd: number
  locked: boolean
  availability_status: string
  availability_known: boolean
  data_status: 'verified' | 'stale' | 'simulated' | 'unverified'
  slot_confirmed_at?: string | null
  slot_expires_at?: string | null
  source_evidence: SourceEvidence[]
  slot_source_evidence: SourceEvidence[]
  poi: POI
}

export interface Itinerary {
  request_id: string
  itinerary_id: string
  data_mode: DataMode
  data_as_of: string
  feasibility_status: string
  estimated_cost_vnd: number
  total_travel_min: number
  group_size?: number
  start_at?: string
  return_deadline?: string
  estimated_return_at?: string
  origin_latitude?: number | null
  origin_longitude?: number | null
  origin_label?: string | null
  destination_latitude?: number | null
  destination_longitude?: number | null
  destination_label?: string | null
  stops: ItineraryStop[]
  routes: RouteLeg[]
  explanation: {
    preserved_intents: string[]
    lost_intents: string[]
    reason_codes: string[]
    evidence_refs: string[]
    uncertainty: string[]
    ranking_model_version?: string | null
  }
}

export interface Booking {
  id: string
  itinerary_id: string | null
  itinerary_stop_id: string | null
  experience_id: string
  experience_title: string
  slot_id: string
  slot_status?: string
  slot_start_at: string | null
  provider_id: string
  provider_name: string
  quantity: number
  amount_vnd: number
  currency: string
  status: 'pending_provider' | 'awaiting_payment' | 'confirmed' | 'rejected' | 'cancelled' | 'expired' | 'cancellation_requested' | 'refund_pending' | 'refunded'
  payment_status?: 'created' | 'pending' | 'succeeded' | 'failed' | 'refund_pending' | 'refunded' | null
  hold_expires_at: string | null
  provider_confirmed_at: string | null
  confirmed_at: string | null
  cancellation_reason: string | null
  created_at: string
  updated_at: string
}

/* ---------- Content managed in the partner/admin portal ---------- */

export interface SiteBanner {
  id: string
  title: string
  subtitle: string
  image_url: string
  link_url: string
}

export interface ArticleSummary {
  id: string
  title: string
  slug: string
  excerpt: string
  cover_url: string
  category: string
  published_at: string | null
}

export interface Article extends ArticleSummary {
  body: string
}

export interface CollectionPlace {
  id: string
  name: string
  district: string | null
  category: string
  image_url: string | null
  is_landmark: boolean
}

export interface SiteCollection {
  id: string
  title: string
  description: string
  places: CollectionPlace[]
}

export interface HomeContent {
  banners: SiteBanner[]
  collections: SiteCollection[]
  articles: ArticleSummary[]
}

export interface ExperienceReview {
  id: string
  rating: number
  comment: string
  author: string
  reply: string | null
  replied_at: string | null
  created_at: string
}

export interface ReviewSummary {
  count: number
  average: number | null
  items: ExperienceReview[]
}

export interface ReviewableBooking {
  booking_id: string
  experience_id: string
  experience_title: string
  slot_start_at: string
}
