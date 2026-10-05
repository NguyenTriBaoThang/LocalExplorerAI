import type { ReactNode } from 'react'

const RULES: [RegExp, string][] = [
  [/^\/\/.*|^#.*/, 'tok-c'],
  [/^"(?:[^"\\]|\\.)*"(?=\s*:)/, 'tok-k'],
  [/^"(?:[^"\\]|\\.)*"/, 'tok-s'],
  [/^-?\d+(?:\.\d+)?/, 'tok-n'],
  [/^(?:true|false|null)\b/, 'tok-b'],
  [/^(?:GET|POST|PUT|PATCH|DELETE)\b/, 'tok-m'],
]

/** Tiny tokenizer for the JSON / HTTP snippets in this site; avoids a highlighting dependency. */
export function Highlight({ code }: { code: string }) {
  return (
    <>
      {code.split('\n').map((line, i, all) => {
        const out: ReactNode[] = []
        let rest = line
        let k = 0
        while (rest.length) {
          let hit = false
          for (const [re, cls] of RULES) {
            const m = rest.match(re)
            if (m) {
              out.push(<span key={k++} className={cls}>{m[0]}</span>)
              rest = rest.slice(m[0].length)
              hit = true
              break
            }
          }
          if (!hit) {
            const next = rest.slice(1).search(/["\d\/#GPD-]/)
            const cut = next === -1 ? rest.length : next + 1
            out.push(rest.slice(0, cut))
            rest = rest.slice(cut)
          }
        }
        return <span key={i}>{out}{i < all.length - 1 ? '\n' : ''}</span>
      })}
    </>
  )
}
