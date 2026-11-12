import { useEffect, useState } from 'react'
import { LifeBuoy, Pencil } from 'lucide-react'
import { Alert, Badge, Button, Card, CardHeader, Field, Input, Select, Spinner, useToast } from '../../components/ui'
import { errorMessage } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { quoteApi, type Quote, type QuoteRevisionRow, type Rescue } from '../../lib/operatorApi'
import { vnd } from './quoteFormat'

const SEATS = [4, 7, 16, 29, 45]

/** Edit pax / departure / vehicle size. The API re-costs; a sent quote keeps its price and only the margin moves. */
export function EditPanel({ quote, onSaved }: { quote: Quote; onSaved: () => Promise<void> }) {
  const toast = useToast()
  const pinned = quote.request.overrides?.vehicle_seats
  const [pax, setPax] = useState(String(quote.request.pax ?? ''))
  const [date, setDate] = useState(quote.request.start_date ?? '')
  const [seats, setSeats] = useState(pinned ? String(pinned) : '')
  const [busy, setBusy] = useState(false)
  useEffect(() => { setPax(String(quote.request.pax ?? '')); setDate(quote.request.start_date ?? ''); setSeats(pinned ? String(pinned) : '') }, [quote.revision, quote.request.pax, quote.request.start_date, pinned])

  const save = async () => {
    const body: Parameters<typeof quoteApi.patch>[1] = {}
    if (Number(pax) !== quote.request.pax) body.pax = Number(pax)
    if (date !== quote.request.start_date) body.start_date = date
    if (seats !== (pinned ? String(pinned) : '')) body.overrides = { vehicle_seats: seats ? Number(seats) : null }
    if (!Object.keys(body).length) return toast.error('Chưa có thay đổi nào.')
    setBusy(true)
    try {
      await quoteApi.patch(quote.id, body)
      toast.success(quote.status === 'draft' ? 'Đã tính lại chi phí và giá.' : 'Đã tính lại chi phí; giá bán giữ nguyên.')
      await onSaved()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card>
      <CardHeader title="Chỉnh sửa báo giá" description={quote.status === 'draft' ? 'Giá được tối ưu lại theo chi phí mới.' : 'Báo giá đã gửi: giá bán giữ nguyên, chỉ biên lợi nhuận thay đổi.'} />
      <div className="flex flex-wrap items-end gap-3 p-5">
        <Field label="Số khách"><Input type="number" min={1} max={60} className="w-28" value={pax} onChange={(e) => setPax(e.target.value)} /></Field>
        <Field label="Ngày khởi hành"><Input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
        <Field label="Xe">
          <Select value={seats} onChange={(e) => setSeats(e.target.value)}>
            <option value="">Tự chọn tổ hợp rẻ nhất</option>
            {SEATS.map((s) => <option key={s} value={s}>Chỉ xe {s} chỗ</option>)}
          </Select>
        </Field>
        <Button icon={Pencil} loading={busy} onClick={save}>Tính lại</Button>
      </div>
    </Card>
  )
}

export function RescuePanel({ quote, onApplied }: { quote: Quote; onApplied: () => Promise<void> }) {
  const toast = useToast()
  const [rescue, setRescue] = useState<Rescue | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const alerting = !!quote.margin_alert
  useEffect(() => {
    if (!alerting) { setRescue(null); return }
    quoteApi.rescue(quote.id).then(setRescue).catch((err) => setError(errorMessage(err)))
  }, [quote.id, quote.revision, alerting])
  if (!alerting) return null

  const apply = async (code: string, visible: boolean) => {
    const sent = ['sent', 'viewed'].includes(quote.status)
    if (visible && sent && !window.confirm('Phương án này đổi thứ khách đã thấy. Báo giá sẽ chuyển về nháp, link cũ bị vô hiệu và bạn cần gửi lại. Tiếp tục?')) return
    setBusy(code)
    try {
      const r = await quoteApi.applyRescue(quote.id, code, visible && sent)
      toast.success(r.requires_resend ? 'Đã áp dụng. Báo giá về nháp, hãy gửi lại cho khách.' : 'Đã áp dụng phương án và tạo phiên bản mới.')
      await onApplied()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy('')
    }
  }
  return (
    <Card>
      <CardHeader title="Phương án cứu biên lợi nhuận" description="Mỗi phương án được tính lại bằng bộ máy chi phí; số liệu không do AI tạo." />
      <div className="space-y-4 p-5">
        {error && <Alert tone="red">{error}</Alert>}
        {!rescue && !error && <Spinner />}
        {rescue && <p className="text-sm leading-relaxed text-slate-700">{rescue.explanation}</p>}
        <div className="grid gap-3 md:grid-cols-2">
          {rescue?.options.map((o) => (
            <div key={o.code} className="space-y-2 rounded-lg border border-slate-200 p-4 text-sm">
              <div className="flex items-start justify-between gap-2">
                <p className="font-medium text-slate-900">{o.title}</p>
                {o.customer_visible && <Badge tone="amber">Khách sẽ thấy</Badge>}
              </div>
              <dl className="grid grid-cols-2 gap-y-1">
                {o.code === 'raise_price'
                  ? <><dt className="text-slate-500">Giá mới</dt><dd className="text-right">{vnd(o.new_price_vnd)}</dd><dt className="text-slate-500">P(chốt)</dt><dd className="text-right">{Math.round((o.p_win ?? 0) * 100)}%</dd></>
                  : <><dt className="text-slate-500">Tiết kiệm</dt><dd className="text-right font-medium text-emerald-700">{vnd(o.savings_vnd)}</dd><dt className="text-slate-500">Giá vốn mới</dt><dd className="text-right">{vnd(o.new_cost_vnd)}</dd></>}
                <dt className="text-slate-500">Biên mới</dt><dd className="text-right">{o.new_margin_pct?.toFixed(1)}%</dd>
              </dl>
              <Button size="sm" icon={LifeBuoy} loading={busy === o.code} onClick={() => apply(o.code, o.customer_visible)}>Áp dụng</Button>
            </div>
          ))}
        </div>
        {rescue && !rescue.options.length && <p className="text-sm text-slate-500">Chưa có phương án nào khả thi.</p>}
      </div>
    </Card>
  )
}

export function RevisionList({ quote }: { quote: Quote }) {
  const [rows, setRows] = useState<QuoteRevisionRow[] | null>(null)
  useEffect(() => { quoteApi.revisions(quote.id).then(setRows).catch(() => setRows([])) }, [quote.id, quote.revision])
  if (!rows || rows.length < 2) return null
  return (
    <Card>
      <CardHeader title="Lịch sử phiên bản" />
      <ul className="divide-y divide-slate-100 text-sm">
        {rows.map((r) => (
          <li key={r.revision} className="flex flex-wrap items-center justify-between gap-2 px-5 py-2">
            <span><b>v{r.revision}</b> · {r.reason ?? 'Tạo báo giá'}</span>
            <span className="text-slate-500">{r.price_vnd ? vnd(r.price_vnd) : '—'} · biên {r.margin_pct?.toFixed(1) ?? '—'}% · {formatDateTime(r.created_at)}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
