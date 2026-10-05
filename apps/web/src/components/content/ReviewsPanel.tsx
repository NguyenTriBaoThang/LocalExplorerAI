import { useEffect, useState } from 'react'
import { MessageSquare } from 'lucide-react'
import { contentApi } from '../../api/content'
import { useTranslation } from '../../i18n'
import type { ReviewSummary } from '../../types'
import { Stars } from './StarRating'
import './content.css'

/** Published reviews of one experience, with the partner's replies. */
export function ReviewsPanel({ experienceId }: { experienceId: string }) {
  const { locale } = useTranslation()
  const [data, setData] = useState<ReviewSummary | null>(null)
  useEffect(() => {
    setData(null)
    contentApi.experienceReviews(experienceId).then(setData).catch(() => setData({ count: 0, average: null, items: [] }))
  }, [experienceId])
  const vi = locale === 'vi'
  if (!data) return null

  return (
    <div className="reviews-panel">
      <h4>
        <MessageSquare size={16} /> {vi ? 'Đánh giá của du khách' : 'Traveler reviews'}
        {data.average !== null && <><Stars value={data.average} /><span className="review-date">{data.average} · {data.count}</span></>}
      </h4>
      {data.items.length === 0 ? (
        <p className="review-text" style={{ marginTop: 8 }}>{vi ? 'Chưa có đánh giá nào cho trải nghiệm này.' : 'No reviews for this experience yet.'}</p>
      ) : data.items.map((review) => (
        <div key={review.id} className="review-item">
          <div className="review-head">{review.author}<Stars value={review.rating} size={12} /><span className="review-date">{new Date(review.created_at).toLocaleDateString(vi ? 'vi-VN' : 'en-GB')}</span></div>
          {review.comment && <p className="review-text">{review.comment}</p>}
          {review.reply && <div className="review-reply"><strong>{vi ? 'Phản hồi từ đối tác' : 'Reply from the host'}</strong>{review.reply}</div>}
        </div>
      ))}
    </div>
  )
}
