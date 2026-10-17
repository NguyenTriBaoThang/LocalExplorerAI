import math
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.trip_entities import TripDestination, TripPlace
from app.services.chat_response_service import _fold

EmbedFn = Callable[[list[str]], list[list[float]] | None]


def _cosine(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def search_places(db: Session, destination: str, query: str, embed_fn: EmbedFn, kind: str | None = None,
                  required_tags=(), avoided_tags=(), limit: int = 8) -> list[TripPlace]:
    # ponytail: whole destination is loaded and scored in Python; fine for ~200 places, needs pgvector beyond ~10k
    stmt = select(TripPlace).where(TripPlace.destination == destination).order_by(TripPlace.id)
    if kind:
        stmt = stmt.where(TripPlace.kind == kind)
    required, avoided = set(required_tags), set(avoided_tags)
    rows = [p for p in db.scalars(stmt) if required <= set(p.tags or []) and not avoided & set(p.tags or [])]
    vecs = embed_fn([query]) if rows and all(p.embedding for p in rows) else None
    if vecs:
        rows.sort(key=lambda p: -_cosine(vecs[0], p.embedding))  # stable: ties keep id order
        return rows[:limit]
    words = set(_fold(query).split())

    def score(p: TripPlace) -> int:
        text = set(_fold(f"{p.name} {p.description} {' '.join(p.raw_tags or [])}".replace("-", " ")).split())
        return len(words & text)

    rows.sort(key=lambda p: -score(p))
    return rows[:limit]


def similar_places(db: Session, place_id: int, kind: str, exclude_ids=(), exclude_tags=(), limit: int = 20) -> list[TripPlace]:
    """Places like place_id from stored embeddings only — no embedding API call, works offline."""
    base = db.get(TripPlace, place_id)
    if base is None:
        return []
    banned = set(exclude_tags)
    rows = [p for p in db.scalars(select(TripPlace).where(
        TripPlace.destination == base.destination, TripPlace.kind == kind, TripPlace.id != place_id,
    ).order_by(TripPlace.id)) if p.id not in set(exclude_ids) and not banned & set(p.tags or [])]
    if base.embedding and all(p.embedding for p in rows):
        rows.sort(key=lambda p: -_cosine(base.embedding, p.embedding))
    else:
        tags = set(base.tags or [])
        rows.sort(key=lambda p: (-len(tags & set(p.tags or [])), (p.lat - base.lat) ** 2 + (p.lon - base.lon) ** 2))
    return rows[:limit]


def get_places(db: Session, ids) -> dict[int, TripPlace]:
    return {p.id: p for p in db.scalars(select(TripPlace).where(TripPlace.id.in_(list(ids))))}


def list_destinations(db: Session) -> list[dict]:
    return [{"slug": d.slug, "name": d.name, "lat": d.lat, "lon": d.lon, "hubs": d.hubs}
            for d in db.scalars(select(TripDestination).order_by(TripDestination.name))]
