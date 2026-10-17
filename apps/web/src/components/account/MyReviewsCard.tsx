import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MessageSquare } from 'lucide-react'
import { myReviewsApi, placeReviewsApi } from '../../api/content'
import { reviewErrorMessage } from '../content/PlaceReviews'
import { StarInput, Stars } from '../content/StarRating'
import { useTranslation } from '../../i18n'
import type { MyReviewsResponse } from '../../types'
import '../content/content.css'

type Key = string // "p:<poi_id>" or "e:<booking_id>"

export function MyReviewsCard() {
  const { locale } = useTranslation()
  const vi = locale === 'vi'
  const [data, setData] = useState<MyReviewsResponse | null>(null)
  const [failed, setFailed] = useState(false)
  const [editKey, setEditKey] = useState<Key | null>(null)
  const [rating, setRating] = useState(5)
  const [comment, setComment] = useState('')
  const [confirmKey, setConfirmKey] = useState<Key | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    myReviewsApi.list().then((d) => { setData(d); setFailed(false) }).catch(() => setFailed(true))
  }, [])
  useEffect(() => { load() }, [load])

  const startEdit = (key: Key, r: number, c: string) => { setEditKey(key); setRating(r); setComment(c); setError(''); setConfirmKey(null) }

  const save = async (key: Key, visitedOn?: string | null) => {
    setBusy(true); setError('')
    try {
      const id = key.slice(2)
      if (key.startsWith('p:')) await placeReviewsApi.save(id, { rating, comment: comment.trim() || undefined, visited_on: visitedOn || undefined })
      else await myReviewsApi.editExperience(id, rating, comment.trim())
      setEditKey(null); load()
    } catch (err) { setError(reviewErrorMessage(err, vi)) } finally { setBusy(false) }
  }
  const remove = async (key: Key) => {
    setBusy(true); setError('')
    try {
      const id = key.slice(2)
      if (key.startsWith('p:')) await placeReviewsApi.remove(id)
      else await myReviewsApi.removeExperience(id)
      setConfirmKey(null); load()
    } catch (err) { setError(reviewErrorMessage(err, vi)) } finally { setBusy(false) }
  }

  const editor = (key: Key, visitedOn?: string | null) => (
    <div className="review-form" style={{ marginTop: 6 }}>
      <StarInput value={rating} onChange={setRating} label={vi ? 'Số sao' : 'Rating'} />
      <textarea value={comment} maxLength={2000} onChange={(e) => setComment(e.target.value)} aria-label={vi ? 'Nội dung đánh giá' : 'Review text'} />
      {error && <p className="pr-error-text" role="alert">{error}</p>}
      <div className="pr-actions">
        <button type="button" className="btn-secondary-3d btn-sm" onClick={() => setEditKey(null)}>{vi ? 'Hủy' : 'Cancel'}</button>
        <button type="button" className="btn-primary-3d btn-sm" disabled={busy} onClick={() => save(key, visitedOn)}>{vi ? 'Lưu' : 'Save'}</button>
      </div>
    </div>
  )
  const actions = (key: Key, r: number, c: string) => (
    <div className="pr-actions" style={{ justifyContent: 'flex-start' }}>
      {confirmKey === key ? (
        <>
          <span className="pr-note" style={{ marginTop: 0 }}>{vi ? 'Xóa đánh giá này?' : 'Delete this review?'}</span>
          <button type="button" className="btn-primary-3d btn-sm" disabled={busy} onClick={() => remove(key)}>{vi ? 'Xóa' : 'Delete'}</button>
          <button type="button" className="btn-secondary-3d btn-sm" onClick={() => setConfirmKey(null)}>{vi ? 'Hủy' : 'Cancel'}</button>
        </>
      ) : (
        <>
          <button type="button" className="btn-secondary-3d btn-sm" onClick={() => startEdit(key, r, c)}>{vi ? 'Sửa' : 'Edit'}</button>
          <button type="button" className="btn-secondary-3d btn-sm" onClick={() => { setConfirmKey(key); setEditKey(null); setError('') }}>{vi ? 'Xóa' : 'Delete'}</button>
        </>
      )}
    </div>
  )

  const empty = data && data.places.length === 0 && data.experiences.length === 0
  return (
    <section className="profile-card-3d mr-card">
      <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-main)', fontWeight: 700 }}>
        <MessageSquare size={18} className="text-amber" /> {vi ? 'Đánh giá của tôi' : 'My reviews'}
      </h3>
      {failed && (
        <p className="review-text" role="alert">
          {vi ? 'Không tải được đánh giá.' : 'Could not load reviews.'}{' '}
          <button type="button" className="btn-secondary-3d btn-sm" onClick={load}>{vi ? 'Thử lại' : 'Retry'}</button>
        </p>
      )}
      {!data && !failed && <p className="review-text">{vi ? 'Đang tải…' : 'Loading…'}</p>}
      {empty && <p className="review-text">{vi ? 'Bạn chưa có đánh giá nào.' : 'You have no reviews yet.'}</p>}
      {error && editKey === null && confirmKey !== null && <p className="pr-error-text" role="alert">{error}</p>}
      {data && data.places.length > 0 && <h4 className="pr-form-title" style={{ marginTop: 12 }}>{vi ? 'Địa điểm' : 'Places'}</h4>}
      {data?.places.map((r) => {
        const key = `p:${r.poi_id}`
        return (
          <div className="mr-item" key={r.id}>
            <div className="review-head">
              <Link to={`/places/${r.poi_id}`}>{r.poi_name}</Link>
              <Stars value={r.rating} />
              {r.status === 'hidden' && <span className="pr-badge pr-badge-warn">{vi ? 'Đang bị ẩn' : 'Hidden'}</span>}
            </div>
            {editKey === key ? editor(key, r.visited_on) : (
              <>
                {r.comment && <p className="review-text">{r.comment}</p>}
                {actions(key, r.rating, r.comment)}
              </>
            )}
          </div>
        )
      })}
      {data && data.experiences.length > 0 && <h4 className="pr-form-title" style={{ marginTop: 12 }}>{vi ? 'Trải nghiệm' : 'Experiences'}</h4>}
      {data?.experiences.map((r) => {
        const key = `e:${r.booking_id}`
        return (
          <div className="mr-item" key={r.id}>
            <div className="review-head">
              <Link to={`/experiences/${r.experience_id}`}>{r.experience_title}</Link>
              <Stars value={r.rating} />
              {r.status === 'hidden' && <span className="pr-badge pr-badge-warn">{vi ? 'Đang bị ẩn' : 'Hidden'}</span>}
            </div>
            {editKey === key ? editor(key) : (
              <>
                {r.comment && <p className="review-text">{r.comment}</p>}
                {r.reply && <div className="review-reply"><strong>{vi ? 'Phản hồi từ đối tác' : 'Partner reply'}</strong>{r.reply}</div>}
                {actions(key, r.rating, r.comment)}
              </>
            )}
          </div>
        )
      })}
    </section>
  )
}
