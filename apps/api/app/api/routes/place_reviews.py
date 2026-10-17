"""Place reviews written by travelers, the Google Maps rating shown beside them, and review moderation for administrators.

Who may review a place: a signed-in traveler who has planned an itinerary that includes it. The two sources are never
merged into one score: the page shows the community's reviews and Google's rating as separate blocks.
"""

import logging
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.guards import public, require_user
from app.api.permissions import P
from app.models.entities import AuditLog, Booking, Experience, ExperienceReview, Itinerary, ItineraryStop, PlaceReview, POI, User
from app.repositories.experience_repository import ExperienceRepository
from app.schemas.portal import PlaceReviewWrite, ReviewModeration
from app.services import external_ratings
from app.services.review_common import author_label, check_comment

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["place-reviews"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _public_poi(db: Session, poi_id: str) -> POI:
    poi = ExperienceRepository(db).get_poi(poi_id)
    if poi is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Place not found."})
    return poi


def has_planned(db: Session, user_id: str, poi_id: str) -> bool:
    """The user owns an itinerary that has a stop at this place."""
    return db.scalar(select(ItineraryStop.id).join(Itinerary, Itinerary.id == ItineraryStop.itinerary_id)
                     .where(Itinerary.user_id == user_id, ItineraryStop.poi_id == poi_id).limit(1)) is not None


def _own_view(review: PlaceReview) -> dict:
    return {"id": review.id, "poi_id": review.poi_id, "rating": review.rating, "comment": review.comment, "visited_on": review.visited_on,
            "status": review.status, "created_at": review.created_at, "updated_at": review.updated_at}


@router.get("/pois/{poi_id}/reviews", dependencies=[Depends(public("published reviews and the Google rating of a public place"))])
def place_reviews(poi_id: str, db: Session = Depends(get_db), limit: int = Query(default=20, ge=1, le=100)):
    poi = _public_poi(db, poi_id)
    published = (PlaceReview.poi_id == poi.id, PlaceReview.status == "published")
    rows = db.execute(select(PlaceReview, User.display_name).outerjoin(User, User.id == PlaceReview.user_id).where(*published)
                      .order_by(PlaceReview.created_at.desc()).limit(limit)).all()
    count, average = db.execute(select(func.count(PlaceReview.id), func.avg(PlaceReview.rating)).where(*published)).one()
    distribution = {str(star): 0 for star in range(1, 6)}
    for star, number in db.execute(select(PlaceReview.rating, func.count(PlaceReview.id)).where(*published).group_by(PlaceReview.rating)).all():
        distribution[str(star)] = number
    google = None
    try:
        google = external_ratings.google_rating(db, poi)
    except Exception:   # the Google block is optional: never let it break the page
        log.exception("Google rating lookup failed for place %s", poi.id)
        db.rollback()
    return {
        "community": {"count": count or 0, "average": round(float(average), 1) if average is not None else None, "distribution": distribution,
                      "items": [{"id": review.id, "author": author_label(name), "rating": review.rating, "comment": review.comment,
                                 "visited_on": review.visited_on, "created_at": review.created_at, "edited": review.updated_at is not None}
                                for review, name in rows]},
        "google": google,
    }


@router.get("/pois/{poi_id}/reviews/mine")
def my_place_review(poi_id: str, user: User = Depends(require_user(P.REVIEW_WRITE)), db: Session = Depends(get_db)):
    _public_poi(db, poi_id)
    mine = db.scalar(select(PlaceReview).where(PlaceReview.poi_id == poi_id, PlaceReview.user_id == user.id))
    allowed = mine is not None or has_planned(db, user.id, poi_id)
    return {"can_review": allowed, "reason": None if allowed else "no_itinerary", "review": _own_view(mine) if mine else None}


@router.put("/pois/{poi_id}/review")
def write_place_review(poi_id: str, payload: PlaceReviewWrite, user: User = Depends(require_user(P.REVIEW_WRITE)), db: Session = Depends(get_db)):
    _public_poi(db, poi_id)
    if payload.visited_on and payload.visited_on > date.today():
        raise HTTPException(status_code=422, detail={"code": "VISIT_DATE_IN_FUTURE", "message": "The visit date cannot be in the future."})
    comment = check_comment(payload.comment)
    review = db.scalar(select(PlaceReview).where(PlaceReview.poi_id == poi_id, PlaceReview.user_id == user.id))
    if review is None:
        if not has_planned(db, user.id, poi_id):
            raise HTTPException(status_code=403, detail={"code": "REVIEW_NOT_ALLOWED", "message": "Plan an itinerary that includes this place to review it."})
        review = PlaceReview(id=str(uuid4()), poi_id=poi_id, user_id=user.id, rating=payload.rating, comment=comment,
                             visited_on=payload.visited_on, created_at=_now())
        db.add(review)
    else:
        review.rating, review.comment, review.visited_on, review.updated_at = payload.rating, comment, payload.visited_on, _now()
    db.commit()
    return _own_view(review)


@router.delete("/pois/{poi_id}/review", status_code=204)
def delete_place_review(poi_id: str, user: User = Depends(require_user(P.REVIEW_WRITE)), db: Session = Depends(get_db)):
    review = db.scalar(select(PlaceReview).where(PlaceReview.poi_id == poi_id, PlaceReview.user_id == user.id))
    if review is None:
        raise HTTPException(status_code=404, detail={"code": "REVIEW_NOT_FOUND", "message": "You have not reviewed this place."})
    db.delete(review)
    db.commit()
    return Response(status_code=204)


@router.get("/me/reviews")
def my_reviews(user: User = Depends(require_user(P.REVIEW_WRITE)), db: Session = Depends(get_db)):
    """Everything the signed-in traveler has written, so it can be edited or removed."""
    places = db.execute(select(PlaceReview, POI.name).join(POI, POI.id == PlaceReview.poi_id).where(PlaceReview.user_id == user.id)
                        .order_by(PlaceReview.created_at.desc())).all()
    experiences = db.execute(select(ExperienceReview, Experience.title).join(Experience, Experience.id == ExperienceReview.experience_id)
                             .where(ExperienceReview.user_id == user.id).order_by(ExperienceReview.created_at.desc())).all()
    return {"places": [{**_own_view(review), "poi_name": name} for review, name in places],
            "experiences": [{"id": review.id, "booking_id": review.booking_id, "experience_id": review.experience_id, "experience_title": title,
                             "rating": review.rating, "comment": review.comment, "reply": review.reply, "status": review.status,
                             "created_at": review.created_at, "updated_at": review.updated_at} for review, title in experiences]}


# ---- moderation (administrators) -------------------------------------------------------------------------------------

def _model(kind: str):
    if kind not in {"place", "experience"}:
        raise HTTPException(status_code=404, detail={"code": "REVIEW_KIND_UNKNOWN", "message": "Reviews are either 'place' or 'experience'."})
    return PlaceReview if kind == "place" else ExperienceReview


@router.get("/admin/reviews")
def admin_reviews(response: Response, user: User = Depends(require_user(P.ADMIN_REVIEWS)), db: Session = Depends(get_db),
                  kind: str = Query(default="place"), status: str = Query(default="", pattern="^(|published|hidden)$"),
                  q: str | None = Query(default=None, max_length=120), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    model = _model(kind)
    if kind == "place":
        base = select(PlaceReview, User.display_name, User.email, POI.name).outerjoin(User, User.id == PlaceReview.user_id).join(POI, POI.id == PlaceReview.poi_id)
        target_id = PlaceReview.poi_id
    else:
        base = select(ExperienceReview, User.display_name, User.email, Experience.title).outerjoin(User, User.id == ExperienceReview.user_id) \
            .join(Experience, Experience.id == ExperienceReview.experience_id)
        target_id = ExperienceReview.experience_id
    if status:
        base = base.where(model.status == status)
    if q and q.strip():
        like = f"%{q.strip()}%"
        base = base.where(or_(model.comment.ilike(like), User.display_name.ilike(like), User.email.ilike(like)))
    response.headers["X-Total-Count"] = str(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    rows = db.execute(base.order_by(model.created_at.desc()).limit(limit).offset(offset)).all()
    return [{"kind": kind, "id": review.id, "target_id": getattr(review, target_id.key), "target_title": title, "author_name": name, "author_email": email,
             "rating": review.rating, "comment": review.comment, "status": review.status, "moderation_note": review.moderation_note,
             "moderated_at": review.moderated_at, "created_at": review.created_at} for review, name, email, title in rows]


@router.post("/admin/reviews/{kind}/{review_id}/status")
def moderate_review(kind: str, review_id: str, payload: ReviewModeration, actor: User = Depends(require_user(P.ADMIN_REVIEWS)), db: Session = Depends(get_db)):
    model = _model(kind)
    review = db.get(model, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail={"code": "REVIEW_NOT_FOUND", "message": "Review not found."})
    note = payload.note.strip()
    if payload.action == "hide" and len(note) < 3:
        raise HTTPException(status_code=422, detail={"code": "REASON_REQUIRED", "message": "Give a short reason for hiding the review."})
    review.status = "hidden" if payload.action == "hide" else "published"
    review.moderation_note, review.moderated_at = (note or None), _now()
    db.add(AuditLog(id=str(uuid4()), actor_id=actor.id, action=f"review.{'hidden' if payload.action == 'hide' else 'restored'}",
                    target_type=f"{kind}_review", target_id=review.id, details={"note": note}, created_at=_now()))
    db.commit()
    return {"kind": kind, "id": review.id, "status": review.status, "moderation_note": review.moderation_note}
