import { useEffect, useState, type FormEvent } from 'react'
import {
  Plus,
  Clock,
  Pencil,
  EyeOff,
  CheckCircle2,
  AlertCircle,
  History,
  X,
  MessageSquareText,
} from 'lucide-react'
import { getPOIs, providerApi } from '../api/client'
import type { Booking, POI } from '../types'
import { ProviderSlotAssistantPanel } from './ProviderSlotAssistantPanel'

type SlotItem = {
  id: string
  start_at: string
  end_at: string
  capacity_total: number
  available_reported: number | null
  confirmed_at: string | null
  expires_at: string | null
  status: string
  version: number
}

type ExperienceItem = {
  id: string
  poi_id: string
  title: string
  description: string
  primary_intent: string
  intent_tags: string[]
  is_hands_on: boolean
  is_indoor: boolean
  duration_min: number
  price_vnd: number
  price_basis: string
  verification_status: string
  poi_name: string
  slots: SlotItem[]
}

type Draft = Omit<ExperienceItem, 'id' | 'verification_status' | 'poi_name' | 'slots'>

function localDateTimeInput(offsetMs: number) {
  const date = new Date(Date.now() + offsetMs)
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset())
  return date.toISOString().slice(0, 16)
}

function slotConfirmationExpiry(slot: SlotItem) {
  const validForFourHours = Date.now() + 4 * 60 * 60 * 1000
  const beforeSlotStart = new Date(slot.start_at).getTime() - 60_000
  return new Date(Math.min(validForFourHours, beforeSlotStart)).toISOString()
}

const blank: Draft = {
  poi_id: '',
  title: '',
  description: '',
  primary_intent: 'thủ_công',
  intent_tags: [],
  is_hands_on: false,
  is_indoor: true,
  duration_min: 60,
  price_vnd: 0,
  price_basis: 'per_person',
}

