import { http } from './api'

export type OperatorOrg = {
  id: string
  name: string
  slug: string
  margin_floor_pct: number
  default_markup_pct: number
  deposit_pct: number
  quote_validity_days: number
  ota_commission_pct: number
  manual_minutes_per_quote: number
  settings: Record<string, unknown>
}

export type OperatorOrgUpdate = Partial<Omit<OperatorOrg, 'id' | 'slug'>>

export const operatorApi = {
  org: async () => (await http.get<OperatorOrg>('/operator/me/org')).data,
  updateOrg: async (patch: OperatorOrgUpdate) => (await http.patch<OperatorOrg>('/operator/me/org', patch)).data,
}

export type RateCategory = 'vehicle' | 'guide' | 'meal' | 'ticket' | 'hotel' | 'surcharge'
export type RateUnit = 'per_km' | 'per_day' | 'per_trip' | 'per_pax' | 'per_room_night' | 'pct'

export type ExtractedLine = {
  category: RateCategory
  label: string
  unit: RateUnit
  seats: number | null
  max_pax: number | null
  amount_vnd: number
  conditions: Record<string, unknown>
  confidence: number
  source_ref: string | null
}

export type OperatorDocument = {
  id: string
  kind: 'rate_sheet' | 'invoice'
  filename: string
  status: 'uploaded' | 'extracted' | 'failed' | 'approved' | 'rejected'
  error: string | null
  extracted: { supplier: string | null; lines: ExtractedLine[] } | null
}

export type RateCardItem = {
  id: string
  code: string
  label: string
  unit: RateUnit
  seats: number | null
  max_pax: number | null
  amount_vnd: number
  conditions: Record<string, unknown>
  confidence: number | null
}

export type RateCard = {
  id: string
  supplier: string
  category: RateCategory
  version: number
  status: 'draft' | 'active' | 'archived'
  valid_from: string | null
  valid_to: string | null
  approved_at: string | null
  item_count: number
  items?: RateCardItem[]
}

export type RateCardDiff = {
  from: RateCard
  to: RateCard
  changed: Array<{ code: string; label: string; old_vnd: number; new_vnd: number; delta_vnd: number; delta_pct: number | null }>
  added: Array<{ code: string; label: string; new_vnd: number }>
  removed: Array<{ code: string; label: string; old_vnd: number }>
  unchanged: number
}

export const rateCardApi = {
  upload: async (filename: string, data_url: string) => (await http.post<OperatorDocument>('/operator/documents', { filename, data_url })).data,
  // Extraction runs inside the request and can take a while on long sheets or images.
  extract: async (id: string) => (await http.post<OperatorDocument>(`/operator/documents/${id}/extract`, null, { timeout: 120000 })).data,
  saveLines: async (id: string, supplier: string | null, lines: ExtractedLine[]) =>
    (await http.patch<OperatorDocument>(`/operator/documents/${id}/lines`, { supplier, lines })).data,
  reject: async (id: string) => (await http.post<OperatorDocument>(`/operator/documents/${id}/reject`)).data,
  cards: async () => (await http.get<RateCard[]>('/operator/rate-cards')).data,
  card: async (id: string) => (await http.get<RateCard>(`/operator/rate-cards/${id}`)).data,
  fromDocument: async (id: string, supplier: string) =>
    (await http.post<{ cards: RateCard[] }>(`/operator/rate-cards/from-document/${id}`, { supplier })).data.cards,
  approve: async (id: string) => (await http.post<RateCard>(`/operator/rate-cards/${id}/approve`)).data,
  diff: async (id: string, otherId: string) => (await http.get<RateCardDiff>(`/operator/rate-cards/${id}/diff/${otherId}`)).data,
}

export type QuoteSegment = 'family' | 'corporate' | 'school'
export type QuoteRequest = {
  pax: number | null
  days: number | null
  start_date: string | null
  segment: QuoteSegment | null
  destinations: string[]
  pickup: string | null
  hotel_class: number | null
  meal_plan: 'none' | 'basic' | 'full' | null
  budget_per_pax: number | null
  interests: string[]
  customer_name: string | null
  missing_fields: string[]
  assumed_fields: string[]
}

export type PriceMode = 'safe' | 'balanced' | 'max_profit'
export type ModePrice = { price_per_pax: number; total: number; margin_pct: number; p_win: number; expected_profit: number; floor_bound: boolean }
export type CostLine = {
  category: RateCategory; label: string; qty: number; unit_vnd: number; amount_vnd: number; fixed: boolean
  surcharge_vnd: number; surcharge_codes: string[]; total_vnd: number
}
export type QuoteSummary = {
  id: string; code: string; status: string; channel: string; customer_name: string | null; pax: number | null; days: number | null
  start_date: string | null; destinations: string[]; price_vnd: number | null; price_mode: PriceMode; cost_total_vnd: number; created_at: string
}
export type Quote = QuoteSummary & {
  customer_contact: string | null
  raw_message: string | null
  request: QuoteRequest
  itinerary: { template_code: string; template_name: string; days: Array<{ title: string; legs: Array<{ from: string; to: string; distance_km: number }>; stops: Array<{ name: string }> }> }
  cost: { total: number; fixed_total: number; variable_total: number; variable_per_pax: number; lines: CostLine[]; surcharges: Array<{ code: string; label: string; pct: number; amount_vnd: number }> }
  pricing: { source: 'model' | 'heuristic'; floor_margin_pct: number; modes: Record<PriceMode, ModePrice> }
  margin_floor_pct: number
  explanation: string | null
  lost_reason: string | null
  revision: number
}
export type QuoteDraft = { quote: Quote | null; request: QuoteRequest; parser: 'llm' | 'offline' | 'given'; questions: string[] }
export type PricingCurve = {
  pax: number; cost_total_vnd: number; cost_per_pax: number; selected_mode: PriceMode; source: string; floor_margin_pct: number
  modes: Record<PriceMode, ModePrice>; points: Array<{ price_per_pax: number; p_win: number; expected_profit: number }>
}

export const quoteApi = {
  // The LLM parse + costing can take a few seconds.
  draft: async (body: { message?: string; request?: QuoteRequest; parse_only?: boolean }) =>
    (await http.post<QuoteDraft>('/operator/quotes', body, { timeout: 60000 })).data,
  list: async (status?: string) => (await http.get<QuoteSummary[]>('/operator/quotes', { params: status ? { status } : {} })).data,
  get: async (id: string) => (await http.get<Quote>(`/operator/quotes/${id}`)).data,
  selectMode: async (id: string, mode: PriceMode) => (await http.post<Quote>(`/operator/quotes/${id}/select-mode`, { mode })).data,
  mark: async (id: string, outcome: 'won' | 'lost', reason?: string) => (await http.post<Quote>(`/operator/quotes/${id}/mark`, { outcome, reason })).data,
  curve: async (id: string) => (await http.get<PricingCurve>(`/operator/quotes/${id}/pricing-curve`)).data,
}
