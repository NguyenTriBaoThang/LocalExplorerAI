import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { Highlight } from './Highlight'

export function CodeBlock({ code, label }: { code: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard may be blocked; leave the button state unchanged */
    }
  }
  return (
    <div className="code">
      <div className="code-bar">
        <span className="mono dim">{label ?? 'snippet'}</span>
        <button type="button" className="icon-btn" onClick={copy} aria-label={copied ? 'Copied' : `Copy ${label ?? 'snippet'}`}>
          {copied ? <Check size={14} aria-hidden /> : <Copy size={14} aria-hidden />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre tabIndex={0}><code><Highlight code={code} /></code></pre>
    </div>
  )
}
