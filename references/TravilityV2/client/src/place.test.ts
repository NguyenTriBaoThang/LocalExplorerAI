import { describe, expect, it } from 'vitest'
import type { Itinerary } from './api'
import { kindStyle, openToday, selectedPlace, tourStops } from './place'

const WEEK = { mon: ['07:00', '22:00'], tue: ['07:00', '22:00'], wed: ['07:00', '22:00'], thu: ['07:00', '22:00'],
  fri: ['07:00', '22:00'], sat: ['07:00', '22:00'], sun: null } as Record<string, [string, string] | null>

describe('openToday', () => {
  it('ngày cụ thể → giờ mở hôm đó (2026-10-18 là Chủ Nhật)', () => {
    expect(openToday(WEEK, '2026-10-17')).toBe('Mở hôm nay 07:00–22:00')
    expect(openToday(WEEK, '2026-10-18')).toBe('Hôm nay đóng cửa')
  })
  it('{} hoặc 00:00–24:00 → mở cả ngày', () => {
    expect(openToday({}, '2026-10-17')).toBe('Mở cả ngày')
    expect(openToday({ sat: ['00:00', '24:00'] }, '2026-10-17')).toBe('Mở cả ngày')
  })
  it('không có ngày: 7 ngày giống nhau thì hiện giờ, khác nhau thì ẩn', () => {
    const same = Object.fromEntries(['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'].map((d) => [d, ['08:00', '17:00']]))
    expect(openToday(same as Record<string, [string, string]>, null)).toBe('Mở 08:00–17:00')
    expect(openToday(WEEK, null)).toBeNull()
  })
  it('Itinerary lưu trước T4 không có open_hours → ẩn dòng', () => {
    expect(openToday(undefined, '2026-10-17')).toBeNull()
  })
})

describe('kindStyle', () => {
  it('kind biết → nhãn tiếng Việt; kind lạ → mặc định', () => {
    expect(kindStyle('cafe').label).toBe('Cafe')
    expect(kindStyle('an-uong').label).toBe('Ăn uống')
    expect(kindStyle('xyz').label).toBe('Địa điểm')
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
    expect(selectedPlace(IT, { day: 1, stop: 0 })).toBe(3)
    expect(selectedPlace(IT, 'stay')).toBe(9)
    expect(selectedPlace(IT, null)).toBeNull()
    expect(selectedPlace(IT, { day: 5, stop: 0 })).toBeNull()
    expect(selectedPlace(null, { day: 0, stop: 0 })).toBeNull()
  })
})

describe('tourStops', () => {
  it('theo ngày rồi theo thứ tự Stop', () => {
    expect(tourStops(IT)).toEqual([{ day: 0, stop: 0 }, { day: 0, stop: 1 }, { day: 1, stop: 0 }])
  })
})