export function ProviderPortalPage() {
  const [providerId, setProviderId] = useState('')
  const [items, setItems] = useState<ExperienceItem[]>([])
  const [bookings, setBookings] = useState<Booking[]>([])
  const [pois, setPois] = useState<POI[]>([])
  const [providerPois, setProviderPois] = useState<Array<POI & { data_revision: number }>>([])
  const [evidenceItems, setEvidenceItems] = useState<Array<{
    id: string; target_type: string; target_id: string; source_uri: string; source_type: string;
    source_label: string | null; fields_covered: string[]; observed_at: string | null;
    expires_at: string | null; verification_status: string; reviewed_at: string | null;
  }>>([])
  const [audit, setAudit] = useState<
    Array<{
      id: string
      action: string
      target_type: string
      target_id: string
      created_at: string
      details: Record<string, unknown>
    }>
  >([])
  const [draft, setDraft] = useState<Draft>(blank)
  const [editing, setEditing] = useState('')
  const [slotTarget, setSlotTarget] = useState('')
  const [slotDate, setSlotDate] = useState(
    new Date(Date.now() + 86400000).toISOString().slice(0, 10)
  )
  const [slotTime, setSlotTime] = useState('09:00')
  const [slotDuration, setSlotDuration] = useState(60)
  const [capacity, setCapacity] = useState(10)
  const [available, setAvailable] = useState(10)
  const [slotExpiresAt, setSlotExpiresAt] = useState(localDateTimeInput(4 * 60 * 60 * 1000))
  const [sourceUrl, setSourceUrl] = useState('')
  const [sourceType, setSourceType] = useState('official_website')
  const [sourceObservedAt, setSourceObservedAt] = useState(localDateTimeInput(0))
  const [sourceExpiresAt, setSourceExpiresAt] = useState(localDateTimeInput(30 * 24 * 60 * 60 * 1000))
  const [sourceLicense, setSourceLicense] = useState('')
  const [sourceLabel, setSourceLabel] = useState('')
  const [sourceConfirmsPoi, setSourceConfirmsPoi] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [showExpForm, setShowExpForm] = useState(false)
  const [showPoiForm, setShowPoiForm] = useState(false)
  const [showSlotAssistant, setShowSlotAssistant] = useState(false)
  const [editingPoi, setEditingPoi] = useState('')
  const [poiDraft, setPoiDraft] = useState({
    name: '', description: '', district: '', latitude: '', longitude: '', category: '', address: '',
  })
  const poiOptions = Array.from([
    ...pois,
    ...providerPois.map((point) => ({
      ...point,
      data_mode: point.verification_status === 'verified' ? 'real' as const : 'simulated' as const,
    })),
  ].reduce((options, point) => options.set(point.id, point), new Map<string, POI>()).values())

  async function load() {
    try {
      const [experiences, points, history, ownedPoints, sources, reservationRows, profile] = await Promise.all([
        providerApi.experiences(),
        getPOIs(),
        providerApi.audit(),
        providerApi.pois(),
        providerApi.evidence(),
        providerApi.bookings(),
        providerApi.profile(),
      ])
      setProviderId(profile.id)
      setItems(experiences)
      setPois(points)
      setAudit(history)
      setProviderPois(ownedPoints)
      setEvidenceItems(sources)
      setBookings(reservationRows)
      setError('')
      const verifiedPointId = points.find((point) => point.data_mode === 'real')?.id
        || ownedPoints.find((point) => point.verification_status === 'verified')?.id
      setDraft((current) => current.poi_id || !verifiedPointId ? current : { ...current, poi_id: verifiedPointId })
    } catch {
      setError('Không tải được dữ liệu cơ sở. Hãy đăng nhập bằng tài khoản có quyền cơ sở.')
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function decideBooking(id: string, action: 'accept' | 'reject') {
    setError('')
    setNotice('')
    try {
      const updated = await providerApi.decideBooking(id, action)
      setNotice(action === 'accept'
        ? (updated.amount_vnd === 0
          ? 'Đã xác nhận đặt chỗ miễn phí.'
          : 'Đã xác nhận năng lực phục vụ và giữ chỗ tạm thời. Khách chưa thanh toán; cổng thanh toán của dự án chưa được cấu hình.')
        : 'Đã từ chối yêu cầu và giải phóng chỗ giữ tạm thời.')
      await load()
    } catch {
      setError('Không thể cập nhật yêu cầu đặt chỗ. Hãy kiểm tra hạn giữ chỗ và xác nhận lại sức chứa của ca.')
    }
  }

  async function decideBookingCancellation(id: string, action: 'approve' | 'reject') {
    setError('')
    setNotice('')
    try {
      const updated = await providerApi.decideBookingCancellation(id, action)
      setNotice(updated.status === 'cancelled'
        ? 'Đã xác nhận hủy đặt chỗ chưa thanh toán.'
        : 'Đã từ chối yêu cầu hủy; đặt chỗ vẫn giữ trạng thái xác nhận.')
      await load()
    } catch {
      setError('Chưa xử lý được yêu cầu. Nếu booking đã thanh toán, dự án cần tích hợp cổng thanh toán để thực hiện hoàn tiền thật; không đánh dấu hoàn khi chưa có kết quả từ cổng.')
    }
  }

  function beginEdit(item: ExperienceItem) {
    setEditing(item.id)
    setSlotTarget('')
    setDraft({
      poi_id: item.poi_id,
      title: item.title,
      description: item.description,
      primary_intent: item.primary_intent || 'thủ_công',
      intent_tags: item.intent_tags || [],
      is_hands_on: item.is_hands_on,
      is_indoor: item.is_indoor,
      duration_min: item.duration_min,
      price_vnd: item.price_vnd,
      price_basis: item.price_basis,
    })
    setShowExpForm(true)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function saveExperience(event: FormEvent) {
    event.preventDefault()
    setError('')
    setNotice('')
    try {
      if (!sourceUrl.trim()) {
        setError('Cần nhập URL nguồn để gửi dữ liệu trải nghiệm cho quản trị viên xác minh.')
        return
      }
      let experienceId = editing
      if (editing) {
        await providerApi.updateExperience(editing, draft as unknown as Record<string, unknown>)
      } else {
        const created = (await providerApi.createExperience(draft as unknown as Record<string, unknown>)) as { id: string }
        experienceId = created.id
      }
      const evidenceBase = {
        source_uri: sourceUrl.trim(),
        source_type: sourceType,
        source_label: sourceLabel || null,
        license: sourceLicense || null,
        observed_at: new Date(sourceObservedAt).toISOString(),
        expires_at: new Date(sourceExpiresAt).toISOString(),
      }
      await providerApi.submitEvidence({
        ...evidenceBase,
        target_type: 'experience',
        target_id: experienceId,
        fields_covered: ['title', 'description', 'primary_intent', 'intent_tags', 'is_hands_on', 'duration_min', 'price_vnd', 'price_basis'],
        notes: 'Cơ sở khai báo nguồn chứng minh các trường trải nghiệm đã chọn.',
      })
      if (sourceConfirmsPoi && draft.poi_id) {
        await providerApi.submitEvidence({
          ...evidenceBase,
          target_type: 'poi',
          target_id: draft.poi_id,
          fields_covered: ['name', 'address', 'latitude', 'longitude', 'category'],
          notes: 'Cơ sở xác nhận nguồn này cũng chứng minh địa chỉ, tọa độ và loại POI.',
        })
      }
      setDraft({ ...blank, poi_id: poiOptions.find((point) => point.data_mode === 'real')?.id || '' })
      setEditing('')
      setShowExpForm(false)
      setSourceUrl('')
      setSourceObservedAt(localDateTimeInput(0))
      setSourceExpiresAt(localDateTimeInput(30 * 24 * 60 * 60 * 1000))
      setSourceConfirmsPoi(false)
      setNotice('Đã lưu thành công. Nội dung mới hoặc chỉnh sửa sẽ chờ quản trị viên duyệt.')
      await load()
    } catch {
      setError('Lưu trải nghiệm thất bại. Vui lòng kiểm tra lại POI, thời lượng và giá.')
    }
  }

  async function addSlot(event: FormEvent) {
    event.preventDefault()
    setError('')
    setNotice('')
    try {
      const start = new Date(`${slotDate}T${slotTime}:00+07:00`)
      await providerApi.createSlot(slotTarget, {
        start_at: start.toISOString(),
        end_at: new Date(start.getTime() + slotDuration * 60000).toISOString(),
        capacity_total: capacity,
        available_reported: available,
        expires_at: new Date(slotExpiresAt).toISOString(),
      })
      setNotice('Đã thêm ca kèm thời điểm xác nhận và hạn xác nhận. Ca hết hạn sẽ không còn được coi là chỗ trống đã xác nhận.')
      setSlotTarget('')
      await load()
    } catch {
      setError('Không thể tạo slot; cần thời gian có múi giờ và sức chứa hợp lệ.')
    }
  }

  async function updateSlot(slot: SlotItem, status: string) {
    if (
      status === 'cancelled' &&
      !window.confirm(
        'Hủy ca này? Du khách có lịch liên quan sẽ nhận cảnh báo và có thể đổi lịch.'
      )
    ) {
      return
    }
    try {
      const reported =
        status === 'cancelled' || status === 'full'
          ? 0
          : slot.available_reported && slot.available_reported > 0
          ? slot.available_reported
          : slot.capacity_total
      const result = (await providerApi.updateSlot(slot.id, {
        expected_version: slot.version,
        status,
        available_reported: reported,
        ...(status === 'open' ? { expires_at: slotConfirmationExpiry(slot) } : {}),
      })) as { affected_itineraries?: number }
      setNotice(
        status === 'cancelled'
          ? `Đã hủy ca; ${result.affected_itineraries || 0} lịch trình bị ảnh hưởng và sẽ nhận cảnh báo đổi lịch.`
          : 'Đã cập nhật tình trạng ca thành công.'
      )
      await load()
    } catch {
      setError('Ca đã được cập nhật ở nơi khác hoặc không còn khả dụng. Hãy tải lại trang.')
    }
  }

  async function editCapacity(slot: SlotItem) {
    const totalValue = window.prompt('Tổng sức chứa của ca', String(slot.capacity_total || 1))
    if (totalValue === null) return
    const total = Number(totalValue)
    const reportValue = window.prompt('Số chỗ còn nhận', String(slot.available_reported ?? total))
    if (reportValue === null) return
    const reported = Number(reportValue)
    try {
      await providerApi.updateSlot(slot.id, {
        expected_version: slot.version,
        status: reported === 0 ? 'full' : 'open',
        capacity_total: total,
        available_reported: reported,
        expires_at: slotConfirmationExpiry(slot),
      })
      setNotice('Đã cập nhật sức chứa ca.')
      await load()
    } catch {
      setError('Sức chứa không hợp lệ hoặc ca đã đổi phiên bản.')
    }
  }

  async function hideExperience(id: string) {
    if (!window.confirm('Ẩn trải nghiệm này khỏi danh mục công khai? Lịch sử cũ được giữ nguyên.'))
      return
    try {
      await providerApi.hideExperience(id)
      setNotice('Đã ẩn trải nghiệm khỏi danh mục công khai.')
      await load()
    } catch {
      setError('Không thể ẩn trải nghiệm.')
    }
  }

  async function savePoi(event: FormEvent) {
    event.preventDefault()
    setError('')
    setNotice('')
    try {
      if (!sourceUrl.trim()) {
        setError('Cần nhập URL nguồn có thể xác minh cho địa chỉ và loại POI.')
        return
      }
      const payload = {
        ...poiDraft,
        latitude: Number(poiDraft.latitude),
        longitude: Number(poiDraft.longitude),
      }
      const created = editingPoi
        ? ((await providerApi.updatePOI(editingPoi, payload)) as { id: string })
        : ((await providerApi.createPOI(payload)) as { id: string })
      const targetPoiId = editingPoi || created.id
      await providerApi.submitEvidence({
        target_type: 'poi',
        target_id: targetPoiId,
        source_uri: sourceUrl.trim(),
        source_type: sourceType,
        source_label: sourceLabel || null,
        license: sourceLicense || null,
        fields_covered: ['name', 'address', 'latitude', 'longitude', 'category'],
        observed_at: new Date(sourceObservedAt).toISOString(),
        expires_at: new Date(sourceExpiresAt).toISOString(),
        notes: 'Cơ sở khai báo nguồn cho địa chỉ, tọa độ và loại POI.',
      })
      setPoiDraft({ name: '', description: '', district: '', latitude: '', longitude: '', category: '', address: '' })
      setDraft((current) => ({ ...current, poi_id: targetPoiId }))
      setEditingPoi('')
      setSourceUrl('')
      setSourceObservedAt(localDateTimeInput(0))
      setSourceExpiresAt(localDateTimeInput(30 * 24 * 60 * 60 * 1000))
      setShowPoiForm(false)
      setNotice('Đã gửi POI và nguồn bằng chứng vào hàng chờ quản trị viên xác minh.')
      await load()
    } catch {
      setError('Không thể lưu POI hoặc bằng chứng. Kiểm tra tọa độ, URL nguồn và hạn dùng.')
    }
  }

  return (
    <div className="portal-page-3d page-wrap">
      {/* Header */}
      <div className="page-title-row-3d">
        <div>
          <span className="eyebrow-3d">
            <span className="eyebrow-dot" /> WORKSPACE CƠ SỞ ĐỐI TÁC
          </span>
          <h1 className="page-heading-3d">
            Quản lý hoạt động & <em>Khung giờ.</em>
          </h1>
          <p className="page-subtext-3d">
            Cập nhật trạng thái slot, thông báo sức chứa chỗ trống và quản lý danh mục trải nghiệm của cơ sở.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button type="button" className="btn-secondary-3d" onClick={() => setShowSlotAssistant((open) => !open)}>
            {showSlotAssistant ? <X size={16} /> : <MessageSquareText size={16} />}
            <span>{showSlotAssistant ? 'Đóng trợ lý' : 'Trợ lý cập nhật ca'}</span>
          </button>
          <button
            type="button"
            className="btn-secondary-3d"
            onClick={() => {
              setShowExpForm(false)
              setEditingPoi('')
              setShowPoiForm(!showPoiForm)
              setSourceUrl('')
            }}
          >
            {showPoiForm ? <X size={16} /> : <Plus size={16} />}
            <span>{showPoiForm ? 'Đóng POI' : 'Thêm POI thật'}</span>
          </button>
          <button
            type="button"
            className="btn-primary-3d"
            onClick={() => {
              setEditing('')
              setDraft({ ...blank, poi_id: poiOptions.find((point) => point.data_mode === 'real')?.id || '' })
              setShowPoiForm(false)
              setShowExpForm(!showExpForm)
              setSourceUrl('')
            }}
          >
            {showExpForm ? <X size={16} /> : <Plus size={16} />}
            <span>{showExpForm ? 'Đóng form' : 'Thêm trải nghiệm mới'}</span>
          </button>
        </div>
      </div>

      {notice && (
        <div className="inline-alert-3d alert-success">
          <CheckCircle2 size={16} className="text-emerald" />
          <span>{notice}</span>
        </div>
      )}

      {error && (
        <div className="inline-alert-3d">
          <AlertCircle size={16} className="text-amber" />
          <span>{error}</span>
        </div>
      )}

      {showSlotAssistant && (
        <ProviderSlotAssistantPanel
          providerId={providerId}
          experiences={items}
          onConfirmed={() => { void load() }}
        />
      )}

      <section className="portal-experiences-section booking-provider-section">
        <h2 className="section-title-3d">Yêu cầu đặt chỗ ({bookings.filter((row) => row.status === 'pending_provider').length} đang chờ)</h2>
        <p className="page-subtext-3d">Chỉ chấp nhận sau khi kiểm tra lại số chỗ. Yêu cầu có thời hạn; khách chỉ được thông báo đã đặt thành công sau khi thanh toán hoặc khi ca miễn phí được cơ sở xác nhận.</p>
        {bookings.length ? (
          <div className="portal-exp-list">
            {bookings.map((booking) => (
              <article key={booking.id} className="portal-exp-card booking-provider-card">
                <div className="portal-exp-top">
                  <div className="portal-exp-meta-left">
                    <span className="portal-status-badge">{booking.status}</span>
                    <h3>{booking.experience_title}</h3>
                    <p className="portal-exp-poi">
                      {booking.quantity} khách · {booking.amount_vnd.toLocaleString('vi-VN')}₫ · {booking.slot_start_at ? new Date(booking.slot_start_at).toLocaleString('vi-VN') : 'Không rõ giờ'}
                    </p>
                    {booking.hold_expires_at && <small>Hạn giữ chỗ: {new Date(booking.hold_expires_at).toLocaleString('vi-VN')}</small>}
                    {booking.status === 'awaiting_payment' && <small>Đã xác nhận sức chứa; chưa có thanh toán và chưa phải đơn hoàn tất.</small>}
                    {booking.status === 'cancellation_requested' && <small>Khách yêu cầu hủy. Nếu giao dịch đã thu tiền, cần cổng thanh toán để hoàn tiền.</small>}
                    {booking.status === 'refund_pending' && <small>Hoàn tiền đang chờ xử lý bởi cổng thanh toán.</small>}
                  </div>
                  {booking.status === 'pending_provider' && (
                    <div className="portal-exp-actions">
                      <button type="button" className="btn-primary-3d btn-sm" onClick={() => void decideBooking(booking.id, 'accept')}>Xác nhận chỗ</button>
                      <button type="button" className="btn-secondary-3d btn-sm" onClick={() => void decideBooking(booking.id, 'reject')}>Từ chối</button>
                    </div>
                  )}
                  {booking.status === 'cancellation_requested' && (
                    <div className="portal-exp-actions">
                      <button type="button" className="btn-primary-3d btn-sm" onClick={() => void decideBookingCancellation(booking.id, 'approve')}>
                        {booking.amount_vnd > 0 ? 'Duyệt hủy / xử lý hoàn' : 'Duyệt hủy'}
                      </button>
                      {booking.slot_status !== 'cancelled' && (
                        <button type="button" className="btn-secondary-3d btn-sm" onClick={() => void decideBookingCancellation(booking.id, 'reject')}>Từ chối hủy</button>
                      )}
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="no-slots-hint">Chưa có yêu cầu đặt chỗ nào.</p>
        )}
      </section>

      {showPoiForm && (
        <section className="form-card-3d mb-8 animate-fadeIn">
          <div className="form-card-header">
            <span className="step-num">POI</span>
            <div>
              <h2>{editingPoi ? 'Cập nhật POI thực' : 'Đăng ký địa điểm thực'}</h2>
              <p>POI mới ở trạng thái chờ duyệt; cần nguồn bao phủ địa chỉ, tọa độ và loại địa điểm.</p>
            </div>
          </div>
          <form onSubmit={savePoi} className="form-fields-grid-2">
            <label className="field-group-3d"><span>Tên địa điểm</span><input required minLength={2} value={poiDraft.name} onChange={(e) => setPoiDraft({ ...poiDraft, name: e.target.value })} /></label>
            <label className="field-group-3d"><span>Loại hoạt động / danh mục</span><input required value={poiDraft.category} onChange={(e) => setPoiDraft({ ...poiDraft, category: e.target.value })} placeholder="handicraft, food, culture..." /></label>
            <label className="field-group-3d" style={{ gridColumn: '1 / -1' }}><span>Địa chỉ đã xác minh tại thực địa</span><input required minLength={5} value={poiDraft.address} onChange={(e) => setPoiDraft({ ...poiDraft, address: e.target.value })} /></label>
            <label className="field-group-3d"><span>Vĩ độ</span><input type="number" required step="any" min={-90} max={90} value={poiDraft.latitude} onChange={(e) => setPoiDraft({ ...poiDraft, latitude: e.target.value })} /></label>
            <label className="field-group-3d"><span>Kinh độ</span><input type="number" required step="any" min={-180} max={180} value={poiDraft.longitude} onChange={(e) => setPoiDraft({ ...poiDraft, longitude: e.target.value })} /></label>
            <label className="field-group-3d"><span>Quận / khu vực</span><input value={poiDraft.district} onChange={(e) => setPoiDraft({ ...poiDraft, district: e.target.value })} /></label>
            <label className="field-group-3d"><span>Mô tả</span><input value={poiDraft.description} onChange={(e) => setPoiDraft({ ...poiDraft, description: e.target.value })} /></label>
            <label className="field-group-3d" style={{ gridColumn: '1 / -1' }}><span>URL nguồn địa chỉ / thông tin chính thức</span><input type="url" required value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="https://..." /></label>
            <label className="field-group-3d"><span>Loại nguồn</span><select value={sourceType} onChange={(e) => setSourceType(e.target.value)}><option value="official_website">Website chính thức</option><option value="provider_confirmation">Xác nhận trực tiếp của cơ sở</option><option value="field_visit">Khảo sát thực địa</option><option value="document">Tài liệu</option><option value="government_dataset">Dữ liệu cơ quan nhà nước</option><option value="other">Khác</option></select></label>
            <label className="field-group-3d"><span>Thời điểm kiểm tra</span><input type="datetime-local" required value={sourceObservedAt} onChange={(e) => setSourceObservedAt(e.target.value)} /></label>
            <label className="field-group-3d"><span>Hạn dùng bằng chứng</span><input type="datetime-local" required value={sourceExpiresAt} onChange={(e) => setSourceExpiresAt(e.target.value)} /></label>
            <label className="field-group-3d"><span>Tên nguồn</span><input value={sourceLabel} onChange={(e) => setSourceLabel(e.target.value)} /></label>
            <label className="field-group-3d"><span>Giấy phép / điều khoản nguồn</span><input value={sourceLicense} onChange={(e) => setSourceLicense(e.target.value)} /></label>
            <div className="form-action-row" style={{ gridColumn: '1 / -1' }}>
              <button className="btn-primary-3d" type="submit"><span>{editingPoi ? 'Lưu POI và gửi bằng chứng mới' : 'Gửi POI và bằng chứng'}</span></button>
            </div>
          </form>
        </section>
      )}

      <section className="portal-experiences-section">
        <h2 className="section-title-3d">POI do cơ sở quản lý ({providerPois.length})</h2>
        <div className="portal-exp-list">
          {providerPois.map((poi) => (
            <article key={poi.id} className="portal-exp-card">
              <div className="portal-exp-top">
                <div className="portal-exp-meta-left">
                  <span className="portal-status-badge">{poi.verification_status}</span>
                  <h3>{poi.name}</h3>
                  <p className="portal-exp-poi">{poi.address} · {poi.latitude.toFixed(5)}, {poi.longitude.toFixed(5)} · {poi.category}</p>
                </div>
                <button
                  type="button"
                  className="btn-secondary-3d btn-sm"
                  onClick={() => {
                    setEditingPoi(poi.id)
                    setPoiDraft({
                      name: poi.name, description: poi.description || '', district: poi.district || '',
                      latitude: String(poi.latitude), longitude: String(poi.longitude),
                      category: poi.category, address: poi.address,
                    })
                    setSourceUrl('')
                    setShowExpForm(false)
                    setShowPoiForm(true)
                    window.scrollTo({ top: 0, behavior: 'smooth' })
                  }}
                >
                  <Pencil size={13} /> Sửa POI
                </button>
              </div>
            </article>
          ))}
          {providerPois.length === 0 && <p className="admin-empty-text">Chưa có POI do cơ sở quản lý.</p>}
        </div>
      </section>

      <section className="portal-experiences-section">
        <h2 className="section-title-3d">Nguồn và bằng chứng ({evidenceItems.length})</h2>
        <div className="portal-exp-list">
          {evidenceItems.map((source) => (
            <article key={source.id} className="portal-exp-card">
              <div className="portal-exp-top">
                <div className="portal-exp-meta-left">
                  <span className="portal-status-badge">{source.verification_status}</span>
                  <h3>{source.source_label || source.source_type} · {source.target_type}</h3>
                  <p className="portal-exp-poi">
                    {source.fields_covered.join(', ')} · quan sát: {source.observed_at ? new Date(source.observed_at).toLocaleString('vi-VN') : '—'}
                    {' · '}hết hạn: {source.expires_at ? new Date(source.expires_at).toLocaleString('vi-VN') : '—'}
                  </p>
                  {source.source_uri.startsWith('http')
                    ? <a href={source.source_uri} target="_blank" rel="noreferrer">{source.source_uri}</a>
                    : <span>{source.source_uri} (xác nhận nội bộ)</span>}
                </div>
              </div>
            </article>
          ))}
          {evidenceItems.length === 0 && <p className="admin-empty-text">Chưa gửi bằng chứng nguồn nào.</p>}
        </div>
      </section>

      {/* Experience Editor Form Card (Collapsible) */}
      {showExpForm && (
        <section className="form-card-3d mb-8 animate-fadeIn">
          <div className="form-card-header">
            <span className="step-num">{editing ? 'EDIT' : 'NEW'}</span>
            <div>
              <h2>{editing ? 'Chỉnh sửa thông tin trải nghiệm' : 'Đăng ký trải nghiệm mới'}</h2>
              <p>Thông tin chi tiết về hoạt động, địa điểm và thời lượng tổ chức.</p>
            </div>
          </div>

          <form onSubmit={saveExperience} className="form-fields-grid-2">
            <label className="field-group-3d">
              <span>Địa điểm tổ chức (POI)</span>
              <select
                required
                value={draft.poi_id}
                onChange={(e) => setDraft({ ...draft, poi_id: e.target.value })}
              >
                <option value="" disabled>Chọn POI đã xác minh trước khi đăng trải nghiệm</option>
                {poiOptions.map((p) => (
                  <option key={p.id} value={p.id} disabled={p.data_mode !== 'real'}>
                    {p.name} — {p.address}{p.data_mode !== 'real' ? ' · DỮ LIỆU MÔ PHỎNG / CHƯA XÁC MINH' : ''}
                  </option>
                ))}
              </select>
            </label>

            <label className="field-group-3d">
              <span>Tên trải nghiệm</span>
              <input
                required
                minLength={2}
                value={draft.title}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                placeholder="Ví dụ: Workshop nặn gốm thủ công..."
              />
            </label>

            <label className="field-group-3d" style={{ gridColumn: '1 / -1' }}>
              <span>Mô tả chi tiết</span>
              <textarea
                required
                rows={3}
                value={draft.description}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                placeholder="Mô tả nội dung diễn ra trong hoạt động..."
              />
            </label>

            <label className="field-group-3d">
              <span>Loại trải nghiệm chính</span>
              <select value={draft.primary_intent} onChange={(e) => setDraft({ ...draft, primary_intent: e.target.value })}>
                <option value="thủ_công">Thủ công</option>
                <option value="ẩm_thực">Ẩm thực</option>
                <option value="văn_hóa">Văn hóa</option>
                <option value="thư_giãn">Thư giãn</option>
              </select>
            </label>

            <label className="field-group-3d">
              <span>Thẻ mục đích (cách nhau bằng dấu phẩy)</span>
              <input
                value={draft.intent_tags.join(', ')}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    intent_tags: e.target.value
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
                placeholder="food, handicraft, relaxation..."
              />
            </label>

            <label className="field-group-3d">
              <span>Thời lượng (phút)</span>
              <input
                required
                type="number"
                min={10}
                value={draft.duration_min}
                onChange={(e) => setDraft({ ...draft, duration_min: Number(e.target.value) })}
              />
            </label>

            <label className="field-group-3d">
              <span>Giá vé dự kiến (VNĐ)</span>
              <input
                required
                type="number"
                min={0}
                step={10000}
                value={draft.price_vnd}
                onChange={(e) => setDraft({ ...draft, price_vnd: Number(e.target.value) })}
              />
            </label>

            <label className="field-group-3d">
              <span>Cách tính giá</span>
              <select
                value={draft.price_basis}
                onChange={(e) => setDraft({ ...draft, price_basis: e.target.value })}
              >
                <option value="per_person">Tính theo từng khách</option>
                <option value="per_group">Tính theo nhóm trọn gói</option>
              </select>
            </label>

            <div className="checkboxes-pair" style={{ gridColumn: '1 / -1' }}>
              <label className="custom-check-pill">
                <input
                  type="checkbox"
                  checked={draft.is_hands_on}
                  onChange={(e) => setDraft({ ...draft, is_hands_on: e.target.checked })}
                />
                <span>Có thực hành trực tiếp (Hands-on)</span>
              </label>

              <label className="custom-check-pill">
                <input
                  type="checkbox"
                  checked={draft.is_indoor}
                  onChange={(e) => setDraft({ ...draft, is_indoor: e.target.checked })}
                />
                <span>Không gian trong nhà</span>
              </label>
            </div>

            <div className="form-card-header" style={{ gridColumn: '1 / -1', marginTop: 12 }}>
              <div>
                <h3>Nguồn và thời hạn xác minh</h3>
                <p>Bằng chứng được gắn với phiên bản dữ liệu hiện tại; sửa nội dung sẽ yêu cầu gửi bằng chứng mới.</p>
              </div>
            </div>
            <label className="field-group-3d" style={{ gridColumn: '1 / -1' }}>
              <span>URL nguồn chứng minh giá, thời lượng, loại hoạt động và hands-on</span>
              <input type="url" required value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="https://..." />
            </label>
            <label className="field-group-3d">
              <span>Loại nguồn</span>
              <select value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
                <option value="official_website">Website chính thức</option>
                <option value="provider_confirmation">Xác nhận trực tiếp của cơ sở</option>
                <option value="field_visit">Khảo sát thực địa</option>
                <option value="document">Tài liệu</option>
                <option value="government_dataset">Dữ liệu cơ quan nhà nước</option>
                <option value="other">Khác</option>
              </select>
            </label>
            <label className="field-group-3d">
              <span>Tên nguồn / đơn vị xuất bản</span>
              <input value={sourceLabel} onChange={(e) => setSourceLabel(e.target.value)} placeholder="Trang chính thức của cơ sở" />
            </label>
            <label className="field-group-3d">
              <span>Giấy phép / điều khoản sử dụng nguồn</span>
              <input value={sourceLicense} onChange={(e) => setSourceLicense(e.target.value)} placeholder="Ví dụ: nội dung do cơ sở cung cấp" />
            </label>
            <label className="field-group-3d">
              <span>Thời điểm kiểm tra nguồn</span>
              <input type="datetime-local" required value={sourceObservedAt} onChange={(e) => setSourceObservedAt(e.target.value)} />
            </label>
            <label className="field-group-3d">
              <span>Hạn dùng bằng chứng</span>
              <input type="datetime-local" required value={sourceExpiresAt} onChange={(e) => setSourceExpiresAt(e.target.value)} />
            </label>
            <label className="custom-check-pill" style={{ gridColumn: '1 / -1' }}>
              <input type="checkbox" checked={sourceConfirmsPoi} onChange={(e) => setSourceConfirmsPoi(e.target.checked)} />
              <span>Nguồn này cũng xác minh tên, địa chỉ, tọa độ và loại POI đã chọn</span>
            </label>

            <div className="form-action-row" style={{ gridColumn: '1 / -1' }}>
              <button className="btn-primary-3d" type="submit">
                <span>{editing ? 'Lưu chỉnh sửa' : 'Tạo trải nghiệm'}</span>
              </button>
              <button
                type="button"
                className="btn-secondary-3d"
                onClick={() => {
                  setEditing('')
                  setShowExpForm(false)
                }}
              >
                Hủy bỏ
              </button>
            </div>
          </form>
        </section>
      )}

      {/* Add Slot Modal / Drawer Card */}
      {slotTarget && (
        <section className="form-card-3d mb-8 animate-fadeIn">
          <div className="form-card-header">
            <span className="step-num">SLOT</span>
            <div>
              <h2>Thêm khung giờ (Slot) cho trải nghiệm</h2>
              <p>Khung giờ này sẽ xuất hiện trên hệ thống tìm kiếm và planner.</p>
            </div>
            <button
              type="button"
              className="btn-ghost-sm"
              onClick={() => setSlotTarget('')}
              aria-label="Đóng"
            >
              <X size={16} />
            </button>
          </div>

          <form className="form-fields-grid-3" onSubmit={addSlot}>
            <label className="field-group-3d">
              <span>Ngày tổ chức</span>
              <input
                type="date"
                required
                value={slotDate}
                onChange={(e) => setSlotDate(e.target.value)}
              />
            </label>

            <label className="field-group-3d">
              <span>Giờ bắt đầu</span>
              <input
                type="time"
                required
                value={slotTime}
                onChange={(e) => setSlotTime(e.target.value)}
              />
            </label>

            <label className="field-group-3d">
              <span>Thời lượng (phút)</span>
              <input
                type="number"
                min={10}
                value={slotDuration}
                onChange={(e) => setSlotDuration(Number(e.target.value))}
              />
            </label>

            <label className="field-group-3d">
              <span>Tổng sức chứa</span>
              <input
                type="number"
                min={1}
                value={capacity}
                onChange={(e) => setCapacity(Number(e.target.value))}
              />
            </label>

            <label className="field-group-3d">
              <span>Số chỗ nhận thực tế</span>
              <input
                type="number"
                min={0}
                value={available}
                onChange={(e) => setAvailable(Number(e.target.value))}
              />
            </label>

            <label className="field-group-3d">
              <span>Ca đã được cơ sở xác nhận đến</span>
              <input
                type="datetime-local"
                required
                value={slotExpiresAt}
                onChange={(e) => setSlotExpiresAt(e.target.value)}
              />
            </label>

            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button className="btn-primary-3d w-full" type="submit">
                <span>Tạo ca hoạt động</span>
              </button>
            </div>
          </form>
        </section>
      )}

      {/* Experience List Cards */}
      <section className="portal-experiences-section">
        <h2 className="section-title-3d">Danh sách trải nghiệm & Khung giờ ({items.length})</h2>

        <div className="portal-exp-list">
          {items.map((item) => (
            <article key={item.id} className="portal-exp-card">
              <div className="portal-exp-top">
                <div className="portal-exp-meta-left">
                  <span className="portal-status-badge">{item.verification_status}</span>
                  <h3>{item.title}</h3>
                  <p className="portal-exp-poi">
                    {item.poi_name} · {item.price_vnd.toLocaleString('vi-VN')}₫ · {item.duration_min} phút
                  </p>
                </div>

                <div className="portal-exp-actions">
                  <button
                    type="button"
                    className="btn-secondary-3d btn-sm"
                    onClick={() => beginEdit(item)}
                  >
                    <Pencil size={13} /> Sửa
                  </button>
                  <button
                    type="button"
                    className="btn-primary-3d btn-sm"
                    onClick={() => {
                      setSlotTarget(item.id)
                      setSlotExpiresAt(localDateTimeInput(4 * 60 * 60 * 1000))
                      window.scrollTo({ top: 200, behavior: 'smooth' })
                    }}
                  >
                    <Plus size={13} /> Thêm ca
                  </button>
                  <button
                    type="button"
                    className="btn-ghost-sm text-rose"
                    onClick={() => void hideExperience(item.id)}
                  >
                    <EyeOff size={13} /> Ẩn
                  </button>
                </div>
              </div>

              {/* Slots List for this experience */}
              <div className="portal-slots-container">
                <span className="slots-heading-label">
                  Khung giờ mở ({item.slots.length} ca):
                </span>
                {item.slots.length > 0 ? (
                  <div className="slots-grid">
                    {item.slots.map((slot) => (
                      <div key={slot.id} className="slot-chip-card">
                        <div className="slot-chip-time">
                          <Clock size={13} className="text-emerald" />
                          <span>
                            {new Date(slot.start_at).toLocaleString('vi-VN', {
                              dateStyle: 'short',
                              timeStyle: 'short',
                              timeZone: 'Asia/Ho_Chi_Minh',
                            })}
                          </span>
                        </div>

                        <div className="slot-chip-info">
                          <span>
                            Còn <strong>{slot.available_reported ?? 'Chưa rõ'}</strong> / {slot.capacity_total} chỗ
                          </span>
                          <small>
                            Xác nhận: {slot.confirmed_at ? new Date(slot.confirmed_at).toLocaleString('vi-VN') : 'chưa có'}
                            {' · '}hết hạn: {slot.expires_at ? new Date(slot.expires_at).toLocaleString('vi-VN') : 'chưa có'}
                          </small>
                        </div>

                        <div className="slot-chip-controls">
                          <select
                            aria-label="Trạng thái slot"
                            value={
                              slot.status === 'open' ||
                              slot.status === 'full' ||
                              slot.status === 'cancelled'
                                ? slot.status
                                : 'open'
                            }
                            onChange={(e) => void updateSlot(slot, e.target.value)}
                            className="slot-status-select"
                          >
                            <option value="open">Mở nhận khách</option>
                            <option value="full">Đã đầy chỗ</option>
                            <option value="cancelled">Hủy ca này</option>
                          </select>
                          <button
                            type="button"
                            className="btn-slot-cap"
                            onClick={() => void editCapacity(slot)}
                            title="Chỉnh sửa sức chứa"
                          >
                            Sửa chỗ
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="no-slots-hint">Chưa có khung giờ nào được lên lịch.</p>
                )}
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Audit History Log */}
      {audit.length > 0 && (
        <section className="portal-audit-section">
          <div className="audit-header-row">
            <History size={18} className="text-emerald" />
            <h3>Nhật ký thao tác gần đây</h3>
          </div>
          <div className="audit-rows-list">
            {audit.map((row) => (
              <div key={row.id} className="audit-log-item">
                <span className="audit-time">
                  {new Date(row.created_at).toLocaleString('vi-VN')}
                </span>
                <span className="audit-action">{row.action}</span>
                <span className="audit-target">
                  {row.target_type} / {row.target_id.slice(0, 8)}
                </span>
                {Boolean(row.details.affected_itineraries) && (
                  <span className="audit-affected">
                    Ảnh hưởng: {String(row.details.affected_itineraries)} lịch trình
                  </span>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
