import type { ReactNode } from 'react'

/** Khung nổi trên bản đồ; thu gọn thành nút nhỏ ghi tiêu đề (+ badge). Không biết gì về nội dung. */
export default function FloatingPanel({ side, title, subtitle, open, onToggle, badge = 0, children }: {
  side: 'left' | 'right'; title: string; subtitle?: string; open: boolean; onToggle: () => void
  badge?: number; children: ReactNode
}) {
  const pos = side === 'left' ? 'left-20' : 'right-4'
  if (!open) {
    return (
      <button type="button" onClick={onToggle} aria-expanded={false}
        className={`absolute top-4 ${pos} z-10 flex items-center gap-2 rounded-xl bg-mist/95 px-3.5 py-2 text-sm font-semibold shadow-lg`}>
        {title}
        {badge > 0 && <span className="rounded-full bg-marigold px-1.5 text-xs text-stone-900">{badge}</span>}
      </button>
    )
  }
  return (
    <section aria-label={title}
      className={`absolute inset-y-4 ${pos} z-10 flex ${side === 'left' ? 'w-[340px]' : 'w-96'} max-w-[calc(100vw-6rem)] flex-col overflow-hidden rounded-2xl bg-mist/95 shadow-xl backdrop-blur`}>
      <header className="flex items-center gap-2 border-b border-stone-200 px-4 py-3">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-[15px] font-bold">{title}</h2>
          {subtitle && <p className="truncate text-xs text-stone-500">{subtitle}</p>}
        </div>
        <button type="button" onClick={onToggle} aria-expanded aria-label={`Thu gọn ${title}`} title="Thu gọn"
          className="grid size-7 place-items-center rounded-lg border border-stone-200 bg-white text-stone-500">
          {side === 'left' ? '‹' : '›'}
        </button>
      </header>
      {children}
    </section>
  )
}
