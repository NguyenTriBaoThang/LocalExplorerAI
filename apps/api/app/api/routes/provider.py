from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from geoalchemy2.elements import WKTElement

from app.api.dependencies import get_db, require_roles
from app.core.request_context import current_request_id
from app.models.entities import AuditLog, Booking, BookingEvent, Event, Evidence, Experience, ExperienceSlot, Itinerary, ItineraryStop, PaymentTransaction, POI, Provider, User
from app.schemas.management import EvidenceCreateRequest, ExperienceDraftRequest, POIDraftRequest, SlotCreateRequest, SlotUpdateRequest
from app.services.auth_service import hash_password
from app.services.evidence_service import REQUIRED_FIELDS, target_revision, utc_now
from app.services.notifications import enqueue_email, queue_booking_status

router = APIRouter(prefix="/api/provider", tags=["provider portal"])


def _provider(db: Session, user: User) -> Provider:
    provider = db.get(Provider, user.provider_id) if user.provider_id else None
    if provider is None or not provider.is_active:
        raise HTTPException(status_code=403, detail={"code": "PROVIDER_PROFILE_REQUIRED", "message": "This account has no active provider profile."})
    return provider


def _audit(db: Session, actor: User, action: str, target_type: str, target_id: str, details: dict | None = None) -> None:
    audit_details = dict(details or {})
    if request_id := current_request_id.get():
        audit_details["request_id"] = request_id
    db.add(AuditLog(id=str(uuid4()), actor_id=actor.id, action=action, target_type=target_type, target_id=target_id, details=audit_details, created_at=datetime.now(timezone.utc)))


