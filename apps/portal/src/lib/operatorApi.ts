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

export type MarginAlert = { margin_pct: number; floor_pct: number; shortfall_vnd: number }
export type RequoteSummary = {
  requoted: number
  quotes: Array<{ quote_id: string; code: string; status: string; old_cost_vnd: number; new_cost_vnd: number; margin_pct: number | null }>
  alerts: Array<MarginAlert & { quote_id: string; code: string }>
}

export const rateCardApi = {
  upload: async (filename: string, data_url: string, kind: 'rate_sheet' | 'invoice' = 'rate_sheet') =>
    (await http.post<OperatorDocument>('/operator/documents', { filename, data_url, kind })).data,
  // Extraction runs inside the request and can take a while on long sheets or images.
  extract: async (id: string) => (await http.post<OperatorDocument>(`/operator/documents/${id}/extract`, null, { timeout: 120000 })).data,
  saveLines: async (id: string, supplier: string | null, lines: ExtractedLine[]) =>
    (await http.patch<OperatorDocument>(`/operator/documents/${id}/lines`, { supplier, lines })).data,
  reject: async (id: string) => (await http.post<OperatorDocument>(`/operator/documents/${id}/reject`)).data,
  cards: async () => (await http.get<RateCard[]>('/operator/rate-cards')).data,
  card: async (id: string) => (await http.get<RateCard>(`/operator/rate-cards/${id}`)).data,
  fromDocument: async (id: string, supplier: string) =>
    (await http.post<{ cards: RateCard[] }>(`/operator/rate-cards/from-document/${id}`, { supplier })).data.cards,
  approve: async (id: string) => (await http.post<RateCard & { requote: RequoteSummary }>(`/operator/rate-cards/${id}/approve`)).data,
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
  start_date: string | null; destinations: string[]; price_vnd: number | null; price_mode: PriceMode; cost_total_vnd: number; margin_pct: number | null; created_at: string
}
export type Quote = QuoteSummary & {
  customer_contact: string | null
  raw_message: string | null
  margin_alert: MarginAlert | null
  request: QuoteRequest & { overrides?: { vehicle_seats?: number; meal_code?: string; hotel_code?: string } }
  itinerary: { template_code: string; template_name: string; days: Array<{ title: string; legs: Array<{ from: string; to: string; distance_km: number }>; stops: Array<{ name: string }> }> }
  cost: { total: number; fixed_total: number; variable_total: number; variable_per_pax: number; lines: CostLine[]; surcharges: Array<{ code: string; label: string; pct: number; amount_vnd: number }> }
  pricing: { source: 'model' | 'heuristic'; floor_margin_pct: number; modes: Record<PriceMode, ModePrice> }
  margin_floor_pct: number
  explanation: string | null
  lost_reason: string | null
  revision: number
  sent_at: string | null; expires_at: string | null; first_viewed_at: string | null; view_count: number; accepted_at: string | null
  deposit_pct?: number; deposit_vnd?: number | null; deposit_paid_at?: string | null
}
export type FollowupReason = 'not_viewed' | 'not_accepted' | 'expiring'
export type FollowupQuote = QuoteSummary & { followup_reason: FollowupReason; reminder_text: string; sent_at: string | null; first_viewed_at: string | null; expires_at: string | null }
export type QuoteSent = { quote: Quote; share_url: string; message: string }
export type QuoteDraft = { quote: Quote | null; request: QuoteRequest; parser: 'llm' | 'offline' | 'given'; questions: string[] }
export type PricingCurve = {
  pax: number; cost_total_vnd: number; cost_per_pax: number; selected_mode: PriceMode; source: string; floor_margin_pct: number
  modes: Record<PriceMode, ModePrice>; points: Array<{ price_per_pax: number; p_win: number; expected_profit: number }>
}

export type QuotePatch = { pax?: number; start_date?: string; overrides?: { vehicle_seats: number | null }; reason?: string }
export type RescueOption = {
  code: string; title: string; changes: Record<string, unknown>; new_cost_vnd: number; savings_vnd: number; new_margin_pct: number | null
  new_price_vnd: number; customer_visible: boolean; p_win?: number
}
export type Rescue = { margin_alert: MarginAlert | null; options: RescueOption[]; explanation: string; explanation_source: 'llm' | 'template' }
export type RescueApplied = { applied: boolean; requires_resend: boolean; quote: Quote; suggested_price_vnd: number }
export type QuoteRevisionRow = { revision: number; reason: string | null; created_at: string; price_vnd: number | null; cost_total_vnd: number | null; margin_pct: number | null }

