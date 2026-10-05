import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Clock, ExternalLink, MapPin, Ticket } from 'lucide-react'
import { useEntityView } from '../analytics'
import { getExperiences } from '../api/client'
import { getPOI } from '../api/content'
import '../components/content/content.css'
import { useTranslation } from '../i18n'
import type { Experience, POI } from '../types'

export function PlacePage() {
  const { placeId = '' } = useParams()
  const { locale } = useTranslation()
  const vi = locale === 'vi'
  const [place, setPlace] = useState<POI | null>(null)
  const [missing, setMissing] = useState(false)
  const [experiences, setExperiences] = useState<Experience[]>([])

  useEffect(() => {
    setPlace(null)
    setMissing(false)
    getPOI(placeId).then(setPlace).catch(() => setMissing(true))
    getExperiences().then((items) => setExperiences(items.filter((item) => item.poi_id === placeId))).catch(() => setExperiences([]))
  }, [placeId])
  useEntityView(place ? { entity_type: 'poi', entity_id: place.id } : null)

  const mapsUrl = place ? `https://www.google.com/maps/search/?api=1&query=${place.latitude},${place.longitude}` : '#'

  return (
    <div className="content-page">
      <Link to="/explore" className="content-back"><ArrowLeft size={15} /> {vi ? 'Khám phá' : 'Explore'}</Link>
      {missing && <p className="review-text" style={{ marginTop: 24 }}>{vi ? 'Địa điểm không tồn tại hoặc chưa được công bố.' : 'This place does not exist or is not published.'}</p>}
      {!place && !missing && <div className="loading-state-3d"><span className="loader-orbit" /></div>}
      {place && (
        <>
          <h1 className="content-title">{place.name}</h1>
          <div className="content-meta">
            <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><MapPin size={14} />{place.address}</span>
            {place.is_landmark && <span className="tag-chip">{vi ? 'Danh lam thắng cảnh' : 'Landmark'}</span>}
          </div>
          {place.image_urls?.[0] && <img className="content-cover" src={place.image_urls[0]} alt={place.name} />}
          <div className="info-chips">
            {place.opening_hours && <span className="info-chip"><Clock size={15} className="text-emerald" />{place.opening_hours}</span>}
            {place.ticket_info && <span className="info-chip"><Ticket size={15} className="text-amber" />{place.ticket_info}</span>}
            <a className="info-chip" href={mapsUrl} target="_blank" rel="noreferrer"><ExternalLink size={15} />{vi ? 'Chỉ đường' : 'Directions'}</a>
          </div>
          {place.description && <p className="prose-content">{place.description}</p>}
          {(place.tags?.length ?? 0) > 0 && <div className="info-chips">{place.tags!.map((tag) => <span key={tag} className="tag-chip">#{tag}</span>)}</div>}
          {place.image_urls && place.image_urls.length > 1 && (
            <div className="content-grid" style={{ marginTop: 24 }}>
              {place.image_urls.slice(1).map((url) => <img key={url} src={url} alt="" loading="lazy" style={{ width: '100%', height: 180, objectFit: 'cover', borderRadius: 'var(--radius-md)' }} />)}
            </div>
          )}
          {experiences.length > 0 && (
            <section style={{ marginTop: 36 }}>
              <h2 className="section-title-3d" style={{ fontSize: 22 }}>{vi ? 'Trải nghiệm tại đây' : 'Experiences here'}</h2>
              <div className="content-grid" style={{ marginTop: 16 }}>
                {experiences.map((item) => (
                  <Link key={item.id} to={`/explore?focus=${item.id}`} className="place-card">
                    <div className="place-card-body">
                      <h4>{item.name}</h4>
                      <p>{item.duration_min} {vi ? 'phút' : 'min'} · {item.price_vnd.toLocaleString('vi-VN')}₫</p>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
