import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, Copy, Send, XCircle } from 'lucide-react'
import { Alert, Badge, Button, Card, CardHeader, DescriptionList, Input, Modal, PageHeader, Spinner, StatusBadge, useToast } from '../../components/ui'
import { Legend, LineChart } from '../../components/charts'
import { errorMessage } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { quoteApi, type PriceMode, type PricingCurve, type Quote, type QuoteSent } from '../../lib/operatorApi'
import { DESTINATION_LABEL, MODE_HINT, MODE_LABEL, SEGMENT_LABEL, vnd } from './quoteFormat'
import { EditPanel, RescuePanel, RevisionList } from './QuoteMarginPanels'

const MODES: PriceMode[] = ['safe', 'balanced', 'max_profit']
const CATEGORY_LABEL: Record<string, string> = { vehicle: 'Xe', guide: 'Hướng dẫn viên', meal: 'Ăn uống', ticket: 'Vé', hotel: 'Lưu trú' }

function PriceChart({ curve }: { curve: PricingCurve }) {
  const maxEp = Math.max(1, ...curve.points.map((p) => p.expected_profit))
  const series = [
    { name: 'Xác suất chốt (%)', values: curve.points.map((p) => p.p_win * 100) },
    { name: 'Lãi kỳ vọng (% của mức cao nhất)', values: curve.points.map((p) => (p.expected_profit / maxEp) * 100) },
  ]
  const selected = curve.modes[curve.selected_mode]
  return (
    <div className="space-y-3 p-5">
      <Legend series={series} />
      <LineChart labels={curve.points.map((p) => `${(p.price_per_pax / 1e6).toLocaleString('vi-VN', { maximumFractionDigits: 2 })}tr`)}
        series={series} format={(v) => `${v.toFixed(0)}%`} />
      <p className="text-xs text-slate-500">
        Trục ngang: giá/khách. Mức đang chọn ({MODE_LABEL[curve.selected_mode]}): {vnd(selected.price_per_pax)}/khách. Giá vốn {vnd(curve.cost_per_pax)}/khách.
        {curve.source === 'heuristic' && ' Xác suất chốt đang dùng công thức ước lượng chung, chưa phải mô hình đã huấn luyện.'} Dữ liệu huấn luyện là giả lập.
      </p>
    </div>
  )
}

