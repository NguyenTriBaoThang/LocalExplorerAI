import type { SourceEvidence } from '../../types'

export function SourceDetails({ sources }: { sources: SourceEvidence[] }) {
  const links = sources.filter((source) => /^https?:\/\//i.test(source.source_uri))
  if (!links.length) return <p className="text-xs">Chưa có nguồn công khai đã xác minh.</p>
  return <ul className="space-y-1 text-xs">{links.map((source) => <li key={source.id}>
    <a href={source.source_uri} target="_blank" rel="noreferrer" className="underline">{source.source_label || 'Nguồn đã duyệt'}</a>
    {' · Kiểm tra: '}{source.observed_at ? new Date(source.observed_at).toLocaleString('vi-VN') : 'chưa ghi nhận'}
  </li>)}</ul>
}
