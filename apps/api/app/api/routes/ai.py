import base64
import logging
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from app.adapters.routing.provider import RoutingConfigurationError, RoutingProviderError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.adapters.llm.provider import StructuredOutputProvider
from app.api.dependencies import get_llm_provider, get_db
from app.core.config import settings
from app.core.enums import normalize_intent_tag
from app.models.entities import Event, Evidence, Experience, ExperienceSlot, Feedback, IntentSimilarity, Itinerary, ItineraryStop, Provider, User
from app.prompts.registry import catalog
from app.schemas.ai import (
    ExperienceMetadata,
    ExperienceTagRequest,
    FeedbackLabelRequest,
    FeedbackTrainingSample,
    IntentSimilarityRequest,
    ProviderActionConfirmRequest,
    ProviderActionPreviewRequest,
    ProviderSlotAction,
    ReplanAcceptRequest,
    ReplanAdviceRequest,
    SimilarityScore,
    WeatherAdjustment,
    WeatherAdviceRequest,
)
from app.services.prompt_service import InvalidStructuredOutput, PromptRunner
from app.services.replanning_service import ReplanningService, aware
from app.services.itinerary_collaboration_hub import collaboration_hub
from app.services.planner_service import PlannerService
from app.services.evidence_service import REQUIRED_FIELDS, utc_now
from app.services.open_meteo_service import OpenMeteoUnavailable, current_conditions
from app.api.guards import public, require, require_user
from app.api.permissions import P


log = logging.getLogger(__name__)
router = APIRouter(tags=["AI workflows"])
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_DEVELOPMENT_SIGNING_SECRET = secrets.token_urlsafe(48)


@router.get("/api/ai/prompts", dependencies=[Depends(public('prompt manifest contains no secrets or user data'))])
def list_prompt_catalog():
    return {key: value for key, value in catalog.manifest.items() if key != "prompt_ids"} | {
        "prompt_ids": list(catalog.prompt_ids),
    }


def _not_found(message: str):
    raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": message})


def _load_slots(db: Session, slot_ids: list[str], lock: bool = False) -> list[ExperienceSlot]:
    if len(set(slot_ids)) != len(slot_ids):
        raise HTTPException(status_code=422, detail={"code": "DUPLICATE_SLOT_IDS", "message": "slot_ids must be unique."})
    slot_query = select(ExperienceSlot).where(ExperienceSlot.id.in_(slot_ids)).options(joinedload(ExperienceSlot.experience))
    if lock:
        slot_query = slot_query.with_for_update()
    slots = db.scalars(slot_query).all()
    if len(slots) != len(slot_ids):
        _not_found("One or more selected slots do not exist.")
    return sorted(slots, key=lambda slot: aware(slot.start_at))


def _provider_auth(db: Session, provider_id: str, access_key: str | None, user: User | None = None) -> Provider:
    provider = db.get(Provider, provider_id)
    if provider is None or not provider.is_active:
        _not_found("Provider not found or inactive.")
    if user is not None:
        if user.role == "provider" and user.provider_id == provider.id:
            return provider
        raise HTTPException(status_code=403, detail={"code": "PROVIDER_FORBIDDEN", "message": "This account cannot manage the selected provider."})
    if not settings.allow_provider_access_key:
        raise HTTPException(status_code=401, detail={"code": "PROVIDER_KEY_DISABLED", "message": "Provider access keys are disabled. Sign in as a provider user."})
    if not access_key or not provider.portal_access_key or not secrets.compare_digest(access_key, provider.portal_access_key):
        raise HTTPException(status_code=401, detail={"code": "PROVIDER_UNAUTHORIZED", "message": "A valid provider access key is required."})
    # Deprecated: providers should sign in. Kept for compatibility; every use is logged so callers can be found and migrated.
    log.warning("deprecated X-Provider-Access-Key used for provider %s; sign in as a provider user instead", provider.id)
    return provider


