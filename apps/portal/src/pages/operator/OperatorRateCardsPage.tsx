import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, FileUp, GitCompare, Sparkles, XCircle } from 'lucide-react'
import { Alert, Badge, Button, Card, CardHeader, Drawer, EmptyState, Input, Modal, PageHeader, Select, Spinner, StatusBadge, useToast } from '../../components/ui'
import { errorMessage } from '../../lib/api'
import {
  rateCardApi, type ExtractedLine, type OperatorDocument, type RateCard, type RateCardDiff, type RateCategory, type RateUnit, type RequoteSummary,
} from '../../lib/operatorApi'

const CATEGORY_LABEL: Record<RateCategory, string> = { vehicle: 'Xe', guide: 'Hướng dẫn viên', meal: 'Ăn uống', ticket: 'Vé tham quan', hotel: 'Lưu trú', surcharge: 'Phụ thu' }
const UNIT_LABEL: Record<RateUnit, string> = { per_km: '/km', per_day: '/ngày', per_trip: '/chuyến', per_pax: '/khách', per_room_night: '/phòng-đêm', pct: '%' }
const LOW_CONFIDENCE = 0.7
const money = (n: number, unit?: RateUnit) => (unit === 'pct' ? `${n}%` : `${n.toLocaleString('vi-VN')}đ`)

function readDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(new Error('Không đọc được tệp.'))
    reader.readAsDataURL(file)
  })
}

