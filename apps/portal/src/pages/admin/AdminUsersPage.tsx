import { useCallback, useEffect, useState } from 'react'
import { LogOut, Save, Search, ShieldCheck, Users } from 'lucide-react'
import { useAuth } from '../../auth/AuthContext'
import {
  Alert, Avatar, Badge, Button, Card, DescriptionList, Drawer, EmptyState, Field, Input, Modal, PageHeader, Pagination, Select, Spinner, StatusBadge, Toggle, useToast,
} from '../../components/ui'
import { adminApi, errorMessage } from '../../lib/api'
import { formatDate, formatDateTime, ROLES, timeAgo } from '../../lib/format'
import type { AdminProvider, AdminUser, AdminUserDetail, Role } from '../../lib/types'

const LIMIT = 25
const ROLE_TONE = { admin: 'violet', provider: 'brand', traveler: 'gray' } as const

export function AdminUsersPage() {
  const { user: me } = useAuth()
  const toast = useToast()
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [role, setRole] = useState<Role | ''>('')
  const [active, setActive] = useState<'' | 'true' | 'false'>('')
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<{ items: AdminUser[]; total: number } | null>(null)
  const [detail, setDetail] = useState<AdminUserDetail | null>(null)

  useEffect(() => { const id = window.setTimeout(() => setDebounced(query), 300); return () => window.clearTimeout(id) }, [query])
  useEffect(() => setOffset(0), [debounced, role, active])

  const load = useCallback(async () => {
    try {
      setPage(await adminApi.users({ q: debounced, role, active: active === '' ? '' : active === 'true', limit: LIMIT, offset }))
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }, [debounced, role, active, offset]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [load])

  const openDetail = async (id: string) => {
    try {
      setDetail(await adminApi.user(id))
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <>
      <PageHeader title="Người dùng" description="Tìm kiếm, phân quyền và khóa tài khoản trên toàn hệ thống." />

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm tên hoặc email…" className="pl-9" />
        </div>
        <Select value={role} onChange={(e) => setRole(e.target.value as Role | '')} className="w-auto">
          <option value="">Mọi vai trò</option>
          {Object.entries(ROLES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </Select>
        <Select value={active} onChange={(e) => setActive(e.target.value as '' | 'true' | 'false')} className="w-auto">
          <option value="">Mọi trạng thái</option>
          <option value="true">Đang hoạt động</option>
          <option value="false">Đã khóa</option>
        </Select>
        {page && <span className="ml-auto text-sm text-slate-500">{page.total} người dùng</span>}
      </div>

      <Card className="overflow-hidden">
        {!page ? <Spinner /> : page.items.length === 0 ? <EmptyState icon={Users} title="Không tìm thấy người dùng" /> : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="table-head">
                  <tr>
                    <th className="px-5 py-3 font-medium">Người dùng</th>
                    <th className="px-5 py-3 font-medium">Vai trò</th>
                    <th className="px-5 py-3 font-medium">Đối tác</th>
                    <th className="px-5 py-3 font-medium">Email</th>
                    <th className="px-5 py-3 font-medium">Ngày tạo</th>
                    <th className="px-5 py-3 font-medium">Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {page.items.map((item) => (
                    <tr key={item.id} onClick={() => void openDetail(item.id)} className="cursor-pointer hover:bg-slate-50/60">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar name={item.display_name || item.email} size="sm" />
                          <div className="min-w-0">
                            <p className="truncate font-medium text-slate-900">{item.display_name || '—'}{item.id === me?.id && <span className="ml-1.5 text-xs font-normal text-slate-400">(bạn)</span>}</p>
                            <p className="truncate text-xs text-slate-500">{item.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3"><Badge tone={ROLE_TONE[item.role]}>{ROLES[item.role]}</Badge></td>
                      <td className="max-w-[180px] truncate px-5 py-3 text-slate-600">{item.provider_name ?? '—'}</td>
                      <td className="px-5 py-3">{item.email_verified_at ? <Badge tone="green">Đã xác minh</Badge> : <Badge>Chưa xác minh</Badge>}</td>
                      <td className="whitespace-nowrap px-5 py-3 text-slate-600">{formatDate(item.created_at)}</td>
                      <td className="px-5 py-3"><StatusBadge status={item.is_active ? 'active' : 'inactive'} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination offset={offset} limit={LIMIT} total={page.total} onChange={setOffset} />
          </>
        )}
      </Card>

      {detail && <UserDrawer key={detail.id} detail={detail} isSelf={detail.id === me?.id} onClose={() => setDetail(null)}
        onChanged={async () => { await Promise.all([load(), openDetail(detail.id)]) }} />}
    </>
  )
}

function UserDrawer({ detail, isSelf, onClose, onChanged }: { detail: AdminUserDetail; isSelf: boolean; onClose: () => void; onChanged: () => Promise<void> }) {
  const toast = useToast()
  const [role, setRole] = useState<Role>(detail.role)
  const [isActive, setIsActive] = useState(detail.is_active)
  const [providerId, setProviderId] = useState(detail.provider_id ?? '')
  const [providers, setProviders] = useState<AdminProvider[]>([])
  const [busy, setBusy] = useState(false)
  const [confirmRevoke, setConfirmRevoke] = useState(false)
  const dirty = role !== detail.role || isActive !== detail.is_active || (role === 'provider' && providerId !== (detail.provider_id ?? ''))

  useEffect(() => {
    if (role === 'provider' && providers.length === 0) adminApi.providers({ limit: 500, offset: 0 }).then((page) => setProviders(page.items)).catch(() => undefined)
  }, [role, providers.length])

  const save = async () => {
    setBusy(true)
    try {
      await adminApi.updateUser(detail.id, { role, is_active: isActive, provider_id: role === 'provider' ? providerId || null : null })
      toast.success('Đã cập nhật người dùng. Các phiên cũ đã bị đăng xuất.')
      await onChanged()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const revoke = async () => {
    setBusy(true)
    try {
      await adminApi.revokeSessions(detail.id)
      toast.success('Đã đăng xuất người dùng khỏi mọi thiết bị.')
      setConfirmRevoke(false)
      await onChanged()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Drawer open onClose={onClose}
      title={<span className="flex items-center gap-3"><Avatar name={detail.display_name || detail.email} />{detail.display_name || detail.email}</span>}
      subtitle={detail.email}
      footer={<>
        <Button variant="secondary" icon={LogOut} disabled={isSelf || detail.active_sessions === 0} onClick={() => setConfirmRevoke(true)}>Đăng xuất mọi thiết bị</Button>
        <Button icon={Save} disabled={!dirty || isSelf || (role === 'provider' && !providerId)} loading={busy} onClick={save}>Lưu thay đổi</Button>
      </>}>
      <div className="space-y-6">
        {isSelf && <Alert tone="brand">Đây là tài khoản của bạn. Bạn không thể tự đổi vai trò hoặc khóa chính mình.</Alert>}
        <section>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Thông tin</h4>
          <DescriptionList items={[
            ['Điện thoại', detail.phone],
            ['Email', detail.email_verified_at ? `Đã xác minh ${formatDate(detail.email_verified_at)}` : 'Chưa xác minh'],
            ['Xác thực 2 lớp', detail.mfa_enabled ? <span className="inline-flex items-center gap-1 text-emerald-700"><ShieldCheck className="h-4 w-4" /> Đang bật</span> : 'Chưa bật'],
            ['Phiên đang hoạt động', String(detail.active_sessions)],
            ['Ngày tạo', formatDateTime(detail.created_at)],
          ]} />
        </section>
        <section className="space-y-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Phân quyền</h4>
          <Field label="Vai trò">
            <Select value={role} disabled={isSelf} onChange={(e) => setRole(e.target.value as Role)}>
              {Object.entries(ROLES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </Select>
          </Field>
          {role === 'provider' && (
            <Field label="Thuộc đối tác" required hint="Tài khoản đối tác phải gắn với một hồ sơ đối tác.">
              <Select value={providerId} onChange={(e) => setProviderId(e.target.value)}>
                <option value="">— Chọn đối tác —</option>
                {providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}
              </Select>
            </Field>
          )}
          <div className="rounded-lg border border-slate-200 p-3">
            <Toggle checked={isActive} onChange={(value) => !isSelf && setIsActive(value)} label={isActive ? 'Tài khoản đang hoạt động' : 'Tài khoản đã bị khóa'} />
          </div>
          {dirty && <p className="text-xs text-amber-700">Đổi vai trò hoặc khóa tài khoản sẽ đăng xuất người dùng khỏi mọi thiết bị.</p>}
        </section>
        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Hoạt động gần đây</h4>
          {detail.audit.length === 0 ? <p className="text-sm text-slate-500">Chưa có hoạt động.</p> : (
            <ol className="relative space-y-4 border-l border-slate-200 pl-5">
              {detail.audit.map((entry, index) => (
                <li key={index} className="relative">
                  <span className="absolute -left-[25px] top-1.5 h-2 w-2 rounded-full bg-slate-300 ring-4 ring-white" />
                  <p className="font-mono text-xs text-slate-700">{entry.action}</p>
                  <p className="text-xs text-slate-500">{entry.target_type} · {timeAgo(entry.created_at)}{entry.actor_id && entry.actor_id !== detail.id ? ' · bởi quản trị viên' : ''}</p>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
      <Modal open={confirmRevoke} onClose={() => setConfirmRevoke(false)} size="sm" title="Đăng xuất mọi thiết bị?"
        footer={<><Button variant="secondary" onClick={() => setConfirmRevoke(false)}>Hủy</Button><Button variant="danger" loading={busy} onClick={revoke}>Đăng xuất</Button></>}>
        <p className="text-sm text-slate-600">{detail.display_name || detail.email} sẽ phải đăng nhập lại trên mọi thiết bị.</p>
      </Modal>
    </Drawer>
  )
}
