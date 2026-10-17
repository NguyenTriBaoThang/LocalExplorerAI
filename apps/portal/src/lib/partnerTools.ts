import { http } from './api'

/* ---------- Slot assistant ---------- */

export type SlotAssistantPreview = {
  action_preview: {
    action: string
    target_time_window: string
    new_status: string
    available_reported: number | null
    reason_note: string
    confirmation_sms_for_artisan_vi: string
  }
  target_slots: Array<{
    slot_id: string
    experience_title: string
    start_at: string
    end_at: string
    current_status: string
    current_available_reported: number | null
  }>
  prompt_version: string
  confirmation_token: string
  token_expires_in_seconds: number
  requires_explicit_confirmation: boolean
}

export type SlotAssistantResult = { updated_slot_ids: string[]; action: string }

export const slotAssistantApi = {
  preview: async (providerId: string, message: string, slotIds: string[]) =>
    (await http.post<SlotAssistantPreview>(`/providers/${providerId}/slot-assistant/preview`, { message, slot_ids: slotIds })).data,
  confirm: async (providerId: string, confirmationToken: string, expiresAt?: string) =>
    (await http.post<SlotAssistantResult>(`/providers/${providerId}/slot-assistant/confirm`, {
      confirmation_token: confirmationToken,
      ...(expiresAt ? { expires_at: expiresAt } : {}),
    })).data,
}

/* ---------- Source evidence ---------- */

export type EvidenceTargetType = 'poi' | 'experience'
export type EvidenceSourceType = 'official_website' | 'provider_confirmation' | 'field_visit' | 'document' | 'government_dataset' | 'other'

export type PartnerEvidence = {
  id: string
  target_type: string
  target_id: string
  source_uri: string
  source_type: string
  source_label: string | null
  license: string | null
  fields_covered: string[]
  observed_at: string | null
  expires_at: string | null
  verification_status: string
  reviewed_at: string | null
  notes: string | null
}

export type EvidenceDraft = {
  target_type: EvidenceTargetType
  target_id: string
  source_uri: string
  source_type: EvidenceSourceType
  source_label?: string | null
  license?: string | null
  fields_covered: string[]
  observed_at: string
  expires_at: string
  notes?: string
}

/** Fields a piece of evidence may cover, per target type (mirrors the API's REQUIRED_FIELDS). */
export const EVIDENCE_FIELDS: Record<EvidenceTargetType, string[]> = {
  poi: ['name', 'address', 'latitude', 'longitude', 'category'],
  experience: ['title', 'description', 'primary_intent', 'intent_tags', 'is_hands_on', 'duration_min', 'price_vnd', 'price_basis'],
}

export const EVIDENCE_SOURCE_TYPES: Record<EvidenceSourceType, string> = {
  official_website: 'Website chính thức',
  provider_confirmation: 'Cơ sở tự xác nhận',
  field_visit: 'Khảo sát thực địa',
  document: 'Tài liệu / giấy phép',
  government_dataset: 'Dữ liệu cơ quan nhà nước',
  other: 'Khác',
}

export const partnerEvidenceApi = {
  list: async () => (await http.get<PartnerEvidence[]>('/provider/evidence')).data,
  submit: async (draft: EvidenceDraft) =>
    (await http.post<{ id: string; status: string; target_revision: number }>('/provider/evidence', draft)).data,
}

/* ---------- Inline evidence (submitted together with a POI / experience save) ---------- */

export type InlineEvidence = {
  source_uri: string
  source_type: EvidenceSourceType
  source_label: string
  observed_at: string // datetime-local value
  expires_at: string // datetime-local value
  fields: string[]
}

const pad2 = (n: number) => String(n).padStart(2, '0')
const toLocalInput = (d: Date) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`

export const blankInlineEvidence = (): InlineEvidence => ({
  source_uri: '', source_type: 'official_website', source_label: '',
  observed_at: toLocalInput(new Date(Date.now() - 60_000)),
  expires_at: toLocalInput(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)),
  fields: [],
})

/** The partner started filling the optional evidence block. */
export const hasInlineEvidence = (e: InlineEvidence) => e.source_uri.trim() !== ''

/** Returns an error message, or null when the block is valid (call only when hasInlineEvidence). */
export function validateInlineEvidence(e: InlineEvidence): string | null {
  if (!/^https:\/\//i.test(e.source_uri.trim())) return 'Nguồn xác minh phải là đường dẫn https://.'
  if (!e.fields.length) return 'Nguồn xác minh: chọn ít nhất một trường dữ liệu mà nguồn chứng minh.'
  const observed = new Date(e.observed_at).getTime()
  const expires = new Date(e.expires_at).getTime()
  if (Number.isNaN(observed) || observed > Date.now()) return 'Nguồn xác minh: thời điểm quan sát không được ở tương lai.'
  if (Number.isNaN(expires) || expires <= Date.now() || expires <= observed) return 'Nguồn xác minh: ngày hết hạn phải ở tương lai.'
  return null
}

export const submitInlineEvidence = (targetType: EvidenceTargetType, targetId: string, e: InlineEvidence) =>
  partnerEvidenceApi.submit({
    target_type: targetType,
    target_id: targetId,
    source_uri: e.source_uri.trim(),
    source_type: e.source_type,
    source_label: e.source_label.trim() || null,
    fields_covered: e.fields,
    observed_at: new Date(e.observed_at).toISOString(),
    expires_at: new Date(e.expires_at).toISOString(),
  })

/** Outcome of a save, used to show a persistent notice on the list pages. */
export type EvidenceOutcome = { state: 'missing' | 'failed'; targetType: EvidenceTargetType; targetId: string }

export const evidenceLink = (targetType: EvidenceTargetType, targetId: string) =>
  `/partner/evidence?type=${targetType}&id=${encodeURIComponent(targetId)}`

/** Splits the fields picked in a combined (new place + experience) evidence block by the target they belong to. */
export const splitEvidenceFields = (fields: string[]) => ({
  poi: fields.filter((field) => EVIDENCE_FIELDS.poi.includes(field)),
  experience: fields.filter((field) => EVIDENCE_FIELDS.experience.includes(field)),
})
