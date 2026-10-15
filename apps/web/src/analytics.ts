import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/*
 * Anonymous page-view beacon for the portal's traffic dashboard.
 * The browser keeps a random id (no personal data); the server stores only a keyed hash of it, never the IP.
 * Query strings are not sent, staff areas are not tracked, and Do-Not-Track / Global Privacy Control are honoured.
 */

type Entity = { entity_type: 'poi' | 'experience' | 'article'; entity_id: string }

const SESSION_IDLE_MS = 30 * 60 * 1000
const UNTRACKED = ['/admin', '/provider-portal']
// Detail pages report their own view together with the place/article id (see useEntityView), so the generic
// route tracker skips them to avoid counting the same view twice.
const ENTITY_PAGES = /^\/(places|guides|experiences)\/[^/]+$/

function randomId() {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

function stored(storage: () => Storage, key: string, create: () => string): string {
  try {
    const existing = storage().getItem(key)
    if (existing) return existing
    const value = create()
    storage().setItem(key, value)
    return value
  } catch {
    return create()  // private mode or blocked storage: still count the view, just not across pages
  }
}

function sessionId(): string {
  try {
    const now = Date.now()
    const raw = sessionStorage.getItem('le_session')
    const [id, last] = raw ? raw.split('|') : []
    const current = id && now - Number(last) < SESSION_IDLE_MS ? id : randomId()
    sessionStorage.setItem('le_session', `${current}|${now}`)
    return current
  } catch {
    return randomId()
  }
}

function optedOut(): boolean {
  const nav = navigator as Navigator & { globalPrivacyControl?: boolean }
  return nav.doNotTrack === '1' || nav.globalPrivacyControl === true
}

let lastSent = { key: '', at: 0 }

export function trackPageView(path: string, entity?: Entity) {
  if (optedOut() || UNTRACKED.some((prefix) => path.startsWith(prefix))) return
  // The same view reported twice within a second (React StrictMode re-running effects, double clicks) counts once.
  const key = `${path}|${entity?.entity_id ?? ''}`
  if (key === lastSent.key && Date.now() - lastSent.at < 1000) return
  lastSent = { key, at: Date.now() }
  const body = JSON.stringify({
    visitor_id: stored(() => localStorage, 'le_visitor', randomId),
    session_id: sessionId(),
    path,
    referrer: document.referrer || null,
    ...entity,
  })
  void fetch('/api/analytics/pageview', { method: 'POST', body, keepalive: true, credentials: 'same-origin', headers: { 'Content-Type': 'application/json' } })
    .catch(() => undefined)  // analytics must never affect the page
}

/** Records one view per route change. Mount once inside the router. */
export function usePageViewTracking() {
  const { pathname } = useLocation()
  useEffect(() => { if (!ENTITY_PAGES.test(pathname)) trackPageView(pathname) }, [pathname])
}

/** Records a view of a specific place, experience or article (feeds "most viewed" and partner statistics). */
export function useEntityView(entity: Entity | null) {
  const { pathname } = useLocation()
  const key = entity ? `${entity.entity_type}:${entity.entity_id}` : ''
  useEffect(() => {
    if (entity) trackPageView(pathname, entity)
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps
}
