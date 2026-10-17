"""Stage place rows from an XLSX sheet without publishing them as operational POIs.

Example:
    python -m scripts.import_place_candidates --dry-run
    python -m scripts.import_place_candidates
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from sqlalchemy import select

# Support both `python -m scripts.import_place_candidates` and direct
# execution from apps/api (the latter puts only the scripts directory on
# sys.path, so `app` would otherwise be unimportable on Windows).
API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.db.session import SessionLocal
from app.models.entities import AuditLog, PlaceImportBatch, PlaceImportCandidate, User


ROOT = Path(__file__).resolve().parents[3]
EXPECTED_HEADERS = {
    "ext_id", "name", "kind", "lat", "lon", "price_vnd", "open_hours",
    "outdoor", "tags", "description", "photo_url", "verified", "source", "note",
}
DISTRICT1_HEADERS = {
    "poi_key", "name", "category", "full_address", "latitude", "longitude",
    "source_url", "source_type", "license", "fields_covered", "observed_at",
    "expires_at", "photo_url", "photo_credit", "verification_status",
}
NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _column_number(cell_ref: str) -> int:
    letters = "".join(character for character in cell_ref if character.isalpha())
    value = 0
    for character in letters:
        value = value * 26 + ord(character.upper()) - ord("A") + 1
    return value


def _raw_cell_value(cell: ET.Element, shared_strings: list[str]) -> str | None:
    inline = cell.find("m:is", NS)
    if inline is not None:
        return "".join(inline.itertext())
    value = cell.find("m:v", NS)
    if value is None:
        return None
    if cell.attrib.get("t") == "s":
        return shared_strings[int(value.text or "0")]
    return value.text


def read_xlsx_sheet(path: Path, sheet_name: str) -> tuple[list[dict], int]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml")) if "xl/sharedStrings.xml" in names else None
        shared_strings = ["".join(item.itertext()) for item in shared_root.findall("m:si", NS)] if shared_root is not None else []
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        sheet = next((item for item in workbook.findall("m:sheets/m:sheet", NS) if item.attrib.get("name") == sheet_name), None)
        if sheet is None:
            raise ValueError(f"Workbook does not contain worksheet {sheet_name!r}.")
        target = targets[sheet.attrib[REL_ID]].lstrip("/")
        target = target if target.startswith("xl/") else f"xl/{target}"
        sheet_xml = ET.fromstring(archive.read(target))
        xml_rows = sheet_xml.findall("m:sheetData/m:row", NS)

    rows: list[list[str | None]] = []
    for xml_row in xml_rows:
        values: list[str | None] = []
        for cell in xml_row.findall("m:c", NS):
            column = _column_number(cell.attrib["r"])
            while len(values) < column:
                values.append(None)
            values[column - 1] = _raw_cell_value(cell, shared_strings)
        rows.append(values)
    if not rows:
        raise ValueError(f"Worksheet {sheet_name!r} is empty.")

    headers = [str(value or "").strip() for value in rows[0]]
    if sheet_name == "Sai_Gon":
        required_headers = EXPECTED_HEADERS
    elif sheet_name == "Verified_District1":
        required_headers = DISTRICT1_HEADERS
    else:
        raise ValueError(
            f"Worksheet {sheet_name!r} is not a POI intake sheet. "
            "Import experiences and slots through their separate review workflows."
        )
    missing = sorted(required_headers - set(headers))
    if missing:
        raise ValueError(f"Worksheet is missing required source columns: {missing}")
    records = []
    for source_row, values in enumerate(rows[1:], start=2):
        record = {header: values[index] if index < len(values) else None for index, header in enumerate(headers) if header}
        if not any(value not in (None, "") for value in record.values()):
            continue
        records.append((_coerce_record(_normalize_poi_record(record, sheet_name)), source_row))
    return records, len(rows)


def read_json_places(path: Path) -> tuple[list[dict], int]:
    """Read the crawler's raw JSON as source candidates, never as verified POIs."""
    document = json.loads(path.read_text(encoding="utf-8"))
    source_rows = document.get("places") if isinstance(document, dict) else document
    if not isinstance(source_rows, list):
        raise ValueError("JSON input must be an array or an object with a 'places' array.")
    records: list[tuple[dict, int]] = []
    for source_row, source_record in enumerate(source_rows, start=1):
        if not isinstance(source_record, dict):
            continue
        record = dict(source_record)
        record["ext_id"] = str(record.get("ext_id") or record.get("osm_id") or "").strip()
        raw_tags = record.get("tags")
        if isinstance(raw_tags, dict):
            record["tags"] = [f"{key}={value}" for key, value in sorted(raw_tags.items())]
        records.append((record, source_row))
    if not records:
        raise ValueError("No place rows were found in the JSON input.")
    return records, len(records)


