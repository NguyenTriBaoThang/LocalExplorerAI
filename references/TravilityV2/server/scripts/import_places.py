"""Nạp data/places/*.json vào Postgres. Chạy: cd server && uv run python -m scripts.import_places ../data/places"""
import json
import sys
from pathlib import Path
from typing import get_args

import numpy as np
from psycopg.types.json import Jsonb

from app import llm
from app.db import apply_schema, connect
from app.domain import KINDS, TAGS, WEEKDAYS, ArrivalMode


def expand_hours(hours: dict) -> dict:
    """{"daily": [...], "mon": null} → đủ 7 ngày; ngày ghi riêng đè lên daily."""
    daily = hours.get("daily")
    out = {d: daily for d in WEEKDAYS} if daily else {}
    out.update({k: v for k, v in hours.items() if k in WEEKDAYS})
    return out


def place_text(p: dict) -> str:
    return f"{p['name']}. {p.get('description', '')}. Tags: {', '.join(p['tags'])}"


def import_file(conn, path, embed_fn) -> int:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    d = data["destination"]
    places = data["places"]
    for p in places:
        bad = set(p["tags"]) - TAGS
        if bad:
            raise ValueError(f"{p['ext_id']}: tag lạ {sorted(bad)}")
        if p["kind"] not in KINDS:
            raise ValueError(f"{p['ext_id']}: kind lạ {p['kind']}")
    hubs = d.get("hubs", {})
    bad_hubs = set(hubs) - set(get_args(ArrivalMode))
    if bad_hubs:
        raise ValueError(f"{d['slug']}: hub lạ {sorted(bad_hubs)}")
    conn.execute(
        """INSERT INTO destinations(slug,name,lat,lon,hubs) VALUES (%s,%s,%s,%s,%s)
           ON CONFLICT (slug) DO UPDATE SET name=excluded.name, lat=excluded.lat, lon=excluded.lon,
             hubs=excluded.hubs""",
        (d["slug"], d["name"], d["lat"], d["lon"], Jsonb(hubs)),
    )
    vecs = embed_fn([place_text(p) for p in places])
    for p, v in zip(places, vecs, strict=True):
        conn.execute(
            """INSERT INTO places(ext_id,destination,name,kind,lat,lon,price,open_hours,outdoor,tags,
                                  description,photo_url,embedding)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (ext_id) DO UPDATE SET destination=excluded.destination, name=excluded.name,
                 kind=excluded.kind, lat=excluded.lat, lon=excluded.lon, price=excluded.price,
                 open_hours=excluded.open_hours, outdoor=excluded.outdoor, tags=excluded.tags,
                 description=excluded.description, photo_url=excluded.photo_url, embedding=excluded.embedding""",
            (p["ext_id"], d["slug"], p["name"], p["kind"], p["lat"], p["lon"], p.get("price", 0),
             Jsonb(expand_hours(p.get("open_hours", {}))), p.get("outdoor", False), p["tags"],
             p.get("description", ""), p.get("photo_url"), np.array(v, dtype=np.float32)),
        )
    return len(places)


if __name__ == "__main__":
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "../data/places")
    with connect() as conn:
        apply_schema(conn, shard=False)  # import chỉ cần bảng chung
        for f in sorted(folder.glob("*.json")):
            print(f.name, import_file(conn, f, llm.embed))