@router.get("/me")
def provider_profile(user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = _provider(db, user)
    return {"id": provider.id, "name": provider.name, "slug": provider.slug, "description": provider.description,
            "contact_phone": provider.contact_phone, "contact_email": provider.contact_email, "address": provider.address,
            "verification_status": provider.verification_status}


@router.get("/experiences")
def list_provider_experiences(user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = _provider(db, user)
    items = db.scalars(select(Experience).where(Experience.provider_id == provider.id).options(joinedload(Experience.poi))).unique().all()
    return [{"id": item.id, "poi_id": item.poi_id, "title": item.title, "description": item.description,
             "primary_intent": item.primary_intent, "intent_tags": item.intent_tags,
             "is_hands_on": item.is_hands_on, "is_indoor": item.is_indoor,
             "duration_min": item.duration_min, "price_vnd": item.price_vnd, "price_basis": item.price_basis,
             "verification_status": item.verification_status, "poi_name": item.poi.name,
             "slots": [{"id": slot.id, "start_at": slot.start_at, "end_at": slot.end_at,
                        "capacity_total": slot.capacity_total, "available_reported": slot.available_reported,
                        "confirmed_at": slot.confirmed_at, "expires_at": slot.expires_at,
                        "status": slot.status, "version": slot.version} for slot in item.slots]}
            for item in items]


@router.get("/pois")
def list_provider_pois(user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = _provider(db, user)
    experience_poi_ids = select(Experience.poi_id).where(Experience.provider_id == provider.id)
    items = db.scalars(select(POI).where(
        (POI.submitted_by_provider_id == provider.id) | POI.id.in_(experience_poi_ids)
    ).order_by(POI.name)).all()
    return [{"id": item.id, "name": item.name, "description": item.description, "district": item.district,
             "latitude": item.latitude, "longitude": item.longitude, "category": item.category,
             "address": item.address, "verification_status": item.verification_status,
             "data_revision": item.data_revision} for item in items]


@router.post("/pois", status_code=201)
def create_poi(payload: POIDraftRequest, user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = _provider(db, user)
    poi = POI(
        id=str(uuid4()), name=payload.name.strip(), description=payload.description.strip(),
        district=payload.district, latitude=payload.latitude, longitude=payload.longitude,
        geom=WKTElement(f"POINT({payload.longitude} {payload.latitude})", srid=4326),
        category=payload.category.strip(), address=payload.address.strip(),
        submitted_by_provider_id=provider.id, verification_status="pending", data_revision=1,
    )
    db.add(poi)
    _audit(db, user, "poi.created", "poi", poi.id, {"status": "pending", "data_revision": poi.data_revision})
    db.commit()
    return {"id": poi.id, "verification_status": poi.verification_status, "data_revision": poi.data_revision}


@router.patch("/pois/{poi_id}")
def update_poi(poi_id: str, payload: POIDraftRequest, user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = _provider(db, user)
    poi = db.get(POI, poi_id)
    if poi is None:
        raise HTTPException(status_code=404, detail={"code": "POI_NOT_FOUND", "message": "POI not found."})
    owns_poi = poi.submitted_by_provider_id == provider.id or (db.scalar(select(func.count(Experience.id)).where(
        Experience.poi_id == poi.id, Experience.provider_id == provider.id,
    )) or 0) > 0
    if not owns_poi:
        raise HTTPException(status_code=403, detail={"code": "POI_FORBIDDEN", "message": "Providers can update only their own POIs."})
    for key, value in payload.model_dump().items():
        setattr(poi, key, value.strip() if isinstance(value, str) else value)
    poi.geom = WKTElement(f"POINT({payload.longitude} {payload.latitude})", srid=4326)
    poi.data_revision += 1
    if poi.verification_status != "hidden":
        poi.verification_status = "pending"
    _audit(db, user, "poi.updated", "poi", poi.id, {"data_revision": poi.data_revision, "previous_evidence_invalidated": True})
    db.commit()
    return {"id": poi.id, "verification_status": poi.verification_status, "data_revision": poi.data_revision}


@router.post("/evidence", status_code=201)
def submit_evidence(payload: EvidenceCreateRequest, user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = _provider(db, user)
    target = db.get(POI if payload.target_type == "poi" else Experience, payload.target_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "EVIDENCE_TARGET_NOT_FOUND", "message": "Target record not found."})
    if payload.target_type == "poi":
        owns_target = target.submitted_by_provider_id == provider.id or (db.scalar(select(func.count(Experience.id)).where(
            Experience.poi_id == target.id, Experience.provider_id == provider.id,
        )) or 0) > 0
    else:
        owns_target = target.provider_id == provider.id
    if not owns_target:
        raise HTTPException(status_code=403, detail={"code": "EVIDENCE_TARGET_FORBIDDEN", "message": "Providers can submit evidence only for their own catalog records."})
    unknown_fields = set(payload.fields_covered) - REQUIRED_FIELDS[payload.target_type]
    if unknown_fields:
        raise HTTPException(status_code=422, detail={"code": "UNKNOWN_EVIDENCE_FIELDS", "message": "Evidence references fields outside this target type.", "fields": sorted(unknown_fields)})
    now = utc_now()
    observed_at = payload.observed_at.astimezone(now.tzinfo)
    expires_at = payload.expires_at.astimezone(now.tzinfo)
    if observed_at > now:
        raise HTTPException(status_code=422, detail={"code": "OBSERVATION_IN_FUTURE", "message": "Observed time cannot be in the future."})
    if expires_at <= now:
        raise HTTPException(status_code=422, detail={"code": "EVIDENCE_ALREADY_EXPIRED", "message": "Expiry must be in the future."})
    evidence = Evidence(
        id=str(uuid4()), source_uri=payload.source_uri, source_type=payload.source_type,
        source_label=payload.source_label, license=payload.license, notes=payload.notes,
        submitted_by=user.id, target_type=payload.target_type, target_id=target.id,
        target_revision=target_revision(payload.target_type, target), fields_covered=payload.fields_covered,
        observed_at=observed_at, expires_at=expires_at, verification_status="pending",
    )
    db.add(evidence)
    _audit(db, user, "evidence.submitted", "evidence", evidence.id, {
        "target_type": payload.target_type, "target_id": target.id,
        "fields_covered": payload.fields_covered,
    })
    db.commit()
    return {"id": evidence.id, "status": evidence.verification_status, "target_revision": evidence.target_revision}


@router.post("/experiences", status_code=201)
def create_experience(payload: ExperienceDraftRequest, user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = _provider(db, user)
    poi = db.get(POI, payload.poi_id)
    if poi is None:
        raise HTTPException(status_code=404, detail={"code": "POI_NOT_FOUND", "message": "Choose an existing point of interest."})
    item = Experience(id=str(uuid4()), provider_id=provider.id, poi_id=poi.id, name=payload.title, title=payload.title,
                      description=payload.description, primary_intent=payload.primary_intent,
                      intent_tags=payload.intent_tags, is_hands_on=payload.is_hands_on,
                      is_indoor=payload.is_indoor, indoor=payload.is_indoor, duration_min=payload.duration_min,
                      price_basis=payload.price_basis, price_vnd=payload.price_vnd, verification_status="pending")
    db.add(item)
    db.flush()
    _audit(db, user, "experience.created", "experience", item.id, {"status": "pending"})
    db.commit()
    return {"id": item.id, "verification_status": item.verification_status}


@router.patch("/experiences/{experience_id}")
def update_experience(experience_id: str, payload: ExperienceDraftRequest, user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = _provider(db, user)
    item = db.scalar(select(Experience).where(Experience.id == experience_id, Experience.provider_id == provider.id))
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "EXPERIENCE_NOT_FOUND", "message": "Experience not found for this provider."})
    if db.get(POI, payload.poi_id) is None:
        raise HTTPException(status_code=404, detail={"code": "POI_NOT_FOUND", "message": "Choose an existing point of interest."})
    old_status = item.verification_status
    for key, value in payload.model_dump().items():
        if key == "title":
            item.name = value
            item.title = value
        elif key == "is_indoor":
            item.indoor = value
            item.is_indoor = value
        else:
            setattr(item, key, value)
    item.data_revision += 1
    if old_status != "hidden":
        item.verification_status = "pending"
    _audit(db, user, "experience.updated", "experience", item.id, {
        "review_reset": old_status == "verified", "data_revision": item.data_revision,
        "previous_evidence_invalidated": True,
    })
    db.commit()
    return {"id": item.id, "verification_status": item.verification_status}


@router.delete("/experiences/{experience_id}")
def hide_experience(experience_id: str, user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = _provider(db, user)
    item = db.scalar(select(Experience).where(Experience.id == experience_id, Experience.provider_id == provider.id))
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "EXPERIENCE_NOT_FOUND", "message": "Experience not found for this provider."})
    item.verification_status = "hidden"
    _audit(db, user, "experience.hidden", "experience", item.id, {"soft_delete": True})
    db.commit()
    return {"id": item.id, "verification_status": item.verification_status}


@router.post("/experiences/{experience_id}/slots", status_code=201)
def create_slot(experience_id: str, payload: SlotCreateRequest, user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = _provider(db, user)
    item = db.scalar(select(Experience).where(Experience.id == experience_id, Experience.provider_id == provider.id))
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "EXPERIENCE_NOT_FOUND", "message": "Experience not found for this provider."})
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=422, detail={"code": "INVALID_SLOT_RANGE", "message": "Slot end must be after start."})
    now = utc_now()
    expires_at = payload.expires_at.astimezone(now.tzinfo)
    start_at = payload.start_at.astimezone(now.tzinfo)
    if expires_at <= now or expires_at > start_at:
        raise HTTPException(status_code=422, detail={"code": "INVALID_SLOT_EXPIRY", "message": "Slot confirmation must expire after now and no later than the slot start."})
    if payload.available_reported > payload.capacity_total:
        raise HTTPException(status_code=422, detail={"code": "CAPACITY_EXCEEDED", "message": "Available seats cannot exceed total capacity."})
    slot = ExperienceSlot(id=str(uuid4()), experience_id=item.id, start_at=payload.start_at, end_at=payload.end_at,
                          capacity_total=payload.capacity_total, available_reported=payload.available_reported,
                          confirmed_at=now, expires_at=expires_at,
                          status="open" if payload.available_reported else "full", version=1)
    db.add(slot)
    db.flush()
    db.add(Evidence(
        id=str(uuid4()), source_uri=f"provider://{provider.id}/slots/{slot.id}",
        source_type="provider_confirmation", source_label=provider.name,
        notes="Authenticated provider confirmation recorded by the provider portal.", submitted_by=user.id,
        target_type="slot", target_id=slot.id, target_revision=slot.version,
        fields_covered=sorted(REQUIRED_FIELDS["slot"]), observed_at=now, expires_at=expires_at,
        verification_status="verified", verified_by=user.id, verified_at=now,
    ))
    _audit(db, user, "slot.created", "experience_slot", slot.id, {"experience_id": item.id})
    db.commit()
    return {"id": slot.id, "version": slot.version, "status": slot.status}


@router.patch("/slots/{slot_id}")
def update_slot(slot_id: str, payload: SlotUpdateRequest, user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = _provider(db, user)
    slot = db.scalar(select(ExperienceSlot).join(Experience).where(ExperienceSlot.id == slot_id, Experience.provider_id == provider.id).with_for_update())
    if slot is None:
        raise HTTPException(status_code=404, detail={"code": "SLOT_NOT_FOUND", "message": "Slot not found for this provider."})
    if slot.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"code": "SLOT_VERSION_CHANGED", "message": "Reload the slot and retry with its latest version."})
    if payload.capacity_total is not None:
        slot.capacity_total = payload.capacity_total
    previous_status = slot.status
    if payload.status == "full" and payload.available_reported not in (None, 0):
        raise HTTPException(status_code=422, detail={"code": "FULL_SLOT_HAS_CAPACITY", "message": "A full slot cannot report available seats."})
    if payload.status == "open" and payload.available_reported == 0:
        raise HTTPException(status_code=422, detail={"code": "OPEN_SLOT_HAS_NO_CAPACITY", "message": "Use full status when no seats remain."})
    now = utc_now()
    expired_holds = db.scalars(select(Booking).where(
        Booking.slot_id == slot.id,
        Booking.status.in_(["pending_provider", "awaiting_payment"]),
        Booking.hold_expires_at.is_not(None),
        Booking.hold_expires_at <= now,
    )).all()
    for booking in expired_holds:
        previous_booking_status = booking.status
        booking.status = "expired"
        booking.updated_at = now
        db.add(BookingEvent(
            id=str(uuid4()), booking_id=booking.id, actor_user_id=None,
            event_type="hold_expired", from_status=previous_booking_status, to_status="expired",
            details={"reason": "hold_timeout", "slot_id": slot.id}, created_at=now,
        ))
    db.flush()
    active_reservations = db.scalars(select(Booking).where(
        Booking.slot_id == slot.id,
        Booking.status.in_(["pending_provider", "awaiting_payment", "confirmed", "cancellation_requested", "refund_pending"]),
    )).all()
    reserved_seats = sum(
        booking.quantity for booking in active_reservations
        if booking.status not in {"pending_provider", "awaiting_payment"}
        or (booking.hold_expires_at is not None and (booking.hold_expires_at.replace(tzinfo=booking.hold_expires_at.tzinfo or timezone.utc) > now))
    )
    if payload.status != "cancelled" and payload.available_reported is not None and payload.available_reported < reserved_seats:
        raise HTTPException(status_code=409, detail={"code": "CAPACITY_BELOW_ACTIVE_HOLDS", "message": "Số chỗ mới thấp hơn các yêu cầu giữ chỗ đang hoạt động; hãy xử lý các yêu cầu trước."})
    effective_capacity = payload.capacity_total if payload.capacity_total is not None else slot.capacity_total
    effective_available = payload.available_reported if payload.available_reported is not None else slot.available_reported
    if payload.status != "cancelled" and effective_capacity is not None and effective_available is not None and effective_available > effective_capacity:
        raise HTTPException(status_code=422, detail={"code": "CAPACITY_EXCEEDED", "message": "Số chỗ khả dụng không thể vượt tổng sức chứa."})
    if payload.status != "cancelled" and effective_capacity is not None and effective_capacity < reserved_seats:
        raise HTTPException(status_code=409, detail={"code": "CAPACITY_BELOW_ACTIVE_HOLDS", "message": "Tổng sức chứa mới thấp hơn số khách đã được giữ/xác nhận."})
    if slot.expires_at is not None and (slot.expires_at.tzinfo is None or slot.expires_at.utcoffset() is None):
        slot.expires_at = slot.expires_at.replace(tzinfo=timezone.utc)
    if payload.expires_at is not None:
        slot.expires_at = payload.expires_at.astimezone(now.tzinfo)
    if payload.status == "open":
        if slot.expires_at is None or slot.expires_at <= now or slot.expires_at > slot.start_at.replace(tzinfo=slot.start_at.tzinfo or now.tzinfo):
            raise HTTPException(status_code=422, detail={"code": "FRESH_SLOT_CONFIRMATION_REQUIRED", "message": "Opening a slot requires a future expiry no later than its start time."})
    slot.status = payload.status
    if payload.available_reported is not None:
        if slot.capacity_total is not None and payload.available_reported > slot.capacity_total:
            raise HTTPException(status_code=422, detail={"code": "CAPACITY_EXCEEDED", "message": "Available seats cannot exceed total capacity."})
        slot.available_reported = payload.available_reported
    if slot.status == "cancelled" and previous_status != "cancelled":
        slot.available_reported = 0
        slot_event = Event(id=str(uuid4()), event_type="SLOT_CANCELLED", target_type="experience_slot", target_id=slot.id,
                           status="active", event_metadata={"source": "provider_portal", "provider_id": provider.id,
                                                              "request_id": current_request_id.get()})
        db.add(slot_event)
        db.flush()
        affected_users = db.scalars(select(User).join(Itinerary, Itinerary.user_id == User.id).join(
            ItineraryStop, ItineraryStop.itinerary_id == Itinerary.id
        ).where(ItineraryStop.slot_id == slot.id, ItineraryStop.status == "planned").distinct()).all()
        for traveler in affected_users:
            enqueue_email(
                db, idempotency_key=f"slot-cancelled:{slot_event.id}:user:{traveler.id}", recipient=traveler,
                event_id=slot_event.id, subject="Local Explorer AI: ca trong lich trinh da bi huy",
                body=f"Xin chao {traveler.display_name or ''},\n\nMot ca trong lich trinh cua ban vua bi co so huy. Hay dang nhap de xem canh bao va dieu chinh lich.\nMa su kien: {slot_event.id}",
            )
        for booking in active_reservations:
            old_booking_status = booking.status
            if booking.status in {"pending_provider", "awaiting_payment"}:
                booking.status = "cancelled"
                booking.cancelled_at = now
                booking.hold_expires_at = None
                event_type = "slot_cancelled_before_payment"
            else:
                booking.status = "cancellation_requested"
                booking.cancellation_reason = "Cơ sở đã hủy ca hoạt động."
                event_type = "provider_cancelled_paid_booking_refund_review_required"
                for payment in db.scalars(select(PaymentTransaction).where(
                    PaymentTransaction.booking_id == booking.id, PaymentTransaction.status == "succeeded",
                )).all():
                    payment.status = "refund_pending"
            booking.updated_at = now
            db.add(BookingEvent(
                id=str(uuid4()), booking_id=booking.id, actor_user_id=user.id,
                event_type=event_type, from_status=old_booking_status, to_status=booking.status,
                details={"slot_id": slot.id, "refund_requires_configured_gateway": booking.status == "cancellation_requested"},
                created_at=now,
            ))
            queue_booking_status(db, booking, event_type)
    elif previous_status == "cancelled" and slot.status != "cancelled":
        active_events = db.scalars(select(Event).where(Event.target_id == slot.id, Event.event_type == "SLOT_CANCELLED", Event.status == "active")).all()
        for event in active_events:
            event.status = "resolved"
    slot.version += 1
    slot.confirmed_at = now
    if slot.expires_at and slot.expires_at > now:
        db.add(Evidence(
            id=str(uuid4()), source_uri=f"provider://{provider.id}/slots/{slot.id}",
            source_type="provider_confirmation", source_label=provider.name,
            notes="Authenticated provider confirmation recorded by the provider portal.", submitted_by=user.id,
            target_type="slot", target_id=slot.id, target_revision=slot.version,
            fields_covered=sorted(REQUIRED_FIELDS["slot"]), observed_at=now, expires_at=slot.expires_at,
            verification_status="verified", verified_by=user.id, verified_at=now,
        ))
    affected = db.scalar(select(func.count(func.distinct(ItineraryStop.itinerary_id))).where(ItineraryStop.slot_id == slot.id, ItineraryStop.status == "planned")) or 0
    _audit(db, user, "slot.updated", "experience_slot", slot.id, {"status": slot.status, "affected_itineraries": affected})
    db.commit()
    return {"id": slot.id, "version": slot.version, "status": slot.status, "available_reported": slot.available_reported,
            "affected_itineraries": affected}


@router.get("/audit")
def provider_audit(user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = _provider(db, user)
    experience_ids = db.scalars(select(Experience.id).where(Experience.provider_id == provider.id)).all()
    slot_ids = db.scalars(select(ExperienceSlot.id).join(Experience).where(Experience.provider_id == provider.id)).all()
    poi_ids = db.scalars(select(POI.id).where(
        (POI.submitted_by_provider_id == provider.id) | POI.id.in_(select(Experience.poi_id).where(Experience.provider_id == provider.id))
    )).all()
    evidence_ids = db.scalars(select(Evidence.id).where(Evidence.submitted_by == user.id)).all()
    target_ids = [*experience_ids, *slot_ids, *poi_ids, *evidence_ids]
    if not target_ids:
        return []
    logs = db.scalars(select(AuditLog).where(
        AuditLog.target_id.in_(target_ids)
    ).order_by(AuditLog.created_at.desc()).limit(100)).all()
    return [{"id": log.id, "action": log.action, "target_type": log.target_type, "target_id": log.target_id,
             "details": log.details, "created_at": log.created_at} for log in logs]


@router.get("/evidence")
def provider_evidence(user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    _provider(db, user)
    items = db.scalars(select(Evidence).where(Evidence.submitted_by == user.id).order_by(Evidence.created_at.desc()).limit(500)).all()
    return [{"id": item.id, "target_type": item.target_type, "target_id": item.target_id,
             "source_uri": item.source_uri, "source_type": item.source_type, "source_label": item.source_label,
             "license": item.license, "fields_covered": item.fields_covered or [], "observed_at": item.observed_at,
             "expires_at": item.expires_at, "verification_status": item.verification_status,
             "reviewed_at": item.reviewed_at, "notes": item.notes} for item in items]
