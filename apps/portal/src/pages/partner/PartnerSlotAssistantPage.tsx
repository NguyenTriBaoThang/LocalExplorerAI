import { useEffect, useMemo, useState } from 'react'
import { MessageSquareText, ShieldCheck } from 'lucide-react'
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Field, Input, PageHeader, Spinner, StatusBadge, Textarea, useToast } from '../../components/ui'
import { errorMessage, partnerApi } from '../../lib/api'
import { localInputToIso } from '../../lib/format'
import type { Experience } from '../../lib/types'
import { slotAssistantApi, type SlotAssistantPreview } from '../../lib/partnerTools'

const TZ = 'Asia/Ho_Chi_Minh'
const dayFmt = new Intl.DateTimeFormat('sv-SE', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' })
const timeFmt = new Intl.DateTimeFormat('vi-VN', { timeZone: TZ, hour: '2-digit', minute: '2-digit' })

type SlotChoice = {
  id: string
  start_at: string
  end_at: string
  available_reported: number | null
  status: string
  experience_title: string
  local_date: string
}

export function PartnerSlotAssistantPage() {
  const toast = useToast()
  const [providerId, setProviderId] = useState('')
  const [experiences, setExperiences] = useState<Experience[] | null>(null)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [message, setMessage] = useState('')
  const [preview, setPreview] = useState<SlotAssistantPreview | null>(null)
  const [expiresAt, setExpiresAt] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)

  const load = () => Promise.all([partnerApi.profile(), partnerApi.experiences()])
    .then(([profile, list]) => { setProviderId(profile.id); setExperiences(list) })
    .catch((err) => { toast.error(errorMessage(err)); setExperiences((current) => current ?? []) })
  useEffect(() => { void load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const slots: SlotChoice[] = useMemo(() => (experiences ?? []).flatMap((experience) => experience.slots
    .filter((slot) => slot.status !== 'cancelled')
    .map((slot) => ({
      id: slot.id, start_at: slot.start_at, end_at: slot.end_at, available_reported: slot.available_reported,
      status: slot.status, experience_title: experience.title, local_date: dayFmt.format(new Date(slot.start_at)),
    }))), [experiences])

  const selected = slots.filter((slot) => selectedIds.includes(slot.id))
  const selectedDay = selected[0]?.local_date
  const todayHcm = dayFmt.format(new Date())
  const todaySlots = slots.filter((slot) => slot.local_date === todayHcm)
  const needsExpiry = preview?.action_preview.action === 'UPDATE_CAPACITY' && preview.action_preview.new_status === 'open'

  function toggleSlot(slot: SlotChoice, checked: boolean) {
    setError('')
    setNotice('')
    setPreview(null)
    if (checked && selectedDay && selectedDay !== slot.local_date) {
      setError('API chỉ cho xử lý một ngày mỗi lần. Hãy bỏ chọn các ca ngày khác trước.')
      return
    }
    setSelectedIds((current) => (checked ? [...new Set([...current, slot.id])] : current.filter((id) => id !== slot.id)))
  }

  async function createPreview() {
    setExpiresAt('')
    setError('')
    setNotice('')
    setPreview(null)
    setLoading(true)
    try {
      setPreview(await slotAssistantApi.preview(providerId, message.trim(), selectedIds))
    } catch (reason) { setError(errorMessage(reason)) }
    finally { setLoading(false) }
  }

  async function confirm() {
    if (!preview) return
    if (needsExpiry && !expiresAt) { setError('Hãy nhập thời điểm hết hạn xác nhận sức chứa.'); return }
    if (!window.confirm('Xác nhận áp dụng chính xác thay đổi trong bản xem trước?')) return
    setError('')
    setNotice('')
    setLoading(true)
    try {
      const result = await slotAssistantApi.confirm(providerId, preview.confirmation_token, needsExpiry ? localInputToIso(expiresAt) : undefined)
      setNotice(`Đã xác nhận ${result.action} cho ${result.updated_slot_ids.length} ca. Bản xem trước đã hết hiệu lực.`)
      setPreview(null)
      setExpiresAt('')
      setMessage('')
      setSelectedIds([])
      void load()
    } catch (reason) {
      setError(errorMessage(reason))
      const status = (reason as { response?: { status?: number } })?.response?.status
      if (status === 409 || status === 401) { setPreview(null); setExpiresAt(''); void load() }   // the token or the slot version is no longer valid
    }
    finally { setLoading(false) }
  }

  return (
    <>
      <PageHeader title="Trợ lý cập nhật ca" description="Chọn ca trong cùng một ngày, nhập tin nhắn của cơ sở, xem trước rồi xác nhận. AI không tự ghi thay đổi nếu bạn chưa bấm xác nhận." />
      {!experiences ? <Spinner /> : (
        <div className="space-y-5">
          <Alert tone="brand" title="Lệnh xác nhận có hiệu lực 5 phút">Hệ thống kiểm tra phiên bản ca để tránh ghi đè dữ liệu mới.</Alert>
          {notice && <Alert tone="green">{notice}</Alert>}
          {error && <Alert tone="red">{error}</Alert>}

          <Card>
            <CardHeader
              title="1. Chọn ca"
              description={`Đã chọn ${selected.length} ca${selectedDay ? ` · ngày ${selectedDay}` : ''}.`}
              actions={(
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="secondary" disabled={!todaySlots.length} onClick={() => { setSelectedIds(todaySlots.map((slot) => slot.id)); setPreview(null); setError('') }}>
                    Chọn toàn bộ ca hôm nay ({todaySlots.length})
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => { setSelectedIds([]); setPreview(null) }}>Bỏ chọn tất cả</Button>
                </div>
              )}
            />
            {slots.length === 0 ? <EmptyState icon={MessageSquareText} title="Chưa có ca để cập nhật" /> : (
              <ul className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
                {slots.map((slot) => (
                  <li key={slot.id}>
                    <label className="flex cursor-pointer items-center gap-3 px-5 py-3 hover:bg-slate-50">
                      <input type="checkbox" className="h-4 w-4 rounded border-slate-300" checked={selectedIds.includes(slot.id)} onChange={(e) => toggleSlot(slot, e.target.checked)} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-slate-900">{slot.experience_title}</span>
                        <span className="block text-xs text-slate-500">
                          {slot.local_date} · {timeFmt.format(new Date(slot.start_at))}–{timeFmt.format(new Date(slot.end_at))} · còn {slot.available_reported ?? 'chưa rõ'} chỗ
                        </span>
                      </span>
                      <StatusBadge status={slot.status} />
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="p-5">
            <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); void createPreview() }}>
              <Field label="Tin nhắn của cơ sở" required>
                <Textarea required minLength={2} maxLength={2000} rows={3} value={message} onChange={(e) => { setMessage(e.target.value); setPreview(null) }}
                  placeholder="Ví dụ: Ca 14 giờ hôm nay hủy giúp tôi; khách đã gọi báo máy hỏng." />
              </Field>
              <Button type="submit" loading={loading} disabled={loading || !providerId || !selectedIds.length || !message.trim()}>
                {loading ? 'Đang phân tích…' : 'Phân tích và xem trước'}
              </Button>
            </form>
          </Card>

          {preview && (
            <Card className="space-y-4 p-5">
              <div>
                <h2 className="text-base font-semibold text-slate-900">Xem trước: {preview.action_preview.action}</h2>
                <p className="mt-1 text-sm text-slate-500">{preview.action_preview.target_time_window} · {preview.action_preview.new_status} · Prompt {preview.prompt_version}</p>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <Badge tone="brand">Sức chứa được báo: {preview.action_preview.available_reported ?? 'không thay đổi'}</Badge>
                <Badge tone="gray">Lý do: {preview.action_preview.reason_note || 'không nêu'}</Badge>
                <Badge tone="amber">Token còn hiệu lực tối đa {Math.floor(preview.token_expires_in_seconds / 60)} phút</Badge>
              </div>
              <p className="text-sm text-slate-700"><strong>Tin nhắn xác nhận:</strong> {preview.action_preview.confirmation_sms_for_artisan_vi}</p>
              {preview.target_slots.length > 0 && (
                <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 text-sm">
                  {preview.target_slots.map((slot) => (
                    <li key={slot.slot_id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                      <span className="font-medium text-slate-800">{slot.experience_title}</span>
                      <span className="text-xs text-slate-500">
                        {dayFmt.format(new Date(slot.start_at))} {timeFmt.format(new Date(slot.start_at))}–{timeFmt.format(new Date(slot.end_at))} · hiện {slot.current_status} · còn {slot.current_available_reported ?? 'chưa rõ'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {needsExpiry && (
                <Field label="Thời điểm hết hạn xác nhận sức chứa" required hint="Nhập theo múi giờ máy; hạn phải trước giờ bắt đầu ca và còn trong tương lai.">
                  <Input type="datetime-local" required value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />
                </Field>
              )}
              <Button icon={ShieldCheck} loading={loading} disabled={loading} onClick={() => void confirm()}>Tôi xác nhận thay đổi này</Button>
            </Card>
          )}
        </div>
      )}
    </>
  )
}
