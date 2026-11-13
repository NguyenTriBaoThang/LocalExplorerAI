import { api } from '../../api/client'
import { roadSegments } from './roadRoutes'
import { GOONG_MAPTILES_KEY } from '../map/goongConfig'
import { useEffect, useRef, useState } from 'react'
import goongjs from '@goongmaps/goong-js'
import '@goongmaps/goong-js/dist/goong-js.css'
import type { Itinerary, Place } from '../../api/trips'
import { selectedPlace, tourStops, type Selected } from './place'
import PlacePopup from './PlacePopup'
import LocationConditions from './LocationConditions'
import { DEFAULT_CALIBRATIONS, sanitizeCalibration } from '../3d/landmark/types'
import { createLandmarkLayer } from './landmarkLayer'
import { installMissingStyleImageFallback } from '../map/missingStyleImages'
import { useTranslation } from '../../i18n'

const COLORS = ['#047857', '#b45309', '#2563eb', '#be123c', '#7c3aed', '#0f766e']
const duration = (ms: number) => matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : ms
type Props = { travelMode?: string; center: [number, number]; searchPins: Place[]; itinerary: Itinerary | null; places: Record<string, Place>; selected: Selected; onSelect(s: Selected): void; padding: { left: number; right: number }; pins: number[]; onPin?(id: number, pinned: boolean): void }

