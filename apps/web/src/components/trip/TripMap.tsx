import { GOONG_MAPTILES_KEY } from '../map/goongConfig'
import { useEffect, useRef, useState } from 'react'
import goongjs from '@goongmaps/goong-js'
import '@goongmaps/goong-js/dist/goong-js.css'
import type { Itinerary, Place } from '../../api/trips'
import { selectedPlace, tourStops, type Selected } from './place'
import PlacePopup from './PlacePopup'
import { DEFAULT_CALIBRATIONS, sanitizeCalibration } from '../3d/landmark/types'
import { createLandmarkLayer } from './landmarkLayer'

const COLORS = ['#047857', '#b45309', '#2563eb', '#be123c', '#7c3aed', '#0f766e']
const duration = (ms: number) => matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : ms
type Props = { center: [number, number]; searchPins: Place[]; itinerary: Itinerary | null; places: Record<string, Place>; selected: Selected; onSelect(s: Selected): void; padding: { left: number; right: number }; pins: number[]; onPin?(id: number, pinned: boolean): void }

export default function TripMap(props: Props) {
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<any>(null)
  const latest = useRef(props); latest.current = props
  const run = useRef(0)
  const [ready, setReady] = useState(false)
  const [tour, setTour] = useState<number | null>(null)
  const [error, setError] = useState('')
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
    m.on('error', () => setError('Bản đồ đang gặp lỗi tải. Lịch trình vẫn được giữ lại.'))
    return () => { disposed = true; run.current++; m.remove(); map.current = null }
  }, [])
  useEffect(() => {
    if (!ready) return
    stop()
    const m = map.current
    const markers: any[] = []
    const features: any[] = []
    const { itinerary, places } = props
    itinerary?.days.forEach((d, day) => {
      const pts = d.stops.map(s => places[s.place_id]).filter(Boolean)
      const stay = itinerary.stay_place_id == null ? undefined : places[itinerary.stay_place_id]
      const line = stay ? [stay, ...pts, stay] : pts
      if (line.length > 1) features.push({ type: 'Feature', properties: { color: COLORS[day % COLORS.length] }, geometry: { type: 'LineString', coordinates: line.map(p => [p.lon, p.lat]) } })
      d.stops.forEach((s, index) => {
        const p = places[s.place_id]; if (!p) return
        const el = document.createElement('button'); el.type = 'button'; el.className = 'trip-pin'
        el.textContent = `${day + 1}.${index + 1}`; el.style.backgroundColor = COLORS[day % COLORS.length]; el.title = p.name
        el.addEventListener('click', () => { stop(); latest.current.onSelect({ day, stop: index }) })
        markers.push(new goongjs.Marker(el).setLngLat([p.lon, p.lat]).addTo(m))
      })
    })
    props.searchPins.forEach(p => {
      const el = document.createElement('span'); el.className = 'trip-pin trip-pin--searching'; el.textContent = '•'; el.title = p.name
      markers.push(new goongjs.Marker(el).setLngLat([p.lon, p.lat]).addTo(m))
    })
    const data = { type: 'FeatureCollection', features }
    if (m.getSource('trip-routes')) m.getSource('trip-routes').setData(data)
    else {
      m.addSource('trip-routes', { type: 'geojson', data })
      m.addLayer({ id: 'trip-routes-line', type: 'line', source: 'trip-routes', paint: { 'line-color': ['get', 'color'], 'line-width': 3, 'line-dasharray': [2, 2] } })
    }
    if (itinerary) fit()
    else m.flyTo({ center: props.center, zoom: 12.5, duration: duration(1000) })
    return () => markers.forEach(marker => marker.remove())
  }, [ready, props.itinerary, props.places, props.searchPins, props.center])
  const selectedId = selectedPlace(props.itinerary, props.selected)
  const selected = selectedId == null ? undefined : props.places[selectedId]
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
    <div ref={container} className="absolute inset-0" />
    {error && <p role="status" className="trip-map-notice">{error}</p>}
    <div className="trip-map-controls">
      <small>Đường nét đứt nối thứ tự điểm, không phải chỉ dẫn đường bộ. Giờ và giá theo dữ liệu tham khảo.</small>
      {props.itinerary && <button className="btn-secondary-3d" onClick={tour == null ? startTour : stop} disabled={!ready}>
        {tour == null ? '▶ Xem hành trình' : `■ Dừng · Ngày ${(tourPoint?.day ?? 0) + 1} · Điểm ${tour + 1} · ${selected?.name ?? ''}`}
      </button>}
    </div>
    {selected && <aside className="trip-place-popup"><button aria-label="Đóng thông tin địa điểm" onClick={() => props.onSelect(null)}>✕</button><PlacePopup place={selected} date={props.selected && props.selected !== 'stay' ? props.itinerary?.days[props.selected.day]?.date ?? null : null} pinned={props.pins.includes(selected.id)} onPin={props.onPin ? p => props.onPin!(selected.id, p) : undefined} /></aside>}
  </>
}
