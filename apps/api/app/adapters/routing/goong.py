from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil, isfinite
from typing import Any

import httpx

from app.adapters.routing.provider import (
    NoRouteFound,
    RouteEstimate,
    RoutingConfigurationError,
    RoutingProviderError,
    UnsupportedTravelMode,
)

GOONG_DIRECTIONS_DOCS = "https://help.goong.io/kb/rest-api-v2/directions-rest-api-v2/directions-v2/"
GOONG_GEOCODE_DOCS = "https://help.goong.io/kb/rest-api-v2/geocode-rest-api-v2/geocode-v2/"


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode a Google-compatible encoded polyline into (latitude, longitude) pairs."""
    coordinates: list[tuple[float, float]] = []
    index = lat = lon = 0
    while index < len(encoded):
        deltas = []
        for _ in range(2):
            result = shift = 0
            while True:
                if index >= len(encoded):
                    raise ValueError("Truncated encoded polyline")
                value = ord(encoded[index]) - 63
                index += 1
                if value < 0:
                    raise ValueError("Invalid encoded polyline character")
                result |= (value & 0x1F) << shift
                shift += 5
                if value < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        coordinates.append((lat / 100_000.0, lon / 100_000.0))
    return coordinates


@dataclass(frozen=True)
class AddressCandidate:
    formatted_address: str
    latitude: float
    longitude: float
    place_id: str | None


@dataclass(frozen=True)
class AddressResolution:
    results: list[AddressCandidate]
    resolved_at: datetime
    valid_until: datetime
    provider: str = "goong_geocode_v2"
    source_uri: str = GOONG_GEOCODE_DOCS


class GoongDirectionsProvider:
    """Goong Directions v2, with a short TTL cache for repeated planner candidates."""

    _vehicles = {
        "car": "car",
        "driving": "car",
        "motorcycle": "bike",
        "walking": "foot",
    }

    def __init__(self, api_key: str | None, base_url: str = "https://rsapi.goong.io",
                 eta_ttl_seconds: int = 300, timeout_seconds: float = 8.0):
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self.eta_ttl_seconds = max(30, eta_ttl_seconds)
        self.timeout_seconds = timeout_seconds
        self._route_cache: dict[tuple, RouteEstimate] = {}

    def _request_json(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        if not self.api_key:
            raise RoutingConfigurationError("Goong is selected but GOONG_API_KEY is not configured.")
        try:
            response = httpx.get(
                f"{self.base_url}{path}", params={**params, "api_key": self.api_key},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException as error:
            raise RoutingProviderError("Goong request timed out; no estimated route was substituted.") from error
        except httpx.HTTPStatusError as error:
            try:
                err_body = error.response.json()
                err_code = (err_body.get("error") or {}).get("code") or ""
                err_msg = (err_body.get("error") or {}).get("message") or error.response.text
                detail = f"{error.response.status_code} [{err_code}]: {err_msg}" if err_code else f"{error.response.status_code}: {err_msg}"
            except Exception:
                detail = f"{error.response.status_code}"
            raise RoutingProviderError(f"Goong returned HTTP {detail}.") from error
        except (httpx.HTTPError, ValueError) as error:
            raise RoutingProviderError("Goong returned an invalid response; no estimated route was substituted.") from error
        if not isinstance(body, dict):
            raise RoutingProviderError("Goong returned an invalid response shape.")
        return body

    def get_route(self, origin: tuple[float, float], destination: tuple[float, float], mode: str) -> RouteEstimate:
        vehicle = self._vehicles.get(mode)
        if vehicle is None:
            raise UnsupportedTravelMode(
                f"Goong routing does not support '{mode}'. Choose motorcycle, walking, or car; public transit and bicycle routing are not configured."
            )
        origin = (float(origin[0]), float(origin[1]))
        destination = (float(destination[0]), float(destination[1]))
        key = (round(origin[0], 6), round(origin[1], 6), round(destination[0], 6), round(destination[1], 6), vehicle)
        now = datetime.now(timezone.utc)
        cached = self._route_cache.get(key)
        if cached and cached.valid_until and cached.valid_until > now:
            return cached

        body = self._request_json("/v2/direction", {
            "origin": f"{origin[0]},{origin[1]}",
            "destination": f"{destination[0]},{destination[1]}",
            "vehicle": vehicle,
            "alternatives": "false",
        })
        status = str(body.get("status", "OK")).upper()
        if status == "ZERO_RESULTS":
            raise NoRouteFound("Goong could not find a route for this leg.")
        if status != "OK":
            raise RoutingProviderError(f"Goong Directions returned status '{status}'.")
        routes = body.get("routes")
        if not isinstance(routes, list) or not routes:
            raise NoRouteFound("Goong could not find a route for this leg.")
        legs = routes[0].get("legs") if isinstance(routes[0], dict) else None
        if not isinstance(legs, list) or not legs:
            raise RoutingProviderError("Goong route response did not include a route leg.")
        try:
            distance = float(legs[0]["distance"]["value"])
            duration = float(legs[0]["duration"]["value"])
        except (KeyError, TypeError, ValueError) as error:
            raise RoutingProviderError("Goong route response omitted distance or duration.") from error
        if not isfinite(distance) or not isfinite(duration) or distance < 0 or duration <= 0:
            raise RoutingProviderError("Goong returned invalid distance or duration values.")

        encoded_geometry = (routes[0].get("overview_polyline") or {}).get("points")
        try:
            geometry = decode_polyline(encoded_geometry) if isinstance(encoded_geometry, str) and encoded_geometry else None
        except ValueError:
            geometry = None

        estimate = RouteEstimate(
            distance_m=round(distance),
            # Round up: hard return-deadline checks must not underestimate seconds.
            duration_min=max(1, ceil(duration / 60)),
            provider="goong_directions_v2",
            is_realtime=False,
            eta_source="Goong Directions API v2 (provider ETA; not live traffic)",
            calculated_at=now,
            valid_until=now + timedelta(seconds=self.eta_ttl_seconds),
            source_uri=GOONG_DIRECTIONS_DOCS,
            geometry=geometry,
        )
        self._route_cache[key] = estimate
        return estimate


class GoongGeocodingProvider(GoongDirectionsProvider):
    """Forward geocoding for a traveler-entered address; no key is sent to the browser."""

    def __init__(self, api_key: str | None, base_url: str = "https://rsapi.goong.io",
                 cache_ttl_seconds: int = 86400, timeout_seconds: float = 8.0):
        super().__init__(api_key, base_url, timeout_seconds=timeout_seconds)
        self.cache_ttl_seconds = max(60, cache_ttl_seconds)
        self._geocode_cache: dict[str, AddressResolution] = {}

    def forward(self, address: str, limit: int = 5) -> AddressResolution:
        query = " ".join(address.split())
        cache_key = query.casefold()
        now = datetime.now(timezone.utc)
        cached = self._geocode_cache.get(cache_key)
        if cached and cached.valid_until > now:
            return cached

        body = self._request_json("/v2/geocode", {"address": query, "limit": limit})
        status = str(body.get("status", "OK")).upper()
        if status not in {"OK", "ZERO_RESULTS"}:
            raise RoutingProviderError(f"Goong Geocoding returned status '{status}'.")
        raw_results = body.get("results", [])
        if not isinstance(raw_results, list):
            raise RoutingProviderError("Goong geocoding response did not include a result list.")
        results: list[AddressCandidate] = []
        for item in raw_results[:limit]:
            if not isinstance(item, dict):
                continue
            location = (item.get("geometry") or {}).get("location") or {}
            try:
                latitude, longitude = float(location["lat"]), float(location["lng"])
                label = str(item.get("formatted_address") or item.get("name") or "").strip()
            except (KeyError, TypeError, ValueError):
                continue
            if not label or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                continue
            results.append(AddressCandidate(label, latitude, longitude, item.get("place_id")))

        resolution = AddressResolution(
            results=results, resolved_at=now,
            valid_until=now + timedelta(seconds=self.cache_ttl_seconds),
        )
        self._geocode_cache[cache_key] = resolution
        return resolution
