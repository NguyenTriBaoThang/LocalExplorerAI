import { useEffect, useState, type ReactNode } from 'react'
import { ArrowLeft, Clock3, ExternalLink, Globe2, MapPin, Phone, Ticket, Users } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { getPOI } from '../api/client'
import type { POIDetail, SourcePhoto } from '../types'

const unavailable = 'Chưa có dữ liệu trong nguồn đã nạp'

function externalUrl(value?: string | null): string | null {
  if (!value) return null
  try {
    const url = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(value) ? value : `https://${value}`)
    return ['https:', 'http:'].includes(url.protocol) ? url.toString() : null
  } catch {
    return null
  }
}

function Info({ label, value, icon }: { label: string; value?: string | null; icon?: ReactNode }) {
  return (
    <div className="place-detail-info">
      <span>{icon}{label}</span>
      <strong>{value?.trim() || unavailable}</strong>
    </div>
  )
}

export function PlaceDetailPage() {
  const { id = '' } = useParams()
  const [place, setPlace] = useState<POIDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

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

  if (loading) return <div className="page-wrap places-empty">Đang tải thông tin địa điểm…</div>
  if (error || !place) return (
    <div className="page-wrap places-empty">
      <p>{error || 'Không có dữ liệu địa điểm.'}</p>
      <Link className="place-back-link" to="/places"><ArrowLeft size={15} /> Về danh sách địa điểm</Link>
    </div>
  )

  const details = place.details || {}
  const photos = (Array.isArray(details.images) ? details.images : [])
    .filter((photo): photo is SourcePhoto => Boolean((photo.local_url || photo.url) && photo.source_url && photo.license))
  const website = externalUrl(details.website)
  const mapUrl = `https://www.openstreetmap.org/?mlat=${place.latitude}&mlon=${place.longitude}#map=18/${place.latitude}/${place.longitude}`
  const tags = Object.entries(details.osm_tags && typeof details.osm_tags === 'object' ? details.osm_tags : {})
  // Older API responses may omit nested lists even though the current schema
  // supplies defaults. Treat absent collections as empty so a partial POI can
  // still render its available details instead of crashing the whole route.
  const experiences = Array.isArray(place.experiences) ? place.experiences : []
  const sourceEvidence = Array.isArray(place.source_evidence) ? place.source_evidence : []

  return (
    <article className="page-wrap place-detail-page">
      <Link className="place-back-link" to="/places"><ArrowLeft size={15} /> Tất cả địa điểm</Link>
      <header className="place-detail-heading">
        <span className="eyebrow-3d"><span className="eyebrow-dot" /> {place.district || 'Khu vực pilot Quận 1'}</span>
        <h1 className="page-heading-3d">{place.name}</h1>
        <p className="page-subtext-3d">{place.description || unavailable}</p>
        <div className="place-detail-badges">
          <span>{place.category}</span>
          <span>{place.verification_status === 'verified' ? 'Đã xác minh theo catalog' : 'Nguồn tham khảo · chưa xác minh vận hành'}</span>
        </div>
      </header>

      {photos.length ? (
        <section className="place-photo-grid" aria-label="Ảnh có nguồn">
          {photos.map((photo) => (
            <figure key={`${photo.source_url}-${photo.url}`}>
              <img src={photo.local_url || photo.url} alt={photo.title || place.name} />
              <figcaption>
                <a href={photo.source_url} target="_blank" rel="noreferrer">
                  {photo.attribution || photo.credit_line || photo.title || 'Nguồn ảnh'}
                </a>
                {' · '}
                {photo.license_url ? <a href={photo.license_url} target="_blank" rel="noreferrer">{photo.license}</a> : photo.license}
              </figcaption>
            </figure>
          ))}
        </section>
      ) : (
        <div className="place-no-photo">
          <MapPin size={22} />
          <span>Chưa tìm thấy ảnh được gắn nguồn rõ ràng cho địa điểm này. Không dùng ảnh minh họa thay thế.</span>
        </div>
      )}

      <section className="place-detail-section">
        <h2>Thông tin địa điểm</h2>
        <div className="place-detail-grid">
          <Info label="Địa chỉ" value={place.address} icon={<MapPin size={14} />} />
          <Info label="Giờ mở cửa (theo nguồn)" value={details.opening_hours} icon={<Clock3 size={14} />} />
          <Info label="Phí vào cửa (theo nguồn)" value={details.fee} icon={<Ticket size={14} />} />
          <Info label="Hỗ trợ xe lăn (theo nguồn)" value={details.wheelchair} icon={<Users size={14} />} />
          <Info label="Điện thoại" value={details.contact_phone} icon={<Phone size={14} />} />
          <Info label="Email" value={details.contact_email} />
          <div className="place-detail-info">
            <span><Globe2 size={14} /> Website</span>
            {website ? <a href={website} target="_blank" rel="noreferrer">Mở trang web <ExternalLink size={13} /></a> : <strong>{unavailable}</strong>}
          </div>
          <div className="place-detail-info">
            <span><MapPin size={14} /> Tọa độ</span>
            <a href={mapUrl} target="_blank" rel="noreferrer">{place.latitude.toFixed(6)}, {place.longitude.toFixed(6)} <ExternalLink size={13} /></a>
          </div>
        </div>
      </section>

      {experiences.length > 0 && (
        <section className="place-detail-section">
          <h2>Trải nghiệm trong catalog</h2>
          <div className="place-experience-list">
            {experiences.map((experience) => {
              const slots = Array.isArray(experience.slots) ? experience.slots : []
              return (
              <div className="place-experience-item" key={experience.id}>
                <strong>{experience.name}</strong>
                <span>{experience.description || unavailable}</span>
                <small>
                  {experience.duration_min} phút · {experience.price_vnd > 0 ? `${experience.price_vnd.toLocaleString('vi-VN')} ₫` : 'Giá chưa ghi nhận'}
                </small>
                {slots.length ? (
                  <ul className="place-slot-list">
                    {slots.map((slot) => (
                      <li key={slot.id}>
                        <strong>{new Date(slot.start_at).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })}</strong>
                        <span>Trạng thái: {slot.status} · Sức chứa còn báo cáo: {slot.available_reported ?? 'chưa có số liệu'}</span>
                        {slot.confirmed_at && <small>Cơ sở xác nhận lúc {new Date(slot.confirmed_at).toLocaleString('vi-VN')}</small>}
                        {slot.expires_at && <small>Dữ liệu slot hết hạn lúc {new Date(slot.expires_at).toLocaleString('vi-VN')}</small>}
                        {(Array.isArray(slot.source_evidence) ? slot.source_evidence : []).map((evidence) => (
                          <a href={evidence.source_uri} key={evidence.id} target="_blank" rel="noreferrer">
                            Nguồn slot: {evidence.source_label || evidence.source_type}
                          </a>
                        ))}
                      </li>
                    ))}
                  </ul>
                ) : <small>Chưa có ca/giờ phục vụ được công bố trong catalog.</small>}
              </div>
              )
            })}
          </div>
        </section>
      )}

      <section className="place-detail-section">
        <h2>Nguồn và thời điểm ghi nhận</h2>
        <div className="place-source-box">
          <span>Trạng thái dữ liệu: {place.data_mode === 'real' ? 'có bằng chứng nguồn trong catalog' : 'chưa được xác minh đầy đủ'}</span>
          <span>Quét/ghi nhận: {details.observed_at ? new Date(details.observed_at).toLocaleString('vi-VN') : unavailable}</span>
          {details.osm_timestamp && <span>OSM cập nhật: {String(details.osm_timestamp)}</span>}
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors · ODbL-1.0</a>
          {details.osm_url && externalUrl(String(details.osm_url)) && (
            <a href={String(details.osm_url)} target="_blank" rel="noreferrer">Bản ghi OpenStreetMap <ExternalLink size={13} /></a>
          )}
          {sourceEvidence.map((evidence) => (
            <a href={evidence.source_uri} target="_blank" rel="noreferrer" key={evidence.id}>
              {evidence.source_label || evidence.source_type} · {evidence.license || 'chưa ghi giấy phép'}
            </a>
          ))}
          {place.data_mode !== 'real' && <small>Thông tin nguồn có thể thiếu hoặc cũ; vui lòng kiểm tra với cơ sở trước khi đến.</small>}
        </div>
      </section>

      {tags.length > 0 && (
        <details className="place-detail-section place-raw-tags">
          <summary>Dữ liệu nguồn thô ({tags.length} trường OSM)</summary>
          <dl>{tags.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>
        </details>
      )}
    </article>
  )
}
