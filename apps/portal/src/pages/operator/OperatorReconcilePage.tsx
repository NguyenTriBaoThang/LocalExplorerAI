import { useCallback, useEffect, useRef, useState } from 'react'
import { CheckCircle2, FileUp, ReceiptText } from 'lucide-react'
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Input, PageHeader, Select, Spinner, useToast } from '../../components/ui'
import { errorMessage } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { quoteApi, rateCardApi, reconcileApi, type CostReason, type QuoteSummary, type Reconciliation } from '../../lib/operatorApi'
import { REASON_LABEL, vnd } from './quoteFormat'

function readDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(new Error('Không đọc được tệp.'))
    reader.readAsDataURL(file)
  })
}

const signed = (n: number) => `${n > 0 ? '+' : ''}${vnd(n)}`

export function OperatorReconcilePage() {
  const toast = useToast()
  const input = useRef<HTMLInputElement>(null)
  const [quotes, setQuotes] = useState<QuoteSummary[] | null>(null)
  const [quoteId, setQuoteId] = useState('')
  const [rec, setRec] = useState<Reconciliation | null>(null)
  const [step, setStep] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    // Only tours that are won or deposit-paid can be reconciled.
    Promise.all([quoteApi.list('won'), quoteApi.list('deposit_paid')]).then(([a, b]) => setQuotes([...a, ...b])).catch((err) => setError(errorMessage(err)))
  }, [])
  const select = useCallback(async (id: string) => {
    setQuoteId(id)
    setRec(null)
    setError('')
    if (!id) return
    try {
      const current = await reconcileApi.get(id)
      setRec(current.rows.length ? current : null)
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [])

  const pick = async (file: File | undefined) => {
    if (!file || !quoteId) return
    setError('')
    try {
      setStep('Đang tải hóa đơn…')
      const doc = await rateCardApi.upload(file.name, await readDataUrl(file), 'invoice')
      setStep('AI đang đọc hóa đơn…')
      const extracted = doc.status === 'extracted' ? doc : await rateCardApi.extract(doc.id)
      setStep('Đang đối chiếu…')
      setRec(await reconcileApi.run(quoteId, extracted.id))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setStep('')
      if (input.current) input.current.value = ''
    }
  }

  const edit = async (id: string, body: Parameters<typeof reconcileApi.patchRow>[1]) => {
    try {
      await reconcileApi.patchRow(id, body)
      setRec(await reconcileApi.get(quoteId))
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }
  const confirm = async () => {
    setStep('Đang xác nhận…')
    try {
      setRec(await reconcileApi.confirm(quoteId))
      toast.success('Đã lưu chi phí thực tế cho báo giá.')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setStep('')
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Đối chiếu hóa đơn" description="Sau tour: so chi phí báo giá với hóa đơn nhà cung cấp, gán lý do chênh lệch rồi xác nhận chi phí thực tế." />
      {error && <Alert tone="red">{error}</Alert>}
      <Card>
        <div className="flex flex-wrap items-end gap-3 p-5">
          <div className="min-w-64">
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Báo giá đã chốt</label>
            <Select value={quoteId} onChange={(e) => void select(e.target.value)}>
              <option value="">Chọn báo giá…</option>
              {quotes?.map((q) => <option key={q.id} value={q.id}>{q.code} · {q.customer_name ?? 'Khách lẻ'} · {q.start_date ? formatDate(q.start_date) : ''}</option>)}
            </Select>
          </div>
          <input ref={input} type="file" hidden accept=".csv,.xlsx,.png,.jpg,.jpeg,.webp,.pdf" onChange={(e) => void pick(e.target.files?.[0])} />
          <Button icon={FileUp} disabled={!quoteId || !!rec?.finalized} loading={!!step} onClick={() => input.current?.click()}>Tải hóa đơn</Button>
          <span className="text-sm text-slate-500">{step || 'CSV, XLSX, ảnh hoặc PDF của hóa đơn nhà cung cấp.'}</span>
        </div>
        {quotes === null && !error && <div className="px-5 pb-5"><Spinner /></div>}
        {quotes?.length === 0 && <EmptyState icon={ReceiptText} title="Chưa có báo giá đã chốt" description="Đánh dấu báo giá là Đã chốt sau khi tour diễn ra để đối chiếu." />}
      </Card>

      {rec && (
        <Card>
          <CardHeader title={`Báo giá ${rec.code}: báo giá so với hóa đơn`}
            description={`Báo giá ${vnd(rec.totals.quoted_vnd)} · thực tế ${vnd(rec.totals.actual_vnd)} · chênh ${signed(rec.totals.variance_vnd)}`}
            actions={rec.finalized ? <Badge tone="green">Đã xác nhận</Badge> : <Button icon={CheckCircle2} loading={step === 'Đang xác nhận…'} onClick={confirm}>Xác nhận chi phí thực tế</Button>} />
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="table-head">
                <tr>{['Khoản mục', 'Báo giá', 'Thực tế', 'Chênh lệch', 'Lý do', 'Ghi chú'].map((h) => <th key={h} className="px-4 py-2 text-left font-medium">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rec.rows.map((r) => (
                  <tr key={r.id} className={r.variance_vnd > 0 ? 'bg-rose-50/60' : r.variance_vnd < 0 ? 'bg-emerald-50/60' : ''}>
                    <td className="px-4 py-2">{r.label}</td>
                    <td className="px-4 py-2 whitespace-nowrap">{vnd(r.quoted_vnd)}</td>
                    <td className="px-4 py-2">
                      {rec.finalized ? vnd(r.actual_vnd) : <Input type="number" min={0} className="w-36" defaultValue={r.actual_vnd} onBlur={(e) => Number(e.target.value) !== r.actual_vnd && void edit(r.id, { actual_vnd: Number(e.target.value) })} />}
                    </td>
                    <td className="px-4 py-2 whitespace-nowrap font-medium">{r.variance_vnd ? signed(r.variance_vnd) : '—'}</td>
                    <td className="px-4 py-2">
                      {rec.finalized ? (r.reason ? REASON_LABEL[r.reason] : '—') : (
                        <Select value={r.reason ?? ''} onChange={(e) => void edit(r.id, { reason: (e.target.value || null) as CostReason | null })}>
                          <option value="">Khớp báo giá</option>
                          {Object.entries(REASON_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                        </Select>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-500">{r.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
