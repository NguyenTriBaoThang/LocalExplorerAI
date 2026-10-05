import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cx } from './ui'

/* Validated categorical order (light surface): blue, orange, green. Max three series per chart. */
export const SERIES_COLORS = ['#2a78d6', '#eb6834', '#0f9a63'] as const

export type Series = { name: string; values: number[]; color?: string }

const compact = new Intl.NumberFormat('vi-VN', { notation: 'compact', maximumFractionDigits: 1 })
const full = new Intl.NumberFormat('vi-VN')
export const formatCompact = (value: number) => compact.format(value)

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    if (!ref.current) return
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])
  return [ref, width] as const
}

/** Round the axis maximum up to a readable step so gridlines land on clean numbers. */
function niceMax(value: number) {
  if (value <= 0) return 1
  const magnitude = 10 ** Math.floor(Math.log10(value))
  const step = [1, 2, 2.5, 5, 10].find((s) => s * magnitude >= value / 4) ?? 10
  return Math.ceil(value / (step * magnitude)) * step * magnitude
}

export function Legend({ series, shape = 'line' }: { series: Series[]; shape?: 'line' | 'rect' }) {
  if (series.length < 2) return null
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
      {series.map((item, index) => (
        <span key={item.name} className="inline-flex items-center gap-1.5">
          <span className={shape === 'line' ? 'h-0.5 w-3.5 rounded-full' : 'h-2.5 w-2.5 rounded-sm'} style={{ background: item.color ?? SERIES_COLORS[index] }} />
          {item.name}
        </span>
      ))}
    </div>
  )
}

function Tooltip({ x, y, width, children }: { x: number; y: number; width: number; children: ReactNode }) {
  const left = Math.min(Math.max(x - 80, 0), Math.max(width - 168, 0))
  return (
    <div className="pointer-events-none absolute z-10 w-[168px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-pop" style={{ left, top: Math.max(y - 8, 0), transform: 'translateY(-100%)' }}>
      {children}
    </div>
  )
}

/** Line chart over a shared x axis with a crosshair that snaps to the nearest point and lists every series. */
export function LineChart({ labels, series, height = 240, format = (v: number) => full.format(v), area = series.length === 1 }: {
  labels: string[]; series: Series[]; height?: number; format?: (value: number) => string; area?: boolean
}) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const pad = { top: 12, right: 12, bottom: 26, left: 44 }
  const innerW = Math.max(width - pad.left - pad.right, 10)
  const innerH = height - pad.top - pad.bottom
  const max = niceMax(Math.max(1, ...series.flatMap((s) => s.values)))
  const x = (i: number) => pad.left + (labels.length <= 1 ? innerW / 2 : (i / (labels.length - 1)) * innerW)
  const y = (v: number) => pad.top + innerH - (v / max) * innerH
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max)
  const every = Math.max(1, Math.ceil(labels.length / Math.max(2, Math.floor(innerW / 64))))

  const onMove = (event: React.PointerEvent<SVGRectElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    const ratio = (event.clientX - box.left) / box.width
    setHover(Math.round(ratio * (labels.length - 1)))
  }

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={series.map((s) => s.name).join(', ')}>
          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={pad.left} x2={width - pad.right} y1={y(tick)} y2={y(tick)} stroke="#e2e8f0" strokeDasharray={tick === 0 ? undefined : '3 4'} />
              <text x={pad.left - 8} y={y(tick)} dy="0.32em" textAnchor="end" className="fill-slate-400 text-[11px]">{formatCompact(tick)}</text>
            </g>
          ))}
          {labels.map((label, i) => (i % every === 0 || i === labels.length - 1) && (
            <text key={label + i} x={x(i)} y={height - 6} textAnchor="middle" className="fill-slate-400 text-[11px]">{label}</text>
          ))}
          {series.map((item, index) => {
            const color = item.color ?? SERIES_COLORS[index]
            const points = item.values.map((v, i) => `${x(i)},${y(v)}`).join(' ')
            return (
              <g key={item.name}>
                {area && <polygon points={`${x(0)},${y(0)} ${points} ${x(item.values.length - 1)},${y(0)}`} fill={color} opacity={0.08} />}
                <polyline points={points} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
              </g>
            )
          })}
          {hover !== null && (
            <g>
              <line x1={x(hover)} x2={x(hover)} y1={pad.top} y2={pad.top + innerH} stroke="#94a3b8" strokeWidth={1} />
              {series.map((item, index) => (
                <circle key={item.name} cx={x(hover)} cy={y(item.values[hover] ?? 0)} r={4} fill={item.color ?? SERIES_COLORS[index]} stroke="#fff" strokeWidth={2} />
              ))}
            </g>
          )}
          <rect x={pad.left} y={pad.top} width={innerW} height={innerH} fill="transparent" onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
        </svg>
      )}
      {hover !== null && (
        <Tooltip x={x(hover)} y={Math.min(...series.map((s) => y(s.values[hover] ?? 0)))} width={width}>
          <p className="mb-1 text-slate-500">{labels[hover]}</p>
          {series.map((item, index) => (
            <p key={item.name} className="flex items-center justify-between gap-3">
              <span className="inline-flex items-center gap-1.5 text-slate-500"><span className="h-0.5 w-3 rounded-full" style={{ background: item.color ?? SERIES_COLORS[index] }} />{item.name}</span>
              <span className="font-semibold text-slate-900">{format(item.values[hover] ?? 0)}</span>
            </p>
          ))}
        </Tooltip>
      )}
    </div>
  )
}

