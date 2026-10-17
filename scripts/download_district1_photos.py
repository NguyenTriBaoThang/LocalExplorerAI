r"""Download already-sourced Wikimedia photos into the web app's public assets.

This script does not search for or guess additional photos. It downloads only
photo URLs already matched to OSM/Wikidata records by the District 1 crawler,
and preserves per-file license and attribution metadata.

Run from the repository root:
    .\apps\api\.venv\Scripts\python.exe scripts\download_district1_photos.py \
      --batch-id 424074e6-fcc0-4e87-9d63-0a15ec77ae23
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

SOURCE_JSON = ROOT / "data" / "raw" / "district1_osm_places.json"
PUBLIC_DIR = ROOT / "apps" / "web" / "public" / "images" / "places" / "district1"
OUTPUT_JSON = ROOT / "data" / "raw" / "district1_osm_places_with_local_photos.json"
MANIFEST_JSON = ROOT / "data" / "raw" / "district1_osm_photos_manifest.json"
USER_AGENT = "LocalExplorerAI-POI-Catalog/1.0 (Wikimedia Commons image cache)"
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
}


def is_allowed_commons_url(value: str) -> bool:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and parsed.username is None
        and parsed.password is None
        and (host == "wikimedia.org" or host.endswith(".wikimedia.org"))
    )


def safe_stem(external_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", external_id).strip("_")[:100] or "place"


def photo_download_url(photo: dict[str, Any]) -> str:
    value = str(photo.get("url") or "").strip()
    if not is_allowed_commons_url(value):
        raise ValueError("Photo URL is not an HTTPS Wikimedia Commons host.")
    if not str(photo.get("source_url") or "").startswith("https://commons.wikimedia.org/wiki/File:"):
        raise ValueError("Photo is missing its Wikimedia Commons file page.")
    if not photo.get("license"):
        raise ValueError("Photo is missing its per-file license.")
    return value


def fetch_image(url: str) -> tuple[bytes, str, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=45) as response:
                final_url = response.geturl()
                if not is_allowed_commons_url(final_url):
                    raise ValueError("Wikimedia redirected the download to a non-Wikimedia host.")
                mime_type = response.headers.get_content_type().lower()
                if mime_type not in MIME_EXTENSIONS:
                    raise ValueError(f"Unsupported image content type: {mime_type}")
                content = response.read(MAX_IMAGE_BYTES + 1)
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError("Image exceeds the 15 MiB safety limit.")
                if not content:
                    raise ValueError("Wikimedia returned an empty image.")
                return content, mime_type, final_url
        except HTTPError as error:
            if error.code not in {429, 503} or attempt == 3:
                raise
            retry_after = error.headers.get("Retry-After")
            try:
                delay_seconds = min(30.0, max(1.0, float(retry_after))) if retry_after else 2 ** attempt
            except ValueError:
                delay_seconds = 2 ** attempt
            time.sleep(delay_seconds)
    raise RuntimeError("Wikimedia retry loop ended unexpectedly.")


def enrich_place_photos(
    document: dict[str, Any],
    *,
    public_dir: Path = PUBLIC_DIR,
    root: Path = ROOT,
    force: bool = False,
    fetcher: Callable[[str], tuple[bytes, str, str]] = fetch_image,
) -> tuple[dict[str, Any], dict[str, Any]]:
    public_root = (root / "apps" / "web" / "public").resolve()
    public_dir_resolved = public_dir.resolve()
    try:
        public_dir_resolved.relative_to(public_root)
    except ValueError as error:
        raise ValueError("Photo output directory must be inside apps/web/public.") from error

    output_document = json.loads(json.dumps(document, ensure_ascii=False))
    manifest_items: list[dict[str, Any]] = []
    downloaded = reused = failed = 0

    for place in output_document.get("places", []):
        external_id = str(place.get("ext_id") or "")
        photos = place.get("photos")
        if not isinstance(photos, list):
            photos = []
        if not photos and place.get("photo_url"):
            photos = [{"url": place["photo_url"]}]
        enriched_photos: list[dict[str, Any]] = []

        for photo in photos:
            if not isinstance(photo, dict):
                continue
            enriched = dict(photo)
            try:
                source_url = photo_download_url(photo)
                existing_relative = photo.get("local_path")
                existing_path = root / str(existing_relative) if existing_relative else None
                if not existing_path or not existing_path.is_file():
                    stem = safe_stem(external_id)
                    existing_path = next(
                        (candidate for candidate in public_dir.glob(f"{stem}.*") if candidate.is_file()),
                        None,
                    )
                if existing_path and existing_path.is_file() and not force:
                    content = existing_path.read_bytes()
                    mime_type = mimetypes.guess_type(existing_path.name)[0] or "application/octet-stream"
                    if mime_type not in MIME_EXTENSIONS or len(content) > MAX_IMAGE_BYTES:
                        existing_path = None
                if existing_path and existing_path.is_file() and not force:
                    content = existing_path.read_bytes()
                    mime_type = mimetypes.guess_type(existing_path.name)[0]
                    destination = existing_path
                    final_url = source_url
                    reused += 1
                else:
                    content, mime_type, final_url = fetcher(source_url)
                    extension = MIME_EXTENSIONS[mime_type]
                    destination = public_dir / f"{safe_stem(external_id)}{extension}"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(content)
                    downloaded += 1

                digest = hashlib.sha256(content).hexdigest()
                relative_path = destination.resolve().relative_to(root.resolve()).as_posix()
                local_url = "/" + destination.resolve().relative_to(public_root).as_posix()
                enriched.update({
                    "remote_url": source_url,
                    "url": source_url,
                    "local_url": local_url,
                    "local_path": relative_path,
                    "content_type": mime_type,
                    "byte_count": len(content),
                    "sha256": digest,
                    "downloaded_at": datetime.now(timezone.utc).isoformat(),
                })
                manifest_items.append({
                    "ext_id": external_id,
                    "name": place.get("name"),
                    "local_url": local_url,
                    "local_path": relative_path,
                    "remote_url": source_url,
                    "source_url": photo.get("source_url"),
                    "title": photo.get("title"),
                    "license": photo.get("license"),
                    "license_url": photo.get("license_url"),
                    "attribution": photo.get("attribution"),
                    "credit_line": photo.get("credit_line"),
                    "content_type": mime_type,
                    "byte_count": len(content),
                    "sha256": digest,
                    "redirected_url": final_url,
                })
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
                enriched["download_status"] = "failed"
                enriched["download_error"] = str(error)
                failed += 1
            enriched_photos.append(enriched)

        place["photos"] = enriched_photos
        images = place.get("details", {}).get("images") if isinstance(place.get("details"), dict) else None
        if isinstance(images, list):
            by_source = {str(item.get("source_url")): item for item in enriched_photos if item.get("source_url")}
            place["details"]["images"] = [by_source.get(str(item.get("source_url")), item) for item in images]
        successful = next((p for p in enriched_photos if p.get("local_url")), None)
        if successful:
            place["local_photo_url"] = successful["local_url"]
            if isinstance(place.get("details"), dict):
                place["details"]["photo_status"] = "downloaded_with_license_attribution"
        elif place.get("photo_url"):
            if isinstance(place.get("details"), dict):
                place["details"]["photo_status"] = "download_failed"

    metadata = dict(output_document.get("metadata") or {})
    metadata["local_photo_count"] = sum(1 for item in manifest_items)
    metadata["local_photo_directory"] = "apps/web/public/images/places/district1"
    metadata["photo_coverage_note"] = (
        "Only existing Wikimedia Commons matches were downloaded. Missing photos were not invented or replaced."
    )
    output_document["metadata"] = metadata
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_dataset": SOURCE_JSON.relative_to(ROOT).as_posix(),
        "photo_count": len(manifest_items),
        "downloaded_count": downloaded,
        "reused_count": reused,
        "failed_count": failed,
        "entries": manifest_items,
    }
    return output_document, manifest


def update_import_batch(batch_id: str, document: dict[str, Any], manifest: dict[str, Any]) -> int:
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.entities import AuditLog, PlaceImportBatch, PlaceImportCandidate, User

    by_external_id = {str(place.get("ext_id")): place for place in document.get("places", [])}
    with SessionLocal() as db:
        batch = db.get(PlaceImportBatch, batch_id)
        if batch is None:
            raise ValueError(f"Place import batch not found: {batch_id}")
        actor = db.scalar(select(User).where(User.role == "admin").order_by(User.email).limit(1))
        candidates = db.scalars(
            select(PlaceImportCandidate).where(PlaceImportCandidate.batch_id == batch_id)
        ).all()
        updated = 0
        for candidate in candidates:
            place = by_external_id.get(candidate.external_id)
            if not place or candidate.review_status != "needs_enrichment":
                continue
            payload = dict(candidate.raw_payload or {})
            for key in ("photos", "photo_url", "local_photo_url", "details"):
                if key in place:
                    payload[key] = place[key]
            candidate.raw_payload = payload
            updated += 1
        db.add(AuditLog(
            actor_id=actor.id if actor else None,
            action="place_import.photos_downloaded",
            target_type="place_import_batch",
            target_id=batch_id,
            details={"candidates_updated": updated, "local_photo_count": manifest["photo_count"]},
        ))
        db.commit()
        return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_JSON)
    parser.add_argument("--output", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_JSON)
    parser.add_argument("--public-dir", type=Path, default=PUBLIC_DIR)
    parser.add_argument("--batch-id", help="Also add local URLs to this existing admin import batch.")
    parser.add_argument("--force", action="store_true", help="Download again even if a local file already exists.")
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error(f"Source JSON not found: {args.source}")
    document = json.loads(args.source.read_text(encoding="utf-8"))
    enriched, manifest = enrich_place_photos(document, public_dir=args.public_dir, force=args.force)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    updated = update_import_batch(args.batch_id, enriched, manifest) if args.batch_id else None
    result = {
        "photo_count": manifest["photo_count"],
        "downloaded_count": manifest["downloaded_count"],
        "reused_count": manifest["reused_count"],
        "failed_count": manifest["failed_count"],
        "candidate_rows_updated": updated,
        "output": args.output.relative_to(ROOT).as_posix() if args.output.is_relative_to(ROOT) else str(args.output),
        "manifest": args.manifest.relative_to(ROOT).as_posix() if args.manifest.is_relative_to(ROOT) else str(args.manifest),
        "public_directory": args.public_dir.relative_to(ROOT).as_posix() if args.public_dir.is_relative_to(ROOT) else str(args.public_dir),
    }
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if manifest["failed_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
