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
