import time

import httpx

from app.core.config import settings

VEHICLE = {"xe-may": "bike", "xe-may-rieng": "bike", "grab": "car", "o-to-rieng": "car"}  # Travel Mode → xe của Goong
COOLDOWN_S = 60

# Cache trong tiến trình. Km giữa hai điểm không đổi nên không cần xoá.
# ponytail: không giới hạn kích thước — số Place hữu hạn.
_cache: dict[tuple, tuple[float, int]] = {}
_down_until = 0.0


def _key(a, b, vehicle: str) -> tuple:
    return (a.lat, a.lon, b.lat, b.lon, vehicle)


def lookup(a, b, mode: str) -> tuple[float, int] | None:
    """(km, phút) đường thật đã lấy từ Goong; chưa có → None. Không gọi Goong."""
    return _cache.get(_key(a, b, VEHICLE.get(mode, "bike")))


def prefetch(origins: list, destinations: list, mode: str, client: httpx.Client | None = None) -> None:
    """Một request Goong Distance Matrix cho mọi cặp origins × destinations, ghi vào cache cho lookup()."""
    global _down_until
    vehicle = VEHICLE.get(mode, "bike")
    if not settings.goong_api_key or time.monotonic() < _down_until:
        return
    if all(lookup(a, b, mode) is not None for a in origins for b in destinations):
        return
    url = f"{settings.goong_api_base_url.rstrip('/')}/DistanceMatrix"
    params = {"origins": "|".join(f"{p.lat},{p.lon}" for p in origins),
              "destinations": "|".join(f"{p.lat},{p.lon}" for p in destinations),
              "vehicle": vehicle, "api_key": settings.goong_api_key}
    try:
        r = client.get(url, params=params) if client is not None else httpx.get(url, params=params, timeout=3)
        r.raise_for_status()
        for a, row in zip(origins, r.json()["rows"]):
            for b, el in zip(destinations, row["elements"]):
                if el["status"] == "OK":
                    _cache[_key(a, b, vehicle)] = (round(el["distance"]["value"] / 1000, 2),
                                                   max(1, round(el["duration"]["value"] / 60)))
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        # Km thật là phần phụ: lỗi thì make_leg dùng chim bay × 1.3. Nghỉ một lúc để mất mạng không làm
        # mỗi ngày của Itinerary chờ thêm một timeout.
        _down_until = time.monotonic() + COOLDOWN_S