def _signing_secret() -> str:
    if settings.app_signing_secret:
        return settings.app_signing_secret
    if settings.app_env.lower() in {"development", "test"}:
        return _DEVELOPMENT_SIGNING_SECRET
    raise HTTPException(status_code=503, detail={"code": "SIGNING_SECRET_NOT_CONFIGURED", "message": "Set APP_SIGNING_SECRET before enabling provider confirmations."})


def _issue_confirmation_token(payload: dict[str, Any]) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")).decode("ascii").rstrip("=")
    signature = hmac.new(_signing_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    sig = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{body}.{sig}"


def _verify_confirmation_token(token: str) -> dict[str, Any]:
    try:
        body, supplied = token.split(".", 1)
        expected = base64.urlsafe_b64encode(
            hmac.new(_signing_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
        ).decode("ascii").rstrip("=")
        if not hmac.compare_digest(supplied, expected):
            raise ValueError("bad signature")
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        if not isinstance(payload, dict) or int(payload["expires_at_epoch"]) <= int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired")
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=400, detail={"code": "INVALID_CONFIRMATION_TOKEN", "message": "The confirmation token is invalid or expired; preview the action again."}) from error


@router.post("/api/experiences/{experience_id}/ai-tag", dependencies=[Depends(require(P.ADMIN_AI_TOOLS))])
def tag_experience(
    experience_id: str,
    payload: ExperienceTagRequest,
    db: Session = Depends(get_db),
    provider: StructuredOutputProvider = Depends(get_llm_provider),
):
    experience = db.scalar(select(Experience).where(Experience.id == experience_id).options(joinedload(Experience.poi)))
    if experience is None:
        _not_found("Experience not found.")
    result = PromptRunner(provider).run("EXPERIENCE_TAGGER", {
        "experience_id": experience.id,
        "name": experience.title or experience.name,
        "description": experience.description,
        "existing_intent_tags": experience.intent_tags or [],
        "existing_hands_on": experience.is_hands_on,
        "existing_is_indoor": experience.is_indoor,
        "poi_name": experience.poi.name,
        "additional_context": payload.additional_context,
    }, ExperienceMetadata)
    if result.experience_id != experience.id:
        raise InvalidStructuredOutput("EXPERIENCE_TAGGER changed the target experience_id.")
    experience.is_hands_on = result.is_hands_on
    experience.is_indoor = result.is_indoor
    experience.indoor = result.is_indoor
    experience.primary_intent = result.primary_intent
    experience.intent_tags = result.intent_tags
    experience.weather_sensitivity = result.weather_sensitivity
    experience.tagger_prompt_version = catalog.version
    db.commit()
    return {"experience_id": experience.id, "metadata": result.model_dump(), "prompt_version": catalog.version}


@router.post("/api/ai/intent-similarity", dependencies=[Depends(require(P.ADMIN_AI_TOOLS))])
def calculate_intent_similarity(
    payload: IntentSimilarityRequest,
    db: Session = Depends(get_db),
    provider: StructuredOutputProvider = Depends(get_llm_provider),
):
    if payload.experience_a_id == payload.experience_b_id:
        raise HTTPException(status_code=422, detail={"code": "SAME_EXPERIENCE", "message": "Two different experiences are required."})
    by_id = {item.id: item for item in db.scalars(
        select(Experience).where(Experience.id.in_([payload.experience_a_id, payload.experience_b_id]))
    ).all()}
    if len(by_id) != 2:
        _not_found("One or both experiences do not exist.")
    a, b = by_id[payload.experience_a_id], by_id[payload.experience_b_id]
    result = PromptRunner(provider).run("INTENT_SIMILARITY", {
        "activity_a": {"experience_id": a.id, "title": a.title or a.name, "description": a.description,
                       "intent_tags": a.intent_tags or [], "is_hands_on": a.is_hands_on, "primary_intent": a.primary_intent},
        "activity_b": {"experience_id": b.id, "title": b.title or b.name, "description": b.description,
                       "intent_tags": b.intent_tags or [], "is_hands_on": b.is_hands_on, "primary_intent": b.primary_intent},
    }, SimilarityScore)
    if (result.experience_a_id, result.experience_b_id) != (a.id, b.id):
        raise InvalidStructuredOutput("INTENT_SIMILARITY changed or swapped the supplied experience IDs.")
    tags_a = {normalize_intent_tag(tag) for tag in (a.intent_tags or [])}
    tags_b = {normalize_intent_tag(tag) for tag in (b.intent_tags or [])}
    tag_union = tags_a | tags_b
    actual_overlap = len(tags_a & tags_b) / len(tag_union) if tag_union else 0.0
    if abs(result.tag_overlap_score - actual_overlap) > 0.02:
        raise InvalidStructuredOutput("INTENT_SIMILARITY tag_overlap_score does not match the stored experience tags.")
    if result.can_substitute_purpose and result.final_score < 0.65:
        raise InvalidStructuredOutput("INTENT_SIMILARITY marked a score below 0.65 as purpose-substitutable.")
    left_id, right_id = sorted((a.id, b.id))
    row = db.get(IntentSimilarity, (left_id, right_id))
    if row is None:
        row = IntentSimilarity(experience_a_id=left_id, experience_b_id=right_id,
                               semantic_similarity=result.semantic_score, tag_overlap_score=result.tag_overlap_score,
                               final_score=result.final_score, can_substitute_purpose=result.can_substitute_purpose,
                               prompt_version=catalog.version, is_human_reviewed=False)
        db.add(row)
    else:
        row.semantic_similarity = result.semantic_score
        row.tag_overlap_score = result.tag_overlap_score
        row.final_score = result.final_score
        row.can_substitute_purpose = result.can_substitute_purpose
        row.prompt_version = catalog.version
        row.is_human_reviewed = False
    db.commit()
    return {"similarity": result.model_dump(), "stored_pair": [left_id, right_id], "prompt_version": catalog.version}


@router.post("/api/itineraries/{itinerary_id}/replan-advice")
def get_replan_advice(
    itinerary_id: str,
    payload: ReplanAdviceRequest,
    db: Session = Depends(get_db),
    provider: StructuredOutputProvider = Depends(get_llm_provider),
    user: User | None = Depends(require_user(P.REPLAN_ADVISE, optional=True)),
):
    itinerary = db.get(Itinerary, itinerary_id)
    if user is not None and user.role != "traveler":
        raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN", "message": "Replanning is a traveler feature."})
    if itinerary and itinerary.user_id and (user is None or user.id != itinerary.user_id):
        raise HTTPException(status_code=403, detail={"code": "ITINERARY_FORBIDDEN", "message": "This itinerary belongs to another account."})
    try:
        return ReplanningService(db, provider).advise(itinerary_id, payload.event_id)
    except LookupError as error:
        _not_found(str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail={"code": "REPLAN_NOT_AVAILABLE", "message": str(error)}) from error
    except RoutingConfigurationError as error:
        raise HTTPException(status_code=503, detail={"code": "ROUTING_NOT_CONFIGURED", "message": str(error)}) from error
    except RoutingProviderError as error:
        raise HTTPException(status_code=502, detail={"code": "ROUTING_PROVIDER_ERROR", "message": str(error)}) from error


@router.post("/api/itineraries/{itinerary_id}/replan-advice/accept")
def accept_replan(
    itinerary_id: str,
    payload: ReplanAcceptRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(require_user(P.REPLAN_ACCEPT, optional=True)),
):
    itinerary = db.get(Itinerary, itinerary_id)
    if itinerary is None:
        _not_found("Itinerary not found.")
    if user is not None and user.role != "traveler":
        raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN", "message": "Replanning is a traveler feature."})
    if itinerary.user_id and (user is None or user.id != itinerary.user_id):
        raise HTTPException(status_code=403, detail={"code": "ITINERARY_FORBIDDEN", "message": "This itinerary belongs to another account."})
    if itinerary.current_version != payload.base_version:
        raise HTTPException(status_code=409, detail={"code": "STALE_ITINERARY_VERSION", "message": "The itinerary changed after this advice. Request fresh advice before accepting."})
    try:
        result = ReplanningService(db, None).accept(
            itinerary_id, payload.event_id, payload.affected_stop_id,
            payload.candidate_experience_id, payload.candidate_slot_id, payload.proposal_code,
            expected_version=payload.base_version,
        )
        try:
            snapshot = PlannerService(db).get_itinerary(itinerary_id)
        except Exception:
            log.exception("could not create collaboration snapshot after accepting replan for %s", itinerary_id)
            snapshot = None
        collaboration_hub.broadcast_from_sync(itinerary_id, {
            "type": "itinerary_updated",
            "itinerary_id": itinerary_id,
            "current_version": result.get("current_version"),
            "itinerary": snapshot,
        })
        return result
    except LookupError as error:
        _not_found(str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail={"code": "REPLAN_NOT_AVAILABLE", "message": str(error)}) from error
    except RoutingConfigurationError as error:
        raise HTTPException(status_code=503, detail={"code": "ROUTING_NOT_CONFIGURED", "message": str(error)}) from error
    except RoutingProviderError as error:
        raise HTTPException(status_code=502, detail={"code": "ROUTING_PROVIDER_ERROR", "message": str(error)}) from error


@router.post("/api/providers/{provider_id}/slot-assistant/preview")
def preview_provider_slot_action(
    provider_id: str,
    payload: ProviderActionPreviewRequest,
    x_provider_access_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
    provider: StructuredOutputProvider = Depends(get_llm_provider),
    user: User | None = Depends(require_user(P.PROVIDER_SLOT_ASSIST, optional=True)),
):
    owner = _provider_auth(db, provider_id, x_provider_access_key, user)
    slots = _load_slots(db, payload.slot_ids)
    if any(slot.experience.provider_id != owner.id for slot in slots):
        raise HTTPException(status_code=403, detail={"code": "SLOT_OUTSIDE_PROVIDER", "message": "All selected slots must belong to this provider."})
    if any(slot.status == "cancelled" for slot in slots):
        raise HTTPException(status_code=409, detail={"code": "SLOT_ALREADY_CANCELLED", "message": "A cancelled slot cannot be changed through this assistant."})
    local_today = datetime.now(LOCAL_TZ).date()
    if len({aware(slot.start_at).astimezone(LOCAL_TZ).date() for slot in slots}) != 1:
        raise HTTPException(status_code=422, detail={"code": "SLOTS_MUST_SHARE_DATE", "message": "Selected slots must be from one local date."})
    action = PromptRunner(provider).run("PROVIDER_ASSISTANT", {
        "message": payload.message,
        "provider": {"provider_id": owner.id, "name": owner.name},
        "user_selected_slots": [{"slot_id": slot.id, "experience_id": slot.experience_id,
             "experience_title": slot.experience.title or slot.experience.name,
             "start_at": aware(slot.start_at).astimezone(LOCAL_TZ).isoformat(),
             "end_at": aware(slot.end_at).astimezone(LOCAL_TZ).isoformat(),
             "status": slot.status, "available_reported": slot.available_reported,
             "capacity_total": slot.capacity_total, "version": slot.version} for slot in slots],
        "today_local_date": local_today.isoformat(),
    }, ProviderSlotAction)
    if action.action == "CANCEL_SLOT" and action.new_status != "cancelled":
        raise InvalidStructuredOutput("CANCEL_SLOT must set new_status=cancelled.")
    if action.action in {"CANCEL_SLOT", "PAUSE_DAY"} and action.available_reported not in (None, 0):
        raise InvalidStructuredOutput("Cancellation actions cannot report a positive available capacity.")
    if action.action == "PAUSE_DAY":
        slot_dates = {aware(slot.start_at).astimezone(LOCAL_TZ).date() for slot in slots}
        if slot_dates != {local_today} or action.new_status != "cancelled":
            raise HTTPException(status_code=422, detail={"code": "PAUSE_DAY_SCOPE_INVALID", "message": "PAUSE_DAY can only cancel the explicitly selected slots for today in Ho Chi Minh City."})
        provider_today_slots = db.scalars(
            select(ExperienceSlot).join(Experience, Experience.id == ExperienceSlot.experience_id)
            .where(Experience.provider_id == owner.id)
        ).all()
        expected_ids = {slot.id for slot in provider_today_slots
                        if aware(slot.start_at).astimezone(LOCAL_TZ).date() == local_today and slot.status != "cancelled"}
        if expected_ids != {slot.id for slot in slots}:
            raise HTTPException(status_code=422, detail={"code": "PAUSE_DAY_INCOMPLETE_SCOPE", "message": "Include every not-yet-cancelled slot for this provider today, or choose the specific slots to cancel."})
    if action.action == "UPDATE_CAPACITY":
        if action.available_reported is None:
            raise InvalidStructuredOutput("UPDATE_CAPACITY requires available_reported.")
        if any(slot.capacity_total is not None and action.available_reported > slot.capacity_total for slot in slots):
            raise HTTPException(status_code=422, detail={"code": "CAPACITY_EXCEEDS_TOTAL", "message": "Reported availability cannot exceed a selected slot's total capacity."})
        expected_status = "full" if action.available_reported == 0 else "open"
        if action.new_status != expected_status:
            raise InvalidStructuredOutput("UPDATE_CAPACITY status must be full when count is zero and open otherwise.")
    if action.action != "UPDATE_CAPACITY" and action.new_status != "cancelled":
        raise InvalidStructuredOutput("Cancellation actions must set new_status=cancelled.")

    token = _issue_confirmation_token({
        "token_id": str(uuid4()), "provider_id": owner.id, "slot_ids": [slot.id for slot in slots],
        "versions": {slot.id: slot.version for slot in slots}, "action": action.action,
        "new_status": action.new_status, "available_reported": action.available_reported,
        "reason_note": action.reason_note, "prompt_version": catalog.version,
        "expires_at_epoch": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp()),
    })
    return {"action_preview": action.model_dump(), "target_slots": [{"slot_id": slot.id,
             "experience_title": slot.experience.title or slot.experience.name,
             "start_at": aware(slot.start_at).astimezone(LOCAL_TZ).isoformat(),
             "end_at": aware(slot.end_at).astimezone(LOCAL_TZ).isoformat(),
             "current_status": slot.status, "current_available_reported": slot.available_reported} for slot in slots],
            "prompt_version": catalog.version, "confirmation_token": token,
            "token_expires_in_seconds": 300, "requires_explicit_confirmation": True}


