import { useCallback, useEffect, useRef, useState } from 'react'
import { Activity, Bell, Mail, RefreshCw, ShieldCheck, Waves, AlertTriangle, Server } from 'lucide-react'
import { Alert, Badge, Button, Card, CardHeader, EmptyState, PageHeader, StatCard, StatusBadge } from '../../components/ui'
import { errorMessage } from '../../lib/api'
import { opsApi, type OperationsStatus, type OpsEventRow, type OpsJobRow, type OpsNotificationRow } from '../../lib/adminOps'

function dateLabel(value?: string | null) {
  return value ? new Date(value).toLocaleString('vi-VN') : '—'
}

export function AdminOperationsPage() {
  const [status, setStatus] = useState<OperationsStatus | null>(null)
  const [jobs, setJobs] = useState<OpsJobRow[]>([])
  const [events, setEvents] = useState<OpsEventRow[]>([])
  const [notifications, setNotifications] = useState<OpsNotificationRow[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const requestId = useRef(0)
  const inFlight = useRef(false)
  const mounted = useRef(true)

  const reload = useCallback(async (force = true) => {
    if (inFlight.current && !force) return
    const id = ++requestId.current
    inFlight.current = true
    setLoading(true)
    const results = await Promise.allSettled([opsApi.status(), opsApi.jobs(), opsApi.events(), opsApi.notifications()])
    if (!mounted.current || id !== requestId.current) return
    const failures: string[] = []
    if (results[0].status === 'fulfilled') setStatus(results[0].value)
    else failures.push(`Trạng thái: ${errorMessage(results[0].reason)}`)
    if (results[1].status === 'fulfilled') setJobs(results[1].value)
    else failures.push(`Jobs: ${errorMessage(results[1].reason)}`)
    if (results[2].status === 'fulfilled') setEvents(results[2].value)
    else failures.push(`Sự kiện: ${errorMessage(results[2].reason)}`)
    if (results[3].status === 'fulfilled') setNotifications(results[3].value)
    else failures.push(`Thông báo: ${errorMessage(results[3].reason)}`)
    setError(failures.join(' · '))
    inFlight.current = false
    setLoading(false)
  }, [])

  useEffect(() => {
    mounted.current = true
    void reload()
    const timer = window.setInterval(() => void reload(false), 30_000)
    return () => { mounted.current = false; window.clearInterval(timer) }
  }, [reload])

  const counts = status?.notifications ?? {}

  return (
    <>
      <PageHeader
        title="Bảng vận hành"
        description="Theo dõi worker, job nền, sự kiện và gửi thông báo. Tự làm mới mỗi 30 giây."
        actions={
          <>
            {status?.generated_at && <span className="text-xs text-slate-500">Dữ liệu lúc {dateLabel(status.generated_at)}</span>}
            <Button variant="secondary" icon={RefreshCw} loading={loading} onClick={() => void reload()}>Làm mới</Button>
          </>
        }
      />
      {error && <div className="mb-5"><Alert tone="red">{error}</Alert></div>}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard label="Worker email outbox" value={status?.worker.status || '—'} icon={Server} />
        <StatCard label="Sự kiện đang hoạt động" value={status ? String(status.active_events) : '—'} icon={Waves} tone="violet" />
        <StatCard label="Thông báo đang chờ" value={String(counts.queued ?? '—')} icon={Bell} tone="amber" />
        <StatCard label="Thông báo lỗi" value={status ? String((counts.failed ?? 0) + (counts.retry ?? 0)) : '—'} icon={AlertTriangle} tone="red" />
        <StatCard label="Email đã cấu hình" value={status ? (status.channels.email_enabled ? 'Có' : 'Chưa') : '—'} icon={Mail} tone="green" />
        <StatCard label="Rate limit" value={status ? (status.rate_limit_enabled ? 'Bật' : 'Tắt') : '—'} icon={ShieldCheck} tone="gray" />
      </div>

      {status?.last_job && (
        <Card className="mt-5">
          <CardHeader title="Job gửi thông báo gần nhất" />
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-4 text-sm text-slate-600">
            <span className="flex items-center gap-2">Trạng thái: <StatusBadge status={status.last_job.status} /></span>
            <span>Bắt đầu: {dateLabel(status.last_job.started_at)}</span>
            <span>Kết thúc: {dateLabel(status.last_job.finished_at)}</span>
            <span>Đã xử lý: {status.last_job.processed_count}</span>
            {status.last_job.error_summary && <span className="text-rose-700">Lỗi: {status.last_job.error_summary}</span>}
          </div>
        </Card>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title={`Job gần đây (${jobs.length})`} />
          {jobs.length === 0 ? <EmptyState icon={Activity} title="Chưa có lịch sử job được ghi nhận." /> : (
            <ul className="divide-y divide-slate-100">
              {jobs.map((job) => (
                <li key={job.id} className="px-5 py-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-slate-900">{job.job_name}</span>
                    <StatusBadge status={job.status} />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{dateLabel(job.started_at)} · {job.processed_count} xử lý</p>
                  {job.error_summary && <p className="mt-1 text-xs text-rose-700">{job.error_summary}</p>}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader title={`Sự kiện gần đây (${events.length})`} />
          {events.length === 0 ? <EmptyState icon={Waves} title="Chưa có sự kiện được ghi nhận." /> : (
            <ul className="divide-y divide-slate-100">
              {events.map((event) => (
                <li key={event.id} className="px-5 py-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-slate-900">{event.event_type}</span>
                    <StatusBadge status={event.status} />
                  </div>
                  <p className="mt-1 break-all text-xs text-slate-500">{event.target_type}: {event.target_id} · {dateLabel(event.created_at)}</p>
                  <p className="text-xs text-slate-500">Hết hạn: {dateLabel(event.valid_until)}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card className="mt-5 overflow-hidden">
        <CardHeader title={`Hàng đợi thông báo (${notifications.length})`} description="Không hiển thị email người nhận hoặc nội dung tin nhắn." />
        {notifications.length === 0 ? <EmptyState icon={Bell} title="Chưa có thông báo nào." /> : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="table-head">
                <tr>
                  <th className="px-5 py-3 font-medium">Thời gian</th>
                  <th className="px-5 py-3 font-medium">Kênh</th>
                  <th className="px-5 py-3 font-medium">Trạng thái</th>
                  <th className="px-5 py-3 font-medium">Số lần</th>
                  <th className="px-5 py-3 font-medium">Tiêu đề</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {notifications.map((item) => (
                  <tr key={item.id}>
                    <td className="whitespace-nowrap px-5 py-3 text-slate-500">{dateLabel(item.created_at)}</td>
                    <td className="px-5 py-3"><Badge>{item.channel}</Badge></td>
                    <td className="px-5 py-3"><StatusBadge status={item.status} /></td>
                    <td className="px-5 py-3">{item.attempts} lần</td>
                    <td className="px-5 py-3 text-slate-700">
                      {item.subject}
                      {item.last_error && <span className="block text-xs text-rose-700">{item.last_error}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
