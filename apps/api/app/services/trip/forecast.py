import datetime as dt
from zoneinfo import ZoneInfo

from app.services import open_meteo_service
from app.services.open_meteo_service import OpenMeteoUnavailable

HORIZON_DAYS = 16


def get_daily_forecasts(lat: float, lon: float, start: dt.date | None, days: int,
                        today: dt.date | None = None, location_name: str = "") -> list[dict | None] | None:
    if start is None:
        return None
    today = today or dt.datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    horizon_end = today + dt.timedelta(days=HORIZON_DAYS - 1)
    if start < today or start > horizon_end:
        return None
    out: list[dict | None] = []
    for i in range(days):
        d = start + dt.timedelta(days=i)
        if d > horizon_end:
            out.append(None)
            continue
        try:
            daily = (open_meteo_service.daily_forecast(lat, lon, d, location_name)
                     if location_name else open_meteo_service.daily_forecast(lat, lon, d))
            out.append(daily)
        except OpenMeteoUnavailable:
            if i == 0:
                return None  # Forecast là phần phụ: lỗi thì lập lịch không có thời tiết
            out.append(None)
    return out


def get_rain_chance(lat: float, lon: float, start: dt.date | None, days: int,
                    today: dt.date | None = None) -> list[int | None] | None:
    """Compatibility wrapper for callers that only need precipitation probability."""
    forecasts = get_daily_forecasts(lat, lon, start, days, today)
    return [item["precipitation_probability_pct"] if item else None for item in forecasts] if forecasts else None
