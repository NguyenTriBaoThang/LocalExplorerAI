import { useEffect, useState } from 'react'
import { Marker, MapContainer, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import type { LatLngExpression } from 'leaflet'
import { divIcon } from 'leaflet'
import { MapPin, Layers, Sparkles, Box, Maximize2, Minimize2, RotateCcw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { CityHero3D } from '../3d/CityHero3D'

export const LEG_COLORS = [
  '#10b981', // 1: Emerald
  '#06b6d4', // 2: Cyan
  '#f59e0b', // 3: Amber
  '#8b5cf6', // 4: Purple
  '#ec4899', // 5: Pink
  '#3b82f6', // 6: Blue
  '#f97316', // 7: Orange
]

export interface MapPoint {
  id: string
  placeId?: string
  latitude: number
  longitude: number
  name: string
  category?: string
  number?: number
  imageUrl?: string
  priceVnd?: number
  district?: string | null
  type?: 'origin' | 'stop' | 'destination'
  time?: string
  address?: string
}

export interface MapRoute {
  id: string
  coordinates: [number, number][]
  color?: string
  fromName?: string
  toName?: string
  legIndex?: number
  durationMin?: number
  distanceM?: number
}

const EMPTY_ROUTES: MapRoute[] = []

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function MapViewController({
  selectedPoint,
  resetCounter,
  allPositions,
}: {
  selectedPoint?: MapPoint
  resetCounter: number
  allPositions: [number, number][]
}) {
  const map = useMap()

  useEffect(() => {
    map.invalidateSize()
    const timer = setTimeout(() => map.invalidateSize(), 250)
    return () => clearTimeout(timer)
  }, [map])

  useEffect(() => {
    if (selectedPoint) {
      map.flyTo([selectedPoint.latitude, selectedPoint.longitude], Math.max(map.getZoom(), 15), {
        duration: 0.8,
        easeLinearity: 0.25,
      })
    }
  }, [selectedPoint, map])

  useEffect(() => {
    if (resetCounter > 0 && allPositions.length > 1) {
      map.fitBounds(allPositions, { padding: [48, 48], maxZoom: 15 })
    }
  }, [resetCounter, map, allPositions])

  return null
}

function InitialBoundsFitter({ points, routes }: { points: MapPoint[]; routes: MapRoute[] }) {
  const map = useMap()
  const fingerprint = `${points.map((p) => `${p.latitude},${p.longitude}`).join('|')}::${routes.map((r) => r.coordinates.map(([lat, lon]) => `${lat},${lon}`).join(';')).join('|')}`

  useEffect(() => {
    const positions = [
      ...points.map((point) => [point.latitude, point.longitude] as [number, number]),
      ...routes.flatMap((route) => route.coordinates),
    ]
    if (positions.length > 1) {
      map.fitBounds(positions, { padding: [42, 42], maxZoom: 15 })
    }
  }, [map, fingerprint])

  return null
}

const TILE_PRESETS: Record<string, { name: string; url: string; attribution: string; subdomains?: string }> = {
  goong_streets: {
    name: 'Đường phố Sài Gòn (HD)',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri',
  },
  google: {
    name: 'Google Maps VN',
    url: 'https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
    attribution: '&copy; Google Maps',
  },
  dark: {
    name: 'Đêm Huyền Ảo (Carto Dark)',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CARTO &copy; OpenStreetMap contributors',
    subdomains: 'abcd',
  },
}

export function MapAdapter({
  points,
  selectedId,
  onSelect,
  routes = EMPTY_ROUTES,
  pointSourceLabel,
  mapFooterLabel,
  className = '',
  compact = false,
  showJourneyTracker = true,
  isExpanded = false,
  onExpandToggle,
}: {
  points: MapPoint[]
  selectedId?: string
  onSelect?: (id: string) => void
  routes?: MapRoute[]
  pointSourceLabel?: string
  mapFooterLabel?: string
  className?: string
  compact?: boolean
  showJourneyTracker?: boolean
  isExpanded?: boolean
  onExpandToggle?: () => void
}) {
  const [styleMode, setStyleMode] = useState<string>('goong_streets')
  const [resetCounter, setResetCounter] = useState(0)
  const [is3D, setIs3D] = useState(false)
  const selected = points.find((point) => point.id === selectedId)
  const center: LatLngExpression = [10.775, 106.7]

  const allPositions: [number, number][] = [
    ...points.map((p) => [p.latitude, p.longitude] as [number, number]),
    ...routes.flatMap((r) => r.coordinates),
  ]

  const hasEndpoints = points.some((p) => p.type === 'origin' || p.type === 'destination')

  return (
    <div
      className={`map-shell-3d ${isExpanded ? 'map-shell-expanded' : ''} ${className}`}
      style={{
        height: isExpanded ? '80vh' : compact ? '400px' : '680px',
        minHeight: compact ? '360px' : '520px',
        width: '100%',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Visual Journey Tracker Strip (Above map canvas if endpoints/routes exist) */}
      {showJourneyTracker && hasEndpoints && points.length > 1 && (
        <div className="map-journey-tracker">
          <div className="journey-tracker-track">
            {points.map((point, idx) => {
              const active = point.id === selectedId
              const isOrigin = point.type === 'origin' || point.id.includes('origin')
              const isDest = point.type === 'destination' || point.id.includes('destination')
              const leg = routes[idx]

              return (
                <div key={point.id} className="journey-tracker-step-wrap">
                  <button
                    type="button"
                    className={`journey-node-btn ${active ? 'active' : ''} ${isOrigin ? 'is-origin' : ''} ${isDest ? 'is-dest' : ''}`}
                    onClick={() => onSelect?.(point.id)}
                    title={point.name}
                  >
                    <span className="journey-node-badge">
                      {isOrigin ? '🚩' : isDest ? '🏁' : point.number ?? idx + 1}
                    </span>
                    <div className="journey-node-text-col">
                      <span className="journey-node-kicker">
                        {isOrigin ? 'Xuất phát' : isDest ? 'Điểm về' : `Điểm ${point.number ?? idx + 1}`}
                      </span>
                      <span className="journey-node-name">{point.name}</span>
                    </div>
                  </button>

                  {idx < points.length - 1 && (
                    <div className="journey-connector">
                      <div
                        className="connector-line"
                        style={{ backgroundColor: LEG_COLORS[idx % LEG_COLORS.length] }}
                      />
                      <span
                        className="connector-pill"
                        style={{ color: LEG_COLORS[idx % LEG_COLORS.length] }}
                        title={`Chặng ${idx + 1}: ${leg?.durationMin ?? '?'} phút`}
                      >
                        {leg?.durationMin ? `${leg.durationMin}p ➔` : '➔'}
                      </span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Main Map View Canvas */}
      <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        {is3D ? (
          <CityHero3D
            journeyPoints={points}
            routes={routes}
            selectedId={selectedId}
            onSelect={onSelect}
            variant="inline"
          />
        ) : (
        <MapContainer
          center={center}
          zoom={13}
          scrollWheelZoom
          className="map-canvas-3d"
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution={TILE_PRESETS[styleMode]?.attribution || TILE_PRESETS.goong_streets.attribution}
            url={TILE_PRESETS[styleMode]?.url || TILE_PRESETS.goong_streets.url}
            subdomains={TILE_PRESETS[styleMode]?.subdomains || 'abc'}
            maxZoom={19}
          />
          <InitialBoundsFitter points={points} routes={routes} />
          <MapViewController
            selectedPoint={selected}
            resetCounter={resetCounter}
            allPositions={allPositions}
          />

          {/* Distinct Multi-colored Route Polylines & Directional Indicators */}
          {routes.map((route, idx) => {
            const legColor = route.color || LEG_COLORS[idx % LEG_COLORS.length]
            const midIndex = Math.floor(route.coordinates.length / 2)
            const midCoord = route.coordinates[midIndex]
            const legNum = route.legIndex ?? idx + 1
            const durationTxt = route.durationMin ? `${route.durationMin}p` : ''
            const distanceTxt = route.distanceM ? `${(route.distanceM / 1000).toFixed(1)}km` : ''

            const waypointIcon = divIcon({
              className: 'leg-waypoint-marker-container',
              html: `
                <div class="leg-waypoint-bubble" style="border-left: 3px solid ${legColor};">
                  <span class="leg-waypoint-num" style="background: ${legColor};">Chặng ${legNum}</span>
                  <span class="leg-waypoint-info">${durationTxt}${distanceTxt ? ` · ${distanceTxt}` : ''} ➔</span>
                </div>
              `,
              iconSize: [120, 26],
              iconAnchor: [60, 13],
            })

            return (
              <div key={route.id || `leg-${idx}`}>
                {/* Outer glowing line */}
                <Polyline
                  positions={route.coordinates}
                  pathOptions={{
                    color: legColor,
                    weight: 9,
                    opacity: 0.35,
                    lineCap: 'round',
                    lineJoin: 'round',
                  }}
                />
                {/* Core route line */}
                <Polyline
                  positions={route.coordinates}
                  pathOptions={{
                    color: legColor,
                    weight: 4.5,
                    opacity: 0.95,
                    lineCap: 'round',
                    lineJoin: 'round',
                  }}
                />
                {/* Directional midpoint chip */}
                {midCoord && (
                  <Marker
                    position={midCoord}
                    icon={waypointIcon}
                    interactive={false}
                  />
                )}
              </div>
            )
          })}

          {/* Points Markers: Origin, Intermediate Stops, and Destination */}
          {points.map((point) => {
            const active = point.id === selectedId
            const isOrigin = point.type === 'origin' || point.id.includes('origin')
            const isDest = point.type === 'destination' || point.id.includes('destination')

            let markerTypeClass = 'marker-stop-pin'
            let bubbleContent = `<b>${point.number ?? '•'}</b>`
            let labelText = `${point.number ? `${point.number}. ` : ''}${point.name}`
            let labelBadge = ''

            if (isOrigin) {
              markerTypeClass = 'marker-origin-pin'
              bubbleContent = '<span class="marker-symbol">🚩</span>'
              labelText = point.name
              labelBadge = '<span class="badge-origin-pill">XUẤT PHÁT</span>'
            } else if (isDest) {
              markerTypeClass = 'marker-dest-pin'
              bubbleContent = '<span class="marker-symbol">🏁</span>'
              labelText = point.name
              labelBadge = '<span class="badge-dest-pill">ĐIỂM VỀ</span>'
            } else if (point.number) {
              labelBadge = `<span class="badge-stop-pill">ĐIỂM ${point.number}</span>`
            }

            const icon = divIcon({
              className: 'custom-3d-marker',
              html: `
                <div class="marker-3d-pin-v2 ${markerTypeClass} ${active ? 'marker-3d-active' : ''}">
                  <div class="marker-floating-label-pill">
                    ${labelBadge}
                    <span class="marker-label-name">${escapeHtml(labelText)}</span>
                    ${point.time ? `<span class="marker-label-time">${point.time}</span>` : ''}
                  </div>
                  <div class="marker-pulse-ring"></div>
                  <div class="marker-bubble">
                    ${bubbleContent}
                  </div>
                  <div class="marker-stem"></div>
                  <div class="marker-shadow"></div>
                </div>
              `,
              iconSize: [180, 78],
              iconAnchor: [90, 72],
              popupAnchor: [0, -68],
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
                      <div className="popup-badge-row">
                        <span className="popup-kicker">
                          {isOrigin ? '🚩 Điểm xuất phát' : isDest ? '🏁 Điểm kết thúc' : point.category ?? 'Trải nghiệm'}
                        </span>
                        {point.time && <span className="popup-time-pill">{point.time}</span>}
                      </div>
                      <strong className="popup-title">{point.name}</strong>
                      <div className="popup-sub-row">
                        <span className="popup-sub">
                          <MapPin size={11} /> {point.address || point.district || pointSourceLabel || 'TP. Hồ Chí Minh'}
                        </span>
                        {point.priceVnd !== undefined && (
                          <span className="popup-price-pill">
                            {point.priceVnd > 0 ? `${point.priceVnd.toLocaleString('vi-VN')}₫` : 'Miễn phí'}
                          </span>
                        )}
                      </div>
                      {point.placeId ? (
                        <Link
                          className="popup-select-btn"
                          to={`/places/${encodeURIComponent(point.placeId)}`}
                          onClick={(event) => event.stopPropagation()}
                        >
                          <Sparkles size={12} /> Xem chi tiết địa điểm
                        </Link>
                      ) : onSelect && (
                        <button
                          type="button"
                          className="popup-select-btn"
                          onClick={() => onSelect(point.id)}
                        >
                          <Sparkles size={12} /> Tập trung điểm này
                        </button>
                      )}
                    </div>
                  </div>
                </Popup>
              </Marker>
            )
          })}
        </MapContainer>
        )}

        {/* Floating Top Controls (Neat Top-Right Stack) */}
        <div className="map-floating-top-right">
          <div className="map-control-btn-group">
            {!is3D && <>
            <button
              type="button"
              className="map-float-btn"
              onClick={() => setResetCounter((c) => c + 1)}
              title="Xem toàn cảnh toàn bộ chuyến đi (Fit Bounds)"
            >
              <RotateCcw size={14} />
              <span>Toàn cảnh</span>
            </button>

            <button
              type="button"
              className="map-float-btn"
              onClick={() => {
                const keys = Object.keys(TILE_PRESETS)
                const nextIdx = (keys.indexOf(styleMode) + 1) % keys.length
                setStyleMode(keys[nextIdx])
              }}
              title="Chuyển chế độ lớp bản đồ"
            >
              <Layers size={14} />
              <span>{TILE_PRESETS[styleMode]?.name.split(' ')[0] || 'Lớp bản đồ'}</span>
            </button>
            </>}

            {onExpandToggle && (
              <button
                type="button"
                className="map-float-btn"
                onClick={onExpandToggle}
                title={isExpanded ? 'Thu nhỏ bản đồ về cột bên phải' : 'Phóng to bản đồ toàn chiều rộng'}
              >
                {isExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                <span>{isExpanded ? 'Thu nhỏ' : 'Mở rộng'}</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => setIs3D((current) => !current)}
              aria-pressed={is3D}
              className="map-float-btn map-float-btn-accent"
              title={is3D ? 'Quay lại bản đồ 2D' : 'Xem hành trình trên bản đồ 3D'}
            >
              {is3D ? <Layers size={14} /> : <Box size={14} />}
              <span>{is3D ? 'Bản đồ 2D' : '3D Sài Gòn'}</span>
            </button>
          </div>
        </div>

        {/* Top-Left Provider Status Pill */}
        <div className="map-floating-top-left">
          <div className="map-provider-pill">
            <span className="badge-live-pulse" />
            <span>{is3D ? 'Bản đồ 3D hành trình · TP.HCM' : 'Bản đồ hành trình · TP.HCM'}</span>
          </div>
        </div>

        {/* Bottom Route Legend Overlay */}
        <div className="map-3d-bottom-info">
          <span>{mapFooterLabel || (is3D ? 'Mô hình 3D minh họa · Tuyến nối theo các điểm hành trình' : 'Vị trí theo danh mục · Kiểm tra nguồn thông tin trước chuyến đi')}</span>
        </div>
      </div>
    </div>
  )
}

