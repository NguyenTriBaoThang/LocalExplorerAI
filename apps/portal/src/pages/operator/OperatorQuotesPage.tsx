import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Copy, FileText, Plus } from 'lucide-react'
import { Alert, Button, Card, EmptyState, PageHeader, Select, Spinner, StatusBadge, Tabs, useToast } from '../../components/ui'
import { errorMessage } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { quoteApi, type FollowupQuote, type FollowupReason, type QuoteSummary } from '../../lib/operatorApi'
import { DESTINATION_LABEL, STATUS_LABEL, vnd } from './quoteFormat'

const REASON_LABEL: Record<FollowupReason, string> = {
  not_viewed: 'Chưa xem sau 24 giờ', not_accepted: 'Đã xem, chưa chấp nhận sau 48 giờ', expiring: 'Sắp hết hạn (trong 24 giờ)',
}

function FollowupList() {
  const toast = useToast()
  const [rows, setRows] = useState<FollowupQuote[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { quoteApi.followups().then(setRows).catch((err) => setError(errorMessage(err))) }, [])
  if (error) return <Alert tone="red">{error}</Alert>
  if (rows === null) return <Spinner />
  if (rows.length === 0) return <EmptyState icon={FileText} title="Không có báo giá nào cần follow-up" description="Báo giá đã gửi mà khách chưa xem, chưa chấp nhận hoặc sắp hết hạn sẽ hiện ở đây." />
  return (
    <ul className="divide-y divide-slate-100">
      {rows.map((q) => (
        <li key={q.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-sm">
          <div>
            <Link className="font-medium text-brand-700 hover:underline" to={`/operator/quotes/${q.id}`}>{q.code}</Link>
            <span className="ml-2 text-slate-500">{q.customer_name || 'Khách chưa rõ tên'} · {q.price_vnd ? vnd(q.price_vnd) : '—'}</span>
            <p className="text-amber-700">{REASON_LABEL[q.followup_reason]} · hết hạn {formatDateTime(q.expires_at)}</p>
          </div>
          <Button variant="secondary" size="sm" icon={Copy} onClick={() => { void navigator.clipboard?.writeText(q.reminder_text); toast.success('Đã sao chép tin nhắc.') }}>Sao chép tin nhắc</Button>
        </li>
      ))}
    </ul>
  )
}

export function OperatorQuotesPage() {
  const [tab, setTab] = useState<'all' | 'followup'>('all')
  const [status, setStatus] = useState('')
  const [rows, setRows] = useState<QuoteSummary[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setRows(null)
    quoteApi.list(status || undefined).then(setRows).catch((err) => setError(errorMessage(err)))
  }, [status])

  return (
    <>
      <PageHeader title="Báo giá" description="Soạn nháp báo giá từ tin nhắn của khách, chọn mức giá và theo dõi kết quả."
        actions={<Link to="/operator/quotes/new"><Button icon={Plus}>Báo giá mới</Button></Link>} />
      {error && <Alert tone="red">{error}</Alert>}
      <div className="mb-3"><Tabs value={tab} onChange={setTab} items={[{ value: 'all', label: 'Tất cả' }, { value: 'followup', label: 'Cần follow-up' }]} /></div>
      {tab === 'followup' ? <Card><FollowupList /></Card> : <Card>
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-3">
          <span className="text-sm text-slate-500">Trạng thái</span>
          <Select className="w-48" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Tất cả</option>
            {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </div>
        {rows === null ? <Spinner /> : rows.length === 0 ? (
          <EmptyState icon={FileText} title="Chưa có báo giá nào" description="Dán tin nhắn của khách để tạo báo giá đầu tiên." />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="table-head">
                <tr>{['Mã', 'Khách', 'Đoàn', 'Điểm đến', 'Khởi hành', 'Giá chào', 'Trạng thái'].map((h) => <th key={h} className="px-4 py-2 text-left font-medium">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((q) => (
                  <tr key={q.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5 font-medium"><Link className="text-brand-700 hover:underline" to={`/operator/quotes/${q.id}`}>{q.code}</Link></td>
                    <td className="px-4 py-2.5">{q.customer_name || '—'}</td>
                    <td className="px-4 py-2.5">{q.pax} khách, {q.days} ngày</td>
                    <td className="px-4 py-2.5">{q.destinations.map((d) => DESTINATION_LABEL[d] ?? d).join(', ')}</td>
                    <td className="px-4 py-2.5">{formatDate(q.start_date)}</td>
                    <td className="px-4 py-2.5">{q.price_vnd ? vnd(q.price_vnd) : '—'}</td>
                    <td className="px-4 py-2.5"><StatusBadge status={q.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>}
    </>
  )
}
