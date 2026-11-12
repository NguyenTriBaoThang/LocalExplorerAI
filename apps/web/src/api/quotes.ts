import { api } from './client'

export type PublicQuote = {
  code: string; status: 'sent' | 'viewed' | 'accepted' | 'deposit_paid' | 'expired' | 'won' | 'lost' | 'draft'
  company_name: string; customer_name: string | null; pax: number; days: number; start_date: string | null; destinations: string[]
  itinerary: Array<{ title: string; stops: string[] }>; inclusions: string[]
  price_vnd: number; price_per_pax: number; deposit_pct: number; deposit_vnd: number
  expires_at: string | null; accepted_at: string | null; can_accept: boolean; can_pay: boolean
}

const base = (token: string) => `/public/quotes/${encodeURIComponent(token)}`
export const getPublicQuote = async (token: string) => (await api.get<PublicQuote>(base(token))).data
export const acceptPublicQuote = async (token: string, body: { name: string; phone: string }) => (await api.post<PublicQuote>(`${base(token)}/accept`, body)).data
export const checkoutPublicQuote = async (token: string, provider: 'vnpay' | 'momo') =>
  (await api.post<{ checkout_url: string }>(`${base(token)}/checkout`, { provider })).data
