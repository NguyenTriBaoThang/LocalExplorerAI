"""Small cached Open-Meteo adapter for current weather and PM2.5 AQI."""

from __future__ import annotations

import time
import math
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.core.config import settings

_TIMEZONE = "Asia/Ho_Chi_Minh"
_CACHE: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}
_FORECAST_CACHE: dict[tuple[float, float, date], tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = Lock()


class OpenMeteoUnavailable(RuntimeError):
    pass


def daily_forecast(
    latitude: float,
    longitude: float,
    forecast_date: date,
    location_name: str = "",
) -> dict[str, Any]:
    """Return date-aligned daily precipitation data from Open-Meteo."""
    if (not math.isfinite(latitude) or not math.isfinite(longitude)
            or not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
        raise OpenMeteoUnavailable("The requested forecast coordinates are invalid.")

    local_today = datetime.now(ZoneInfo(_TIMEZONE)).date()
    if forecast_date < local_today or forecast_date > local_today + timedelta(days=15):
        raise OpenMeteoUnavailable("Open-Meteo's supported forecast window does not include the requested date.")

    key = (round(latitude, 2), round(longitude, 2), forecast_date)
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _FORECAST_CACHE.get(key)
        if cached and cached[0] > now:
            return dict(cached[1])

    params: dict[str, str | float | int] = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": _TIMEZONE,
        "timeformat": "iso8601",
        "forecast_days": 16,
        "daily": "precipitation_probability_max,precipitation_sum",
    }
    if settings.open_meteo_api_key:
        params["apikey"] = settings.open_meteo_api_key.strip()

    try:
        with httpx.Client(timeout=8.0, follow_redirects=False) as client:
            response = client.get(settings.open_meteo_forecast_url, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise OpenMeteoUnavailable("Open-Meteo did not return a daily forecast.") from error

    daily = payload.get("daily") if isinstance(payload, dict) else None
    dates = daily.get("time") if isinstance(daily, dict) else None
    probabilities = daily.get("precipitation_probability_max") if isinstance(daily, dict) else None
    amounts = daily.get("precipitation_sum") if isinstance(daily, dict) else None
    if not all(isinstance(values, list) for values in (dates, probabilities, amounts)):
        raise OpenMeteoUnavailable("Open-Meteo returned an incomplete daily forecast.")
    try:
        index = dates.index(forecast_date.isoformat())
        probability = float(probabilities[index])
        amount = float(amounts[index])
    except (ValueError, IndexError, TypeError) as error:
        raise OpenMeteoUnavailable("Open-Meteo did not return data for the requested date.") from error
    if (not math.isfinite(probability) or not math.isfinite(amount)
            or not 0 <= probability <= 100 or amount < 0):
        raise OpenMeteoUnavailable("Open-Meteo returned invalid precipitation values.")

    result = {
        "location": location_name,
        "forecast_date": forecast_date.isoformat(),
        "precipitation_probability_pct": round(probability),
        "precipitation_sum_mm": amount,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source": "Open-Meteo",
        "source_url": "https://open-meteo.com/en/docs",
        "attribution": "Weather forecast data: Open-Meteo (CC BY 4.0).",
    }
    with _CACHE_LOCK:
        for cache_key, (expires_at, _) in list(_FORECAST_CACHE.items()):
            if expires_at <= now:
                _FORECAST_CACHE.pop(cache_key, None)
        if len(_FORECAST_CACHE) >= 2048:
            _FORECAST_CACHE.pop(next(iter(_FORECAST_CACHE)))
        _FORECAST_CACHE[key] = (now + settings.open_meteo_cache_ttl_seconds, result)
    return dict(result)


def current_conditions(latitude: float, longitude: float) -> dict[str, Any]:
    """Return current model data, cached briefly to limit requests to the provider."""
    key = (round(latitude, 2), round(longitude, 2))
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] > now:
            return dict(cached[1])

    params: dict[str, str | float] = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": _TIMEZONE,
        "timeformat": "iso8601",
        "current": "temperature_2m,precipitation,rain",
    }
    air_params: dict[str, str | float] = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": _TIMEZONE,
        "timeformat": "iso8601",
        "current": "us_aqi_pm2_5,pm2_5",
    }
    if settings.open_meteo_api_key:
        params["apikey"] = settings.open_meteo_api_key.strip()
        air_params["apikey"] = settings.open_meteo_api_key.strip()

    try:
        with httpx.Client(timeout=8.0, follow_redirects=False) as client:
            weather_response = client.get(settings.open_meteo_forecast_url, params=params)
            air_response = client.get(settings.open_meteo_air_quality_url, params=air_params)
        weather_response.raise_for_status()
        air_response.raise_for_status()
        weather = weather_response.json()
        air = air_response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise OpenMeteoUnavailable("Open-Meteo did not return current weather and air-quality data.") from error

    current_weather = weather.get("current") if isinstance(weather, dict) else None
    current_air = air.get("current") if isinstance(air, dict) else None
    if not isinstance(current_weather, dict) or not isinstance(current_air, dict):
        raise OpenMeteoUnavailable("Open-Meteo returned an incomplete current-conditions response.")

    rain = current_weather.get("precipitation")
    if rain is None:
        rain = current_weather.get("rain")
    values = (rain, current_weather.get("temperature_2m"), current_air.get("us_aqi_pm2_5"))
    try:
        rain_value, temperature, aqi = (float(value) for value in values)
    except (TypeError, ValueError) as error:
        raise OpenMeteoUnavailable("Open-Meteo omitted a required rain, temperature, or PM2.5 AQI value.") from error
    if not all(math.isfinite(value) for value in (rain_value, temperature, aqi)):
        raise OpenMeteoUnavailable("Open-Meteo returned a non-finite current-conditions value.")
    observed_at = current_weather.get("time")
    if not isinstance(observed_at, str) or not observed_at.strip():
        raise OpenMeteoUnavailable("Open-Meteo omitted the observation timestamp.")

    data = {
        "rain_mm_per_hour": max(0.0, rain_value),
        "aqi_pm25": max(0, min(1000, round(aqi))),
        "pm25_ug_m3": current_air.get("pm2_5"),
        "temperature_c": temperature,
        "observed_at": observed_at,
        "timezone": _TIMEZONE,
        "source": "Open-Meteo",
        "weather_source_url": "https://open-meteo.com/en/docs",
        "air_quality_source_url": "https://open-meteo.com/en/docs/air-quality-api",
        "attribution": "Weather forecast: Open-Meteo. Air-quality data: CAMS via Open-Meteo (CC BY 4.0).",
    }
    with _CACHE_LOCK:
        for cache_key, (expires_at, _) in list(_CACHE.items()):
            if expires_at <= now:
                _CACHE.pop(cache_key, None)
        if len(_CACHE) >= 2048:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = (now + settings.open_meteo_cache_ttl_seconds, data)
    return dict(data)
