import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  ArrowRight,
  CalendarDays,
  Clock3,
  MapPin,
  Minus,
  Plus,
  Users,
  Wallet,
  Sparkles,
  Navigation,
  CheckCircle2,
  Lock,
  Search,
} from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiErrorMessage, createItinerary, geocodeAddress, getPOIs, getRoutingCapabilities } from '../api/client'
import { TiltCard3D } from '../components/3d/TiltCard3D'
import type { GeocodeResponse, POI, RoutingCapabilities } from '../types'
import { useTranslation } from '../i18n'

const budgetPresets = [500000, 1000000, 2000000, 3500000]

const today = () =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date())
const tomorrow = () => {
  const date = new Date(`${today()}T12:00:00+07:00`)
  date.setUTCDate(date.getUTCDate() + 1)
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(date)
}

export function PlannerPage() {
  const { t, locale } = useTranslation()
  const navigate = useNavigate()

  const intents = useMemo(() => [
    { id: 'food', label: t('home.catFood'), glyph: '🍜', desc: t('home.catFoodDesc') },
    { id: 'handicraft', label: t('home.catCraft'), glyph: '🎨', desc: t('home.catCraftDesc') },
    { id: 'culture', label: t('home.catCulture'), glyph: '🏛️', desc: t('home.catCultureDesc') },
    { id: 'nature', label: t('home.catNature'), glyph: '🌿', desc: t('home.catNatureDesc') },
    {
      id: 'relaxation',
      label: locale === 'en' ? 'Wellness & Relaxation' : 'Thư giãn & Phục hồi',
      glyph: '🍵',
      desc: locale === 'en' ? 'Herbal tea, singing bowls' : 'Trà thảo mộc, chuông xoay Tây Tạng',
    },
  ], [t, locale])

  const transportModes = useMemo(() => [
    { id: 'motorcycle', label: locale === 'en' ? 'Motorcycle' : 'Xe máy', icon: '🛵', note: locale === 'en' ? 'Goong motorcycle profile' : 'Tuyến xe máy từ Goong' },
    { id: 'car', label: locale === 'en' ? 'Car' : 'Ô tô', icon: '🚗', note: locale === 'en' ? 'Goong car profile' : 'Tuyến ô tô từ Goong' },
    { id: 'walking', label: locale === 'en' ? 'Walking' : 'Đi bộ', icon: '🚶', note: locale === 'en' ? 'Goong walking profile' : 'Tuyến đi bộ từ Goong' },
  ], [locale])

  const [date, setDate] = useState(tomorrow())
  const [startTime, setStartTime] = useState('09:00')
  const [endTime, setEndTime] = useState('16:00')
  const [groupSize, setGroupSize] = useState(2)
  const [budget, setBudget] = useState(1200000)
  const [transport, setTransport] = useState('motorcycle')
  const [selectedIntents, setSelectedIntents] = useState<string[]>(['food', 'handicraft'])
  const [pois, setPois] = useState<POI[]>([])
  // Place and experience pages link here with ?poi=<id> so the chosen place is already on the list.
  const [searchParams] = useSearchParams()
  const [lockedPois, setLockedPois] = useState<string[]>(() => searchParams.getAll('poi'))
  const [poiSearch, setPoiSearch] = useState('')
  const [originId, setOriginId] = useState('')
  const [destinationId, setDestinationId] = useState('')
  const [originAddress, setOriginAddress] = useState('')
  const [destinationAddress, setDestinationAddress] = useState('')
  const [originGeocode, setOriginGeocode] = useState<GeocodeResponse | null>(null)
  const [destinationGeocode, setDestinationGeocode] = useState<GeocodeResponse | null>(null)
  const [originResolved, setOriginResolved] = useState<GeocodeResponse['results'][number] | null>(null)
  const [destinationResolved, setDestinationResolved] = useState<GeocodeResponse['results'][number] | null>(null)
  const [geocoding, setGeocoding] = useState<'origin' | 'destination' | null>(null)
  const [routingCapabilities, setRoutingCapabilities] = useState<RoutingCapabilities | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    void getPOIs().then(setPois).catch(() => setPois([]))
    void getRoutingCapabilities().then((capabilities) => {
      setRoutingCapabilities(capabilities)
      setTransport((current) => capabilities.supported_modes.includes(current)
        ? current
        : capabilities.supported_modes[0] || current)
    }).catch(() => undefined)
  }, [])

  const visibleTransportModes = transportModes.filter((mode) =>
    !routingCapabilities || routingCapabilities.supported_modes.includes(mode.id)
  )

  const toggleIntent = (id: string) => {
    setSelectedIntents((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    )
  }

  const toggleLockPoi = (id: string) => {
    setLockedPois((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    )
  }

  const startHour =
    parseInt(startTime.split(':')[0], 10) + parseInt(startTime.split(':')[1], 10) / 60
  const endHour =
    parseInt(endTime.split(':')[0], 10) + parseInt(endTime.split(':')[1], 10) / 60
  const totalHours = Math.max(1, Math.round((endHour - startHour) * 10) / 10)

  const filteredPois = pois.filter((poi) =>
    poi.name.toLowerCase().includes(poiSearch.toLowerCase()) ||
    poi.address.toLowerCase().includes(poiSearch.toLowerCase())
  )

  async function resolveAddress(which: 'origin' | 'destination') {
    const address = which === 'origin' ? originAddress.trim() : destinationAddress.trim()
    if (address.length < 3) {
      setError(locale === 'en' ? 'Enter at least 3 characters for the address.' : 'Nhập địa chỉ tối thiểu 3 ký tự.')
      return
    }
    setGeocoding(which)
    setError('')
    try {
      const result = await geocodeAddress(address)
      if (which === 'origin') {
        setOriginGeocode(result)
        setOriginResolved(null)
      } else {
        setDestinationGeocode(result)
        setDestinationResolved(null)
      }
      if (result.results.length === 0) {
        setError(locale === 'en' ? 'No address matches were returned. Refine the address.' : 'Không tìm thấy địa chỉ; hãy nhập cụ thể hơn.')
      }
    } catch (reason) {
      setError(apiErrorMessage(reason, locale))
    } finally {
      setGeocoding(null)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const toIso = (value: string) => new Date(`${date}T${value}:00+07:00`).toISOString()
      const origin = pois.find((poi) => poi.id === originId)
      const destination = pois.find((poi) => poi.id === destinationId)
      if (originAddress.trim() && !originResolved) {
        throw new Error(locale === 'en' ? 'Choose a geocoding result for the origin address first.' : 'Hãy tìm và chọn kết quả địa chỉ điểm xuất phát trước.')
      }
      if (destinationAddress.trim() && !destinationResolved) {
        throw new Error(locale === 'en' ? 'Choose a geocoding result for the return address first.' : 'Hãy tìm và chọn kết quả địa chỉ điểm về trước.')
      }
      const originPoint = originResolved ?? origin
      const destinationPoint = destinationResolved ?? destination
      if (!originPoint || !destinationPoint) {
        throw new Error(locale === 'en'
          ? 'Choose both a departure point and a return destination so the route and return deadline can be checked.'
          : 'Hãy chọn cả điểm xuất phát và điểm về để kiểm tra đủ lộ trình và giờ về.')
      }
      const result = await createItinerary({
        start_at: toIso(startTime),
        end_at: toIso(endTime),
        group_size: groupSize,
        budget_vnd: budget,
        transport_mode: transport,
        intent_weights: Object.fromEntries(selectedIntents.map((intent) => [intent, 1])),
        locked_experience_ids: [],
        locked_poi_ids: lockedPois,
        ...(originPoint
          ? {
              origin_latitude: originPoint.latitude,
              origin_longitude: originPoint.longitude,
              origin_label: 'formatted_address' in originPoint ? originPoint.formatted_address : originPoint.name,
            }
          : {}),
        ...(destinationPoint
          ? {
              destination_latitude: destinationPoint.latitude,
              destination_longitude: destinationPoint.longitude,
              destination_label: 'formatted_address' in destinationPoint ? destinationPoint.formatted_address : destinationPoint.name,
            }
          : {}),
      })
      navigate(`/itinerary/${result.itinerary_id}`, { state: { itinerary: result } })
    } catch (reason) {
      setError(apiErrorMessage(reason, locale))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="planner-page-3d page-wrap">
      {/* Page Header */}
      <div className="page-title-row-3d">
        <div>
          <span className="eyebrow-3d">
            <span className="eyebrow-dot" /> {t('planner.eyebrow')}
          </span>
          <h1 className="page-heading-3d">
            {t('planner.headingMain')} <em>{t('planner.headingHighlight')}</em>
          </h1>
          <p className="page-subtext-3d">
            {t('planner.headingLead')}
          </p>
        </div>
        <div className="planner-badge-wrap">
          <span className="planner-city-badge">
            <MapPin size={14} className="text-emerald" />
            {locale === 'en' ? 'Pilot area: District 1' : 'Khu vực pilot: Quận 1'}
          </span>
        </div>
      </div>

      <div className="planner-grid-3d">
        {/* Main Form */}
        <form className="planner-form-3d" onSubmit={submit}>
          {/* Section 01: Thời gian & Nhóm */}
          <div className="form-card-3d">
            <div className="form-card-header">
              <span className="step-num">{t('planner.step1Num')}</span>
              <div>
                <h2>{t('planner.step1Title')}</h2>
                <p>{t('planner.step1Desc')}</p>
              </div>
              <div className="duration-preview-chip">
                <Clock3 size={13} className="text-emerald" />
                <span>
                  {totalHours > 0
                    ? t('planner.durationHours', { hours: totalHours })
                    : t('planner.checkHours')}
                </span>
              </div>
            </div>

            <div className="form-fields-grid-3">
              <label className="field-group-3d">
                <span>
                  <CalendarDays size={14} className="text-emerald" /> {t('planner.dateLabel')}
                </span>
                <input
                  required
                  type="date"
                  value={date}
                  min={today()}
                  onChange={(e) => setDate(e.target.value)}
                />
              </label>

              <label className="field-group-3d">
                <span>
                  <Clock3 size={14} className="text-amber" /> {t('planner.startTime')}
                </span>
                <input
                  required
                  type="time"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                />
              </label>

              <label className="field-group-3d">
                <span>
                  <Clock3 size={14} className="text-amber" /> {t('planner.endTime')}
                </span>
                <input
                  required
                  type="time"
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                />
              </label>
            </div>

            <div className="form-fields-grid-2">
              <div className="field-group-3d">
                <span>
                  <Users size={14} className="text-cyan" /> {t('planner.groupSize')}
                </span>
                <div className="stepper-3d">
                  <button
                    type="button"
                    onClick={() => setGroupSize(Math.max(1, groupSize - 1))}
                    aria-label="Decrease"
                  >
                    <Minus size={15} />
                  </button>
                  <span className="stepper-value">
                    {t('planner.guestsUnit', { count: groupSize })}
                  </span>
                  <button
                    type="button"
                    onClick={() => setGroupSize(Math.min(30, groupSize + 1))}
                    aria-label="Increase"
                  >
                    <Plus size={15} />
                  </button>
                </div>
              </div>

              <div className="field-group-3d">
                <div className="field-label-split">
                  <span>
                    <Wallet size={14} className="text-emerald" /> {t('planner.budget')}
                  </span>
                  <span className="budget-calc-sub">
                    {t('planner.budgetPerPerson', {
                      cost: Math.floor(budget / groupSize).toLocaleString('vi-VN'),
                    })}
                  </span>
                </div>
                <input
                  required
                  type="number"
                  aria-label={t('planner.budget')}
                  min={100000}
                  step={50000}
                  value={budget}
                  onChange={(e) => setBudget(Math.max(0, Number(e.target.value)))}
                />
                <div className="budget-presets-row">
                  {budgetPresets.map((amt) => (
                    <button
                      key={amt}
                      type="button"
                      className={`preset-btn ${budget === amt ? 'preset-active' : ''}`}
                      onClick={() => setBudget(amt)}
                    >
                      {(amt / 1000000).toFixed(amt % 1000000 === 0 ? 0 : 1)}tr
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Section 02: Mục đích trải nghiệm */}
          <div className="form-card-3d">
            <div className="form-card-header">
              <span className="step-num">{t('planner.step2Num')}</span>
              <div>
                <h2>{t('planner.step2Title')}</h2>
                <p>{t('planner.step2Desc')}</p>
              </div>
            </div>

            <div className="intent-selector-grid">
              {intents.map((item) => {
                const active = selectedIntents.includes(item.id)
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`intent-btn-3d ${active ? 'intent-btn-active' : ''}`}
                    onClick={() => toggleIntent(item.id)}
                  >
                    <span className="intent-btn-glyph">{item.glyph}</span>
                    <div className="intent-btn-info">
                      <strong>{item.label}</strong>
                      <small>{item.desc}</small>
                    </div>
                    {active && <CheckCircle2 size={18} className="intent-check-icon" />}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Section 03: Phương tiện di chuyển */}
          <div className="form-card-3d">
            <div className="form-card-header">
              <span className="step-num">{t('planner.step3Num')}</span>
              <div>
                <h2>{t('planner.step3Title')}</h2>
                <p>{t('planner.step3Desc')}</p>
              </div>
            </div>

            <div className="transport-mode-grid">
              {visibleTransportModes.map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  className={`transport-btn-3d ${transport === mode.id ? 'transport-active' : ''}`}
                  onClick={() => setTransport(mode.id)}
                >
                  <span className="transport-icon">{mode.icon}</span>
                  <div>
                    <strong>{mode.label}</strong>
                    <small>{mode.note}</small>
                  </div>
                </button>
              ))}
            </div>
            {routingCapabilities && (
              <p className="routing-provider-note">
                {locale === 'en' ? 'Routing provider' : 'Nhà cung cấp tuyến đường'}: {routingCapabilities.provider}. {routingCapabilities.eta_is_realtime ? (locale === 'en' ? 'Live traffic ETA.' : 'ETA giao thông thời gian thực.') : (locale === 'en' ? 'ETAs are estimates, not live traffic.' : 'ETA là ước tính, không phải giao thông thời gian thực.')}
                {!routingCapabilities.configured && ` · ${locale === 'en' ? 'Routing provider is not configured' : 'Chưa cấu hình nhà cung cấp tuyến đường'}`}
                {routingCapabilities.geocoding_configured === false && ` · ${locale === 'en' ? `Geocoding provider/key unavailable (${routingCapabilities.geocoding_provider})` : `Nhà cung cấp/khóa geocoding chưa sẵn sàng (${routingCapabilities.geocoding_provider})`}`}
              </p>
            )}
          </div>

          {/* Section 04: Điểm xuất phát, Điểm về & Khóa POI */}
          <div className="form-card-3d">
            <div className="form-card-header">
              <span className="step-num">{t('planner.step4Num')}</span>
              <div>
                <h2>{t('planner.step4Title')}</h2>
                <p>{t('planner.step4Desc')}</p>
              </div>
            </div>

            <div className="form-fields-grid-2">
              <div className="field-group-3d">
                <span>
                  <MapPin size={14} className="text-emerald" /> {t('planner.originLabel')}
                </span>
                <select aria-label={locale === 'en' ? 'Start point' : 'Điểm xuất phát'} value={originId} onChange={(e) => {
                  setOriginId(e.target.value)
                  setOriginAddress('')
                  setOriginResolved(null)
                  setOriginGeocode(null)
                }}>
                  <option value="">{t('planner.originDefault')}</option>
                  {pois.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <div className="address-resolve-row">
                  <input aria-label={locale === 'en' ? 'Start address' : 'Địa chỉ xuất phát'} value={originAddress} placeholder={locale === 'en' ? 'Or enter a street address' : 'Hoặc nhập địa chỉ'} onChange={(event) => {
                    setOriginAddress(event.target.value)
                    setOriginId('')
                    setOriginResolved(null)
                    setOriginGeocode(null)
                  }} />
                  <button type="button" className="btn-geocode" disabled={geocoding !== null} onClick={() => void resolveAddress('origin')}>
                    <Search size={14} /> {geocoding === 'origin' ? (locale === 'en' ? 'Searching…' : 'Đang tìm…') : (locale === 'en' ? 'Find' : 'Tìm')}
                  </button>
                </div>
                {originGeocode?.results.map((result) => (
                  <button type="button" className={`address-result-item ${originResolved?.place_id === result.place_id ? 'address-result-active' : ''}`} key={result.place_id || `${result.latitude},${result.longitude}`} onClick={() => setOriginResolved(result)}>
                    {result.formatted_address}
                  </button>
                ))}
                {originResolved && originGeocode && <small className="address-source-note">{originGeocode.provider} · {locale === 'en' ? 'age' : 'tuổi'} {originGeocode.age_seconds}s · {locale === 'en' ? 'valid until' : 'hạn'} {new Date(originGeocode.valid_until).toLocaleTimeString(locale === 'en' ? 'en-US' : 'vi-VN')} · <a href={originGeocode.source_uri} target="_blank" rel="noreferrer">{locale === 'en' ? 'source' : 'nguồn'}</a></small>}
              </div>

              <div className="field-group-3d">
                <span>
                  <MapPin size={14} className="text-amber" /> {t('planner.destinationLabel')}
                </span>
                <select aria-label={locale === 'en' ? 'End point' : 'Điểm kết thúc'} value={destinationId} onChange={(e) => {
                  setDestinationId(e.target.value)
                  setDestinationAddress('')
                  setDestinationResolved(null)
                  setDestinationGeocode(null)
                }}>
                  <option value="">{t('planner.destDefault')}</option>
                  {pois.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <div className="address-resolve-row">
                  <input aria-label={locale === 'en' ? 'End address' : 'Địa chỉ điểm về'} value={destinationAddress} placeholder={locale === 'en' ? 'Or enter a return address' : 'Hoặc nhập địa chỉ điểm về'} onChange={(event) => {
                    setDestinationAddress(event.target.value)
                    setDestinationId('')
                    setDestinationResolved(null)
                    setDestinationGeocode(null)
                  }} />
                  <button type="button" className="btn-geocode" disabled={geocoding !== null} onClick={() => void resolveAddress('destination')}>
                    <Search size={14} /> {geocoding === 'destination' ? (locale === 'en' ? 'Searching…' : 'Đang tìm…') : (locale === 'en' ? 'Find' : 'Tìm')}
                  </button>
                </div>
                {destinationGeocode?.results.map((result) => (
                  <button type="button" className={`address-result-item ${destinationResolved?.place_id === result.place_id ? 'address-result-active' : ''}`} key={result.place_id || `${result.latitude},${result.longitude}`} onClick={() => setDestinationResolved(result)}>
                    {result.formatted_address}
                  </button>
                ))}
                {destinationResolved && destinationGeocode && <small className="address-source-note">{destinationGeocode.provider} · {locale === 'en' ? 'age' : 'tuổi'} {destinationGeocode.age_seconds}s · {locale === 'en' ? 'valid until' : 'hạn'} {new Date(destinationGeocode.valid_until).toLocaleTimeString(locale === 'en' ? 'en-US' : 'vi-VN')} · <a href={destinationGeocode.source_uri} target="_blank" rel="noreferrer">{locale === 'en' ? 'source' : 'nguồn'}</a></small>}
              </div>
            </div>

            {/* POI Locking Section with Card Selection */}
            <div className="poi-lock-section">
              <div className="poi-lock-header">
                <div className="poi-lock-title-col">
                  <span className="poi-lock-label">
                    <Lock size={14} className="text-cyan" /> {t('planner.pinTitle')}
                  </span>
                  <small>
                    {t('planner.pinDesc')}
                  </small>
                </div>
                {pois.length > 6 && (
                  <div className="poi-search-box-mini">
                    <Search size={14} />
                    <input
                      placeholder={t('planner.searchPoiPlaceholder')}
                      value={poiSearch}
                      onChange={(e) => setPoiSearch(e.target.value)}
                    />
                  </div>
                )}
              </div>

              <div className="poi-lock-cards-grid">
                {filteredPois.slice(0, 8).map((poi) => {
                  const locked = lockedPois.includes(poi.id)
                  return (
                    <button
                      key={poi.id}
                      type="button"
                      className={`poi-lock-card ${locked ? 'poi-locked-active' : ''}`}
                      onClick={() => toggleLockPoi(poi.id)}
                    >
                      <div className="poi-lock-status">
                        {locked ? (
                          <CheckCircle2 size={16} className="text-emerald" />
                        ) : (
                          <span className="poi-lock-empty-dot" />
                        )}
                      </div>
                      <div className="poi-lock-info">
                        <strong>{poi.name}</strong>
                        <small>{poi.address}</small>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          </div>

          {error && <div className="form-alert-3d">{error}</div>}

          {/* Submit Row */}
          <div className="submit-action-card">
            <div className="submit-summary-text">
              <strong>
                {t('planner.submitSummary', { intents: selectedIntents.length, group: groupSize })}
              </strong>
              <small>{t('planner.submitEngine')}</small>
            </div>
            <button className="btn-planner-submit" type="submit" disabled={loading}>
              <span>{loading ? t('planner.planning') : t('planner.submitBtn')}</span>
              <ArrowRight size={18} />
            </button>
          </div>
        </form>

        {/* Right Column: 3D Interactive Live Preview Card */}
        <aside className="planner-aside-3d">
          <TiltCard3D maxTilt={8} className="live-preview-card-3d">
            <div className="preview-card-header">
              <div className="preview-icon-box">
                <img src="/logo-icon.png" alt="Local Explorer AI" className="brand-logo-img" />
              </div>
              <div>
                <span className="preview-kicker">{t('planner.previewKicker')}</span>
                <h3 className="preview-main-title">{t('planner.previewMainTitle')}</h3>
              </div>
            </div>

            <div className="preview-stats-bar">
              <div className="preview-stat-cell">
                <small>{t('planner.previewDuration')}</small>
                <strong>
                  {totalHours > 0
                    ? `${totalHours} ${locale === 'en' ? 'hrs' : 'giờ'}`
                    : t('planner.checkHours')}
                </strong>
              </div>
              <div className="preview-stat-cell">
                <small>{t('planner.previewEst')}</small>
                <strong>~{Math.floor(budget / groupSize).toLocaleString('vi-VN')}₫</strong>
                <span className="stat-unit">/ {locale === 'en' ? 'person' : 'người'}</span>
              </div>
              <div className="preview-stat-cell">
                <small>{t('planner.previewGroup')}</small>
                <strong>{t('planner.guestsUnit', { count: groupSize })}</strong>
              </div>
            </div>

            <div className="preview-vibe-list">
              <span className="vibe-list-label">{t('planner.previewPriority')}</span>
              <div className="vibe-tags-wrap">
                {selectedIntents.length > 0 ? (
                  selectedIntents.map((id) => {
                    const found = intents.find((i) => i.id === id)
                    return (
                      <span key={id} className="vibe-pill-active">
                        {found?.glyph} {found?.label}
                      </span>
                    )
                  })
                ) : (
                  <span className="vibe-pill-empty">{t('planner.noIntentSelected')}</span>
                )}
              </div>
            </div>

            <div className="preview-simulation-notice">
              <Sparkles size={16} className="text-amber" />
              <p>
                {t('planner.previewHeuristicNotice')}
              </p>
            </div>

            <div className="preview-card-footer">
              <Navigation size={14} className="text-emerald" />
              <span>
                {t('planner.modeLabel', {
                  mode: transportModes.find((m) => m.id === transport)?.label || transport,
                })}
              </span>
            </div>
          </TiltCard3D>

          {/* Quick FAQ / Guarantee */}
          <div className="planner-guarantee-card">
            <h4>{t('planner.feasibilityTitle')}</h4>
            <p>
              {t('planner.feasibilityBody')}
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}
