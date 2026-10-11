from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.adapters.llm.provider import StructuredOutputProvider
from app.core.config import settings
from app.core.enums import ItineraryStatus, PriceBasis, normalize_intent_tag
from app.models.entities import (
    DecisionLog,
    Event,
    Experience,
    ExperienceSlot,
    IntentSimilarity,
    Itinerary,
    ItineraryStop,
    ItineraryVersion,
    POI,
)
from app.prompts.registry import catalog
from app.schemas.ai import ReplanProposal, ReplanProposals, XAIExplanation
from app.services.availability_service import AvailabilityService
from app.services.evidence_service import entity_is_operationally_verified, slot_is_operationally_verified
from app.services.ml_ranker_service import MLRankerUnavailable, ranker_service
from app.services.prompt_service import InvalidStructuredOutput, PromptRunner
from app.services.routing_service import RoutingService

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@dataclass
class ReplanCandidate:
    experience: Experience
    slot: ExperienceSlot
    cost_vnd: int
    cost_diff_vnd: int
    travel_time_diff_min: int
    eta_min: int
    preserved_intents: list[str]
    lost_intents: list[str]
    ranking_score: float
    similarity_source: str
    code: str

    def prompt_dict(self, return_time: str) -> dict[str, Any]:
        return {
            "code": self.code,
            "candidate_experience_id": self.experience.id,
            "candidate_slot_id": self.slot.id,
            "title": self.experience.title or self.experience.name,
            "description": self.experience.description,
            "intent_tags": self.experience.intent_tags or [],
            "is_hands_on": self.experience.is_hands_on,
            "is_indoor": self.experience.is_indoor,
            "duration_min": self.experience.duration_min,
            "price_vnd": self.experience.price_vnd,
            "cost_vnd_for_group": self.cost_vnd,
            "cost_diff_vnd": self.cost_diff_vnd,
            "travel_time_diff_min": self.travel_time_diff_min,
            "estimated_return_time": return_time,
            "preserved_intents": self.preserved_intents,
            "lost_intents": self.lost_intents,
            "similarity_source": self.similarity_source,
            "similarity_score_for_ranking_only": round(self.ranking_score, 4),
            "slot": {
                "start_at": aware(self.slot.start_at).isoformat(),
                "end_at": aware(self.slot.end_at).isoformat(),
                "status": self.slot.status,
                "available_reported": self.slot.available_reported,
            },
        }


