import { useEffect, useRef } from 'react'
import { noFeasibleText, signed, vnd, type Proposal } from '../api'

export default function ProposalPanel({ proposal, busy, onApply, onClose }: {
  proposal: Proposal; busy: boolean; onApply: (option: number) => void; onClose: () => void
}) {
  const ref = useRef<HTMLElement>(null)
  // Panel nằm đầu Timeline; nút sự cố thường ở giữa/cuối danh sách → cuộn tới để người dùng thấy kết quả
  useEffect(() => { ref.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }) }, [proposal])
  return (
    <section ref={ref} aria-live="polite" className="mb-3 rounded-xl border border-sky-200 bg-sky-50 p-3 text-sm">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="font-semibold">Phương án thay thế</h2>
        <button type="button" onClick={onClose} className="text-xs text-stone-500 hover:underline">Huỷ</button>
      </div>
      {proposal.no_feasible && (
        <ul className="space-y-1 text-stone-700">
          {noFeasibleText(proposal.no_feasible).map((t) => <li key={t}>{t}</li>)}
        </ul>
      )}
      <ol className="space-y-2">
        {proposal.options?.map((o, i) => {
          const m = o.metrics
          return (
            <li key={i} className="rounded-lg bg-white p-3 shadow-sm">
              <div className="font-medium">{i + 1}. {o.title}</div>
              <p className="mt-1 text-xs text-stone-600">{o.explanation}</p>
              <dl className="mt-2 grid grid-cols-3 gap-1 text-xs">
                <div><dt className="text-stone-500">Chi phí</dt><dd>{signed(m.cost_delta, vnd)}</dd></div>
                <div><dt className="text-stone-500">Di chuyển</dt><dd>{signed(m.travel_min_delta, (x) => `${x} phút`)}</dd></div>
                <div>
                  <dt className="text-stone-500">Giữ mục đích</dt>
                  <dd>{m.retention_after == null ? '—' : `${Math.round(m.retention_after * 100)}%`}</dd>
                </div>
              </dl>
              <button type="button" disabled={busy} onClick={() => onApply(i)}
                className="mt-2 rounded bg-emerald-700 px-3 py-1 text-xs text-white disabled:opacity-50">
                Áp dụng
              </button>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