export function OperatorQuoteDetailPage() {
  const { id = '' } = useParams()
  const toast = useToast()
  const [quote, setQuote] = useState<Quote | null>(null)
  const [curve, setCurve] = useState<PricingCurve | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [lostOpen, setLostOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [sent, setSent] = useState<QuoteSent | null>(null)  // the plain link is shown once: only its hash is stored

  const load = useCallback(async () => {
    try {
      const [q, c] = await Promise.all([quoteApi.get(id), quoteApi.curve(id)])
      setQuote(q)
      setCurve(c)
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [id])
  useEffect(() => { void load() }, [load])

  const act = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key)
    try {
      await fn()
      await load()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy('')
    }
  }
  const surchargeLabel = useMemo(() => Object.fromEntries((quote?.cost.surcharges ?? []).map((s) => [s.code, s.label])), [quote])

  if (error) return <Alert tone="red">{error}</Alert>
  if (!quote || !curve) return <Spinner />
  const r = quote.request
  const editable = quote.status === 'draft'
  const open = ['draft', 'sent', 'viewed', 'accepted', 'deposit_paid'].includes(quote.status)
  const canSend = ['draft', 'sent', 'viewed', 'expired'].includes(quote.status)
  const copy = (text: string) => { void navigator.clipboard?.writeText(text); toast.success('Đã sao chép.') }
  const timeline: Array<[string, string | null | undefined]> = [
    ['Đã gửi khách', quote.sent_at], ['Khách đã xem', quote.first_viewed_at], ['Khách chấp nhận', quote.accepted_at], ['Đã đặt cọc', quote.deposit_paid_at],
  ]

  return (
    <>
      <PageHeader title={`Báo giá ${quote.code}`} description={`${quote.itinerary.template_name} · phiên bản ${quote.revision}`}
        actions={<>
          <StatusBadge status={quote.status} />
          <Link to="/operator/quotes"><Button variant="secondary" icon={ArrowLeft}>Danh sách</Button></Link>
          {canSend && <Button icon={Send} loading={busy === 'send'} onClick={() => act('send', async () => setSent(await quoteApi.send(quote.id)))}>{quote.status === 'draft' ? 'Gửi khách' : 'Gửi lại (đổi link)'}</Button>}
          {open && <Button icon={CheckCircle2} loading={busy === 'won'} onClick={() => act('won', () => quoteApi.mark(quote.id, 'won'))}>Đã chốt</Button>}
          {open && <Button variant="secondary" icon={XCircle} onClick={() => setLostOpen(true)}>Không chốt</Button>}
        </>} />
      <div className="space-y-4">
        {sent && (
          <Card>
            <CardHeader title="Liên kết gửi khách" description="Link chỉ hiện một lần ở đây; gửi lại sẽ tạo link mới và vô hiệu link cũ." />
            <div className="space-y-3 p-5 text-sm">
              <div className="flex gap-2"><Input readOnly value={sent.share_url} onFocus={(e) => e.currentTarget.select()} /><Button variant="secondary" icon={Copy} onClick={() => copy(sent.share_url)}>Sao chép link</Button></div>
              <textarea readOnly rows={5} className="w-full rounded-lg border border-slate-200 p-3 text-sm" value={sent.message} />
              <Button variant="secondary" icon={Copy} onClick={() => copy(sent.message)}>Sao chép tin nhắn Zalo</Button>
            </div>
          </Card>
        )}
        {quote.sent_at && (
          <Card>
            <CardHeader title="Tiến trình" description={quote.expires_at ? `Hiệu lực đến ${formatDateTime(quote.expires_at)} · khách mở link ${quote.view_count} lần` : undefined} />
            <ol className="grid gap-3 p-5 text-sm sm:grid-cols-4">
              {timeline.map(([label, at]) => (
                <li key={label} className={at ? 'text-slate-900' : 'text-slate-400'}>
                  <p className="font-medium">{at ? '✓ ' : '○ '}{label}</p><p className="text-xs">{at ? formatDateTime(at) : 'Chưa có'}</p>
                </li>
              ))}
            </ol>
          </Card>
        )}
        {quote.margin_alert && (
          <Alert tone="red" title="Biên lợi nhuận dưới mức sàn">
            Biên hiện tại {quote.margin_alert.margin_pct.toFixed(1)}% so với sàn {quote.margin_alert.floor_pct}%. Giá bán cần tăng thêm {vnd(quote.margin_alert.shortfall_vnd)} để về sàn,
            hoặc giảm chi phí theo các phương án bên dưới.
          </Alert>
        )}
        {quote.status === 'expired' && <Alert tone="amber">Báo giá đã hết hạn. Bấm "Gửi lại" để gia hạn và tạo link mới.</Alert>}
        {quote.status === 'lost' && <Alert tone="amber">Không chốt: {quote.lost_reason || 'không ghi lý do'}.</Alert>}

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader title="Khách và yêu cầu" />
            <div className="px-5 pb-3">
              <DescriptionList items={[
                ['Khách', quote.customer_name], ['Liên hệ', quote.customer_contact],
                ['Đoàn', `${r.pax} khách, ${r.days} ngày${r.segment ? ` · ${SEGMENT_LABEL[r.segment]}` : ''}`],
                ['Khởi hành', formatDate(r.start_date)], ['Điểm đến', r.destinations.map((d) => DESTINATION_LABEL[d] ?? d).join(', ')],
                ['Ngân sách / khách', r.budget_per_pax ? vnd(r.budget_per_pax) : null], ['Tin nhắn gốc', quote.raw_message],
              ]} />
            </div>
          </Card>
          <Card>
            <CardHeader title="Lịch trình" description={quote.itinerary.template_name} />
            <ol className="space-y-3 p-5 text-sm">
              {quote.itinerary.days.map((d, i) => (
                <li key={i}>
                  <p className="font-medium text-slate-900">Ngày {i + 1}: {d.title}</p>
                  <p className="text-slate-500">{d.stops.map((s) => s.name).join(' · ')} · {d.legs.reduce((n, l) => n + l.distance_km, 0)} km</p>
                </li>
              ))}
            </ol>
          </Card>
        </div>

        {open && <EditPanel quote={quote} onSaved={load} />}
        {open && <RescuePanel quote={quote} onApplied={load} />}

        <Card>
          <CardHeader title="Chi phí" description={`Giá vốn ${vnd(quote.cost.total)} · cố định ${vnd(quote.cost.fixed_total)} · biến đổi ${vnd(quote.cost.variable_total)}`} />
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="table-head">
                <tr>{['Khoản mục', 'Loại chi phí', 'SL', 'Đơn giá', 'Thành tiền', 'Phụ thu'].map((h) => <th key={h} className="px-4 py-2 text-left font-medium">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {quote.cost.lines.map((l, i) => (
                  <tr key={i} className={l.surcharge_vnd ? 'bg-amber-50' : ''}>
                    <td className="px-4 py-2">{l.label} <span className="text-xs text-slate-400">{CATEGORY_LABEL[l.category]}</span></td>
                    <td className="px-4 py-2"><Badge tone={l.fixed ? 'gray' : 'brand'}>{l.fixed ? 'Cố định' : 'Theo khách'}</Badge></td>
                    <td className="px-4 py-2">{l.qty}</td>
                    <td className="px-4 py-2">{vnd(l.unit_vnd)}</td>
                    <td className="px-4 py-2">{vnd(l.amount_vnd)}</td>
                    <td className="px-4 py-2">{l.surcharge_vnd ? <span className="font-medium text-amber-700">+{vnd(l.surcharge_vnd)} <span className="text-xs">({l.surcharge_codes.map((c) => surchargeLabel[c] ?? c).join(', ')})</span></span> : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="grid gap-4 md:grid-cols-3">
          {MODES.map((m) => {
            const p = quote.pricing.modes[m]
            const chosen = quote.price_mode === m
            return (
              <Card key={m} className={chosen ? 'ring-2 ring-brand-500' : ''}>
                <div className="space-y-2 p-5 text-sm">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-slate-900">{MODE_LABEL[m]}</h3>
                    {chosen && <Badge tone="brand">Đang chọn</Badge>}
                  </div>
                  <p className="text-2xl font-semibold text-slate-900">{vnd(p.price_per_pax)}<span className="text-sm font-normal text-slate-500">/khách</span></p>
                  <p className="text-slate-500">{MODE_HINT[m]}</p>
                  <dl className="grid grid-cols-2 gap-y-1">
                    <dt className="text-slate-500">Tổng</dt><dd className="text-right">{vnd(p.total)}</dd>
                    <dt className="text-slate-500">Biên lợi nhuận</dt><dd className="text-right">{p.margin_pct.toFixed(1)}%</dd>
                    <dt className="text-slate-500">P(chốt)</dt><dd className="text-right">{Math.round(p.p_win * 100)}%</dd>
                    <dt className="text-slate-500">Lãi kỳ vọng</dt><dd className="text-right">{vnd(p.expected_profit)}</dd>
                  </dl>
                  {p.floor_bound && <Alert tone="amber">Không mức nào đạt P ≥ 75%, giá ở sát mức sàn.</Alert>}
                  {editable && !chosen && <Button variant="secondary" size="sm" loading={busy === m} onClick={() => act(m, () => quoteApi.selectMode(quote.id, m))}>Chọn mức này</Button>}
                </div>
              </Card>
            )
          })}
        </div>
        <p className="text-xs text-slate-500">Biên sàn của công ty: {quote.margin_floor_pct}% trên giá bán. Mọi mức giá đều không thấp hơn sàn.</p>

        {quote.explanation && (
          <Card>
            <CardHeader title="Giải thích mức giá" />
            <p className="p-5 text-sm leading-relaxed text-slate-700">{quote.explanation}</p>
          </Card>
        )}

        <RevisionList quote={quote} />

        <Card>
          <CardHeader title="Đường cong giá" description="Xác suất chốt và lãi kỳ vọng theo giá chào." />
          <PriceChart curve={curve} />
        </Card>
      </div>

      <Modal open={lostOpen} onClose={() => setLostOpen(false)} title="Không chốt được" description="Ghi lại lý do để cải thiện mô hình giá sau này."
        footer={<Button loading={busy === 'lost'} onClick={() => act('lost', async () => { await quoteApi.mark(quote.id, 'lost', reason.trim() || undefined); setLostOpen(false) })}>Xác nhận</Button>}>
        <Input value={reason} placeholder="Ví dụ: đối thủ rẻ hơn" onChange={(e) => setReason(e.target.value)} />
      </Modal>
    </>
  )
}