export default function TripMap(props: Props) {
  const { t, locale } = useTranslation()
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<any>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [roadStatus, setRoadStatus] = useState('')
  const [mapPoint, setMapPoint] = useState<{ lat: number; lon: number } | null>(null)
  const [inspectSearchPin, setInspectSearchPin] = useState<Place | null>(null)
  const [tour, setTour] = useState<number | null>(null)
  const run = useRef(0)
  const roadCache = useRef<Map<string, { at: number; coordinates: number[][] }>>(new Map())
  const { padding, onSelect, travelMode = 'motorcycle' } = props
  const profile = travelMode === 'car' ? 'car' : 'bike'
  const stop = () => { run.current++; setTour(null) }
  const latest = useRef({ center: props.center, onSelect })
  latest.current = { center: props.center, onSelect }

  function fit() {
    const pts = props.itinerary?.days.flatMap(d => d.stops).map(s => props.places[s.place_id]).filter(Boolean) ?? []
    if (!map.current || !pts.length) return
    const bounds = new goongjs.LngLatBounds(); pts.forEach(p => bounds.extend([p.lon, p.lat]))
    const width = container.current?.clientWidth ?? 1000
    const pad = width < 1100 ? { left: 80, right: 24 } : padding
    map.current.fitBounds(bounds, { padding: { top: 80, bottom: 100, ...pad }, maxZoom: 15, duration: duration(1000) })
  }
  useEffect(() => {
    const key = GOONG_MAPTILES_KEY
    if (!key) { setError(t('tripChat.goongApiKeyMissing')); return }
    let disposed = false
    goongjs.accessToken = key
    const m = new goongjs.Map({ container: container.current!, style: 'https://tiles.goong.io/assets/goong_map_web.json', center: latest.current.center, zoom: 12.5, pitch: 45 })
    map.current = m
    const removeMissingImageFallback = installMissingStyleImageFallback(m)
    // Goong must track layout changes as well as browser window resizes.
    const resizeObserver = new ResizeObserver(() => m.resize())
    resizeObserver.observe(container.current!)
    m.on('load', () => {
      if (disposed) return
      setReady(true)
      const defaults = Object.values(DEFAULT_CALIBRATIONS).filter(c => c.latitude > 10.6 && c.latitude < 11.2 && c.longitude < 107)
      void Promise.all(defaults.map(async c => {
        try {
          const response = await fetch(`/api/models-3d/calibration/${encodeURIComponent(c.model_name)}`)
          return response.ok ? sanitizeCalibration(await response.json(), c) : c
        } catch { return c }
      })).then(cals => { if (!disposed) m.addLayer(createLandmarkLayer('trip-landmarks', cals)) })
    })
    m.on('dragstart', stop)
    m.on('click', (event: any) => {
      setInspectSearchPin(null)
      latest.current.onSelect(null)
      setMapPoint({ lat: event.lngLat.lat, lon: event.lngLat.lng })
    })
    m.on('error', () => setError(t('tripChat.mapLoadError')))
    return () => { disposed = true; resizeObserver.disconnect(); run.current++; removeMissingImageFallback(); m.remove(); map.current = null }
  }, [t])

  useEffect(() => {
    if (!ready) return
    stop()
    const m = map.current
    const markers: any[] = []
    const { itinerary, places } = props
    itinerary?.days.forEach((d, day) => {
      d.stops.forEach((s, index) => {
        const p = places[s.place_id]; if (!p) return
        const el = document.createElement('button'); el.type = 'button'; el.className = 'trip-pin'
        el.textContent = `${day + 1}.${index + 1}`; el.style.backgroundColor = COLORS[day % COLORS.length]; el.title = p.name
        el.addEventListener('click', event => { event.stopPropagation(); stop(); setMapPoint(null); setInspectSearchPin(null); latest.current.onSelect({ day, stop: index }) })
        markers.push(new goongjs.Marker(el).setLngLat([p.lon, p.lat]).addTo(m))
      })
    })
    props.searchPins.forEach(p => {
      const el = document.createElement('button'); el.type = 'button'; el.className = 'trip-pin trip-pin--searching';
      el.textContent = p.rank_position == null ? '•' : String(p.rank_position)
      el.title = p.rank_position == null
        ? `Ranker: ${t('tripChat.unranked')} · ${p.name}`
        : `Ranker: ${t('tripChat.rankPosition', { rank: p.rank_position, total: p.rank_candidate_count ?? '—' })} · ${p.name}`
      el.setAttribute('aria-label', locale === 'en' ? `View ${p.name}; ${el.title}` : `Xem thông tin ${p.name}; ${el.title}`)
      el.addEventListener('click', event => { event.stopPropagation(); stop(); setMapPoint(null); setInspectSearchPin(p); latest.current.onSelect(null) })
      markers.push(new goongjs.Marker(el).setLngLat([p.lon, p.lat]).addTo(m))
    })
    if (itinerary) fit()
    else m.flyTo({ center: props.center, zoom: 12.5, duration: duration(1000) })
    return () => markers.forEach(marker => marker.remove())
  }, [ready, props.itinerary, props.places, props.searchPins, props.center, t, locale])

  useEffect(() => {
    if (!ready || !map.current) return
    const m = map.current
    const controller = new AbortController()
    const features: any[] = []
    const update = () => {
      if (controller.signal.aborted) return
      const data = { type: 'FeatureCollection', features: [...features] }
      if (m.getSource('trip-routes')) m.getSource('trip-routes').setData(data)
      else {
        m.addSource('trip-routes', { type: 'geojson', data })
        m.addLayer({ id: 'trip-routes-line', type: 'line', source: 'trip-routes',
          paint: { 'line-color': ['get', 'color'], 'line-width': 4, 'line-opacity': 0.85 } })
      }
    }
    const segments = roadSegments(props.itinerary, props.places)
    setRoadStatus(segments.length ? t('tripChat.loadingRoute') : '')
    let completed = 0; let failed = 0
    let nextIndex = 0
    const worker = async () => {
      while (nextIndex < segments.length) {
        if (controller.signal.aborted) return
        const index = nextIndex++
        const { origin, destination, day } = segments[index]
        const key = `${profile}:${origin.lat.toFixed(5)},${origin.lon.toFixed(5)}->${destination.lat.toFixed(5)},${destination.lon.toFixed(5)}`
        try {
          const cached = roadCache.current.get(key)
          let coordinates = cached && Date.now() - cached.at < 24 * 3600 * 1000 ? cached.coordinates : null
          if (!coordinates) {
            const { data } = await api.post('/routing/road', { origin: { lat: origin.lat, lon: origin.lon },
              destination: { lat: destination.lat, lon: destination.lon }, mode: profile }, { signal: controller.signal })
            coordinates = data.coordinates as number[][]
            if (roadCache.current.size > 256) roadCache.current.clear()
            roadCache.current.set(key, { at: Date.now(), coordinates })
          }
          if (controller.signal.aborted) return
          features.push({ type: 'Feature', properties: { color: COLORS[day % COLORS.length] },
            geometry: { type: 'LineString', coordinates } })
          update()
        } catch { if (controller.signal.aborted) return; failed++ }
        completed++
        setRoadStatus(completed < segments.length
          ? (locale === 'en' ? `Loading route ${completed}/${segments.length}…` : `Đang tải tuyến đường ${completed}/${segments.length}…`)
          : failed
          ? (locale === 'en' ? `${failed}/${segments.length} legs failed to route.` : `${failed}/${segments.length} chặng chưa lấy được đường đi; không vẽ nối thẳng thay thế.`)
          : t('tripChat.routeLoaded'))
      }
    }
    void Promise.all(Array.from({ length: Math.min(3, segments.length) }, worker))
    return () => controller.abort()
  }, [ready, props.itinerary, props.places, profile, t, locale])

  const selectedId = selectedPlace(props.itinerary, props.selected)
  const selected = selectedId == null ? undefined : props.places[selectedId]
  const popupPlace = inspectSearchPin ?? selected

  useEffect(() => {
    if (props.selected != null) { setMapPoint(null); setInspectSearchPin(null) }
  }, [props.selected])
  useEffect(() => {
    if (inspectSearchPin && !props.searchPins.some(place => place.id === inspectSearchPin.id)) setInspectSearchPin(null)
  }, [props.searchPins, inspectSearchPin])
  useEffect(() => {
    if (ready && selected) map.current.flyTo({ center: [selected.lon, selected.lat], zoom: 16, pitch: 60, duration: duration(1800) })
  }, [ready, selected])

  async function startTour() {
    if (!props.itinerary) return
    const id = ++run.current
    const points = tourStops(props.itinerary)
    for (let i = 0; i < points.length && run.current === id; i++) {
      setTour(i); props.onSelect(points[i])
      const p = props.places[props.itinerary.days[points[i].day].stops[points[i].stop].place_id]
      if (p) map.current?.flyTo({ center: [p.lon, p.lat], pitch: 60, zoom: 16, bearing: 40 * (i + 1), duration: duration(1800) })
      await new Promise(resolve => setTimeout(resolve, duration(1800) + 1200))
    }
    if (run.current === id) { setTour(null); fit() }
  }
  const tourPoint = tour != null && props.itinerary ? tourStops(props.itinerary)[tour] : null

  return <>
    <div ref={container} className="trip-map-surface" />
    {error && <p role="status" className="trip-map-notice">{error}</p>}
    <div className="trip-map-controls">
      <small>
        {locale === 'en'
          ? `${roadStatus || 'Select an itinerary to view routes.'} Route for ${profile === 'car' ? 'car' : 'motorbike'}. Estimated travel times.`
          : `${roadStatus || 'Chọn lịch trình để xem đường đi.'} Tuyến ${profile === 'car' ? 'ô tô' : 'xe máy'}, không phải chỉ dẫn đi bộ. Thời gian lịch trình vẫn là ước tính; không phải giao thông trực tiếp.`}
      </small>
      {props.itinerary && <button className="btn-secondary-3d" onClick={tour == null ? startTour : stop} disabled={!ready}>
        {tour == null ? t('tripChat.startTour') : (locale === 'en' ? `■ Stop · Day ${(tourPoint?.day ?? 0) + 1} · Point ${tour + 1} · ${selected?.name ?? ''}` : `■ Dừng · Ngày ${(tourPoint?.day ?? 0) + 1} · Điểm ${tour + 1} · ${selected?.name ?? ''}`)}
      </button>}
    </div>
    {(popupPlace || mapPoint) && <aside className="trip-place-popup">
      <button aria-label={t('tripChat.closePlaceInfo')} onClick={() => { setMapPoint(null); setInspectSearchPin(null); props.onSelect(null) }}>✕</button>
      {popupPlace ? <PlacePopup place={popupPlace} date={props.selected && props.selected !== 'stay' ? props.itinerary?.days[props.selected.day]?.date ?? null : null}
        pinned={!inspectSearchPin && props.pins.includes(popupPlace.id)}
        onPin={!inspectSearchPin && props.onPin ? p => props.onPin!(popupPlace.id, p) : undefined} /> : (
          <div className="grid max-h-[70vh] w-[min(22rem,calc(100vw-2rem))] gap-2 overflow-y-auto bg-[var(--bg-surface)] p-3 text-[var(--text-main)]">
            <h3 className="text-sm font-bold">{t('tripChat.pointConditions')}</h3>
            <p className="text-[10px] text-[var(--text-muted)]">{mapPoint!.lat.toFixed(5)}, {mapPoint!.lon.toFixed(5)}</p>
            <LocationConditions latitude={mapPoint!.lat} longitude={mapPoint!.lon} />
          </div>
      )}
    </aside>}
  </>
}
