import { useJourney, useTripField } from '../journey'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
import {
  api,
  apiErrorMessage,
  getExperiences,
  getBehaviorExperimentStatus,
  getRecommendationConsent,
  rankBehaviorExperiences,
  recordRecommendationInteractions,
  searchExperiences,
  type RecommendationInteraction,
} from '../api/client'
import { useAuth } from '../auth'
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

function simulatedPlaceKey(name: string) {
  return name.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[đĐ]/g, 'd').toLocaleLowerCase('vi').replace(/[^a-z0-9]+/g, ' ').trim()
}

function uniqueSimulatedPlaces(items: Experience[]) {
  const unique: Experience[] = []
  for (const item of items) {
    const key = simulatedPlaceKey(item.poi.name)
    const duplicateIndex = unique.findIndex((existing) => {
      if (simulatedPlaceKey(existing.poi.name) !== key) return false
      const meanLatitude = (existing.poi.latitude + item.poi.latitude) / 2
      const distanceM = Math.hypot(
        (existing.poi.latitude - item.poi.latitude) * 111_320,
        (existing.poi.longitude - item.poi.longitude) * 111_320 * Math.cos(meanLatitude * Math.PI / 180),
      )
      return distanceM <= 150
    })
    if (duplicateIndex < 0) {
      unique.push(item)
      continue
    }
    const existing = unique[duplicateIndex]
    if (existing.poi.details?.catalog_mode !== 'hcmc_catalog_candidate' && item.poi.details?.catalog_mode === 'hcmc_catalog_candidate') {
      unique[duplicateIndex] = item
    }
  }
  return unique
}

