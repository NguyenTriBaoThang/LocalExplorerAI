"""Một cửa cho mọi lần đọc Place / Destination (spec scale §8): code gọi không biết dữ liệu đến từ đâu.

`conn` là kết nối Trip của người gọi. Nó chỉ được dùng để đọc Place ở chế độ đơn giản (một database);
có CATALOG_REPLICA_URL hoặc SHARD_URLS thì module tự mở kết nối đọc database chung; có PLACES_URL thì gọi
service places qua HTTP.
"""
from contextlib import contextmanager

import httpx

from app import db, places
from app.config import settings
from app.domain import Place

PLACES_DOWN = "Dịch vụ địa điểm tạm không truy cập được, bạn thử lại sau nhé."
TIMEOUT_S = 15  # /search có một lượt embedding qua llm-gateway

_http: httpx.Client | None = None  # test thay bằng TestClient của places_service
_dests: list[dict] | None = None  # Destination đọc được gần nhất; dùng khi places chết (spec S27)


class PlacesDown(Exception):
    """Service places không trả lời hoặc trả lỗi."""


def call(method: str, path: str, **kw):
    url = settings.places_url + path
    try:
        r = _http.request(method, url, **kw) if _http else httpx.request(method, url, timeout=TIMEOUT_S, **kw)
        if r.status_code >= 400:
            raise PlacesDown(f"{method} {path} → {r.status_code}")
        return r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise PlacesDown(str(e)) from e


@contextmanager
def _reader(conn):
    if settings.catalog_replica_url or settings.shard_urls:
        with db.catalog_read() as c:
            yield c
    else:
        yield conn


def search_places(conn, destination: str, query: str, embed_fn, kind: str | None = None,
                  must_have_tags=(), exclude_tags=(), limit: int = 8) -> list[Place]:
    if settings.places_url:  # service tự embed qua llm-gateway; embed_fn của người gọi không dùng
        rows = call("POST", "/search", json={
            "destination": destination, "query": query, "kind": kind, "must_have_tags": list(must_have_tags),
            "exclude_tags": list(exclude_tags), "limit": limit})
        return [Place.model_validate(r) for r in rows]
    vec = embed_fn([query])[0]
    with _reader(conn) as c:
        return places.search_places(c, destination, vec, kind, must_have_tags, exclude_tags, limit)


def similar_places(conn, place_id: int, kind: str, exclude_ids=(), exclude_tags=(), limit: int = 20) -> list[Place]:
    if settings.places_url:
        rows = call("POST", "/similar", json={
            "place_id": place_id, "kind": kind, "exclude_ids": list(exclude_ids), "exclude_tags": list(exclude_tags),
            "limit": limit})
        return [Place.model_validate(r) for r in rows]
    with _reader(conn) as c:
        return places.similar_places(c, place_id, kind, exclude_ids, exclude_tags, limit)


def get_places(conn, ids) -> dict[int, Place]:
    ids = list(ids)
    if settings.places_url:
        rows = call("GET", "/places", params={"ids": ids}) if ids else []
        return {r["id"]: Place.model_validate(r) for r in rows}
    with _reader(conn) as c:
        return places.get_places(c, ids)


def list_destinations(conn) -> list[dict]:
    global _dests
    if not settings.places_url:
        with _reader(conn) as c:
            return places.list_destinations(c)
    try:
        _dests = call("GET", "/destinations")
    except PlacesDown:
        if _dests is None:
            raise
    return _dests
