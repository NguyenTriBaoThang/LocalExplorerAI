import { useEffect, useRef, useState } from 'react'
// @ts-expect-error - Goong's Mapbox GL fork does not publish TypeScript definitions.
import goongjs from '@goongmaps/goong-js'
import '@goongmaps/goong-js/dist/goong-js.css'
import { Compass, Moon, RotateCcw, Sun } from 'lucide-react'
import { getPOIs } from '../../api/client'
import type { POI } from '../../types'
import { useTheme } from '../../theme'
import { useTranslation } from '../../i18n'

const GOONG_MAPTILES_KEY =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_GOONG_MAPTILES_KEY ||
  '7LMSzHRsHaOKryYjpUQ29NGQAcrSLFw8ho3tcpXU'

const MAP_STYLES = {
  night: 'https://tiles.goong.io/assets/goong_map_dark.json',
  day: 'https://tiles.goong.io/assets/goong_map_web.json',
}

const CITY_CENTER: [number, number] = [106.7009, 10.7769]
const BUILDING_LAYER_ID = 'local-explorer-hero-buildings-3d'

function addBuildingExtrusions(map: any): boolean {
  const style = map.getStyle?.()
  const layers = style?.layers as Array<Record<string, any>> | undefined
  const sources = style?.sources as Record<string, { type?: string }> | undefined
  if (!layers || !sources) return false

  if (layers.some((layer) => layer.id === BUILDING_LAYER_ID || layer.type === 'fill-extrusion')) return true

  const footprint = layers.find((layer) =>
    typeof layer['source-layer'] === 'string' &&
    /building/i.test(layer['source-layer']) &&
    typeof layer.source === 'string' &&
    sources[layer.source]?.type === 'vector'
  )
  if (!footprint?.source || !footprint['source-layer']) return false

  const firstLabel = layers.find((layer) => layer.type === 'symbol')
  map.addLayer({
    id: BUILDING_LAYER_ID,
    type: 'fill-extrusion',
    source: footprint.source,
    'source-layer': footprint['source-layer'],
    ...(footprint.filter ? { filter: footprint.filter } : {}),
    minzoom: 13.5,
    paint: {
      'fill-extrusion-color': [
        'interpolate', ['linear'], ['to-number', ['get', 'height'], 8],
        0, '#0b5b4a', 40, '#10b981', 120, '#2dd4bf',
      ],
      'fill-extrusion-height': [
        'interpolate', ['linear'], ['zoom'],
        13.5, 0,
        15, ['max', 8, ['to-number', ['get', 'height'], ['to-number', ['get', 'render_height'], 8]]],
      ],
      'fill-extrusion-base': ['max', 0, ['to-number', ['get', 'min_height'], ['to-number', ['get', 'render_min_height'], 0]]],
      'fill-extrusion-opacity': 0.88,
      'fill-extrusion-vertical-gradient': true,
    },
  }, firstLabel?.id)
  return true
}

function createPoiMarker(poi: POI, index: number): HTMLElement {
  const marker = document.createElement('div')
  marker.className = 'mapgl3d-poi-marker'
  marker.setAttribute('role', 'img')
  marker.setAttribute('aria-label', poi.name)
  marker.title = poi.name
  const number = document.createElement('span')
  number.textContent = String(index + 1)
  marker.appendChild(number)
  return marker
}

