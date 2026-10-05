import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Ban, Building2, Check, ExternalLink, Plus, RotateCcw, Search, X } from 'lucide-react'
import {
  Alert, Avatar, Badge, Button, Card, DescriptionList, Drawer, EmptyState, Field, Input, Modal, PageHeader, Pagination, Spinner, StatusBadge, Tabs, Textarea, useToast,
} from '../../components/ui'
import { adminApi, errorMessage } from '../../lib/api'
import { BUSINESS_TYPES, formatDate, formatDateTime, formatMoney, ROLES, timeAgo } from '../../lib/format'
import type { AdminProvider, AdminProviderDetail } from '../../lib/types'
import { usePendingPartners } from './AdminLayout'

type StatusFilter = 'pending' | 'verified' | 'rejected' | 'suspended' | ''
type Action = 'approve' | 'reject' | 'suspend' | 'reactivate'
const LIMIT = 20
const ACTION_COPY: Record<Action, { title: string; button: string; variant: 'success' | 'danger' | 'primary'; needsReason: boolean; text: string }> = {
  approve: { title: 'Duyệt hồ sơ đối tác', button: 'Duyệt', variant: 'success', needsReason: false, text: 'Đối tác sẽ có thể tạo trải nghiệm và mở slot ngay. Một email thông báo sẽ được gửi.' },
  reject: { title: 'Từ chối hồ sơ', button: 'Từ chối', variant: 'danger', needsReason: true, text: 'Đối tác sẽ thấy lý do và có thể cập nhật hồ sơ để gửi lại.' },
  suspend: { title: 'Tạm khóa đối tác', button: 'Tạm khóa', variant: 'danger', needsReason: true, text: 'Mọi trải nghiệm của đối tác sẽ bị ẩn khỏi du khách và đối tác không thể chỉnh sửa cho đến khi được mở lại.' },
  reactivate: { title: 'Mở lại đối tác', button: 'Mở lại', variant: 'primary', needsReason: false, text: 'Trải nghiệm của đối tác sẽ hiển thị trở lại.' },
}

