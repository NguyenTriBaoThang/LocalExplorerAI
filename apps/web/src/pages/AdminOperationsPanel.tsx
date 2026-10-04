import { useCallback, useEffect, useState } from 'react'
import { Activity, Bell, RefreshCw, ShieldAlert, Waves } from 'lucide-react'
import { adminApi, apiErrorMessage } from '../api/client'

type OperationsStatus = {
  generated_at: string
  notifications: Record<string, number>
  worker: { status: string; last_seen: string | null }
  last_job: { status: string; started_at: string; finished_at: string | null; processed_count: number; error_summary: string | null } | null
  active_events: number
  channels: { email_enabled: boolean }
  rate_limit_enabled: boolean
}

type JobRow = { id: string; job_name: string; status: string; started_at: string; finished_at: string | null; processed_count: number; error_summary: string | null }
type EventRow = { id: string; event_type: string; target_type: string; target_id: string; status: string; valid_until: string | null; metadata: Record<string, unknown>; created_at: string }
type NotificationRow = { id: string; channel: string; booking_id: string | null; event_id: string | null; subject: string; status: string; attempts: number; available_at: string; sent_at: string | null; last_error: string | null; created_at: string }

function dateLabel(value?: string | null) {
  return value ? new Date(value).toLocaleString('vi-VN') : '—'
}

export function AdminOperationsPanel() {
  const [status, setStatus] = useState<OperationsStatus | null>(null)
  const [jobs, setJobs] = useState<JobRow[]>([])
  const [events, setEvents] = useState<EventRow[]>([])
  const [notifications, setNotifications] = useState<NotificationRow[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const reload = useCallback(async () => {
    setLoading(true)
    const results = await Promise.allSettled([
      adminApi.operationsStatus(), adminApi.operationsJobs(),
      adminApi.operationsEvents(), adminApi.operationsNotifications(),
    ])
    const failures: string[] = []
    if (results[0].status === 'fulfilled') setStatus(results[0].value as OperationsStatus)
    else failures.push(`Trạng thái: ${apiErrorMessage(results[0].reason)}`)
    if (results[1].status === 'fulfilled') setJobs(results[1].value as JobRow[])
    else failures.push(`Jobs: ${apiErrorMessage(results[1].reason)}`)
    if (results[2].status === 'fulfilled') setEvents(results[2].value as EventRow[])
    else failures.push(`Sự kiện: ${apiErrorMessage(results[2].reason)}`)
    if (results[3].status === 'fulfilled') setNotifications(results[3].value as NotificationRow[])
    else failures.push(`Thông báo: ${apiErrorMessage(results[3].reason)}`)
    setError(failures.join(' · '))
    setLoading(false)
  }, [])

  useEffect(() => {
    void reload()
    const timer = window.setInterval(() => void reload(), 30_000)
    return () => window.clearInterval(timer)
  }, [reload])

  const notificationCounts = status?.notifications || {}
  const metrics = [
    ['Worker email outbox', status?.worker.status || '—'],
    ['Sự kiện đang hoạt động', String(status?.active_events ?? '—')],
    ['Thông báo đang chờ', String(notificationCounts.queued ?? '—')],
    ['Thông báo lỗi', String((notificationCounts.failed ?? 0) + (notificationCounts.retry ?? 0))],
    ['Email đã cấu hình', status ? (status.channels.email_enabled ? 'Có' : 'Chưa') : '—'],
    ['Rate limit', status ? (status.rate_limit_enabled ? 'Bật' : 'Tắt') : '—'],
  ]

  return (
    <div className="admin-tab-content animate-fadeIn">
      <div className="page-title-row-3d">
        <div>
          <h2 className="section-title-3d"><Activity size={19} /> Bảng vận hành</h2>
          <p className="page-subtext-3d">Theo dõi worker, job nền, sự kiện và gửi thông báo. Tự làm mới mỗi 30 giây.</p>
          {status?.generated_at && <small>Dữ liệu lúc {dateLabel(status.generated_at)}</small>}
        </div>
        <button type="button" className="btn-secondary-3d" onClick={() => void reload()} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} /> Làm mới
        </button>
      </div>
      {error && <div className="inline-alert-3d" role="alert"><ShieldAlert size={16} /><span>{error}</span></div>}

      <div className="admin-metrics-grid">
        {metrics.map(([label, value]) => <div className="admin-kpi-card" key={label}><small>{label}</small><strong>{value}</strong></div>)}
      </div>

      {status?.last_job && (
        <section className="admin-section-card" style={{ marginTop: 18 }}>
          <div className="admin-section-header"><h3>Job gửi thông báo gần nhất</h3></div>
          <div className="item-sub-meta">
            <span>Trạng thái: {status.last_job.status}</span>
            <span>Bắt đầu: {dateLabel(status.last_job.started_at)}</span>
            <span>Kết thúc: {dateLabel(status.last_job.finished_at)}</span>
            <span>Đã xử lý: {status.last_job.processed_count}</span>
            {status.last_job.error_summary && <span>Lỗi: {status.last_job.error_summary}</span>}
          </div>
        </section>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 18, marginTop: 18 }}>
        <section className="admin-section-card">
          <div className="admin-section-header"><h3><Activity size={17} /> Job gần đây ({jobs.length})</h3></div>
          {jobs.length ? jobs.map((job) => (
            <article className="moderation-item-card" key={job.id}>
              <div className="item-meta-info"><strong>{job.job_name} · {job.status}</strong><div className="item-sub-meta"><span>{dateLabel(job.started_at)}</span><span>{job.processed_count} xử lý</span></div>{job.error_summary && <small>{job.error_summary}</small>}</div>
            </article>
          )) : <p className="admin-empty-text">Chưa có lịch sử job được ghi nhận.</p>}
        </section>

        <section className="admin-section-card">
          <div className="admin-section-header"><h3><Waves size={17} /> Sự kiện gần đây ({events.length})</h3></div>
          {events.length ? events.map((event) => (
            <article className="moderation-item-card" key={event.id}>
              <div className="item-meta-info"><strong>{event.event_type} · {event.status}</strong><div className="item-sub-meta"><span>{event.target_type}: {event.target_id}</span><span>{dateLabel(event.created_at)}</span></div><small>Hết hạn: {dateLabel(event.valid_until)}</small></div>
            </article>
          )) : <p className="admin-empty-text">Chưa có sự kiện được ghi nhận.</p>}
        </section>
      </div>

      <section className="admin-section-card" style={{ marginTop: 18 }}>
        <div className="admin-section-header"><h3><Bell size={17} /> Hàng đợi thông báo ({notifications.length})</h3><p>Không hiển thị email người nhận hoặc nội dung tin nhắn.</p></div>
        {notifications.length ? (
          <div className="audit-table-list">
            {notifications.map((item) => (
              <div className="audit-entry-row" key={item.id}>
                <span className="audit-entry-time">{dateLabel(item.created_at)}</span>
                <span className="audit-entry-action">{item.channel} · {item.status} · {item.attempts} lần</span>
                <span className="audit-entry-target">{item.subject}{item.last_error ? ` · ${item.last_error}` : ''}</span>
              </div>
            ))}
          </div>
        ) : <p className="admin-empty-text">Chưa có thông báo nào.</p>}
      </section>
    </div>
  )
}
