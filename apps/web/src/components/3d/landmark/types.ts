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

export const HOI_AN_CALIBRATION: ModelCalibration = {
  model_name: 'hoian',
  display_name: 'Phố cổ Hội An - Chùa Cầu',
  file_url: '/models_3d/HoiAn_ChuaCau_web.glb',
  latitude: 15.8779,
  longitude: 108.3264,
  altitude: 0,
  heading: 0,
  pitch: 0,
  roll: 0,
  scale: 10,
  description: 'Mô hình 3D khu phố cổ Hội An, đặt gần Chùa Cầu.',
}

export const VUNG_TAU_CHRIST_CALIBRATION: ModelCalibration = {
  model_name: 'vungtauchrist',
  display_name: 'Tượng Chúa Kitô Vua Vũng Tàu',
  file_url: '/models_3d/VungTauChristDiorama3_web.glb',
  latitude: 10.3264,
  longitude: 107.0845,
  altitude: 0,
  heading: 0,
  pitch: 0,
  roll: 0,
  scale: 42,
  description: 'Mô hình 3D Tượng Chúa Kitô Vua trên Núi Nhỏ, Vũng Tàu.',
}

export const DEFAULT_CALIBRATIONS: Record<string, ModelCalibration> = {
  nhathoducba: DEFAULT_CALIBRATION,
  dinhdoclap: {
    model_name: 'dinhdoclap',
    display_name: 'Dinh Độc Lập',
    file_url: '/models_3d/Independence_Palace.glb',
    latitude: 10.776953,
    longitude: 106.6953188,
    altitude: 0,
    heading: 222.5,
    pitch: 0,
    roll: 0,
    scale: 30,
  },
  chobenthanh: {
    model_name: 'chobenthanh',
    display_name: 'Chợ Bến Thành',
    file_url: '/models_3d/Ben_Thanh_Market.glb',
    latitude: 10.772527,
    longitude: 106.6980182,
    altitude: 0,
    heading: 328.5,
    pitch: 0,
    roll: 0,
    scale: 36.5,
  },
  nhahatthanhpho: {
    model_name: 'nhahatthanhpho',
    display_name: 'Nhà hát Thành phố',
    file_url: '/models_3d/Saigon_Opera_House.glb',
    latitude: 10.776765,
    longitude: 106.7033003,
    altitude: 0,
    heading: 312.5,
    pitch: 0,
    roll: 0,
    scale: 29,
  },
  bitexco: {
    model_name: 'bitexco',
    display_name: 'Bitexco Financial Tower',
    file_url: '/models_3d/Bitexco_Tower.glb',
    latitude: 10.7717,
    longitude: 106.7043455,
    altitude: 0,
    heading: 275.5,
    pitch: 0,
    roll: 0,
    scale: 356,
  },
  landmark81: {
    model_name: 'landmark81',
    display_name: 'Landmark 81',
    file_url: '/models_3d/Landmark_81.glb',
    latitude: 10.795,
    longitude: 106.7218,
    altitude: 0,
    heading: 285,
    pitch: 0,
    roll: 0,
    scale: 504,
  },
  hoian: HOI_AN_CALIBRATION,
  vungtauchrist: VUNG_TAU_CHRIST_CALIBRATION,
}

export function getDefaultCalibration(modelId: string): ModelCalibration {
  return DEFAULT_CALIBRATIONS[modelId] ?? DEFAULT_CALIBRATION
}

/** Older saves used a raw multiplier (e.g. 0.08) — treat anything tiny as invalid. */
export function sanitizeCalibration(raw: Partial<ModelCalibration>, fallback: ModelCalibration): ModelCalibration {
  // Calibration saves may outlive a model file rename. Keep placement edits,
  // but always load the canonical asset configured for the selected model.
  const merged = { ...fallback, ...raw, model_name: fallback.model_name, file_url: fallback.file_url }
  const finite = (v: unknown, d: number) => (typeof v === 'number' && Number.isFinite(v) ? v : d)
  return {
    ...merged,
    model_name: fallback.model_name,
    file_url: fallback.file_url,
    latitude: finite(merged.latitude, fallback.latitude),
    longitude: finite(merged.longitude, fallback.longitude),
    altitude: finite(merged.altitude, 0),
    heading: finite(merged.heading, 0),
    scale: finite(merged.scale, 0) >= 1 ? merged.scale : fallback.scale,
  }
}
