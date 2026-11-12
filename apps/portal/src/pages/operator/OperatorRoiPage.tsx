import { useEffect, useState } from 'react'
import { Clock, Percent, PiggyBank, Timer, TrendingUp } from 'lucide-react'
import { Alert, Card, CardHeader, Input, PageHeader, Spinner, StatCard } from '../../components/ui'
import { BarList, Delta, formatCompact } from '../../components/charts'
import { errorMessage } from '../../lib/api'
import { roiApi, type RoiAnalytics } from '../../lib/operatorApi'

const dash = (v: number | null, f: (n: number) => string) => (v === null ? '—' : f(v))
const Basis = ({ text }: { text: string }) => <span title={text}>Cách tính: {text}</span>

export function OperatorRoiPage() {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [data, setData] = useState<RoiAnalytics | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    setData(null)
    roiApi.get(from, to).then(setData).catch((err) => setError(errorMessage(err)))
  }, [from, to])

  const bt = data?.backtest
  return (
    <div className="space-y-4">
      <PageHeader title="Giá trị kinh doanh (ROI)" description="Số liệu sống từ báo giá của bạn; mỗi chỉ số kèm cách tính." />
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">Từ ngày khởi hành <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label className="flex items-center gap-2">đến <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
      </div>
      {error && <Alert tone="red">{error}</Alert>}
      {!data && !error && <Spinner />}
      {data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard label="Giờ công tiết kiệm" value={dash(data.hours_saved.value, (n) => `${n.toFixed(1)} giờ`)} icon={Clock} tone="green"
              hint={<><Basis text={data.hours_saved.basis} /><br />{data.sent_count} báo giá đã gửi</>} />
            <StatCard label="Thời gian phản hồi trung vị" value={dash(data.median_response_minutes.value, (n) => `${n.toFixed(0)} phút`)} icon={Timer}
              hint={<Basis text={data.median_response_minutes.basis} />} />
            <StatCard label="Tỉ lệ chốt" value={dash(data.win_rate.value, (n) => `${(n * 100).toFixed(1)}%`)} icon={Percent} tone="amber"
              hint={<><Basis text={data.win_rate.basis} /><br />{data.won_count} chốt · {data.lost_count} mất</>} />
            <StatCard label="Lãi thêm trên đơn đã chốt (so với markup cố định)" value={dash(data.margin_uplift_vnd.value, (n) => `${n > 0 ? '+' : ''}${formatCompact(n)}đ`)} icon={TrendingUp} tone="green"
              hint={<><Basis text={data.margin_uplift_vnd.basis} /><br /><Delta value={data.margin_uplift_vnd.pct_of_fixed_markup_profit} suffix="so với lợi nhuận markup cố định" /></>} />
            <StatCard label="Hoa hồng OTA tránh được" value={dash(data.ota_commission_avoided_vnd.value, (n) => `${formatCompact(n)}đ`)} icon={PiggyBank} tone="amber"
              hint={<Basis text={data.ota_commission_avoided_vnd.basis} />} />
          </div>

          {bt && (
            <Card>
              <CardHeader title="Backtest bộ tối ưu giá so với markup cố định 25%" description={bt.basis} />
              <div className="space-y-3 p-5">
                {bt.dataset_status === 'synthetic' && <Alert tone="amber">Dữ liệu giả lập — chứng minh phương pháp, chưa phải kết quả thực tế.</Alert>}
                <BarList items={bt.strategies.map((s) => ({ label: s.label, value: s.expected_profit_vnd,
                  hint: `${s.profit_vs_baseline_pct === null ? '' : `${s.profit_vs_baseline_pct >= 0 ? '+' : ''}${s.profit_vs_baseline_pct}% · `}tỉ lệ chốt ${(s.expected_win_rate * 100).toFixed(1)}%` }))}
                  format={(v) => `${formatCompact(v)}đ`} />
                <p className="text-xs text-slate-500">{bt.quotes} báo giá thử nghiệm{bt.period ? `, ${bt.period[0]} đến ${bt.period[1]}` : ''}.</p>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
