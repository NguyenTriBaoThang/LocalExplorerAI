import { Fragment, useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Copy, KeyRound, Lock, Plus, RotateCcw, Save, Search, ShieldCheck, Trash2 } from 'lucide-react'
import { Alert, Badge, Button, Card, cx, EmptyState, Field, IconButton, Input, Modal, PageHeader, Spinner, Tabs, useToast } from '../../components/ui'
import { adminApi, errorMessage } from '../../lib/api'
import { formatDateTime, ROLES, timeAgo } from '../../lib/format'
import type { RbacMatrix, ServiceAccount } from '../../lib/types'

const GROUPS: Record<string, string> = {
  account: 'Tài khoản', itinerary: 'Lịch trình', notification: 'Thông báo', chat: 'AI Concierge', replan: 'Điều chỉnh lịch trình',
  booking: 'Đặt chỗ', review: 'Đánh giá', provider: 'Đối tác', admin: 'Quản trị', ops: 'Vận hành',
}
const LABELS: Record<string, string> = {
  'account:read': 'Xem hồ sơ cá nhân', 'account:update': 'Sửa hồ sơ cá nhân', 'account:password': 'Đổi mật khẩu', 'account:sessions': 'Xem & đăng xuất thiết bị', 'account:mfa': 'Quản lý xác thực hai lớp',
  'itinerary:plan': 'Tạo lịch trình', 'itinerary:read': 'Xem lịch trình', 'itinerary:list': 'Danh sách lịch trình của mình', 'itinerary:compare': 'So sánh lịch trình',
  'itinerary:versions': 'Lịch sử phiên bản lịch trình', 'itinerary:share': 'Chia sẻ lịch trình', 'itinerary:feedback': 'Gửi đánh giá lịch trình',
  'notification:read': 'Xem thông báo hủy slot', 'chat:use': 'Dùng AI Concierge', 'replan:advise': 'Xin gợi ý điều chỉnh lịch trình', 'replan:accept': 'Chấp nhận điều chỉnh',
  'booking:create': 'Giữ chỗ', 'booking:read': 'Xem đặt chỗ của mình', 'booking:cancel': 'Hủy đặt chỗ chưa thanh toán', 'booking:checkout': 'Thanh toán đặt chỗ', 'booking:history': 'Xem lịch sử đặt chỗ',
  'provider:profile': 'Xem hồ sơ đối tác', 'provider:experience': 'Quản lý trải nghiệm', 'provider:poi': 'Quản lý địa điểm của mình', 'provider:evidence': 'Gửi minh chứng',
  'provider:slot': 'Quản lý slot', 'provider:audit': 'Xem nhật ký đối tác', 'provider:booking_read': 'Xem yêu cầu đặt chỗ', 'provider:booking_decide': 'Nhận / từ chối đặt chỗ', 'provider:slot_assist': 'Dùng trợ lý slot AI',
  'admin:dashboard': 'Xem dashboard quản trị', 'admin:users': 'Quản lý người dùng', 'admin:providers': 'Quản lý & duyệt đối tác', 'admin:moderation': 'Kiểm duyệt nội dung',
  'admin:duplicates': 'Gộp địa điểm trùng', 'admin:place_import': 'Nhập dữ liệu địa điểm', 'admin:audit': 'Xem nhật ký hệ thống', 'admin:integrations': 'Cấu hình tích hợp',
  'admin:ai_tools': 'Công cụ AI quản trị', 'admin:bot': 'Quản lý chatbot', 'admin:system': 'Cài đặt hệ thống', 'admin:models_3d': 'Hiệu chỉnh mô hình 3D',
  'admin:rbac': 'Phân quyền vai trò', 'admin:places': 'Quản lý địa điểm & danh thắng', 'admin:content': 'Quản lý nội dung website', 'admin:analytics': 'Xem thống kê truy cập',
  'provider:reviews': 'Xem & trả lời đánh giá', 'provider:analytics': 'Xem thống kê trải nghiệm', 'review:write': 'Viết đánh giá trải nghiệm', 'admin:service_accounts': 'Quản lý khóa API', 'ops:read': 'Xem trạng thái vận hành',
}
const ROLE_ORDER = ['admin', 'provider', 'traveler']
const GROUP_ORDER = ['account', 'itinerary', 'booking', 'review', 'chat', 'replan', 'notification', 'provider', 'admin', 'ops']
// Kept in sync with ADMIN_REQUIRED on the server: the admin role can never lose these.
const ADMIN_LOCKED = new Set(['admin:rbac', 'admin:users', 'admin:service_accounts'])

