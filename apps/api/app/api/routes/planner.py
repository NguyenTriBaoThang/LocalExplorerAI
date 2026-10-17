import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_llm_provider
from app.adapters.llm.provider import StructuredOutputProvider
from app.adapters.routing.provider import RoutingConfigurationError, RoutingProviderError, UnsupportedTravelMode
from app.db.session import get_db
from app.models.entities import Event, Experience, ExperienceSlot, Feedback, Itinerary, ItineraryStop, ItineraryVersion, User
from app.schemas.ai import FeedbackLabelRequest
from app.schemas.planner import ItinerarySuggestionsResponse, PlanConfirmationRequest, PlanPreviewResponse, PlanRequest, PlanResponse
from app.services.itinerary_suggestions import rank_suggestions_with_gemini, suggest_itineraries
from app.services.plan_preview_token import InvalidPlanPreviewToken, issue_plan_preview_token, request_fingerprint, verify_plan_preview_token
from app.services.planner_service import NoFeasiblePlan, PlanPreviewChanged, PlannerService
from app.api.guards import public, require_user
from app.api.permissions import P

router = APIRouter(prefix="/api", tags=["planner"])


def _create_preview(payload: PlanRequest, db: Session, user: User | None) -> dict:
    result = PlannerService(db).plan(payload, user.id if user else None, persist=False)
    preview_id, token = issue_plan_preview_token(payload, result, user.id if user else None)
    return {"preview_id": preview_id, "confirmation_token": token, **result}


def _check_traveler(user: User | None) -> None:
    if user is not None and user.role != "traveler":
        raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN", "message": "Only traveler accounts can create itineraries."})


@router.post("/itineraries/suggestions", response_model=ItinerarySuggestionsResponse)
def itinerary_suggestions(payload: PlanRequest, db: Session = Depends(get_db), user: User | None = Depends(require_user(P.ITINERARY_PLAN, optional=True)), provider: StructuredOutputProvider = Depends(get_llm_provider)):
    _check_traveler(user)
    if payload.origin_latitude is None:
        raise HTTPException(status_code=422, detail={"code": "TRIP_ENDPOINTS_REQUIRED", "message": "Choose both departure and return points."})
    try:
        result = suggest_itineraries(db, payload)
        return rank_suggestions_with_gemini(db, payload, result, provider)
    except NoFeasiblePlan as error:
        raise HTTPException(status_code=422, detail={"code": error.code, "message": str(error), "diagnostics": error.diagnostics}) from error
    except UnsupportedTravelMode as error:
        raise HTTPException(status_code=422, detail={"code": "UNSUPPORTED_TRAVEL_MODE", "message": str(error)}) from error
    except RoutingConfigurationError as error:
        raise HTTPException(status_code=503, detail={"code": "ROUTING_NOT_CONFIGURED", "message": str(error)}) from error
    except RoutingProviderError as error:
        raise HTTPException(status_code=502, detail={"code": "ROUTING_PROVIDER_ERROR", "message": str(error)}) from error


@router.post("/itineraries/plan", response_model=PlanResponse)
def plan_itinerary(payload: PlanRequest, db: Session = Depends(get_db), user: User | None = Depends(require_user(P.ITINERARY_PLAN, optional=True))):
    _check_traveler(user)
    try:
        return PlannerService(db).plan(payload, user.id if user else None)
    except NoFeasiblePlan as error:
        raise HTTPException(status_code=422, detail={
            "code": error.code,
            "message": str(error),
            "diagnostics": error.diagnostics,
        }) from error
    except UnsupportedTravelMode as error:
        raise HTTPException(status_code=422, detail={"code": "UNSUPPORTED_TRAVEL_MODE", "message": str(error)}) from error
    except RoutingConfigurationError as error:
        raise HTTPException(status_code=503, detail={"code": "ROUTING_NOT_CONFIGURED", "message": str(error)}) from error
    except RoutingProviderError as error:
        raise HTTPException(status_code=502, detail={"code": "ROUTING_PROVIDER_ERROR", "message": str(error)}) from error


