import { useEffect, useState, type FormEvent } from 'react'
import { Brain, CheckCircle2, RefreshCw, Sparkles } from 'lucide-react'
import { Alert, Badge, Button, Card, CardHeader, Field, Input, Modal, PageHeader, Select, Tabs, useToast } from '../../components/ui'
import { errorMessage } from '../../lib/api'
import { adminAiApi, type AiTargetSet, type MlStatus, type PromptManifest, modelMessage } from '../../lib/adminAi'

type ToolKey = 'tag' | 'similarity' | 'weather'

export function AdminAiToolsPage() {
  const toast = useToast()
  const [targets, setTargets] = useState<AiTargetSet>({ experiences: [], itineraries: [] })
  const [manifest, setManifest] = useState<PromptManifest | null>(null)
  const [modelStatus, setModelStatus] = useState<MlStatus | null>(null)
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
  const [loadErrors, setLoadErrors] = useState<string[]>([])
  const [confirmTag, setConfirmTag] = useState(false)

  async function loadTargets() {
    setLoading(true)
    setLoadErrors([])
    const [targetRes, promptRes, modelRes] = await Promise.allSettled([adminAiApi.targets(), adminAiApi.promptCatalog(), adminAiApi.mlStatus()])
    const failures: string[] = []
    if (targetRes.status === 'fulfilled') {
      const targetData = targetRes.value
      setTargets(targetData)
      setExperienceId((current) => current || targetData.experiences[0]?.id || '')
      setExperienceA((current) => current || targetData.experiences[0]?.id || '')
      setExperienceB((current) => current || targetData.experiences[1]?.id || '')
      setItineraryId((current) => current || targetData.itineraries[0]?.id || '')
    } else failures.push(`Danh sách mục tiêu: ${errorMessage(targetRes.reason)}`)
    if (promptRes.status === 'fulfilled') setManifest(promptRes.value)
    else failures.push(`Bộ prompt: ${errorMessage(promptRes.reason)}`)
    if (modelRes.status === 'fulfilled') setModelStatus(modelRes.value)
    else failures.push(`Trạng thái model: ${errorMessage(modelRes.reason)}`)
    setLoadErrors(failures)
    setLoading(false)
  }

  useEffect(() => { void loadTargets() }, [])

  function submitTool(event: FormEvent) {
    event.preventDefault()
    if (tool === 'weather' && Number.isNaN(new Date(observedAt).getTime())) {
      setError('Thời điểm quan sát không hợp lệ. Hãy chọn lại ngày giờ.')
      return
    }
    setConfirmTag(true)
  }

  async function run() {
    setError('')
    setResult(null)
    if (tool === 'weather' && Number.isNaN(new Date(observedAt).getTime())) {
      setError('Thời điểm quan sát không hợp lệ. Hãy chọn lại ngày giờ.')
      return
    }
    setLoading(true)
    try {
      let response: unknown
      if (tool === 'tag') {
        response = await adminAiApi.tagExperience(experienceId, additionalContext)
      } else if (tool === 'similarity') {
        response = await adminAiApi.compareIntent(experienceA, experienceB)
      } else {
        response = await adminAiApi.weatherAdvisory(itineraryId, {
          rain_mm_per_hour: Number(rain),
          aqi_pm25: Number(aqi),
          temperature_c: Number(temperature),
          children_in_group: children,
          observed_at: new Date(observedAt).toISOString(),
        })
      }
      setResult(response)
      toast.success('Đã chạy công cụ AI.')
    } catch (reason) {
      setError(errorMessage(reason))
    } finally {
      setLoading(false)
    }
  }

  const experienceOptions = (placeholder: string) => (
    <>
      <option value="" disabled>{placeholder}</option>
      {targets.experiences.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
    </>
  )

  return (
    <>
      <PageHeader title="Công cụ AI quản trị" description="Chạy các workflow có cấu trúc; những thao tác thay đổi dữ liệu sẽ ghi kết quả vào hệ thống."
        actions={<Button variant="secondary" icon={RefreshCw} onClick={() => void loadTargets()} loading={loading}>Tải mục tiêu</Button>} />

      <div className="space-y-6">
        {manifest && (
          <Card>
            <CardHeader title={<span className="inline-flex items-center gap-2"><Sparkles className="h-4 w-4 text-brand-600" /> Bộ prompt {manifest.version} · PRD {manifest.prd_version}</span>}
              description={`${manifest.prompt_ids.length} prompt · hiệu lực ${manifest.effective_date}. Chỉ hiện metadata; prompt hệ thống không được gửi ra trình duyệt.`} />
            <div className="flex flex-wrap gap-2 p-5">{manifest.prompt_ids.map((id) => <Badge key={id}>{id}</Badge>)}</div>
          </Card>
        )}

        {modelStatus && (
          <Card>
            <CardHeader title="Trạng thái model local" description="Model chưa được triển khai sẽ không sinh điểm dự đoán." />
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              {([['Ranker trải nghiệm', modelStatus.experience_ranker], ['Dự đoán ngập', modelStatus.flood_risk_model]] as const).map(([name, model]) => (
                <div key={name} className="rounded-xl border border-slate-200 p-4">
                  <p className="text-xs text-slate-500">{name}</p>
                  <p className="mt-1 text-base font-semibold text-slate-900">{model.deployment_allowed ? 'Sẵn sàng' : 'Chưa sẵn sàng'}</p>
                  <p className="mt-1 text-sm text-slate-600">{model.model_version || modelMessage(model.block_reason) || 'Chưa có artifact'}</p>
                  {model.dataset_status && <p className="mt-1 text-xs text-slate-500">Dataset: {model.dataset_status}</p>}
                </div>
              ))}
            </div>
          </Card>
        )}

        {loadErrors.length > 0 && (
          <Alert tone="red" title="Không tải được một phần dữ liệu"
            action={<Button size="sm" variant="secondary" icon={RefreshCw} loading={loading} onClick={() => void loadTargets()}>Thử lại</Button>}>
            <ul className="list-disc pl-4">{loadErrors.map((message) => <li key={message}>{message}</li>)}</ul>
          </Alert>
        )}
        {error && <Alert tone="red">{error}</Alert>}
        {targets.experiences.length === 0 && !loading && <Alert tone="amber">Chưa có trải nghiệm trong catalog để chạy các công cụ AI.</Alert>}

        <Tabs value={tool} onChange={(key) => { setTool(key); setResult(null); setError('') }}
          items={[{ value: 'tag', label: 'Gán nhãn trải nghiệm' }, { value: 'similarity', label: 'So sánh mục đích' }, { value: 'weather', label: 'Tư vấn thời tiết' }]} />

        <Card>
          {tool === 'tag' && (
            <form className="grid gap-4 p-5 sm:grid-cols-2" onSubmit={submitTool}>
              <div className="sm:col-span-2"><h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Brain className="h-4 w-4" /> EXPERIENCE_TAGGER</h3>
                <p className="text-sm text-slate-500">Phân loại mục đích, indoor/outdoor và hands-on. Kết quả được ghi vào trải nghiệm.</p></div>
              <Field label="Trải nghiệm"><Select required value={experienceId} onChange={(event) => setExperienceId(event.target.value)}>{experienceOptions('Chọn trải nghiệm')}</Select></Field>
              <Field label="Ngữ cảnh bổ sung (nếu có)"><Input value={additionalContext} onChange={(event) => setAdditionalContext(event.target.value)} maxLength={2000} /></Field>
              <div className="sm:col-span-2"><Button type="submit" icon={Sparkles} loading={loading} disabled={!experienceId}>Phân tích & cập nhật</Button></div>
            </form>
          )}

          {tool === 'similarity' && (
            <form className="grid gap-4 p-5 sm:grid-cols-2" onSubmit={submitTool}>
              <div className="sm:col-span-2"><h3 className="text-sm font-semibold text-slate-900">INTENT_SIMILARITY</h3>
                <p className="text-sm text-slate-500">So sánh mục đích và lưu cặp kết quả để phục vụ re-plan.</p></div>
              <Field label="Trải nghiệm A"><Select required value={experienceA} onChange={(event) => setExperienceA(event.target.value)}>{experienceOptions('Chọn trải nghiệm A')}</Select></Field>
              <Field label="Trải nghiệm B"><Select required value={experienceB} onChange={(event) => setExperienceB(event.target.value)}>{experienceOptions('Chọn trải nghiệm B')}</Select></Field>
              <div className="sm:col-span-2"><Button type="submit" loading={loading} disabled={!experienceA || !experienceB || experienceA === experienceB}>Tính tương đồng</Button></div>
            </form>
          )}

          {tool === 'weather' && (
            <form className="grid gap-4 p-5 sm:grid-cols-2" onSubmit={submitTool}>
              <div className="sm:col-span-2"><h3 className="text-sm font-semibold text-slate-900">WEATHER_AQI_ADVISOR</h3>
                <p className="text-sm text-slate-500">Dùng số liệu do quản trị viên nhập; không tự coi mưa là ngập. Kết quả có thể tạo sự kiện cảnh báo thời tiết cho điểm ngoài trời.</p></div>
              <Field label="Lịch trình">
                <Select required value={itineraryId} onChange={(event) => setItineraryId(event.target.value)}>
                  <option value="" disabled>Chọn lịch trình</option>
                  {targets.itineraries.map((item) => <option key={item.id} value={item.id}>{item.id.slice(0, 12)} · {item.planned_date || new Date(item.created_at).toLocaleDateString('vi-VN')}</option>)}
                </Select>
              </Field>
              <Field label="Mưa (mm/giờ)"><Input type="number" required min="0" max="500" step="0.1" value={rain} onChange={(event) => setRain(event.target.value)} /></Field>
              <Field label="AQI PM2.5"><Input type="number" required min="0" max="1000" value={aqi} onChange={(event) => setAqi(event.target.value)} /></Field>
              <Field label="Nhiệt độ (°C)"><Input type="number" required min="-20" max="60" step="0.1" value={temperature} onChange={(event) => setTemperature(event.target.value)} /></Field>
              <Field label="Thời điểm quan sát"><Input type="datetime-local" required value={observedAt} onChange={(event) => setObservedAt(event.target.value)} /></Field>
              <label className="flex items-center gap-2 self-end pb-2 text-sm text-slate-700">
                <input type="checkbox" checked={children} onChange={(event) => setChildren(event.target.checked)} /> Có trẻ nhỏ trong nhóm
              </label>
              <div className="sm:col-span-2"><Button type="submit" loading={loading} disabled={!itineraryId}>Tạo tư vấn & cảnh báo</Button></div>
            </form>
          )}
        </Card>

        <Modal open={confirmTag} onClose={() => setConfirmTag(false)} title="Xác nhận ghi dữ liệu"
          description="Công cụ này sẽ ghi vào dữ liệu thật."
          footer={<>
            <Button variant="secondary" onClick={() => setConfirmTag(false)}>Hủy</Button>
            <Button onClick={() => { setConfirmTag(false); void run() }}>Xác nhận và chạy</Button>
          </>}>
          <p className="text-sm text-slate-700">
            {tool === 'tag'
              ? `Metadata của trải nghiệm “${targets.experiences.find((item) => item.id === experienceId)?.title || experienceId}” (mục đích, indoor/outdoor, hands-on) sẽ bị ghi đè bằng kết quả AI.`
              : tool === 'similarity'
                ? 'Cặp kết quả tương đồng mục đích sẽ được lưu vào hệ thống và có thể ghi đè kết quả cũ của cặp này.'
                : 'Kết quả có thể tạo sự kiện cảnh báo thời tiết gắn với lịch trình và các điểm ngoài trời.'}
            {' '}Bạn có chắc chắn muốn tiếp tục?
          </p>
        </Modal>

        <Alert tone="brand">FEEDBACK_LABELER có API nhưng chưa mở thao tác trên giao diện. Cần xác nhận riêng trước khi gửi review thật của khách tới nhà cung cấp AI bên ngoài.</Alert>

        {Boolean(result) && (
          <Card>
            <CardHeader title={<span className="inline-flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-600" /> Kết quả</span>} />
            <pre className="overflow-x-auto whitespace-pre-wrap break-words p-5 text-xs text-slate-700">{JSON.stringify(result, null, 2)}</pre>
          </Card>
        )}
      </div>
    </>
  )
}
