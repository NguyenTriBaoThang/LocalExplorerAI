import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  Search,
  Calendar,
  Clock,
  Users,
  Wallet,
  Sparkles,
  MapPin,
  RotateCcw,
  SlidersHorizontal,
  Zap,
} from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiErrorMessage, getExperiences, searchExperiences } from '../api/client'
import { ExperienceCard } from '../components/experience/ExperienceCard'
import { MapAdapter } from '../components/map/MapAdapter'
import { SimulatedBadge, VerificationBadge } from '../components/common/StatusBadge'
import type { Experience } from '../types'
import { useTranslation } from '../i18n'
import { trackPageView } from '../analytics'
import { ReviewsPanel } from '../components/content/ReviewsPanel'

const topicSuggestions = [
  'cà phê',
  'làm gốm',
  'giấy dó',
  'cơm niêu',
  'sông Sài Gòn',
  'bảo tàng',
  'thảo mộc',
]

const localToday = () =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date())
const localTomorrow = () => {
  const date = new Date(`${localToday()}T12:00:00+07:00`)
  date.setUTCDate(date.getUTCDate() + 1)
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(date)
}

export function ExplorePage() {
  const { t, locale } = useTranslation()
  const [searchParams] = useSearchParams()
  const initialIntent = searchParams.get('intent') || ''

  const categories = useMemo(() => [
    { value: '', label: t('explore.allIntents'), icon: '✨' },
    { value: 'food', label: t('explore.intentFood'), icon: '🍜' },
    { value: 'handicraft', label: t('explore.intentCraft'), icon: '🎨' },
    { value: 'culture', label: t('explore.intentCulture'), icon: '🏛️' },
    { value: 'nature', label: t('explore.intentNature'), icon: '🌿' },
    { value: 'relaxation', label: t('explore.intentRelax'), icon: '🍵' },
  ], [t])

  const [items, setItems] = useState<Experience[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [intent, setIntent] = useState(initialIntent)
  const [date, setDate] = useState(localTomorrow())
  const [time, setTime] = useState('09:00')
  const [groupSize, setGroupSize] = useState(2)
  const [budget, setBudget] = useState(2000000)
  const [indoor, setIndoor] = useState('all')
  const [topic, setTopic] = useState('')
  const [radiusKm, setRadiusKm] = useState(15)
  const [slotId, setSlotId] = useState('')
  const [semantic, setSemantic] = useState(false)
  // Place filters from the portal's place data; applied in the browser to the experiences already returned.
  const [landmarkOnly, setLandmarkOnly] = useState(false)
  const [placeTag, setPlaceTag] = useState('')
  const [selectedId, setSelectedId] = useState(searchParams.get('focus') || '')
  // A deliberate pick counts as a view of that experience (partner statistics); the automatic first pick does not.
  const selectExperience = (id: string) => {
    setSelectedId(id)
    trackPageView('/explore', { entity_type: 'experience', entity_id: id })
  }
  const [showAdvanced, setShowAdvanced] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    const from = new Date(`${date}T${time}:00+07:00`).toISOString()
    const to = new Date(`${date}T23:59:59+07:00`).toISOString()

    const params = {
      ...(intent ? { intent } : {}),
      ...(topic ? { topic } : {}),
      ...(indoor !== 'all' ? { is_indoor: indoor === 'indoor' } : {}),
      start_at: from,
      end_at: to,
      group_size: groupSize,
      max_price: Math.floor(budget / groupSize),
      max_distance_km: radiusKm,
      center_latitude: 10.7769,
      center_longitude: 106.7009,
      ...(slotId ? { slot_id: slotId } : {}),
    }
    const request =
      semantic && search.trim().length >= 2
        ? searchExperiences(search.trim(), params, true)
        : getExperiences({ ...params, ...(search.trim() ? { query: search.trim() } : {}) })
    request
      .then((data) => {
        if (active) {
          setItems(data)
          setSelectedId((current) =>
            data.some((item) => item.id === current) ? current : data[0]?.id || ''
          )
        }
      })
      .catch((reason: unknown) => {
        if (active) setError(apiErrorMessage(reason))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [intent, date, time, groupSize, budget, indoor, topic, radiusKm, slotId, semantic, search])

  const visible = useMemo(
    () =>
      items.filter(
        (item) =>
          (!landmarkOnly || item.poi.is_landmark) &&
          (!placeTag || (item.poi.tags ?? []).includes(placeTag)) &&
          (semantic ||
            !search.trim() ||
            `${item.name} ${item.description} ${item.poi.name}`
              .toLowerCase()
              .includes(search.toLowerCase()))
      ),
    [items, search, semantic, landmarkOnly, placeTag]
  )

  // The most common place tags among the current results (a tag nobody has would only lead to an empty list).
  const placeTags = useMemo(() => {
    const counts = new Map<string, number>()
    items.forEach((item) => (item.poi.tags ?? []).forEach((tag) => counts.set(tag, (counts.get(tag) ?? 0) + 1)))
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([tag]) => tag)
  }, [items])

  const points = visible.map((item, index) => ({
    id: item.id,
    latitude: item.poi.latitude,
    longitude: item.poi.longitude,
    name: item.name,
    category: item.poi.category,
    number: index + 1,
    imageUrl: item.poi.image_urls?.[0],
    priceVnd: item.price_vnd,
    district: item.poi.district,
  }))

  const resetFilters = () => {
    setSearch('')
    setIntent('')
    setDate(localTomorrow())
    setTime('09:00')
    setGroupSize(2)
    setBudget(2000000)
    setIndoor('all')
    setTopic('')
    setRadiusKm(15)
    setSlotId('')
    setSemantic(false)
    setLandmarkOnly(false)
    setPlaceTag('')
  }

  const activeAdvancedCount =
    (indoor !== 'all' ? 1 : 0) +
    (topic ? 1 : 0) +
    (radiusKm !== 15 ? 1 : 0) +
    (slotId ? 1 : 0) +
    (semantic ? 1 : 0) +
    (landmarkOnly ? 1 : 0) +
    (placeTag ? 1 : 0)

  return (
    <div className="explore-page-3d page-wrap">
      {/* Title & Banner */}
      <div className="page-title-row-3d">
        <div>
          <span className="eyebrow-3d">
            <span className="eyebrow-dot" /> {t('explore.eyebrow')}
          </span>
          <h1 className="page-heading-3d">
            {t('explore.headingMain')} <em>{t('explore.headingHighlight')}</em>
          </h1>
          <p className="page-subtext-3d">
            {t('explore.headingLead')}
          </p>
        </div>
        <div className="title-extra-badges">
          {items.some((item) => item.data_mode !== 'real') && <SimulatedBadge />}
          {items.some((item) => item.data_mode === 'real') && <VerificationBadge status="verified" />}
        </div>
      </div>

      {/* Category Pills Strip */}
      <div className="category-pills-strip">
        {categories.map((cat) => (
          <button
            key={cat.value}
            type="button"
            className={`cat-pill-btn ${intent === cat.value ? 'cat-pill-active' : ''}`}
            onClick={() => setIntent(cat.value)}
          >
            <span>{cat.icon}</span>
            <span>{cat.label}</span>
          </button>
        ))}
      </div>

      {/* Modern Glassmorphic Toolbar */}
      <div className="explore-toolbar-3d">
        <div className="search-box-3d">
          <Search size={18} className="search-icon" />
          <input
            aria-label={t('explore.searchPlaceholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={
              semantic
                ? t('explore.semanticPlaceholder')
                : t('explore.searchPlaceholder')
            }
          />
          {search && (
            <button
              type="button"
              className="clear-search-btn"
              onClick={() => setSearch('')}
              aria-label="Clear search"
            >
              ×
            </button>
          )}
          {semantic && (
            <span className="semantic-active-badge">
              <Zap size={12} /> {t('explore.semanticActive')}
            </span>
          )}
        </div>

        <div className="filter-inputs-group">
          {/* Date Picker */}
          <div className="toolbar-input-card">
            <div className="input-card-label">
              <Calendar size={13} className="text-emerald" />
              <span>{t('explore.dateDepart')}</span>
            </div>
            <input
              type="date"
              aria-label={t('explore.dateDepart')}
              value={date}
              min={localToday()}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>

          {/* Time Picker */}
          <div className="toolbar-input-card">
            <div className="input-card-label">
              <Clock size={13} className="text-amber" />
              <span>{t('explore.timeArrive')}</span>
            </div>
            <input type="time" aria-label={t('explore.timeArrive')} value={time} onChange={(e) => setTime(e.target.value)} />
          </div>

          {/* Group Size */}
          <div className="toolbar-input-card">
            <div className="input-card-label">
              <Users size={13} className="text-cyan" />
              <span>{t('explore.groupLabel')}</span>
            </div>
            <input
              type="number"
              aria-label={t('explore.groupLabel')}
              min={1}
              max={50}
              value={groupSize}
              onChange={(e) => setGroupSize(Math.max(1, Number(e.target.value)))}
            />
          </div>

          {/* Budget */}
          <div className="toolbar-input-card budget-card">
            <div className="input-card-label">
              <Wallet size={13} className="text-emerald" />
              <span>{t('explore.groupBudget')}</span>
            </div>
            <input
              type="number"
              aria-label={t('explore.groupBudget')}
              min={0}
              step={100000}
              value={budget}
              onChange={(e) => setBudget(Math.max(0, Number(e.target.value)))}
            />
          </div>

          <div className="toolbar-actions-pair">
            <button
              type="button"
              className={`advanced-toggle-btn ${showAdvanced || activeAdvancedCount > 0 ? 'advanced-btn-active' : ''}`}
              onClick={() => setShowAdvanced(!showAdvanced)}
              title={t('explore.advancedFilters')}
            >
              <SlidersHorizontal size={16} />
              <span>{t('explore.moreFilters')}</span>
              {activeAdvancedCount > 0 && (
                <span className="advanced-count-bubble">{activeAdvancedCount}</span>
              )}
            </button>

            <button
              type="button"
              className="reset-filters-btn"
              onClick={resetFilters}
              title={t('explore.resetFilters')}
            >
              <RotateCcw size={16} />
            </button>
          </div>
        </div>

        {/* Expandable Advanced Filters Drawer */}
        {showAdvanced && (
          <div className="advanced-filter-panel animate-fadeIn">
            <div className="advanced-filter-row">
              {/* Topic suggestions */}
              <div className="advanced-field-col">
                <label className="adv-label">
                  <span>{t('explore.topicsLabel')}</span>
                  <input
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder={t('explore.topicsPlaceholder')}
                    className="adv-text-input"
                  />
                </label>
                <div className="topic-quick-pills">
                  {topicSuggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className={`topic-pill ${topic === s ? 'topic-pill-active' : ''}`}
                      onClick={() => setTopic(topic === s ? '' : s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              {/* Space: Indoor / Outdoor */}
              <div className="advanced-field-col">
                <label className="adv-label">
                  <span>{t('explore.indoorLabel')}</span>
                </label>
                <div className="segmented-control">
                  <button
                    type="button"
                    className={`seg-btn ${indoor === 'all' ? 'seg-active' : ''}`}
                    onClick={() => setIndoor('all')}
                  >
                    {t('explore.indoorAll')}
                  </button>
                  <button
                    type="button"
                    className={`seg-btn ${indoor === 'indoor' ? 'seg-active' : ''}`}
                    onClick={() => setIndoor('indoor')}
                  >
                    {t('explore.indoorOnly')}
                  </button>
                  <button
                    type="button"
                    className={`seg-btn ${indoor === 'outdoor' ? 'seg-active' : ''}`}
                    onClick={() => setIndoor('outdoor')}
                  >
                    {t('explore.outdoorOnly')}
                  </button>
                </div>
              </div>

              {/* Distance Radius */}
              <div className="advanced-field-col">
                <label className="adv-label">
                  <span>{t('explore.radiusText', { radius: radiusKm })}</span>
                  <input
                    type="range"
                    min={1}
                    max={50}
                    step={1}
                    value={radiusKm}
                    onChange={(e) => setRadiusKm(Number(e.target.value))}
                    className="adv-range-slider"
                  />
                </label>
              </div>

              {/* Place filters: landmarks and tags */}
              <div className="advanced-field-col">
                <label className="adv-label">
                  <span>{locale === 'vi' ? 'Địa điểm' : 'Place'}</span>
                </label>
                <label className="toggle-switch-card">
                  <input type="checkbox" checked={landmarkOnly} onChange={(e) => setLandmarkOnly(e.target.checked)} className="toggle-checkbox" />
                  <div className="toggle-slider" />
                  <span className="toggle-label">{locale === 'vi' ? 'Chỉ danh lam thắng cảnh' : 'Landmarks only'}</span>
                </label>
                {placeTags.length > 0 && (
                  <div className="topic-quick-pills">
                    {placeTags.map((tag) => (
                      <button key={tag} type="button" className={`topic-pill ${placeTag === tag ? 'topic-pill-active' : ''}`} onClick={() => setPlaceTag(placeTag === tag ? '' : tag)}>
                        #{tag}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Semantic E5 Toggle */}
              <div className="advanced-field-col">
                <label className="adv-label">
                  <span>{t('explore.aiVectorTitle')}</span>
                </label>
                <label className="toggle-switch-card">
                  <input
                    type="checkbox"
                    checked={semantic}
                    onChange={(e) => setSemantic(e.target.checked)}
                    className="toggle-checkbox"
                  />
                  <div className="toggle-slider" />
                  <span className="toggle-label">{t('explore.aiVectorModel')}</span>
                </label>
              </div>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="inline-alert-3d">
          <Sparkles size={16} className="text-amber" />
          <span>{error}</span>
          <Link to="/planner" className="alert-link">
            {t('explore.openPlannerAuto')} <ArrowRight size={14} />
          </Link>
        </div>
      )}

      {/* Main Split Layout: Cards + Map */}
      <div className="explore-layout-3d">
        {/* Results List Column */}
        <section className="results-column-3d">
          <div className="results-header-3d">
            <div>
              <span className="results-sub">{t('explore.eyebrow')}</span>
              <strong className="results-count">
                {loading ? t('explore.scanning') : t('explore.resultsCount', { count: visible.length })}
              </strong>
            </div>
            <span className="budget-per-person">
              {t('explore.estPerPerson', { cost: Math.floor(budget / groupSize).toLocaleString('vi-VN') })}
            </span>
          </div>

          <div className="experience-list-3d">
            {loading ? (
              <div className="loading-state-3d">
                <span className="loader-orbit" />
                <p>{t('explore.scanning')}</p>
              </div>
            ) : visible.length > 0 ? (
              visible.map((experience) => (
                <ExperienceCard
                  key={experience.id}
                  experience={experience}
                  selected={selectedId === experience.id}
                  onSelect={() => selectExperience(experience.id)}
                />
              ))
            ) : (
              <div className="empty-state-3d">
                <div className="empty-icon-box">🧭</div>
                <h3>{t('explore.emptyTitle')}</h3>
                <p>
                  {t('explore.emptyDesc')}
                </p>
                <button type="button" className="btn-secondary-3d btn-sm" onClick={resetFilters}>
                  <RotateCcw size={14} /> {t('explore.resetAllFilters')}
                </button>
              </div>
            )}
          </div>
        </section>

        {/* Map Column */}
        <section className="map-column-3d">
          <div className="map-panel-header-3d">
            <div>
              <span className="map-sub">{t('explore.mapSubtitle')}</span>
              <strong className="map-title">{t('explore.mapTitle')}</strong>
            </div>
            <span className="map-poi-counter">
              <MapPin size={13} className="text-emerald" /> {t('explore.anchorPoints', { count: points.length })}
            </span>
          </div>

          <MapAdapter
            points={points}
            selectedId={selectedId}
            onSelect={selectExperience}
            className="explore-map-container"
          />

          {selectedId && <ReviewsPanel experienceId={selectedId} />}

          <div className="map-footer-caption">
            <span className="live-dot-glow" />
            <span>
              {t('explore.mapHint')}
            </span>
          </div>
        </section>
      </div>
    </div>
  )
}
