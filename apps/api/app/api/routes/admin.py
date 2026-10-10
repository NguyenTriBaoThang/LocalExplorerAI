import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement

from app.adapters.llm.provider import LLMNotConfigured, LLMProviderError
from app.adapters.routing.provider import RoutingConfigurationError, RoutingProviderError
from app.api.dependencies import get_db, get_llm_provider, require_roles
from app.models.entities import AuditLog, Evidence, Experience, ExperienceSlot, Itinerary, ItineraryStop, PlaceImportBatch, PlaceImportCandidate, POI, Provider, User
from app.schemas.management import AdminUserUpdateRequest, ModerationRequest, POIMergeRequest, ProviderCreateRequest
from app.services.auth_service import hash_password
from app.services.evidence_service import REQUIRED_FIELDS, covered_fields, current_verified_evidence, get_target, is_current_and_unexpired, target_revision, utc_now
from app.services.integration_config import (
    INTEGRATION_FIELDS,
    IntegrationSecretConfigurationError,
    list_integration_settings,
    resolve_integration_value,
    update_integration_settings,
)
from app.services.momo import get_momo_config
from app.services.place_label_suggestion_service import suggest_place_labels
from app.services.routing_service import make_geocoding_provider, make_routing_provider
from app.services.vnpay import get_vnpay_config

router = APIRouter(prefix="/api/admin", tags=["administration"])


class IntegrationSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict[str, str] = Field(default_factory=dict)
    remove_keys: list[str] = Field(default_factory=list, max_length=40)


