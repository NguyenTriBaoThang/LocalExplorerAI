import { useEffect, useMemo, useState, type ChangeEvent } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import { AlertTriangle, Download, MapPinned, RefreshCw, Upload } from 'lucide-react'
import { apiErrorMessage, mlApi } from '../api/client'

type FloodSample = { edge_id: string; decision_time: string; horizon_min: number; region: string; road_class: string; [key: string]: string | number }
type GeoSample = { latitude: number; longitude: number; sample: FloodSample }
type Prediction = { edge_id: string; decision_time: string; horizon_min: number; probability: number; risk_state: string; coverage_ratio: number | null; model_version: string; is_verified_observation: false }
type FloodModelStatus = { configured: boolean; loaded: boolean; model_version: string | null; demo_mode: boolean | null; deployment_allowed: boolean; block_reason: string | null; error: string | null }

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
  rows[0] = rows[0].map((header) => header.replace(/^\uFEFF/, '').trim())
  return rows
}

function csvRecords(text: string): Array<Record<string, unknown>> {
  const matrix = parseCsv(text)
  const headers = matrix[0]
  const dataRows = matrix.slice(1)
  return dataRows.map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ''])))
}

function FitRiskBounds({ positions }: { positions: Array<[number, number]> }) {
  const map = useMap()
  useEffect(() => {
    if (positions.length > 1) map.fitBounds(positions, { padding: [28, 28], maxZoom: 14 })
    else if (positions.length === 1) map.setView(positions[0], 14)
  }, [map, positions])
  return null
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

function riskColor(state: string) {
  if (state === 'predicted_high_risk') return '#f43f5e'
  if (state === 'predicted_lower_risk') return '#34d399'
  return '#94a3b8'
}

export function AdminFloodRiskPanel() {
  const [model, setModel] = useState<FloodModelStatus | null>(null)
  const [rows, setRows] = useState<GeoSample[]>([])
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [fileName, setFileName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function refreshModel() {
    try {
      const response = await mlApi.status() as { flood_risk_model?: FloodModelStatus }
      setModel(response.flood_risk_model || null)
    } catch (reason) { setError(apiErrorMessage(reason)) }
  }

  useEffect(() => { void refreshModel() }, [])

  async function loadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setError('')
    setPredictions([])
    if (file.size > 10 * 1024 * 1024) { setError('File vượt quá giới hạn 10 MB.'); return }
    try {
      const content = await file.text()
      const records = file.name.toLowerCase().endsWith('.json')
        ? (() => { const parsed: unknown = JSON.parse(content); if (!Array.isArray(parsed)) throw new Error('JSON phải là một mảng các mẫu.'); return parsed as Array<Record<string, unknown>> })()
        : csvRecords(content)
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
      const response = await mlApi.predictFloodRisk(rows.map((row) => row.sample)) as { predictions: Prediction[]; model_version: string | null }
      setPredictions(response.predictions)
    } catch (reason) { setError(apiErrorMessage(reason)) }
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

  const mapped = useMemo(() => predictions.map((prediction, index) => ({ ...rows[index], prediction })), [predictions, rows])
  const positions = useMemo(() => mapped.map((row) => [row.latitude, row.longitude] as [number, number]), [mapped])
  const center: [number, number] = mapped.length
    ? [mapped.reduce((sum, row) => sum + row.latitude, 0) / mapped.length, mapped.reduce((sum, row) => sum + row.longitude, 0) / mapped.length]
    : [10.775, 106.7]

  return (
    <div className="admin-tab-content animate-fadeIn">
      <div className="page-title-row-3d">
        <div><h2 className="section-title-3d"><MapPinned size={19} /> Lớp bản đồ rủi ro ngập</h2><p className="page-subtext-3d">Dự đoán theo mẫu đường có tọa độ do bạn cung cấp; lớp này không phải báo cáo ngập hay xác nhận đóng đường.</p></div>
        <button type="button" className="btn-secondary-3d" onClick={() => void refreshModel()}><RefreshCw size={15} /> Kiểm tra model</button>
      </div>

      <div className={`inline-alert-3d ${model?.deployment_allowed ? 'alert-success' : ''}`}>
        <AlertTriangle size={16} />
        <span>{model?.deployment_allowed ? `Model ${model.model_version || 'đã tải'} sẵn sàng${model.loaded ? ' và đã nạp' : ''}. Kết quả chỉ là xác suất dự đoán.` : model?.block_reason || 'Đang kiểm tra artifact model…'}</span>
      </div>
      {model?.error && <div className="inline-alert-3d"><span>{model.error}</span></div>}
      {error && <div className="inline-alert-3d" role="alert"><span>{error}</span></div>}

      <section className="admin-section-card" style={{ marginBottom: 18 }}>
        <div className="admin-section-header"><h3>Nạp mẫu suy luận</h3><p>CSV hoặc JSON; cần edge_id, tọa độ, decision_time có múi giờ và horizon_min. Các đặc trưng còn thiếu sẽ được model xử lý theo preprocessor.</p></div>
        <div className="item-action-btns" style={{ flexWrap: 'wrap' }}>
          <label className="btn-primary-3d" style={{ cursor: 'pointer' }}><Upload size={15} /> Chọn CSV / JSON<input type="file" accept=".csv,.json,text/csv,application/json" onChange={(event) => void loadFile(event)} hidden /></label>
          <button type="button" className="btn-secondary-3d" onClick={downloadTemplate}><Download size={15} /> Tải mẫu CSV</button>
          <button type="button" className="btn-primary-3d" onClick={() => void predict()} disabled={loading || !rows.length || !model?.deployment_allowed}>{loading ? 'Đang dự đoán…' : `Chạy dự đoán (${rows.length})`}</button>
          {fileName && <span>{fileName} · {rows.length} mẫu đã kiểm tra</span>}
        </div>
      </section>

      <div className="admin-section-card" style={{ padding: 8 }}>
        <div style={{ height: 520, width: '100%' }}>
          <MapContainer center={center} zoom={mapped.length ? 12 : 11} scrollWheelZoom style={{ height: '100%', width: '100%', borderRadius: 14 }}>
            <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <FitRiskBounds positions={positions} />
            {mapped.map((row, index) => {
              const color = riskColor(row.prediction.risk_state)
              return <CircleMarker key={`${row.prediction.edge_id}-${index}`} center={[row.latitude, row.longitude]} radius={10} pathOptions={{ color, fillColor: color, fillOpacity: 0.72, weight: 2 }}>
                <Popup><strong>{row.prediction.edge_id}</strong><br />{row.prediction.risk_state}<br />Xác suất: {(row.prediction.probability * 100).toFixed(1)}%<br />Chân trời: {row.prediction.horizon_min} phút<br />Độ phủ dữ liệu: {row.prediction.coverage_ratio == null ? 'chưa cung cấp' : `${(row.prediction.coverage_ratio * 100).toFixed(0)}%`}<br />Model: {row.prediction.model_version}<br /><em>Không phải quan trắc đã xác minh.</em></Popup>
              </CircleMarker>
            })}
          </MapContainer>
        </div>
        <div className="item-sub-meta" style={{ padding: '14px 10px 6px' }}>
          <span style={{ color: '#f43f5e' }}>● Rủi ro dự đoán cao</span><span style={{ color: '#34d399' }}>● Rủi ro dự đoán thấp hơn</span><span style={{ color: '#94a3b8' }}>● Chưa đủ độ phủ</span>
          <span>{mapped.length ? `${mapped.length} điểm dự đoán · model ${mapped[0]?.prediction.model_version}` : 'Chưa có kết quả. Nền bản đồ không phải dữ liệu quan trắc.'}</span>
        </div>
      </div>
    </div>
  )
}
