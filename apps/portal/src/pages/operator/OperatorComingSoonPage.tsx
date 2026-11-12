import { Hourglass } from 'lucide-react'
import { Card, EmptyState, PageHeader } from '../../components/ui'

export function OperatorComingSoonPage({ title }: { title: string }) {
  return (
    <div>
      <PageHeader title={title} />
      <Card><EmptyState icon={Hourglass} title="Sắp ra mắt" description="Tính năng này đang được phát triển." /></Card>
    </div>
  )
}
