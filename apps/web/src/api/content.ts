import { api } from './client'
import type { Article, ArticleSummary, Experience, HomeContent, PartnerSummary, POI, ReviewSummary, ReviewableBooking } from '../types'

/** Published content and reviews written in the partner/admin portal. */
export const contentApi = {
  experience: async (id: string) => (await api.get<Experience>(`/experiences/${encodeURIComponent(id)}`)).data,
  partners: async (q = '') => (await api.get<PartnerSummary[]>('/partners', { params: q ? { q } : {} })).data,
  places: async () => (await api.get<POI[]>('/pois')).data,
  home: async () => (await api.get<HomeContent>('/content/home')).data,
  articles: async (params: { category?: string; q?: string } = {}) => (await api.get<ArticleSummary[]>('/content/articles', { params })).data,
  article: async (slug: string) => (await api.get<Article>(`/content/articles/${encodeURIComponent(slug)}`)).data,
  experienceReviews: async (experienceId: string) => (await api.get<ReviewSummary>(`/experiences/${experienceId}/reviews`)).data,
  reviewableBookings: async () => (await api.get<ReviewableBooking[]>('/me/reviewable-bookings')).data,
  reviewBooking: async (bookingId: string, rating: number, comment: string) => (await api.post(`/bookings/${bookingId}/review`, { rating, comment })).data,
}

export async function getPOI(id: string) {
  const { data } = await api.get<import('../types').POI>(`/pois/${id}?scope=citywide`)
  return data
}
