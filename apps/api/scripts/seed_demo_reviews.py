"""Sample reviews so the place-review screens can be reviewed without waiting for real users.

    python -m scripts.seed_demo_reviews

Development only (refused while REAL_DATA_ONLY is on or in production). Safe to run twice: it does nothing if the demo
reviewers already exist. It never invents Google data: only traveler reviews are created. Demo reviewers get an unusable
random password, so nobody can sign in as them; the existing demo traveler gets an itinerary through two landmarks so a
review can be written by hand.
"""

import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.entities import (  # noqa: E402
    Booking, Experience, ExperienceReview, ExperienceSlot, Itinerary, ItineraryStop, PlaceReview, POI, User,
)

DEMO_REVIEWERS = [
    ("demo.minhanh@example.test", "Lê Minh Anh"),
    ("demo.hoangnam@example.test", "Phạm Hoàng Nam"),
    ("demo.thuha@example.test", "Nguyễn Thu Hà"),
    ("demo.quocbao@example.test", "Trần Quốc Bảo"),
]
# (landmark index, reviewer index, rating, comment, visited days ago)
PLACE_REVIEWS = [
    (0, 0, 5, "Góc nhỏ rất yên tĩnh, đi buổi sáng ánh sáng đẹp. Nhân viên hướng dẫn nhiệt tình.", 12),
    (0, 1, 4, "Đáng ghé, nhưng cuối tuần khá đông nên nên đi sớm.", 9),
    (0, 2, 5, "Mình dẫn bố mẹ đi, ai cũng thích. Sẽ quay lại.", 20),
    (0, 3, 3, "Ổn, chỉ hơi khó tìm đường vào lần đầu.", 5),
    (1, 0, 4, "Không gian đẹp, giá hợp lý.", 7),
    (1, 2, 4, "Phù hợp đi nhóm nhỏ, chụp ảnh đẹp.", 14),
    (1, 1, 5, "Trải nghiệm tuyệt vời, rất đáng tiền.", 3),
    (2, 3, 2, "Mong đợi nhiều hơn, hôm mình đi hơi ồn.", 10),
]
HIDDEN_PLACE_REVIEW = (2, 1, 1, "Liên hệ ngay để được giảm giá cực sốc!!!", "Nội dung quảng cáo, không phải đánh giá.")
# (experience index, reviewer index, rating, comment, partner reply)
EXPERIENCE_REVIEWS = [
    (0, 0, 5, "Lớp học thú vị, tự tay làm được một món quà nhỏ.", "Cảm ơn bạn đã tham gia! Hẹn gặp lại ở lớp tiếp theo."),
    (0, 1, 4, "Hướng dẫn kỹ, thời lượng vừa phải.", None),
    (1, 2, 4, "Gốm đẹp, cô giáo vui tính.", None),
    (2, 3, 3, "Ổn nhưng phần chờ hơi lâu.", "Cảm ơn góp ý của bạn, chúng tôi sẽ rút ngắn thời gian chờ."),
]


def _plan(db, user, experience, now):
    slot = db.scalars(select(ExperienceSlot).where(ExperienceSlot.experience_id == experience.id, ExperienceSlot.start_at > now)
                      .order_by(ExperienceSlot.start_at)).first()
    itinerary = Itinerary(user_id=user.id, group_size=2, budget_vnd=1_000_000, travel_mode="driving", start_at=slot.start_at, end_at=slot.end_at,
                          status="feasible", constraints={}, estimated_cost_vnd=experience.price_vnd * 2)
    db.add(itinerary)
    db.flush()
    db.add(ItineraryStop(itinerary_id=itinerary.id, experience_id=experience.id, slot_id=slot.id, poi_id=experience.poi_id, stop_order=1, position=1,
                         arrival_at=slot.start_at, departure_at=slot.end_at, start_at=slot.start_at, end_at=slot.end_at,
                         activity_duration_min=experience.duration_min, cost_vnd=experience.price_vnd * 2))


def main() -> None:
    if settings.real_data_only or settings.app_env.lower() == "production":
        raise SystemExit("Demo reviews are only for a development database (REAL_DATA_ONLY must be off).")
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        experiences = db.scalars(select(Experience).order_by(Experience.name)).all()
        if len(experiences) < 3:
            raise SystemExit("Run `python -m scripts.seed_db` first: no demo experiences found.")
        if db.scalar(select(User.id).where(User.email == DEMO_REVIEWERS[0][0])):
            print("Demo reviews already exist; nothing to do.")
            return
        landmarks = [db.get(POI, e.poi_id) for e in experiences[:3]]
        for poi in landmarks:
            poi.is_landmark = True
        users = []
        for email, name in DEMO_REVIEWERS:
            user = User(email=email, display_name=name, password_hash=hash_password(secrets.token_urlsafe(24)), role="traveler", email_verified_at=now)
            db.add(user)
            users.append(user)
        db.flush()
        # Reviewing a place needs an itinerary that includes it.
        for index, user in enumerate(users):
            for experience in experiences[:3]:
                _plan(db, user, experience, now)
        for landmark, reviewer, rating, comment, days_ago in PLACE_REVIEWS:
            db.add(PlaceReview(poi_id=landmarks[landmark].id, user_id=users[reviewer].id, rating=rating, comment=comment,
                               visited_on=(now - timedelta(days=days_ago)).date(), created_at=now - timedelta(days=days_ago)))
        landmark, reviewer, rating, comment, note = HIDDEN_PLACE_REVIEW
        db.add(PlaceReview(poi_id=landmarks[landmark].id, user_id=users[reviewer].id, rating=rating, comment=comment, status="hidden",
                           moderation_note=note, moderated_at=now, created_at=now - timedelta(days=2)))
        # Attended, confirmed bookings (a slot that already started) for the experience reviews.
        for index, experience in enumerate(experiences[:3]):
            start = now - timedelta(days=3 + index)
            slot = ExperienceSlot(experience_id=experience.id, start_at=start, end_at=start + timedelta(hours=2), capacity_total=10,
                                  available_reported=10, status="open")
            db.add(slot)
            db.flush()
            for exp_index, reviewer, rating, comment, reply in EXPERIENCE_REVIEWS:
                if exp_index != index:
                    continue
                booking = Booking(user_id=users[reviewer].id, provider_id=experience.provider_id, experience_id=experience.id, slot_id=slot.id,
                                  quantity=2, amount_vnd=experience.price_vnd * 2, status="confirmed", confirmed_at=start - timedelta(days=1))
                db.add(booking)
                db.flush()
                db.add(ExperienceReview(experience_id=experience.id, provider_id=experience.provider_id, booking_id=booking.id, user_id=users[reviewer].id,
                                        rating=rating, comment=comment, reply=reply, replied_at=now - timedelta(days=1) if reply else None,
                                        created_at=now - timedelta(days=1)))
        # The demo traveler can write a review by hand: give them an itinerary through two of the landmarks.
        demo = db.scalar(select(User).where(User.email == settings.demo_traveler_email.strip().lower()))
        if demo is not None and not db.scalar(select(Itinerary.id).where(Itinerary.user_id == demo.id)):
            for experience in experiences[:2]:
                _plan(db, demo, experience, now)
        db.commit()
        print(f"Seeded {len(users)} demo reviewers, {len(PLACE_REVIEWS) + 1} place reviews (1 hidden), {len(EXPERIENCE_REVIEWS)} experience reviews, "
              f"3 landmarks. Demo traveler {settings.demo_traveler_email} can now review the first two landmarks.")


if __name__ == "__main__":
    main()
