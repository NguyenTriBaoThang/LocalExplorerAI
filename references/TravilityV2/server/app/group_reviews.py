from fastapi import APIRouter, Depends, HTTPException
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, Field, field_validator

from app.auth import current_user, get_shard
from app.trips import _stream, load_itinerary, log_message, save_itinerary

router = APIRouter()


class GroupReviewIn(BaseModel):
    source_version: int = Field(ge=1)
    feedback: str = Field(min_length=1, max_length=2000)

    @field_validator("feedback", mode="before")
    @classmethod
    def trim_feedback(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("feedback")
    @classmethod
    def non_blank_feedback(cls, value: str) -> str:
        if not value:
            raise ValueError("Góp ý không được chỉ có khoảng trắng")
        return value


@router.post("/trips/{trip_id}/group-reviews")
def create_group_review(trip_id: int, body: GroupReviewIn, user_id: int = Depends(current_user), conn=Depends(get_shard)):
    trip = conn.execute("SELECT 1 FROM trips WHERE id = %s AND user_id = %s", (trip_id, user_id)).fetchone()
    if not trip:
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    if not load_itinerary(conn, trip_id, body.source_version):
        raise HTTPException(404, "Không tìm thấy phiên bản lịch trình")
    return _stream("group_review", user_id, trip_id=trip_id, source_version=body.source_version, feedback=body.feedback)


STALE = "Lịch trình đã có bản mới hơn, hãy mở bản mới nhất rồi thử lại."


def _owned_review(conn, trip_id: int, review_id: int, user_id: int) -> dict | None:
    return conn.execute(
        """SELECT p.* FROM group_review_proposals p
           JOIN trips t ON t.id = p.trip_id AND t.user_id = %s
           WHERE p.id = %s AND p.trip_id = %s FOR UPDATE OF p""",
        (user_id, review_id, trip_id),
    ).fetchone()


@router.post("/trips/{trip_id}/group-reviews/{review_id}/apply")
def apply_group_review(trip_id: int, review_id: int, user_id: int = Depends(current_user), conn=Depends(get_shard)):
    with conn.transaction():
        review = _owned_review(conn, trip_id, review_id, user_id)
        if not review:
            raise HTTPException(404, "Không tìm thấy góp ý nhóm")
        conn.execute("SELECT id FROM trips WHERE id = %s AND user_id = %s FOR UPDATE", (trip_id, user_id)).fetchone()
        candidate = review["candidate"]
        if review["status"] == "applied":
            version = review["applied_version"]
        elif review["status"] == "cancelled":
            raise HTTPException(409, "Góp ý nhóm đã bị huỷ")
        else:
            latest = conn.execute("SELECT MAX(version) AS version FROM itineraries WHERE trip_id = %s", (trip_id,)) \
                         .fetchone()["version"]
            if review["base_version"] != latest:
                raise HTTPException(409, STALE)
            try:
                version = save_itinerary(conn, trip_id, candidate["itinerary"], candidate["places"])
            except UniqueViolation:
                raise HTTPException(409, STALE) from None
            conn.execute("UPDATE group_review_proposals SET status = 'applied', applied_version = %s WHERE id = %s",
                         (version, review_id))
            log_message(conn, trip_id, "ai", candidate["summary"], version)
    return {"type": "itinerary", "itinerary": candidate["itinerary"], "places": candidate["places"],
            "trip_id": trip_id, "version": version}


@router.post("/trips/{trip_id}/group-reviews/{review_id}/cancel")
def cancel_group_review(trip_id: int, review_id: int, user_id: int = Depends(current_user), conn=Depends(get_shard)):
    with conn.transaction():
        review = _owned_review(conn, trip_id, review_id, user_id)
        if not review:
            raise HTTPException(404, "Không tìm thấy góp ý nhóm")
        if review["status"] == "applied":
            raise HTTPException(409, "Góp ý nhóm đã được áp dụng")
        if review["status"] == "pending":
            conn.execute("UPDATE group_review_proposals SET status = 'cancelled' WHERE id = %s", (review_id,))
    return {"review_id": review_id, "status": "cancelled"}
