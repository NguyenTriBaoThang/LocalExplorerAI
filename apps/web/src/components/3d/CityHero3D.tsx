import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { Sparkles, Compass, Eye, Sun, Moon } from 'lucide-react'
import { useTheme } from '../../theme'
import { useTranslation } from '../../i18n'

interface HoveredPoint {
  name: string
  category: string
  time: string
  district: string
  x: number
  y: number
}

export function CityHero3D() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [hoveredPoint, setHoveredPoint] = useState<HoveredPoint | null>(null)
  const theme = useTheme()
  const { t } = useTranslation()
  const [themeMode, setThemeMode] = useState<'night' | 'day'>(theme === 'light' ? 'day' : 'night')
  // Follow the global theme; the Moon/Sun buttons still override locally.
  useEffect(() => setThemeMode(theme === 'light' ? 'day' : 'night'), [theme])
  const [activeDistrict, setActiveDistrict] = useState('Quận 1')

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
    camera.position.set(0, 8.5, 14.5)
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

    // Interactive 3D POI Pins
    const poiData = [
      { name: 'Góc thủ công giấy', category: 'Thủ công', time: '09:00 - 10:15', district: 'Quận 1', pos: [-2.8, 1.2, 1.5] },
      { name: 'Bếp món Nam Bộ', category: 'Ẩm thực', time: '11:30 - 13:00', district: 'Quận 1', pos: [-0.5, 1.4, -0.8] },
      { name: 'Chuyện phố qua ảnh', category: 'Văn hóa', time: '14:30 - 15:30', district: 'Quận 3', pos: [2.5, 1.5, -2.2] },
      { name: 'Bàn trải nghiệm gốm', category: 'Thủ công', time: '10:00 - 11:30', district: 'Bình Thạnh', pos: [3.8, 1.3, 1.8] },
      { name: 'Khoảng nghỉ thảo mộc', category: 'Thư giãn', time: '16:00 - 17:00', district: 'Quận 1', pos: [-4.2, 1.1, -1.8] },
    ]

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
      head.userData = { isHead: true, poi }
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
    const targetCameraPos = new THREE.Vector3(0, 8.5, 14.5)
    const raycaster = new THREE.Raycaster()

    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect()
      const x = ((e.clientX - rect.left) / width) * 2 - 1
      const y = -((e.clientY - rect.top) / height) * 2 + 1
      mouse.x = x
      mouse.y = y

      targetCameraPos.x = x * 3.5
      targetCameraPos.y = 8.5 + y * 2.2
      targetCameraPos.z = 14.5 - y * 1.5

      raycaster.setFromCamera(mouse, camera)
      const intersects = raycaster.intersectObjects(pinInteractiveObjects, false)

      if (intersects.length > 0) {
        const hit = intersects[0].object
        const poi = hit.userData.poi as HoveredPoint
        // Project 3D point to 2D screen coordinate
        const screenPos = hit.getWorldPosition(new THREE.Vector3()).project(camera)
        const sx = ((screenPos.x + 1) * width) / 2
        const sy = ((-screenPos.y + 1) * height) / 2

        setHoveredPoint({
          name: poi.name,
          category: poi.category,
          time: poi.time,
          district: poi.district,
          x: sx,
          y: sy,
        })
        setActiveDistrict(poi.district)
      } else {
        setHoveredPoint(null)
      }
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
      renderer.dispose()
      if (renderer.domElement && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement)
      }
    }
  }, [themeMode])

  return (
    <div className="city-hero-3d-wrapper" ref={containerRef}>
      {/* 3D Scene Overlay Badge & Controls */}
      <div className="city-hero-3d-header">
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
      </div>

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
              {hoveredPoint.time} · {hoveredPoint.district}
            </span>
          </div>
        </div>
      )}

      {/* 3D Floating Info Cards */}
      <div className="hero-3d-floating-stats">
        <div className="stat-capsule">
          <Eye size={13} className="text-emerald" />
          <span>{t('city3d.floatingStats')}</span>
        </div>
      </div>

      <div className="hero-3d-bottom-badge">
        <span className="hero-lat-lng">10°46'37" N · 106°42'04" E</span>
        <span className="hero-tech-label">{t('city3d.digitalTwin')}</span>
      </div>
    </div>
  )
}
