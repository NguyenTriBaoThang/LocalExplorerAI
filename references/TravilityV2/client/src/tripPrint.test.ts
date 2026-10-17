// @vitest-environment jsdom
import { createElement, type ReactNode } from 'react'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TripPrintView from './components/TripPrintView'
import Timeline from './components/Timeline'
import * as api from './api'
import type { Itinerary, Place, TripSummary, TripView } from './api'
import { buildTripPrintModel } from './tripPrint'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
})

const trip: TripSummary = {
  id: 12,
  spec: { destination: 'Đà Lạt', days: 1 },
  created_at: '2026-10-01T10:00:00+07:00',
  destination_name: 'Đà Lạt',
}

const itinerary: Itinerary = {
  stay_place_id: 2,
  days: [{
    date: '2026-10-20',
    stops: [{ place_id: 1, start_time: '09:00', duration_min: 90, reason: 'Thưởng thức cà phê', pinned: false, est_cost: 45_000 }],
    legs: [{ from_place_id: null, to_place_id: 1, distance_km: 5.2, duration_min: 15, mode: 'car', cost: 25_000 }],
    rain_chance: null,
  }],
  total_cost: 345_000,
  conflicts: [{ kind: 'budget', message: 'Vượt ngân sách', day_index: null, place_id: null }],
  summary: 'Một ngày ở Đà Lạt',
}

const places: Record<string, Place> = {
  '1': { id: 1, name: 'Cà phê Tùng', kind: 'cafe', lat: 11.94, lon: 108.45, photo_url: null, outdoor: false, price: 45_000 },
  '2': { id: 2, name: 'Khách sạn trung tâm', kind: 'hotel', lat: 11.95, lon: 108.44, photo_url: null, outdoor: false, price: 300_000 },
}

describe('buildTripPrintModel', () => {
  it('copies the viewed itinerary version and already computed display data', () => {
    const model = buildTripPrintModel(
      trip, 3, itinerary, places, '2026-10-14T10:00:00+07:00',
    )

    expect(model.destination).toBe('Đà Lạt')
    expect(model.version).toBe(3)
    expect(model.days[0].date).toBe('2026-10-20')
    expect(model.days[0].stops[0]).toMatchObject({
      startTime: '09:00', placeName: 'Cà phê Tùng', reason: 'Thưởng thức cà phê', cost: 45_000,
    })
    expect(model.days[0].legs[0]).toMatchObject({
      fromLabel: 'Bến/sân bay', toLabel: 'Cà phê Tùng', mode: 'car',
      distanceKm: 5.2, durationMin: 15, cost: 25_000,
    })
    expect(model).toMatchObject({
      stayName: 'Khách sạn trung tâm', totalCost: 345_000,
      conflicts: ['Vượt ngân sách'], exportedAt: '2026-10-14T10:00:00+07:00',
    })
    expect(model).not.toHaveProperty('budget')
  })

  it('labels missing places neutrally and does not invent a name', () => {
    const model = buildTripPrintModel(
      trip, 1, itinerary, {}, '2026-10-14T10:00:00+07:00',
    )

    expect(model.stayName).toBeNull()
    expect(model.days[0].stops[0].placeName).toBe('Địa điểm không xác định')
    expect(model.days[0].legs[0]).toMatchObject({
      fromLabel: 'Bến/sân bay', toLabel: 'Địa điểm không xác định',
    })
  })
})

describe('TripPrintView', () => {
  it('renders the snapshot details needed for a printable trip copy', () => {
    const model = buildTripPrintModel(
      trip, 3, itinerary, places, '2026-10-14T10:00:00+07:00',
    )
    const { container } = render(createElement(TripPrintView, { model }))
    const printable = container.querySelector('.trip-print')

    expect(printable?.textContent).toContain('Đà Lạt')
    expect(printable?.textContent).toContain('v3')
    expect(printable?.textContent).toContain('Khách sạn trung tâm')
    expect(printable?.textContent).toContain('Cà phê Tùng')
    expect(printable?.textContent).toContain('Thưởng thức cà phê')
    expect(printable?.textContent).toContain('Bến/sân bay')
    expect(printable?.textContent).toContain('car')
    expect(printable?.textContent).toContain('5.2 km')
    expect(printable?.textContent).toContain('15 phút')
    expect(printable?.textContent).toContain('345.000đ')
    expect(printable?.textContent).not.toContain('Ngân sách')
    expect(printable?.textContent).not.toContain('2.000.000đ')
    expect(printable?.textContent).toContain('Xung đột')
    expect(printable?.textContent).toContain('Vượt ngân sách')
    expect(printable?.textContent).toContain('2026-10-20')
    expect(printable?.textContent).toContain(new Date(model.exportedAt).toLocaleString('vi-VN'))
  })
})

