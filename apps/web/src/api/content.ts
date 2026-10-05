import { api } from './client'
import type { Article, ArticleSummary, HomeContent, ReviewSummary, ReviewableBooking } from '../types'

/** Published content and reviews written in the partner/admin portal. */
export const contentApi = {
  home: async () => (await api.get<HomeContent>('/content/home')).data,
  articles: async (params: { category?: string; q?: string } = {}) => (await api.get<ArticleSummary[]>('/content/articles', { params })).data,
  article: async (slug: string) => (await api.get<Article>(`/content/articles/${encodeURIComponent(slug)}`)).data,
  experienceReviews: async (experienceId: string) => (await api.get<ReviewSummary>(`/experiences/${experienceId}/reviews`)).data,
  reviewableBookings: async () => (await api.get<ReviewableBooking[]>('/me/reviewable-bookings')).data,
  reviewBooking: async (bookingId: string, rating: number, comment: string) => (await api.post(`/bookings/${bookingId}/review`, { rating, comment })).data,
}

export async function getPOI(id: string) {
  const { data } = await api.get<import('../types').POI>(`/pois/${id}`)
  return data
}
