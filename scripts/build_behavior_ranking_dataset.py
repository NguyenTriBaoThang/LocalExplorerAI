"""Export consented Explore impressions as a de-identified ranking dataset.

The output contains one row per experience impression. It is a research
dataset, not an API-ready model bundle. Run after migration 0018 and after
eligible interactions have aged through the attribution window.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import sys
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.entities import (  # noqa: E402
    Booking,
    Itinerary,
    ItineraryStop,
    RecommendationConsent,
    RecommendationInteraction,
)


DEFAULT_OUTPUT = ROOT / "data" / "derived" / "behavior-ranking" / "training_dataset.csv"
ATTRIBUTION_DAYS = 7
HISTORY_DAYS = 90


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def pseudonymize(user_id: str) -> str:
    secret = settings.app_signing_secret
    if not secret:
        raise RuntimeError("Set APP_SIGNING_SECRET before exporting training data.")
    return hmac.new(secret.encode(), user_id.encode(), hashlib.sha256).hexdigest()[:32]


def tag_set(snapshot: dict[str, Any]) -> set[str]:
    values = snapshot.get("intent_tags") or []
    return {str(value).strip().casefold() for value in values if str(value).strip()}


def assign_outcome(row: dict[str, Any], grade: int, reason: str, action_at: datetime) -> None:
    if grade > row["label_grade"]:
        row["label_grade"] = grade
        row["label_reason"] = reason
        row["outcome_time"] = as_utc(action_at).isoformat()


def build_rows(db: Session, attribution_days: int, as_of: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    consented_users = set(db.scalars(
        select(RecommendationConsent.user_id).where(RecommendationConsent.model_training_enabled.is_(True))
    ).all())
    if not consented_users:
        return [], {"reason": "No users have opted in to model-training data use."}

    interactions = db.scalars(
        select(RecommendationInteraction)
        .where(
            RecommendationInteraction.user_id.in_(consented_users),
            RecommendationInteraction.model_training_eligible.is_(True),
        )
        .order_by(RecommendationInteraction.created_at, RecommendationInteraction.id)
    ).all()
    impressions = [row for row in interactions if row.event_type == "impression" and row.candidate_snapshot]
    if not impressions:
        return [], {"reason": "No model-training-eligible Explore impressions have been recorded."}

    rows: list[dict[str, Any]] = []
    row_by_impression_id: dict[str, dict[str, Any]] = {}
    by_request_experience: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    by_user_experience: dict[tuple[str, str], list[int]] = defaultdict(list)
    request_latest: dict[tuple[str, str], datetime] = {}
    for impression in impressions:
        created_at = as_utc(impression.created_at)
        experience_id = impression.experience_id or str(impression.candidate_snapshot.get("experience_id", ""))
        row = {
            "query_id": impression.request_id,
            "user_key": pseudonymize(impression.user_id),
            "event_time": created_at.isoformat(),
            "candidate_experience_id": experience_id,
            "display_position": impression.position,
            "user_intent_tags": ";".join(impression.context_snapshot.get("intent_tags", [])),
            "budget_band": impression.context_snapshot.get("budget_band", ""),
            "group_size": impression.context_snapshot.get("group_size", ""),
            "indoor_preference": impression.context_snapshot.get("indoor_preference", ""),
            "time_bucket": impression.context_snapshot.get("time_bucket", ""),
            "candidate_tags": ";".join(impression.candidate_snapshot.get("intent_tags", [])),
            "candidate_primary_intent": impression.candidate_snapshot.get("primary_intent") or "",
            "candidate_price_vnd": impression.candidate_snapshot.get("price_vnd"),
            "candidate_price_basis": impression.candidate_snapshot.get("price_basis") or "",
            "duration_min": impression.candidate_snapshot.get("duration_min"),
            "is_hands_on": impression.candidate_snapshot.get("is_hands_on"),
            "is_indoor": impression.candidate_snapshot.get("is_indoor"),
            "verification_status": impression.candidate_snapshot.get("verification_status") or "",
            "poi_category": impression.candidate_snapshot.get("poi_category") or "",
            "district": impression.candidate_snapshot.get("district") or "",
            "catalog_revision": impression.candidate_snapshot.get("data_revision"),
            "consent_version": impression.consent_version,
            "label_grade": 0,
            "label_reason": "shown_without_followup_after_attribution_window",
            "outcome_time": "",
        }
        index = len(rows)
        rows.append(row)
        row_by_impression_id[impression.id] = row
        by_request_experience[(impression.user_id, impression.request_id, experience_id)].append(index)
        by_user_experience[(impression.user_id, experience_id)].append(index)
        request_key = (impression.user_id, impression.request_id)
        request_latest[request_key] = max(request_latest.get(request_key, created_at), created_at)

    horizon = timedelta(days=attribution_days)

    # A direct selection is attributed only to the impression in that same list request.
    for interaction in interactions:
        if interaction.event_type != "selected" or not interaction.experience_id:
            continue
        action_at = as_utc(interaction.created_at)
        key = (interaction.user_id, interaction.request_id, interaction.experience_id)
        for index in by_request_experience.get(key, []):
            impression_at = datetime.fromisoformat(rows[index]["event_time"])
            if timedelta(0) <= action_at - impression_at <= horizon:
                assign_outcome(rows[index], 1, "experience_selected", action_at)

    # Plans and confirmed bookings are attributed to the most recent matching
    # impression within the window, avoiding duplicate credit for older views.
    plan_actions = db.execute(
        select(Itinerary.user_id, Itinerary.created_at, ItineraryStop.experience_id)
        .join(ItineraryStop, ItineraryStop.itinerary_id == Itinerary.id)
        .where(Itinerary.user_id.in_(consented_users))
    ).all()
    booking_actions = db.scalars(
        select(Booking).where(Booking.user_id.in_(consented_users), Booking.status == "confirmed")
    ).all()
    actions: list[tuple[datetime, str, str, int, str]] = []
    actions.extend(
        (as_utc(created_at), user_id, experience_id, 2, "experience_added_to_itinerary")
        for user_id, created_at, experience_id in plan_actions
        if user_id and created_at and experience_id
    )
    actions.extend(
        (as_utc(booking.confirmed_at or booking.updated_at or booking.created_at),
         booking.user_id, booking.experience_id, 3, "booking_confirmed")
        for booking in booking_actions
        if booking.user_id and booking.experience_id
    )
    for action_at, user_id, experience_id, grade, reason in sorted(actions, key=lambda item: item[0]):
        candidates = by_user_experience.get((user_id, experience_id), [])
        if not candidates:
            continue
        candidate_times = [datetime.fromisoformat(rows[index]["event_time"]) for index in candidates]
        position = bisect_right(candidate_times, action_at) - 1
        if position < 0:
            continue
        index = candidates[position]
        impression_at = candidate_times[position]
        if action_at - impression_at <= horizon:
            assign_outcome(rows[index], grade, reason, action_at)

    # Avoid treating recent, right-censored impressions as negative examples.
    mature_requests = {
        request_key
        for request_key, latest_at in request_latest.items()
        if as_of - latest_at >= horizon
    }
    # Keep only mature request groups. The user ID is intentionally not exported,
    # so derive membership from the already-pseudonymized impression rows.
    mature_request_keys = {
        (pseudonymize(user_id), request_id)
        for user_id, request_id in mature_requests
    }
    rows = [
        row for row in rows
        if (row["user_key"], row["query_id"]) in mature_request_keys
    ]

    # Historical affinity uses only earlier selected impressions from opted-in users.
    selected_by_user: dict[str, list[tuple[datetime, RecommendationInteraction]]] = defaultdict(list)
    for interaction in interactions:
        if interaction.event_type == "selected":
            selected_by_user[interaction.user_id].append((as_utc(interaction.created_at), interaction))
    for user_id, selected in selected_by_user.items():
        selected.sort(key=lambda item: item[0])
    # Revisit source impressions to calculate user features at request time.
    mature_ids = {
        item.id
        for item in impressions
        if (item.user_id, item.request_id) in mature_requests
    }
    for impression in impressions:
        if impression.id not in mature_ids:
            continue
        created_at = as_utc(impression.created_at)
        history = selected_by_user.get(impression.user_id, [])
        history_times = [item[0] for item in history]
        end = bisect_left(history_times, created_at)
        start = bisect_left(history_times, created_at - timedelta(days=HISTORY_DAYS))
        previous = history[start:end]
        tags: dict[str, int] = defaultdict(int)
        prices: list[float] = []
        indoor_values: list[float] = []
        for _, selected_event in previous:
            snapshot = selected_event.candidate_snapshot or {}
            for tag in tag_set(snapshot):
                tags[tag] += 1
            if snapshot.get("price_vnd") is not None and snapshot.get("price_basis") == "per_person":
                prices.append(float(snapshot["price_vnd"]))
            if snapshot.get("is_indoor") is not None:
                indoor_values.append(float(bool(snapshot["is_indoor"])))

        candidate_tags = tag_set(impression.candidate_snapshot or {})
        candidate_price = impression.candidate_snapshot.get("price_vnd")
        if impression.candidate_snapshot.get("price_basis") != "per_person":
            candidate_price = None
        candidate_indoor = impression.candidate_snapshot.get("is_indoor")
        history_count = len(previous)
        affinity = sum(tags.get(tag, 0) for tag in candidate_tags) / max(sum(tags.values()), 1)
        avg_price = sum(prices) / len(prices) if prices else None
        price_affinity = (
            1.0 / (1.0 + abs(float(candidate_price) - avg_price) / max(avg_price, 1.0))
            if candidate_price is not None and avg_price is not None else 0.0
        )
        avg_indoor = sum(indoor_values) / len(indoor_values) if indoor_values else None
        indoor_affinity = (
            1.0 - abs(float(bool(candidate_indoor)) - avg_indoor)
            if candidate_indoor is not None and avg_indoor is not None else 0.0
        )
        output = row_by_impression_id.get(impression.id)
        if output is not None:
            output.update({
                "user_has_history": int(history_count > 0),
                "user_history_count_90d": history_count,
                "user_candidate_tag_affinity": round(affinity, 6),
                "user_price_affinity": round(price_affinity, 6),
                "user_indoor_affinity": round(indoor_affinity, 6),
            })

    for row in rows:
        row.setdefault("user_has_history", 0)
        row.setdefault("user_history_count_90d", 0)
        row.setdefault("user_candidate_tag_affinity", 0.0)
        row.setdefault("user_price_affinity", 0.0)
        row.setdefault("user_indoor_affinity", 0.0)

    metadata = {
        "dataset_kind": "consented_user_behavior",
        "attribution_days": attribution_days,
        "history_days": HISTORY_DAYS,
        "impression_count_total": len(impressions),
        "mature_request_count": len(mature_requests),
        "training_row_count": len(rows),
        "label_counts": {str(label): sum(row["label_grade"] == label for row in rows) for label in range(4)},
        "label_note": "Unselected mature impressions are weak implicit negatives, not explicit dislikes.",
        "feedback_note": "Itinerary-level ratings are not assigned to individual experiences.",
        "user_identity": "HMAC pseudonym; APP_SIGNING_SECRET is not written to output.",
    }
    return rows, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--attribution-days", type=int, default=ATTRIBUTION_DAYS, choices=range(1, 91))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {args.output}; pass --overwrite to replace it.")

    db = SessionLocal()
    try:
        rows, metadata = build_rows(db, args.attribution_days, datetime.now(timezone.utc))
    finally:
        db.close()

    if not rows:
        raise SystemExit(metadata.get("reason", "No mature behavior rows are available yet."))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    metadata["output"] = str(args.output)
    args.output.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
