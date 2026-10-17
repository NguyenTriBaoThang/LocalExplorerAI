import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Activity, AlertCircle, CheckCircle2, CreditCard, Map as MapIcon, Plug, Save, Settings2, Sparkles, Star, Trash2, UserCheck } from 'lucide-react'
import { Alert, Badge, Button, Card, Drawer, EmptyState, Field, IconButton, Input, PageHeader, Select, Spinner, useToast } from '../../components/ui'
import { errorMessage } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { integrationsApi, type IntegrationField, type IntegrationGroup, type IntegrationStatus } from '../../lib/adminOps'

const ICONS: Record<string, typeof Plug> = { payments: CreditCard, routing: MapIcon, ai: Sparkles, google_oauth: UserCheck, google_places: Star }
const STATUS: Record<IntegrationStatus, { label: string; tone: 'green' | 'amber' | 'gray' }> = {
  active: { label: 'Đang hoạt động', tone: 'green' },
  incomplete: { label: 'Thiếu cấu hình', tone: 'amber' },
  inactive: { label: 'Chưa cấu hình', tone: 'gray' },
}

const HINTS: Record<string, string> = {
  api_key: 'Khóa Google Cloud đã bật Places API (New). Hệ thống chỉ đọc điểm sao công khai và dừng gọi khi đạt hạn mức hằng tháng (mặc định 900 lượt, trong hạn mức miễn phí).',
  goong_api_key: 'Khóa loại API Key dùng để tính tuyến đường và tìm tọa độ (Geocoding).',
  goong_maptiles_key: 'Khóa loại Maptiles Key từ account.goong.io để tải bản đồ nền và lớp 3D.',
  gemini_api_key: 'Lấy Gemini API Key từ Google AI Studio (aistudio.google.com).',
  openai_api_key: 'Khóa OpenAI API (bắt đầu bằng sk-…) hoặc khóa của endpoint tương thích.',
  vnpay_tmn_code: 'Mã Terminal ID (TMN Code) do VNPay cấp cho Merchant.',
  momo_return_url: 'Phải là HTTPS công khai, kết thúc bằng /api/payments/momo/return.',
  momo_ipn_url: 'Phải là HTTPS công khai, kết thúc bằng /api/payments/momo/ipn.',
  vnpay_return_url: 'Phải là HTTPS công khai, kết thúc bằng /api/payments/vnpay/return.',
  vnpay_ipn_url: 'Phải là HTTPS công khai, kết thúc bằng /api/payments/vnpay/ipn.',
  client_id: 'OAuth 2.0 Client ID từ Google Cloud Console (APIs & Services > Credentials).',
}

const choicesFor = (key: string): Array<[string, string]> | null =>
  key.endsWith('environment') ? [['sandbox', 'Sandbox (thử nghiệm)'], ['production', 'Production (thật)']] : key === 'geocoding_provider' ? [['goong', 'Goong']] : null

type TestResult = { ok: boolean; message: string; detail?: string }

