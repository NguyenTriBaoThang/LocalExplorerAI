import { useEffect, useState } from 'react'
import { MessageSquareReply, Star } from 'lucide-react'
import { Avatar, Button, Card, cx, EmptyState, PageHeader, Spinner, Tabs, Textarea, useToast } from '../../components/ui'
import { errorMessage, partnerApi } from '../../lib/api'
import { timeAgo } from '../../lib/format'
import type { Review } from '../../lib/types'

function Stars({ value, size = 'h-4 w-4' }: { value: number; size?: string }) {
  return (
    <span className="inline-flex gap-0.5" aria-label={`${value} sao`}>
      {[1, 2, 3, 4, 5].map((i) => <Star key={i} className={cx(size, i <= value ? 'fill-amber-400 text-amber-400' : 'text-slate-200')} />)}
    </span>
  )
}

export function PartnerReviewsPage() {
  const toast = useToast()
  const [reviews, setReviews] = useState<Review[] | null>(null)
  const [filter, setFilter] = useState<'all' | 'unreplied'>('all')
  const [replying, setReplying] = useState<string | null>(null)
  const [text, setText] = useState('')
  const load = () => partnerApi.reviews().then(setReviews).catch((err) => { toast.error(errorMessage(err)); setReviews([]) })
  useEffect(() => { void load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const list = (reviews ?? []).filter((r) => filter === 'all' || !r.reply)
  const average = reviews?.length ? reviews.reduce((s, r) => s + r.rating, 0) / reviews.length : 0
  const distribution = [5, 4, 3, 2, 1].map((star) => ({ star, count: (reviews ?? []).filter((r) => r.rating === star).length }))

  return (
    <>
      <PageHeader title="Đánh giá" description="Phản hồi của du khách sau khi tham gia trải nghiệm." />
      {!reviews ? <Spinner /> : (
        <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
          <Card className="h-fit p-6">
            <p className="text-sm text-slate-500">Điểm trung bình</p>
            {reviews.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">Chưa có đánh giá. Du khách đánh giá được sau khi tham gia booking đã xác nhận.</p>
            ) : (
              <>
                <p className="mt-1 text-4xl font-bold text-slate-900">{average.toFixed(1)}</p>
                <Stars value={Math.round(average)} size="h-5 w-5" />
                <p className="mt-1 text-sm text-slate-500">{reviews.length} đánh giá</p>
              </>
            )}
            <ul className="mt-5 space-y-2">
              {distribution.map((row) => (
                <li key={row.star} className="flex items-center gap-2 text-sm">
                  <span className="w-6 text-slate-600">{row.star}★</span>
                  <span className="h-1.5 flex-1 rounded-full bg-slate-100"><span className="block h-full rounded-full bg-amber-400" style={{ width: `${(row.count / Math.max(reviews.length, 1)) * 100}%` }} /></span>
                  <span className="w-6 text-right text-slate-500">{row.count}</span>
                </li>
              ))}
            </ul>
          </Card>
          <div>
            <div className="mb-4"><Tabs value={filter} onChange={setFilter} items={[{ value: 'all', label: 'Tất cả', count: reviews.length }, { value: 'unreplied', label: 'Chưa trả lời', count: reviews.filter((r) => !r.reply).length }]} /></div>
            {list.length === 0 ? <Card><EmptyState icon={Star} title="Không có đánh giá nào" /></Card> : (
              <div className="space-y-4">
                {list.map((review) => (
                  <Card key={review.id} className="p-5">
                    <div className="flex items-start gap-3">
                      <Avatar name={review.author} />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                          <p className="font-medium text-slate-900">{review.author}</p>
                          <Stars value={review.rating} />
                          <span className="text-xs text-slate-400">{timeAgo(review.created_at)}</span>
                        </div>
                        <p className="text-xs text-slate-500">{review.experience_title}</p>
                        {review.comment && <p className="mt-2 text-sm text-slate-700">{review.comment}</p>}
                        {review.reply && (
                          <div className="mt-3 rounded-lg border-l-2 border-brand-400 bg-slate-50 px-3 py-2 text-sm">
                            <p className="text-xs font-medium text-brand-700">Phản hồi của bạn</p>
                            <p className="mt-0.5 text-slate-700">{review.reply}</p>
                          </div>
                        )}
                        {replying === review.id ? (
                          <div className="mt-3 space-y-2">
                            <Textarea value={text} onChange={(e) => setText(e.target.value)} className="min-h-[72px]" placeholder="Cảm ơn du khách, giải đáp góp ý…" autoFocus />
                            <div className="flex justify-end gap-2">
                              <Button size="sm" variant="secondary" onClick={() => setReplying(null)}>Hủy</Button>
                              <Button size="sm" disabled={!text.trim()} onClick={async () => { try { await partnerApi.replyReview(review.id, text.trim()); setReplying(null); toast.success('Đã gửi phản hồi. Du khách sẽ thấy phản hồi trên web.'); void load() } catch (err) { toast.error(errorMessage(err)) } }}>Gửi</Button>
                            </div>
                          </div>
                        ) : (
                          <Button size="sm" variant="ghost" icon={MessageSquareReply} className="mt-2 -ml-2" onClick={() => { setReplying(review.id); setText(review.reply ?? '') }}>{review.reply ? 'Sửa phản hồi' : 'Trả lời'}</Button>
                        )}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}
