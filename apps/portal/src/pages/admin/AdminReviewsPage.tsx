import { useCallback, useEffect, useRef, useState } from 'react'
import { EyeOff, MessageSquare, RotateCcw, Search, Star } from 'lucide-react'
import { Alert, Button, Card, EmptyState, Field, Input, Modal, PageHeader, Pagination, Select, Spinner, StatusBadge, Tabs, Textarea, useToast } from '../../components/ui'
import { errorMessage } from '../../lib/api'
import { adminReviewsApi, type AdminReview, type ReviewKind } from '../../lib/adminReviews'
import { formatDateTime } from '../../lib/format'

const LIMIT = 25
type Pending = { review: AdminReview; action: 'hide' | 'restore' }

function Stars({ value }: { value: number }) {
  return (
    <span className="inline-flex items-center gap-0.5" aria-label={`${value} trên 5 sao`}>
      {[1, 2, 3, 4, 5].map((n) => <Star key={n} className={`h-3.5 w-3.5 ${n <= value ? 'fill-amber-400 text-amber-400' : 'text-slate-300'}`} />)}
    </span>
  )
}

function Comment({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  const long = text.length > 120 || text.includes('\n')
  return (
    <div className="max-w-md">
      <p className={`whitespace-pre-line break-words text-slate-700 ${open ? '' : 'line-clamp-2'}`}>{text}</p>
      {long && <button type="button" onClick={() => setOpen(!open)} className="mt-0.5 text-xs font-medium text-brand-600 hover:underline">{open ? 'Thu gọn' : 'Xem thêm'}</button>}
    </div>
  )
}

export function AdminReviewsPage() {
  const toast = useToast()
  const [kind, setKind] = useState<ReviewKind>('place')
  const [status, setStatus] = useState('')
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<{ items: AdminReview[]; total: number } | null>(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState<Pending | null>(null)
  const [note, setNote] = useState('')
  const [noteError, setNoteError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => { const id = window.setTimeout(() => setDebounced(query.trim()), 300); return () => window.clearTimeout(id) }, [query])
  useEffect(() => setOffset(0), [kind, status, debounced])

  const latest = useRef(0)
  const load = useCallback(async () => {
    const request = ++latest.current
    setError('')
    try {
      const result = await adminReviewsApi.list({ kind, status, q: debounced, limit: LIMIT, offset })
      if (request === latest.current) setPage(result)   // ignore an older request's answer
    } catch (err) {
      if (request === latest.current) { setError(errorMessage(err)); setPage(null) }
    }
  }, [kind, status, debounced, offset])
  useEffect(() => { setPage(null); void load() }, [load])

  const open = (review: AdminReview, action: 'hide' | 'restore') => { setPending({ review, action }); setNote(''); setNoteError('') }
  const close = () => { if (!busy) setPending(null) }

  const confirm = async () => {
    if (!pending) return
    const { review, action } = pending
    if (action === 'hide' && note.trim().length < 3) { setNoteError('Vui lòng nhập lý do ẩn (ít nhất 3 ký tự).'); return }
    setBusy(true)
    try {
      await adminReviewsApi.setStatus(review.kind, review.id, action, action === 'hide' ? note.trim() : undefined)
      toast.success(action === 'hide' ? 'Đã ẩn đánh giá.' : 'Đã khôi phục đánh giá.')
      setPending(null)
      await load()
    } catch (err) {
      const message = errorMessage(err)
      if (action === 'hide') setNoteError(message); else toast.error(message)
    } finally {
      setBusy(false)
    }
  }

  const hiding = pending?.action === 'hide'

  return (
    <>
      <PageHeader title="Đánh giá" description="Kiểm duyệt đánh giá của du khách về địa điểm và trải nghiệm. Đánh giá bị ẩn sẽ không hiển thị công khai." />

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Tabs value={kind} onChange={setKind} items={[{ value: 'place', label: 'Địa điểm' }, { value: 'experience', label: 'Trải nghiệm' }]} />
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Lọc theo trạng thái" className="w-full sm:w-44">
            <option value="">Tất cả</option><option value="published">Đang hiển thị</option><option value="hidden">Đã ẩn</option>
          </Select>
          <div className="relative w-full sm:w-64">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm nội dung, tên, email…" className="pl-9" />
          </div>
        </div>
      </div>

      {error && <div className="mb-4"><Alert tone="red" title="Không tải được danh sách đánh giá" action={<Button size="sm" variant="secondary" onClick={() => void load()}>Thử lại</Button>}>{error}</Alert></div>}

      <Card className="overflow-hidden">
        {!page ? (error ? null : <Spinner />) : page.items.length === 0 ? (
          <EmptyState icon={MessageSquare} title="Không có đánh giá nào" description={debounced || status ? 'Thử đổi bộ lọc hoặc từ khóa tìm kiếm.' : undefined} />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="table-head">
                  <tr>
                    <th className="px-5 py-3 font-medium">{kind === 'place' ? 'Địa điểm' : 'Trải nghiệm'}</th>
                    <th className="px-5 py-3 font-medium">Người đánh giá</th>
                    <th className="px-5 py-3 font-medium">Điểm</th>
                    <th className="px-5 py-3 font-medium">Nội dung</th>
                    <th className="px-5 py-3 font-medium">Trạng thái</th>
                    <th className="px-5 py-3 font-medium">Ngày tạo</th>
                    <th className="px-5 py-3 font-medium"><span className="sr-only">Thao tác</span></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {page.items.map((review) => (
                    <tr key={`${review.kind}-${review.id}`} className="align-top">
                      <td className="px-5 py-3 font-medium text-slate-900">{review.target_title}</td>
                      <td className="px-5 py-3">
                        <p className="text-slate-900">{review.author_name ?? '—'}</p>
                        <p className="text-xs text-slate-500">{review.author_email ?? ''}</p>
                      </td>
                      <td className="px-5 py-3"><Stars value={review.rating} /></td>
                      <td className="px-5 py-3"><Comment text={review.comment} /></td>
                      <td className="px-5 py-3">
                        <StatusBadge status={review.status} />
                        {review.status === 'hidden' && (review.moderation_note || review.moderated_at) && (
                          <div className="mt-1 max-w-[14rem] text-xs text-slate-500">
                            {review.moderation_note && <p className="break-words">{review.moderation_note}</p>}
                            {review.moderated_at && <p>{formatDateTime(review.moderated_at)}</p>}
                          </div>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-slate-600">{formatDateTime(review.created_at)}</td>
                      <td className="px-5 py-3 text-right">
                        {review.status === 'published'
                          ? <Button size="sm" variant="secondary" icon={EyeOff} onClick={() => open(review, 'hide')}>Ẩn</Button>
                          : <Button size="sm" variant="secondary" icon={RotateCcw} onClick={() => open(review, 'restore')}>Khôi phục</Button>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination offset={offset} limit={LIMIT} total={page.total} onChange={setOffset} />
          </>
        )}
      </Card>

      <Modal open={!!pending} onClose={close} size="sm"
        title={hiding ? 'Ẩn đánh giá' : 'Khôi phục đánh giá'}
        description={hiding ? 'Đánh giá sẽ không còn hiển thị công khai và không tính vào điểm trung bình.' : 'Đánh giá sẽ hiển thị công khai trở lại.'}
        footer={<>
          <Button variant="secondary" onClick={close} disabled={busy}>Hủy</Button>
          <Button variant={hiding ? 'danger' : 'primary'} loading={busy} onClick={() => void confirm()}>{hiding ? 'Ẩn đánh giá' : 'Khôi phục'}</Button>
        </>}>
        {pending && (
          <div className="space-y-3">
            <div className="rounded-lg bg-slate-50 p-3 text-sm">
              <p className="font-medium text-slate-900">{pending.review.target_title}</p>
              <div className="mt-1"><Stars value={pending.review.rating} /></div>
              <p className="mt-1 line-clamp-3 whitespace-pre-line break-words text-slate-600">{pending.review.comment}</p>
            </div>
            {hiding && (
              <Field label="Lý do ẩn" required error={noteError}>
                <Textarea value={note} onChange={(e) => { setNote(e.target.value); setNoteError('') }} maxLength={500} rows={3} placeholder="VD: Nội dung xúc phạm, spam…" />
              </Field>
            )}
          </div>
        )}
      </Modal>
    </>
  )
}
