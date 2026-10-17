import { useEffect, useState } from 'react'
import { Star } from 'lucide-react'
import { contentApi } from '../../api/content'
import { apiErrorMessage } from '../../api/client'
import { useTranslation } from '../../i18n'
import type { ReviewableBooking } from '../../types'
import { StarInput } from './StarRating'
import './content.css'

/** "Rate your experience" card on the traveler profile for attended bookings that have no review yet. */
export function ReviewPrompt() {
  const { locale } = useTranslation()
  const vi = locale === 'vi'
  const [items, setItems] = useState<ReviewableBooking[]>([])
  const [open, setOpen] = useState<string | null>(null)
  const [rating, setRating] = useState(5)
  const [comment, setComment] = useState('')
  const [message, setMessage] = useState('')

  const load = () => contentApi.reviewableBookings().then(setItems).catch(() => setItems([]))
  useEffect(() => { void load() }, [])
  if (items.length === 0 && !message) return null

  const submit = async (bookingId: string) => {
    try {
      await contentApi.reviewBooking(bookingId, rating, comment.trim())
      setMessage(vi ? 'Cảm ơn bạn đã đánh giá!' : 'Thanks for your review!')
      setOpen(null)
      setComment('')
      void load()
    } catch (error) {
      setMessage(apiErrorMessage(error))
    }
  }

  return (
    <section className="profile-card-3d">
      <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-main)', fontWeight: 700 }}>
        <Star size={18} className="text-amber" /> {vi ? 'Đánh giá trải nghiệm đã tham gia' : 'Rate experiences you attended'}
      </h3>
      {message && <p className="review-text" style={{ marginTop: 8 }}>{message}</p>}
      <div className="review-form" style={{ marginTop: 8 }}>
        {items.map((item) => (
          <div key={item.booking_id}>
            <div className="review-form-row">
              <div>
                <p style={{ color: 'var(--text-main)', fontWeight: 600 }}>{item.experience_title}</p>
                <p className="review-date">{new Date(item.slot_start_at).toLocaleString(vi ? 'vi-VN' : 'en-GB')}</p>
              </div>
              {open !== item.booking_id && (
                <button type="button" className="btn-secondary-3d btn-sm" onClick={() => { setOpen(item.booking_id); setRating(5); setComment('') }}>
                  {vi ? 'Đánh giá' : 'Rate'}
                </button>
              )}
            </div>
            {open === item.booking_id && (
              <div style={{ paddingBottom: 14 }}>
                <StarInput value={rating} onChange={setRating} label={vi ? 'Số sao' : 'Rating'} />
                <textarea value={comment} maxLength={2000} onChange={(e) => setComment(e.target.value)}
                  placeholder={vi ? 'Chia sẻ cảm nhận của bạn (không bắt buộc)' : 'Share your experience (optional)'} />
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
                  <button type="button" className="btn-secondary-3d btn-sm" onClick={() => setOpen(null)}>{vi ? 'Hủy' : 'Cancel'}</button>
                  <button type="button" className="btn-primary-3d btn-sm" onClick={() => submit(item.booking_id)}>{vi ? 'Gửi đánh giá' : 'Submit'}</button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}
