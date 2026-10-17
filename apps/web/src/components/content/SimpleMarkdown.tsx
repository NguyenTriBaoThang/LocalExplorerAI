import type { ReactNode } from 'react'

/**
 * Renders the small Markdown subset used by portal articles (headings, paragraphs, lists, quotes, **bold**).
 * Text is always rendered as React text nodes, never as HTML, so article content cannot inject markup.
 */
export function SimpleMarkdown({ source }: { source: string }) {
  const blocks: ReactNode[] = []
  let list: string[] = []
  const flush = () => {
    if (list.length) blocks.push(<ul key={`ul-${blocks.length}`}>{list.map((item, i) => <li key={i}>{inline(item)}</li>)}</ul>)
    list = []
  }
  for (const raw of source.split(/\r?\n/)) {
    const line = raw.trim()
    if (/^[-*] /.test(line)) { list.push(line.slice(2)); continue }
    flush()
    if (!line) continue
    if (line.startsWith('### ')) blocks.push(<h3 key={blocks.length}>{inline(line.slice(4))}</h3>)
    else if (line.startsWith('## ') || line.startsWith('# ')) blocks.push(<h2 key={blocks.length}>{inline(line.replace(/^#+ /, ''))}</h2>)
    else if (line.startsWith('> ')) blocks.push(<blockquote key={blocks.length}>{inline(line.slice(2))}</blockquote>)
    else blocks.push(<p key={blocks.length}>{inline(line)}</p>)
  }
  flush()
  return <div className="prose-content">{blocks}</div>
}

function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) => (part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part))
}
