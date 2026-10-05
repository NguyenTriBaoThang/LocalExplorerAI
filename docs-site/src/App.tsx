import { Suspense, lazy, useEffect, useRef } from 'react'
import { useRoute } from './router'
import { NAV } from './data/site'
import { Layout } from './components/Layout'

const pages: Record<string, React.LazyExoticComponent<() => JSX.Element>> = {
  '/': lazy(() => import('./pages/Overview')),
  '/architecture': lazy(() => import('./pages/Architecture')),
  '/concierge': lazy(() => import('./pages/Concierge')),
  '/planning': lazy(() => import('./pages/Planning')),
  '/ml': lazy(() => import('./pages/ML')),
  '/digital-twin': lazy(() => import('./pages/DigitalTwin')),
  '/platform': lazy(() => import('./pages/Platform')),
  '/api': lazy(() => import('./pages/ApiExplorer')),
  '/demo': lazy(() => import('./pages/Demo')),
  '/roadmap': lazy(() => import('./pages/Roadmap')),
}

export function App() {
  const path = useRoute()
  const Page = pages[path]
  const item = NAV.find((n) => n.path === path)
  const first = useRef(true)

  useEffect(() => {
    document.title = item && item.id !== 'overview' ? `${item.label} · LocalExplorerAI Docs` : 'LocalExplorerAI Docs'
  }, [item])

  // Move focus to the page on navigation so keyboard and screen-reader users start at the top.
  useEffect(() => {
    if (first.current) { first.current = false; return }
    document.getElementById('main')?.focus({ preventScroll: true })
  }, [path])

  return (
    <Layout path={path}>
      <Suspense fallback={<p className="loading" role="status">Loading…</p>}>
        {Page ? <Page /> : <NotFound />}
      </Suspense>
    </Layout>
  )
}

function NotFound() {
  return (
    <section className="page narrow">
      <h1>Page not found</h1>
      <p>There is no page at this address. <a href="#/">Back to the overview</a>.</p>
    </section>
  )
}