@router.post("/itineraries/preview", response_model=PlanPreviewResponse)
def preview_itinerary(payload: PlanRequest, db: Session = Depends(get_db), user: User | None = Depends(require_user(P.ITINERARY_PLAN, optional=True))):
    _check_traveler(user)
    try:
        return _create_preview(payload, db, user)
    except NoFeasiblePlan as error:
        raise HTTPException(status_code=422, detail={"code": error.code, "message": str(error)}) from error
    except UnsupportedTravelMode as error:
        raise HTTPException(status_code=422, detail={"code": "UNSUPPORTED_TRAVEL_MODE", "message": str(error)}) from error
    except RoutingConfigurationError as error:
        raise HTTPException(status_code=503, detail={"code": "ROUTING_NOT_CONFIGURED", "message": str(error)}) from error
    except RoutingProviderError as error:
        raise HTTPException(status_code=502, detail={"code": "ROUTING_PROVIDER_ERROR", "message": str(error)}) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail={"code": "SIGNING_SECRET_NOT_CONFIGURED", "message": str(error)}) from error


@router.post("/itineraries/confirm", response_model=PlanResponse)
def confirm_itinerary(payload: PlanConfirmationRequest, db: Session = Depends(get_db), user: User | None = Depends(require_user(P.ITINERARY_PLAN, optional=True))):
    _check_traveler(user)
    owner_id = user.id if user else None
    try:
        claims = verify_plan_preview_token(payload.confirmation_token, owner_id)
    except InvalidPlanPreviewToken as error:
        raise HTTPException(status_code=409, detail={
            "code": "PREVIEW_INVALID",
            "message": "The preview expired or is no longer valid. Please generate a fresh preview.",
        }) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail={"code": "SIGNING_SECRET_NOT_CONFIGURED", "message": str(error)}) from error
    if claims.get("request_fingerprint") != request_fingerprint(payload.plan):
        try:
            replacement = _create_preview(payload.plan, db, user)
        except NoFeasiblePlan as error:
            raise HTTPException(status_code=409, detail={"code": "PREVIEW_STALE", "message": str(error)}) from error
        except UnsupportedTravelMode as error:
            raise HTTPException(status_code=422, detail={"code": "UNSUPPORTED_TRAVEL_MODE", "message": str(error)}) from error
        except RoutingConfigurationError as error:
            raise HTTPException(status_code=503, detail={"code": "ROUTING_NOT_CONFIGURED", "message": str(error)}) from error
        except RoutingProviderError as error:
            raise HTTPException(status_code=502, detail={"code": "ROUTING_PROVIDER_ERROR", "message": str(error)}) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail={"code": "SIGNING_SECRET_NOT_CONFIGURED", "message": str(error)}) from error
        raise HTTPException(status_code=409, detail={
            "code": "PREVIEW_STALE",
            "message": "The request changed after preview. Review this updated itinerary and confirm it again.",
            "preview": replacement,
        })
    try:
        return PlannerService(db).plan(
            payload.plan,
            owner_id,
            persist=True,
            expected_plan_fingerprint=claims.get("plan_fingerprint"),
        )
    except PlanPreviewChanged as error:
        try:
            preview_id, token = issue_plan_preview_token(payload.plan, error.current_plan, owner_id)
        except RuntimeError as signing_error:
            raise HTTPException(status_code=503, detail={"code": "SIGNING_SECRET_NOT_CONFIGURED", "message": str(signing_error)}) from signing_error
        replacement = {"preview_id": preview_id, "confirmation_token": token, **error.current_plan}
        raise HTTPException(status_code=409, detail={
            "code": "PREVIEW_STALE",
            "message": "Availability or route data changed. Review this updated itinerary and confirm it again.",
            "preview": replacement,
        }) from error
    except NoFeasiblePlan as error:
        raise HTTPException(status_code=409, detail={"code": "PREVIEW_STALE", "message": str(error)}) from error
    except UnsupportedTravelMode as error:
        raise HTTPException(status_code=422, detail={"code": "UNSUPPORTED_TRAVEL_MODE", "message": str(error)}) from error
    except RoutingConfigurationError as error:
        raise HTTPException(status_code=503, detail={"code": "ROUTING_NOT_CONFIGURED", "message": str(error)}) from error
    except RoutingProviderError as error:
        raise HTTPException(status_code=502, detail={"code": "ROUTING_PROVIDER_ERROR", "message": str(error)}) from error


