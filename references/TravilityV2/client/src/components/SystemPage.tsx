import { useEffect, useState } from 'react'
import { getSystemStatus, tiers, type NodeState, type SystemNode, type SystemStatus } from '../api'

const BOX: Record<NodeState, string> = {
  up: 'border-emerald-500 bg-emerald-50',
  down: 'border-red-500 bg-red-50',
  unknown: 'border-stone-300 bg-stone-100 text-stone-500',
}
const DOT: Record<NodeState, string> = { up: 'bg-emerald-500', down: 'bg-red-500', unknown: 'bg-stone-400' }
const STATE: Record<NodeState, string> = { up: 'đang chạy', down: 'đã chết', unknown: 'không rõ' }
const REFRESH_MS = 2000

function note(n: SystemNode, s: SystemStatus): string | null {
  if (n.name === s.served_by) return 'vừa phục vụ bạn'
  if (s.my_shard != null && n.name === `pg-shard-${s.my_shard}`) return 'shard của bạn'
  if (n.lag_ms != null) return `trễ ${n.lag_ms} ms`
  return null
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-white px-4 py-3 shadow-sm">
      <dt className="text-xs font-semibold uppercase tracking-wider text-stone-500">{label}</dt>
      <dd className="mt-1 text-sm font-semibold">{value}</dd>
    </div>
  )
}

/** Sơ đồ cụm theo tầng (spec scale §12, S32). Tự làm mới; node chết đổi đỏ, không rõ thì xám. */
export default function SystemPage({ token, onClose }: { token: string; onClose: () => void }) {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [lost, setLost] = useState(false)

  useEffect(() => {
    let live = true
    let timer = 0
    // Hẹn lần kế tiếp sau khi có phản hồi: một node treo làm server trả chậm thì request không chồng lên nhau.
    const tick = async () => {
      try {
        const s = await getSystemStatus(token)
        if (live) { setStatus(s); setLost(false) }
      } catch {
        if (live) setLost(true)
      }
      if (live) timer = window.setTimeout(tick, REFRESH_MS)
    }
    tick()
    return () => { live = false; clearTimeout(timer) }
  }, [token])

  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    addEventListener('keydown', esc)
    return () => removeEventListener('keydown', esc)
  }, [onClose])

  const st = status?.stats
  return (
    <div role="dialog" aria-label="Hệ thống" className="absolute inset-y-0 left-16 right-0 z-30 overflow-y-auto bg-mist p-6">
      <header className="mb-6 flex items-center gap-3">
        <h2 className="text-xl font-bold">Hệ thống</h2>
        {lost && (
          <span role="status" className="rounded-full bg-red-100 px-3 py-1 text-sm text-red-800">
            Mất kết nối tới máy chủ, đang thử lại…
          </span>
        )}
        <div className="flex-1" />
        <button type="button" onClick={onClose} aria-label="Đóng trang Hệ thống" title="Đóng"
          className="grid size-9 place-items-center rounded-lg border border-stone-200 bg-white text-stone-600">✕</button>
      </header>
      {!status ? (!lost && <p className="text-stone-500">Đang tải…</p>) : (
        <>
          <div className="space-y-5">
            {tiers(status.nodes).map((t) => (
              <section key={t.label} aria-label={t.label}>
                <h3 className="mb-2 text-center text-xs font-semibold uppercase tracking-wider text-stone-500">{t.label}</h3>
                <ul className="flex flex-wrap justify-center gap-3">
                  {t.nodes.map((n) => {
                    const extra = note(n, status)
                    return (
                      <li key={n.name} className={`min-w-44 rounded-xl border-2 px-4 py-2.5 ${BOX[n.state]} ${
                        n.name === status.served_by ? 'ring-2 ring-marigold ring-offset-2 ring-offset-mist' : ''}`}>
                        <div className="flex items-center gap-2 font-semibold">
                          <span aria-hidden className={`size-2.5 shrink-0 rounded-full ${DOT[n.state]}`} />
                          <span className="truncate">{n.name}</span>
                        </div>
                        <p className="text-xs">{STATE[n.state]}{extra ? ` · ${extra}` : ''}</p>
                      </li>
                    )
                  })}
                </ul>
              </section>
            ))}
          </div>
          <dl className="mx-auto mt-8 grid max-w-4xl grid-cols-2 gap-3 lg:grid-cols-5">
            <Stat label="Lập lịch" value={status.planner_mode === 'multi' ? 'đa agent' : 'agent đơn'} />
            {st ? (
              <>
                <Stat label="Queue" value={`${st.waiting} chờ · ${st.running} đang chạy`} />
                <Stat label="Cache LLM" value={`${st.cache_hit} trúng · ${st.cache_miss} trượt`} />
                <Stat label="Provider" value={`${st.provider_call} lượt · ${st.provider_wait} chờ · ${st.provider_fallback} chuyển`} />
                <Stat label="Rate limit" value={`${st.rate_limited} lượt bị chặn`} />
              </>
            ) : <Stat label="Queue và cache" value="không có số liệu (Redis không chạy)" />}
          </dl>
        </>
      )}
    </div>
  )
}
