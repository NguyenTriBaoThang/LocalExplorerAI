/* Local Explorer AI: cache the app shell and public reference data only. */
const SHELL_CACHE = 'local-explorer-shell-v1.1'
const ASSET_CACHE = 'local-explorer-assets-v1.1'
const CATALOG_CACHE = 'local-explorer-catalog-v1.1'
const CURRENT_CACHES = [SHELL_CACHE, ASSET_CACHE, CATALOG_CACHE]
const APP_SHELL = ['/', '/offline.html', '/manifest.webmanifest', '/logo-icon.png', '/pwa-icon-192.png', '/apple-touch-icon.png']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL_CACHE).then((cache) => cache.addAll(APP_SHELL)).catch(() => undefined))
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((names) => Promise.all(
    names.filter((name) => name.startsWith('local-explorer-') && !CURRENT_CACHES.includes(name))
      .map((name) => caches.delete(name)),
  )))
  self.clients.claim()
})

function isPublicCatalogRequest(url) {
  if (url.search || url.pathname.endsWith('/slots')) return false
  return /^\/api\/(?:pois(?:\/[A-Za-z0-9_-]+)?|experiences(?:\/[A-Za-z0-9_-]+)?|partners(?:\/[A-Za-z0-9_-]+)?)$/.test(url.pathname)
}

function cacheableJson(response) {
  if (!response || response.status !== 200 || response.type !== 'basic') return false
  const headers = response.headers
  const control = (headers.get('Cache-Control') || '').toLowerCase()
  const vary = (headers.get('Vary') || '').toLowerCase()
  return headers.get('Content-Type')?.includes('application/json')
    && !headers.has('Set-Cookie')
    && !/(private|no-store|no-cache)/.test(control)
    && !/(cookie|authorization)/.test(vary)
}

async function fetchPublicCatalog(request, url) {
  const key = new Request(url.href, { method: 'GET', credentials: 'omit', headers: { Accept: 'application/json' } })
  const cache = await caches.open(CATALOG_CACHE)
  const update = fetch(key).then(async (response) => {
    if (cacheableJson(response)) await cache.put(key, response.clone())
    return response
  })
  const cached = await cache.match(key)
  if (cached) {
    void update.catch(() => undefined)
    return cached
  }
  return update
}

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return

  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(async () => (
      await caches.match('/') || await caches.match('/offline.html')
    )))
    return
  }

  if (isPublicCatalogRequest(url) && !request.headers.has('Authorization')) {
    event.respondWith(fetchPublicCatalog(request, url).catch(async () => (
      await caches.match(new Request(url.href, { credentials: 'omit', headers: { Accept: 'application/json' } }))
        || Response.error()
    )))
    return
  }

  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(caches.open(ASSET_CACHE).then(async (cache) => {
      const cached = await cache.match(request)
      if (cached) return cached
      const response = await fetch(request)
      if (response.ok && response.type === 'basic') await cache.put(request, response.clone())
      return response
    }).catch(() => Response.error()))
  }
})

self.addEventListener('push', (event) => {
  let payload = {}
  try { payload = event.data ? event.data.json() : {} } catch { /* show a generic booking update */ }
  const title = typeof payload.title === 'string' ? payload.title : 'Local Explorer AI'
  const options = {
    body: typeof payload.body === 'string' ? payload.body : 'Bạn có cập nhật về yêu cầu đặt chỗ.',
    icon: '/logo-icon.png',
    badge: '/favicon-32x32.png',
    tag: typeof payload.tag === 'string' ? payload.tag : 'booking-update',
    data: { url: typeof payload.url === 'string' ? payload.url : '/profile' },
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = new URL(event.notification.data?.url || '/profile', self.location.origin)
  if (target.origin !== self.location.origin) return
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
    const existing = clients.find((client) => new URL(client.url).origin === self.location.origin)
    if (existing) return existing.navigate(target.href).then(() => existing.focus())
    return self.clients.openWindow(target.href)
  }))
})
