import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ExternalLink, Plus, ShieldCheck, X } from 'lucide-react'
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, Select, Spinner, StatCard, StatusBadge, Textarea, useToast } from '../../components/ui'
import { errorMessage, partnerApi } from '../../lib/api'
import { formatDateTime, isoToLocalInput, localInputToIso } from '../../lib/format'
import type { Experience, Poi } from '../../lib/types'
import {
  EVIDENCE_FIELDS, EVIDENCE_SOURCE_TYPES, evidenceLink, partnerEvidenceApi,
  type EvidenceOutcome, type EvidenceSourceType, type InlineEvidence, type EvidenceTargetType, type PartnerEvidence,
} from '../../lib/partnerTools'

const DAY = 24 * 60 * 60 * 1000

type Form = {
  target_type: EvidenceTargetType
  target_id: string
  source_uri: string
  source_type: EvidenceSourceType
  source_label: string
  license: string
  fields: string[]
  observed_at: string
  expires_at: string
  notes: string
}

const blank = (): Form => ({
  target_type: 'experience', target_id: '', source_uri: '', source_type: 'official_website', source_label: '', license: '',
  fields: [], observed_at: isoToLocalInput(new Date(Date.now() - 60_000)), expires_at: isoToLocalInput(new Date(Date.now() + 30 * DAY)), notes: '',
})

