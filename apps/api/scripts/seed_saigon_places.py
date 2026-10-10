import json
import os
import sys
from pathlib import Path
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

# Ensure app package is importable
current_dir = Path(__file__).resolve().parent
api_dir = current_dir.parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from uuid import uuid4
from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from app.core.enums import PriceBasis, SlotStatus, VerificationStatus
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.entities import Evidence, Experience, ExperienceSlot, POI, Provider, User
from app.services.evidence_service import REQUIRED_FIELDS

HCMC = ZoneInfo("Asia/Ho_Chi_Minh")


def seed_saigon_places(session_factory=SessionLocal, json_path: str | Path | None = None) -> int:
    raise RuntimeError(
        "Operational seeding is disabled: this legacy loader inferred addresses, prices, "
        "experiences, slots, and evidence. Import the workbook through "
        "scripts/import_place_candidates.py and promote records only after source review."
    )
    # Ensure tables exist
    try:
        with session_factory() as db:
            Base.metadata.create_all(bind=db.get_bind())
    except Exception as e:
        print(f"Notice: Table initialization check: {e}")

    if json_path is None:
        candidates = [
            Path("data/sai_gon_places.json"),
            Path("../data/sai_gon_places.json"),
            Path("../../data/sai_gon_places.json"),
            Path("D:/MyProject/MLAI_DA/data/sai_gon_places.json")
        ]
        for c in candidates:
            if c.exists():
                json_path = c
                break

    if not json_path or not Path(json_path).exists():
        print(f"Error: Places file not found at {json_path}")
        return 0

    with open(json_path, "r", encoding="utf-8") as f:
        places_data = json.load(f)

    with session_factory() as db:
        # Check or create Saigon provider
        provider = db.scalar(select(Provider).where(Provider.slug == "saigon-heritage-partner"))
        if not provider:
            provider = Provider(
                name="Sài Gòn Heritage & Local Partners",
                slug="saigon-heritage-partner",
                description="Mạng lưới điểm đến văn hoá, ẩm thực, trải nghiệm thực tế TP. Hồ Chí Minh.",
                address="TP. Hồ Chí Minh, Việt Nam",
                status="active",
                verification_status="verified"
            )
            db.add(provider)
            db.flush()

        inserted_count = 0
        today = datetime.now(HCMC).date()
        daily_times = [time(9, 0), time(14, 0), time(18, 30)]
        now_utc = datetime.now(timezone.utc)

        def _ensure_slots(exp: Experience, days: int = 30):
            for day_offset in range(days):
                service_date = today + timedelta(days=day_offset)
                for slot_time in daily_times:
                    start = datetime.combine(service_date, slot_time, HCMC)
                    existing_slot = db.scalar(
                        select(ExperienceSlot).where(
                            ExperienceSlot.experience_id == exp.id,
                            ExperienceSlot.start_at == start,
                        )
                    )
                    if existing_slot:
                        continue

                    end = start + timedelta(minutes=90)
                    slot_expires = end if end.tzinfo else end.replace(tzinfo=timezone.utc) + timedelta(days=30)
                    slot = ExperienceSlot(
                        experience_id=exp.id,
                        start_at=start,
                        end_at=end,
                        capacity_total=20,
                        available_reported=15,
                        status=SlotStatus.OPEN.value,
                        confirmed_at=now_utc - timedelta(hours=1),
                        expires_at=slot_expires,
                        version=1,
                    )
                    db.add(slot)
                    db.flush()

                    db.add(Evidence(
                        id=str(uuid4()),
                        source_uri=f"https://hcmc.gov.vn/slots/{slot.id}",
                        source_type="provider_confirmation",
                        source_label="Sài Gòn Heritage & Local Partners",
                        license="Open Data",
                        notes="Open slot verified",
                        submitted_by=None,
                        target_type="slot",
                        target_id=slot.id,
                        target_revision=1,
                        fields_covered=sorted(REQUIRED_FIELDS["slot"]),
                        observed_at=now_utc - timedelta(hours=2),
                        valid_from=now_utc - timedelta(hours=2),
                        expires_at=slot_expires,
                        verification_status="verified",
                        verified_at=now_utc - timedelta(hours=1),
                    ))

        for item in places_data:
            poi_id = str(item.get("id") or item.get("name"))
            existing_poi = db.scalar(select(POI).where(POI.id == poi_id))
            if existing_poi:
                exp = db.scalar(select(Experience).where(Experience.poi_id == existing_poi.id))
                if exp:
                    _ensure_slots(exp, days=30)
                continue

            lat = float(item.get("lat") or 10.7769)
            lon = float(item.get("lon") or 106.7009)
            category = str(item.get("kind") or "culture")
            tags = item.get("tags") or [category]
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]
            price_vnd = int(item.get("price_vnd") or 0)
            is_outdoor = bool(item.get("outdoor", False))
            is_indoor = not is_outdoor
            name = str(item.get("name") or "Điểm đến Sài Gòn")
            desc = str(item.get("description") or f"Trải nghiệm khám phá {name}")

            poi = POI(
                id=poi_id,
                name=name,
                description=desc,
                district="Quận 1, TP.HCM",
                latitude=lat,
                longitude=lon,
                geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
                category=category,
                address=str(item.get("open_hours") or "TP. Hồ Chí Minh"),
                source_attribution=str(item.get("source") or "HK2T.HUTECH Local Explorer Dataset"),
                is_in_pilot_polygon=True,
                image_urls=[item.get("photo_url")] if item.get("photo_url") else [],
                verification_status=VerificationStatus.VERIFIED.value,
                data_revision=1
            )
            db.add(poi)
            db.flush()

            db.add(Evidence(
                id=str(uuid4()),
                source_uri=f"https://hcmc.gov.vn/places/{poi.id}",
                source_type="official_dataset",
                source_label=str(item.get("source") or "Sở Du Lịch TP. Hồ Chí Minh"),
                license="Open Data",
                notes=f"Verified real Saigon POI: {name}",
                submitted_by=None,
                target_type="poi",
                target_id=poi.id,
                target_revision=1,
                fields_covered=sorted(REQUIRED_FIELDS["poi"]),
                observed_at=now_utc - timedelta(days=1),
                valid_from=now_utc - timedelta(days=1),
                expires_at=now_utc + timedelta(days=365),
                verification_status="verified",
                verified_at=now_utc,
            ))

            exp = Experience(
                id=f"exp-{poi_id}",
                poi_id=poi.id,
                provider_id=provider.id,
                name=name,
                title=name,
                description=desc,
                intent_tags=tags,
                is_hands_on="hands_on" in tags or "workshop" in tags or "craft" in tags,
                is_indoor=is_indoor,
                primary_intent=category,
                duration_min=90,
                indoor=is_indoor,
                price_basis=PriceBasis.PER_PERSON.value,
                price_vnd=price_vnd,
                verification_status=VerificationStatus.VERIFIED.value,
                data_revision=1
            )
            db.add(exp)
            db.flush()

            db.add(Evidence(
                id=str(uuid4()),
                source_uri=f"https://hcmc.gov.vn/experiences/{exp.id}",
                source_type="official_dataset",
                source_label=str(item.get("source") or "Sở Du Lịch TP. Hồ Chí Minh"),
                license="Open Data",
                notes=f"Verified real Saigon Experience: {name}",
                submitted_by=None,
                target_type="experience",
                target_id=exp.id,
                target_revision=1,
                fields_covered=sorted(REQUIRED_FIELDS["experience"]),
                observed_at=now_utc - timedelta(days=1),
                valid_from=now_utc - timedelta(days=1),
                expires_at=now_utc + timedelta(days=365),
                verification_status="verified",
                verified_at=now_utc,
            ))

            # Seed 30 days of open slots for planning
            _ensure_slots(exp, days=30)
            inserted_count += 1

        db.commit()
        print(f"Seeded {inserted_count} real Saigon places and experience slots with verified evidence into database.")
        return inserted_count


if __name__ == "__main__":
    raise SystemExit(
        "Disabled: this legacy seeder would manufacture operational POI, experience, "
        "slot, and evidence values. Use scripts/import_place_candidates.py to stage source rows."
    )
