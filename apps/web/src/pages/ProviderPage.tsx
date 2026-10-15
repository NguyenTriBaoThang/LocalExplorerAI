import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, MapPin, Search, Store } from 'lucide-react'
import { contentApi } from '../api/content'
import '../components/content/content.css'
import { Stars } from '../components/content/StarRating'
import { useTranslation } from '../i18n'
import type { PartnerSummary } from '../types'

const CATEGORY_KEYS: Record<string, string> = {
  food: 'explore.intentFood', handicraft: 'explore.intentCraft', culture: 'explore.intentCulture', nature: 'explore.intentNature', relaxation: 'explore.intentRelax',
}

const PORTAL_URL = ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_PORTAL_URL || 'http://localhost:5174').replace(/\/$/, '')

export function ProviderPage() {
  const { t, locale } = useTranslation()
  const vi = locale === 'vi'
  const [input, setInput] = useState('')
  const [q, setQ] = useState('')
  const [partners, setPartners] = useState<PartnerSummary[] | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const t = window.setTimeout(() => setQ(input.trim()), 300)
    return () => window.clearTimeout(t)
  }, [input])

  useEffect(() => {
    let alive = true
    setError(false)
    setPartners(null)
    contentApi.partners(q).then((d) => alive && setPartners(d)).catch(() => alive && setError(true))
    return () => { alive = false }
  }, [q, attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])

  return (
    <div className="pd-wrap">
      <section className="pd-hero">
        <div className="pd-hero-main">
        <h1>{vi ? 'Đối tác địa phương' : 'Local partners'}</h1>
        <p>{vi ? 'Các cơ sở và đơn vị tổ chức trải nghiệm đã được duyệt trên LocalExplorer. Xem đánh giá thật từ du khách trước khi đặt.' : 'Approved venues and experience hosts on LocalExplorer. Read real traveler reviews before you book.'}</p>
        <label className="pd-search">
          <Search size={18} aria-hidden />
          <input type="search" value={input} onChange={(e) => setInput(e.target.value)} aria-label={vi ? 'Tìm đối tác' : 'Search partners'} placeholder={vi ? 'Tìm theo tên, loại hình, địa chỉ…' : 'Search by name, category, address…'} />
        </label>
        </div>
        <aside className="pd-hero-side">
          <strong>{vi ? 'Bạn điều hành một cơ sở hoặc tour?' : 'Run a venue or tour?'}</strong>
          <span>{vi ? 'Hồ sơ được quản trị viên xem xét trước khi hiển thị.' : 'Your profile is reviewed by an admin before it appears.'}</span>
          <a className="pd-btn pd-btn-primary" href={`${PORTAL_URL}/register`}>{vi ? 'Đăng ký trở thành đối tác' : 'Become a partner'}</a>
        </aside>
      </section>

      {partners && !error && <p className="pd-count" aria-live="polite">{vi ? `${partners.length} đối tác${q ? ` cho “${q}”` : ''}` : `${partners.length} partner${partners.length === 1 ? '' : 's'}${q ? ` for “${q}”` : ''}`}</p>}
      {!partners && !error && <p className="pd-count">{vi ? 'Đang tải…' : 'Loading…'}</p>}

      {error ? (
        <div className="pd-state" role="alert">
          <AlertCircle size={28} />
          <h3>{vi ? 'Không tải được danh sách đối tác' : 'Could not load partners'}</h3>
          <p>{vi ? 'Vui lòng kiểm tra kết nối rồi thử lại.' : 'Please check your connection and try again.'}</p>
          <button type="button" className="pd-btn" onClick={retry}>{vi ? 'Thử lại' : 'Retry'}</button>
        </div>
      ) : !partners ? (
        <div className="pd-grid" aria-busy="true">{[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="pd-skeleton" />)}</div>
      ) : partners.length === 0 ? (
        <div className="pd-state">
          <Store size={28} />
          <h3>{q ? (vi ? 'Không có đối tác phù hợp' : 'No matching partners') : (vi ? 'Chưa có đối tác nào' : 'No partners yet')}</h3>
          <p>{q ? (vi ? 'Thử từ khóa khác.' : 'Try a different keyword.') : (vi ? 'Đối tác sẽ xuất hiện khi có trải nghiệm được mở.' : 'Partners appear once they have an open experience.')}</p>
        </div>
      ) : (
        <div className="pd-grid">
          {partners.map((p) => {
            const cover = p.cover_url && /^https?:\/\//i.test(p.cover_url) ? p.cover_url : null
            return (
              <article key={p.id} className="pd-card">
                <div className={`pd-cover${cover ? '' : ' pd-cover-empty'}`}>
                  <Store size={34} aria-hidden />
                  {cover && <img src={cover} alt="" loading="lazy" onError={(e) => { e.currentTarget.style.display = 'none' }} />}
                </div>
                <div className="pd-card-body">
                  <h3>{p.name}</h3>
                  {p.description && <p className="pd-desc">{p.description}</p>}
                  {p.address && <div className="pd-line"><MapPin size={14} /><span>{p.address}</span></div>}
                  {p.categories.length > 0 && <div className="pd-chips">{p.categories.slice(0, 3).map((c) => <span key={c} className="tag-chip">{CATEGORY_KEYS[c] ? t(CATEGORY_KEYS[c]) : c.replaceAll('_', ' ')}</span>)}</div>}
                  <div className="pd-rating">
                    {p.rating_average != null && p.rating_count > 0
                      ? <><Stars value={p.rating_average} size={13} />{p.rating_average.toFixed(1)} ({p.rating_count})</>
                      : <span className="pd-muted">{vi ? 'Chưa có đánh giá' : 'No reviews yet'}</span>}
                  </div>
                  <div className="pd-foot">
                    <span>{p.experience_count} {vi ? 'trải nghiệm đang mở' : p.experience_count === 1 ? 'open experience' : 'open experiences'}</span>
                    {p.min_price_vnd != null && <span>{vi ? 'Từ ' : 'From '}<strong>{p.min_price_vnd.toLocaleString('vi-VN')}₫</strong></span>}
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}

    </div>
  )
}
