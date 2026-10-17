import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { categoryLabel } from '../../lib/catalog'
import { MapPin, Pencil, Plus } from 'lucide-react'
import { Alert, Button, Card, EmptyState, Field, IconButton, Input, Modal, PageHeader, Spinner, StatusBadge, Textarea, useToast } from '../../components/ui'
import { errorMessage, partnerApi } from '../../lib/api'
import type { Poi, PoiDraft } from '../../lib/types'
import { usePartner } from './PartnerLayout'
import { EvidenceNotice, InlineEvidenceBlock } from './PartnerEvidencePage'
import {
  blankInlineEvidence, hasInlineEvidence, submitInlineEvidence, validateInlineEvidence, type EvidenceOutcome, type InlineEvidence,
} from '../../lib/partnerTools'

const EMPTY: PoiDraft = { name: '', description: '', district: '', latitude: 10.7769, longitude: 106.7009, category: '', address: '' }

export function PartnerPlacesPage() {
  const { profile } = usePartner()
  const toast = useToast()
  const [pois, setPois] = useState<Poi[] | null>(null)
  const [editing, setEditing] = useState<{ id?: string; draft: PoiDraft } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [evidence, setEvidence] = useState<InlineEvidence>(blankInlineEvidence)
  const [notice, setNotice] = useState<EvidenceOutcome | null>(null)

  const load = useCallback(() => { partnerApi.pois().then(setPois).catch(() => setPois([])) }, [])
  useEffect(load, [load])

  const save = async (event: FormEvent) => {
    event.preventDefault()
    if (!editing) return
    const withEvidence = hasInlineEvidence(evidence)
    if (withEvidence) {
      const problem = validateInlineEvidence(evidence)
      if (problem) { setError(problem); return }
    }
    setBusy(true)
    setError('')
    try {
      const payload = { ...editing.draft, district: editing.draft.district || null }
      const saved = editing.id ? await partnerApi.updatePoi(editing.id, payload) : await partnerApi.createPoi(payload)
      const id = saved?.id ?? editing.id ?? ''
      const message = editing.id ? 'Đã cập nhật địa điểm. Địa điểm sẽ được kiểm duyệt lại.' : 'Đã thêm địa điểm, đang chờ kiểm duyệt.'
      if (!withEvidence) {
        toast.success(message)
        // Updates report whether earlier evidence was voided; a new place simply has none yet.
        setNotice(!editing.id || (saved as { evidence_invalidated?: boolean } | undefined)?.evidence_invalidated === true ? { state: 'missing', targetType: 'poi', targetId: id } : null)
      } else {
        try {
          await submitInlineEvidence('poi', id, evidence)
          toast.success(`${message} Nguồn xác minh đã được gửi.`)
          setNotice(null)
        } catch (evErr) {
          toast.error(`Đã lưu địa điểm nhưng chưa gửi được nguồn xác minh: ${errorMessage(evErr)}. Vào Nguồn xác minh để gửi lại.`)
          setNotice({ state: 'failed', targetType: 'poi', targetId: id })
        }
      }
      setEditing(null)
      load()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const draft = editing?.draft
  const set = <K extends keyof PoiDraft>(key: K, value: PoiDraft[K]) => editing && setEditing({ ...editing, draft: { ...editing.draft, [key]: value } })
  const mapSrc = draft && `https://www.openstreetmap.org/export/embed.html?bbox=${draft.longitude - 0.006},${draft.latitude - 0.004},${draft.longitude + 0.006},${draft.latitude + 0.004}&layer=mapnik&marker=${draft.latitude},${draft.longitude}`

  return (
    <>
      <PageHeader title="Địa điểm của tôi" description="Nơi diễn ra các trải nghiệm của bạn. Địa điểm mới được kiểm duyệt trước khi hiển thị trên bản đồ."
        actions={<Button icon={Plus} disabled={!profile.can_publish} onClick={() => { setError(''); setEvidence(blankInlineEvidence()); setEditing({ draft: { ...EMPTY } }) }}>Thêm địa điểm</Button>} />
      {notice && <EvidenceNotice outcome={notice} onDismiss={() => setNotice(null)} />}
      {!pois ? <Spinner /> : pois.length === 0 ? (
        <Card><EmptyState icon={MapPin} title="Chưa có địa điểm" description="Thêm địa điểm cơ sở của bạn để gắn trải nghiệm." /></Card>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {pois.map((poi) => (
            <Card key={poi.id} className="overflow-hidden">
              <iframe title={poi.name} className="pointer-events-none h-36 w-full" loading="lazy"
                src={`https://www.openstreetmap.org/export/embed.html?bbox=${poi.longitude - 0.004},${poi.latitude - 0.0025},${poi.longitude + 0.004},${poi.latitude + 0.0025}&layer=mapnik&marker=${poi.latitude},${poi.longitude}`} />
              <div className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-slate-900">{poi.name}</p>
                    <p className="truncate text-sm text-slate-500">{poi.address}</p>
                  </div>
                  <IconButton icon={Pencil} label="Sửa" disabled={!profile.can_publish} onClick={() => { setError(''); setEvidence(blankInlineEvidence()); setEditing({ id: poi.id, draft: { name: poi.name, description: poi.description, district: poi.district ?? '', latitude: poi.latitude, longitude: poi.longitude, category: poi.category, address: poi.address } }) }} />
                </div>
                <div className="mt-3 flex items-center justify-between text-xs text-slate-500"><span>{categoryLabel(poi.category)}{poi.district && ` · ${poi.district}`}</span><StatusBadge status={poi.verification_status} /></div>
              </div>
            </Card>
          ))}
        </div>
      )}
      <Modal open={!!editing} onClose={() => setEditing(null)} size="lg" title={editing?.id ? 'Sửa địa điểm' : 'Thêm địa điểm'}
        footer={<><Button variant="secondary" onClick={() => setEditing(null)}>Hủy</Button><Button type="submit" form="poi-form" loading={busy}>Lưu</Button></>}>
        {draft && (
          <form id="poi-form" onSubmit={save} className="grid gap-4 sm:grid-cols-2">
            {error && <div className="sm:col-span-2"><Alert tone="red">{error}</Alert></div>}
            <Field label="Tên địa điểm" required><Input value={draft.name} onChange={(e) => set('name', e.target.value)} required minLength={2} /></Field>
            <Field label="Loại" required><Input value={draft.category} onChange={(e) => set('category', e.target.value)} required minLength={2} placeholder="workshop, nhà hàng…" /></Field>
            <Field label="Địa chỉ" required className="sm:col-span-2"><Input value={draft.address} onChange={(e) => set('address', e.target.value)} required minLength={5} /></Field>
            <Field label="Quận/Huyện"><Input value={draft.district ?? ''} onChange={(e) => set('district', e.target.value)} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Vĩ độ"><Input type="number" step="any" value={draft.latitude} onChange={(e) => set('latitude', Number(e.target.value))} /></Field>
              <Field label="Kinh độ"><Input type="number" step="any" value={draft.longitude} onChange={(e) => set('longitude', Number(e.target.value))} /></Field>
            </div>
            <Field label="Mô tả" className="sm:col-span-2"><Textarea value={draft.description} onChange={(e) => set('description', e.target.value)} /></Field>
            <InlineEvidenceBlock targetType="poi" value={evidence} onChange={setEvidence} />
            {mapSrc && <iframe title="Bản đồ" src={mapSrc} className="h-52 w-full rounded-lg border border-slate-200 sm:col-span-2" loading="lazy" />}
          </form>
        )}
      </Modal>
    </>
  )
}