@router.post("/api/providers/{provider_id}/slot-assistant/confirm")
def confirm_provider_slot_action(
    provider_id: str,
    payload: ProviderActionConfirmRequest,
    x_provider_access_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
    user: User | None = Depends(require_user(P.PROVIDER_SLOT_ASSIST, optional=True)),
):
    owner = _provider_auth(db, provider_id, x_provider_access_key, user)
    claims = _verify_confirmation_token(payload.confirmation_token)
    if claims.get("provider_id") != owner.id:
        raise HTTPException(status_code=403, detail={"code": "TOKEN_PROVIDER_MISMATCH", "message": "This confirmation is not for the authenticated provider."})
    slots = _load_slots(db, claims.get("slot_ids", []), lock=True)
    if any(slot.experience.provider_id != owner.id for slot in slots):
        raise HTTPException(status_code=403, detail={"code": "SLOT_OUTSIDE_PROVIDER", "message": "A selected slot no longer belongs to this provider."})
    created_events = []
    for slot in slots:
        if slot.version != claims.get("versions", {}).get(slot.id):
            raise HTTPException(status_code=409, detail={"code": "SLOT_VERSION_CHANGED", "message": "Availability changed after preview; preview the action again."})
    action = claims.get("action")
    confirmed_at = utc_now()
    confirmation_expiry = payload.expires_at
    if action == "UPDATE_CAPACITY" and claims.get("new_status") == "open":
        if confirmation_expiry is None or confirmation_expiry.tzinfo is None or confirmation_expiry.utcoffset() is None:
            raise HTTPException(status_code=422, detail={"code": "FRESH_SLOT_CONFIRMATION_REQUIRED", "message": "Opening a slot requires a timezone-aware expires_at."})
        confirmation_expiry = confirmation_expiry.astimezone(timezone.utc)
        if confirmation_expiry <= confirmed_at or any(confirmation_expiry > aware(slot.start_at) for slot in slots):
            raise HTTPException(status_code=422, detail={"code": "INVALID_SLOT_EXPIRY", "message": "Expiry must be in the future and no later than each selected slot's start."})
    for slot in slots:
        if action in {"CANCEL_SLOT", "PAUSE_DAY"}:
            slot.status = "cancelled"
            slot.available_reported = 0
            event = Event(event_type="SLOT_CANCELLED", target_type="experience_slot", target_id=slot.id,
                          status="active", event_metadata={"reason_note": claims.get("reason_note", ""),
                          "action": action, "provider_confirmed": True, "prompt_version": claims.get("prompt_version")})
            db.add(event)
            created_events.append(event)
        elif action == "UPDATE_CAPACITY":
            slot.available_reported = claims["available_reported"]
            slot.status = claims["new_status"]
        else:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ACTION_TOKEN", "message": "Unknown provider action."})
        slot.confirmed_at = confirmed_at
        if slot.status == "open":
            slot.expires_at = confirmation_expiry
        slot.version += 1
        if slot.status == "open" and slot.expires_at:
            db.add(Evidence(
                id=str(uuid4()), source_uri=f"provider://{owner.id}/slots/{slot.id}",
                source_type="provider_confirmation", source_label=owner.name,
                notes="Authenticated provider confirmation via the two-step slot assistant.",
                submitted_by=user.id if user else None,
                target_type="slot", target_id=slot.id, target_revision=slot.version,
                fields_covered=sorted(REQUIRED_FIELDS["slot"]), observed_at=confirmed_at,
                expires_at=slot.expires_at, verification_status="verified",
                verified_by=user.id if user else owner.id, verified_at=confirmed_at,
            ))
    db.commit()
    return {"status": "confirmed", "provider_id": owner.id, "updated_slot_ids": [slot.id for slot in slots],
            "action": action, "prompt_version": claims.get("prompt_version"),
            "event_ids": [event.id for event in created_events]}