export function AdminIntegrationsPage() {
  const toast = useToast()
  const [groups, setGroups] = useState<IntegrationGroup[] | null>(null)
  const [loadError, setLoadError] = useState('')
  const [openService, setOpenService] = useState<string | null>(null)
  const [provider, setProvider] = useState('')            // provider chosen in the drawer (not saved until "Lưu")
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState<string | null>(null)
  const [results, setResults] = useState<Record<string, TestResult>>({})

  const load = useCallback(async () => {
    try {
      setGroups(await integrationsApi.list())
      setLoadError('')
    } catch (err) {
      setGroups((current) => current ?? [])
      const status = (err as { response?: { status?: number } })?.response?.status
      setLoadError(`${errorMessage(err)}${status === 500 ? ' Có thể database chưa chạy migration: chạy `alembic upgrade head` trong apps/api rồi tải lại.' : ''}`)
    }
  }, [])
  useEffect(() => { void load() }, [load])

  const group = groups?.find((item) => item.service === openService) ?? null
  const byKey = useMemo(() => new Map((group?.fields ?? []).map((field) => [field.key, field])), [group])

  const open = (item: IntegrationGroup) => {
    // Secret values are never returned: secret drafts always start empty.
    const next: Record<string, string> = {}
    for (const field of item.fields) next[field.key] = field.secret ? '' : field.value || (choicesFor(field.key)?.[0][0] ?? '')
    setDrafts(next)
    setProvider(item.active_provider ?? '')
    setOpenService(item.service)
  }

  // Which keys the drawer shows depends on the selected provider, so adding a provider needs no UI change.
  const shownKeys = useMemo(() => {
    if (!group) return []
    const chosen = group.providers.find((item) => item.id === provider)
    return group.provider_key
      ? [...group.shared_fields, ...(chosen?.fields ?? [])]
      : group.fields.map((field) => field.key)
  }, [group, provider])

  const save = async (event: FormEvent) => {
    event.preventDefault()
    if (!group) return
    const values: Record<string, string> = {}
    for (const key of shownKeys) {
      const field = byKey.get(key)
      const draft = drafts[key]?.trim() ?? ''
      if (field && draft && (field.secret || draft !== (field.value ?? ''))) values[key] = draft
    }
    if (group.provider_key && provider && provider !== group.active_provider) values[group.provider_key] = provider
    if (!Object.keys(values).length) {
      toast.error('Chưa có thay đổi để lưu. Ô bí mật để trống sẽ giữ nguyên khóa đang có; muốn bỏ một giá trị đã đặt, dùng nút xóa bên cạnh ô.')
      return
    }
    setSaving(true)
    try {
      setGroups(await integrationsApi.update(group.service, values))
      setResults(({ [group.service]: _stale, ...rest }) => rest)   // a test result describes the old configuration
      toast.success(`Đã lưu cấu hình ${group.title}. Khóa bí mật đã được mã hóa.`)
      setOpenService(null)
    } catch (err) {
      toast.error(errorMessage(err, 'Không lưu được cấu hình. Kiểm tra khóa mã hóa và giá trị.'))
    } finally {
      setSaving(false)
    }
  }

  const removeOverride = async (field: IntegrationField) => {
    if (!group || !window.confirm(`Xóa cấu hình admin của "${field.label}"? Giá trị sẽ quay về biến môi trường nếu có.`)) return
    setSaving(true)
    try {
      const rows = await integrationsApi.update(group.service, {}, [field.key])
      setGroups(rows)
      setResults(({ [group.service]: _stale, ...rest }) => rest)
      const refreshed = rows.find((item) => item.service === group.service)?.fields.find((item) => item.key === field.key)
      setDrafts((current) => ({ ...current, [field.key]: field.secret ? '' : refreshed?.value ?? '' }))
      toast.success('Đã xóa cấu hình admin.')
    } catch (err) {
      toast.error(errorMessage(err, 'Không xóa được cấu hình.'))
    } finally {
      setSaving(false)
    }
  }

  const test = async (item: IntegrationGroup) => {
    setTesting(item.service)
    setResults((current) => ({ ...current, [item.service]: { ok: false, message: 'Đang kiểm tra kết nối…' } }))
    try {
      const result = await integrationsApi.test(item.service)
      setResults((current) => ({ ...current, [item.service]: { ok: result.ok, message: result.message_vi, detail: result.detail_vi } }))
      if (result.ok) toast.success(`${item.title}: ${result.message_vi}`)
      else toast.error(`${item.title}: ${result.message_vi}`)
    } catch {
      setResults((current) => ({ ...current, [item.service]: { ok: false, message: 'Không thể kết nối tới dịch vụ.', detail: 'Kiểm tra máy chủ backend đang chạy.' } }))
      toast.error('Kiểm tra kết nối thất bại.')
    } finally {
      setTesting(null)
    }
  }

  const active = (groups ?? []).filter((item) => item.status === 'active' && !item.simulated).length

  return (
    <>
      <PageHeader title="Tích hợp & API keys" description="Các dịch vụ bên thứ ba đang kết nối với hệ thống: trạng thái, nhà cung cấp đang dùng và cấu hình." />
      <div className="mb-5 space-y-3">
        {loadError && <Alert tone="amber">Không tải được cấu hình tích hợp: {loadError}</Alert>}
        <Alert tone="brand">
          Khóa được mã hóa trong cơ sở dữ liệu bằng INTEGRATION_SECRETS_KEY ở máy chủ và không bao giờ được trả về trình duyệt. Cấu hình ở đây được ưu tiên
          hơn biến môi trường; xóa cấu hình sẽ quay về biến môi trường.
        </Alert>
      </div>

      {!groups ? <Spinner /> : groups.length === 0 ? (
        <Card><EmptyState icon={Plug} title="Chưa có dịch vụ tích hợp nào" /></Card>
      ) : (
        <>
          <p className="mb-3 text-sm text-slate-500"><strong className="text-slate-900">{active}</strong>/{groups.length} dịch vụ đang hoạt động</p>
          <div className="grid gap-4 lg:grid-cols-2">
            {groups.map((item) => {
              const Icon = ICONS[item.service] ?? Plug
              const status = item.simulated && item.status === 'active' ? { label: 'Chế độ mô phỏng', tone: 'amber' as const } : STATUS[item.status]
              const providerLabel = item.providers.find((p) => p.id === item.active_provider)?.label
              const result = results[item.service]
              const relevant = item.fields.filter((field) => (item.relevant_fields ?? item.fields.map((f) => f.key)).includes(field.key))
              const set = relevant.filter((field) => field.configured).length
              return (
                <Card key={item.service}>
                  <div className="flex items-start gap-4 p-5">
                    <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-700"><Icon className="h-5 w-5" /></span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-base font-semibold text-slate-900">{item.title}</h3>
                        <Badge tone={status.tone} dot>{status.label}</Badge>
                      </div>
                      <p className="mt-0.5 text-sm text-slate-500">{item.description}</p>
                      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                        {providerLabel && <><dt className="text-slate-500">Nhà cung cấp</dt><dd className="font-medium text-slate-900">{providerLabel}</dd></>}
                        <dt className="text-slate-500">Khóa đã cấu hình</dt><dd className="text-slate-900">{set}/{relevant.length}{item.admin_overrides > 0 && ` · ${item.admin_overrides} do admin đặt`}</dd>
                        <dt className="text-slate-500">Cập nhật</dt><dd className="text-slate-900">{item.updated_at ? formatDate(item.updated_at) : 'Dùng biến môi trường'}</dd>
                      </dl>
                      {item.status !== 'active' && item.missing.length > 0 && (
                        <p className="mt-2 text-sm text-amber-700">Còn thiếu: {item.missing.map((key) => item.fields.find((field) => field.key === key)?.label ?? key).join(', ')}</p>
                      )}
                    </div>
                  </div>
                  {result && (
                    <div role="status" className={`mx-5 mb-4 rounded-lg border p-3 text-sm ${result.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>
                      <div className="flex items-center gap-2 font-semibold">{result.ok ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}{result.message}</div>
                      {result.detail && <p className="mt-1 opacity-90">{result.detail}</p>}
                    </div>
                  )}
                  <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 px-5 py-3">
                    {item.testable && (
                      <Button type="button" variant="secondary" size="sm" icon={Activity} loading={testing === item.service} disabled={!!testing || item.status === 'inactive'} onClick={() => void test(item)}>
                        Kiểm tra kết nối
                      </Button>
                    )}
                    <Button type="button" size="sm" icon={Settings2} onClick={() => open(item)}>{item.status === 'inactive' ? 'Thiết lập' : 'Cấu hình'}</Button>
                  </div>
                </Card>
              )
            })}
          </div>
        </>
      )}

      <Drawer
        open={!!group}
        onClose={() => !saving && setOpenService(null)}
        title={group ? `Cấu hình ${group.title}` : ''}
        subtitle={group?.description}
        footer={group && (
          <>
            <Button type="button" variant="secondary" disabled={saving} onClick={() => setOpenService(null)}>Hủy</Button>
            <Button type="submit" form="integration-form" icon={Save} loading={saving}>Lưu cấu hình</Button>
          </>
        )}
      >
        {group && (
          <form id="integration-form" onSubmit={(event) => void save(event)} className="space-y-5">
            <input type="text" name="username" autoComplete="username" className="hidden" aria-hidden="true" tabIndex={-1} readOnly />
            {group.provider_key && (
              <Field label="Nhà cung cấp đang dùng" hint="Chỉ các khóa của nhà cung cấp được chọn mới hiển thị bên dưới.">
                <Select value={provider} onChange={(e) => setProvider(e.target.value)}>
                  {group.providers.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                </Select>
              </Field>
            )}
            {shownKeys.length === 0 && <p className="text-sm text-slate-500">Nhà cung cấp này không cần khóa nào.</p>}
            {shownKeys.map((key) => {
              const field = byKey.get(key)
              if (!field) return null
              const required = group.required.includes(key)
              const choices = choicesFor(key)
              const hint = HINTS[key]
              const inputType = field.secret ? 'password' : /_(url|uri)$/.test(key) ? 'url' : 'text'
              return (
                <div key={key} className="flex items-start gap-2">
                  <Field label={field.label} required={required} hint={hint} className="min-w-0 flex-1">
                    {choices ? (
                      <Select value={drafts[key] || choices[0][0]} onChange={(e) => setDrafts({ ...drafts, [key]: e.target.value })}>
                        {choices.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </Select>
                    ) : (
                      <Input
                        type={inputType}
                        autoComplete={field.secret ? 'new-password' : 'off'}
                        value={drafts[key] ?? ''}
                        placeholder={field.secret && field.configured ? 'Đã có khóa · để trống để giữ nguyên' : field.secret ? 'Nhập khóa' : 'Chưa cấu hình'}
                        onChange={(e) => setDrafts({ ...drafts, [key]: e.target.value })}
                      />
                    )}
                    <span className="mt-1 block">
                      <Badge tone={field.source === 'admin' ? 'brand' : field.source === 'environment' ? 'green' : 'gray'}>
                        {field.source === 'admin' ? 'Cấu hình admin' : field.source === 'environment' ? 'Biến môi trường' : 'Chưa cấu hình'}
                      </Badge>
                    </span>
                  </Field>
                  {field.source === 'admin' && (
                    <IconButton type="button" icon={Trash2} label={`Xóa cấu hình ${field.label}`} disabled={saving} onClick={() => void removeOverride(field)} className="mt-6" />
                  )}
                </div>
              )
            })}
          </form>
        )}
      </Drawer>
    </>
  )
}
