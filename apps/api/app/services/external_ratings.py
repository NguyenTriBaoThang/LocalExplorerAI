"""The public Google Maps rating of a place, read lazily, cached briefly and capped per month.

Only the rating, the number of ratings and the Maps link are read. Calls are counted in ``external_api_usage`` and stop at
``GOOGLE_PLACES_MONTHLY_CALL_CAP`` (default 900, inside the free allowance), after which the last cached value, if any, is
shown. Nothing here raises: a place without Google data simply shows no Google block.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.places.google_places import GooglePlaceNotFound, GooglePlacesClient, GooglePlacesError
from app.core.config import settings
from app.models.entities import ExternalApiUsage, PlaceExternalRating, POI
from app.services.integration_config import IntegrationSecretConfigurationError, resolve_integration_value

log = logging.getLogger(__name__)
SERVICE = "google_places"
SOURCE = "google"
NOT_FOUND_RETRY = timedelta(days=7)
ERROR_RETRY = timedelta(hours=1)
MAX_MATCH_DISTANCE_M = 400.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a = sin(radians(lat2 - lat1) / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    return 6371000.0 * 2 * asin(sqrt(min(1.0, a)))


def api_key(db: Session) -> str | None:
    try:
        value = resolve_integration_value(db, "google_places", "api_key")
    except IntegrationSecretConfigurationError:
        return None
    return value.strip() if value and value.strip() else None


def make_client(key: str) -> GooglePlacesClient:
    return GooglePlacesClient(key)


def calls_this_month(db: Session, now: datetime | None = None) -> int:
    period = (now or _now()).strftime("%Y-%m")
    row = db.scalar(select(ExternalApiUsage).where(ExternalApiUsage.service == SERVICE, ExternalApiUsage.period == period))
    return row.calls if row else 0


def _take_call(db: Session, now: datetime) -> bool:
    """Reserve one billable call; False when this month's cap is used up."""
    period = now.strftime("%Y-%m")
    row = db.scalar(select(ExternalApiUsage).where(ExternalApiUsage.service == SERVICE, ExternalApiUsage.period == period))
    if row is None:
        row = ExternalApiUsage(service=SERVICE, period=period, calls=0)
        db.add(row)
    if row.calls >= settings.google_places_monthly_call_cap:
        return False
    row.calls += 1
    db.flush()
    return True


def _view(row: PlaceExternalRating) -> dict | None:
    if row.status != "ok" or row.rating is None:
        return None
    return {"source": "google", "rating": round(float(row.rating), 1), "rating_count": row.rating_count or 0, "maps_uri": row.maps_uri,
            "matched_name": row.matched_name, "fetched_at": _aware(row.fetched_at)}


def eligible(poi: POI) -> bool:
    """Google is queried only for landmarks and for places an administrator linked, so public traffic cannot spend the quota."""
    return bool(poi.is_landmark or poi.google_place_id)


def google_rating(db: Session, poi: POI, *, now: datetime | None = None, client: GooglePlacesClient | None = None) -> dict | None:
    now = now or _now()
    key = api_key(db)
    if not key or not eligible(poi):
        return None
    row = db.scalar(select(PlaceExternalRating).where(PlaceExternalRating.poi_id == poi.id, PlaceExternalRating.source == SOURCE))
    if row is not None:
        age = now - _aware(row.fetched_at)
        if row.status == "ok" and age < timedelta(hours=settings.google_places_cache_hours):
            return _view(row)
        if row.status == "not_found" and age < NOT_FOUND_RETRY:
            return None
        if row.status == "error" and age < ERROR_RETRY:
            return _view(row)   # the previous good value, if there was one
    stale = _view(row) if row is not None and row.status == "ok" else None
    client = client or make_client(key)
    if row is None:
        row = PlaceExternalRating(poi_id=poi.id, source=SOURCE, status="error", fetched_at=now)
        db.add(row)
    try:
        place_id = poi.google_place_id or row.external_place_id
        if not place_id:
            if not _take_call(db, now):
                db.commit()
                return stale
            found = client.find_place(poi.name, poi.latitude, poi.longitude)
            if found is None or found.latitude is None or found.longitude is None or \
                    _distance_m(poi.latitude, poi.longitude, found.latitude, found.longitude) > MAX_MATCH_DISTANCE_M:
                row.status, row.fetched_at, row.rating = "not_found", now, None
                db.commit()
                return None
            place_id, row.external_place_id, row.matched_name = found.place_id, found.place_id, found.name
        if not _take_call(db, now):
            db.commit()
            return stale
        result = client.rating(place_id)
        row.external_place_id = row.external_place_id or place_id
        row.matched_name = result.name or row.matched_name
        row.rating, row.rating_count, row.maps_uri = result.rating, result.rating_count, result.maps_uri
        row.status, row.fetched_at = ("ok" if result.rating is not None else "not_found"), now
    except GooglePlaceNotFound:
        row.status, row.fetched_at = "not_found", now
    except GooglePlacesError as error:
        log.warning("Google Places lookup failed for %s: %s", poi.id, error)
        row.status, row.fetched_at = "error", now
        db.commit()
        return stale
    db.commit()
    return _view(row)


def test_connection(db: Session, client: GooglePlacesClient | None = None) -> tuple[str, str]:
    """(status, Vietnamese detail) for the admin 'test connection' button. Costs one counted call."""
    key = api_key(db)
    if not key:
        return "not_configured", "Chưa cấu hình khóa Google Places API."
    if not _take_call(db, _now()):
        db.commit()
        return "failed", "Đã dùng hết số lượt gọi Google trong tháng này (xem GOOGLE_PLACES_MONTHLY_CALL_CAP)."
    db.commit()
    try:
        (client or make_client(key)).find_place("Nhà thờ Đức Bà Sài Gòn", 10.7798, 106.6990)
    except GooglePlacesError as error:
        return "failed", f"Google từ chối hoặc không phản hồi: {error}. Kiểm tra khóa và việc bật Places API (New)."
    return "connected", "Đã kết nối thành công tới Google Places API."
