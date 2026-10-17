import * as THREE from 'three'
import goongjs from '@goongmaps/goong-js'
import { loadLandmarkModel } from '../3d/landmark/landmarkScene'
import type { ModelCalibration } from '../3d/landmark/types'

export function createLandmarkLayer(id: string, calibrations: ModelCalibration[]) {
  let removed = false
  let renderer: THREE.WebGLRenderer
  let map: any
  const camera = new THREE.Camera()
  const models: { scene: THREE.Scene; transform: THREE.Matrix4; dispose: () => void }[] = []
  return {
    id, type: 'custom' as const, renderingMode: '3d' as const,
    onAdd(m: any, gl: WebGLRenderingContext) {
      map = m
      renderer = new THREE.WebGLRenderer({ canvas: m.getCanvas(), context: gl, antialias: true })
      renderer.autoClear = false
      for (const cal of calibrations) {
        void loadLandmarkModel(cal.file_url, () => {}).then(model => {
          if (removed) { model.dispose(); return }
          const scene = new THREE.Scene()
          scene.add(new THREE.HemisphereLight(0xffffff, 0x64748b, 2.5))
          const sun = new THREE.DirectionalLight(0xffffff, 2); sun.position.set(40, 80, 50); scene.add(sun)
          scene.add(model.anchor)
          const c = goongjs.MercatorCoordinate.fromLngLat([cal.longitude, cal.latitude], cal.altitude)
          const scale = c.meterInMercatorCoordinateUnits() * cal.scale
          const transform = new THREE.Matrix4().makeTranslation(c.x, c.y, c.z)
            .scale(new THREE.Vector3(scale, -scale, scale))
            .multiply(new THREE.Matrix4().makeRotationX(Math.PI / 2))
            .multiply(new THREE.Matrix4().makeRotationY(-cal.heading * Math.PI / 180))
            .multiply(new THREE.Matrix4().makeRotationX(cal.pitch * Math.PI / 180))
            .multiply(new THREE.Matrix4().makeRotationZ(cal.roll * Math.PI / 180))
          models.push({ scene, transform, dispose: model.dispose }); map.triggerRepaint()
        }).catch(() => console.warn('Không tải được landmark', cal.model_name))
      }
    },
    render(_gl: WebGLRenderingContext, matrix: number[]) {
      for (const model of models) {
        camera.projectionMatrix.fromArray(matrix).multiply(model.transform)
        camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert()
        renderer.resetState(); renderer.render(model.scene, camera)
      }
    },
    onRemove() { removed = true; models.forEach(m => m.dispose()); renderer?.dispose() },
  }
}
