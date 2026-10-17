import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api, apiErrorMessage } from '../../api/client'
import { useJourney } from '../../journey'
import { useAuth } from '../../auth'

type PilotStatus = { ready_experiences: number; verified_experiences: number; demo_available: boolean; demo_experiences: number }
export function JourneyBar() {
  const { pathname } = useLocation()
  const { user } = useAuth()
  const { trip, assistant, setTrip, toggleExperience, reset } = useJourney()
  const [pilot, setPilot] = useState<PilotStatus | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    api.get<PilotStatus>('/journey/pilot').then(({ data }) => { if (active) setPilot(data) })
      .catch((reason) => { if (active) setError(apiErrorMessage(reason)) })
    return () => { active = false }
  }, [])
  if ((user && user.role !== 'traveler') || !['/chat', '/map-3d', '/planner',  '/explore'].includes(pathname)) return null
  return <section className="border-y border-emerald-200 bg-white px-5 py-3 text-slate-800" aria-label="Hành trình của bạn">
    <div className="mx-auto max-w-7xl space-y-2">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        <strong>Hành trình di sản · Quận 1, TP.HCM</strong>
        <nav className="flex flex-wrap gap-3" aria-label="Các bước hành trình">
          {[['/chat', '1. Sở thích'], ['/map-3d', '2. Xem 3D'], ['/explore', '3. Chọn trải nghiệm'], ['/planner', '4. Tạo lịch trình']].map(([to, label]) =>
            <Link key={to} to={to} aria-current={pathname === to ? 'step' : undefined} className={pathname === to ? 'font-bold text-emerald-700 underline' : 'text-slate-600 underline'}>{label}</Link>)}
        </nav>
        <button type="button" className="text-xs underline" disabled={assistant.busy} onClick={reset}>Hành trình mới</button>
      </div>
      <p className="text-xs">{trip.date} · {trip.startTime}–{trip.endTime} · {trip.groupSize} người · Tổng ngân sách {trip.budget.toLocaleString('vi-VN')} ₫ · Đã chọn {trip.selected.length}/6 trải nghiệm</p>
      {pilot && pilot.ready_experiences === 0 && <p role="status" className="text-xs text-amber-800">Chưa có trải nghiệm đủ nguồn và khung giờ xác minh để thử nghiệm thực tế. Cần bổ sung dữ liệu trước khi phục vụ du khách.</p>}
      {error && <p role="alert" className="text-xs text-red-700">Chưa kiểm tra được dữ liệu pilot: {error}</p>}
      {(pilot?.demo_available || trip.demo) && <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={trip.demo} onChange={(event) => setTrip((current) => ({ ...current, demo: event.target.checked, selected: [], lockedPois: [], originId: '', destinationId: '' }))} />
        Thử demo: trải nghiệm và tình trạng chỗ mô phỏng; tuyến đường vẫn lấy từ API bản đồ
      </label>}
      {trip.selected.length > 0 && <div className="flex flex-wrap gap-2">
        {trip.selected.map((item) => <button key={item.id} type="button" onClick={() => toggleExperience(item)} className="rounded-full bg-emerald-50 px-3 py-1 text-xs text-emerald-800" title="Bỏ chọn trải nghiệm">{item.name} ×</button>)}
      </div>}
    </div>
  </section>
}
