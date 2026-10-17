import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { ChevronDown, ChevronRight, Copy, FileSpreadsheet, GitMerge } from 'lucide-react'
import {
  Alert, Badge, Button, Card, CardHeader, EmptyState, Field, Input, Modal, PageHeader, Select, Spinner, Tabs, useToast,
} from '../../components/ui'
import { useAuth } from '../../auth/AuthContext'
import { errorMessage } from '../../lib/api'
import {
  adminImportsApi, type DuplicatePair, type PlaceImportBatch, type PlaceImportCandidate,
} from '../../lib/adminImports'

type Tab = 'imports' | 'duplicates'

export function AdminImportsPage() {
  const { can } = useAuth()
  const canImports = can('admin:place_import')
  const canDuplicates = can('admin:duplicates')
  const [selected, setTab] = useState<Tab>('imports')
  // Fall back to the one section the role may use.
  const tab: Tab = selected === 'imports' && !canImports ? 'duplicates' : selected === 'duplicates' && !canDuplicates ? 'imports' : selected
  const [dupCount, setDupCount] = useState<number | undefined>(undefined)
  return (
    <>
      <PageHeader title="Nhập địa điểm & Trùng lặp" description="Bổ sung bằng chứng cho địa điểm nhập từ file nguồn và gộp các địa điểm trùng nhau." />
      <div className="mb-6">
        <Tabs value={tab} onChange={setTab} items={[
          ...(canImports ? [{ value: 'imports' as const, label: 'Nhập địa điểm' }] : []),
          ...(canDuplicates ? [{ value: 'duplicates' as const, label: 'Trùng lặp', count: dupCount }] : []),
        ]} />
      </div>
      {tab === 'imports' ? <PlaceImports /> : <Duplicates onCount={setDupCount} />}
      {tab === 'imports' && canDuplicates && <DuplicateCountLoader onCount={setDupCount} />}
    </>
  )
}

