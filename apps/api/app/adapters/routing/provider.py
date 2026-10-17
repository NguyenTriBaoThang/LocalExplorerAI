from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Protocol


@dataclass(frozen=True)
class RouteEstimate:
    distance_m: int
    duration_min: int
    provider: str = "mock"
    is_realtime: bool = False
    eta_source: str = "mock straight-line estimate"
    calculated_at: datetime | None = None
    valid_until: datetime | None = None
    source_uri: str | None = None
    geometry: list[tuple[float, float]] | None = None


class RoutingProvider(Protocol):
    def get_route(self, origin: tuple[float, float], destination: tuple[float, float], mode: str) -> RouteEstimate: ...


class RoutingProviderError(RuntimeError):
    """A routing/geocoding service is unconfigured or returned unusable data."""


class RoutingConfigurationError(RoutingProviderError):
    pass


class UnsupportedTravelMode(RoutingProviderError):
    pass


class NoRouteFound(RoutingProviderError):
    pass


class MockRoutingProvider:
    """Straight-line distance with an assumed speed; this is not a real route or traffic feed."""

    speeds_kmh = {"walking": 4.5, "bicycling": 14.0, "driving": 20.0, "motorcycle": 25.0, "car": 20.0, "transit": 16.0}

    def get_route(self, origin: tuple[float, float], destination: tuple[float, float], mode: str) -> RouteEstimate:
        if mode not in self.speeds_kmh:
            raise UnsupportedTravelMode(f"Mock routing does not support travel mode '{mode}'.")
        lat1, lon1 = map(radians, origin)
        lat2, lon2 = map(radians, destination)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        hav = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        distance_m = int(6_371_000 * 2 * asin(sqrt(hav)) * 1.3)  # road factor is illustrative
        speed = self.speeds_kmh.get(mode, self.speeds_kmh["driving"])
        duration_min = max(5, round(distance_m / 1000 / speed * 60))
        now = datetime.now(timezone.utc)
        return RouteEstimate(
            distance_m, duration_min, provider="mock", is_realtime=False,
            eta_source="Mock straight-line estimate", calculated_at=now,
            valid_until=now + timedelta(minutes=5),
            # The demo is explicitly a straight segment, not a road route.
            # Supplying its endpoints lets the itinerary map render the route.
            geometry=[origin, destination],
        )
