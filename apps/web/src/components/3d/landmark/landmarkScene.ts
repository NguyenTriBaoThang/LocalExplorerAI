import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { TransformControls } from 'three/examples/jsm/controls/TransformControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { createReferencePin, createSatelliteGround } from './satelliteGround'
import type { GeoPoint } from './geo'

export interface LandmarkScene {
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  orbit: OrbitControls
  transform: TransformControls
  frame: (target: THREE.Vector3, height: number, direction?: THREE.Vector3) => void
  dispose: () => void
}

export function createLandmarkScene(container: HTMLElement, origin: GeoPoint): LandmarkScene {
  const width = Math.max(container.clientWidth, 1)
  const height = Math.max(container.clientHeight, 1)

  const scene = new THREE.Scene()
  scene.background = new THREE.Color('#0b1222')
  scene.fog = new THREE.Fog('#0b1222', 600, 1800)

  const camera = new THREE.PerspectiveCamera(45, width / height, 0.5, 5000)
  camera.position.set(90, 70, 130)

  const renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.05
  renderer.domElement.style.display = 'block'
  container.appendChild(renderer.domElement)

  const orbit = new OrbitControls(camera, renderer.domElement)
  orbit.enableDamping = true
  orbit.dampingFactor = 0.08
  orbit.maxPolarAngle = Math.PI / 2 - 0.03
  orbit.minDistance = 8
  orbit.maxDistance = 1200
  orbit.target.set(0, 15, 0)

  const transform = new TransformControls(camera, renderer.domElement)
  transform.setSpace('world')
  transform.setSize(1.1)
  scene.add(transform.getHelper())
  transform.addEventListener('dragging-changed', (event) => { orbit.enabled = !event.value })

  scene.add(new THREE.HemisphereLight('#dbeafe', '#334155', 1.1))
  const sun = new THREE.DirectionalLight('#fff7ed', 2.2)
  sun.position.set(140, 220, 90)
  sun.castShadow = true
  sun.shadow.mapSize.set(2048, 2048)
  Object.assign(sun.shadow.camera, { near: 10, far: 600, left: -150, right: 150, top: 150, bottom: -150 })
  sun.shadow.bias = -0.0004
  scene.add(sun)

  const ground = createSatelliteGround(origin)
  scene.add(ground.group)
  scene.add(createReferencePin())

  let frameId = 0
  const loop = () => {
    frameId = requestAnimationFrame(loop)
    orbit.update()
    renderer.render(scene, camera)
  }
  loop()

  const resizeObserver = new ResizeObserver(() => {
    const w = Math.max(container.clientWidth, 1)
    const h = Math.max(container.clientHeight, 1)
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h)
  })
  resizeObserver.observe(container)

  const frame = (target: THREE.Vector3, objectHeight: number, direction = new THREE.Vector3(0.6, 0.45, 1)) => {
    const distance = Math.max(objectHeight * 2.4, 40)
    orbit.target.copy(target).add(new THREE.Vector3(0, objectHeight * 0.4, 0))
    camera.position.copy(orbit.target).add(direction.clone().normalize().multiplyScalar(distance))
    orbit.update()
  }

  return {
    scene, camera, orbit, transform, frame,
    dispose: () => {
      cancelAnimationFrame(frameId)
      resizeObserver.disconnect()
      transform.detach()
      transform.dispose()
      orbit.dispose()
      ground.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    },
  }
}

export interface LoadedLandmark {
  anchor: THREE.Group
  dispose: () => void
}

/**
 * Loads a GLB and wraps it so that: pivot = centre of footprint at ground level,
 * native height normalised to 1 unit. `anchor.scale` therefore equals real height in metres.
 */
export async function loadLandmarkModel(url: string, onProgress: (pct: number) => void): Promise<LoadedLandmark> {
  const gltf = await new GLTFLoader().loadAsync(url, (evt) => {
    if (evt.total > 0) onProgress(Math.round((evt.loaded / evt.total) * 100))
  })
  const raw = gltf.scene
  raw.traverse((child) => {
    const mesh = child as THREE.Mesh
    if (!mesh.isMesh) return
    mesh.castShadow = true
    mesh.receiveShadow = true
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
    materials.forEach((m) => { if (m) m.side = THREE.DoubleSide })
  })

  const box = new THREE.Box3().setFromObject(raw)
  const size = box.getSize(new THREE.Vector3())
  const center = box.getCenter(new THREE.Vector3())
  if (!Number.isFinite(size.y) || size.y <= 0) throw new Error('Mô hình rỗng hoặc không có hình học hợp lệ.')

  raw.position.set(-center.x, -box.min.y, -center.z)
  const normalizer = new THREE.Group()
  normalizer.scale.setScalar(1 / size.y)
  normalizer.add(raw)
  const anchor = new THREE.Group()
  anchor.name = 'landmark-anchor'
  anchor.add(normalizer)

  return {
    anchor,
    dispose: () => {
      anchor.removeFromParent()
      raw.traverse((child) => {
        const mesh = child as THREE.Mesh
        if (!mesh.isMesh) return
        mesh.geometry?.dispose()
        const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
        materials.forEach((m) => {
          Object.values(m ?? {}).forEach((v) => { if (v instanceof THREE.Texture) v.dispose() })
          m?.dispose()
        })
      })
    },
  }
}
