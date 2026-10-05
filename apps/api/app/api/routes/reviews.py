"""Experience reviews: travelers review what they attended, partners reply, everyone can read published reviews."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.guards import public, require_user
from app.api.permissions import P
from app.models.entities import AuditLog, Booking, Experience, ExperienceReview, ExperienceSlot, Provider, User
from app.schemas.portal import ReviewCreate, ReviewReply

router = APIRouter(prefix="/api", tags=["reviews"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _author(name: str | None) -> str:
    """Public reviews show a first name and initial only."""
    parts = (name or "").split()
    if not parts:
        return "Du khách"
    return parts[-1] if len(parts) == 1 else f"{parts[-1]} {parts[0][0]}."


def review_view(review: ExperienceReview, author: str | None, experience_title: str | None = None) -> dict:
    return {"id": review.id, "experience_id": review.experience_id, "experience_title": experience_title, "rating": review.rating,
            "comment": review.comment, "author": _author(author), "reply": review.reply, "replied_at": review.replied_at,
            "status": review.status, "created_at": review.created_at}


@router.get("/experiences/{experience_id}/reviews", dependencies=[Depends(public("published reviews of a public experience"))])
def experience_reviews(experience_id: str, db: Session = Depends(get_db), limit: int = Query(default=20, ge=1, le=100)):
    rows = db.execute(select(ExperienceReview, User.display_name).outerjoin(User, User.id == ExperienceReview.user_id).where(
        ExperienceReview.experience_id == experience_id, ExperienceReview.status == "published",
    ).order_by(ExperienceReview.created_at.desc()).limit(limit)).all()
    stats = db.execute(select(func.count(ExperienceReview.id), func.avg(ExperienceReview.rating)).where(
        ExperienceReview.experience_id == experience_id, ExperienceReview.status == "published")).one()
    return {"count": stats[0] or 0, "average": round(float(stats[1]), 1) if stats[1] is not None else None,
            "items": [review_view(review, name) for review, name in rows]}


@router.post("/bookings/{booking_id}/review", status_code=201)
def create_review(booking_id: str, payload: ReviewCreate, user: User = Depends(require_user(P.REVIEW_WRITE)), db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if booking is None or booking.user_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Booking not found."})
    slot = db.get(ExperienceSlot, booking.slot_id)
    if booking.status != "confirmed" or slot is None or _aware(slot.start_at) > _now():
        raise HTTPException(status_code=409, detail={"code": "REVIEW_NOT_ALLOWED", "message": "You can review an experience after attending a confirmed booking."})
    if db.scalar(select(ExperienceReview.id).where(ExperienceReview.booking_id == booking.id)):
        raise HTTPException(status_code=409, detail={"code": "ALREADY_REVIEWED", "message": "This booking has already been reviewed."})
    review = ExperienceReview(id=str(uuid4()), experience_id=booking.experience_id, provider_id=booking.provider_id, booking_id=booking.id,
                              user_id=user.id, rating=payload.rating, comment=payload.comment.strip(), created_at=_now())
    db.add(review)
    db.commit()
    return review_view(review, user.display_name)


@router.get("/me/reviewable-bookings")
def reviewable_bookings(user: User = Depends(require_user(P.REVIEW_WRITE)), db: Session = Depends(get_db)):
    """Attended, confirmed bookings the traveler has not reviewed yet (for a "rate your experience" prompt)."""
    reviewed = select(ExperienceReview.booking_id)
    rows = db.execute(select(Booking, Experience.title, ExperienceSlot.start_at).join(Experience, Experience.id == Booking.experience_id)
                      .join(ExperienceSlot, ExperienceSlot.id == Booking.slot_id).where(
        Booking.user_id == user.id, Booking.status == "confirmed", Booking.id.not_in(reviewed),
    ).order_by(ExperienceSlot.start_at.desc()).limit(20)).all()
    now = _now()
    return [{"booking_id": booking.id, "experience_id": booking.experience_id, "experience_title": title, "slot_start_at": start}
            for booking, title, start in rows if _aware(start) <= now]


def _provider_id(db: Session, user: User) -> str:
    provider = db.get(Provider, user.provider_id) if user.provider_id else None
    if provider is None:
        raise HTTPException(status_code=403, detail={"code": "PROVIDER_PROFILE_REQUIRED", "message": "This account has no provider profile."})
    return provider.id


@router.get("/provider/me/reviews")
def provider_reviews(user: User = Depends(require_user(P.PROVIDER_REVIEWS)), db: Session = Depends(get_db)):
    provider_id = _provider_id(db, user)
    rows = db.execute(select(ExperienceReview, User.display_name, Experience.title)
                      .outerjoin(User, User.id == ExperienceReview.user_id).join(Experience, Experience.id == ExperienceReview.experience_id)
                      .where(ExperienceReview.provider_id == provider_id).order_by(ExperienceReview.created_at.desc()).limit(500)).all()
    return [review_view(review, name, title) for review, name, title in rows]


@router.post("/provider/me/reviews/{review_id}/reply")
def reply_to_review(review_id: str, payload: ReviewReply, user: User = Depends(require_user(P.PROVIDER_REVIEWS)), db: Session = Depends(get_db)):
    provider_id = _provider_id(db, user)
    review = db.scalar(select(ExperienceReview).where(ExperienceReview.id == review_id, ExperienceReview.provider_id == provider_id))
    if review is None:
        raise HTTPException(status_code=404, detail={"code": "REVIEW_NOT_FOUND", "message": "Review not found."})
    review.reply, review.replied_at = payload.reply.strip(), _now()
    db.add(AuditLog(id=str(uuid4()), actor_id=user.id, action="review.replied", target_type="review", target_id=review.id, details={}, created_at=_now()))
    db.commit()
    title = db.scalar(select(Experience.title).where(Experience.id == review.experience_id))
    author = db.scalar(select(User.display_name).where(User.id == review.user_id)) if review.user_id else None
    return review_view(review, author, title)
