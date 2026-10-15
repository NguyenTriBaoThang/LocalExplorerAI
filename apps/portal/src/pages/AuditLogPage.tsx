import { useEffect, useMemo, useState } from 'react'
import { History, Search } from 'lucide-react'
import { Badge, Card, EmptyState, Input, PageHeader, Select, Spinner } from '../components/ui'
import { errorMessage } from '../lib/api'
import { formatDateTime, timeAgo } from '../lib/format'
import type { AuditLog } from '../lib/types'

const ACTION_LABELS: Record<string, string> = {
  created: 'Tạo', updated: 'Cập nhật', hidden: 'Ẩn', approve: 'Duyệt', reject: 'Từ chối', suspend: 'Tạm khóa', reactivate: 'Mở lại',
  sessions_revoked: 'Thu hồi phiên', application_submitted: 'Gửi hồ sơ', application_resubmitted: 'Gửi lại hồ sơ', role_permissions_updated: 'Đổi quyền',
  publish: 'Xuất bản', draft: 'Chuyển nháp', hide: 'Ẩn', deleted: 'Xóa', replied: 'Trả lời', merged: 'Gộp',
  staged: 'Nhập vào kho', submitted: 'Gửi', candidate_evidence_submitted: 'Gửi minh chứng', payment_checkout_created: 'Bắt đầu thanh toán',
  connection_tested: 'Kiểm tra kết nối', settings_updated: 'Đổi cấu hình', revoked: 'Thu hồi',
}
const TARGETS: Record<string, string> = {
  poi: 'Địa điểm', experience: 'Trải nghiệm', experience_slot: 'Slot', slot: 'Slot', provider: 'Đối tác', user: 'Người dùng', role: 'Vai trò',
  banner: 'Banner', article: 'Bài viết', collection: 'Bộ sưu tập', review: 'Đánh giá', evidence: 'Minh chứng', booking: 'Đặt chỗ', service_account: 'Khóa API', place_import_batch: 'Lô nhập địa điểm', place: 'Địa điểm', integration: 'Tích hợp',
}
const TONES: Record<string, 'green' | 'red' | 'amber' | 'brand' | 'gray'> = { approve: 'green', publish: 'green', created: 'brand', reject: 'red', suspend: 'red', deleted: 'red', hidden: 'gray', hide: 'gray', updated: 'amber' }

/** Shared by admin (whole system) and partner (own records) — the loader decides the scope. */
export function AuditLogPage({ title, description, load }: { title: string; description: string; load: () => Promise<AuditLog[]> }) {
  const [rows, setRows] = useState<AuditLog[] | null>(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [target, setTarget] = useState('')

  useEffect(() => { load().then(setRows).catch((err) => { setError(errorMessage(err)); setRows([]) }) }, [load])
  const targets = useMemo(() => [...new Set((rows ?? []).map((row) => row.target_type))].sort(), [rows])
  const visible = (rows ?? []).filter((row) => (!target || row.target_type === target) && (row.action + row.target_id + (row.actor_name ?? '') + (row.actor_email ?? '')).toLowerCase().includes(query.toLowerCase()))

  return (
    <>
      <PageHeader title={title} description={description} />
      <div className="mb-5 flex flex-wrap gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm người, hành động, ID…" className="pl-9" />
        </div>
        <Select value={target} onChange={(e) => setTarget(e.target.value)} className="w-auto">
          <option value="">Mọi đối tượng</option>
          {targets.map((item) => <option key={item} value={item}>{TARGETS[item] ?? item}</option>)}
        </Select>
      </div>
      <Card className="overflow-hidden">
        {!rows ? <Spinner /> : visible.length === 0 ? <EmptyState icon={History} title="Chưa có hoạt động" description={error || undefined} /> : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="table-head"><tr><th className="px-5 py-3 font-medium">Thời gian</th><th className="px-5 py-3 font-medium">Người thực hiện</th><th className="px-5 py-3 font-medium">Hành động</th><th className="px-5 py-3 font-medium">Đối tượng</th><th className="px-5 py-3 font-medium">Chi tiết</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {visible.map((row) => {
                  const verb = row.action.split('.').slice(-1)[0]
                  return (
                    <tr key={row.id} className="align-top hover:bg-slate-50/60">
                      <td className="whitespace-nowrap px-5 py-3"><p className="text-slate-900">{timeAgo(row.created_at)}</p><p className="text-xs text-slate-500">{formatDateTime(row.created_at)}</p></td>
                      <td className="px-5 py-3"><p className="text-slate-900">{row.actor_name || (row.actor_id ? 'Người dùng đã xóa' : 'Hệ thống')}</p>{row.actor_email && <p className="text-xs text-slate-500">{row.actor_email}</p>}</td>
                      <td className="px-5 py-3"><Badge tone={TONES[verb] ?? 'gray'}>{ACTION_LABELS[verb] ?? verb}</Badge><p className="mt-1 font-mono text-[11px] text-slate-400">{row.action}</p></td>
                      <td className="px-5 py-3"><p className="text-slate-700">{TARGETS[row.target_type] ?? row.target_type}</p><p className="font-mono text-[11px] text-slate-400">{row.target_id.slice(0, 12)}</p></td>
                      <td className="max-w-md px-5 py-3"><code className="line-clamp-2 break-all text-xs text-slate-500">{Object.keys(row.details ?? {}).length ? JSON.stringify(row.details) : '—'}</code></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
