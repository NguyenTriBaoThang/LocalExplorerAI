import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Plus } from 'lucide-react'
import { Alert, Button, Card, EmptyState, PageHeader, Select, Spinner, StatusBadge } from '../../components/ui'
import { errorMessage } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { quoteApi, type QuoteSummary } from '../../lib/operatorApi'
import { DESTINATION_LABEL, STATUS_LABEL, vnd } from './quoteFormat'

export function OperatorQuotesPage() {
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
      <Card>
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
      </Card>
    </>
  )
}
