/** Shared destination for staff login, registration and portal redirects. */
const defaultPortalUrl = ['www.localexplorerai.site', 'localexplorerai.site'].includes(window.location.hostname)
  ? 'https://portal.localexplorerai.site'
  : 'http://localhost:5174'

export const PORTAL_URL = ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_PORTAL_URL || defaultPortalUrl).replace(/\/$/, '')
