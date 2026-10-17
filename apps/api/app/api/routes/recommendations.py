from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, joinedload

from app.api.guards import require_user
from app.api.permissions import P
from app.db.session import get_db
from app.models.entities import Experience, RecommendationConsent, RecommendationInteraction, User
from app.services.behavior_experiment_ranker import (
    BehaviorExperimentUnavailable,
    behavior_experiment_ranker,
)
from app.schemas.recommendations import (
    CONSENT_VERSION,
    BehaviorExperimentRankRequest,
    RecommendationConsentRead,
    RecommendationConsentUpdate,
    RecommendationInteractionBatch,
)

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("/behavior-experiment/status")
def behavior_experiment_status(user: User = Depends(require_user(P.RECOMMENDATIONS_USE))):
    return behavior_experiment_ranker.status()


@router.post("/behavior-experiment/rank")
def rank_with_behavior_experiment(
    payload: BehaviorExperimentRankRequest,
    user: User = Depends(require_user(P.RECOMMENDATIONS_USE)),
    db: Session = Depends(get_db),
):
    status = behavior_experiment_ranker.status()
    if not status["available"]:
        raise HTTPException(status_code=404, detail={"code": "BEHAVIOR_EXPERIMENT_UNAVAILABLE", "message": "The experimental model is available only in local development."})

    consent = db.get(RecommendationConsent, user.id)
    if consent is None or not consent.personalization_enabled:
        raise HTTPException(status_code=403, detail={"code": "PERSONALIZATION_CONSENT_REQUIRED", "message": "Enable personal recommendations in your profile to try this model."})

    requested_ids = list(dict.fromkeys(payload.experience_ids))
    experiences = db.scalars(
        select(Experience)
        .options(joinedload(Experience.poi), joinedload(Experience.slots))
        .where(Experience.id.in_(requested_ids))
    ).unique().all()
    if len(experiences) != len(requested_ids):
        raise HTTPException(status_code=422, detail={"code": "UNKNOWN_EXPERIENCE_ID", "message": "Some Explore candidates are no longer available."})
    by_id = {experience.id: experience for experience in experiences}
    ordered_experiences = [by_id[experience_id] for experience_id in requested_ids]

    history_rows = db.scalars(
        select(RecommendationInteraction)
        .where(
            RecommendationInteraction.user_id == user.id,
            RecommendationInteraction.personalization_eligible.is_(True),
            RecommendationInteraction.event_type == "selected",
        )
        .order_by(RecommendationInteraction.created_at.desc())
        .limit(500)
    ).all()
    history = [
        {
            "candidate_snapshot": row.candidate_snapshot,
            "context_snapshot": row.context_snapshot,
        }
        for row in history_rows
    ]
    query = payload.model_dump(exclude={"experience_ids"})
    try:
        ranked = behavior_experiment_ranker.rank(ordered_experiences, query, history)
    except BehaviorExperimentUnavailable as error:
        raise HTTPException(status_code=503, detail={"code": "BEHAVIOR_EXPERIMENT_NOT_READY", "message": str(error)}) from error
    return {
        "model_version": status.get("model_version"),
        "dataset_status": status.get("dataset_status"),
        "warning": status.get("warning"),
        "score_type": "relative_ranking_score_not_probability",
        "ranked_candidates": ranked,
    }


def _consent_read(consent: RecommendationConsent | None) -> RecommendationConsentRead:
    if consent is None:
        return RecommendationConsentRead()
    return RecommendationConsentRead(
        personalization_enabled=consent.personalization_enabled,
        model_training_enabled=consent.model_training_enabled,
        admin_history_enabled=consent.admin_history_enabled,
        consent_version=consent.consent_version,
    )


@router.get("/consent", response_model=RecommendationConsentRead)
def read_recommendation_consent(
    user: User = Depends(require_user(P.RECOMMENDATIONS_USE)),
    db: Session = Depends(get_db),
):
    return _consent_read(db.get(RecommendationConsent, user.id))


