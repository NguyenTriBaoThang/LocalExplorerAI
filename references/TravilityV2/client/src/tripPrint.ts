import type { Itinerary, Place, TripSummary } from './api'

export type TripPrintModel = {
  destination: string; version: number; exportedAt: string; stayName: string | null
  totalCost: number; conflicts: string[]
  days: Array<{
    date: string | null
    stops: Array<{ startTime: string; placeName: string; reason: string; cost: number }>
    legs: Array<{ fromLabel: string; toLabel: string; mode: string; distanceKm: number; durationMin: number; cost: number }>
  }>
}

const UNKNOWN_PLACE = 'Địa điểm không xác định'
const HUB_LABEL = 'Bến/sân bay'

function placeLabel(placeId: number | null, places: Record<string, Place>): string {
  if (placeId == null) return HUB_LABEL
  return places[placeId]?.name ?? UNKNOWN_PLACE
}

export function buildTripPrintModel(
  trip: TripSummary, version: number, itinerary: Itinerary, places: Record<string, Place>,
  exportedAt: string,
): TripPrintModel {
  return {
    destination: trip.destination_name ?? trip.spec.destination,
    version,
    exportedAt,
    stayName: itinerary.stay_place_id == null ? null : places[itinerary.stay_place_id]?.name ?? null,
    totalCost: itinerary.total_cost,
    conflicts: itinerary.conflicts.map((conflict) => conflict.message),
    days: itinerary.days.map((day) => ({
      date: day.date,
      stops: day.stops.map((stop) => ({
        startTime: stop.start_time,
        placeName: placeLabel(stop.place_id, places),
        reason: stop.reason,
        cost: stop.est_cost,
      })),
      legs: day.legs.map((leg) => ({
        fromLabel: placeLabel(leg.from_place_id, places),
        toLabel: placeLabel(leg.to_place_id, places),
        mode: leg.mode,
        distanceKm: leg.distance_km,
        durationMin: leg.duration_min,
        cost: leg.cost,
      })),
    })),
  }
}
