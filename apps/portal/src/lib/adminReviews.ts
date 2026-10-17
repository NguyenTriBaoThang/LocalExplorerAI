import { http } from './api'

export type ReviewKind = 'place' | 'experience'
export type ReviewStatus = 'published' | 'hidden'

export type AdminReview = {
  kind: ReviewKind
  id: string
  target_id: string
  target_title: string
  author_name: string | null
  author_email: string | null
  rating: number
  comment: string
  status: ReviewStatus
  moderation_note: string | null
  moderated_at: string | null
  created_at: string
}

export const adminReviewsApi = {
  list: async (params: { kind: ReviewKind; status?: string; q?: string; limit: number; offset: number }) => {
    const clean = Object.fromEntries(Object.entries(params).filter(([, value]) => value !== '' && value !== undefined))
    const response = await http.get<AdminReview[]>('/admin/reviews', { params: clean })
    const header = (response.headers as Record<string, unknown>)['x-total-count']
    return { items: response.data, total: Number(header ?? response.data.length) }
  },
  setStatus: async (kind: ReviewKind, id: string, action: 'hide' | 'restore', note?: string) =>
    (await http.post<{ kind: ReviewKind; id: string; status: ReviewStatus; moderation_note: string | null }>(
      `/admin/reviews/${kind}/${id}/status`, note ? { action, note } : { action })).data,
}