@router.put("/consent", response_model=RecommendationConsentRead)
def update_recommendation_consent(
    payload: RecommendationConsentUpdate,
    user: User = Depends(require_user(P.RECOMMENDATIONS_USE)),
    db: Session = Depends(get_db),
):
    consent = db.get(RecommendationConsent, user.id)
    if consent is None:
        consent = RecommendationConsent(user_id=user.id)
        db.add(consent)

    consent.personalization_enabled = payload.personalization_enabled
    consent.model_training_enabled = payload.model_training_enabled
    if payload.admin_history_enabled is not None:
        consent.admin_history_enabled = payload.admin_history_enabled
    consent.consent_version = CONSENT_VERSION
    consent.consented_at = datetime.now(timezone.utc) if (
        payload.personalization_enabled or payload.model_training_enabled or consent.admin_history_enabled
    ) else None

    if not payload.model_training_enabled:
        db.execute(
            update(RecommendationInteraction)
            .where(RecommendationInteraction.user_id == user.id)
            .values(model_training_eligible=False)
        )
    if not payload.personalization_enabled:
        db.execute(
            update(RecommendationInteraction)
            .where(RecommendationInteraction.user_id == user.id)
            .values(personalization_eligible=False)
        )
    if not consent.admin_history_enabled:
        db.execute(
            update(RecommendationInteraction)
            .where(RecommendationInteraction.user_id == user.id)
            .values(admin_history_eligible=False)
        )
    if not payload.personalization_enabled and not payload.model_training_enabled and not consent.admin_history_enabled:
        db.execute(delete(RecommendationInteraction).where(RecommendationInteraction.user_id == user.id))

    db.commit()
    db.refresh(consent)
    return _consent_read(consent)


@router.post("/interactions")
def record_recommendation_interactions(
    payload: RecommendationInteractionBatch,
    user: User = Depends(require_user(P.RECOMMENDATIONS_USE)),
    db: Session = Depends(get_db),
):
    consent = db.get(RecommendationConsent, user.id)
    if consent is None or not (
        consent.personalization_enabled or consent.model_training_enabled or consent.admin_history_enabled
    ):
        return {"accepted": 0, "status": "consent_required"}

    experience_ids = {event.experience_id for event in payload.events}
    experiences = db.scalars(
        select(Experience)
        .options(joinedload(Experience.poi))
        .where(Experience.id.in_(experience_ids))
    ).all()
    experiences_by_id = {experience.id: experience for experience in experiences}

    # Ignore unknown IDs without persisting client-supplied candidate details.
    event_ids = [str(event.event_id) for event in payload.events]
    existing_ids = set(db.scalars(
        select(RecommendationInteraction.id).where(
            RecommendationInteraction.user_id == user.id,
            RecommendationInteraction.id.in_(event_ids),
        )
    ).all())
    request_ids = {str(event.request_id) for event in payload.events}
    existing_keys = {tuple(row) for row in db.execute(
        select(
            RecommendationInteraction.request_id,
            RecommendationInteraction.experience_id,
            RecommendationInteraction.event_type,
        ).where(
            RecommendationInteraction.user_id == user.id,
            RecommendationInteraction.request_id.in_(request_ids),
        )
    ).all()}

    accepted = 0
    seen_event_ids = set(existing_ids)
    seen_event_keys = set(existing_keys)
    for event in payload.events:
        experience = experiences_by_id.get(event.experience_id)
        event_id = str(event.event_id)
        event_key = (str(event.request_id), event.experience_id, event.event_type)
        if experience is None or event_id in seen_event_ids or event_key in seen_event_keys:
            continue
        candidate_snapshot = {
            "experience_id": experience.id,
            "intent_tags": experience.intent_tags or [],
            "primary_intent": experience.primary_intent,
            "price_vnd": experience.price_vnd,
            "price_basis": experience.price_basis,
            "duration_min": experience.duration_min,
            "is_hands_on": experience.is_hands_on,
            "is_indoor": experience.is_indoor,
            "verification_status": experience.verification_status,
            "poi_category": experience.poi.category,
            "district": experience.poi.district,
            "data_revision": experience.data_revision,
        }
        db.add(RecommendationInteraction(
            id=event_id,
            user_id=user.id,
            request_id=str(event.request_id),
            experience_id=experience.id,
            event_type=event.event_type,
            position=event.position,
            context_snapshot=event.context.model_dump(exclude_none=True),
            candidate_snapshot=candidate_snapshot,
            personalization_eligible=consent.personalization_enabled,
            model_training_eligible=consent.model_training_enabled,
            admin_history_eligible=consent.admin_history_enabled,
            consent_version=consent.consent_version,
        ))
        seen_event_ids.add(event_id)
        seen_event_keys.add(event_key)
        accepted += 1

    db.commit()
    return {"accepted": accepted, "status": "recorded"}
