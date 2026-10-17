import { vnd } from '../../api/trips'
import type { TripPrintModel } from './tripPrint'

export default function TripPrintView({ model }: { model: TripPrintModel }) {
  return (
    <article className="trip-print" aria-label="Bản in lịch trình">
      <header className="print-trip-header">
        <p>Local Explorer AI · Lịch trình</p>
        <h1>{model.destination}</h1>
        <p>Phiên bản v{model.version}</p>
        <p>Xuất lúc {new Date(model.exportedAt).toLocaleString('vi-VN')}</p>
      </header>

      <section className="print-trip-overview" aria-label="Tổng quan chi phí">
        {model.stayName && <p><strong>Chỗ ở:</strong> {model.stayName}</p>}
        <p><strong>Tổng chi phí ước tính:</strong> {vnd(model.totalCost)}</p>
      </section>

      {model.conflicts.length > 0 && (
        <section className="print-trip-conflicts" aria-label="Xung đột lịch trình">
          <h2>Xung đột</h2>
          <ul>{model.conflicts.map((conflict, index) => <li key={index}>{conflict}</li>)}</ul>
        </section>
      )}

      {model.days.map((day, dayIndex) => (
        <section className="print-trip-day" key={dayIndex}>
          <h2 className="print-trip-day-title">
            Ngày {dayIndex + 1}{day.date && <> · <time dateTime={day.date}>{day.date}</time></>}
          </h2>
          {day.stops.length > 0 ? (
            <ol className="print-trip-stops">
              {day.stops.map((stop, stopIndex) => (
                <li className="print-trip-stop" key={`${stop.startTime}-${stopIndex}`}>
                  <div className="print-trip-stop-heading">
                    <strong>{stop.startTime} · {stop.placeName}</strong>
                    <span>{vnd(stop.cost)}</span>
                  </div>
                  <p>{stop.reason}</p>
                </li>
              ))}
            </ol>
          ) : <p>Chưa có điểm dừng trong ngày này.</p>}

          {day.legs.length > 0 && (
            <ul className="print-trip-legs" aria-label={`Các chặng di chuyển ngày ${dayIndex + 1}`}>
              {day.legs.map((leg, legIndex) => (
                <li key={legIndex}>
                  {leg.fromLabel} → {leg.toLabel} · {leg.mode} · {leg.distanceKm} km · {leg.durationMin} phút · {vnd(leg.cost)}
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </article>
  )
}
