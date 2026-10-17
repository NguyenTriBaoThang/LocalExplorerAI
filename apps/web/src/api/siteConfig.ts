import { api } from './client'

export type SiteConfig = { site_announcement: string; maintenance_mode: boolean; maptiles_key: string | null }

const EMPTY: SiteConfig = { site_announcement: '', maintenance_mode: false, maptiles_key: null }
let pending: Promise<SiteConfig> | null = null

/** Settings managed in the admin portal. Fetched once per page load; falls back to defaults if the API is unreachable. */
export function loadSiteConfig(): Promise<SiteConfig> {
  pending ??= api.get<SiteConfig>('/site-config').then((r) => r.data).catch(() => EMPTY)
  return pending
}
