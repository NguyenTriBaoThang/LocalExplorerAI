import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Compass, Crosshair, Maximize2, Move, RotateCcw, RotateCw, Save } from 'lucide-react'
import type { ReactNode } from 'react'
import type { ModelCalibration } from './types'

export type GizmoMode = 'translate' | 'rotate' | 'scale'
export type PanelStatus = { kind: 'success' | 'error' | 'info'; text: string } | null

interface Props {
  calibration: ModelCalibration
  mode: GizmoMode
  dirty: boolean
  saving: boolean
  status: PanelStatus
  nudgeStep: number
  onModeChange: (mode: GizmoMode) => void
  onNudgeStepChange: (meters: number) => void
  onNudge: (eastM: number, northM: number) => void
  onChange: (patch: Partial<ModelCalibration>) => void
  onSnapToReference: () => void
  onSave: () => void
  onRevert: () => void
}

const MODES: Array<{ key: GizmoMode; label: string; Icon: typeof Move }> = [
  { key: 'translate', label: 'Di chuyển', Icon: Move },
  { key: 'rotate', label: 'Xoay', Icon: RotateCw },
  { key: 'scale', label: 'Kích thước', Icon: Maximize2 },
]

const STATUS_STYLE = {
  success: 'bg-emerald-950/80 border-emerald-500/40 text-emerald-300',
  error: 'bg-rose-950/80 border-rose-500/40 text-rose-300',
  info: 'bg-slate-800/80 border-slate-600 text-slate-200',
}

function toNumber(raw: string, fallback: number): number {
  const value = Number.parseFloat(raw)
  return Number.isFinite(value) ? value : fallback
}

