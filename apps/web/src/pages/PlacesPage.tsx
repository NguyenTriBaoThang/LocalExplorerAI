import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowUpRight,
  Compass,
  MapPin,
  Search,
  X,
  ShieldCheck,
  Building2,
} from 'lucide-react'
import { getPOIs } from '../api/client'
import { useTranslation } from '../i18n'
import type { POI } from '../types'

// The catalogue mixes the older English intents (food, culture, ...) with the Vietnamese OSM groups (an-uong, tham-quan, ...);
// each tab lists every category id it covers so no place falls outside the filter.
const CATEGORY_TABS = [
  { id: 'all', icon: '✨', ids: [] as string[] },
  { id: 'an-uong', icon: '🍜', ids: ['an-uong', 'food'] },
  { id: 'cafe', icon: '☕', ids: ['cafe'] },
  { id: 'tham-quan', icon: '🏛️', ids: ['tham-quan', 'culture', 'heritage', 'local_life'] },
  { id: 'giai-tri', icon: '🎭', ids: ['giai-tri'] },
  { id: 'cho-o', icon: '🏨', ids: ['cho-o', 'accommodation'] },
  { id: 'handicraft', icon: '🎨', ids: ['handicraft'] },
  { id: 'nature', icon: '🌿', ids: ['nature'] },
  { id: 'relaxation', icon: '🍵', ids: ['relaxation'] },
]

const CATEGORY_META: Record<string, { icon: string }> = {
  'an-uong': { icon: '🍜' },
  food: { icon: '🍜' },
  cafe: { icon: '☕' },
  'tham-quan': { icon: '🏛️' },
  culture: { icon: '🏛️' },
  heritage: { icon: '🏛️' },
  local_life: { icon: '🏛️' },
  accommodation: { icon: '🏨' },
  'giai-tri': { icon: '🎭' },
  'cho-o': { icon: '🏨' },
  handicraft: { icon: '🎨' },
  nature: { icon: '🌿' },
  relaxation: { icon: '🍵' },
}

/** Imported descriptions say "thuộc nhóm an-uong"; show the category's label instead of its slug. */
const humanizeDescription = (text: string, label: (slug: string) => string, group: string) =>
  text.replace(/thuộc nhóm ([a-z-]+)/g, (match, slug: string) => (CATEGORY_META[slug] ? `${group} ${label(slug).toLowerCase()}` : match))

const inTab = (category: string, tabId: string) =>
  tabId === 'all' || (CATEGORY_TABS.find((tab) => tab.id === tabId)?.ids ?? []).includes(category)

