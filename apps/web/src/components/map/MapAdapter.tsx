import { useEffect, useState } from 'react'
import { Marker, MapContainer, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import type { LatLngExpression } from 'leaflet'
import { divIcon } from 'leaflet'
import { MapPin, Layers, Sparkles, Box } from 'lucide-react'
import { Link } from 'react-router-dom'

export const LEG_COLORS = [
  '#10b981', // 1: Emerald
  '#f59e0b', // 2: Amber
  '#06b6d4', // 3: Cyan
  '#8b5cf6', // 4: Purple
  '#ec4899', // 5: Pink
  '#3b82f6', // 6: Blue
  '#f97316', // 7: Orange
]

export interface MapPoint {
  id: string
  latitude: number
  longitude: number
  name: string
  category?: string
  number?: number
  imageUrl?: string
  priceVnd?: number
  district?: string | null
}

export interface MapRoute {
  id: string
  coordinates: [number, number][]
  color?: string
}

function FocusPoint({ point }: { point?: MapPoint }) {
  const map = useMap()

  useEffect(() => {
    map.invalidateSize()
    const timer = setTimeout(() => {
      map.invalidateSize()
    }, 250)
    return () => clearTimeout(timer)
  }, [map])

  useEffect(() => {
    if (point) {
      map.flyTo([point.latitude, point.longitude], Math.max(map.getZoom(), 15), {
        duration: 0.8,
        easeLinearity: 0.25,
      })
    }
  }, [point, map])
  return null
}

function FitRouteBounds({ points, routes }: { points: MapPoint[]; routes: MapRoute[] }) {
  const map = useMap()
  const boundsFingerprint = `${points.map((point) => `${point.latitude},${point.longitude}`).join('|')}::${routes.map((route) => route.coordinates.map(([lat, lon]) => `${lat},${lon}`).join(';')).join('|')}`
  useEffect(() => {
    const positions = [
      ...points.map((point) => [point.latitude, point.longitude] as [number, number]),
      ...routes.flatMap((route) => route.coordinates),
    ]
    if (positions.length > 1) map.fitBounds(positions, { padding: [36, 36], maxZoom: 15 })
  }, [map, boundsFingerprint])
  return null
}

const TILE_PRESETS: Record<string, { name: string; url: string; attribution: string; subdomains?: string }> = {
  goong_streets: {
    name: 'Đường phố Sài Gòn (HD)',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Goong Directions V2 · Sài Gòn &copy; OpenStreetMap contributors',
  },
  google: {
    name: 'Google Maps VN',
    url: 'https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
    attribution: '&copy; Google Maps &copy; Goong Directions',
  },
  dark: {
    name: 'Đêm Huyền Ảo (Carto Dark)',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CARTO &copy; OpenStreetMap &copy; Goong Directions',
    subdomains: 'abcd',
  },
}

export function MapAdapter({
  points,
  selectedId,
  onSelect,
  routes = [],
  pointSourceLabel,
  mapFooterLabel,
  className = '',
}: {
  points: MapPoint[]
  selectedId?: string
  onSelect?: (id: string) => void
  routes?: MapRoute[]
  pointSourceLabel?: string
  mapFooterLabel?: string
  className?: string
}) {
  const [styleMode, setStyleMode] = useState<string>('goong_streets')
  const selected = points.find((point) => point.id === selectedId)
  const center: LatLngExpression = [10.775, 106.700]

  return (
    <div
      className={`map-shell-3d ${className}`}
      style={{ height: '680px', minHeight: '500px', width: '100%', position: 'relative' }}
    >
      <MapContainer
        center={center}
        zoom={13}
        scrollWheelZoom
        className="map-canvas-3d"
        style={{ height: '100%', width: '100%', minHeight: '500px' }}
      >
        <TileLayer
          attribution={TILE_PRESETS[styleMode]?.attribution || TILE_PRESETS.goong_streets.attribution}
          url={TILE_PRESETS[styleMode]?.url || TILE_PRESETS.goong_streets.url}
          subdomains={TILE_PRESETS[styleMode]?.subdomains || 'abc'}
          maxZoom={19}
        />
        <FitRouteBounds points={points} routes={routes} />
        <FocusPoint point={selected} />

        {/* Multi-color distinct route legs for clear navigation */}
        {routes.map((route, idx) => {
          const legColor = route.color || LEG_COLORS[idx % LEG_COLORS.length]
          return (
            <div key={route.id || `leg-${idx}`}>
              {/* Outer soft glow line */}
              <Polyline
                positions={route.coordinates}
                pathOptions={{
                  color: legColor,
                  weight: 10,
                  opacity: 0.32,
                  lineCap: 'round',
                  lineJoin: 'round',
                }}
              />
              {/* Core colored route line */}
              <Polyline
                positions={route.coordinates}
                pathOptions={{
                  color: legColor,
                  weight: 5,
                  opacity: 0.95,
                  lineCap: 'round',
                  lineJoin: 'round',
                }}
              />
            </div>
          )
        })}

        {points.map((point) => {
          const active = point.id === selectedId
          const icon = divIcon({
            className: 'custom-3d-marker',
            html: `
              <div class="marker-3d-pin ${active ? 'marker-3d-active' : ''}">
                <div class="marker-pulse-ring"></div>
                <div class="marker-bubble">
                  ${point.number ? `<b>${point.number}</b>` : '<span class="marker-dot-inner"></span>'}
                </div>
                <div class="marker-stem"></div>
                <div class="marker-shadow"></div>
              </div>
            `,
            iconSize: [38, 48],
            iconAnchor: [19, 44],
            popupAnchor: [0, -42],
          })

          return (
            <Marker
              key={point.id}
              position={[point.latitude, point.longitude]}
              icon={icon}
              eventHandlers={{ click: () => onSelect?.(point.id) }}
            >
              <Popup className="custom-3d-popup">
                <div className="map-popup-3d">
                  {point.imageUrl && (
                    <div className="popup-photo-wrap">
                      <img
                        src={point.imageUrl}
                        alt={point.name}
                        className="popup-photo-img"
                        loading="lazy"
                        onError={(e) => {
                          ;(e.target as HTMLElement).style.display = 'none'
                        }}
                      />
                      <div className="popup-photo-gradient" />
                      <span className="popup-kicker-floating">{point.category ?? 'Trải nghiệm'}</span>
                    </div>
                  )}
                  <div className="popup-content-box">
                    {!point.imageUrl && <span className="popup-kicker">{point.category ?? 'Trải nghiệm'}</span>}
                    <strong className="popup-title">{point.name}</strong>
                    <div className="popup-sub-row">
                      <span className="popup-sub">
                        <MapPin size={11} /> {point.district || pointSourceLabel || 'TP. Hồ Chí Minh'}
                      </span>
                      {point.priceVnd !== undefined && (
                        <span className="popup-price-pill">
                          {point.priceVnd > 0 ? `${point.priceVnd.toLocaleString('vi-VN')}₫` : 'Miễn phí'}
                        </span>
                      )}
                    </div>
                    {onSelect && (
                      <button
                        type="button"
                        className="popup-select-btn"
                        onClick={() => onSelect(point.id)}
                      >
                        <Sparkles size={12} /> Xem chi tiết
                      </button>
                    )}
                  </div>
                </div>
              </Popup>
            </Marker>
          )
        })}
      </MapContainer>

      {/* Top Map Controls */}
      <div className="map-3d-controls">
        <div className="map-3d-badge">
          <span className="badge-live-pulse" />
          <span>GOONG MAPS & DIRECTIONS V2 · SÀI GÒN</span>
        </div>

        <Link
          to="/map-3d"
          className="map-layer-toggle"
          style={{ textDecoration: 'none', background: 'rgba(99, 102, 241, 0.2)', borderColor: 'rgba(129, 140, 248, 0.4)' }}
          title="Xem mô hình 3D Landmark & Tùy chỉnh vị trí"
        >
          <Box size={13} />
          <span>Bản đồ 3D Landmark</span>
        </Link>

        <button
          type="button"
          className="map-layer-toggle"
          onClick={() => {
            const keys = Object.keys(TILE_PRESETS)
            const nextIdx = (keys.indexOf(styleMode) + 1) % keys.length
            setStyleMode(keys[nextIdx])
          }}
          title="Chuyển lớp bản đồ (Goong HD / Google / Đêm)"
        >
          <Layers size={13} />
          <span>{TILE_PRESETS[styleMode]?.name || 'Goong Streets'}</span>
        </button>
      </div>

      <div className="map-3d-bottom-info">
        <span>{mapFooterLabel || 'Tọa độ & tuyến đường chính xác từ Goong Directions API · Đồng bộ với lịch trình'}</span>
      </div>
    </div>
  )
}
