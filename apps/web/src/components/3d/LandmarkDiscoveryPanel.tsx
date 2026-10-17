import { useEffect, useRef, useState } from 'react'
import { BookOpen, ChevronDown, MapPin, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { CameraView, LandmarkStory, StoryFact, StoryImage, StoryResponse } from '../../types/landmarkStory'
import type { ModelCalibration } from './landmark/types'
import './landmarkDiscovery.css'

function ImageCredit({ image }: { image: StoryImage }) {
  const [failed, setFailed] = useState(false)
  return <figure>{!failed && <img src={image.url} alt={image.caption} loading="lazy" onError={() => setFailed(true)} />}
    <figcaption>{failed ? 'Không tải được ảnh. ' : ''}{image.caption} · <a href={image.source_url} target="_blank" rel="noopener noreferrer">{image.credit}</a></figcaption></figure>
}

export function StoryFactView({ fact, story }: { fact: StoryFact; story: LandmarkStory }) {
  return <div className="heritage-fact"><p>{fact.text || 'Chưa có thông tin được xác nhận.'}</p>
    {fact.status === 'unverified' && <span className="heritage-unverified">Chưa xác minh</span>}
    <div className="heritage-citations">{fact.source_ids.map(id => {
      const source = story.sources.find(s => s.id === id)
      return source ? <a key={id} href={source.url} target="_blank" rel="noopener noreferrer">{source.title} ↗</a> : null
    })}</div></div>
}

export function LandmarkDiscoveryPanel({ modelId, landmark, open, onOpen, onClose, onView }: {
  modelId: string; landmark: ModelCalibration; open: boolean; onOpen: () => void; onClose: () => void; onView: (view: CameraView) => void
}) {
  const [result, setResult] = useState<StoryResponse | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [section, setSection] = useState('overview')
  const [allEvents, setAllEvents] = useState(false)
  const [poiId, setPoiId] = useState<string | null>(null)
  const titleRef = useRef<HTMLHeadingElement>(null)
  const launchRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const controller = new AbortController()
    setResult(null); setError(false); setSection('overview'); setAllEvents(false); setPoiId(null)
    api.get<StoryResponse>(`/landmark-stories/${encodeURIComponent(modelId)}`, { signal: controller.signal })
      .then(({ data }) => { if (!controller.signal.aborted) setResult(data) })
      .catch(() => { if (!controller.signal.aborted) setError(true) })
    api.get<{ poi_id: string | null }>(`/journey/landmarks/${encodeURIComponent(modelId)}`, { signal: controller.signal })
      .then(({ data }) => { if (!controller.signal.aborted) setPoiId(data.poi_id) }).catch(() => {})
    return () => controller.abort()
  }, [modelId, attempt])

  useEffect(() => { if (open) titleRef.current?.focus({ preventScroll: true }) }, [open, modelId])
  function close() { onClose(); requestAnimationFrame(() => launchRef.current?.focus()) }
  const story = result?.content
  const events = [...(story?.timeline || [])].sort((a, b) => a.year_start - b.year_start)
  return <aside className={`heritage-panel ${open ? 'is-open' : 'is-closed'}`} aria-label={`Khám phá ${landmark.display_name}`} onKeyDown={e => { if (e.key === 'Escape' && open) { e.stopPropagation(); close() } }}>
    {!open ? <button ref={launchRef} className="heritage-launch" onClick={onOpen} aria-expanded={false} aria-controls="heritage-content"><BookOpen size={20} /><span><strong>{landmark.display_name}</strong><small>Tổng quan · Lịch sử · Tham quan</small></span><ChevronDown size={16} /></button> : <>
      <header className="heritage-header"><div><span className="heritage-eyebrow">KHÁM PHÁ DI SẢN</span><h2 ref={titleRef} tabIndex={-1}>{landmark.display_name}</h2></div>
        <button onClick={close} title="Đóng thẻ thông tin" aria-label="Đóng thẻ thông tin"><X size={20} /></button></header>
      <nav className="heritage-tabs" aria-label="Nội dung địa điểm">{[['overview', 'Tổng quan'], ['history', 'Lịch sử'], ['architecture', 'Kiến trúc'], ['visit', 'Tham quan']].map(([key, label]) => <button key={key} aria-pressed={section === key} onClick={() => setSection(key)}>{label}</button>)}</nav>
      <div id="heritage-content" className="heritage-body" key={`${modelId}-${section}`}>
        {error ? <div role="alert"><p>Chưa tải được thông tin địa điểm.</p><button className="heritage-action" onClick={() => setAttempt(n => n + 1)}>Thử lại</button></div> : !result ? <p role="status">Đang tải câu chuyện địa điểm…</p> : !story ? <div><h3>Câu chuyện đang được biên soạn</h3><p>Địa điểm này chưa có nội dung được xuất bản. Bạn vẫn có thể xem mô hình và vị trí bên dưới.</p></div> : <>
          {section === 'overview' && <>{story.image && <ImageCredit key={story.image.url} image={story.image} />}<StoryFactView fact={story.overview} story={story} /><div className="heritage-summary"><strong>{events.length} mốc lịch sử</strong><span>{story.architecture.length} góc khám phá</span></div><button className="heritage-action" onClick={() => setSection('history')}>Khám phá dòng thời gian →</button><p className="heritage-note">Thông tin lịch sử có nguồn không đồng nghĩa với xác nhận giờ mở cửa hoặc khả năng đặt chỗ.</p></>}
          {section === 'history' && <><h3>Dòng thời gian hình thành</h3><p className="heritage-note">Mốc được sắp theo thời gian. Mô hình 3D minh họa hiện tại, không tái dựng từng thời kỳ.</p>{events.length ? <ol className="heritage-timeline">{(allEvents ? events : events.slice(0, 3)).map(item => <li key={item.id}><span className="heritage-period">{item.period}</span><h4>{item.title}</h4><StoryFactView fact={item} story={story} />{item.image && <ImageCredit key={item.image.url} image={item.image} />}</li>)}</ol> : <p>Chưa có mốc lịch sử được biên soạn.</p>}{events.length > 3 && <button className="heritage-action" aria-expanded={allEvents} onClick={() => setAllEvents(v => !v)}>{allEvents ? 'Thu gọn lịch sử' : `Xem toàn bộ ${events.length} mốc lịch sử`}</button>}</>}
          {section === 'architecture' && <><h3>Kiến trúc & câu chuyện</h3>{story.architecture.length ? story.architecture.map((item, i) => <section className="heritage-detail" key={i}><h4>{item.title}</h4><StoryFactView fact={item} story={story} />{item.view && <button className="heritage-action" onClick={() => onView(item.view!)}>Xem góc nhìn trên mô hình ↗</button>}</section>) : <p>Chưa có chi tiết kiến trúc được biên soạn.</p>}</>}
          {section === 'visit' && <><h3>Chuẩn bị chuyến tham quan</h3>{([['address', 'Địa chỉ'], ['duration', 'Thời lượng tham khảo'], ['hours', 'Giờ tham quan'], ['admission', 'Giá vé'], ['notes', 'Lưu ý']] as const).map(([key, label]) => <section key={key} className="heritage-detail"><h4>{label}</h4><StoryFactView fact={story.visit[key]} story={story} /></section>)}<p className="heritage-note">{story.visit.checked_on ? `Ngày đối chiếu thông tin: ${story.visit.checked_on}` : 'Chưa có ngày xác nhận thông tin tham quan.'} Hãy kiểm tra lại với đơn vị quản lý trước chuyến đi.</p></>}
          <details className="heritage-sources"><summary>Nguồn tham khảo ({story.sources.length})</summary>{story.sources.map(s => <p key={s.id}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.title} ↗</a><small>Đối chiếu ngày {s.accessed_on}</small></p>)}</details>
        </>}
      </div>
      <footer className="heritage-footer"><a href={`https://www.google.com/maps/dir/?api=1&destination=${landmark.latitude},${landmark.longitude}`} target="_blank" rel="noopener noreferrer"><MapPin size={14} /> Chỉ đường</a><Link to={poiId ? `/explore?poi_id=${encodeURIComponent(poiId)}` : '/explore'}>{poiId ? 'Chọn trải nghiệm để lên lịch →' : 'Khám phá các trải nghiệm →'}</Link></footer>
    </>}
  </aside>
}
