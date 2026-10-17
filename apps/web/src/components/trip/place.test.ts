import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import type { Itinerary } from '../../api/trips'
import { kindStyle, openToday, selectedPlace, tourStops } from './place.ts'

const WEEK = { mon: ['07:00', '22:00'], tue: ['07:00', '22:00'], wed: ['07:00', '22:00'], thu: ['07:00', '22:00'],
  fri: ['07:00', '22:00'], sat: ['07:00', '22:00'], sun: null } as Record<string, [string, string] | null>

describe('openToday', () => {
  it('ngày cụ thể → giờ mở hôm đó (2026-10-18 là Chủ Nhật)', () => {
    assert.deepEqual(openToday(WEEK, '2026-10-17'), 'Mở hôm nay 07:00–22:00')
    assert.deepEqual(openToday(WEEK, '2026-10-18'), 'Hôm nay đóng cửa')
  })
  it('{} hoặc 00:00–24:00 → mở cả ngày', () => {
    assert.deepEqual(openToday({}, '2026-10-17'), 'Mở cả ngày')
    assert.deepEqual(openToday({ sat: ['00:00', '24:00'] }, '2026-10-17'), 'Mở cả ngày')
  })
  it('không có ngày: 7 ngày giống nhau thì hiện giờ, khác nhau thì ẩn', () => {
    const same = Object.fromEntries(['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'].map((d) => [d, ['08:00', '17:00']]))
    assert.deepEqual(openToday(same as Record<string, [string, string]>, null), 'Mở 08:00–17:00')
    assert.equal(openToday(WEEK, null), null)
  })
  it('Itinerary lưu trước T4 không có open_hours → ẩn dòng', () => {
    assert.equal(openToday(undefined, '2026-10-17'), null)
  })
})

describe('kindStyle', () => {
  it('kind biết → nhãn tiếng Việt; kind lạ → mặc định', () => {
    assert.deepEqual(kindStyle('cafe').label, 'Cafe')
    assert.deepEqual(kindStyle('an-uong').label, 'Ăn uống')
    assert.deepEqual(kindStyle('xyz').label, 'Địa điểm')
  })
})

const IT = {
  stay_place_id: 9, total_cost: 0, conflicts: [], summary: '',
  days: [
    { date: null, rain_chance: null, legs: [], stops: [{ place_id: 1 }, { place_id: 2 }] },
    { date: null, rain_chance: null, legs: [], stops: [{ place_id: 3 }] },
  ],
} as unknown as Itinerary

describe('selectedPlace', () => {
  it('Stop, Stay, không chọn, chỉ số lệch (Itinerary vừa đổi)', () => {
    assert.deepEqual(selectedPlace(IT, { day: 1, stop: 0 }), 3)
    assert.deepEqual(selectedPlace(IT, 'stay'), 9)
    assert.equal(selectedPlace(IT, null), null)
    assert.equal(selectedPlace(IT, { day: 5, stop: 0 }), null)
    assert.equal(selectedPlace(null, { day: 0, stop: 0 }), null)
  })
})

describe('tourStops', () => {
  it('theo ngày rồi theo thứ tự Stop', () => {
    assert.deepEqual(tourStops(IT), [{ day: 0, stop: 0 }, { day: 0, stop: 1 }, { day: 1, stop: 0 }])
  })
})
