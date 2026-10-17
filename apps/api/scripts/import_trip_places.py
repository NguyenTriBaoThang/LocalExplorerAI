"""Load data/sai_gon_places.json into trip_places. Run: python -m scripts.import_trip_places /data/sai_gon_places.json"""
import json
import sys
from pathlib import Path

from sqlalchemy import null, select
from sqlalchemy.orm import Session

from app.models.trip_entities import TripDestination, TripPlace
from app.services.trip.domain import TAGS, WEEKDAYS

DAY_CODES = {"T2": 0, "T3": 1, "T4": 2, "T5": 3, "T6": 4, "T7": 5, "CN": 6}

TAG_MAP = {
    **dict.fromkeys(["chay"], "an-chay"),
    **dict.fromkeys(["mon-viet", "dac-san", "dac-san-sai-gon", "am-thuc-duong-pho", "com-tam", "banh-mi", "nam-bo",
                     "an-vat", "binh-dan"], "an-dia-phuong"),
    **dict.fromkeys(["specialty-coffee", "cafe", "chill", "cafe-phin"], "cafe-chill"),
    **dict.fromkeys(["bao-tang", "di-tich", "di-san", "di-tich-quoc-gia"], "lich-su"),
    **dict.fromkeys(["kien-truc", "nghe-thuat", "tam-linh", "ton-giao", "truyen-thong"], "van-hoa"),
    **dict.fromkeys(["cong-vien", "cay-xanh", "sinh-thai", "san-vuon"], "thien-nhien"),
    **dict.fromkeys(["rooftop", "hoang-hon", "view-song", "view-toan-canh"], "view-dep"),
    **dict.fromkeys(["bar", "pub", "nightclub", "live-music", "pho-di-bo", "nhon-nhip"], "soi-dong"),
    **dict.fromkeys(["buoi-toi", "giai-tri-dem"], "dem"),
    **dict.fromkeys(["thanh-tinh", "thu-gian"], "yen-tinh"),
    **dict.fromkeys(["hen-ho"], "lang-man"),
    **dict.fromkeys(["bieu-tuong", "noi-tieng"], "check-in"),
    **dict.fromkeys(["khach-san-5-sao", "michelin", "michelin-selected", "fine-dining", "xa-hoa"], "sang-trong"),
    **dict.fromkeys(["cho", "cho-que"], "mua-sam"),
    **dict.fromkeys(["cong-vien-nuoc"], "gia-dinh"),
    # additions for tags that occur in the dataset
    **dict.fromkeys(["oc", "cho-hai-san", "buffet-tom-hum"], "hai-san"),
    **dict.fromkeys(["cocktail", "skybar", "jazz", "lounge", "nhac-song"], "soi-dong"),
    **dict.fromkeys(["ven-song", "view-cong-vien", "view-pho-tay", "view-trung-tam"], "view-dep"),
    **dict.fromkeys(["khach-san-6-sao", "michelin-star", "1-sao-michelin"], "sang-trong"),
}

HCMC_HUBS = {
    "may-bay": {"name": "Sân bay Tân Sơn Nhất", "lat": 10.8188, "lon": 106.6519},
    "tau": {"name": "Ga Sài Gòn", "lat": 10.7820, "lon": 106.6773},
    "xe-khach": {"name": "Bến xe Miền Đông mới", "lat": 10.8790, "lon": 106.8146},
}
DESTINATION = {"slug": "tp-hcm", "name": "TP. Hồ Chí Minh", "lat": 10.7769, "lon": 106.7009}


def _open_days(days: str, ext_id: str) -> set[int]:
    try:
        if "-" in days:
            lo, hi = (DAY_CODES[c.strip()] for c in days.split("-"))
            if lo > hi:
                raise KeyError(days)
            return set(range(lo, hi + 1))
        return {DAY_CODES[c.strip()] for c in days.split(",")}
    except (KeyError, ValueError):
        raise ValueError(f"{ext_id}: giờ mở cửa lạ {days!r}") from None


def _open_hours(raw: dict) -> dict:
    try:
        h = json.loads(raw["open_hours"])
        window, days = [h["open"], h["close"]], h["days"]
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"{raw['id']}: giờ mở cửa lạ {raw.get('open_hours')!r}") from None
    open_days = _open_days(days, raw["id"])
    return {d: (window if i in open_days else None) for i, d in enumerate(WEEKDAYS)}


def convert(raw: dict) -> dict:
    """One sai_gon_places.json record -> TripPlace columns (without destination/embedding)."""
    raw_tags = raw.get("tags", [])
    note = raw.get("note")
    return {
        "ext_id": raw["id"], "name": raw["name"], "kind": raw["kind"], "lat": raw["lat"], "lon": raw["lon"],
        "price": raw.get("price_vnd", 0), "open_hours": _open_hours(raw), "outdoor": raw.get("outdoor", False),
        "tags": sorted({TAG_MAP[t] for t in raw_tags if t in TAG_MAP} | (set(raw_tags) & TAGS)),
        "raw_tags": raw_tags,
        "description": raw.get("description", "") + (f" {note}" if note else ""),
        "address": raw.get("address", ""), "photo_url": raw.get("photo_url"), "source": raw.get("source"),
    }


def place_text(p: dict) -> str:
    return f"{p['name']}. {p['description']}. Tags: {', '.join(p['raw_tags'])}"


def import_file(db: Session, path, embed_fn) -> int:
    rows = [convert(r) for r in json.loads(Path(path).read_text(encoding="utf-8"))]
    dest = db.get(TripDestination, DESTINATION["slug"]) or TripDestination(**DESTINATION)
    dest.name, dest.lat, dest.lon, dest.hubs = DESTINATION["name"], DESTINATION["lat"], DESTINATION["lon"], HCMC_HUBS
    db.add(dest)
    vecs = embed_fn([place_text(r) for r in rows]) or [None] * len(rows)
    existing = {p.ext_id: p for p in db.scalars(select(TripPlace))}
    for row, vec in zip(rows, vecs, strict=True):
        place = existing.get(row["ext_id"]) or TripPlace(ext_id=row["ext_id"])
        for k, v in row.items():
            setattr(place, k, v)
        place.destination = dest.slug
        place.embedding = vec if vec is not None else null()  # SQL NULL, not JSON null
        db.add(place)
    db.commit()
    return len(rows)


if __name__ == "__main__":
    from app.db.session import SessionLocal
    from app.services.trip import llm

    with SessionLocal() as db:
        print(import_file(db, sys.argv[1] if len(sys.argv) > 1 else "/data/sai_gon_places.json",
                          lambda texts: llm.embed(db, texts)))
