import { ModelLocationSearch } from './ModelLocationSearch'
import { LandmarkDiscoveryPanel } from './LandmarkDiscoveryPanel'
import { useCallback, useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
// @ts-expect-error - @goongmaps/goong-js does not have official typescript definitions
import goongjs from '@goongmaps/goong-js'
import '@goongmaps/goong-js/dist/goong-js.css'
import axios from 'axios'
import {
  AlertCircle,
  Compass,
  Layers,
  RotateCcw,
  Save,
  Settings,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Crosshair,
} from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../auth'
import {
  getDefaultCalibration,
  NOTRE_DAME_ORIGIN,
  sanitizeCalibration,
  type ModelCalibration
} from './landmark/types'
import { offsetGeo } from './landmark/geo'

export type { ModelCalibration } from './landmark/types'

const GOONG_MAPTILES_KEY =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_GOONG_MAPTILES_KEY ||
  '7LMSzHRsHaOKryYjpUQ29NGQAcrSLFw8ho3tcpXU'

const GOONG_STYLES = {
  streets: 'https://tiles.goong.io/assets/goong_map_web.json',
  dark: 'https://tiles.goong.io/assets/goong_map_dark.json',
}

const round = (v: number, digits: number) => Number(v.toFixed(digits))

function toNumber(raw: string, fallback: number): number {
  const value = Number.parseFloat(raw)
  return Number.isFinite(value) ? value : fallback
}

function createProceduralCathedralModel(): THREE.Group {
  const root = new THREE.Group()

  // Authentic Toulouse terracotta red brick material
  const brickMaterial = new THREE.MeshStandardMaterial({
    color: 0xc84d32,
    roughness: 0.75,
    metalness: 0.08,
  })

  // Off-white stone trims and Romanesque arches
  const stoneMaterial = new THREE.MeshStandardMaterial({
    color: 0xe2dcd0,
    roughness: 0.82,
    metalness: 0.05,
  })

  // Zinc-iron slate gray roof spires
  const roofMaterial = new THREE.MeshStandardMaterial({
    color: 0x334155,
    roughness: 0.45,
    metalness: 0.35,
  })

  // Gold cross material
  const goldMaterial = new THREE.MeshStandardMaterial({
    color: 0xf59e0b,
    roughness: 0.3,
    metalness: 0.8,
  })

  // 1. Main Nave Body (Thân thánh đường chính)
  const naveGeo = new THREE.BoxGeometry(22, 17, 56)
  const nave = new THREE.Mesh(naveGeo, brickMaterial)
  nave.position.set(0, 8.5, 6)
  nave.castShadow = true
  nave.receiveShadow = true
  root.add(nave)

  // 1.1 Main Sloped Roof (Mái dốc chính)
  const roofGeo = new THREE.ConeGeometry(16, 7.5, 4)
  const roof = new THREE.Mesh(roofGeo, roofMaterial)
  roof.rotation.y = Math.PI / 4
  roof.scale.set(1, 1, 3.4)
  roof.position.set(0, 20.5, 6)
  roof.castShadow = true
  root.add(roof)

  // 2. Twin Bell Towers (2 Tháp chuông đôi phía trước cao 60.5m)
  const towerGeo = new THREE.BoxGeometry(7.8, 36, 7.8)
  const spireGeo = new THREE.ConeGeometry(5.6, 24, 8)

  // Left Bell Tower
  const leftTower = new THREE.Mesh(towerGeo, brickMaterial)
  leftTower.position.set(-8, 18, -22)
  leftTower.castShadow = true
  leftTower.receiveShadow = true
  root.add(leftTower)

  const leftSpire = new THREE.Mesh(spireGeo, roofMaterial)
  leftSpire.position.set(-8, 48, -22)
  leftSpire.castShadow = true
  root.add(leftSpire)

  // Right Bell Tower
  const rightTower = new THREE.Mesh(towerGeo, brickMaterial)
  rightTower.position.set(8, 18, -22)
  rightTower.castShadow = true
  rightTower.receiveShadow = true
  root.add(rightTower)

  const rightSpire = new THREE.Mesh(spireGeo, roofMaterial)
  rightSpire.position.set(8, 48, -22)
  rightSpire.castShadow = true
  root.add(rightSpire)

  // 3. Spire Crosses (Thánh giá đỉnh tháp)
  const crossGeo = new THREE.BoxGeometry(0.5, 3.2, 0.5)
  const crossBarGeo = new THREE.BoxGeometry(2, 0.5, 0.5)

  const leftCross1 = new THREE.Mesh(crossGeo, goldMaterial)
  leftCross1.position.set(-8, 61, -22)
  const leftCross2 = new THREE.Mesh(crossBarGeo, goldMaterial)
  leftCross2.position.set(-8, 61.4, -22)
  root.add(leftCross1, leftCross2)

  const rightCross1 = new THREE.Mesh(crossGeo, goldMaterial)
  rightCross1.position.set(8, 61, -22)
  const rightCross2 = new THREE.Mesh(crossBarGeo, goldMaterial)
  rightCross2.position.set(8, 61.4, -22)
  root.add(rightCross1, rightCross2)

  // 4. Central Front Rose Window (Cửa sổ hoa hồng mặt tiền)
  const roseGeo = new THREE.CylinderGeometry(3.6, 3.6, 0.8, 24)
  const rose = new THREE.Mesh(roseGeo, stoneMaterial)
  rose.rotation.x = Math.PI / 2
  rose.position.set(0, 16.5, -22.2)
  root.add(rose)

  // 5. Triple Front Portals (3 Cổng vòm mặt tiền)
  const portalGeo = new THREE.CylinderGeometry(2.4, 2.4, 4.5, 16, 1, false, 0, Math.PI)
  const portal = new THREE.Mesh(portalGeo, stoneMaterial)
  portal.rotation.z = Math.PI / 2
  portal.position.set(0, 3.5, -22.4)
  root.add(portal)

  return root
}

export function Map3DLandmarkViewer({
  modelId = 'nhathoducba',
  previewJobId,
  defaultCalibration: providedCalibration,
  className = '',
}: {
  modelId?: string
  previewJobId?: string
  defaultCalibration?: ModelCalibration
  className?: string
}) {
  const { user } = useAuth()
  const canEdit =
    user?.role === 'admin' ||
    !user ||
    (import.meta as unknown as { env?: Record<string, unknown> }).env?.DEV === true

  const fallbackCalibration = providedCalibration ?? getDefaultCalibration(modelId)

  const mapContainerRef = useRef<HTMLDivElement>(null)
  const threeCanvasRef = useRef<HTMLCanvasElement>(null)

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.Camera | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const modelAnchorRef = useRef<THREE.Group | null>(null)
  const modelRaycasterRef = useRef(new THREE.Raycaster())
  const calibrationRef = useRef<ModelCalibration>(fallbackCalibration)

  const [calibration, setCalibration] = useState<ModelCalibration>(fallbackCalibration)
  const [saved, setSaved] = useState<ModelCalibration>(fallbackCalibration)
  const [calibrationReady, setCalibrationReady] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingProgress, setLoadingProgress] = useState(0)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [editMode, setEditMode] = useState(false)
  const [nudgeStep, setNudgeStep] = useState(1)
  const [styleMode, setStyleMode] = useState<'streets' | 'dark'>('streets')
  const [saving, setSaving] = useState(false)
  const [statusMessage, setStatusMessage] = useState<{ kind: 'success' | 'error' | 'info'; text: string } | null>(null)
  const [modelCardVisible, setModelCardVisible] = useState(false)

  useEffect(() => {
    if (!modelCardVisible || loading) return
    const originals = new Map<THREE.MeshStandardMaterial, { color: THREE.Color; intensity: number }>()
    modelAnchorRef.current?.traverse(node => {
      if (!(node instanceof THREE.Mesh)) return
      const materials = Array.isArray(node.material) ? node.material : [node.material]
      for (const material of materials) {
        if (!(material instanceof THREE.MeshStandardMaterial) || originals.has(material)) continue
        originals.set(material, { color: material.emissive.clone(), intensity: material.emissiveIntensity })
        material.emissive.set('#b88a4c')
        material.emissiveIntensity = 0.12
      }
    })
    mapRef.current?.triggerRepaint()
    return () => {
      originals.forEach((value, material) => { material.emissive.copy(value.color); material.emissiveIntensity = value.intensity })
      mapRef.current?.triggerRepaint()
    }
  }, [modelCardVisible, loading, modelId])

  calibrationRef.current = calibration
  const dirty = JSON.stringify(calibration) !== JSON.stringify(saved)

  // 1. Fetch initial calibration from backend API
  useEffect(() => {
    let alive = true
    setCalibrationReady(false)
    setCalibration(fallbackCalibration)
    setSaved(fallbackCalibration)
    api
      .get(previewJobId ? `/admin/meshy/jobs/${previewJobId}/calibration` : `/models-3d/calibration/${modelId}`)
      .then(({ data }) => {
        if (!alive) return
        const next = sanitizeCalibration(data, fallbackCalibration)
        setCalibration(next)
        setSaved(next)
      })
      .catch(() => {
        if (alive) {
          const cached = localStorage.getItem(`calib_${modelId}`)
          if (cached) {
            try {
              const parsed = sanitizeCalibration(JSON.parse(cached), fallbackCalibration)
              setCalibration(parsed)
              setSaved(parsed)
            } catch {}
          }
        }
      })
      .finally(() => {
        if (alive) setCalibrationReady(true)
      })
    return () => {
      alive = false
    }
  }, [modelId, fallbackCalibration])

  // 2. Initialize the independent Three.js overlay. Goong JS 1.0.9 creates a
  // WebGL 1 map context, while current Three.js requires WebGL 2.
  useEffect(() => {
    const canvas = threeCanvasRef.current
    if (!canvas) return
    const renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: 'high-performance',
    })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    // CSS owns layout; writing fixed inline pixels here breaks map alignment
    // after the viewport or parent resizes.
    renderer.setSize(canvas.clientWidth || window.innerWidth, canvas.clientHeight || window.innerHeight, false)
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.15
    rendererRef.current = renderer

    const scene = new THREE.Scene()
    sceneRef.current = scene

    const camera = new THREE.Camera()
    cameraRef.current = camera

    // Atmospheric lighting for Goong Map integration
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.3)
    scene.add(ambientLight)

    const hemiLight = new THREE.HemisphereLight(0xdbeafe, 0x334155, 1.2)
    scene.add(hemiLight)

    const sunLight = new THREE.DirectionalLight(0xfff7ed, 2.2)
    sunLight.position.set(80, 160, 100).normalize()
    scene.add(sunLight)

    const fillLight = new THREE.DirectionalLight(0x38bdf8, 0.9)
    fillLight.position.set(-80, 100, -80).normalize()
    scene.add(fillLight)

    return () => {
      renderer.dispose()
      rendererRef.current = null
      sceneRef.current = null
      cameraRef.current = null
    }
  }, [])

  // 3. Render Three.js overlay synchronized with Goong Map
  const renderFrame = useCallback(() => {
    const map = mapRef.current
    const scene = sceneRef.current
    const camera = cameraRef.current
    const renderer = rendererRef.current
    const anchor = modelAnchorRef.current
    const cal = calibrationRef.current

    if (!map || !map.transform || !scene || !camera || !renderer || !anchor) return

    // Convert GPS (lng, lat, alt) to Goong Mercator Coordinates
    const coord = goongjs.MercatorCoordinate.fromLngLat(
      [cal.longitude, cal.latitude],
      cal.altitude || 0
    )

    const meterUnits = coord.meterInMercatorCoordinateUnits()
    const modelScale = meterUnits * (cal.scale || 58.0)

    const rotationX = new THREE.Matrix4().makeRotationAxis(new THREE.Vector3(1, 0, 0), Math.PI / 2)
    const rotationY = new THREE.Matrix4().makeRotationAxis(
      new THREE.Vector3(0, 1, 0),
      (-cal.heading * Math.PI) / 180
    )

    const m = new THREE.Matrix4().fromArray(map.transform.customLayerMatrix())
    const l = new THREE.Matrix4()
      .makeTranslation(coord.x, coord.y, coord.z)
      .scale(new THREE.Vector3(modelScale, -modelScale, modelScale))
      .multiply(rotationX)
      .multiply(rotationY)

    camera.projectionMatrix = m.multiply(l)
    camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert()
    renderer.resetState()
    renderer.render(scene, camera)
  }, [])

  // 4. Initialize Goong Map
  useEffect(() => {
    const container = mapContainerRef.current
    if (!container || !calibrationReady) return

    goongjs.accessToken = GOONG_MAPTILES_KEY

    const initialLat = calibration.latitude || NOTRE_DAME_ORIGIN.lat
    const initialLng = calibration.longitude || NOTRE_DAME_ORIGIN.lng

    const map = new goongjs.Map({
      container,
      style: GOONG_STYLES[styleMode],
      center: [initialLng, initialLat],
      zoom: calibration.scale > 350 ? 14.8 : calibration.scale > 150 ? 15.8 : 17.6,
      pitch: 60,
      bearing: 0,
    })
    mapRef.current = map

    map.on('render', renderFrame)
    map.on('move', renderFrame)
    map.on('zoom', renderFrame)
    map.on('pitch', renderFrame)
    map.on('rotate', renderFrame)
    const handleMapClick = (event: { point?: { x: number; y: number } }) => {
      const model = modelAnchorRef.current
      const camera = cameraRef.current
      const canvas = threeCanvasRef.current
      if (!model || !camera || !canvas || !event.point) {
        setModelCardVisible(false)
        return
      }

      const bounds = canvas.getBoundingClientRect()
      const pointer = new THREE.Vector2(
        (event.point.x / bounds.width) * 2 - 1,
        -(event.point.y / bounds.height) * 2 + 1,
      )
      const raycaster = modelRaycasterRef.current
      // The overlay uses a base THREE.Camera with Goong's combined view/model
      // matrix, so build the ray from its inverse clip matrix directly.
      const nearPoint = new THREE.Vector3(pointer.x, pointer.y, -1).applyMatrix4(camera.projectionMatrixInverse)
      const farPoint = new THREE.Vector3(pointer.x, pointer.y, 1).applyMatrix4(camera.projectionMatrixInverse)
      raycaster.set(nearPoint, farPoint.sub(nearPoint).normalize())
      const hit = raycaster.intersectObject(model, true).length > 0
      setModelCardVisible(hit)
    }
    map.on('click', handleMapClick)
    const resizeOverlay = () => {
      const canvas = threeCanvasRef.current
      const renderer = rendererRef.current
      if (!canvas || !renderer) return
      const { width, height } = canvas.getBoundingClientRect()
      renderer.setSize(width, height, false)
      map.resize()
      renderFrame()
    }
    const resizeObserver = new ResizeObserver(resizeOverlay)
    resizeObserver.observe(container)

    return () => {
      resizeObserver.disconnect()
      map.off('render', renderFrame)
      map.off('move', renderFrame)
      map.off('zoom', renderFrame)
      map.off('pitch', renderFrame)
      map.off('rotate', renderFrame)
      map.off('click', handleMapClick)
      map.remove()
      mapRef.current = null
    }
  }, [calibrationReady, styleMode, renderFrame])

  // 5. Load 3D GLB Model of Notre Dame Cathedral
  useEffect(() => {
    const scene = sceneRef.current
    if (!scene || !calibrationReady) return

    let cancelled = false
    setLoading(true)
    setLoadError(null)
    setLoadingProgress(0)

    const loader = new GLTFLoader()
    loader.setWithCredentials(true)
    loader.load(
      calibrationRef.current.file_url,
      (gltf) => {
        if (cancelled) return
        const raw = gltf.scene

        raw.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            const mesh = child as THREE.Mesh
            mesh.castShadow = true
            mesh.receiveShadow = true
            const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
            materials.forEach((m) => {
              if (m) {
                m.side = THREE.DoubleSide
                const stdMat = m as THREE.MeshStandardMaterial
                if (stdMat.roughness !== undefined) {
                  stdMat.roughness = Math.min(stdMat.roughness || 0.7, 0.85)
                  stdMat.metalness = Math.max(stdMat.metalness || 0.05, 0.1)
                }
              }
            })
          }
        })

        // Calculate bounding box and normalize height to 1 unit
        const box = new THREE.Box3().setFromObject(raw)
        const size = box.getSize(new THREE.Vector3())
        const center = box.getCenter(new THREE.Vector3())

        if (size.y > 0) {
          raw.position.set(-center.x, -box.min.y, -center.z)
          const normalizer = new THREE.Group()
          normalizer.scale.setScalar(1 / size.y)
          normalizer.add(raw)

          const anchor = new THREE.Group()
          anchor.add(normalizer)

          // Remove any previous model
          if (modelAnchorRef.current) {
            scene.remove(modelAnchorRef.current)
          }

          modelAnchorRef.current = anchor
          scene.add(anchor)
        }

        setLoading(false)
        if (previewJobId) void api.post(`/admin/meshy/jobs/${previewJobId}/previewed`).catch(() => {})
        mapRef.current?.triggerRepaint()
      },
      (xhr) => {
        if (xhr.total > 0) {
          setLoadingProgress(Math.round((xhr.loaded / xhr.total) * 100))
        } else {
          setLoadingProgress(Math.min(95, Math.round(xhr.loaded / (1024 * 1024))))
        }
      },
      (err) => {
        if (cancelled) return
        console.warn('3D GLB model file could not be loaded:', err)
        if (modelId !== 'nhathoducba') {
          setLoading(false)
          setLoadError('Không tải được mô hình của địa danh này. Hãy kiểm tra tệp GLB; hệ thống không thay bằng mô hình của địa danh khác.')
          return
        }
        const raw = createProceduralCathedralModel()
        const box = new THREE.Box3().setFromObject(raw)
        const size = box.getSize(new THREE.Vector3())
        const center = box.getCenter(new THREE.Vector3())

        if (size.y > 0) {
          raw.position.set(-center.x, -box.min.y, -center.z)
          const normalizer = new THREE.Group()
          normalizer.scale.setScalar(1 / size.y)
          normalizer.add(raw)

          const anchor = new THREE.Group()
          anchor.add(normalizer)

          if (modelAnchorRef.current) {
            scene.remove(modelAnchorRef.current)
          }

          modelAnchorRef.current = anchor
          scene.add(anchor)
        }

        setLoading(false)
        setLoadError('Không tải được tệp GLB. Đang hiển thị hình học minh họa Nhà thờ Đức Bà, chưa được kiểm chứng về kiến trúc.')
        mapRef.current?.triggerRepaint()
      }
    )

    return () => {
      cancelled = true
    }
  }, [calibrationReady, renderFrame])

  // Ask Goong to render another frame after calibration changes.
  useEffect(() => {
    mapRef.current?.triggerRepaint()
  }, [calibration, renderFrame])

  const patch = useCallback((p: Partial<ModelCalibration>) => {
    setCalibration((prev) => ({ ...prev, ...p }))
  }, [])

  // Nudge model by meters East/North
  const nudge = (eastM: number, northM: number) => {
    const next = offsetGeo({ lat: calibration.latitude, lng: calibration.longitude }, eastM, northM)
    patch({
      latitude: round(next.lat, 7),
      longitude: round(next.lng, 7),
    })
  }

  // Save to backend API & localStorage
  const handleSave = async () => {
    setSaving(true)
    setStatusMessage(null)
    try {
      const payload = {
        latitude: calibration.latitude,
        longitude: calibration.longitude,
        altitude: calibration.altitude,
        heading: calibration.heading,
        pitch: calibration.pitch,
        roll: calibration.roll,
        scale: calibration.scale,
      }

      const { data } = await api.post(previewJobId ? `/admin/meshy/jobs/${previewJobId}/calibration` : `/models-3d/calibration/${modelId}`, payload)
      const next = sanitizeCalibration(data.calibration, calibration)
      setCalibration(next)
      setSaved(next)
      localStorage.setItem(`calib_${modelId}`, JSON.stringify(next))
      setStatusMessage({
        kind: 'success',
        text: 'Đã lưu tọa độ & góc xoay chuẩn vào hệ thống Goong Map thành công!',
      })
    } catch (err: unknown) {
      localStorage.setItem(`calib_${modelId}`, JSON.stringify(calibration))
      setSaved(calibration)
      if (axios.isAxiosError(err)) {
        if (err.response?.status === 401) {
          setStatusMessage({
            kind: 'error',
            text: 'Cần đăng nhập tài khoản Quản trị viên (Admin) để lưu vĩnh viễn trên máy chủ.',
          })
          return
        }
        if (err.response?.status === 403) {
          setStatusMessage({ kind: 'error', text: 'Chỉ tài khoản admin mới có quyền lưu tọa độ.' })
          return
        }
      }
      setStatusMessage({
        kind: 'info',
        text: 'Đã lưu tọa độ vào bộ nhớ cục bộ trình duyệt.',
      })
    } finally {
      setSaving(false)
    }
  }

  // Camera Presets using Goong Map flyTo
  const setCameraPreset = (preset: 'front' | 'top' | 'park' | 'cinematic') => {
    const map = mapRef.current
    if (!map) return

    const lat = calibration.latitude
    const lng = calibration.longitude
    const zoomForScale = (zoom: number) => Math.max(13.8, zoom - Math.max(0, Math.log2(calibration.scale / 77.5)))

    switch (preset) {
      case 'front': // Mặt tiền chính diện nhìn từ Công xã Paris
        map.flyTo({
          center: [lng, lat - 0.00075],
          zoom: zoomForScale(17.8),
          pitch: 60,
          bearing: 0,
          duration: 1500,
        })
        break
      case 'top': // Góc nhìn trên cao (Fly-over)
        map.flyTo({
          center: [lng, lat],
          zoom: zoomForScale(17.2),
          pitch: 15,
          bearing: 0,
          duration: 1500,
        })
        break
      case 'park': // Góc nhìn từ công viên Bưu điện / Nhà hát
        map.flyTo({
          center: [lng - 0.0009, lat - 0.0006],
          zoom: zoomForScale(17.8),
          pitch: 65,
          bearing: 45,
          duration: 1500,
        })
        break
      case 'cinematic': // Góc nhìn 3D nghệ thuật
        map.flyTo({
          center: [lng + 0.0008, lat + 0.0008],
          zoom: zoomForScale(17.9),
          pitch: 62,
          bearing: -135,
          duration: 1500,
        })
        break
    }
  }

  const btnNudge = 'px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-200 font-bold transition-colors'

  return (
    <div className={`relative w-full h-full min-h-[640px] bg-slate-950 overflow-hidden select-none ${className}`}>
      {/* Goong Map Base Container */}
      <div
        ref={mapContainerRef}
        className="absolute inset-0 w-full h-full"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      />

      {/* Three.js WebGL2 overlay, aligned to Goong's camera matrix */}
      <canvas ref={threeCanvasRef} className="absolute inset-0 w-full h-full pointer-events-none" style={{ width: '100%', height: '100%' }} />

      {/* Loading Overlay */}
      {loading && !loadError && (
        <div className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-sm pointer-events-none">
          <div className="w-14 h-14 border-4 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin mb-4" />
          <h3 className="text-base font-bold text-white mb-1">
            Đang tải mô hình 3D {calibration.display_name}...
          </h3>
          <p className="text-xs text-slate-400 mb-3">
            {calibrationReady
              ? 'Đang tải cấu trúc 3D & khớp tọa độ Goong Map Sài Gòn'
              : 'Đang đọc tọa độ đã lưu...'}
          </p>
          <div className="w-64 h-2 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-cyan-400 transition-all duration-300"
              style={{ width: `${Math.max(5, loadingProgress)}%` }}
            />
          </div>
          <span className="text-xs text-slate-500 mt-2">{loadingProgress}% hoàn tất</span>
        </div>
      )}

      {/* Error Banner */}
      {loadError && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-40 max-w-xl bg-rose-950/90 border border-rose-500/40 text-rose-200 px-5 py-3 rounded-xl shadow-2xl flex items-start gap-3">
          <AlertCircle size={20} className="text-rose-400 shrink-0 mt-0.5" />
          <span className="text-sm">{loadError}</span>
        </div>
      )}

      {/* Top Header Badge & Camera Controls */}
      <div className="absolute top-4 left-4 z-20 flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-2 bg-slate-900/90 border border-slate-700/60 backdrop-blur-md px-3.5 py-1.5 rounded-xl shadow-xl">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs font-bold tracking-wider text-slate-200 uppercase">
            GOONG MAPS 3D · {calibration.display_name.toUpperCase()}
          </span>
        </div>

        {/* Camera Preset Quick Buttons */}
        <div className="flex items-center gap-1 bg-slate-900/85 border border-slate-800 backdrop-blur-md p-1 rounded-xl shadow">
          <button
            type="button"
            onClick={() => setCameraPreset('front')}
            className="px-2.5 py-1 text-xs text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg transition-all"
            title="Góc nhìn mặt tiền chính diện từ Công xã Paris"
          >
            Mặt tiền
          </button>
          <button
            type="button"
            onClick={() => setCameraPreset('top')}
            className="px-2.5 py-1 text-xs text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg transition-all"
            title="Góc nhìn trên cao bao quát Sài Gòn"
          >
            Fly-over
          </button>
          <button
            type="button"
            onClick={() => setCameraPreset('park')}
            className="px-2.5 py-1 text-xs text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg transition-all"
            title="Góc nhìn từ công viên Bưu điện / Nhà hát"
          >
            Công viên
          </button>
          <button
            type="button"
            onClick={() => setCameraPreset('cinematic')}
            className="px-2.5 py-1 text-xs text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg transition-all"
            title="Góc nhìn 3D nghệ thuật"
          >
            Cinematic
          </button>
        </div>

        {/* Layer style toggle */}
        <button
          type="button"
          onClick={() => setStyleMode((m) => (m === 'streets' ? 'dark' : 'streets'))}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900/85 border border-slate-800 backdrop-blur-md rounded-xl text-xs text-slate-300 hover:text-white transition-all"
          title="Chuyển đổi giao diện bản đồ Goong Sáng / Tối"
        >
          <Layers size={13} />
          <span>{styleMode === 'streets' ? 'Goong Sáng' : 'Goong Đêm'}</span>
        </button>
      </div>

      {/* Top-Right Admin HUD Toggle */}
      {canEdit && (
        <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
          <button
            type="button"
            onClick={() => setEditMode((v) => !v)}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold backdrop-blur-md border transition-all ${
              editMode
                ? 'bg-amber-500/20 border-amber-500/50 text-amber-300 shadow-lg shadow-amber-500/10'
                : 'bg-slate-900/80 border-slate-700/60 text-slate-300 hover:text-white'
            }`}
          >
            <Settings size={14} />
            <span>{editMode ? 'Đang Căn Chỉnh (Admin)' : 'Căn Chỉnh Vị Trí'}</span>
          </button>
        </div>
      )}

      {/* Admin 3D Floating Calibrator HUD Panel */}
      {canEdit && editMode && (
        <div className="absolute bottom-4 right-4 z-20 w-80 sm:w-96 max-h-[82vh] overflow-y-auto bg-slate-900/95 border border-slate-700/80 backdrop-blur-xl p-4 rounded-2xl shadow-2xl text-slate-200 text-xs">
          <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <Compass size={18} className="text-amber-400" />
              <strong className="text-sm font-bold text-white">Hiệu Chỉnh Tọa Độ 3D</strong>
            </div>
            <span
              className={`text-xs px-2 py-0.5 rounded font-mono font-bold ${
                dirty ? 'bg-amber-500/20 text-amber-300' : 'bg-emerald-500/20 text-emerald-300'
              }`}
            >
              {dirty ? 'CHƯA LƯU' : 'ĐÃ LƯU'}
            </span>
          </div>

          <p className="text-xs text-slate-400 mb-3">
            Dùng các nút điều hướng bên dưới để khớp mô hình 3D với mặt đường và vị trí thực tế trên Goong Map.
          </p>

          {/* Quick Nudge Matrix */}
          <div className="mb-4">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-slate-400">Dịch chuyển nhanh</span>
              <select
                value={nudgeStep}
                onChange={(e) => setNudgeStep(Number(e.target.value))}
                className="bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-white"
              >
                {[0.5, 1, 2, 5, 10].map((m) => (
                  <option key={m} value={m}>
                    {m} mét / bước
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-3 gap-1 w-36 mx-auto">
              <span />
              <button
                type="button"
                className={btnNudge}
                title="Dời về phía Bắc"
                onClick={() => nudge(0, nudgeStep)}
              >
                <ArrowUp size={13} className="mx-auto" />
              </button>
              <span />
              <button
                type="button"
                className={btnNudge}
                title="Dời về phía Tây"
                onClick={() => nudge(-nudgeStep, 0)}
              >
                <ArrowLeft size={13} className="mx-auto" />
              </button>
              <button
                type="button"
                className={btnNudge}
                title="Đặt lại về tọa độ gốc Nhà thờ Đức Bà"
                onClick={() => patch({ latitude: NOTRE_DAME_ORIGIN.lat, longitude: NOTRE_DAME_ORIGIN.lng })}
              >
                <Crosshair size={13} className="mx-auto text-rose-400" />
              </button>
              <button
                type="button"
                className={btnNudge}
                title="Dời về phía Đông"
                onClick={() => nudge(nudgeStep, 0)}
              >
                <ArrowRight size={13} className="mx-auto" />
              </button>
              <span />
              <button
                type="button"
                className={btnNudge}
                title="Dời về phía Nam"
                onClick={() => nudge(0, -nudgeStep)}
              >
                <ArrowDown size={13} className="mx-auto" />
              </button>
              <span />
            </div>
          </div>

          <ModelLocationSearch key={modelId} onSelect={place => {
            patch({ latitude: place.latitude, longitude: place.longitude })
            mapRef.current?.flyTo({ center: [place.longitude, place.latitude], zoom: 17.2, duration: 1400 })
            setStatusMessage({ kind: 'info', text: 'Đã chọn vị trí từ Goong. Bấm Lưu để cập nhật mô hình.' })
          }} />

          {/* Coordinate Inputs */}
          <div className="space-y-2.5">
            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-slate-400">Vĩ độ (Latitude WGS84)</span>
                <input
                  type="number"
                  step="0.000005"
                  value={calibration.latitude}
                  onChange={(e) => patch({ latitude: toNumber(e.target.value, calibration.latitude) })}
                  className="w-full mt-1 bg-slate-950/80 border border-slate-800 rounded-lg px-2 py-1 font-mono text-white focus:outline-none focus:border-amber-500"
                />
              </label>
              <label className="block">
                <span className="text-slate-400">Kinh độ (Longitude WGS84)</span>
                <input
                  type="number"
                  step="0.000005"
                  value={calibration.longitude}
                  onChange={(e) => patch({ longitude: toNumber(e.target.value, calibration.longitude) })}
                  className="w-full mt-1 bg-slate-950/80 border border-slate-800 rounded-lg px-2 py-1 font-mono text-white focus:outline-none focus:border-amber-500"
                />
              </label>
            </div>

            {/* Heading */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="text-slate-400">Góc xoay mặt tiền (Heading):</span>
                <span className="font-mono font-bold text-emerald-300">{calibration.heading.toFixed(1)}°</span>
              </div>
              <div className="flex gap-1.5 items-center">
                <input
                  type="range"
                  min="0"
                  max="359.5"
                  step="0.5"
                  value={calibration.heading}
                  onChange={(e) => patch({ heading: toNumber(e.target.value, calibration.heading) })}
                  className="flex-1 accent-emerald-400"
                />
                <button
                  type="button"
                  className={btnNudge}
                  onClick={() => patch({ heading: ((calibration.heading - 5 + 360) % 360) })}
                  title="Xoay ngược chiều kim đồng hồ 5 độ"
                >
                  -5°
                </button>
                <button
                  type="button"
                  className={btnNudge}
                  onClick={() => patch({ heading: ((calibration.heading + 5) % 360) })}
                  title="Xoay theo chiều kim đồng hồ 5 độ"
                >
                  +5°
                </button>
              </div>
            </div>

            {/* Height / Scale */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="text-slate-400">Chiều cao thực tế (Scale):</span>
                <span className="font-mono font-bold text-purple-300">{calibration.scale.toFixed(1)} mét</span>
              </div>
              <div className="flex gap-1.5 items-center">
                <input
                  type="range"
                  min="10"
                  max="120"
                  step="0.5"
                  value={calibration.scale}
                  onChange={(e) => patch({ scale: Math.max(1, toNumber(e.target.value, calibration.scale)) })}
                  className="flex-1 accent-purple-400"
                />
                <input
                  type="number"
                  step="0.5"
                  value={calibration.scale}
                  onChange={(e) => patch({ scale: Math.max(1, toNumber(e.target.value, calibration.scale)) })}
                  className="w-16 bg-slate-950/80 border border-slate-800 rounded px-1.5 py-0.5 font-mono text-center text-white"
                />
              </div>
            </div>

            {/* Altitude */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="text-slate-400">Cao độ mặt đất (Altitude):</span>
                <span className="font-mono font-bold text-cyan-300">{calibration.altitude.toFixed(1)}m</span>
              </div>
              <div className="flex gap-1.5 items-center">
                <input
                  type="range"
                  min="-10"
                  max="30"
                  step="0.2"
                  value={calibration.altitude}
                  onChange={(e) => patch({ altitude: toNumber(e.target.value, calibration.altitude) })}
                  className="flex-1 accent-cyan-400"
                />
                <input
                  type="number"
                  step="0.2"
                  value={calibration.altitude}
                  onChange={(e) => patch({ altitude: toNumber(e.target.value, calibration.altitude) })}
                  className="w-16 bg-slate-950/80 border border-slate-800 rounded px-1.5 py-0.5 font-mono text-center text-white"
                />
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="pt-4 mt-3 border-t border-slate-800 flex gap-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !dirty}
              className="flex-1 flex items-center justify-center gap-2 py-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition-all shadow-lg shadow-emerald-900/30 disabled:opacity-50"
            >
              {saving ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Đang lưu...
                </>
              ) : (
                <>
                  <Save size={14} /> Lưu Tọa Độ Vị Trí
                </>
              )}
            </button>
            <button
              type="button"
              onClick={() => {
                setCalibration(saved)
                setStatusMessage(null)
              }}
              disabled={!dirty}
              className="py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-xl transition-all disabled:opacity-40"
              title="Hoàn tác về lần lưu gần nhất"
            >
              <RotateCcw size={14} />
            </button>
          </div>

          {/* Status Message */}
          {statusMessage && (
            <div
              className={`mt-2.5 p-2 border rounded-lg text-xs ${
                statusMessage.kind === 'success'
                  ? 'bg-emerald-950/80 border-emerald-500/40 text-emerald-300'
                  : statusMessage.kind === 'error'
                  ? 'bg-rose-950/80 border-rose-500/40 text-rose-300'
                  : 'bg-slate-800/80 border-slate-600 text-slate-200'
              }`}
            >
              {statusMessage.text}
            </div>
          )}
        </div>
      )}

      {!previewJobId && <LandmarkDiscoveryPanel key={modelId} modelId={modelId} landmark={calibration}
        open={modelCardVisible} onOpen={() => setModelCardVisible(true)} onClose={() => setModelCardVisible(false)} onView={setCameraPreset} />}
    </div>
  )
}
