"""Google Places API (New): find a place and read its public rating. Server-side only; the key never reaches a browser."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

BASE_URL = "https://places.googleapis.com/v1"


class GooglePlacesError(RuntimeError):
    """The request failed (network, quota, key or API error)."""


class GooglePlaceNotFound(GooglePlacesError):
    """Google does not know this place id."""


@dataclass(frozen=True)
class FoundPlace:
    place_id: str
    name: str
    latitude: float | None
    longitude: float | None


@dataclass(frozen=True)
class PlaceRating:
    rating: float | None
    rating_count: int | None
    maps_uri: str | None
    name: str | None


class GooglePlacesClient:
    def __init__(self, api_key: str, *, timeout: float = 6.0, transport: httpx.BaseTransport | None = None) -> None:
        self._key = api_key
        self._http = httpx.Client(timeout=timeout, transport=transport)

    def _request(self, method: str, url: str, field_mask: str, **kwargs) -> dict:
        try:
            response = self._http.request(method, url, headers={"X-Goog-Api-Key": self._key, "X-Goog-FieldMask": field_mask}, **kwargs)
        except httpx.HTTPError as error:
            raise GooglePlacesError(f"Google Places request failed: {error.__class__.__name__}") from error
        if response.status_code == 404:
            raise GooglePlaceNotFound("Place not found.")
        if response.status_code != 200:
            raise GooglePlacesError(f"Google Places returned HTTP {response.status_code}.")
        try:
            return response.json()
        except ValueError as error:
            raise GooglePlacesError("Google Places returned an unreadable response.") from error

    def find_place(self, name: str, latitude: float, longitude: float, *, radius_m: float = 500.0) -> FoundPlace | None:
        """The best text match near the given point, or None."""
        body = {"textQuery": name, "languageCode": "vi", "maxResultCount": 1,
                "locationBias": {"circle": {"center": {"latitude": latitude, "longitude": longitude}, "radius": radius_m}}}
        data = self._request("POST", f"{BASE_URL}/places:searchText", "places.id,places.displayName,places.location", json=body)
        places = data.get("places") or []
        if not places:
            return None
        item = places[0]
        location = item.get("location") or {}
        return FoundPlace(place_id=item["id"], name=(item.get("displayName") or {}).get("text", ""),
                          latitude=location.get("latitude"), longitude=location.get("longitude"))

    def rating(self, place_id: str) -> PlaceRating:
        """Only the rating, the number of ratings and the Google Maps link are requested (the cheapest useful field set)."""
        data = self._request("GET", f"{BASE_URL}/places/{place_id}", "id,displayName,rating,userRatingCount,googleMapsUri", params={"languageCode": "vi"})
        return PlaceRating(rating=data.get("rating"), rating_count=data.get("userRatingCount"), maps_uri=data.get("googleMapsUri"),
                           name=(data.get("displayName") or {}).get("text"))
