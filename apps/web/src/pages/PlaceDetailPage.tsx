import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  ArrowUpRight,
  Clock3,
  ExternalLink,
  Globe2,
  MapPin,
  Phone,
  Ticket,
  Users,
  Compass,
  Sparkles,
  Bot,
  Calendar,
  ShieldCheck,
  Copy,
  Check,
  ChevronRight,
  Building,
} from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getPOI } from '../api/client'
import { useEntityView } from '../analytics'
import { useTranslation } from '../i18n'
import type { POIDetail, SourcePhoto } from '../types'

function textValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function hoursText(value: unknown): string {
  let parsed = value
  if (typeof value === 'string') {
    try { parsed = JSON.parse(value) } catch { return value }
  }
  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
    const hours = parsed as Record<string, unknown>
    return [textValue(hours.days), [textValue(hours.open), textValue(hours.close)].filter(Boolean).join('–')].filter(Boolean).join(' · ')
  }
  return textValue(parsed)
}

function externalUrl(value?: string | null): string | null {
  if (!value) return null
  try {
    const url = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(value) ? value : `https://${value}`)
    return ['https:', 'http:'].includes(url.protocol) ? url.toString() : null
  } catch {
    return null
  }
}

export function PlaceDetailPage() {
  const { placeId: id = '' } = useParams()
  const navigate = useNavigate()
  const { t, locale, formatCurrency, formatDateTime } = useTranslation()
  const [place, setPlace] = useState<POIDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const unavailable = t('placeDetail.unavailable')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    getPOI(id)
      .then((data) => { if (active) setPlace(data) })
      .catch(() => { if (active) setError(t('placeDetail.notFound')) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id, t])

  useEntityView(place && place.id === id ? { entity_type: 'poi', entity_id: place.id } : null)

  const copyAddress = () => {
    if (place?.address) {
      void navigator.clipboard.writeText(place.address)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (loading) {
    return (
      <div className="page-wrap places-loading-container">
        <div className="places-spinner" />
        <p className="text-slate-300 font-medium">{t('placeDetail.loading')}</p>
      </div>
    )
  }

  if (error || !place) {
    return (
      <div className="page-wrap places-empty-box">
        <p className="text-rose-400 font-semibold mb-4">{error || t('placeDetail.noData')}</p>
        <Link className="btn-primary-3d inline-flex items-center gap-2" to="/places">
          <ArrowLeft size={16} /> {t('placeDetail.backToPlaces')}
        </Link>
      </div>
    )
  }

  const details = place.details || {}
  const rawCandidate = details.source_candidate
  const sourceCandidate = rawCandidate && typeof rawCandidate === 'object'
    ? rawCandidate as Record<string, unknown>
    : null
  const candidateSourceUrl = typeof sourceCandidate?.source_url === 'string'
    ? externalUrl(sourceCandidate.source_url)
    : null
  const rawSourceFields = sourceCandidate?.source_fields
  const sourceFields = rawSourceFields && typeof rawSourceFields === 'object'
    ? rawSourceFields as Record<string, unknown>
    : null
  const sourceDescription = typeof sourceFields?.description === 'string' ? sourceFields.description : ''
  const sourceAddress = typeof sourceFields?.address === 'string' ? sourceFields.address : ''
  const sourceNote = typeof sourceFields?.note === 'string' ? sourceFields.note : ''
  const sourceHours = hoursText(sourceFields?.open_hours)
  const sourcePrice = typeof sourceFields?.price_vnd === 'number' && Number.isFinite(sourceFields.price_vnd)
    ? sourceFields.price_vnd
    : null
  const sourcePhotos = (Array.isArray(details.images) ? details.images : [])
    .filter((photo): photo is SourcePhoto => Boolean((photo.local_url || photo.url) && photo.source_url && photo.license))
  const catalogPhotos = Array.isArray(place.image_urls) ? place.image_urls : []

  // Main primary cover photo
  const primaryHeroPhoto =
    sourcePhotos[0]?.local_url ||
    sourcePhotos[0]?.url ||
    catalogPhotos[0] ||
    null

  const venueFacts = details.venue_facts && typeof details.venue_facts === 'object'
    ? details.venue_facts as Record<string, unknown> : {}
  const sourceUrls = details.source_urls && typeof details.source_urls === 'object'
    ? details.source_urls as Record<string, unknown> : {}
  const openingHours = place.opening_hours || hoursText(details.opening_hours) || hoursText(venueFacts.public_hours) || sourceHours || hoursText(details.open_hours)
  const referencePrice = sourcePrice ?? (typeof venueFacts.public_admission_fee_vnd === 'number' ? venueFacts.public_admission_fee_vnd : null)
  const fee = place.ticket_info || textValue(details.fee) || textValue(venueFacts.fee_note)
    || (referencePrice !== null ? t('placeDetail.referencePriceFromSource', { price: formatCurrency(referencePrice) }) : unavailable)
  const website = externalUrl(details.website || place.source_url || textValue(details.source_url)
    || textValue(sourceUrls.venue_official) || textValue(venueFacts.facts_source) || candidateSourceUrl)
  const mapUrl = `https://www.openstreetmap.org/?mlat=${place.latitude}&mlon=${place.longitude}#map=18/${place.latitude}/${place.longitude}`
  const tags = Object.entries(details.osm_tags && typeof details.osm_tags === 'object' ? details.osm_tags : {})
  const experiences = Array.isArray(place.experiences) ? place.experiences : []
  const sourceEvidence = Array.isArray(place.source_evidence) ? place.source_evidence : []

  const categoryMeta: Record<string, { label: string; icon: string; bg: string }> = {
    food: { label: t('placeDetail.catFood'), icon: '🍜', bg: 'bg-orange-500/15 text-orange-400 border-orange-500/30' },
    culture: { label: t('placeDetail.catCulture'), icon: '🏛️', bg: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
    handicraft: { label: t('placeDetail.catHandicraft'), icon: '🎨', bg: 'bg-amber-500/15 text-amber-400 border-amber-500/30' },
    nature: { label: t('placeDetail.catNature'), icon: '🌿', bg: 'bg-teal-500/15 text-teal-400 border-teal-500/30' },
    relaxation: { label: t('placeDetail.catRelaxation'), icon: '🍵', bg: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30' },
    accommodation: { label: t('placeDetail.catAccommodation'), icon: '🏨', bg: 'bg-blue-500/15 text-blue-400 border-blue-500/30' },
  }

  const cat = categoryMeta[place.category] || { label: place.category, icon: '📍', bg: 'bg-slate-700/30 text-slate-300 border-slate-600/30' }

  return (
    <article className="page-wrap place-detail-page">
      {/* Top Breadcrumb */}
      <div className="flex items-center justify-between gap-4 mb-5">
        <Link className="place-back-pill" to="/places">
          <ArrowLeft size={15} /> <span>{t('placeDetail.allPlaces')}</span>
        </Link>
        <div className="place-detail-breadcrumb flex items-center gap-2 text-xs text-slate-400">
          <span>{place.district || (locale === 'en' ? 'Ho Chi Minh City' : 'TP. Hồ Chí Minh')}</span>
          <ChevronRight size={13} />
          <span>{cat.label}</span>
          <ChevronRight size={13} />
          <span className="place-detail-breadcrumb-current text-slate-200 font-semibold truncate max-w-[200px]">{place.name}</span>
        </div>
      </div>

      {/* Hero Showcase Banner */}
      <div className="place-hero-banner">
        {primaryHeroPhoto ? (
          <img
            src={primaryHeroPhoto}
            alt={place.name}
            className="place-hero-img"
          />
        ) : (
          <div className="place-hero-fallback">
            <span className="text-6xl mb-2">{cat.icon}</span>
            <span className="text-lg font-bold text-slate-300">{cat.label}</span>
          </div>
        )}

        <div className="place-hero-gradient" />

        {/* Floating Content Over Banner */}
        <div className="place-hero-content">
          <div className="flex items-center gap-2 flex-wrap mb-3">
            <span className={`place-hero-badge place-hero-category px-3 py-1 rounded-full text-xs font-bold border backdrop-blur-md ${cat.bg}`}>
              {cat.icon} {cat.label}
            </span>
            <span className="place-hero-badge px-3 py-1 rounded-full text-xs font-semibold bg-slate-900/80 text-slate-300 border border-slate-700 backdrop-blur-md flex items-center gap-1.5">
              <MapPin size={12} className="text-emerald-400" />
              {place.district || (locale === 'en' ? 'District 1, Ho Chi Minh City' : 'Quận 1, TP. Hồ Chí Minh')}
            </span>
            {place.verification_status === 'verified' ? (
              <span className="place-hero-badge place-hero-verified px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 backdrop-blur-md flex items-center gap-1.5">
                <ShieldCheck size={13} /> {t('placeDetail.verified')}
              </span>
            ) : (
              <span className="place-hero-badge place-hero-unverified px-3 py-1 rounded-full text-xs font-medium bg-amber-500/15 text-amber-300 border border-amber-500/30 backdrop-blur-md">
                {t('placeDetail.unverified')}
              </span>
            )}
          </div>

          <h1 className="place-hero-title">{place.name}</h1>
          <p className="place-hero-desc">
            {sourceDescription || place.description || unavailable}
          </p>
          {(place.tags?.length ?? 0) > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">{place.tags!.map((tag) => <span key={tag} className="place-hero-tag">#{tag}</span>)}</div>
          )}

          {/* Quick CTA Action Buttons */}
          <div className="place-hero-actions">
            <button
              type="button"
              onClick={() => navigate(`/chat?prompt=${encodeURIComponent(t('placeDetail.askAiPrompt', { name: place.name }))}`)}
              className="btn-primary-3d flex items-center gap-2"
            >
              <Bot size={17} />
              <span>{t('placeDetail.askAi')}</span>
            </button>
            <button
              type="button"
              onClick={() => navigate('/planner')}
              className="btn-secondary-3d flex items-center gap-2"
            >
              <Calendar size={17} />
              <span>{t('placeDetail.planTrip')}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Two-Column Content Grid */}
      <div className="place-detail-layout-grid">
        {/* Left Column: Photos, Details, Experiences, Open Data */}
        <div className="place-main-col">
          {/* Photo Gallery Grid if multiple photos */}
          {sourcePhotos.length > 0 ? (
            <section className="place-detail-card" aria-label={t('placeDetail.sourcePhotos', { count: sourcePhotos.length })}>
              <h2 className="section-card-title flex items-center gap-2">
                <Sparkles size={18} className="text-emerald-400" />
                {t('placeDetail.sourcePhotos', { count: sourcePhotos.length })}
              </h2>
              <div className="place-photo-grid-elevated">
                {sourcePhotos.map((photo, i) => (
                  <figure key={`${photo.source_url}-${i}`} className="place-photo-figure">
                    <img
                      src={photo.local_url || photo.url}
                      alt={photo.title || place.name}
                      loading="lazy"
                    />
                    <figcaption>
                      <a href={photo.source_url} target="_blank" rel="noreferrer" className="credit-link">
                        {photo.attribution || photo.credit_line || photo.title || 'Wikimedia Commons'}
                      </a>
                      <span className="license-tag">
                        {photo.license_url ? (
                          <a href={photo.license_url} target="_blank" rel="noreferrer">
                            {photo.license}
                          </a>
                        ) : (
                          photo.license
                        )}
                      </span>
                    </figcaption>
                  </figure>
                ))}
              </div>
            </section>
          ) : catalogPhotos.length > 1 ? (
            <section className="place-detail-card">
              <h2 className="section-card-title flex items-center gap-2">
                <Sparkles size={18} className="text-emerald-400" />
                {t('placeDetail.noPhotoTitle')}
              </h2>
              <div className="place-photo-grid-elevated">
                {catalogPhotos.map((url, i) => (
                  <figure key={i} className="place-photo-figure">
                    <img src={url} alt={`${place.name} ${i + 1}`} loading="lazy" />
                    <figcaption>
                      <span className="text-slate-400 text-xs">
                        {place.source_attribution || (locale === 'en' ? 'Ho Chi Minh City Archive Photography' : 'Ảnh tư liệu catalog TP. Hồ Chí Minh')}
                      </span>
                    </figcaption>
                  </figure>
                ))}
              </div>
            </section>
          ) : details.catalog_mode === 'hcmc_catalog_candidate' ? (
            <section className="place-detail-card">
              <h2 className="section-card-title flex items-center gap-2">
                <Sparkles size={18} className="text-emerald-400" />
                {t('placeDetail.noPhotoTitle')}
              </h2>
              <p className="text-sm text-slate-400">
                {t('placeDetail.noPhotoDesc')}
              </p>
            </section>
          ) : null}

          {details.catalog_mode === 'hcmc_catalog_candidate' && sourceFields && (
            <section className="place-detail-card">
              <h2 className="section-card-title flex items-center gap-2">
                <MapPin size={18} className="text-amber-400" />
                {t('placeDetail.provenanceTitle')}
              </h2>
              <p className="text-xs text-amber-300 mb-4">
                {t('placeDetail.provenanceNotice')}
              </p>
              <div className="place-provenance-box">
                {sourceDescription && <div className="provenance-item"><span className="provenance-label">{t('placeDetail.sourceDesc')}</span><span className="provenance-val">{sourceDescription}</span></div>}
                {sourceAddress && <div className="provenance-item"><span className="provenance-label">{t('placeDetail.sourceAddress')}</span><span className="provenance-val">{sourceAddress}</span></div>}
                {sourceHours && <div className="provenance-item"><span className="provenance-label">{t('placeDetail.sourceHours')}</span><span className="provenance-val">{sourceHours}</span></div>}
                {sourcePrice !== null && <div className="provenance-item"><span className="provenance-label">{t('placeDetail.sourcePrice')}</span><span className="provenance-val">{formatCurrency(sourcePrice)} · {t('placeDetail.unverified')}</span></div>}
                {sourceNote && <div className="provenance-item"><span className="provenance-label">{t('placeDetail.sourceNote')}</span><span className="provenance-val">{sourceNote}</span></div>}
              </div>
            </section>
          )}

          {/* Experiences inside this POI */}
          {experiences.length > 0 && (
            <section className="place-detail-card">
              <h2 className="section-card-title flex items-center gap-2">
                <Calendar size={18} className="text-emerald-400" />
                {t('placeDetail.experiences', { count: experiences.length })}
              </h2>
              <div className="place-exp-list">
                {experiences.map((exp) => {
                  const slots = Array.isArray(exp.slots) ? exp.slots : []
                  return (
                    <div className="place-exp-item-card" key={exp.id}>
                      <div className="flex items-start justify-between gap-4 flex-wrap">
                        <div>
                          <h3 className="place-exp-title"><Link to={`/experiences/${encodeURIComponent(exp.id)}`}>{exp.name} <ArrowUpRight size={14} className="inline" /></Link></h3>
                          <p className="place-exp-desc">{exp.description || unavailable}</p>
                        </div>
                        <div className="place-exp-price-badge">
                          {details.catalog_mode === 'hcmc_catalog_candidate' ? t('placeDetail.noExpPrice') : exp.price_vnd > 0 ? formatCurrency(exp.price_vnd) : t('common.free')}
                          {details.catalog_mode !== 'hcmc_catalog_candidate' && <span className="text-[10px] text-slate-400 font-normal"> / {exp.price_basis === 'per_person' ? t('itinerary.perPerson') : t('itinerary.perGroup')}</span>}
                        </div>
                      </div>

                      <div className="flex items-center gap-3 text-xs text-slate-300 mt-2">
                        <span className="flex items-center gap-1.5">
                          <Clock3 size={13} className="text-amber-400" />
                          {exp.duration_min > 0 ? t('placeDetail.durationMinutes', { minutes: exp.duration_min }) : t('placeDetail.noDuration')}
                        </span>
                        <span className="flex items-center gap-1.5">
                          <Compass size={13} className="text-emerald-400" />
                          {exp.indoor ? t('placeDetail.indoor') : t('placeDetail.outdoor')}
                        </span>
                      </div>

                      {slots.length > 0 && (
                        <div className="place-slots-box mt-3">
                          <span className="text-xs font-semibold text-slate-400 block mb-2">
                            {t('placeDetail.servingSlots')}
                          </span>
                          <div className="flex flex-wrap gap-2">
                            {slots.map((s) => (
                              <div key={s.id} className="place-slot-pill">
                                <span className="place-slot-time">
                                  {s.start_at.slice(11, 16)} - {s.end_at.slice(11, 16)}
                                </span>
                                <span className="place-slot-cap">
                                  {s.available_reported != null ? t('placeDetail.slotsAvailable', { count: s.available_reported }) : t('placeDetail.slotsAvailableOpen')}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </section>
          )}

          {/* Data Provenance & Transparency (Open Data) */}
          <section className="place-detail-card place-transparency-card">
            <h2 className="section-card-title flex items-center gap-2">
              <Building size={18} className="text-emerald-400" />
              {t('placeDetail.provenanceAndTransparency')}
            </h2>
            <div className="place-provenance-box">
              {place.source_url && (
                <div className="provenance-item">
                  <span className="provenance-label">{t('placeDetail.initialSource')}</span>
                  <span className="provenance-val">
                    <a href={place.source_url} target="_blank" rel="noreferrer" className="provenance-link flex items-center gap-1">
                      {t('placeDetail.openSourceRecord')} <ExternalLink size={12} />
                    </a>
                  </span>
                </div>
              )}

              {Boolean(details.data_license) && (
                <div className="provenance-item">
                  <span className="provenance-label">{t('placeDetail.license')}</span>
                  <span className="provenance-val font-mono">{String(details.data_license)}</span>
                </div>
              )}

              <div className="provenance-item">
                <span className="provenance-label">{t('placeDetail.dataStatus')}</span>
                <span className="provenance-val">
                  {details.catalog_mode === 'hcmc_catalog_candidate'
                    ? t('placeDetail.statusCandidate')
                    : sourceEvidence.length > 0
                    ? t('placeDetail.statusVerified')
                    : t('placeDetail.statusOsm')}
                </span>
              </div>

              {Boolean(details.updated_at) && (
                <div className="provenance-item">
                  <span className="provenance-label">{t('placeDetail.recordedAt')}</span>
                  <span className="provenance-val">{formatDateTime(String(details.updated_at))}</span>
                </div>
              )}

              {Boolean(details.osm_id) && (
                <div className="provenance-item">
                  <span className="provenance-label">{t('placeDetail.osmRecord')}</span>
                  <span className="provenance-val">
                    <a href={mapUrl} target="_blank" rel="noreferrer" className="provenance-link flex items-center gap-1 font-mono">
                      osm:{String(details.osm_type || 'node')}/{String(details.osm_id)} ({t('placeDetail.viewOsm')} <ExternalLink size={12} />)
                    </a>
                  </span>
                </div>
              )}

              {sourceEvidence.length > 0 && (
                <div className="provenance-item">
                  <span className="provenance-label">{t('placeDetail.evidence')}</span>
                  <span className="provenance-val flex flex-wrap gap-1.5">
                    {sourceEvidence.map((ev, i) => (
                      <span key={i} className="source-evidence-badge">
                        {ev.source_type || 'proof'}
                      </span>
                    ))}
                  </span>
                </div>
              )}
            </div>

            {tags.length > 0 && (
              <details className="place-osm-tags-details mt-4">
                <summary className="cursor-pointer text-xs font-semibold text-slate-400 hover:text-slate-200 transition-colors">
                  <span>{t('placeDetail.osmTags', { count: tags.length })}</span>
                </summary>
                <div className="place-osm-tags-grid mt-2">
                  {tags.map(([k, v]) => (
                    <div key={k} className="osm-tag-item">
                      <span className="osm-tag-key font-mono">{k}</span>
                      <span className="osm-tag-val">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </section>
        </div>

        {/* Right Column: Practical Details, Action Card, Address, Contacts */}
        <aside className="place-sidebar-col">
          {/* Quick Facts Card */}
          <div className="place-sidebar-card">
            <h3 className="text-sm font-bold text-slate-200 mb-4 pb-3 border-b border-slate-800 flex items-center gap-2">
              <MapPin size={16} className="text-emerald-400" />
              {t('placeDetail.fieldInfo')}
            </h3>

            <div className="space-y-4">
              {/* Address */}
              <div className="side-info-item">
                <div className="flex items-center justify-between gap-2 text-xs text-slate-400 mb-1">
                  <span className="flex items-center gap-1.5 font-medium">
                    <MapPin size={13} className="text-emerald-400 shrink-0" />
                    <span>{t('placeDetail.address')}</span>
                  </span>
                  {place.address && (
                    <button
                      type="button"
                      onClick={copyAddress}
                      className="text-[11px] text-emerald-400 hover:text-emerald-300 flex items-center gap-1 transition-colors"
                      title={t('placeDetail.copyAddress')}
                    >
                      {copied ? <Check size={11} /> : <Copy size={11} />}
                      <span>{copied ? t('common.copied') : t('common.copy')}</span>
                    </button>
                  )}
                </div>
                <p className="text-xs text-slate-200 font-medium leading-relaxed">
                  {place.address || t('placeDetail.noAddress')}
                </p>
              </div>

              {/* Coordinates */}
              <div className="side-info-item">
                <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                  <Compass size={13} className="text-teal-400 shrink-0" />
                  <span>{t('placeDetail.gpsCoords')}</span>
                </div>
                <a
                  href={mapUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-teal-400 hover:underline flex items-center gap-1 font-mono"
                >
                  {place.latitude.toFixed(6)}, {place.longitude.toFixed(6)}
                  <ExternalLink size={12} />
                </a>
              </div>

              {/* Opening Hours */}
              <div className="side-info-item">
                <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                  <Clock3 size={13} className="text-amber-400 shrink-0" />
                  <span>{t('placeDetail.openingHours')}</span>
                </div>
                <p className="text-xs text-slate-200 font-medium">
                  {openingHours || unavailable}
                </p>
              </div>

              {/* Fee */}
              <div className="side-info-item">
                <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                  <Ticket size={13} className="text-emerald-400 shrink-0" />
                  <span>{t('placeDetail.referencePrice')}</span>
                </div>
                <p className="text-xs text-slate-200 font-medium">
                  {fee}
                </p>
              </div>

              {/* Wheelchair */}
              <div className="side-info-item">
                <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                  <Users size={13} className="text-indigo-400 shrink-0" />
                  <span>{t('placeDetail.wheelchair')}</span>
                </div>
                <p className="text-xs text-slate-200 font-medium">
                  {details.wheelchair || unavailable}
                </p>
              </div>

              {/* Phone & Contact */}
              {details.contact_phone && (
                <div className="side-info-item">
                  <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                    <Phone size={13} className="text-emerald-400 shrink-0" />
                    <span>{t('placeDetail.phone')}</span>
                  </div>
                  <a href={`tel:${details.contact_phone}`} className="text-xs text-emerald-400 hover:underline font-semibold">
                    {details.contact_phone}
                  </a>
                </div>
              )}

              {/* Website */}
              {website && (
                <div className="side-info-item">
                  <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                    <Globe2 size={13} className="text-cyan-400 shrink-0" />
                    <span>{t('placeDetail.website')}</span>
                  </div>
                  <a href={website} target="_blank" rel="noreferrer" className="text-xs text-cyan-400 hover:underline flex items-center gap-1 font-semibold break-all">
                    {t('placeDetail.openWebsite')} <ExternalLink size={12} />
                  </a>
                </div>
              )}
            </div>

            {/* Quick Action Buttons on Side Panel */}
            <div className="mt-5 pt-4 border-t border-slate-800 space-y-2.5">
              <button
                type="button"
                onClick={() => navigate(`/chat?prompt=${encodeURIComponent(t('placeDetail.askAiPromptDetailed', { name: place.name }))}`)}
                className="w-full py-2.5 px-3 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-bold text-xs rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20 transition-all"
              >
                <Bot size={15} />
                <span>{t('placeDetail.askAiButton')}</span>
              </button>

              <a
                href={`https://www.google.com/maps/dir/?api=1&destination=${place.latitude},${place.longitude}`}
                target="_blank"
                rel="noreferrer"
                className="place-directions-link w-full py-2.5 px-3 bg-slate-800/80 hover:bg-slate-700 text-slate-200 font-semibold text-xs rounded-xl flex items-center justify-center gap-2 border border-slate-700/60 transition-all"
              >
                <MapPin size={14} className="place-directions-icon text-emerald-400" />
                <span>{t('placeDetail.googleMaps')}</span>
              </a>
            </div>
          </div>
        </aside>
      </div>
    </article>
  )
}
