import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { AlertTriangle, Download, MapPinned, RefreshCw, Upload } from 'lucide-react'
import { Alert, Badge, Button, Card, CardHeader, EmptyState, PageHeader } from '../../components/ui'
import { errorMessage } from '../../lib/api'
import { adminAiApi, type FloodModelStatus, type FloodPrediction, type FloodSample } from '../../lib/adminAi'

type GeoSample = { latitude: number; longitude: number; sample: FloodSample }

const numericFeatures = [
  'rain_15m_mm', 'rain_30m_mm', 'rain_60m_mm', 'rain_180m_mm',
  'rain_forecast_15m_mm', 'rain_forecast_30m_mm', 'rain_forecast_60m_mm',
  'elevation_m', 'slope_pct', 'depression_index', 'distance_to_canal_m',
  'tide_level_m', 'tide_change_30m_m', 'drainage_density_km2', 'road_width_m',
  'nearby_flood_reports_30m', 'latest_depth_cm', 'observation_age_min', 'coverage_ratio',
] as const

function parseCsv(text: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index]
    if (char === '"' && quoted && text[index + 1] === '"') { cell += '"'; index += 1 }
    else if (char === '"') quoted = !quoted
    else if (char === ',' && !quoted) { row.push(cell.trim()); cell = '' }
    else if ((char === '\n' || char === '\r') && !quoted) {
      if (char === '\r' && text[index + 1] === '\n') index += 1
      row.push(cell.trim()); cell = ''
      if (row.some((value) => value !== '')) rows.push(row)
      row = []
    } else cell += char
  }
  row.push(cell.trim())
  if (row.some((value) => value !== '')) rows.push(row)
  if (quoted) throw new Error('CSV có dấu ngoặc kép chưa đóng.')
  if (!rows.length) throw new Error('File CSV trống.')
  rows[0] = rows[0].map((header) => header.replace(/^﻿/, '').trim())
  return rows
}

function csvRecords(text: string): Array<Record<string, unknown>> {
  const matrix = parseCsv(text)
  const headers = matrix[0]
  return matrix.slice(1).map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ''])))
}

function normalizeRow(value: Record<string, unknown>, index: number): GeoSample {
  const edgeId = String(value.edge_id ?? '').trim()
  const decisionTime = String(value.decision_time ?? '').trim()
  const horizon = Number(value.horizon_min)
  const latitude = Number(value.latitude ?? value.lat)
  const longitude = Number(value.longitude ?? value.lon)
  if (!edgeId) throw new Error(`Dòng ${index + 1}: thiếu edge_id.`)
  if (!decisionTime || !/(Z|[+-]\d{2}:?\d{2})$/i.test(decisionTime) || Number.isNaN(Date.parse(decisionTime))) {
    throw new Error(`Dòng ${index + 1}: decision_time phải là ngày giờ ISO có múi giờ, ví dụ 2026-10-04T10:00:00+07:00.`)
  }
  if (!Number.isInteger(horizon) || horizon < 1 || horizon > 1440) throw new Error(`Dòng ${index + 1}: horizon_min phải trong khoảng 1–1440.`)
  if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90 || !Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
    throw new Error(`Dòng ${index + 1}: cần latitude/longitude hợp lệ để đặt kết quả lên bản đồ.`)
  }
  const sample: FloodSample = { edge_id: edgeId, decision_time: decisionTime, horizon_min: horizon, region: String(value.region || 'unknown'), road_class: String(value.road_class || 'unknown') }
  for (const field of numericFeatures) {
    const raw = value[field]
    if (raw === undefined || raw === null || String(raw).trim() === '') continue
    const number = Number(raw)
    if (!Number.isFinite(number)) throw new Error(`Dòng ${index + 1}: ${field} không phải số hợp lệ.`)
    sample[field] = number
  }
  return { latitude, longitude, sample }
}

function riskColor(state: string): string {
  if (state === 'predicted_high_risk') return '#f43f5e'
  if (state === 'predicted_lower_risk') return '#34d399'
  return '#94a3b8'
}

function FitRiskBounds({ positions }: { positions: Array<[number, number]> }) {
  const map = useMap()
  useEffect(() => {
    if (positions.length > 1) map.fitBounds(positions, { padding: [28, 28], maxZoom: 14 })
    else if (positions.length === 1) map.setView(positions[0], 14)
  }, [map, positions])
  return null
}

function riskTone(state: string): 'red' | 'green' | 'gray' {
  if (state === 'predicted_high_risk') return 'red'
  if (state === 'predicted_lower_risk') return 'green'
  return 'gray'
}

