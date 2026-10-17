import numpy as np
from psycopg.types.json import Jsonb

from app.domain import WEEKDAYS
from app.llm import EMBED_DIM

ALL_DAY = {d: ["00:00", "24:00"] for d in WEEKDAYS}


def unit_vec(i: int) -> list[float]:
    v = [0.0] * EMBED_DIM
    v[i] = 1.0
    return v


def add_place(conn, name="Place", kind="tham-quan", tags=(), price=0, lat=11.94, lon=108.44,
              outdoor=False, open_hours=None, vec=0, destination="da-lat") -> int:
    conn.execute(
        "INSERT INTO destinations(slug,name,lat,lon) VALUES (%s,%s,11.94,108.44) ON CONFLICT DO NOTHING",
        (destination, destination),
    )
    return conn.execute(
        """INSERT INTO places(ext_id,destination,name,kind,lat,lon,price,open_hours,outdoor,tags,embedding)
           VALUES (gen_random_uuid()::text,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (destination, name, kind, lat, lon, price, Jsonb(open_hours or ALL_DAY), outdoor,
         list(tags), np.array(unit_vec(vec), dtype=np.float32)),
    ).fetchone()["id"]
