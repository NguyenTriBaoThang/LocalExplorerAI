import { http } from './api'

/* ---------- Integrations ---------- */

export type IntegrationField = {
  key: string
  label: string
  secret: boolean
  configured: boolean
  source: 'admin' | 'environment' | 'missing'
  value: string | null
  updated_at: string | null
}
export type IntegrationProvider = { id: string; label: string; fields: string[]; required: string[] }
export type IntegrationStatus = 'active' | 'incomplete' | 'inactive'
export type IntegrationGroup = {
  service: string
  fields: IntegrationField[]
  title: string
  description: string
  testable: boolean
  status: IntegrationStatus
  missing: string[]
  provider_key: string | null
  active_provider: string | null
  providers: IntegrationProvider[]
  shared_fields: string[]
  required: string[]
  updated_at: string | null
  admin_overrides: number
  simulated: boolean
  relevant_fields: string[]
}
export type IntegrationTestResult = { service: string; status: string; ok: boolean; message_vi: string; detail_vi?: string }

export const integrationsApi = {
  list: async () => (await http.get<IntegrationGroup[]>('/admin/integrations')).data,
  update: async (service: string, values: Record<string, string>, removeKeys: string[] = []) =>
    (await http.put<IntegrationGroup[]>(`/admin/integrations/${encodeURIComponent(service)}`, { values, remove_keys: removeKeys })).data,
  test: async (service: string) =>
    (await http.post<IntegrationTestResult>(`/admin/integrations/${encodeURIComponent(service)}/test`)).data,
}

/* ---------- Operations ---------- */

export type OperationsStatus = {
  generated_at: string
  notifications: Record<string, number>
  worker: { status: string; last_seen: string | null }
  last_job: { status: string; started_at: string; finished_at: string | null; processed_count: number; error_summary: string | null } | null
  active_events: number
  channels: { email_enabled: boolean }
  rate_limit_enabled: boolean
}
export type OpsJobRow = { id: string; job_name: string; status: string; started_at: string; finished_at: string | null; processed_count: number; error_summary: string | null }
export type OpsEventRow = { id: string; event_type: string; target_type: string; target_id: string; status: string; valid_until: string | null; metadata: Record<string, unknown>; created_at: string }
export type OpsNotificationRow = { id: string; channel: string; booking_id: string | null; event_id: string | null; subject: string; status: string; attempts: number; available_at: string; sent_at: string | null; last_error: string | null; created_at: string }

export const opsApi = {
  status: async () => (await http.get<OperationsStatus>('/ops/status')).data,
  jobs: async () => (await http.get<OpsJobRow[]>('/ops/jobs')).data,
  events: async () => (await http.get<OpsEventRow[]>('/ops/events')).data,
  notifications: async () => (await http.get<OpsNotificationRow[]>('/ops/notifications')).data,
}