export function PlacesPage() {
  const { t } = useTranslation()
  const catLabel = (slug: string) => t(`places.meta.${({ heritage: 'culture', local_life: 'tham-quan', accommodation: 'cho-o' } as Record<string, string>)[slug] ?? slug}`)
  const [places, setPlaces] = useState<POI[]>([])
  const [query, setQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getPOIs('citywide')
      .then(setPlaces)
      .catch(() => setError(t('places.loadError')))
      .finally(() => setLoading(false))
  }, [])

  const filteredPlaces = useMemo(() => {
    let list = places
    if (selectedCategory !== 'all') {
      list = list.filter((p) => inTab(p.category, selectedCategory))
    }
    const val = query.trim().toLocaleLowerCase('vi')
    if (val) {
      list = list.filter((p) =>
        `${p.name} ${p.address} ${p.category} ${p.description}`
          .toLocaleLowerCase('vi')
          .includes(val)
      )
    }
    return list
  }, [places, selectedCategory, query])

  return (
    <div className="page-wrap places-page">
      {/* Hero Header */}
      <header className="places-page-header">
        <div className="flex items-center gap-2 mb-2">
          <span className="eyebrow-3d">
            <span className="eyebrow-dot" /> {t('places.eyebrow')}
          </span>
          <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider">
            {t('places.pilot')}
          </span>
        </div>

        <h1 className="page-heading-3d">
          {t('places.titleA')} <em>{t('places.titleB')}</em> {t('places.titleC')}
        </h1>
        <p className="page-subtext-3d">
          {places.length > 0 ? t('places.sub', { count: places.length }) : t('places.subNoCount')}
        </p>

        {/* Live Metrics Row */}
        <div className="places-stats-row">
          <div className="places-stat-pill">
            <Building2 size={13} className="text-emerald-400" />
            <span><strong>{places.length || 0}</strong> {t('places.statCatalog')}</span>
          </div>
          <div className="places-stat-pill">
            <Compass size={13} className="text-cyan-400" />
            <span><strong>{places.filter((place) => place.details?.catalog_mode === 'hcmc_catalog_candidate').length}</strong> {t('places.statCandidates')}</span>
          </div>
          <div className="places-stat-pill">
            <ShieldCheck size={13} className="text-amber-400" />
            <span>{t('places.statLicense')}</span>
          </div>
        </div>
      </header>

      {/* Filter and Search Bar Section */}
      <div className="places-controls-bar">
        {/* Category Tabs */}
        <div className="places-category-tabs">
          {CATEGORY_TABS.map((cat) => {
            const active = selectedCategory === cat.id
            const count = places.filter((p) => inTab(p.category, cat.id)).length
            if (cat.id !== 'all' && count === 0 && !active) return null

            return (
              <button
                key={cat.id}
                type="button"
                onClick={() => setSelectedCategory(cat.id)}
                className={`places-cat-btn ${active ? 'active' : ''}`}
              >
                <span>{cat.icon}</span>
                <span>{t(`places.cat.${cat.id}`)}</span>
                <span className="cat-count-badge">{count}</span>
              </button>
            )
          })}
        </div>

        {/* Search Input Box */}
        <div className="places-search-box">
          <Search size={18} className="search-icon" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('places.searchPlaceholder')}
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              className="search-clear-btn"
              title={t('places.searchClear')} aria-label={t('places.searchClear')}
            >
              <X size={15} />
            </button>
          )}
        </div>
      </div>

      {error && <div className="inline-alert-3d mb-6">{error}</div>}

      {/* Results Header */}
      <div className="places-results-meta">
        <span>
          {t('places.showing', { count: filteredPlaces.length })}
          {selectedCategory !== 'all' && ` · ${t(`places.cat.${selectedCategory}`)}`}
          {query && ` ${t('places.forKeyword', { query })}`}
        </span>
        {query && (
          <button
            type="button"
            onClick={() => { setQuery(''); setSelectedCategory('all') }}
            className="text-xs text-emerald-400 hover:underline"
          >
            {t('places.reset')}
          </button>
        )}
      </div>

      {loading ? (
        <div className="places-loading-box">
          <div className="places-spinner" />
          <p>{t('places.loading')}</p>
        </div>
      ) : filteredPlaces.length > 0 ? (
        <div className="places-grid-elevated">
          {filteredPlaces.map((place) => {
            const sourcePhoto = place.details?.images?.find(
              (item) => (item.local_url || item.url) && item.source_url && item.license
            )
            const photoUrl =
              (sourcePhoto && (sourcePhoto.local_url || sourcePhoto.url)) ||
              place.image_urls?.[0] ||
              null

            const catInfo = {
              icon: CATEGORY_META[place.category]?.icon ?? '📍',
              label: CATEGORY_META[place.category] ? catLabel(place.category) : place.category,
            }

            return (
              <Link
                className="place-card-elevated group"
                data-category={place.category}
                to={`/places/${encodeURIComponent(place.id)}`}
                key={place.id}
              >
                <div className="place-card-photo-box" data-category={place.category} data-has-photo={photoUrl ? 'true' : 'false'}>
                  {photoUrl ? (
                    <img
                      src={photoUrl}
                      alt={place.name}
                      loading="lazy"
                      className="place-card-img"
                      onError={(e) => {
                        const img = e.currentTarget
                        img.style.display = 'none'
                        img.parentElement?.setAttribute('data-has-photo', 'false')
                        const fallback = img.parentElement?.querySelector('.place-card-fallback') as HTMLElement
                        if (fallback) fallback.style.display = 'flex'
                      }}
                    />
                  ) : null}

                  <div
                    className="place-card-fallback"
                    style={{ display: photoUrl ? 'none' : 'flex' }}
                  >
                    <span className="text-3xl mb-1">{catInfo.icon}</span>
                    <span className="text-xs font-semibold text-slate-300">{catInfo.label}</span>
                  </div>

                  <div className="place-card-gradient-overlay" />
                  {sourcePhoto && (
                    <span className="card-photo-credit" title={`${sourcePhoto.attribution || sourcePhoto.credit_line || sourcePhoto.title} · ${sourcePhoto.license}`}>
                      {sourcePhoto.attribution || sourcePhoto.credit_line || sourcePhoto.title} · {sourcePhoto.license}
                    </span>
                  )}

                  {/* Top Badges */}
                  <div className="place-card-top-badges">
                    <span className="place-cat-pill">
                      <span>{catInfo.icon}</span> {catInfo.label}
                    </span>
                    <span className="place-action-circle">
                      <ArrowUpRight size={14} />
                    </span>
                  </div>

                  {/* Bottom Badges */}
                  <div className="place-card-bottom-badges">
                    <span className="place-district-pill">
                      <MapPin size={11} /> {place.district || t('places.defaultDistrict')}
                    </span>
                    {place.verification_status === 'verified' && (
                      <span className="place-verified-pill">
                        <ShieldCheck size={11} /> {t('places.verified')}
                      </span>
                    )}
                    {place.details?.catalog_mode === 'hcmc_catalog_candidate' && (
                      <span className="place-verified-pill place-candidate-pill" title={t('places.candidateHint')}>
                        {t('places.candidate')}
                      </span>
                    )}
                  </div>
                </div>

                <div className="place-card-body-content">
                  <h3 className="place-card-title group-hover:text-emerald-400 transition-colors">
                    {place.name}
                  </h3>

                  <p className="place-card-address">
                    <MapPin size={12} className="place-address-icon shrink-0 text-emerald-400 mt-0.5" />
                    <span>{place.address || t('places.defaultAddress')}</span>
                  </p>

                  {place.description && (
                    <p className="place-card-desc">
                      {humanizeDescription(place.description, catLabel, t('places.group'))}
                    </p>
                  )}

                  <div className="place-card-footer">
                    <span className="place-card-cta">
                      {t('places.viewDetail')} <ArrowUpRight size={13} />
                    </span>
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      ) : (
        <div className="places-empty-box">
          <div className="empty-icon-wrap">
            <Search size={32} />
          </div>
          <h3>{t('places.emptyTitle')}</h3>
          <p>{t('places.emptyHint')}</p>
          <button
            type="button"
            onClick={() => { setQuery(''); setSelectedCategory('all') }}
            className="btn-reset-search"
          >
            {t('places.viewAll', { count: places.length })}
          </button>
        </div>
      )}
    </div>
  )
}
