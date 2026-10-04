import { useEffect, useState, type FormEvent } from 'react'
import {
  Users,
  Building,
  Layers,
  GitMerge,
  History,
  Check,
  X,
  EyeOff,
  AlertCircle,
  Plus,
  RefreshCw,
  KeyRound,
  Save,
  Trash2,
} from 'lucide-react'
import { adminApi } from '../api/client'
import { TiltCard3D } from '../components/3d/TiltCard3D'
import { useTranslation } from '../i18n'

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

type TabKey = 'queue' | 'duplicates' | 'providers' | 'users' | 'audit' | 'integrations'

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
  const [integrationDrafts, setIntegrationDrafts] = useState<Record<string, string>>({})
  const [savingIntegration, setSavingIntegration] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  // Create Provider State
  const [providerName, setProviderName] = useState('')
  const [providerEmail, setProviderEmail] = useState('')
  const [providerPassword, setProviderPassword] = useState('')
  const [providerAddress, setProviderAddress] = useState('')

  async function load() {
    setLoading(true)
    try {
      const [metrics, accounts, providerRows, pending, nearDuplicates, logs, integrationRows] =
        await Promise.all([
          adminApi.dashboard(),
          adminApi.users(),
          adminApi.providers(),
          adminApi.moderation('pending'),
          adminApi.duplicates(),
          adminApi.audit(),
          adminApi.integrations(),
        ])
      setDashboard(metrics)
      setUsers(accounts)
      setProviders(providerRows)
      setQueue({
        pois: pending.pois,
        experiences: pending.experiences,
        evidence: pending.evidence,
      })
      setDuplicates(nearDuplicates)
      setAudit(logs)
      setIntegrations(integrationRows)
      setIntegrationDrafts((previous) => {
        const next = { ...previous }
        for (const group of integrationRows as IntegrationGroup[]) {
          for (const field of group.fields) {
            const name = `${group.service}.${field.key}`
            if (!field.secret) next[name] = field.value || ''
            else next[name] = ''
          }
        }
        return next
      })
      setError('')
    } catch (reason) {
      setError(
        String(
          (reason as { response?: { data?: { error?: { message?: string } } } })?.response?.data
            ?.error?.message || 'Không tải được dữ liệu quản trị.'
        )
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function review(kind: string, id: string, action: string) {
    try {
      await adminApi.review(kind, id, action, `Admin action: ${action}`)
      setMessage(`Đã thực hiện: ${action} ${kind}.`)
      await load()
    } catch {
      setError('Không thể lưu quyết định duyệt.')
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
      setMessage('Đã tạo hồ sơ cơ sở và tài khoản đối tác thành công!')
      await load()
    } catch {
      setError('Tạo cơ sở thất bại. Email có thể đã được dùng hoặc mật khẩu chưa đủ 12 ký tự.')
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
      setMessage('Đã cập nhật vai trò người dùng.')
      await load()
    } catch {
      setError('Không thể cập nhật vai trò hoặc trạng thái tài khoản.')
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
      setError('ID giữ lại phải là một trong hai POI đang được hiển thị.')
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
      setMessage('Đã chuyển trải nghiệm/lịch sang POI giữ lại và ẩn POI trùng.')
      await load()
    } catch {
      setError('Không thể gộp hai POI này.')
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
        setMessage('Chưa có thay đổi mới để lưu. Ô bí mật để trống sẽ giữ nguyên khóa đang có.')
        return
      }
      await adminApi.updateIntegration(group.service, values)
      setMessage(`Đã lưu cấu hình ${group.service}. Giá trị bí mật không được gửi ngược về trình duyệt.`)
      setError('')
      await load()
    } catch (reason) {
      const detail = (reason as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message
      setError(detail || 'Không lưu được cấu hình tích hợp. Kiểm tra khóa mã hóa và giá trị đã nhập.')
    } finally {
      setSavingIntegration(false)
    }
  }

  async function removeIntegrationOverride(group: IntegrationGroup, field: IntegrationField) {
    if (!window.confirm(`Xóa cấu hình admin cho ${group.service}.${field.key}? Cấu hình sẽ quay về biến môi trường nếu có.`)) return
    setSavingIntegration(true)
    try {
      await adminApi.updateIntegration(group.service, {}, [field.key])
      setMessage(`Đã xóa override ${group.service}.${field.key}.`)
      setError('')
      await load()
    } catch (reason) {
      const detail = (reason as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message
      setError(detail || 'Không xóa được cấu hình tích hợp.')
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

  return (
    <div className="admin-page-3d page-wrap">
      {/* Header */}
      <div className="page-title-row-3d">
        <div>
          <span className="eyebrow-3d">
            <span className="eyebrow-dot" /> TRUNG TÂM QUẢN TRỊ TOÀN DIỆN
          </span>
          <h1 className="page-heading-3d">
            Quản trị hệ thống <em>Local Explorer AI.</em>
          </h1>
          <p className="page-subtext-3d">
            Kiểm duyệt dữ liệu, phát hiện trùng lặp POI, quản lý phân quyền và theo dõi audit logs.
          </p>
        </div>

        <button
          type="button"
          className="btn-secondary-3d btn-sm"
          onClick={() => void load()}
          disabled={loading}
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          <span>Làm mới dữ liệu</span>
        </button>
      </div>

      {message && (
        <div className="inline-alert-3d alert-success">
          <Check size={16} className="text-emerald" />
          <span>{message}</span>
        </div>
      )}

      {error && (
        <div className="inline-alert-3d">
          <AlertCircle size={16} className="text-amber" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Metrics Dashboard Cards */}
      <div className="admin-metrics-grid">
        {Object.entries(dashboard).map(([key, value]) => (
          <TiltCard3D key={key} maxTilt={6} className="admin-kpi-card">
            <small>{key.replaceAll('_', ' ').toUpperCase()}</small>
            <strong>{value}</strong>
          </TiltCard3D>
        ))}
      </div>

      {/* Tab Navigation Strip */}
      <div className="admin-tab-strip">
        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'queue' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('queue')}
        >
          <Layers size={15} />
          <span>{t('admin.tabQueue')}</span>
          {queueTotal > 0 && <span className="admin-tab-badge">{queueTotal}</span>}
        </button>

        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'duplicates' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('duplicates')}
        >
          <GitMerge size={15} />
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
          <Building size={15} />
          <span>{t('admin.tabProviders')}</span>
        </button>

        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'users' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          <Users size={15} />
          <span>{t('admin.tabUsers')} ({users.length})</span>
        </button>

        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'audit' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          <History size={15} />
          <span>{t('admin.tabAudit')} ({audit.length})</span>
        </button>

        <button
          type="button"
          className={`admin-tab-btn ${activeTab === 'integrations' ? 'admin-tab-active' : ''}`}
          onClick={() => setActiveTab('integrations')}
        >
          <KeyRound size={15} />
          <span>Tích hợp & API keys</span>
        </button>
      </div>

      {/* Tab 1: Moderation Queue */}
      {activeTab === 'queue' && (
        <div className="admin-tab-content animate-fadeIn">
          <div className="inline-alert-3d">
            <AlertCircle size={16} />
            <span>Dữ liệu mô phỏng không được duyệt thành dữ liệu vận hành. Chỉ duyệt sau khi nguồn bao phủ đủ trường, đúng phiên bản và còn hạn.</span>
          </div>
          {(['pois', 'experiences', 'evidence'] as const).map((kind) => (
            <section key={kind} className="admin-section-card mb-6">
              <div className="admin-section-header">
                <h3>
                  Hạng mục: <span className="text-emerald uppercase">{kind}</span> ({queue[kind].length})
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
                            <span>{item.source_type || 'source'} · {item.target_type || 'no target'}</span>
                            <span>Fields: {(item.fields_covered || []).join(', ') || 'none'}</span>
                            <span>License: {item.license || 'not specified'}</span>
                            <span>Target: {item.target_id || 'unlinked'}</span>
                            <span>Observed: {item.observed_at ? new Date(item.observed_at).toLocaleString() : 'missing'}</span>
                            <span>Expires: {item.expires_at ? new Date(item.expires_at).toLocaleString() : 'missing'}</span>
                            {item.source_uri && <a href={item.source_uri} target="_blank" rel="noreferrer">Open source</a>}
                          </div>
                        )}
                      </div>

                      <div className="item-action-btns">
                        <button
                          type="button"
                          className="btn-action-approve"
                          onClick={() =>
                            void review(
                              kind === 'pois' ? 'poi' : kind === 'experiences' ? 'experience' : 'evidence',
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
                              kind === 'pois' ? 'poi' : kind === 'experiences' ? 'experience' : 'evidence',
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
                              kind === 'pois' ? 'poi' : kind === 'experiences' ? 'experience' : 'evidence',
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

      {/* Tab 2: Duplicates Detection */}
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
                  <div
                    key={`${pair.poi_a.id}-${pair.poi_b.id}`}
                    className="duplicate-pair-card"
                  >
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

      {/* Tab 3: Create Provider */}
      {activeTab === 'providers' && (
        <div className="admin-tab-content animate-fadeIn">
          <section className="form-card-3d">
            <div className="form-card-header">
              <span className="step-num"><Plus size={16} /></span>
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
        </div>
      )}

      {/* Tab 4: User & Role Management */}
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

      {/* Tab 5: Audit Log */}
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

      {activeTab === 'integrations' && (
        <div className="admin-tab-content animate-fadeIn">
          <div className="inline-alert-3d">
            <AlertCircle size={16} />
            <span>Khóa được mã hóa trong cơ sở dữ liệu bằng INTEGRATION_SECRETS_KEY ở môi trường máy chủ. Ô bí mật luôn để trống khi tải; lưu ô trống giữ khóa cũ. Không nhập khóa vào log hoặc chia sẻ qua chat.</span>
          </div>
          {integrations.map((group) => (
            <form key={group.service} className="admin-section-card integration-config-card" onSubmit={(event) => void saveIntegration(group, event)}>
              <div className="admin-section-header">
                <h3>{integrationTitle[group.service] || group.service}</h3>
                <p>Override đã mã hóa được ưu tiên hơn biến môi trường. Xóa override sẽ quay về giá trị môi trường nếu có.</p>
              </div>
              <div className="integration-config-grid">
                {group.fields.map((field) => {
                  const id = `${group.service}.${field.key}`
                  const fallback = field.key === 'provider'
                    ? group.service === 'payments' ? 'vnpay' : group.service === 'routing' ? 'goong' : 'openai'
                    : field.key.endsWith('environment') ? 'sandbox' : ''
                  const value = integrationDrafts[id] ?? field.value ?? fallback
                  const choices = group.service === 'payments' && field.key === 'provider'
                    ? [['vnpay', 'VNPay'], ['momo', 'MoMo']]
                    : group.service === 'payments' && field.key.endsWith('environment')
                      ? [['sandbox', 'Sandbox'], ['production', 'Production']]
                      : group.service === 'routing' && field.key === 'provider'
                        ? [['goong', 'Goong'], ['mock', 'Mock (development only)']]
                        : group.service === 'routing' && field.key === 'geocoding_provider'
                          ? [['goong', 'Goong']]
                          : group.service === 'ai' && field.key === 'provider'
                            ? [['openai', 'OpenAI-compatible'], ['gemini', 'Gemini']]
                            : null
                  return (
                    <div className="integration-setting-field" key={field.key}>
                      <label className="field-group-3d">
                        <span>{field.label}</span>
                        {choices ? (
                          <select value={value} onChange={(event) => setIntegrationDrafts({ ...integrationDrafts, [id]: event.target.value })}>
                            {choices.map(([choice, label]) => <option key={choice} value={choice}>{label}</option>)}
                          </select>
                        ) : (
                          <input
                            type={field.secret ? 'password' : field.key.endsWith('_url') || field.key.endsWith('_uri') || field.key.endsWith('_base_url') ? 'url' : 'text'}
                            autoComplete={field.secret ? 'new-password' : 'off'}
                            value={value}
                            placeholder={field.secret && field.configured ? 'Đã có khóa · để trống để giữ nguyên' : field.secret ? 'Nhập khóa mới' : 'Chưa cấu hình'}
                            onChange={(event) => setIntegrationDrafts({ ...integrationDrafts, [id]: event.target.value })}
                          />
                        )}
                        <small>{field.source === 'admin' ? 'Nguồn: cấu hình admin' : field.source === 'environment' ? 'Nguồn: biến môi trường' : 'Chưa cấu hình'}</small>
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
              <div className="integration-save-row">
                <button className="btn-primary-3d btn-sm" type="submit" disabled={savingIntegration}>
                  <Save size={15} /> {savingIntegration ? 'Đang lưu…' : 'Lưu cấu hình'}
                </button>
              </div>
            </form>
          ))}
        </div>
      )}
    </div>
  )
}
