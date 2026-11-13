import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { restorePalaceTexture } from './landmark/palaceMaterial'

export function Walkthrough3D({ url, title, onClose }: { url: string; title: string; onClose: () => void }) {
  const mount = useRef<HTMLDivElement>(null)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => {
    const host = mount.current
    if (!host) return
    let disposed = false
    let frame = 0
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0xcedbe4)
    const camera = new THREE.PerspectiveCamera(72, 1, 0.05, 2000)
    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    host.appendChild(renderer.domElement)
    scene.add(new THREE.HemisphereLight(0xffffff, 0x64748b, 2.3))
    const sun = new THREE.DirectionalLight(0xffffff, 2.5)
    sun.position.set(25, 60, 30)
    scene.add(sun)

    let bounds = new THREE.Box3(new THREE.Vector3(-50, 0, -50), new THREE.Vector3(50, 20, 50))
    let eyeHeight = 1.7
    let speed = 5
    let ready = false
    let yaw = 0
    let pitch = 0
    const keys = new Set<string>()
    const clock = new THREE.Clock()
    const resize = () => {
      const width = host.clientWidth || 1
      const height = host.clientHeight || 1
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    }
    resize()
    const observer = new ResizeObserver(resize)
    observer.observe(host)

    const loader = new GLTFLoader()
    loader.load(url, ({ scene: model }) => {
      if (disposed) return
      restorePalaceTexture(model)
      const rawBox = new THREE.Box3().setFromObject(model)
      const size = rawBox.getSize(new THREE.Vector3())
      if (!Number.isFinite(size.y) || size.y <= 0) {
        setError('Mô hình không có kích thước hợp lệ.')
        return
      }
      // Preserve the model's proportions while giving the palace a human-scale height.
      const scale = 20 / size.y
      const center = rawBox.getCenter(new THREE.Vector3())
      model.scale.setScalar(scale)
      model.position.set(-center.x * scale, -rawBox.min.y * scale, -center.z * scale)
      scene.add(model)
      bounds = new THREE.Box3().setFromObject(model)
      eyeHeight = Math.min(1.7, Math.max(0.5, bounds.max.y * 0.08))
      speed = Math.max(2, Math.min(8, bounds.getSize(new THREE.Vector3()).length() / 30))
      camera.position.set(0, bounds.min.y + eyeHeight, bounds.max.z + Math.max(4, bounds.getSize(new THREE.Vector3()).z * 0.08))
      camera.lookAt(0, bounds.min.y + eyeHeight + 1, 0)
      yaw = Math.atan2(-camera.getWorldDirection(new THREE.Vector3()).x, -camera.getWorldDirection(new THREE.Vector3()).z)
      ready = true
      setProgress(100)
    }, (event) => {
      if (!disposed && event.total > 0) setProgress(Math.min(99, Math.round(event.loaded / event.total * 100)))
    }, () => { if (!disposed) setError('Không tải được file GLB. Kiểm tra đường dẫn hoặc tải lại trang.') })

    const onKeyDown = (event: KeyboardEvent) => {
      if (['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ShiftLeft'].includes(event.code)) event.preventDefault()
      keys.add(event.code)
      if (event.code === 'Escape') document.exitPointerLock?.()
    }
    const onKeyUp = (event: KeyboardEvent) => keys.delete(event.code)
    const onMouse = (event: MouseEvent) => {
      if (document.pointerLockElement !== renderer.domElement) return
      yaw -= event.movementX * 0.002
      pitch = THREE.MathUtils.clamp(pitch - event.movementY * 0.002, -1.35, 1.35)
      camera.rotation.set(pitch, yaw, 0, 'YXZ')
    }
    const lock = () => { if (ready) void renderer.domElement.requestPointerLock() }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    window.addEventListener('mousemove', onMouse)
    renderer.domElement.addEventListener('click', lock)

    const animate = () => {
      frame = requestAnimationFrame(animate)
      const delta = Math.min(clock.getDelta(), 0.05)
      if (ready && document.pointerLockElement === renderer.domElement) {
        const forward = Number(keys.has('KeyW') || keys.has('ArrowUp')) - Number(keys.has('KeyS') || keys.has('ArrowDown'))
        const right = Number(keys.has('KeyD') || keys.has('ArrowRight')) - Number(keys.has('KeyA') || keys.has('ArrowLeft'))
        const step = new THREE.Vector3(right, 0, -forward)
        if (step.lengthSq()) {
          step.normalize().applyAxisAngle(new THREE.Vector3(0, 1, 0), yaw).multiplyScalar(speed * (keys.has('ShiftLeft') ? 2 : 1) * delta)
          const next = camera.position.clone().add(step)
          const margin = 12
          camera.position.x = THREE.MathUtils.clamp(next.x, bounds.min.x - margin, bounds.max.x + margin)
          camera.position.z = THREE.MathUtils.clamp(next.z, bounds.min.z - margin, bounds.max.z + margin)
          camera.position.y = bounds.min.y + eyeHeight
        }
      }
      renderer.render(scene, camera)
    }
    animate()
    return () => {
      disposed = true
      cancelAnimationFrame(frame)
      if (document.pointerLockElement === renderer.domElement) void document.exitPointerLock()
      observer.disconnect()
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      window.removeEventListener('mousemove', onMouse)
      renderer.domElement.removeEventListener('click', lock)
      scene.traverse((node) => {
        if (!(node instanceof THREE.Mesh)) return
        node.geometry.dispose()
        for (const material of Array.isArray(node.material) ? node.material : [node.material]) material.dispose()
      })
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [url])

  return <div className="absolute inset-0 z-30 bg-slate-950 text-white" role="dialog" aria-label={`Đi bộ trong ${title}`}>
    <div ref={mount} className="absolute inset-0" />
    <div className="absolute left-4 top-4 rounded-xl bg-slate-950/85 px-4 py-3 text-sm shadow-lg">
      <strong>{title}</strong>
      <p className="mt-1 text-slate-300">{error || (progress < 100 ? `Đang tải mô hình ${progress}%…` : 'Nhấp vào cảnh để điều khiển · WASD di chuyển · Chuột nhìn quanh · Shift chạy · Esc thả chuột')}</p>
    </div>
    <button type="button" onClick={onClose} className="absolute right-4 top-4 rounded-xl bg-slate-950/85 px-4 py-2 text-sm font-semibold hover:bg-slate-800">Đóng chế độ đi bộ</button>
  </div>
}
