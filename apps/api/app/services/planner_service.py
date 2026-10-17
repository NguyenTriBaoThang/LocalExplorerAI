from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.adapters.routing.provider import MockRoutingProvider, NoRouteFound, RoutingConfigurationError, RoutingProvider
from app.core.config import settings
from app.core.pilot_area import PILOT_DISTRICT
from app.core.enums import ItineraryStatus, PriceBasis, normalize_intent_tag
from app.models.entities import DecisionLog, Experience, ExperienceSlot, Itinerary, ItineraryStop, ItineraryVersion
from app.repositories.experience_repository import ExperienceRepository
from app.schemas.planner import PlanRequest
from app.services.explanation_service import ExplanationService
from app.services.evidence_service import entity_is_operationally_verified
from app.services.availability_service import AvailabilityService
from app.services.ml_ranker_service import MLRankerUnavailable, ranker_service
from app.services.planner_engine import HeuristicPlanner, PlannerEngine, SuggestionPlanner
from app.services.recommendation_service import RecommendationService
from app.services.routing_service import RoutingService


class NoFeasiblePlan(Exception):
    def __init__(self, message: str, code: str = "NO_FEASIBLE_PLAN", diagnostics: dict | None = None):
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics or {}


LOCAL_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def as_aware(value: datetime) -> datetime:
    # SQLite drops tzinfo when reloading DateTime(timezone=True); persisted values
    # are UTC, while incoming PlanRequest datetimes are required to be offset-aware.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PlannerService:
    def __init__(self, db: Session, routing: RoutingProvider | None = None,
                 engine: PlannerEngine | None = None, ranker=None):
        self.db = db
        self.repository = ExperienceRepository(db)
        self.routing = RoutingService(routing, db=db)
        self.availability = AvailabilityService()
        self.engine = engine or HeuristicPlanner()
        self.ranker = ranker or ranker_service
        self.recommender = RecommendationService()
        self.explainer = ExplanationService()

    def _rank_feasible_candidates(self, candidates: list[dict], request: PlanRequest,
                                  cursor: datetime, end_at: datetime,
                                  budget_remaining_vnd: int) -> tuple[str, str] | None:
        """Rank only the planner-approved candidates; feasibility stays planner-owned."""
        if (len(candidates) < 2 or any(item["locked"] for item in candidates)
                or not isinstance(self.engine, HeuristicPlanner)
                or getattr(self.ranker, "available", True) is False):
            return None

        intent_tags = [tag for tag, weight in request.intent_weights.items() if weight > 0]
        query = {
            "user_intent_text": " ".join(intent_tags),
            "user_intent_tags": intent_tags,
            "remaining_time_min": max(1, (end_at - cursor).total_seconds() / 60),
            "group_size": request.group_size,
            "budget_remaining_vnd": max(0, budget_remaining_vnd),
        }
        rows = []
        candidates_by_key = {}
        for item in candidates:
            experience = item["experience"]
            slot = item["slot"]
            key = (experience.id, slot.id)
            candidates_by_key[key] = item
            rows.append({
                "candidate_experience_id": experience.id,
                "candidate_slot_id": slot.id,
                "candidate_name": experience.name,
                "candidate_tags": experience.intent_tags or [],
                "duration_min": experience.duration_min,
                "price_vnd_per_person": item["cost"] / max(request.group_size, 1),
                "total_cost_vnd": item["cost"],
                "is_hands_on": experience.is_hands_on,
                "is_indoor": experience.is_indoor,
                "eta_min": item["travel"],
                "hard_feasible": True,
            })

        try:
            ranked, filtered_ids, status = self.ranker.rank(query, rows)
        except MLRankerUnavailable:
            return None

        # If the model/service disagrees with the already-validated candidate set,
        # keep the deterministic planner unchanged instead of dropping choices.
        if filtered_ids or len(ranked) != len(candidates):
            return None
        scores = {
            (row["candidate_experience_id"], row["candidate_slot_id"]): row["rank_score"]
            for row in ranked
        }
        if set(scores) != set(candidates_by_key):
            return None
        for key, item in candidates_by_key.items():
            item["score"] = float(scores[key])
        return (
            status.get("model_version") or "local-ranker",
            status.get("ranking_source") or "ml_model",
        )

    def plan(self, request: PlanRequest, user_id: str | None = None, *, persist: bool = True) -> dict:
        if request.planning_style != "balanced":
            self.engine = SuggestionPlanner(request.planning_style)
        if request.routing_mode == "demo":
            if settings.real_data_only or request.require_verified:
                raise RoutingConfigurationError("Demo routing requires explicit demo data mode and REAL_DATA_ONLY=false.")
            self.routing = RoutingService(MockRoutingProvider())
        start_at, end_at = as_aware(request.start_at), as_aware(request.end_at)
        if end_at <= start_at or start_at < datetime.now(timezone.utc):
            raise NoFeasiblePlan(
                "The trip must start in the future and end after it starts",
                code="TRIP_TIME_INVALID",
                diagnostics={"reason_codes": ["TRIP_TIME_INVALID"]},
            )

        # The pilot intentionally plans only against Quận 1 and only loads slots
        # overlapping this trip, not the entire historical slot calendar.
        experiences = self.repository.list_experiences(
            district=PILOT_DISTRICT,
            slot_start_at=start_at,
            slot_end_at=end_at,
        )
        if request.require_verified:
            experiences = [item for item in experiences if item.verification_status == "verified"]
            if not experiences:
                raise NoFeasiblePlan(
                    "The pilot has no experiences with current verified sources. Add verified data or explicitly use demo mode.",
                    code="VERIFIED_CATALOG_EMPTY",
                    diagnostics={"reason_codes": ["VERIFIED_CATALOG_EMPTY"]},
                )
        experiences = [item for item in experiences if item.id not in request.excluded_experience_ids]
        by_id = {experience.id: experience for experience in experiences}
        if any(experience_id not in by_id for experience_id in request.locked_experience_ids):
            raise NoFeasiblePlan(
                f"A locked experience is not available in the current {PILOT_DISTRICT} pilot catalog.",
                code="PINNED_STOP_NOT_AVAILABLE",
                diagnostics={"reason_codes": ["PINNED_STOP_NOT_AVAILABLE"]},
            )
        poi_ids = {experience.poi_id for experience in experiences}
        if any(poi_id not in poi_ids for poi_id in request.locked_poi_ids):
            raise NoFeasiblePlan(
                f"A locked POI is not available in the current {PILOT_DISTRICT} pilot catalog or has no experience.",
                code="PINNED_STOP_NOT_AVAILABLE",
                diagnostics={"reason_codes": ["PINNED_STOP_NOT_AVAILABLE"]},
            )

        chosen: list[dict] = []
        chosen_experience_ids: set[str] = set()
        chosen_poi_ids: set[str] = set()
        cursor = start_at
        previous_poi: tuple[float, float] | None = (
            (request.origin_latitude, request.origin_longitude)
            if request.origin_latitude is not None and request.origin_longitude is not None else None
        )
        total_cost = 0
        total_travel = 0
        routes: list[dict] = []
        reason_codes: set[str] = set()
        unknown_capacity = False
        ranking_model_version = "heuristic-v1"
        ranking_source: str | None = None
        rejection_counts = {
            "over_budget": 0,
            "unavailable_slots": 0,
            "insufficient_capacity": 0,
            "stale_slots": 0,
            "unreachable_routes": 0,
            "arrival_too_late": 0,
            "return_too_late": 0,
        }

        # Locked experiences are scheduled first in the caller's requested order.
        ordered_ids = list(dict.fromkeys(request.locked_experience_ids))
        remaining = [item for item in experiences if item.id not in ordered_ids]
        remaining.sort(
            key=lambda item: self.recommender.score(item, request.intent_weights, request.group_size, request.budget_vnd - total_cost)[0],
            reverse=True,
        )
        pool = [by_id[item] for item in ordered_ids] + remaining

        remaining_locked = set(request.locked_experience_ids)
        while len(chosen) < 6:
            candidates: list[dict] = []
            for experience in pool:
                if len(candidates) >= 5 and not (remaining_locked - chosen_experience_ids):
                    break
                if experience.id in chosen_experience_ids:
                    continue
                locked = experience.id in request.locked_experience_ids or (
                    experience.poi_id in request.locked_poi_ids and experience.poi_id not in chosen_poi_ids
                )
                cost = experience.price_vnd * request.group_size if experience.price_basis == PriceBasis.PER_PERSON.value else experience.price_vnd
                if total_cost + cost > request.budget_vnd:
                    rejection_counts["over_budget"] += len(experience.slots)
                    continue
                score, reasons = self.recommender.score(experience, request.intent_weights, request.group_size, request.budget_vnd - total_cost)
                for slot in sorted(experience.slots, key=lambda item: as_aware(item.start_at)):
                    slot_start, slot_end = as_aware(slot.start_at), as_aware(slot.end_at)
                    if slot_start < start_at or slot_end > end_at or slot_end <= cursor:
                        continue
                    if experience.verification_status == "verified" and not self.repository.is_fresh_slot(slot):
                        rejection_counts["stale_slots"] += 1
                        continue
                    if not self.availability.can_fit(slot, request.group_size):
                        if slot.status in {"full", "unavailable", "cancelled"} or slot.available_reported == 0:
                            rejection_counts["unavailable_slots"] += 1
                        else:
                            rejection_counts["insufficient_capacity"] += 1
                        continue
                    if request.preferred_slot_ids and slot.id not in request.preferred_slot_ids:
                        continue
                    if previous_poi:
                        try:
                            leg = self.routing.get_route(previous_poi, (experience.poi.latitude, experience.poi.longitude), request.transport_mode)
                        except NoRouteFound:
                            rejection_counts["unreachable_routes"] += 1
                            continue
                        travel = leg.duration_min
                    else:
                        leg, travel = None, 0
                    if slot_start < cursor + timedelta(minutes=travel):
                        rejection_counts["arrival_too_late"] += 1
                        continue
                    return_leg = None
                    return_travel = 0
                    if request.destination_latitude is not None and request.destination_longitude is not None:
                        try:
                            return_leg = self.routing.get_route(
                                (experience.poi.latitude, experience.poi.longitude),
                                (request.destination_latitude, request.destination_longitude),
                                request.transport_mode,
                            )
                        except NoRouteFound:
                            rejection_counts["unreachable_routes"] += 1
                            continue
                        return_travel = return_leg.duration_min
                        if slot_end + timedelta(minutes=return_travel) > end_at:
                            rejection_counts["return_too_late"] += 1
                            continue
                    capacity_known = self.availability.is_capacity_known(slot)
                    candidates.append({
                        "experience": experience,
                        "slot": slot,
                        "cost": cost,
                        "score": score,
                        "reasons": reasons,
                        "locked": locked,
                        "leg": leg,
                        "travel": travel,
                        "capacity_known": capacity_known,
                        "return_leg": return_leg,
                        "return_travel": return_travel,
                    })
            ranker_result = self._rank_feasible_candidates(
                candidates, request, cursor, end_at, request.budget_vnd - total_cost,
            )
            if ranker_result:
                ranking_model_version, ranking_source = ranker_result
                reason_codes.add({
                    "rule_baseline": "RULE_BASELINE_RANKER",
                    "bootstrap_ml_model": "BOOTSTRAP_PILOT_RANKER",
                }.get(ranking_source, "ML_RANKER"))
            next_item = self.engine.plan(candidates)
            if not next_item:
                break

            experience, slot = next_item["experience"], next_item["slot"]
            slot_start, slot_end = as_aware(slot.start_at), as_aware(slot.end_at)
            if next_item["leg"]:
                total_travel += next_item["travel"]
                routes.append({
                    "from_experience_id": chosen[-1]["experience"].id if chosen else None,
                    "to_experience_id": experience.id,
                    "from_label": None if chosen else (request.origin_label or "Điểm xuất phát"),
                    "distance_m": next_item["leg"].distance_m,
                    "duration_min": next_item["leg"].duration_min,
                    **self.routing.eta_metadata(next_item["leg"]),
                })
                reason_codes.add("MOCK_ROUTING" if next_item["leg"].provider == "mock" else "GOONG_ROUTING")
            chosen.append({**next_item, "arrival": slot_start})
            chosen_experience_ids.add(experience.id)
            chosen_poi_ids.add(experience.poi_id)
            total_cost += next_item["cost"]
            cursor = slot_end
            previous_poi = (experience.poi.latitude, experience.poi.longitude)
            reason_codes.update(next_item["reasons"])
            reason_codes.add("SLOT_AVAILABLE")
            if (experience.verification_status == "verified"
                    and experience.poi.verification_status == "verified"
                    and self.repository.is_fresh_slot(slot)):
                reason_codes.add("VERIFIED_DATA")
            elif experience.verification_status == "simulated" and experience.poi.verification_status == "simulated":
                reason_codes.add("SIMULATED_DATA")
            else:
                reason_codes.add("STALE_DATA")
            if next_item["locked"]:
                reason_codes.add("LOCKED_ACTIVITY")
            if not next_item["capacity_known"]:
                unknown_capacity = True
                reason_codes.add("CAPACITY_UNKNOWN")

        if not chosen:
            requested_local_date = start_at.astimezone(LOCAL_TIMEZONE).date()
            requested_local_end_date = end_at.astimezone(LOCAL_TIMEZONE).date()
            requested_day_start = datetime.combine(requested_local_date, datetime.min.time(), tzinfo=LOCAL_TIMEZONE).astimezone(timezone.utc)
            requested_day_end = datetime.combine(
                requested_local_end_date + timedelta(days=1), datetime.min.time(), tzinfo=LOCAL_TIMEZONE,
            ).astimezone(timezone.utc)
            all_catalog_slots = self.db.scalars(
                select(ExperienceSlot).where(
                    ExperienceSlot.experience_id.in_(list(by_id)),
                    ExperienceSlot.start_at >= requested_day_start,
                    ExperienceSlot.start_at < requested_day_end,
                )
            ).all() if by_id else []
            slots_on_requested_date = [
                (experience, slot)
                for experience in experiences
                for slot in all_catalog_slots
                if slot.experience_id == experience.id
                and requested_local_date <= as_aware(slot.start_at).astimezone(LOCAL_TIMEZONE).date() <= requested_local_end_date
            ]
            has_bookable_slot = any(
                self.availability.can_fit(slot, request.group_size)
                and (
                    experience.verification_status != "verified"
                    or self.repository.is_fresh_slot(slot)
                )
                for experience, slot in slots_on_requested_date
            )
            date_slots_unavailable = sum(
                slot.status in {"full", "unavailable", "cancelled"} or slot.available_reported == 0
                for _, slot in slots_on_requested_date
            )
            date_slots_insufficient_capacity = sum(
                slot.available_reported is not None and 0 < slot.available_reported < request.group_size
                for _, slot in slots_on_requested_date
            )
            date_slots_stale = sum(
                experience.verification_status == "verified" and not self.repository.is_fresh_slot(slot)
                for experience, slot in slots_on_requested_date
            )
            counts = {
                "experiences_checked": len(experiences),
                "slots_in_requested_window": sum(len(experience.slots) for experience in experiences),
                "slots_on_requested_date_range": len(slots_on_requested_date),
                "date_slots_unavailable": date_slots_unavailable,
                "date_slots_with_insufficient_capacity": date_slots_insufficient_capacity,
                "date_slots_with_stale_availability": date_slots_stale,
                "slots_rejected_over_budget": rejection_counts["over_budget"],
                "slots_unavailable": rejection_counts["unavailable_slots"],
                "slots_with_insufficient_capacity": rejection_counts["insufficient_capacity"],
                "slots_with_stale_availability": rejection_counts["stale_slots"],
                "routes_unavailable": rejection_counts["unreachable_routes"],
                "arrivals_after_slot_start": rejection_counts["arrival_too_late"],
                "returns_after_deadline": rejection_counts["return_too_late"],
            }
            if slots_on_requested_date and not has_bookable_slot:
                date_reason_codes = ["NO_BOOKABLE_SLOTS"]
                if date_slots_unavailable:
                    date_reason_codes.append("SLOTS_UNAVAILABLE")
                if date_slots_insufficient_capacity:
                    date_reason_codes.append("GROUP_TOO_LARGE_FOR_CAPACITY")
                if date_slots_stale:
                    date_reason_codes.append("AVAILABILITY_NEEDS_CONFIRMATION")
                raise NoFeasiblePlan(
                    "No bookable slots are currently available on "
                    f"{requested_local_date.isoformat()}. Choose another date or ask the provider to update availability.",
                    code="NO_BOOKABLE_SLOTS",
                    diagnostics={"reason_codes": date_reason_codes, "counts": counts},
                )
            reason_codes_for_failure = []
            if not experiences:
                reason_codes_for_failure.append("NO_ELIGIBLE_EXPERIENCES")
            elif not slots_on_requested_date:
                reason_codes_for_failure.append("NO_SLOTS_ON_DATE")
            elif not sum(len(experience.slots) for experience in experiences):
                reason_codes_for_failure.append("NO_SLOTS_IN_TIME_WINDOW")
            if rejection_counts["over_budget"]:
                reason_codes_for_failure.append("BUDGET_TOO_LOW")
            if rejection_counts["unavailable_slots"]:
                reason_codes_for_failure.append("SLOTS_UNAVAILABLE")
            if rejection_counts["insufficient_capacity"]:
                reason_codes_for_failure.append("GROUP_TOO_LARGE_FOR_CAPACITY")
            if rejection_counts["stale_slots"]:
                reason_codes_for_failure.append("AVAILABILITY_NEEDS_CONFIRMATION")
            if rejection_counts["unreachable_routes"]:
                reason_codes_for_failure.append("ROUTE_UNAVAILABLE")
            if rejection_counts["arrival_too_late"]:
                reason_codes_for_failure.append("NOT_ENOUGH_TIME_TO_REACH_STOP")
            if rejection_counts["return_too_late"]:
                reason_codes_for_failure.append("RETURN_DEADLINE_TOO_EARLY")
            if not reason_codes_for_failure:
                reason_codes_for_failure.append("NO_FEASIBLE_PLAN")
            raise NoFeasiblePlan(
                f"No itinerary in {PILOT_DISTRICT} satisfies the current constraints",
                diagnostics={"reason_codes": reason_codes_for_failure, "counts": counts},
            )

        if not chosen or any(item not in chosen_experience_ids for item in request.locked_experience_ids) or not set(request.locked_poi_ids).issubset(chosen_poi_ids):
            counts = {
                "experiences_checked": len(experiences),
                "slots_in_requested_window": sum(len(experience.slots) for experience in experiences),
                "slots_rejected_over_budget": rejection_counts["over_budget"],
                "slots_unavailable": rejection_counts["unavailable_slots"],
                "slots_with_insufficient_capacity": rejection_counts["insufficient_capacity"],
                "slots_with_stale_availability": rejection_counts["stale_slots"],
                "routes_unavailable": rejection_counts["unreachable_routes"],
                "arrivals_after_slot_start": rejection_counts["arrival_too_late"],
                "returns_after_deadline": rejection_counts["return_too_late"],
            }
            pinned_reasons = ["PINNED_STOP_NOT_FEASIBLE"]
            for counter, reason in (
                ("over_budget", "BUDGET_TOO_LOW"),
                ("unavailable_slots", "SLOTS_UNAVAILABLE"),
                ("insufficient_capacity", "GROUP_TOO_LARGE_FOR_CAPACITY"),
                ("stale_slots", "AVAILABILITY_NEEDS_CONFIRMATION"),
                ("unreachable_routes", "ROUTE_UNAVAILABLE"),
                ("arrival_too_late", "NOT_ENOUGH_TIME_TO_REACH_STOP"),
                ("return_too_late", "RETURN_DEADLINE_TOO_EARLY"),
            ):
                if rejection_counts[counter]:
                    pinned_reasons.append(reason)
            raise NoFeasiblePlan(
                f"No itinerary in {PILOT_DISTRICT} satisfies the current constraints",
                diagnostics={"reason_codes": pinned_reasons, "counts": counts},
            )

        estimated_return_at = as_aware(chosen[-1]["slot"].end_at)
        if request.destination_latitude is not None and request.destination_longitude is not None:
            final = chosen[-1]
            route = final["return_leg"]
            if route:
                total_travel += final["return_travel"]
                estimated_return_at += timedelta(minutes=final["return_travel"])
                routes.append({
                    "from_experience_id": final["experience"].id,
                    "to_experience_id": None,
                    "to_label": request.destination_label or "Điểm về",
                    "distance_m": route.distance_m,
                    "duration_min": route.duration_min,
                    **self.routing.eta_metadata(route),
                })
                reason_codes.add("MOCK_ROUTING" if route.provider == "mock" else "GOONG_ROUTING")

        requested_intents = {tag for tag, weight in request.intent_weights.items() if weight > 0}
        provided_intents = {normalize_intent_tag(tag) for item in chosen for tag in item["experience"].intent_tags}
        preserved = sorted(tag for tag in requested_intents if normalize_intent_tag(tag) in provided_intents)
        lost = sorted(requested_intents - set(preserved))
        status = ItineraryStatus.TENTATIVE.value if unknown_capacity else ItineraryStatus.FEASIBLE.value
        data_statuses = {
            "verified" if (item["experience"].verification_status == "verified"
                           and item["experience"].poi.verification_status == "verified"
                           and entity_is_operationally_verified(self.db, "experience", item["experience"])
                           and entity_is_operationally_verified(self.db, "poi", item["experience"].poi)
                           and self.repository.is_fresh_slot(item["slot"]))
            else "simulated" if (item["experience"].verification_status == "simulated"
                                 and item["experience"].poi.verification_status == "simulated")
            else "stale"
            for item in chosen
        }
        itinerary_data_mode = next(iter(data_statuses)) if len(data_statuses) == 1 else "mixed"
        itinerary = Itinerary(
            id=str(uuid4()), user_id=user_id, group_size=request.group_size, budget_vnd=request.budget_vnd,
            start_at=start_at, end_at=end_at, status=status,
            planned_date=start_at.date(), start_time=start_at, return_deadline=end_at,
            travel_mode=request.transport_mode, target_intents=request.intent_weights, current_version=1,
            origin_latitude=request.origin_latitude, origin_longitude=request.origin_longitude,
            destination_latitude=request.destination_latitude, destination_longitude=request.destination_longitude,
            constraints={"transport_mode": request.transport_mode, "routing_mode": request.routing_mode, "intent_weights": request.intent_weights,
                         "planning_style": request.planning_style, "excluded_experience_ids": request.excluded_experience_ids,
                         "preferred_slot_ids": request.preferred_slot_ids,
                         "locked_experience_ids": request.locked_experience_ids, "locked_poi_ids": request.locked_poi_ids,
                         "origin_latitude": request.origin_latitude, "origin_longitude": request.origin_longitude,
                         "destination_latitude": request.destination_latitude, "destination_longitude": request.destination_longitude,
                         "origin_label": request.origin_label, "destination_label": request.destination_label},
            estimated_cost_vnd=total_cost, data_mode="real" if itinerary_data_mode == "verified" else "simulated" if itinerary_data_mode == "simulated" else "mixed",
        )
        if persist:
            self.db.add(itinerary)
            self.db.flush()
        response_stops = []
        version_snapshot = []
        for position, item in enumerate(chosen, start=1):
            experience, slot = item["experience"], item["slot"]
            stop = ItineraryStop(
                id=str(uuid4()), itinerary_id=itinerary.id, experience_id=experience.id, slot_id=slot.id,
                poi_id=experience.poi_id, stop_order=position, position=position,
                arrival_at=item["arrival"], start_at=as_aware(slot.start_at), end_at=as_aware(slot.end_at),
                departure_at=as_aware(slot.end_at), wait_duration_min=0,
                activity_duration_min=experience.duration_min,
                cost_vnd=item["cost"], status="planned", is_locked=item["locked"], locked=item["locked"],
            )
            if persist:
                self.db.add(stop)
            response_stops.append(self._stop_dict(stop, experience, slot, position))
            version_snapshot.append({
                "stop_id": stop.id, "stop_order": position, "poi_id": experience.poi_id,
                "experience_id": experience.id, "slot_id": slot.id,
                "arrival_at": stop.arrival_at.isoformat(), "departure_at": stop.departure_at.isoformat(),
                "cost_vnd": stop.cost_vnd, "is_locked": stop.is_locked,
            })
        if persist:
            self.db.add(ItineraryVersion(
                itinerary_id=itinerary.id, version_number=1, stops_snapshot=version_snapshot,
                total_cost_vnd=total_cost, total_travel_time_s=total_travel * 60,
                preserved_intents_ratio=(len(preserved) / sum(weight > 0 for weight in request.intent_weights.values())) if any(weight > 0 for weight in request.intent_weights.values()) else 1.0,
            ))
        explanation = self.explainer.explain(sorted(reason_codes), preserved, lost)
        explanation["ranking_model_version"] = ranking_model_version if ranking_source else None
        explanation["ranking_source"] = ranking_source
        explanation["evidence_refs"] = sorted({
            evidence["id"]
            for item in response_stops
            for evidence in (item["poi"]["source_evidence"] + item["source_evidence"] + item["slot_source_evidence"])
        })
        if persist:
            self.db.add(DecisionLog(
                itinerary_id=itinerary.id, base_version=0, new_version=1,
                preserved_intents=preserved, lost_intents=lost,
                comparative_metrics={"estimated_cost_vnd": total_cost, "total_travel_time_s": total_travel * 60},
                explanation_vi="Lịch trình được tạo theo ngân sách, thời gian và mục đích chuyến đi đã chọn.",
                reason_codes=sorted(reason_codes), rejected_candidates=[], model_version=ranking_model_version,
            ))
            self.db.commit()
        return {
            "request_id": itinerary.id,
            "itinerary_id": itinerary.id,
            "data_mode": "real" if itinerary_data_mode == "verified" else "simulated" if itinerary_data_mode == "simulated" else "mixed",
            "data_as_of": datetime.now(timezone.utc),
            "feasibility_status": status,
            "estimated_cost_vnd": total_cost,
            "total_travel_min": total_travel,
            "group_size": request.group_size,
            "start_at": start_at,
            "return_deadline": end_at,
            "estimated_return_at": estimated_return_at,
            "origin_latitude": request.origin_latitude,
            "origin_longitude": request.origin_longitude,
            "origin_label": request.origin_label,
            "destination_latitude": request.destination_latitude,
            "destination_longitude": request.destination_longitude,
            "destination_label": request.destination_label,
            "stops": response_stops,
            "routes": routes,
            "explanation": explanation,
        }

    def _stop_dict(self, stop: ItineraryStop, experience: Experience, slot: ExperienceSlot, position: int) -> dict:
        poi_verified = entity_is_operationally_verified(self.db, "poi", experience.poi)
        experience_verified = entity_is_operationally_verified(self.db, "experience", experience)
        slot_verified = self.repository.is_fresh_slot(slot)
        is_demo = experience.verification_status == "simulated" and experience.poi.verification_status == "simulated"
        data_status = (
            "simulated" if is_demo else
            "verified" if poi_verified and experience_verified and slot_verified else
            "stale" if experience.verification_status == "verified" and experience.poi.verification_status == "verified" else
            "unverified"
        )
        poi_evidence = self.repository.source_evidence("poi", experience.poi.id, experience.poi.data_revision)
        experience_evidence = self.repository.source_evidence("experience", experience.id, experience.data_revision)
        slot_evidence = self.repository.source_evidence("slot", slot.id, slot.version)
        return {
            "id": stop.id or str(uuid4()), "experience_id": experience.id, "slot_id": slot.id,
            "position": position, "name": experience.name, "category": experience.poi.category,
            "arrival_at": as_aware(stop.arrival_at), "start_at": as_aware(slot.start_at), "end_at": as_aware(slot.end_at),
            "duration_min": experience.duration_min, "cost_vnd": experience.price_vnd,
            "locked": stop.locked, "availability_status": slot.status,
            "availability_known": slot.available_reported is not None,
            "data_status": data_status,
            "slot_confirmed_at": slot.confirmed_at,
            "slot_expires_at": slot.expires_at,
            "source_evidence": experience_evidence,
            "slot_source_evidence": slot_evidence,
            "poi": {"id": experience.poi.id, "name": experience.poi.name, "description": experience.poi.description,
                    "latitude": experience.poi.latitude, "longitude": experience.poi.longitude,
                    "category": experience.poi.category, "address": experience.poi.address,
                    "verification_status": experience.poi.verification_status,
                    "data_mode": "real" if poi_verified else "simulated",
                    "data_status": "simulated" if experience.poi.verification_status == "simulated" else "verified" if poi_verified else "stale" if experience.poi.verification_status == "verified" else "unverified",
                    "source_evidence": poi_evidence},
        }

    def get_itinerary(self, itinerary_id: str) -> dict | None:
        itinerary = self.db.scalar(
            select(Itinerary).where(Itinerary.id == itinerary_id).options(selectinload(Itinerary.stops).joinedload(ItineraryStop.experience).joinedload(Experience.poi), selectinload(Itinerary.stops).joinedload(ItineraryStop.slot))
        )
        if itinerary is None:
            return None
        stops = [self._stop_dict(stop, stop.experience, stop.slot, stop.position) for stop in itinerary.stops]
        routes = []
        travel = 0
        mode = itinerary.constraints.get("transport_mode", "driving")
        if stops and itinerary.origin_latitude is not None and itinerary.origin_longitude is not None:
            first = stops[0]
            route = self.routing.get_route((itinerary.origin_latitude, itinerary.origin_longitude),
                                           (first["poi"]["latitude"], first["poi"]["longitude"]), mode)
            travel += route.duration_min
            routes.append({"from_experience_id": None, "to_experience_id": first["experience_id"],
                           "from_label": itinerary.constraints.get("origin_label") or "Điểm xuất phát",
                           "distance_m": route.distance_m, "duration_min": route.duration_min,
                           **self.routing.eta_metadata(route)})
        for previous, current in zip(stops, stops[1:]):
            route = self.routing.get_route(
                (previous["poi"]["latitude"], previous["poi"]["longitude"]),
                (current["poi"]["latitude"], current["poi"]["longitude"]),
                mode,
            )
            travel += route.duration_min
            routes.append({"from_experience_id": previous["experience_id"], "to_experience_id": current["experience_id"], "distance_m": route.distance_m, "duration_min": route.duration_min, **self.routing.eta_metadata(route)})
        if stops and itinerary.destination_latitude is not None and itinerary.destination_longitude is not None:
            last = stops[-1]
            route = self.routing.get_route((last["poi"]["latitude"], last["poi"]["longitude"]),
                                           (itinerary.destination_latitude, itinerary.destination_longitude), mode)
            travel += route.duration_min
            routes.append({"from_experience_id": last["experience_id"], "to_experience_id": None,
                           "to_label": itinerary.constraints.get("destination_label") or "Điểm về",
                           "distance_m": route.distance_m, "duration_min": route.duration_min,
                           **self.routing.eta_metadata(route)})
        current_modes = {stop["data_status"] for stop in stops}
        reasons = ["SLOT_AVAILABLE"]
        if any(route["provider"] == "mock" for route in routes):
            reasons.append("MOCK_ROUTING")
        if any(route["provider"] != "mock" for route in routes):
            reasons.append("GOONG_ROUTING")
        if "verified" in current_modes:
            reasons.append("VERIFIED_DATA")
        if "simulated" in current_modes:
            reasons.append("SIMULATED_DATA")
        if "stale" in current_modes:
            reasons.append("STALE_DATA")
        if "unverified" in current_modes:
            reasons.append("UNVERIFIED_DATA")
        if any(not stop["availability_known"] for stop in stops):
            reasons.append("CAPACITY_UNKNOWN")
        intents = itinerary.constraints.get("intent_weights", {})
        requested_intents = {tag for tag, weight in intents.items() if weight > 0}
        provided_intents = {normalize_intent_tag(tag) for stop in itinerary.stops for tag in stop.experience.intent_tags}
        preserved = sorted(tag for tag in requested_intents if normalize_intent_tag(tag) in provided_intents)
        current_data_mode = (
            "real" if current_modes == {"verified"} else
            "simulated" if current_modes == {"simulated"} else
            "mixed" if current_modes else itinerary.data_mode
        )
        return {
            "request_id": itinerary.id, "itinerary_id": itinerary.id,
            "data_mode": current_data_mode,
            "data_as_of": itinerary.created_at, "feasibility_status": itinerary.status,
            "estimated_cost_vnd": itinerary.estimated_cost_vnd, "total_travel_min": travel,
            "group_size": itinerary.group_size, "stops": stops,
            "start_at": as_aware(itinerary.start_time or itinerary.start_at),
            "return_deadline": as_aware(itinerary.return_deadline or itinerary.end_at),
            "estimated_return_at": (as_aware(stops[-1]["end_at"]) if stops else as_aware(itinerary.end_at)) + timedelta(minutes=(routes[-1]["duration_min"] if routes and routes[-1].get("to_experience_id") is None else 0)),
            "origin_latitude": itinerary.origin_latitude,
            "origin_longitude": itinerary.origin_longitude,
            "origin_label": itinerary.constraints.get("origin_label"),
            "destination_latitude": itinerary.destination_latitude,
            "destination_longitude": itinerary.destination_longitude,
            "destination_label": itinerary.constraints.get("destination_label"),
            "routes": routes, "explanation": {
                **self.explainer.explain(reasons, preserved, sorted(requested_intents - set(preserved))),
                "evidence_refs": sorted({
                    evidence["id"]
                    for item in stops
                    for evidence in (item["poi"]["source_evidence"] + item["source_evidence"] + item["slot_source_evidence"])
                }),
            },
        }
