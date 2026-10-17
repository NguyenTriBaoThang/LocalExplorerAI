import { Link } from 'react-router-dom'
import { ArrowUpRight, Clock3, MapPin, Users, Sparkles, Compass, Star } from 'lucide-react'
import { useJourney } from '../../journey'
import { SourceDetails } from '../journey/SourceDetails'
import type { Experience } from '../../types'
import { VerificationBadge } from '../common/StatusBadge'
import { TiltCard3D } from '../3d/TiltCard3D'
import { useTranslation } from '../../i18n'
import { tagLabel } from '../../tags'

export function ExperienceCard({
  experience,
  selected,
  onSelect,
}: {
  experience: Experience
  selected?: boolean
  onSelect: () => void
}) {
  const { t, locale } = useTranslation()
  const { trip, toggleExperience } = useJourney()
  const included = trip.selected.some((item) => item.id === experience.id)
  const isSimulated = experience.data_mode === 'simulated'
  const sourceCandidate = experience.poi.details?.source_candidate
  const sourceFields = sourceCandidate && typeof sourceCandidate === 'object'
    ? (sourceCandidate as Record<string, unknown>).source_fields
    : undefined
  const sourceDescription = sourceFields && typeof sourceFields === 'object'
    ? (sourceFields as Record<string, unknown>).description
    : undefined
  const cardDescription = isSimulated && typeof sourceDescription === 'string' && sourceDescription.trim()
    ? sourceDescription
    : experience.description

  const categoryMeta: Record<string, { label: string; color: string; icon: string }> = {
    handicraft: { label: t('explore.intentCraft'), color: 'bg-amber-500/10 text-amber-700 border-amber-200', icon: '🎨' },
    culture: { label: t('explore.intentCulture'), color: 'bg-emerald-500/10 text-emerald-700 border-emerald-200', icon: '🏛️' },
    food: { label: t('explore.intentFood'), color: 'bg-orange-500/10 text-orange-700 border-orange-200', icon: '🍜' },
    nature: { label: t('explore.intentNature'), color: 'bg-teal-500/10 text-teal-700 border-teal-200', icon: '🌿' },
    relaxation: { label: t('explore.intentRelax'), color: 'bg-indigo-500/10 text-indigo-700 border-indigo-200', icon: '🍵' },
  }

  const sourcePhoto = experience.poi.details?.images?.find((item) => (item.local_url || item.url) && item.source_url && item.license)
  const photoUrl = (sourcePhoto && (sourcePhoto.local_url || sourcePhoto.url)) || experience.poi.image_urls?.[0] || null
  const slot = isSimulated ? undefined : experience.slots.find((item) => !['full', 'unavailable', 'cancelled'].includes(item.status))
  const time = slot
    ? new Intl.DateTimeFormat(locale === 'vi' ? 'vi-VN' : 'en-US', {
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'Asia/Ho_Chi_Minh',
      }).format(new Date(slot.start_at))
    : null

  const cat = categoryMeta[experience.poi.category] || { label: experience.poi.category, color: '', icon: '✨' }

  return (
    <TiltCard3D
      maxTilt={5}
      scale={selected ? 1.02 : 1.01}
      className={`experience-card-3d ${selected ? 'card-3d-selected' : ''}`}
      onClick={onSelect}
    >
      <div className="card-3d-inner">
        {/* Photo Header Container */}
        <div className="card-photo-container">
          {photoUrl ? (
            <img
              src={photoUrl}
              alt={experience.name}
              className="card-photo-img"
              loading="lazy"
              onError={(e) => {
                const img = e.currentTarget
                img.style.display = 'none'
                const parent = img.parentElement
                if (parent) {
                  const fallback = parent.querySelector('.card-photo-placeholder') as HTMLElement
                  if (fallback) fallback.style.display = 'flex'
                }
              }}
            />
          ) : null}
          <div
            className="card-photo-placeholder"
            style={{ display: photoUrl ? 'none' : 'flex' }}
          >
            <span className="card-placeholder-icon">{cat.icon}</span>
            <span className="card-placeholder-label">{cat.label}</span>
          </div>
          <div className="card-photo-gradient" />
          {sourcePhoto ? (
            <a
              className="card-photo-credit"
              href={sourcePhoto.source_url}
              target="_blank"
              rel="noreferrer"
              onClick={(event) => event.stopPropagation()}
            >
              Ảnh: {sourcePhoto.attribution || sourcePhoto.credit_line || sourcePhoto.title} · {sourcePhoto.license}
            </a>
          ) : experience.poi.source_attribution ? (
            <span className="card-photo-credit">
              {experience.poi.source_attribution}
            </span>
          ) : null}
          
          <div className="card-photo-top-badges">
            <div className="cat-badge">
              <span className="cat-icon">{cat.icon}</span>
              <span className="cat-label">{cat.label}</span>
            </div>
            <div className="card-action-hint">
              <ArrowUpRight size={16} />
            </div>
          </div>

          <div className="card-photo-bottom-badges">
            <span className="card-district-badge">
              <MapPin size={11} /> {experience.poi.district || 'TP. Hồ Chí Minh'}
            </span>
            <span className="card-price-glow-badge">
              {isSimulated
                ? (locale === 'vi' ? 'Mô phỏng' : 'Simulated')
                : experience.price_vnd > 0 ? `${experience.price_vnd.toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-US')}₫` : (locale === 'vi' ? 'Miễn phí' : 'Free')}
            </span>
          </div>
        </div>

        <div className="card-body-content">
          <h3 className="card-title">{experience.name}</h3>
          <div className="card-rating-row" style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12.5 }}>
            {experience.rating_average != null && (experience.rating_count ?? 0) > 0 ? (
              <span className="card-rating" title={locale === 'vi' ? `${experience.rating_count} đánh giá` : `${experience.rating_count} reviews`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--amber)', fontWeight: 600 }}>
                <Star size={13} fill="currentColor" />{experience.rating_average.toFixed(1)}
                <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>({experience.rating_count})</span>
              </span>
            ) : (
              <span style={{ color: 'var(--text-dim)' }}>{locale === 'vi' ? 'Chưa có đánh giá' : 'No reviews yet'}</span>
            )}
            <Link to={`/experiences/${experience.id}`} onClick={(event) => event.stopPropagation()} className="source-evidence-link">
              {locale === 'vi' ? 'Xem chi tiết' : 'Details'}
            </Link>
          </div>
          <p className="card-desc">{cardDescription}</p>
          <Link
            className="card-place-detail-link"
            to={`/places/${encodeURIComponent(experience.poi.id)}`}
            onClick={(event) => event.stopPropagation()}
          >
            Xem chi tiết địa điểm <ArrowUpRight size={13} />
          </Link>

          {/* Intent Tags */}
          <div className="card-tags-row">
            {experience.intent_tags.slice(0, 3).map((tag) => (
              <span key={tag} className="intent-pill">
                #{tagLabel(tag, locale)}
              </span>
            ))}
          </div>

          {/* Meta Stats: Duration & Price */}
          <div className="card-stats-row">
            <div className="stat-item">
              <Clock3 size={13} className="stat-icon text-amber" />
              <span>{isSimulated ? (locale === 'vi' ? 'Thời lượng chưa xác minh' : 'Duration unverified') : `${experience.duration_min} ${t('explore.minutes')}`}</span>
            </div>
            <div className="stat-item">
              <Users size={13} className="stat-icon text-cyan" />
              {isSimulated ? <span>{locale === 'vi' ? 'Giá chưa xác minh' : 'Price unverified'}</span> : <span>
                {experience.price_vnd.toLocaleString(locale === 'vi' ? 'vi-VN' : 'en-US')}
                {experience.price_basis === 'per_person' ? (locale === 'vi' ? '₫ / người' : ' VND / person') : (locale === 'vi' ? '₫ / nhóm' : ' VND / group')}
              </span>}
            </div>
            {isSimulated ? (
              <div className="stat-item">
                <Sparkles size={13} className="stat-icon text-emerald" />
                <span>{locale === 'vi' ? 'Thông tin chưa xác minh' : 'Details unverified'}</span>
              </div>
            ) : experience.indoor ? (
              <div className="stat-item">
                <Compass size={13} className="stat-icon text-emerald" />
                <span>{locale === 'vi' ? 'Trong nhà' : 'Indoor'}</span>
              </div>
            ) : (
              <div className="stat-item">
                <Sparkles size={13} className="stat-icon text-emerald" />
                <span>{locale === 'vi' ? 'Ngoài trời' : 'Outdoor'}</span>
              </div>
            )}
          </div>

          {experience.slots.length > 0 && (trip.demo || experience.data_mode === 'real') && <button type="button" disabled={!included && trip.selected.length >= 6} onClick={(event) => { event.stopPropagation(); toggleExperience({ id: experience.id, name: experience.name, poiId: experience.poi_id }) }} className="my-2 rounded-lg bg-emerald-700 px-3 py-2 text-sm text-white disabled:opacity-50">{included ? 'Bỏ khỏi hành trình' : 'Chọn vào hành trình'}</button>}
          {experience.data_mode === 'real' && <SourceDetails sources={[...(experience.poi.source_evidence || []), ...(experience.source_evidence || [])]} />}
          {/* Card Footer */}
          <div className="card-footer-3d">
            <span className="slot-notice">
              <MapPin size={12} className="text-emerald" />
              {isSimulated
                ? (locale === 'vi' ? 'Lịch mô phỏng · không đặt chỗ' : 'Simulated schedule · not bookable')
                : slot ? t('explore.slotNotice', { time: time || '' }) : t('explore.noFixedSlot')}
            </span>
            <VerificationBadge status={experience.data_mode === 'real' ? 'verified' : 'simulated'} />
          </div>
          {experience.data_mode === 'real' && slot?.confirmed_at && slot.expires_at && (
            <small className="slot-freshness-note">
              Cơ sở xác nhận lúc {new Date(slot.confirmed_at).toLocaleString()} · còn hiệu lực đến {new Date(slot.expires_at).toLocaleString()}
            </small>
          )}
          {experience.data_mode === 'real' && experience.source_evidence?.[0] && (
            <a
              className="source-evidence-link"
              href={experience.source_evidence[0].source_uri}
              target="_blank"
              rel="noreferrer"
              onClick={(event) => event.stopPropagation()}
              title={`Nguồn xác nhận ${experience.source_evidence[0].observed_at || ''}; hết hạn ${experience.source_evidence[0].expires_at || ''}`}
            >
              {experience.source_evidence[0].source_label || 'Xem nguồn đã duyệt'}
              {experience.source_evidence[0].expires_at && ` · đến ${new Date(experience.source_evidence[0].expires_at).toLocaleDateString()}`}
            </a>
          )}
        </div>
      </div>
    </TiltCard3D>
  )
}
