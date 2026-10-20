import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  Clock3,
  History,
  MapPin,
  Route,
  Sparkles,
  Users,
  Wallet,
} from 'lucide-react'
import { apiErrorMessage, getMyCompletedItineraries, type MyItinerarySummary } from '../api/client'
import { TiltCard3D } from '../components/3d/TiltCard3D'
import { useTranslation } from '../i18n'

function formatDate(value: string | null | undefined, locale: string, includeTime = false) {
  if (!value) return locale === 'en' ? 'Date not set' : 'Chưa có ngày'
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'vi-VN', {
    dateStyle: 'medium',
    ...(includeTime ? { timeStyle: 'short' as const } : {}),
    timeZone: 'Asia/Ho_Chi_Minh',
  }).format(date)
}

export function TripHistoryPage() {
  const { locale } = useTranslation()
  const en = locale === 'en'
  const [items, setItems] = useState<MyItinerarySummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    getMyCompletedItineraries()
      .then((rows) => { if (active) setItems(rows) })
      .catch((reason: unknown) => {
        if (active) setError(apiErrorMessage(reason, locale))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [locale, reloadKey])

  const totals = useMemo(() => ({
    stops: items.reduce((sum, trip) => sum + (trip.stop_count ?? 0), 0),
    spend: items.reduce((sum, trip) => sum + trip.estimated_cost_vnd, 0),
  }), [items])

  return (
    <main className="trip-history-page page-wrap">
      <header className="trip-history-hero">
        <div>
          <span className="eyebrow-3d"><span className="eyebrow-dot" /> {en ? 'YOUR TRAVEL JOURNAL' : 'NHẬT KÝ HÀNH TRÌNH'}</span>
          <h1 className="page-heading-3d">{en ? 'Trips you have ' : 'Hành trình đã '}<em>{en ? 'experienced' : 'trải nghiệm'}</em></h1>
          <p className="page-subtext-3d">{en
            ? 'Review completed trips, the places you visited, and their estimated cost.'
            : 'Xem lại các chuyến đi đã hoàn thành, những nơi bạn đã ghé và chi phí dự kiến.'}</p>
        </div>
        <Link to="/chat" className="trip-history-new-link"><Sparkles size={16} /> {en ? 'Plan with AI Chat' : 'Lập lịch bằng AI Chat'}</Link>
      </header>

      <section className="trip-history-summary" aria-label={en ? 'History summary' : 'Tổng quan lịch sử'}>
        <article><span className="trip-history-summary-icon"><History size={18} /></span><small>{en ? 'COMPLETED TRIPS' : 'HÀNH TRÌNH HOÀN TẤT'}</small><strong>{items.length}</strong></article>
        <article><span className="trip-history-summary-icon"><MapPin size={18} /></span><small>{en ? 'PLACES VISITED' : 'ĐỊA ĐIỂM ĐÃ GHÉ'}</small><strong>{totals.stops}</strong></article>
        <article><span className="trip-history-summary-icon"><Wallet size={18} /></span><small>{en ? 'ESTIMATED TOTAL' : 'TỔNG CHI PHÍ DỰ KIẾN'}</small><strong>{totals.spend.toLocaleString(en ? 'en-US' : 'vi-VN')} ₫</strong></article>
      </section>

      {error && <div className="trip-history-error" role="alert">
        <span>{error}</span>
        <button type="button" onClick={() => setReloadKey((key) => key + 1)}>{en ? 'Try again' : 'Thử lại'}</button>
      </div>}

      {loading ? (
        <div className="trip-history-loading" role="status">{en ? 'Loading your completed trips…' : 'Đang tải hành trình đã hoàn thành…'}</div>
      ) : error ? null : items.length === 0 ? (
        <section className="trip-history-empty">
          <span className="trip-history-empty-icon"><Route size={30} /></span>
          <h2>{en ? 'No completed trips yet' : 'Bạn chưa có hành trình hoàn tất'}</h2>
          <p>{en
            ? 'When you finish a trip and mark it complete, it will appear here for you to revisit.'
            : 'Sau khi kết thúc chuyến đi và đánh dấu hoàn tất, lịch sử sẽ được lưu tại đây để bạn xem lại.'}</p>
          <Link to="/chat" className="trip-history-empty-link">{en ? 'Start with AI Chat' : 'Bắt đầu với AI Chat'} <ArrowRight size={16} /></Link>
        </section>
      ) : (
        <section className="trip-history-list" aria-label={en ? 'Completed trips' : 'Các chuyến đi đã hoàn tất'}>
          {items.map((trip) => {
            const stopNames = trip.stop_names ?? []
            const destination = trip.destination_label || stopNames[stopNames.length - 1] || trip.city || (en ? 'Ho Chi Minh City' : 'TP. Hồ Chí Minh')
            const origin = trip.origin_label || stopNames[0]
            return (
              <TiltCard3D key={trip.id} maxTilt={3} className="trip-history-entry">
                <div className="trip-history-entry-top">
                  <div className="trip-history-destination">
                    <span className="trip-history-entry-icon"><Route size={19} /></span>
                    <div><small>{en ? 'COMPLETED JOURNEY' : 'HÀNH TRÌNH ĐÃ TRẢI NGHIỆM'}</small><h2>{destination}</h2></div>
                  </div>
                  <span className="trip-history-complete-chip"><CheckCircle2 size={14} /> {en ? 'Completed' : 'Đã hoàn tất'}</span>
                </div>

                {origin && <div className="trip-history-route-line"><MapPin size={15} /><span>{origin}</span><ArrowRight size={15} /><span>{destination}</span></div>}

                {stopNames.length > 0 && <div className="trip-history-stops">
                  {stopNames.slice(0, 5).map((name, index) => <span key={`${trip.id}-${index}`}>{name}</span>)}
                  {stopNames.length > 5 && <span className="trip-history-more">+{stopNames.length - 5}</span>}
                </div>}

                <div className="trip-history-metrics">
                  <span><CalendarDays size={15} /><small>{en ? 'Trip date' : 'Ngày đi'}</small><strong>{formatDate(trip.planned_date, locale)}</strong></span>
                  <span><Clock3 size={15} /><small>{en ? 'Completed' : 'Hoàn thành'}</small><strong>{formatDate(trip.completed_at, locale, true)}</strong></span>
                  <span><MapPin size={15} /><small>{en ? 'Places' : 'Địa điểm'}</small><strong>{trip.stop_count ?? stopNames.length}</strong></span>
                  <span><Users size={15} /><small>{en ? 'Travelers' : 'Số người'}</small><strong>{trip.group_size ?? '—'}</strong></span>
                  <span><Wallet size={15} /><small>{en ? 'Estimated cost' : 'Chi phí dự kiến'}</small><strong>{trip.estimated_cost_vnd.toLocaleString(en ? 'en-US' : 'vi-VN')} ₫</strong></span>
                </div>

                <footer className="trip-history-entry-footer">
                  <span>{en ? `Trip #${trip.id.slice(0, 8)}` : `Mã hành trình #${trip.id.slice(0, 8)}`}</span>
                  <Link to={`/itinerary/${trip.id}`}>{en ? 'View trip and reviews' : 'Xem hành trình và đánh giá'} <ArrowRight size={15} /></Link>
                </footer>
              </TiltCard3D>
            )
          })}
        </section>
      )}
    </main>
  )
}
