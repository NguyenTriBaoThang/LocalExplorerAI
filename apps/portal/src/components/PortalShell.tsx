import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Menu, X, type LucideIcon } from 'lucide-react'
import { BrandLogo } from './Brand'
import { UserMenu } from './UserMenu'
import { cx } from './ui'

export type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean; badge?: number }
export type NavGroup = { title?: string; items: NavItem[] }

/** Sidebar + topbar frame shared by the partner and admin areas. */
export function PortalShell({ area, nav, sidebarFooter, banner }: { area: string; nav: NavGroup[]; sidebarFooter?: ReactNode; banner?: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  useEffect(() => setMobileOpen(false), [location.pathname])

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center px-5"><BrandLogo subtitle={area} /></div>
      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
        {nav.map((group, index) => (
          <div key={group.title ?? index} className="space-y-0.5">
            {group.title && <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{group.title}</p>}
            {group.items.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end}
            className={({ isActive }) => cx(
              'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition',
              isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
            )}>
            {({ isActive }) => (
              <>
                <item.icon className={cx('h-[18px] w-[18px]', isActive ? 'text-brand-600' : 'text-slate-400 group-hover:text-slate-600')} />
                <span className="flex-1">{item.label}</span>
                {!!item.badge && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">{item.badge}</span>}
              </>
            )}
          </NavLink>
            ))}
          </div>
        ))}
      </nav>
      {sidebarFooter && <div className="border-t border-slate-200 p-4">{sidebarFooter}</div>}
    </div>
  )

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-slate-200 bg-white lg:block">{sidebar}</aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="animate-fade-in absolute inset-0 bg-slate-900/40" onClick={() => setMobileOpen(false)} />
          <aside className="animate-slide-in absolute inset-y-0 left-0 w-72 bg-white shadow-pop">
            <button type="button" aria-label="Đóng menu" onClick={() => setMobileOpen(false)} className="absolute right-3 top-4 rounded-lg p-1.5 text-slate-500 hover:bg-slate-100"><X className="h-5 w-5" /></button>
            {sidebar}
          </aside>
        </div>
      )}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/80 px-4 backdrop-blur sm:px-6 lg:px-8">
          <button type="button" aria-label="Mở menu" onClick={() => setMobileOpen(true)} className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 lg:hidden"><Menu className="h-5 w-5" /></button>
          <div className="flex-1" />
          <UserMenu />
        </header>
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">{banner && <div className="mb-6">{banner}</div>}<Outlet /></main>
      </div>
    </div>
  )
}
