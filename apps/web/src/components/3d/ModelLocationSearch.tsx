import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { Search, MapPin } from 'lucide-react'
import { api } from '../../api/client'
import type { GeocodeCandidate, GeocodeResponse } from '../../types'

export function ModelLocationSearch({ onSelect }: { onSelect: (place: GeocodeCandidate) => void }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<GeocodeCandidate[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const request = useRef<AbortController | null>(null)
  useEffect(() => () => request.current?.abort(), [])
  async function search() {
    const address = query.trim()
    if (address.length < 3) { setMessage('Nhập ít nhất 3 ký tự để tìm địa điểm.'); return }
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    setBusy(true); setResults([]); setMessage('')
    try {
      const { data } = await api.get<GeocodeResponse>('/geocoding/forward', { params: { address }, signal: controller.signal })
      if (controller.signal.aborted) return
      if (!['goong', 'goong_geocode_v2'].includes(data.provider.toLowerCase())) throw new Error('Kết quả chưa được cung cấp bởi Goong.')
      const candidates = data.results.filter(p => Number.isFinite(p.latitude) && Number.isFinite(p.longitude) && Math.abs(p.latitude) <= 90 && Math.abs(p.longitude) <= 180)
      setResults(candidates)
      if (!candidates.length) setMessage('Không tìm thấy địa điểm. Thử thêm tên đường, quận hoặc tỉnh/thành phố.')
    } catch (error) {
      if (controller.signal.aborted) return
      const code = axios.isAxiosError(error) ? error.response?.data?.error?.code : undefined
      setMessage(code === 'GEOCODING_NOT_CONFIGURED' ? 'Chưa cấu hình Goong REST API key. Kiểm tra mục Tích hợp trong Portal.' : 'Chưa tìm được vị trí từ Goong. Hãy kiểm tra kết nối hoặc thử lại với địa chỉ đầy đủ.')
    } finally { if (!controller.signal.aborted) setBusy(false) }
  }
  return <section className="mb-4 rounded-xl border border-slate-300 bg-stone-50 p-3 text-slate-900" aria-label="Tìm vị trí mô hình trên Goong">
    <label htmlFor="model-goong-location" className="mb-2 flex items-center gap-2 font-semibold"><MapPin size={15} />Tìm vị trí thực trên Goong</label>
    <div className="flex gap-2"><input id="model-goong-location" maxLength={300} value={query} placeholder="Tên công trình hoặc địa chỉ…" className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900" onChange={e => { request.current?.abort(); setBusy(false); setQuery(e.target.value); setResults([]); setMessage('') }} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); void search() } }} /><button type="button" disabled={busy || query.trim().length < 3} onClick={() => void search()} className="rounded-lg bg-slate-800 px-3 py-2 text-white disabled:opacity-40" aria-label="Tìm địa điểm trên Goong"><Search size={16} /></button></div>
    {busy && <p role="status" className="mt-2">Đang tìm trên Goong…</p>}
    {message && <p role="status" className="mt-2 text-amber-900">{message}</p>}
    {!!results.length && <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto" aria-label="Kết quả tìm địa điểm">{results.map((place, index) => <li key={`${place.place_id || index}-${place.latitude}`}><button type="button" className="w-full rounded-lg border border-slate-200 bg-white p-2 text-left hover:border-indigo-400 hover:bg-indigo-50 focus:outline-indigo-600" onClick={() => { onSelect(place); setQuery(place.formatted_address); setResults([]); setMessage('Đã chuyển mô hình đến vị trí chọn. Căn lại góc xoay/kích thước nếu cần rồi bấm Lưu.') }}><span className="block font-medium">{place.formatted_address}</span><span className="mt-1 block text-xs text-slate-500">{place.latitude.toFixed(6)}, {place.longitude.toFixed(6)} · Đặt mô hình tại đây</span></button></li>)}</ul>}
    <p className="mt-2 text-xs text-slate-500">Chọn kết quả để thay vĩ độ/kinh độ. Kiểm tra đúng vị trí công trình trước khi lưu.</p>
  </section>
}