/** Vertical bars for one series; each bar is its own hover target. */
export function BarChart({ labels, values, height = 220, color = SERIES_COLORS[0], name, format = (v: number) => full.format(v) }: {
  labels: string[]; values: number[]; height?: number; color?: string; name: string; format?: (value: number) => string
}) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const pad = { top: 12, right: 8, bottom: 26, left: 44 }
  const innerW = Math.max(width - pad.left - pad.right, 10)
  const innerH = height - pad.top - pad.bottom
  const max = niceMax(Math.max(1, ...values))
  const slot = innerW / Math.max(values.length, 1)
  const barW = Math.max(Math.min(slot - 2, 36), 2)
  const y = (v: number) => pad.top + innerH - (v / max) * innerH
  const every = Math.max(1, Math.ceil(labels.length / Math.max(2, Math.floor(innerW / 56))))

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={name}>
          {[0, 0.5, 1].map((t) => t * max).map((tick) => (
            <g key={tick}>
              <line x1={pad.left} x2={width - pad.right} y1={y(tick)} y2={y(tick)} stroke="#e2e8f0" strokeDasharray={tick === 0 ? undefined : '3 4'} />
              <text x={pad.left - 8} y={y(tick)} dy="0.32em" textAnchor="end" className="fill-slate-400 text-[11px]">{formatCompact(tick)}</text>
            </g>
          ))}
          {values.map((value, i) => {
            const cx0 = pad.left + slot * i + (slot - barW) / 2
            const top = y(value)
            const h = Math.max(pad.top + innerH - top, value > 0 ? 2 : 0)
            const r = Math.min(4, barW / 2, h)
            return (
              <g key={i} onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)}>
                <rect x={pad.left + slot * i} y={pad.top} width={slot} height={innerH} fill="transparent" />
                {/* rounded data end, square at the baseline */}
                <path d={`M${cx0},${top + h} V${top + r} Q${cx0},${top} ${cx0 + r},${top} H${cx0 + barW - r} Q${cx0 + barW},${top} ${cx0 + barW},${top + r} V${top + h} Z`}
                  fill={color} opacity={hover === null || hover === i ? 1 : 0.55} />
                {(i % every === 0 || i === values.length - 1) && (
                  <text x={cx0 + barW / 2} y={height - 6} textAnchor="middle" className="fill-slate-400 text-[11px]">{labels[i]}</text>
                )}
              </g>
            )
          })}
        </svg>
      )}
      {hover !== null && (
        <Tooltip x={pad.left + slot * hover + slot / 2} y={y(values[hover])} width={width}>
          <p className="text-slate-500">{labels[hover]}</p>
          <p className="text-sm font-semibold text-slate-900">{format(values[hover])}</p>
          <p className="text-slate-500">{name}</p>
        </Tooltip>
      )}
    </div>
  )
}

/** Ranked horizontal bars with the label and value always visible (no hover needed). */
export function BarList({ items, format = (v: number) => full.format(v), color = SERIES_COLORS[0] }: {
  items: Array<{ label: ReactNode; value: number; hint?: ReactNode }>; format?: (value: number) => string; color?: string
}) {
  const max = Math.max(1, ...items.map((item) => item.value))
  return (
    <ul className="space-y-2.5">
      {items.map((item, index) => (
        <li key={index}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="min-w-0 truncate text-slate-700">{item.label}</span>
            <span className="shrink-0 font-medium text-slate-900">{format(item.value)}{item.hint && <span className="ml-1.5 text-xs font-normal text-slate-500">{item.hint}</span>}</span>
          </div>
          <div className="h-1.5 rounded-full bg-slate-100">
            <div className="h-full rounded-full" style={{ width: `${(item.value / max) * 100}%`, background: color }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

/** Share-of-total strip for 2–3 parts; every part is labeled with its value, so color is never the only key. */
export function ShareBar({ parts, showCounts = true }: { parts: Array<{ label: string; value: number }>; showCounts?: boolean }) {
  const total = Math.max(1, parts.reduce((sum, part) => sum + part.value, 0))
  return (
    <div>
      <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full">
        {parts.map((part, index) => (
          <div key={part.label} style={{ width: `${(part.value / total) * 100}%`, background: SERIES_COLORS[index] }} className={cx(index === 0 && 'rounded-l-full', index === parts.length - 1 && 'rounded-r-full')} />
        ))}
      </div>
      <div className="mt-3 grid gap-2" style={{ gridTemplateColumns: `repeat(${parts.length}, minmax(0, 1fr))` }}>
        {parts.map((part, index) => (
          <div key={part.label}>
            <p className="flex items-center gap-1.5 text-xs text-slate-500"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: SERIES_COLORS[index] }} />{part.label}</p>
            <p className="mt-0.5 text-sm font-semibold text-slate-900">{Math.round((part.value / total) * 100)}%{showCounts && <span className="font-normal text-slate-500"> · {full.format(part.value)}</span>}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

export function Delta({ value, suffix = 'so với kỳ trước' }: { value: number | null; suffix?: string }) {
  if (value === null) return <span className="text-xs text-slate-400">Chưa có dữ liệu kỳ trước</span>
  const up = value >= 0
  return (
    <span className="text-xs text-slate-500">
      <span className={cx('font-semibold', up ? 'text-emerald-600' : 'text-rose-600')}>{up ? '▲' : '▼'} {Math.abs(value).toFixed(1)}%</span> {suffix}
    </span>
  )
}
