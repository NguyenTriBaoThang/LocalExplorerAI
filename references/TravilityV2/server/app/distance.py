import json
import time

import httpx

from app import kv, places_client
from app.config import settings

URL = "https://rsapi.goong.io/DistanceMatrix"
VEHICLE = {"xe-may": "bike", "xe-may-rieng": "bike", "grab": "car", "o-to-rieng": "car"}  # Travel Mode → xe của Goong
COOLDOWN_S = 60

# Lớp cache trong tiến trình, đứng trước Redis (kv). Km giữa hai điểm không đổi nên không cần xoá.
# ponytail: không giới hạn kích thước — số Place hữu hạn.
_cache: dict[tuple, tuple[float, int]] = {}
_down_until = 0.0


def _key(a, b, vehicle: str) -> tuple:
    return (a.lat, a.lon, b.lat, b.lon, vehicle)


def _kv_key(k: tuple) -> str:
    return "goong:" + ":".join(map(str, k))


def lookup(a, b, mode: str) -> tuple[float, int] | None:
    """(km, phút) đường thật đã lấy từ Goong; chưa có → None. Không gọi Goong."""
    k = _key(a, b, VEHICLE.get(mode, "bike"))
    if k not in _cache and (raw := kv.get(_kv_key(k))):
        _cache[k] = tuple(json.loads(raw))
    return _cache.get(k)


def prefetch(origins: list, destinations: list, mode: str, client: httpx.Client | None = None) -> None:
    """Lấy km/phút thật cho mọi cặp origins × destinations vào cache của lookup().

    Có PLACES_URL → nhờ service places gọi Goong (spec scale §8); không thì gọi Goong ngay trong tiến trình.
    """
    if settings.places_url:
        _via_places(origins, destinations, mode)
    else:
        goong(origins, destinations, mode, client)


def _via_places(origins: list, destinations: list, mode: str) -> None:
    global _down_until
    if time.monotonic() < _down_until or all(lookup(a, b, mode) is not None for a in origins for b in destinations):
        return
    vehicle = VEHICLE.get(mode, "bike")
    try:
        rows = places_client.call("POST", "/distance", json={
            "origins": [{"lat": p.lat, "lon": p.lon} for p in origins],
            "destinations": [{"lat": p.lat, "lon": p.lon} for p in destinations], "mode": mode})["rows"]
        for a, row in zip(origins, rows):
            for b, v in zip(destinations, row):
                if v:
                    _cache[_key(a, b, vehicle)] = (v[0], v[1])
    except (places_client.PlacesDown, KeyError, TypeError, IndexError):
        _down_until = time.monotonic() + COOLDOWN_S  # places chết: make_leg dùng chim bay × 1.3 như khi Goong lỗi


def goong(origins: list, destinations: list, mode: str, client: httpx.Client | None = None) -> None:
    """Một request Goong Distance Matrix cho mọi cặp origins × destinations, ghi vào cache cho lookup()."""
    global _down_until
    vehicle = VEHICLE.get(mode, "bike")
    if not settings.goong_api_key or time.monotonic() < _down_until:
        return
    if all(lookup(a, b, mode) is not None for a in origins for b in destinations):
        return
    params = {"origins": "|".join(f"{p.lat},{p.lon}" for p in origins),
              "destinations": "|".join(f"{p.lat},{p.lon}" for p in destinations),
              "vehicle": vehicle, "api_key": settings.goong_api_key}
    try:
        r = client.get(URL, params=params) if client is not None else httpx.get(URL, params=params, timeout=3)
        r.raise_for_status()
        for a, row in zip(origins, r.json()["rows"]):
            for b, el in zip(destinations, row["elements"]):
                if el["status"] == "OK":
                    k, v = _key(a, b, vehicle), (round(el["distance"]["value"] / 1000, 2),
                                                 max(1, round(el["duration"]["value"] / 60)))
                    _cache[k] = v
                    kv.put(_kv_key(k), json.dumps(v))
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        # Km thật là phần phụ: lỗi thì make_leg dùng chim bay × 1.3. Nghỉ một lúc để mất mạng không làm
        # mỗi ngày của Itinerary chờ thêm một timeout.
        _down_until = time.monotonic() + COOLDOWN_S