export const quoteApi = {
  // The LLM parse + costing can take a few seconds.
  draft: async (body: { message?: string; request?: QuoteRequest; parse_only?: boolean }) =>
    (await http.post<QuoteDraft>('/operator/quotes', body, { timeout: 60000 })).data,
  list: async (status?: string) => (await http.get<QuoteSummary[]>('/operator/quotes', { params: status ? { status } : {} })).data,
  followups: async () => (await http.get<FollowupQuote[]>('/operator/quotes', { params: { needs_followup: 1 } })).data,
  send: async (id: string) => (await http.post<QuoteSent>(`/operator/quotes/${id}/send`)).data,
  get: async (id: string) => (await http.get<Quote>(`/operator/quotes/${id}`)).data,
  selectMode: async (id: string, mode: PriceMode) => (await http.post<Quote>(`/operator/quotes/${id}/select-mode`, { mode })).data,
  mark: async (id: string, outcome: 'won' | 'lost', reason?: string) => (await http.post<Quote>(`/operator/quotes/${id}/mark`, { outcome, reason })).data,
  patch: async (id: string, body: QuotePatch) => (await http.patch<Quote>(`/operator/quotes/${id}`, body, { timeout: 60000 })).data,
  rescue: async (id: string) => (await http.get<Rescue>(`/operator/quotes/${id}/rescue`)).data,
  applyRescue: async (id: string, code: string, confirmResend = false) =>
    (await http.post<RescueApplied>(`/operator/quotes/${id}/apply-rescue/${code}`, { confirm_resend: confirmResend })).data,
  revisions: async (id: string) => (await http.get<QuoteRevisionRow[]>(`/operator/quotes/${id}/revisions`)).data,
  curve: async (id: string) => (await http.get<PricingCurve>(`/operator/quotes/${id}/pricing-curve`)).data,
}

export type CostReason = 'price_change' | 'pax_change' | 'unplanned' | 'surcharge' | 'not_used' | 'other'
export type CostActualRow = {
  id: string; category: RateCategory; label: string; quoted_vnd: number; actual_vnd: number; variance_vnd: number
  reason: CostReason | null; matched_cost_line: number | null; note: string | null; confirmed: boolean
}
export type Reconciliation = {
  quote_id: string; code: string; status: string; finalized: boolean; actual_cost_vnd: number | null; price_vnd: number | null; quoted_total_vnd: number
  rows: CostActualRow[]; totals: { quoted_vnd: number; actual_vnd: number; variance_vnd: number }
}
export type MarginAnalytics = {
  totals: { quotes: number; price_vnd: number; expected_cost_vnd: number; actual_cost_vnd: number; variance_vnd: number; expected_margin_pct: number | null; actual_margin_pct: number | null }
  quotes: Array<{ quote_id: string; code: string; customer_name: string | null; start_date: string; price_vnd: number; expected_cost_vnd: number; actual_cost_vnd: number
    variance_vnd: number; expected_margin_pct: number | null; actual_margin_pct: number | null }>
  by_reason: Array<{ reason: CostReason; variance_vnd: number; count: number }>
  by_supplier: Array<{ supplier: string; quoted_vnd: number; actual_vnd: number; variance_vnd: number }>
}

export const reconcileApi = {
  get: async (quoteId: string) => (await http.get<Reconciliation>(`/operator/quotes/${quoteId}/reconcile`)).data,
  run: async (quoteId: string, documentId: string) => (await http.post<Reconciliation>(`/operator/quotes/${quoteId}/reconcile`, { document_id: documentId })).data,
  patchRow: async (id: string, body: { actual_vnd?: number; reason?: CostReason | null; note?: string | null }) =>
    (await http.patch<CostActualRow>(`/operator/cost-actuals/${id}`, body)).data,
  confirm: async (quoteId: string) => (await http.post<Reconciliation>(`/operator/quotes/${quoteId}/reconcile/confirm`)).data,
  margin: async (from?: string, to?: string) => (await http.get<MarginAnalytics>('/operator/analytics/margin', { params: { from: from || undefined, to: to || undefined } })).data,
}