function ReviewGrid({ doc, onChange }: { doc: OperatorDocument; onChange: (doc: OperatorDocument | null) => void }) {
  const toast = useToast()
  const [supplier, setSupplier] = useState(doc.extracted?.supplier ?? '')
  const [lines, setLines] = useState<ExtractedLine[]>(doc.extracted?.lines ?? [])
  const [edited, setEdited] = useState<Set<number>>(new Set())
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  const patch = (index: number, change: Partial<ExtractedLine>) => {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...change } : line)))
    setEdited((prev) => new Set(prev).add(index))
  }
  const numberOrNull = (value: string) => (value === '' ? null : Number(value))

  const create = async () => {
    setBusy('create')
    setError('')
    try {
      // A cell the user touched has been looked at, so it stops being flagged as uncertain.
      const reviewed = lines.map((line, i) => (edited.has(i) ? { ...line, confidence: 1 } : line))
      await rateCardApi.saveLines(doc.id, supplier.trim() || null, reviewed)
      await rateCardApi.fromDocument(doc.id, supplier.trim())
      toast.success('Đã tạo bảng giá nháp. Kiểm tra rồi duyệt để kích hoạt.')
      onChange(null)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy('')
    }
  }
  const reject = async () => {
    setBusy('reject')
    try {
      await rateCardApi.reject(doc.id)
      onChange(null)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy('')
    }
  }

  const uncertain = lines.filter((l, i) => l.confidence < LOW_CONFIDENCE && !edited.has(i)).length
  return (
    <Card>
      <CardHeader title={`Duyệt dữ liệu trích xuất: ${doc.filename}`} description="Sửa trực tiếp trên bảng. Dòng tô vàng có độ tin cậy thấp, cần đối chiếu với tài liệu gốc." />
      <div className="space-y-4 p-5">
        {error && <Alert tone="red">{error}</Alert>}
        {uncertain > 0 && <Alert tone="amber">{uncertain} dòng có độ tin cậy dưới {LOW_CONFIDENCE * 100}%.</Alert>}
        <div className="max-w-sm">
          <label className="mb-1 block text-sm font-medium text-slate-700">Nhà cung cấp</label>
          <Input value={supplier} placeholder="Tên nhà cung cấp" onChange={(e) => setSupplier(e.target.value)} />
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="table-head">
              <tr>
                {['Loại', 'Mô tả', 'Đơn vị', 'Số chỗ', 'Đơn giá (VNĐ / %)', 'Tin cậy', 'Nguồn'].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {lines.map((line, i) => (
                <tr key={i} className={line.confidence < LOW_CONFIDENCE && !edited.has(i) ? 'bg-amber-50' : ''}>
                  <td className="px-3 py-2">
                    <Select value={line.category} onChange={(e) => patch(i, { category: e.target.value as RateCategory })}>
                      {Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </Select>
                  </td>
                  <td className="px-3 py-2"><Input value={line.label} onChange={(e) => patch(i, { label: e.target.value })} /></td>
                  <td className="px-3 py-2">
                    <Select value={line.unit} onChange={(e) => patch(i, { unit: e.target.value as RateUnit })}>
                      {Object.entries(UNIT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </Select>
                  </td>
                  <td className="px-3 py-2"><Input type="number" min={1} className="w-20" value={line.seats ?? ''} onChange={(e) => patch(i, { seats: numberOrNull(e.target.value) })} /></td>
                  <td className="px-3 py-2"><Input type="number" min={0} className="w-36" value={line.amount_vnd} onChange={(e) => patch(i, { amount_vnd: Number(e.target.value) })} /></td>
                  <td className="px-3 py-2 whitespace-nowrap">{Math.round((edited.has(i) ? 1 : line.confidence) * 100)}%</td>
                  <td className="px-3 py-2 text-slate-500">{line.source_ref}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {lines.length === 0 && <EmptyState icon={FileUp} title="Không trích xuất được dòng giá nào" description="Thử tệp khác hoặc từ chối tài liệu này." />}
        <div className="flex flex-wrap gap-2">
          <Button icon={CheckCircle2} loading={busy === 'create'} disabled={!supplier.trim() || lines.length === 0} onClick={create}>Tạo bảng giá</Button>
          <Button variant="secondary" icon={XCircle} loading={busy === 'reject'} onClick={reject}>Từ chối tài liệu</Button>
        </div>
      </div>
    </Card>
  )
}

function Importer({ onDone }: { onDone: () => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [doc, setDoc] = useState<OperatorDocument | null>(null)
  const [step, setStep] = useState('')
  const [error, setError] = useState('')

  const pick = async (file: File | undefined) => {
    if (!file) return
    setError('')
    setDoc(null)
    try {
      setStep('Đang tải lên…')
      const uploaded = await rateCardApi.upload(file.name, await readDataUrl(file))
      if (uploaded.status === 'approved' || uploaded.status === 'rejected') {
        setError(uploaded.status === 'approved' ? 'Tệp này đã được dùng để tạo bảng giá.' : 'Tệp này đã bị từ chối trước đó.')
        return
      }
      setStep('AI đang đọc bảng giá…')
      setDoc(uploaded.status === 'extracted' ? uploaded : await rateCardApi.extract(uploaded.id))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setStep('')
      if (input.current) input.current.value = ''
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center gap-3 p-5">
          <input ref={input} type="file" hidden accept=".csv,.xlsx,.png,.jpg,.jpeg,.webp,.pdf" onChange={(e) => void pick(e.target.files?.[0])} />
          <Button icon={FileUp} loading={!!step} onClick={() => input.current?.click()}>Tải lên bảng giá</Button>
          <span className="text-sm text-slate-500">{step || 'CSV, XLSX, ảnh chụp hoặc PDF, tối đa 10 MB. AI sẽ trích xuất, bạn duyệt trước khi áp dụng.'}</span>
        </div>
        {error && <div className="px-5 pb-5"><Alert tone="red">{error}</Alert></div>}
      </Card>
      {doc?.status === 'extracted' && <ReviewGrid doc={doc} onChange={(next) => { setDoc(next); if (!next) onDone() }} />}
    </div>
  )
}

export function OperatorRateCardsPage() {
  const toast = useToast()
  const [cards, setCards] = useState<RateCard[] | null>(null)
  const [error, setError] = useState('')
  const [detail, setDetail] = useState<RateCard | null>(null)
  const [diff, setDiff] = useState<RateCardDiff | null>(null)
  const [busy, setBusy] = useState('')
  const [requote, setRequote] = useState<RequoteSummary | null>(null)

  const load = useCallback(async () => {
    try {
      setCards(await rateCardApi.cards())
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [])
  useEffect(() => { void load() }, [load])

  const groups = useMemo(() => {
    const map = new Map<string, RateCard[]>()
    for (const card of cards ?? []) map.set(`${card.supplier}\u0000${card.category}`, [...(map.get(`${card.supplier}\u0000${card.category}`) ?? []), card])
    return [...map.values()]
  }, [cards])

  const act = async (key: string, fn: () => Promise<void>) => {
    setBusy(key)
    try {
      await fn()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy('')
    }
  }
  const approve = (card: RateCard) => act(card.id, async () => {
    const { requote: summary } = await rateCardApi.approve(card.id)
    toast.success(summary.requoted ? `Đã kích hoạt ${card.supplier} v${card.version}. ${summary.requoted} báo giá bị ảnh hưởng.` : `Đã kích hoạt ${card.supplier} v${card.version}`)
    setRequote(summary.requoted ? summary : null)
    setDetail(null)
    await load()
  })
  const open = (card: RateCard) => act(`open-${card.id}`, async () => setDetail(await rateCardApi.card(card.id)))
  const compare = (older: RateCard, newer: RateCard) => act(`diff-${newer.id}`, async () => setDiff(await rateCardApi.diff(older.id, newer.id)))

  return (
    <div className="space-y-6">
      <PageHeader title="Bảng giá" description="Bảng giá NET theo nhà cung cấp, có phiên bản. Chỉ bản đã duyệt mới được dùng để tính giá." />
      <Importer onDone={() => void load()} />
      {requote && (
        <Alert tone={requote.alerts.length ? 'red' : 'amber'} title={`${requote.requoted} báo giá bị ảnh hưởng, ${requote.alerts.length} xuống dưới biên sàn`}>
          <ul className="mt-1 space-y-1">
            {requote.quotes.map((q) => (
              <li key={q.quote_id}>
                <Link className="font-medium underline" to={`/operator/quotes/${q.quote_id}`}>{q.code}</Link>: giá vốn {q.old_cost_vnd.toLocaleString('vi-VN')}đ → {q.new_cost_vnd.toLocaleString('vi-VN')}đ
                {requote.alerts.some((a) => a.quote_id === q.quote_id) && <b> · dưới sàn, cần xử lý</b>}
              </li>
            ))}
          </ul>
        </Alert>
      )}
      {error && <Alert tone="red">{error}</Alert>}
      {cards === null && !error && <Spinner />}
      {cards?.length === 0 && <Card><EmptyState icon={Sparkles} title="Chưa có bảng giá" description="Tải lên bảng giá đầu tiên của nhà cung cấp để bắt đầu." /></Card>}
      {groups.map((versions) => {
        const head = versions[0]
        return (
          <Card key={`${head.supplier}-${head.category}`}>
            <CardHeader title={head.supplier} description={CATEGORY_LABEL[head.category]} />
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="table-head">
                  <tr>{['Phiên bản', 'Trạng thái', 'Số dòng', 'Hiệu lực từ', ''].map((h) => <th key={h} className="px-5 py-2 font-medium">{h}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {versions.map((card, i) => (
                    <tr key={card.id}>
                      <td className="px-5 py-2 font-medium">v{card.version}</td>
                      <td className="px-5 py-2"><StatusBadge status={card.status} /></td>
                      <td className="px-5 py-2">{card.item_count}</td>
                      <td className="px-5 py-2">{card.valid_from ?? '—'}</td>
                      <td className="flex justify-end gap-2 px-5 py-2">
                        <Button size="sm" variant="secondary" loading={busy === `open-${card.id}`} onClick={() => void open(card)}>Xem</Button>
                        {versions[i + 1] && <Button size="sm" variant="secondary" icon={GitCompare} loading={busy === `diff-${card.id}`} onClick={() => void compare(versions[i + 1], card)}>So với v{versions[i + 1].version}</Button>}
                        {card.status === 'draft' && <Button size="sm" loading={busy === card.id} onClick={() => void approve(card)}>Duyệt</Button>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )
      })}

      <Drawer open={!!detail} onClose={() => setDetail(null)} title={detail ? `${detail.supplier} v${detail.version}` : ''} subtitle={detail ? CATEGORY_LABEL[detail.category] : ''}
        footer={detail?.status === 'draft' ? <Button loading={busy === detail.id} onClick={() => void approve(detail)}>Duyệt và kích hoạt</Button> : undefined}>
        {detail?.status === 'draft' && <div className="mb-4"><Alert tone="amber">Bản nháp: chưa được dùng để tính giá. Sau khi duyệt sẽ không sửa được.</Alert></div>}
        <ul className="divide-y divide-slate-100 text-sm">
          {detail?.items?.map((item) => (
            <li key={item.id} className="flex items-start justify-between gap-3 py-2">
              <div>
                <div className="font-medium text-slate-800">{item.label}</div>
                <div className="text-xs text-slate-500">{item.code}{item.seats ? ` · ${item.seats} chỗ` : ''}{Object.keys(item.conditions).length ? ` · ${JSON.stringify(item.conditions)}` : ''}</div>
              </div>
              <div className="whitespace-nowrap font-medium">{money(item.amount_vnd, item.unit)} <span className="text-xs font-normal text-slate-500">{UNIT_LABEL[item.unit]}</span></div>
            </li>
          ))}
        </ul>
      </Drawer>

      <Modal open={!!diff} onClose={() => setDiff(null)} size="lg" title={diff ? `${diff.from.supplier}: v${diff.from.version} → v${diff.to.version}` : ''}
        description={diff ? `${diff.changed.length} đổi giá, ${diff.added.length} thêm mới, ${diff.removed.length} bị bỏ, ${diff.unchanged} không đổi` : ''}>
        <ul className="divide-y divide-slate-100 text-sm">
          {diff?.changed.map((c) => (
            <li key={c.code} className="flex items-center justify-between gap-3 py-2">
              <span>{c.label}</span>
              <span className="whitespace-nowrap">{money(c.old_vnd)} → <b>{money(c.new_vnd)}</b>{' '}
                <Badge tone={c.delta_vnd > 0 ? 'red' : 'green'}>{c.delta_vnd > 0 ? '+' : ''}{c.delta_pct ?? '—'}%</Badge></span>
            </li>
          ))}
          {diff?.added.map((c) => <li key={c.code} className="flex justify-between py-2"><span>{c.label}</span><Badge tone="green">Mới · {money(c.new_vnd)}</Badge></li>)}
          {diff?.removed.map((c) => <li key={c.code} className="flex justify-between py-2"><span>{c.label}</span><Badge tone="gray">Bỏ · {money(c.old_vnd)}</Badge></li>)}
        </ul>
        {diff && !diff.changed.length && !diff.added.length && !diff.removed.length && <p className="text-sm text-slate-500">Hai phiên bản giống nhau.</p>}
      </Modal>
    </div>
  )
}
