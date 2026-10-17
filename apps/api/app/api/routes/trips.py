from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.adapters.llm.provider import StructuredOutputProvider
from app.api.dependencies import get_llm_provider
from app.api.guards import require_user
from app.api.permissions import P
from app.db.session import get_db
from app.models.entities import User
from app.models.trip_entities import Trip as TripRow, TripDestination
from app.services.trip import flow, store
from app.services.trip.agent import apply_answers
from app.services.trip.domain import Trip, TripAnswers
from app.services.trip.followup import changed_trip

router = APIRouter(prefix="/api", tags=["trips"])


class NewTrip(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    trip_id: int | None = None  # có → tin nhắn tiếp theo của Trip đang mở (PRD §5.4: chat gắn với Trip)


class Replan(BaseModel):
    changes: dict
    message: str = Field(min_length=1, max_length=2000)


def _owned(db: Session, user: User, trip_id: int) -> TripRow:
    row = store.trip_row(db, user.id, trip_id)
    if row is None:
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    return row


def _stream(events) -> StreamingResponse:
    # The request's db session stays open until the stream ends (FastAPI runs yield-dependency teardown after the response).
    return StreamingResponse(events, media_type="text/event-stream")


def _invalid(e: ValidationError) -> HTTPException:
    return HTTPException(422, e.errors()[0]["msg"].removeprefix("Value error, "))


@router.get("/trips")
def list_trips(db: Session = Depends(get_db), user: User = Depends(require_user(P.TRIP_USE))):
    return store.list_trips(db, user.id)


@router.post("/trips")
def create_trip(body: NewTrip, db: Session = Depends(get_db),
                provider: StructuredOutputProvider = Depends(get_llm_provider),
                user: User = Depends(require_user(P.TRIP_USE))):
    if body.trip_id is not None:
        _owned(db, user, body.trip_id)
    return _stream(flow.run_message(db, user, body.message, body.trip_id, provider))


@router.post("/trips/{trip_id}/plan")
def plan_trip(trip_id: int, answers: TripAnswers, db: Session = Depends(get_db),
              user: User = Depends(require_user(P.TRIP_USE))):
    row = _owned(db, user, trip_id)
    if store.latest_itinerary(db, trip_id):
        raise HTTPException(409, "Chuyến đi đã có lịch trình")
    try:
        apply_answers(Trip.model_validate(row.spec), answers)
    except ValidationError as e:
        raise _invalid(e) from None
    return _stream(flow.run_plan(db, user, trip_id, answers))


@router.post("/trips/{trip_id}/replan")
def replan_trip(trip_id: int, body: Replan, db: Session = Depends(get_db),
                user: User = Depends(require_user(P.TRIP_USE))):
    """Người dùng xác nhận đổi Trip (event confirm_replan) → lập lại, gửi kèm lịch cũ làm gợi ý."""
    row = _owned(db, user, trip_id)
    try:
        changed_trip(Trip.model_validate(row.spec), body.changes)
    except ValidationError as e:
        raise _invalid(e) from None
    return _stream(flow.run_replan(db, user, trip_id, body.changes, body.message))


@router.get("/trips/{trip_id}")
def get_trip(trip_id: int, version: int | None = None, db: Session = Depends(get_db),
             user: User = Depends(require_user(P.TRIP_USE))):
    row = _owned(db, user, trip_id)
    it = store.load_itinerary(db, trip_id, version)
    if version is not None and not it:
        raise HTTPException(404, "Không tìm thấy phiên bản lịch trình")
    dest = db.get(TripDestination, row.spec["destination"])
    return {"trip_id": row.id, "trip": row.spec, "center": [dest.lon, dest.lat],
            "version": it[0] if it else None,
            "itinerary": it[1].model_dump(mode="json") if it else None,
            "places": it[2] if it else {}, "versions": store.versions(db, trip_id),
            "pinned_place_ids": row.pinned_place_ids}
