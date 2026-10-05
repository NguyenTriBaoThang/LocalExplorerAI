import type { ReactNode } from 'react'
import { STATUS_LABEL, type Status } from '../data/site'

export function StatusBadge({ status }: { status: Status }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABEL[status]}</span>
}

export function PageHeader({ eyebrow, title, lead }: { eyebrow: string; title: string; lead: ReactNode }) {
  return (
    <header className="page-head">
      <p className="eyebrow mono">{eyebrow}</p>
      <h1>{title}</h1>
      <p className="lead">{lead}</p>
    </header>
  )
}

export function DemoLabel({ children }: { children?: ReactNode }) {
  return (
    <p className="demo-label mono">
      <span className="dot" aria-hidden /> Interactive demo — client-side sample data{children ? ` · ${children}` : ''}
    </p>
  )
}

export function Callout({ tone = 'note', title, children }: { tone?: 'note' | 'warn'; title: string; children: ReactNode }) {
  return (
    <aside className={`callout callout-${tone}`}>
      <strong>{title}</strong>
      <div>{children}</div>
    </aside>
  )
}

export function Src({ path }: { path: string }) {
  return <code className="src mono">{path}</code>
}
