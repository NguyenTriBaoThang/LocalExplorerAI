import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowUpRight,
  Compass,
  MapPin,
  Search,
  X,
  ExternalLink,
  ShieldCheck,
  Building2,
} from 'lucide-react'
import { getPOIs } from '../api/client'
import type { POI } from '../types'

const CATEGORY_TABS = [
  { id: 'all', label: 'Tất cả', icon: '✨' },
  { id: 'food', label: 'Ẩm thực', icon: '🍜' },
  { id: 'culture', label: 'Di sản & Văn hóa', icon: '🏛️' },
  { id: 'handicraft', label: 'Thủ công', icon: '🎨' },
  { id: 'nature', label: 'Thiên nhiên', icon: '🌿' },
  { id: 'relaxation', label: 'Thư giãn', icon: '🍵' },
]

export function PlacesPage() {
  const [places, setPlaces] = useState<POI[]>([])
  const [query, setQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getPOIs()
      .then(setPlaces)
      .catch(() => setError('Không tải được danh mục địa điểm. Hãy thử tải lại trang.'))
      .finally(() => setLoading(false))
  }, [])

  const filteredPlaces = useMemo(() => {
    let list = places
    if (selectedCategory !== 'all') {
      list = list.filter((p) => p.category === selectedCategory)
    }
    const val = query.trim().toLocaleLowerCase('vi')
    if (val) {
      list = list.filter((p) =>
        `${p.name} ${p.address} ${p.category} ${p.description}`
          .toLocaleLowerCase('vi')
          .includes(val)
      )
    }
    return list
  }, [places, selectedCategory, query])

  const categoryMeta: Record<string, { label: string; icon: string }> = {
    food: { label: 'Ẩm thực', icon: '🍜' },
    culture: { label: 'Di sản & Văn hóa', icon: '🏛️' },
    handicraft: { label: 'Thủ công mỹ nghệ', icon: '🎨' },
    nature: { label: 'Sinh thái & Tự nhiên', icon: '🌿' },
    relaxation: { label: 'Thư giãn & Wellness', icon: '🍵' },
  }

  return (
    <div className="page-wrap places-page">
      {/* Hero Header */}
      <header className="places-page-header">
        <div className="flex items-center gap-2 mb-2">
          <span className="eyebrow-3d">
            <span className="eyebrow-dot" /> DANH MỤC ĐỊA ĐIỂM SÀI GÒN
          </span>
          <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider">
            Pilot Quận 1
          </span>
        </div>

        <h1 className="page-heading-3d">
          Khám phá <em>Địa Điểm & Không Gian</em> Văn Hóa
        </h1>
        <p className="page-subtext-3d">
          Khám phá 124 điểm đến đặc sắc tại trung tâm Sài Gòn. Dữ liệu chuẩn xác từ OpenStreetMap, tích hợp định vị không gian và khung giờ thực.
        </p>

        {/* Live Metrics Row */}
        <div className="places-stats-row">
          <div className="places-stat-pill">
            <Building2 size={13} className="text-emerald-400" />
            <span><strong>{places.length || 124}</strong> địa điểm catalog</span>
          </div>
          <div className="places-stat-pill">
            <Compass size={13} className="text-cyan-400" />
            <span><strong>100%</strong> tọa độ GPS</span>
          </div>
          <div className="places-stat-pill">
            <ShieldCheck size={13} className="text-amber-400" />
            <span>Bảo vệ bản quyền ODbL-1.0</span>
          </div>
          <a
            href="https://www.openstreetmap.org/copyright"
            target="_blank"
            rel="noreferrer"
            className="places-stat-pill places-stat-link"
          >
            <span>© OpenStreetMap contributors</span>
            <ExternalLink size={11} />
          </a>
        </div>
      </header>

      {/* Filter and Search Bar Section */}
      <div className="places-controls-bar">
        {/* Category Tabs */}
        <div className="places-category-tabs">
          {CATEGORY_TABS.map((cat) => {
            const active = selectedCategory === cat.id
            const count = cat.id === 'all'
              ? places.length
              : places.filter((p) => p.category === cat.id).length

            return (
              <button
                key={cat.id}
                type="button"
                onClick={() => setSelectedCategory(cat.id)}
                className={`places-cat-btn ${active ? 'active' : ''}`}
              >
                <span>{cat.icon}</span>
                <span>{cat.label}</span>
                <span className="cat-count-badge">{count}</span>
              </button>
            )
          })}
        </div>

        {/* Search Input Box */}
        <div className="places-search-box">
          <Search size={18} className="search-icon" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tìm theo tên địa điểm, địa chỉ, loại hình…"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              className="search-clear-btn"
              title="Xóa tìm kiếm"
            >
              <X size={15} />
            </button>
          )}
        </div>
      </div>

      {error && <div className="inline-alert-3d mb-6">{error}</div>}

      {/* Results Header */}
      <div className="places-results-meta">
        <span>
          Hiển thị <strong>{filteredPlaces.length}</strong> địa điểm
          {selectedCategory !== 'all' && ` · ${CATEGORY_TABS.find((c) => c.id === selectedCategory)?.label}`}
          {query && ` cho từ khóa "${query}"`}
        </span>
        {query && (
          <button
            type="button"
            onClick={() => { setQuery(''); setSelectedCategory('all') }}
            className="text-xs text-emerald-400 hover:underline"
          >
            Đặt lại bộ lọc
          </button>
        )}
      </div>

      {loading ? (
        <div className="places-loading-box">
          <div className="places-spinner" />
          <p>Đang tải danh mục địa điểm Sài Gòn…</p>
        </div>
      ) : filteredPlaces.length > 0 ? (
        <div className="places-grid-elevated">
          {filteredPlaces.map((place) => {
            const sourcePhoto = place.details?.images?.find(
              (item) => (item.local_url || item.url) && item.source_url && item.license
            )
            const photoUrl =
              (sourcePhoto && (sourcePhoto.local_url || sourcePhoto.url)) ||
              place.image_urls?.[0] ||
              null

            const catInfo = categoryMeta[place.category] || { label: place.category, icon: '📍' }

            return (
              <Link
                className="place-card-elevated group"
                to={`/places/${encodeURIComponent(place.id)}`}
                key={place.id}
              >
                <div className="place-card-photo-box">
                  {photoUrl ? (
                    <img
                      src={photoUrl}
                      alt={place.name}
                      loading="lazy"
                      className="place-card-img"
                      onError={(e) => {
                        const img = e.currentTarget
                        img.style.display = 'none'
                        const fallback = img.parentElement?.querySelector('.place-card-fallback') as HTMLElement
                        if (fallback) fallback.style.display = 'flex'
                      }}
                    />
                  ) : null}

                  <div
                    className="place-card-fallback"
                    style={{ display: photoUrl ? 'none' : 'flex' }}
                  >
                    <span className="text-3xl mb-1">{catInfo.icon}</span>
                    <span className="text-xs font-semibold text-slate-300">{catInfo.label}</span>
                  </div>

                  <div className="place-card-gradient-overlay" />

                  {/* Top Badges */}
                  <div className="place-card-top-badges">
                    <span className="place-cat-pill">
                      <span>{catInfo.icon}</span> {catInfo.label}
                    </span>
                    <span className="place-action-circle">
                      <ArrowUpRight size={14} />
                    </span>
                  </div>

                  {/* Bottom Badges */}
                  <div className="place-card-bottom-badges">
                    <span className="place-district-pill">
                      <MapPin size={11} /> {place.district || 'Quận 1, TP.HCM'}
                    </span>
                    {place.verification_status === 'verified' && (
                      <span className="place-verified-pill">
                        <ShieldCheck size={11} /> Đã duyệt
                      </span>
                    )}
                  </div>
                </div>

                <div className="place-card-body-content">
                  <h3 className="place-card-title group-hover:text-emerald-400 transition-colors">
                    {place.name}
                  </h3>

                  <p className="place-card-address">
                    <MapPin size={12} className="shrink-0 text-emerald-400 mt-0.5" />
                    <span>{place.address || 'Trung tâm TP. Hồ Chí Minh'}</span>
                  </p>

                  {place.description && (
                    <p className="place-card-desc">
                      {place.description}
                    </p>
                  )}

                  <div className="place-card-footer">
                    <span className="place-card-cta">
                      Xem chi tiết địa điểm <ArrowUpRight size={13} />
                    </span>
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      ) : (
        <div className="places-empty-box">
          <div className="empty-icon-wrap">
            <Search size={32} />
          </div>
          <h3>Không tìm thấy địa điểm phù hợp</h3>
          <p>Hãy thử tìm kiếm với từ khóa khác hoặc chuyển sang danh mục "Tất cả".</p>
          <button
            type="button"
            onClick={() => { setQuery(''); setSelectedCategory('all') }}
            className="btn-reset-search"
          >
            Xem tất cả {places.length} địa điểm
          </button>
        </div>
      )}
    </div>
  )
}
