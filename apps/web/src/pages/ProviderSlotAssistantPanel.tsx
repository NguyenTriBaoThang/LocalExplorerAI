import { useMemo, useState } from 'react'
import { AlertCircle, CheckCircle2, MessageSquareText, ShieldCheck } from 'lucide-react'
import { apiErrorMessage, providerApi } from '../api/client'

type AssistantSlot = { id: string; start_at: string; end_at: string; available_reported: number | null; status: string; version: number }
type AssistantExperience = { id: string; title: string; poi_name: string; slots: AssistantSlot[] }
type SlotChoice = AssistantSlot & { experience_title: string; local_date: string }
type Preview = {
  action_preview: { action: string; target_time_window: string; new_status: string; available_reported: number | null; reason_note: string; confirmation_sms_for_artisan_vi: string }
  target_slots: Array<{ slot_id: string; experience_title: string; start_at: string; end_at: string; current_status: string; current_available_reported: number | null }>
  prompt_version: string
  confirmation_token: string
  token_expires_in_seconds: number
  requires_explicit_confirmation: boolean
}

function hcmDate(value: string) {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(value))
}

export function ProviderSlotAssistantPanel({ providerId, experiences, onConfirmed }: {
  providerId: string
  experiences: AssistantExperience[]
  onConfirmed: () => void
}) {
  const slots = useMemo(() => experiences.flatMap((experience) => experience.slots
    .filter((slot) => slot.status !== 'cancelled')
    .map((slot) => ({ ...slot, experience_title: experience.title, local_date: hcmDate(slot.start_at) }))), [experiences])
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [message, setMessage] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [expiresAt, setExpiresAt] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)
  const selected = slots.filter((slot) => selectedIds.includes(slot.id))
  const selectedDay = selected[0]?.local_date
  const todayHcm = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
  const todaySlots = slots.filter((slot) => slot.local_date === todayHcm)

  function toggleSlot(slot: SlotChoice, checked: boolean) {
    setError('')
    setNotice('')
    setPreview(null)
    if (checked && selectedDay && selectedDay !== slot.local_date) {
      setError('API chỉ cho xử lý một ngày mỗi lần. Hãy bỏ chọn các ca ngày khác trước.')
      return
    }
    setSelectedIds((current) => checked ? [...new Set([...current, slot.id])] : current.filter((id) => id !== slot.id))
  }

  async function createPreview() {
    setError('')
    setNotice('')
    setPreview(null)
    setLoading(true)
    try {
      const result = await providerApi.previewSlotAssistant(providerId, message.trim(), selectedIds) as Preview
      setPreview(result)
    } catch (reason) { setError(apiErrorMessage(reason)) }
    finally { setLoading(false) }
  }

  async function confirm() {
    if (!preview) return
    if (!window.confirm('Xác nhận áp dụng chính xác thay đổi trong bản xem trước?')) return
    setError('')
    setNotice('')
    setLoading(true)
    try {
      const expiry = preview.action_preview.action === 'UPDATE_CAPACITY' && preview.action_preview.new_status === 'open'
        ? new Date(expiresAt).toISOString()
        : undefined
      const result = await providerApi.confirmSlotAssistant(providerId, preview.confirmation_token, expiry) as { updated_slot_ids: string[]; action: string }
      setNotice(`Đã xác nhận ${result.action} cho ${result.updated_slot_ids.length} ca. Bản xem trước đã hết hiệu lực.`)
      setPreview(null)
      setMessage('')
      setSelectedIds([])
      onConfirmed()
    } catch (reason) { setError(apiErrorMessage(reason)) }
    finally { setLoading(false) }
  }

  return (
    <section className="admin-section-card" style={{ margin: '0 0 22px' }}>
      <div className="admin-section-header">
        <h2><MessageSquareText size={19} /> Trợ lý cập nhật ca</h2>
        <p>Chọn ca trong cùng một ngày, nhập tin nhắn của cơ sở, xem trước rồi xác nhận. AI không tự ghi thay đổi nếu bạn chưa bấm xác nhận.</p>
      </div>
      <div className="inline-alert-3d"><ShieldCheck size={16} /><span>Lệnh xác nhận có hiệu lực 5 phút và kiểm tra phiên bản ca để tránh ghi đè dữ liệu mới.</span></div>
      {notice && <div className="inline-alert-3d alert-success"><CheckCircle2 size={16} /><span>{notice}</span></div>}
      {error && <div className="inline-alert-3d" role="alert"><AlertCircle size={16} /><span>{error}</span></div>}

      <div className="item-action-btns" style={{ margin: '14px 0', flexWrap: 'wrap' }}>
        <button type="button" className="btn-secondary-3d btn-sm" disabled={!todaySlots.length} onClick={() => { setSelectedIds(todaySlots.map((slot) => slot.id)); setPreview(null); setError('') }}>
          Chọn toàn bộ ca hôm nay ({todaySlots.length}) cho lệnh tạm dừng ngày
        </button>
        <button type="button" className="btn-secondary-3d btn-sm" onClick={() => { setSelectedIds([]); setPreview(null) }}>Bỏ chọn tất cả</button>
      </div>

      <div className="portal-exp-list" style={{ maxHeight: 280, overflowY: 'auto', marginBottom: 16 }}>
        {slots.map((slot) => (
          <label className="portal-exp-card" key={slot.id} style={{ display: 'flex', gap: 12, alignItems: 'center', cursor: 'pointer' }}>
            <input type="checkbox" checked={selectedIds.includes(slot.id)} onChange={(event) => toggleSlot(slot, event.target.checked)} />
            <span><strong>{slot.experience_title}</strong><br /><small>{slot.local_date} · {new Intl.DateTimeFormat('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit' }).format(new Date(slot.start_at))}–{new Intl.DateTimeFormat('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit' }).format(new Date(slot.end_at))} · {slot.status} · còn {slot.available_reported ?? 'chưa rõ'} chỗ</small></span>
          </label>
        ))}
        {!slots.length && <p className="admin-empty-text">Chưa có ca để cập nhật.</p>}
      </div>

      <form onSubmit={(event) => { event.preventDefault(); void createPreview() }}>
        <label className="field-group-3d"><span>Tin nhắn của cơ sở</span><textarea required minLength={2} maxLength={2000} rows={3} value={message} onChange={(event) => { setMessage(event.target.value); setPreview(null) }} placeholder="Ví dụ: Ca 14 giờ hôm nay hủy giúp tôi; khách đã gọi báo máy hỏng." /></label>
        <div className="item-action-btns" style={{ marginTop: 14 }}>
          <button type="submit" className="btn-primary-3d" disabled={loading || !providerId || !selectedIds.length || !message.trim()}>{loading ? 'Đang phân tích…' : 'Phân tích và xem trước'}</button>
          <small>Đã chọn {selected.length} ca{selectedDay ? ` · ngày ${selectedDay}` : ''}.</small>
        </div>
      </form>

      {preview && (
        <div className="moderation-item-card" style={{ marginTop: 18 }}>
          <div className="admin-section-header"><h3>Xem trước: {preview.action_preview.action}</h3><p>{preview.action_preview.target_time_window} · {preview.action_preview.new_status} · Prompt {preview.prompt_version}</p></div>
          <div className="item-sub-meta"><span>Sức chứa được báo: {preview.action_preview.available_reported ?? 'không thay đổi'}</span><span>Lý do: {preview.action_preview.reason_note || 'không nêu'}</span><span>Token còn hiệu lực tối đa {Math.floor(preview.token_expires_in_seconds / 60)} phút</span></div>
          <p><strong>Tin nhắn xác nhận:</strong> {preview.action_preview.confirmation_sms_for_artisan_vi}</p>
          {preview.action_preview.action === 'UPDATE_CAPACITY' && preview.action_preview.new_status === 'open' && (
            <label className="field-group-3d"><span>Thời điểm hết hạn xác nhận sức chứa</span><input type="datetime-local" required value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} /><small>Nhập theo múi giờ máy; hạn phải trước giờ bắt đầu ca và còn trong tương lai.</small></label>
          )}
          <button type="button" className="btn-primary-3d" style={{ marginTop: 14 }} disabled={loading} onClick={() => void confirm()}><ShieldCheck size={15} /> Tôi xác nhận thay đổi này</button>
        </div>
      )}
    </section>
  )
}