describe('Timeline PDF export action', () => {
  it('shows export only for a viewed itinerary version and calls its handler', () => {
    const onExportPdf = vi.fn()
    const { getByRole, rerender, queryByRole } = render(createElement(Timeline, {
      itinerary, places, budget: 2_000_000, version: 3, latest: 3, onExportPdf,
    }))

    fireEvent.click(getByRole('button', { name: 'Xuất PDF' }))
    expect(onExportPdf).toHaveBeenCalledOnce()

    rerender(createElement(Timeline, {
      itinerary, places, budget: 2_000_000, version: null, latest: 3, onExportPdf,
    }))
    expect(queryByRole('button', { name: 'Xuất PDF' })).toBeNull()
  })
})

describe('App PDF snapshot', () => {
  it('prints the viewed version from loaded state and clears it after the dialog closes', async () => {
    const olderPlaces = { '11': { ...places['1'], id: 11, name: 'Quán ở bản một' } }
    const olderItinerary: Itinerary = {
      ...itinerary,
      days: [{ ...itinerary.days[0], stops: [{ ...itinerary.days[0].stops[0], place_id: 11 }] }],
      total_cost: 111_000,
    }
    const olderView: TripView = {
      trip_id: trip.id, trip: { budget: 2_000_000 }, center: [108.45, 11.94], version: 1,
      itinerary: olderItinerary, places: olderPlaces, versions: [1, 3], pinned_place_ids: [],
    }
    const latestView: TripView = {
      trip_id: trip.id, trip: { budget: 2_000_000 }, center: [108.45, 11.94], version: 3,
      itinerary, places, versions: [1, 3], pinned_place_ids: [],
    }
    vi.spyOn(api, 'listTrips').mockResolvedValue([trip])
    const getTrip = vi.spyOn(api, 'getTrip').mockImplementation(async (_token, _tripId, requestedVersion) =>
      requestedVersion === 1 ? olderView : latestView)
    vi.spyOn(api, 'getMessages').mockResolvedValue([])

    vi.doMock('./components/MapView', () => ({ default: () => null }))
    vi.doMock('./components/Rail', () => ({ default: () => null }))
    vi.doMock('./components/ChatPanel', () => ({ default: ({ children }: { children: ReactNode }) =>
      createElement('section', null, children) }))
    vi.doMock('./components/GroupReviewPanel', () => ({ default: () => null }))
    vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
    const print = vi.fn()
    vi.stubGlobal('print', print)
    localStorage.setItem('token', 'test-token')

    const { default: App } = await import('./App')
    const { getByRole } = render(createElement(App))
    await waitFor(() => expect(getByRole('button', { name: 'Xuất PDF' })).toBeTruthy())

    fireEvent.click(getByRole('button', { name: 'v1' }))
    await waitFor(() => expect(getByRole('button', { name: 'v1' }).getAttribute('aria-current')).toBe('true'))
    const callsBeforeExport = getTrip.mock.calls.length

    fireEvent.click(getByRole('button', { name: 'Xuất PDF' }))
    await waitFor(() => expect(print).toHaveBeenCalledOnce())

    const printable = document.querySelector('.trip-print')
    expect(printable?.textContent).toContain('Phiên bản v1')
    expect(printable?.textContent).toContain('Quán ở bản một')
    expect(printable?.textContent).not.toContain('Phiên bản v3')
    expect(getTrip).toHaveBeenCalledTimes(callsBeforeExport)

    window.dispatchEvent(new Event('afterprint'))
    await waitFor(() => expect(document.querySelector('.trip-print')).toBeNull())
  })
})
