import { useEffect, useState, useMemo, type FormEvent } from 'react'
import {
  Plus,
  Clock,
  Pencil,
  EyeOff,
  CheckCircle2,
  AlertCircle,
  History,
  X,
  Compass,
  MapPin,
  CalendarCheck,
  Tag,
  Sparkles,
  Search,
  Users,
  ShieldCheck,
  AlertTriangle,
  ExternalLink,
  Ban,
  Building2,
  Calendar,
  Check,
  CreditCard,
  Layers,
  RotateCcw,
  TrendingUp,
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

function renderStatusBadge(status: string) {
  switch (status) {
    case 'verified':
      return (
        <span className="portal-badge-pill badge-emerald">
          <CheckCircle2 size={12} /> Đã xác thực
        </span>
      )
    case 'open':
      return (
        <span className="portal-badge-pill badge-emerald">
          <CheckCircle2 size={12} /> Đang mở
        </span>
      )
    case 'confirmed':
      return (
        <span className="portal-badge-pill badge-emerald">
          <CheckCircle2 size={12} /> Đã xác nhận
        </span>
      )
    case 'pending':
    case 'pending_provider':
      return (
        <span className="portal-badge-pill badge-amber">
          <Clock size={12} /> Chờ cơ sở duyệt
        </span>
      )
    case 'awaiting_payment':
      return (
        <span className="portal-badge-pill badge-cyan">
          <CreditCard size={12} /> Chờ thanh toán
        </span>
      )
    case 'cancellation_requested':
      return (
        <span className="portal-badge-pill badge-rose">
          <AlertTriangle size={12} /> Yêu cầu hủy
        </span>
      )
    case 'refund_pending':
      return (
        <span className="portal-badge-pill badge-rose">
          <RotateCcw size={12} /> Chờ hoàn tiền
        </span>
      )
    case 'full':
      return (
        <span className="portal-badge-pill badge-purple">
          <Users size={12} /> Đầy chỗ
        </span>
      )
    case 'cancelled':
      return (
        <span className="portal-badge-pill badge-muted">
          <Ban size={12} /> Đã hủy
        </span>
      )
    case 'rejected':
      return (
        <span className="portal-badge-pill badge-muted">
          <Ban size={12} /> Đã từ chối
        </span>
      )
    default:
      return <span className="portal-badge-pill badge-slate">{status}</span>
  }
}

export function ProviderPortalPage() {
  const [providerId, setProviderId] = useState('')
  const [items, setItems] = useState<ExperienceItem[]>([])
  const [bookings, setBookings] = useState<Booking[]>([])
  const [pois, setPois] = useState<POI[]>([])
  const [providerPois, setProviderPois] = useState<Array<POI & { data_revision: number }>>([])
  const [evidenceItems, setEvidenceItems] = useState<
    Array<{
      id: string
      target_type: string
      target_id: string
      source_uri: string
      source_type: string
      source_label: string | null
      fields_covered: string[]
      observed_at: string | null
      expires_at: string | null
      verification_status: string
      reviewed_at: string | null
    }>
  >([])
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
    name: '',
    description: '',
    district: '',
    latitude: '',
    longitude: '',
    category: '',
    address: '',
  })

  // Modern UI Navigation State
  const [activeTab, setActiveTab] = useState<'experiences' | 'bookings' | 'locations' | 'audit'>('experiences')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [bookingStatusFilter, setBookingStatusFilter] = useState<string>('all')

  const poiOptions = Array.from(
    [
      ...pois,
      ...providerPois.map((point) => ({
        ...point,
        data_mode: point.verification_status === 'verified' ? ('real' as const) : ('simulated' as const),
      })),
    ].reduce((options, point) => options.set(point.id, point), new Map<string, POI>()).values()
  )

  async function load() {
    try {
      const [experiences, points, history, ownedPoints, sources, reservationRows, profile] =
        await Promise.all([
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
      const verifiedPointId =
        points.find((point) => point.data_mode === 'real')?.id ||
        ownedPoints.find((point) => point.verification_status === 'verified')?.id
      setDraft((current) =>
        current.poi_id || !verifiedPointId ? current : { ...current, poi_id: verifiedPointId }
      )
    } catch {
      setError('Không tải được dữ liệu cơ sở. Hãy đăng nhập bằng tài khoản có quyền cơ sở.')
    }
  }

  useEffect(() => {
    void load()
  }, [])

  // Derived metrics
  const totalSlots = useMemo(() => items.reduce((sum, item) => sum + item.slots.length, 0), [items])
  const pendingBookings = useMemo(
    () => bookings.filter((row) => row.status === 'pending_provider').length,
    [bookings]
  )
  const cancellationRequestedBookings = useMemo(
    () => bookings.filter((row) => row.status === 'cancellation_requested').length,
    [bookings]
  )
  const verifiedPoisCount = useMemo(
    () => providerPois.filter((p) => p.verification_status === 'verified').length,
    [providerPois]
  )
  const verifiedEvidenceCount = useMemo(
    () => evidenceItems.filter((e) => e.verification_status === 'verified').length,
    [evidenceItems]
  )

  // Filtered lists
  const filteredExperiences = useMemo(() => {
    return items.filter((item) => {
      const q = searchQuery.trim().toLowerCase()
      const matchesSearch =
        !q ||
        item.title.toLowerCase().includes(q) ||
        item.poi_name.toLowerCase().includes(q) ||
        (item.intent_tags && item.intent_tags.some((t) => t.toLowerCase().includes(q)))
      const matchesCategory =
        selectedCategory === 'all' || item.primary_intent === selectedCategory
      return matchesSearch && matchesCategory
    })
  }, [items, searchQuery, selectedCategory])

  const filteredBookings = useMemo(() => {
    return bookings.filter((b) => {
      if (bookingStatusFilter === 'all') return true
      return b.status === bookingStatusFilter
    })
  }, [bookings, bookingStatusFilter])

  const targetExperienceForSlot = useMemo(
    () => items.find((i) => i.id === slotTarget),
    [items, slotTarget]
  )

  async function decideBooking(id: string, action: 'accept' | 'reject') {
    setError('')
    setNotice('')
    try {
      const updated = await providerApi.decideBooking(id, action)
      setNotice(
        action === 'accept'
          ? updated.amount_vnd === 0
            ? 'Đã xác nhận đặt chỗ miễn phí.'
            : 'Đã xác nhận năng lực phục vụ và giữ chỗ tạm thời. Khách chưa thanh toán; cổng thanh toán của dự án chưa được cấu hình.'
          : 'Đã từ chối yêu cầu và giải phóng chỗ giữ tạm thời.'
      )
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
      setNotice(
        updated.status === 'cancelled'
          ? 'Đã xác nhận hủy đặt chỗ chưa thanh toán.'
          : 'Đã từ chối yêu cầu hủy; đặt chỗ vẫn giữ trạng thái xác nhận.'
      )
      await load()
    } catch {
      setError(
        'Chưa xử lý được yêu cầu. Nếu booking đã thanh toán, dự án cần tích hợp cổng thanh toán để thực hiện hoàn tiền thật; không đánh dấu hoàn khi chưa có kết quả từ cổng.'
      )
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
        const created = (await providerApi.createExperience(
          draft as unknown as Record<string, unknown>
        )) as { id: string }
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
        fields_covered: [
          'title',
          'description',
          'primary_intent',
          'intent_tags',
          'is_hands_on',
          'duration_min',
          'price_vnd',
          'price_basis',
        ],
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
      setDraft({
        ...blank,
        poi_id: poiOptions.find((point) => point.data_mode === 'real')?.id || '',
      })
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
      setNotice(
        'Đã thêm ca kèm thời điểm xác nhận và hạn xác nhận. Ca hết hạn sẽ không còn được coi là chỗ trống đã xác nhận.'
      )
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
      setPoiDraft({
        name: '',
        description: '',
        district: '',
        latitude: '',
        longitude: '',
        category: '',
        address: '',
      })
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

  function renderCapacityBar(slot: SlotItem) {
    const total = slot.capacity_total || 1
    const avail = slot.available_reported ?? total
    const booked = Math.max(0, total - avail)
    const percentBooked = Math.min(100, Math.round((booked / total) * 100))
    const percentAvailable = Math.max(0, 100 - percentBooked)

    let fillClass = 'high'
    if (slot.status === 'cancelled') {
      fillClass = 'cancelled'
    } else if (slot.status === 'full' || avail <= 0) {
      fillClass = 'full'
    } else if (percentAvailable <= 30) {
      fillClass = 'medium'
    }

    return (
      <div className="portal-capacity-wrap">
        <div className="portal-capacity-text">
          <span>
            Chỗ: <strong>{avail}</strong> còn lại / {total} tổng
          </span>
          <span>
            {slot.status === 'cancelled'
              ? 'Đã hủy'
              : slot.status === 'full'
              ? 'Hết chỗ'
              : `${percentAvailable}% trống`}
          </span>
        </div>
        <div className="portal-capacity-bar">
          <div
            className={`portal-capacity-fill ${fillClass}`}
            style={{ width: `${slot.status === 'cancelled' ? 100 : percentBooked}%` }}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="portal-page-3d page-wrap">
      {/* Hero Banner Card */}
      <div className="portal-hero-card">
        <div className="portal-hero-top-row">
          <div className="portal-live-badge">
            <span className="portal-live-dot" />
            <span>WORKSPACE CƠ SỞ ĐỐI TÁC · TRỰC TUYẾN</span>
          </div>
          {providerId && (
            <div className="portal-provider-chip">
              <Building2 size={13} className="text-emerald" />
              <span>
                Mã cơ sở: <strong>{providerId.slice(0, 8)}...</strong>
              </span>
            </div>
          )}
        </div>

        <h1 className="portal-hero-title">
          Quản lý Hoạt động & <em>Khung giờ Thực tế.</em>
        </h1>
        <p className="portal-hero-desc">
          Theo dõi yêu cầu đặt chỗ từ du khách, chủ động cập nhật sức chứa ca theo thời gian thực và quản
          lý hồ sơ trải nghiệm văn hóa đã xác thực trên bản đồ 3D Sài Gòn.
        </p>

        <div className="portal-hero-actions">
          <button
            type="button"
            className={`btn-secondary-3d ${showSlotAssistant ? 'active' : ''}`}
            onClick={() => setShowSlotAssistant((open) => !open)}
          >
            {showSlotAssistant ? <X size={16} /> : <Sparkles size={16} className="text-emerald" />}
            <span>{showSlotAssistant ? 'Đóng trợ lý' : 'Trợ lý AI cập nhật ca'}</span>
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
            {showPoiForm ? <X size={16} /> : <MapPin size={16} />}
            <span>{showPoiForm ? 'Đóng POI' : '+ Đăng ký POI thực'}</span>
          </button>
          <button
            type="button"
            className="btn-primary-3d"
            onClick={() => {
              setEditing('')
              setDraft({
                ...blank,
                poi_id: poiOptions.find((point) => point.data_mode === 'real')?.id || '',
              })
              setShowPoiForm(false)
              setShowExpForm(!showExpForm)
              setSourceUrl('')
            }}
          >
            {showExpForm ? <X size={16} /> : <Plus size={16} />}
            <span>{showExpForm ? 'Đóng form' : '+ Tạo trải nghiệm mới'}</span>
          </button>
        </div>
      </div>

      {/* KPI Overview Grid */}
      <div className="portal-kpi-grid">
        <div className="portal-kpi-card">
          <div className="portal-kpi-header">
            <span className="portal-kpi-label">Trải nghiệm</span>
            <div className="portal-kpi-icon-wrap">
              <Compass size={18} />
            </div>
          </div>
          <div className="portal-kpi-value">{items.length}</div>
          <div className="portal-kpi-footnote">
            <Layers size={13} className="text-emerald" />
            <span>{totalSlots} khung giờ hoạt động</span>
          </div>
        </div>

        <div className="portal-kpi-card">
          <div className="portal-kpi-header">
            <span className="portal-kpi-label">Yêu cầu đặt chỗ</span>
            <div className="portal-kpi-icon-wrap amber">
              <CalendarCheck size={18} />
            </div>
          </div>
          <div className="portal-kpi-value">{bookings.length}</div>
          <div className="portal-kpi-footnote">
            {pendingBookings > 0 ? (
              <span className="portal-kpi-alert-pill">
                <AlertCircle size={11} /> {pendingBookings} ca chờ duyệt
              </span>
            ) : cancellationRequestedBookings > 0 ? (
              <span className="portal-kpi-alert-pill">
                <AlertTriangle size={11} /> {cancellationRequestedBookings} yêu cầu hủy
              </span>
            ) : (
              <span style={{ color: 'var(--tx-emerald)' }}>
                <Check size={13} /> Tất cả đã xử lý
              </span>
            )}
          </div>
        </div>

        <div className="portal-kpi-card">
          <div className="portal-kpi-header">
            <span className="portal-kpi-label">Điểm POI quản lý</span>
            <div className="portal-kpi-icon-wrap cyan">
              <Building2 size={18} />
            </div>
          </div>
          <div className="portal-kpi-value">{providerPois.length}</div>
          <div className="portal-kpi-footnote">
            <ShieldCheck size={13} className="text-cyan" />
            <span>{verifiedPoisCount} địa điểm đã xác minh</span>
          </div>
        </div>

        <div className="portal-kpi-card">
          <div className="portal-kpi-header">
            <span className="portal-kpi-label">Minh chứng & Bằng chứng</span>
            <div className="portal-kpi-icon-wrap violet">
              <ShieldCheck size={18} />
            </div>
          </div>
          <div className="portal-kpi-value">{evidenceItems.length}</div>
          <div className="portal-kpi-footnote">
            <TrendingUp size={13} style={{ color: '#c084fc' }} />
            <span>{verifiedEvidenceCount} nguồn đã kiểm duyệt</span>
          </div>
        </div>
      </div>

      {/* Notices & Alerts */}
      {notice && (
        <div className="inline-alert-3d alert-success animate-fadeIn mb-6">
          <CheckCircle2 size={18} className="text-emerald" />
          <span>{notice}</span>
        </div>
      )}

      {error && (
        <div className="inline-alert-3d animate-fadeIn mb-6">
          <AlertCircle size={18} className="text-amber" />
          <span>{error}</span>
        </div>
      )}

      {/* AI Slot Assistant Modal / Drawer */}
      {showSlotAssistant && (
        <div className="animate-fadeIn mb-8">
          <ProviderSlotAssistantPanel
            providerId={providerId}
            experiences={items}
            onConfirmed={() => {
              void load()
            }}
          />
        </div>
      )}

      {/* Add Slot Modal / Drawer Card */}
      {slotTarget && (
        <section className="form-card-3d mb-8 animate-fadeIn">
          <div className="form-card-header">
            <span className="step-num">SLOT</span>
            <div>
              <h2>Thêm khung giờ (Slot) cho trải nghiệm</h2>
              <p>
                Áp dụng cho:{' '}
                <strong className="text-emerald">
                  {targetExperienceForSlot?.title || slotTarget}
                </strong>
                . Khung giờ này sẽ xuất hiện trên hệ thống tìm kiếm và AI itinerary planner.
              </p>
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

            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, gridColumn: '1 / -1' }}>
              <button className="btn-primary-3d" type="submit">
                <span>Tạo ca hoạt động</span>
              </button>
              <button
                type="button"
                className="btn-secondary-3d"
                onClick={() => setSlotTarget('')}
              >
                Hủy
              </button>
            </div>
          </form>
        </section>
      )}

      {/* POI Registration Form Drawer */}
      {showPoiForm && (
        <section className="form-card-3d mb-8 animate-fadeIn">
          <div className="form-card-header">
            <span className="step-num">POI</span>
            <div>
              <h2>{editingPoi ? 'Cập nhật POI thực tế' : 'Đăng ký địa điểm thực tế'}</h2>
              <p>POI mới ở trạng thái chờ duyệt; cần nguồn bao phủ địa chỉ, tọa độ và loại địa điểm.</p>
            </div>
            <button
              type="button"
              className="btn-ghost-sm"
              onClick={() => {
                setShowPoiForm(false)
                setEditingPoi('')
              }}
              aria-label="Đóng"
            >
              <X size={16} />
            </button>
          </div>
          <form onSubmit={savePoi} className="form-fields-grid-2">
            <label className="field-group-3d">
              <span>Tên địa điểm</span>
              <input
                required
                minLength={2}
                value={poiDraft.name}
                onChange={(e) => setPoiDraft({ ...poiDraft, name: e.target.value })}
                placeholder="Ví dụ: Lò gốm Sài Gòn Xưa..."
              />
            </label>
            <label className="field-group-3d">
              <span>Loại hoạt động / danh mục</span>
              <input
                required
                value={poiDraft.category}
                onChange={(e) => setPoiDraft({ ...poiDraft, category: e.target.value })}
                placeholder="handicraft, food, culture, workshop..."
              />
            </label>
            <label className="field-group-3d" style={{ gridColumn: '1 / -1' }}>
              <span>Địa chỉ đã xác minh tại thực địa</span>
              <input
                required
                minLength={5}
                value={poiDraft.address}
                onChange={(e) => setPoiDraft({ ...poiDraft, address: e.target.value })}
                placeholder="Số nhà, đường, phường, quận..."
              />
            </label>
            <label className="field-group-3d">
              <span>Vĩ độ (Latitude)</span>
              <input
                type="number"
                required
                step="any"
                min={-90}
                max={90}
                value={poiDraft.latitude}
                onChange={(e) => setPoiDraft({ ...poiDraft, latitude: e.target.value })}
                placeholder="10.7769..."
              />
            </label>
            <label className="field-group-3d">
              <span>Kinh độ (Longitude)</span>
              <input
                type="number"
                required
                step="any"
                min={-180}
                max={180}
                value={poiDraft.longitude}
                onChange={(e) => setPoiDraft({ ...poiDraft, longitude: e.target.value })}
                placeholder="106.7009..."
              />
            </label>
            <label className="field-group-3d">
              <span>Quận / Khu vực</span>
              <input
                value={poiDraft.district}
                onChange={(e) => setPoiDraft({ ...poiDraft, district: e.target.value })}
                placeholder="Quận 1, Quận 5..."
              />
            </label>
            <label className="field-group-3d">
              <span>Mô tả ngắn gọn</span>
              <input
                value={poiDraft.description}
                onChange={(e) => setPoiDraft({ ...poiDraft, description: e.target.value })}
                placeholder="Mô tả không gian và văn hóa tại cơ sở..."
              />
            </label>
            <label className="field-group-3d" style={{ gridColumn: '1 / -1' }}>
              <span>URL nguồn chứng minh địa chỉ & thông tin chính thức</span>
              <input
                type="url"
                required
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://..."
              />
            </label>
            <label className="field-group-3d">
              <span>Loại nguồn</span>
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
              >
                <option value="official_website">Website chính thức</option>
                <option value="provider_confirmation">Xác nhận trực tiếp của cơ sở</option>
                <option value="field_visit">Khảo sát thực địa</option>
                <option value="document">Tài liệu / Giấy tờ pháp lý</option>
                <option value="government_dataset">Dữ liệu cơ quan nhà nước</option>
                <option value="other">Khác</option>
              </select>
            </label>
            <label className="field-group-3d">
              <span>Tên nguồn / Đơn vị thẩm định</span>
              <input
                value={sourceLabel}
                onChange={(e) => setSourceLabel(e.target.value)}
                placeholder="Trang chính thức của cơ sở"
              />
            </label>
            <label className="field-group-3d">
              <span>Thời điểm kiểm tra</span>
              <input
                type="datetime-local"
                required
                value={sourceObservedAt}
                onChange={(e) => setSourceObservedAt(e.target.value)}
              />
            </label>
            <label className="field-group-3d">
              <span>Hạn dùng bằng chứng</span>
              <input
                type="datetime-local"
                required
                value={sourceExpiresAt}
                onChange={(e) => setSourceExpiresAt(e.target.value)}
              />
            </label>
            <label className="field-group-3d" style={{ gridColumn: '1 / -1' }}>
              <span>Giấy phép / điều khoản nguồn</span>
              <input
                value={sourceLicense}
                onChange={(e) => setSourceLicense(e.target.value)}
                placeholder="Ví dụ: Nội dung do cơ sở ủy quyền cung cấp"
              />
            </label>
            <div className="form-action-row" style={{ gridColumn: '1 / -1' }}>
              <button className="btn-primary-3d" type="submit">
                <span>{editingPoi ? 'Lưu POI và gửi bằng chứng mới' : 'Gửi POI và bằng chứng'}</span>
              </button>
              <button
                type="button"
                className="btn-secondary-3d"
                onClick={() => {
                  setShowPoiForm(false)
                  setEditingPoi('')
                }}
              >
                Hủy bỏ
              </button>
            </div>
          </form>
        </section>
      )}

      {/* Experience Editor Form Card (Collapsible) */}
      {showExpForm && (
        <section className="form-card-3d mb-8 animate-fadeIn">
          <div className="form-card-header">
            <span className="step-num">{editing ? 'EDIT' : 'NEW'}</span>
            <div>
              <h2>{editing ? 'Chỉnh sửa thông tin trải nghiệm' : 'Đăng ký trải nghiệm mới'}</h2>
              <p>Thông tin chi tiết về hoạt động, địa điểm và thời lượng tổ chức.</p>
            </div>
            <button
              type="button"
              className="btn-ghost-sm"
              onClick={() => {
                setEditing('')
                setShowExpForm(false)
              }}
              aria-label="Đóng"
            >
              <X size={16} />
            </button>
          </div>

          <form onSubmit={saveExperience} className="form-fields-grid-2">
            <label className="field-group-3d">
              <span>Địa điểm tổ chức (POI)</span>
              <select
                required
                value={draft.poi_id}
                onChange={(e) => setDraft({ ...draft, poi_id: e.target.value })}
              >
                <option value="" disabled>
                  Chọn POI đã xác minh trước khi đăng trải nghiệm
                </option>
                {poiOptions.map((p) => (
                  <option key={p.id} value={p.id} disabled={p.data_mode !== 'real'}>
                    {p.name} — {p.address}
                    {p.data_mode !== 'real' ? ' · DỮ LIỆU MÔ PHỎNG / CHƯA XÁC MINH' : ''}
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
              <select
                value={draft.primary_intent}
                onChange={(e) => setDraft({ ...draft, primary_intent: e.target.value })}
              >
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
                <p>
                  Bằng chứng được gắn với phiên bản dữ liệu hiện tại; sửa nội dung sẽ yêu cầu gửi bằng chứng mới.
                </p>
              </div>
            </div>
            <label className="field-group-3d" style={{ gridColumn: '1 / -1' }}>
              <span>URL nguồn chứng minh giá, thời lượng, loại hoạt động và hands-on</span>
              <input
                type="url"
                required
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://..."
              />
            </label>
            <label className="field-group-3d">
              <span>Loại nguồn</span>
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
              >
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
              <input
                value={sourceLabel}
                onChange={(e) => setSourceLabel(e.target.value)}
                placeholder="Trang chính thức của cơ sở"
              />
            </label>
            <label className="field-group-3d">
              <span>Giấy phép / điều khoản sử dụng nguồn</span>
              <input
                value={sourceLicense}
                onChange={(e) => setSourceLicense(e.target.value)}
                placeholder="Ví dụ: nội dung do cơ sở cung cấp"
              />
            </label>
            <label className="field-group-3d">
              <span>Thời điểm kiểm tra nguồn</span>
              <input
                type="datetime-local"
                required
                value={sourceObservedAt}
                onChange={(e) => setSourceObservedAt(e.target.value)}
              />
            </label>
            <label className="field-group-3d">
              <span>Hạn dùng bằng chứng</span>
              <input
                type="datetime-local"
                required
                value={sourceExpiresAt}
                onChange={(e) => setSourceExpiresAt(e.target.value)}
              />
            </label>
            <label className="custom-check-pill" style={{ gridColumn: '1 / -1' }}>
              <input
                type="checkbox"
                checked={sourceConfirmsPoi}
                onChange={(e) => setSourceConfirmsPoi(e.target.checked)}
              />
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

      {/* Modern Tabs Navigation */}
      <div className="portal-tabs-nav">
        <button
          type="button"
          className={`portal-tab-btn ${activeTab === 'experiences' ? 'active' : ''}`}
          onClick={() => setActiveTab('experiences')}
        >
          <Compass size={15} />
          <span>Trải nghiệm & Khung giờ</span>
          <span className="portal-tab-badge">{items.length}</span>
        </button>

        <button
          type="button"
          className={`portal-tab-btn ${activeTab === 'bookings' ? 'active' : ''}`}
          onClick={() => setActiveTab('bookings')}
        >
          <CalendarCheck size={15} />
          <span>Yêu cầu đặt chỗ</span>
          <span className={`portal-tab-badge ${pendingBookings > 0 ? 'badge-amber' : ''}`}>
            {bookings.length}
          </span>
        </button>

        <button
          type="button"
          className={`portal-tab-btn ${activeTab === 'locations' ? 'active' : ''}`}
          onClick={() => setActiveTab('locations')}
        >
          <MapPin size={15} />
          <span>Địa điểm POI & Bằng chứng</span>
          <span className="portal-tab-badge">
            {providerPois.length + evidenceItems.length}
          </span>
        </button>

        <button
          type="button"
          className={`portal-tab-btn ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          <History size={15} />
          <span>Nhật ký kiểm toán</span>
          <span className="portal-tab-badge">{audit.length}</span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: EXPERIENCES & SLOTS                                                */}
      {/* ========================================================================= */}
      {activeTab === 'experiences' && (
        <section className="portal-experiences-section animate-fadeIn">
          {/* Filter & Search Bar */}
          <div className="portal-filter-bar">
            <div className="portal-search-wrap">
              <Search size={15} className="portal-search-icon" />
              <input
                type="text"
                className="portal-search-input"
                placeholder="Tìm kiếm trải nghiệm, POI..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <div className="portal-pills-row">
              {[
                { id: 'all', label: 'Tất cả' },
                { id: 'thủ_công', label: 'Thủ công' },
                { id: 'ẩm_thực', label: 'Ẩm thực' },
                { id: 'văn_hóa', label: 'Văn hóa' },
                { id: 'thư_giãn', label: 'Thư giãn' },
              ].map((cat) => (
                <button
                  key={cat.id}
                  type="button"
                  className={`portal-filter-pill ${selectedCategory === cat.id ? 'active' : ''}`}
                  onClick={() => setSelectedCategory(cat.id)}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          {/* List of Experiences */}
          {filteredExperiences.length > 0 ? (
            <div className="portal-exp-list">
              {filteredExperiences.map((item) => (
                <article key={item.id} className="portal-exp-card">
                  <div className="portal-exp-top">
                    <div className="portal-exp-meta-left" style={{ flex: 1 }}>
                      <div className="portal-tags-row">
                        {renderStatusBadge(item.verification_status)}
                        {item.primary_intent && (
                          <span className="portal-badge-pill badge-cyan">
                            <Tag size={11} /> {item.primary_intent}
                          </span>
                        )}
                        {item.is_hands_on && (
                          <span className="portal-badge-pill badge-purple">
                            <Sparkles size={11} /> Hands-on
                          </span>
                        )}
                        <span className="portal-badge-pill badge-slate">
                          {item.is_indoor ? 'Trong nhà' : 'Ngoài trời'}
                        </span>
                      </div>

                      <h3 className="portal-exp-title">{item.title}</h3>

                      <div className="portal-exp-meta-bar">
                        <span className="portal-meta-item">
                          <MapPin size={13} className="text-emerald" /> {item.poi_name}
                        </span>
                        <span className="portal-meta-item">
                          <Tag size={13} className="text-amber" />
                          {item.price_vnd.toLocaleString('vi-VN')}₫ (
                          {item.price_basis === 'per_person' ? 'mỗi khách' : 'trọn gói'})
                        </span>
                        <span className="portal-meta-item">
                          <Clock size={13} className="text-cyan" /> {item.duration_min} phút
                        </span>
                      </div>

                      {item.description && (
                        <p className="portal-exp-desc">{item.description}</p>
                      )}
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

                  {/* Slots Grid for this experience */}
                  <div className="portal-slots-container">
                    <div className="slots-heading-row">
                      <span className="slots-heading-label">
                        <Clock size={13} className="text-emerald" /> Khung giờ đã lên lịch (
                        {item.slots.length} ca):
                      </span>
                      <button
                        type="button"
                        className="btn-slot-cap"
                        onClick={() => {
                          setSlotTarget(item.id)
                          setSlotExpiresAt(localDateTimeInput(4 * 60 * 60 * 1000))
                          window.scrollTo({ top: 200, behavior: 'smooth' })
                        }}
                      >
                        <Plus size={11} /> Thêm ca nhanh
                      </button>
                    </div>

                    {item.slots.length > 0 ? (
                      <div className="slots-grid">
                        {item.slots.map((slot) => (
                          <div key={slot.id} className="slot-chip-card">
                            <div className="slot-chip-top">
                              <div className="slot-chip-time">
                                <Calendar size={13} className="text-emerald" />
                                <span>
                                  {new Date(slot.start_at).toLocaleString('vi-VN', {
                                    dateStyle: 'short',
                                    timeStyle: 'short',
                                    timeZone: 'Asia/Ho_Chi_Minh',
                                  })}
                                </span>
                              </div>
                              {renderStatusBadge(slot.status)}
                            </div>

                            {/* Capacity Visual Progress Bar */}
                            {renderCapacityBar(slot)}

                            <div className="slot-chip-dates">
                              <div>
                                Xác nhận:{' '}
                                {slot.confirmed_at
                                  ? new Date(slot.confirmed_at).toLocaleTimeString('vi-VN', {
                                      hour: '2-digit',
                                      minute: '2-digit',
                                      day: '2-digit',
                                      month: '2-digit',
                                    })
                                  : 'chưa có'}
                              </div>
                              <div>
                                Hạn chót:{' '}
                                {slot.expires_at
                                  ? new Date(slot.expires_at).toLocaleTimeString('vi-VN', {
                                      hour: '2-digit',
                                      minute: '2-digit',
                                      day: '2-digit',
                                      month: '2-digit',
                                    })
                                  : 'chưa có'}
                              </div>
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
                      <p className="no-slots-hint">
                        Chưa có khung giờ nào được lên lịch cho trải nghiệm này. Nhấn &ldquo;Thêm ca&rdquo; để đón khách.
                      </p>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="portal-empty-card">
              <div className="portal-empty-icon">
                <Compass size={32} />
              </div>
              <h3 className="portal-empty-title">
                {searchQuery || selectedCategory !== 'all'
                  ? 'Không tìm thấy trải nghiệm phù hợp'
                  : 'Chưa có trải nghiệm nào được đăng ký'}
              </h3>
              <p className="portal-empty-desc">
                {searchQuery || selectedCategory !== 'all'
                  ? 'Thử thay đổi từ khóa tìm kiếm hoặc chọn danh mục khác.'
                  : 'Đăng ký trải nghiệm văn hóa, ẩm thực hoặc nghệ thuật đầu tiên của cơ sở để đón khách du lịch trên nền tảng.'}
              </p>
              {searchQuery || selectedCategory !== 'all' ? (
                <button
                  type="button"
                  className="btn-secondary-3d"
                  onClick={() => {
                    setSearchQuery('')
                    setSelectedCategory('all')
                  }}
                >
                  Xóa bộ lọc
                </button>
              ) : (
                <button
                  type="button"
                  className="btn-primary-3d"
                  onClick={() => {
                    setEditing('')
                    setDraft({
                      ...blank,
                      poi_id: poiOptions.find((point) => point.data_mode === 'real')?.id || '',
                    })
                    setShowPoiForm(false)
                    setShowExpForm(true)
                  }}
                >
                  <Plus size={15} /> Thêm trải nghiệm đầu tiên
                </button>
              )}
            </div>
          )}
        </section>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: BOOKINGS                                                           */}
      {/* ========================================================================= */}
      {activeTab === 'bookings' && (
        <section className="portal-experiences-section animate-fadeIn">
          {/* Booking Notice Guidance */}
          <div className="booking-info-pill mb-6 w-full" style={{ padding: '12px 16px' }}>
            <AlertCircle size={16} className="text-amber" style={{ flexShrink: 0 }} />
            <span>
              <strong>Lưu ý xác nhận:</strong> Chỉ chấp nhận sau khi kiểm tra lại số chỗ thực tế. Yêu
              cầu có thời hạn giữ chỗ; du khách sẽ được thông báo đã đặt thành công sau khi thanh toán
              hoặc khi ca miễn phí được cơ sở xác nhận.
            </span>
          </div>

          {/* Filter Pills for Bookings */}
          <div className="portal-filter-bar">
            <div className="portal-pills-row">
              {[
                { id: 'all', label: `Tất cả (${bookings.length})` },
                { id: 'pending_provider', label: `Chờ duyệt (${pendingBookings})` },
                { id: 'awaiting_payment', label: 'Chờ thanh toán' },
                { id: 'cancellation_requested', label: `Yêu cầu hủy (${cancellationRequestedBookings})` },
                { id: 'confirmed', label: 'Đã xác nhận' },
                { id: 'cancelled', label: 'Đã hủy' },
              ].map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className={`portal-filter-pill ${bookingStatusFilter === f.id ? 'active' : ''}`}
                  onClick={() => setBookingStatusFilter(f.id)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {filteredBookings.length > 0 ? (
            <div className="portal-exp-list">
              {filteredBookings.map((booking) => (
                <article
                  key={booking.id}
                  className={`portal-exp-card booking-provider-card ${booking.status}`}
                >
                  <div className="portal-exp-top">
                    <div className="portal-exp-meta-left" style={{ flex: 1 }}>
                      <div className="portal-tags-row">
                        {renderStatusBadge(booking.status)}
                        <span className="portal-badge-pill badge-slate">
                          <Users size={11} /> {booking.quantity} khách
                        </span>
                        <span className="portal-badge-pill badge-cyan">
                          <Tag size={11} /> {booking.amount_vnd.toLocaleString('vi-VN')}₫
                        </span>
                      </div>

                      <h3 className="portal-exp-title">{booking.experience_title}</h3>

                      <div className="portal-exp-meta-bar">
                        <span className="portal-meta-item">
                          <Calendar size={13} className="text-emerald" /> Ca:{' '}
                          {booking.slot_start_at
                            ? new Date(booking.slot_start_at).toLocaleString('vi-VN', {
                                dateStyle: 'short',
                                timeStyle: 'short',
                                timeZone: 'Asia/Ho_Chi_Minh',
                              })
                            : 'Không rõ giờ'}
                        </span>
                        {booking.hold_expires_at && (
                          <span className="portal-meta-item text-amber">
                            <Clock size={13} /> Hạn giữ chỗ:{' '}
                            {new Date(booking.hold_expires_at).toLocaleString('vi-VN', {
                              dateStyle: 'short',
                              timeStyle: 'short',
                              timeZone: 'Asia/Ho_Chi_Minh',
                            })}
                          </span>
                        )}
                      </div>

                      {/* Status Info Notes */}
                      {booking.status === 'awaiting_payment' && (
                        <div className="booking-info-pill" style={{ marginTop: 8 }}>
                          <CheckCircle2 size={13} className="text-emerald" />
                          <span>
                            Đã xác nhận năng lực phục vụ; đang chờ khách thanh toán qua cổng thanh toán.
                          </span>
                        </div>
                      )}
                      {booking.status === 'cancellation_requested' && (
                        <div className="booking-info-pill text-rose" style={{ marginTop: 8 }}>
                          <AlertTriangle size={13} />
                          <span>
                            Khách yêu cầu hủy. Nếu giao dịch đã thu tiền thật, cần cổng thanh toán để hoàn tiền.
                          </span>
                        </div>
                      )}
                      {booking.status === 'refund_pending' && (
                        <div className="booking-info-pill" style={{ marginTop: 8 }}>
                          <RotateCcw size={13} className="text-amber" />
                          <span>Hoàn tiền đang chờ xử lý bởi cổng thanh toán.</span>
                        </div>
                      )}
                    </div>

                    {/* Action buttons */}
                    <div className="portal-exp-actions">
                      {booking.status === 'pending_provider' && (
                        <>
                          <button
                            type="button"
                            className="btn-primary-3d btn-sm"
                            onClick={() => void decideBooking(booking.id, 'accept')}
                          >
                            <Check size={13} /> Xác nhận chỗ
                          </button>
                          <button
                            type="button"
                            className="btn-secondary-3d btn-sm"
                            onClick={() => void decideBooking(booking.id, 'reject')}
                          >
                            <X size={13} /> Từ chối
                          </button>
                        </>
                      )}

                      {booking.status === 'cancellation_requested' && (
                        <>
                          <button
                            type="button"
                            className="btn-primary-3d btn-sm"
                            onClick={() => void decideBookingCancellation(booking.id, 'approve')}
                          >
                            {booking.amount_vnd > 0 ? 'Duyệt hủy & hoàn tiền' : 'Duyệt hủy'}
                          </button>
                          {booking.slot_status !== 'cancelled' && (
                            <button
                              type="button"
                              className="btn-secondary-3d btn-sm"
                              onClick={() => void decideBookingCancellation(booking.id, 'reject')}
                            >
                              Từ chối hủy
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="portal-empty-card">
              <div className="portal-empty-icon">
                <CalendarCheck size={32} />
              </div>
              <h3 className="portal-empty-title">Không có yêu cầu đặt chỗ nào</h3>
              <p className="portal-empty-desc">
                {bookingStatusFilter !== 'all'
                  ? 'Không tìm thấy booking nào với trạng thái này.'
                  : 'Các yêu cầu đặt chỗ từ du khách sẽ hiển thị ở đây để cơ sở phê duyệt và giữ chỗ.'}
              </p>
              {bookingStatusFilter !== 'all' && (
                <button
                  type="button"
                  className="btn-secondary-3d"
                  onClick={() => setBookingStatusFilter('all')}
                >
                  Xem tất cả yêu cầu
                </button>
              )}
            </div>
          )}
        </section>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: LOCATIONS & EVIDENCE                                               */}
      {/* ========================================================================= */}
      {activeTab === 'locations' && (
        <section className="portal-experiences-section animate-fadeIn">
          {/* POI Section */}
          <div style={{ marginBottom: 40 }}>
            <div className="slots-heading-row" style={{ marginBottom: 16 }}>
              <div>
                <h2 className="section-title-3d" style={{ margin: 0 }}>
                  Địa điểm POI do cơ sở quản lý ({providerPois.length})
                </h2>
                <p className="page-subtext-3d" style={{ margin: '4px 0 0' }}>
                  Địa điểm thực tế đã được khai báo tọa độ GPS và liên kết với các trải nghiệm.
                </p>
              </div>
              <button
                type="button"
                className="btn-primary-3d btn-sm"
                onClick={() => {
                  setShowExpForm(false)
                  setEditingPoi('')
                  setShowPoiForm(true)
                  setSourceUrl('')
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }}
              >
                <Plus size={14} /> Thêm POI mới
              </button>
            </div>

            {providerPois.length > 0 ? (
              <div className="portal-poi-grid">
                {providerPois.map((poi) => (
                  <article key={poi.id} className="portal-poi-card">
                    <div className="portal-poi-top">
                      <div>
                        {renderStatusBadge(poi.verification_status)}
                        <h4 className="portal-poi-name">{poi.name}</h4>
                      </div>
                      <button
                        type="button"
                        className="btn-secondary-3d btn-sm"
                        onClick={() => {
                          setEditingPoi(poi.id)
                          setPoiDraft({
                            name: poi.name,
                            description: poi.description || '',
                            district: poi.district || '',
                            latitude: String(poi.latitude),
                            longitude: String(poi.longitude),
                            category: poi.category,
                            address: poi.address,
                          })
                          setSourceUrl('')
                          setShowExpForm(false)
                          setShowPoiForm(true)
                          window.scrollTo({ top: 0, behavior: 'smooth' })
                        }}
                      >
                        <Pencil size={12} /> Sửa POI
                      </button>
                    </div>

                    <div className="portal-poi-address">
                      <MapPin size={14} className="text-emerald" style={{ flexShrink: 0, marginTop: 2 }} />
                      <span>{poi.address}</span>
                    </div>

                    <div className="portal-poi-chips">
                      <span className="portal-poi-chip">
                        GPS: {poi.latitude.toFixed(5)}, {poi.longitude.toFixed(5)}
                      </span>
                      <span className="portal-poi-chip">{poi.category}</span>
                      {poi.district && <span className="portal-poi-chip">{poi.district}</span>}
                    </div>

                    {poi.description && (
                      <p className="portal-exp-desc" style={{ margin: 0 }}>
                        {poi.description}
                      </p>
                    )}
                  </article>
                ))}
              </div>
            ) : (
              <div className="portal-empty-card">
                <div className="portal-empty-icon">
                  <MapPin size={32} />
                </div>
                <h3 className="portal-empty-title">Chưa có POI do cơ sở quản lý</h3>
                <p className="portal-empty-desc">
                  Khai báo địa chỉ và tọa độ GPS thực tế của cơ sở để du khách có thể ghé thăm và định vị trên bản đồ 3D.
                </p>
                <button
                  type="button"
                  className="btn-primary-3d"
                  onClick={() => {
                    setShowExpForm(false)
                    setEditingPoi('')
                    setShowPoiForm(true)
                    setSourceUrl('')
                    window.scrollTo({ top: 0, behavior: 'smooth' })
                  }}
                >
                  <Plus size={14} /> Đăng ký POI đầu tiên
                </button>
              </div>
            )}
          </div>

          {/* Evidence Section */}
          <div>
            <div className="slots-heading-row" style={{ marginBottom: 16 }}>
              <div>
                <h2 className="section-title-3d" style={{ margin: 0 }}>
                  Nguồn và bằng chứng xác minh ({evidenceItems.length})
                </h2>
                <p className="page-subtext-3d" style={{ margin: '4px 0 0' }}>
                  Bằng chứng pháp lý, bài viết báo chí hoặc xác nhận chính thức chứng minh tính xác thực của cơ sở.
                </p>
              </div>
            </div>

            {evidenceItems.length > 0 ? (
              <div className="portal-evidence-grid">
                {evidenceItems.map((source) => (
                  <article key={source.id} className="portal-evidence-card">
                    <div className="portal-exp-top" style={{ paddingBottom: 10, marginBottom: 10 }}>
                      <div>
                        {renderStatusBadge(source.verification_status)}
                        <h4 className="portal-poi-name">
                          {source.source_label || source.source_type}
                        </h4>
                      </div>
                      <span className="portal-badge-pill badge-cyan">
                        {source.target_type === 'experience' ? 'Trải nghiệm' : 'Địa điểm POI'}
                      </span>
                    </div>

                    <div className="portal-poi-chips">
                      {source.fields_covered.map((field) => (
                        <span key={field} className="portal-poi-chip">
                          {field}
                        </span>
                      ))}
                    </div>

                    <div className="slot-chip-dates">
                      <div>
                        Quan sát:{' '}
                        {source.observed_at
                          ? new Date(source.observed_at).toLocaleString('vi-VN', {
                              dateStyle: 'short',
                              timeStyle: 'short',
                            })
                          : '—'}
                      </div>
                      <div>
                        Hết hạn:{' '}
                        {source.expires_at
                          ? new Date(source.expires_at).toLocaleString('vi-VN', {
                              dateStyle: 'short',
                              timeStyle: 'short',
                            })
                          : '—'}
                      </div>
                    </div>

                    <div style={{ marginTop: 'auto', paddingTop: 8 }}>
                      {source.source_uri.startsWith('http') ? (
                        <a
                          href={source.source_uri}
                          target="_blank"
                          rel="noreferrer"
                          className="btn-secondary-3d btn-sm w-full"
                          style={{ justifyContent: 'center' }}
                        >
                          <ExternalLink size={12} /> Xem liên kết nguồn
                        </a>
                      ) : (
                        <span className="no-slots-hint">
                          {source.source_uri} (xác nhận nội bộ)
                        </span>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="portal-empty-card">
                <div className="portal-empty-icon">
                  <ShieldCheck size={32} />
                </div>
                <h3 className="portal-empty-title">Chưa gửi bằng chứng nguồn nào</h3>
                <p className="portal-empty-desc">
                  Khi tạo mới POI hoặc trải nghiệm, hãy đính kèm URL nguồn để quản trị viên tiến hành thẩm định và cấp huy hiệu xác thực.
                </p>
              </div>
            )}
          </div>
        </section>
      )}

      {/* ========================================================================= */}
      {/* TAB 4: AUDIT LOG                                                          */}
      {/* ========================================================================= */}
      {activeTab === 'audit' && (
        <section className="portal-audit-section animate-fadeIn">
          <div className="audit-header-row">
            <History size={18} className="text-emerald" />
            <h3>Nhật ký kiểm toán & thao tác gần đây ({audit.length})</h3>
          </div>

          {audit.length > 0 ? (
            <div className="audit-rows-list">
              {audit.map((row) => (
                <div key={row.id} className="audit-log-item">
                  <span className="audit-time">
                    <Clock size={12} style={{ display: 'inline', marginRight: 4 }} />
                    {new Date(row.created_at).toLocaleString('vi-VN', {
                      dateStyle: 'short',
                      timeStyle: 'medium',
                      timeZone: 'Asia/Ho_Chi_Minh',
                    })}
                  </span>
                  <span className="audit-action">{row.action}</span>
                  <span className="audit-target">
                    {row.target_type} · {row.target_id.slice(0, 8)}...
                  </span>
                  {Boolean(row.details.affected_itineraries) && (
                    <span className="audit-affected">
                      Ảnh hưởng: {String(row.details.affected_itineraries)} lịch trình
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="portal-empty-card">
              <div className="portal-empty-icon">
                <History size={32} />
              </div>
              <h3 className="portal-empty-title">Chưa có nhật ký thao tác</h3>
              <p className="portal-empty-desc">
                Các hoạt động điều chỉnh slot, duyệt booking hoặc sửa dữ liệu sẽ được ghi nhận tại đây nhằm đảm bảo tính minh bạch.
              </p>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
