"""Export an allowlisted catalog or import it without replacing existing records."""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from geoalchemy2.elements import WKTElement
from sqlalchemy import DateTime, select
from sqlalchemy.orm import Session

from app.models.entities import POI, Experience, ExperienceSlot, Provider, LandmarkStory
from app.models.trip_entities import TripDestination, TripPlace

# Explicit fields: future schema additions must not silently enter a public export.
SPEC = {
    "providers": (Provider, "id name slug description address website".split()),
    "pois": (POI, "id name description district latitude longitude category address source_attribution is_in_pilot_polygon image_urls opening_hours ticket_info tags is_landmark source_url details verification_status data_revision".split()),
    "experiences": (Experience, "id poi_id provider_id name title description intent_tags is_hands_on is_indoor primary_intent weather_sensitivity duration_min price_basis price_vnd verification_status data_revision indoor".split()),
    "experience_slots": (ExperienceSlot, "id experience_id start_at end_at capacity_total available_reported confirmed_at expires_at status version".split()),
    "trip_destinations": (TripDestination, "slug name lat lon hubs".split()),
    "trip_places": (TripPlace, "ext_id destination name kind lat lon price open_hours outdoor tags raw_tags description address photo_url source".split()),
    "landmark_stories": (LandmarkStory, "model_id published revision workflow published_at".split()),
}
KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_-]{30,}|msy_[0-9A-Za-z]{20,}|gh[pousr]_[0-9A-Za-z]{20,}|-----BEGIN .*PRIVATE KEY-----")


def export_catalog(engine):
    tables = {}
    with Session(engine) as db:
        for name, (model, fields) in SPEC.items():
            records = []
            for obj in db.scalars(select(model)):
                if name == "landmark_stories" and not obj.published:
                    continue
                row = {field: getattr(obj, field) for field in fields}
                if name == "experience_slots":
                    # Historical reference only: do not restore bookable inventory.
                    row.update(status="tentative", available_reported=0, confirmed_at=None, expires_at=None)
                records.append(row)
            tables[name] = sorted(records, key=lambda r: str(r.get("id", r.get("ext_id", r.get("slug", r.get("model_id"))))))
    data = {"format": 1, "purpose": "catalog-reference-not-operational-inventory", "tables": tables}
    encoded = json.dumps(data, ensure_ascii=False, default=lambda x: x.isoformat(), indent=2)
    if KEY_PATTERN.search(encoded):
        raise ValueError("Secret-like value detected in catalog; review before export")
    return encoded + "\n"


def import_catalog(engine, data):
    if data.get("format") != 1 or set(data["tables"]) != set(SPEC):
        raise ValueError("Unsupported catalog format or table set")
    counts = {}
    with Session(engine) as db, db.begin():
        for name, (model, fields) in SPEC.items():
            added = 0
            for original in data["tables"][name]:
                if set(original) - set(fields):
                    raise ValueError(f"Unexpected fields in {name}")
                row = dict(original)
                key = "ext_id" if name == "trip_places" else ("slug" if name == "trip_destinations" else "model_id" if name == "landmark_stories" else "id")
                if db.scalar(select(model).where(getattr(model, key) == row[key])) is not None:
                    continue
                for col in model.__table__.columns:
                    if (isinstance(col.type, DateTime) or col.name.endswith("_at")) and isinstance(row.get(col.name), str):
                        row[col.name] = datetime.fromisoformat(row[col.name])
                if name == "providers":
                    row.update(verification_status="pending", is_active=False, status="inactive")
                elif name == "pois":
                    row["geom"] = WKTElement(f"POINT({row['longitude']} {row['latitude']})", srid=4326)
                    if row.get("verification_status") not in {"simulated", "unverified"}:
                        row["verification_status"] = "unverified"
                elif name == "experiences":
                    if row.get("verification_status") not in {"simulated", "unverified"}:
                        row["verification_status"] = "unverified"
                elif name == "experience_slots":
                    row.update(status="tentative", available_reported=0, confirmed_at=None, expires_at=None)
                elif name == "landmark_stories":
                    row["draft"] = row["published"]
                db.add(model(**row))
                db.flush()
                added += 1
            counts[name] = added
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "import"])
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    from app.db.session import engine
    if args.action == "export":
        args.file.parent.mkdir(parents=True, exist_ok=True)
        with args.file.open("x", encoding="utf-8") as stream:
            stream.write(export_catalog(engine))
        print("Catalog exported. Review public content before committing.")
    else:
        print(json.dumps(import_catalog(engine, json.loads(args.file.read_text(encoding="utf-8")))))


if __name__ == "__main__":
    main()
