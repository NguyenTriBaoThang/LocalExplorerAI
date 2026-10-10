"""Attach sourced local District 1 photos to exact matching catalog POIs.

The script only links an image when the normalized place names match exactly
and the OSM point is within a short radius of the existing POI. It never
changes operational fields or a POI's verification status. Dry-run by default.

Run from apps/api:
    .\\.venv\\Scripts\\python.exe ..\\..\\scripts\\attach_district1_photos_to_catalog.py
    .\\.venv\\Scripts\\python.exe ..\\..\\scripts\\attach_district1_photos_to_catalog.py --apply
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

DEFAULT_BATCH_ID = "424074e6-fcc0-4e87-9d63-0a15ec77ae23"
LOCAL_PREFIX = "/images/places/district1/"


def normalized_name(value: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_name.lower()).strip()


def distance_meters(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    mean_lat = math.radians((lat_a + lat_b) / 2)
    north_m = (lat_a - lat_b) * 111_000
    east_m = (lon_a - lon_b) * 111_000 * math.cos(mean_lat)
    return math.hypot(north_m, east_m)


def valid_local_photo(photo: dict[str, Any]) -> bool:
    return (
        str(photo.get("local_url") or "").startswith(LOCAL_PREFIX)
        and ".." not in str(photo.get("local_url"))
        and str(photo.get("source_url") or "").startswith("https://commons.wikimedia.org/wiki/File:")
        and bool(photo.get("license"))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", default=DEFAULT_BATCH_ID)
    parser.add_argument("--max-distance-m", type=float, default=300)
    parser.add_argument("--apply", action="store_true", help="Persist image metadata to matching catalog POIs.")
    args = parser.parse_args()

    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.entities import AuditLog, PlaceImportCandidate, PlaceImportBatch, POI, User

    report: list[dict[str, Any]] = []
    linked = 0
    with SessionLocal() as db:
        batch = db.get(PlaceImportBatch, args.batch_id)
        if batch is None:
            parser.error(f"Place import batch not found: {args.batch_id}")
        candidates = db.scalars(
            select(PlaceImportCandidate).where(PlaceImportCandidate.batch_id == args.batch_id)
        ).all()
        pois = db.scalars(select(POI).where(POI.verification_status == "verified")).all()

        # Greedy shortest-distance assignment prevents duplicate OSM rows from
        # assigning the same photograph/POI pair more than once.
        matches: list[tuple[float, PlaceImportCandidate, POI, list[dict[str, Any]]]] = []
        for candidate in candidates:
            raw = candidate.raw_payload or {}
            photos = [item for item in raw.get("photos", []) if isinstance(item, dict) and valid_local_photo(item)]
            photos = [item for item in photos if (ROOT / str(item.get("local_path") or "")).is_file()]
            if not photos or raw.get("lat") is None or raw.get("lon") is None:
                continue
            source_name = normalized_name(candidate.name)
            for poi in pois:
                if normalized_name(poi.name) != source_name:
                    continue
                distance = distance_meters(float(raw["lat"]), float(raw["lon"]), poi.latitude, poi.longitude)
                if distance <= args.max_distance_m:
                    matches.append((distance, candidate, poi, photos))

        used_candidates: set[str] = set()
        used_pois: set[str] = set()
        actor = db.scalar(select(User).where(User.role == "admin").order_by(User.email).limit(1))
        for distance, candidate, poi, photos in sorted(matches, key=lambda item: item[0]):
            if candidate.id in used_candidates or poi.id in used_pois:
                continue
            used_candidates.add(candidate.id)
            used_pois.add(poi.id)
            details = dict(poi.details or {})
            images = list(details.get("images") or [])
            known_sources = {str(item.get("source_url")) for item in images if isinstance(item, dict)}
            new_photos = [item for item in photos if str(item.get("source_url")) not in known_sources]
            report.append({
                "poi_id": poi.id,
                "poi_name": poi.name,
                "candidate_name": candidate.name,
                "distance_m": round(distance, 1),
                "local_urls": [item["local_url"] for item in photos],
                "new_images": len(new_photos),
            })
            if not args.apply or not new_photos:
                continue

            details["images"] = images + new_photos
            details["photo_status"] = "source_photos_linked_from_osm_candidate"
            poi.details = details
            current_urls = list(poi.image_urls or [])
            poi.image_urls = list(dict.fromkeys([item["local_url"] for item in new_photos] + current_urls))
            db.add(AuditLog(
                actor_id=actor.id if actor else None,
                action="poi.source_photos_linked",
                target_type="poi",
                target_id=poi.id,
                details={
                    "candidate_id": candidate.id,
                    "osm_external_id": candidate.external_id,
                    "match_method": "exact_normalized_name_and_distance",
                    "distance_m": round(distance, 1),
                    "image_count": len(new_photos),
                    "verification_status_unchanged": poi.verification_status,
                },
            ))
            linked += len(new_photos)

        if args.apply:
            db.commit()

    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps({
        "mode": "apply" if args.apply else "dry_run",
        "batch_id": args.batch_id,
        "max_distance_m": args.max_distance_m,
        "matched_poi_count": len(report),
        "linked_photo_count": linked,
        "matches": report,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
