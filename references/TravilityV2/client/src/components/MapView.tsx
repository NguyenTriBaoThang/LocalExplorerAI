import { useEffect, useRef, useState } from 'react'
import Map, { Layer, Marker, Popup, Source, type MapRef } from 'react-map-gl/maplibre'
import polyline from '@mapbox/polyline'
import { setWorkerUrl } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import type { Itinerary, Place } from '../api'
import { selectedPlace, tourStops, type Selected } from '../place'
import PlacePopup from './PlacePopup'

// MapLibre v6 tìm worker cạnh file của nó (import.meta.url) — sau khi Vite bundle thì file đó không tồn tại
setWorkerUrl(workerUrl)

const STYLE_URL = `https://tiles.goong.io/assets/goong_map_web.json?api_key=${import.meta.env.VITE_GOONG_MAPTILES_KEY}`
export const DAY_COLORS = ['#047857', '#b45309', '#1d4ed8', '#be123c', '#7c3aed', '#0f766e', '#a16207']
const EMPTY: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }
const still = () => matchMedia('(prefers-reduced-motion: reduce)').matches
const dur = (ms: number) => (still() ? 0 : ms)

async function legLine(a: Place, b: Place): Promise<[number, number][]> {
  try {
    const r = await fetch(`https://rsapi.goong.io/Direction?origin=${a.lat},${a.lon}&destination=${b.lat},${b.lon}` +
      `&vehicle=bike&api_key=${import.meta.env.VITE_GOONG_API_KEY}`, { signal: AbortSignal.timeout(5000) })
    const body = await r.json()
    return polyline.decode(body.routes[0].overview_polyline.points).map(([lat, lon]: [number, number]) => [lon, lat])
  } catch {
    return [[a.lon, a.lat], [b.lon, b.lat]] // Goong lỗi hoặc quá 5s → đường thẳng, không chặn demo
  }
}

