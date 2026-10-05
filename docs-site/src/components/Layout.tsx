import { Suspense, lazy, useEffect, useState, type ReactNode } from 'react'
import { Github, Menu, Search as SearchIcon, X } from 'lucide-react'
import { NAV, REPO_URL } from '../data/site'

const SearchDialog = lazy(() => import('./SearchDialog'))

export function Layout({ path, children }: { path: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [searching, setSearching] = useState(false)

  useEffect(() => setOpen(false), [path])
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setSearching(true)
      }
    }
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [])

  return (
    <>
      <a className="skip" href="#main" onClick={(e) => { e.preventDefault(); document.getElementById('main')?.focus() }}>Skip to content</a>
      <header className="nav">
        <div className="nav-inner">
          <a className="brand" href="#/" aria-label="LocalExplorerAI, overview">
            <img src="./img/logo-icon.png" alt="" width={26} height={26} />
            <span>LocalExplorerAI</span>
          </a>
          <nav className="nav-links" aria-label="Primary">
            {NAV.map((n) => (
              <a key={n.id} href={`#${n.path}`} aria-current={n.path === path ? 'page' : undefined}>{n.label}</a>
            ))}
          </nav>
          <div className="nav-actions">
            <button type="button" className="icon-btn" onClick={() => setSearching(true)} aria-label="Search documentation (Ctrl+K)">
              <SearchIcon size={16} aria-hidden /><span className="hide-sm">Search</span><kbd className="hide-sm">Ctrl K</kbd>
            </button>
            <a className="icon-btn gh" href={REPO_URL} target="_blank" rel="noreferrer"><Github size={16} aria-hidden /><span className="hide-sm">GitHub</span></a>
            <button type="button" className="icon-btn menu-btn" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="drawer" aria-label={open ? 'Close menu' : 'Open menu'}>
              {open ? <X size={18} aria-hidden /> : <Menu size={18} aria-hidden />}
            </button>
          </div>
        </div>
        {open && (
          <nav id="drawer" className="drawer" aria-label="Mobile">
            {NAV.map((n) => (
              <a key={n.id} href={`#${n.path}`} aria-current={n.path === path ? 'page' : undefined}>
                {n.label}<span>{n.blurb}</span>
              </a>
            ))}
          </nav>
        )}
      </header>
      <main id="main" tabIndex={-1}>{children}</main>
      <footer className="footer">
        <p>LocalExplorerAI documentation. Content is derived from the repository; where something is partial or unverified, the page says so.</p>
        <p className="mono dim">Static site · no backend · interactive demos use client-side sample data</p>
      </footer>
      {searching && (
        <Suspense fallback={null}>
          <SearchDialog onClose={() => setSearching(false)} />
        </Suspense>
      )}
    </>
  )
}