@router.post("/api/itineraries/{itinerary_id}/feedback/label", dependencies=[Depends(require(P.ADMIN_AI_TOOLS))])
def label_feedback(
    itinerary_id: str,
    payload: FeedbackLabelRequest,
    db: Session = Depends(get_db),
    provider: StructuredOutputProvider = Depends(get_llm_provider),
):
    itinerary = db.scalar(select(Itinerary).where(Itinerary.id == itinerary_id).options(
        selectinload(Itinerary.stops).joinedload(ItineraryStop.experience)
    ))
    if itinerary is None:
        _not_found("Itinerary not found.")
    facts = {"itinerary_id": itinerary.id, "target_intents": itinerary.target_intents or {},
             "budget_vnd": itinerary.budget_vnd, "estimated_cost_vnd": itinerary.estimated_cost_vnd,
             "return_deadline": aware(itinerary.return_deadline or itinerary.end_at).isoformat(),
             "stops": [{"title": stop.experience.title or stop.experience.name,
                        "intent_tags": stop.experience.intent_tags or [], "is_hands_on": stop.experience.is_hands_on,
                        "cost_vnd": stop.cost_vnd, "status": stop.status,
                        "departure_at": aware(stop.departure_at).isoformat()} for stop in itinerary.stops],
             "actual_feedback": {"review_text": payload.review_text, "rating": payload.rating}}
    result = PromptRunner(provider).run("FEEDBACK_LABELER", facts, FeedbackTrainingSample)
    if result.itinerary_id != itinerary.id:
        raise InvalidStructuredOutput("FEEDBACK_LABELER changed the itinerary_id.")
    feedback = db.scalar(select(Feedback).where(
        Feedback.itinerary_id == itinerary.id,
        Feedback.comment == payload.review_text,
        Feedback.rating == payload.rating,
        Feedback.labeler_prompt_version.is_(None),
    ).order_by(Feedback.created_at.desc()).with_for_update())
    if feedback is None:
        feedback = Feedback(itinerary_id=itinerary.id, rating=payload.rating, comment=payload.review_text)
        db.add(feedback)
    feedback.relevance_grade = result.relevance_grade
    feedback.rubric_justification_vi = result.rubric_justification_vi
    feedback.objective_achieved_ratio = result.objective_achieved_ratio
    feedback.is_usable_for_training = result.is_usable_for_training
    feedback.labeler_prompt_version = catalog.version
    db.commit()
    db.refresh(feedback)
    return {"feedback_id": feedback.id, "label": result.model_dump(), "prompt_version": catalog.version}