export default function MapView({ center, searchPins, itinerary, places, selected, onSelect, padding, pins, onPin }: {
  center: [number, number]; searchPins: Place[]; itinerary: Itinerary | null; places: Record<string, Place>
  selected: Selected; onSelect: (s: Selected) => void; padding: { left: number; right: number }
  pins: number[]; onPin?: (placeId: number, pinned: boolean) => void
}) {
  const mapRef = useRef<MapRef>(null)
  const [routes, setRoutes] = useState<GeoJSON.FeatureCollection>(EMPTY)
  const [tour, setTour] = useState<number | null>(null)  // vị trí trong tourStops đang bay tới
  const tourRun = useRef(0)  // tăng lên để huỷ vòng bay đang chạy
  const stopTour = () => { tourRun.current++; setTour(null) }

  function fit() {
    const map = mapRef.current
    if (!map || !itinerary) return
    const ids = itinerary.days.flatMap((d) => d.stops.map((s) => s.place_id))
    if (itinerary.stay_place_id != null) ids.push(itinerary.stay_place_id)
    const pts = ids.map((id) => places[id]).filter((p): p is Place => p !== undefined)
    if (pts.length === 0) return
    const lons = pts.map((p) => p.lon), lats = pts.map((p) => p.lat)
    map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
      { padding: { top: 60, bottom: 110, ...padding }, maxZoom: 15, pitch: 0, bearing: 0, duration: dur(1200) })  // pitch > 0 làm lệch khung: Stop xa bị khuất sau panel
  }

  useEffect(() => {
    if (!itinerary) mapRef.current?.flyTo({ center, zoom: 12.5, pitch: 45, duration: dur(2000) })
  }, [center])

  useEffect(() => {  // Itinerary đổi: dừng tour, vẽ tuyến, thu vừa toàn tuyến — không tự bay
    stopTour()
    if (!itinerary) { setRoutes(EMPTY); return }
    fit()
    let cancelled = false
    Promise.all(itinerary.days.flatMap((day, i) => day.legs.map(async (leg): Promise<GeoJSON.Feature | null> => {
      // ponytail: Leg tới/từ Hub chưa vẽ (Hub không có trong places); thêm marker Hub khi cần
      const a = leg.from_place_id != null ? places[leg.from_place_id] : undefined
      const b = leg.to_place_id != null ? places[leg.to_place_id] : undefined
      if (!a || !b) return null
      return { type: 'Feature', properties: { color: DAY_COLORS[i % DAY_COLORS.length] },
        geometry: { type: 'LineString', coordinates: await legLine(a, b) } }
    }))).then((fs) => {
      if (!cancelled) setRoutes({ type: 'FeatureCollection', features: fs.filter((f): f is GeoJSON.Feature => f !== null) })
    })
    return () => { cancelled = true }
  }, [itinerary, places])

  const selId = selectedPlace(itinerary, selected)
  const sel = selId != null ? places[selId] : undefined

  useEffect(() => {  // chọn Stop (từ Timeline, marker hoặc tour) → bay tới
    const map = mapRef.current
    if (!sel || !map) return
    map.flyTo({ center: [sel.lon, sel.lat], zoom: 15, pitch: 60, duration: dur(1800),
      bearing: tour != null ? (map.getBearing() + 40) % 360 : map.getBearing(),
      padding: { top: 0, bottom: 0, ...padding } })
  }, [selected])

  useEffect(() => () => { tourRun.current++ }, [])  // unmount → huỷ tour

  async function runTour() {
    if (!itinerary) return
    const run = ++tourRun.current
    for (const [i, s] of tourStops(itinerary).entries()) {
      if (tourRun.current !== run) return
      setTour(i); onSelect(s)
      await new Promise((r) => setTimeout(r, still() ? 1500 : 2200))
    }
    if (tourRun.current === run) { setTour(null); fit() }
  }

  const order = itinerary ? tourStops(itinerary) : []
  const at = tour != null ? order[tour] : undefined
  const date = selected && selected !== 'stay' ? itinerary?.days[selected.day]?.date ?? null : null
  const stay = itinerary?.stay_place_id != null ? places[itinerary.stay_place_id] : undefined

  return (
    <div className="absolute inset-0">
      <Map ref={mapRef} mapStyle={STYLE_URL} style={{ width: '100%', height: '100%' }}
        initialViewState={{ longitude: center[0], latitude: center[1], zoom: 12, pitch: 45 }}
        onLoad={fit}
        onMoveStart={(e) => { if (e.originalEvent && tour != null) stopTour() }}
        onClick={() => { if (tour == null) onSelect(null) }}>
        <Source id="routes" type="geojson" data={routes}>
          <Layer id="routes" type="line" layout={{ 'line-cap': 'round', 'line-join': 'round' }}
            paint={{ 'line-color': ['get', 'color'], 'line-width': 4, 'line-opacity': 0.85 }} />
        </Source>
        {searchPins.map((p) => (
          <Marker key={`s${p.id}`} longitude={p.lon} latitude={p.lat}>
            <span className="relative flex size-3" title={p.name}>
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-amber-400 opacity-75" />
              <span className="relative inline-flex size-3 rounded-full bg-amber-500" />
            </span>
          </Marker>
        ))}
        {itinerary?.days.flatMap((day, i) => day.stops.map((s, j) => {
          const p = places[s.place_id]
          const on = selected !== null && selected !== 'stay' && selected.day === i && selected.stop === j
          return p && (
            <Marker key={`d${i}-${j}`} longitude={p.lon} latitude={p.lat}
              onClick={(e) => { e.originalEvent.stopPropagation(); onSelect({ day: i, stop: j }) }}>
              <button type="button" aria-label={`Ngày ${i + 1}, điểm ${j + 1}: ${p.name}`} title={p.name}
                style={{ background: DAY_COLORS[i % DAY_COLORS.length] }}
                className={`flex cursor-pointer items-center justify-center rounded-full border-2 border-white font-bold text-white shadow ${
                  on ? 'size-9 text-sm ring-4 ring-marigold/60' : 'size-7 text-xs'}`}>
                {j + 1}
              </button>
            </Marker>
          )
        }))}
        {stay && (
          <Marker longitude={stay.lon} latitude={stay.lat}
            onClick={(e) => { e.originalEvent.stopPropagation(); onSelect('stay') }}>
            <button type="button" title={stay.name}
              className="cursor-pointer rounded-md border-2 border-white bg-stone-900 px-2 py-1 text-xs font-semibold text-white shadow">
              Chỗ ở
            </button>
          </Marker>
        )}
        {sel && (
          <Popup longitude={sel.lon} latitude={sel.lat} offset={22} closeOnClick={false} maxWidth="none"
            className="place-popup" onClose={() => { stopTour(); onSelect(null) }}>
            <PlacePopup place={sel} date={date} pinned={pins.includes(sel.id)}
              onPin={selected !== 'stay' && onPin ? (v) => onPin(sel.id, v) : undefined} />
          </Popup>
        )}
      </Map>
      {itinerary && (at == null ? (
        <button type="button" onClick={runTour}
          className="absolute bottom-6 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2.5 rounded-full bg-stone-900 py-2.5 pl-3 pr-4 text-sm font-semibold text-white shadow-xl">
          <span className="grid size-7 place-items-center rounded-full bg-marigold text-stone-900">▶</span>Xem hành trình
        </button>
      ) : (
        <button type="button" onClick={stopTour}
          className="absolute bottom-6 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2.5 rounded-full bg-stone-900 py-2.5 pl-3 pr-4 text-sm font-semibold text-white shadow-xl">
          <span className="grid size-7 place-items-center rounded-full bg-marigold text-stone-900">⏹</span>Dừng
          <span className="font-normal text-stone-300">
            Ngày {at.day + 1} · điểm {tour! + 1}/{order.length} · {places[itinerary.days[at.day].stops[at.stop].place_id]?.name}
          </span>
        </button>
      ))}
    </div>
  )
}