def _normalize_poi_record(record: dict, sheet_name: str) -> dict:
    output = dict(record)
    if sheet_name == "Verified_District1":
        output.update({
            "ext_id": record.get("poi_key"),
            "kind": record.get("category"),
            "lat": record.get("latitude"),
            "lon": record.get("longitude"),
            "address": record.get("full_address"),
            "source": record.get("source_url"),
            "verified": str(record.get("verification_status") or "").strip().lower() == "verified",
        })
    else:
        output["ext_id"] = record.get("ext_id") or record.get("poi_key")
        output["kind"] = record.get("kind") or record.get("category")
        output["lat"] = record.get("lat", record.get("latitude"))
        output["lon"] = record.get("lon", record.get("longitude"))
        output["address"] = record.get("address") or record.get("full_address")
        output["source"] = record.get("source") or record.get("source_url")
    return output


def _coerce_record(record: dict) -> dict:
    output = dict(record)
    for field in ("lat", "lon"):
        raw = record.get(field)
        output[field] = float(raw) if raw not in (None, "") else None
    raw_price = record.get("price_vnd")
    output["price_vnd"] = int(float(raw_price)) if raw_price not in (None, "") else None
    for field in ("outdoor", "verified"):
        raw = record.get(field)
        output[field] = None if raw in (None, "") else str(raw).strip().lower() in {"1", "true", "yes"}
    raw_hours = record.get("open_hours") or record.get("opening_hours")
    output["open_hours"] = json.loads(raw_hours) if isinstance(raw_hours, str) and raw_hours else raw_hours
    raw_tags = record.get("tags")
    if isinstance(raw_tags, list):
        output["tags"] = raw_tags
    elif isinstance(raw_tags, str):
        try:
            parsed_tags = json.loads(raw_tags) if raw_tags.lstrip().startswith("[") else None
        except json.JSONDecodeError:
            parsed_tags = None
        output["tags"] = parsed_tags if isinstance(parsed_tags, list) else [item.strip() for item in raw_tags.split(",") if item.strip()]
    else:
        output["tags"] = []
    return output


def _is_missing(value: object) -> bool:
    if value is None or value == [] or value == {}:
        return True
    return str(value).strip().lower() in {"", "none", "null", "nan", "unknown", "n/a"}


def _source_url(record: dict) -> str:
    return str(record.get("source_url") or record.get("source") or "").strip()


def _covered_fields(record: dict) -> set[str]:
    raw = record.get("fields_covered")
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw) if raw.lstrip().startswith("[") else None
        except json.JSONDecodeError:
            parsed = None
        values = parsed if isinstance(parsed, list) else raw.split(",")
    else:
        values = []
    aliases = {"full_address": "address", "lat": "latitude", "lon": "longitude"}
    fields = {aliases.get(str(item).strip(), str(item).strip()) for item in values if str(item).strip()}
    if "coordinates" in fields:
        fields.update({"latitude", "longitude"})
    return fields


