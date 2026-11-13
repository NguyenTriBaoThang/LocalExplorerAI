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
import { DEFAULT_CALIBRATIONS, sanitizeCalibration, type ModelCalibration } from '../3d/landmark/types'
import { createLandmarkLayer } from './landmarkLayer'
import { installMissingStyleImageFallback } from '../map/missingStyleImages'

const COLORS = ['#047857', '#b45309', '#2563eb', '#be123c', '#7c3aed', '#0f766e']
const duration = (ms: number) => matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : ms
type Props = { travelMode?: string; center: [number, number]; searchPins: Place[]; itinerary: Itinerary | null; places: Record<string, Place>; selected: Selected; onSelect(s: Selected): void; padding: { left: number; right: number }; pins: number[]; onPin?(id: number, pinned: boolean): void }

export default function TripMap(props: Props) {
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<any>(null)
  const latest = useRef(props); latest.current = props
  const run = useRef(0)
  const [ready, setReady] = useState(false)
  const [tour, setTour] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [roadStatus, setRoadStatus] = useState('')
  const [mapPoint, setMapPoint] = useState<{ lat: number; lon: number } | null>(null)
  const [inspectSearchPin, setInspectSearchPin] = useState<Place | null>(null)
  const roadCache = useRef(new Map<string, { at: number; coordinates: number[][] }>())
  const profile = ['grab', 'o-to-rieng'].includes(props.travelMode ?? '') ? 'car' : 'motorcycle'
  const stop = () => { run.current++; setTour(null) }
  function fit() {
    const { itinerary, places, padding } = latest.current
    const pts = itinerary?.days.flatMap(d => d.stops.map(s => places[s.place_id])).filter(Boolean) ?? []
    if (!map.current || !pts.length) return
    const bounds = new goongjs.LngLatBounds(); pts.forEach(p => bounds.extend([p.lon, p.lat]))
    const width = container.current?.clientWidth ?? 1000
    const pad = width < 1100 ? { left: 80, right: 24 } : padding
    map.current.fitBounds(bounds, { padding: { top: 80, bottom: 100, ...pad }, maxZoom: 15, duration: duration(1000) })
  }
  useEffect(() => {
    const key = GOONG_MAPTILES_KEY
    if (!key) { setError('Chưa cấu hình bản đồ Goong. Bạn vẫn có thể lập và xem lịch trình.'); return }
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
      void api.get<Record<string, ModelCalibration>>('/models-3d/calibration')
        .then(({ data }) => {
          if (disposed) return
          const calibrations = Object.entries(DEFAULT_CALIBRATIONS)
            .map(([id, fallback]) => sanitizeCalibration(data?.[id] ?? {}, fallback))
            .filter(c => c.latitude > 10.6 && c.latitude < 11.2 && c.longitude < 107)
          m.addLayer(createLandmarkLayer('trip-landmarks', calibrations))
        })
        .catch(() => {
          if (disposed) return
          const calibrations = Object.values(DEFAULT_CALIBRATIONS)
            .filter(c => c.latitude > 10.6 && c.latitude < 11.2 && c.longitude < 107)
          m.addLayer(createLandmarkLayer('trip-landmarks', calibrations))
        })
    })
    m.on('dragstart', stop)
    m.on('click', (event: any) => {
      setInspectSearchPin(null)
      latest.current.onSelect(null)
      setMapPoint({ lat: event.lngLat.lat, lon: event.lngLat.lng })
    })
    m.on('error', () => setError('Bản đồ đang gặp lỗi tải. Lịch trình vẫn được giữ lại.'))
    return () => { disposed = true; resizeObserver.disconnect(); run.current++; removeMissingImageFallback(); m.remove(); map.current = null }
  }, [])
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
      el.title = p.rank_position == null ? `Ranker: chưa xếp hạng · ${p.name}`
        : `Ranker: hạng ${p.rank_position}/${p.rank_candidate_count ?? '—'} · ${p.name}`
      el.setAttribute('aria-label', `Xem thông tin ${p.name}; ${el.title}`)
      el.addEventListener('click', event => { event.stopPropagation(); stop(); setMapPoint(null); setInspectSearchPin(p); latest.current.onSelect(null) })
      markers.push(new goongjs.Marker(el).setLngLat([p.lon, p.lat]).addTo(m))
    })
    if (itinerary) fit()
    else m.flyTo({ center: props.center, zoom: 12.5, duration: duration(1000) })
    return () => markers.forEach(marker => marker.remove())
  }, [ready, props.itinerary, props.places, props.searchPins, props.center])
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
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: { 'line-color': ['get', 'color'], 'line-width': 4, 'line-opacity': 0.85 } })
      }
    }
    update()
    const segments = roadSegments(props.itinerary, props.places)
    let cursor = 0, completed = 0, failed = 0
    setRoadStatus(segments.length ? 'Đang tải tuyến đường Goong…' : '')
    async function worker() {
      while (cursor < segments.length && !controller.signal.aborted) {
        const { day, origin, destination } = segments[cursor++]
        const key = `${profile}:${origin.lat},${origin.lon}:${destination.lat},${destination.lon}`
        try {
          const cached = roadCache.current.get(key)
          let coordinates = cached && Date.now() - cached.at < 300000 ? cached.coordinates : null
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
        setRoadStatus(completed < segments.length ? `Đang tải tuyến đường ${completed}/${segments.length}…`
          : failed ? `${failed}/${segments.length} chặng chưa lấy được đường đi; không vẽ nối thẳng thay thế.`
          : 'Đã tải tuyến đường Goong theo tọa độ các điểm.')
      }
    }
    void Promise.all(Array.from({ length: Math.min(3, segments.length) }, worker))
    return () => controller.abort()
  }, [ready, props.itinerary, props.places, profile])
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
      <small>{roadStatus || 'Chọn lịch trình để xem đường đi.'} Tuyến {profile === 'car' ? 'ô tô' : 'xe máy'}, không phải chỉ dẫn đi bộ. Thời gian lịch trình vẫn là ước tính; không phải giao thông trực tiếp.</small>
      {props.itinerary && <button className="btn-secondary-3d" onClick={tour == null ? startTour : stop} disabled={!ready}>
        {tour == null ? '▶ Xem hành trình' : `■ Dừng · Ngày ${(tourPoint?.day ?? 0) + 1} · Điểm ${tour + 1} · ${selected?.name ?? ''}`}
      </button>}
    </div>
    {(popupPlace || mapPoint) && <aside className="trip-place-popup">
      <button aria-label="Đóng thông tin địa điểm" onClick={() => { setMapPoint(null); setInspectSearchPin(null); props.onSelect(null) }}>✕</button>
      {popupPlace ? <PlacePopup place={popupPlace} date={props.selected && props.selected !== 'stay' ? props.itinerary?.days[props.selected.day]?.date ?? null : null}
        pinned={!inspectSearchPin && props.pins.includes(popupPlace.id)}
        onPin={!inspectSearchPin && props.onPin ? p => props.onPin!(popupPlace.id, p) : undefined} /> : (
          <div className="grid max-h-[70vh] w-[min(22rem,calc(100vw-2rem))] gap-2 overflow-y-auto bg-[var(--bg-surface)] p-3 text-[var(--text-main)]">
            <h3 className="text-sm font-bold">Điều kiện tại điểm bản đồ</h3>
            <p className="text-[10px] text-[var(--text-muted)]">{mapPoint!.lat.toFixed(5)}, {mapPoint!.lon.toFixed(5)}</p>
            <LocationConditions latitude={mapPoint!.lat} longitude={mapPoint!.lon} />
          </div>
      )}
    </aside>}
  </>
}
