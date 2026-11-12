import { Clock, Percent, Wallet } from 'lucide-react'
import { PageHeader, StatCard } from '../../components/ui'
import { useOperator } from './OperatorLayout'

export function OperatorOverviewPage() {
  const { org } = useOperator()
  return (
    <div>
      <PageHeader title={org.name} description="Tổng quan Trợ lý báo giá & biên lợi nhuận." />
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Biên tối thiểu" value={`${org.margin_floor_pct}%`} icon={Percent} tone="amber" />
        <StatCard label="Đặt cọc" value={`${org.deposit_pct}%`} icon={Wallet} tone="green" />
        <StatCard label="Hiệu lực báo giá" value={`${org.quote_validity_days} ngày`} icon={Clock} />
      </div>
    </div>
  )
}
