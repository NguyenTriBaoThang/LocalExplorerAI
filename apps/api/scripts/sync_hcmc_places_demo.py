"""Add the project's HCMC candidates and non-bookable Explore discovery cards.

Candidate names and coordinates remain simulated/unverified. No price, venue
hours, photos, duration, or booking slots are copied into operational fields.
The script is local-development only and is safe to rerun.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from app.core.config import settings
from app.core.enums import VerificationStatus
from app.db.session import SessionLocal
from app.models.entities import Experience, POI, Provider
from app.services.pilot_area import is_pilot_location

SOURCE = Path(__file__).resolve().parents[3] / "data" / "sai_gon_places.json"
PHOTO_MANIFEST = Path(__file__).resolve().parents[3] / "data" / "raw" / "district1_osm_photos_manifest.json"
HCMC_PHOTO_MANIFEST = Path(__file__).resolve().parents[3] / "data" / "raw" / "hcmc_commons_photo_manifest.json"
SOURCE_LABEL = "Dữ liệu địa điểm TP.HCM trong dự án; các trường nguồn chưa được duyệt để vận hành."
CATEGORY_BY_KIND = {
    "tham-quan": "culture",
    "an-uong": "food",
    "cafe": "food",
    "giai-tri": "relaxation",
    "cho-o": "accommodation",
}


def stable_id(source_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"localexplorer-hcmc-candidate:{source_id}"))


def candidate_tags(category: str) -> list[str]:
    return [category, "hcmc_catalog_candidate"]


def load_licensed_photos_by_name() -> dict[str, list[dict]]:
    photos_by_name: dict[str, list[dict]] = {}
    project_root = Path(__file__).resolve().parents[3]
    for manifest_path in (PHOTO_MANIFEST, HCMC_PHOTO_MANIFEST):
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for photo in manifest.get("entries", []):
            local_path = photo.get("local_path")
            if not (
                photo.get("name") and photo.get("source_url") and photo.get("license")
                and photo.get("license_url") and local_path
                and (project_root / local_path).is_file()
            ):
                continue
            key = normalize(str(photo["name"]))
            photos_by_name.setdefault(key, []).append({
                "url": photo.get("remote_url"),
                "local_url": photo.get("local_url"),
                "source_url": photo["source_url"],
                "title": photo.get("title") or photo["name"],
                "license": photo["license"],
                "license_url": photo["license_url"],
                "attribution": photo.get("attribution"),
                "credit_line": photo.get("credit_line"),
            })
    return photos_by_name


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).replace("đ", "d")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def load_source() -> list[dict]:
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"Expected a non-empty JSON array in {SOURCE}")
    for row in rows:
        if not row.get("id") or not row.get("name") or not row.get("source"):
            raise RuntimeError("Every source row must have an id, name, and source URL.")
        latitude, longitude = row.get("lat"), row.get("lon")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise RuntimeError(f"Missing coordinates for source record {row['id']}")
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise RuntimeError(f"Invalid coordinates for source record {row['id']}")
    return rows


def sync() -> tuple[int, int, int, int, int]:
    if settings.app_env.lower() not in {"development", "dev", "local"} or settings.real_data_only:
        raise RuntimeError("Refusing to sync unverified place candidates outside local development.")

    rows = load_source()
    licensed_photos = load_licensed_photos_by_name()
    added = updated = added_experiences = updated_experiences = hidden_demo_pois = 0
    with SessionLocal() as db:
        provider_id = stable_id("provider")
        provider = db.get(Provider, provider_id)
        if provider is None:
            provider = Provider(
                id=provider_id,
                name="Local Explorer HCMC candidate catalog (SIMULATED)",
                slug="local-explorer-hcmc-candidate-catalog",
                description="Local-only simulated discovery entries; not bookable.",
                address="TP. Hồ Chí Minh · dữ liệu ứng viên",
                status="simulated",
                verification_status="mock",
            )
            db.add(provider)
            db.flush()

        existing_by_name = {
            normalize(poi.name): poi
            for poi in db.scalars(select(POI)).all()
            if (poi.details or {}).get("catalog_mode") == "source_attributed_demo"
        }

        for row in rows:
            poi_id = stable_id(str(row["id"]))
            latitude, longitude = float(row["lat"]), float(row["lon"])
            category = CATEGORY_BY_KIND.get(str(row.get("kind") or "").casefold(), "culture")
            source_candidate = {
                "source_id": row["id"],
                "source_url": row["source"],
                "source_claimed_verified": bool(row.get("verified")),
                "coordinate_status": "reverse_geocoded_needs_POI_confirmation",
                "address_status": "source_file_value_unverified",
                "opening_hours_status": "source_file_value_unverified",
                "price_status": "source_file_value_unverified",
                "source_fields": {
                    "kind": row.get("kind"),
                    "tags": row.get("tags"),
                    "description": row.get("description"),
                    "address": row.get("address"),
                    "open_hours": row.get("open_hours"),
                    "price_vnd": row.get("price_vnd"),
                    "outdoor": row.get("outdoor"),
                    "note": row.get("note"),
                },
            }
            details = {
                "catalog_mode": "hcmc_catalog_candidate",
                "source_dataset": str(SOURCE).replace("\\", "/"),
                "source_candidate": source_candidate,
                "images": licensed_photos.get(normalize(str(row["name"])), []),
                "photo_status": "licensed_exact_name_match" if licensed_photos.get(normalize(str(row["name"]))) else "no_licensed_exact_name_match",
                "review_status": "needs_field_level_verification",
                "demo_notice": "Ứng viên địa điểm chỉ hiển thị trong bản local. Tọa độ, địa chỉ, giờ mở cửa và giá chưa được xác minh; không phải thông tin đặt chỗ.",
            }

            # Reuse the better-enriched records added in the previous step
            # instead of creating duplicate museum/landmark cards.
            if normalize(row["name"]) in existing_by_name:
                continue
            poi = existing_by_name.get(normalize(row["name"])) or db.get(POI, poi_id)
            if poi is None:
                poi = POI(
                    id=poi_id,
                    name=str(row["name"])[:180],
                    description=(
                        "Ứng viên trong bộ dữ liệu địa điểm TP.HCM. "
                        "Tọa độ và thông tin mô tả chưa được xác minh độc lập; "
                        "đang hiển thị để rà soát trong môi trường local."
                    ),
                    district="TP. Hồ Chí Minh · ứng viên",
                    latitude=latitude,
                    longitude=longitude,
                    geom=WKTElement(f"POINT({longitude} {latitude})", srid=4326),
                    category=category,
                    address=str(row.get("address") or "Địa chỉ ứng viên · cần xác minh")[:300],
                    source_attribution=f"{SOURCE_LABEL} Nguồn bản ghi: {row['source']}",
                    is_in_pilot_polygon=is_pilot_location(latitude, longitude),
                    image_urls=[photo["local_url"] for photo in details["images"] if photo.get("local_url")],
                    details=details,
                    verification_status=VerificationStatus.SIMULATED.value,
                )
                db.add(poi)
                added += 1
            else:
                poi.name = str(row["name"])[:180]
                poi.description = "Ứng viên địa điểm TP.HCM; tọa độ và mô tả chưa được xác minh độc lập."
                poi.district = "TP. Hồ Chí Minh · ứng viên"
                poi.latitude, poi.longitude = latitude, longitude
                poi.geom = WKTElement(f"POINT({longitude} {latitude})", srid=4326)
                poi.category = category
                poi.address = str(row.get("address") or "Địa chỉ ứng viên · cần xác minh")[:300]
                poi.source_attribution = f"{SOURCE_LABEL} Nguồn bản ghi: {row['source']}"
                poi.is_in_pilot_polygon = is_pilot_location(latitude, longitude)
                poi.image_urls = [photo["local_url"] for photo in details["images"] if photo.get("local_url")]
                poi.details = details
                poi.verification_status = VerificationStatus.SIMULATED.value
                updated += 1

            # Give Explore a non-bookable discovery card for each catalog
            # candidate. Do not copy source price, hours, description, or
            # availability into operational fields; the UI labels these as
            # unverified and shows no visit duration or time slot.
            experience_id = stable_id(f"discovery:{row['id']}")
            experience = db.get(Experience, experience_id)
            tags = candidate_tags(category)
            title = f"Khám phá địa điểm: {poi.name}"
            copy = (
                "Thông tin tham khảo từ danh mục địa điểm TP.HCM trong dự án. "
                "Hãy kiểm tra độc lập vị trí, giờ mở cửa và giá trước khi đi. "
                "Đây không phải hoạt động có khung giờ hoặc đặt chỗ."
            )
            if experience is None:
                experience = Experience(
                    id=experience_id,
                    poi_id=poi.id,
                    provider_id=provider_id,
                    name=title[:180],
                    title=title[:180],
                    description=copy,
                    intent_tags=tags,
                    is_hands_on=False,
                    is_indoor=not bool(row.get("outdoor")),
                    indoor=not bool(row.get("outdoor")),
                    primary_intent=category,
                    weather_sensitivity="unknown",
                    duration_min=0,
                    price_vnd=0,
                    verification_status=VerificationStatus.SIMULATED.value,
                )
                db.add(experience)
                added_experiences += 1
            else:
                experience.poi_id = poi.id
                experience.provider_id = provider_id
                experience.name = title[:180]
                experience.title = title[:180]
                experience.description = copy
                experience.intent_tags = tags
                experience.primary_intent = category
                experience.duration_min = 0
                experience.price_vnd = 0
                experience.verification_status = VerificationStatus.SIMULATED.value
                updated_experiences += 1

        # Hide only the ten fictional fixtures generated by seed_db.py. Keep
        # their rows and relationships intact in case local user data refers
        # to them; unverified rows are excluded from the public catalog.
        for poi in db.scalars(select(POI).where(POI.name.like("Điểm demo %"))).all():
            if poi.verification_status == VerificationStatus.SIMULATED.value:
                poi.verification_status = VerificationStatus.UNVERIFIED.value
                hidden_demo_pois += 1
                for experience in db.scalars(select(Experience).where(Experience.poi_id == poi.id)).all():
                    if experience.verification_status == VerificationStatus.SIMULATED.value:
                        experience.verification_status = VerificationStatus.UNVERIFIED.value

        db.commit()
    return added, updated, hidden_demo_pois, added_experiences, updated_experiences


if __name__ == "__main__":
    added, updated, hidden, added_experiences, updated_experiences = sync()
    print(f"Added {added} HCMC place candidates; refreshed {updated}; hid {hidden} fictional demo POIs.")
    print(f"Added {added_experiences} and refreshed {updated_experiences} non-bookable Explore discovery cards; no prices, visit durations, or time slots were generated.")
