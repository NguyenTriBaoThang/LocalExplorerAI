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

from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from app.core.enums import PriceBasis, SlotStatus, VerificationStatus
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.entities import Experience, ExperienceSlot, POI, Provider, User

HCMC = ZoneInfo("Asia/Ho_Chi_Minh")


def seed_saigon_places(session_factory=SessionLocal, json_path: str | Path | None = None) -> int:
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

        for item in places_data:
            poi_id = str(item.get("id") or item.get("name"))
            existing_poi = db.scalar(select(POI).where(POI.id == poi_id))
            if existing_poi:
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
                verification_status=VerificationStatus.VERIFIED.value
            )
            db.add(poi)
            db.flush()

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
                verification_status=VerificationStatus.VERIFIED.value
            )
            db.add(exp)
            db.flush()

            # Seed 7 days of open slots for planning
            for day_offset in range(7):
                service_date = today + timedelta(days=day_offset)
                for slot_time in daily_times:
                    start = datetime.combine(service_date, slot_time, HCMC)
                    end = start + timedelta(minutes=90)
                    slot = ExperienceSlot(
                        experience_id=exp.id,
                        start_at=start,
                        end_at=end,
                        capacity_total=20,
                        available_reported=15,
                        status=SlotStatus.OPEN.value,
                        confirmed_at=datetime.now(timezone.utc),
                        expires_at=start - timedelta(minutes=15)
                    )
                    db.add(slot)

            inserted_count += 1

        db.commit()
        print(f"Seeded {inserted_count} real Saigon places and experience slots into database.")
        return inserted_count


if __name__ == "__main__":
    seed_saigon_places()