class ReplanningService:
    """Generates solver-filtered alternatives; the LLM only ranks/explains them."""

    def __init__(self, db: Session, provider: StructuredOutputProvider | None):
        self.db = db
        self.runner = PromptRunner(provider) if provider else None
        self.routing = RoutingService(db=db)
        self.availability = AvailabilityService()

    def _load(self, itinerary_id: str, event_id: str, lock: bool = False):
        itinerary_query = (
            select(Itinerary)
            .where(Itinerary.id == itinerary_id)
            .options(
                selectinload(Itinerary.stops).joinedload(ItineraryStop.experience).joinedload(Experience.poi),
                selectinload(Itinerary.stops).joinedload(ItineraryStop.slot),
                selectinload(Itinerary.stops).joinedload(ItineraryStop.poi),
            )
        )
        if lock:
            itinerary_query = itinerary_query.with_for_update()
        itinerary = self.db.scalar(itinerary_query)
        event = self.db.get(Event, event_id)
        if itinerary is None:
            raise LookupError("Itinerary not found")
        if event is None:
            raise LookupError("Disruption event not found")
        if event.event_type != "SLOT_CANCELLED" or event.target_type != "experience_slot":
            raise ValueError("Replanning currently accepts active slot-cancellation events only")
        if event.status != "active" or (event.valid_until and aware(event.valid_until) <= datetime.now(timezone.utc)):
            raise ValueError("Disruption event is resolved or expired")
        ordered = sorted(itinerary.stops, key=lambda stop: stop.stop_order)
        affected = next((stop for stop in ordered if stop.slot_id == event.target_id), None)
        if affected is None:
            raise ValueError("The event's cancelled slot is not part of this itinerary")
        return itinerary, event, affected, ordered

    def _options(self, itinerary: Itinerary, affected: ItineraryStop, stops: list[ItineraryStop]) -> list[ReplanCandidate]:
        if affected.is_locked or affected.locked:
            return []

        affected_index = stops.index(affected)
        previous = stops[affected_index - 1] if affected_index > 0 else None
        following = stops[affected_index + 1] if affected_index + 1 < len(stops) else None
        start_time = aware(itinerary.start_time or itinerary.start_at)
        return_deadline = aware(itinerary.return_deadline or itinerary.end_at)
        requested = {key for key, weight in (itinerary.target_intents or {}).items() if weight > 0}
        if not requested:
            requested = set(affected.experience.intent_tags or [])
        normalized_requested = {normalize_intent_tag(key) for key in requested}
        used_experience_ids = {stop.experience_id for stop in stops if stop.id != affected.id}
        budget_remaining = itinerary.budget_vnd - sum(stop.cost_vnd for stop in stops if stop.id != affected.id)
        mode = {"motorcycle": "motorcycle", "car": "driving"}.get(itinerary.travel_mode, itinerary.travel_mode)
        now = datetime.now(timezone.utc)

        allowed_statuses = ["verified"] if settings.real_data_only else ["verified", "simulated"]
        experiences = self.db.scalars(
            select(Experience)
            .join(POI)
            .where(Experience.id != affected.experience_id,
                   Experience.verification_status.in_(allowed_statuses),
                   POI.verification_status.in_(allowed_statuses))
            .options(selectinload(Experience.slots), joinedload(Experience.poi))
        ).all()
        experiences = [experience for experience in experiences if (
            not settings.real_data_only and experience.verification_status == "simulated"
            and experience.poi.verification_status == "simulated"
        ) or (
            entity_is_operationally_verified(self.db, "experience", experience)
            and entity_is_operationally_verified(self.db, "poi", experience.poi)
        )]
        candidates: list[ReplanCandidate] = []
        old_travel = 0
        if previous:
            old_travel += self.routing.get_route(
                (previous.poi.latitude, previous.poi.longitude),
                (affected.poi.latitude, affected.poi.longitude), mode,
            ).duration_min
        elif itinerary.origin_latitude is not None and itinerary.origin_longitude is not None:
            old_travel += self.routing.get_route(
                (itinerary.origin_latitude, itinerary.origin_longitude),
                (affected.poi.latitude, affected.poi.longitude), mode,
            ).duration_min
        if following:
            old_travel += self.routing.get_route(
                (affected.poi.latitude, affected.poi.longitude),
                (following.poi.latitude, following.poi.longitude), mode,
            ).duration_min
        elif itinerary.destination_latitude is not None and itinerary.destination_longitude is not None:
            old_travel += self.routing.get_route(
                (affected.poi.latitude, affected.poi.longitude),
                (itinerary.destination_latitude, itinerary.destination_longitude), mode,
            ).duration_min

        for experience in experiences:
            if experience.id in used_experience_ids:
                continue
            if experience.price_basis == PriceBasis.PER_PERSON.value:
                cost = experience.price_vnd * itinerary.group_size
            else:
                cost = experience.price_vnd
            if cost > budget_remaining:
                continue

            tags = set(experience.intent_tags or [])
            normalized_tags = {normalize_intent_tag(tag) for tag in tags}
            preserved = sorted(tag for tag in requested if normalize_intent_tag(tag) in normalized_tags)
            lost = sorted(requested - set(preserved))
            old_tags = {normalize_intent_tag(tag) for tag in (affected.experience.intent_tags or [])}
            union = old_tags | normalized_tags
            overlap = len(old_tags & normalized_tags) / len(union) if union else 0.0
            hands_on_match = 1.0 if experience.is_hands_on == affected.experience.is_hands_on else 0.0
            fallback_score = 0.75 * overlap + 0.25 * hands_on_match
            pair = tuple(sorted((affected.experience_id, experience.id)))
            stored_similarity = self.db.get(IntentSimilarity, pair)
            if stored_similarity:
                score = stored_similarity.final_score
                source = f"intent_similarities@{stored_similarity.prompt_version or 'stored'}"
            else:
                score = fallback_score
                source = "tag_overlap_heuristic (not an LLM score)"

            for slot in experience.slots:
                if not self.availability.can_fit(slot, itinerary.group_size):
                    continue
                if slot.expires_at and aware(slot.expires_at) <= now:
                    continue
                if experience.verification_status == "verified" and not slot_is_operationally_verified(self.db, slot):
                    continue
                slot_start, slot_end = aware(slot.start_at), aware(slot.end_at)
                travel_before = 0
                if previous:
                    travel_before = self.routing.get_route(
                        (previous.poi.latitude, previous.poi.longitude),
                        (experience.poi.latitude, experience.poi.longitude), mode,
                    ).duration_min
                    if slot_start < aware(previous.departure_at or previous.end_at) + timedelta(minutes=travel_before):
                        continue
                elif itinerary.origin_latitude is not None and itinerary.origin_longitude is not None:
                    travel_before = self.routing.get_route(
                        (itinerary.origin_latitude, itinerary.origin_longitude),
                        (experience.poi.latitude, experience.poi.longitude), mode,
                    ).duration_min
                    if slot_start < start_time + timedelta(minutes=travel_before):
                        continue
                elif slot_start < start_time:
                    continue

                travel_after = 0
                if following:
                    travel_after = self.routing.get_route(
                        (experience.poi.latitude, experience.poi.longitude),
                        (following.poi.latitude, following.poi.longitude), mode,
                    ).duration_min
                    if slot_end + timedelta(minutes=travel_after) > aware(following.arrival_at):
                        continue
                elif itinerary.destination_latitude is not None and itinerary.destination_longitude is not None:
                    travel_after = self.routing.get_route(
                        (experience.poi.latitude, experience.poi.longitude),
                        (itinerary.destination_latitude, itinerary.destination_longitude), mode,
                    ).duration_min
                    if slot_end + timedelta(minutes=travel_after) > return_deadline:
                        continue
                elif slot_end > return_deadline:
                    continue

                new_travel = travel_before + travel_after
                candidates.append(ReplanCandidate(
                    experience=experience,
                    slot=slot,
                    cost_vnd=cost,
                    cost_diff_vnd=cost - affected.cost_vnd,
                    travel_time_diff_min=new_travel - old_travel,
                    eta_min=travel_before,
                    preserved_intents=preserved,
                    lost_intents=lost,
                    ranking_score=score,
                    similarity_source=source,
                    code="",
                ))

        if ranker_service.available and candidates:
            query_for_ranker = {
                "user_intent_text": " ".join(sorted(requested)),
                "user_intent_tags": sorted(requested | set(affected.experience.intent_tags or [])),
                "lost_experience_text": " ".join(filter(None, [
                    affected.experience.title or affected.experience.name,
                    affected.experience.description,
                    " ".join(affected.experience.intent_tags or []),
                ])),
                "remaining_time_min": max(1, (return_deadline - start_time).total_seconds() / 60),
                "group_size": itinerary.group_size,
                "budget_remaining_vnd": budget_remaining,
            }
            rows = []
            by_slot = {}
            for candidate in candidates:
                row = {
                    "candidate_experience_id": candidate.experience.id,
                    "candidate_slot_id": candidate.slot.id,
                    "candidate_name": candidate.experience.title or candidate.experience.name,
                    "candidate_tags": candidate.experience.intent_tags or [],
                    "duration_min": candidate.experience.duration_min,
                    "price_vnd_per_person": candidate.cost_vnd / max(itinerary.group_size, 1),
                    "total_cost_vnd": candidate.cost_vnd,
                    "is_hands_on": candidate.experience.is_hands_on,
                    "is_indoor": candidate.experience.is_indoor,
                    "eta_min": candidate.eta_min,
                    "hard_feasible": True,
                }
                rows.append(row)
                by_slot[(candidate.experience.id, candidate.slot.id)] = candidate
            try:
                ranked, _, status = ranker_service.rank(query_for_ranker, rows)
                for row in ranked:
                    candidate = by_slot[(row["candidate_experience_id"], row["candidate_slot_id"])]
                    candidate.ranking_score = row["rank_score"]
                    family = status.get("model_family") or "ranker"
                    candidate.similarity_source = f"{family}@{status.get('model_version') or 'unknown'}"
            except MLRankerUnavailable:
                # Preserve the deterministic tag-similarity order when the optional artifact
                # is incomplete; /api/ml/status exposes the artifact/dependency failure.
                for candidate in candidates:
                    candidate.similarity_source = "tag_overlap_heuristic (ranker unavailable)"

        candidates.sort(key=lambda candidate: (-candidate.ranking_score, candidate.cost_diff_vnd, candidate.travel_time_diff_min))
        for index, candidate in enumerate(candidates[:2]):
            candidate.code = "B" if index == 0 else "C"
        return candidates[:2]

    def advise(self, itinerary_id: str, event_id: str) -> dict[str, Any]:
        if self.runner is None:
            raise RuntimeError("A structured LLM provider is required to generate re-plan advice")
        itinerary, event, affected, stops = self._load(itinerary_id, event_id)
        candidates = self._options(itinerary, affected, stops)
        return_deadline = aware(itinerary.return_deadline or itinerary.end_at).astimezone(LOCAL_TZ).strftime("%H:%M")
        old_experience = affected.experience
        last_stop = stops[-1]
        solver_options = []
        for candidate in candidates:
            final_stop_end = aware(candidate.slot.end_at if last_stop.id == affected.id else last_stop.departure_at)
            if itinerary.destination_latitude is not None and itinerary.destination_longitude is not None:
                final_poi = candidate.experience.poi if last_stop.id == affected.id else last_stop.poi
                home_leg = self.routing.get_route((final_poi.latitude, final_poi.longitude),
                    (itinerary.destination_latitude, itinerary.destination_longitude),
                    {"motorcycle": "motorcycle", "car": "driving"}.get(itinerary.travel_mode, itinerary.travel_mode))
                final_stop_end += timedelta(minutes=home_leg.duration_min)
            solver_options.append(candidate.prompt_dict(final_stop_end.astimezone(LOCAL_TZ).strftime("%H:%M")))
        proposals = self.runner.run(
            "REPLAN_ADVISOR",
            {
                "event": {"event_type": event.event_type, "reason": event.event_metadata.get("reason_note", ""), "target_id": event.target_id},
                "itinerary": {
                    "itinerary_id": itinerary.id,
                    "current_version": itinerary.current_version,
                    "group_size": itinerary.group_size,
                    "budget_vnd": itinerary.budget_vnd,
                    "target_intents": itinerary.target_intents or {},
                    "return_deadline": return_deadline,
                    "return_time_estimate_basis": "final scheduled stop plus route to stored destination when available; solver enforces the return deadline",
                },
                "cancelled_experience": {
                    "experience_id": old_experience.id,
                    "title": old_experience.title or old_experience.name,
                    "intent_tags": old_experience.intent_tags or [],
                    "is_hands_on": old_experience.is_hands_on,
                },
                "solver_feasible_candidates": solver_options,
            },
            ReplanProposals,
        )
        if proposals.disruption_summary.cancelled_experience_title != (old_experience.title or old_experience.name):
            raise InvalidStructuredOutput("REPLAN_ADVISOR changed the cancelled experience title.")
        if {proposal.code for proposal in proposals.proposals} != {candidate.code for candidate in candidates}:
            raise InvalidStructuredOutput("REPLAN_ADVISOR omitted or added a solver-provided candidate.")
        option_by_code = {candidate.code: candidate for candidate in candidates}
        for proposal in proposals.proposals:
            candidate = option_by_code.get(proposal.code)
            if not candidate or proposal.candidate_experience_id != candidate.experience.id:
                raise InvalidStructuredOutput("REPLAN_ADVISOR referenced an option that the solver did not provide.")
            expected_option = next(item for item in solver_options if item["code"] == proposal.code)
            if (proposal.title != expected_option["title"]
                    or proposal.cost_diff_vnd != candidate.cost_diff_vnd
                    or proposal.travel_time_diff_min != candidate.travel_time_diff_min
                    or proposal.estimated_return_time != expected_option["estimated_return_time"]
                    or set(proposal.preserved_intents) != set(candidate.preserved_intents)
                    or set(proposal.lost_intents) != set(candidate.lost_intents)):
                raise InvalidStructuredOutput("REPLAN_ADVISOR changed solver-owned itinerary facts.")
        if len({item.code for item in proposals.proposals}) != len(proposals.proposals):
            raise InvalidStructuredOutput("REPLAN_ADVISOR returned duplicate proposal codes.")
        if proposals.proposals and sum(item.is_recommended for item in proposals.proposals) != 1:
            raise InvalidStructuredOutput("REPLAN_ADVISOR must recommend exactly one feasible proposal.")

        now = datetime.now(timezone.utc).isoformat()
        explanation = None
        if proposals.proposals:
            recommended = next((item for item in proposals.proposals if item.is_recommended), proposals.proposals[0])
            explanation = self.runner.run(
                "XAI_EXPLANATION",
                {
                    "preserved_intents": recommended.preserved_intents,
                    "lost_intents": recommended.lost_intents,
                    "comparative_metrics": {
                        "estimated_cost_diff_vnd": recommended.cost_diff_vnd,
                        "travel_time_diff_min": recommended.travel_time_diff_min,
                        "estimated_return_time": recommended.estimated_return_time,
                        "comparison_options": [item.model_dump() for item in proposals.proposals],
                        "estimated_return_time_basis": "final scheduled stop plus route to stored destination when available",
                    },
                    "data_timestamp": now,
                },
                XAIExplanation,
            )
            if explanation.data_timestamp != now:
                raise InvalidStructuredOutput("XAI_EXPLANATION changed the supplied data timestamp.")

        # Advice is auditable, but it does not mutate the plan/version before the user accepts.
        self.db.add(DecisionLog(
            itinerary_id=itinerary.id,
            trigger_event_id=event.id,
            base_version=itinerary.current_version,
            new_version=itinerary.current_version,
            preserved_intents=(next((p.preserved_intents for p in proposals.proposals if p.is_recommended), []) if proposals.proposals else []),
            lost_intents=(next((p.lost_intents for p in proposals.proposals if p.is_recommended), []) if proposals.proposals else []),
            comparative_metrics={
                "proposals": [p.model_dump() for p in proposals.proposals],
                "solver_candidates": solver_options,
                "candidate_ranking_sources": sorted({item.similarity_source for item in candidates}),
            },
            explanation_vi=explanation.core_explanation_vi if explanation else None,
            reason_codes=["SLOT_CANCELLED", "REPLAN_PROPOSAL"],
            rejected_candidates=[item for item in solver_options if item["candidate_experience_id"] not in {p.candidate_experience_id for p in proposals.proposals}],
            model_version=f"{self.runner.provider.model_name}/prompt-{catalog.version}",
        ))
        self.db.commit()

        response_proposals = []
        for proposal in proposals.proposals:
            candidate = option_by_code[proposal.code]
            response_proposals.append({**proposal.model_dump(), "candidate_slot_id": candidate.slot.id,
                                       "available_reported": candidate.slot.available_reported,
                                       "availability_known": candidate.slot.available_reported is not None})
        return {
            "itinerary_id": itinerary.id,
            "event_id": event.id,
            "affected_stop_id": affected.id,
            "base_version": itinerary.current_version,
            "prompt_version": catalog.version,
            "disruption_summary": proposals.disruption_summary.model_dump(),
            "proposals": response_proposals,
            "xai_explanation": explanation.model_dump() if explanation else None,
            "return_time_estimate_basis": "final scheduled stop plus route to stored destination when available",
            "requires_user_confirmation": True,
        }

    def accept(self, itinerary_id: str, event_id: str, affected_stop_id: str,
               candidate_experience_id: str, candidate_slot_id: str, proposal_code: str,
               expected_version: int) -> dict[str, Any]:
        itinerary, event, affected, stops = self._load(itinerary_id, event_id, lock=True)
        if itinerary.current_version != expected_version:
            raise ValueError("The itinerary version changed; request fresh advice before accepting")
        if affected.id != affected_stop_id:
            raise ValueError("affected_stop_id does not match the active disruption")
        candidates = self._options(itinerary, affected, stops)
        candidate = next((item for item in candidates if item.code == proposal_code
                          and item.experience.id == candidate_experience_id and item.slot.id == candidate_slot_id), None)
        if candidate is None:
            raise ValueError("The selected replacement is no longer feasible; request new advice")

        base_version = itinerary.current_version
        affected.experience_id = candidate.experience.id
        affected.poi_id = candidate.experience.poi_id
        affected.poi = candidate.experience.poi
        affected.slot_id = candidate.slot.id
        affected.arrival_at = aware(candidate.slot.start_at)
        affected.start_at = aware(candidate.slot.start_at)
        affected.departure_at = aware(candidate.slot.end_at)
        affected.end_at = aware(candidate.slot.end_at)
        affected.activity_duration_min = candidate.experience.duration_min
        affected.cost_vnd = candidate.cost_vnd
        affected.status = "planned"
        itinerary.estimated_cost_vnd += candidate.cost_diff_vnd
        itinerary.current_version += 1
        itinerary.version = itinerary.current_version
        itinerary.status = ItineraryStatus.RE_PLANNED.value
        event.status = "resolved"

        total_travel_min = 0
        ordered = sorted(stops, key=lambda stop: stop.stop_order)
        mode = {"motorcycle": "motorcycle", "car": "driving"}.get(itinerary.travel_mode, itinerary.travel_mode)
        if ordered and itinerary.origin_latitude is not None and itinerary.origin_longitude is not None:
            first = ordered[0]
            total_travel_min += self.routing.get_route((itinerary.origin_latitude, itinerary.origin_longitude),
                (first.poi.latitude, first.poi.longitude), mode).duration_min
        for left, right in zip(ordered, ordered[1:]):
            total_travel_min += self.routing.get_route(
                (left.poi.latitude, left.poi.longitude), (right.poi.latitude, right.poi.longitude), mode
            ).duration_min
        if ordered and itinerary.destination_latitude is not None and itinerary.destination_longitude is not None:
            last = ordered[-1]
            total_travel_min += self.routing.get_route((last.poi.latitude, last.poi.longitude),
                (itinerary.destination_latitude, itinerary.destination_longitude), mode).duration_min
        snapshot = [{
            "stop_id": stop.id,
            "stop_order": stop.stop_order,
            "poi_id": stop.poi_id,
            "experience_id": stop.experience_id,
            "slot_id": stop.slot_id,
            "arrival_at": aware(stop.arrival_at).isoformat(),
            "departure_at": aware(stop.departure_at).isoformat(),
            "cost_vnd": stop.cost_vnd,
            "is_locked": stop.is_locked,
        } for stop in ordered]
        self.db.add(ItineraryVersion(
            itinerary_id=itinerary.id,
            version_number=itinerary.current_version,
            stops_snapshot=snapshot,
            total_cost_vnd=itinerary.estimated_cost_vnd,
            total_travel_time_s=total_travel_min * 60,
            preserved_intents_ratio=(len(candidate.preserved_intents) / len(candidate.preserved_intents + candidate.lost_intents)) if candidate.preserved_intents or candidate.lost_intents else 1.0,
        ))
        self.db.add(DecisionLog(
            itinerary_id=itinerary.id,
            trigger_event_id=event.id,
            base_version=base_version,
            new_version=itinerary.current_version,
            preserved_intents=candidate.preserved_intents,
            lost_intents=candidate.lost_intents,
            comparative_metrics={
                "estimated_cost_vnd": itinerary.estimated_cost_vnd,
                "cost_diff_vnd": candidate.cost_diff_vnd,
                "travel_time_diff_min": candidate.travel_time_diff_min,
                "total_travel_time_s": total_travel_min * 60,
                "candidate_ranking_source": candidate.similarity_source,
            },
            explanation_vi=f"Đã áp dụng phương án {proposal_code} theo xác nhận của người dùng.",
            reason_codes=["SLOT_CANCELLED", "USER_ACCEPTED_REPLAN"],
            model_version=f"user-accepted-replan/prompt-{catalog.version}",
        ))
        self.db.commit()
        return {
            "itinerary_id": itinerary.id,
            "event_id": event.id,
            "current_version": itinerary.current_version,
            "status": itinerary.status,
            "selected_experience_id": candidate.experience.id,
            "selected_slot_id": candidate.slot.id,
            "estimated_cost_vnd": itinerary.estimated_cost_vnd,
        }