export function CalibrationPanel(props: Props) {
  const { calibration: c, mode, dirty, saving, status, nudgeStep } = props
  const btn = 'px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-200 font-bold transition-colors'

  return (
    <div className="absolute bottom-4 right-4 z-20 w-80 sm:w-96 max-h-[78vh] overflow-y-auto bg-slate-900/95 border border-slate-700/80 backdrop-blur-xl p-4 rounded-2xl shadow-2xl text-slate-200 text-xs">
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Compass size={18} className="text-amber-400" />
          <strong className="text-sm font-bold text-white">Hiệu Chỉnh Vị Trí Mô Hình</strong>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded font-mono font-bold ${dirty ? 'bg-amber-500/20 text-amber-300' : 'bg-emerald-500/20 text-emerald-300'}`}>
          {dirty ? 'CHƯA LƯU' : 'ĐÃ LƯU'}
        </span>
      </div>

      <p className="text-xs text-slate-400 mb-3">
        Kéo mũi tên trên mô hình hoặc dùng nút bên dưới để khớp với ảnh vệ tinh. Ghim đỏ là toạ độ chuẩn của địa điểm.
      </p>

      <div className="grid grid-cols-3 gap-1.5 p-1 mb-4 bg-slate-950/70 rounded-xl border border-slate-800">
        {MODES.map(({ key, label, Icon }) => (
          <button key={key} id={`gizmo-mode-${key}`} type="button" onClick={() => props.onModeChange(key)}
            className={`flex items-center justify-center gap-1.5 py-1.5 rounded-lg font-medium transition-all ${mode === key ? 'bg-amber-500 text-slate-950 font-bold shadow' : 'text-slate-400 hover:text-white'}`}>
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>

      <div className="mb-4">
        <div className="flex justify-between items-center mb-1.5">
          <span className="text-slate-400">Dịch chuyển nhanh</span>
          <select id="nudge-step" value={nudgeStep} onChange={(e) => props.onNudgeStepChange(Number(e.target.value))}
            className="bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-white">
            {[0.5, 1, 2, 5, 10].map((m) => <option key={m} value={m}>{m} m / lần</option>)}
          </select>
        </div>
        <div className="grid grid-cols-3 gap-1 w-32 mx-auto">
          <span />
          <button id="nudge-north" type="button" className={btn} title="Lên Bắc" onClick={() => props.onNudge(0, nudgeStep)}><ArrowUp size={13} className="mx-auto" /></button>
          <span />
          <button id="nudge-west" type="button" className={btn} title="Sang Tây" onClick={() => props.onNudge(-nudgeStep, 0)}><ArrowLeft size={13} className="mx-auto" /></button>
          <button id="snap-reference" type="button" className={btn} title="Đưa về ghim toạ độ chuẩn" onClick={props.onSnapToReference}><Crosshair size={13} className="mx-auto text-rose-400" /></button>
          <button id="nudge-east" type="button" className={btn} title="Sang Đông" onClick={() => props.onNudge(nudgeStep, 0)}><ArrowRight size={13} className="mx-auto" /></button>
          <span />
          <button id="nudge-south" type="button" className={btn} title="Xuống Nam" onClick={() => props.onNudge(0, -nudgeStep)}><ArrowDown size={13} className="mx-auto" /></button>
          <span />
        </div>
      </div>

      <div className="space-y-2.5">
        <div className="grid grid-cols-2 gap-2">
          <label className="block">
            <span className="text-slate-400">Vĩ độ (lat)</span>
            <input id="calib-lat" type="number" step="0.000005" value={c.latitude}
              onChange={(e) => props.onChange({ latitude: toNumber(e.target.value, c.latitude) })}
              className="w-full mt-1 bg-slate-950/80 border border-slate-800 rounded-lg px-2 py-1 font-mono text-white focus:outline-none focus:border-amber-500" />
          </label>
          <label className="block">
            <span className="text-slate-400">Kinh độ (lng)</span>
            <input id="calib-lng" type="number" step="0.000005" value={c.longitude}
              onChange={(e) => props.onChange({ longitude: toNumber(e.target.value, c.longitude) })}
              className="w-full mt-1 bg-slate-950/80 border border-slate-800 rounded-lg px-2 py-1 font-mono text-white focus:outline-none focus:border-amber-500" />
          </label>
        </div>

        <RangeRow id="calib-heading" label="Hướng mặt tiền (độ, từ Bắc theo chiều kim đồng hồ)" value={c.heading} min={0} max={359.5} step={0.5}
          unit="°" accent="accent-emerald-400" onChange={(v) => props.onChange({ heading: v })}
          extra={<>
            <button type="button" className={btn} onClick={() => props.onChange({ heading: (c.heading + 359) % 360 })}>-1°</button>
            <button type="button" className={btn} onClick={() => props.onChange({ heading: (c.heading + 1) % 360 })}>+1°</button>
          </>} />
        <RangeRow id="calib-scale" label="Chiều cao thực tế (mét)" value={c.scale} min={5} max={150} step={0.5}
          unit="m" accent="accent-purple-400" onChange={(v) => props.onChange({ scale: Math.max(1, v) })} />
        <RangeRow id="calib-alt" label="Cao độ so với mặt đất (mét)" value={c.altitude} min={-10} max={30} step={0.1}
          unit="m" accent="accent-cyan-400" onChange={(v) => props.onChange({ altitude: v })} />
      </div>

      <div className="pt-4 mt-3 border-t border-slate-800 flex gap-2">
        <button id="calib-save" type="button" onClick={props.onSave} disabled={saving || !dirty}
          className="flex-1 flex items-center justify-center gap-2 py-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition-all shadow-lg shadow-emerald-900/30 disabled:opacity-50">
          {saving ? <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Save size={14} />}
          {saving ? 'Đang lưu...' : 'Lưu Tọa Độ Vị Trí'}
        </button>
        <button id="calib-revert" type="button" onClick={props.onRevert} disabled={!dirty}
          className="py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-xl transition-all disabled:opacity-40"
          title="Hoàn tác về lần lưu gần nhất">
          <RotateCcw size={14} />
        </button>
      </div>

      {status && (
        <div className={`mt-2.5 p-2 border rounded-lg text-xs ${STATUS_STYLE[status.kind]}`}>{status.text}</div>
      )}
    </div>
  )
}

function RangeRow(props: {
  id: string; label: string; value: number; min: number; max: number; step: number
  unit: string; accent: string; onChange: (v: number) => void; extra?: ReactNode
}) {
  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-slate-400">{props.label}</span>
        <span className="font-mono font-bold text-white">{props.value.toFixed(1)}{props.unit}</span>
      </div>
      <div className="flex gap-1.5 items-center">
        <input id={`${props.id}-range`} type="range" min={props.min} max={props.max} step={props.step} value={props.value}
          onChange={(e) => props.onChange(toNumber(e.target.value, props.value))} className={`flex-1 ${props.accent}`} />
        <input id={props.id} type="number" step={props.step} value={props.value}
          onChange={(e) => props.onChange(toNumber(e.target.value, props.value))}
          className="w-16 bg-slate-950/80 border border-slate-800 rounded px-1.5 py-0.5 font-mono text-center text-white" />
        {props.extra}
      </div>
    </div>
  )
}
