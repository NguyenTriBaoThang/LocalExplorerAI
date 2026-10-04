/**
 * Geo helpers for the 3D landmark scene.
 * Scene convention: +X = East, +Y = Up, -Z = North, 1 unit = 1 metre.
 */

export interface GeoPoint {
  lat: number
  lng: number
}

const METERS_PER_DEG_LAT = 110_574
const EARTH_CIRCUMFERENCE_M = 40_075_016.686
const TILE_SIZE_PX = 256

export function metersPerDegLng(lat: number): number {
  return 111_320 * Math.cos((lat * Math.PI) / 180)
}

export function geoToLocal(lat: number, lng: number, alt: number, origin: GeoPoint) {
  return {
    x: (lng - origin.lng) * metersPerDegLng(origin.lat),
    y: alt,
    z: -(lat - origin.lat) * METERS_PER_DEG_LAT,
  }
}

export function localToGeo(x: number, y: number, z: number, origin: GeoPoint) {
  return {
    lat: origin.lat - z / METERS_PER_DEG_LAT,
    lng: origin.lng + x / metersPerDegLng(origin.lat),
    alt: y,
  }
}

/** Move a coordinate by metres towards East / North. */
export function offsetGeo(point: GeoPoint, eastM: number, northM: number): GeoPoint {
  return {
    lat: point.lat + northM / METERS_PER_DEG_LAT,
    lng: point.lng + eastM / metersPerDegLng(point.lat),
  }
}

export function normalizeHeading(deg: number): number {
  const wrapped = ((deg % 360) + 360) % 360
  return wrapped >= 359.95 ? 0 : wrapped
}

/** Compass heading (clockwise from North) → Three.js Y rotation (counter-clockwise). */
export function headingToRotationY(headingDeg: number): number {
  return (-headingDeg * Math.PI) / 180
}

export function rotationYToHeading(rotationY: number): number {
  return normalizeHeading((-rotationY * 180) / Math.PI)
}

/** Web-Mercator global pixel coordinates at a given zoom. */
export function geoToWorldPixel(lat: number, lng: number, zoom: number) {
  const worldSize = TILE_SIZE_PX * 2 ** zoom
  const latRad = (lat * Math.PI) / 180
  return {
    x: ((lng + 180) / 360) * worldSize,
    y: ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * worldSize,
  }
}

export function metersPerPixel(lat: number, zoom: number): number {
  return (EARTH_CIRCUMFERENCE_M * Math.cos((lat * Math.PI) / 180)) / (TILE_SIZE_PX * 2 ** zoom)
}

export const TILE_PX = TILE_SIZE_PX
