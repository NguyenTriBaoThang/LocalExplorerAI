import type { Itinerary, Place } from '../../api/trips'

export function roadSegments(itinerary: Itinerary | null, places: Record<string, Place>) {
  const segments: { day: number; origin: Place; destination: Place }[] = []
  itinerary?.days.forEach((day, index) => {
    const stops = day.stops.map(stop => places[stop.place_id])
    const stay = itinerary.stay_place_id == null ? undefined : places[itinerary.stay_place_id]
    const points = stay ? [stay, ...stops, stay] : stops
    for (let i = 1; i < points.length; i++) {
      const origin = points[i - 1], destination = points[i]
      // Missing coordinates must not silently bridge over a stop.
      if (origin && destination && (origin.lat !== destination.lat || origin.lon !== destination.lon)) {
        segments.push({ day: index, origin, destination })
      }
    }
  })
  return segments
}
