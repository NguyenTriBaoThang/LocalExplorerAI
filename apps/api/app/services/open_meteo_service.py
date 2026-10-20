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
            result = dict(cached[1])
            if location_name:
                result["location"] = location_name
            return result

    params: dict[str, str | float | int] = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": _TIMEZONE,
        "timeformat": "iso8601",
        "forecast_days": 16,
        "daily": "precipitation_probability_max,precipitation_sum,temperature_2m_max,temperature_2m_min,weather_code",
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
    temperature_max_values = daily.get("temperature_2m_max") if isinstance(daily, dict) else None
    temperature_min_values = daily.get("temperature_2m_min") if isinstance(daily, dict) else None
    weather_codes = daily.get("weather_code") if isinstance(daily, dict) else None
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
    for key, values in (("temperature_2m_max_c", temperature_max_values),
                        ("temperature_2m_min_c", temperature_min_values)):
        if isinstance(values, list) and index < len(values) and values[index] is not None:
            try:
                temperature = float(values[index])
            except (TypeError, ValueError):
                continue
            if math.isfinite(temperature):
                result[key] = temperature
    if isinstance(weather_codes, list) and index < len(weather_codes) and weather_codes[index] is not None:
        try:
            code = int(weather_codes[index])
        except (TypeError, ValueError):
            code = -1
        if 0 <= code <= 99:
            result["weather_code"] = code
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
    if (not math.isfinite(latitude) or not math.isfinite(longitude)
            or not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
        raise OpenMeteoUnavailable("The requested coordinates are invalid.")

    # Keep nearby places distinct while still coalescing repeat map requests.
    key = (round(latitude, 3), round(longitude, 3))
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] > now:
            result = dict(cached[1])
            result["latitude"] = latitude
            result["longitude"] = longitude
            return result

    params: dict[str, str | float] = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": _TIMEZONE,
        "timeformat": "iso8601",
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,rain,weather_code,cloud_cover,wind_speed_10m",
    }
    air_params: dict[str, str | float] = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": _TIMEZONE,
        "timeformat": "iso8601",
        "current": "european_aqi,us_aqi,pm2_5,pm10,nitrogen_dioxide,ozone,sulphur_dioxide,us_aqi_pm2_5",
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

    observed_at = current_weather.get("time")
    if not isinstance(observed_at, str) or not observed_at.strip():
        raise OpenMeteoUnavailable("Open-Meteo omitted the observation timestamp.")

    def optional_number(payload: dict[str, Any], field: str, *, nonnegative: bool = False):
        value = payload.get(field)
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number) or (nonnegative and number < 0):
            return None
        return number

    precipitation = optional_number(current_weather, "precipitation", nonnegative=True)
    rain = optional_number(current_weather, "rain", nonnegative=True)
    if rain is None:
        rain = precipitation
    temperature = optional_number(current_weather, "temperature_2m")
    if temperature is None:
        raise OpenMeteoUnavailable("Open-Meteo omitted the current temperature.")

    european_aqi = optional_number(current_air, "european_aqi", nonnegative=True)
    us_aqi_pm25 = optional_number(current_air, "us_aqi_pm2_5", nonnegative=True)

    def european_aqi_label(value: float | None) -> str | None:
        if value is None:
            return None
        if value <= 20:
            return "good"
        if value <= 40:
            return "fair"
        if value <= 60:
            return "moderate"
        if value <= 80:
            return "poor"
        if value <= 100:
            return "very_poor"
        return "extremely_poor"

    air_fields = {
        "pm25_ug_m3": "pm2_5",
        "pm10_ug_m3": "pm10",
        "nitrogen_dioxide_ug_m3": "nitrogen_dioxide",
        "ozone_ug_m3": "ozone",
        "sulphur_dioxide_ug_m3": "sulphur_dioxide",
    }
    air_quality = {name: optional_number(current_air, field, nonnegative=True)
                   for name, field in air_fields.items()}
    air_quality.update({
        "european_aqi": european_aqi,
        "european_aqi_label": european_aqi_label(european_aqi),
        "us_aqi": optional_number(current_air, "us_aqi", nonnegative=True),
        "us_aqi_pm25": us_aqi_pm25,
    })

    data = {
        "latitude": latitude,
        "longitude": longitude,
        "rain_mm_per_hour": rain,
        "precipitation_mm": precipitation,
        "aqi_pm25": round(us_aqi_pm25) if us_aqi_pm25 is not None else None,
        "pm25_ug_m3": air_quality["pm25_ug_m3"],
        "temperature_c": temperature,
        "apparent_temperature_c": optional_number(current_weather, "apparent_temperature"),
        "relative_humidity_pct": optional_number(current_weather, "relative_humidity_2m", nonnegative=True),
        "weather_code": (
            int(current_weather["weather_code"])
            if str(current_weather.get("weather_code", "")).isdigit()
            and 0 <= int(current_weather["weather_code"]) <= 99 else None
        ),
        "cloud_cover_pct": optional_number(current_weather, "cloud_cover", nonnegative=True),
        "wind_speed_kmh": optional_number(current_weather, "wind_speed_10m", nonnegative=True),
        "air_quality": air_quality,
        "observed_at": observed_at,
        "air_quality_observed_at": current_air.get("time"),
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
