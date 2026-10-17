"""Add source-attributed, non-bookable District 1 demo visits to local Explore.

This script creates simulated POIs, experiences, and slots. It intentionally
refuses production and REAL_DATA_ONLY configurations. The venue facts are
source-backed; the provider and slot availability are synthetic demo data.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from app.core.config import settings
from app.core.enums import PriceBasis, SlotStatus, VerificationStatus
from app.db.session import SessionLocal
from app.models.entities import Experience, ExperienceSlot, POI, Provider
from app.services.pilot_area import is_pilot_location

HCMC = ZoneInfo("Asia/Ho_Chi_Minh")
OSM_DATA = "data/raw/district1_osm_places.json"
OSM_COPYRIGHT = "© OpenStreetMap contributors (ODbL); venue facts checked against the listed official source."
SLOT_NOTICE = "Khung giờ và sức chứa là dữ liệu mô phỏng để xem giao diện; chưa được địa điểm xác nhận và không thể đặt chỗ thật."

# ext_id, official place name, public category, address fallback, fee, fee note,
# hours note, official information URL, duration, tags, indoor, open weekdays,
# visit windows, short guide text.
PLACES = [
    {
        "ext_id": "way/39598493", "name": "Dinh Độc Lập", "category": "culture",
        "address": "135 Nam Kỳ Khởi Nghĩa", "fee": 80000,
        "fee_note": "Vé người lớn tham quan tổng hợp; chính sách miễn/giảm khác không mô phỏng.",
        "hours": "Hằng ngày 07:00–18:00", "official": "https://dinhdoclap.gov.vn/gio-tham-quan/",
        "duration": 120, "tags": ["culture", "history", "architecture"], "indoor": True,
        "weekdays": set(range(7)), "windows": [(9, 0), (13, 0)],
        "guide": "Tự tham quan di tích và khu trưng bày. Giá tham khảo là vé người lớn; không bao gồm hướng dẫn viên hay dịch vụ khác.",
    },
    {
        "ext_id": "relation/17758150", "name": "Bảo tàng Lịch sử Thành phố Hồ Chí Minh", "category": "culture",
        "address": "2 Nguyễn Bỉnh Khiêm", "fee": 60000,
        "fee_note": "Phí tham quan 60.000 đồng/người/lượt theo thông báo áp dụng từ 01/10/2026.",
        "hours": "Thứ Ba–Chủ nhật 08:00–11:30, 13:00–17:00; đóng cửa thứ Hai", "official": "https://www.baotanglichsutphcm.com.vn/ban-tin/thong-bao-thay-doi-muc-phi-tham-quan-bao-tang",
        "duration": 90, "tags": ["culture", "history", "museum"], "indoor": True,
        "weekdays": {1, 2, 3, 4, 5, 6}, "windows": [(9, 0), (13, 30)],
        "guide": "Tự tham quan các bộ sưu tập lịch sử. Khung giờ mô phỏng chỉ nằm trong giờ mở cửa công bố.",
    },
    {
        "ext_id": "way/802105071", "name": "Bảo tàng Thành phố Hồ Chí Minh", "category": "culture",
        "address": "65 Lý Tự Trọng", "fee": 60000,
        "fee_note": "Phí tham quan 60.000 đồng/người/lượt, áp dụng từ 01/10/2026.",
        "hours": "Hằng ngày 08:00–17:00", "official": "https://hcmc-museum.edu.vn/luu-tru/5465",
        "duration": 90, "tags": ["culture", "history", "museum", "architecture"], "indoor": True,
        "weekdays": set(range(7)), "windows": [(9, 0), (13, 0)],
        "guide": "Tự khám phá các phòng trưng bày về lịch sử và đời sống thành phố. Giá là phí vào cửa tham khảo.",
    },
    {
        "ext_id": "way/802157425", "name": "Bảo tàng Mỹ thuật Thành phố Hồ Chí Minh", "category": "culture",
        "address": "97A Phó Đức Chính", "fee": 60000,
        "fee_note": "Phí tham quan bảo tàng do Sở Văn hóa và Thể thao quản lý, áp dụng từ 01/10/2026.",
        "hours": "Hằng ngày 08:00–17:00", "official": "https://ttbc-hcm.gov.vn/tp-hcm-mien-ve-tham-quan-bao-tang-cho-hoc-sinh-sinh-vien-tu-1-10-1022256.html",
        "duration": 90, "tags": ["culture", "art", "museum", "architecture"], "indoor": True,
        "weekdays": set(range(7)), "windows": [(9, 0), (13, 0)],
        "guide": "Tự tham quan các bộ sưu tập mỹ thuật và kiến trúc tòa nhà. Giá tham khảo theo mức phí mới của thành phố.",
    },
    {
        "ext_id": "way/39514795", "name": "Chợ Bến Thành", "category": "local_life",
        "address": "Công trường Quách Thị Trang", "fee": 0,
        "fee_note": "Vào khu chợ không thu vé; mua sắm và ăn uống phát sinh chi phí riêng.",
        "hours": "Khu chợ ban ngày; giờ từng gian hàng có thể khác nhau", "official": "https://visithcmc.vn/vi/tin-tuc/top-20-places-you-need-to-visit-in-ho-chi-minh-city",
        "duration": 75, "tags": ["local_life", "food", "shopping", "culture"], "indoor": True,
        "weekdays": set(range(7)), "windows": [(9, 0), (14, 0)],
        "guide": "Tự đi bộ tham quan khu chợ và quan sát sinh hoạt địa phương. Không bao gồm hàng hóa, đồ ăn hoặc dịch vụ mua tại chợ.",
    },
    {
        "ext_id": "way/39514793", "name": "Bưu điện Trung tâm Sài Gòn", "category": "culture",
        "address": "2 Công trường Công xã Paris", "fee": 0,
        "fee_note": "Tham quan không gian công cộng không thu vé; dịch vụ bưu chính phát sinh phí riêng.",
        "hours": "Thông tin du lịch thành phố công bố 07:30–18:00; có thể thay đổi theo hoạt động tại điểm", "official": "https://visithcmc.vn/vi/tin-tuc/top-20-places-you-need-to-visit-in-ho-chi-minh-city",
        "duration": 45, "tags": ["culture", "architecture", "history"], "indoor": True,
        "weekdays": set(range(7)), "windows": [(9, 0), (14, 0)],
        "guide": "Tự tham quan kiến trúc và không gian công cộng. Cần tôn trọng hoạt động bưu chính đang diễn ra.",
    },
    {
        "ext_id": "way/500888743", "name": "Công viên Tao Đàn", "category": "nature",
        "address": "Trương Định, Quận 1", "fee": 0,
        "fee_note": "Vào công viên miễn phí; sự kiện hoặc dịch vụ riêng có thể thu phí.",
        "hours": "Hằng ngày 07:00–22:00", "official": "https://visithcmc.vn/vi/tin-tuc/kham-pha-cong-vien-tao-dan-oc-dao-xanh-giua-long-thanh-pho",
        "duration": 60, "tags": ["nature", "relaxation", "local_life"], "indoor": False,
        "weekdays": set(range(7)), "windows": [(8, 0), (16, 0)],
        "guide": "Tự đi bộ thư giãn và quan sát mảng xanh đô thị. Không bao gồm dịch vụ hoặc sự kiện riêng.",
    },
]


def stable_id(key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"localexplorer-d1-demo:{key}"))


def load_osm_places() -> dict[str, dict]:
    import json
    from pathlib import Path

    rows = json.loads(Path(OSM_DATA).read_text(encoding="utf-8"))["places"]
    return {row["ext_id"]: row for row in rows}


def seed() -> tuple[int, int, int]:
    if settings.app_env.lower() not in {"development", "dev", "local"} or settings.real_data_only:
        raise RuntimeError("Refusing to seed demo places outside local development or while REAL_DATA_ONLY is enabled.")

    osm_places = load_osm_places()
    provider_id = stable_id("provider")
    added_pois = added_experiences = added_slots = 0
    with SessionLocal() as db:
        provider = db.get(Provider, provider_id)
        if provider is None:
            provider = Provider(
                id=provider_id,
                name="Local Explorer self-guided demo (SIMULATED)",
                slug="local-explorer-self-guided-demo",
                description="Local-only synthetic provider used to preview source-attributed self-guided visits.",
                address="Quận 1, Thành phố Hồ Chí Minh (dữ liệu demo)",
                status="simulated", verification_status="mock",
            )
            db.add(provider)
            db.flush()

        for item in PLACES:
            osm = osm_places.get(item["ext_id"])
            if osm is None:
                raise RuntimeError(f"Missing OSM source candidate: {item['ext_id']}")
            lat, lon = float(osm["lat"]), float(osm["lon"])
            if not is_pilot_location(lat, lon):
                raise RuntimeError(f"Out-of-scope coordinate for {item['name']}: {lat}, {lon}")
            poi_id = stable_id(item["ext_id"])
            exp_id = stable_id(f"experience:{item['ext_id']}")
            poi = db.get(POI, poi_id)
            if poi is None:
                photos = osm.get("photos") or []
                first_photo = photos[0] if photos else {}
                details = {
                    "catalog_mode": "source_attributed_demo",
                    "source_urls": {"openstreetmap": osm["source"], "venue_official": item["official"]},
                    "osm_observed_at": osm.get("source_observed_at"),
                    "osm_license": "ODbL-1.0",
                    # Explore's map cards inspect details.images to choose a
                    # licensed thumbnail, so retain the source payload shape.
                    "images": photos,
                    "photo_credits": photos,
                    "venue_facts": {
                        "public_hours": item["hours"],
                        "public_admission_fee_vnd": item["fee"],
                        "fee_note": item["fee_note"],
                        "facts_source": item["official"],
                    },
                    "demo_notice": SLOT_NOTICE,
                }
                poi = POI(
                    id=poi_id, name=item["name"], description=item["guide"], district="District 1",
                    latitude=lat, longitude=lon,
                    geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
                    category=item["category"], address=osm.get("address") or item["address"],
                    source_attribution=f"{OSM_COPYRIGHT} Official venue source: {item['official']}",
                    is_in_pilot_polygon=True,
                    image_urls=[photo["url"] for photo in photos if photo.get("url")],
                    details=details, verification_status=VerificationStatus.SIMULATED.value,
                )
                db.add(poi)
                added_pois += 1
            else:
                # Keep reruns useful when source metadata or thumbnails change.
                photos = osm.get("photos") or []
                poi.address = osm.get("address") or item["address"]
                poi.description = item["guide"]
                poi.source_attribution = f"{OSM_COPYRIGHT} Official venue source: {item['official']}"
                poi.image_urls = [photo["url"] for photo in photos if photo.get("url")]
                poi.details = {
                    **(poi.details or {}),
                    "catalog_mode": "source_attributed_demo",
                    "source_urls": {"openstreetmap": osm["source"], "venue_official": item["official"]},
                    "osm_observed_at": osm.get("source_observed_at"),
                    "osm_license": "ODbL-1.0",
                    "images": photos,
                    "photo_credits": photos,
                    "venue_facts": {
                        "public_hours": item["hours"],
                        "public_admission_fee_vnd": item["fee"],
                        "fee_note": item["fee_note"],
                        "facts_source": item["official"],
                    },
                    "demo_notice": SLOT_NOTICE,
                }
            experience = db.get(Experience, exp_id)
            if experience is None:
                experience = Experience(
                    id=exp_id, poi_id=poi_id, provider_id=provider_id,
                    name=f"Tự tham quan: {item['name']}", title=f"Tự tham quan: {item['name']}",
                    description=(
                        f"{item['guide']} Phí vào cửa tham khảo: {item['fee']:,} VND/người. "
                        f"{item['fee_note']} Giờ công khai: {item['hours']}. {SLOT_NOTICE}"
                    ),
                    intent_tags=item["tags"], is_hands_on=False, is_indoor=item["indoor"],
                    indoor=item["indoor"], primary_intent=item["tags"][0],
                    weather_sensitivity="high" if not item["indoor"] else "low",
                    duration_min=item["duration"], price_basis=PriceBasis.PER_PERSON.value,
                    price_vnd=item["fee"], verification_status=VerificationStatus.SIMULATED.value,
                )
                db.add(experience)
                db.flush()
                added_experiences += 1
            else:
                experience.description = (
                    f"{item['guide']} Phí vào cửa tham khảo: {item['fee']:,} VND/người. "
                    f"{item['fee_note']} Giờ công khai: {item['hours']}. {SLOT_NOTICE}"
                )
                experience.price_vnd = item["fee"]

            # Available-looking slots are explicitly simulated and remain
            # non-bookable because both the POI and experience are simulated.
            today = datetime.now(HCMC).date()
            for day_offset in range(30):
                service_date = today + timedelta(days=day_offset)
                if service_date.weekday() not in item["weekdays"]:
                    continue
                for hour, minute in item["windows"]:
                    start = datetime.combine(service_date, time(hour, minute), HCMC)
                    if start <= datetime.now(HCMC):
                        continue
                    existing = db.scalar(select(ExperienceSlot.id).where(
                        ExperienceSlot.experience_id == exp_id,
                        ExperienceSlot.start_at == start,
                    ))
                    if existing:
                        continue
                    db.add(ExperienceSlot(
                        id=stable_id(f"slot:{item['ext_id']}:{start.isoformat()}"),
                        experience_id=exp_id, start_at=start,
                        end_at=start + timedelta(minutes=item["duration"]),
                        capacity_total=10, available_reported=10,
                        status=SlotStatus.OPEN.value, confirmed_at=None,
                        expires_at=start - timedelta(minutes=15),
                    ))
                    added_slots += 1
        db.commit()
    return added_pois, added_experiences, added_slots


if __name__ == "__main__":
    pois, experiences, slots = seed()
    print(f"Added {pois} simulated POIs, {experiences} simulated self-guided experiences, and {slots} simulated slots.")
    print("Demo slots are not provider-confirmed and cannot be booked.")
