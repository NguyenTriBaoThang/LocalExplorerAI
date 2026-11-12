import { useEffect, useState } from 'react'
import { Percent, Receipt, TrendingDown, Wallet } from 'lucide-react'
import { Alert, Card, CardHeader, EmptyState, Input, PageHeader, Spinner, StatCard } from '../../components/ui'
import { BarList, ShareBar, formatCompact } from '../../components/charts'
import { errorMessage } from '../../lib/api'
import { reconcileApi, type MarginAnalytics } from '../../lib/operatorApi'
import { REASON_LABEL, vnd } from './quoteFormat'

const pct = (n: number | null) => (n === null ? '—' : `${n.toFixed(1)}%`)

export function OperatorMarginPage() {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [data, setData] = useState<MarginAnalytics | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    setData(null)
    reconcileApi.margin(from, to).then(setData).catch((err) => setError(errorMessage(err)))
  }, [from, to])

  const t = data?.totals
  const drift = t ? (t.actual_margin_pct ?? 0) - (t.expected_margin_pct ?? 0) : 0
  const over = data?.by_reason.filter((r) => r.variance_vnd > 0) ?? []
  const under = data?.by_reason.filter((r) => r.variance_vnd < 0) ?? []
  return (
    <div className="space-y-4">
      <PageHeader title="Biên lợi nhuận" description="Dự kiến và thực tế của các tour đã đối chiếu hóa đơn." />
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">Từ ngày khởi hành <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label className="flex items-center gap-2">đến <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
      </div>
      {error && <Alert tone="red">{error}</Alert>}
      {!data && !error && <Spinner />}
      {data && t && t.quotes === 0 && <Card><EmptyState icon={Receipt} title="Chưa có tour nào được đối chiếu" description="Xác nhận chi phí thực tế ở trang Đối chiếu để thấy biên lợi nhuận thực tế." /></Card>}
      {data && t && t.quotes > 0 && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Số tour đã đối chiếu" value={t.quotes} icon={Receipt} />
            <StatCard label="Biên dự kiến" value={pct(t.expected_margin_pct)} icon={Percent} tone="amber" hint={`Doanh thu ${vnd(t.price_vnd)}`} />
            <StatCard label="Biên thực tế" value={pct(t.actual_margin_pct)} icon={Percent} tone={drift < 0 ? 'red' : 'green'} hint={`${drift >= 0 ? '+' : ''}${drift.toFixed(1)} điểm so với dự kiến`} />
            <StatCard label="Chi phí chênh" value={`${t.variance_vnd > 0 ? '+' : ''}${formatCompact(t.variance_vnd)}đ`} icon={t.variance_vnd > 0 ? TrendingDown : Wallet} tone={t.variance_vnd > 0 ? 'red' : 'green'} hint={`Dự kiến ${vnd(t.expected_cost_vnd)} · thực tế ${vnd(t.actual_cost_vnd)}`} />
          </div>

          <Card>
            <CardHeader title="Biên dự kiến và thực tế theo tour" />
            <div className="space-y-3 p-5">
              <BarList items={data.quotes.flatMap((q) => [
                { label: `${q.code} · dự kiến`, value: q.expected_margin_pct ?? 0, hint: vnd(q.price_vnd - q.expected_cost_vnd) },
                { label: `${q.code} · thực tế`, value: q.actual_margin_pct ?? 0, hint: vnd(q.price_vnd - q.actual_cost_vnd) },
              ])} format={(v) => `${v.toFixed(1)}%`} />
            </div>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader title="Chênh lệch chi phí theo lý do" description="Dương = chi nhiều hơn báo giá, âm = chi ít hơn." />
              <div className="space-y-4 p-5">
                {over.length > 0 && <ShareBar showCounts={false} parts={over.slice(0, 3).map((r) => ({ label: REASON_LABEL[r.reason] ?? r.reason, value: r.variance_vnd }))} />}
                <BarList color="#eb6834" items={data.by_reason.map((r) => ({ label: REASON_LABEL[r.reason] ?? r.reason, value: Math.abs(r.variance_vnd), hint: `${r.variance_vnd > 0 ? '+' : '-'}${vnd(Math.abs(r.variance_vnd))} · ${r.count} dòng` }))} format={(v) => vnd(v)} />
                {under.length > 0 && <p className="text-xs text-slate-500">Các khoản âm là tiết kiệm so với báo giá.</p>}
              </div>
            </Card>
            <Card>
              <CardHeader title="Chênh lệch theo nhà cung cấp" />
              <div className="p-5">
                <BarList items={data.by_supplier.map((s) => ({ label: s.supplier, value: Math.abs(s.variance_vnd), hint: `${s.variance_vnd > 0 ? '+' : s.variance_vnd < 0 ? '-' : ''}${vnd(Math.abs(s.variance_vnd))} (báo giá ${vnd(s.quoted_vnd)})` }))} format={(v) => vnd(v)} />
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
