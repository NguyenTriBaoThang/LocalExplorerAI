import { useEffect, useState } from 'react'
import { http, errorMessage } from '../../lib/api'
import type { LandmarkStory, StoryFact, StoryImage, StorySource, CameraView } from '../../lib/landmarkStory'

type Draft = { model_id: string; revision: number; workflow: string; content: LandmarkStory; published: LandmarkStory | null }
type Model = { model_id: string; display_name: string }
const field = 'w-full rounded-lg border border-slate-300 bg-white p-2 text-sm text-slate-900'
const button = 'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 disabled:opacity-40'
const fact = (): StoryFact => ({ text: '', status: 'unverified', source_ids: [] })

function FactEditor({ label, value, sources, onChange }: { label: string; value: StoryFact; sources: StorySource[]; onChange: (v: StoryFact) => void }) {
  return <div className="space-y-2"><label className="block text-sm font-semibold">{label}<textarea className={field} rows={3} maxLength={1600} value={value.text} onChange={e => onChange({ ...value, text: e.target.value })} /></label>
    <label className="block text-xs">Trạng thái <select className={field} value={value.status} onChange={e => onChange({ ...value, status: e.target.value as StoryFact['status'] })}><option value="unverified">Chưa xác minh</option><option value="sourced">Đã đối chiếu nguồn</option></select></label>
    <fieldset className="flex flex-wrap gap-3 text-xs"><legend className="mb-1">Nguồn hỗ trợ nội dung này</legend>{sources.length ? sources.map(s => <label key={s.id} className="flex items-center gap-1"><input type="checkbox" checked={value.source_ids.includes(s.id)} onChange={e => onChange({ ...value, source_ids: e.target.checked ? [...value.source_ids, s.id] : value.source_ids.filter(id => id !== s.id) })} />{s.title || s.id}</label>) : <p className="text-amber-800">Thêm nguồn tham khảo ở phần đầu trang.</p>}</fieldset>
  </div>
}

function ImageEditor({ value, onChange }: { value: StoryImage | null; onChange: (v: StoryImage | null) => void }) {
  return <details className="rounded-lg border border-slate-200 p-3"><summary className="cursor-pointer text-sm">Ảnh và ghi nguồn {value ? '(đã thêm)' : '(tùy chọn)'}</summary>{value ? <div className="mt-3 space-y-2">{([['url', 'URL ảnh (HTTPS hoặc /images/…)'], ['caption', 'Chú thích / mô tả ảnh'], ['credit', 'Tác giả, giấy phép'], ['source_url', 'Đường dẫn nguồn ảnh HTTPS']] as const).map(([key, label]) => <label className="block text-xs" key={key}>{label}<input className={field} value={value[key]} onChange={e => onChange({ ...value, [key]: e.target.value })} /></label>)}<button type="button" className={button} onClick={() => onChange(null)}>Bỏ ảnh</button></div> : <button type="button" className={button} onClick={() => onChange({ url: '', caption: '', credit: '', source_url: '' })}>Thêm ảnh có quyền sử dụng</button>}</details>
}

function Preview({ story }: { story: LandmarkStory }) {
  const renderImage = (image: StoryImage | null) => image && <figure className="space-y-1">{(image.url.startsWith('/images/') || image.url.startsWith('https://')) && <img src={image.url} alt={image.caption} className="max-h-56 rounded-lg object-cover" />}<figcaption className="text-xs text-slate-600">{image.caption} · <a href={image.source_url.startsWith('https://') ? image.source_url : undefined} target="_blank" rel="noreferrer">{image.credit}</a></figcaption></figure>

  const renderFact = (f: StoryFact) => <><p className="whitespace-pre-wrap text-sm">{f.text || 'Chưa có thông tin được xác nhận.'}</p><small className="text-amber-800">{f.status === 'unverified' ? 'Chưa xác minh' : 'Đã đối chiếu nguồn'}</small>{f.source_ids.map(id => { const s = story.sources.find(x => x.id === id); return s ? <a key={id} className="ml-2 text-xs text-blue-800 underline" href={s.url.startsWith('https://') ? s.url : undefined} target="_blank" rel="noreferrer">{s.title}</a> : null })}</>
  return <section className="space-y-5 rounded-xl border border-amber-200 bg-amber-50 p-5"><h2 className="font-semibold">Xem trước bản nháp — chưa công khai</h2><h3>Tổng quan</h3>{renderImage(story.image)}{renderFact(story.overview)}<h3>Lịch sử</h3><ol className="space-y-5 border-l-2 border-amber-500 pl-5">{[...story.timeline].sort((a,b) => a.year_start-b.year_start).map(e => <li key={e.id}><strong>{e.period} · {e.title}</strong>{renderFact(e)}{renderImage(e.image)}</li>)}</ol><h3>Kiến trúc</h3>{story.architecture.map((a,i) => <div key={i}><strong>{a.title}</strong>{renderFact(a)}</div>)}<h3>Tham quan</h3>{(['address','duration','hours','admission','notes'] as const).map(key => <div key={key}>{renderFact(story.visit[key])}</div>)}</section>
}