export function MapGL3DHero() {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<any>(null)
  const markersRef = useRef<any[]>([])
  const [pois, setPois] = useState<POI[]>([])
  const [loaded, setLoaded] = useState(false)
  const [hasExtrusions, setHasExtrusions] = useState(false)
  const [mapError, setMapError] = useState(false)
  const [styleMode, setStyleMode] = useState<'night' | 'day'>('night')
  const { t, locale } = useTranslation()
  const theme = useTheme()
  const isVi = locale === 'vi'

  useEffect(() => {
    setStyleMode(theme === 'light' ? 'day' : 'night')
  }, [theme])

  useEffect(() => {
    let active = true
    void getPOIs().then((rows) => {
      if (active) setPois(rows.filter((poi) => Number.isFinite(poi.latitude) && Number.isFinite(poi.longitude)).slice(0, 18))
    }).catch(() => {
      if (active) setPois([])
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    let active = true
    setLoaded(false)
    setMapError(false)
    setHasExtrusions(false)
    goongjs.accessToken = GOONG_MAPTILES_KEY

    const map = new goongjs.Map({
      container,
      style: MAP_STYLES[styleMode],
      center: CITY_CENTER,
      zoom: 13.6,
      pitch: 58,
      bearing: -18,
      minZoom: 10,
      maxZoom: 19,
      attributionControl: true,
      antialias: true,
    })
    mapRef.current = map

    const onLoad = () => {
      if (!active) return
      setHasExtrusions(addBuildingExtrusions(map))
      setLoaded(true)
      map.resize()
    }
    const onError = () => {
      if (active && !map.loaded()) setMapError(true)
    }
    map.on('load', onLoad)
    map.on('error', onError)

    const resizeObserver = new ResizeObserver(() => map.resize())
    resizeObserver.observe(container)

    return () => {
      active = false
      resizeObserver.disconnect()
      map.off('load', onLoad)
      map.off('error', onError)
      markersRef.current.forEach((marker) => marker.remove())
      markersRef.current = []
      map.remove()
      if (mapRef.current === map) mapRef.current = null
    }
  }, [styleMode])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !loaded) return

    markersRef.current.forEach((marker) => marker.remove())
    markersRef.current = pois.map((poi, index) => new goongjs.Marker({
      element: createPoiMarker(poi, index),
      anchor: 'bottom',
    }).setLngLat([poi.longitude, poi.latitude]).addTo(map))
  }, [loaded, pois])

  const resetCamera = () => {
    mapRef.current?.easeTo({ center: CITY_CENTER, zoom: 13.6, pitch: 58, bearing: -18, duration: 900 })
  }

  return (
    <div className="mapgl3d-hero">
      <div ref={containerRef} className="mapgl3d-canvas" role="application" aria-label={isVi ? 'Bản đồ 3D Thành phố Hồ Chí Minh' : 'Ho Chi Minh City 3D map'} />

      {!loaded && !mapError && <div className="mapgl3d-loading" aria-live="polite">{isVi ? 'Đang tải bản đồ 3D…' : 'Loading 3D map…'}</div>}
      {mapError && <div className="mapgl3d-error" role="status">{isVi ? 'Chưa tải được bản đồ. Kiểm tra kết nối và Goong Map Tiles key.' : 'Map unavailable. Check your connection and Goong Map Tiles key.'}</div>}

      <div className="mapgl3d-topbar">
        <div className="mapgl3d-location-pill">
          <span className="mapgl3d-live-dot" />
          <Compass size={13} />
          <span>{t('city3d.city')} · <strong>Quận 1, TP.HCM</strong></span>
        </div>
        <div className="mapgl3d-controls">
          <button type="button" onClick={() => setStyleMode('night')} aria-label={t('city3d.modeNight')} title={t('city3d.modeNight')} className={styleMode === 'night' ? 'active' : ''}><Moon size={14} /></button>
          <button type="button" onClick={() => setStyleMode('day')} aria-label={t('city3d.modeDay')} title={t('city3d.modeDay')} className={styleMode === 'day' ? 'active' : ''}><Sun size={14} /></button>
          <button type="button" onClick={resetCamera} aria-label={isVi ? 'Đặt lại góc nhìn bản đồ' : 'Reset map view'} title={isVi ? 'Đặt lại góc nhìn' : 'Reset view'}><RotateCcw size={13} /></button>
        </div>
      </div>

      <div className="mapgl3d-bottom-left">
        <span className="mapgl3d-status-dot" />
        <span>{loaded ? (isVi ? `${pois.length} điểm trải nghiệm` : `${pois.length} experience points`) : (isVi ? 'Bản đồ GL 3D' : 'GL 3D map')}</span>
      </div>
      <div className="mapgl3d-bottom-right">
        <span>{hasExtrusions ? (isVi ? 'MAP GL 3D · TÒA NHÀ NỔI KHỐI' : 'MAP GL 3D · 3D BUILDINGS') : 'MAP GL 3D'}</span>
      </div>
    </div>
  )
}
