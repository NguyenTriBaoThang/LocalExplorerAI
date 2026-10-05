import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { CalendarPlus, Clock, Compass, EyeOff, MapPin, Pencil, Plus, Search, Users } from 'lucide-react'
import {
  Alert, Badge, Button, Card, EmptyState, Field, IconButton, Input, Modal, PageHeader, Select, Spinner, StatusBadge, Tabs, Textarea, Toggle, useToast,
} from '../../components/ui'
import { errorMessage, partnerApi } from '../../lib/api'
import { formatDateTime, formatMoney, INTENTS, isoToLocalInput, localInputToIso } from '../../lib/format'
import type { Experience, ExperienceDraft, Intent, Poi, PoiDraft, Slot } from '../../lib/types'
import { usePartner } from './PartnerLayout'

type SlotFilter = 'upcoming' | 'past' | 'all'

export function PartnerExperiencesPage() {
  const { profile } = usePartner()
  const toast = useToast()
  const [experiences, setExperiences] = useState<Experience[] | null>(null)
  const [pois, setPois] = useState<Poi[]>([])
  const [query, setQuery] = useState('')
  const [slotFilter, setSlotFilter] = useState<SlotFilter>('upcoming')
  const [editing, setEditing] = useState<Experience | 'new' | null>(null)
  const [slotFor, setSlotFor] = useState<Experience | null>(null)
  const [slotEdit, setSlotEdit] = useState<Slot | null>(null)
  const [hiding, setHiding] = useState<Experience | null>(null)

  const load = useCallback(async () => {
    const [items, places] = await Promise.all([partnerApi.experiences(), partnerApi.pois()])
    setExperiences(items)
    setPois(places)
  }, [])
  useEffect(() => { load().catch((err) => { toast.error(errorMessage(err)); setExperiences([]) }) }, [load]) // eslint-disable-line react-hooks/exhaustive-deps

  const visible = useMemo(() => (experiences ?? []).filter((item) =>
    item.title.toLowerCase().includes(query.trim().toLowerCase()) || item.poi_name.toLowerCase().includes(query.trim().toLowerCase())), [experiences, query])

  const hide = async () => {
    if (!hiding) return
    try {
      await partnerApi.hideExperience(hiding.id)
      toast.success('Đã ẩn trải nghiệm.')
      setHiding(null)
      await load()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  if (!experiences) return <Spinner />

  return (
    <>
      <PageHeader title="Trải nghiệm & Slot" description="Tạo trải nghiệm và mở các khung giờ (slot) để du khách đặt chỗ."
        actions={<Button icon={Plus} disabled={!profile.can_publish} onClick={() => setEditing('new')}>Tạo trải nghiệm</Button>} />

      {experiences.length > 0 && (
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div className="relative w-full max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm trải nghiệm, địa điểm…" className="pl-9" />
          </div>
          <Tabs value={slotFilter} onChange={setSlotFilter} items={[{ value: 'upcoming', label: 'Sắp tới' }, { value: 'past', label: 'Đã qua' }, { value: 'all', label: 'Tất cả' }]} />
        </div>
      )}

      {experiences.length === 0 ? (
        <Card>
          <EmptyState icon={Compass} title="Chưa có trải nghiệm nào"
            description={profile.can_publish ? 'Tạo trải nghiệm đầu tiên, sau đó mở slot để khách có thể đặt chỗ.' : 'Bạn có thể tạo trải nghiệm sau khi hồ sơ đối tác được duyệt.'}
            action={profile.can_publish && <Button icon={Plus} onClick={() => setEditing('new')}>Tạo trải nghiệm</Button>} />
        </Card>
      ) : (
        <div className="space-y-5">
          {visible.map((experience) => (
            <ExperienceCard key={experience.id} experience={experience} filter={slotFilter} canPublish={profile.can_publish}
              onEdit={() => setEditing(experience)} onHide={() => setHiding(experience)} onAddSlot={() => setSlotFor(experience)} onEditSlot={setSlotEdit} />
          ))}
          {visible.length === 0 && <p className="py-10 text-center text-sm text-slate-500">Không tìm thấy trải nghiệm phù hợp.</p>}
        </div>
      )}

      {editing && <ExperienceModal experience={editing === 'new' ? null : editing} pois={pois} onClose={() => setEditing(null)}
        onSaved={async (message) => { setEditing(null); toast.success(message); await load() }} />}
      {slotFor && <CreateSlotModal experience={slotFor} onClose={() => setSlotFor(null)}
        onSaved={async (message) => { setSlotFor(null); toast.success(message); await load() }} />}
      {slotEdit && <UpdateSlotModal slot={slotEdit} onClose={() => setSlotEdit(null)}
        onSaved={async () => { setSlotEdit(null); toast.success('Đã cập nhật slot.'); await load() }} />}
      <Modal open={!!hiding} onClose={() => setHiding(null)} size="sm" title="Ẩn trải nghiệm?"
        footer={<><Button variant="secondary" onClick={() => setHiding(null)}>Hủy</Button><Button variant="danger" onClick={hide}>Ẩn trải nghiệm</Button></>}>
        <p className="text-sm text-slate-600">“{hiding?.title}” sẽ không còn hiển thị với du khách. Các booking đã có vẫn được giữ nguyên.</p>
      </Modal>
    </>
  )
}

function ExperienceCard({ experience, filter, canPublish, onEdit, onHide, onAddSlot, onEditSlot }: {
  experience: Experience; filter: SlotFilter; canPublish: boolean; onEdit: () => void; onHide: () => void; onAddSlot: () => void; onEditSlot: (slot: Slot) => void
}) {
  const now = Date.now()
  const slots = experience.slots
    .filter((slot) => filter === 'all' || (filter === 'upcoming' ? new Date(slot.end_at).getTime() >= now : new Date(slot.end_at).getTime() < now))
    .sort((a, b) => (filter === 'past' ? b.start_at.localeCompare(a.start_at) : a.start_at.localeCompare(b.start_at)))
  const hidden = experience.verification_status === 'hidden'

  return (
    <Card className={hidden ? 'opacity-70' : undefined}>
      <div className="flex flex-wrap items-start justify-between gap-4 p-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-slate-900">{experience.title}</h3>
            <StatusBadge status={experience.verification_status} />
            {experience.primary_intent && <Badge tone="brand">{INTENTS[experience.primary_intent]}</Badge>}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-500">
            <span className="inline-flex items-center gap-1.5"><MapPin className="h-4 w-4" />{experience.poi_name}</span>
            <span className="inline-flex items-center gap-1.5"><Clock className="h-4 w-4" />{experience.duration_min} phút</span>
            <span className="font-medium text-slate-700">{formatMoney(experience.price_vnd)}<span className="font-normal text-slate-500"> / {experience.price_basis === 'per_group' ? 'nhóm' : 'khách'}</span></span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button size="sm" icon={CalendarPlus} disabled={!canPublish || hidden} onClick={onAddSlot}>Mở slot</Button>
          <IconButton icon={Pencil} label="Sửa trải nghiệm" disabled={!canPublish} onClick={onEdit} className="disabled:opacity-40" />
          {!hidden && <IconButton icon={EyeOff} label="Ẩn trải nghiệm" disabled={!canPublish} onClick={onHide} className="disabled:opacity-40" />}
        </div>
      </div>
      {experience.verification_status === 'pending' && (
        <p className="mx-5 mb-4 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">Trải nghiệm đang chờ quản trị viên kiểm duyệt nội dung trước khi hiển thị công khai. Bạn vẫn có thể mở slot trước.</p>
      )}
      <div className="overflow-x-auto border-t border-slate-100">
        {slots.length === 0 ? (
          <p className="px-5 py-6 text-center text-sm text-slate-500">{filter === 'upcoming' ? 'Chưa có slot sắp tới.' : 'Không có slot.'}</p>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="table-head">
              <tr>
                <th className="px-5 py-2.5 font-medium">Thời gian</th>
                <th className="px-5 py-2.5 font-medium">Chỗ trống</th>
                <th className="px-5 py-2.5 font-medium">Trạng thái</th>
                <th className="px-5 py-2.5 font-medium">Xác nhận đến</th>
                <th className="px-5 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {slots.map((slot) => {
                const ratio = slot.capacity_total ? Math.max(0, (slot.available_reported ?? 0) / slot.capacity_total) : 0
                const stale = slot.expires_at && new Date(slot.expires_at).getTime() < now
                return (
                  <tr key={slot.id} className="hover:bg-slate-50/60">
                    <td className="whitespace-nowrap px-5 py-3">
                      <p className="font-medium text-slate-900">{formatDateTime(slot.start_at)}</p>
                      <p className="text-xs text-slate-500">đến {new Date(slot.end_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</p>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <span className="inline-flex items-center gap-1 whitespace-nowrap text-slate-700"><Users className="h-3.5 w-3.5 text-slate-400" />{slot.available_reported ?? '?'} / {slot.capacity_total ?? '?'}</span>
                        <span className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-slate-100 sm:block">
                          <span className={ratio > 0.3 ? 'block h-full bg-emerald-500' : 'block h-full bg-amber-500'} style={{ width: `${ratio * 100}%` }} />
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-3"><StatusBadge status={slot.status} /></td>
                    <td className="whitespace-nowrap px-5 py-3">
                      <span className={stale ? 'text-rose-600' : 'text-slate-600'}>{formatDateTime(slot.expires_at)}</span>
                      {stale && <p className="text-xs text-rose-500">Cần xác nhận lại</p>}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <Button size="sm" variant="ghost" disabled={!canPublish || slot.status === 'cancelled' || new Date(slot.start_at).getTime() <= now} title={new Date(slot.start_at).getTime() <= now ? 'Slot đã bắt đầu' : undefined} onClick={() => onEditSlot(slot)}>Cập nhật</Button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </Card>
  )
}

const EMPTY_EXPERIENCE: ExperienceDraft = {
  poi_id: '', title: '', description: '', primary_intent: 'văn_hóa', intent_tags: [], is_hands_on: false, is_indoor: true,
  duration_min: 60, price_vnd: 0, price_basis: 'per_person',
}
const EMPTY_POI: PoiDraft = { name: '', description: '', district: '', latitude: 10.7769, longitude: 106.7009, category: '', address: '' }

function ExperienceModal({ experience, pois, onClose, onSaved }: { experience: Experience | null; pois: Poi[]; onClose: () => void; onSaved: (message: string) => void }) {
  const [draft, setDraft] = useState<ExperienceDraft>(() => experience ? {
    poi_id: experience.poi_id, title: experience.title, description: experience.description, primary_intent: experience.primary_intent ?? 'văn_hóa',
    intent_tags: experience.intent_tags, is_hands_on: experience.is_hands_on, is_indoor: experience.is_indoor,
    duration_min: experience.duration_min, price_vnd: experience.price_vnd, price_basis: experience.price_basis,
  } : { ...EMPTY_EXPERIENCE, poi_id: pois[0]?.id ?? '' })
  const [newPoi, setNewPoi] = useState<PoiDraft | null>(pois.length === 0 ? { ...EMPTY_POI } : null)
  const [tags, setTags] = useState(draft.intent_tags.join(', '))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = <K extends keyof ExperienceDraft>(key: K, value: ExperienceDraft[K]) => setDraft((current) => ({ ...current, [key]: value }))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      let poiId = draft.poi_id
      if (newPoi) poiId = (await partnerApi.createPoi({ ...newPoi, district: newPoi.district || null })).id
      const payload = { ...draft, poi_id: poiId, intent_tags: tags.split(',').map((tag) => tag.trim()).filter(Boolean) }
      if (experience) await partnerApi.updateExperience(experience.id, payload)
      else await partnerApi.createExperience(payload)
      onSaved(experience ? 'Đã cập nhật trải nghiệm. Nội dung sẽ được kiểm duyệt lại.' : 'Đã tạo trải nghiệm. Giờ bạn có thể mở slot.')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open onClose={onClose} size="lg" title={experience ? 'Sửa trải nghiệm' : 'Tạo trải nghiệm'}
      footer={<><Button variant="secondary" onClick={onClose}>Hủy</Button><Button type="submit" form="experience-form" loading={busy}>{experience ? 'Lưu thay đổi' : 'Tạo trải nghiệm'}</Button></>}>
      <form id="experience-form" onSubmit={submit} className="space-y-5">
        {error && <Alert tone="red">{error}</Alert>}
        <Field label="Tên trải nghiệm" required>
          <Input value={draft.title} onChange={(e) => set('title', e.target.value)} required minLength={2} placeholder="VD: Lớp nặn gốm 90 phút" />
        </Field>
        <Field label="Mô tả" required>
          <Textarea value={draft.description} onChange={(e) => set('description', e.target.value)} required placeholder="Khách sẽ làm gì, mang về gì, cần chuẩn bị gì…" />
        </Field>

        <div className="rounded-xl border border-slate-200 p-4">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-medium text-slate-700">Địa điểm</p>
            {pois.length > 0 && (
              <button type="button" onClick={() => setNewPoi(newPoi ? null : { ...EMPTY_POI })} className="text-sm font-medium text-brand-600 hover:text-brand-700">
                {newPoi ? 'Chọn địa điểm có sẵn' : '+ Thêm địa điểm mới'}
              </button>
            )}
          </div>
          {newPoi ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Tên địa điểm" required><Input value={newPoi.name} onChange={(e) => setNewPoi({ ...newPoi, name: e.target.value })} required minLength={2} /></Field>
              <Field label="Loại địa điểm" required><Input value={newPoi.category} onChange={(e) => setNewPoi({ ...newPoi, category: e.target.value })} required minLength={2} placeholder="VD: workshop, nhà hàng" /></Field>
              <Field label="Địa chỉ" required className="sm:col-span-2"><Input value={newPoi.address} onChange={(e) => setNewPoi({ ...newPoi, address: e.target.value })} required minLength={5} /></Field>
              <Field label="Quận/Huyện"><Input value={newPoi.district ?? ''} onChange={(e) => setNewPoi({ ...newPoi, district: e.target.value })} /></Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Vĩ độ" required><Input type="number" step="any" value={newPoi.latitude} onChange={(e) => setNewPoi({ ...newPoi, latitude: Number(e.target.value) })} required /></Field>
                <Field label="Kinh độ" required><Input type="number" step="any" value={newPoi.longitude} onChange={(e) => setNewPoi({ ...newPoi, longitude: Number(e.target.value) })} required /></Field>
              </div>
            </div>
          ) : (
            <Select value={draft.poi_id} onChange={(e) => set('poi_id', e.target.value)} required>
              {pois.map((poi) => <option key={poi.id} value={poi.id}>{poi.name} — {poi.address}</option>)}
            </Select>
          )}
        </div>

        <div className="grid gap-5 sm:grid-cols-3">
          <Field label="Chủ đề" required>
            <Select value={draft.primary_intent} onChange={(e) => set('primary_intent', e.target.value as Intent)}>
              {Object.entries(INTENTS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </Select>
          </Field>
          <Field label="Thời lượng (phút)" required>
            <Input type="number" min={10} max={1440} value={draft.duration_min} onChange={(e) => set('duration_min', Number(e.target.value))} required />
          </Field>
          <Field label="Giá (VND)" required>
            <Input type="number" min={0} step={1000} value={draft.price_vnd} onChange={(e) => set('price_vnd', Number(e.target.value))} required />
          </Field>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Tính giá theo">
            <Select value={draft.price_basis} onChange={(e) => set('price_basis', e.target.value as ExperienceDraft['price_basis'])}>
              <option value="per_person">Mỗi khách</option>
              <option value="per_group">Mỗi nhóm</option>
            </Select>
          </Field>
          <Field label="Thẻ" hint="Phân cách bằng dấu phẩy"><Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="gốm, gia đình, cuối tuần" /></Field>
        </div>
        <div className="flex flex-wrap gap-6">
          <Toggle checked={draft.is_hands_on} onChange={(value) => set('is_hands_on', value)} label="Khách được tự tay làm" />
          <Toggle checked={draft.is_indoor} onChange={(value) => set('is_indoor', value)} label="Trong nhà" />
        </div>
      </form>
    </Modal>
  )
}

function CreateSlotModal({ experience, onClose, onSaved }: { experience: Experience; onClose: () => void; onSaved: (message: string) => void }) {
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  tomorrow.setHours(9, 0, 0, 0)
  const [start, setStart] = useState(isoToLocalInput(tomorrow))
  const [duration, setDuration] = useState(experience.duration_min)
  const [capacity, setCapacity] = useState(10)
  const [available, setAvailable] = useState(10)
  const [repeatDays, setRepeatDays] = useState(1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const occurrences = useMemo(() => Array.from({ length: Math.max(1, Math.min(30, repeatDays)) }, (_, index) => {
    const begin = new Date(start)
    begin.setDate(begin.getDate() + index)
    return { begin, end: new Date(begin.getTime() + duration * 60_000) }
  }), [start, duration, repeatDays])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (available > capacity) return setError('Số chỗ trống không được lớn hơn sức chứa.')
    if (occurrences[0].begin.getTime() <= Date.now()) return setError('Thời gian bắt đầu phải ở tương lai.')
    setBusy(true)
    setError('')
    let created = 0
    try {
      for (const { begin, end } of occurrences) {
        const startIso = localInputToIso(isoToLocalInput(begin))
        await partnerApi.createSlot(experience.id, {
          start_at: startIso, end_at: localInputToIso(isoToLocalInput(end)), capacity_total: capacity, available_reported: available,
          expires_at: startIso,  // the seat count is vouched for until the session starts
        })
        created += 1
      }
      onSaved(created === 1 ? 'Đã mở slot.' : `Đã mở ${created} slot.`)
    } catch (err) {
      setError(created ? `Đã mở ${created}/${occurrences.length} slot. Lỗi ở slot tiếp theo: ${errorMessage(err)}` : errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open onClose={onClose} title="Mở slot mới" description={experience.title}
      footer={<><Button variant="secondary" onClick={onClose}>Hủy</Button><Button type="submit" form="slot-form" loading={busy}>{occurrences.length > 1 ? `Mở ${occurrences.length} slot` : 'Mở slot'}</Button></>}>
      <form id="slot-form" onSubmit={submit} className="space-y-5">
        {error && <Alert tone="red">{error}</Alert>}
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Bắt đầu" required><Input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} required /></Field>
          <Field label="Thời lượng (phút)" required><Input type="number" min={10} max={1440} value={duration} onChange={(e) => setDuration(Number(e.target.value))} required /></Field>
          <Field label="Sức chứa" required><Input type="number" min={1} max={10000} value={capacity} onChange={(e) => { setCapacity(Number(e.target.value)); setAvailable(Number(e.target.value)) }} required /></Field>
          <Field label="Chỗ trống hiện tại" required><Input type="number" min={0} max={capacity} value={available} onChange={(e) => setAvailable(Number(e.target.value))} required /></Field>
        </div>
        <Field label="Lặp lại hằng ngày" hint="Tạo cùng khung giờ cho nhiều ngày liên tiếp (tối đa 30).">
          <Input type="number" min={1} max={30} value={repeatDays} onChange={(e) => setRepeatDays(Number(e.target.value))} />
        </Field>
        <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
          <p className="font-medium text-slate-700">Xem trước</p>
          <ul className="mt-1.5 space-y-0.5">
            {occurrences.slice(0, 4).map(({ begin, end }) => (
              <li key={begin.toISOString()}>{formatDateTime(begin.toISOString())} – {end.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</li>
            ))}
            {occurrences.length > 4 && <li className="text-slate-400">… và {occurrences.length - 4} slot khác</li>}
          </ul>
        </div>
      </form>
    </Modal>
  )
}

function UpdateSlotModal({ slot, onClose, onSaved }: { slot: Slot; onClose: () => void; onSaved: () => void }) {
  const [status, setStatus] = useState<'open' | 'full' | 'cancelled'>(slot.status === 'full' ? 'full' : 'open')
  const [available, setAvailable] = useState(slot.available_reported ?? 0)
  const [capacity, setCapacity] = useState(slot.capacity_total ?? 1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await partnerApi.updateSlot(slot.id, {
        expected_version: slot.version, status,
        available_reported: status === 'cancelled' ? null : status === 'full' ? 0 : available,
        capacity_total: capacity,
        expires_at: status === 'cancelled' ? null : localInputToIso(isoToLocalInput(new Date(slot.start_at))),
      })
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open onClose={onClose} size="sm" title="Cập nhật slot" description={formatDateTime(slot.start_at)}
      footer={<><Button variant="secondary" onClick={onClose}>Hủy</Button><Button type="submit" form="slot-update-form" variant={status === 'cancelled' ? 'danger' : 'primary'} loading={busy}>{status === 'cancelled' ? 'Hủy slot' : 'Xác nhận số chỗ'}</Button></>}>
      <form id="slot-update-form" onSubmit={submit} className="space-y-5">
        {error && <Alert tone="red">{error}</Alert>}
        <Tabs value={status} onChange={setStatus} items={[{ value: 'open', label: 'Còn chỗ' }, { value: 'full', label: 'Hết chỗ' }, { value: 'cancelled', label: 'Hủy' }]} />
        {status === 'open' && (
          <div className="grid grid-cols-2 gap-4">
            <Field label="Chỗ trống"><Input type="number" min={1} max={capacity} value={available} onChange={(e) => setAvailable(Number(e.target.value))} required /></Field>
            <Field label="Sức chứa"><Input type="number" min={1} value={capacity} onChange={(e) => setCapacity(Number(e.target.value))} required /></Field>
          </div>
        )}
        {status === 'cancelled' && <Alert tone="amber">Khách đã giữ chỗ ở slot này sẽ được thông báo. Không thể hoàn tác.</Alert>}
        {status !== 'cancelled' && <p className="text-xs text-slate-500">Xác nhận này có hiệu lực đến giờ bắt đầu slot.</p>}
      </form>
    </Modal>
  )
}