def _aware_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif not _is_missing(value):
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def candidate_flags(record: dict, reused_coordinates: set[tuple[float, float]]) -> list[str]:
    flags = []
    source_url = urlparse(_source_url(record))
    if source_url.scheme not in {"http", "https"} or not source_url.netloc or source_url.username or source_url.password:
        flags.append("source_url_missing")
    elif source_url.scheme != "https":
        flags.append("source_url_insecure")
    address_value = record.get("address") or record.get("full_address")
    address = "" if _is_missing(address_value) else str(address_value).strip()
    address_status = str(record.get("address_status") or "").strip().lower()
    if not address:
        flags.append("address_missing")
    elif address_status.startswith("reverse_geocoded"):
        flags.append("address_geocode_needs_confirmation")
    hours = record.get("open_hours") or record.get("opening_hours")
    if not hours:
        flags.append("opening_hours_missing")
    price_basis = str(record.get("price_basis") or "").strip().lower()
    if record.get("price_vnd") is not None and price_basis not in {"per_person", "per_group", "free"}:
        flags.append("price_basis_missing")
    price_status = str(record.get("price_status") or "").strip().lower()
    if record.get("price_vnd") is not None and price_status not in {"verified_source", "reviewed_current_source"}:
        flags.append("price_amount_unverified")
    if _is_missing(record.get("photo_url")):
        flags.append("photo_missing")
    elif _is_missing(record.get("photo_license")) and _is_missing(record.get("photo_license_url")):
        flags.append("photo_rights_review_pending")
    lat, lon = record.get("lat"), record.get("lon")
    if lat is None or lon is None:
        flags.append("coordinates_missing")
    elif (lat, lon) in reused_coordinates:
        flags.append("coordinates_reused")
    if _is_missing(record.get("source_type")):
        flags.append("source_type_missing")
    if _is_missing(record.get("license")):
        flags.append("source_license_missing")
    flags.append("source_license_review_pending")
    if _is_missing(record.get("observed_at")):
        flags.append("observed_at_missing")
    if _is_missing(record.get("expires_at")):
        flags.append("expires_at_missing")
    observed_at = _aware_datetime(record.get("observed_at"))
    expires_at = _aware_datetime(record.get("expires_at"))
    now = datetime.now(timezone.utc)
    if not _is_missing(record.get("observed_at")) and observed_at is None:
        flags.append("observed_at_invalid_or_timezone_missing")
    elif observed_at and observed_at > now:
        flags.append("observed_at_in_future")
    if not _is_missing(record.get("expires_at")) and expires_at is None:
        flags.append("expires_at_invalid_or_timezone_missing")
    elif expires_at and expires_at <= now:
        flags.append("evidence_expired")
    if observed_at and expires_at and expires_at <= observed_at:
        flags.append("evidence_expiry_before_observation")
    if not REQUIRED_POI_FIELDS.issubset(_covered_fields(record)):
        flags.append("field_coverage_incomplete")
    if record.get("verified"):
        flags.append("verified_claim_pending_review")
    if record.get("verified") and ("source_url_missing" in flags or "observed_at_missing" in flags):
        flags.append("verified_flag_unsubstantiated")
    flags.append("field_level_evidence_pending")
    return sorted(set(flags))


REQUIRED_POI_FIELDS = {"name", "address", "latitude", "longitude", "category"}


def make_quality_summary(records: list[tuple[dict, int]], reused_coordinates: set[tuple[float, float]]) -> dict:
    source_rows = [record for record, _ in records]
    def count(predicate) -> int:
        return sum(1 for record in source_rows if predicate(record))

    return {
        "records": len(records),
        "by_kind": dict(Counter(record.get("kind") or "unknown" for record in source_rows)),
        "by_source": dict(Counter(_source_url(record) or "unknown" for record in source_rows)),
        "source_verified_true": sum(bool(record.get("verified")) for record in source_rows),
        "source_url_missing": count(lambda record: "source_url_missing" in candidate_flags(record, reused_coordinates)),
        "source_url_insecure": count(lambda record: "source_url_insecure" in candidate_flags(record, reused_coordinates)),
        "source_type_missing": count(lambda record: _is_missing(record.get("source_type"))),
        "source_license_missing": count(lambda record: _is_missing(record.get("license"))),
        "source_license_review_pending": len(source_rows),
        "observed_at_missing": count(lambda record: _is_missing(record.get("observed_at"))),
        "expires_at_missing": count(lambda record: _is_missing(record.get("expires_at"))),
        "observed_at_invalid_or_timezone_missing": count(
            lambda record: not _is_missing(record.get("observed_at")) and _aware_datetime(record.get("observed_at")) is None
        ),
        "observed_at_in_future": count(
            lambda record: _aware_datetime(record.get("observed_at")) is not None
            and _aware_datetime(record.get("observed_at")) > datetime.now(timezone.utc)
        ),
        "expires_at_invalid_or_timezone_missing": count(
            lambda record: not _is_missing(record.get("expires_at")) and _aware_datetime(record.get("expires_at")) is None
        ),
        "evidence_expired": count(
            lambda record: _aware_datetime(record.get("expires_at")) is not None
            and _aware_datetime(record.get("expires_at")) <= datetime.now(timezone.utc)
        ),
        "evidence_expiry_before_observation": count(
            lambda record: _aware_datetime(record.get("observed_at")) is not None
            and _aware_datetime(record.get("expires_at")) is not None
            and _aware_datetime(record.get("expires_at")) <= _aware_datetime(record.get("observed_at"))
        ),
        "verified_flag_unsubstantiated": sum(
            bool(record.get("verified"))
            and ("source_url_missing" in candidate_flags(record, reused_coordinates)
                 or _is_missing(record.get("observed_at")))
            for record in source_rows
        ),
        "verified_claim_pending_review": sum(bool(record.get("verified")) for record in source_rows),
        "field_level_evidence_pending": len(source_rows),
        "field_coverage_incomplete": count(lambda record: not REQUIRED_POI_FIELDS.issubset(_covered_fields(record))),
        "address_missing": count(lambda record: _is_missing(record.get("address") or record.get("full_address"))),
        "address_geocode_needs_confirmation": sum(
            not _is_missing(record.get("address") or record.get("full_address"))
            and str(record.get("address_status") or "").strip().lower().startswith("reverse_geocoded")
            for record in source_rows
        ),
        "opening_hours_missing": count(lambda record: not (record.get("open_hours") or record.get("opening_hours"))),
        "price_basis_missing": sum(
            record.get("price_vnd") is not None
            and str(record.get("price_basis") or "").strip().lower() not in {"per_person", "per_group", "free"}
            for record in source_rows
        ),
        "price_amount_unverified": sum(
            record.get("price_vnd") is not None
            and str(record.get("price_status") or "").strip().lower() not in {"verified_source", "reviewed_current_source"}
            for record in source_rows
        ),
        "coordinates_reused": sum(
            record.get("lat") is not None and record.get("lon") is not None
            and (record["lat"], record["lon"]) in reused_coordinates
            for record in source_rows
        ),
        "photos_missing": count(lambda record: _is_missing(record.get("photo_url"))),
        "photo_rights_review_pending": count(
            lambda record: not _is_missing(record.get("photo_url"))
            and _is_missing(record.get("photo_license"))
            and _is_missing(record.get("photo_license_url"))
        ),
        "all_records_status": "needs_enrichment",
    }


