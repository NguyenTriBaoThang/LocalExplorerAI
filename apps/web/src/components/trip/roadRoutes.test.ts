import { test } from 'node:test'
import assert from 'node:assert/strict'
import { roadSegments } from './roadRoutes.ts'
import type { Itinerary, Place } from '../../api/trips'

const places = Object.fromEntries([1, 2, 3].map(id => [id, { id, lat: 10 + id, lon: 106 + id } as Place]))
test('road segments preserve day order and hotel return', () => {
  const trip = { stay_place_id: 3, days: [{ stops: [{ place_id: 1 }, { place_id: 2 }] }] } as Itinerary
  assert.deepEqual(roadSegments(trip, places).map(s => [s.day, s.origin.id, s.destination.id]), [[0, 3, 1], [0, 1, 2], [0, 2, 3]])
})
test('missing stop coordinates never bridge unrelated stops', () => {
  const trip = { stay_place_id: null, days: [{ stops: [{ place_id: 1 }, { place_id: 999 }, { place_id: 2 }] }] } as Itinerary
  assert.equal(roadSegments(trip, places).length, 0)
  assert.equal(roadSegments(null, places).length, 0)
})
