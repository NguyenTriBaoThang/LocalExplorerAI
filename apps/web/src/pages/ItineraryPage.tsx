import { useEffect, useState, type FormEvent } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  Clock3,
  MapPin,
  Route,
  Wallet,
  Sparkles,
  Share2,
  Printer,
  CheckCircle2,
  AlertCircle,
  Car,
  Copy,
  Check,
  Star,
  RefreshCw,
  History,
  X,
  ShieldAlert,
  ShieldCheck,
  Flag,
} from 'lucide-react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  acceptReplan,
  api,
  apiErrorMessage,
  beginBookingCheckout,
  cancelBooking,
  createShareLink,
  getItinerary,
  getItineraryVersions,
  getMyBookings,
  getNotifications,
  requestReplanAdvice,
  requestBooking,
  submitFeedback,
} from '../api/client'
import { MapAdapter, LEG_COLORS, type MapPoint, type MapRoute } from '../components/map/MapAdapter'
import { SimulatedBadge } from '../components/common/StatusBadge'
import { TiltCard3D } from '../components/3d/TiltCard3D'
import type { Booking, Itinerary } from '../types'
import { useAuth } from '../auth'
import { useTranslation } from '../i18n'

const getReasonCopy = (code: string, locale: string): string => {
  const vi: Record<string, string> = {
    INTENT_MATCH: 'Ưu tiên trải nghiệm khớp chính xác với sở thích bạn đã chọn.',
    WITHIN_BUDGET: 'Chi phí ước tính nằm an toàn trong khoảng ngân sách bạn đặt.',
    SLOT_AVAILABLE: 'Khung giờ trải nghiệm khớp với mốc thời gian di chuyển của chuyến đi.',
    CAPACITY_UNKNOWN: 'Sức chứa chưa được cập nhật chính thức; hãy liên hệ trước khi đến.',
    MOCK_ROUTING: 'Thời gian di chuyển là ước tính theo ma trận mô phỏng, không phải dữ liệu giao thông thời gian thực.',
    GOONG_ROUTING: 'Quãng đường và thời gian đến dự kiến lấy từ Goong Directions; đây không phải dữ liệu giao thông trực tiếp.',
    SIMULATED_DATA: 'Dữ liệu trải nghiệm và giá tiền trong bản demo mô phỏng.',
    VERIFIED_DATA: 'POI, hoạt động và khung giờ có nguồn được duyệt, còn hiệu lực tại thời điểm lập lịch.',
    STALE_DATA: 'Một phần bằng chứng đã cũ hoặc hết hạn; cần xác minh lại trước khi đi.',
    UNVERIFIED_DATA: 'Một phần dữ liệu chưa được xác minh nguồn.',
    LOCKED_ACTIVITY: 'Trải nghiệm đã được bạn ghim cố định trong hành trình.',
    RULE_BASELINE_RANKER: 'Xếp hạng dùng quy tắc nhóm mục đích; chưa được kiểm chứng bằng lựa chọn thật của du khách.',
    ML_RANKER: 'Mô hình học máy chỉ sắp xếp các phương án đã vượt qua kiểm tra khả thi.',
    BOOTSTRAP_PILOT_RANKER: 'Ranker pilot học từ nhãn quy tắc yếu; đây là thử nghiệm, chưa chứng minh chất lượng với lựa chọn thật của du khách.',
  }
  const en: Record<string, string> = {
    INTENT_MATCH: 'Prioritized experience perfectly matching your chosen preferences.',
    WITHIN_BUDGET: 'Estimated expense is safely within your group budget limit.',
    SLOT_AVAILABLE: 'Experience timeslot synchronizes with transit schedule.',
    CAPACITY_UNKNOWN: 'Capacity not yet officially reported; please call ahead.',
    MOCK_ROUTING: 'Transit duration is estimated with a simulated routing matrix, not live traffic data.',
    GOONG_ROUTING: 'Distance and estimated duration come from Goong Directions; this is not live traffic data.',
    SIMULATED_DATA: 'Experience and pricing data in transparent simulated demo mode.',
    VERIFIED_DATA: 'POIs, experiences, and slots have approved, current source evidence at planning time.',
    STALE_DATA: 'Some evidence is outdated or expired; reconfirm before the trip.',
    UNVERIFIED_DATA: 'Some catalog data has not been source-verified.',
    LOCKED_ACTIVITY: 'Experience pinned and locked by your request.',
    RULE_BASELINE_RANKER: 'Ranking uses intent/category rules; it has not been validated against real traveler choices.',
    ML_RANKER: 'The machine-learning model only orders candidates that already passed feasibility checks.',
    BOOTSTRAP_PILOT_RANKER: 'This pilot ranker learned from weak rule-generated labels; it is experimental and not validated against real traveler choices.',
  }
  const dict = locale === 'en' ? en : vi
  return dict[code] ?? code.replaceAll('_', ' ')
}

const timeLabel = (value: string, locale: string) =>
  new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Ho_Chi_Minh',
  }).format(new Date(value))

const dateTimeLabel = (value: string, locale: string) =>
  new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Asia/Ho_Chi_Minh',
  }).format(new Date(value))

const bookingStatusLabel = (status: Booking['status'], locale: string) => {
  const vi: Record<Booking['status'], string> = {
    pending_provider: 'Chờ cơ sở xác nhận', awaiting_payment: 'Cơ sở đã xác nhận · chờ thanh toán',
    confirmed: 'Đã xác nhận', rejected: 'Cơ sở từ chối', cancelled: 'Đã hủy', expired: 'Hết hạn giữ chỗ',
    cancellation_requested: 'Đang yêu cầu hủy/hoàn tiền', refund_pending: 'Chờ xử lý hoàn tiền', refunded: 'Đã hoàn tiền',
  }
  const en: Record<Booking['status'], string> = {
    pending_provider: 'Waiting for provider', awaiting_payment: 'Provider confirmed · payment pending',
    confirmed: 'Confirmed', rejected: 'Rejected by provider', cancelled: 'Cancelled', expired: 'Hold expired',
    cancellation_requested: 'Cancellation/refund requested', refund_pending: 'Refund pending', refunded: 'Refunded',
  }
  return (locale === 'en' ? en : vi)[status]
}