@router.post("/api/itineraries/{itinerary_id}/weather-advisory", dependencies=[Depends(require(P.ADMIN_AI_TOOLS))])
def weather_advisory(
    itinerary_id: str,
    payload: WeatherAdviceRequest,
    db: Session = Depends(get_db),
    provider: StructuredOutputProvider = Depends(get_llm_provider),
):
    itinerary = db.scalar(select(Itinerary).where(Itinerary.id == itinerary_id).options(
        selectinload(Itinerary.stops).joinedload(ItineraryStop.experience).joinedload(Experience.poi)
    ))
    if itinerary is None:
        _not_found("Itinerary not found.")
    outdoor_stops = [stop for stop in itinerary.stops if not stop.experience.is_indoor]
    result = PromptRunner(provider).run("WEATHER_AQI_ADVISOR", {
        "weather_data": {"temperature_c": payload.temperature_c, "rain_mm_per_hour": payload.rain_mm_per_hour,
                         "aqi_pm25": payload.aqi_pm25, "observed_at": payload.observed_at.isoformat(),
                         "source": "caller-provided observation; not independently verified"},
        "children_in_group": payload.children_in_group,
        "scheduled_outdoor_activities": [{"title": stop.experience.title or stop.experience.name,
                         "poi_name": stop.experience.poi.name, "experience_id": stop.experience_id,
                         "poi_id": stop.poi_id} for stop in outdoor_stops],
        "thresholds": {"heavy_rain_mm_per_hour": 10, "poor_aqi_pm25": 150},
        "flood_data_available": False,
    }, WeatherAdjustment)
    allowed_names = {stop.experience.title or stop.experience.name for stop in outdoor_stops}
    if not set(result.impacted_outdoor_activities).issubset(allowed_names):
        raise InvalidStructuredOutput("WEATHER_AQI_ADVISOR referenced an outdoor activity not present in this itinerary.")
    if payload.rain_mm_per_hour > 10 and (not result.indoor_priority_boost or result.weather_condition != "rainy"):
        raise InvalidStructuredOutput("Heavy rain must produce rainy status and an indoor priority boost.")
    if payload.rain_mm_per_hour > 10 and outdoor_stops and not allowed_names.issubset(set(result.impacted_outdoor_activities)):
        raise InvalidStructuredOutput("Heavy rain must identify each scheduled outdoor activity as impacted.")
    events = []
    impacted_names = set(result.impacted_outdoor_activities)
    if result.indoor_priority_boost or result.impacted_outdoor_activities:
        for stop in outdoor_stops:
            title = stop.experience.title or stop.experience.name
            if impacted_names and title not in impacted_names:
                continue
            event = Event(event_type="WEATHER_ALERT", target_type="poi", target_id=stop.poi_id,
                          valid_until=datetime.now(timezone.utc) + timedelta(hours=3), status="active",
                          event_metadata={"itinerary_id": itinerary.id, "experience_id": stop.experience_id,
                              "experience_title": title, "rain_mm_per_hour": payload.rain_mm_per_hour,
                              "aqi_pm25": payload.aqi_pm25, "temperature_c": payload.temperature_c,
                              "children_in_group": payload.children_in_group, "observed_at": payload.observed_at.isoformat(),
                              "prompt_version": catalog.version, "advisory_message_vi": result.advisory_message_vi,
                              "flood_inference_made": False})
            db.add(event)
            events.append(event)
    db.commit()
    event_ids = [event.id for event in events]
    return {"advisory": result.model_dump(), "prompt_version": catalog.version,
            "event_ids": event_ids,
            "impacted_experience_ids": [stop.experience_id for stop in outdoor_stops
                                         if (stop.experience.title or stop.experience.name) in impacted_names],
            "source_data_unverified": True,
            "flood_status_inferred": False}