export function PartnerEvidencePage() {
  const toast = useToast()
  const [items, setItems] = useState<PartnerEvidence[] | null>(null)
  const [experiences, setExperiences] = useState<Experience[]>([])
  const [pois, setPois] = useState<Poi[]>([])
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<Form>(blank)
  const [saving, setSaving] = useState(false)
  const [params, setParams] = useSearchParams()

  // Preselect target from ?type=experience|poi&id=... (used by the post-save notice).
  useEffect(() => {
    const type = params.get('type')
    const id = params.get('id')
    if ((type === 'experience' || type === 'poi') && id) {
      setForm({ ...blank(), target_type: type, target_id: id })
      setOpen(true)
      setParams({}, { replace: true })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const load = () => Promise.all([partnerEvidenceApi.list(), partnerApi.experiences(), partnerApi.pois()])
    .then(([evidence, exps, points]) => { setItems(evidence); setExperiences(exps); setPois(points) })
    .catch((err) => { toast.error(errorMessage(err)); setItems((current) => current ?? []) })
  useEffect(() => { void load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const targets = useMemo(
    () => (form.target_type === 'experience'
      ? experiences.map((e) => ({ id: e.id, label: e.title }))
      : pois.map((p) => ({ id: p.id, label: p.name }))),
    [form.target_type, experiences, pois],
  )
  const names = useMemo(() => new Map([
    ...experiences.map((e) => [e.id, e.title] as const),
    ...pois.map((p) => [p.id, p.name] as const),
  ]), [experiences, pois])
  const verified = (items ?? []).filter((e) => e.verification_status === 'verified').length

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }))
  const fieldOptions = EVIDENCE_FIELDS[form.target_type]

  function changeTarget(type: EvidenceTargetType) {
    setForm((f) => ({ ...f, target_type: type, target_id: '', fields: [] }))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!form.target_id) { toast.error('Hãy chọn đối tượng cần chứng minh.'); return }
    if (!/^https?:\/\//i.test(form.source_uri.trim())) { toast.error('Nguồn phải là đường dẫn http(s) có thể truy vết.'); return }
    if (!form.fields.length) { toast.error('Chọn ít nhất một trường dữ liệu mà nguồn này chứng minh.'); return }
    setSaving(true)
    try {
      await partnerEvidenceApi.submit({
        target_type: form.target_type,
        target_id: form.target_id,
        source_uri: form.source_uri.trim(),
        source_type: form.source_type,
        source_label: form.source_label.trim() || null,
        license: form.license.trim() || null,
        fields_covered: form.fields,
        observed_at: localInputToIso(form.observed_at),
        expires_at: localInputToIso(form.expires_at),
        notes: form.notes.trim(),
      })
      toast.success('Đã gửi nguồn vào hàng chờ quản trị viên xác minh.')
      setOpen(false)
      setForm(blank())
      void load()
    } catch (err) { toast.error(errorMessage(err)) }
    finally { setSaving(false) }
  }

  return (
    <>
      <PageHeader
        title="Nguồn xác minh"
        description="Bằng chứng pháp lý, bài viết báo chí hoặc xác nhận chính thức chứng minh tính xác thực của cơ sở."
        actions={<Button icon={Plus} onClick={() => { setForm(blank()); setOpen(true) }}>Gửi nguồn mới</Button>}
      />
      {!items ? <Spinner /> : (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-2">
            <StatCard label="Nguồn đã gửi" value={items.length} icon={ShieldCheck} />
            <StatCard label="Đã kiểm duyệt" value={verified} icon={ShieldCheck} tone="green" />
          </div>
          {items.length === 0 ? (
            <Card><EmptyState icon={ShieldCheck} title="Chưa gửi bằng chứng nguồn nào" description="Gửi nguồn có thể truy vết để quản trị viên xác minh trải nghiệm và địa điểm của bạn."
              action={<Button icon={Plus} onClick={() => { setForm(blank()); setOpen(true) }}>Gửi nguồn mới</Button>} /></Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {items.map((source) => (
                <Card key={source.id} className="flex flex-col gap-3 p-5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <StatusBadge status={source.verification_status} />
                      <h3 className="mt-2 truncate font-medium text-slate-900">{source.source_label || EVIDENCE_SOURCE_TYPES[source.source_type as EvidenceSourceType] || source.source_type}</h3>
                      <p className="truncate text-xs text-slate-500">{names.get(source.target_id) ?? source.target_id}</p>
                    </div>
                    <Badge tone="brand">{source.target_type === 'experience' ? 'Trải nghiệm' : 'Địa điểm POI'}</Badge>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {source.fields_covered.map((field) => <span key={field} className="rounded-md bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{field}</span>)}
                  </div>
                  <div className="text-xs text-slate-500">
                    <p>Quan sát: {formatDateTime(source.observed_at)}</p>
                    <p>Hết hạn: {formatDateTime(source.expires_at)}</p>
                  </div>
                  <div className="mt-auto pt-1">
                    {/^https?:\/\//i.test(source.source_uri) ? (
                      <a href={source.source_uri} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline">
                        <ExternalLink className="h-3.5 w-3.5" /> Xem liên kết nguồn
                      </a>
                    ) : <span className="text-xs text-slate-500">{source.source_uri} (xác nhận nội bộ)</span>}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Gửi nguồn xác minh" size="lg"
        description="Nguồn được đưa vào hàng chờ và chỉ có hiệu lực sau khi quản trị viên duyệt."
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Hủy</Button><Button type="submit" form="evidence-form" loading={saving}>Gửi nguồn</Button></>}>
        <form id="evidence-form" className="space-y-4" onSubmit={submit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Loại đối tượng" required>
              <Select value={form.target_type} onChange={(e) => changeTarget(e.target.value as EvidenceTargetType)}>
                <option value="experience">Trải nghiệm</option>
                <option value="poi">Địa điểm (POI)</option>
              </Select>
            </Field>
            <Field label="Đối tượng" required>
              <Select required value={form.target_id} onChange={(e) => set('target_id', e.target.value)}>
                <option value="">— Chọn —</option>
                {targets.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </Select>
            </Field>
          </div>
          <Field label="Đường dẫn nguồn (https)" required>
            <Input required type="url" maxLength={1000} value={form.source_uri} onChange={(e) => set('source_uri', e.target.value)} placeholder="https://…" />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Loại nguồn" required>
              <Select value={form.source_type} onChange={(e) => set('source_type', e.target.value as EvidenceSourceType)}>
                {Object.entries(EVIDENCE_SOURCE_TYPES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </Select>
            </Field>
            <Field label="Nhãn nguồn"><Input maxLength={180} value={form.source_label} onChange={(e) => set('source_label', e.target.value)} placeholder="Ví dụ: Trang chủ làng nghề" /></Field>
          </div>
          <Field label="Giấy phép / bản quyền"><Input maxLength={120} value={form.license} onChange={(e) => set('license', e.target.value)} /></Field>
          <Field label="Các trường dữ liệu được chứng minh" required>
            <div className="flex flex-wrap gap-2">
              {fieldOptions.map((field) => {
                const on = form.fields.includes(field)
                return (
                  <label key={field} className={`cursor-pointer rounded-full border px-3 py-1 text-xs ${on ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-slate-300 text-slate-600'}`}>
                    <input type="checkbox" className="sr-only" checked={on} onChange={(e) => set('fields', e.target.checked ? [...form.fields, field] : form.fields.filter((f) => f !== field))} />
                    {field}
                  </label>
                )
              })}
              <button type="button" className="text-xs text-brand-700 hover:underline" onClick={() => set('fields', form.fields.length === fieldOptions.length ? [] : [...fieldOptions])}>
                {form.fields.length === fieldOptions.length ? 'Bỏ chọn tất cả' : 'Chọn tất cả'}
              </button>
            </div>
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Thời điểm quan sát" required hint="Không được ở tương lai."><Input required type="datetime-local" value={form.observed_at} onChange={(e) => set('observed_at', e.target.value)} /></Field>
            <Field label="Hết hạn" required hint="Phải còn trong tương lai."><Input required type="datetime-local" value={form.expires_at} onChange={(e) => set('expires_at', e.target.value)} /></Field>
          </div>
          <Field label="Ghi chú"><Textarea maxLength={1000} value={form.notes} onChange={(e) => set('notes', e.target.value)} placeholder="Cơ sở khai báo nguồn chứng minh các trường đã chọn." /></Field>
        </form>
      </Modal>
    </>
  )
}

/* ---------- Reusable pieces for the experience / place forms ---------- */

/** Optional collapsible "Nguồn xác minh" block. Controlled; validation lives in lib/partnerTools. */
export function InlineEvidenceBlock({ targetType, value, onChange }: {
  /** 'both' is used while a new place is created together with its experience: one source, fields of either record. */
  targetType: EvidenceTargetType | 'both'; value: InlineEvidence; onChange: (next: InlineEvidence) => void
}) {
  const options = targetType === 'both' ? [...EVIDENCE_FIELDS.poi, ...EVIDENCE_FIELDS.experience] : EVIDENCE_FIELDS[targetType]
  const set = <K extends keyof InlineEvidence>(key: K, v: InlineEvidence[K]) => onChange({ ...value, [key]: v })
  return (
    <details className="rounded-xl border border-slate-200 p-4 sm:col-span-2" open={value.source_uri.trim() !== ''}>
      <summary className="cursor-pointer text-sm font-medium text-slate-700">
        Nguồn xác minh <span className="font-normal text-slate-500">(tùy chọn — cần để hiển thị công khai)</span>
      </summary>
      <div className="mt-4 space-y-4">
        {targetType === 'both' && (
          <p className="text-xs text-slate-500">Địa điểm mới và trải nghiệm là hai bản ghi riêng: nguồn này sẽ được gửi cho từng bản ghi với các trường tương ứng bạn chọn (name, address, latitude, longitude, category thuộc địa điểm; các trường còn lại thuộc trải nghiệm).</p>
        )}
        <p className="text-xs text-slate-500">Mỗi lần sửa nội dung, nguồn cũ bị vô hiệu. Gửi nguồn mới tại đây để quản trị viên xác minh ngay.</p>
        <Field label="Đường dẫn nguồn (https)">
          <Input type="text" inputMode="url" maxLength={1000} value={value.source_uri} onChange={(e) => set('source_uri', e.target.value)} placeholder="https://…" />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Loại nguồn">
            <Select value={value.source_type} onChange={(e) => set('source_type', e.target.value as EvidenceSourceType)}>
              {Object.entries(EVIDENCE_SOURCE_TYPES).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </Select>
          </Field>
          <Field label="Nhãn nguồn"><Input maxLength={180} value={value.source_label} onChange={(e) => set('source_label', e.target.value)} placeholder="Ví dụ: Trang chủ làng nghề" /></Field>
        </div>
        <Field label="Các trường dữ liệu được chứng minh">
          <div className="flex flex-wrap gap-2">
            {options.map((field) => {
              const on = value.fields.includes(field)
              return (
                <label key={field} className={`cursor-pointer rounded-full border px-3 py-1 text-xs ${on ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-slate-300 text-slate-600'}`}>
                  <input type="checkbox" className="sr-only" checked={on} onChange={(e) => set('fields', e.target.checked ? [...value.fields, field] : value.fields.filter((f) => f !== field))} />
                  {field}
                </label>
              )
            })}
            <button type="button" className="text-xs text-brand-700 hover:underline" onClick={() => set('fields', value.fields.length === options.length ? [] : [...options])}>
              {value.fields.length === options.length ? 'Bỏ chọn tất cả' : 'Chọn tất cả'}
            </button>
          </div>
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Thời điểm quan sát" hint="Không được ở tương lai."><Input type="datetime-local" value={value.observed_at} onChange={(e) => set('observed_at', e.target.value)} /></Field>
          <Field label="Hết hạn" hint="Phải còn trong tương lai."><Input type="datetime-local" value={value.expires_at} onChange={(e) => set('expires_at', e.target.value)} /></Field>
        </div>
      </div>
    </details>
  )
}

/** Persistent notice shown on list pages after a save without (or with failed) evidence. */
export function EvidenceNotice({ outcome, onDismiss }: { outcome: EvidenceOutcome; onDismiss: () => void }) {
  const failed = outcome.state === 'failed'
  return (
    <div className="mb-5">
      <Alert tone="amber"
        title={failed ? 'Đã lưu, nhưng nguồn xác minh chưa được gửi' : undefined}
        action={<button type="button" aria-label="Đóng" onClick={onDismiss} className="text-amber-700 hover:text-amber-900"><X className="h-4 w-4" /></button>}>
        {failed
          ? 'Mục đã được lưu nhưng chưa hiển thị công khai vì chưa có nguồn xác minh. '
          : 'Đã lưu. Mục này chưa hiển thị công khai cho tới khi có nguồn xác minh — thêm ở Nguồn xác minh. '}
        <Link to={evidenceLink(outcome.targetType, outcome.targetId)} className="font-medium underline">
          {failed ? 'Gửi lại nguồn xác minh' : 'Thêm nguồn xác minh'}
        </Link>
      </Alert>
    </div>
  )
}