export function AdminLandmarkStoriesPage() {
  const [models, setModels] = useState<Model[]>([])
  const [selected, setSelected] = useState('')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [preview, setPreview] = useState(false)
  const [reload, setReload] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    http.get<Model[]>('/admin/landmark-stories', { signal: controller.signal }).then(({ data }) => { if (!controller.signal.aborted) { setModels(data); setSelected(data[0]?.model_id || '') } }).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)) })
    return () => controller.abort()
  }, [reload])
  useEffect(() => {
    if (!selected) return
    const controller = new AbortController()
    setDraft(null); setError(''); setNotice(''); setDirty(false)
    http.get<Draft>(`/admin/landmark-stories/${selected}`, { signal: controller.signal }).then(({ data }) => { if (!controller.signal.aborted) setDraft(data) }).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)) })
    return () => controller.abort()
  }, [selected, reload])
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = '' } }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  function update(content: LandmarkStory) { if (draft) { setDraft({ ...draft, content }); setDirty(true); setNotice('') } }
  async function persist(action: 'save' | 'submit' | 'publish' | 'unpublish') {
    if (!draft) return
    if (action === 'unpublish' && !window.confirm('Gỡ bản đang công khai? Bản nháp vẫn được giữ lại.')) return
    setBusy(true); setError(''); setNotice('')
    try {
      const url = `/admin/landmark-stories/${selected}`
      const { data } = action === 'save'
        ? await http.put<Draft>(url, { revision: draft.revision, content: draft.content })
        : await http.post<Draft>(`${url}/${action}`, { revision: draft.revision })
      setDraft(data); setDirty(false); setNotice(({ save: 'Đã lưu nháp. Bản công khai được giữ nguyên.', submit: 'Đã gửi duyệt. Kiểm tra bản xem trước trước khi xuất bản.', publish: 'Đã xuất bản lên bản đồ 3D.', unpublish: 'Đã gỡ bản công khai.' })[action])
    } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  const story = draft?.content
  return <main className="mx-auto max-w-5xl space-y-5 p-4 text-slate-900 sm:p-6"><header><h1 className="text-2xl font-bold">Câu chuyện địa danh 3D</h1><p className="text-sm text-slate-600">Biên soạn tổng quan, timeline và nguồn. Nội dung lịch sử không xác nhận khả năng đặt chỗ.</p></header>
    <label className="block">Địa danh<select className={field} value={selected} disabled={busy} onChange={e => { if (!dirty || window.confirm('Bỏ các chỉnh sửa chưa lưu để chuyển địa danh?')) { setSelected(e.target.value); setPreview(false) } }}>{models.map(m => <option value={m.model_id} key={m.model_id}>{m.display_name}</option>)}</select></label>
    {error && <div role="alert" className="rounded-lg bg-red-50 p-3 text-red-800">{error}<button className={`${button} ml-3`} onClick={() => { if (!dirty || window.confirm('Tải lại sẽ bỏ thay đổi chưa lưu?')) setReload(n => n+1) }}>Tải lại</button></div>}
    {notice && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-emerald-800">{notice}</p>}
    {draft && story ? <><div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3"><span className="mr-auto text-xs">Bản {draft.revision} · {({draft:'Nháp',review:'Chờ duyệt',published:'Đã xuất bản'} as Record<string,string>)[draft.workflow]}{dirty ? ' · Chưa lưu' : ''}</span>
      <button className={button} disabled={busy} onClick={() => setPreview(v => !v)}>{preview ? 'Tiếp tục sửa' : 'Xem trước'}</button>
      <button className={button} disabled={busy || !dirty} onClick={() => void persist('save')}>Lưu nháp</button>
      <button className={button} disabled={busy || dirty || !draft.revision || draft.workflow === 'review'} onClick={() => void persist('submit')}>Gửi duyệt</button>
      <button className={`${button} !bg-slate-800 !text-white`} disabled={busy || dirty || draft.workflow !== 'review' || !preview} onClick={() => void persist('publish')}>Duyệt & xuất bản</button>
      {draft.published && <button className={button} disabled={busy || dirty} onClick={() => void persist('unpublish')}>Gỡ công khai</button>}
    </div><p className="text-xs text-slate-500">Luồng: Lưu nháp → Gửi duyệt → Xem trước → Duyệt & xuất bản. Timeline hiển thị theo năm; thứ tự nhập dùng khi trùng năm.</p>
    {preview ? <Preview story={story} /> : <fieldset disabled={busy} className="space-y-6">
      <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4"><h2 className="font-bold">1. Nguồn tham khảo</h2>{story.sources.map((s,i) => <div key={s.id} className="grid gap-2 rounded-lg bg-slate-50 p-3 sm:grid-cols-2"><label className="text-xs">Tên nguồn<input className={field} value={s.title} onChange={e => update({ ...story, sources: story.sources.map((x,j) => j === i ? { ...x, title:e.target.value } : x) })} /></label><label className="text-xs">URL HTTPS<input className={field} value={s.url} onChange={e => update({ ...story, sources:story.sources.map((x,j) => j === i ? {...x,url:e.target.value} : x) })} /></label><label className="text-xs">Ngày đối chiếu<input type="date" className={field} value={s.accessed_on} onChange={e => update({...story,sources:story.sources.map((x,j) => j === i ? {...x,accessed_on:e.target.value} : x)})} /></label><span className="self-end text-xs text-slate-500">Mã nguồn: {s.id}</span></div>)}<button className={button} onClick={() => update({...story,sources:[...story.sources,{id:crypto.randomUUID(),title:'',url:'',accessed_on:new Date().toISOString().slice(0,10)}]})}>+ Thêm nguồn</button></section>
      <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4"><h2 className="font-bold">2. Tổng quan</h2><FactEditor label="Giới thiệu ngắn" value={story.overview} sources={story.sources} onChange={v => update({...story,overview:v})} /><ImageEditor value={story.image} onChange={v => update({...story,image:v})} /></section>
      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4"><h2 className="font-bold">3. Timeline lịch sử</h2>{story.timeline.map((event,i) => <article key={event.id} className="space-y-3 rounded-xl border border-slate-200 p-4"><div className="flex gap-2"><strong className="mr-auto">Mốc {i+1}</strong><button className={button} disabled={!i} onClick={() => {const items=[...story.timeline]; [items[i-1],items[i]]=[items[i],items[i-1]]; update({...story,timeline:items})}}>↑</button><button className={button} disabled={i===story.timeline.length-1} onClick={() => {const items=[...story.timeline]; [items[i+1],items[i]]=[items[i],items[i+1]]; update({...story,timeline:items})}}>↓</button><button className={button} onClick={() => update({...story,timeline:story.timeline.filter((_,j) => i!==j)})}>Bỏ mốc</button></div>
        {(['title','period'] as const).map(k => <label key={k} className="block text-xs">{k==='title'?'Tên sự kiện':'Ngày, năm hoặc giai đoạn hiển thị'}<input className={field} value={event[k]} onChange={e => update({...story,timeline:story.timeline.map((x,j) => i===j?{...x,[k]:e.target.value}:x)})} /></label>)}
        <div className="grid grid-cols-2 gap-2">{(['year_start','year_end'] as const).map(k => <label key={k} className="text-xs">{k==='year_start'?'Năm bắt đầu (sắp xếp)':'Năm kết thúc (tùy chọn)'}<input type="number" min={1} max={2200} className={field} value={event[k]??''} onChange={e => update({...story,timeline:story.timeline.map((x,j) => i===j?{...x,[k]:e.target.value?Number(e.target.value):null}:x)})} /></label>)}</div>
        <FactEditor label="Nội dung mốc" value={event} sources={story.sources} onChange={v => update({...story,timeline:story.timeline.map((x,j) => i===j?{...x,...v}:x)})} /><ImageEditor value={event.image} onChange={v => update({...story,timeline:story.timeline.map((x,j) => i===j?{...x,image:v}:x)})} /></article>)}<button className={button} onClick={() => update({...story,timeline:[...story.timeline,{...fact(),id:crypto.randomUUID(),title:'',period:'',year_start:1900,year_end:null,image:null}]})}>+ Thêm mốc lịch sử</button></section>
      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4"><h2 className="font-bold">4. Kiến trúc & câu chuyện</h2>{story.architecture.map((a,i) => <article className="space-y-2 border-b pb-4" key={i}><label className="text-xs">Tiêu đề<input className={field} value={a.title} onChange={e => update({...story,architecture:story.architecture.map((x,j) => i===j?{...x,title:e.target.value}:x)})} /></label><FactEditor label="Mô tả" value={a} sources={story.sources} onChange={v => update({...story,architecture:story.architecture.map((x,j) => i===j?{...x,...v}:x)})} /><label className="text-xs">Góc nhìn mô hình<select className={field} value={a.view??''} onChange={e => update({...story,architecture:story.architecture.map((x,j) => i===j?{...x,view:(e.target.value||null) as CameraView|null}:x)})}><option value="">Không gắn góc nhìn</option><option value="front">Mặt tiền</option><option value="top">Trên cao</option><option value="park">Từ công viên</option><option value="cinematic">Toàn cảnh</option></select></label><button className={button} onClick={() => update({...story,architecture:story.architecture.filter((_,j) => i!==j)})}>Bỏ chi tiết</button></article>)}<button className={button} onClick={() => update({...story,architecture:[...story.architecture,{...fact(),title:'',view:null}]})}>+ Thêm chi tiết</button></section>
      <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4"><h2 className="font-bold">5. Tham quan</h2>{([['address','Địa chỉ'],['duration','Thời lượng tham khảo'],['hours','Giờ tham quan'],['admission','Giá vé'],['notes','Lưu ý']] as const).map(([key,label]) => <FactEditor key={key} label={label} value={story.visit[key]} sources={story.sources} onChange={v => update({...story,visit:{...story.visit,[key]:v}})} />)}<label className="block text-xs">Ngày xác nhận thông tin tham quan<input type="date" className={field} value={story.visit.checked_on??''} onChange={e => update({...story,visit:{...story.visit,checked_on:e.target.value||null}})} /></label></section>
    </fieldset>}</> : !error && <p role="status">Đang tải nội dung…</p>}
  </main>
}
