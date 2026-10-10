import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, MapPin, Search } from 'lucide-react'
import { getPOIs } from '../api/client'
import type { POI } from '../types'

export function PlacesPage() {
  const [places, setPlaces] = useState<POI[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getPOIs()
      .then(setPlaces)
      .catch(() => setError('Không tải được danh mục địa điểm. Hãy thử tải lại trang.'))
      .finally(() => setLoading(false))
  }, [])

  const visible = useMemo(() => {
    const value = query.trim().toLocaleLowerCase('vi')
    if (!value) return places
    return places.filter((place) =>
      `${place.name} ${place.address} ${place.category} ${place.description}`
        .toLocaleLowerCase('vi')
        .includes(value)
    )
  }, [places, query])

  return (
    <div className="page-wrap places-page">
      <header className="places-page-header">
        <span className="eyebrow-3d"><span className="eyebrow-dot" /> DANH MỤC ĐỊA ĐIỂM</span>
        <h1 className="page-heading-3d">Khám phá <em>địa điểm Quận 1</em></h1>
        <p className="page-subtext-3d">
          Chỉ hiển thị POI đã được đưa vào catalog của dự án. Dữ liệu còn thiếu được ghi rõ, không tự suy đoán.
        </p>
        <p className="places-count">Nguồn địa điểm: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors · ODbL-1.0</a></p>
      </header>

      <label className="places-search">
        <Search size={17} />
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm tên, địa chỉ, loại địa điểm…" />
      </label>

      {error && <div className="inline-alert-3d">{error}</div>}
      {loading ? <p className="places-empty">Đang tải catalog địa điểm…</p> : (
        <>
          <p className="places-count">{visible.length} địa điểm trong catalog · ảnh chỉ hiện khi có nguồn và thông tin giấy phép</p>
          <div className="places-grid">
            {visible.map((place) => {
              const photo = place.details?.images?.find((item) => (item.local_url || item.url) && item.source_url && item.license)
              return (
                <Link className="place-card" to={`/places/${encodeURIComponent(place.id)}`} key={place.id}>
                  {photo ? (
                    <img src={photo.local_url || photo.url} alt={place.name} loading="lazy" />
                  ) : (
                    <div className="place-card-no-photo"><MapPin size={24} /><span>Chưa có ảnh nguồn hợp lệ</span></div>
                  )}
                  <div className="place-card-body">
                    <span className="place-card-category">{place.category}</span>
                    <strong>{place.name}</strong>
                    <small><MapPin size={12} /> {place.address || 'Chưa có địa chỉ trong nguồn'}</small>
                    <span className="place-card-details">Xem thông tin địa điểm <ArrowUpRight size={14} /></span>
                  </div>
                </Link>
              )
            })}
          </div>
          {!visible.length && <p className="places-empty">Không tìm thấy địa điểm trong catalog.</p>}
        </>
      )}
    </div>
  )
}
