export type Panels = { chat: boolean; timeline: boolean }
export const NARROW = '(max-width: 1099px)'

/** Cửa sổ hẹp chỉ chứa một panel: mở panel này thì đóng panel kia. */
export function setPanel(p: Panels, side: keyof Panels, open: boolean, narrow: boolean): Panels {
  const next = { ...p, [side]: open }
  if (narrow && open) next[side === 'chat' ? 'timeline' : 'chat'] = false
  return next
}
