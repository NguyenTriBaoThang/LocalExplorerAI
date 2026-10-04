import type { GeoPoint } from './geo'

export interface ModelCalibration {
  model_name: string
  display_name: string
  file_url: string
  latitude: number
  longitude: number
  altitude: number
  /** Compass heading of the facade, degrees clockwise from North. */
  heading: number
  pitch: number
  roll: number
  /** Real-world height of the building in metres (model is normalised to height 1). */
  scale: number
  description?: string
  updated_at?: string | null
}

/** Official POI coordinate of Nhà thờ Đức Bà — the scene origin. */
export const NOTRE_DAME_ORIGIN: GeoPoint = { lat: 10.779785, lng: 106.699018 }

export const DEFAULT_CALIBRATION: ModelCalibration = {
  model_name: 'nhathoducba',
  display_name: 'Nhà thờ Đức Bà Sài Gòn',
  file_url: '/models_3d/NhaThoDucBa2_cathedral_textured_1004080927_texture.glb',
  latitude: NOTRE_DAME_ORIGIN.lat,
  longitude: NOTRE_DAME_ORIGIN.lng,
  altitude: 0,
  heading: 0,
  pitch: 0,
  roll: 0,
  scale: 58,
  description: 'Vương cung thánh đường Chính tòa Đức Mẹ Vô nhiễm Nguyên tội tại Công xã Paris, Quận 1.',
}

/** Older saves used a raw multiplier (e.g. 0.08) — treat anything tiny as invalid. */
export function sanitizeCalibration(raw: Partial<ModelCalibration>, fallback: ModelCalibration): ModelCalibration {
  const merged = { ...fallback, ...raw }
  const finite = (v: unknown, d: number) => (typeof v === 'number' && Number.isFinite(v) ? v : d)
  return {
    ...merged,
    latitude: finite(merged.latitude, fallback.latitude),
    longitude: finite(merged.longitude, fallback.longitude),
    altitude: finite(merged.altitude, 0),
    heading: finite(merged.heading, 0),
    scale: finite(merged.scale, 0) >= 1 ? merged.scale : fallback.scale,
  }
}
