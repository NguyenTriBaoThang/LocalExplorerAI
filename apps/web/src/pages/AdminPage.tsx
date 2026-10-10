import { useEffect, useState, type FormEvent } from 'react'
import {
  Users,
  Building,
  Layers,
  GitMerge,
  History,
  Check,
  CheckCircle2,
  X,
  EyeOff,
  AlertCircle,
  AlertTriangle,
  Plus,
  RefreshCw,
  KeyRound,
  Save,
  Trash2,
  FileSpreadsheet,
  Activity,
  Brain,
  MapPinned,
  Compass,
  ShieldCheck,
  Clock,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { adminApi } from '../api/client'
import { TiltCard3D } from '../components/3d/TiltCard3D'
import { useTranslation } from '../i18n'
import { AdminOperationsPanel } from './AdminOperationsPanel'
import { AdminAiToolsPanel } from './AdminAiToolsPanel'
import { AdminFloodRiskPanel } from './AdminFloodRiskPanel'

type QueueItem = {
  id: string
  name?: string
  title?: string
  source_uri?: string
  source_type?: string
  source_label?: string | null
  license?: string | null
  target_type?: string | null
  target_id?: string | null
  fields_covered?: string[]
  observed_at?: string | null
  expires_at?: string | null
  status: string
}

type DuplicatePair = {
  poi_a: { id: string; name: string }
  poi_b: { id: string; name: string }
  name_similarity: number
}

type IntegrationField = {
  key: string
  label: string
  secret: boolean
  configured: boolean
  source: 'admin' | 'environment' | 'missing'
  value: string | null
  updated_at: string | null
}

type IntegrationGroup = { service: string; fields: IntegrationField[] }

type PlaceImportBatch = {
  id: string
  source_name: string
  source_sha256: string
  worksheet_name: string
  record_count: number
  quality_summary: Record<string, unknown>
  created_at: string
}

type PlaceImportCandidate = {
  id: string
  external_id: string
  source_row: number
  name: string
  kind: string
  raw_payload: Record<string, unknown>
  suggested_labels?: {
    ruleset_version: string
    label_status: string
    intent_columns: {
      handicraft: boolean
      food: boolean
      culture: boolean
      relaxation: boolean
    }
    poi_type: string
    poi_type_label_vi: string
    activity_mode: string
    primary_intent: string | null
    intent_tags: string[]
    source_topic_tags: string[]
    hands_on: boolean | null
    hands_on_status: string
    indoor_outdoor: string
    weather_sensitivity: string
    basis_fields: string[]
    warning: string
  } | null
  quality_flags: string[]
  review_status: string
  target_poi_id?: string | null
  target_poi_status?: string | null
}

function toDateTimeLocal(value: unknown): string {
  if (typeof value !== 'string') return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

const PLACE_ACTIVITY_MODE_LABELS: Record<string, string> = {
  passive_visit: 'Tham quan / quan sát',
  food_service: 'Ăn uống',
  coffee_service: 'Cà phê',
  entertainment: 'Giải trí',
  lodging: 'Lưu trú',
  participatory_activity: 'Có dấu hiệu tham gia trực tiếp',
  unknown: 'Chưa phân loại',
}

const PLACE_CORE_INTENT_COLUMNS = [
  { key: 'handicraft', label: 'Thủ công' },
  { key: 'food', label: 'Ẩm thực' },
  { key: 'culture', label: 'Văn hóa' },
  { key: 'relaxation', label: 'Thư giãn' },
] as const

type TabKey =
  | 'queue'
  | 'imports'
  | 'duplicates'
  | 'providers'
  | 'users'
  | 'audit'
  | 'integrations'
  | 'operations'
  | 'ai-tools'
  | 'flood-risk'

type ToastMessage = {
  id: string
  type: 'success' | 'error' | 'warning'
  title: string
  text: string
}

const METRIC_CONFIG: Record<
  string,
  { label: string; icon: typeof Users; colorClass: string; hint: string }
> = {
  users: {
    label: 'Người dùng',
    icon: Users,
    colorClass: 'cyan',
    hint: 'Tài khoản trong hệ thống',
  },
  providers: {
    label: 'Cơ sở đối tác',
    icon: Building,
    colorClass: 'emerald',
    hint: 'Doanh nghiệp & xưởng',
  },
  pending_pois: {
    label: 'POI chờ duyệt',
    icon: MapPinned,
    colorClass: 'amber',
    hint: 'Địa điểm cần xác thực',
  },
  pending_experiences: {
    label: 'Trải nghiệm chờ duyệt',
    icon: Compass,
    colorClass: 'purple',
    hint: 'Hoạt động & workshop',
  },
  pending_evidence: {
    label: 'Bằng chứng chờ duyệt',
    icon: ShieldCheck,
    colorClass: 'purple',
    hint: 'Tài liệu xác minh',
  },
  unknown_slot_capacity: {
    label: 'Slot chưa rõ sức chứa',
    icon: AlertCircle,
    colorClass: 'amber',
    hint: 'Cần đối tác cập nhật',
  },
  expired_evidence: {
    label: 'Bằng chứng hết hạn',
    icon: Clock,
    colorClass: 'amber',
    hint: 'Cần kiểm tra lại hạn',
  },
}

export function AdminPage() {
  const { t } = useTranslation()
  const [dashboard, setDashboard] = useState<Record<string, number>>({})
  const [users, setUsers] = useState<
    Array<{
      id: string
      email: string
      display_name: string
      role: string
      provider_id: string | null
      is_active: boolean
    }>
  >([])
  const [providers, setProviders] = useState<Array<{ id: string; name: string }>>([])
  const [queue, setQueue] = useState<{
    pois: QueueItem[]
    experiences: QueueItem[]
    evidence: QueueItem[]
  }>({ pois: [], experiences: [], evidence: [] })
  const [duplicates, setDuplicates] = useState<DuplicatePair[]>([])
  const [audit, setAudit] = useState<
    Array<{
      id: string
      action: string
      target_type: string
      target_id: string
      created_at: string
    }>
  >([])
  const [activeTab, setActiveTab] = useState<TabKey>('queue')
  const [integrations, setIntegrations] = useState<IntegrationGroup[]>([])
  const [integrationLoadError, setIntegrationLoadError] = useState('')
  const [integrationDrafts, setIntegrationDrafts] = useState<Record<string, string>>({})
  const [savingIntegration, setSavingIntegration] = useState(false)
  const [testingIntegration, setTestingIntegration] = useState<Record<string, boolean>>({})
  const [integrationTestResults, setIntegrationTestResults] = useState<
    Record<string, { ok: boolean; message: string; detail?: string }>
  >({})
  const [placeImports, setPlaceImports] = useState<PlaceImportBatch[]>([])
  const [selectedImportId, setSelectedImportId] = useState('')
  const [placeImportCandidates, setPlaceImportCandidates] = useState<PlaceImportCandidate[]>([])
  const [placeImportLoadError, setPlaceImportLoadError] = useState('')
  const [loadingPlaceCandidates, setLoadingPlaceCandidates] = useState(false)
  const [loading, setLoading] = useState(false)

  // Floating Toast Notification System (Zero Layout Shift)
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const [apiFailures, setApiFailures] = useState<string[]>([])
  const [showWarningDrawer, setShowWarningDrawer] = useState(false)

  // Create Provider State
  const [providerName, setProviderName] = useState('')
  const [providerEmail, setProviderEmail] = useState('')
  const [providerPassword, setProviderPassword] = useState('')
  const [providerAddress, setProviderAddress] = useState('')

  function addToast(type: 'success' | 'error' | 'warning', text: string, title?: string) {
    const id = Math.random().toString(36).slice(2, 9)
    const defaultTitle =
      type === 'success'
        ? 'Thao tác thành công'
        : type === 'warning'
        ? 'Cảnh báo hệ thống'
        : 'Có lỗi xảy ra'
    setToasts((prev) => [...prev, { id, type, title: title || defaultTitle, text }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 4500)
  }

  function notifySuccess(text: string, title?: string) {
    addToast('success', text, title)
  }

  function notifyError(text: string, title?: string) {
    addToast('error', text, title)
  }

  function notifyWarning(text: string, title?: string) {
    addToast('warning', text, title)
  }

  function describeLoadFailure(reason: unknown): string {
    if (!reason || typeof reason !== 'object') return 'Lỗi không xác định.'
    const failure = reason as {
      message?: string
      response?: {
        status?: number
        data?: {
          error?: { code?: string; message?: string }
          detail?: { code?: string; message?: string }
        }
      }
    }
    const response = failure.response
    const apiError = response?.data?.error || response?.data?.detail
    const code = apiError?.code ? ` [${apiError.code}]` : ''
    if (apiError?.message) return `${apiError.message}${code}`
    if (response?.status) return `API trả về HTTP ${response.status}${code}.`
    return failure.message || 'Không kết nối được API.'
  }

  async function load(preferLatestPlaceImport = false) {
    setLoading(true)
    const results = await Promise.allSettled([
      adminApi.dashboard(),
      adminApi.users(),
      adminApi.providers(),
      adminApi.moderation('pending'),
      adminApi.duplicates(),
      adminApi.audit(),
      adminApi.integrations(),
      adminApi.placeImports(),
    ])
    const failures: string[] = []
    const apply = <T,>(
      result: PromiseSettledResult<T>,
      label: string,
      update: (value: T) => void
    ) => {
      if (result.status === 'fulfilled') update(result.value)
      else failures.push(`${label}: ${describeLoadFailure(result.reason)}`)
    }

    apply(results[0], 'Tổng quan', setDashboard)
    apply(results[1], 'Người dùng', setUsers)
    apply(results[2], 'Cơ sở', setProviders)
    apply(results[3], 'Hàng chờ duyệt', (pending) =>
      setQueue({
        pois: pending.pois,
        experiences: pending.experiences,
        evidence: pending.evidence,
      })
    )
    apply(results[4], 'POI trùng', setDuplicates)
    apply(results[5], 'Nhật ký', setAudit)
    apply(results[6], 'Tích hợp & API keys', (integrationRows) => {
      setIntegrations(integrationRows)
      setIntegrationLoadError('')
      setIntegrationDrafts((previous) => {
        const next = { ...previous }
        for (const group of integrationRows) {
          for (const field of group.fields) {
            const name = `${group.service}.${field.key}`
            if (!field.secret) next[name] = field.value || ''
            else next[name] = ''
          }
        }
        return next
      })
    })
    apply(results[7], 'Place imports', (batches: PlaceImportBatch[]) => {
      setPlaceImports(batches)
      setSelectedImportId((current) =>
        preferLatestPlaceImport ? batches[0]?.id || '' : current || batches[0]?.id || ''
      )
    })

    if (results[6].status === 'rejected') {
      const detail = describeLoadFailure(results[6].reason)
      const status = (results[6].reason as { response?: { status?: number } })?.response?.status
      const migrationHint =
        status === 500
          ? ' Có thể database chưa cập nhật migration; hãy chạy `alembic upgrade head` trong apps/api rồi tải lại.'
          : ''
      setIntegrationLoadError(`${detail}${migrationHint}`)
    }

    setApiFailures(failures)
    setLoading(false)
  }

  useEffect(() => {
    void load()
  }, [])

  useEffect(() => {
    if (activeTab !== 'imports' || !selectedImportId) return
    let cancelled = false
    setLoadingPlaceCandidates(true)
    setPlaceImportLoadError('')
    adminApi
      .placeImportCandidates(selectedImportId)
      .then((rows: PlaceImportCandidate[]) => {
        if (!cancelled) setPlaceImportCandidates(rows)
      })
      .catch((reason: unknown) => {
        if (!cancelled) setPlaceImportLoadError(describeLoadFailure(reason))
      })
      .finally(() => {
        if (!cancelled) setLoadingPlaceCandidates(false)
      })
    return () => {
      cancelled = true
    }
  }, [activeTab, selectedImportId])

  async function review(kind: string, id: string, action: string) {
    try {
      await adminApi.review(kind, id, action, `Admin action: ${action}`)
      notifySuccess(`Đã thực hiện: ${action} cho ${kind}.`)
      await load()
    } catch {
      notifyError('Không thể lưu quyết định duyệt.')
    }
  }

  async function createProvider(event: FormEvent) {
    event.preventDefault()
    try {
      await adminApi.createProvider({
        name: providerName,
        email: providerEmail,
        password: providerPassword,
        address: providerAddress,
      })
      setProviderName('')
      setProviderEmail('')
      setProviderPassword('')
      setProviderAddress('')
      notifySuccess('Đã tạo hồ sơ cơ sở và tài khoản đối tác thành công!')
      await load()
    } catch {
      notifyError(
        'Tạo cơ sở thất bại. Email có thể đã được dùng hoặc mật khẩu chưa đủ 12 ký tự.'
      )
    }
  }

  async function changeRole(
    id: string,
    role: string,
    is_active: boolean,
    provider_id?: string | null
  ) {
    try {
      await adminApi.updateUser(id, {
        role,
        is_active,
        ...(role === 'provider' ? { provider_id: provider_id || providers[0]?.id } : {}),
      })
      notifySuccess('Đã cập nhật vai trò người dùng thành công.')
      await load()
    } catch {
      notifyError('Không thể cập nhật vai trò hoặc trạng thái tài khoản.')
    }
  }

  async function merge(pair: DuplicatePair) {
    const keep = window.prompt(
      `Nhập ID POI cần giữ lại (mặc định ${pair.poi_a.name})`,
      pair.poi_a.id
    )
    if (!keep) return
    const duplicate = keep === pair.poi_a.id ? pair.poi_b.id : pair.poi_a.id
    if (keep !== pair.poi_a.id && keep !== pair.poi_b.id) {
      notifyError('ID giữ lại phải là một trong hai POI đang được hiển thị.')
      return
    }
    const keepName = keep === pair.poi_a.id ? pair.poi_a.name : pair.poi_b.name
    const duplicateName = keep === pair.poi_a.id ? pair.poi_b.name : pair.poi_a.name
    if (
      !window.confirm(
        `Chuyển toàn bộ trải nghiệm/lịch sang “${keepName}” và ẩn “${duplicateName}”?`
      )
    )
      return
    try {
      await adminApi.mergeDuplicate(keep, duplicate, 'Admin xác nhận gộp cặp trùng')
      notifySuccess('Đã chuyển trải nghiệm/lịch sang POI giữ lại và ẩn POI trùng.')
      await load()
    } catch {
      notifyError('Không thể gộp hai POI này.')
    }
  }

  async function saveIntegration(group: IntegrationGroup, event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSavingIntegration(true)
    try {
      const values: Record<string, string> = {}
      for (const field of group.fields) {
        const draft = integrationDrafts[`${group.service}.${field.key}`]?.trim() || ''
        if (draft && (field.secret || draft !== (field.value || ''))) values[field.key] = draft
      }
      if (!Object.keys(values).length) {
        notifyWarning('Chưa có thay đổi mới để lưu. Ô bí mật để trống sẽ giữ nguyên khóa đang có.')
        return
      }
      await adminApi.updateIntegration(group.service, values)
      notifySuccess(
        `Đã lưu cấu hình ${group.service}. Khóa bí mật đã được mã hóa an toàn.`
      )
      await load()
    } catch (reason) {
      const detail = (reason as { response?: { data?: { error?: { message?: string } } } })?.response
        ?.data?.error?.message
      notifyError(detail || 'Không lưu được cấu hình tích hợp. Kiểm tra khóa mã hóa và giá trị.')
    } finally {
      setSavingIntegration(false)
    }
  }

  async function promotePlaceCandidate(
    candidate: PlaceImportCandidate,
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault()
    if (!selectedImportId) return
    const formData = new FormData(event.currentTarget)
    const observedAt = new Date(String(formData.get('observed_at') || ''))
    const expiresAt = new Date(String(formData.get('expires_at') || ''))
    if (Number.isNaN(observedAt.getTime()) || Number.isNaN(expiresAt.getTime())) {
      notifyError('Vui lòng nhập ngày quan sát và hạn dùng bằng chứng hợp lệ.')
      return
    }
    try {
      await adminApi.promotePlaceCandidate(selectedImportId, candidate.id, {
        address: String(formData.get('address') || ''),
        latitude: Number(formData.get('latitude')),
        longitude: Number(formData.get('longitude')),
        category: String(formData.get('category') || ''),
        source_uri: String(formData.get('source_uri') || ''),
        source_type: String(formData.get('source_type') || ''),
        source_label: String(formData.get('source_label') || ''),
        license: String(formData.get('license') || '') || null,
        fields_covered: ['name', 'address', 'latitude', 'longitude', 'category'],
        observed_at: observedAt.toISOString(),
        expires_at: expiresAt.toISOString(),
      })
      notifySuccess(
        `Đã gửi ${candidate.name} vào hàng chờ duyệt bằng chứng. Địa điểm sẽ hiển thị công khai sau khi duyệt.`
      )
      const rows = (await adminApi.placeImportCandidates(
        selectedImportId
      )) as PlaceImportCandidate[]
      setPlaceImportCandidates(rows)
    } catch (reason) {
      notifyError(describeLoadFailure(reason))
    }
  }

  async function testIntegration(group: IntegrationGroup) {
    setTestingIntegration((current) => ({ ...current, [group.service]: true }))
    setIntegrationTestResults((current) => ({
      ...current,
      [group.service]: { ok: false, message: 'Đang kiểm tra kết nối...' },
    }))
    try {
      const result = await adminApi.testIntegration(group.service)
      setIntegrationTestResults((current) => ({
        ...current,
        [group.service]: { ok: result.ok, message: result.message_vi, detail: result.detail_vi },
      }))
      if (result.ok) {
        notifySuccess(result.message_vi, `Kết nối ${group.service} OK`)
      } else {
        notifyWarning(result.message_vi, `Kết nối ${group.service} thất bại`)
      }
    } catch {
      setIntegrationTestResults((current) => ({
        ...current,
        [group.service]: {
          ok: false,
          message: 'Không thể kết nối tới dịch vụ.',
          detail: 'Kiểm tra máy chủ backend đang chạy và kết nối internet ổn định.',
        },
      }))
      notifyError('Kiểm tra kết nối thất bại.')
    } finally {
      setTestingIntegration((current) => ({ ...current, [group.service]: false }))
    }
  }

  async function removeIntegrationOverride(group: IntegrationGroup, field: IntegrationField) {
    if (
      !window.confirm(
        `Xóa cấu hình admin cho ${group.service}.${field.key}? Cấu hình sẽ quay về biến môi trường nếu có.`
      )
    )
      return
    setSavingIntegration(true)
    try {
      await adminApi.updateIntegration(group.service, {}, [field.key])
      notifySuccess(`Đã xóa override ${group.service}.${field.key}.`)
      await load()
    } catch (reason) {
      const detail = (reason as { response?: { data?: { error?: { message?: string } } } })?.response
        ?.data?.error?.message
      notifyError(detail || 'Không xóa được cấu hình tích hợp.')
    } finally {
      setSavingIntegration(false)
    }
  }

  const integrationTitle: Record<string, string> = {
    payments: 'Thanh toán · MoMo / VNPay',
    routing: 'Tuyến đường · Goong',
    ai: 'Chat AI · Gemini / OpenAI-compatible',
    google_oauth: 'Đăng nhập · Google OAuth',
  }

  const queueTotal = queue.pois.length + queue.experiences.length + queue.evidence.length
  const selectedImport = placeImports.find((batch) => batch.id === selectedImportId)
  const importFlagLabels: Record<string, string> = {
    source_url_missing: 'Thiếu URL nguồn',
    address_missing: 'Thiếu địa chỉ',
    address_geocode_needs_confirmation: 'Địa chỉ tra ngược, chưa xác nhận đúng POI',
    opening_hours_missing: 'Thiếu giờ mở cửa',
    price_basis_missing: 'Thiếu đơn vị/phạm vi giá',
    price_amount_unverified: 'Giá trong file chưa được kiểm chứng',
    photo_missing: 'Thiếu ảnh',
    coordinates_missing: 'Thiếu tọa độ',
    coordinates_reused: 'Tọa độ bị lặp',
    verified_flag_unsubstantiated: 'Cờ verified chưa có bằng chứng',
    field_level_evidence_pending: 'Chưa duyệt bằng chứng theo từng trường',
  }

  // Display metrics mapping
  const metricsToDisplay =
    Object.keys(dashboard).length > 0
      ? Object.entries(dashboard).map(([key, value]) => {
          const conf = METRIC_CONFIG[key] || {
            label: key.replaceAll('_', ' ').toUpperCase(),
            icon: Activity,
            colorClass: 'cyan',
            hint: 'Chỉ số hệ thống',
          }
          return { key, value, ...conf }
        })
      : [
          {
            key: 'users',
            value: users.length,
            label: 'Người dùng',
            icon: Users,
            colorClass: 'cyan',
            hint: 'Tài khoản trong hệ thống',
          },
          {
            key: 'providers',
            value: providers.length,
            label: 'Cơ sở đối tác',
            icon: Building,
            colorClass: 'emerald',
            hint: 'Doanh nghiệp & xưởng',
          },
          {
            key: 'pending_pois',
            value: queue.pois.length,
            label: 'POI chờ duyệt',
            icon: MapPinned,
            colorClass: 'amber',
            hint: 'Địa điểm cần xác minh',
          },
          {
            key: 'pending_experiences',
            value: queue.experiences.length,
            label: 'Trải nghiệm chờ duyệt',
            icon: Compass,
            colorClass: 'purple',
            hint: 'Hoạt động & workshop',
          },
        ]

  return (
    <div className="admin-page-3d page-wrap">
      {/* Floating Toast Notification Container (Zero layout shift) */}
      <div className="admin-toast-container" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`admin-toast-item ${toast.type}`}>
            {toast.type === 'success' ? (
              <CheckCircle2
                size={18}
                className="text-emerald"
                style={{ flexShrink: 0, marginTop: 1 }}
              />
            ) : toast.type === 'warning' ? (
              <AlertTriangle
                size={18}
                className="text-amber"
                style={{ flexShrink: 0, marginTop: 1 }}
              />
            ) : (
              <AlertCircle
                size={18}
                className="text-rose"
                style={{ flexShrink: 0, marginTop: 1 }}
              />
            )}
            <div className="admin-toast-content">
              <div className="admin-toast-title">{toast.title}</div>
              <div className="admin-toast-body">{toast.text}</div>
            </div>
            <button
              type="button"
              className="admin-toast-close"
              onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
              aria-label="Đóng thông báo"
            >
              <X size={14} />
            </button>
            <div className="admin-toast-progress">
              <div className="admin-toast-progress-bar" />
            </div>
          </div>
        ))}
      </div>

      {/* Hero Header Card */}
      <div className="admin-hero-card">
        <div className="admin-hero-top">
          <div className="portal-live-badge">
            <span className="portal-live-dot" />
            <span>TRUNG TÂM QUẢN TRỊ TOÀN DIỆN · LOCAL EXPLORER AI</span>
          </div>

          <div className="admin-hero-actions">
            {apiFailures.length > 0 ? (
              <button
                type="button"
                className="admin-health-badge warning"
                onClick={() => setShowWarningDrawer((v) => !v)}
                title="Nhấn để xem chi tiết cảnh báo kết nối API"
              >
                <AlertTriangle size={13} />
                <span>{apiFailures.length} cảnh báo kết nối API</span>
                {showWarningDrawer ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
            ) : (
              <div className="admin-health-badge healthy">
                <span className="admin-health-dot" />
                <span>Hệ thống trực tuyến</span>
              </div>
            )}

            <button
              type="button"
              className="btn-secondary-3d btn-sm"
              onClick={() => void load(true)}
              disabled={loading}
            >
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
              <span>Làm mới dữ liệu</span>
            </button>
          </div>
        </div>

        <h1 className="admin-hero-title">
          Điều hành & Kiểm toán <em>Toàn hệ thống.</em>
        </h1>
        <p className="admin-hero-desc">
          Kiểm duyệt dữ liệu POI thực tế, rà soát trùng lặp không gian, quản lý phân quyền đối tác và
          theo dõi cấu hình hạ tầng tích hợp AI thời gian thực.
        </p>
      </div>

      {/* Collapsible Warning Drawer for Background API Failures (Zero Layout Shift on normal loads) */}
      {showWarningDrawer && apiFailures.length > 0 && (
        <div className="admin-warning-drawer animate-fadeIn">
          <div className="admin-warning-drawer-header">
            <span className="admin-warning-drawer-title">
              <AlertTriangle size={16} /> Chi tiết sự cố kết nối API ({apiFailures.length})
            </span>
            <button
              type="button"
              className="admin-toast-close"
              onClick={() => setShowWarningDrawer(false)}
              aria-label="Đóng"
            >
              <X size={15} />
            </button>
          </div>
          <div className="admin-warning-list">
            {apiFailures.map((failure, idx) => (
              <div key={idx}>• {failure}</div>
            ))}
          </div>
        </div>
      )}

      {/* KPI Metrics Dashboard Cards */}
      <div className="admin-metrics-grid">
        {metricsToDisplay.map((item) => {
          const Icon = item.icon
          return (
            <TiltCard3D key={item.key} maxTilt={6} className="admin-kpi-card">
              <div className="admin-kpi-top">
                <span className="admin-kpi-label">{item.label}</span>
                <div className={`admin-kpi-icon ${item.colorClass}`}>
                  <Icon size={17} />
                </div>
              </div>
              <strong className="admin-kpi-value">{item.value}</strong>
              <div className="admin-kpi-hint">
                <span>{item.hint}</span>
              </div>
            </TiltCard3D>
          )
        })}
      </div>

      {/* Tab Navigation Strip */}
      <div className="admin-tab-strip">
        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'queue' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('queue')}
        >
          <Layers size={14} />
          <span>{t('admin.tabQueue')}</span>
          {queueTotal > 0 && <span className="admin-tab-badge">{queueTotal}</span>}
        </button>

        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'imports' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('imports')}
        >
          <FileSpreadsheet size={14} />
          <span>{t('admin.tabPlaceImports')}</span>
          {placeImports.reduce((sum, batch) => sum + batch.record_count, 0) > 0 && (
            <span className="admin-tab-badge badge-warn">
              {placeImports.reduce((sum, batch) => sum + batch.record_count, 0)}
            </span>
          )}
        </button>

        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'duplicates' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('duplicates')}
        >
          <GitMerge size={14} />
          <span>{t('admin.tabDuplicates')}</span>
          {duplicates.length > 0 && (
            <span className="admin-tab-badge badge-warn">{duplicates.length}</span>
          )}
        </button>

        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'providers' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('providers')}
        >
          <Building size={14} />
          <span>{t('admin.tabProviders')}</span>
          {providers.length > 0 && <span className="admin-tab-badge">{providers.length}</span>}
        </button>

        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'users' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          <Users size={14} />
          <span>
            {t('admin.tabUsers')} ({users.length})
          </span>
        </button>

        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'audit' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          <History size={14} />
          <span>
            {t('admin.tabAudit')} ({audit.length})
          </span>
        </button>

        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'integrations' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('integrations')}
        >
          <KeyRound size={14} />
          <span>Tích hợp & API keys</span>
        </button>

        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'operations' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('operations')}
        >
          <Activity size={14} />
          <span>Vận hành</span>
        </button>

        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'ai-tools' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('ai-tools')}
        >
          <Brain size={14} />
          <span>Công cụ AI</span>
        </button>

        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'flood-risk' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('flood-risk')}
        >
          <MapPinned size={14} />
          <span>Rủi ro ngập</span>
        </button>
      </div>

      {/* Tab Panels */}
      {activeTab === 'operations' && <AdminOperationsPanel />}
      {activeTab === 'ai-tools' && <AdminAiToolsPanel />}
      {activeTab === 'flood-risk' && <AdminFloodRiskPanel />}

      {/* Tab: Place Imports */}
      {activeTab === 'imports' && (
        <div className="admin-tab-content animate-fadeIn">
          <div className="inline-alert-3d mb-6">
            <AlertCircle size={16} />
            <span>
              Dữ liệu ở đây chỉ là bản ghi nguồn chờ bổ sung, chưa phải POI vận hành và không xuất hiện
              trong tìm kiếm/lập lịch. Không duyệt cờ verified từ Excel nếu thiếu URL nguồn và bằng
              chứng hiện hành.
            </span>
          </div>
          {placeImports.length === 0 ? (
            <section className="admin-section-card">
              <p className="admin-empty-text">Chưa có lô dữ liệu POI nào được nhập.</p>
            </section>
          ) : (
            <>
              <section className="admin-section-card mb-6">
                <div className="admin-section-header">
                  <h3>Danh sách địa điểm chờ bổ sung</h3>
                  <p>
                    {selectedImport?.source_name} · Sheet {selectedImport?.worksheet_name} ·{' '}
                    {selectedImport?.record_count} dòng
                  </p>
                </div>
                <label className="field-group-3d">
                  <span>Lô dữ liệu</span>
                  <select
                    value={selectedImportId}
                    onChange={(event) => setSelectedImportId(event.target.value)}
                  >
                    {placeImports.map((batch) => (
                      <option key={batch.id} value={batch.id}>
                        {batch.source_name} ({batch.record_count}) ·{' '}
                        {new Date(batch.created_at).toLocaleString('vi-VN')} ·{' '}
                        {batch.source_sha256.slice(0, 8)}
                      </option>
                    ))}
                  </select>
                </label>
                {selectedImport && (
                  <div className="admin-metrics-grid" style={{ marginTop: 18 }}>
                    {(
                      [
                        ['Thiếu địa chỉ', 'address_missing'],
                        ['Tọa độ dùng lại', 'coordinates_reused'],
                        ['Thiếu giờ mở cửa', 'opening_hours_missing'],
                        ['Thiếu URL nguồn', 'source_url_missing'],
                        ['Thiếu cơ sở giá', 'price_basis_missing'],
                        ['Giá chưa xác minh', 'price_amount_unverified'],
                        ['Địa chỉ cần đối chiếu', 'address_geocode_needs_confirmation'],
                        ['Bằng chứng theo trường còn thiếu', 'field_level_evidence_pending'],
                        ['Cờ verified thiếu chứng cứ', 'verified_flag_unsubstantiated'],
                        ['Cờ verified trong file', 'source_verified_true'],
                      ] as const
                    ).map(([label, key]) => (
                      <div className="admin-kpi-card" key={key}>
                        <small className="admin-kpi-label">{label}</small>
                        <strong className="admin-kpi-value">
                          {Number(selectedImport.quality_summary[key] || 0)}
                        </strong>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {placeImportLoadError && (
                <div className="inline-alert-3d mb-6">
                  <AlertCircle size={16} />
                  <span>{placeImportLoadError}</span>
                </div>
              )}
              {loadingPlaceCandidates ? (
                <section className="admin-section-card">
                  <p className="admin-empty-text">Đang tải bản ghi nguồn…</p>
                </section>
              ) : (
                <section className="admin-section-card">
                  <div className="admin-section-header">
                    <h3>Bản ghi nguồn ({placeImportCandidates.length})</h3>
                  </div>
                  <div className="moderation-items-list">
                    {placeImportCandidates.map((candidate) => {
                      const raw = candidate.raw_payload
                      const sourceDetails = (raw.details && typeof raw.details === 'object'
                        ? raw.details
                        : {}) as Record<string, unknown> & { osm_tags: Record<string, unknown> }
                      const sourcePhotos = Array.isArray(sourceDetails.images)
                        ? sourceDetails.images.filter((photo): photo is Record<string, unknown> => Boolean(photo && typeof photo === 'object'))
                        : []
                      const sourceOsmTags = sourceDetails.osm_tags && typeof sourceDetails.osm_tags === 'object'
                        ? sourceDetails.osm_tags as Record<string, unknown>
                        : {}
                      const suggested = candidate.suggested_labels
                      const tags = Array.isArray(raw.tags)
                        ? raw.tags.map(String).join(', ')
                        : String(raw.tags || '')
                      const intentLabels: Record<string, string> = {
                        handicraft: 'Thủ công',
                        food: 'Ẩm thực',
                        culture: 'Văn hóa',
                        relaxation: 'Thư giãn',
                        shopping: 'Mua sắm',
                        entertainment: 'Giải trí',
                        accommodation: 'Lưu trú',
                        sightseeing: 'Tham quan',
                      }
                      return (
                        <details key={candidate.id} className="moderation-item-card">
                          <summary className="item-meta-info" style={{ cursor: 'pointer' }}>
                            <strong>{candidate.name}</strong>
                            <div className="item-sub-meta">
                              <span>{candidate.kind}</span>
                              <span>Dòng Excel {candidate.source_row}</span>
                              <span className="item-status-pill">
                                {candidate.target_poi_status === 'verified'
                                  ? 'Verified and public'
                                  : candidate.target_poi_id
                                  ? 'Awaiting evidence review'
                                  : 'Needs enrichment'}
                              </span>
                              <span>{candidate.quality_flags.length} cảnh báo</span>
                            </div>
                            <div className="item-sub-meta">
                              {candidate.quality_flags.map((flag) => (
                                <span key={flag}>{importFlagLabels[flag] || flag}</span>
                              ))}
                            </div>
                            {suggested?.intent_columns ? (
                              <div className="place-intent-columns place-intent-columns-compact">
                                {PLACE_CORE_INTENT_COLUMNS.map(({ key, label }) => (
                                  <span
                                    className={`place-intent-cell ${suggested.intent_columns[key] ? 'is-suggested' : 'is-not-suggested'}`}
                                    key={key}
                                  >
                                    <strong>{label}</strong>
                                    <small>{suggested.intent_columns[key] ? 'Có dấu hiệu nguồn' : 'Chưa thấy trong nguồn'}</small>
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <div className="item-sub-meta place-label-tags">
                                <span>Nhãn 4 mục đích chưa được API trả về. Khởi động lại API để tải nhãn mới.</span>
                              </div>
                            )}
                          </summary>
                          {suggested ? (
                          <div className="place-label-suggestion-panel">
                            <strong>Nhãn phân loại gợi ý · {suggested.ruleset_version}</strong>
                            <div className="item-sub-meta">
                              <span>Loại POI: {suggested.poi_type_label_vi}</span>
                              <span>Loại hoạt động: {PLACE_ACTIVITY_MODE_LABELS[suggested.activity_mode] || suggested.activity_mode}</span>
                              <span>
                                Mục đích chính: {suggested.primary_intent
                                  ? intentLabels[suggested.primary_intent] || suggested.primary_intent
                                  : 'Chưa khớp 4 mục đích cốt lõi'}
                              </span>
                              <span>
                                Hands-on: {suggested.hands_on === true
                                  ? 'Có dấu hiệu tham gia trực tiếp trong mô tả'
                                  : 'Chưa xác định ở cấp địa điểm'}
                              </span>
                              <span>
                                Không gian: {suggested.indoor_outdoor === 'outdoor'
                                  ? 'Ngoài trời theo cột nguồn'
                                  : suggested.indoor_outdoor === 'indoor'
                                  ? 'Trong nhà theo cột nguồn'
                                  : 'Chưa rõ'}
                              </span>
                            </div>
                            <div className="place-intent-columns">
                              {PLACE_CORE_INTENT_COLUMNS.map(({ key, label }) => (
                                <span
                                  className={`place-intent-cell ${suggested.intent_columns?.[key] ? 'is-suggested' : 'is-not-suggested'}`}
                                  key={key}
                                >
                                  <strong>{label}</strong>
                                  <small>{suggested.intent_columns?.[key] ? 'Có dấu hiệu trong nguồn' : 'Chưa thấy dấu hiệu trong nguồn'}</small>
                                </span>
                              ))}
                            </div>
                            <div className="item-sub-meta place-label-tags">
                              {(suggested.intent_tags || []).map((tag) => (
                                <span key={tag}>{intentLabels[tag] || tag}</span>
                              ))}
                            </div>
                            <small>{suggested.warning}</small>
                          </div>
                          ) : (
                            <div className="place-label-suggestion-panel">
                              <strong>Chưa có nhãn gợi ý từ API</strong>
                              <small>
                                Bản ghi này dùng phản hồi API cũ hoặc thiếu trường nhãn. Khởi động lại API rồi tải lại trang để nhận nhãn phân loại.
                              </small>
                            </div>
                          )}
                          {candidate.review_status === 'needs_enrichment' && (
                            <form
                              className="form-fields-grid-2"
                              style={{ marginTop: 18 }}
                              onSubmit={(event) => void promotePlaceCandidate(candidate, event)}
                            >
                              <h4 style={{ gridColumn: '1 / -1' }}>
                                Enrich and submit POI evidence for review
                              </h4>
                              <label className="field-group-3d">
                                <span>Address suggestion (verify against source)</span>
                                <input
                                  name="address"
                                  defaultValue={String(raw.address || '')}
                                  required
                                  minLength={5}
                                  maxLength={300}
                                />
                              </label>
                              <label className="field-group-3d">
                                <span>Latitude (re-enter and verify)</span>
                                <input
                                  name="latitude"
                                  type="number"
                                  min={-90}
                                  max={90}
                                  step="any"
                                  required
                                  defaultValue={String(raw.lat ?? '')}
                                />
                              </label>
                              <label className="field-group-3d">
                                <span>Longitude (re-enter and verify)</span>
                                <input
                                  name="longitude"
                                  type="number"
                                  min={-180}
                                  max={180}
                                  step="any"
                                  required
                                  defaultValue={String(raw.lon ?? '')}
                                />
                              </label>
                              <label className="field-group-3d">
                                <span>Verified category</span>
                                <input
                                  name="category"
                                  defaultValue={candidate.kind}
                                  required
                                  minLength={2}
                                  maxLength={40}
                                />
                              </label>
                              <label className="field-group-3d">
                                <span>HTTPS source URL</span>
                                <input
                                  name="source_uri"
                                  type="url"
                                  required
                                  placeholder="https://..."
                                  defaultValue={String(raw.source || '')}
                                />
                              </label>
                              <label className="field-group-3d">
                                <span>Source type</span>
                                <select name="source_type" defaultValue={String(raw.source_type || 'dataset')}>
                                  <option value="official">Official</option>
                                  <option value="provider">Provider</option>
                                  <option value="website">Website</option>
                                  <option value="dataset">Sourced dataset</option>
                                  <option value="field_check">Field check</option>
                                </select>
                              </label>
                              <label className="field-group-3d">
                                <span>Source label / verifier</span>
                                <input
                                  name="source_label"
                                  required
                                  minLength={2}
                                  maxLength={180}
                                  defaultValue={String(raw.source_label || 'OpenStreetMap contributors')}
                                />
                              </label>
                              <label className="field-group-3d">
                                <span>License (optional)</span>
                                <input name="license" maxLength={120} defaultValue={String(raw.license || 'ODbL-1.0')} />
                              </label>
                              <label className="field-group-3d">
                                <span>Observed at</span>
                                <input name="observed_at" type="datetime-local" required defaultValue={toDateTimeLocal(raw.source_observed_at)} />
                              </label>
                              <label className="field-group-3d">
                                <span>Evidence expires at</span>
                                <input name="expires_at" type="datetime-local" required />
                              </label>
                              <label
                                className="field-group-3d"
                                style={{ gridColumn: '1 / -1' }}
                              >
                                <span>
                                  <input type="checkbox" name="source_confirmed" required /> I
                                  checked that this source supports the POI name, address,
                                  coordinates, and category.
                                </span>
                              </label>
                              <button
                                className="btn-primary-3d btn-sm"
                                type="submit"
                                style={{ gridColumn: '1 / -1' }}
                              >
                                <Check size={14} /> Submit for moderation
                              </button>
                            </form>
                          )}
                          <div className="item-sub-meta" style={{ marginTop: 12 }}>
                            <span>ID nguồn: {candidate.external_id}</span>
                            <span>
                              Tọa độ trong file: {String(raw.lat ?? 'trống')},{' '}
                              {String(raw.lon ?? 'trống')}
                            </span>
                            <span>
                              Giá trong file: {String(raw.price_vnd ?? 'trống')} VND · cơ sở:{' '}
                              {String(raw.price_basis || 'chưa có')} · đơn vị:{' '}
                              {String(raw.price_unit || 'chưa rõ')}
                            </span>
                            {Boolean(raw.address) && (
                              <span>Địa chỉ Goong gợi ý: {String(raw.address)}</span>
                            )}
                            {Boolean(raw.address_source_reference) && (
                              <span>Nguồn địa chỉ: {String(raw.address_source_reference)}</span>
                            )}
                            {Boolean(raw.address_status) && (
                              <span>Trạng thái địa chỉ: {String(raw.address_status)}</span>
                            )}
                            {Boolean(raw.price_status) && (
                              <span>Trạng thái giá: {String(raw.price_status)}</span>
                            )}
                            {Boolean(raw.verification_basis) && (
                              <span>Căn cứ cờ xác minh: {String(raw.verification_basis)}</span>
                            )}
                            {Boolean(raw.evidence_status) && (
                              <span>Bằng chứng: {String(raw.evidence_status)}</span>
                            )}
                            <span>Cờ verified gốc trong Excel: {String(raw.verified ?? false)}</span>
                            <span>Nguồn ghi trong file: {String(raw.source || 'không có')}</span>
                            <span>Tags: {tags || 'không có'}</span>
                            {Boolean(raw.description) && <span>{String(raw.description)}</span>}
                            {Boolean(sourceDetails.opening_hours) && <span>opening_hours (OSM): {String(sourceDetails.opening_hours)}</span>}
                            {Boolean(sourceDetails.contact_phone) && <span>phone (OSM): {String(sourceDetails.contact_phone)}</span>}
                            {Boolean(sourceDetails.website) && <span>website (OSM): {String(sourceDetails.website)}</span>}
                            {Boolean(sourceDetails.fee) && <span>fee (OSM): {String(sourceDetails.fee)}</span>}
                            {Boolean(sourceDetails.observed_at) && <span>Thời điểm crawl: {String(sourceDetails.observed_at)}</span>}
                            {sourcePhotos.map((photo, index) => (
                              <a key={`${String(photo.source_url || photo.url)}-${index}`} href={String(photo.source_url || photo.url || '#')} target="_blank" rel="noreferrer">
                                Ảnh nguồn: {String(photo.title || 'Wikimedia Commons')} · {String(photo.license || 'không có thông tin giấy phép')}
                              </a>
                            ))}
                            {Object.keys(sourceOsmTags).length > 0 && (
                              <details>
                                <summary>Toàn bộ tags OSM ({Object.keys(sourceDetails.osm_tags).length})</summary>
                                <pre>{JSON.stringify(sourceDetails.osm_tags, null, 2)}</pre>
                              </details>
                            )}
                            {Boolean(raw.note) && <span>Ghi chú nguồn: {String(raw.note)}</span>}
                          </div>
                        </details>
                      )
                    })}
                    {!placeImportCandidates.length && (
                      <p className="admin-empty-text">Lô này chưa có bản ghi.</p>
                    )}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      )}

      {/* Tab: Moderation Queue */}
      {activeTab === 'queue' && (
        <div className="admin-tab-content animate-fadeIn">
          <div className="inline-alert-3d mb-6">
            <AlertCircle size={16} />
            <span>
              Dữ liệu mô phỏng không được duyệt thành dữ liệu vận hành. Chỉ duyệt sau khi nguồn bao
              phủ đủ trường, đúng phiên bản và còn hạn.
            </span>
          </div>
          {(['pois', 'experiences', 'evidence'] as const).map((kind) => (
            <section key={kind} className="admin-section-card mb-6">
              <div className="admin-section-header">
                <h3>
                  Hạng mục: <span className="text-emerald uppercase">{kind}</span> (
                  {queue[kind].length})
                </h3>
              </div>

              {queue[kind].length > 0 ? (
                <div className="moderation-items-list">
                  {queue[kind].map((item) => (
                    <div key={item.id} className="moderation-item-card">
                      <div className="item-meta-info">
                        <strong>{item.name || item.title || item.source_uri}</strong>
                        <div className="item-sub-meta">
                          <span className="item-status-pill">{item.status}</span>
                          <span className="item-id-snippet">ID: {item.id.slice(0, 10)}</span>
                        </div>
                        {kind === 'evidence' && (
                          <div className="item-sub-meta">
                            <span>
                              {item.source_type || 'source'} · {item.target_type || 'no target'}
                            </span>
                            <span>Fields: {(item.fields_covered || []).join(', ') || 'none'}</span>
                            <span>License: {item.license || 'not specified'}</span>
                            <span>Target: {item.target_id || 'unlinked'}</span>
                            <span>
                              Observed:{' '}
                              {item.observed_at ? new Date(item.observed_at).toLocaleString() : 'missing'}
                            </span>
                            <span>
                              Expires:{' '}
                              {item.expires_at ? new Date(item.expires_at).toLocaleString() : 'missing'}
                            </span>
                            {item.source_uri && (
                              <a href={item.source_uri} target="_blank" rel="noreferrer">
                                Open source
                              </a>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="item-action-btns">
                        <button
                          type="button"
                          className="btn-action-approve"
                          onClick={() =>
                            void review(
                              kind === 'pois'
                                ? 'poi'
                                : kind === 'experiences'
                                ? 'experience'
                                : 'evidence',
                              item.id,
                              'approve'
                            )
                          }
                        >
                          <Check size={14} /> Duyệt
                        </button>
                        <button
                          type="button"
                          className="btn-action-reject"
                          onClick={() =>
                            void review(
                              kind === 'pois'
                                ? 'poi'
                                : kind === 'experiences'
                                ? 'experience'
                                : 'evidence',
                              item.id,
                              'reject'
                            )
                          }
                        >
                          <X size={14} /> Từ chối
                        </button>
                        <button
                          type="button"
                          className="btn-action-hide"
                          onClick={() =>
                            void review(
                              kind === 'pois'
                                ? 'poi'
                                : kind === 'experiences'
                                ? 'experience'
                                : 'evidence',
                              item.id,
                              'hide'
                            )
                          }
                        >
                          <EyeOff size={14} /> Ẩn
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="admin-empty-text">Không có mục nào đang chờ duyệt.</p>
              )}
            </section>
          ))}
        </div>
      )}

      {/* Tab: Duplicates Detection */}
      {activeTab === 'duplicates' && (
        <div className="admin-tab-content animate-fadeIn">
          <section className="admin-section-card">
            <div className="admin-section-header">
              <h3>Các cặp địa điểm (POI) có khả năng trùng lặp ({duplicates.length})</h3>
              <p>Thuật toán phát hiện dựa trên khoảng cách địa lý và độ tương đồng tên gọi.</p>
            </div>

            {duplicates.length > 0 ? (
              <div className="duplicate-pairs-list">
                {duplicates.map((pair) => (
                  <div key={`${pair.poi_a.id}-${pair.poi_b.id}`} className="duplicate-pair-card">
                    <div className="pair-names-comparison">
                      <div className="poi-item-box">
                        <small>POI A</small>
                        <strong>{pair.poi_a.name}</strong>
                      </div>
                      <div className="similarity-meter">
                        <span className="sim-percent">
                          {Math.round(pair.name_similarity * 100)}%
                        </span>
                        <small>Trùng tên</small>
                      </div>
                      <div className="poi-item-box">
                        <small>POI B</small>
                        <strong>{pair.poi_b.name}</strong>
                      </div>
                    </div>

                    <button
                      type="button"
                      className="btn-primary-3d btn-sm"
                      onClick={() => void merge(pair)}
                    >
                      <GitMerge size={14} /> Gộp cặp này...
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="admin-empty-text">Chưa phát hiện cặp tên hoặc tọa độ trùng nhau.</p>
            )}
          </section>
        </div>
      )}

      {/* Tab: Create Provider */}
      {activeTab === 'providers' && (
        <div className="admin-tab-content animate-fadeIn">
          <section className="form-card-3d mb-6">
            <div className="form-card-header">
              <span className="step-num">
                <Plus size={16} />
              </span>
              <div>
                <h2>Tạo cơ sở đối tác & Tài khoản quản lý</h2>
                <p>Khởi tạo thông tin cơ sở mới và tài khoản đối tác để bàn giao quyền quản lý.</p>
              </div>
            </div>

            <form className="form-fields-grid-2" onSubmit={createProvider}>
              <label className="field-group-3d">
                <span>Tên cơ sở / Doanh nghiệp</span>
                <input
                  required
                  value={providerName}
                  onChange={(e) => setProviderName(e.target.value)}
                  placeholder="Ví dụ: Xưởng Gốm Thủ Công Sài Gòn"
                />
              </label>

              <label className="field-group-3d">
                <span>Email đăng nhập cơ sở</span>
                <input
                  required
                  type="email"
                  value={providerEmail}
                  onChange={(e) => setProviderEmail(e.target.value)}
                  placeholder="partner@example.com"
                />
              </label>

              <label className="field-group-3d">
                <span>Mật khẩu tạm thời (ít nhất 12 ký tự)</span>
                <input
                  required
                  minLength={12}
                  type="password"
                  autoComplete="new-password"
                  value={providerPassword}
                  onChange={(e) => setProviderPassword(e.target.value)}
                  placeholder="Mật khẩu ít nhất 12 ký tự..."
                />
              </label>

              <label className="field-group-3d">
                <span>Địa chỉ cơ sở</span>
                <input
                  value={providerAddress}
                  onChange={(e) => setProviderAddress(e.target.value)}
                  placeholder="Số nhà, đường, phường, quận..."
                />
              </label>

              <div style={{ gridColumn: '1 / -1', marginTop: 12 }}>
                <button className="btn-primary-3d" type="submit">
                  <span>Tạo Cơ Sở & Tài Khoản Ngay</span>
                </button>
              </div>
            </form>
          </section>

          {/* List of existing providers */}
          <section className="admin-section-card">
            <div className="admin-section-header">
              <h3>Danh sách cơ sở đối tác ({providers.length})</h3>
            </div>
            {providers.length > 0 ? (
              <div className="users-table-list">
                {providers.map((p) => (
                  <div key={p.id} className="user-row-card">
                    <div className="user-details-col">
                      <strong>{p.name}</strong>
                      <small>ID: {p.id}</small>
                    </div>
                    <span className="portal-badge-pill badge-emerald">
                      <CheckCircle2 size={12} /> Đang hoạt động
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="admin-empty-text">Chưa có cơ sở nào được tạo.</p>
            )}
          </section>
        </div>
      )}

      {/* Tab: User & Role Management */}
      {activeTab === 'users' && (
        <div className="admin-tab-content animate-fadeIn">
          <section className="admin-section-card">
            <div className="admin-section-header">
              <h3>Danh sách người dùng & Phân quyền hệ thống ({users.length})</h3>
            </div>

            <div className="users-table-list">
              {users.map((account) => (
                <div key={account.id} className="user-row-card">
                  <div className="user-details-col">
                    <strong>{account.display_name || 'Chưa đặt tên'}</strong>
                    <small>{account.email}</small>
                  </div>

                  <div className="user-role-control">
                    <label className="user-control-label">Vai trò:</label>
                    <select
                      value={account.role}
                      onChange={(e) =>
                        void changeRole(
                          account.id,
                          e.target.value,
                          account.is_active,
                          account.provider_id
                        )
                      }
                      className="admin-select"
                    >
                      <option value="traveler">Du khách (traveler)</option>
                      <option value="provider">Cơ sở (provider)</option>
                      <option value="admin">Quản trị viên (admin)</option>
                    </select>

                    {account.role === 'provider' && (
                      <select
                        value={account.provider_id || ''}
                        onChange={(e) =>
                          void changeRole(
                            account.id,
                            account.role,
                            account.is_active,
                            e.target.value
                          )
                        }
                        className="admin-select"
                      >
                        <option value="">Gán cơ sở...</option>
                        {providers.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  <label className="user-active-toggle">
                    <input
                      type="checkbox"
                      checked={account.is_active}
                      onChange={(e) =>
                        void changeRole(
                          account.id,
                          account.role,
                          e.target.checked,
                          account.provider_id
                        )
                      }
                    />
                    <span>Hoạt động</span>
                  </label>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}

      {/* Tab: Audit Log */}
      {activeTab === 'audit' && (
        <div className="admin-tab-content animate-fadeIn">
          <section className="admin-section-card">
            <div className="admin-section-header">
              <h3>Nhật ký hoạt động & Kiểm toán bảo mật ({audit.length})</h3>
            </div>

            <div className="audit-table-list">
              {audit.map((row) => (
                <div key={row.id} className="audit-entry-row">
                  <span className="audit-entry-time">
                    {new Date(row.created_at).toLocaleString('vi-VN')}
                  </span>
                  <span className="audit-entry-action">{row.action}</span>
                  <span className="audit-entry-target">
                    {row.target_type} / {row.target_id.slice(0, 8)}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}

      {/* Tab: Integrations & API Keys */}
      {activeTab === 'integrations' && (
        <div className="admin-tab-content animate-fadeIn">
          {integrationLoadError && (
            <div className="inline-alert-3d mb-6" role="alert">
              <AlertCircle size={16} className="text-amber" />
              <span>Không tải được cấu hình tích hợp: {integrationLoadError}</span>
            </div>
          )}
          <div className="inline-alert-3d mb-6">
            <AlertCircle size={16} />
            <span>
              Khóa được mã hóa trong cơ sở dữ liệu bằng INTEGRATION_SECRETS_KEY ở môi trường máy chủ.
              Ô bí mật luôn để trống khi tải; lưu ô trống giữ khóa cũ. Không nhập khóa vào log hoặc
              chia sẻ qua chat.
            </span>
          </div>
          {integrations.map((group) => (
            <form
              key={group.service}
              className="admin-section-card integration-config-card mb-6"
              onSubmit={(event) => void saveIntegration(group, event)}
            >
              <input
                type="text"
                name="username"
                autoComplete="username"
                style={{ display: 'none' }}
                aria-hidden="true"
                tabIndex={-1}
              />
              <div className="admin-section-header">
                <h3>{integrationTitle[group.service] || group.service}</h3>
                <p>
                  Override đã mã hóa được ưu tiên hơn biến môi trường. Xóa override sẽ quay về giá trị
                  môi trường nếu có.
                </p>
              </div>
              <div className="integration-config-grid">
                {group.fields.map((field) => {
                  const id = `${group.service}.${field.key}`
                  const fallback =
                    field.key === 'provider'
                      ? group.service === 'payments'
                        ? 'vnpay'
                        : group.service === 'routing'
                        ? 'goong'
                        : 'openai'
                      : field.key.endsWith('environment')
                      ? 'sandbox'
                      : ''
                  const value = integrationDrafts[id] ?? field.value ?? fallback
                  const choices =
                    group.service === 'payments' && field.key === 'provider'
                      ? [
                          ['vnpay', 'VNPay'],
                          ['momo', 'MoMo'],
                        ]
                      : group.service === 'payments' && field.key.endsWith('environment')
                      ? [
                          ['sandbox', 'Sandbox'],
                          ['production', 'Production'],
                        ]
                      : group.service === 'routing' && field.key === 'provider'
                      ? [['goong', 'Goong']]
                      : group.service === 'routing' && field.key === 'geocoding_provider'
                      ? [['goong', 'Goong']]
                      : group.service === 'ai' && field.key === 'provider'
                      ? [
                          ['openai', 'OpenAI-compatible'],
                          ['gemini', 'Gemini'],
                        ]
                      : null
                  return (
                    <div className="integration-setting-field" key={field.key}>
                      <label className="field-group-3d">
                        <span>{field.label}</span>
                        {choices ? (
                          <select
                            value={value}
                            onChange={(event) =>
                              setIntegrationDrafts({
                                ...integrationDrafts,
                                [id]: event.target.value,
                              })
                            }
                          >
                            {choices.map(([choice, label]) => (
                              <option key={choice} value={choice}>
                                {label}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <input
                            type={
                              field.secret
                                ? 'password'
                                : field.key.endsWith('_url') ||
                                  field.key.endsWith('_uri') ||
                                  field.key.endsWith('_base_url')
                                ? 'url'
                                : 'text'
                            }
                            autoComplete={field.secret ? 'new-password' : 'off'}
                            value={value}
                            placeholder={
                              field.secret && field.configured
                                ? 'Đã có khóa · để trống để giữ nguyên'
                                : field.secret
                                ? 'Nhập khóa mới'
                                : 'Chưa cấu hình'
                            }
                            onChange={(event) =>
                              setIntegrationDrafts({
                                ...integrationDrafts,
                                [id]: event.target.value,
                              })
                            }
                          />
                        )}
                        <small>
                          {field.source === 'admin'
                            ? 'Nguồn: cấu hình admin'
                            : field.source === 'environment'
                            ? 'Nguồn: biến môi trường'
                            : 'Chưa cấu hình'}
                        </small>
                        {field.key === 'goong_api_key' && (
                          <div className="field-hint-tip">
                            <span>🔑 <strong>REST API Key:</strong> Dùng khóa loại <code>API Key</code> (ví dụ: <code>HWtLA...</code>) để tính tuyến đường và tìm kiếm tọa độ Geocoding.</span>
                          </div>
                        )}
                        {field.key === 'goong_maptiles_key' && (
                          <div className="field-hint-tip">
                            <span>🗺️ <strong>Maptiles Key:</strong> Dùng khóa loại <code>Maptiles Key</code> (ví dụ: <code>7LMSz...</code>) từ account.goong.io để tải gạch hiển thị bản đồ và lớp 3D.</span>
                          </div>
                        )}
                        {field.key === 'gemini_api_key' && (
                          <div className="field-hint-tip">
                            <span>🤖 Lấy Gemini API Key từ <strong>Google AI Studio</strong> (aistudio.google.com).</span>
                          </div>
                        )}
                        {field.key === 'openai_api_key' && (
                          <div className="field-hint-tip">
                            <span>⚡ Khóa OpenAI API bắt đầu bằng <code>sk-...</code> hoặc endpoint tương thích.</span>
                          </div>
                        )}
                        {field.key === 'vnpay_tmn_code' && (
                          <div className="field-hint-tip">
                            <span>💳 Mã Terminal ID (TMN Code) do VNPay cấp cho Merchant Sandbox / Production.</span>
                          </div>
                        )}
                        {field.key === 'client_id' && group.service === 'google_oauth' && (
                          <div className="field-hint-tip">
                            <span>🌐 Lấy OAuth 2.0 Client ID từ Google Cloud Console (APIs &amp; Services &gt; Credentials).</span>
                          </div>
                        )}
                      </label>
                      {field.source === 'admin' && (
                        <button
                          type="button"
                          className="btn-secondary-3d btn-sm integration-remove-btn"
                          disabled={savingIntegration}
                          aria-label={`Xóa override ${field.label}`}
                          onClick={() => void removeIntegrationOverride(group, field)}
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
              {/* Dedicated Connection Status Alert Card */}
              {integrationTestResults[group.service] && (
                <div
                  role="status"
                  className={`integration-test-result-box ${
                    integrationTestResults[group.service].ok
                      ? 'result-success'
                      : 'result-warning'
                  }`}
                >
                  <div className="test-result-header">
                    {integrationTestResults[group.service].ok ? (
                      <CheckCircle2 size={18} className="text-emerald" />
                    ) : (
                      <AlertCircle size={18} className="text-amber" />
                    )}
                    <strong>{integrationTestResults[group.service].message}</strong>
                  </div>
                  {integrationTestResults[group.service].detail && (
                    <div className="test-result-detail">
                      {integrationTestResults[group.service].detail}
                    </div>
                  )}
                </div>
              )}

              <div className="integration-actions-toolbar">
                <div className="integration-test-action">
                  {['ai', 'routing', 'payments', 'google_oauth'].includes(group.service) && (
                    <button
                      className="btn-secondary-3d btn-sm"
                      type="button"
                      disabled={testingIntegration[group.service] || savingIntegration}
                      onClick={() => void testIntegration(group)}
                    >
                      <Activity size={15} />{' '}
                      {testingIntegration[group.service] ? 'Đang kiểm tra…' : 'Kiểm tra kết nối'}
                    </button>
                  )}
                </div>
                <div className="integration-save-action">
                  <button
                    className="btn-primary-3d btn-sm"
                    type="submit"
                    disabled={savingIntegration}
                  >
                    <Save size={15} /> {savingIntegration ? 'Đang lưu…' : 'Lưu cấu hình'}
                  </button>
                </div>
              </div>
            </form>
          ))}
        </div>
      )}
    </div>
  )
}