@router.get("/itineraries/{itinerary_id}", response_model=PlanResponse)
def get_itinerary(itinerary_id: str, db: Session = Depends(get_db), user: User | None = Depends(require_user(P.ITINERARY_READ, optional=True))):
    record = db.get(Itinerary, itinerary_id)
    if user is not None and user.role != "traveler":
        raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN", "message": "This itinerary view is for travelers."})
    if record and record.user_id and (user is None or user.id != record.user_id):
        raise HTTPException(status_code=403, detail={"code": "ITINERARY_FORBIDDEN", "message": "This itinerary belongs to another account."})
    try:
        result = PlannerService(db).get_itinerary(itinerary_id)
    except RoutingConfigurationError as error:
        raise HTTPException(status_code=503, detail={"code": "ROUTING_NOT_CONFIGURED", "message": str(error)}) from error
    except RoutingProviderError as error:
        raise HTTPException(status_code=502, detail={"code": "ROUTING_PROVIDER_ERROR", "message": str(error)}) from error
    if not result:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Itinerary not found"})
    return result


@router.get("/me/itineraries")
def list_my_itineraries(user: User = Depends(require_user(P.ITINERARY_LIST)), db: Session = Depends(get_db)):
    records = db.scalars(select(Itinerary).where(Itinerary.user_id == user.id).order_by(Itinerary.created_at.desc())).all()
    return [{"id": item.id, "planned_date": item.planned_date, "start_time": item.start_time,
             "return_deadline": item.return_deadline, "status": item.status, "estimated_cost_vnd": item.estimated_cost_vnd,
             "current_version": item.current_version, "share_enabled": bool(item.share_token)} for item in records]


@router.get("/itinerary-comparisons")
def compare_itineraries(first_id: str, second_id: str, user: User = Depends(require_user(P.ITINERARY_COMPARE)), db: Session = Depends(get_db)):
    if first_id == second_id:
        raise HTTPException(status_code=422, detail={"code": "SAME_ITINERARY", "message": "Choose two different itineraries."})
    records = {item.id: item for item in db.scalars(select(Itinerary).where(Itinerary.id.in_([first_id, second_id]))).all()}
    if len(records) != 2:
        raise HTTPException(status_code=404, detail={"code": "ITINERARY_NOT_FOUND", "message": "Both itineraries must exist."})
    if any(item.user_id != user.id for item in records.values()):
        raise HTTPException(status_code=403, detail={"code": "ITINERARY_FORBIDDEN", "message": "You may compare only your own itineraries."})
    left, right = records[first_id], records[second_id]
    def snapshot(item: Itinerary) -> dict:
        return {"id": item.id, "status": item.status, "estimated_cost_vnd": item.estimated_cost_vnd,
                "return_deadline": item.return_deadline or item.end_at, "stops": [
                    {"experience_id": stop.experience_id, "name": stop.experience.name,
                     "start_at": stop.start_at, "end_at": stop.end_at, "cost_vnd": stop.cost_vnd}
                    for stop in sorted(item.stops, key=lambda row: row.position)]}
    left_data, right_data = snapshot(left), snapshot(right)
    left_ids = [stop["experience_id"] for stop in left_data["stops"]]
    right_ids = [stop["experience_id"] for stop in right_data["stops"]]
    return {"first": left_data, "second": right_data,
            "cost_diff_vnd": right.estimated_cost_vnd - left.estimated_cost_vnd,
            "added_experience_ids": [item for item in right_ids if item not in left_ids],
            "removed_experience_ids": [item for item in left_ids if item not in right_ids],
            "order_changed": left_ids != right_ids,
            "return_deadline_diff_min": int(((right.return_deadline or right.end_at) - (left.return_deadline or left.end_at)).total_seconds() // 60)}


@router.get("/itineraries/{itinerary_id}/versions")
def itinerary_versions(itinerary_id: str, user: User = Depends(require_user(P.ITINERARY_VERSIONS)), db: Session = Depends(get_db)):
    itinerary = db.get(Itinerary, itinerary_id)
    if itinerary is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Itinerary not found."})
    _owner_only(itinerary, user)
    rows = db.scalars(select(ItineraryVersion).where(ItineraryVersion.itinerary_id == itinerary_id).order_by(ItineraryVersion.version_number)).all()
    experience_ids = {stop.get("experience_id") for row in rows for stop in row.stops_snapshot if stop.get("experience_id")}
    names = {item_id: (title, name) for item_id, title, name in db.execute(
        select(Experience.id, Experience.title, Experience.name).where(Experience.id.in_(experience_ids))
    ).all()} if experience_ids else {}
    return [{"version": row.version_number, "stops": [{**stop, "name": (names.get(stop.get("experience_id")) or (None, stop.get("experience_id")))[0] or (names.get(stop.get("experience_id")) or (None, stop.get("experience_id")))[1]} for stop in row.stops_snapshot], "total_cost_vnd": row.total_cost_vnd,
             "total_travel_time_s": row.total_travel_time_s, "created_at": row.created_at} for row in rows]


def _owner_only(itinerary: Itinerary, user: User) -> None:
    if itinerary.user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "ITINERARY_FORBIDDEN", "message": "This itinerary belongs to another account."})


