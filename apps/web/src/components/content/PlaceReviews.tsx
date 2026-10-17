import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ExternalLink, Star } from 'lucide-react'
import { placeReviewsApi } from '../../api/content'
import { useAuth } from '../../auth'
import { useTranslation } from '../../i18n'
import type { MyPlaceReviewState, PlaceReviewsResponse } from '../../types'
import { StarInput, Stars } from './StarRating'
import './content.css'

export function reviewErrorMessage(error: unknown, vi: boolean): string {
  const resp = (error as { response?: { status?: number; data?: { error?: { code?: string } } } } | null)?.response
  const code = resp?.data?.error?.code
  if (code === 'REVIEW_REJECTED') return vi ? 'Nội dung đánh giá không được chứa liên kết.' : 'Reviews cannot contain links.'
  if (code === 'VISIT_DATE_IN_FUTURE') return vi ? 'Ngày ghé thăm không được ở tương lai.' : 'The visit date cannot be in the future.'
  if (code === 'REVIEW_NOT_ALLOWED') return vi ? 'Bạn cần có lịch trình chứa địa điểm này để đánh giá.' : 'You need an itinerary containing this place to review it.'
  if (resp?.status === 401) return vi ? 'Vui lòng đăng nhập để tiếp tục.' : 'Please sign in to continue.'
  return vi ? 'Không thể thực hiện. Vui lòng thử lại.' : 'Something went wrong. Please try again.'
}