class PlaceCandidatePromotion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    address: str = Field(min_length=5, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    category: str = Field(min_length=2, max_length=40)
    description: str = Field(default="", max_length=4000)
    source_uri: str = Field(min_length=12, max_length=1000)
    source_type: str = Field(min_length=3, max_length=40)
    source_label: str = Field(min_length=2, max_length=180)
    license: str | None = Field(default=None, max_length=120)
    fields_covered: list[str] = Field(min_length=1, max_length=10)
    observed_at: datetime
    expires_at: datetime

    @field_validator("observed_at", "expires_at")
    @classmethod
    def require_timezone_aware_dates(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Evidence timestamps must include a timezone.")
        return value


def _normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    unaccented = "".join(character for character in decomposed if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", "", unaccented)


def _audit(db: Session, actor: User, action: str, target_type: str, target_id: str, details: dict | None = None) -> None:
    db.add(AuditLog(id=str(uuid4()), actor_id=actor.id, action=action, target_type=target_type,
                    target_id=target_id, details=details or {}, created_at=datetime.now(timezone.utc)))


@router.get("/dashboard")
def dashboard(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    return {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "providers": db.scalar(select(func.count(Provider.id))) or 0,
        "pending_experiences": db.scalar(select(func.count(Experience.id)).where(Experience.verification_status == "pending")) or 0,
        "pending_pois": db.scalar(select(func.count(POI.id)).where(POI.verification_status == "pending")) or 0,
        "pending_evidence": db.scalar(select(func.count(Evidence.id)).where(Evidence.verification_status == "pending")) or 0,
        "unknown_slot_capacity": db.scalar(select(func.count(ExperienceSlot.id)).where(ExperienceSlot.available_reported.is_(None))) or 0,
        "expired_evidence": db.scalar(select(func.count(Evidence.id)).where(Evidence.expires_at.is_not(None), Evidence.expires_at < datetime.now(timezone.utc))) or 0,
    }


@router.get("/users")
def list_users(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db), limit: int = Query(default=100, ge=1, le=500)):
    records = db.scalars(select(User).order_by(User.created_at.desc()).limit(limit)).all()
    return [{"id": item.id, "email": item.email, "display_name": item.display_name, "role": item.role,
             "provider_id": item.provider_id, "is_active": item.is_active, "created_at": item.created_at} for item in records]


@router.get("/providers")
def list_providers(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db), limit: int = Query(default=200, ge=1, le=500)):
    rows = db.scalars(select(Provider).order_by(Provider.name).limit(limit)).all()
    return [{"id": item.id, "name": item.name, "slug": item.slug, "verification_status": item.verification_status,
             "is_active": item.is_active} for item in rows]


@router.get("/ai/targets")
def ai_tool_targets(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    """Return minimal identifiers for admin AI tools without exposing traveler data."""
    experiences = db.execute(
        select(Experience.id, Experience.title, Experience.name)
        .order_by(Experience.name).limit(500)
    ).all()
    itineraries = db.execute(
        select(Itinerary.id, Itinerary.planned_date, Itinerary.created_at)
        .order_by(Itinerary.created_at.desc()).limit(500)
    ).all()
    return {
        "experiences": [{"id": row.id, "title": row.title or row.name} for row in experiences],
        "itineraries": [{"id": row.id, "planned_date": row.planned_date, "created_at": row.created_at}
                        for row in itineraries],
    }


@router.get("/place-imports")
def list_place_imports(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    batches = db.scalars(select(PlaceImportBatch).order_by(PlaceImportBatch.created_at.desc()).limit(100)).all()
    return [{"id": item.id, "source_name": item.source_name, "source_sha256": item.source_sha256,
             "worksheet_name": item.worksheet_name, "record_count": item.record_count,
             "quality_summary": item.quality_summary, "created_at": item.created_at}
            for item in batches]


@router.get("/place-imports/{batch_id}/candidates")
def list_place_import_candidates(
    batch_id: str,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
    limit: int = Query(default=250, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    if db.get(PlaceImportBatch, batch_id) is None:
        raise HTTPException(status_code=404, detail={"code": "PLACE_IMPORT_NOT_FOUND", "message": "Import batch not found."})
    rows = db.execute(
        select(PlaceImportCandidate, POI.verification_status)
        .outerjoin(POI, POI.id == PlaceImportCandidate.target_poi_id)
        .where(PlaceImportCandidate.batch_id == batch_id)
        .order_by(PlaceImportCandidate.source_row).offset(offset).limit(limit)
    ).all()
    return [{"id": item.id, "external_id": item.external_id, "source_row": item.source_row,
             "name": item.name, "kind": item.kind, "raw_payload": item.raw_payload,
             "suggested_labels": suggest_place_labels(item.raw_payload, item.kind),
             "quality_flags": item.quality_flags, "review_status": item.review_status,
             "target_poi_id": item.target_poi_id, "target_poi_status": poi_status,
             "created_at": item.created_at}
            for item, poi_status in rows]


@router.post("/place-imports/{batch_id}/candidates/{candidate_id}/promote")
def promote_place_candidate(
    batch_id: str,
    candidate_id: str,
    payload: PlaceCandidatePromotion,
    actor: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Submit one imported POI with current source evidence; moderation publishes it later."""
    candidate = db.scalar(select(PlaceImportCandidate).where(
        PlaceImportCandidate.id == candidate_id,
        PlaceImportCandidate.batch_id == batch_id,
    ))
    if candidate is None:
        raise HTTPException(status_code=404, detail={"code": "PLACE_CANDIDATE_NOT_FOUND", "message": "Place candidate not found in this import."})
    if candidate.target_poi_id:
        return {"poi_id": candidate.target_poi_id, "status": "already_submitted"}
    if candidate.review_status != "needs_enrichment":
        raise HTTPException(status_code=409, detail={"code": "PLACE_CANDIDATE_NOT_PROMOTABLE", "message": "Only candidates awaiting enrichment can be promoted."})

    required_fields = REQUIRED_FIELDS["poi"]
    if set(payload.fields_covered) != required_fields:
        missing = sorted(required_fields - set(payload.fields_covered))
        extra = sorted(set(payload.fields_covered) - required_fields)
        raise HTTPException(status_code=422, detail={"code": "POI_EVIDENCE_FIELDS_INCOMPLETE", "message": "The source must explicitly support every required POI field.", "details": {"missing": missing, "unsupported": extra}})
    source = urlparse(payload.source_uri.strip())
    if source.scheme != "https" or not source.hostname or source.username or source.password:
        raise HTTPException(status_code=422, detail={"code": "INVALID_EVIDENCE_URL", "message": "Evidence URL must be an HTTPS URL without embedded credentials."})
    now = datetime.now(timezone.utc)
    if payload.observed_at > now or payload.expires_at <= now or payload.expires_at <= payload.observed_at:
        raise HTTPException(status_code=422, detail={"code": "EVIDENCE_NOT_CURRENT", "message": "Evidence must have a past observation time and a future expiry time."})

    poi_id = str(uuid4())
    poi = POI(
        id=poi_id,
        name=candidate.name,
        description=payload.description.strip() or str(candidate.raw_payload.get("description") or "").strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        geom=WKTElement(f"POINT({payload.longitude} {payload.latitude})", srid=4326),
        category=payload.category.strip(),
        address=payload.address.strip(),
        source_attribution=payload.source_label.strip(),
        verification_status="pending",
        data_revision=1,
    )
    db.add(poi)
    db.add(Evidence(
        id=str(uuid4()),
        source_uri=payload.source_uri.strip(),
        source_type=payload.source_type.strip(),
        source_label=payload.source_label.strip(),
        license=payload.license.strip() if payload.license else None,
        notes=f"Admin-verified enrichment of source row {candidate.source_row}.",
        submitted_by=actor.id,
        target_type="poi",
        target_id=poi_id,
        target_revision=1,
        fields_covered=sorted(required_fields),
        observed_at=payload.observed_at,
        valid_from=payload.observed_at,
        expires_at=payload.expires_at,
        verification_status="pending",
    ))
    candidate.review_status = "submitted_for_review"
    candidate.target_poi_id = poi_id
    _audit(db, actor, "place_import.candidate_evidence_submitted", "poi", poi_id, {
        "batch_id": batch_id,
        "candidate_id": candidate.id,
        "source_row": candidate.source_row,
        "source_uri": payload.source_uri,
        "fields_covered": sorted(required_fields),
        "expires_at": payload.expires_at.isoformat(),
    })
    db.commit()
    return {"poi_id": poi_id, "status": "pending_review", "data_mode": "not_public"}


@router.patch("/users/{user_id}")
def update_user(user_id: str, payload: AdminUserUpdateRequest, actor: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    if target.id == actor.id and (not payload.is_active or payload.role != "admin"):
        raise HTTPException(status_code=409, detail={"code": "SELF_LOCKOUT", "message": "You cannot deactivate or demote your own account."})
    if payload.role == "provider":
        if not payload.provider_id or db.get(Provider, payload.provider_id) is None:
            raise HTTPException(status_code=422, detail={"code": "PROVIDER_REQUIRED", "message": "Provider accounts must be linked to a provider profile."})
        target.provider_id = payload.provider_id
    else:
        target.provider_id = None
    old_role, old_active = target.role, target.is_active
    target.role, target.is_active = payload.role, payload.is_active
    _audit(db, actor, "user.updated", "user", target.id, {"old_role": old_role, "role": target.role, "old_active": old_active, "is_active": target.is_active})
    db.commit()
    return {"id": target.id, "role": target.role, "provider_id": target.provider_id, "is_active": target.is_active}


@router.post("/providers", status_code=201)
def create_provider(payload: ProviderCreateRequest, actor: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail={"code": "EMAIL_IN_USE", "message": "This email is already registered."})
    slug_base = re.sub(r"[^a-z0-9]+", "-", payload.name.strip().lower()).strip("-")[:160] or "provider"
    slug = f"{slug_base}-{uuid4().hex[:8]}"
    provider = Provider(id=str(uuid4()), name=payload.name.strip(), slug=slug, address=payload.address,
                        contact_phone=payload.contact_phone, contact_email=email, verification_status="pending")
    db.add(provider)
    db.flush()
    account = User(id=str(uuid4()), email=email, display_name=payload.name.strip(), password_hash=hash_password(payload.password),
                   role="provider", provider_id=provider.id)
    db.add(account)
    _audit(db, actor, "provider.created", "provider", provider.id, {"user_id": account.id})
    db.commit()
    return {"provider_id": provider.id, "user_id": account.id, "role": account.role, "verification_status": provider.verification_status}


@router.get("/moderation")
def moderation_queue(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db), status: str = Query(default="pending", pattern="^(pending|simulated|verified|rejected|hidden)$")):
    pois = db.scalars(select(POI).where(POI.verification_status == status).order_by(POI.created_at.desc()).limit(250)).all()
    experiences = db.scalars(select(Experience).where(Experience.verification_status == status).order_by(Experience.created_at.desc()).limit(250)).all()
    evidence = db.scalars(select(Evidence).where(Evidence.verification_status == status).order_by(Evidence.created_at.desc()).limit(250)).all()
    return {
        "pois": [{"id": item.id, "name": item.name, "address": item.address, "status": item.verification_status} for item in pois],
        "experiences": [{"id": item.id, "title": item.title, "provider_id": item.provider_id, "status": item.verification_status} for item in experiences],
        "evidence": [{"id": item.id, "source_uri": item.source_uri, "source_type": item.source_type,
                      "source_label": item.source_label, "license": item.license, "notes": item.notes,
                      "target_type": item.target_type, "target_id": item.target_id,
                      "target_revision": item.target_revision, "fields_covered": item.fields_covered,
                      "observed_at": item.observed_at, "expires_at": item.expires_at,
                      "submitted_by": item.submitted_by, "status": item.verification_status} for item in evidence],
    }


@router.patch("/moderation/{entity_type}/{entity_id}")
def review_entity(entity_type: str, entity_id: str, payload: ModerationRequest, actor: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    models = {"poi": POI, "experience": Experience, "evidence": Evidence}
    model = models.get(entity_type)
    if model is None:
        raise HTTPException(status_code=404, detail={"code": "ENTITY_TYPE_NOT_FOUND", "message": "Use poi, experience or evidence."})
    entity = db.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail={"code": "ENTITY_NOT_FOUND", "message": "Entity not found."})
    now = utc_now()
    if payload.action == "approve" and isinstance(entity, Evidence):
        target = get_target(db, entity.target_type or "", entity.target_id or "")
        if target is None:
            raise HTTPException(status_code=409, detail={"code": "EVIDENCE_TARGET_REQUIRED", "message": "Evidence must be attached to a POI, experience, or slot before approval."})
        if entity.target_revision != target_revision(entity.target_type, target):
            raise HTTPException(status_code=409, detail={"code": "EVIDENCE_STALE_REVISION", "message": "The target changed after this evidence was submitted. Submit fresh evidence."})
        if not is_current_and_unexpired(entity, now):
            raise HTTPException(status_code=409, detail={"code": "EVIDENCE_EXPIRED_OR_UNDATED", "message": "Evidence needs a valid observation time and a future expiry."})
        if entity.target_type not in REQUIRED_FIELDS or not set(entity.fields_covered or {}).issubset(REQUIRED_FIELDS[entity.target_type]):
            raise HTTPException(status_code=422, detail={"code": "INVALID_EVIDENCE_COVERAGE", "message": "Evidence field coverage is missing or invalid."})
    if payload.action == "approve" and isinstance(entity, (POI, Experience)):
        kind = "poi" if isinstance(entity, POI) else "experience"
        current_evidence = current_verified_evidence(db, kind, entity.id, entity.data_revision)
        missing_fields = sorted(REQUIRED_FIELDS[kind] - covered_fields(current_evidence))
        if missing_fields:
            raise HTTPException(status_code=409, detail={
                "code": "CATALOG_EVIDENCE_INCOMPLETE",
                "message": "Cannot approve catalog data until every required field is covered by current, reviewed, unexpired evidence.",
                "missing_fields": missing_fields,
            })
        if isinstance(entity, Experience) and not entity_is_verified_poi(db, entity.poi_id):
            raise HTTPException(status_code=409, detail={"code": "POI_NOT_VERIFIED", "message": "Verify the linked POI and its evidence before approving an experience."})
    entity.verification_status = {"approve": "verified", "reject": "rejected", "hide": "hidden"}[payload.action]
    if isinstance(entity, Evidence):
        entity.reviewed_by = actor.id
        entity.reviewed_at = now
        if payload.action == "approve":
            entity.verified_by = actor.id
            entity.verified_at = now
    _audit(db, actor, f"{entity_type}.{payload.action}", entity_type, entity_id, {"note": payload.note, "new_status": entity.verification_status})
    db.commit()
    return {"entity_type": entity_type, "id": entity_id, "status": entity.verification_status}


def entity_is_verified_poi(db: Session, poi_id: str) -> bool:
    poi = db.get(POI, poi_id)
    if poi is None or poi.verification_status != "verified":
        return False
    evidence = current_verified_evidence(db, "poi", poi.id, poi.data_revision)
    return REQUIRED_FIELDS["poi"].issubset(covered_fields(evidence))


@router.get("/duplicates/pois")
def duplicate_pois(actor: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    pois = db.scalars(select(POI).order_by(POI.name)).all()
    pairs = []
    for index, left in enumerate(pois):
        left_name = _normalized_name(left.name)
        for right in pois[index + 1:]:
            right_name = _normalized_name(right.name)
            score = SequenceMatcher(None, left_name, right_name).ratio()
            if score >= 0.88:
                pairs.append({"poi_a": {"id": left.id, "name": left.name}, "poi_b": {"id": right.id, "name": right.name}, "name_similarity": round(score, 3)})
    return pairs


@router.post("/duplicates/pois/merge")
def merge_duplicate_pois(payload: POIMergeRequest, actor: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    if payload.keep_id == payload.duplicate_id:
        raise HTTPException(status_code=422, detail={"code": "SAME_POI", "message": "The retained and duplicate POIs must differ."})
    keep, duplicate = db.get(POI, payload.keep_id), db.get(POI, payload.duplicate_id)
    if keep is None or duplicate is None:
        raise HTTPException(status_code=404, detail={"code": "POI_NOT_FOUND", "message": "Both POIs must exist."})
    experience_count = db.query(Experience).filter(Experience.poi_id == duplicate.id).update({Experience.poi_id: keep.id}, synchronize_session=False)
    stop_count = db.query(ItineraryStop).filter(ItineraryStop.poi_id == duplicate.id).update({ItineraryStop.poi_id: keep.id}, synchronize_session=False)
    duplicate.verification_status = "hidden"
    _audit(db, actor, "poi.merged", "poi", duplicate.id, {"kept_poi_id": keep.id, "reason": payload.reason,
        "experiences_relinked": experience_count, "stops_relinked": stop_count})
    db.commit()
    return {"kept_poi_id": keep.id, "hidden_duplicate_id": duplicate.id,
            "experiences_relinked": experience_count, "stops_relinked": stop_count}


@router.get("/audit")
def audit_history(actor: User = Depends(require_roles("admin")), db: Session = Depends(get_db), limit: int = Query(default=100, ge=1, le=500)):
    logs = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [{"id": item.id, "actor_id": item.actor_id, "action": item.action, "target_type": item.target_type,
             "target_id": item.target_id, "details": item.details, "created_at": item.created_at} for item in logs]


@router.get("/integrations")
def integrations(actor: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    try:
        return list_integration_settings(db)
    except IntegrationSecretConfigurationError as error:
        raise HTTPException(status_code=503, detail={
            "code": "INTEGRATION_SECRETS_NOT_CONFIGURED",
            "message": str(error),
        }) from error


@router.put("/integrations/{service}")
def update_integrations(
    service: str,
    payload: IntegrationSettingsUpdate,
    actor: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    if service not in INTEGRATION_FIELDS:
        raise HTTPException(status_code=404, detail={"code": "INTEGRATION_NOT_FOUND", "message": "This integration is not managed by the application."})
    try:
        updated, removed = update_integration_settings(db, service, payload.values, payload.remove_keys, actor.id)
    except IntegrationSecretConfigurationError as error:
        raise HTTPException(status_code=503, detail={"code": "INTEGRATION_SECRETS_NOT_CONFIGURED", "message": str(error)}) from error
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=422, detail={"code": "INVALID_INTEGRATION_SETTINGS", "message": str(error)}) from error
    if updated or removed:
        _audit(db, actor, "integration.settings_updated", "integration", service, {
            "updated_keys": sorted(updated), "removed_keys": sorted(removed),
        })
        db.commit()
    try:
        return list_integration_settings(db)
    except IntegrationSecretConfigurationError as error:
        raise HTTPException(status_code=503, detail={"code": "INTEGRATION_SECRETS_NOT_CONFIGURED", "message": str(error)}) from error


@router.post("/integrations/{service}/test")
def test_integration_connection(
    service: str,
    actor: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Run a small, non-customer-data health check and never return provider payloads or secrets."""
    if service not in {"ai", "routing", "payments", "google_oauth"}:
        raise HTTPException(
            status_code=404,
            detail={"code": "INTEGRATION_TEST_UNSUPPORTED", "message": "Connection tests are available for AI, routing, payments, and Google OAuth integrations."},
        )

    status = "failed"
    detail_vi = None
    if service == "ai":
        provider = get_llm_provider(db)
        if provider.model_name == "not-configured":
            status = "not_configured"
            detail_vi = "Chưa cấu hình API Key hoặc nhà cung cấp AI (Gemini hoặc OpenAI)."
        else:
            try:
                response = provider.generate(
                    "Connection check only. Return the requested JSON object.",
                    {"check": "connection"},
                    {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False},
                )
                if response.get("ok") is True:
                    status = "connected"
                    detail_vi = f"Đã kết nối thành công tới mô hình '{provider.model_name}'."
                else:
                    status = "invalid_response"
                    detail_vi = "Mô hình AI phản hồi nhưng không khớp dữ liệu kiểm tra."
            except LLMNotConfigured as exc:
                status = "not_configured"
                detail_vi = str(exc)
            except LLMProviderError as exc:
                status = "failed"
                err_text = str(exc)
                if "API_KEY_INVALID" in err_text or "400" in err_text or "403" in err_text:
                    detail_vi = f"Khóa AI API không hợp lệ hoặc bị từ chối: {err_text}. Vui lòng kiểm tra lại khóa Gemini / OpenAI."
                else:
                    detail_vi = f"Lỗi gọi AI: {err_text}"
    elif service == "routing":
        provider_name = (resolve_integration_value(db, "routing", "provider") or "goong").strip().lower()
        if provider_name == "mock":
            status = "connected"
            detail_vi = "Chế độ Tuyến đường giả lập (Mock Routing) đang hoạt động bình thường."
        else:
            api_key = resolve_integration_value(db, "routing", "goong_api_key")
            if not api_key:
                status = "not_configured"
                detail_vi = "Chưa nhập Goong API Key."
            else:
                try:
                    resolution = make_geocoding_provider(db).forward("Ho Chi Minh City, Vietnam", limit=1)
                    route = make_routing_provider(db).get_route(
                        (10.7769, 106.7009), (10.7829, 106.6951), "motorcycle",
                    )
                    if resolution.results and route.distance_m > 0 and route.duration_min > 0:
                        status = "connected"
                        maptiles_key = resolve_integration_value(db, "routing", "goong_maptiles_key")
                        maptiles_note = f" Đồng thời phát hiện Goong Maptiles Key ({maptiles_key[:6]}...) sẵn sàng cho đồ họa bản đồ nền." if maptiles_key else ""
                        detail_vi = f"Kết nối Goong thành công! Geocode tìm thấy '{resolution.results[0].formatted_address}', Tuyến đường: {route.distance_m}m (~{route.duration_min} phút).{maptiles_note}"
                    else:
                        status = "no_results"
                        detail_vi = "Kết nối được nhưng Goong không trả kết quả kiểm tra mẫu."
                except (IntegrationSecretConfigurationError, RoutingConfigurationError) as exc:
                    status = "not_configured"
                    detail_vi = str(exc)
                except RoutingProviderError as exc:
                    status = "failed"
                    err_msg = str(exc)
                    if "403" in err_msg or "API_KEY_INVALID" in err_msg or "401" in err_msg:
                        detail_vi = (
                            "Lỗi từ chối truy cập (403 Forbidden / API_KEY_INVALID).\n"
                            "⚠️ LƯU Ý QUAN TRỌNG: Goong phân chia 2 loại khóa riêng biệt:\n"
                            "1. 'Maptiles Key' (chỉ dùng tải bản đồ nền tile — bạn có thể đã lấy nhầm loại này)\n"
                            "2. 'API Key' (dùng cho REST API Tuyến đường & Geocode)\n"
                            "👉 Cách khắc phục: Vào account.goong.io -> mục 'API Keys' -> bấm nút 'Tạo Key' -> CHỌN LOẠI 'API Key' (không chọn Maptiles Key) -> Copy khóa đó và dán lại vào ô 'Goong API key'."
                        )
                    else:
                        detail_vi = f"Lỗi phản hồi từ Goong: {err_msg}"
    elif service == "payments":
        provider_name = (resolve_integration_value(db, "payments", "provider") or "vnpay").strip().lower()
        if provider_name == "vnpay":
            tmn = resolve_integration_value(db, "payments", "vnpay_tmn_code")
            secret = resolve_integration_value(db, "payments", "vnpay_hash_secret")
            if get_vnpay_config(db).vnpay_checkout_enabled:
                status = "configured"
                detail_vi = f"Cấu hình VNPay hợp lệ (TMN Code: {tmn}, Hash Secret: đã thiết lập)."
            else:
                status = "not_configured"
                detail_vi = "Chưa cấu hình đầy đủ VNPay TMN Code hoặc Hash Secret."
        else:
            partner = resolve_integration_value(db, "payments", "momo_partner_code")
            access = resolve_integration_value(db, "payments", "momo_access_key")
            secret = resolve_integration_value(db, "payments", "momo_secret_key")
            if get_momo_config(db).checkout_enabled:
                status = "configured"
                detail_vi = f"Cấu hình MoMo hợp lệ (Partner Code: {partner}, Access Key: đã thiết lập)."
            else:
                status = "not_configured"
                detail_vi = "Chưa cấu hình đầy đủ MoMo Partner Code, Access Key hoặc Secret Key."
    elif service == "google_oauth":
        from app.api.routes.auth import _google_configuration_issue

        client_id = resolve_integration_value(db, "google_oauth", "client_id")
        client_secret = resolve_integration_value(db, "google_oauth", "client_secret")
        if client_id and client_secret and not _google_configuration_issue(db):
            status = "configured"
            detail_vi = f"Cấu hình Google OAuth hợp lệ (Client ID: {client_id[:16]}...)."
        else:
            status = "not_configured"
            detail_vi = "Chưa cấu hình đầy đủ Google OAuth Client ID hoặc Client Secret."
    else:
        status = "not_configured"
        detail_vi = "Dịch vụ không hỗ trợ kiểm tra trực tiếp."

    if service == "payments" and status == "configured":
        detail_vi = "Merchant credentials and public HTTPS callbacks pass configuration checks; complete a sandbox checkout to verify gateway/IPN behavior."
    elif service == "google_oauth" and status == "configured":
        detail_vi = "Client credentials and HTTPS callback pass configuration checks; complete a browser sign-in in staging."

    _audit(db, actor, "integration.connection_tested", "integration", service, {"status": status})
    db.commit()
    messages = {
        "connected": "Kết nối dịch vụ thành công.",
        "not_configured": "Chưa cấu hình đầy đủ hoặc chưa thể giải mã khóa tích hợp.",
        "invalid_response": "Dịch vụ đã trả lời nhưng không đúng định dạng kiểm tra.",
        "no_results": "Kết nối được nhưng dịch vụ không trả kết quả kiểm tra.",
        "failed": "Không thể kết nối tới dịch vụ.",
    }
    messages["configured"] = "Configuration checks passed; complete the sandbox transaction or browser OAuth flow on staging."
    return {
        "service": service,
        "status": status,
        "ok": status in {"connected", "configured"},
        "check_type": "external_request" if service in {"ai", "routing"} else "configuration_only",
        "message_vi": messages[status],
        "detail_vi": detail_vi,
    }
