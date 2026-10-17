import datetime as dt
import json

import httpx

from app import kv
from app.config import settings

URL = "https://api.open-meteo.com/v1/forecast"
HORIZON_DAYS = 16
CACHE_S = 6 * 3600


def get_rain_chance(lat: float, lon: float, start: dt.date | None, days: int,
                    client: httpx.Client | None = None, today: dt.date | None = None) -> list[int | None] | None:
    if start is None:
        return None
    today = today or dt.date.today()
    horizon_end = today + dt.timedelta(days=HORIZON_DAYS - 1)
    if start < today or start > horizon_end:
        return None
    end = min(start + dt.timedelta(days=days - 1), horizon_end)
    key = f"forecast:{lat}:{lon}:{start.isoformat()}:{days}"
    if (raw := kv.get(key)) is not None:
        return json.loads(raw)
    # DEMO_TODAY: brief phải giống hệt lúc ghi thì llm-gateway mới trúng cache → ghi cả kết quả lỗi, không hết hạn.
    frozen = settings.demo_today is not None

    def _fetch(c):
        r = c.get(URL, params={
            "latitude": lat, "longitude": lon, "daily": "precipitation_probability_max",
            "timezone": "Asia/Ho_Chi_Minh", "start_date": start.isoformat(), "end_date": end.isoformat(),
        })
        r.raise_for_status()
        return r.json()["daily"]["precipitation_probability_max"]

    try:
        if client is not None:
            values = _fetch(client)
        else:
            with httpx.Client(timeout=5) as c:
                values = _fetch(c)
    except (httpx.HTTPError, KeyError, ValueError):
        if frozen:
            kv.put(key, "null")
        return None  # Forecast là phần phụ: lỗi thì lập lịch không có thời tiết
    out = (values + [None] * days)[:days]
    kv.put(key, json.dumps(out), ex=None if frozen else CACHE_S)
    return out
