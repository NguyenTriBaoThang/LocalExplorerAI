import { test } from 'node:test'
import assert from 'node:assert/strict'
import { clarifyAfter, confirmAfter, mealOf, viewingOld, toAnswers } from './tripState.ts'
import { buildTripPrintModel } from './tripPrint.ts'
import type { Itinerary } from '../../api/trips'

test('a failed plan retains clarification, a successful plan dismisses it', () => {
  const c = { tripId: 2, questions: [] }
  assert.equal(clarifyAfter(c, { type: 'error', message: 'quota' }), c)
  assert.equal(clarifyAfter(c, { type: 'itinerary' } as any), null)
})
test('confirmation persists while searching, but clears after an answer', () => {
  const c = { tripId: 2, text: 'Lập lại?', changes: {}, message: '3 ngày' }
  assert.equal(confirmAfter(c, { type: 'thinking', text: 'Tìm…' }), c)
  assert.equal(confirmAfter(c, { type: 'answer', text: 'Đã trả lời' }), null)
})
test('meal boundaries, old versions and empty clarification fields', () => {
  assert.equal(mealOf('an-uong', '10:00'), null)
  assert.equal(mealOf('an-uong', '11:00'), 'Bữa trưa')
  assert.equal(mealOf('cafe', '11:00'), null)
  assert.equal(viewingOld(1, 3), true)
  assert.equal(viewingOld(null, 3), false)
  assert.deepEqual(toAnswers({ arrival_time: '', travel_mode: 'xe-may' }), { travel_mode: 'xe-may' })
})
test('print uses the selected snapshot and does not invent missing places', () => {
  const itinerary: Itinerary = { stay_place_id: 9, total_cost: 45000, summary: '', conflicts: [], days: [{ date: null, rain_chance: null, legs: [], stops: [{ place_id: 1, start_time: '09:00', duration_min: 60, reason: 'Cafe', pinned: false, est_cost: 45000 }] }] }
  const model = buildTripPrintModel({ id: 1, spec: { destination: 'tp-hcm', days: 1 }, created_at: '', destination_name: 'TP.HCM' }, 2, itinerary, {}, '2026-10-17T00:00:00Z')
  assert.equal(model.version, 2)
  assert.equal(model.stayName, null)
  assert.equal(model.days[0].stops[0].placeName, 'Địa điểm không xác định')
  assert.equal(model.totalCost, 45000)
})
