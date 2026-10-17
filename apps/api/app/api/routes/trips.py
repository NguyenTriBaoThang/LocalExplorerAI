from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.llm.provider import StructuredOutputProvider
from app.api.dependencies import get_llm_provider
from app.api.guards import require_user
from app.api.permissions import P
from app.db.session import get_db
from app.models.entities import User
from app.models.trip_entities import Trip as TripRow, TripDestination, TripProposal
from app.services.trip import flow, store
from app.services.trip.agent import apply_answers, itinerary_event
from app.services.trip.domain import Trip, TripAnswers
from app.services.trip.domain import Disruption
from app.services.trip.followup import changed_trip
from app.services.trip.places import get_places, list_destinations, similar_places
from app.services.trip.replan import InvalidDisruption, NoFeasible, propose, to_draft
from app.services.trip.rules import InvalidDraft, build_itinerary

router = APIRouter(prefix="/api", tags=["trips"])


class NewTrip(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    trip_id: int | None = None  # có → tin nhắn tiếp theo của Trip đang mở (PRD §5.4: chat gắn với Trip)


STALE = "Lịch trình đã có bản mới hơn, hãy mở bản mới nhất rồi thử lại."


class PinIn(BaseModel):
    place_id: int
    pinned: bool


class DisruptionIn(Disruption):
    version: int


class ApplyIn(BaseModel):
    option: int = Field(ge=0)


class Replan(BaseModel):
    changes: dict
    message: str = Field(min_length=1, max_length=2000)


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


def _stop_ids(itin) -> set[int]:
    return {s.place_id for d in itin.days for s in d.stops}


@router.patch("/trips/{trip_id}/pins")
def set_pin(trip_id: int, body: PinIn, db: Session = Depends(get_db),
            user: User = Depends(require_user(P.TRIP_USE))):
    row = _owned(db, user, trip_id)
    if body.pinned:
        latest = store.latest_itinerary(db, trip_id)
        if not latest or body.place_id not in _stop_ids(latest[1]):
            raise HTTPException(422, "Chỉ ghim được Stop đang có trong lịch trình mới nhất")
    return {"pinned_place_ids": store.set_pin(db, row, body.place_id, body.pinned)}


@router.get("/trips/{trip_id}/messages")
def get_messages(trip_id: int, db: Session = Depends(get_db), user: User = Depends(require_user(P.TRIP_USE))):
    _owned(db, user, trip_id)
    return store.messages(db, trip_id)


@router.post("/trips/{trip_id}/restore/{version}")
def restore(trip_id: int, version: int, db: Session = Depends(get_db),
            user: User = Depends(require_user(P.TRIP_USE))):
    """Chép bản cũ thành bản mới, tính lại tiền + Conflict theo Trip hiện tại (spec §2 D3–D5)."""
    row = _owned(db, user, trip_id)
    old = store.load_itinerary(db, trip_id, version)
    if not old:
        raise HTTPException(404, "Không tìm thấy phiên bản lịch trình")
    trip, itin = Trip.model_validate(row.spec), old[1]
    if len(itin.days) != trip.days:
        raise HTTPException(422, f"Bản {version} có {len(itin.days)} ngày nhưng chuyến đi hiện là {trip.days} ngày "
                                 "— hãy đổi lại số ngày trước khi quay lại bản này.")
    places = store.itinerary_places(db, itin)
    used = _stop_ids(itin)
    pins = [p for p in row.pinned_place_ids or [] if p in used]
    dropped = get_places(db, [p for p in row.pinned_place_ids or [] if p not in used])
    dest = next(d for d in list_destinations(db) if d["slug"] == trip.destination)
    try:
        new = build_itinerary(trip, to_draft(itin), places, [d.rain_chance for d in itin.days],
                              store.hub_for(dest, trip))
    except InvalidDraft as e:  # vd Place trong bản cũ đã bị xoá khỏi dữ liệu
        raise HTTPException(422, f"Không quay lại được bản {version}: {e}") from None
    ev = itinerary_event(new, places)
    row.pinned_place_ids = pins
    n = store.save_itinerary(db, trip_id, ev["itinerary"], ev["places"], commit=False)
    text = f"Đã quay lại bản {version} (thành bản {n})."
    if dropped:
        text += " Bỏ ghim: " + ", ".join(p.name for p in dropped.values()) + "."
    store.log_message(db, trip_id, "ai", text, n)  # commits pins + version + message together
    return {**ev, "trip_id": trip_id, "version": n, "pinned_place_ids": pins}


@router.post("/trips/{trip_id}/disruptions")
def create_disruption(trip_id: int, body: DisruptionIn, db: Session = Depends(get_db),
                      user: User = Depends(require_user(P.TRIP_USE))):
    row = _owned(db, user, trip_id)
    loaded = store.load_itinerary(db, trip_id, body.version)
    if not loaded:
        raise HTTPException(404, "Không tìm thấy phiên bản lịch trình")
    if body.version != store.versions(db, trip_id)[-1]:
        raise HTTPException(409, STALE)
    trip, itin = Trip.model_validate(row.spec), loaded[1]
    ids = _stop_ids(itin) | ({itin.stay_place_id} - {None})
    places = get_places(db, ids)
    dest = next(d for d in list_destinations(db) if d["slug"] == trip.destination)
    try:
        result = propose(trip, itin, places, body,
                         lambda lost, used: similar_places(db, lost.id, lost.kind, used, trip.avoided_tags),
                         store.hub_for(dest, trip))
    except InvalidDisruption as e:
        raise HTTPException(422, str(e)) from None

    prop = TripProposal(trip_id=trip_id, base_version=body.version, disruption=body.model_dump(exclude={"version"}),
                        options=[])
    if isinstance(result, NoFeasible):
        prop.no_feasible = result.reason_codes
        db.add(prop)
        db.commit()
        return {"proposal_id": prop.id, "no_feasible": result.reason_codes}
    options = []
    for o in result:
        ev = itinerary_event(o.itinerary, places | {p.id: p for p in o.added})
        options.append({"itinerary": ev["itinerary"], "places": ev["places"], "changed": o.changed,
                        "metrics": o.metrics, "reason_codes": o.reason_codes, "explanation": o.explanation,
                        "title": o.title, "added": [p.id for p in o.added]})
    prop.options = options
    db.add(prop)
    db.commit()
    return {"proposal_id": prop.id, "options": options}


@router.post("/trips/{trip_id}/proposals/{proposal_id}/apply")
def apply_proposal(trip_id: int, proposal_id: int, body: ApplyIn, db: Session = Depends(get_db),
                   user: User = Depends(require_user(P.TRIP_USE))):
    row = _owned(db, user, trip_id)
    db.refresh(row, with_for_update=True)  # serialise with other saves before the stale check
    p = store.locked_proposal(db, trip_id, proposal_id)
    if p is None:
        raise HTTPException(404, "Không tìm thấy phương án")
    if p.applied_version is not None:  # áp dụng lại cùng phương án → trả version cũ (idempotent)
        if p.chosen_index != body.option:
            raise HTTPException(409, "Đã áp dụng một phương án khác cho sự cố này")
        version = p.applied_version
    else:
        if body.option >= len(p.options):
            raise HTTPException(422, "Không có phương án này")
        if p.base_version != store.versions(db, trip_id)[-1]:
            raise HTTPException(409, STALE)
        opt = p.options[body.option]
        if set(row.pinned_place_ids or []) - {st["place_id"] for d in opt["itinerary"]["days"] for st in d["stops"]}:
            raise HTTPException(409, "Stop này vừa được ghim — bỏ ghim rồi báo sự cố lại nếu vẫn muốn đổi.")
        version = store.save_itinerary(db, trip_id, opt["itinerary"], opt["places"], commit=False)
        p.chosen_index, p.applied_version = body.option, version
        store.log_message(db, trip_id, "ai", f"Đã áp dụng phương án — lịch trình bản {version}.", version)
    opt = p.options[body.option]
    return {"type": "itinerary", "itinerary": opt["itinerary"], "places": opt["places"],
            "trip_id": trip_id, "version": version}


@router.post("/trips/{trip_id}/group-reviews")
def create_group_review(trip_id: int, body: GroupReviewIn, db: Session = Depends(get_db),
                        user: User = Depends(require_user(P.TRIP_USE))):
    _owned(db, user, trip_id)
    if not store.load_itinerary(db, trip_id, body.source_version):
        raise HTTPException(404, "Không tìm thấy phiên bản lịch trình")
    return _stream(flow.run_group_review(db, user, trip_id, body.source_version, body.feedback))


@router.post("/trips/{trip_id}/group-reviews/{review_id}/apply")
def apply_group_review(trip_id: int, review_id: int, db: Session = Depends(get_db),
                       user: User = Depends(require_user(P.TRIP_USE))):
    row = _owned(db, user, trip_id)
    db.refresh(row, with_for_update=True)  # serialise with other saves before the stale check
    review = store.locked_review(db, trip_id, review_id)
    if review is None:
        raise HTTPException(404, "Không tìm thấy góp ý nhóm")
    candidate = review.candidate
    if review.status == "applied":
        version = review.applied_version
    elif review.status == "cancelled":
        raise HTTPException(409, "Góp ý nhóm đã bị huỷ")
    else:
        if review.base_version != store.versions(db, trip_id)[-1]:
            raise HTTPException(409, STALE)
        try:
            version = store.save_itinerary(db, trip_id, candidate["itinerary"], candidate["places"], commit=False)
            review.status, review.applied_version = "applied", version
            store.log_message(db, trip_id, "ai", candidate["summary"], version)  # commits all three together
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, STALE) from None
    return {"type": "itinerary", "itinerary": candidate["itinerary"], "places": candidate["places"],
            "trip_id": trip_id, "version": version}


@router.post("/trips/{trip_id}/group-reviews/{review_id}/cancel")
def cancel_group_review(trip_id: int, review_id: int, db: Session = Depends(get_db),
                        user: User = Depends(require_user(P.TRIP_USE))):
    _owned(db, user, trip_id)
    review = store.locked_review(db, trip_id, review_id)
    if review is None:
        raise HTTPException(404, "Không tìm thấy góp ý nhóm")
    if review.status == "applied":
        raise HTTPException(409, "Góp ý nhóm đã được áp dụng")
    if review.status == "pending":
        review.status = "cancelled"
    db.commit()
    return {"review_id": review_id, "status": "cancelled"}
