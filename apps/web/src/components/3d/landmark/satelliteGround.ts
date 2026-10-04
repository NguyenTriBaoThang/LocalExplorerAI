import * as THREE from 'three'
import { TILE_PX, geoToWorldPixel, metersPerPixel, type GeoPoint } from './geo'

const IMAGERY_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile'

export interface SatelliteGround {
  group: THREE.Group
  dispose: () => void
}

/**
 * Builds a ground plane textured with real satellite tiles, georeferenced so that
 * `origin` sits exactly at scene (0, 0, 0). This is the visual reference admins
 * use to line the model up with the real footprint.
 */
export function createSatelliteGround(origin: GeoPoint, zoom = 18, grid = 7): SatelliteGround {
  const group = new THREE.Group()
  const half = Math.floor(grid / 2)
  const mpp = metersPerPixel(origin.lat, zoom)
  const originPx = geoToWorldPixel(origin.lat, origin.lng, zoom)
  const tileX0 = Math.floor(originPx.x / TILE_PX) - half
  const tileY0 = Math.floor(originPx.y / TILE_PX) - half
  const canvasPx = grid * TILE_PX

  const canvas = document.createElement('canvas')
  canvas.width = canvasPx
  canvas.height = canvasPx
  const ctx = canvas.getContext('2d')
  if (ctx) {
    ctx.fillStyle = '#1e293b'
    ctx.fillRect(0, 0, canvasPx, canvasPx)
  }

  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 8

  const sizeM = canvasPx * mpp
  const geometry = new THREE.PlaneGeometry(sizeM, sizeM)
  geometry.rotateX(-Math.PI / 2)
  const material = new THREE.MeshStandardMaterial({ map: texture, roughness: 1, metalness: 0 })
  const imagery = new THREE.Mesh(geometry, material)
  imagery.receiveShadow = true
  // Canvas centre vs. origin pixel → shift plane so origin lands on (0,0,0).
  const originInCanvasX = originPx.x - tileX0 * TILE_PX
  const originInCanvasY = originPx.y - tileY0 * TILE_PX
  imagery.position.set((canvasPx / 2 - originInCanvasX) * mpp, 0, (canvasPx / 2 - originInCanvasY) * mpp)
  group.add(imagery)

  // Wide dark base so the horizon never shows a hard edge.
  const baseGeometry = new THREE.CircleGeometry(sizeM * 3, 48)
  baseGeometry.rotateX(-Math.PI / 2)
  const baseMaterial = new THREE.MeshStandardMaterial({ color: '#0f172a', roughness: 1 })
  const base = new THREE.Mesh(baseGeometry, baseMaterial)
  base.position.y = -0.05
  base.receiveShadow = true
  group.add(base)

  let disposed = false
  const images: HTMLImageElement[] = []
  for (let dy = 0; dy < grid; dy += 1) {
    for (let dx = 0; dx < grid; dx += 1) {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => {
        if (disposed || !ctx) return
        ctx.drawImage(img, dx * TILE_PX, dy * TILE_PX)
        texture.needsUpdate = true
      }
      img.src = `${IMAGERY_URL}/${zoom}/${tileY0 + dy}/${tileX0 + dx}`
      images.push(img)
    }
  }

  return {
    group,
    dispose: () => {
      disposed = true
      images.forEach((img) => { img.onload = null; img.src = '' })
      texture.dispose()
      geometry.dispose()
      material.dispose()
      baseGeometry.dispose()
      baseMaterial.dispose()
    },
  }
}

/** Red pin marking the official POI coordinate (scene origin). */
export function createReferencePin(): THREE.Group {
  const pin = new THREE.Group()
  const material = new THREE.MeshBasicMaterial({ color: '#f43f5e', depthTest: false, transparent: true, opacity: 0.9 })
  const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.25, 8, 8), material)
  stem.position.y = 4
  const head = new THREE.Mesh(new THREE.SphereGeometry(1.2, 16, 16), material)
  head.position.y = 9
  const ring = new THREE.Mesh(new THREE.RingGeometry(2.2, 2.8, 40), material)
  ring.rotation.x = -Math.PI / 2
  ring.position.y = 0.1
  pin.add(stem, head, ring)
  pin.renderOrder = 999
  return pin
}