export function AdminPartnersPage() {
  const toast = useToast()
  const { refreshPending } = usePendingPartners()
  const [params, setParams] = useSearchParams()
  const status = (params.get('status') ?? 'pending') as StatusFilter
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<{ items: AdminProvider[]; total: number } | null>(null)
  const [detail, setDetail] = useState<AdminProviderDetail | null>(null)
  const [action, setAction] = useState<Action | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [creating, setCreating] = useState(false)

  useEffect(() => { const id = window.setTimeout(() => setDebounced(query), 300); return () => window.clearTimeout(id) }, [query])
  useEffect(() => setOffset(0), [status, debounced])

  const load = useCallback(async () => {
    try {
      setPage(await adminApi.providers({ status, q: debounced, limit: LIMIT, offset }))
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }, [status, debounced, offset]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [load])

  const openDetail = useCallback(async (id: string) => {
    try {
      setDetail(await adminApi.provider(id))
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const id = params.get('open')
    if (id) { void openDetail(id); params.delete('open'); setParams(params, { replace: true }) }
  }, [params, setParams, openDetail])

  const setStatus = (value: StatusFilter) => setParams(value ? { status: value } : { status: '' })

  const decide = async () => {
    if (!detail || !action) return
    setBusy(true)
    try {
      await adminApi.decideProvider(detail.id, action, note)
      toast.success(`Đã ${ACTION_COPY[action].button.toLowerCase()} “${detail.name}”.`)
      setAction(null)
      await Promise.all([load(), openDetail(detail.id)])
      refreshPending()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const s = detail?.verification_status
  const available: Action[] = !detail ? [] : s === 'pending' ? ['reject', 'approve'] : s === 'rejected' ? ['approve'] : s === 'suspended' ? ['reactivate'] : ['suspend']

  return (
    <>
      <PageHeader title="Đối tác" description="Duyệt hồ sơ đăng ký và quản lý trạng thái các đối tác."
        actions={<Button icon={Plus} onClick={() => setCreating(true)}>Thêm đối tác</Button>} />

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Tabs value={status} onChange={setStatus} items={[
          { value: 'pending', label: 'Chờ duyệt' }, { value: 'verified', label: 'Đã duyệt' }, { value: 'rejected', label: 'Từ chối' },
          { value: 'suspended', label: 'Tạm khóa' }, { value: '', label: 'Tất cả' },
        ]} />
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm tên, email…" className="pl-9" />
        </div>
      </div>

      <Card className="overflow-hidden">
        {!page ? <Spinner /> : page.items.length === 0 ? (
          <EmptyState icon={Building2} title={status === 'pending' ? 'Không có hồ sơ chờ duyệt' : 'Không có đối tác'} />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="table-head">
                  <tr>
                    <th className="px-5 py-3 font-medium">Đối tác</th>
                    <th className="px-5 py-3 font-medium">Loại hình</th>
                    <th className="px-5 py-3 font-medium">Trải nghiệm</th>
                    <th className="px-5 py-3 font-medium">{status === 'pending' ? 'Ngày gửi' : 'Ngày tạo'}</th>
                    <th className="px-5 py-3 font-medium">Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {page.items.map((provider) => (
                    <tr key={provider.id} onClick={() => void openDetail(provider.id)} className="cursor-pointer hover:bg-slate-50/60">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar name={provider.name} size="sm" />
                          <div className="min-w-0">
                            <p className="truncate font-medium text-slate-900">{provider.name}</p>
                            <p className="truncate text-xs text-slate-500">{provider.contact_email ?? '—'}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3 text-slate-600">{provider.business_type ? BUSINESS_TYPES[provider.business_type] : '—'}</td>
                      <td className="px-5 py-3 text-slate-600">{provider.experience_count}</td>
                      <td className="whitespace-nowrap px-5 py-3 text-slate-600">{status === 'pending' ? timeAgo(provider.applied_at) : formatDate(provider.created_at)}</td>
                      <td className="px-5 py-3"><StatusBadge status={provider.verification_status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination offset={offset} limit={LIMIT} total={page.total} onChange={setOffset} />
          </>
        )}
      </Card>

      <Drawer open={!!detail} onClose={() => setDetail(null)}
        title={detail && <span className="flex items-center gap-2">{detail.name} <StatusBadge status={detail.verification_status} /></span>}
        subtitle={detail?.contact_email}
        footer={available.map((item) => (
          <Button key={item} variant={ACTION_COPY[item].variant === 'danger' ? 'secondary' : ACTION_COPY[item].variant}
            icon={{ approve: Check, reject: X, suspend: Ban, reactivate: RotateCcw }[item]}
            className={ACTION_COPY[item].variant === 'danger' ? 'text-rose-600' : undefined}
            onClick={() => { setNote(''); setAction(item) }}>{ACTION_COPY[item].button}</Button>
        ))}>
        {detail && (
          <div className="space-y-6">
            {detail.review_note && <Alert tone={detail.verification_status === 'verified' ? 'brand' : 'amber'} title="Ghi chú xét duyệt gần nhất">{detail.review_note}</Alert>}
            <section>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Thông tin cơ sở</h4>
              <DescriptionList items={[
                ['Loại hình', detail.business_type ? BUSINESS_TYPES[detail.business_type] : ''],
                ['Điện thoại', detail.contact_phone],
                ['Địa chỉ', detail.address],
                ['Website', detail.website && <a href={detail.website} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">{detail.website}</a>],
                ['Giới thiệu', detail.description],
                ['Ngày gửi', formatDateTime(detail.applied_at)],
                ['Ngày duyệt', formatDateTime(detail.reviewed_at)],
              ]} />
            </section>
            <section>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Pháp lý</h4>
              <DescriptionList items={[
                ['Mã số thuế', detail.tax_code],
                ['Giấy phép KD', detail.business_license_no],
                ['Giấy tờ', detail.document_urls.length > 0 && (
                  <ul className="space-y-1">
                    {detail.document_urls.map((url, index) => (
                      <li key={url}><a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand-600 hover:underline">Tài liệu {index + 1} <ExternalLink className="h-3 w-3" /></a></li>
                    ))}
                  </ul>
                )],
                ['Ghi chú', detail.application_note],
              ]} />
            </section>
            <section>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Tài khoản ({detail.users.length})</h4>
              <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
                {detail.users.map((member) => (
                  <li key={member.id} className="flex items-center gap-3 px-3 py-2.5">
                    <Avatar name={member.display_name || member.email} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-900">{member.display_name || member.email}</p>
                      <p className="truncate text-xs text-slate-500">{member.email}</p>
                    </div>
                    <Badge tone={member.is_active ? 'green' : 'red'}>{member.is_active ? ROLES[member.role] : 'Đã khóa'}</Badge>
                  </li>
                ))}
              </ul>
            </section>
            <section>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Trải nghiệm ({detail.experiences.length})</h4>
              {detail.experiences.length === 0 ? <p className="text-sm text-slate-500">Chưa có trải nghiệm.</p> : (
                <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
                  {detail.experiences.map((item) => (
                    <li key={item.id} className="flex items-center justify-between gap-3 px-3 py-2.5">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-900">{item.title}</p>
                        <p className="text-xs text-slate-500">{formatMoney(item.price_vnd)} · {item.duration_min} phút · {item.open_slot_count}/{item.slot_count} slot mở</p>
                      </div>
                      <StatusBadge status={item.verification_status} />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
      </Drawer>

      <Modal open={!!action} onClose={() => setAction(null)} size="sm" title={action ? ACTION_COPY[action].title : ''} description={detail?.name}
        footer={<><Button variant="secondary" onClick={() => setAction(null)}>Hủy</Button>
          <Button variant={action ? ACTION_COPY[action].variant : 'primary'} loading={busy} disabled={!!action && ACTION_COPY[action].needsReason && !note.trim()} onClick={decide}>{action && ACTION_COPY[action].button}</Button></>}>
        {action && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">{ACTION_COPY[action].text}</p>
            <Field label={ACTION_COPY[action].needsReason ? 'Lý do (gửi cho đối tác)' : 'Ghi chú (không bắt buộc)'} required={ACTION_COPY[action].needsReason}>
              <Textarea value={note} onChange={(e) => setNote(e.target.value)} className="min-h-[88px]" autoFocus />
            </Field>
          </div>
        )}
      </Modal>

      {creating && <CreatePartnerModal onClose={() => setCreating(false)} onCreated={async () => { setCreating(false); toast.success('Đã tạo đối tác.'); await load() }} />}
    </>
  )
}

function CreatePartnerModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ name: '', email: '', password: '', contact_phone: '', address: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await adminApi.createProvider({ ...form, contact_phone: form.contact_phone || undefined })
      onCreated()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open onClose={onClose} title="Thêm đối tác" description="Đối tác do quản trị viên tạo được duyệt sẵn."
      footer={<><Button variant="secondary" onClick={onClose}>Hủy</Button><Button type="submit" form="create-partner" loading={busy}>Tạo đối tác</Button></>}>
      <form id="create-partner" onSubmit={submit} className="space-y-4">
        {error && <Alert tone="red">{error}</Alert>}
        <Field label="Tên cơ sở" required><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required minLength={2} /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Email đăng nhập" required><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></Field>
          <Field label="Mật khẩu tạm" required hint="Tối thiểu 12 ký tự"><Input type="text" minLength={12} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required /></Field>
          <Field label="Điện thoại"><Input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} /></Field>
          <Field label="Địa chỉ"><Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></Field>
        </div>
      </form>
    </Modal>
  )
}
