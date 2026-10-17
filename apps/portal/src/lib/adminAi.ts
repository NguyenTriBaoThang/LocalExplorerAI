import { http } from './api'

export type AiTargetSet = {
  experiences: Array<{ id: string; title: string }>
  itineraries: Array<{ id: string; planned_date: string | null; created_at: string }>
}
export type PromptManifest = { suite: string; version: string; prd_version: string; effective_date: string; prompt_ids: string[] }
export type LocalModelStatus = {
  configured: boolean; loaded: boolean; deployment_allowed: boolean
  model_version: string | null; block_reason: string | null; dataset_status?: string
}
export type FloodModelStatus = LocalModelStatus & { demo_mode?: boolean | null; error?: string | null }
export type MlStatus = { experience_ranker: LocalModelStatus; flood_risk_model: FloodModelStatus }

export type WeatherAdvisoryPayload = {
  rain_mm_per_hour: number
  aqi_pm25: number
  temperature_c: number
  children_in_group: boolean
  observed_at: string
}

export type FloodSample = { edge_id: string; decision_time: string; horizon_min: number; region: string; road_class: string; [key: string]: string | number }
export type FloodPrediction = {
  edge_id: string; decision_time: string; horizon_min: number; probability: number; risk_state: string
  coverage_ratio: number | null; model_version: string; is_verified_observation: false
}
export type FloodRiskResponse = { model_version: string | null; predictions: FloodPrediction[]; safety_note?: string }

export const adminAiApi = {
  targets: async () => (await http.get<AiTargetSet>('/admin/ai/targets')).data,
  promptCatalog: async () => (await http.get<PromptManifest>('/ai/prompts')).data,
  mlStatus: async () => (await http.get<MlStatus>('/ml/status')).data,
  tagExperience: async (experienceId: string, additional_context: string) =>
    (await http.post<unknown>(`/experiences/${experienceId}/ai-tag`, { additional_context })).data,
  compareIntent: async (experience_a_id: string, experience_b_id: string) =>
    (await http.post<unknown>('/ai/intent-similarity', { experience_a_id, experience_b_id })).data,
  weatherAdvisory: async (itineraryId: string, payload: WeatherAdvisoryPayload) =>
    (await http.post<unknown>(`/itineraries/${itineraryId}/weather-advisory`, payload)).data,
  predictFloodRisk: async (samples: FloodSample[]) =>
    (await http.post<FloodRiskResponse>('/ml/flood-risk', { samples })).data,
}
