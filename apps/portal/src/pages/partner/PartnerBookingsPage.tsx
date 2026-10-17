import { useCallback, useEffect, useMemo, useState } from 'react'
import { CalendarCheck, Check, RefreshCw, X } from 'lucide-react'
import { Alert, Button, Card, EmptyState, Field, Modal, PageHeader, Spinner, StatusBadge, Tabs, Textarea, useToast } from '../../components/ui'
import { errorMessage, partnerApi } from '../../lib/api'
import { formatDateTime, formatMoney, timeAgo } from '../../lib/format'
import type { Booking } from '../../lib/types'
import { usePartner } from './PartnerLayout'

type Filter = 'action' | 'upcoming' | 'all'
type Decision = { booking: Booking; kind: 'booking' | 'cancellation'; approve: boolean }
const NEEDS_ACTION = new Set(['pending_provider', 'cancellation_requested'])

export function PartnerBookingsPage() {
  const { profile } = usePartner()
  const toast = useToast()
  const [bookings, setBookings] = useState<Booking[] | null>(null)
  const [filter, setFilter] = useState<Filter>('action')
  const [decision, setDecision] = useState<Decision | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      setBookings(await partnerApi.bookings())
    } catch (err) {
      toast.error(errorMessage(err))
      setBookings([])
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (profile.can_publish) void load(); else setBookings([]) }, [load, profile.can_publish])

  const counts = useMemo(() => ({
    action: (bookings ?? []).filter((b) => NEEDS_ACTION.has(b.status)).length,
    upcoming: (bookings ?? []).filter((b) => b.status === 'confirmed' && b.slot_start_at && new Date(b.slot_start_at).getTime() > Date.now()).length,
  }), [bookings])
  const rows = useMemo(() => (bookings ?? []).filter((booking) => {
    if (filter === 'action') return NEEDS_ACTION.has(booking.status)
    if (filter === 'upcoming') return booking.status === 'confirmed' && booking.slot_start_at && new Date(booking.slot_start_at).getTime() > Date.now()
    return true
  }), [bookings, filter])

  const decide = async () => {
    if (!decision) return
    setBusy(true)
    try {
      if (decision.kind === 'booking') await partnerApi.decideBooking(decision.booking.id, decision.approve ? 'accept' : 'reject', note)
      else await partnerApi.decideCancellation(decision.booking.id, decision.approve ? 'approve' : 'reject', note)
      toast.success('Đã cập nhật yêu cầu.')
      setDecision(null)
      await load()
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (!bookings) return <Spinner />

  return (
    <>
      <PageHeader title="Đặt chỗ" description="Xác nhận yêu cầu giữ chỗ và xử lý yêu cầu hủy từ du khách."
        actions={<Button variant="secondary" icon={RefreshCw} onClick={() => void load()} disabled={!profile.can_publish}>Làm mới</Button>} />
      <div className="mb-5">
        <Tabs value={filter} onChange={setFilter} items={[
          { value: 'action', label: 'Cần xử lý', count: counts.action },
          { value: 'upcoming', label: 'Sắp diễn ra', count: counts.upcoming },
          { value: 'all', label: 'Tất cả', count: bookings.length },
        ]} />
      </div>
      <Card className="overflow-hidden">
        {rows.length === 0 ? (
          <EmptyState icon={CalendarCheck} title={filter === 'action' ? 'Không có yêu cầu nào cần xử lý' : 'Chưa có đặt chỗ'} description="Khi du khách giữ chỗ trong slot của bạn, yêu cầu sẽ xuất hiện ở đây." />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="table-head">
                <tr>
                  <th className="px-5 py-3 font-medium">Trải nghiệm</th>
                  <th className="px-5 py-3 font-medium">Slot</th>
                  <th className="px-5 py-3 font-medium">Khách</th>
                  <th className="px-5 py-3 font-medium">Số tiền</th>
                  <th className="px-5 py-3 font-medium">Trạng thái</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((booking) => (
                  <tr key={booking.id} className="hover:bg-slate-50/60">
                    <td className="px-5 py-3">
                      <p className="font-medium text-slate-900">{booking.experience_title}</p>
                      <p className="text-xs text-slate-500">Yêu cầu {timeAgo(booking.created_at)}</p>
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-slate-700">{formatDateTime(booking.slot_start_at)}</td>
                    <td className="px-5 py-3 text-slate-700">{booking.quantity}</td>
                    <td className="whitespace-nowrap px-5 py-3 font-medium text-slate-900">{formatMoney(booking.amount_vnd)}</td>
                    <td className="px-5 py-3">
                      <StatusBadge status={booking.status} />
                      {booking.hold_expires_at && NEEDS_ACTION.has(booking.status) && <p className="mt-1 text-xs text-slate-500">Hết hạn {timeAgo(booking.hold_expires_at)}</p>}
                    </td>
                    <td className="whitespace-nowrap px-5 py-3 text-right">
                      {NEEDS_ACTION.has(booking.status) && (
                        <div className="inline-flex gap-1.5">
                          <Button size="sm" variant="secondary" icon={X} onClick={() => { setNote(''); setDecision({ booking, kind: booking.status === 'pending_provider' ? 'booking' : 'cancellation', approve: false }) }}>Từ chối</Button>
                          <Button size="sm" variant="success" icon={Check} onClick={() => { setNote(''); setDecision({ booking, kind: booking.status === 'pending_provider' ? 'booking' : 'cancellation', approve: true }) }}>
                            {booking.status === 'pending_provider' ? 'Nhận khách' : 'Đồng ý hủy'}
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal open={!!decision} onClose={() => setDecision(null)} size="sm"
        title={decision?.kind === 'booking' ? (decision.approve ? 'Nhận yêu cầu đặt chỗ?' : 'Từ chối yêu cầu đặt chỗ?') : (decision?.approve ? 'Đồng ý hủy?' : 'Từ chối yêu cầu hủy?')}
        description={decision ? `${decision.booking.experience_title} · ${decision.booking.quantity} khách` : undefined}
        footer={<><Button variant="secondary" onClick={() => setDecision(null)}>Đóng</Button><Button variant={decision?.approve ? 'success' : 'danger'} loading={busy} onClick={decide}>Xác nhận</Button></>}>
        <div className="space-y-4">
          {decision?.kind === 'booking' && decision.approve && <Alert tone="brand">Hãy chắc chắn slot vẫn còn đủ chỗ. Với booking có phí, khách sẽ được chuyển sang bước thanh toán.</Alert>}
          <Field label="Ghi chú cho khách" hint="Không bắt buộc"><Textarea value={note} onChange={(e) => setNote(e.target.value)} className="min-h-[72px]" /></Field>
        </div>
      </Modal>
    </>
  )
}
