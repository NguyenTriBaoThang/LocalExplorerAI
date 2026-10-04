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

from app.db.session import SessionLocal
from app.models.entities import AuditLog, PlaceImportBatch, PlaceImportCandidate, User


ROOT = Path(__file__).resolve().parents[3]
EXPECTED_HEADERS = {
    "ext_id", "name", "kind", "lat", "lon", "price_vnd", "open_hours",
    "outdoor", "tags", "description", "photo_url", "verified", "source", "note",
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
    missing = sorted(EXPECTED_HEADERS - set(headers))
    if missing:
        raise ValueError(f"Worksheet is missing required source columns: {missing}")
    records = []
    for source_row, values in enumerate(rows[1:], start=2):
        record = {header: values[index] if index < len(values) else None for index, header in enumerate(headers) if header}
        if not any(value not in (None, "") for value in record.values()):
            continue
        records.append((_coerce_record(record), source_row))
    return records, len(rows)


def _coerce_record(record: dict[str, str | None]) -> dict:
    output = dict(record)
    for field in ("lat", "lon"):
        raw = record.get(field)
        output[field] = float(raw) if raw not in (None, "") else None
    raw_price = record.get("price_vnd")
    output["price_vnd"] = int(float(raw_price)) if raw_price not in (None, "") else None
    for field in ("outdoor", "verified"):
        output[field] = str(record.get(field) or "").strip().lower() in {"1", "true", "yes"}
    output["open_hours"] = json.loads(record["open_hours"]) if record.get("open_hours") else None
    output["tags"] = [item.strip() for item in (record.get("tags") or "").split(",") if item.strip()]
    return output


def candidate_flags(record: dict, reused_coordinates: set[tuple[float, float]]) -> list[str]:
    flags = []
    source = str(record.get("source") or "").strip()
    source_url = urlparse(source)
    if not source_url.scheme or not source_url.netloc:
        flags.append("source_url_missing")
    flags.append("address_missing")
    hours = record.get("open_hours")
    if not hours:
        flags.append("opening_hours_missing")
    if record.get("price_vnd") is not None:
        flags.append("price_basis_missing")
    if not record.get("photo_url"):
        flags.append("photo_missing")
    lat, lon = record.get("lat"), record.get("lon")
    if lat is None or lon is None:
        flags.append("coordinates_missing")
    elif (lat, lon) in reused_coordinates:
        flags.append("coordinates_reused")
    if record.get("verified") and ("source_url_missing" in flags or not record.get("observed_at")):
        flags.append("verified_flag_unsubstantiated")
    return flags


def make_quality_summary(records: list[tuple[dict, int]], reused_coordinates: set[tuple[float, float]]) -> dict:
    source_rows = [record for record, _ in records]
    return {
        "records": len(records),
        "by_kind": dict(Counter(record.get("kind") or "unknown" for record in source_rows)),
        "by_source": dict(Counter(record.get("source") or "unknown" for record in source_rows)),
        "source_verified_true": sum(bool(record.get("verified")) for record in source_rows),
        "source_url_missing": sum(not urlparse(str(record.get("source") or "")).netloc for record in source_rows),
        "address_missing": len(source_rows),
        "opening_hours_missing": sum(not record.get("open_hours") for record in source_rows),
        "price_basis_missing": sum(record.get("price_vnd") is not None for record in source_rows),
        "coordinates_reused": sum(
            record.get("lat") is not None and record.get("lon") is not None
            and (record["lat"], record["lon"]) in reused_coordinates
            for record in source_rows
        ),
        "photos_missing": sum(not record.get("photo_url") for record in source_rows),
        "all_records_status": "needs_enrichment",
    }


def stage(path: Path, sheet_name: str, dry_run: bool = False) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    records, _ = read_xlsx_sheet(path, sheet_name)
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
    parser = argparse.ArgumentParser(description="Import a place worksheet into the admin-only enrichment queue.")
    parser.add_argument("--source", type=Path, default=ROOT / "data" / "raw" / "Sai_Gon_Places.xlsx")
    parser.add_argument("--worksheet", default="Sai_Gon")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error(f"Workbook not found: {args.source}")
    result = stage(args.source, args.worksheet, args.dry_run)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
