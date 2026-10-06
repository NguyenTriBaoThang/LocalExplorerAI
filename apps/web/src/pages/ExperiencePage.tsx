import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CalendarClock, Clock3, Compass, MapPin, Sparkles, Store, Users } from 'lucide-react'
import { useEntityView } from '../analytics'
import { contentApi } from '../api/content'
import '../components/content/content.css'
import { ReviewsPanel } from '../components/content/ReviewsPanel'
import { Stars } from '../components/content/StarRating'
import { VerificationBadge } from '../components/common/StatusBadge'
import { useTranslation } from '../i18n'
import type { Experience } from '../types'

export function ExperiencePage() {
  const { experienceId = '' } = useParams()
  const { locale } = useTranslation()
  const vi = locale === 'vi'
  const [experience, setExperience] = useState<Experience | null>(null)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    setExperience(null)
    setMissing(false)
    contentApi.experience(experienceId).then(setExperience).catch(() => setMissing(true))
  }, [experienceId])
  useEntityView(experience ? { entity_type: 'experience', entity_id: experience.id } : null)

  const money = (value: number) => (value > 0 ? `${value.toLocaleString(vi ? 'vi-VN' : 'en-US')}₫` : vi ? 'Miễn phí' : 'Free')
  const when = (value: string) => new Intl.DateTimeFormat(vi ? 'vi-VN' : 'en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date(value))
  const openSlots = (experience?.slots ?? []).filter((slot) => !['full', 'unavailable', 'cancelled'].includes(slot.status))

  return (
    <div className="content-page">
      <Link to="/explore" className="content-back"><ArrowLeft size={15} /> {vi ? 'Khám phá' : 'Explore'}</Link>
      {missing && <p className="review-text" style={{ marginTop: 24 }}>{vi ? 'Trải nghiệm không tồn tại hoặc hiện không mở cho khách.' : 'This experience does not exist or is not open to visitors.'}</p>}
      {!experience && !missing && <div className="loading-state-3d"><span className="loader-orbit" /></div>}
      {experience && (
        <>
          <h1 className="content-title">{experience.name}</h1>
          <div className="content-meta">
            {experience.rating_average != null && (experience.rating_count ?? 0) > 0 && (
              <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><Stars value={experience.rating_average} />{experience.rating_average.toFixed(1)} ({experience.rating_count})</span>
            )}
            {experience.provider_name && <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><Store size={14} />{experience.provider_name}</span>}
            <VerificationBadge status={experience.data_mode === 'real' ? 'verified' : 'simulated'} />
          </div>
          {experience.poi.image_urls?.[0] && <img className="content-cover" src={experience.poi.image_urls[0]} alt={experience.name} />}
          <div className="info-chips">
            <span className="info-chip"><Clock3 size={15} className="text-amber" />{experience.duration_min} {vi ? 'phút' : 'min'}</span>
            <span className="info-chip"><Users size={15} className="text-cyan" />{money(experience.price_vnd)}{vi ? ' / người' : ' / person'}</span>
            <span className="info-chip">{experience.indoor ? <Compass size={15} className="text-emerald" /> : <Sparkles size={15} className="text-emerald" />}{experience.indoor ? (vi ? 'Trong nhà' : 'Indoor') : (vi ? 'Ngoài trời' : 'Outdoor')}</span>
            <Link className="info-chip" to={`/places/${experience.poi_id}`}><MapPin size={15} />{experience.poi.name}</Link>
          </div>
          {experience.description && <p className="prose-content">{experience.description}</p>}
          {experience.intent_tags.length > 0 && <div className="info-chips">{experience.intent_tags.map((tag) => <span key={tag} className="tag-chip">#{tag.replaceAll('_', ' ')}</span>)}</div>}

          <section style={{ marginTop: 32 }}>
            <h2 className="section-title-3d" style={{ fontSize: 22 }}>{vi ? 'Khung giờ sắp tới' : 'Upcoming time slots'}</h2>
            {openSlots.length === 0 ? (
              <p className="review-text" style={{ marginTop: 8 }}>{vi ? 'Hiện chưa có khung giờ mở. Hãy quay lại sau.' : 'No open time slots right now. Please check back later.'}</p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0, margin: '12px 0 0', display: 'grid', gap: 8 }}>
                {openSlots.map((slot) => (
                  <li key={slot.id} className="info-chip" style={{ justifyContent: 'space-between', borderRadius: 'var(--radius-md)' }}>
                    <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}><CalendarClock size={15} className="text-emerald" />{when(slot.start_at)}</span>
                    <span>{slot.available_reported === null ? (vi ? 'Chưa rõ chỗ trống' : 'Availability unconfirmed') : vi ? `Còn ${slot.available_reported} chỗ` : `${slot.available_reported} left`}</span>
                  </li>
                ))}
              </ul>
            )}
            <Link to={`/explore?focus=${experience.id}`} className="btn-primary-3d" style={{ display: 'inline-flex', marginTop: 16 }}>{vi ? 'Chọn giờ và đặt chỗ' : 'Choose a time and book'}</Link>
          </section>

          <ReviewsPanel experienceId={experience.id} />
        </>
      )}
    </div>
  )
}
