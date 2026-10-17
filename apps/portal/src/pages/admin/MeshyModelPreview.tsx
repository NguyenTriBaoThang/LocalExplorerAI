import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { http, errorMessage } from '../../lib/api'

function disposeModel(root: THREE.Object3D) {
  const textures = new Set<THREE.Texture>()
  const materials = new Set<THREE.Material>()
  root.traverse(node => {
    if (!(node instanceof THREE.Mesh)) return
    node.geometry.dispose()
    for (const material of Array.isArray(node.material) ? node.material : [node.material]) {
      materials.add(material)
      for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value)
    }
  })
  textures.forEach(texture => { texture.dispose(); const image = texture.source?.data; if (typeof ImageBitmap !== 'undefined' && image instanceof ImageBitmap) image.close() })
  materials.forEach(material => material.dispose())
}

export default function MeshyModelPreview({ jobId, name }: { jobId: string; name: string }) {
  const host = useRef<HTMLDivElement>(null)
  const resetCamera = useRef<() => void>(() => {})
  const zoomCamera = useRef<(factor: number) => void>(() => {})
  const [attempt, setAttempt] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    const element = host.current
    if (!element) return
    let renderer: THREE.WebGLRenderer
    setLoading(true); setError('')
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false }) } catch {
      setLoading(false); setError('Trình duyệt chưa hỗ trợ WebGL. Hãy bật tăng tốc phần cứng hoặc dùng trình duyệt khác.'); return
    }
    const abort = new AbortController()
    let disposed = false
    let visible = true
    let frame = 0
    let model: THREE.Object3D | undefined
    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#f4f2ed')
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.1
    renderer.domElement.style.cssText = 'display:block;width:100%;height:100%;touch-action:none'
    renderer.domElement.setAttribute('aria-label', `Mô hình 3D ${name}: kéo để xoay, cuộn để phóng to`)
    renderer.domElement.setAttribute('role', 'img')
    element.appendChild(renderer.domElement)
    const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 100)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.minDistance = 1.4; controls.maxDistance = 18
    controls.maxPolarAngle = Math.PI * 0.92
    const reset = () => { camera.position.set(4.3, 3.1, 5.2); controls.target.set(0, 0.9, 0); controls.update() }
    resetCamera.current = reset
    zoomCamera.current = factor => {
      const offset = camera.position.clone().sub(controls.target)
      offset.setLength(THREE.MathUtils.clamp(offset.length() * factor, controls.minDistance, controls.maxDistance))
      camera.position.copy(controls.target).add(offset); controls.update()
    }
    reset()
    const pmrem = new THREE.PMREMGenerator(renderer)
    const room = new RoomEnvironment()
    const environment = pmrem.fromScene(room)
    scene.environment = environment.texture
    room.dispose(); pmrem.dispose()
    scene.add(new THREE.HemisphereLight(0xffffff, 0x8b8175, 2.4))
    const light = new THREE.DirectionalLight(0xffffff, 3)
    light.position.set(4, 7, 5); scene.add(light)
    const grid = new THREE.GridHelper(8, 16, 0xc3c2c0, 0xe0ded9)
    grid.position.y = -0.015; scene.add(grid)
    const resize = () => {
      const { width, height } = element.getBoundingClientRect()
      renderer.setSize(Math.max(width, 1), Math.max(height, 1), false)
      camera.aspect = Math.max(width, 1) / Math.max(height, 1); camera.updateProjectionMatrix()
    }
    const observer = new ResizeObserver(resize); observer.observe(element); resize()
    const visibility = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting ?? false })
    visibility.observe(element)
    const animate = () => {
      if (disposed) return
      frame = requestAnimationFrame(animate)
      if (visible && !document.hidden) { controls.update(); renderer.render(scene, camera) }
    }
    animate()
    const contextLost = (event: Event) => { event.preventDefault(); setError('Bộ nhớ đồ họa bị gián đoạn. Bấm Tải lại mô hình để thử lại.'); setLoading(false) }
    renderer.domElement.addEventListener('webglcontextlost', contextLost)
    void (async () => {
      try {
        const response = await http.get<ArrayBuffer>(`/admin/meshy/jobs/${jobId}/asset`, { responseType: 'arraybuffer', signal: abort.signal, timeout: 120000 })
        const gltf = await new GLTFLoader().parseAsync(response.data, '')
        if (disposed) { disposeModel(gltf.scene); return }
        model = gltf.scene
        const box = new THREE.Box3().setFromObject(model)
        const size = box.getSize(new THREE.Vector3())
        const extent = Math.max(size.x, size.y, size.z)
        if (!Number.isFinite(extent) || extent <= 0) throw new Error('Model không có hình học để hiển thị.')
        const center = box.getCenter(new THREE.Vector3())
        const pivot = new THREE.Group()
        pivot.add(model)
        model.position.sub(center)
        pivot.scale.setScalar(3 / extent)
        pivot.position.y = size.y * 1.5 / extent
        scene.add(pivot)
        controls.target.set(0, pivot.position.y, 0)
        controls.update(); setLoading(false)
      } catch (err) {
        if (!disposed) { setLoading(false); setError(errorMessage(err, 'Không tải được model. Phiên đăng nhập có thể đã hết hạn hoặc tệp GLB chưa sẵn sàng.')) }
      }
    })()
    return () => {
      disposed = true; abort.abort(); cancelAnimationFrame(frame)
      observer.disconnect(); visibility.disconnect(); controls.dispose()
      renderer.domElement.removeEventListener('webglcontextlost', contextLost)
      if (model) disposeModel(model)
      grid.geometry.dispose(); (grid.material as THREE.Material).dispose()
      environment.dispose(); renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove()
      resetCamera.current = () => {}; zoomCamera.current = () => {}
    }
  }, [jobId, name, attempt])
  const button = 'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 disabled:opacity-40'
  return <section className="overflow-hidden rounded-xl border border-slate-200" aria-label={`Xem trực tiếp ${name}`}>
    <div className="flex flex-wrap items-center justify-between gap-2 bg-stone-50 px-4 py-3"><strong className="text-sm">Xem mô hình 3D trực tiếp</strong><div className="flex gap-2"><button type="button" className={button} disabled={loading || !!error} onClick={() => zoomCamera.current(0.8)} aria-label="Phóng to mô hình">+</button><button type="button" className={button} disabled={loading || !!error} onClick={() => zoomCamera.current(1.25)} aria-label="Thu nhỏ mô hình">−</button><button type="button" className={button} disabled={loading || !!error} onClick={() => resetCamera.current()}>Góc nhìn ban đầu</button></div></div>
    <div className="relative"><div ref={host} className="h-[340px] w-full sm:h-[440px]" />{loading && <p role="status" className="absolute inset-0 flex items-center justify-center bg-stone-50/90 text-sm">Đang tải mô hình 3D…</p>}{error && <div role="alert" className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-stone-50/95 p-6 text-center text-sm text-red-800"><p>{error}</p><button type="button" className={button} onClick={() => setAttempt(value => value + 1)}>Tải lại mô hình</button></div>}</div>
    <p className="bg-stone-50 px-4 py-3 text-xs text-slate-600">Kéo để xoay · Cuộn hoặc chụm hai ngón để phóng to · Chuột phải để dịch chuyển. Đây là bản xem hình dáng; dùng nút căn vị trí trên bản đồ trước khi xuất bản.</p>
  </section>
}
