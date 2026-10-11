from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Evidence, Experience, ExperienceSlot, POI


REQUIRED_FIELDS = {
    "poi": {"name", "address", "latitude", "longitude", "category"},
    "experience": {"title", "description", "primary_intent", "intent_tags", "is_hands_on", "duration_min", "price_vnd", "price_basis"},
    "slot": {"start_at", "end_at", "capacity_total", "available_reported", "status"},
}
TARGET_MODELS = {"poi": POI, "experience": Experience, "slot": ExperienceSlot}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def target_revision(target_type: str, target: POI | Experience | ExperienceSlot) -> int:
    return target.version if target_type == "slot" else target.data_revision


def get_target(db: Session, target_type: str, target_id: str):
    model = TARGET_MODELS.get(target_type)
    return db.get(model, target_id) if model else None


def is_current_and_unexpired(evidence: Evidence, now: datetime | None = None) -> bool:
    now = now or utc_now()
    if not evidence.expires_at or not evidence.observed_at:
        return False
    observed_at = evidence.observed_at
    expires_at = evidence.expires_at
    valid_from = evidence.valid_from
    # SQLite may return naive datetimes for timezone-aware columns.
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if valid_from and valid_from.tzinfo is None:
        valid_from = valid_from.replace(tzinfo=timezone.utc)
    return observed_at <= now and expires_at > now and (valid_from is None or valid_from <= now)


def current_verified_evidence(
    db: Session, target_type: str, target_id: str, revision: int | None = None,
) -> list[Evidence]:
    query = select(Evidence).where(
        Evidence.target_type == target_type,
        Evidence.target_id == target_id,
        Evidence.verification_status == "verified",
    )
    if revision is not None:
        query = query.where(Evidence.target_revision == revision)
    return [item for item in db.scalars(query.order_by(Evidence.observed_at.desc())).all() if is_current_and_unexpired(item)]


def covered_fields(evidence_items: list[Evidence]) -> set[str]:
    return {field for evidence in evidence_items for field in (evidence.fields_covered or [])}


def entity_is_operationally_verified(
    db: Session,
    target_type: str,
    target,
    evidence_items: list[Evidence] | None = None,
) -> bool:
    if target is None or getattr(target, "verification_status", None) != "verified":
        return False
    revision = target_revision(target_type, target)
    evidence = evidence_items if evidence_items is not None else current_verified_evidence(db, target_type, target.id, revision)
    return REQUIRED_FIELDS[target_type].issubset(covered_fields(evidence))


def slot_is_operationally_verified(
    db: Session,
    slot: ExperienceSlot,
    evidence_items: list[Evidence] | None = None,
) -> bool:
    evidence = evidence_items if evidence_items is not None else current_verified_evidence(db, "slot", slot.id, slot.version)
    if not REQUIRED_FIELDS["slot"].issubset(covered_fields(evidence)) or not slot.expires_at or not slot.confirmed_at:
        return False
    expires_at = slot.expires_at
    confirmed_at = slot.confirmed_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if confirmed_at.tzinfo is None:
        confirmed_at = confirmed_at.replace(tzinfo=timezone.utc)
    now = utc_now()
    return confirmed_at <= now and expires_at > now


def evidence_summary(evidence: Evidence) -> dict:
    return {
        "id": evidence.id,
        "source_uri": evidence.source_uri,
        "source_type": evidence.source_type,
        "source_label": evidence.source_label,
        "license": evidence.license,
        "fields_covered": evidence.fields_covered or [],
        "observed_at": evidence.observed_at,
        "expires_at": evidence.expires_at,
        "verification_status": evidence.verification_status,
        "target_type": evidence.target_type,
    }