export function AdminFloodRiskPage() {
  const fileInput = useRef<HTMLInputElement>(null)
  const [model, setModel] = useState<FloodModelStatus | null>(null)
  const [rows, setRows] = useState<GeoSample[]>([])
  const [predictions, setPredictions] = useState<FloodPrediction[]>([])
  const [fileName, setFileName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [modelError, setModelError] = useState('')
  const [modelLoading, setModelLoading] = useState(false)

  async function refreshModel() {
    setModelLoading(true)
    try {
      const response = await adminAiApi.mlStatus()
      setModel(response.flood_risk_model || null)
      setModelError('')
    } catch (reason) { setModelError(errorMessage(reason)) }
    finally { setModelLoading(false) }
  }

  useEffect(() => { void refreshModel() }, [])

  async function loadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setError('')
    setPredictions([])
    if (file.size > 10 * 1024 * 1024) { setError('File vượt quá giới hạn 10 MB.'); event.target.value = ''; return }
    try {
      const content = await file.text()
      let records: Array<Record<string, unknown>>
      if (file.name.toLowerCase().endsWith('.json')) {
        const parsed: unknown = JSON.parse(content)
        if (!Array.isArray(parsed)) throw new Error('JSON phải là một mảng các mẫu.')
        records = parsed as Array<Record<string, unknown>>
      } else {
        records = csvRecords(content)
      }
      if (!records.length || records.length > 500) throw new Error('File cần có từ 1 đến 500 mẫu dự đoán.')
      setRows(records.map(normalizeRow))
      setFileName(file.name)
    } catch (reason) {
      setRows([])
      setFileName('')
      setError(reason instanceof Error ? reason.message : 'Không đọc được file đầu vào.')
    } finally { event.target.value = '' }
  }

  async function predict() {
    setError('')
    setPredictions([])
    if (!model?.deployment_allowed) { setError(model?.block_reason || 'Model chưa được phép triển khai.'); return }
    if (!rows.length) { setError('Hãy nạp CSV/JSON có đặc trưng model và tọa độ thật trước.'); return }
    setLoading(true)
    try {
      const response = await adminAiApi.predictFloodRisk(rows.map((row) => row.sample))
      setPredictions(response.predictions)
    } catch (reason) { setError(errorMessage(reason)) }
    finally { setLoading(false) }
  }

  function downloadTemplate() {
    const headers = ['edge_id', 'latitude', 'longitude', 'decision_time', 'horizon_min', 'region', 'road_class', ...numericFeatures]
    const blob = new Blob([`${headers.join(',')}\n`], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'flood_inference_input_template.csv'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const mapped = predictions.map((prediction, index) => ({ ...rows[index], prediction }))
    .filter((row) => Number.isFinite(row.latitude) && Number.isFinite(row.longitude))
  const positions = mapped.map((row) => [row.latitude, row.longitude] as [number, number])
  const center: [number, number] = positions[0] ?? [10.7769, 106.7009]

  return (
    <>
      <PageHeader title="Lớp bản đồ rủi ro ngập" description="Dự đoán theo mẫu đường có tọa độ do bạn cung cấp; lớp này không phải báo cáo ngập hay xác nhận đóng đường."
        actions={<Button variant="secondary" icon={RefreshCw} loading={modelLoading} onClick={() => void refreshModel()}>Kiểm tra model</Button>} />

      <div className="space-y-6">
        {modelError ? (
          <Alert tone="red" title="Không kiểm tra được model"
            action={<Button size="sm" variant="secondary" icon={RefreshCw} loading={modelLoading} onClick={() => void refreshModel()}>Thử lại</Button>}>
            {modelError}
          </Alert>
        ) : (
        <Alert tone={model?.deployment_allowed ? 'green' : 'amber'} title={<span className="inline-flex items-center gap-2"><AlertTriangle className="h-4 w-4" /> Trạng thái model</span>}>
          {model?.deployment_allowed ? `Model ${model.model_version || 'đã tải'} sẵn sàng${model.loaded ? ' và đã nạp' : ''}. Kết quả chỉ là xác suất dự đoán.` : model?.block_reason || (modelLoading || !model ? 'Đang kiểm tra artifact model…' : 'Model chưa được phép triển khai.')}
        </Alert>
        )}
        {model?.error && <Alert tone="amber">{model.error}</Alert>}
        {error && <Alert tone="red">{error}</Alert>}

        <Card>
          <CardHeader title="Nạp mẫu suy luận" description="CSV hoặc JSON; cần edge_id, tọa độ, decision_time có múi giờ và horizon_min. Các đặc trưng còn thiếu sẽ được model xử lý theo preprocessor." />
          <div className="flex flex-wrap items-center gap-3 p-5">
            <Button icon={Upload} onClick={() => fileInput.current?.click()}>Chọn CSV / JSON</Button>
            <input ref={fileInput} type="file" accept=".csv,.json,text/csv,application/json" onChange={(event) => void loadFile(event)} hidden />
            <Button variant="secondary" icon={Download} onClick={downloadTemplate}>Tải mẫu CSV</Button>
            <Button onClick={() => void predict()} loading={loading} disabled={!rows.length || !model?.deployment_allowed}>
              {loading ? 'Đang dự đoán…' : `Chạy dự đoán (${rows.length})`}
            </Button>
            {fileName && <span className="text-sm text-slate-600">{fileName} · {rows.length} mẫu đã kiểm tra</span>}
          </div>
        </Card>

        <Card>
          <CardHeader title="Kết quả dự đoán"
            description={mapped.length ? `${mapped.length} điểm dự đoán · model ${mapped[0]?.prediction.model_version}` : 'Chưa có kết quả. Đây không phải dữ liệu quan trắc.'}
            actions={<span className="flex gap-2"><Badge tone="red" dot>Rủi ro dự đoán cao</Badge><Badge tone="green" dot>Rủi ro dự đoán thấp hơn</Badge><Badge tone="gray" dot>Chưa đủ độ phủ</Badge></span>} />
          {mapped.length === 0 ? (
            <EmptyState icon={MapPinned} title="Chưa có kết quả" description="Nạp file mẫu và chạy dự đoán để xem rủi ro theo từng đoạn đường." />
          ) : (
            <>
            <div className="h-[420px] w-full overflow-hidden border-b border-slate-200">
              <MapContainer center={center} zoom={12} scrollWheelZoom style={{ height: '100%', width: '100%' }}>
                <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                <FitRiskBounds positions={positions} />
                {mapped.map((row, index) => {
                  const color = riskColor(row.prediction.risk_state)
                  return (
                    <CircleMarker key={`${row.prediction.edge_id}-${index}`} center={[row.latitude, row.longitude]} radius={10}
                      pathOptions={{ color, fillColor: color, fillOpacity: 0.72, weight: 2 }}>
                      <Popup>
                        <strong>{row.prediction.edge_id}</strong><br />{row.prediction.risk_state}<br />
                        Xác suất: {(row.prediction.probability * 100).toFixed(1)}%<br />
                        Chân trời: {row.prediction.horizon_min} phút<br />
                        Độ phủ dữ liệu: {row.prediction.coverage_ratio == null ? 'chưa cung cấp' : `${(row.prediction.coverage_ratio * 100).toFixed(0)}%`}<br />
                        Model: {row.prediction.model_version}<br /><em>Không phải quan trắc đã xác minh.</em>
                      </Popup>
                    </CircleMarker>
                  )
                })}
              </MapContainer>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Edge</th><th className="px-4 py-3">Tọa độ</th><th className="px-4 py-3">Rủi ro</th>
                    <th className="px-4 py-3">Xác suất</th><th className="px-4 py-3">Chân trời</th><th className="px-4 py-3">Độ phủ dữ liệu</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {mapped.map((row, index) => (
                    <tr key={`${row.prediction.edge_id}-${index}`}>
                      <td className="px-4 py-3 font-medium text-slate-900">{row.prediction.edge_id}</td>
                      <td className="px-4 py-3 text-slate-600">{row.latitude?.toFixed(5)}, {row.longitude?.toFixed(5)}</td>
                      <td className="px-4 py-3"><Badge tone={riskTone(row.prediction.risk_state)} dot>{row.prediction.risk_state}</Badge></td>
                      <td className="px-4 py-3">{(row.prediction.probability * 100).toFixed(1)}%</td>
                      <td className="px-4 py-3">{row.prediction.horizon_min} phút</td>
                      <td className="px-4 py-3">{row.prediction.coverage_ratio == null ? 'chưa cung cấp' : `${(row.prediction.coverage_ratio * 100).toFixed(0)}%`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="px-4 py-3 text-xs italic text-slate-500">Không phải quan trắc đã xác minh.</p>
            </div>
            </>
          )}
        </Card>
      </div>
    </>
  )
}