def stage(path: Path, sheet_name: str, dry_run: bool = False) -> dict:
    digest_input = path.read_bytes()
    if path.suffix.lower() != ".json":
        digest_input += b"\0" + sheet_name.encode("utf-8")
    digest = hashlib.sha256(digest_input).hexdigest()
    records, _ = read_json_places(path) if path.suffix.lower() == ".json" else read_xlsx_sheet(path, sheet_name)
    if not records:
        raise ValueError("No place rows were found in the worksheet.")
    external_ids = [str(record.get("ext_id") or "").strip() for record, _ in records]
    if any(not value for value in external_ids):
        raise ValueError("Every candidate must have an ext_id.")
    if len(external_ids) != len(set(external_ids)):
        raise ValueError("Duplicate ext_id values exist in the worksheet; import stopped.")
    if any(not str(record.get("name") or "").strip() for record, _ in records):
        raise ValueError("Every candidate must have a name.")
    coordinates = Counter(
        (record.get("lat"), record.get("lon")) for record, _ in records
        if record.get("lat") is not None and record.get("lon") is not None
    )
    reused_coordinates = {coordinate for coordinate, count in coordinates.items() if count > 1}
    summary = make_quality_summary(records, reused_coordinates)
    if dry_run:
        return {"source_sha256": digest, "source_name": path.name, "worksheet_name": sheet_name, **summary, "dry_run": True}

    with SessionLocal() as db:
        existing = db.scalar(select(PlaceImportBatch).where(PlaceImportBatch.source_sha256 == digest))
        if existing is not None:
            return {"batch_id": existing.id, "source_sha256": digest, "source_name": existing.source_name,
                    "record_count": existing.record_count, "already_imported": True}
        actor = db.scalar(select(User).where(User.role == "admin").order_by(User.email).limit(1))
        batch = PlaceImportBatch(
            source_name=path.name,
            source_sha256=digest,
            worksheet_name=sheet_name,
            imported_by=actor.id if actor else None,
            record_count=len(records),
            quality_summary=summary,
        )
        db.add(batch)
        db.flush()
        for (record, source_row), external_id in zip(records, external_ids):
            flags = candidate_flags(record, reused_coordinates)
            db.add(PlaceImportCandidate(
                batch_id=batch.id,
                external_id=external_id,
                source_row=source_row,
                name=str(record["name"]).strip()[:180],
                kind=str(record.get("kind") or "unknown")[:80],
                raw_payload=record,
                quality_flags=flags,
                review_status="needs_enrichment",
            ))
        db.add(AuditLog(
            actor_id=actor.id if actor else None,
            action="place_import.staged",
            target_type="place_import_batch",
            target_id=batch.id,
            details=summary,
        ))
        db.commit()
        return {"batch_id": batch.id, "source_sha256": digest, "source_name": path.name,
                "record_count": batch.record_count, "already_imported": False, **summary}


def main() -> None:
    parser = argparse.ArgumentParser(description="Import XLSX or crawled JSON places into the admin-only enrichment queue.")
    parser.add_argument("--source", type=Path, default=ROOT / "data" / "raw" / "Sai_Gon_Places.xlsx")
    parser.add_argument("--worksheet", default="Sai_Gon", help="Worksheet name for XLSX only; JSON ignores this option.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error(f"Workbook not found: {args.source}")
    result = stage(args.source, args.worksheet, args.dry_run)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
