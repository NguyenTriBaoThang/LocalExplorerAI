from app.core.config import settings
from app.services import open_meteo_service


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_current_conditions_returns_weather_aqi_and_uses_distinct_coordinates(monkeypatch):
    calls = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, url, params):
            calls.append((url, params.copy()))
            lat = float(params["latitude"])
            if url == settings.open_meteo_forecast_url:
                return FakeResponse({"current": {
                    "time": "2026-10-20T10:00", "temperature_2m": 30 + lat,
                    "apparent_temperature": 34 + lat, "relative_humidity_2m": 75,
                    "precipitation": 1.2, "rain": 1.0, "weather_code": 61,
                    "cloud_cover": 80, "wind_speed_10m": 12,
                }})
            return FakeResponse({"current": {
                "time": "2026-10-20T10:00", "european_aqi": lat,
                "us_aqi": 35, "us_aqi_pm2_5": 40, "pm2_5": 12,
                "pm10": 20, "nitrogen_dioxide": 3, "ozone": 4, "sulphur_dioxide": 5,
            }})

    monkeypatch.setattr(open_meteo_service.httpx, "Client", lambda **_kwargs: FakeClient())
    with open_meteo_service._CACHE_LOCK:
        open_meteo_service._CACHE.clear()

    first = open_meteo_service.current_conditions(10.7751, 106.7001)
    second = open_meteo_service.current_conditions(10.7851, 106.7001)

    assert first["temperature_c"] != second["temperature_c"]
    assert first["latitude"] == 10.7751 and second["latitude"] == 10.7851
    assert first["weather_code"] == 61 and first["rain_mm_per_hour"] == 1.0
    assert first["air_quality"]["european_aqi_label"] == "good"
    assert first["air_quality"]["pm10_ug_m3"] == 20
    assert first["air_quality"]["nitrogen_dioxide_ug_m3"] == 3
    assert len(calls) == 4


def test_current_conditions_rejects_invalid_coordinates():
    from app.services.open_meteo_service import OpenMeteoUnavailable

    try:
        open_meteo_service.current_conditions(91, 106.7)
    except OpenMeteoUnavailable as error:
        assert "coordinates" in str(error)
    else:
        raise AssertionError("invalid coordinates should be rejected")
