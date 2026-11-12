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