/** Loads the duplicate count on mount so the tab badge is accurate before the tab is opened. */
function DuplicateCountLoader({ onCount }: { onCount: (count: number) => void }) {
  useEffect(() => {
    let alive = true
    adminImportsApi.duplicates().then((rows) => { if (alive) onCount(rows.length) }).catch(() => undefined)
    return () => { alive = false }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

/* ---------- Place imports ---------- */

const FLAG_LABELS: Record<string, string> = {
  source_url_missing: 'Thiếu URL nguồn',
  source_url_insecure: 'URL nguồn chưa dùng HTTPS',
  source_type_missing: 'Thiếu loại nguồn',
  source_license_missing: 'Thiếu giấy phép/điều khoản nguồn',
  source_license_review_pending: 'Giấy phép/điều khoản nguồn cần rà soát',
  address_missing: 'Thiếu địa chỉ',
  address_geocode_needs_confirmation: 'Địa chỉ tra ngược, chưa xác nhận đúng POI',
  opening_hours_missing: 'Thiếu giờ mở cửa',
  price_basis_missing: 'Thiếu đơn vị/phạm vi giá',
  price_amount_unverified: 'Giá trong file chưa được kiểm chứng',
  photo_missing: 'Thiếu ảnh',
  photo_rights_review_pending: 'Quyền sử dụng ảnh cần rà soát riêng',
  coordinates_missing: 'Thiếu tọa độ',
  coordinates_reused: 'Tọa độ bị lặp',
  verified_flag_unsubstantiated: 'Cờ verified chưa có bằng chứng',
  verified_claim_pending_review: 'Nhãn verified trong file chưa được duyệt',
  field_coverage_incomplete: 'Nguồn chưa khai báo đủ trường POI bắt buộc',
  field_level_evidence_pending: 'Chưa duyệt bằng chứng theo từng trường',
  observed_at_missing: 'Thiếu thời điểm quan sát nguồn',
  observed_at_invalid_or_timezone_missing: 'Thời điểm nguồn sai hoặc thiếu múi giờ',
  observed_at_in_future: 'Thời điểm nguồn đang ở tương lai',
  expires_at_missing: 'Thiếu hạn rà soát nguồn',
  expires_at_invalid_or_timezone_missing: 'Hạn nguồn sai hoặc thiếu múi giờ',
  evidence_expired: 'Bằng chứng đã hết hạn',
  evidence_expiry_before_observation: 'Hạn nguồn trước thời điểm quan sát',
}

const POI_EVIDENCE_FIELDS = [
  ['name', 'Tên địa điểm'],
  ['address', 'Địa chỉ'],
  ['latitude', 'Vĩ độ'],
  ['longitude', 'Kinh độ'],
  ['category', 'Danh mục'],
] as const

function isSafeHttpsUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && Boolean(url.hostname) && !url.username && !url.password
  } catch {
    return false
  }
}

const QUALITY_METRICS: Array<[string, string]> = [
  ['Thiếu địa chỉ', 'address_missing'],
  ['Tọa độ dùng lại', 'coordinates_reused'],
  ['Thiếu giờ mở cửa', 'opening_hours_missing'],
  ['Thiếu URL nguồn', 'source_url_missing'],
  ['URL nguồn không dùng HTTPS', 'source_url_insecure'],
  ['Thiếu loại nguồn', 'source_type_missing'],
  ['Thiếu giấy phép/điều khoản', 'source_license_missing'],
  ['Điều khoản nguồn cần rà soát', 'source_license_review_pending'],
  ['Ảnh cần rà quyền dùng', 'photo_rights_review_pending'],
  ['Thiếu thời điểm quan sát', 'observed_at_missing'],
  ['Thiếu hạn rà soát', 'expires_at_missing'],
  ['Nguồn khai thiếu trường POI', 'field_coverage_incomplete'],
  ['Thiếu cơ sở giá', 'price_basis_missing'],
  ['Giá chưa xác minh', 'price_amount_unverified'],
  ['Địa chỉ cần đối chiếu', 'address_geocode_needs_confirmation'],
  ['Bằng chứng theo trường còn thiếu', 'field_level_evidence_pending'],
  ['Cờ verified thiếu chứng cứ', 'verified_flag_unsubstantiated'],
  ['Cờ verified trong file', 'source_verified_true'],
]

function PlaceImports() {
  const [batches, setBatches] = useState<PlaceImportBatch[] | null>(null)
  const [batchId, setBatchId] = useState('')
  const [candidates, setCandidates] = useState<PlaceImportCandidate[] | null>(null)
  const [loadError, setLoadError] = useState('')
  const [batchError, setBatchError] = useState('')
  const [promoting, setPromoting] = useState<PlaceImportCandidate | null>(null)

  const loadBatches = useCallback(() => {
    setBatchError('')
    adminImportsApi.placeImports()
      .then((rows) => { setBatches(rows); setBatchId((current) => current || rows[0]?.id || '') })
      .catch((err) => { setBatchError(errorMessage(err)); setBatches((current) => current ?? []) })
  }, [])
  useEffect(loadBatches, [loadBatches])

  // Only the latest request may fill the list: a slow answer for a batch the admin already left must not replace it.
  const latestBatch = useRef('')
  const loadCandidates = useCallback(() => {
    if (!batchId) return
    latestBatch.current = batchId
    setCandidates(null)
    setLoadError('')
    adminImportsApi.candidates(batchId)
      .then((rows) => { if (latestBatch.current === batchId) setCandidates(rows) })
      .catch((err) => { if (latestBatch.current === batchId) { setLoadError(errorMessage(err)); setCandidates([]) } })
  }, [batchId])
  useEffect(loadCandidates, [loadCandidates])

  if (!batches) return <Spinner />
  if (batchError) {
    return (
      <Alert tone="red" title="Không tải được danh sách lô dữ liệu"
        action={<Button size="sm" variant="secondary" onClick={loadBatches}>Thử lại</Button>}>{batchError}</Alert>
    )
  }
  const batch = batches.find((item) => item.id === batchId)

  return (
    <div className="space-y-6">
      <Alert tone="amber">
        Dữ liệu ở đây chỉ là bản ghi nguồn chờ bổ sung, chưa phải POI vận hành và không xuất hiện trong tìm kiếm/lập lịch.
        Không duyệt cờ verified từ Excel nếu thiếu URL nguồn và bằng chứng hiện hành.
      </Alert>

      {batches.length === 0 || !batch ? (
        <Card><EmptyState icon={FileSpreadsheet} title="Chưa có lô dữ liệu POI nào được nhập." /></Card>
      ) : (
        <>
          <Card>
            <CardHeader title="Danh sách địa điểm chờ bổ sung" description={`${batch.source_name} · Sheet ${batch.worksheet_name} · ${batch.record_count} dòng`} />
            <div className="space-y-5 p-5">
              <Field label="Lô dữ liệu">
                <Select value={batchId} onChange={(event) => setBatchId(event.target.value)}>
                  {batches.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.source_name} ({item.record_count}) · {new Date(item.created_at).toLocaleString('vi-VN')} · {item.source_sha256.slice(0, 8)}
                    </option>
                  ))}
                </Select>
              </Field>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                {QUALITY_METRICS.map(([label, key]) => (
                  <div key={key} className="rounded-lg border border-slate-200 p-3">
                    <p className="text-xs text-slate-500">{label}</p>
                    <p className="mt-1 text-xl font-semibold text-slate-900">{Number(batch.quality_summary[key] || 0)}</p>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          {loadError && (
            <Alert tone="red" title="Không tải được bản ghi nguồn"
              action={<Button size="sm" variant="secondary" onClick={loadCandidates}>Thử lại</Button>}>{loadError}</Alert>
          )}
          {!candidates ? <Spinner label="Đang tải bản ghi nguồn…" /> : loadError ? null : (
            <Card>
              <CardHeader title={`Bản ghi nguồn (${candidates.length})`} />
              {candidates.length === 0
                ? <EmptyState icon={FileSpreadsheet} title="Lô này chưa có bản ghi." />
                : <div className="divide-y divide-slate-100">
                    {candidates.map((candidate) => (
                      <CandidateRow key={candidate.id} candidate={candidate} onPromote={() => setPromoting(candidate)} />
                    ))}
                  </div>}
            </Card>
          )}
        </>
      )}

      {promoting && (
        <PromoteModal
          batchId={batchId}
          candidate={promoting}
          onClose={() => setPromoting(null)}
          onSettled={loadCandidates}
          onDone={() => setPromoting(null)}
        />
      )}
    </div>
  )
}

function candidateStatus(candidate: PlaceImportCandidate): [string, 'green' | 'amber' | 'gray'] {
  if (candidate.target_poi_status === 'verified') return ['Verified and public', 'green']
  if (candidate.target_poi_id) return ['Awaiting evidence review', 'amber']
  return ['Needs enrichment', 'gray']
}

function CandidateRow({ candidate, onPromote }: { candidate: PlaceImportCandidate; onPromote: () => void }) {
  const [open, setOpen] = useState(false)
  const raw = candidate.raw_payload
  const sourceUrl = String(raw.source_url || raw.source_uri || raw.source || '')
  const sourceUrlIsHttps = isSafeHttpsUrl(sourceUrl)
  const tags = Array.isArray(raw.tags) ? raw.tags.map(String).join(', ') : String(raw.tags || '')
  const [statusLabel, statusTone] = candidateStatus(candidate)
  const lines: string[] = [
    `ID nguồn: ${candidate.external_id}`,
    `Tọa độ trong file: ${String(raw.lat ?? 'trống')}, ${String(raw.lon ?? 'trống')}`,
    `Giá trong file: ${String(raw.price_vnd ?? 'trống')} VND · cơ sở: ${String(raw.price_basis || 'chưa có')} · đơn vị: ${String(raw.price_unit || 'chưa rõ')}`,
  ]
  if (raw.address) lines.push(`Địa chỉ Goong gợi ý: ${String(raw.address)}`)
  if (raw.address_source_reference) lines.push(`Nguồn địa chỉ: ${String(raw.address_source_reference)}`)
  if (raw.address_status) lines.push(`Trạng thái địa chỉ: ${String(raw.address_status)}`)
  if (raw.source_type) lines.push(`Loại nguồn ghi trong file (chưa rà soát): ${String(raw.source_type)}`)
  if (raw.license) lines.push(`Giấy phép/điều khoản ghi trong file (chưa rà soát): ${String(raw.license)}`)
  if (raw.fields_covered) lines.push(`Trường nguồn tự khai (chưa đối chiếu): ${Array.isArray(raw.fields_covered) ? raw.fields_covered.map(String).join(', ') : String(raw.fields_covered)}`)
  if (raw.observed_at) lines.push(`Thời điểm nguồn ghi trong file (chưa rà soát): ${String(raw.observed_at)}`)
  if (raw.expires_at) lines.push(`Hạn nguồn ghi trong file (chưa rà soát): ${String(raw.expires_at)}`)
  if (raw.price_status) lines.push(`Trạng thái giá: ${String(raw.price_status)}`)
  if (raw.verification_basis) lines.push(`Căn cứ cờ xác minh: ${String(raw.verification_basis)}`)
  if (raw.evidence_status) lines.push(`Bằng chứng: ${String(raw.evidence_status)}`)
  lines.push(
    `Cờ verified gốc trong Excel: ${String(raw.verified ?? false)}`,
    `Nguồn ghi trong file: ${String(raw.source || 'không có')}`,
    `Tags: ${tags || 'không có'}`,
  )
  if (raw.description) lines.push(String(raw.description))
  if (raw.note) lines.push(`Ghi chú nguồn: ${String(raw.note)}`)
  if (raw.photo_url) lines.push(`Ảnh ghi trong file: ${String(raw.photo_url)} · ghi công: ${String(raw.photo_credit || 'chưa có')} · giấy phép ảnh: ${String(raw.photo_license || 'chưa có')}`)

  return (
    <div className="px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <button type="button" className="flex min-w-0 flex-1 items-start gap-2 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-slate-400" /> : <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-slate-400" />}
          <span className="min-w-0">
            <span className="block font-medium text-slate-900">{candidate.name}</span>
            <span className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span>{candidate.kind}</span>
              <span>Dòng Excel {candidate.source_row}</span>
              <Badge tone={statusTone} dot>{statusLabel}</Badge>
              <span>{candidate.quality_flags.length} cảnh báo</span>
            </span>
            {candidate.quality_flags.length > 0 && (
              <span className="mt-2 flex flex-wrap gap-1.5">
                {candidate.quality_flags.map((flag) => <Badge key={flag} tone="amber">{FLAG_LABELS[flag] || flag}</Badge>)}
              </span>
            )}
          </span>
        </button>
        {(candidate.review_status === 'needs_enrichment' || (candidate.target_poi_id && candidate.target_poi_status === 'pending')) && (
          <Button size="sm" onClick={onPromote}>{candidate.target_poi_id ? 'Thêm nguồn xác minh' : 'Bổ sung & gửi duyệt'}</Button>
        )}
      </div>
      {open && (
        <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
          <ul className="space-y-1">
            {lines.map((line, index) => <li key={index} className="break-words">{line}</li>)}
            {sourceUrl && <li className="break-words">URL nguồn trong file (chưa xác minh): {sourceUrlIsHttps
              ? <a href={sourceUrl} target="_blank" rel="noreferrer" className="text-blue-700 underline">Mở nguồn HTTPS</a>
              : sourceUrl}</li>}
            {Boolean(raw.photo_url) && (() => {
              const photoUrl = String(raw.photo_url)
              const safePhotoUrl = isSafeHttpsUrl(photoUrl)
              return <li className="break-words">URL ảnh trong file (chưa xác minh): {safePhotoUrl
                ? <a href={photoUrl} target="_blank" rel="noreferrer" className="text-blue-700 underline">Mở ảnh</a>
                : photoUrl}</li>
            })()}
          </ul>
        </div>
      )}
    </div>
  )
}

