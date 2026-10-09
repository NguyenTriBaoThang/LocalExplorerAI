import { useEffect, useState, type FormEvent } from 'react'
import { Brain, CheckCircle2, RefreshCw, Sparkles } from 'lucide-react'
import { adminApi, apiErrorMessage, mlApi } from '../api/client'

type TargetSet = {
  experiences: Array<{ id: string; title: string }>
  itineraries: Array<{ id: string; planned_date: string | null; created_at: string }>
}
type PromptManifest = { suite: string; version: string; prd_version: string; effective_date: string; prompt_ids: string[] }
type LocalModelStatus = {
  configured: boolean
  loaded: boolean
  deployment_allowed: boolean
  model_version: string | null
  active_version?: string | null
  active_ranker?: string
  fallback_active?: boolean
  block_reason: string | null
  dataset_status?: string
}
type ToolKey = 'tag' | 'similarity' | 'weather'

export function AdminAiToolsPanel() {
  const [targets, setTargets] = useState<TargetSet>({ experiences: [], itineraries: [] })
  const [manifest, setManifest] = useState<PromptManifest | null>(null)
  const [modelStatus, setModelStatus] = useState<{ experience_ranker: LocalModelStatus; flood_risk_model: LocalModelStatus } | null>(null)
  const [tool, setTool] = useState<ToolKey>('tag')
  const [experienceId, setExperienceId] = useState('')
  const [experienceA, setExperienceA] = useState('')
  const [experienceB, setExperienceB] = useState('')
  const [itineraryId, setItineraryId] = useState('')
  const [additionalContext, setAdditionalContext] = useState('')
  const [rain, setRain] = useState('')
  const [aqi, setAqi] = useState('')
  const [temperature, setTemperature] = useState('')
  const [children, setChildren] = useState(false)
  const [observedAt, setObservedAt] = useState('')
  const [result, setResult] = useState<unknown>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function loadTargets() {
    setLoading(true)
    setError('')
    try {
      const [targetData, promptData, modelData] = await Promise.all([adminApi.aiTargets(), adminApi.promptCatalog(), mlApi.status()])
      const nextTargets = targetData as TargetSet
      setTargets(nextTargets)
      setManifest(promptData as PromptManifest)
      setModelStatus(modelData as { experience_ranker: LocalModelStatus; flood_risk_model: LocalModelStatus })
      setExperienceId((current) => current || nextTargets.experiences[0]?.id || '')
      setExperienceA((current) => current || nextTargets.experiences[0]?.id || '')
      setExperienceB((current) => current || nextTargets.experiences[1]?.id || '')
      setItineraryId((current) => current || nextTargets.itineraries[0]?.id || '')
    } catch (reason) {
      setError(apiErrorMessage(reason))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void loadTargets() }, [])

  async function run(event: FormEvent) {
    event.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      let response: unknown
      if (tool === 'tag') {
        response = await adminApi.tagExperience(experienceId, additionalContext)
      } else if (tool === 'similarity') {
        response = await adminApi.compareIntent(experienceA, experienceB)
      } else {
        response = await adminApi.weatherAdvisory(itineraryId, {
          rain_mm_per_hour: Number(rain),
          aqi_pm25: Number(aqi),
          temperature_c: Number(temperature),
          children_in_group: children,
          observed_at: new Date(observedAt).toISOString(),
        })
      }
      setResult(response)
    } catch (reason) {
      setError(apiErrorMessage(reason))
    } finally {
      setLoading(false)
    }
  }

  const toolOptions: Array<[ToolKey, string]> = [
    ['tag', 'Gán nhãn trải nghiệm'],
    ['similarity', 'So sánh mục đích'],
    ['weather', 'Tư vấn thời tiết'],
  ]

  return (
    <div className="admin-tab-content animate-fadeIn">
      <div className="page-title-row-3d">
        <div>
          <h2 className="section-title-3d"><Brain size={19} /> Công cụ AI quản trị</h2>
          <p className="page-subtext-3d">Chạy các workflow có cấu trúc; những thao tác thay đổi dữ liệu sẽ ghi kết quả vào hệ thống.</p>
        </div>
        <button type="button" className="btn-secondary-3d" onClick={() => void loadTargets()} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} /> Tải mục tiêu
        </button>
      </div>

      {manifest && (
        <section className="admin-section-card" style={{ marginBottom: 18 }}>
          <div className="admin-section-header">
            <h3><Sparkles size={17} /> Bộ prompt {manifest.version} · PRD {manifest.prd_version}</h3>
            <p>{manifest.prompt_ids.length} prompt · hiệu lực {manifest.effective_date}. Chỉ hiện metadata; prompt hệ thống không được gửi ra trình duyệt.</p>
          </div>
          <div className="item-sub-meta">{manifest.prompt_ids.map((id) => <span key={id}>{id}</span>)}</div>
        </section>
      )}

      {modelStatus && (
        <section className="admin-section-card" style={{ marginBottom: 18 }}>
          <div className="admin-section-header"><h3>Trạng thái model local</h3><p>Baseline quy tắc sẽ xếp hạng khi chưa có ML đủ điều kiện; model nhãn yếu không được triển khai.</p></div>
          <div className="admin-metrics-grid">
            {([['Ranker trải nghiệm', modelStatus.experience_ranker], ['Dự đoán ngập', modelStatus.flood_risk_model]] as const).map(([name, model]) => (
              <div className="admin-kpi-card" key={name}>
                <small>{name}</small>
                <strong>{model.active_ranker === 'rule_baseline' ? 'Baseline quy tắc đang hoạt động' : model.deployment_allowed ? 'Sẵn sàng' : 'Chưa sẵn sàng'}</strong>
                <span>{model.active_version || model.model_version || model.block_reason || 'Chưa có artifact'}</span>
                {model.active_ranker === 'rule_baseline' && model.block_reason && <small>{model.block_reason}</small>}
                {model.dataset_status && <small>Dataset: {model.dataset_status}</small>}
              </div>
            ))}
          </div>
        </section>
      )}

      {error && <div className="inline-alert-3d" role="alert"><span>{error}</span></div>}
      {targets.experiences.length === 0 && <div className="inline-alert-3d"><span>Chưa có trải nghiệm trong catalog để chạy các công cụ AI.</span></div>}

      <div className="admin-tab-strip" role="tablist" aria-label="Công cụ AI">
        {toolOptions.map(([key, label]) => (
          <button type="button" role="tab" aria-selected={tool === key} key={key}
            className={`admin-tab-btn ${tool === key ? 'admin-tab-active' : ''}`}
            onClick={() => { setTool(key); setResult(null); setError('') }}>
            {label}
          </button>
        ))}
      </div>

      <section className="admin-section-card">
        {tool === 'tag' && (
          <form className="form-fields-grid-2" onSubmit={(event) => void run(event)}>
            <div className="admin-section-header" style={{ gridColumn: '1 / -1' }}><h3>EXPERIENCE_TAGGER</h3><p>Phân loại mục đích, indoor/outdoor và hands-on. Kết quả được ghi vào trải nghiệm.</p></div>
            <label className="field-group-3d"><span>Trải nghiệm</span><select required value={experienceId} onChange={(event) => setExperienceId(event.target.value)}><option value="" disabled>Chọn trải nghiệm</option>{targets.experiences.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
            <label className="field-group-3d"><span>Ngữ cảnh bổ sung (nếu có)</span><input value={additionalContext} onChange={(event) => setAdditionalContext(event.target.value)} maxLength={2000} /></label>
            <button className="btn-primary-3d" type="submit" disabled={loading || !experienceId}><Sparkles size={15} /> Phân tích & cập nhật</button>
          </form>
        )}

        {tool === 'similarity' && (
          <form className="form-fields-grid-2" onSubmit={(event) => void run(event)}>
            <div className="admin-section-header" style={{ gridColumn: '1 / -1' }}><h3>INTENT_SIMILARITY</h3><p>So sánh mục đích và lưu cặp kết quả để phục vụ re-plan.</p></div>
            <label className="field-group-3d"><span>Trải nghiệm A</span><select required value={experienceA} onChange={(event) => setExperienceA(event.target.value)}><option value="" disabled>Chọn trải nghiệm A</option>{targets.experiences.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
            <label className="field-group-3d"><span>Trải nghiệm B</span><select required value={experienceB} onChange={(event) => setExperienceB(event.target.value)}><option value="" disabled>Chọn trải nghiệm B</option>{targets.experiences.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
            <button className="btn-primary-3d" type="submit" disabled={loading || !experienceA || !experienceB || experienceA === experienceB}>Tính tương đồng</button>
          </form>
        )}

        {tool === 'weather' && (
          <form className="form-fields-grid-2" onSubmit={(event) => void run(event)}>
            <div className="admin-section-header" style={{ gridColumn: '1 / -1' }}><h3>WEATHER_AQI_ADVISOR</h3><p>Dùng số liệu do quản trị viên nhập; không tự coi mưa là ngập. Kết quả có thể tạo sự kiện cảnh báo thời tiết cho điểm ngoài trời.</p></div>
            <label className="field-group-3d"><span>Lịch trình</span><select required value={itineraryId} onChange={(event) => setItineraryId(event.target.value)}><option value="" disabled>Chọn lịch trình</option>{targets.itineraries.map((item) => <option key={item.id} value={item.id}>{item.id.slice(0, 12)} · {item.planned_date || new Date(item.created_at).toLocaleDateString('vi-VN')}</option>)}</select></label>
            <label className="field-group-3d"><span>Mưa (mm/giờ)</span><input type="number" required min="0" max="500" step="0.1" value={rain} onChange={(event) => setRain(event.target.value)} /></label>
            <label className="field-group-3d"><span>AQI PM2.5</span><input type="number" required min="0" max="1000" value={aqi} onChange={(event) => setAqi(event.target.value)} /></label>
            <label className="field-group-3d"><span>Nhiệt độ (°C)</span><input type="number" required min="-20" max="60" step="0.1" value={temperature} onChange={(event) => setTemperature(event.target.value)} /></label>
            <label className="field-group-3d"><span>Thời điểm quan sát</span><input type="datetime-local" required value={observedAt} onChange={(event) => setObservedAt(event.target.value)} /></label>
            <label className="field-group-3d" style={{ alignSelf: 'end' }}><span><input type="checkbox" checked={children} onChange={(event) => setChildren(event.target.checked)} /> Có trẻ nhỏ trong nhóm</span></label>
            <button className="btn-primary-3d" type="submit" disabled={loading || !itineraryId}>Tạo tư vấn & cảnh báo</button>
          </form>
        )}
      </section>

      <div className="inline-alert-3d" style={{ marginTop: 18 }}>
        <span>FEEDBACK_LABELER có API nhưng chưa mở thao tác trên giao diện. Cần xác nhận riêng trước khi gửi review thật của khách tới nhà cung cấp AI bên ngoài.</span>
      </div>

      {Boolean(result) && <section className="admin-section-card" style={{ marginTop: 18 }}><div className="admin-section-header"><h3><CheckCircle2 size={17} /> Kết quả</h3></div><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(result, null, 2)}</pre></section>}
    </div>
  )
}
