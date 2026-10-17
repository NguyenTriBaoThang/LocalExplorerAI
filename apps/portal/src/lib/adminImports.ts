import { http } from './api'

export interface PlaceImportBatch {
  id: string
  source_name: string
  source_sha256: string
  worksheet_name: string
  record_count: number
  quality_summary: Record<string, unknown>
  created_at: string
}

export interface PlaceImportCandidate {
  id: string
  external_id: string
  source_row: number
  name: string
  kind: string
  raw_payload: Record<string, unknown>
  quality_flags: string[]
  review_status: string
  target_poi_id?: string | null
  target_poi_status?: string | null
}

export interface PlacePromotePayload {
  address: string
  latitude: number
  longitude: number
  category: string
  source_uri: string
  source_type: string
  source_label: string
  license: string | null
  fields_covered: string[]
  observed_at: string
  expires_at: string
}

export interface DuplicatePair {
  poi_a: { id: string; name: string }
  poi_b: { id: string; name: string }
  name_similarity: number
}

export interface MergeResult {
  kept_poi_id: string
  hidden_duplicate_id: string
  experiences_relinked: number
  stops_relinked: number
}

export const adminImportsApi = {
  placeImports: async () => (await http.get<PlaceImportBatch[]>('/admin/place-imports')).data,
  candidates: async (batchId: string) =>
    (await http.get<PlaceImportCandidate[]>(`/admin/place-imports/${batchId}/candidates`)).data,
  promote: async (batchId: string, candidateId: string, payload: PlacePromotePayload) =>
    (await http.post(`/admin/place-imports/${batchId}/candidates/${candidateId}/promote`, payload)).data,
  duplicates: async () => (await http.get<DuplicatePair[]>('/admin/duplicates/pois')).data,
  merge: async (keepId: string, duplicateId: string, reason: string) =>
    (await http.post<MergeResult>('/admin/duplicates/pois/merge', { keep_id: keepId, duplicate_id: duplicateId, reason })).data,
}