function PromoteModal({ batchId, candidate, onClose, onDone, onSettled }: {
  batchId: string; candidate: PlaceImportCandidate; onClose: () => void; onDone: () => void; onSettled: () => void
}) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [fieldsCovered, setFieldsCovered] = useState<string[]>([])
  const sourceTypes = ['official', 'provider', 'website', 'dataset', 'field_check']
  const rawSourceType = String(candidate.raw_payload.source_type || '')

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const selectedFields = form.getAll('fields_covered').map(String)
    const observedAt = new Date(String(form.get('observed_at') || ''))
    const expiresAt = new Date(String(form.get('expires_at') || ''))
    if (selectedFields.length === 0) {
      toast.error('Chọn ít nhất một trường mà URL nguồn xác nhận trực tiếp.')
      return
    }
    if (Number.isNaN(observedAt.getTime()) || Number.isNaN(expiresAt.getTime())) {
      toast.error('Vui lòng nhập ngày quan sát và hạn dùng bằng chứng hợp lệ.')
      return
    }
    setBusy(true)
    try {
      const response = await adminImportsApi.promote(batchId, candidate.id, {
        address: String(form.get('address') || ''),
        latitude: Number(form.get('latitude')),
        longitude: Number(form.get('longitude')),
        category: String(form.get('category') || ''),
        source_uri: String(form.get('source_uri') || ''),
        source_type: String(form.get('source_type') || ''),
        source_label: String(form.get('source_label') || ''),
        license: String(form.get('license') || '') || null,
        fields_covered: selectedFields,
        observed_at: observedAt.toISOString(),
        expires_at: expiresAt.toISOString(),
      })
      if ((response as { status?: string } | undefined)?.status === 'already_submitted') {
        toast.info('Ứng viên này đã được gửi trước đó')
      } else {
        toast.success(`Đã gửi ${candidate.name} vào hàng chờ duyệt bằng chứng. Địa điểm sẽ hiển thị công khai sau khi duyệt.`)
      }
      onDone()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
      onSettled()
    }
  }

  return (
    <Modal open onClose={() => { if (!busy) onClose() }} size="lg" title={`Bổ sung bằng chứng: ${candidate.name}`}
      description="Chỉ chọn những trường URL này xác nhận trực tiếp. Các cờ verified trong Excel không thay thế bằng chứng."
      footer={<>
        <Button variant="secondary" onClick={onClose} disabled={busy}>Hủy</Button>
        <Button type="submit" form="promote-form" loading={busy} disabled={!confirmed || fieldsCovered.length === 0}>Gửi duyệt</Button>
      </>}>
      <form id="promote-form" onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label="Địa chỉ (đối chiếu với nguồn)" required className="sm:col-span-2">
          <Input name="address" defaultValue={String(candidate.raw_payload.address || candidate.raw_payload.full_address || '')} required minLength={5} maxLength={300} />
        </Field>
        <Field label="Vĩ độ (nhập lại và xác minh)" required>
          <Input name="latitude" type="number" min={-90} max={90} step="any" required />
        </Field>
        <Field label="Kinh độ (nhập lại và xác minh)" required>
          <Input name="longitude" type="number" min={-180} max={180} step="any" required />
        </Field>
        <Field label="Danh mục đã xác minh" required>
          <Input name="category" defaultValue={candidate.kind} required minLength={2} maxLength={40} />
        </Field>
        <Field label="URL nguồn (HTTPS)" required>
          <Input name="source_uri" type="url" defaultValue={String(candidate.raw_payload.source_url || candidate.raw_payload.source_uri || '')} required placeholder="https://..." />
        </Field>
        <Field label="Loại nguồn">
          <Select name="source_type" defaultValue={sourceTypes.includes(rawSourceType) ? rawSourceType : ''} required>
            <option value="" disabled>Chọn loại nguồn</option>
            <option value="official">Chính thức</option>
            <option value="provider">Đối tác</option>
            <option value="website">Website</option>
            <option value="dataset">Bộ dữ liệu có nguồn</option>
            <option value="field_check">Khảo sát thực địa</option>
          </Select>
        </Field>
        <Field label="Tên nguồn / người xác minh" required>
          <Input name="source_label" required minLength={2} maxLength={180} />
        </Field>
        <Field label="Giấy phép (tùy chọn)">
          <Input name="license" maxLength={120} placeholder="Chỉ ghi điều khoản đã kiểm tra; chưa rõ thì để trống" />
        </Field>
        <Field label="Ngày quan sát" required>
          <Input name="observed_at" type="datetime-local" required />
        </Field>
        <Field label="Bằng chứng hết hạn vào" required>
          <Input name="expires_at" type="datetime-local" required />
        </Field>
        <fieldset className="space-y-2 sm:col-span-2">
          <legend className="mb-2 text-sm font-medium text-slate-700">Các trường URL này xác nhận trực tiếp</legend>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {POI_EVIDENCE_FIELDS.map(([field, label]) => (
              <label key={field} className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  name="fields_covered"
                  value={field}
                  checked={fieldsCovered.includes(field)}
                  onChange={(event) => setFieldsCovered((current) => event.target.checked
                    ? [...current, field]
                    : current.filter((item) => item !== field))}
                />
                {label}
              </label>
            ))}
          </div>
          <p className="text-xs text-slate-500">Có thể gửi thêm nguồn riêng cho các trường còn thiếu. Không chọn trường chỉ vì giá trị có sẵn trong Excel.</p>
        </fieldset>
        <label className="flex items-start gap-2 text-sm text-slate-700 sm:col-span-2">
          <input type="checkbox" className="mt-1" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
          Tôi đã mở URL và đối chiếu từng trường đã chọn; giấy phép và quyền ảnh chưa rõ sẽ không được xem là đã xác minh.
        </label>
      </form>
    </Modal>
  )
}

