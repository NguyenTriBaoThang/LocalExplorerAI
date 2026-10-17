import { EmailVerificationBanner } from '../components/account/EmailVerificationBanner'
import { useState, useRef, useEffect } from 'react'
import {
  Sparkles,
  Menu,
  X,
  MapPin,
  Heart,
  User,
  LogOut,
  GitCompare,
  ChevronDown,
  CheckCircle2,
  Sun,
  Moon,
} from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { logout } from '../api/client'
import { setTheme, useTheme } from '../theme'
import { useTranslation } from '../i18n'
import { LanguageSwitcher } from '../components/common/LanguageSwitcher'
import { usePageViewTracking } from '../analytics'
import { JourneyBar } from '../components/journey/JourneyBar'

export function AppLayout() {
  const [open, setOpen] = useState(false)
  const [userDropdown, setUserDropdown] = useState(false)
  const [isOnline, setIsOnline] = useState(() => typeof navigator === 'undefined' || navigator.onLine)
  const { user, loading, setUser } = useAuth()
  const navigate = useNavigate()
  const theme = useTheme()
  const { t } = useTranslation()
  const dropdownRef = useRef<HTMLDivElement>(null)
  usePageViewTracking()

  useEffect(() => {
    const online = () => setIsOnline(true)
    const offline = () => setIsOnline(false)
    window.addEventListener('online', online)
    window.addEventListener('offline', offline)
    return () => {
      window.removeEventListener('online', online)
      window.removeEventListener('offline', offline)
    }
  }, [])

  const isStaff = user?.role === 'admin' || user?.role === 'provider'
  // Staff browse the same public site as everyone else; chat and planner are traveler features. A Portal link leads back to work.
  const links = loading ? [] : [
    ...(isStaff ? [] : [{ to: '/chat', label: t('nav.chat') }]),
    { to: '/places', label: t('nav.places') },
    { to: '/explore', label: t('nav.explore') },
    ...(isStaff ? [] : [{ to: '/planner', label: t('nav.planner') }]),
    { to: '/map-3d', label: t('nav.map3d') },
    { to: '/guides', label: t('nav.guides') },
    { to: '/provider', label: t('nav.provider') },
    { to: '/about', label: t('nav.about') },
    ...(isStaff ? [{ to: user?.role === 'admin' ? '/admin' : '/provider-portal', label: user?.role === 'admin' ? t('nav.admin') : t('nav.providerPortal') }] : []),
  ]

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setUserDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleLogout = async () => {
    setUserDropdown(false)
    setOpen(false)
    try {
      await logout()
      setUser(null)
      navigate('/')
    } catch {
      setUser(null)
      navigate('/')
    }
  }

  const roleLabels: Record<string, { label: string; color: string }> = {
    traveler: { label: t('nav.role.traveler'), color: 'badge-role-traveler' },
    provider: { label: t('nav.role.provider'), color: 'badge-role-provider' },
    admin: { label: t('nav.role.admin'), color: 'badge-role-admin' },
  }

  const userInitials = (user?.display_name || user?.email || 'U')
    .slice(0, 2)
    .toUpperCase()

  return (
    <div className="app-frame-3d">
      {!isOnline && <div role="status" aria-live="polite" style={{ position: 'sticky', top: 0, zIndex: 2000, padding: '8px 16px', textAlign: 'center', background: '#fff4d6', color: '#654a00', fontSize: 13 }}>
        Đang ngoại tuyến. Nội dung đã lưu có thể cũ; lịch trống và đặt chỗ cần kết nối để xác nhận.
      </div>}
      {/* Floating Glass Navigation Header with Scroll Mask */}
      <div className="header-outer-sticky">
        <header className="site-header-3d">
        <div className="header-inner">
          <NavLink to="/" className="brand-3d" onClick={() => setOpen(false)}>
            <div className="brand-gem-3d">
              <img src="/logo-icon.png" alt="Local Explorer AI" className="brand-logo-img" />
              <div className="gem-glow" />
            </div>
            <div className="brand-text">
              <span className="brand-title">
                Local Explorer <span className="brand-ai-chip">3D AI</span>
              </span>
              <span className="brand-tagline">{t('nav.tagline')}</span>
            </div>
          </NavLink>

          {/* Desktop Navigation */}
          <nav className="desktop-nav-3d">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  isActive ? 'nav-link-3d nav-link-active-3d' : 'nav-link-3d'
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>

          {/* Header Action / User Menu Area */}
          <div className="header-actions-area">
            {/* Quick CTA */}
            {!loading && (!user || user.role === 'traveler') && (
              <NavLink to="/chat" className="header-cta-3d">
                <span>{t('nav.planNow')}</span>
                <Sparkles size={15} />
              </NavLink>
            )}

            {/* Language Switcher (VN / EN) */}
            <LanguageSwitcher />

            {/* User Account Menu */}
            {user ? (
              <div className="user-dropdown-container" ref={dropdownRef}>
                <button
                  type="button"
                  className="user-profile-trigger"
                  onClick={() => setUserDropdown(!userDropdown)}
                  aria-expanded={userDropdown}
                  aria-label="Menu tài khoản"
                >
                  <div className="user-avatar-gem">
                    <span>{userInitials}</span>
                  </div>
                  <div className="user-meta-brief">
                    <span className="user-brief-name">
                      {user.display_name || user.email.split('@')[0]}
                    </span>
                    <span className={`user-role-micro ${roleLabels[user.role]?.color || ''}`}>
                      {roleLabels[user.role]?.label || user.role}
                    </span>
                  </div>
                  <ChevronDown
                    size={14}
                    className={`dropdown-chevron ${userDropdown ? 'chevron-rotated' : ''}`}
                  />
                </button>

                {userDropdown && (
                  <div className="user-dropdown-panel animate-fadeIn">
                    <div className="dropdown-user-header">
                      <div className="user-avatar-large">{userInitials}</div>
                      <div className="header-info">
                        <strong>{user.display_name || user.email.split('@')[0]}</strong>
                        <small>{user.email}</small>
                        <span className="role-tag-pill">
                          {roleLabels[user.role]?.label || user.role}
                        </span>
                      </div>
                    </div>

                    <div className="dropdown-menu-list">
                      <NavLink
                        to="/profile"
                        className="dropdown-menu-item"
                        onClick={() => setUserDropdown(false)}
                      >
                        <User size={16} className="text-emerald" />
                        <div>
                          <span>{t('nav.profile')}</span>
                          <small>{t('nav.profileDesc')}</small>
                        </div>
                      </NavLink>

                      {user.role === 'traveler' && (
                        <NavLink
                          to="/compare"
                          className="dropdown-menu-item"
                          onClick={() => setUserDropdown(false)}
                        >
                          <GitCompare size={16} className="text-cyan" />
                          <div>
                            <span>{t('nav.compare')}</span>
                            <small>{t('nav.compareDesc')}</small>
                          </div>
                        </NavLink>
                      )}

                      <div className="dropdown-divider" />

                      <button
                        type="button"
                        className="dropdown-menu-item item-logout"
                        onClick={handleLogout}
                      >
                        <LogOut size={16} />
                        <span>{t('nav.logout')}</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="guest-action-group">
                <NavLink to="/login" className="btn-login-ghost">
                  <User size={15} />
                  <span>{t('nav.login')}</span>
                </NavLink>
              </div>
            )}

            {/* Dark / Light Theme Toggle */}
            <button
              type="button"
              className="theme-toggle-3d"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              aria-label={theme === 'dark' ? t('nav.themeLight') : t('nav.themeDark')}
              title={theme === 'dark' ? t('nav.themeLight') : t('nav.themeDark')}
            >
              {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            </button>

            {/* Mobile Burger Toggle */}
            <button
              className="menu-toggle-3d"
              onClick={() => setOpen(!open)}
              aria-label={open ? t('nav.close') : t('nav.menu')}
            >
              {open ? <X size={22} /> : <Menu size={22} />}
            </button>
          </div>
        </div>

        {/* Mobile Slide-down Drawer */}
        {open && (
          <div className="mobile-nav-drawer animate-fadeIn">
            <div className="mobile-links-list">
              <div className="mobile-lang-row" style={{ padding: '8px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>Ngôn ngữ / Language:</span>
                <LanguageSwitcher />
              </div>

              {links.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    isActive ? 'mobile-nav-item mobile-nav-active' : 'mobile-nav-item'
                  }
                >
                  {link.label}
                </NavLink>
              ))}

              <div className="mobile-nav-divider" />

              {user ? (
                <>
                  <NavLink
                    to="/profile"
                    onClick={() => setOpen(false)}
                    className="mobile-nav-item"
                  >
                    <User size={16} className="text-emerald" />
                    <span>{t('nav.profile')} ({user.display_name || user.email.split('@')[0]})</span>
                  </NavLink>
                  {user.role === 'traveler' && (
                    <NavLink
                      to="/compare"
                      onClick={() => setOpen(false)}
                      className="mobile-nav-item"
                    >
                      <GitCompare size={16} className="text-cyan" />
                      <span>{t('nav.compare')}</span>
                    </NavLink>
                  )}
                  <button
                    type="button"
                    className="mobile-nav-item text-rose"
                    onClick={handleLogout}
                  >
                    <LogOut size={16} />
                    <span>{t('nav.logout')}</span>
                  </button>
                </>
              ) : (
                <div className="mobile-guest-buttons">
                  <NavLink
                    to="/login"
                    onClick={() => setOpen(false)}
                    className="btn-secondary-3d w-full text-center"
                  >
                    {t('nav.login')}
                  </NavLink>
                  <NavLink
                    to="/register"
                    onClick={() => setOpen(false)}
                    className="btn-primary-3d w-full text-center"
                  >
                    {t('nav.register')}
                  </NavLink>
                </div>
              )}
            </div>
          </div>
        )}
      </header>
      </div>

      {/* Main Content Area */}
      <main className="main-content-3d">
        <EmailVerificationBanner />
        <JourneyBar />
        <Outlet />
      </main>

      {/* Modern Footer */}
      <footer className="site-footer-3d">
        <div className="footer-wrap">
          <div className="footer-top">
            <div className="footer-brand-col">
              <NavLink to="/" className="footer-brand-title">
                <img src="/logo-icon.png" alt="Local Explorer AI" className="footer-logo-img" />
                <span>Local Explorer AI</span>
              </NavLink>
              <p className="footer-desc">
                {t('footer.desc')}
              </p>
              <div className="footer-live-status">
                <span className="live-dot-glow" />
                <span>{t('footer.onlineStatus')}</span>
              </div>
              <div className="footer-coords">
                <MapPin size={13} className="text-amber" />
                <span>{t('footer.coords')}</span>
              </div>
            </div>

            <div className="footer-links-col">
              <span className="footer-col-title">{t('footer.colExplore')}</span>
              {loading ? null : (!user || user.role === 'traveler') ? (
                <>
                  <NavLink to="/explore">{t('nav.explore')}</NavLink>
                  <NavLink to="/planner">{t('nav.planner')}</NavLink>
                  <NavLink to="/provider">{t('nav.provider')}</NavLink>
                  <NavLink to="/about">{t('nav.about')}</NavLink>
                  {user && <NavLink to="/compare">{t('nav.compare')}</NavLink>}
                </>
              ) : (
                <NavLink to={user.role === 'admin' ? '/admin' : '/provider-portal'}>
                  {user.role === 'admin' ? t('nav.admin') : t('nav.providerPortal')}
                </NavLink>
              )}
            </div>

            <div className="footer-links-col">
              <span className="footer-col-title">{t('footer.colPolicy')}</span>
              <div className="footer-policy-item">
                <CheckCircle2 size={14} className="text-emerald" />
                <span>{t('footer.noHallucination')}</span>
              </div>
              <div className="footer-policy-item">
                <CheckCircle2 size={14} className="text-emerald" />
                <span>{t('footer.timeTransparency')}</span>
              </div>
              <div className="footer-policy-item">
                <CheckCircle2 size={14} className="text-emerald" />
                <span>{t('footer.noMiddleman')}</span>
              </div>
              <div className="footer-policy-item">
                <CheckCircle2 size={14} className="text-emerald" />
                <span>{t('footer.instantSpeed')}</span>
              </div>
            </div>
          </div>

          <div className="footer-bottom">
            <span>{t('footer.copyright')}</span>
            <div className="footer-credits">
              <span>{t('footer.builtWith')} <Heart size={12} className="inline text-rose-500 fill-rose-500" /></span>
              <span className="footer-version-tag">{t('footer.version')}</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
