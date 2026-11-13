import { useEffect, useState } from 'react'
import { getLocationContext, type LocationContext } from '../../api/client'
import { useTranslation } from '../../i18n'

export default function LocationConditions({ latitude, longitude }: { latitude: number; longitude: number }) {
  const { t, locale } = useTranslation()
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

  const value = (number: number | null | undefined, suffix = '') =>
    number == null || !Number.isFinite(number)
      ? (locale === 'en' ? 'N/A' : 'Chưa có')
      : `${number.toFixed(number < 10 ? 1 : 0)}${suffix}`

  const getAqiLabel = (label: string | null | undefined) => {
    if (!label) return locale === 'en' ? 'No index' : 'Chưa có chỉ số'
    const key = `aqi.${label}`
    const res = t(key)
    return res !== key ? res : label
  }

  const getWeatherLabel = (code: number | null | undefined) => {
    if (code == null) return t('weather.conditionSky')
    const key = `weather.code${code}`
    const res = t(key)
    return res !== key ? res : `${t('weather.conditionSky')} ${code}`
  }

  const section = 'rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] p-2.5'
  if (error) {
    return (
      <section className={section} aria-live="polite">
        <div className="flex items-center justify-between gap-2">
          <strong className="text-xs">{t('weather.titleAndAqi')}</strong>
          <button type="button" className="text-xs text-emerald-700 underline" onClick={() => setRetry(x => x + 1)}>
            {t('weather.retry')}
          </button>
        </div>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          {t('weather.errorUnavailable')}
        </p>
      </section>
    )
  }

  if (!data) {
    return (
      <section className={section} aria-live="polite">
        <strong className="text-xs">{t('weather.titleAndAqi')}</strong>
        <p className="mt-1 text-xs text-[var(--text-muted)]">{t('weather.loadingCoords')}</p>
      </section>
    )
  }

  const { conditions } = data
  const aqi = conditions.air_quality
  const weatherLabel = getWeatherLabel(conditions.weather_code)
  const intlLocale = locale === 'en' ? 'en-US' : 'vi-VN'
  const observed = new Date(conditions.observed_at).toLocaleString(intlLocale, {
    timeZone: 'Asia/Ho_Chi_Minh',
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
  })

  return (
    <div className="grid gap-2" aria-live="polite">
      <section className={section}>
        <div className="flex items-center justify-between gap-2">
          <strong className="text-xs">{t('weather.title')}</strong>
          <span className="text-[10px] text-[var(--text-muted)]">{observed}</span>
        </div>
        <p className="mt-1 text-sm font-semibold">{weatherLabel} · {value(conditions.temperature_c, '°C')}</p>
        <p className="mt-1 text-xs leading-relaxed text-[var(--text-muted)]">
          {locale === 'en' ? 'Feels like' : 'Cảm giác'} {value(conditions.apparent_temperature_c, '°C')} · {locale === 'en' ? 'Rain' : 'Mưa'} {value(conditions.rain_mm_per_hour, ' mm/h')} · {locale === 'en' ? 'Humidity' : 'Ẩm'} {value(conditions.relative_humidity_pct, '%')} · {locale === 'en' ? 'Wind' : 'Gió'} {value(conditions.wind_speed_kmh, ' km/h')} · {locale === 'en' ? 'Cloud' : 'Mây'} {value(conditions.cloud_cover_pct, '%')}
        </p>
      </section>

      <section className={section}>
        <div className="flex items-center justify-between gap-2">
          <strong className="text-xs">{t('aqi.title')}</strong>
          <span className="text-[10px] text-[var(--text-muted)]">{t('aqi.europeanAqi')}</span>
        </div>
        <p className="mt-1 text-sm font-semibold">
          {value(aqi.european_aqi)} · {getAqiLabel(aqi.european_aqi_label)}
        </p>
        <div className="mt-1 grid grid-cols-2 gap-x-2 text-xs text-[var(--text-muted)]">
          <span>PM2.5: {value(aqi.pm25_ug_m3, ' µg/m³')}</span><span>PM10: {value(aqi.pm10_ug_m3, ' µg/m³')}</span>
          <span>NO₂: {value(aqi.nitrogen_dioxide_ug_m3, ' µg/m³')}</span><span>O₃: {value(aqi.ozone_ug_m3, ' µg/m³')}</span>
          <span>SO₂: {value(aqi.sulphur_dioxide_ug_m3, ' µg/m³')}</span><span>US AQI: {value(aqi.us_aqi)}</span>
        </div>
      </section>
    </div>
  )
}
