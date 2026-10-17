import { useState } from 'react'
import { History } from 'lucide-react'
import { Alert, Button, DescriptionList } from '../../components/ui'
import { adminApi, errorMessage } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import type { AdminCustomerHistory } from '../../lib/types'

const money = (value: number) => `${new Intl.NumberFormat('vi-VN').format(value)} ₫`

export function CustomerHistory({ userId }: { userId: string }) {
  const [data, setData] = useState<AdminCustomerHistory | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)

  const load = async () => {
    if (open) { setOpen(false); setData(null); return }
    setOpen(true)
    setBusy(true)
    setError('')
    try { setData(await adminApi.customerHistory(userId)) }
    catch (reason) { setError(errorMessage(reason)) }
    finally { setBusy(false) }
  }

  return <section className="space-y-3">
    <Button variant="secondary" icon={History} loading={busy} onClick={() => void load()} aria-expanded={open}>
      {open ? 'Ẩn lịch sử khách hàng' : 'Xem lịch sử khách hàng'}
    </Button>
    {open && <>
      <p className="text-xs text-slate-500">Lịch trình, đặt chỗ và đánh giá dùng cho hỗ trợ vận hành. Lịch sử Khám phá chỉ hiện khi khách đồng ý riêng. Mỗi lần xem được ghi vào nhật ký kiểm toán.</p>
      {error && <Alert tone="red">{error}</Alert>}
      {data && <div className="space-y-4">
        <DescriptionList items={[
          ['Lịch trình', String(data.summary.itineraries)], ['Đặt chỗ', String(data.summary.bookings)],
          ['Đánh giá', String(data.summary.feedback)], ['Lượt Khám phá', data.summary.behavior_events == null ? 'Chưa đồng ý chia sẻ' : String(data.summary.behavior_events)],
          ['Cá nhân hóa', data.consent.personalization_enabled ? 'Đã bật' : 'Tắt'],
          ['Huấn luyện mô hình', data.consent.model_training_enabled ? 'Đã bật' : 'Tắt'],
          ['Admin xem lịch sử Khám phá', data.consent.admin_history_enabled ? 'Đã đồng ý' : 'Chưa đồng ý'],
        ]} />
        <HistoryList title="Lịch trình gần đây" items={data.itineraries.map((item) => ({
          id: item.id, title: item.city || 'Lịch trình',
          detail: `${item.planned_date || formatDateTime(item.created_at)} · ${item.status} · ${item.group_size} người · ${money(item.estimated_cost_vnd)}`,
        }))} />
        <HistoryList title="Đặt chỗ gần đây" items={data.bookings.map((item) => ({
          id: item.id, title: item.experience_name,
          detail: `${formatDateTime(item.created_at)} · ${item.status} · ${item.quantity} khách · ${money(item.amount_vnd)}`,
        }))} />
        <HistoryList title="Đánh giá" items={data.feedback.map((item) => ({
          id: item.id, title: item.rating == null ? 'Chưa chấm sao' : `${item.rating}/5 sao`, detail: formatDateTime(item.created_at),
        }))} />
        {data.behavior_history_visible ? <HistoryList title="Lịch sử Khám phá" items={data.behavior_events.map((item) => ({
          id: item.id, title: item.experience_name || 'Trải nghiệm không còn trong danh mục',
          detail: `${formatDateTime(item.created_at)} · ${{ selected: 'Đã chọn', dismissed: 'Đã bỏ qua', impression: 'Đã hiển thị' }[item.event_type]}${item.position != null ? ` · vị trí ${item.position + 1}` : ''}${Array.isArray(item.context.intent_tags) ? ` · ${item.context.intent_tags.join(', ')}` : ''}`,
        }))} /> : <p className="text-sm text-slate-500">Khách chưa đồng ý cho admin xem lịch sử Khám phá.</p>}
        <p className="text-xs text-slate-400">Tối đa {data.limit} bản ghi mỗi mục. Không hiển thị nội dung bình luận và mã giao dịch.</p>
      </div>}
    </>}
  </section>
}

function HistoryList({ title, items }: { title: string; items: Array<{ id: string; title: string; detail: string }> }) {
  return <section>
    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h4>
    {items.length ? <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
      {items.map((item) => <li key={item.id} className="px-3 py-2 text-sm">
        <p className="font-medium text-slate-800">{item.title}</p><p className="text-xs text-slate-500">{item.detail}</p>
      </li>)}
    </ul> : <p className="text-sm text-slate-500">Chưa có dữ liệu.</p>}
  </section>
}
