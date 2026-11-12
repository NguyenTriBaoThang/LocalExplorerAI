import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { Alert, Badge, Button, Card, CardHeader, Field, Input, PageHeader, Select, Textarea } from '../../components/ui'
import { errorMessage } from '../../lib/api'
import { quoteApi, type QuoteDraft, type QuoteRequest } from '../../lib/operatorApi'
import { DESTINATION_LABEL, SEGMENT_LABEL } from './quoteFormat'

const FIELD_LABEL: Record<string, string> = { pax: 'Số khách', days: 'Số ngày', start_date: 'Ngày khởi hành', destinations: 'Điểm đến' }
const num = (v: string) => (v === '' ? null : Number(v))

export function OperatorQuoteNewPage() {
  const navigate = useNavigate()
  const [message, setMessage] = useState('')
  const [draft, setDraft] = useState<QuoteDraft | null>(null)
  const [req, setReq] = useState<QuoteRequest | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  const parse = async () => {
    setBusy('parse')
    setError('')
    try {
      const result = await quoteApi.draft({ message, parse_only: true })
      setDraft(result)
      setReq(result.request)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy('')
    }
  }

  const create = async () => {
    if (!req) return
    setBusy('create')
    setError('')
    try {
      const result = await quoteApi.draft({ message, request: req })
      if (result.quote) navigate(`/operator/quotes/${result.quote.id}`)
      else { setDraft(result); setReq(result.request) }  // still missing something: show the questions
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy('')
    }
  }

  const patch = (change: Partial<QuoteRequest>) => setReq((prev) => {
    if (!prev) return prev
    const next = { ...prev, ...change }
    const required: Array<[string, unknown]> = [['pax', next.pax], ['days', next.days], ['start_date', next.start_date], ['destinations', next.destinations.length]]
    return { ...next, missing_fields: required.filter(([, v]) => !v).map(([k]) => k) }
  })
  const missing = (field: string) => req?.missing_fields.includes(field) ?? false
  const toggleDest = (key: string) => req && patch({ destinations: req.destinations.includes(key) ? req.destinations.filter((d) => d !== key) : [...req.destinations, key] })

  return (
    <>
      <PageHeader title="Báo giá mới" description="Dán tin nhắn của khách, kiểm tra các trường AI đã tách rồi tạo nháp báo giá." />
      <div className="space-y-4">
        {error && <Alert tone="red">{error}</Alert>}
        <Card>
          <div className="space-y-3 p-5">
            <Textarea rows={5} value={message} placeholder="Ví dụ: Công ty mình 32 người muốn đi Củ Chi – Mekong 2 ngày 1 đêm, khởi hành 30/4, ngân sách tầm 2 triệu/người"
              onChange={(e) => setMessage(e.target.value)} />
            <Button icon={Sparkles} loading={busy === 'parse'} disabled={message.trim().length < 3} onClick={parse}>Phân tích tin nhắn</Button>
          </div>
        </Card>
        {req && draft && (
          <Card>
            <CardHeader title="Yêu cầu đã tách" description={`Nguồn: ${draft.parser === 'llm' ? 'AI' : 'quy tắc ngoại tuyến'}. Sửa lại nếu sai rồi tạo báo giá.`} />
            <div className="space-y-4 p-5">
              {req.missing_fields.length > 0 && (
                <Alert tone="amber" title="Cần hỏi thêm khách trước khi báo giá">
                  <ul className="list-disc pl-5">{(draft.questions.length ? draft.questions : req.missing_fields.map((f) => FIELD_LABEL[f] ?? f)).map((q) => <li key={q}>{q}</li>)}</ul>
                </Alert>
              )}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Field label="Số khách" required error={missing('pax') ? 'Thiếu' : undefined}>
                  <Input type="number" min={1} max={60} invalid={missing('pax')} value={req.pax ?? ''} onChange={(e) => patch({ pax: num(e.target.value) })} />
                </Field>
                <Field label="Số ngày" required error={missing('days') ? 'Thiếu' : undefined}>
                  <Input type="number" min={1} max={3} invalid={missing('days')} value={req.days ?? ''} onChange={(e) => patch({ days: num(e.target.value) })} />
                </Field>
                <Field label="Ngày khởi hành" required error={missing('start_date') ? 'Thiếu' : undefined}>
                  <Input type="date" invalid={missing('start_date')} value={req.start_date ?? ''} onChange={(e) => patch({ start_date: e.target.value || null })} />
                </Field>
                <Field label="Nhóm khách" hint={req.assumed_fields.includes('segment') ? 'AI chưa chắc, mặc định gia đình' : undefined}>
                  <Select value={req.segment ?? 'family'} onChange={(e) => patch({ segment: e.target.value as QuoteRequest['segment'] })}>
                    {Object.entries(SEGMENT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </Select>
                </Field>
                <Field label="Ngân sách / khách (VNĐ)">
                  <Input type="number" min={0} value={req.budget_per_pax ?? ''} onChange={(e) => patch({ budget_per_pax: num(e.target.value) })} />
                </Field>
                <Field label="Tên khách / công ty">
                  <Input value={req.customer_name ?? ''} onChange={(e) => patch({ customer_name: e.target.value || null })} />
                </Field>
              </div>
              <div>
                <span className="mb-1.5 block text-sm font-medium text-slate-700">Điểm đến <span className="text-rose-500">*</span></span>
                <div className={`flex flex-wrap gap-2 rounded-lg p-1 ${missing('destinations') ? 'bg-amber-50 ring-1 ring-amber-300' : ''}`}>
                  {Object.entries(DESTINATION_LABEL).map(([k, v]) => (
                    <button key={k} type="button" onClick={() => toggleDest(k)} aria-pressed={req.destinations.includes(k)}>
                      <Badge tone={req.destinations.includes(k) ? 'brand' : 'gray'}>{v}</Badge>
                    </button>
                  ))}
                </div>
              </div>
              <Button loading={busy === 'create'} disabled={req.missing_fields.length > 0} onClick={create}>Tạo nháp báo giá</Button>
            </div>
          </Card>
        )}
      </div>
    </>
  )
}
