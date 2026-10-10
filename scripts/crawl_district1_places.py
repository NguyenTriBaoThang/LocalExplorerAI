"""Fetch named POI-like OSM records in the legacy District 1 pilot polygon.

The crawler only stages sourced facts. It does not mark places as verified and
never invents venue descriptions, prices, opening hours, slots, or capacity.

Run from the repository root with the API virtualenv:
    ./apps/api/.venv/Scripts/python.exe scripts/crawl_district1_places.py
    ./apps/api/.venv/Scripts/python.exe scripts/crawl_district1_places.py --skip-photos
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
sys.path.insert(0, str(API_DIR))

from app.services.pilot_area import (  # noqa: E402
    PILOT_MAX_LATITUDE,
    PILOT_MAX_LONGITUDE,
    PILOT_MIN_LATITUDE,
    PILOT_MIN_LONGITUDE,
    is_pilot_location,
)


OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "LocalExplorerAI-POI-Catalog/1.0 (OSM and Wikimedia public APIs)"


def _request_json(url: str, *, body: bytes | None = None, timeout: int = 90) -> dict[str, Any]:
    request = Request(
        url,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            **({"Content-Type": "application/x-www-form-urlencoded"} if body is not None else {}),
        },
        method="POST" if body is not None else "GET",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def overpass_query() -> str:
    bbox = (
        f"{PILOT_MIN_LATITUDE},{PILOT_MIN_LONGITUDE},"
        f"{PILOT_MAX_LATITUDE},{PILOT_MAX_LONGITUDE}"
    )
    # Keep named, public-facing place categories broad. Exact inclusion is
    # checked against the pilot polygon below, not this bounding box.
    filters = (
        '["name"]["tourism"]', '["name"]["historic"]',
        '["name"]["amenity"]', '["name"]["leisure"]',
        '["name"]["shop"]', '["name"]["craft"]',
        '["name"]["artwork_type"]', '["name"]["attraction"]',
    )
    statements = "\n".join(f"  nwr{filter_text}({bbox});" for filter_text in filters)
    return f"[out:json][timeout:120];\n(\n{statements}\n);\nout meta center;"


def fetch_osm_elements() -> tuple[list[dict[str, Any]], str]:
    query = overpass_query().encode("utf-8")
    errors: list[str] = []
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(3):
            try:
                payload = _request_json(endpoint, body=urlencode({"data": query.decode()}).encode(), timeout=180)
                elements = payload.get("elements")
                if not isinstance(elements, list):
                    raise ValueError("Overpass returned no elements array.")
                snapshot = str(payload.get("osm3s", {}).get("timestamp_osm_base") or "")
                return elements, snapshot
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
                errors.append(f"{endpoint} attempt {attempt + 1}: {error}")
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("Could not query an Overpass endpoint. " + " | ".join(errors[-4:]))


def element_point(element: dict[str, Any]) -> tuple[float, float] | None:
    if element.get("type") == "node":
        latitude, longitude = element.get("lat"), element.get("lon")
    else:
        center = element.get("center") or {}
        latitude, longitude = center.get("lat"), center.get("lon")
    try:
        latitude, longitude = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None
    return (latitude, longitude) if is_pilot_location(latitude, longitude) else None


def _address(tags: dict[str, str]) -> str:
    full = tags.get("addr:full") or tags.get("address")
    if full:
        return full.strip()
    parts = [tags.get("addr:housenumber"), tags.get("addr:street")]
    locality = tags.get("addr:suburb") or tags.get("addr:quarter")
    if locality:
        parts.append(locality)
    return ", ".join(part.strip() for part in parts if part and part.strip())


def _category(tags: dict[str, str]) -> str:
    for key in ("tourism", "historic", "amenity", "leisure", "shop", "craft", "artwork_type", "attraction"):
        if tags.get(key):
            return f"{key}:{tags[key]}"
    return "unknown"


def normalize_elements(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for element in elements:
        point = element_point(element)
        tags = element.get("tags") or {}
        name = str(tags.get("name") or "").strip()
        if not point or not name:
            continue
        osm_type = str(element.get("type") or "")
        osm_id = element.get("id")
        if not osm_type or osm_id is None:
            continue
        external_id = f"{osm_type}/{osm_id}"
        if external_id in seen:
            continue
        seen.add(external_id)
        latitude, longitude = point
        source_uri = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
        description = tags.get("description:vi") or tags.get("description") or ""
        photos = []
        commons_tag = tags.get("wikimedia_commons", "")
        if commons_tag.startswith("File:"):
            photos.append({"commons_title": commons_tag})
        image_tag = tags.get("image", "")
        if image_tag.startswith(("File:", "https://commons.wikimedia.org/wiki/File:")):
            photos.append({"commons_title": image_tag})
        rows.append({
            "ext_id": external_id,
            "name": name,
            "kind": _category(tags),
            "lat": latitude,
            "lon": longitude,
            "address": _address(tags),
            "price_vnd": None,
            "price_basis": None,
            "open_hours": tags.get("opening_hours"),
            "outdoor": None,
            "tags": dict(sorted(tags.items())),
            "description": description,
            "photo_url": None,
            "photos": photos,
            "source": source_uri,
            "verified": False,
            "source_observed_at": datetime.now(timezone.utc).isoformat(),
            "details": {
                "contact_phone": tags.get("phone") or tags.get("contact:phone"),
                "contact_email": tags.get("email") or tags.get("contact:email"),
                "website": tags.get("website") or tags.get("contact:website"),
                "opening_hours": tags.get("opening_hours"),
                "fee": tags.get("fee"),
                "wheelchair": tags.get("wheelchair"),
                "osm_type": osm_type,
                "osm_id": int(osm_id),
                "osm_url": source_uri,
                "osm_version": element.get("version"),
                "osm_timestamp": element.get("timestamp"),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "osm_tags": dict(sorted(tags.items())),
                "images": [],
                "photo_status": "not_found",
            },
        })
    return rows


def _wikidata_photo_titles(rows: list[dict[str, Any]]) -> dict[str, str]:
    ids = sorted({str(row["tags"].get("wikidata")) for row in rows if row["tags"].get("wikidata")})
    result: dict[str, str] = {}
    for offset in range(0, len(ids), 50):
        batch = ids[offset:offset + 50]
        query = urlencode({"action": "wbgetentities", "ids": "|".join(batch), "props": "claims", "format": "json"})
        try:
            data = _request_json(f"{WIKIDATA_API}?{query}")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            continue
        for entity_id, entity in data.get("entities", {}).items():
            claims = entity.get("claims", {}).get("P18", [])
            if claims:
                value = claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(value, str) and value.strip():
                    result[entity_id] = f"File:{value.strip()}"
    return result


def _strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]*>", "", value or "")).strip()


def _commons_file_metadata(titles: list[str]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for offset in range(0, len(titles), 25):
        batch = titles[offset:offset + 25]
        params = urlencode({
            "action": "query", "format": "json", "formatversion": "2",
            "titles": "|".join(batch), "prop": "imageinfo", "iiprop": "url|extmetadata",
            "iiurlwidth": "1200",
        })
        try:
            data = _request_json(f"{COMMONS_API}?{params}")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            continue
        pages = data.get("query", {}).get("pages", [])
        for page in pages:
            image_info = (page.get("imageinfo") or [{}])[0]
            extra = image_info.get("extmetadata") or {}
            license_short = _strip_html((extra.get("LicenseShortName") or {}).get("value", ""))
            license_url = (extra.get("LicenseUrl") or {}).get("value")
            thumb_url = image_info.get("thumburl")
            original_url = image_info.get("url")
            description_url = image_info.get("descriptionurl")
            if not license_short or not thumb_url or not description_url:
                continue
            output[page.get("title", "")] = {
                "url": thumb_url or original_url,
                "source_url": description_url,
                "title": page.get("title", ""),
                "license": license_short,
                "license_url": license_url,
                "attribution": _strip_html((extra.get("Artist") or {}).get("value", "")),
                "credit_line": _strip_html((extra.get("Credit") or {}).get("value", "")),
            }
    return output


def enrich_commons_photos(rows: list[dict[str, Any]]) -> None:
    wikidata_photos = _wikidata_photo_titles(rows)
    title_by_external_id: dict[str, str] = {}
    for row in rows:
        candidates = [item["commons_title"] for item in row["photos"] if item.get("commons_title")]
        wikidata_id = str(row["tags"].get("wikidata") or "")
        if not candidates and wikidata_id in wikidata_photos:
            candidates.append(wikidata_photos[wikidata_id])
        if candidates:
            title = candidates[0]
            if title.startswith("https://commons.wikimedia.org/wiki/File:"):
                title = "File:" + title.rsplit("/File:", 1)[-1].replace("_", " ")
            title_by_external_id[row["ext_id"]] = title
    metadata = _commons_file_metadata(sorted(set(title_by_external_id.values())))
    for row in rows:
        title = title_by_external_id.get(row["ext_id"])
        photo = metadata.get(title or "")
        if not photo:
            continue
        row["photos"] = [photo]
        row["photo_url"] = photo["url"]
        row["details"]["images"] = [photo]
        row["details"]["photo_status"] = "commons_license_metadata_found"


def crawl(output_path: Path, include_photos: bool = True) -> dict[str, Any]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    elements, osm_snapshot = fetch_osm_elements()
    places = normalize_elements(elements)
    if include_photos:
        enrich_commons_photos(places)
    for place in places:
        place["source_observed_at"] = fetched_at
        place["details"]["observed_at"] = fetched_at
        place["details"]["photo_source"] = "Wikimedia Commons, matched by explicit OSM wikimedia_commons/image or Wikidata P18" if place["photo_url"] else None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "metadata": {
            "dataset": "legacy_district1_named_places_from_openstreetmap",
            "fetched_at": fetched_at,
            "osm_snapshot_at": osm_snapshot,
            "source": "OpenStreetMap Overpass API",
            "source_url": "https://www.openstreetmap.org/copyright",
            "license": "ODbL-1.0",
            "photo_source": "Wikimedia Commons API; per-file license/credit retained",
            "pilot_boundary": "historic District 1 pilot polygon based on 2016 OSM-derived boundary; not a current administrative boundary",
            "coverage_note": "Contains named OSM records with selected public-facing tags whose representative coordinates fall inside the pilot polygon. OSM coverage may be incomplete; this is not proof every real-world venue is listed.",
            "verification_status": "source_candidates_not_operationally_verified",
            "estimated_columns": [],
            "record_count": len(places),
            "photo_count": sum(bool(place["photo_url"]) for place in places),
        },
        "places": places,
    }
    output_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return document["metadata"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "raw" / "district1_osm_places.json")
    parser.add_argument("--skip-photos", action="store_true", help="Skip Commons/Wikidata queries and collect only OSM tags.")
    args = parser.parse_args()
    try:
        result = crawl(args.output, include_photos=not args.skip_photos)
    except Exception as error:
        print(f"Crawl failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({**result, "output": str(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
