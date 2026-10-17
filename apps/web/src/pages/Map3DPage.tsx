import { useEffect, useState } from 'react'
import { Map3DLandmarkViewer } from '../components/3d/Map3DLandmarkViewer'
import { Map3DGuidePanel } from '../components/3d/Map3DGuidePanel'
import {
  Compass,
  ArrowLeft,
  Building2
} from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTripField } from '../journey'
import { api } from '../api/client'
import { contentApi } from '../api/content'
import type { POI } from '../types'
import { DEFAULT_CALIBRATIONS, type ModelCalibration } from '../components/3d/landmark/types'

export function Map3DPage() {
  const [search] = useSearchParams()
  const previewJobId = search.get("meshyPreview") || undefined
  const [draft, setDraft] = useState<ModelCalibration | null>(null)
  const [draftError, setDraftError] = useState("")
  useEffect(() => {
    if (!previewJobId) return
    api.get<ModelCalibration>(`/admin/meshy/jobs/${previewJobId}/calibration`).then(r => setDraft(r.data)).catch(() => setDraftError("Không thể mở model nháp. Hãy đăng nhập tài khoản có quyền quản lý mô hình 3D."))
  }, [previewJobId])
  const [selectedLandmark, setSelectedLandmark] = useTripField('modelId')
  const [landmarks, setLandmarks] = useState<Record<string, ModelCalibration>>(DEFAULT_CALIBRATIONS)

  useEffect(() => {
    let active = true
    api.get<Record<string, ModelCalibration>>('/models-3d/calibration')
      .then(({ data }) => {
        if (!active || !data || typeof data !== 'object') return
        const next = { ...DEFAULT_CALIBRATIONS, ...data }
        setLandmarks(next)
        setSelectedLandmark((current) => next[current] ? current : 'nhathoducba')
      })
      .catch(() => {
        // Keep the built-in catalog usable if the API is temporarily offline.
      })
    return () => { active = false }
  }, [])

  const landmarkIds = [
    ...Object.keys(DEFAULT_CALIBRATIONS),
    ...Object.keys(landmarks).filter((id) => !(id in DEFAULT_CALIBRATIONS)),
  ]
  // Landmarks published in the portal: each links to its place page; the ones with a 3D model also open it here.
  const [portalLandmarks, setPortalLandmarks] = useState<POI[]>([])
  useEffect(() => {
    contentApi.places().then((places) => setPortalLandmarks(places.filter((place) => place.is_landmark))).catch(() => setPortalLandmarks([]))
  }, [])
  const normalise = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase().replace(/[^a-z0-9]/g, '')
  const modelFor = (place: POI) => landmarkIds.find((id) => {
    const name = normalise((landmarks[id] ?? DEFAULT_CALIBRATIONS[id])?.display_name ?? '')
    return name !== '' && normalise(place.name).includes(name)
  })

  const selectedCalibration = landmarks[selectedLandmark] ?? DEFAULT_CALIBRATIONS.nhathoducba

  if (previewJobId) return <div className="p-3">
    <p className="rounded-lg bg-amber-50 p-3 text-amber-900">Bản nháp riêng tư · Mô hình do AI tạo. Căn vị trí rồi lưu trước khi quay về Portal xuất bản.</p>
    {draftError && <p role="alert">{draftError}</p>}
    {!draft && !draftError && <p>Đang tải bản nháp…</p>}
    {draft && <Map3DLandmarkViewer key={previewJobId} modelId={draft.model_name} previewJobId={previewJobId} defaultCalibration={draft} className="h-[80vh]" />}
  </div>

  return (
    <div className="map3d-page w-full flex flex-col min-h-[calc(100vh-64px)]">
      {/* Top Banner Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-4 px-4 sm:px-8 py-3.5 bg-slate-900/90 border-b border-slate-800 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <Link
            to="/explore"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white rounded-xl text-xs font-semibold transition-all"
          >
            <ArrowLeft size={14} /> Quay lại Khám Phá
          </Link>

          <div className="h-4 w-px bg-slate-700 hidden sm:block" />

          <div className="flex items-center gap-2">
            <span className="p-1.5 bg-emerald-500/20 text-emerald-400 rounded-lg">
              <Compass size={18} />
            </span>
            <div>
              <h1 className="text-sm font-bold text-white flex items-center gap-2">
                Bản Đồ 3D Di Sản Việt Nam
                <span className="text-[10px] bg-gradient-to-r from-emerald-500 to-cyan-500 text-slate-950 font-black px-2 py-0.5 rounded-full uppercase tracking-wider">
                  WebGL 3D
                </span>
              </h1>
              <p className="text-[11px] text-slate-400 hidden md:block">
                Tương tác 3D với các di sản và công trình biểu tượng tại Sài Gòn và Hội An
              </p>
            </div>
          </div>
        </div>

        {/* Landmark Selector Dropdown / Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-1 max-w-full">
          {landmarkIds.map((id) => {
            const landmark = landmarks[id] ?? DEFAULT_CALIBRATIONS[id]
            if (!landmark) return null
            const isSelected = selectedLandmark === id
            return (
              <button
                key={id}
                type="button"
                onClick={() => setSelectedLandmark(id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-all ${
                  isSelected
                    ? 'bg-emerald-500 text-slate-950 font-bold shadow-lg shadow-emerald-500/20'
                    : 'bg-slate-800/60 hover:bg-slate-800 text-slate-300 border border-slate-700/50'
                }`}
              >
                <Building2 size={13} />
                <span>{landmark.display_name}</span>
              </button>
            )
          })}
        </div>
      </div>

      {portalLandmarks.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 px-4 sm:px-8 py-2.5 bg-slate-900/60 border-b border-slate-800">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Danh thắng</span>
          {portalLandmarks.map((place) => {
            const model = modelFor(place)
            return (
              <span key={place.id} className="inline-flex items-center overflow-hidden rounded-lg border border-slate-700/60 text-xs">
                <Link to={`/places/${place.id}`} className="px-2.5 py-1 text-slate-200 hover:bg-slate-800">{place.name}</Link>
                {model && (
                  <button type="button" onClick={() => setSelectedLandmark(model)} className="border-l border-slate-700/60 px-2 py-1 text-emerald-400 hover:bg-slate-800" title="Xem mô hình 3D">3D</button>
                )}
              </span>
            )
          })}
        </div>
      )}

      {selectedLandmark.startsWith("meshy-") && <p className="bg-amber-50 px-4 py-2 text-sm text-amber-900">Mô hình do AI tạo · Hình dáng có thể khác công trình thực tế.</p>}

      {/* Main 3D Canvas Area */}
      <div className="flex-1 w-full relative min-h-[680px]">
        <Map3DLandmarkViewer
          modelId={selectedLandmark}
          defaultCalibration={selectedCalibration}
          className="w-full h-full min-h-[calc(100vh-140px)]"
        />
        <Map3DGuidePanel landmark={selectedCalibration} modelId={selectedLandmark} />
      </div>
    </div>
  )
}
