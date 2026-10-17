import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { Sparkles, Compass, Eye, Sun, Moon } from 'lucide-react'
import { getPOIs } from '../../api/client'
import type { POI } from '../../types'
import type { MapPoint, MapRoute } from '../map/MapAdapter'
import { useTheme } from '../../theme'
import { useTranslation } from '../../i18n'

interface HoveredPoint {
  name: string
  category: string
  district: string
  x: number
  y: number
}

const EMPTY_ROUTES: MapRoute[] = []

export function CityHero3D({
  journeyPoints,
  routes = EMPTY_ROUTES,
  selectedId,
  onSelect,
  variant = 'hero',
}: {
  journeyPoints?: MapPoint[]
  routes?: MapRoute[]
  selectedId?: string
  onSelect?: (id: string) => void
  variant?: 'hero' | 'inline'
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [pois, setPois] = useState<POI[]>([])
  const [hoveredPoint, setHoveredPoint] = useState<HoveredPoint | null>(null)
  const theme = useTheme()
  const { t } = useTranslation()
  const [themeMode, setThemeMode] = useState<'night' | 'day'>(theme === 'light' ? 'day' : 'night')
  // Follow the global theme; the Moon/Sun buttons still override locally.
  useEffect(() => setThemeMode(theme === 'light' ? 'day' : 'night'), [theme])
  const [activeDistrict, setActiveDistrict] = useState('Quận 1')
  const selectedIdRef = useRef(selectedId)
  const onSelectRef = useRef(onSelect)
  selectedIdRef.current = selectedId
  onSelectRef.current = onSelect

  useEffect(() => {
    if (journeyPoints !== undefined) return
    let active = true
    void getPOIs().then((rows) => {
      if (active) setPois(rows)
    }).catch(() => {
      if (active) setPois([])
    })
    return () => { active = false }
  }, [journeyPoints])

  const themeRef = useRef(themeMode)
  themeRef.current = themeMode

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    let width = container.clientWidth
    let height = container.clientHeight

    // Scene, Camera, Renderer
    const scene = new THREE.Scene()
    scene.fog = new THREE.FogExp2(themeRef.current === 'night' ? 0x051310 : 0xf0fdf4, 0.045)

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100)
    camera.position.set(0, 12, 25)
    camera.lookAt(0, 0, 0)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    container.appendChild(renderer.domElement)

    // Lighting
    const ambientLight = new THREE.AmbientLight(
      themeRef.current === 'night' ? 0x13382c : 0xffffff,
      themeRef.current === 'night' ? 1.4 : 1.2
    )
    scene.add(ambientLight)

    const dirLight = new THREE.DirectionalLight(0x34d399, 1.8)
    dirLight.position.set(10, 20, 10)
    scene.add(dirLight)

    const accentLight = new THREE.PointLight(0xf59e0b, 2.5, 20)
    accentLight.position.set(-2, 3, 2)
    scene.add(accentLight)

    const cyanLight = new THREE.PointLight(0x06b6d4, 2, 20)
    cyanLight.position.set(3, 4, -2)
    scene.add(cyanLight)

    // City Ground Grid (Topographic Mesh)
    const gridGeometry = new THREE.PlaneGeometry(28, 28, 48, 48)
    const posAttr = gridGeometry.attributes.position
    for (let i = 0; i < posAttr.count; i++) {
      const x = posAttr.getX(i)
      const y = posAttr.getY(i)
      // river depression trough along curve
      const riverDist = Math.abs(y - Math.sin(x * 0.4) * 2.5)
      let z = Math.sin(x * 0.5) * Math.cos(y * 0.5) * 0.35
      if (riverDist < 1.4) {
        z -= 0.65 * (1 - riverDist / 1.4)
      }
      posAttr.setZ(i, z)
    }
    gridGeometry.computeVertexNormals()

    const gridMaterial = new THREE.MeshStandardMaterial({
      color: themeRef.current === 'night' ? 0x06281e : 0xd1fae5,
      wireframe: true,
      wireframeLinewidth: 1.2,
      roughness: 0.8,
      metalness: 0.2,
    })
    const gridMesh = new THREE.Mesh(gridGeometry, gridMaterial)
    gridMesh.rotation.x = -Math.PI / 2
    gridMesh.position.y = -0.5
    scene.add(gridMesh)

    // River Water Ribbon
    const riverCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-12, -0.6, -5),
      new THREE.Vector3(-7, -0.65, -2.5),
      new THREE.Vector3(-2, -0.65, 0.5),
      new THREE.Vector3(3, -0.65, 2.2),
      new THREE.Vector3(8, -0.65, 0),
      new THREE.Vector3(12, -0.6, -3),
    ])
    const riverGeometry = new THREE.TubeGeometry(riverCurve, 64, 0.85, 8, false)
    const riverMaterial = new THREE.MeshStandardMaterial({
      color: 0x0ea5e9,
      roughness: 0.1,
      metalness: 0.8,
      transparent: true,
      opacity: 0.85,
      emissive: 0x0284c7,
      emissiveIntensity: 0.35,
    })
    const riverMesh = new THREE.Mesh(riverGeometry, riverMaterial)
    scene.add(riverMesh)

    // 3D City Buildings
    const buildingGroup = new THREE.Group()
    const buildingCount = 42
    const buildingMeshes: THREE.Mesh[] = []

    const buildingColors = [0x10b981, 0x059669, 0x047857, 0x0d9488, 0x14b8a6, 0xf59e0b]

    for (let i = 0; i < buildingCount; i++) {
      const w = 0.45 + Math.random() * 0.65
      const d = 0.45 + Math.random() * 0.65
      const h = 0.8 + Math.random() * (i === 15 ? 4.8 : 2.6) // Landmark tower
      const geo = new THREE.BoxGeometry(w, h, d)

      // Random position avoiding direct center of river
      let bx = (Math.random() - 0.5) * 16
      let bz = (Math.random() - 0.5) * 14
      const riverY = Math.sin(bx * 0.4) * 2.5
      if (Math.abs(bz - riverY) < 1.6) {
        bz += (bz > riverY ? 1.8 : -1.8)
      }

      const mat = new THREE.MeshStandardMaterial({
        color: buildingColors[i % buildingColors.length],
        roughness: 0.3,
        metalness: 0.5,
        transparent: true,
        opacity: 0.88,
        emissive: buildingColors[i % buildingColors.length],
        emissiveIntensity: 0.18,
      })
      const bMesh = new THREE.Mesh(geo, mat)
      bMesh.position.set(bx, h / 2 - 0.5, bz)

      // Add edge line highlight to buildings
      const edges = new THREE.EdgesGeometry(geo)
      const line = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({
          color: themeRef.current === 'night' ? 0x34d399 : 0x059669,
          transparent: true,
          opacity: 0.55,
        })
      )
      bMesh.add(line)

      buildingGroup.add(bMesh)
      buildingMeshes.push(bMesh)
    }
    scene.add(buildingGroup)

    // Center and scale the selected POIs/routes so the real journey fits this scene.
    const mapPois = journeyPoints ?? (pois.length <= 12
      ? pois
      : Array.from({ length: 12 }, (_, index) => pois[Math.round(index * (pois.length - 1) / 11)]))
    const scenePoints: MapPoint[] = journeyPoints ?? mapPois.map((poi) => ({
      id: poi.id,
      latitude: poi.latitude,
      longitude: poi.longitude,
      name: poi.name,
      category: poi.category,
      district: poi.district,
    }))
    const allCoordinates = [
      ...scenePoints.map((point) => [point.latitude, point.longitude] as [number, number]),
      ...routes.flatMap((route) => route.coordinates),
    ].filter(([latitude, longitude]) => Number.isFinite(latitude) && Number.isFinite(longitude))
    const minLatitude = Math.min(...allCoordinates.map(([latitude]) => latitude), 10.7769)
    const maxLatitude = Math.max(...allCoordinates.map(([latitude]) => latitude), 10.7769)
    const minLongitude = Math.min(...allCoordinates.map(([, longitude]) => longitude), 106.7009)
    const maxLongitude = Math.max(...allCoordinates.map(([, longitude]) => longitude), 106.7009)
    const centerLatitude = (minLatitude + maxLatitude) / 2
    const centerLongitude = (minLongitude + maxLongitude) / 2
    const longitudeFactor = Math.cos((centerLatitude * Math.PI) / 180)
    const sceneExtent = Math.max((maxLongitude - minLongitude) * longitudeFactor, maxLatitude - minLatitude, 0.01)
    const sceneScale = 18 / sceneExtent
    const toScenePosition = (latitude: number, longitude: number) => new THREE.Vector3(
      (longitude - centerLongitude) * longitudeFactor * sceneScale,
      0.12,
      (centerLatitude - latitude) * sceneScale,
    )
    const poiData = scenePoints.map((point) => ({
      id: point.id,
      name: point.name,
      category: point.category ?? 'Địa điểm',
      district: point.district || 'TP. Hồ Chí Minh',
      pos: toScenePosition(point.latitude, point.longitude).toArray(),
    }))

    // Draw each route leg in its own color, matching the 2D map legend.
    const routeGroup = new THREE.Group()
    routes.forEach((route, index) => {
      const positions = route.coordinates.map(([latitude, longitude]) => {
        const position = toScenePosition(latitude, longitude)
        position.y = 0.22
        return position
      })
      if (positions.length < 2) return
      const curve = new THREE.CatmullRomCurve3(positions)
      const geometry = new THREE.TubeGeometry(curve, Math.max(24, positions.length * 8), 0.075, 8, false)
      const color = new THREE.Color(route.color || ['#10b981', '#06b6d4', '#f59e0b', '#8b5cf6'][index % 4])
      const material = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: 0.55,
        roughness: 0.3,
        metalness: 0.2,
      })
      routeGroup.add(new THREE.Mesh(geometry, material))
    })
    scene.add(routeGroup)

    const pinGroup = new THREE.Group()
    const pinInteractiveObjects: THREE.Object3D[] = []

    poiData.forEach((poi, index) => {
      const pinAnchor = new THREE.Group()
      pinAnchor.position.set(poi.pos[0], poi.pos[1], poi.pos[2])
      pinAnchor.userData = { poi, index }

      // Glow beacon stalk
      const stalkGeo = new THREE.CylinderGeometry(0.04, 0.04, 1.4, 12)
      const stalkMat = new THREE.MeshBasicMaterial({
        color: 0x34d399,
        transparent: true,
        opacity: 0.75,
      })
      const stalk = new THREE.Mesh(stalkGeo, stalkMat)
      stalk.position.y = 0.7
      pinAnchor.add(stalk)

      // Glowing floating orb on top
      const headGeo = new THREE.SphereGeometry(0.28, 16, 16)
      const headMat = new THREE.MeshStandardMaterial({
        color: index === 1 ? 0xf59e0b : 0x10b981,
        emissive: index === 1 ? 0xf59e0b : 0x10b981,
        emissiveIntensity: 0.9,
        roughness: 0.1,
      })
      const head = new THREE.Mesh(headGeo, headMat)
      head.position.y = 1.4
      head.userData = { isHead: true, poi, poiId: poi.id }
      pinAnchor.add(head)

      // Outer radar pulse ring
      const ringGeo = new THREE.RingGeometry(0.35, 0.42, 24)
      const ringMat = new THREE.MeshBasicMaterial({
        color: index === 1 ? 0xf59e0b : 0x34d399,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.7,
      })
      const ring = new THREE.Mesh(ringGeo, ringMat)
      ring.rotation.x = Math.PI / 2
      ring.position.y = 0.05
      pinAnchor.add(ring)

      pinGroup.add(pinAnchor)
      pinInteractiveObjects.push(head)
    })
    scene.add(pinGroup)

    // Floating 3D Particles
    const particleCount = 75
    const particleGeometry = new THREE.BufferGeometry()
    const particlePositions = new Float32Array(particleCount * 3)
    for (let i = 0; i < particleCount * 3; i += 3) {
      particlePositions[i] = (Math.random() - 0.5) * 22
      particlePositions[i + 1] = Math.random() * 8
      particlePositions[i + 2] = (Math.random() - 0.5) * 20
    }
    particleGeometry.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3))
    const particleMaterial = new THREE.PointsMaterial({
      color: 0x6ee7b7,
      size: 0.16,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending,
    })
    const particleSystem = new THREE.Points(particleGeometry, particleMaterial)
    scene.add(particleSystem)

    // Mouse & Raycasting for 3D Camera Parallax and Pin Tooltip
    const mouse = new THREE.Vector2(-999, -999)
    const targetCameraPos = new THREE.Vector3(0, 12, 25)
    const raycaster = new THREE.Raycaster()

    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect()
      const x = ((e.clientX - rect.left) / width) * 2 - 1
      const y = -((e.clientY - rect.top) / height) * 2 + 1
      mouse.x = x
      mouse.y = y

      targetCameraPos.x = x * 3.5
      targetCameraPos.y = 12 + y * 2.2
      targetCameraPos.z = 25 - y * 1.5

      raycaster.setFromCamera(mouse, camera)
      const intersects = raycaster.intersectObjects(pinInteractiveObjects, false)

      if (intersects.length > 0) {
        const hit = intersects[0].object
        const poi = hit.userData.poi as HoveredPoint
        container.style.cursor = 'pointer'
        // Project 3D point to 2D screen coordinate
        const screenPos = hit.getWorldPosition(new THREE.Vector3()).project(camera)
        const sx = ((screenPos.x + 1) * width) / 2
        const sy = ((-screenPos.y + 1) * height) / 2

        setHoveredPoint({
          name: poi.name,
          category: poi.category,
          district: poi.district,
          x: sx,
          y: sy,
        })
        setActiveDistrict(poi.district)
      } else {
        container.style.cursor = 'grab'
        setHoveredPoint(null)
      }
    }

    const handlePinClick = (event: MouseEvent) => {
      const rect = container.getBoundingClientRect()
      mouse.x = ((event.clientX - rect.left) / width) * 2 - 1
      mouse.y = -((event.clientY - rect.top) / height) * 2 + 1
      raycaster.setFromCamera(mouse, camera)
      const hit = raycaster.intersectObjects(pinInteractiveObjects, false)[0]?.object
      const pointId = hit?.userData.poiId
      if (typeof pointId === 'string') onSelectRef.current?.(pointId)
    }

    const handleResize = () => {
      if (!container) return
      width = container.clientWidth
      height = container.clientHeight
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    }

    window.addEventListener('resize', handleResize)
    container.addEventListener('mousemove', handleMouseMove)
    container.addEventListener('click', handlePinClick)

    // Animation Loop
    let animationFrameId: number
    const startTime = performance.now()

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate)
      const elapsed = (performance.now() - startTime) / 1000

      // Smooth camera damping
      camera.position.lerp(targetCameraPos, 0.05)
      camera.lookAt(0, 0.5, 0)

      // Floating pins
      pinGroup.children.forEach((anchor, i) => {
        anchor.position.y = poiData[i].pos[1] + Math.sin(elapsed * 2 + i * 1.5) * 0.12
        const head = anchor.children[1] as THREE.Mesh
        const headMaterial = head.material as THREE.MeshStandardMaterial
        const isSelected = poiData[i].id && poiData[i].id === selectedIdRef.current
        headMaterial.color.setHex(isSelected ? 0xf59e0b : i === 1 ? 0xf59e0b : 0x10b981)
        headMaterial.emissive.setHex(isSelected ? 0xf59e0b : i === 1 ? 0xf59e0b : 0x10b981)
        const ring = anchor.children[2] as THREE.Mesh
        if (ring) {
          const s = 1 + Math.sin(elapsed * 3 + i) * 0.25
          ring.scale.set(s, s, 1)
        }
      })

      // River glow pulse
      riverMaterial.emissiveIntensity = 0.35 + Math.sin(elapsed * 1.8) * 0.15

      // Gentle building breathing
      buildingMeshes.forEach((mesh, idx) => {
        mesh.rotation.y = Math.sin(elapsed * 0.3 + idx) * 0.02
      })

      // Drift particles
      const positions = particleGeometry.attributes.position.array as Float32Array
      for (let i = 1; i < particleCount * 3; i += 3) {
        positions[i] += 0.008
        if (positions[i] > 8) positions[i] = 0
      }
      particleGeometry.attributes.position.needsUpdate = true

      renderer.render(scene, camera)
    }

    animate()

    return () => {
      cancelAnimationFrame(animationFrameId)
      window.removeEventListener('resize', handleResize)
      container.removeEventListener('mousemove', handleMouseMove)
      container.removeEventListener('click', handlePinClick)
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh
        mesh.geometry?.dispose()
        if (Array.isArray(mesh.material)) mesh.material.forEach((material) => material.dispose())
        else mesh.material?.dispose()
      })
      renderer.dispose()
      if (renderer.domElement && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement)
      }
    }
  }, [themeMode, pois, journeyPoints, routes])

  return (
    <div className={`city-hero-3d-wrapper ${variant === 'inline' ? 'city-hero-3d-inline' : ''}`} ref={containerRef}>
      {/* 3D Scene Overlay Badge & Controls */}
      {variant === 'hero' && <div className="city-hero-3d-header">
        <div className="district-pill">
          <span className="pulse-beacon" />
          <Compass size={14} className="icon-emerald" />
          <span>{t('city3d.city')} · <strong>{activeDistrict}</strong></span>
        </div>
        <div className="view-mode-controls">
          <button
            type="button"
            className={`mode-btn ${themeMode === 'night' ? 'mode-active' : ''}`}
            onClick={() => setThemeMode('night')}
            title={t('city3d.modeNight')}
            aria-label={t('city3d.modeNight')}
          >
            <Moon size={14} />
          </button>
          <button
            type="button"
            className={`mode-btn ${themeMode === 'day' ? 'mode-active' : ''}`}
            onClick={() => setThemeMode('day')}
            title={t('city3d.modeDay')}
            aria-label={t('city3d.modeDay')}
          >
            <Sun size={14} />
          </button>
        </div>
      </div>}

      {/* Floating 3D Interactive Tooltip */}
      {hoveredPoint && (
        <div
          className="city-3d-tooltip"
          style={{
            left: `${hoveredPoint.x}px`,
            top: `${hoveredPoint.y}px`,
          }}
        >
          <div className="tooltip-glow" />
          <div className="tooltip-content">
            <span className="tooltip-tag">{hoveredPoint.category}</span>
            <strong className="tooltip-title">{hoveredPoint.name}</strong>
            <span className="tooltip-meta">
              <Sparkles size={12} className="text-amber" />
              {hoveredPoint.district}
            </span>
          </div>
        </div>
      )}

      {/* 3D Floating Info Cards */}
      {variant === 'hero' && <div className="hero-3d-floating-stats">
        <div className="stat-capsule">
          <Eye size={13} className="text-emerald" />
          <span>{t('city3d.floatingStats')}</span>
        </div>
      </div>}

      {variant === 'hero' && <div className="hero-3d-bottom-badge">
        <span className="hero-lat-lng">10°46'37" N · 106°42'04" E</span>
        <span className="hero-tech-label">{t('city3d.digitalTwin')}</span>
      </div>}
    </div>
  )
}