export function AdminRbacPage() {
  const [tab, setTab] = useState<'matrix' | 'service'>('matrix')
  return (
    <>
      <PageHeader title="Phân quyền" description="Quyết định vai trò nào được làm gì. Thay đổi có hiệu lực ngay cho mọi người dùng thuộc vai trò đó." />
      <div className="mb-6"><Tabs value={tab} onChange={setTab} items={[{ value: 'matrix', label: 'Vai trò & quyền' }, { value: 'service', label: 'Tài khoản dịch vụ (API key)' }]} /></div>
      {tab === 'matrix' ? <Matrix /> : <ServiceAccounts />}
    </>
  )
}

function Matrix() {
  const toast = useToast()
  const [matrix, setMatrix] = useState<RbacMatrix | null>(null)
  const [draft, setDraft] = useState<Record<string, Set<string>>>({})
  const [query, setQuery] = useState('')
  const [group, setGroup] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirmRisky, setConfirmRisky] = useState<Array<{ role: string; permissions: string[] }> | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await adminApi.rbac()
      setMatrix(data)
      setDraft(Object.fromEntries(data.roles.map((role) => [role.name, new Set(role.permissions)])))
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [load])

  const roles = useMemo(() => [...(matrix?.roles ?? [])].sort((a, b) => ROLE_ORDER.indexOf(a.name) - ROLE_ORDER.indexOf(b.name)), [matrix])
  const changed = roles.filter((role) => {
    const current = new Set(role.permissions)
    const next = draft[role.name] ?? new Set()
    return current.size !== next.size || [...next].some((p) => !current.has(p))
  })
  useEffect(() => {
    if (changed.length === 0) return
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [changed.length])
  const grouped = useMemo(() => {
    const groups = new Map<string, RbacMatrix['permissions']>()
    for (const permission of matrix?.permissions ?? []) {
      if (query && !(permission.name + permission.description + (LABELS[permission.name] ?? '')).toLowerCase().includes(query.toLowerCase())) continue
      const key = permission.name.split(':')[0]
      groups.set(key, [...(groups.get(key) ?? []), permission])
    }
    return [...groups.entries()].sort((a, b) => GROUP_ORDER.indexOf(a[0]) - GROUP_ORDER.indexOf(b[0]))
  }, [matrix, query])
  const activeGroup = group && grouped.some(([key]) => key === group) ? group : grouped[0]?.[0] ?? ''
  const visibleGroups = query ? grouped : grouped.filter(([key]) => key === activeGroup)
  const dirtyGroups = new Set((matrix?.permissions ?? []).filter((permission) =>
    roles.some((role) => (draft[role.name]?.has(permission.name) ?? false) !== role.permissions.includes(permission.name))).map((p) => p.name.split(':')[0]))

  const toggle = (role: string, permission: string) => {
    if (role === 'admin' && ADMIN_LOCKED.has(permission)) return
    setDraft((current) => {
      const next = new Set(current[role])
      if (next.has(permission)) next.delete(permission)
      else next.add(permission)
      return { ...current, [role]: next }
    })
  }

  const setGroupForRole = (role: string, permissions: string[], enable: boolean) => {
    setDraft((current) => {
      const next = new Set(current[role])
      for (const permission of permissions) {
        if (enable) next.add(permission)
        else next.delete(permission)
      }
      return { ...current, [role]: next }
    })
  }

  // Granting administrator permissions to a non-admin role is the most damaging mistake here; make it explicit.
  const riskyGrants = () => changed.filter((role) => role.name !== 'admin').map((role) => ({
    role: role.name,
    permissions: [...(draft[role.name] ?? [])].filter((p) => p.startsWith('admin:') && !role.permissions.includes(p)),
  })).filter((item) => item.permissions.length > 0)

  const requestSave = () => {
    const risky = riskyGrants()
    if (risky.length) setConfirmRisky(risky)
    else void save()
  }

  const save = async () => {
    setConfirmRisky(null)
    setSaving(true)
    try {
      for (const role of changed) await adminApi.setRolePermissions(role.name, [...draft[role.name]])
      toast.success(`Đã cập nhật quyền cho ${changed.map((r) => ROLES[r.name] ?? r.name).join(', ')}.`)
      await load()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (!matrix) return <Spinner />

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm quyền…" className="pl-9" />
        </div>
        <div className="ml-auto flex gap-2">
          {changed.length > 0 && <Button variant="ghost" icon={RotateCcw} onClick={() => setDraft(Object.fromEntries(matrix.roles.map((r) => [r.name, new Set(r.permissions)])))}>Hoàn tác</Button>}
          <Button icon={Save} disabled={changed.length === 0} loading={saving} onClick={requestSave}>Lưu thay đổi{changed.length > 0 && ` (${changed.length})`}</Button>
        </div>
      </div>
      {/* Vertical group list: scales to any number of permission groups without hiding any. */}
      <Card className="grid grid-cols-1 overflow-hidden md:grid-cols-[220px_minmax(0,1fr)]">
        <nav aria-label="Nhóm quyền" className="min-w-0 border-b border-slate-200 bg-slate-50/60 p-2 md:max-h-[640px] md:overflow-y-auto md:border-b-0 md:border-r">
          <p className="px-3 pb-1.5 pt-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{query ? 'Kết quả theo nhóm' : 'Nhóm quyền'}</p>
          <ul className="flex gap-1 overflow-x-auto md:block md:space-y-0.5 md:overflow-visible">
            {grouped.map(([key, permissions]) => {
              const active = !query && key === activeGroup
              return (
                <li key={key} className="shrink-0">
                  <button type="button" onClick={() => { setQuery(''); setGroup(key) }}
                    className={cx('flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium transition',
                      active ? 'bg-white text-brand-700 shadow-sm ring-1 ring-slate-200' : 'text-slate-600 hover:bg-white hover:text-slate-900')}>
                    <span className="flex-1 truncate">{GROUPS[key] ?? key}</span>
                    {dirtyGroups.has(key) && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" title="Có thay đổi chưa lưu" />}
                    <span className={cx('shrink-0 rounded-full px-1.5 text-xs', active ? 'bg-brand-50 text-brand-700' : 'bg-slate-200/70 text-slate-500')}>{permissions.length}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>
        <div className="min-w-0 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-5 py-3 text-left">
                  <p className="text-sm font-semibold text-slate-900">{query ? `Kết quả cho “${query}”` : GROUPS[activeGroup] ?? activeGroup}</p>
                  <p className="text-xs font-normal text-slate-500">{visibleGroups.reduce((n, [, items]) => n + items.length, 0)} quyền</p>
                </th>
                {roles.map((role) => (
                  <th key={role.name} className="w-28 px-3 py-3 text-center">
                    <p className="text-sm font-semibold text-slate-900">{ROLES[role.name] ?? role.name}</p>
                    <p className="text-xs font-normal text-slate-500">{draft[role.name]?.size ?? 0} quyền</p>
                  </th>
                ))}
              </tr>
              {!query && visibleGroups[0] && (
                <tr className="border-t border-slate-200 bg-white">
                  <td className="px-5 py-2 text-xs text-slate-500">Bật / tắt cả nhóm</td>
                  {roles.map((role) => {
                    const editable = visibleGroups[0][1].filter((p) => !(role.name === 'admin' && ADMIN_LOCKED.has(p.name)))
                    const on = editable.filter((p) => draft[role.name]?.has(p.name)).length
                    return (
                      <td key={role.name} className="px-3 py-2 text-center">
                        <input type="checkbox" aria-label={`Bật tất cả quyền nhóm này cho ${role.name}`} disabled={editable.length === 0}
                          checked={editable.length > 0 && on === editable.length}
                          ref={(el) => { if (el) el.indeterminate = on > 0 && on < editable.length }}
                          onChange={() => setGroupForRole(role.name, editable.map((p) => p.name), on < editable.length)}
                          className="h-4 w-4 cursor-pointer rounded border-slate-300 text-brand-600 focus:ring-brand-500 disabled:opacity-40" />
                      </td>
                    )
                  })}
                </tr>
              )}
            </thead>
            <tbody>
              {visibleGroups.map(([key, permissions]) => (
                <Fragment key={key}>
                  {query && <tr className="bg-slate-50/70"><td colSpan={roles.length + 1} className="px-5 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{GROUPS[key] ?? key}</td></tr>}
                  {permissions.map((permission) => (
                    <tr key={permission.name} className="border-t border-slate-100 hover:bg-slate-50/60">
                      <td className="px-5 py-2.5">
                        <p className="text-slate-800">{LABELS[permission.name] ?? permission.description}</p>
                        <p className="font-mono text-[11px] text-slate-400">{permission.name}</p>
                      </td>
                      {roles.map((role) => {
                        const locked = role.name === 'admin' && ADMIN_LOCKED.has(permission.name)
                        const checked = draft[role.name]?.has(permission.name) ?? false
                        const dirty = checked !== role.permissions.includes(permission.name)
                        return (
                          <td key={role.name} className={cx('px-3 py-2.5 text-center', dirty && 'bg-amber-50')}>
                            {locked ? <Lock className="mx-auto h-4 w-4 text-slate-400" aria-label="Bắt buộc với quản trị viên" /> : (
                              <input type="checkbox" checked={checked} onChange={() => toggle(role.name, permission.name)} aria-label={`${permission.name} cho ${role.name}`}
                                className="h-4 w-4 cursor-pointer rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </Fragment>
              ))}
              {visibleGroups.length === 0 && <tr><td colSpan={roles.length + 1} className="px-5 py-8 text-center text-sm text-slate-500">Không tìm thấy quyền phù hợp.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>
      <Modal open={!!confirmRisky} onClose={() => setConfirmRisky(null)} size="sm" title="Cấp quyền quản trị?"
        footer={<><Button variant="secondary" onClick={() => setConfirmRisky(null)}>Xem lại</Button><Button variant="danger" onClick={() => void save()}>Vẫn lưu</Button></>}>
        <Alert tone="red">Thay đổi này cho phép người dùng không phải quản trị viên truy cập chức năng quản trị.</Alert>
        <ul className="mt-4 space-y-2 text-sm">
          {confirmRisky?.map((item) => (
            <li key={item.role}><span className="font-semibold text-slate-900">{ROLES[item.role] ?? item.role}</span>: {item.permissions.map((p) => LABELS[p] ?? p).join(', ')}</li>
          ))}
        </ul>
      </Modal>
      <p className="mt-3 flex items-center gap-1.5 text-xs text-slate-500"><Lock className="h-3.5 w-3.5" /> Quyền khóa là bắt buộc với vai trò Quản trị viên để không ai bị khóa khỏi hệ thống.</p>
    </>
  )
}

function ServiceAccounts() {
  const toast = useToast()
  const [items, setItems] = useState<ServiceAccount[] | null>(null)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [created, setCreated] = useState<string | null>(null)
  const load = useCallback(() => { adminApi.serviceAccounts().then(setItems).catch((err) => { toast.error(errorMessage(err)); setItems([]) }) }, []) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(load, [load])

  const create = async (event: FormEvent) => {
    event.preventDefault()
    try {
      const account = await adminApi.createServiceAccount(name, ['ops:read'])
      setCreating(false)
      setName('')
      setCreated(account.key)
      load()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-slate-500">Khóa API cho hệ thống giám sát. Chỉ có thể cấp quyền đọc trạng thái vận hành.</p>
        <Button icon={Plus} onClick={() => setCreating(true)}>Tạo khóa API</Button>
      </div>
      <Card className="overflow-hidden">
        {!items ? <Spinner /> : items.length === 0 ? <EmptyState icon={KeyRound} title="Chưa có tài khoản dịch vụ" /> : (
          <ul className="divide-y divide-slate-100">
            {items.map((account) => (
              <li key={account.id} className="flex items-center gap-4 px-5 py-3.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-500"><ShieldCheck className="h-[18px] w-[18px]" /></span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900">{account.name} <span className="font-mono text-xs text-slate-400">{account.key_id}</span></p>
                  <p className="text-xs text-slate-500">Tạo {formatDateTime(account.created_at)} · dùng lần cuối {account.last_used_at ? timeAgo(account.last_used_at) : 'chưa dùng'}</p>
                </div>
                {account.permissions.map((p) => <Badge key={p}>{p}</Badge>)}
                {account.revoked_at ? <Badge tone="red">Đã thu hồi</Badge> : (
                  <IconButton icon={Trash2} label="Thu hồi" className="text-rose-600" onClick={async () => { await adminApi.revokeServiceAccount(account.id).catch((err) => toast.error(errorMessage(err))); load() }} />
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Modal open={creating} onClose={() => setCreating(false)} size="sm" title="Tạo khóa API"
        footer={<><Button variant="secondary" onClick={() => setCreating(false)}>Hủy</Button><Button type="submit" form="sa-form">Tạo</Button></>}>
        <form id="sa-form" onSubmit={create}>
          <Field label="Tên" hint="Chữ thường, số, dấu chấm, gạch ngang. VD: uptime-monitor">
            <Input value={name} onChange={(e) => setName(e.target.value.toLowerCase())} required minLength={3} pattern="[a-z0-9][a-z0-9._-]*" />
          </Field>
        </form>
      </Modal>
      <Modal open={!!created} onClose={() => setCreated(null)} title="Lưu khóa API ngay"
        footer={<Button onClick={() => setCreated(null)}>Tôi đã lưu</Button>}>
        <Alert tone="amber">Khóa chỉ hiển thị một lần duy nhất.</Alert>
        <div className="mt-4 flex gap-2">
          <Input readOnly value={created ?? ''} className="font-mono text-xs" />
          <IconButton icon={Copy} label="Sao chép" onClick={() => { void navigator.clipboard.writeText(created ?? ''); toast.success('Đã sao chép.') }} />
        </div>
      </Modal>
    </>
  )
}
