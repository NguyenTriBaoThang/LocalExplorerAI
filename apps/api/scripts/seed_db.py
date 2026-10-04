from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from app.core.enums import PriceBasis, SlotStatus, VerificationStatus
from app.db.session import SessionLocal
from app.models.entities import Experience, ExperienceSlot, POI, Provider
from app.models.entities import User
from app.core.config import settings
from app.services.auth_service import hash_password

HCMC = ZoneInfo("Asia/Ho_Chi_Minh")
DEMO_EXPERIENCES = [
    ("Góc thủ công giấy", "handicraft", ["handicraft", "hands_on", "local_life"], 75, 120000, True, 10.7752, 106.7018),
    ("Bàn trải nghiệm gốm", "handicraft", ["handicraft", "hands_on", "relaxation"], 90, 180000, True, 10.7791, 106.6957),
    ("Bếp món Nam bộ", "food", ["food", "hands_on", "local_life"], 90, 220000, True, 10.7715, 106.6981),
    ("Bữa thử món địa phương", "food", ["food", "culture"], 60, 160000, False, 10.7682, 106.7040),
    ("Chuyện phố qua ảnh", "culture", ["culture", "local_life"], 60, 90000, True, 10.7797, 106.7004),
    ("Góc ký ức đô thị", "culture", ["culture", "relaxation"], 75, 110000, True, 10.7733, 106.6918),
    ("Vườn xanh trong phố", "nature", ["nature", "relaxation"], 60, 80000, False, 10.7820, 106.7060),
    ("Đi bộ quan sát cây phố", "nature", ["nature", "local_life"], 75, 70000, False, 10.7676, 106.6962),
    ("Khoảng nghỉ trà thảo mộc", "relaxation", ["relaxation", "food"], 60, 100000, True, 10.7812, 106.6909),
    ("Tự làm quà lưu niệm", "handicraft", ["handicraft", "hands_on", "culture"], 105, 250000, True, 10.7697, 106.7072),
]


def seed(session_factory=SessionLocal) -> None:
    if settings.real_data_only:
        raise RuntimeError("Demo seeding is disabled while REAL_DATA_ONLY is enabled. Use a separate test/development configuration to seed fixtures.")
    with session_factory() as db:
        if settings.app_env.lower() == "development":
            demo_accounts = [
                (settings.demo_admin_email.strip().lower(), settings.demo_admin_password, "Local Explorer Admin", "admin"),
                (settings.demo_traveler_email.strip().lower(), settings.demo_traveler_password, "Bao Thang", "traveler"),
            ]
            for email, password, display_name, role in demo_accounts:
                if password and not db.scalar(select(User.id).where(User.email == email)):
                    db.add(User(email=email, display_name=display_name, password_hash=hash_password(password), role=role))
            db.commit()
        if db.scalar(select(Provider.id).limit(1)):
            print("Seed data already exists; leaving existing records untouched.")
            return
        provider = Provider(
            name="Local Explorer demo provider (SIMULATED)", slug="local-explorer-demo-provider",
            description="Synthetic provider record for development only.", address="Ho Chi Minh City (simulated)",
            status="simulated", verification_status="mock",
        )
        db.add(provider)
        db.flush()
        experiences: list[Experience] = []
        for index, (name, category, tags, duration, price, indoor, lat, lon) in enumerate(DEMO_EXPERIENCES, start=1):
            poi = POI(
                name=f"Điểm demo {index:02d}: {name}",
                description="Địa điểm hư cấu dùng để trình diễn giao diện; cần xác minh trước khi sử dụng thực tế.",
                latitude=lat, longitude=lon, category=category, geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
                address=f"Khu vực trung tâm TP. Hồ Chí Minh — tọa độ mô phỏng {index:02d}",
                verification_status=VerificationStatus.SIMULATED.value,
            )
            experience = Experience(
                poi=poi, provider=provider, name=name, title=name,
                description="Hoạt động demo. Giá, khung giờ và thông tin nhà cung cấp đều là dữ liệu mô phỏng, chưa xác nhận đặt chỗ.",
                intent_tags=tags, is_hands_on="hands_on" in tags, is_indoor=indoor,
                duration_min=duration, indoor=indoor,
                price_basis=PriceBasis.PER_PERSON.value, price_vnd=price,
                verification_status=VerificationStatus.SIMULATED.value,
            )
            db.add(experience)
            experiences.append(experience)
        db.flush()
        today = datetime.now(HCMC).date()
        daily_times = [time(9, 0), time(11, 30), time(14, 30)]
        for day_offset in range(30):
            service_date = today + timedelta(days=day_offset)
            for exp_index, experience in enumerate(experiences):
                for slot_index, slot_time in enumerate(daily_times):
                    start = datetime.combine(service_date, slot_time, HCMC)
                    end = start + timedelta(minutes=experience.duration_min)
                    unknown = slot_index == 1 and day_offset % 2 == 0
                    available = None if unknown else (0 if day_offset % 11 == 0 and slot_index == 2 else 8)
                    status = SlotStatus.TENTATIVE.value if unknown else (SlotStatus.FULL.value if available == 0 else SlotStatus.OPEN.value)
                    db.add(ExperienceSlot(
                        experience_id=experience.id, start_at=start, end_at=end,
                        capacity_total=10, available_reported=available, status=status,
                        confirmed_at=None if unknown else datetime.now(timezone.utc),
                        expires_at=start - timedelta(minutes=30) if unknown else start - timedelta(minutes=15),
                    ))
        db.commit()
        print(f"Inserted 1 simulated provider, {len(experiences)} experiences and {len(experiences) * 90} simulated slots.")


if __name__ == "__main__":
    seed()