/* ---------- Duplicates ---------- */

function Duplicates({ onCount }: { onCount: (count: number) => void }) {
  const toast = useToast()
  const [pairs, setPairs] = useState<DuplicatePair[] | null>(null)
  const [merging, setMerging] = useState<DuplicatePair | null>(null)
  const [keep, setKeep] = useState<'a' | 'b'>('a')
  const [busy, setBusy] = useState(false)
  const [loadError, setLoadError] = useState('')

  const load = useCallback(() => {
    setLoadError('')
    adminImportsApi.duplicates()
      .then((rows) => { setPairs(rows); onCount(rows.length) })
      .catch((err) => { setLoadError(errorMessage(err)); setPairs((current) => current ?? []) })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(load, [load])

  const openMerge = (pair: DuplicatePair) => { setKeep('a'); setMerging(pair) }
  const confirmMerge = async () => {
    if (!merging) return
    const kept = keep === 'a' ? merging.poi_a : merging.poi_b
    const dup = keep === 'a' ? merging.poi_b : merging.poi_a
    setBusy(true)
    try {
      await adminImportsApi.merge(kept.id, dup.id, 'Admin xác nhận gộp cặp trùng')
      toast.success('Đã chuyển trải nghiệm/lịch sang POI giữ lại và ẩn POI trùng.')
      setMerging(null)
      setPairs(null)
      load()
    } catch (err) {
      toast.error(errorMessage(err, 'Không thể gộp hai POI này.'))
    } finally {
      setBusy(false)
    }
  }

  if (!pairs) return <Spinner />
  if (loadError) {
    return (
      <Alert tone="red" title="Không tải được danh sách trùng lặp"
        action={<Button size="sm" variant="secondary" onClick={load}>Thử lại</Button>}>{loadError}</Alert>
    )
  }
  const kept = merging ? (keep === 'a' ? merging.poi_a : merging.poi_b) : null
  const dup = merging ? (keep === 'a' ? merging.poi_b : merging.poi_a) : null

  return (
    <>
      <Card>
        <CardHeader title={`Các cặp địa điểm (POI) có khả năng trùng lặp (${pairs.length})`}
          description="Thuật toán phát hiện dựa trên khoảng cách địa lý và độ tương đồng tên gọi." />
        {pairs.length === 0 ? (
          <EmptyState icon={Copy} title="Chưa phát hiện cặp tên hoặc tọa độ trùng nhau." />
        ) : (
          <div className="divide-y divide-slate-100">
            {pairs.map((pair) => (
              <div key={`${pair.poi_a.id}-${pair.poi_b.id}`} className="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
                <div className="grid min-w-0 flex-1 items-center gap-3 sm:grid-cols-[1fr_auto_1fr]">
                  <div className="min-w-0">
                    <p className="text-xs text-slate-500">POI A</p>
                    <p className="truncate font-medium text-slate-900">{pair.poi_a.name}</p>
                  </div>
                  <div className="text-center">
                    <Badge tone="amber">{Math.round(pair.name_similarity * 100)}%</Badge>
                    <p className="mt-0.5 text-xs text-slate-500">Trùng tên</p>
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs text-slate-500">POI B</p>
                    <p className="truncate font-medium text-slate-900">{pair.poi_b.name}</p>
                  </div>
                </div>
                <Button size="sm" icon={GitMerge} onClick={() => openMerge(pair)}>Gộp cặp này...</Button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Modal open={!!merging} onClose={() => { if (!busy) setMerging(null) }} title="Gộp hai POI"
        description="Chọn POI cần giữ lại. POI còn lại sẽ bị ẩn."
        footer={<>
          <Button variant="secondary" disabled={busy} onClick={() => setMerging(null)}>Hủy</Button>
          <Button variant="danger" icon={GitMerge} loading={busy} onClick={confirmMerge}>Xác nhận gộp</Button>
        </>}>
        {merging && kept && dup && (
          <div className="space-y-4">
            <div className="space-y-2">
              {([['a', merging.poi_a], ['b', merging.poi_b]] as const).map(([key, poi]) => (
                <label key={key} className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 p-3 text-sm has-[:checked]:border-brand-500 has-[:checked]:bg-brand-50">
                  <input type="radio" name="keep" className="mt-1" checked={keep === key} onChange={() => setKeep(key)} />
                  <span className="min-w-0">
                    <span className="block font-medium text-slate-900">Giữ lại: {poi.name}</span>
                    <span className="block break-all text-xs text-slate-500">ID: {poi.id}</span>
                  </span>
                </label>
              ))}
            </div>
            <Alert tone="amber">
              Chuyển toàn bộ trải nghiệm/lịch sang “{kept.name}” và ẩn “{dup.name}”?
            </Alert>
          </div>
        )}
      </Modal>
    </>
  )
}