export function ExplorePage() {
  const { t, locale } = useTranslation()
  const { user, loading: authLoading } = useAuth()
  const [searchParams] = useSearchParams()
  const { trip, setTrip } = useJourney()
  const poiId = searchParams.get('poi_id') || ''

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
  const [demoAvailable, setDemoAvailable] = useState(false)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const intent = trip.intents.length === 1 ? trip.intents[0] : ''
  const setIntent = (value: string) => setTrip((current) => ({ ...current, intents: value ? [value] : [] }))
  useEffect(() => {
    const requested = searchParams.get('intent')
    if (requested && ['food', 'handicraft', 'culture', 'nature', 'relaxation'].includes(requested)) setTrip((current) => ({ ...current, intents: [requested] }))
  }, [searchParams, setTrip])
  const [date, setDate] = useTripField('date')
  const [time, setTime] = useTripField('startTime')
  const [groupSize, setGroupSize] = useTripField('groupSize')
  const [budget, setBudget] = useTripField('budget')
  const [landmarkModelId, setLandmarkModelId] = useTripField('modelId')
  const [indoor, setIndoor] = useState('all')
  const [topic, setTopic] = useState('')
  const [radiusKm, setRadiusKm] = useState(15)
  const [slotId, setSlotId] = useState('')
  const [semantic, setSemantic] = useState(false)
  // Place filters from the portal's place data; applied in the browser to the experiences already returned.
  const [landmarkOnly, setLandmarkOnly] = useState(false)
  const [placeTag, setPlaceTag] = useState('')
  const [selectedId, setSelectedId] = useState(searchParams.get('focus') || '')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [recommendationTrackingEnabled, setRecommendationTrackingEnabled] = useState(false)
  const [recommendationPersonalizationEnabled, setRecommendationPersonalizationEnabled] = useState(false)
  const [behaviorRankerAvailable, setBehaviorRankerAvailable] = useState(false)
  const [behaviorRankerEnabled, setBehaviorRankerEnabled] = useState(false)
  const [behaviorRankerApplied, setBehaviorRankerApplied] = useState(false)
  const [behaviorRankerWarning, setBehaviorRankerWarning] = useState('')
  const [behaviorRankerError, setBehaviorRankerError] = useState('')
  const [listRequestId, setListRequestId] = useState('')
  const sentImpressions = useRef(new Set<string>())
  const interactionWriteQueue = useRef<Promise<void>>(Promise.resolve())

  useEffect(() => {
    let active = true
    api.get<{ demo_available: boolean }>('/journey/pilot')
      .then(({ data }) => {
        if (active) setDemoAvailable(data.demo_available)
      })
      .catch(() => {
        if (active) setDemoAvailable(false)
      })
    return () => { active = false }
  }, [])

  const queueInteractionWrite = useCallback((events: RecommendationInteraction[]) => {
    if (!events.length) return interactionWriteQueue.current
    const nextWrite = interactionWriteQueue.current
      .catch(() => undefined)
      .then(() => recordRecommendationInteractions(events))
    interactionWriteQueue.current = nextWrite
    return nextWrite
  }, [])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    const requestId = globalThis.crypto.randomUUID()

    if (!trip.demo && (!date || !time || !trip.endTime || time >= trip.endTime)) {
      setItems([])
      setLoading(false)
      setError('Chọn ngày và khung giờ hợp lệ; giờ về phải sau giờ bắt đầu.')
      return
    }
    const params = {
      scope: trip.demo ? 'citywide' : 'pilot',
      verified_only: !trip.demo,
      ...(!trip.demo ? {
        start_at: new Date(`${date}T${time}:00+07:00`).toISOString(),
        end_at: new Date(`${date}T${trip.endTime}:00+07:00`).toISOString(),
        group_size: groupSize,
        total_budget_vnd: budget,
        max_distance_km: radiusKm,
        center_latitude: 10.779785,
        center_longitude: 106.699018,
        ...(slotId ? { slot_id: slotId } : {}),
        ...(indoor !== 'all' ? { is_indoor: indoor === 'indoor' } : {}),
      } : {}),
      ...(poiId ? { poi_id: poiId } : {}),
      ...(intent ? { intent } : {}),
      ...(topic ? { topic } : {}),
    }
    const timer = window.setTimeout(() => {
      const request =
        semantic && search.trim().length >= 2
          ? searchExperiences(search.trim(), params, true)
          : getExperiences({ ...params, ...(search.trim() ? { query: search.trim() } : {}) })
      request
        .then(async (response) => {
          const data = trip.demo
            ? uniqueSimulatedPlaces(response.filter((item) => item.data_mode === 'simulated'))
            : response
          let ordered = data
          setBehaviorRankerApplied(false)
          setBehaviorRankerError('')
          setBehaviorRankerWarning('')
          if (
            behaviorRankerEnabled &&
            behaviorRankerAvailable &&
            recommendationPersonalizationEnabled &&
            !trip.demo &&
            user?.role === 'traveler' &&
            data.some((item) => item.poi.details?.catalog_mode !== 'hcmc_catalog_candidate')
          ) {
            try {
              const budgetBand = budget < 500000
                ? 'under_500k'
                : budget < 1000000
                  ? '500k_1m'
                  : budget <= 2000000
                    ? '1m_2m'
                    : 'over_2m'
              const response = await rankBehaviorExperiences({
                experience_ids: data
                  .filter((item) => item.poi.details?.catalog_mode !== 'hcmc_catalog_candidate')
                  .slice(0, 100)
                  .map((item) => item.id),
                intent_tags: intent ? [intent] : [],
                budget_band: budgetBand,
                group_size: groupSize,
                center_latitude: 10.7769,
                center_longitude: 106.7009,
              })
              if (!active) return
              const rankedPositions = new Map(
                response.ranked_candidates.map((candidate, index) => [candidate.experience_id, index]),
              )
              ordered = [...data].sort((left, right) =>
                (rankedPositions.get(left.id) ?? Number.MAX_SAFE_INTEGER) -
                (rankedPositions.get(right.id) ?? Number.MAX_SAFE_INTEGER)
              )
              setBehaviorRankerApplied(true)
              setBehaviorRankerWarning(response.warning)
            } catch (reason: unknown) {
              if (!active) return
              setBehaviorRankerError(apiErrorMessage(reason))
            }
          }
          if (active) {
            setItems(ordered)
            setListRequestId(requestId)
            setSelectedId((current) =>
              ordered.some((item) => item.id === current) ? current : ordered[0]?.id || ''
            )
          }
        })
        .catch((reason: unknown) => {
          if (active) setError(apiErrorMessage(reason))
        })
        .finally(() => {
          if (active) setLoading(false)
        })
    }, search.trim() ? 250 : 0)

    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [intent, date, time, groupSize, budget, indoor, topic, radiusKm, slotId, semantic, search,
    behaviorRankerEnabled, behaviorRankerAvailable, recommendationPersonalizationEnabled, user?.role, trip.demo, trip.endTime, poiId])

  useEffect(() => {
    let active = true
    if (authLoading) return () => { active = false }
    if (user?.role !== 'traveler') {
      setRecommendationTrackingEnabled(false)
      setRecommendationPersonalizationEnabled(false)
      setBehaviorRankerAvailable(false)
      setBehaviorRankerEnabled(false)
      return () => { active = false }
    }
    getRecommendationConsent()
      .then((consent) => {
        if (active) {
          setRecommendationPersonalizationEnabled(consent.personalization_enabled)
          if (!consent.personalization_enabled) setBehaviorRankerEnabled(false)
          setRecommendationTrackingEnabled(
            consent.personalization_enabled || consent.model_training_enabled || consent.admin_history_enabled,
          )
        }
      })
      .catch(() => {
        if (active) {
          setRecommendationTrackingEnabled(false)
          setRecommendationPersonalizationEnabled(false)
        }
      })
    getBehaviorExperimentStatus()
      .then((status) => {
        if (active) {
          setBehaviorRankerAvailable(status.available)
          if (!status.available) setBehaviorRankerEnabled(false)
          if (status.warning) setBehaviorRankerWarning(status.warning)
        }
      })
      .catch(() => {
        if (active) setBehaviorRankerAvailable(false)
      })
    return () => { active = false }
  }, [authLoading, user?.id, user?.role])

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
  const interactionContext = useMemo(() => {
    const supportedIntents = new Set(['food', 'handicraft', 'culture', 'nature', 'relaxation'])
    const hour = Number(time.split(':')[0] || 9)
    const budgetBand = budget < 500000
      ? 'under_500k'
      : budget < 1000000
        ? '500k_1m'
        : budget <= 2000000
          ? '1m_2m'
          : 'over_2m'
    return {
      intent_tags: supportedIntents.has(intent) ? [intent] : [],
      budget_band: budgetBand as RecommendationInteraction['context']['budget_band'],
      group_size: groupSize,
      indoor_preference: indoor as RecommendationInteraction['context']['indoor_preference'],
      time_bucket: hour < 12 ? 'morning' as const : hour < 17 ? 'afternoon' as const : 'evening' as const,
    }
  }, [intent, budget, groupSize, indoor, time])

  useEffect(() => {
    if (!recommendationTrackingEnabled || trip.demo || !listRequestId || visible.length === 0) return
    const events: RecommendationInteraction[] = []
    visible
      .filter((experience) => experience.poi.details?.catalog_mode !== 'hcmc_catalog_candidate')
      .slice(0, 100)
      .forEach((experience, position) => {
      const impressionKey = `${listRequestId}:${experience.id}`
      if (sentImpressions.current.has(impressionKey)) return
      sentImpressions.current.add(impressionKey)
      events.push({
        event_id: globalThis.crypto.randomUUID(),
        request_id: listRequestId,
        experience_id: experience.id,
        event_type: 'impression',
        position,
        context: interactionContext,
      })
    })
    if (events.length) void queueInteractionWrite(events).catch(() => undefined)
  }, [recommendationTrackingEnabled, trip.demo, listRequestId, visible, interactionContext, queueInteractionWrite])

  const selectExperience = (experienceId: string) => {
    setSelectedId(experienceId)
    trackPageView('/explore', { entity_type: 'experience', entity_id: experienceId })
    if (!recommendationTrackingEnabled || trip.demo || !listRequestId) return
    const selectedExperience = visible.find((item) => item.id === experienceId)
    if (selectedExperience?.poi.details?.catalog_mode === 'hcmc_catalog_candidate') return
    const position = visible.findIndex((item) => item.id === experienceId)
    void queueInteractionWrite([{
      event_id: globalThis.crypto.randomUUID(),
      request_id: listRequestId,
      experience_id: experienceId,
      event_type: 'selected',
      position: position >= 0 ? position : undefined,
      context: interactionContext,
    }]).catch(() => undefined)
  }

  const points = useMemo(() => {
    const uniquePois = new Map<string, Experience>()
    visible.forEach((item) => {
      if (!uniquePois.has(item.poi.id)) uniquePois.set(item.poi.id, item)
    })
    return [...uniquePois.values()].map((item, index) => ({
      // Keep an experience ID for the existing card-selection interaction,
      // but render one map pin per physical POI instead of stacking duplicates.
      id: item.id,
      placeId: item.poi.id,
      latitude: item.poi.latitude,
      longitude: item.poi.longitude,
      name: item.poi.name,
      category: item.poi.category,
      number: index + 1,
      imageUrl: item.poi.details?.images?.find((photo) => (photo.local_url || photo.url) && photo.source_url && photo.license)?.local_url
        || item.poi.details?.images?.find((photo) => photo.url && photo.source_url && photo.license)?.url,
      priceVnd: trip.demo ? undefined : item.price_vnd,
      district: item.poi.district,
    }))
  }, [visible, trip.demo])

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
          <p className="page-subtext-3d" role="note">
            {trip.demo
              ? (locale === 'en'
                ? 'Simulation: browsing Ho Chi Minh City places from the previous project. Location, details, prices and hours are unverified; time, schedule, group, distance, budget and indoor/outdoor filters are not applied. These listings cannot be booked.'
                : 'Chế độ mô phỏng: xem địa điểm TP.HCM từ dự án cũ. Vị trí, thông tin, giá và giờ mở cửa chưa được xác minh; bộ lọc giờ, lịch, số người, khoảng cách, ngân sách và trong/ngoài trời không áp dụng. Các mục này không đặt chỗ được.')
              : (locale === 'en'
                ? 'District 1 pilot. Filters use your shared trip time, group and total budget. The planner also checks travel and the return leg.'
                : 'Pilot Quận 1. Bộ lọc dùng thời gian, số người và tổng ngân sách của hành trình. Planner sẽ kiểm tra thêm thời gian di chuyển và chặng về.')}
          </p>
        </div>
        <div className="title-extra-badges">
          <span className="pilot-scope-badge"><MapPin size={13} /> {trip.demo
            ? (locale === 'en' ? 'Ho Chi Minh City · simulated places' : 'TP.HCM · địa điểm mô phỏng')
            : (locale === 'en' ? 'District 1 · heritage pilot' : 'Quận 1 · pilot di sản')}</span>
          {items.some((item) => item.data_mode !== 'real') && <SimulatedBadge />}
          {items.some((item) => item.data_mode === 'real') && <VerificationBadge status="verified" />}
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-4 text-sm">
        <label>Giờ về <input type="time" value={trip.endTime} onChange={(event) => setTrip((current) => ({ ...current, endTime: event.target.value }))} /></label>
        {poiId && <Link to="/explore" className="underline">Bỏ lọc địa danh · Xem toàn pilot</Link>}
        <Link to="/planner" className="font-semibold text-emerald-700 underline">Tạo lịch trình với {trip.selected.length} trải nghiệm đã chọn →</Link>
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
            {behaviorRankerAvailable && user?.role === 'traveler' && (
              <button
                type="button"
                className={`advanced-toggle-btn ${behaviorRankerEnabled ? 'advanced-btn-active' : ''}`}
                disabled={!recommendationPersonalizationEnabled || loading}
                onClick={() => setBehaviorRankerEnabled((enabled) => !enabled)}
                title={t('explore.behaviorModelTitle')}
              >
                <Sparkles size={15} />
                <span>{behaviorRankerEnabled ? t('explore.behaviorModelOn') : t('explore.behaviorModelOff')}</span>
              </button>
            )}
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

        {behaviorRankerAvailable && user?.role === 'traveler' && (behaviorRankerEnabled || !recommendationPersonalizationEnabled) && (
          <div role="status" className="behavior-model-note" style={{ marginTop: 10, fontSize: 12 }}>
            {behaviorRankerEnabled && (behaviorRankerApplied
              ? t('explore.behaviorModelActive')
              : behaviorRankerError || behaviorRankerWarning || t('explore.behaviorModelPreparing'))}
            {!recommendationPersonalizationEnabled && (
              <> {' '}<Link to="/profile">{t('explore.behaviorModelConsentLink')}</Link></>
            )}
          </div>
        )}

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
                  <span>{t('explore.radiusText', { radius: radiusKm })} · từ Nhà thờ Đức Bà</span>
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
              {trip.demo
                ? (locale === 'en' ? 'Price and budget unverified' : 'Giá và ngân sách chưa xác minh')
                : t('explore.estPerPerson', { cost: Math.floor(budget / groupSize).toLocaleString('vi-VN') })}
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
                <p>{demoAvailable && !trip.demo ? t('explore.demoEmptyDesc') : t('explore.emptyDesc')}</p>
                {demoAvailable && !trip.demo && (
                  <button
                    type="button"
                    className="btn-secondary-3d btn-sm"
                    onClick={() => setTrip((current) => ({
                      ...current,
                      demo: true,
                      selected: [],
                      lockedPois: [],
                      originId: '',
                      destinationId: '',
                    }))}
                  >
                    <Sparkles size={14} /> {t('explore.enableDemo')}
                  </button>
                )}
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
            webgl3d
            selectedLandmarkId={landmarkModelId}
            onLandmarkChange={setLandmarkModelId}
          />

          {selectedId && <ReviewsPanel experienceId={selectedId} />}

          <div className="map-footer-caption">
            <span className="live-dot-glow" />
            <span>
              {trip.demo
                ? (locale === 'en' ? 'Map points are simulated and are not confirmed for visits or booking.' : 'Điểm trên bản đồ dùng để mô phỏng, chưa xác nhận để tham quan hoặc đặt chỗ.')
                : t('explore.mapHint')}
            </span>
          </div>
        </section>
      </div>
    </div>
  )
}
