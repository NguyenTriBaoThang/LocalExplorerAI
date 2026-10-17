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
import type { POIDetail, SourcePhoto } from '../types'

const unavailable = 'Chưa có dữ liệu trong nguồn đã nạp'

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
  const [place, setPlace] = useState<POIDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    getPOI(id)
      .then((data) => { if (active) setPlace(data) })
      .catch(() => { if (active) setError('Không tìm thấy địa điểm hoặc địa điểm chưa được công bố trong catalog.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id])

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
        <p className="text-slate-300 font-medium">Đang tải thông tin chi tiết địa điểm…</p>
      </div>
    )
  }

  if (error || !place) {
    return (
      <div className="page-wrap places-empty-box">
        <p className="text-rose-400 font-semibold mb-4">{error || 'Không có dữ liệu địa điểm.'}</p>
        <Link className="btn-primary-3d inline-flex items-center gap-2" to="/places">
          <ArrowLeft size={16} /> Về danh sách địa điểm
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
    || (referencePrice !== null ? `${referencePrice.toLocaleString('vi-VN')} ₫ · giá tham khảo từ nguồn` : unavailable)
  const website = externalUrl(details.website || place.source_url || textValue(details.source_url)
    || textValue(sourceUrls.venue_official) || textValue(venueFacts.facts_source) || candidateSourceUrl)
  const mapUrl = `https://www.openstreetmap.org/?mlat=${place.latitude}&mlon=${place.longitude}#map=18/${place.latitude}/${place.longitude}`
  const tags = Object.entries(details.osm_tags && typeof details.osm_tags === 'object' ? details.osm_tags : {})
  const experiences = Array.isArray(place.experiences) ? place.experiences : []
  const sourceEvidence = Array.isArray(place.source_evidence) ? place.source_evidence : []

  const categoryMeta: Record<string, { label: string; icon: string; bg: string }> = {
    food: { label: 'Ẩm thực', icon: '🍜', bg: 'bg-orange-500/15 text-orange-400 border-orange-500/30' },
    culture: { label: 'Di sản & Văn hóa', icon: '🏛️', bg: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
    handicraft: { label: 'Thủ công mỹ nghệ', icon: '🎨', bg: 'bg-amber-500/15 text-amber-400 border-amber-500/30' },
    nature: { label: 'Sinh thái & Tự nhiên', icon: '🌿', bg: 'bg-teal-500/15 text-teal-400 border-teal-500/30' },
    relaxation: { label: 'Thư giãn & Phục hồi', icon: '🍵', bg: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30' },
    accommodation: { label: 'Lưu trú', icon: '🏨', bg: 'bg-blue-500/15 text-blue-400 border-blue-500/30' },
  }

  const cat = categoryMeta[place.category] || { label: place.category, icon: '📍', bg: 'bg-slate-700/30 text-slate-300 border-slate-600/30' }

  return (
    <article className="page-wrap place-detail-page">
      {/* Top Breadcrumb */}
      <div className="flex items-center justify-between gap-4 mb-5">
        <Link className="place-back-pill" to="/places">
          <ArrowLeft size={15} /> <span>Tất cả địa điểm</span>
        </Link>
        <div className="place-detail-breadcrumb flex items-center gap-2 text-xs text-slate-400">
          <span>{place.district || 'TP. Hồ Chí Minh'}</span>
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
              {place.district || 'Quận 1, TP. Hồ Chí Minh'}
            </span>
            {place.verification_status === 'verified' ? (
              <span className="place-hero-badge place-hero-verified px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 backdrop-blur-md flex items-center gap-1.5">
                <ShieldCheck size={13} /> Đã xác minh catalog
              </span>
            ) : (
              <span className="place-hero-badge place-hero-unverified px-3 py-1 rounded-full text-xs font-medium bg-amber-500/15 text-amber-300 border border-amber-500/30 backdrop-blur-md">
                Dữ liệu tham khảo · chưa xác minh vận hành
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
              onClick={() => navigate(`/chat?prompt=${encodeURIComponent(`Gợi ý lịch trình và kinh nghiệm khám phá ${place.name}`)}`)}
              className="btn-primary-3d flex items-center gap-2"
            >
              <Bot size={17} />
              <span>Hỏi AI về địa điểm này</span>
            </button>
            <button
              type="button"
              onClick={() => navigate('/planner')}
              className="btn-secondary-3d flex items-center gap-2"
            >
              <Calendar size={17} />
              <span>Lên lịch trình tự động</span>
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
            <section className="place-detail-card" aria-label="Bộ ảnh nguồn">
              <h2 className="section-card-title flex items-center gap-2">
                <Sparkles size={18} className="text-emerald-400" />
                Ảnh tư liệu có bản quyền ({sourcePhotos.length} ảnh)
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
                Ảnh chụp không gian địa điểm
              </h2>
              <div className="place-photo-grid-elevated">
                {catalogPhotos.map((url, i) => (
                  <figure key={i} className="place-photo-figure">
                    <img src={url} alt={`${place.name} ${i + 1}`} loading="lazy" />
                    <figcaption>
                      <span className="text-slate-400 text-xs">
                        {place.source_attribution || 'Ảnh tư liệu catalog TP. Hồ Chí Minh'}
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
                Ảnh địa điểm
              </h2>
              <p className="text-sm text-slate-400">
                Chưa tìm thấy ảnh khớp chính xác có giấy phép và thông tin ghi công rõ ràng; mình không dùng ảnh minh họa thay thế.
              </p>
            </section>
          ) : null}

          {details.catalog_mode === 'hcmc_catalog_candidate' && sourceFields && (
            <section className="place-detail-card">
              <h2 className="section-card-title flex items-center gap-2">
                <MapPin size={18} className="text-amber-400" />
                Thông tin từ dữ liệu nguồn · chưa xác minh
              </h2>
              <p className="text-xs text-amber-300 mb-4">
                Đây là nội dung được điền từ bộ dữ liệu của dự án, không phải thông tin vận hành đã được địa điểm xác nhận.
              </p>
              <div className="place-provenance-box">
                {sourceDescription && <div className="provenance-item"><span className="provenance-label">Mô tả nguồn:</span><span className="provenance-val">{sourceDescription}</span></div>}
                {sourceAddress && <div className="provenance-item"><span className="provenance-label">Địa chỉ nguồn:</span><span className="provenance-val">{sourceAddress}</span></div>}
                {sourceHours && <div className="provenance-item"><span className="provenance-label">Giờ nguồn:</span><span className="provenance-val">{sourceHours}</span></div>}
                {sourcePrice !== null && <div className="provenance-item"><span className="provenance-label">Giá nguồn:</span><span className="provenance-val">{sourcePrice.toLocaleString('vi-VN')} ₫ · chưa xác minh</span></div>}
                {sourceNote && <div className="provenance-item"><span className="provenance-label">Ghi chú nguồn:</span><span className="provenance-val">{sourceNote}</span></div>}
              </div>
            </section>
          )}

          {/* Experiences inside this POI */}
          {experiences.length > 0 && (
            <section className="place-detail-card">
              <h2 className="section-card-title flex items-center gap-2">
                <Calendar size={18} className="text-emerald-400" />
                Hoạt động & Trải nghiệm ({experiences.length})
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
                          {details.catalog_mode === 'hcmc_catalog_candidate' ? 'Chưa có giá hoạt động' : exp.price_vnd > 0 ? `${exp.price_vnd.toLocaleString('vi-VN')} ₫` : 'Miễn phí'}
                          {details.catalog_mode !== 'hcmc_catalog_candidate' && <span className="text-[10px] text-slate-400 font-normal"> / {exp.price_basis === 'per_person' ? 'người' : 'nhóm'}</span>}
                        </div>
                      </div>

                      <div className="flex items-center gap-3 text-xs text-slate-300 mt-2">
                        <span className="flex items-center gap-1.5">
                          <Clock3 size={13} className="text-amber-400" />
                          {exp.duration_min > 0 ? `${exp.duration_min} phút` : 'Chưa có thời lượng'}
                        </span>
                        <span className="flex items-center gap-1.5">
                          <Compass size={13} className="text-emerald-400" />
                          {exp.indoor ? 'Trong nhà' : 'Ngoài trời'}
                        </span>
                      </div>

                      {slots.length > 0 && (
                        <div className="place-slots-box mt-3">
                          <span className="text-xs font-semibold text-slate-400 block mb-2">
                            Khung giờ phục vụ (Slot):
                          </span>
                          <div className="flex flex-wrap gap-2">
                            {slots.map((s) => (
                              <div key={s.id} className="place-slot-pill">
                                <strong>
                                  {new Date(s.start_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
                                </strong>
                                <span className={`slot-status-dot ${s.status}`} />
                                <span className="text-[11px] text-slate-300">
                                  {s.available_reported != null ? `${s.available_reported} chỗ` : 'Còn chỗ'}
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

          {/* Open Data Provenance & Legal */}
          <section className="place-detail-card">
            <h2 className="section-card-title flex items-center gap-2">
              <ShieldCheck size={18} className="text-cyan-400" />
              Nguồn dữ liệu & Tính minh bạch
            </h2>
            <div className="place-provenance-box">
              {details.catalog_mode === 'hcmc_catalog_candidate' ? (
                <>
                  {candidateSourceUrl && (
                    <div className="provenance-item">
                      <span className="provenance-label">Nguồn ban đầu:</span>
                      <span className="provenance-val">
                        <a href={candidateSourceUrl} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline inline-flex items-center gap-1">
                          Mở nguồn của bản ghi <ExternalLink size={12} />
                        </a>
                      </span>
                    </div>
                  )}
                </>
              ) : (
                <div className="provenance-item">
                  <span className="provenance-label">Bản quyền dữ liệu:</span>
                  <span className="provenance-val">
                    <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" className="text-emerald-400 hover:underline inline-flex items-center gap-1">
                      © OpenStreetMap contributors · ODbL-1.0 <ExternalLink size={12} />
                    </a>
                  </span>
                </div>
              )}
              <div className="provenance-item">
                <span className="provenance-label">Trạng thái dữ liệu:</span>
                <span className="provenance-val">
                  {details.catalog_mode === 'hcmc_catalog_candidate'
                    ? 'Ứng viên từ bộ dữ liệu địa điểm TP.HCM; chưa được xác minh độc lập.'
                    : place.data_mode === 'real'
                    ? 'Có bằng chứng nguồn kiểm định trong catalog'
                    : 'Dữ liệu pilot tham khảo từ OpenStreetMap'}
                </span>
              </div>
              {details.observed_at && (
                <div className="provenance-item">
                  <span className="provenance-label">Thời điểm ghi nhận:</span>
                  <span className="provenance-val">
                    {new Date(details.observed_at).toLocaleString('vi-VN')}
                  </span>
                </div>
              )}
              {details.osm_url && (
                <div className="provenance-item">
                  <span className="provenance-label">Bản ghi OpenStreetMap:</span>
                  <span className="provenance-val">
                    <a href={String(details.osm_url)} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline inline-flex items-center gap-1">
                      Xem đối tượng trên OSM <ExternalLink size={12} />
                    </a>
                  </span>
                </div>
              )}
              {sourceEvidence.map((ev) => (
                <div className="provenance-item" key={ev.id}>
                  <span className="provenance-label">Minh chứng:</span>
                  <span className="provenance-val">
                    <a href={ev.source_uri} target="_blank" rel="noreferrer" className="text-emerald-400 hover:underline inline-flex items-center gap-1">
                      {ev.source_label || ev.source_type} ({ev.license || 'ODbL'}) <ExternalLink size={12} />
                    </a>
                  </span>
                </div>
              ))}
            </div>
          </section>

          {/* Raw OSM Tags Accordion */}
          {tags.length > 0 && (
            <details className="place-detail-card place-raw-tags-accordion">
              <summary className="section-card-title cursor-pointer flex items-center justify-between">
                <span>Dữ liệu thuộc tính OpenStreetMap ({tags.length} trường)</span>
                <ChevronRight size={16} className="accordion-chevron" />
              </summary>
              <div className="tags-chips-grid mt-4">
                {tags.map(([key, value]) => (
                  <div key={key} className="tag-chip-item">
                    <span className="tag-key">{key}</span>
                    <span className="tag-val">{String(value)}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>

        {/* Right Sticky Column: Fast Facts & Map */}
        <aside className="place-side-col">
          <div className="sticky-info-panel">
            <h2 className="text-base font-bold text-white mb-4 flex items-center gap-2">
              <Building size={17} className="text-emerald-400" />
              Thông tin thực địa
            </h2>

            <div className="side-info-list">
              {/* Address with copy */}
              <div className="side-info-item">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                    <MapPin size={13} className="text-emerald-400 shrink-0" />
                    <span>Địa chỉ</span>
                  </div>
                  {place.address && (
                    <button
                      type="button"
                      onClick={copyAddress}
                      className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
                      title="Sao chép địa chỉ"
                    >
                      {copied ? <Check size={12} /> : <Copy size={12} />}
                      <span>{copied ? 'Đã chép' : 'Chép'}</span>
                    </button>
                  )}
                </div>
                <p className="text-sm text-slate-200 font-semibold leading-snug">
                  {place.address || 'Chưa có thông tin địa chỉ cụ thể'}
                </p>
              </div>

              {/* Coordinates */}
              <div className="side-info-item">
                <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                  <Compass size={13} className="text-cyan-400 shrink-0" />
                  <span>Tọa độ GPS</span>
                </div>
                <a
                  href={mapUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-cyan-400 hover:underline flex items-center gap-1 font-mono"
                >
                  {place.latitude.toFixed(6)}, {place.longitude.toFixed(6)}
                  <ExternalLink size={12} />
                </a>
              </div>

              {/* Opening Hours */}
              <div className="side-info-item">
                <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                  <Clock3 size={13} className="text-amber-400 shrink-0" />
                  <span>Giờ mở cửa (nguồn)</span>
                </div>
                <p className="text-xs text-slate-200 font-medium">
                  {openingHours || unavailable}
                </p>
              </div>

              {/* Fee */}
              <div className="side-info-item">
                <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                  <Ticket size={13} className="text-emerald-400 shrink-0" />
                  <span>Phí / giá tham khảo</span>
                </div>
                <p className="text-xs text-slate-200 font-medium">
                  {fee}
                </p>
              </div>

              {/* Wheelchair */}
              <div className="side-info-item">
                <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                  <Users size={13} className="text-indigo-400 shrink-0" />
                  <span>Hỗ trợ tiếp cận (xe lăn)</span>
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
                    <span>Điện thoại liên hệ</span>
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
                    <span>Website / nguồn thông tin</span>
                  </div>
                  <a href={website} target="_blank" rel="noreferrer" className="text-xs text-cyan-400 hover:underline flex items-center gap-1 font-semibold break-all">
                    Mở website <ExternalLink size={12} />
                  </a>
                </div>
              )}
            </div>

            {/* Quick Action Buttons on Side Panel */}
            <div className="mt-5 pt-4 border-t border-slate-800 space-y-2.5">
              <button
                type="button"
                onClick={() => navigate(`/chat?prompt=${encodeURIComponent(`Hãy gợi ý cho tôi lộ trình ghé thăm ${place.name} và các điểm lân cận`)}`)}
                className="w-full py-2.5 px-3 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-bold text-xs rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20 transition-all"
              >
                <Bot size={15} />
                <span>Hỏi AI về kinh nghiệm ghé thăm</span>
              </button>

              <a
                href={`https://www.google.com/maps/dir/?api=1&destination=${place.latitude},${place.longitude}`}
                target="_blank"
                rel="noreferrer"
                className="place-directions-link w-full py-2.5 px-3 bg-slate-800/80 hover:bg-slate-700 text-slate-200 font-semibold text-xs rounded-xl flex items-center justify-center gap-2 border border-slate-700/60 transition-all"
              >
                <MapPin size={14} className="place-directions-icon text-emerald-400" />
                <span>Chỉ đường trên Google Maps</span>
              </a>
            </div>
          </div>
        </aside>
      </div>
    </article>
  )
}
