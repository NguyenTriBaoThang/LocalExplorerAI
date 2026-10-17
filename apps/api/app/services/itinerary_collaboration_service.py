"""Owner-approved collaboration for itinerary stop lists."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.enums import ItineraryStatus, PriceBasis, normalize_intent_tag
from app.core.pilot_area import PILOT_DISTRICT
from app.models.entities import (
    Booking,
    Experience,
    ExperienceSlot,
    Itinerary,
    ItineraryEditProposal,
    ItineraryStop,
    ItineraryVersion,
    User,
)
from app.repositories.experience_repository import ExperienceRepository
from app.services.availability_service import AvailabilityService
from app.services.planner_service import PlannerService, as_aware
from app.services.routing_service import RoutingService
from app.adapters.routing.provider import NoRouteFound


LIVE_BOOKING_STATUSES = (
    "pending_provider",
    "awaiting_payment",
    "confirmed",
    "cancellation_requested",
)


class CollaborationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class _ProposalExpired(Exception):
    """The persisted proposal no longer fits current itinerary/catalog facts."""


@dataclass(frozen=True)
class _CandidateStop:
    experience: Experience
    slot: ExperienceSlot
    cost_vnd: int
    travel_before_min: int


def _not_found() -> CollaborationError:
    return CollaborationError("ITINERARY_NOT_FOUND", "The itinerary or collaboration invite was not found.", 404)


def _require_traveler(user: User) -> None:
    if user.role != "traveler" or not user.is_active:
        raise CollaborationError("TRAVELER_ACCOUNT_REQUIRED", "An active traveler account is required.", 403)


def _require_owner(itinerary: Itinerary, owner: User) -> None:
    _require_traveler(owner)
    if itinerary.user_id != owner.id:
        raise CollaborationError("ITINERARY_FORBIDDEN", "Only the itinerary owner can manage collaboration.", 403)


def _load_itinerary(db: Session, itinerary_id: str, *, lock: bool = False) -> Itinerary:
    query = select(Itinerary).where(Itinerary.id == itinerary_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    itinerary = db.scalar(query)
    if itinerary is None:
        raise _not_found()
    return itinerary


def _load_stops(db: Session, itinerary_id: str, *, lock: bool = False) -> list[ItineraryStop]:
    query = select(ItineraryStop)
    if lock:
        query = query.with_for_update(of=ItineraryStop)
    return list(db.scalars(
        query
        .where(ItineraryStop.itinerary_id == itinerary_id)
        .options(joinedload(ItineraryStop.experience).joinedload(Experience.poi), joinedload(ItineraryStop.slot))
        .order_by(ItineraryStop.stop_order)
    ).all())


def proposal_summary(proposal: ItineraryEditProposal) -> dict:
    return {
        "id": proposal.id,
        "itinerary_id": proposal.itinerary_id,
        "proposer_id": proposal.proposer_id,
        "proposer_name": proposal.proposer.display_name if proposal.proposer else None,
        "base_version": proposal.base_version,
        "proposed_stops": proposal.proposed_stops,
        "status": proposal.status,
        "reviewed_by": proposal.reviewed_by,
        "reviewer_name": proposal.reviewer.display_name if proposal.reviewer else None,
        "created_at": proposal.created_at,
        "reviewed_at": proposal.reviewed_at,
    }


def create_invite(db: Session, itinerary_id: str, owner: User) -> str:
    itinerary = _load_itinerary(db, itinerary_id, lock=True)
    _require_owner(itinerary, owner)
    token = secrets.token_urlsafe(32)
    itinerary.collaboration_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db.commit()
    return token


def revoke_invite(db: Session, itinerary_id: str, owner: User) -> None:
    itinerary = _load_itinerary(db, itinerary_id, lock=True)
    _require_owner(itinerary, owner)
    itinerary.collaboration_token_hash = None
    db.commit()


def find_invite_itinerary(db: Session, token: str, *, lock: bool = False) -> Itinerary:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    query = select(Itinerary).where(Itinerary.collaboration_token_hash == digest)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    itinerary = db.scalar(query)
    if itinerary is None:
        raise CollaborationError("COLLABORATION_INVITE_NOT_FOUND", "This collaboration invite is invalid or has been revoked.", 404)
    return itinerary


def load_invite(db: Session, token: str) -> tuple[Itinerary, dict]:
    itinerary = find_invite_itinerary(db, token)
    snapshot = PlannerService(db).get_itinerary(itinerary.id)
    if snapshot is None:
        raise _not_found()
    protected_stop_ids = set(db.scalars(
        select(ItineraryStop.id).where(
            ItineraryStop.itinerary_id == itinerary.id,
            or_(ItineraryStop.is_locked.is_(True), ItineraryStop.locked.is_(True)),
        )
    ).all())
    active_booking_stop_ids = set(db.scalars(
        select(Booking.itinerary_stop_id).where(
            Booking.itinerary_id == itinerary.id,
            Booking.itinerary_stop_id.is_not(None),
            Booking.status.in_(LIVE_BOOKING_STATUSES),
        )
    ).all())
    for stop in snapshot.get("stops", []):
        stop["locked"] = bool(stop.get("id") in protected_stop_ids or stop.get("id") in active_booking_stop_ids)
    return itinerary, snapshot


def list_proposals(db: Session, itinerary_id: str) -> list[ItineraryEditProposal]:
    return list(db.scalars(
        select(ItineraryEditProposal)
        .where(ItineraryEditProposal.itinerary_id == itinerary_id)
        .options(selectinload(ItineraryEditProposal.proposer), selectinload(ItineraryEditProposal.reviewer))
        .order_by(ItineraryEditProposal.created_at.desc(), ItineraryEditProposal.id.desc())
    ).unique().all())


def _validate_stop_pairs(proposed_stops: list[dict]) -> list[tuple[str, str]]:
    if not isinstance(proposed_stops, list) or not 1 <= len(proposed_stops) <= 6:
        raise CollaborationError("INVALID_PROPOSED_STOPS", "A proposal must contain between one and six stops.", 422)
    pairs: list[tuple[str, str]] = []
    experience_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    for index, item in enumerate(proposed_stops):
        if not isinstance(item, dict):
            raise CollaborationError("INVALID_PROPOSED_STOPS", f"Stop {index + 1} must be an object.", 422)
        experience_id, slot_id = item.get("experience_id"), item.get("slot_id")
        if not isinstance(experience_id, str) or not experience_id or not isinstance(slot_id, str) or not slot_id:
            raise CollaborationError("INVALID_PROPOSED_STOPS", f"Stop {index + 1} needs an experience and time slot.", 422)
        pair = (experience_id, slot_id)
        if pair in seen_pairs or experience_id in experience_ids:
            raise CollaborationError("DUPLICATE_PROPOSED_STOP", "An experience can appear only once in a proposal.", 422)
        pairs.append(pair)
        seen_pairs.add(pair)
        experience_ids.add(experience_id)
    return pairs


def _check_locked_stops(current: list[ItineraryStop], pairs: list[tuple[str, str]]) -> None:
    locked_pairs = [(stop.experience_id, stop.slot_id) for stop in current if stop.is_locked or stop.locked]
    proposed_locked_order = [pair for pair in pairs if pair in set(locked_pairs)]
    if len(proposed_locked_order) != len(locked_pairs) or proposed_locked_order != locked_pairs:
        raise CollaborationError("LOCKED_STOPS_CHANGED", "Locked stops must remain in the same relative order and keep their experience and slot.", 422)


def submit_proposal(
    db: Session,
    itinerary_id: str,
    proposer: User,
    base_version: int,
    proposed_stops: list[dict],
    invite_token: str,
) -> ItineraryEditProposal:
    _require_traveler(proposer)
    # Serialize proposal submission with invite rotation/revocation so a command
    # that began before the link was revoked cannot commit after the revocation.
    itinerary = _load_itinerary(db, itinerary_id, lock=True)
    expected_hash = hashlib.sha256(invite_token.encode("utf-8")).hexdigest()
    if itinerary.collaboration_token_hash != expected_hash:
        raise CollaborationError("COLLABORATION_INVITE_NOT_FOUND", "This collaboration invite is invalid or has been revoked.", 404)
    if itinerary.current_version != base_version:
        raise CollaborationError("STALE_ITINERARY_VERSION", "The itinerary changed. Reload it before proposing edits.", 409)
    pairs = _validate_stop_pairs(proposed_stops)
    current = _load_stops(db, itinerary.id)
    _check_locked_stops(current, pairs)

    slot_pairs = set(db.execute(
        select(ExperienceSlot.experience_id, ExperienceSlot.id)
        .join(Experience, Experience.id == ExperienceSlot.experience_id)
        .where(ExperienceSlot.id.in_([slot_id for _, slot_id in pairs]))
    ).all())
    if any(pair not in slot_pairs for pair in pairs):
        raise CollaborationError("INVALID_EXPERIENCE_SLOT", "Every proposed time slot must belong to its experience.", 422)

    proposal = ItineraryEditProposal(
        itinerary_id=itinerary.id,
        proposer_id=proposer.id,
        base_version=base_version,
        proposed_stops=[{"experience_id": experience_id, "slot_id": slot_id} for experience_id, slot_id in pairs],
        status="pending",
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


def _build_candidates(
    db: Session,
    itinerary: Itinerary,
    pairs: list[tuple[str, str]],
    preserved_booking_pairs: set[tuple[str, str]],
) -> tuple[list[_CandidateStop], int, bool]:
    repository = ExperienceRepository(db)
    availability = AvailabilityService()
    routing = RoutingService(db=db)
    start_at = as_aware(itinerary.start_time or itinerary.start_at)
    deadline = as_aware(itinerary.return_deadline or itinerary.end_at)
    if deadline <= start_at or start_at < datetime.now(timezone.utc):
        raise _ProposalExpired("The trip window is no longer valid.")

    experiences = repository.list_experiences(
        district=PILOT_DISTRICT,
        slot_start_at=start_at,
        slot_end_at=deadline,
    )
    experience_by_id = {experience.id: experience for experience in experiences}

    mode = {"motorcycle": "motorcycle", "car": "driving"}.get(itinerary.travel_mode, itinerary.travel_mode)
    candidates: list[_CandidateStop] = []
    total_cost = 0
    total_travel_min = 0
    unknown_capacity = False
    cursor = start_at
    previous_poi: tuple[float, float] | None = None
    origin = None
    if itinerary.origin_latitude is not None and itinerary.origin_longitude is not None:
        origin = (itinerary.origin_latitude, itinerary.origin_longitude)

    for experience_id, slot_id in pairs:
        experience = experience_by_id.get(experience_id)
        if experience is None:
            raise _ProposalExpired("A proposed experience is no longer available in the catalog.")
        slot = next((item for item in experience.slots if item.id == slot_id), None)
        if slot is None:
            raise _ProposalExpired("A proposed time slot is no longer available in the catalog.")
        slot_start, slot_end = as_aware(slot.start_at), as_aware(slot.end_at)
        if slot_start < start_at or slot_end > deadline or slot_end <= slot_start:
            raise _ProposalExpired("A proposed time slot falls outside the trip window.")
        preserved_booking = (experience_id, slot_id) in preserved_booking_pairs
        if preserved_booking:
            if slot.status in {"unavailable", "cancelled"}:
                raise _ProposalExpired("A booked time slot is no longer available.")
        else:
            if not availability.can_fit(slot, itinerary.group_size):
                raise _ProposalExpired("A proposed time slot no longer has enough reported capacity.")
            if experience.verification_status == "verified" and not repository.is_fresh_slot(slot):
                raise _ProposalExpired("A proposed time slot's verified availability evidence has expired.")

        travel_before = 0
        if previous_poi is not None:
            try:
                travel_before = routing.get_route(previous_poi, (experience.poi.latitude, experience.poi.longitude), mode).duration_min
            except NoRouteFound as error:
                raise _ProposalExpired("The route between proposed stops is no longer feasible.") from error
        elif origin is not None:
            try:
                travel_before = routing.get_route(origin, (experience.poi.latitude, experience.poi.longitude), mode).duration_min
            except NoRouteFound as error:
                raise _ProposalExpired("The route from the trip origin is no longer feasible.") from error

        if slot_start < cursor + timedelta(minutes=travel_before):
            raise _ProposalExpired("The proposed stop order does not fit the available travel time.")
        total_travel_min += travel_before
        cost = experience.price_vnd * itinerary.group_size if experience.price_basis == PriceBasis.PER_PERSON.value else experience.price_vnd
        total_cost += cost
        if total_cost > itinerary.budget_vnd:
            raise _ProposalExpired("The proposed stops exceed the trip budget.")
        unknown_capacity = unknown_capacity or (not preserved_booking and not availability.is_capacity_known(slot))
        candidates.append(_CandidateStop(experience, slot, cost, travel_before))
        previous_poi = (experience.poi.latitude, experience.poi.longitude)
        cursor = slot_end

    if candidates and itinerary.destination_latitude is not None and itinerary.destination_longitude is not None:
        try:
            final_leg = routing.get_route(
                previous_poi,
                (itinerary.destination_latitude, itinerary.destination_longitude),
                mode,
            )
        except NoRouteFound as error:
            raise _ProposalExpired("The route back to the trip destination is no longer feasible.") from error
        if cursor + timedelta(minutes=final_leg.duration_min) > deadline:
            raise _ProposalExpired("The last stop no longer leaves enough time to return by the trip deadline.")
        total_travel_min += final_leg.duration_min
    elif cursor > deadline:
        raise _ProposalExpired("The proposed stops exceed the trip deadline.")

    return candidates, total_travel_min * 60, unknown_capacity


def _mark_stale(db: Session, proposal: ItineraryEditProposal, owner: User, message: str, itinerary: Itinerary) -> dict:
    proposal.status = "stale"
    proposal.reviewed_by = owner.id
    proposal.reviewer = owner
    proposal.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "itinerary_id": itinerary.id,
        "current_version": itinerary.current_version,
        "proposal": proposal_summary(proposal),
        "error": message,
    }


def review_proposal(
    db: Session,
    itinerary_id: str,
    owner: User,
    proposal_id: str,
    decision: Literal["approve", "reject"],
    invite_token: str | None = None,
) -> dict:
    _require_traveler(owner)
    itinerary = _load_itinerary(db, itinerary_id, lock=True)
    if invite_token is not None:
        expected_hash = hashlib.sha256(invite_token.encode("utf-8")).hexdigest()
        if itinerary.collaboration_token_hash != expected_hash:
            raise CollaborationError("COLLABORATION_INVITE_NOT_FOUND", "This collaboration invite is invalid or has been revoked.", 404)
    _require_owner(itinerary, owner)
    proposal = db.scalar(
        select(ItineraryEditProposal)
        .where(ItineraryEditProposal.id == proposal_id, ItineraryEditProposal.itinerary_id == itinerary.id)
        .options(selectinload(ItineraryEditProposal.proposer), selectinload(ItineraryEditProposal.reviewer))
        .with_for_update()
    )
    if proposal is None:
        raise CollaborationError("PROPOSAL_NOT_FOUND", "This itinerary proposal was not found.", 404)
    if proposal.status != "pending":
        raise CollaborationError("PROPOSAL_ALREADY_REVIEWED", "This proposal has already been reviewed.", 409)
    if decision not in {"approve", "reject"}:
        raise CollaborationError("INVALID_PROPOSAL_DECISION", "Choose approve or reject.", 422)

    if decision == "reject":
        proposal.status = "rejected"
        proposal.reviewed_by = owner.id
        proposal.reviewer = owner
        proposal.reviewed_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "itinerary_id": itinerary.id,
            "current_version": itinerary.current_version,
            "proposal": proposal_summary(proposal),
        }

    if proposal.base_version != itinerary.current_version:
        return _mark_stale(db, proposal, owner, "The itinerary changed after this proposal was submitted.", itinerary)

    current = _load_stops(db, itinerary.id, lock=True)
    old_by_pair = {(stop.experience_id, stop.slot_id): stop for stop in current}
    live_booking_stop_ids = set(db.scalars(
        select(Booking.itinerary_stop_id).where(
            Booking.itinerary_stop_id.in_([stop.id for stop in current]),
            Booking.status.in_(LIVE_BOOKING_STATUSES),
        )
    ).all()) if current else set()
    live_booking_pairs = {pair for pair, stop in old_by_pair.items() if stop.id in live_booking_stop_ids}
    proposed_pairs: list[tuple[str, str]] = []
    try:
        proposed_pairs = _validate_stop_pairs(proposal.proposed_stops)
        _check_locked_stops(current, proposed_pairs)
        if live_booking_stop_ids - {old_by_pair[pair].id for pair in proposed_pairs if pair in old_by_pair}:
            return _mark_stale(db, proposal, owner, "A stop with an active booking cannot be removed.", itinerary)
        candidates, total_travel_time_s, unknown_capacity = _build_candidates(
            db, itinerary, proposed_pairs, preserved_booking_pairs=live_booking_pairs & set(proposed_pairs)
        )
    except CollaborationError as error:
        return _mark_stale(db, proposal, owner, error.message, itinerary)
    except _ProposalExpired as error:
        return _mark_stale(db, proposal, owner, str(error), itinerary)
    except Exception:
        db.rollback()
        raise

    try:
        base_version = itinerary.current_version
        max_order = max((stop.stop_order for stop in current), default=0)
        temporary_start = max(max_order, 0) + len(current) + 1
        for index, stop in enumerate(current, start=1):
            stop.stop_order = temporary_start + index
        db.flush()

        retained_pairs = set(proposed_pairs)
        for stop in current:
            if (stop.experience_id, stop.slot_id) not in retained_pairs:
                db.delete(stop)

        now_stops: list[ItineraryStop] = []
        candidate_by_pair = {(item.experience.id, item.slot.id): item for item in candidates}
        for order, pair in enumerate(proposed_pairs, start=1):
            candidate = candidate_by_pair[pair]
            existing = old_by_pair.get(pair)
            if existing is None:
                stop = ItineraryStop(
                    id=str(uuid4()),
                    itinerary_id=itinerary.id,
                    experience_id=candidate.experience.id,
                    slot_id=candidate.slot.id,
                    poi_id=candidate.experience.poi_id,
                    stop_order=order,
                    position=order,
                    arrival_at=as_aware(candidate.slot.start_at),
                    start_at=as_aware(candidate.slot.start_at),
                    departure_at=as_aware(candidate.slot.end_at),
                    end_at=as_aware(candidate.slot.end_at),
                    wait_duration_min=0,
                    activity_duration_min=candidate.experience.duration_min,
                    cost_vnd=candidate.cost_vnd,
                    status="planned",
                    is_locked=False,
                    locked=False,
                )
                db.add(stop)
            else:
                existing.stop_order = order
                existing.position = order
                if existing.id not in live_booking_stop_ids and not (existing.is_locked or existing.locked):
                    existing.experience = candidate.experience
                    existing.slot = candidate.slot
                    existing.experience_id = candidate.experience.id
                    existing.slot_id = candidate.slot.id
                    existing.poi_id = candidate.experience.poi_id
                    existing.arrival_at = as_aware(candidate.slot.start_at)
                    existing.start_at = as_aware(candidate.slot.start_at)
                    existing.departure_at = as_aware(candidate.slot.end_at)
                    existing.end_at = as_aware(candidate.slot.end_at)
                    existing.wait_duration_min = 0
                    existing.activity_duration_min = candidate.experience.duration_min
                    existing.cost_vnd = candidate.cost_vnd
                    existing.status = "planned"
                stop = existing
            now_stops.append(stop)

        itinerary.estimated_cost_vnd = sum(item.cost_vnd for item in candidates)
        itinerary.current_version = base_version + 1
        itinerary.version = itinerary.current_version
        itinerary.status = ItineraryStatus.TENTATIVE.value if unknown_capacity else ItineraryStatus.FEASIBLE.value
        proposal.status = "approved"
        proposal.reviewed_by = owner.id
        proposal.reviewer = owner
        proposal.reviewed_at = datetime.now(timezone.utc)
        intent_weights = itinerary.target_intents or itinerary.constraints.get("intent_weights", {})
        requested_intents = {tag for tag, weight in intent_weights.items() if weight > 0}
        provided_intents = {
            normalize_intent_tag(tag)
            for item in candidates
            for tag in (item.experience.intent_tags or [])
        }
        preserved_ratio = (
            sum(normalize_intent_tag(tag) in provided_intents for tag in requested_intents) / len(requested_intents)
            if requested_intents else 1.0
        )
        version_snapshot = [{
            "stop_id": stop.id,
            "stop_order": stop.stop_order,
            "poi_id": stop.poi_id,
            "experience_id": stop.experience_id,
            "slot_id": stop.slot_id,
            "arrival_at": as_aware(stop.arrival_at).isoformat(),
            "departure_at": as_aware(stop.departure_at).isoformat(),
            "cost_vnd": stop.cost_vnd,
            "is_locked": stop.is_locked,
        } for stop in now_stops]
        db.add(ItineraryVersion(
            itinerary_id=itinerary.id,
            version_number=itinerary.current_version,
            stops_snapshot=version_snapshot,
            total_cost_vnd=itinerary.estimated_cost_vnd,
            total_travel_time_s=total_travel_time_s,
            preserved_intents_ratio=preserved_ratio,
        ))
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "itinerary_id": itinerary.id,
        "current_version": itinerary.current_version,
        "status": itinerary.status,
        "proposal": proposal_summary(proposal),
    }
