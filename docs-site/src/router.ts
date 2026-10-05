import { useEffect, useState } from 'react'

/** Hash routing: GitHub Pages has no SPA fallback, so deep links live after the #. */
function read(): string {
  const raw = window.location.hash.replace(/^#/, '')
  const path = raw.split('?')[0] || '/'
  return path.startsWith('/') ? path : `/${path}`
}

export function useRoute(): string {
  const [path, setPath] = useState(read)
  useEffect(() => {
    const on = () => {
      setPath(read())
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return path
}

export const href = (path: string) => `#${path}`
