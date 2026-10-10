import { useEffect, useState } from 'react'
import { Map3DLandmarkViewer } from '../components/3d/Map3DLandmarkViewer'
import {
  Compass,
  ArrowLeft,
  Building2
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { contentApi } from '../api/content'
import type { POI } from '../types'

const LANDMARKS = [
  {
    id: 'nhathoducba',
    name: 'Nhà thờ Đức Bà Sài Gòn',
    tag: 'Mô hình 3D Hoạt động',
    status: 'active',
    district: 'Quận 1, TP. Hồ Chí Minh',
    built: '1880',
    height: '60.5m',
    poi_link: '/explore?q=nhathoducba'
  },
  {
    id: 'dinhdoclap',
    name: 'Dinh Độc Lập',
    tag: 'Sắp ra mắt',
    status: 'coming_soon',
    district: 'Quận 1, TP. Hồ Chí Minh',
    built: '1966',
    height: '26m',
  },
  {
    id: 'chobenthanh',
    name: 'Chợ Bến Thành',
    tag: 'Sắp ra mắt',
    status: 'coming_soon',
    district: 'Quận 1, TP. Hồ Chí Minh',
    built: '1912',
    height: '28m',
  },
  {
    id: 'landmark81',
    name: 'Landmark 81 SkyView',
    tag: 'Sắp ra mắt',
    status: 'coming_soon',
    district: 'Bình Thạnh, TP. Hồ Chí Minh',
    built: '2018',
    height: '461.2m',
  }
]

export function Map3DPage() {
  const [selectedLandmark, setSelectedLandmark] = useState('nhathoducba')
  // Landmarks published in the portal: each links to its place page; the ones with a 3D model also open it here.
  const [landmarks, setLandmarks] = useState<POI[]>([])
  useEffect(() => {
    contentApi.places().then((places) => setLandmarks(places.filter((place) => place.is_landmark))).catch(() => setLandmarks([]))
  }, [])
  const normalise = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase().replace(/[^a-z0-9]/g, '')
  const modelFor = (place: POI) => LANDMARKS.find((model) => model.status === 'active' && normalise(place.name).includes(normalise(model.name)))

  return (
    <div className="w-full flex flex-col bg-slate-950 text-slate-100 min-h-[calc(100vh-64px)]">
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
                Bản Đồ 3D Không Gian Landmark Sài Gòn
                <span className="text-xs bg-gradient-to-r from-emerald-500 to-cyan-500 text-slate-950 font-black px-2 py-0.5 rounded-full uppercase tracking-wider">
                  WebGL 3D
                </span>
              </h1>
              <p className="text-xs text-slate-400 hidden md:block">
                Tương tác không gian 3 chiều với các di sản và công trình biểu tượng của TP. Hồ Chí Minh
              </p>
            </div>
          </div>
        </div>

        {/* Landmark Selector Dropdown / Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-1 max-w-full">
          {LANDMARKS.map((lm) => {
            const isSelected = selectedLandmark === lm.id
            return (
              <button
                key={lm.id}
                type="button"
                onClick={() => setSelectedLandmark(lm.id)}
                disabled={lm.status === 'coming_soon'}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-all ${
                  isSelected
                    ? 'bg-emerald-500 text-slate-950 font-bold shadow-lg shadow-emerald-500/20'
                    : lm.status === 'coming_soon'
                      ? 'bg-slate-900/40 text-slate-500 border border-slate-800/60 cursor-not-allowed opacity-60'
                      : 'bg-slate-800/60 hover:bg-slate-800 text-slate-300 border border-slate-700/50'
                }`}
              >
                <Building2 size={13} />
                <span>{lm.name}</span>
                {lm.status === 'coming_soon' && (
                  <span className="text-xs bg-slate-800 text-slate-400 px-1.5 py-0.2 rounded font-normal">
                    Sắp có
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {landmarks.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 px-4 sm:px-8 py-2.5 bg-slate-900/60 border-b border-slate-800">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Danh thắng</span>
          {landmarks.map((place) => {
            const model = modelFor(place)
            return (
              <span key={place.id} className="inline-flex items-center overflow-hidden rounded-lg border border-slate-700/60 text-xs">
                <Link to={`/places/${place.id}`} className="px-2.5 py-1 text-slate-200 hover:bg-slate-800">{place.name}</Link>
                {model && (
                  <button type="button" onClick={() => setSelectedLandmark(model.id)} className="border-l border-slate-700/60 px-2 py-1 text-emerald-400 hover:bg-slate-800" title="Xem mô hình 3D">3D</button>
                )}
              </span>
            )
          })}
        </div>
      )}

      {/* Main 3D Canvas Area */}
      <div className="flex-1 w-full relative min-h-[680px]">
        <Map3DLandmarkViewer
          modelId={selectedLandmark}
          className="w-full h-full min-h-[calc(100vh-140px)]"
        />
      </div>
    </div>
  )
}