export function ItineraryPage() {
  const { t, locale } = useTranslation()
  const { id = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const initial = (location.state as { itinerary?: Itinerary } | null)?.itinerary
  const [itinerary, setItinerary] = useState<Itinerary | null>(initial ?? null)
  const [loading, setLoading] = useState(!initial)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [isMapExpanded, setIsMapExpanded] = useState(false)
  const [copied, setCopied] = useState(false)
  const { user } = useAuth()
  const [shareToken, setShareToken] = useState('')
  const [shareUrl, setShareUrl] = useState('')
  const [currentTimeMs, setCurrentTimeMs] = useState(() => Date.now())
  const [notifications, setNotifications] = useState<
    Array<{ event_id: string; itinerary_id: string; stop_id: string; message: string; created_at?: string }>
  >([])
  const [versions, setVersions] = useState<
    Array<{
      version: number
      stops: Array<{
        experience_id: string
        name: string
        stop_order: number
        cost_vnd: number
        arrival_at?: string
        departure_at?: string
      }>
      total_cost_vnd: number
      total_travel_time_s: number
    }>
  >([])
  const [reviewText, setReviewText] = useState('')
  const [rating, setRating] = useState(5)
  const [notice, setNotice] = useState('')
  const [bookings, setBookings] = useState<Booking[]>([])
  const [bookingQuantity, setBookingQuantity] = useState(1)
  const [bookingBusyStopId, setBookingBusyStopId] = useState('')
  const [advice, setAdvice] = useState<
    Record<
      string,
      {
        base_version: number
        affected_stop_id: string
        proposals: Array<{
          code: 'B' | 'C'
          title: string
          candidate_experience_id: string
          candidate_slot_id: string
          cost_diff_vnd: number
          travel_time_diff_min: number
          estimated_return_time: string
          recommendation_reason_vi: string
          is_recommended: boolean
        }>
      }
    >
  >({})

  useEffect(() => {
    if (!id) return
    getItinerary(id)
      .then(setItinerary)
      .catch((reason) => setError(apiErrorMessage(reason)))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (itinerary?.group_size) setBookingQuantity(itinerary.group_size)
  }, [itinerary?.itinerary_id])

  useEffect(() => {
    const timer = window.setInterval(() => setCurrentTimeMs(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!user || !id) return
    getItineraryVersions(id).then(setVersions).catch(() => setVersions([]))
  }, [id, user?.id])

  useEffect(() => {
    if (!user || user.role !== 'traveler' || !id) {
      setBookings([])
      return
    }
    let active = true
    const returnParams = new URLSearchParams(location.search)
    const returnedPayment = returnParams.get('payment') === 'returned'
    const returnedBookingId = returnParams.get('booking')
    const deadline = Date.now() + 60_000
    let trackingPayment = returnedPayment && Boolean(returnedBookingId)
    const refresh = () => getMyBookings(id).then((rows) => {
      if (!active) return
      setBookings(rows)
      if (trackingPayment && returnedBookingId) {
        const returnedBooking = rows.find((row) => row.id === returnedBookingId)
        if (returnedBooking?.status === 'confirmed') {
          trackingPayment = false
          setNotice(locale === 'en' ? 'Payment was verified by the server; your reservation is confirmed.' : 'Máy chủ đã xác minh thanh toán; yêu cầu đặt chỗ của bạn đã được xác nhận.')
          navigate(location.pathname, { replace: true })
        } else if (returnedBooking?.status === 'refund_pending') {
          trackingPayment = false
          setNotice(locale === 'en' ? 'Payment was received, but the reservation needs manual reconciliation. Please contact support.' : 'Đã nhận thanh toán nhưng đặt chỗ cần được đối soát thủ công. Vui lòng liên hệ hỗ trợ.')
          navigate(location.pathname, { replace: true })
        } else if (returnedBooking?.payment_status === 'failed') {
          trackingPayment = false
          setNotice(locale === 'en' ? 'The payment provider reported that payment did not complete. You can retry checkout.' : 'Cổng thanh toán báo giao dịch chưa hoàn tất. Bạn có thể thử thanh toán lại.')
          navigate(location.pathname, { replace: true })
        } else if (Date.now() >= deadline) {
          trackingPayment = false
          setNotice(locale === 'en' ? 'Payment confirmation is still pending. Refresh your bookings shortly; do not pay again yet.' : 'Thanh toán vẫn đang chờ xác nhận. Hãy tải lại đặt chỗ sau ít phút; chưa thanh toán lại lúc này.')
          navigate(location.pathname, { replace: true })
        }
      }
    }).catch(() => undefined)
    void refresh()
    const timer = window.setInterval(refresh, returnedPayment ? 2000 : 15000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [id, location.pathname, location.search, locale, navigate, user?.id, user?.role])

  useEffect(() => {
    const paymentResult = new URLSearchParams(location.search).get('payment')
    if (paymentResult === 'invalid') {
      setNotice(locale === 'en'
        ? 'The payment return could not be verified. Check the reservation status before trying again.'
        : 'Không xác minh được thông tin quay về từ cổng thanh toán. Hãy kiểm tra trạng thái đặt chỗ trước khi thử lại.')
    } else if (paymentResult === 'returned') {
      setNotice(locale === 'en'
        ? 'Returned from the payment provider. Waiting for the server to verify the payment notification…'
        : 'Đã quay về từ cổng thanh toán. Đang chờ máy chủ xác minh thông báo thanh toán…')
    }
  }, [location.search, locale])

  useEffect(() => {
    if (!user || !id) return
    let active = true
    const refreshAlerts = () =>
      getNotifications()
        .then((rows) => {
          if (active) setNotifications(rows.filter((row) => row.itinerary_id === id))
        })
        .catch(() => undefined)
    void refreshAlerts()
    const timer = window.setInterval(refreshAlerts, 30000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [id, user?.id])

  const handleShare = async () => {
    try {
      const result = await createShareLink(id)
      const absolute = `${window.location.origin}${result.share_url}`
      setShareToken(result.share_token)
      setShareUrl(absolute)
      try {
        await navigator.clipboard.writeText(absolute)
        setCopied(true)
        setTimeout(() => setCopied(false), 2500)
      } catch {
        setNotice(locale === 'en' ? 'Link created below; please copy manually.' : 'Link đã tạo bên dưới; hãy sao chép thủ công.')
      }
    } catch {
      setNotice(locale === 'en' ? 'Sign in with trip owner account to generate shareable link.' : 'Đăng nhập bằng tài khoản chủ lịch để tạo liên kết chia sẻ.')
    }
  }

  async function handleFeedback(event: FormEvent) {
    event.preventDefault()
    try {
      await submitFeedback(id, rating, reviewText)
      setReviewText('')
      setNotice(locale === 'en' ? 'Review submitted successfully! Thank you for your feedback.' : 'Đã gửi đánh giá thành công! Cảm ơn bạn đã phản hồi.')
    } catch (reason) {
      setNotice(apiErrorMessage(reason))
    }
  }

  async function holdStop(stopId: string) {
    setBookingBusyStopId(stopId)
    try {
      const booking = await requestBooking(id, stopId, bookingQuantity)
      setBookings((rows) => [booking, ...rows.filter((row) => row.itinerary_stop_id !== stopId)])
      setNotice(locale === 'en'
        ? 'Seat hold requested. It is not a confirmed booking until the provider responds.'
        : 'Đã gửi yêu cầu giữ chỗ. Đây chưa phải đặt chỗ xác nhận cho tới khi cơ sở phản hồi.')
    } catch (reason) {
      setNotice(apiErrorMessage(reason))
    } finally {
      setBookingBusyStopId('')
    }
  }

  async function cancelReservation(booking: Booking) {
    setBookingBusyStopId(booking.itinerary_stop_id || '')
    try {
      const updated = await cancelBooking(booking.id)
      setBookings((rows) => rows.map((row) => row.id === updated.id ? updated : row))
      setNotice(updated.status === 'cancellation_requested'
        ? (locale === 'en' ? 'Cancellation requested; refund is not complete yet.' : 'Đã gửi yêu cầu hủy; khoản hoàn tiền chưa được xử lý.')
        : (locale === 'en' ? 'Reservation request cancelled.' : 'Đã hủy yêu cầu giữ chỗ.'))
    } catch (reason) {
      setNotice(apiErrorMessage(reason))
    } finally {
      setBookingBusyStopId('')
    }
  }

  async function checkoutBooking(booking: Booking) {
    try {
      const { checkout_url } = await beginBookingCheckout(booking.id)
      window.location.assign(checkout_url)
    } catch (reason) {
      setNotice(apiErrorMessage(reason))
    }
  }

  async function getAdvice(eventId: string) {
    try {
      const result = await requestReplanAdvice(id, eventId)
      setAdvice((old) => ({ ...old, [eventId]: result as unknown as (typeof old)[string] }))
    } catch {
      setNotice(locale === 'en' ? 'Unable to generate replan proposal. Please try again.' : 'Chưa thể tạo gợi ý đổi lịch. Vui lòng thử lại sau.')
    }
  }

  async function acceptProposal(
    eventId: string,
    proposal: NonNullable<(typeof advice)[string]['proposals']>[number]
  ) {
    const selected = advice[eventId]
    if (!selected) return
    try {
      await acceptReplan(id, {
        event_id: eventId,
        affected_stop_id: selected.affected_stop_id,
        candidate_experience_id: proposal.candidate_experience_id,
        candidate_slot_id: proposal.candidate_slot_id,
        proposal_code: proposal.code,
        base_version: selected.base_version,
      })
      setNotice(locale === 'en' ? 'Applied alternative proposal successfully!' : 'Đã áp dụng phương án mới thành công!')
      const updated = await getItinerary(id)
      setItinerary(updated)
      getItineraryVersions(id).then(setVersions).catch(() => undefined)
      setNotifications((old) => old.filter((item) => item.event_id !== eventId))
    } catch {
      setNotice(locale === 'en' ? 'Proposal no longer feasible or version outdated.' : 'Phương án không còn khả thi hoặc phiên bản lịch đã đổi.')
    }
  }

  const handlePrint = () => {
    window.print()
  }

  if (loading) {
    return (
      <div className="page-wrap page-loading-3d">
        <span className="loader-orbit" />
        <h2>{t('planner.planning')}</h2>
        <p>{locale === 'en' ? 'Algorithm is calculating optimal timeslots and transit buffers.' : 'Thuật toán đang tính toán các khung giờ và thứ tự di chuyển tối ưu nhất.'}</p>
      </div>
    )
  }

  if (error || !itinerary) {
    return (
      <div className="page-wrap not-found-3d">
        <div className="not-found-card">
          <AlertCircle size={40} className="text-amber" />
          <h1>{locale === 'en' ? 'Unable to load itinerary' : 'Chưa thể tải lịch trình'}</h1>
          <p>{error || (locale === 'en' ? 'Itinerary data not found.' : 'Không tìm thấy dữ liệu cho mã lịch trình này.')}</p>
          <Link to="/planner" className="btn-primary-3d">
            {t('nav.planNow')} <ArrowRight size={17} />
          </Link>
        </div>
      </div>
    )
  }

  const points: MapPoint[] = itinerary.stops.map((stop) => ({
    id: stop.experience_id,
    latitude: stop.poi.latitude,
    longitude: stop.poi.longitude,
    name: stop.name,
    category: stop.category,
    number: stop.position,
  }))
  if (itinerary.origin_latitude != null && itinerary.origin_longitude != null) {
    points.unshift({
      id: 'itinerary-origin', latitude: itinerary.origin_latitude, longitude: itinerary.origin_longitude,
      name: itinerary.origin_label || (locale === 'en' ? 'Trip origin' : 'Điểm xuất phát'), category: locale === 'en' ? 'Origin' : 'Điểm đi',
    })
  }
  if (itinerary.destination_latitude != null && itinerary.destination_longitude != null) {
    points.push({
      id: 'itinerary-destination', latitude: itinerary.destination_latitude, longitude: itinerary.destination_longitude,
      name: itinerary.destination_label || (locale === 'en' ? 'Return destination' : 'Điểm về'), category: locale === 'en' ? 'Destination' : 'Điểm về',
    })
  }
  const mapRoutes: MapRoute[] = (itinerary.routes ?? [])
    .filter((route) => route.geometry && route.geometry.length > 1)
    .map((route, index) => ({
      id: `${route.from_experience_id ?? 'origin'}-${route.to_experience_id ?? 'destination'}-${index}`,
      coordinates: route.geometry!,
      color: LEG_COLORS[index % LEG_COLORS.length],
    }))

  const activeStop = itinerary.stops.find((stop) => stop.experience_id === selectedId)
  const latestBookingByStop = new Map<string, Booking>()
  for (const booking of bookings) {
    if (booking.itinerary_stop_id && !latestBookingByStop.has(booking.itinerary_stop_id)) {
      latestBookingByStop.set(booking.itinerary_stop_id, booking)
    }
  }
  const lastStop = itinerary.stops[itinerary.stops.length - 1]
  const tripStartAt = itinerary.start_at || itinerary.stops[0]?.start_at
  const estimatedReturnAt = itinerary.estimated_return_at || lastStop?.end_at
  const totalMinutes = lastStop
    ? Math.round(
        (new Date(estimatedReturnAt || lastStop.end_at).getTime() -
          new Date(tripStartAt || itinerary.stops[0].start_at).getTime()) /
          60000
      )
    : 0

  return (
    <div className="itinerary-page-3d page-wrap">
      {/* Top Navigation & Actions */}
      <div className="itinerary-topbar">
        <Link to="/planner" className="btn-back-link">
          <ArrowLeft size={16} /> {t('itinerary.backToEdit')}
        </Link>
        <div className="topbar-actions">
          <button
            type="button"
            className="btn-action-icon"
            onClick={handleShare}
            title={t('itinerary.share')}
          >
            {copied ? <Check size={15} className="text-emerald" /> : <Share2 size={15} />}
            <span>{copied ? t('itinerary.copied') : t('itinerary.share')}</span>
          </button>
          <button
            type="button"
            className="btn-action-icon"
            onClick={handlePrint}
            title={t('itinerary.printSave')}
          >
            <Printer size={15} />
            <span>{t('itinerary.printSave')}</span>
          </button>
          <SimulatedBadge />
        </div>
      </div>

      {notice && (
        <div className="inline-alert-3d" role="status">
          <Sparkles size={16} className="text-emerald" />
          <span>{notice}</span>
          <button
            type="button"
            className="alert-dismiss-btn"
            onClick={() => setNotice('')}
            aria-label={t('common.close')}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Share Link Drawer Card */}
      {shareToken && (
        <div className="share-link-banner animate-fadeIn">
          <div className="share-link-info">
            <span className="share-link-label">{t('itinerary.publicShareUrl')}</span>
            <div className="share-input-group">
              <input
                readOnly
                value={shareUrl}
                onFocus={(event) => event.currentTarget.select()}
                className="share-url-field"
              />
              <button
                type="button"
                className="btn-primary-3d btn-sm"
                onClick={async () => {
                  await navigator.clipboard.writeText(shareUrl)
                  setCopied(true)
                  setTimeout(() => setCopied(false), 2000)
                }}
              >
                <Copy size={13} /> {copied ? t('itinerary.copiedShort') : t('itinerary.copy')}
              </button>
              <button
                type="button"
                className="btn-ghost-sm text-rose"
                onClick={async () => {
                  try {
                    await api.delete(`/itineraries/${id}/share`)
                    setShareToken('')
                    setShareUrl('')
                    setNotice(locale === 'en' ? 'Shareable link revoked.' : 'Đã thu hồi link chia sẻ.')
                  } catch {
                    setNotice(locale === 'en' ? 'Unable to revoke link.' : 'Không thể thu hồi liên kết.')
                  }
                }}
              >
                {t('itinerary.revokeShare')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cancelled Slot Alerts & Replan Advice */}
      {notifications.length > 0 && (
        <section className="replan-alert-card animate-fadeIn">
          <div className="replan-header">
            <ShieldAlert size={22} className="text-amber" />
            <div>
              <h3>{t('itinerary.slotChangeAlert')}</h3>
              <p>{t('itinerary.slotChangeDesc')}</p>
            </div>
          </div>

          <div className="notifications-list">
            {notifications.map((item) => (
              <div key={item.event_id} className="notification-row">
                <p className="notification-msg">{item.message}</p>
                <button
                  type="button"
                  className="btn-primary-3d btn-sm"
                  onClick={() => void getAdvice(item.event_id)}
                >
                  <RefreshCw size={13} /> {t('itinerary.findAlt')}
                </button>

                {advice[item.event_id]?.proposals.map((proposal) => (
                  <article key={proposal.code} className="proposal-card-3d">
                    <div className="proposal-top">
                      <div className="proposal-badge-wrap">
                        <span className="proposal-code">
                          {t('itinerary.proposal', { code: proposal.code })}
                        </span>
                        {proposal.is_recommended && (
                          <span className="proposal-rec-tag">{t('itinerary.optimalProposal')}</span>
                        )}
                      </div>
                      <h4>{proposal.title}</h4>
                    </div>

                    <div className="proposal-stats-row">
                      <span className="prop-stat">
                        {t('itinerary.diffCost', {
                          cost: `${proposal.cost_diff_vnd >= 0 ? '+' : ''}${proposal.cost_diff_vnd.toLocaleString('vi-VN')}₫`,
                        })}
                      </span>
                      <span className="prop-stat">
                        {t('itinerary.diffTravel', {
                          travel: `${proposal.travel_time_diff_min > 0 ? '+' : ''}${proposal.travel_time_diff_min} ${locale === 'en' ? 'mins' : 'phút'}`,
                        })}
                      </span>
                      <span className="prop-stat">
                        {t('itinerary.estReturn', { time: proposal.estimated_return_time })}
                      </span>
                    </div>

                    <p className="proposal-reason">{proposal.recommendation_reason_vi}</p>

                    <button
                      type="button"
                      className="btn-primary-3d btn-sm"
                      onClick={() => void acceptProposal(item.event_id, proposal)}
                    >
                      <Check size={14} /> {t('itinerary.applyProposal', { code: proposal.code })}
                    </button>
                  </article>
                ))}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Version History Diff Banner */}
      {versions.length > 1 && (
        <section className="version-diff-card">
          <div className="version-diff-header">
            <History size={18} className="text-cyan" />
            <div>
              <h3>{t('itinerary.revisionHistory')}</h3>
              <p>{t('itinerary.revisionDesc')}</p>
            </div>
          </div>
          {(() => {
            const oldVersion = versions[versions.length - 2]
            const newVersion = versions[versions.length - 1]
            const oldIds = oldVersion.stops.map((stop) => stop.experience_id)
            const newIds = newVersion.stops.map((stop) => stop.experience_id)
            const added = newVersion.stops.filter((stop) => !oldIds.includes(stop.experience_id))
            const removed = oldVersion.stops.filter((stop) => !newIds.includes(stop.experience_id))
            const costDiff = newVersion.total_cost_vnd - oldVersion.total_cost_vnd
            const timeDiff =
              (newVersion.total_travel_time_s - oldVersion.total_travel_time_s) / 60

            return (
              <div className="version-diff-body">
                <div className="version-badges-row">
                  <span className="version-chip">
                    {t('itinerary.versionShift', { old: oldVersion.version, next: newVersion.version })}
                  </span>
                  <span className="version-diff-stat">
                    {t('itinerary.costShift', {
                      cost: `${costDiff >= 0 ? '+' : ''}${costDiff.toLocaleString('vi-VN')}₫`,
                    })}
                  </span>
                  <span className="version-diff-stat">
                    {t('itinerary.travelShift', {
                      travel: `${timeDiff >= 0 ? '+' : ''}${timeDiff} ${locale === 'en' ? 'mins' : 'phút'}`,
                    })}
                  </span>
                </div>
                {added.length > 0 && (
                  <p className="version-changes-text">
                    <strong>{t('itinerary.newAddedStops', { stops: added.map((s) => s.name).join(', ') })}</strong>
                  </p>
                )}
                {removed.length > 0 && (
                  <p className="version-changes-text">
                    <strong>{t('itinerary.omittedStops', { stops: removed.map((s) => s.name).join(', ') })}</strong>
                  </p>
                )}
              </div>
            )
          })()}
        </section>
      )}

      {/* Main Heading & Feasibility Pill */}
      <div className="itinerary-header-3d">
        <div>
          <span className="eyebrow-3d">
            <span className="eyebrow-dot" /> {t('itinerary.eyebrow')}
          </span>
          <h1 className="page-heading-3d">
            {t('itinerary.headingMain')} <em>{t('itinerary.headingHighlight')}</em>
          </h1>
          <p className="page-subtext-3d">
            {t('itinerary.headingDesc', { count: itinerary.stops.length })}
          </p>
        </div>
        <div
          className={`feasibility-badge-3d ${
            itinerary.feasibility_status === 'tentative' ? 'feasibility-warning' : 'feasibility-ok'
          }`}
        >
          <span className="feasibility-dot" />
          <span>
            {itinerary.feasibility_status === 'tentative'
              ? t('itinerary.feasibilityTentative')
              : t('itinerary.feasibilityHigh')}
          </span>
        </div>
      </div>

      {/* 4 Glowing 3D Metric KPI Cards */}
      <div className="itinerary-metrics-grid">
        <TiltCard3D maxTilt={6} className="metric-kpi-card">
          <div className="kpi-icon-box text-emerald">
            <Clock3 size={20} />
          </div>
          <div className="kpi-info">
            <small>{t('itinerary.kpiDuration')}</small>
            <strong>
              {Math.floor(totalMinutes / 60)}h {totalMinutes % 60}p
            </strong>
            <span>
              {timeLabel(tripStartAt || itinerary.stops[0].start_at, locale)} —{' '}
              {timeLabel(estimatedReturnAt || lastStop.end_at, locale)}
            </span>
          </div>
        </TiltCard3D>

        <TiltCard3D maxTilt={6} className="metric-kpi-card">
          <div className="kpi-icon-box text-cyan">
            <Route size={20} />
          </div>
          <div className="kpi-info">
            <small>{t('itinerary.kpiTravel')}</small>
            <strong>{itinerary.total_travel_min} {locale === 'en' ? 'mins' : 'phút'}</strong>
            <span>{t('itinerary.kpiTravelSub')}</span>
          </div>
        </TiltCard3D>

        <TiltCard3D maxTilt={6} className="metric-kpi-card">
          <div className="kpi-icon-box text-amber">
            <Wallet size={20} />
          </div>
          <div className="kpi-info">
            <small>{t('itinerary.kpiCost')}</small>
            <strong>{itinerary.estimated_cost_vnd.toLocaleString('vi-VN')}₫</strong>
            <span>{t('itinerary.kpiCostSub')}</span>
          </div>
        </TiltCard3D>

        <TiltCard3D maxTilt={6} className="metric-kpi-card">
          <div className="kpi-icon-box text-rose">
            <MapPin size={20} />
          </div>
          <div className="kpi-info">
            <small>{t('itinerary.kpiStops')}</small>
            <strong>{itinerary.stops.length} {locale === 'en' ? 'stops' : 'trải nghiệm'}</strong>
            <span>{t('itinerary.kpiStopsSub')}</span>
          </div>
        </TiltCard3D>
      </div>

      {/* Content Split: 3D Timeline + Interactive Map */}
      <div className="itinerary-content-split">
        {/* Timeline Column */}
        <section className="timeline-col-3d">
          <div className="timeline-header-bar">
            <div>
              <span className="results-sub">{t('itinerary.timelineSubtitle')}</span>
              <strong className="timeline-main-title">{t('itinerary.timelineMain')}</strong>
            </div>
            <span className="timeline-date-chip">
              {new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'vi-VN', {
                dateStyle: 'medium',
                timeZone: 'Asia/Ho_Chi_Minh',
              }).format(new Date(itinerary.stops[0]?.start_at ?? itinerary.data_as_of))}
            </span>
          </div>

          <div className="timeline-stops-container">
            {itinerary.stops.map((stop, index) => {
              const nextStop = itinerary.stops[index + 1]
              const nextLeg = nextStop && itinerary.routes.find((route) =>
                route.from_experience_id === stop.experience_id && route.to_experience_id === nextStop.experience_id
              )
              return (
              <div key={stop.id} className="timeline-row-wrapper">
                <article
                  className={`timeline-stop-card-3d ${
                    selectedId === stop.experience_id ? 'stop-card-active' : ''
                  }`}
                  onMouseEnter={() => setSelectedId(stop.experience_id)}
                  onClick={() => setSelectedId(stop.experience_id)}
                  tabIndex={0}
                >
                  <div className="timeline-marker-col">
                    <span className="stop-number-badge">
                      {String(stop.position).padStart(2, '0')}
                    </span>
                    {index < itinerary.stops.length - 1 && (
                      <span className="timeline-laser-line" />
                    )}
                  </div>

                  <div className="stop-card-body">
                    <div className="stop-top-meta">
                      <span className="stop-time-range">
                        <Clock3 size={13} className="text-emerald" />
                        {timeLabel(stop.start_at, locale)} — {timeLabel(stop.end_at, locale)}
                      </span>
                      <span className="stop-category-tag">{stop.category}</span>
                    </div>

                    <h3 className="stop-title">{stop.name}</h3>

                    <p className="stop-address">
                      <MapPin size={13} className="text-emerald" /> {stop.poi.address}
                    </p>

                    <div className="stop-footer-meta">
                      <span className="meta-badge-item">
                        {t('itinerary.durationMinutes', { min: stop.duration_min })}
                      </span>
                      <span className="meta-badge-item">
                        {stop.cost_vnd.toLocaleString('vi-VN')}₫ / {locale === 'en' ? 'person' : 'người'}
                      </span>
                      {stop.availability_known ? (
                        <span className="stop-status-pill status-pill-confirmed">
                          <CheckCircle2 size={12} /> {t('itinerary.reportedCapacity')}
                        </span>
                      ) : (
                        <span className="stop-status-pill status-pill-tentative">
                          <AlertCircle size={12} /> {t('itinerary.callToConfirm')}
                        </span>
                      )}
                    </div>

                    <div className="stop-provenance">
                      <span className={`provenance-state provenance-${stop.data_status}`}>
                        {locale === 'en'
                          ? ({ verified: 'Source verified', stale: 'Source expired or outdated', simulated: 'Demo data', unverified: 'Not verified' } as const)[stop.data_status]
                          : ({ verified: 'Nguồn đã xác minh', stale: 'Nguồn hết hạn hoặc dữ liệu cũ', simulated: 'Dữ liệu trình diễn', unverified: 'Chưa xác minh' } as const)[stop.data_status]}
                      </span>
                      {stop.slot_confirmed_at && (
                        <span>
                          {locale === 'en' ? 'Slot confirmed' : 'Ca xác nhận'}: {dateTimeLabel(stop.slot_confirmed_at, locale)}
                        </span>
                      )}
                      {stop.slot_expires_at && (
                        <span>
                          {locale === 'en' ? 'Slot data expires' : 'Hạn dữ liệu ca'}: {dateTimeLabel(stop.slot_expires_at, locale)}
                        </span>
                      )}
                      {([
                        [locale === 'en' ? 'Place' : 'Địa điểm', stop.poi.source_evidence ?? []],
                        [locale === 'en' ? 'Experience' : 'Trải nghiệm', stop.source_evidence ?? []],
                        [locale === 'en' ? 'Availability' : 'Khung giờ', stop.slot_source_evidence ?? []],
                      ] as const).map(([label, evidence]) => (evidence?.length ?? 0) > 0 && (
                        <div className="stop-source-group" key={label}>
                          <span>{label}:</span>
                          {evidence.map((item) => (
                            <a key={item.id} href={item.source_uri} target="_blank" rel="noreferrer">
                              {item.source_label || item.source_type}
                              {item.expires_at && ` · ${locale === 'en' ? 'expires' : 'hết hạn'} ${dateTimeLabel(item.expires_at, locale)}`}
                            </a>
                          ))}
                        </div>
                      ))}
                    </div>

                    {user?.role === 'traveler' && (() => {
                      const booking = latestBookingByStop.get(stop.id)
                      const canCancel = booking && ['pending_provider', 'awaiting_payment', 'confirmed'].includes(booking.status)
                      const canRequestAgain = !booking || ['rejected', 'cancelled', 'expired', 'refunded'].includes(booking.status)
                      return (
                        <div className="booking-inline-panel" onClick={(event) => event.stopPropagation()}>
                          {booking ? (
                            <div className="booking-inline-status">
                              <strong>{locale === 'en' ? 'Reservation' : 'Yêu cầu đặt chỗ'}: {bookingStatusLabel(booking.status, locale)}</strong>
                              <span>{booking.quantity} {locale === 'en' ? 'guest(s)' : 'khách'} · {booking.amount_vnd.toLocaleString('vi-VN')}₫</span>
                              {booking.hold_expires_at && ['pending_provider', 'awaiting_payment'].includes(booking.status) && (
                                <small>{locale === 'en' ? 'Hold expires' : 'Giữ chỗ đến'}: {dateTimeLabel(booking.hold_expires_at, locale)}</small>
                              )}
                              {booking.payment_status === 'failed' && (
                                <small>{locale === 'en' ? 'Latest payment attempt did not complete; you may retry before the hold expires.' : 'Lần thanh toán gần nhất chưa hoàn tất; bạn có thể thử lại trước khi giữ chỗ hết hạn.'}</small>
                              )}
                              {booking.cancellation_reason && <small>{booking.cancellation_reason}</small>}
                            </div>
                          ) : (
                            <strong>{locale === 'en' ? 'Ask provider to confirm seats' : 'Yêu cầu cơ sở xác nhận chỗ'}</strong>
                          )}
                          {booking?.status === 'awaiting_payment' && (
                            <button type="button" className="btn-secondary-3d btn-sm" onClick={() => void checkoutBooking(booking)}>
                              {locale === 'en' ? 'Continue to payment' : 'Tiếp tục thanh toán'}
                            </button>
                          )}
                          {canCancel && booking && (
                            <button type="button" className="btn-secondary-3d btn-sm" disabled={bookingBusyStopId === stop.id} onClick={() => void cancelReservation(booking)}>
                              {locale === 'en' ? 'Request cancellation' : 'Yêu cầu hủy'}
                            </button>
                          )}
                          {canRequestAgain && stop.data_status === 'verified' && (
                            <div className="booking-inline-controls">
                              <label>
                                {locale === 'en' ? 'Guests' : 'Số khách'}
                                <input type="number" min={1} max={itinerary.group_size ?? 50} value={bookingQuantity} onChange={(event) => setBookingQuantity(Math.max(1, Math.min(itinerary.group_size ?? 50, Number(event.target.value) || 1)))} />
                              </label>
                              <button type="button" className="btn-primary-3d btn-sm" disabled={bookingBusyStopId === stop.id} onClick={() => void holdStop(stop.id)}>
                                {bookingBusyStopId === stop.id
                                  ? (locale === 'en' ? 'Sending…' : 'Đang gửi…')
                                  : (locale === 'en' ? 'Request temporary hold' : 'Yêu cầu giữ chỗ tạm thời')}
                              </button>
                            </div>
                          )}
                          {canRequestAgain && stop.data_status === 'verified' && (
                            <small>{locale === 'en' ? 'The app holds seats for 15 minutes while the provider responds; this is not confirmed until they accept.' : 'Ứng dụng giữ chỗ tạm 15 phút trong khi chờ cơ sở phản hồi; chưa xác nhận cho tới khi cơ sở chấp nhận.'}</small>
                          )}
                          {canRequestAgain && stop.data_status !== 'verified' && (
                            <small>{locale === 'en' ? 'Booking is disabled for demo or unverified catalog data.' : 'Chưa thể đặt chỗ với dữ liệu trình diễn hoặc chưa được xác minh.'}</small>
                          )}
                          {(booking?.amount_vnd || stop.cost_vnd) > 0 && (
                            <small>{locale === 'en' ? 'Checkout redirects to the configured payment provider. The reservation is confirmed only after the server verifies its payment notification.' : 'Thanh toán sẽ chuyển đến cổng đã cấu hình. Đặt chỗ chỉ được xác nhận sau khi máy chủ xác minh thông báo thanh toán.'}</small>
                          )}
                        </div>
                      )
                    })()}
                  </div>
                </article>

                {/* Travel Leg between stops with distinct color */}
                {nextStop && nextLeg && (() => {
                  const legIdx = index
                  const legColor = LEG_COLORS[legIdx % LEG_COLORS.length]
                  return (
                    <div className="travel-leg-indicator">
                      <div
                        className="travel-leg-pill"
                        style={{
                          borderLeft: `4px solid ${legColor}`,
                          background: 'rgba(15, 23, 42, 0.85)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          padding: '8px 14px',
                          borderRadius: '8px',
                          margin: '10px 0',
                        }}
                      >
                        <span
                          className="leg-mini-badge"
                          style={{
                            backgroundColor: legColor,
                            color: '#ffffff',
                            fontSize: '0.72rem',
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontWeight: 700,
                            letterSpacing: '0.5px',
                          }}
                        >
                          Chặng {legIdx + 1}
                        </span>
                        <Car size={14} style={{ color: legColor }} />
                        <span style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '0.85rem' }}>
                          {nextLeg.duration_min} {locale === 'en' ? 'mins travel' : 'phút di chuyển'}
                          {nextLeg.distance_m ? ` (~${(nextLeg.distance_m / 1000).toFixed(1)} km)` : ''}
                        </span>
                        <small style={{ color: '#94a3b8', fontSize: '0.75rem', marginLeft: 'auto' }}>
                          · Goong Directions
                        </small>
                      </div>
                    </div>
                  )
                })()}
              </div>
              )
            })}
          </div>
        </section>

        {/* Map Column */}
        <section className="map-col-3d">
          <div className="map-panel-header-3d">
            <div>
              <span className="map-sub">{t('itinerary.mapSub')}</span>
              <strong className="map-title">{t('itinerary.mapMain')}</strong>
            </div>
            <span className="route-count-tag">
              {t('itinerary.routeStopsCount', { count: points.length })}
            </span>
          </div>

          <MapAdapter
            points={points}
            routes={mapRoutes}
            selectedId={selectedId}
            onSelect={setSelectedId}
            pointSourceLabel={locale === 'en' ? 'Itinerary location' : 'Địa điểm trong lịch trình'}
            mapFooterLabel={locale === 'en' ? 'Trip endpoints, stops, and provider route geometry' : 'Điểm đầu-cuối, điểm dừng và hình học tuyến từ nhà cung cấp'}
            className="itinerary-map-container"
          />

          <div className="map-route-caption">
            <span className="route-dot-active" />
            <span>{t('itinerary.routeMatrixNote')}</span>
          </div>

          {itinerary.routes && itinerary.routes.length > 0 && (
            <div
              className="itinerary-legs-legend-bar"
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: '8px',
                marginTop: '12px',
                marginBottom: '12px',
                padding: '10px 14px',
                background: 'rgba(15, 23, 42, 0.75)',
                borderRadius: '8px',
                border: '1px solid rgba(255, 255, 255, 0.08)',
              }}
            >
              {itinerary.routes.map((leg, i) => {
                const color = LEG_COLORS[i % LEG_COLORS.length]
                return (
                  <div
                    key={i}
                    className="leg-legend-chip"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      background: 'rgba(30, 41, 59, 0.85)',
                      borderLeft: `3px solid ${color}`,
                      fontSize: '0.8rem',
                    }}
                  >
                    <span
                      style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: color,
                      }}
                    />
                    <strong style={{ color }}>Chặng {i + 1}</strong>
                    <span style={{ color: '#cbd5e1' }}>
                      {leg.duration_min}p ({(leg.distance_m / 1000).toFixed(1)}km)
                    </span>
                  </div>
                )
              })}
            </div>
          )}
          {itinerary.routes.length > 0 && (
            <div className="route-estimate-list" aria-label={t('itinerary.routeEstimates')}>
              <h3>{t('itinerary.routeEstimates')}</h3>
              {itinerary.routes.map((leg, index) => {
                const fromName = leg.from_label || itinerary.stops.find((stop) => stop.experience_id === leg.from_experience_id)?.name || (locale === 'en' ? 'Trip origin' : 'Điểm xuất phát')
                const toName = leg.to_label || itinerary.stops.find((stop) => stop.experience_id === leg.to_experience_id)?.name || (locale === 'en' ? 'Return destination' : 'Điểm về')
                const expired = Boolean(leg.eta_valid_until && new Date(leg.eta_valid_until).getTime() < currentTimeMs)
                const ageSeconds = leg.eta_calculated_at
                  ? Math.max(0, Math.floor((currentTimeMs - new Date(leg.eta_calculated_at).getTime()) / 1000))
                  : leg.eta_age_seconds
                const legColor = LEG_COLORS[index % LEG_COLORS.length]
                return (
                  <article
                    className="route-estimate-card"
                    key={`${leg.from_experience_id ?? 'origin'}-${leg.to_experience_id ?? 'destination'}-${index}`}
                    style={{ borderLeft: `4px solid ${legColor}` }}
                  >
                    <div className="route-estimate-heading">
                      <span
                        style={{
                          backgroundColor: legColor,
                          color: '#ffffff',
                          fontSize: '0.72rem',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontWeight: 700,
                          marginRight: '6px',
                        }}
                      >
                        Chặng {index + 1}
                      </span>
                      <Route size={14} style={{ color: legColor }} />
                      <strong>{fromName} → {toName}</strong>
                      <span>{(leg.distance_m / 1000).toFixed(1)} km · {t('itinerary.transitLeg', { min: leg.duration_min })}</span>
                    </div>
                    <div className="route-estimate-meta">
                      <span>{leg.eta_source || leg.provider}</span>
                      <span>{ageSeconds == null
                        ? t('itinerary.routeAgeUnknown')
                        : t('itinerary.routeAge', { age: ageSeconds })}</span>
                      {leg.eta_calculated_at && <span>{t('itinerary.routeCalculatedAt', { time: dateTimeLabel(leg.eta_calculated_at, locale) })}</span>}
                      {leg.eta_valid_until && <span className={expired ? 'route-estimate-expired' : ''}>
                        {expired ? t('itinerary.routeEstimateExpired') : t('itinerary.routeValidUntil', { time: dateTimeLabel(leg.eta_valid_until, locale) })}
                      </span>}
                      <span>{leg.is_realtime ? t('itinerary.liveTraffic') : t('itinerary.notLiveTraffic')}</span>
                      {leg.eta_source_uri && <a href={leg.eta_source_uri} target="_blank" rel="noreferrer">{t('itinerary.routeSource')}</a>}
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </section>
      </div>

      {/* AI Explanation & Transparency Card */}
      <div className="itinerary-explanation-card-3d">
        <div className="explanation-title-row">
          <div className="explanation-icon-pill">
            <Sparkles size={20} className="text-emerald" />
          </div>
          <div>
            <span className="explanation-eyebrow">{t('itinerary.algorithmTransparency')}</span>
            <h2 className="explanation-title">{t('itinerary.whyProposed')}</h2>
          </div>
        </div>

        <div className="reason-code-grid">
          {itinerary.explanation.reason_codes.map((code) => (
            <div key={code} className="reason-code-item">
              <CheckCircle2 size={16} className="text-emerald flex-shrink-0" />
              <span>{getReasonCopy(code, locale)}</span>
            </div>
          ))}
        </div>

        {itinerary.explanation.ranking_source && (
          <div className="item-sub-meta">
            <span>
              {locale === 'en' ? 'Ranking source:' : 'Nguồn xếp hạng:'}{' '}
              {itinerary.explanation.ranking_source === 'rule_baseline'
                ? 'rule-baseline-v1'
                : itinerary.explanation.ranking_source === 'bootstrap_ml_model'
                  ? `${itinerary.explanation.ranking_model_version || 'bootstrap ranker'} · ${locale === 'en' ? 'experimental' : 'thử nghiệm'}`
                  : itinerary.explanation.ranking_model_version || 'ML ranker'}
            </span>
          </div>
        )}

        {itinerary.explanation.ranking_source === 'bootstrap_ml_model' && (
          <div className="lost-intents-notice" role="note">
            <AlertCircle size={15} />
            <span>{locale === 'en'
              ? 'Experimental ranking only: labels are weak/rule-generated and operational data is not verified. Feasibility checks remain authoritative.'
              : 'Chỉ là xếp hạng thử nghiệm: nhãn được tạo yếu theo quy tắc và dữ liệu vận hành chưa được xác minh. Các kiểm tra khả thi vẫn là căn cứ quyết định.'}</span>
          </div>
        )}

        {itinerary.explanation.lost_intents.length > 0 && (
          <div className="lost-intents-notice">
            <AlertCircle size={15} />
            <span>
              {t('itinerary.lostIntents', { lost: itinerary.explanation.lost_intents.join(', ') })}
            </span>
          </div>
        )}

        <div className="explanation-footer-bar">
          <span>{t('itinerary.tryAnotherQuestion')}</span>
          <Link to="/planner" className="btn-replan-link">
            <span>{t('itinerary.tryAnotherBtn')}</span>
            <ArrowRight size={15} />
          </Link>
        </div>
      </div>

      {/* Post-trip Review Section */}
      <div className="feedback-section-card">
        <div className="feedback-header">
          <Star size={20} className="text-amber" />
          <div>
            <h3>{t('itinerary.postTripReview')}</h3>
            <p>{t('itinerary.postTripSub')}</p>
          </div>
        </div>

        {user?.role === 'traveler' ? (
          <form onSubmit={handleFeedback} className="feedback-form-layout">
            <div className="feedback-rating-row">
              <span className="rating-label">{t('itinerary.satisfactionLevel')}</span>
              <div className="star-rating-buttons">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    className={`star-btn ${rating >= star ? 'star-active' : ''}`}
                    onClick={() => setRating(star)}
                    aria-label={`${star} star`}
                  >
                    <Star
                      size={20}
                      className={rating >= star ? 'fill-amber-400 text-amber-400' : 'text-slate-600'}
                    />
                  </button>
                ))}
                <span className="rating-score-text">
                  {rating === 5
                    ? t('itinerary.rate5')
                    : rating === 4
                    ? t('itinerary.rate4')
                    : rating === 3
                    ? t('itinerary.rate3')
                    : t('itinerary.rateLow')}
                </span>
              </div>
            </div>

            <div className="field-group-3d">
              <span>{t('itinerary.detailedFeedback')}</span>
              <textarea
                required
                minLength={1}
                maxLength={4000}
                rows={3}
                value={reviewText}
                onChange={(e) => setReviewText(e.target.value)}
                placeholder={t('itinerary.feedbackPlaceholder')}
                className="feedback-textarea"
              />
            </div>

            <button type="submit" className="btn-primary-3d">
              <span>{t('itinerary.submitFeedback')}</span>
              <ArrowRight size={16} />
            </button>
          </form>
        ) : (
          <div className="feedback-guest-notice">
            <p>
              {t('itinerary.loginToReview')}
            </p>
            <Link to="/login" className="btn-secondary-3d btn-sm">
              {t('itinerary.loginNow')}
            </Link>
          </div>
        )}
      </div>

      {activeStop && (
        <div className="sr-only" aria-live="polite">
          {locale === 'en' ? `Viewing ${activeStop.name} on map` : `Đang xem ${activeStop.name} trên bản đồ`}
        </div>
      )}
    </div>
  )
}