@router.get("/api/itineraries/{itinerary_id}/weather-data", dependencies=[Depends(require(P.ADMIN_AI_TOOLS))])
def itinerary_weather_data(
    itinerary_id: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """Fetch live model context for the first outdoor stop without treating it as a flood observation."""
    response.headers["Cache-Control"] = "private, no-store"
    itinerary = db.scalar(select(Itinerary).where(Itinerary.id == itinerary_id).options(
        selectinload(Itinerary.stops).joinedload(ItineraryStop.poi),
        selectinload(Itinerary.stops).joinedload(ItineraryStop.experience),
    ))
    if itinerary is None:
        raise HTTPException(status_code=404, detail={"code": "ITINERARY_NOT_FOUND", "message": "Itinerary not found."})

    location_name = itinerary.city or "Ho Chi Minh City"
    latitude = longitude = None
    if itinerary.stops:
        outdoor_stops = [stop for stop in itinerary.stops if stop.experience and not stop.experience.is_indoor]
        stop = (outdoor_stops or itinerary.stops)[0]
        poi = stop.poi
        if poi is not None:
            latitude, longitude, location_name = poi.latitude, poi.longitude, poi.name
    if latitude is None or longitude is None:
        if itinerary.destination_latitude is not None and itinerary.destination_longitude is not None:
            latitude, longitude = itinerary.destination_latitude, itinerary.destination_longitude
        elif itinerary.origin_latitude is not None and itinerary.origin_longitude is not None:
            latitude, longitude = itinerary.origin_latitude, itinerary.origin_longitude
    if latitude is None or longitude is None:
        raise HTTPException(status_code=422, detail={
            "code": "ITINERARY_LOCATION_UNAVAILABLE",
            "message": "This itinerary has no stop or origin/destination coordinates for live weather.",
        })

    try:
        weather = current_conditions(latitude, longitude)
    except OpenMeteoUnavailable as error:
        raise HTTPException(status_code=502, detail={
            "code": "WEATHER_PROVIDER_UNAVAILABLE",
            "message": "Live weather data is temporarily unavailable. You can retry or enter a documented observation manually.",
        }) from error
    return {**weather, "location": {"name": location_name, "latitude": latitude, "longitude": longitude}}
