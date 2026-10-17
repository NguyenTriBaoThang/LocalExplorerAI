import { useState, type ReactNode } from 'react'

export type ChatItem = { role: 'user' | 'ai' | 'tool' | 'error'; text: string; version?: number | null }
export type GroupReviewRetry = { feedback: string; sourceVersion: number; message: string }

const STYLE: Record<ChatItem['role'], string> = {
  user: 'self-end bg-emerald-700 text-white',
  ai: 'bg-[var(--bg-surface)] border border-[var(--border)]',
  tool: 'text-xs italic text-[var(--text-muted)]',
  error: 'bg-red-50 text-red-700 border border-red-200',
}

const SUGGESTIONS = [
  'Sài Gòn 2 ngày, 3 triệu, 2 người, thích cafe và lịch sử',
  'TP.HCM 3 ngày cho gia đình có trẻ nhỏ, đi ô tô',
  'Sài Gòn 1 ngày tham quan và ăn uống, đi xe máy',
]

export default function ChatPanel({ items, busy, onSend, children, versions = [], version = null, latest = null,
  onGroupReview, onRetryGroupReview, retry, reviewPending = false }: {
  items: ChatItem[]; busy: boolean; onSend: (message: string) => void; children?: ReactNode
  versions?: number[]; version?: number | null; latest?: number | null
  onGroupReview?: (feedback: string, sourceVersion: number) => Promise<boolean>
  onRetryGroupReview?: (feedback: string, sourceVersion: number) => Promise<boolean>
  retry?: GroupReviewRetry | null
  reviewPending?: boolean
}) {
  const [text, setText] = useState('')
  const [groupMode, setGroupMode] = useState(false)
  const [sourceVersion, setSourceVersion] = useState<number | null>(null)
  const canGroupReview = version != null && versions.length > 0 && onGroupReview != null
  const selectedSource = sourceVersion ?? version
  const sourceIsOld = selectedSource != null && latest != null && selectedSource !== latest

  async function retryPreview() {
    if (!retry || busy || !onRetryGroupReview) return
    const draftAtRetry = text
    const succeeded = await onRetryGroupReview(retry.feedback, retry.sourceVersion)
    if (succeeded && draftAtRetry.trim() === retry.feedback) {
      setText((current) => current === draftAtRetry ? '' : current)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-4" aria-live="polite">
        {items.length === 0 && !groupMode && (
          <div className="grid gap-3 py-2">
            <h3 className="text-2xl font-extrabold leading-tight tracking-tight text-[var(--text-main)]">Cuối tuần này bạn muốn đi đâu?</h3>
            <p className="text-sm text-[var(--text-muted)]">Cho Local Explorer AI biết nơi đến, số ngày và ngân sách. Lịch trình hiện ngay trên bản đồ, sửa bằng cách nhắn tiếp.</p>
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" disabled={busy} onClick={() => onSend(s)}
                className="rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] px-3 py-2.5 text-left text-sm hover:border-[var(--border)] disabled:opacity-50">
                {s}
              </button>
            ))}
          </div>
        )}
        {items.map((it, i) => (
          <div key={i} className={`max-w-[90%] rounded-xl px-3 py-2 text-sm ${STYLE[it.role]}`}>
            {it.version != null && <div className="mb-1 text-[10px] font-semibold opacity-75">
              {it.role === 'user' ? `Góp ý cho v${it.version}` : `Lịch trình v${it.version}`}
            </div>}
            {it.text}
          </div>
        ))}
        {children}
        {busy && <div className="animate-pulse text-xs text-[var(--text-muted)]">AI đang lên lịch trình…</div>}
      </div>
      {canGroupReview && (
        <div className="border-t border-[var(--border)] px-3 pt-2">
          <button type="button" disabled={busy || (!groupMode && reviewPending)} onClick={() => {
            if (groupMode) setGroupMode(false)
            else { setSourceVersion(version); setGroupMode(true) }
          }} className="rounded-full border border-[var(--border)] px-3 py-1 text-xs font-semibold text-[var(--text-main)] disabled:opacity-50">
            {groupMode ? 'Quay lại chat thường' : 'Góp ý nhóm'}
          </button>
          {groupMode && (
            <div className="mt-2 grid gap-2">
              {reviewPending && <p className="text-xs text-[var(--text-muted)]">Hãy áp dụng hoặc huỷ preview hiện có trước khi tạo góp ý khác.</p>}
              <label className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                <span>Bản góp ý</span>
                <select aria-label="Version nguồn góp ý" value={selectedSource ?? ''} disabled={busy}
                  onChange={(e) => setSourceVersion(Number(e.target.value))}
                  className="rounded border border-stone-300 bg-[var(--bg-surface)] px-2 py-1 text-[var(--text-main)]">
                  {versions.map((v) => <option key={v} value={v}>v{v}{v === latest ? ' · mới nhất' : ''}</option>)}
                </select>
              </label>
              {sourceIsOld && (
                <p role="status" className="rounded-lg bg-amber-50 px-2.5 py-2 text-xs text-amber-900">
                  Bạn đang góp ý trên v{selectedSource}; bản mới nhất hiện là v{latest}. Preview sẽ đối chiếu với bản mới nhất.
                </p>
              )}
            </div>
          )}
        </div>
      )}
      {retry && (
        <div role="status" className="mx-3 mt-2 rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-xs text-amber-900">
          <p>{retry.message}</p>
          <button type="button" disabled={busy || !onRetryGroupReview} onClick={() => void retryPreview()}
            className="mt-2 rounded bg-amber-700 px-2.5 py-1 font-semibold text-white disabled:opacity-50">
            Tạo lại preview
          </button>
        </div>
      )}
      <form className="flex gap-2 border-t border-[var(--border)] p-3" onSubmit={(e) => {
        e.preventDefault()
        const m = text.trim()
        if (!m || busy) return
        if (groupMode && selectedSource != null && onGroupReview) {
          const draftAtSubmit = text
          void onGroupReview(m, selectedSource).then((created) => {
            if (created) setText((current) => current === draftAtSubmit ? '' : current)
          })
        } else {
          setText('')
          onSend(m)
        }
      }}>
        <input aria-label={groupMode ? 'Góp ý nhóm' : 'Yêu cầu chuyến đi'}
          placeholder={groupMode ? `Góp ý cho bản v${selectedSource}…` : 'Nhắn cho Travility…'}
          className="min-w-0 flex-1 rounded-lg border border-stone-300 bg-[var(--bg-surface)] px-3 py-2 text-sm"
          value={text} onChange={(e) => setText(e.target.value)} />
        <button disabled={busy || (groupMode && (selectedSource == null || reviewPending))}
          className="rounded-lg bg-amber-400 px-4 text-sm font-semibold text-[var(--text-main)] disabled:opacity-50">
          {groupMode ? 'Tạo preview' : 'Gửi'}
        </button>
      </form>
    </div>
  )
}
