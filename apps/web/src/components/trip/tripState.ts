import type { AgentEvent, Clarify, ConfirmReplan, Answers } from '../../api/trips'
const MEALS: [string, string, string][] = [['Bữa sáng', '06:00', '10:00'], ['Bữa trưa', '11:00', '14:00'], ['Bữa tối', '17:00', '21:00']]

export function mealOf(kind: string | undefined, startTime: string): string | null {
  if (kind !== 'an-uong') return null
  return MEALS.find(([, lo, hi]) => lo <= startTime && startTime < hi)?.[0] ?? null
}


export function clarifyAfter(current: Clarify | null, e: AgentEvent): Clarify | null {
  if (e.type === 'clarify') return { tripId: e.trip_id, questions: e.questions }
  if (e.type === 'itinerary') return null
  return current
}


export function confirmAfter(current: ConfirmReplan | null, e: AgentEvent): ConfirmReplan | null {
  if (e.type === 'confirm_replan') return { tripId: e.trip_id, text: e.text, changes: e.changes, message: e.message }
  if (e.type === 'thinking' || e.type === 'tool_call') return current
  return null
}

/** Bỏ trường rỗng (ô giờ chưa nhập, chip chưa chọn) để server không trả 422. */
export function toAnswers(form: Record<string, string>): Answers {
  return Object.fromEntries(Object.entries(form).filter(([, v]) => v !== '')) as Answers
}

export const viewingOld = (version: number | null, latest: number | null) =>
  version != null && latest != null && version !== latest

