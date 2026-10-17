import { MeshyChat } from './MeshyChat'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { http, errorMessage } from '../../lib/api'
const MeshyModelPreview = lazy(() => import('./MeshyModelPreview'))

type Placement = { display_name: string; latitude: number; longitude: number; scale: number; heading: number; altitude: number; poi_id?: string }
type Job = { id: string; task_id: string | null; kind: string; status: string; progress: number; credits: number; error: string | null; published: boolean; previewed: boolean; calibration: Placement }
type Place = { id: string; name: string; latitude: number; longitude: number }
const field = 'w-full rounded-lg border border-slate-300 bg-white p-2 text-slate-900'
const button = 'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 disabled:opacity-40'
const states: Record<string, string> = { submitting: 'Đang gửi', pending: 'Đang chờ', running: 'Đang tạo', ready: 'Sẵn sàng', failed: 'Không hoàn thành', uncertain: 'Cần đối chiếu Meshy', timeout: 'Hết thời gian theo dõi' }
const webOrigin = ['localhost', '127.0.0.1'].includes(location.hostname) ? `${location.protocol}//${location.hostname}:8080` : location.origin
export function AdminMeshyPage() {
  const [previewId, setPreviewId] = useState<string | null | undefined>(undefined)
  const [jobs, setJobs] = useState<Job[]>([])
  const [places, setPlaces] = useState<Place[]>([])
  const [configured, setConfigured] = useState(false)
  const [limit, setLimit] = useState(120)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [kind, setKind] = useState<'text' | 'image'>('text')
  const [briefReady, setBriefReady] = useState(false)
  const [prompt, setPrompt] = useState('')
  const [images, setImages] = useState<string[]>([])
  const [reading, setReading] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [placement, setPlacement] = useState<Placement>({ display_name: '', latitude: 10.779785, longitude: 106.699018, scale: 20, heading: 0, altitude: 0 })
  const requestKey = useRef(crypto.randomUUID())
  const [recoverIds, setRecoverIds] = useState<Record<string, string>>({})
  const [refineId, setRefineId] = useState<string | null>(null)
  const refineKeys = useRef<Record<string, string>>({})
  async function refresh() {
    const { data } = await http.get('/admin/meshy/jobs')
    setJobs(data.jobs); setConfigured(data.configured); setLimit(data.daily_limit); setPlaces(data.places)
  }
  useEffect(() => {
    void refresh().catch(e => setError(errorMessage(e)))
    const timer = window.setInterval(() => void refresh().catch(() => {}), 15000)
    return () => clearInterval(timer)
  }, [])
  async function run(fn: () => Promise<unknown>) {
    setBusy(true); setError('')
    try { await fn(); await refresh() } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  async function readImages(files: FileList | null) {
    setError(''); setImages([]); setReading(true); setConfirmed(false); setBriefReady(false)
    try {
      const picked = Array.from(files || [])
      if (picked.length > 4 || picked.some(f => f.size > 5 * 1024 * 1024 || !['image/jpeg', 'image/png', 'image/webp'].includes(f.type))) throw new Error('Tối đa 4 ảnh JPEG/PNG/WebP, mỗi ảnh không quá 5 MB.')
      setImages(await Promise.all(picked.map(f => new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = reject; reader.readAsDataURL(f) }))))
    } catch (e) { setError(e instanceof Error ? e.message : 'Không đọc được ảnh') } finally { setReading(false) }
  }
  const cost = kind === 'text' ? 20 : 30
  const activePreview = previewId === undefined ? jobs.find(job => job.status === 'ready')?.id : previewId
  return <main className="mx-auto max-w-6xl space-y-6 p-4 text-slate-900">
    <div><h1 className="text-2xl font-bold">Tạo mô hình 3D bằng AI</h1><p className="mt-2 text-sm text-slate-600">Chat và ảnh → Gemini chuẩn bị → Meshy tạo 3D → căn vị trí và xuất bản. Mô hình AI cần đối chiếu với công trình thực tế.</p></div>
    {!configured && <p className="rounded-xl bg-amber-50 p-4 text-amber-900">Chưa cấu hình Meshy. <Link className="underline" to="/admin/integrations">Nhập API key mới tại Tích hợp & API keys</Link>.</p>}
    {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-red-800">{error}</p>}
    <MeshyChat images={images} reading={reading} disabled={busy} placeName={placement.display_name} onImages={readImages}
      onInvalidate={() => { setBriefReady(false); setConfirmed(false) }}
      onBrief={brief => { setPrompt(brief.prompt); setBriefReady(brief.ready); setConfirmed(false); setKind(images.length ? 'image' : 'text'); if (!placement.display_name && brief.display_name) setPlacement(current => current.display_name ? current : ({ ...current, display_name: brief.display_name })) }} />
    <h2 className="text-lg font-semibold">Bản mô tả và yêu cầu gửi Meshy</h2>
    {!briefReady && <p className="text-sm text-slate-600">Trao đổi với Gemini để hoàn thiện bản mô tả trước khi tạo model.</p>}
    <form className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-5 md:grid-cols-2" onSubmit={e => { e.preventDefault(); void run(async () => { await http.post('/admin/meshy/jobs', { ...placement, kind, prompt, images: kind === 'image' ? images : [], request_key: requestKey.current, max_credits: cost }); requestKey.current = crypto.randomUUID(); setConfirmed(false) }) }}>
      <label>Địa điểm<select className={field} value={placement.poi_id || ''} onChange={e => { const p = places.find(x => x.id === e.target.value); setPlacement(p ? { ...placement, poi_id: p.id, display_name: p.name, latitude: p.latitude, longitude: p.longitude } : { ...placement, poi_id: undefined }) }}><option value="">Nhập vị trí thủ công</option>{places.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <label>Tên mô hình<input className={field} required minLength={2} maxLength={120} value={placement.display_name} onChange={e => setPlacement({ ...placement, display_name: e.target.value })} /></label>
      <label>Cách tạo<select className={field} value={kind} onChange={e => { setKind(e.target.value as 'text' | 'image'); setConfirmed(false) }}><option value="text">Từ mô tả — hình học</option><option value="image">Từ 1–4 ảnh — có texture</option></select></label>
      <p className="text-sm text-slate-600">Meshy-6 · GLB · mục tiêu 30.000 mặt. Hạn mức {limit} credit/tài khoản/ngày (UTC), tối đa 2 tác vụ đang xử lý. Chi phí dự kiến, số dư thực tế do Meshy quyết định.</p>
      <label className="md:col-span-2">Mô tả do Gemini chuẩn bị (có thể chỉnh sửa)<textarea className={field} rows={4} maxLength={800} required={kind === 'text'} value={prompt} onChange={e => { setPrompt(e.target.value); setConfirmed(false) }} /></label>
      {kind === 'image' && <p className="text-sm text-amber-900 md:col-span-2">Meshy sẽ nhận {images.length} ảnh gốc đã gửi Gemini. Chế độ ảnh không áp dụng thay đổi hình học từ mô tả; chọn “Từ mô tả” nếu muốn tạo theo nội dung đã chỉnh.</p>}
      {([['latitude', 'Vĩ độ', -90, 90], ['longitude', 'Kinh độ', -180, 180], ['scale', 'Chiều cao mô hình (m)', 0.51, 1000], ['heading', 'Hướng xoay (độ)', 0, 359.99], ['altitude', 'Độ cao nền (m)', -50, 200]] as const).map(([key, label, min, max]) => <label key={key}>{label}<input className={field} type="number" step="any" min={min} max={max} required value={placement[key]} onChange={e => setPlacement({ ...placement, [key]: Number(e.target.value) })} /></label>)}
      <label className="flex items-center gap-2 text-sm md:col-span-2"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Tôi đồng ý gửi {kind === 'text' ? 'mô tả' : 'các ảnh đã chọn'} tới Meshy và sử dụng khoảng {cost} API credit.</label>
      <button className={button} disabled={busy || !briefReady || !configured || !confirmed || reading || (kind === 'image' && !images.length)}>{busy ? 'Đang gửi…' : `Gửi sang Meshy · ${cost} credit`}</button>
    </form>
    <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Tác vụ và mô hình</h2><button className={button} disabled={busy} onClick={() => void run(refresh)}>Cập nhật</button></div>
    {!jobs.length && <p className="rounded-xl bg-slate-50 p-5">Chưa có tác vụ. Tạo mô hình đầu tiên sau khi cấu hình key.</p>}
    {jobs.map(job => <article key={job.id} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap justify-between gap-2"><h3 className="font-semibold">{job.calibration.display_name}</h3><span>{job.published ? 'Đã xuất bản' : states[job.status] || job.status} · {job.progress}%</span></div>
      <progress className="w-full" max={100} value={job.progress} aria-label="Tiến trình tạo model" />
      <p className="text-xs text-slate-600">{job.kind === 'text' ? 'Hình học' : 'Có texture'} · {job.credits} credit dự kiến · {job.task_id || job.id}</p>
      {job.error && <p className="text-sm text-amber-900">{job.error}</p>}
      {job.status === 'ready' && <div className="space-y-3"><button type="button" className={button} aria-expanded={activePreview === job.id} onClick={() => setPreviewId(activePreview === job.id ? null : job.id)}>{activePreview === job.id ? 'Thu gọn mô hình 3D' : 'Xem 3D ngay tại đây'}</button>
        {activePreview === job.id && <Suspense fallback={<p role="status" className="rounded-xl bg-stone-50 p-8">Đang mở trình xem 3D…</p>}><MeshyModelPreview jobId={job.id} name={job.calibration.display_name} /></Suspense>}
      </div>}
      <div className="flex flex-wrap gap-2">
        {job.status === 'ready' && <a className={button} href={`${webOrigin}/map-3d?meshyPreview=${job.id}`} target="_blank" rel="noreferrer">Xem thử và căn vị trí trên bản đồ</a>}
        {job.status === 'ready' && job.kind === 'text' && <button className={button} disabled={busy} onClick={() => setRefineId(job.id)}>Thêm texture · 10 credit</button>}
        {job.status === 'ready' && !job.published && <button className={button} disabled={busy || !job.previewed} title="Mở bản xem thử và chờ model tải xong trước" onClick={() => void run(() => http.post(`/admin/meshy/jobs/${job.id}/publish`))}>Xuất bản lên Map3D</button>}
        {job.published && <button className={button} disabled={busy} onClick={() => void run(() => http.post(`/admin/meshy/jobs/${job.id}/unpublish`))}>Gỡ xuất bản</button>}
        {job.status === 'timeout' && <button className={button} disabled={busy} onClick={() => void run(() => http.post(`/admin/meshy/jobs/${job.id}/resume`))}>Tiếp tục kiểm tra (không tạo mới)</button>}
      </div>
      {job.status === 'uncertain' && <div className="space-y-2 rounded-lg bg-amber-50 p-3 text-sm"><p>Đối chiếu tác vụ trên dashboard Meshy. Nhập ID tác vụ đúng mô hình để tiếp tục, không mất thêm credit.</p><input className={field} aria-label="Meshy task ID" value={recoverIds[job.id] || ''} onChange={e => setRecoverIds({ ...recoverIds, [job.id]: e.target.value })} placeholder="Task ID từ Meshy" /><button className={button} disabled={busy || !recoverIds[job.id]} onClick={() => void run(() => http.post(`/admin/meshy/jobs/${job.id}/reconcile`, { task_id: recoverIds[job.id] }))}>Gắn tác vụ và tiếp tục</button> <button className={button} disabled={busy} onClick={() => void run(() => http.post(`/admin/meshy/jobs/${job.id}/reconcile`, { confirmed_not_created: true }))}>Đã kiểm tra: không có tác vụ trên Meshy</button></div>}
      {refineId === job.id && <div className="rounded-lg bg-amber-50 p-3 text-sm"><p>Tạo texture sẽ gửi thêm một yêu cầu tới Meshy, khoảng 10 credit.</p><button className={button} disabled={busy} onClick={() => void run(async () => { refineKeys.current[job.id] ||= crypto.randomUUID(); await http.post(`/admin/meshy/jobs/${job.id}/refine`, { request_key: refineKeys.current[job.id], max_credits: 10 }); setRefineId(null) })}>Xác nhận tạo texture</button> <button className={button} onClick={() => setRefineId(null)}>Đóng</button></div>}
    </article>)}
  </main>
}
