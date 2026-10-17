import numpy as np

from app.domain import Place

COLUMNS = "id, destination, name, kind, lat, lon, price, open_hours, outdoor, tags, description, photo_url"


def search_places(conn, destination: str, query_vec: list[float], kind: str | None = None,
                  must_have_tags=(), exclude_tags=(), limit: int = 8) -> list[Place]:
    rows = conn.execute(
        f"""SELECT {COLUMNS} FROM places
            WHERE destination = %(d)s
              AND (%(k)s::text IS NULL OR kind = %(k)s)
              AND tags @> %(must)s::text[]
              AND NOT (tags && %(ex)s::text[])
            ORDER BY embedding <=> %(v)s
            LIMIT %(n)s""",
        {"d": destination, "k": kind, "must": list(must_have_tags), "ex": list(exclude_tags),
         "v": np.array(query_vec, dtype=np.float32), "n": limit},
    ).fetchall()
    return [Place.model_validate(r) for r in rows]


def similar_places(conn, place_id: int, kind: str, exclude_ids=(), exclude_tags=(), limit: int = 20) -> list[Place]:
    """Place giống place_id theo embedding đã lưu — không gọi API embedding, chạy được khi mất mạng."""
    rows = conn.execute(
        f"""SELECT {COLUMNS} FROM places
            WHERE destination = (SELECT destination FROM places WHERE id = %(id)s)
              AND kind = %(k)s
              AND NOT (id = ANY(%(ids)s::int[]))
              AND NOT (tags && %(ex)s::text[])
            ORDER BY embedding <=> (SELECT embedding FROM places WHERE id = %(id)s)
            LIMIT %(n)s""",
        {"id": place_id, "k": kind, "ids": list(exclude_ids), "ex": list(exclude_tags), "n": limit},
    ).fetchall()
    return [Place.model_validate(r) for r in rows]


def get_places(conn, ids: list[int]) -> dict[int, Place]:
    rows = conn.execute(f"SELECT {COLUMNS} FROM places WHERE id = ANY(%s)", (list(ids),)).fetchall()
    return {r["id"]: Place.model_validate(r) for r in rows}


def list_destinations(conn) -> list[dict]:
    return conn.execute("SELECT slug, name, lat, lon, hubs FROM destinations ORDER BY name").fetchall()