@router.post("/itineraries/{itinerary_id}/share")
def create_share_link(itinerary_id: str, user: User = Depends(require_user(P.ITINERARY_SHARE)), db: Session = Depends(get_db)):
    itinerary = db.get(Itinerary, itinerary_id)
    if itinerary is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Itinerary not found."})
    _owner_only(itinerary, user)
    if itinerary.share_token is None:
        itinerary.share_token = secrets.token_urlsafe(32)
        db.commit()
    return {"share_url": f"/shared/{itinerary.share_token}", "share_token": itinerary.share_token}


@router.delete("/itineraries/{itinerary_id}/share", status_code=204)
def revoke_share_link(itinerary_id: str, user: User = Depends(require_user(P.ITINERARY_SHARE)), db: Session = Depends(get_db)):
    itinerary = db.get(Itinerary, itinerary_id)
    if itinerary is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Itinerary not found."})
    _owner_only(itinerary, user)
    itinerary.share_token = None
    db.commit()


@router.get("/shared/itineraries/{share_token}", response_model=PlanResponse, dependencies=[Depends(public('the unguessable share token is the credential'))])
def read_shared_itinerary(share_token: str, db: Session = Depends(get_db)):
    itinerary = db.scalar(select(Itinerary).where(Itinerary.share_token == share_token))
    if itinerary is None:
        raise HTTPException(status_code=404, detail={"code": "SHARE_LINK_NOT_FOUND", "message": "This share link is invalid or has been revoked."})
    return PlannerService(db).get_itinerary(itinerary.id)


@router.post("/itineraries/{itinerary_id}/feedback", status_code=201)
def submit_feedback(itinerary_id: str, payload: FeedbackLabelRequest, user: User = Depends(require_user(P.ITINERARY_FEEDBACK)), db: Session = Depends(get_db)):
    itinerary = db.get(Itinerary, itinerary_id)
    if itinerary is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Itinerary not found."})
    _owner_only(itinerary, user)
    if itinerary.end_at and itinerary.end_at.replace(tzinfo=itinerary.end_at.tzinfo or timezone.utc) > datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail={"code": "TRIP_NOT_FINISHED", "message": "Feedback is available after the itinerary has finished."})
    feedback = Feedback(id=secrets.token_hex(16), itinerary_id=itinerary.id, user_id=user.id,
                        rating=payload.rating, comment=payload.review_text)
    db.add(feedback)
    db.commit()
    return {"id": feedback.id, "itinerary_id": feedback.itinerary_id, "rating": feedback.rating,
            "comment": feedback.comment, "created_at": feedback.created_at}


@router.get("/itineraries/{itinerary_id}/feedback")
def list_feedback(itinerary_id: str, user: User = Depends(require_user(P.ITINERARY_FEEDBACK)), db: Session = Depends(get_db)):
    itinerary = db.get(Itinerary, itinerary_id)
    if itinerary is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Itinerary not found."})
    if itinerary.user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "ITINERARY_FORBIDDEN", "message": "Feedback is private."})
    rows = db.scalars(select(Feedback).where(Feedback.itinerary_id == itinerary_id).order_by(Feedback.created_at.desc())).all()
    return [{"id": row.id, "rating": row.rating, "comment": row.comment, "created_at": row.created_at} for row in rows]


@router.get("/notifications")
def my_notifications(user: User = Depends(require_user(P.NOTIFICATION_READ)), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Event, Itinerary, ItineraryStop, ExperienceSlot)
        .join(ExperienceSlot, Event.target_id == ExperienceSlot.id)
        .join(ItineraryStop, ItineraryStop.slot_id == ExperienceSlot.id)
        .join(Itinerary, Itinerary.id == ItineraryStop.itinerary_id)
        .where(Itinerary.user_id == user.id, Event.status == "active", Event.event_type == "SLOT_CANCELLED")
        .order_by(Event.created_at.desc()).limit(100)
    ).all()
    return [{"event_id": event.id, "itinerary_id": itinerary.id, "stop_id": stop.id,
             "slot_id": slot.id, "message": "Một ca trong lịch trình đã bị hủy.", "created_at": event.created_at}
            for event, itinerary, stop, slot in rows]