const fmtDate = (iso: string, vi: boolean) => new Date(iso).toLocaleDateString(vi ? 'vi-VN' : 'en-GB')
const fmtVisit = (d: string, vi: boolean) => {
  const [y, m, day] = d.split('-')
  return vi ? `${day}/${m}/${y}` : `${day}/${m}/${y}`
}
const todayStr = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function PlaceReviews({ poiId }: { poiId: string }) {
  const { locale } = useTranslation()
  const vi = locale === 'vi'
  const { user } = useAuth()
  const location = useLocation()
  const isTraveler = user?.role === 'traveler'
  const isStaff = !!user && !isTraveler

  const [data, setData] = useState<PlaceReviewsResponse | null>(null)
  const [failed, setFailed] = useState(false)
  const [mine, setMine] = useState<MyPlaceReviewState | null>(null)
  const [editing, setEditing] = useState(false)
  const [rating, setRating] = useState(5)
  const [comment, setComment] = useState('')
  const [visited, setVisited] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)

  const loadPublic = useCallback(() => {
    setFailed(false)
    placeReviewsApi.list(poiId).then(setData).catch(() => setFailed(true))
  }, [poiId])
  const loadMine = useCallback(() => {
    if (!isTraveler) { setMine(null); return }
    placeReviewsApi.mine(poiId).then(setMine).catch(() => setMine(null))
  }, [poiId, isTraveler])

  useEffect(() => { setData(null); loadPublic() }, [loadPublic])
  useEffect(() => { loadMine() }, [loadMine])

  const startEdit = () => {
    const r = mine?.review
    setRating(r?.rating ?? 5); setComment(r?.comment ?? ''); setVisited(r?.visited_on ?? ''); setError(''); setEditing(true)
  }
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      await placeReviewsApi.save(poiId, { rating, comment: comment.trim() || undefined, visited_on: visited || undefined })
      setEditing(false)
      loadPublic(); loadMine()
    } catch (err) { setError(reviewErrorMessage(err, vi)) } finally { setBusy(false) }
  }
  const remove = async () => {
    setBusy(true); setError('')
    try {
      await placeReviewsApi.remove(poiId)
      setConfirmDelete(false)
      loadPublic(); loadMine()
    } catch (err) { setError(reviewErrorMessage(err, vi)) } finally { setBusy(false) }
  }

  const title = vi ? 'Đánh giá' : 'Reviews'
  if (failed) {
    return (
      <section className="pr-section" aria-labelledby="pr-title">
        <h2 id="pr-title" className="section-title-3d" style={{ fontSize: 22 }}>{title}</h2>
        <div className="pr-card pr-error" role="alert">
          <p>{vi ? 'Không tải được đánh giá.' : 'Could not load reviews.'}</p>
          <button type="button" className="btn-secondary-3d btn-sm" onClick={loadPublic}>{vi ? 'Thử lại' : 'Retry'}</button>
        </div>
      </section>
    )
  }
  if (!data) {
    return (
      <section className="pr-section" aria-busy="true" aria-label={title}>
        <h2 className="section-title-3d" style={{ fontSize: 22 }}>{title}</h2>
        <div className="pr-grid"><div className="pr-skeleton" /><div className="pr-skeleton" /></div>
      </section>
    )
  }

  const { community, google } = data
  const maxBar = Math.max(1, ...[1, 2, 3, 4, 5].map((n) => community.distribution[String(n)] ?? 0))
  const safeMaps = google?.maps_uri && /^https?:\/\//i.test(google.maps_uri) ? google.maps_uri : null
  const own = mine?.review ?? null
  const showForm = isTraveler && mine && (editing || (!own && mine.can_review && mine.reason !== 'no_itinerary'))

  return (
    <section className="pr-section" aria-labelledby="pr-title">
      <h2 id="pr-title" className="section-title-3d" style={{ fontSize: 22 }}>{title}</h2>
      <div className={`pr-grid${google ? '' : ' pr-grid-single'}`}>
        <div className="pr-card">
          <h3 className="pr-card-title">{vi ? 'Du khách Local Explorer' : 'Local Explorer travelers'}</h3>
          <div className="pr-summary">
            <div className="pr-score">
              <strong>{community.average != null ? community.average.toFixed(1) : '–'}</strong>
              {community.average != null && <Stars value={community.average} size={16} />}
              <span className="review-date">{community.count} {vi ? 'đánh giá' : community.count === 1 ? 'review' : 'reviews'}</span>
            </div>
            <div className="pr-dist" aria-label={vi ? 'Phân bố số sao' : 'Rating distribution'}>
              {[5, 4, 3, 2, 1].map((n) => {
                const c = community.distribution[String(n)] ?? 0
                return (
                  <div className="pr-dist-row" key={n}>
                    <span className="pr-dist-label">{n}<Star size={12} fill="currentColor" /></span>
                    <span className="pr-bar"><span className="pr-bar-fill" style={{ width: `${(c / maxBar) * 100}%` }} /></span>
                    <span className="pr-dist-count">{c}</span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* own review / write area */}
          {!user && (
            <Link to="/login" state={{ from: location.pathname }} className="btn-secondary-3d btn-sm pr-action">
              {vi ? 'Đăng nhập để đánh giá' : 'Sign in to review'}
            </Link>
          )}
          {isStaff && <p className="pr-note">{vi ? 'Tài khoản quản trị/đối tác không thể đánh giá địa điểm.' : 'Staff accounts cannot review places.'}</p>}
          {isTraveler && mine && !own && mine.reason === 'no_itinerary' && (
            <p className="pr-note">
              {vi ? 'Hãy lên lịch trình có địa điểm này để có thể đánh giá. ' : 'Create an itinerary that includes this place to be able to review it. '}
              <Link to="/planner">{vi ? 'Mở trình lập lịch' : 'Open planner'}</Link>
            </p>
          )}
          {isTraveler && mine && !own && !mine.can_review && mine.reason !== 'no_itinerary' && (
            <p className="pr-note">{vi ? 'Bạn chưa thể đánh giá địa điểm này.' : 'You cannot review this place yet.'}</p>
          )}
          {own && !editing && (
            <div className="pr-own">
              <div className="review-head">
                <span>{vi ? 'Đánh giá của bạn' : 'Your review'}</span>
                <Stars value={own.rating} />
                <span className="review-date">{fmtDate(own.updated_at ?? own.created_at, vi)}</span>
              </div>
              {own.status === 'hidden' && (
                <p className="pr-hidden" role="status">{vi ? 'Đánh giá này đã bị người kiểm duyệt ẩn và không hiển thị với người khác.' : 'This review was hidden by a moderator and is not visible to others.'}</p>
              )}
              {own.visited_on && <p className="review-date">{vi ? 'Đã ghé: ' : 'Visited: '}{fmtVisit(own.visited_on, vi)}</p>}
              {own.comment && <p className="review-text">{own.comment}</p>}
              <div className="pr-actions">
                {!confirmDelete ? (
                  <>
                    <button type="button" className="btn-secondary-3d btn-sm" onClick={startEdit}>{vi ? 'Sửa' : 'Edit'}</button>
                    <button type="button" className="btn-secondary-3d btn-sm" onClick={() => setConfirmDelete(true)}>{vi ? 'Xóa' : 'Delete'}</button>
                  </>
                ) : (
                  <>
                    <span className="pr-note">{vi ? 'Xóa đánh giá này?' : 'Delete this review?'}</span>
                    <button type="button" className="btn-primary-3d btn-sm" disabled={busy} onClick={remove}>{vi ? 'Xóa' : 'Delete'}</button>
                    <button type="button" className="btn-secondary-3d btn-sm" onClick={() => setConfirmDelete(false)}>{vi ? 'Hủy' : 'Cancel'}</button>
                  </>
                )}
              </div>
              {error && <p className="pr-error-text" role="alert">{error}</p>}
            </div>
          )}
          {showForm && (
            <form className="review-form pr-form" onSubmit={submit}>
              <p className="pr-form-title">{own ? (vi ? 'Sửa đánh giá của bạn' : 'Edit your review') : (vi ? 'Viết đánh giá' : 'Write a review')}</p>
              <StarInput value={rating} onChange={setRating} label={vi ? 'Số sao' : 'Rating'} />
              <textarea value={comment} maxLength={2000} onChange={(e) => setComment(e.target.value)}
                aria-label={vi ? 'Nội dung đánh giá' : 'Review text'}
                placeholder={vi ? 'Chia sẻ trải nghiệm của bạn (không bắt buộc)' : 'Share your experience (optional)'} />
              <div className="pr-counter">{comment.length}/2000</div>
              <label className="pr-date-label">
                <span>{vi ? 'Ngày ghé thăm (không bắt buộc)' : 'Visit date (optional)'}</span>
                <input type="date" value={visited} max={todayStr()} onChange={(e) => setVisited(e.target.value)} />
              </label>
              {error && <p className="pr-error-text" role="alert">{error}</p>}
              <div className="pr-actions">
                {editing && <button type="button" className="btn-secondary-3d btn-sm" onClick={() => { setEditing(false); setError('') }}>{vi ? 'Hủy' : 'Cancel'}</button>}
                <button type="submit" className="btn-primary-3d btn-sm" disabled={busy}>{vi ? 'Gửi đánh giá' : 'Submit review'}</button>
              </div>
            </form>
          )}

          <div className="pr-list">
            {community.items.length === 0 && <p className="pr-note">{vi ? 'Chưa có đánh giá nào từ du khách. Hãy là người đầu tiên!' : 'No traveler reviews yet. Be the first!'}</p>}
            {community.items.map((r) => (
              <div className="review-item" key={r.id}>
                <div className="review-head">
                  <span>{r.author}</span>
                  <Stars value={r.rating} />
                  <span className="review-date">{fmtDate(r.created_at, vi)}</span>
                  {r.edited && <span className="pr-badge">{vi ? 'đã chỉnh sửa' : 'edited'}</span>}
                </div>
                {r.visited_on && <p className="review-date">{vi ? 'Đã ghé: ' : 'Visited: '}{fmtVisit(r.visited_on, vi)}</p>}
                {r.comment && <p className="review-text">{r.comment}</p>}
              </div>
            ))}
          </div>
        </div>

        {google && (
          <aside className="pr-card pr-google" aria-label="Google Maps">
            <h3 className="pr-card-title pr-google-head">Google Maps</h3>
            <div className="pr-score">
              <strong>{google.rating.toFixed(1)}</strong>
              <Stars value={google.rating} size={16} />
              <span className="review-date">({google.rating_count.toLocaleString(vi ? 'vi-VN' : 'en-GB')} {vi ? 'đánh giá' : 'reviews'})</span>
            </div>
            <p className="pr-note">{vi ? 'Dữ liệu từ Google Maps' : 'Data from Google Maps'}</p>
            <p className="review-date">{vi ? 'Cập nhật: ' : 'Updated: '}{fmtDate(google.fetched_at, vi)}</p>
            {safeMaps && (
              <a className="pr-link" href={safeMaps} target="_blank" rel="noreferrer noopener">
                <ExternalLink size={14} /> {vi ? 'Xem trên Google Maps' : 'View on Google Maps'}
              </a>
            )}
          </aside>
        )}
      </div>
    </section>
  )
}
