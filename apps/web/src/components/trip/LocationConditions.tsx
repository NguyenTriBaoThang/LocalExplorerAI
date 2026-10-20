import { useEffect, useState } from 'react'
import { getLocationContext, type LocationContext } from '../../api/client'

const AQI_LABELS: Record<string, string> = {
  good: 'Tốt', fair: 'Khá', moderate: 'Trung bình', poor: 'Kém',
  very_poor: 'Rất kém', extremely_poor: 'Cực kém',
}
const WEATHER_LABELS: Record<number, string> = {
  0: 'Trời quang', 1: 'Ít mây', 2: 'Mây rải rác', 3: 'Nhiều mây',
  45: 'Sương mù', 48: 'Sương mù đóng băng', 51: 'Mưa phùn nhẹ', 53: 'Mưa phùn', 55: 'Mưa phùn dày',
  61: 'Mưa nhẹ', 63: 'Mưa vừa', 65: 'Mưa to', 80: 'Mưa rào nhẹ', 81: 'Mưa rào', 82: 'Mưa rào lớn',
  95: 'Dông', 96: 'Dông có mưa đá', 99: 'Dông mạnh',
}
const value = (number: number | null | undefined, suffix = '') =>
  number == null || !Number.isFinite(number) ? 'Chưa có' : `${number.toFixed(number < 10 ? 1 : 0)}${suffix}`

export default function LocationConditions({ latitude, longitude }: { latitude: number; longitude: number }) {
  const [data, setData] = useState<LocationContext | null>(null)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setData(null)
    setError(false)
    getLocationContext(latitude, longitude, controller.signal)
      .then(setData)
      .catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [latitude, longitude, retry])

  const section = 'rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] p-2.5'
  if (error) return <section className={section} aria-live="polite">
    <div className="flex items-center justify-between gap-2"><strong className="text-xs">Thời tiết & chất lượng không khí</strong>
      <button type="button" className="text-xs text-emerald-700 underline" onClick={() => setRetry(x => x + 1)}>Thử lại</button></div>
    <p className="mt-1 text-xs text-[var(--text-muted)]">Nguồn dữ liệu trực tiếp hiện không phản hồi. Không có dữ liệu mới để hiển thị.</p>
  </section>

  if (!data) return <section className={section} aria-live="polite"><strong className="text-xs">Thời tiết & chất lượng không khí</strong>
    <p className="mt-1 text-xs text-[var(--text-muted)]">Đang tải theo tọa độ địa điểm…</p></section>

  const { conditions } = data
  const aqi = conditions.air_quality
  const weatherLabel = conditions.weather_code == null ? 'Điều kiện trời' : WEATHER_LABELS[conditions.weather_code] ?? `Mã thời tiết ${conditions.weather_code}`
  const observed = new Date(conditions.observed_at).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })
  return <div className="grid gap-2" aria-live="polite">
    <section className={section}>
      <div className="flex items-center justify-between gap-2"><strong className="text-xs">Thời tiết hiện tại</strong>
        <span className="text-[10px] text-[var(--text-muted)]">{observed}</span></div>
      <p className="mt-1 text-sm font-semibold">{weatherLabel} · {value(conditions.temperature_c, '°C')}</p>
      <p className="mt-1 text-xs leading-relaxed text-[var(--text-muted)]">
        Cảm giác {value(conditions.apparent_temperature_c, '°C')} · Mưa {value(conditions.rain_mm_per_hour, ' mm/h')} · Ẩm {value(conditions.relative_humidity_pct, '%')} · Gió {value(conditions.wind_speed_kmh, ' km/h')} · Mây {value(conditions.cloud_cover_pct, '%')}
      </p>
    </section>

    <section className={section}>
      <div className="flex items-center justify-between gap-2"><strong className="text-xs">Chất lượng không khí</strong>
        <span className="text-[10px] text-[var(--text-muted)]">AQI châu Âu</span></div>
      <p className="mt-1 text-sm font-semibold">{value(aqi.european_aqi)} · {aqi.european_aqi_label ? AQI_LABELS[aqi.european_aqi_label] ?? aqi.european_aqi_label : 'Chưa có chỉ số'}</p>
      <div className="mt-1 grid grid-cols-2 gap-x-2 text-xs text-[var(--text-muted)]">
        <span>PM2.5: {value(aqi.pm25_ug_m3, ' µg/m³')}</span><span>PM10: {value(aqi.pm10_ug_m3, ' µg/m³')}</span>
        <span>NO₂: {value(aqi.nitrogen_dioxide_ug_m3, ' µg/m³')}</span><span>O₃: {value(aqi.ozone_ug_m3, ' µg/m³')}</span>
        <span>SO₂: {value(aqi.sulphur_dioxide_ug_m3, ' µg/m³')}</span><span>US AQI: {value(aqi.us_aqi)}</span>
      </div>
    </section>

  </div>
}
