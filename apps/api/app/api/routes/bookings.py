from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, require_roles
from app.core.request_context import current_request_id
from app.models.entities import (
    AuditLog,
    Booking,
    BookingEvent,
    Experience,
    ExperienceSlot,
    Itinerary,
    ItineraryStop,
    PaymentTransaction,
    POI,
    Provider,
    User,
)
from app.schemas.booking import BookingCancelRequest, BookingCancellationDecisionRequest, BookingDecisionRequest, BookingHoldRequest
from app.services.evidence_service import entity_is_operationally_verified, slot_is_operationally_verified
from app.services.notifications import queue_booking_status

router = APIRouter(tags=["bookings and payments"])
_LIVE_STATUSES = ("pending_provider", "awaiting_payment", "confirmed", "cancellation_requested", "refund_pending")
_HOLD_STATUSES = ("pending_provider", "awaiting_payment")
_HOLD_MINUTES = 15


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        return value.replace(tzinfo=timezone.utc)
    return value


def _event(db: Session, booking: Booking, actor: User | None, event_type: str, old_status: str | None, details: dict | None = None) -> None:
    event_details = dict(details or {})
    if request_id := current_request_id.get():
        event_details["request_id"] = request_id
    db.add(BookingEvent(
        id=str(uuid4()), booking_id=booking.id, actor_user_id=actor.id if actor else None,
        event_type=event_type, from_status=old_status, to_status=booking.status,
        details=event_details, created_at=_now(),
    ))
    queue_booking_status(db, booking, event_type)
    if actor:
        db.add(AuditLog(
            id=str(uuid4()), actor_id=actor.id, action=f"booking.{event_type}",
            target_type="booking", target_id=booking.id, details=event_details, created_at=_now(),
        ))


def _expire_slot_holds(db: Session, slot_id: str, now: datetime) -> None:
    rows = db.scalars(select(Booking).where(
        Booking.slot_id == slot_id,
        Booking.status.in_(_HOLD_STATUSES),
        Booking.hold_expires_at.is_not(None),
        Booking.hold_expires_at <= now,
    )).all()
    for row in rows:
        old = row.status
        row.status = "expired"
        row.updated_at = now
        _event(db, row, None, "hold_expired", old, {"reason": "hold_timeout"})


def _held_seats(db: Session, slot_id: str, now: datetime) -> int:
    rows = db.scalars(select(Booking).where(Booking.slot_id == slot_id, Booking.status.in_(_LIVE_STATUSES))).all()
    return sum(
        row.quantity for row in rows
        if row.status not in _HOLD_STATUSES or (_aware(row.hold_expires_at) is not None and _aware(row.hold_expires_at) > now)
    )


def _payload(db: Session, booking: Booking) -> dict:
    experience = db.get(Experience, booking.experience_id)
    slot = db.get(ExperienceSlot, booking.slot_id)
    provider = db.get(Provider, booking.provider_id)
    return {
        "id": booking.id,
        "itinerary_id": booking.itinerary_id,
        "itinerary_stop_id": booking.itinerary_stop_id,
        "experience_id": booking.experience_id,
        "experience_title": experience.title if experience else "",
        "slot_id": booking.slot_id,
        "slot_status": slot.status if slot else "unknown",
        "slot_start_at": slot.start_at if slot else None,
        "provider_id": booking.provider_id,
        "provider_name": provider.name if provider else "",
        "quantity": booking.quantity,
        "amount_vnd": booking.amount_vnd,
        "currency": booking.currency,
        "status": booking.status,
        "hold_expires_at": booking.hold_expires_at,
        "provider_confirmed_at": booking.provider_confirmed_at,
        "confirmed_at": booking.confirmed_at,
        "cancellation_reason": booking.cancellation_reason,
        "created_at": booking.created_at,
        "updated_at": booking.updated_at,
    }


@router.get("/api/payments/status")
def payment_status():
    # Fail closed until the team chooses a gateway, configures its credentials,
    # webhook verification, and cancellation/refund policy.
    return {"provider": "unconfigured", "checkout_enabled": False, "refunds_enabled": False,
            "message": "Chưa cấu hình cổng thanh toán; hệ thống không thu tiền hoặc xác nhận đã thanh toán."}


@router.post("/api/bookings", status_code=201)
def request_booking(payload: BookingHoldRequest, user: User = Depends(require_roles("traveler")), db: Session = Depends(get_db)):
    now = _now()
    itinerary = db.get(Itinerary, payload.itinerary_id)
    if itinerary is None:
        raise HTTPException(status_code=404, detail={"code": "ITINERARY_NOT_FOUND", "message": "Không tìm thấy lịch trình."})
    if itinerary.user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "ITINERARY_FORBIDDEN", "message": "Chỉ chủ lịch trình mới có thể yêu cầu giữ chỗ."})
    stop = db.get(ItineraryStop, payload.itinerary_stop_id)
    if stop is None or stop.itinerary_id != itinerary.id:
        raise HTTPException(status_code=404, detail={"code": "ITINERARY_STOP_NOT_FOUND", "message": "Điểm dừng không thuộc lịch trình này."})
    if stop.status != "planned":
        raise HTTPException(status_code=409, detail={"code": "ITINERARY_STOP_INACTIVE", "message": "Điểm dừng này không còn là một hoạt động đang có trong lịch trình."})
    if payload.quantity > itinerary.group_size:
        raise HTTPException(status_code=422, detail={"code": "QUANTITY_EXCEEDS_GROUP_SIZE", "message": "Số khách đặt không thể lớn hơn quy mô nhóm của lịch trình."})

    # Lock the slot row so concurrent requests are serialized on PostgreSQL.
    slot = db.scalar(select(ExperienceSlot).where(ExperienceSlot.id == stop.slot_id).with_for_update())
    experience = db.scalar(select(Experience).where(Experience.id == stop.experience_id).with_for_update())
    if slot is None or experience is None or slot.experience_id != experience.id:
        raise HTTPException(status_code=409, detail={"code": "BOOKABLE_SLOT_CHANGED", "message": "Ca đã thay đổi; hãy tải lại lịch trình."})
    provider = db.get(Provider, experience.provider_id)
    poi = db.scalar(select(POI).where(POI.id == experience.poi_id).with_for_update())
    if not provider or not provider.is_active or not poi:
        raise HTTPException(status_code=409, detail={"code": "PROVIDER_UNAVAILABLE", "message": "Cơ sở hiện không thể nhận yêu cầu."})
    if not entity_is_operationally_verified(db, "experience", experience) or not entity_is_operationally_verified(db, "poi", poi):
        raise HTTPException(status_code=409, detail={"code": "CATALOG_NOT_VERIFIED", "message": "Chỉ có thể giữ chỗ cho địa điểm và trải nghiệm đã được xác minh nguồn."})

    _expire_slot_holds(db, slot.id, now)
    db.flush()
    if slot.status != "open" or slot.start_at.replace(tzinfo=slot.start_at.tzinfo or timezone.utc) <= now:
        raise HTTPException(status_code=409, detail={"code": "SLOT_NOT_BOOKABLE", "message": "Ca này không còn mở để giữ chỗ."})
    if slot.available_reported is None or not slot_is_operationally_verified(db, slot):
        raise HTTPException(status_code=409, detail={"code": "CAPACITY_NOT_CONFIRMED", "message": "Sức chứa của ca chưa được cơ sở xác nhận còn hiệu lực."})
    if slot.capacity_total is not None and payload.quantity > slot.capacity_total:
        raise HTTPException(status_code=422, detail={"code": "QUANTITY_EXCEEDS_CAPACITY", "message": "Số khách vượt sức chứa toàn ca."})
    if db.scalar(select(Booking.id).where(
        Booking.user_id == user.id, Booking.itinerary_stop_id == stop.id,
        Booking.status.in_(_LIVE_STATUSES),
    ).limit(1)):
        raise HTTPException(status_code=409, detail={"code": "BOOKING_ALREADY_EXISTS", "message": "Bạn đã có yêu cầu giữ chỗ đang xử lý cho điểm dừng này."})
    remaining = slot.available_reported - _held_seats(db, slot.id, now)
    if payload.quantity > remaining:
        raise HTTPException(status_code=409, detail={"code": "INSUFFICIENT_CAPACITY", "message": "Số chỗ còn lại không đủ; cơ sở cần cập nhật sức chứa."})

    price = int(experience.price_vnd or 0)
    amount = price * payload.quantity if experience.price_basis == "per_person" else price
    if amount > itinerary.budget_vnd:
        raise HTTPException(status_code=409, detail={"code": "BOOKING_OVER_BUDGET", "message": "Giá đặt chỗ hiện tại vượt ngân sách lịch trình; hãy kiểm tra lại giá với cơ sở."})
    hold_until = min(now + timedelta(minutes=_HOLD_MINUTES), _aware(slot.start_at))
    if hold_until <= now:
        raise HTTPException(status_code=409, detail={"code": "SLOT_STARTED", "message": "Ca đã bắt đầu hoặc đã qua."})
    booking = Booking(
        id=str(uuid4()), user_id=user.id, provider_id=provider.id, itinerary_id=itinerary.id,
        itinerary_stop_id=stop.id, experience_id=experience.id, slot_id=slot.id,
        quantity=payload.quantity, amount_vnd=amount, currency="VND", status="pending_provider",
        hold_expires_at=hold_until, created_at=now, updated_at=now,
    )
    db.add(booking)
    db.flush()
    _event(db, booking, user, "hold_requested", None, {"quantity": payload.quantity, "amount_vnd": amount})
    db.commit()
    db.refresh(booking)
    return _payload(db, booking)


@router.get("/api/bookings")
def my_bookings(itinerary_id: str | None = Query(default=None, max_length=36), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = _now()
    for booking in db.scalars(select(Booking).where(
        Booking.user_id == user.id, Booking.status.in_(_HOLD_STATUSES),
        Booking.hold_expires_at.is_not(None), Booking.hold_expires_at <= now,
    )).all():
        old = booking.status
        booking.status = "expired"
        booking.updated_at = now
        _event(db, booking, None, "hold_expired", old, {"reason": "hold_timeout"})
    query = select(Booking).where(Booking.user_id == user.id)
    if itinerary_id:
        query = query.where(Booking.itinerary_id == itinerary_id)
    rows = db.scalars(query.order_by(Booking.created_at.desc()).limit(200)).all()
    db.commit()
    return [_payload(db, row) for row in rows]


@router.post("/api/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: str, payload: BookingCancelRequest, user: User = Depends(require_roles("traveler")), db: Session = Depends(get_db)):
    booking = db.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
    if booking is None or booking.user_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Không tìm thấy yêu cầu đặt chỗ."})
    if booking.status in ("pending_provider", "awaiting_payment") or (booking.status == "confirmed" and booking.amount_vnd == 0):
        old = booking.status
        booking.status = "cancelled"
        booking.cancelled_at = _now()
        booking.hold_expires_at = None
        booking.cancellation_reason = payload.reason.strip() or None
        _event(db, booking, user, "cancelled_before_payment", old, {"reason": booking.cancellation_reason})
    elif booking.status == "confirmed":
        old = booking.status
        booking.status = "cancellation_requested"
        booking.cancellation_reason = payload.reason.strip() or None
        _event(db, booking, user, "cancellation_requested", old, {"reason": booking.cancellation_reason, "refund_requires_gateway": True})
    else:
        raise HTTPException(status_code=409, detail={"code": "BOOKING_NOT_CANCELLABLE", "message": "Yêu cầu đang ở trạng thái không thể hủy."})
    booking.updated_at = _now()
    db.commit()
    db.refresh(booking)
    return _payload(db, booking)


@router.post("/api/bookings/{booking_id}/checkout")
def begin_checkout(booking_id: str, user: User = Depends(require_roles("traveler")), db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if booking is None or booking.user_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Không tìm thấy yêu cầu đặt chỗ."})
    if booking.status != "awaiting_payment" or (_aware(booking.hold_expires_at) is None or _aware(booking.hold_expires_at) <= _now()):
        raise HTTPException(status_code=409, detail={"code": "BOOKING_NOT_READY_FOR_PAYMENT", "message": "Cơ sở chưa xác nhận yêu cầu hoặc thời hạn giữ chỗ đã hết."})
    raise HTTPException(status_code=503, detail={
        "code": "PAYMENT_GATEWAY_NOT_CONFIGURED",
        "message": "Cơ sở đã xác nhận chỗ, nhưng cổng thanh toán chưa được nhóm cấu hình. Chưa có khoản tiền nào bị thu.",
    })


@router.get("/api/provider/me/bookings")
def provider_bookings(user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = db.get(Provider, user.provider_id) if user.provider_id else None
    if provider is None or not provider.is_active:
        raise HTTPException(status_code=403, detail={"code": "PROVIDER_PROFILE_REQUIRED", "message": "Tài khoản chưa có hồ sơ cơ sở hoạt động."})
    now = _now()
    for booking in db.scalars(select(Booking).where(
        Booking.provider_id == provider.id, Booking.status.in_(_HOLD_STATUSES),
        Booking.hold_expires_at.is_not(None), Booking.hold_expires_at <= now,
    )).all():
        old = booking.status
        booking.status = "expired"
        booking.updated_at = now
        _event(db, booking, None, "hold_expired", old, {"reason": "hold_timeout"})
    rows = db.scalars(select(Booking).where(Booking.provider_id == provider.id).order_by(Booking.created_at.desc()).limit(200)).all()
    db.commit()
    return [_payload(db, row) for row in rows]


@router.post("/api/provider/me/bookings/{booking_id}/decision")
def decide_booking(booking_id: str, payload: BookingDecisionRequest, user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = db.get(Provider, user.provider_id) if user.provider_id else None
    if provider is None or not provider.is_active:
        raise HTTPException(status_code=403, detail={"code": "PROVIDER_PROFILE_REQUIRED", "message": "Tài khoản chưa có hồ sơ cơ sở hoạt động."})
    initial = db.scalar(select(Booking).where(Booking.id == booking_id, Booking.provider_id == provider.id))
    if initial is None:
        raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Không tìm thấy yêu cầu đặt chỗ."})
    now = _now()
    slot = db.scalar(select(ExperienceSlot).where(ExperienceSlot.id == initial.slot_id).with_for_update())
    booking = db.scalar(select(Booking).where(Booking.id == booking_id, Booking.provider_id == provider.id).with_for_update())
    if booking is None:
        raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Không tìm thấy yêu cầu đặt chỗ."})
    _expire_slot_holds(db, booking.slot_id, now)
    db.flush()
    if booking.status != "pending_provider":
        raise HTTPException(status_code=409, detail={"code": "BOOKING_NOT_PENDING", "message": "Yêu cầu không còn chờ cơ sở xác nhận."})
    if payload.action == "reject":
        old = booking.status
        booking.status = "rejected"
        booking.hold_expires_at = None
        booking.updated_at = now
        _event(db, booking, user, "provider_rejected", old, {"note": payload.note.strip()})
    else:
        if slot is None or slot.status != "open" or not slot.available_reported or not slot_is_operationally_verified(db, slot):
            raise HTTPException(status_code=409, detail={"code": "PROVIDER_CAPACITY_CONFIRMATION_STALE", "message": "Trước khi nhận yêu cầu, hãy mở ca và xác nhận lại số chỗ còn hiệu lực."})
        if _held_seats(db, slot.id, now) > slot.available_reported:
            raise HTTPException(status_code=409, detail={"code": "PROVIDER_CAPACITY_EXCEEDED", "message": "Tổng yêu cầu giữ chỗ vượt số chỗ cơ sở vừa xác nhận; hãy cập nhật slot trước."})
        old = booking.status
        booking.status = "confirmed" if booking.amount_vnd == 0 else "awaiting_payment"
        booking.provider_confirmed_at = now
        booking.confirmed_at = now if booking.amount_vnd == 0 else None
        booking.hold_expires_at = None if booking.amount_vnd == 0 else min(now + timedelta(minutes=_HOLD_MINUTES), _aware(slot.start_at))
        booking.updated_at = now
        _event(db, booking, user, "provider_confirmed_free_booking" if booking.amount_vnd == 0 else "provider_capacity_confirmed", old,
               {"note": payload.note.strip(), "slot_version": slot.version})
    db.commit()
    db.refresh(booking)
    return _payload(db, booking)


@router.post("/api/provider/me/bookings/{booking_id}/cancellation-decision")
def decide_cancellation(booking_id: str, payload: BookingCancellationDecisionRequest, user: User = Depends(require_roles("provider")), db: Session = Depends(get_db)):
    provider = db.get(Provider, user.provider_id) if user.provider_id else None
    if provider is None or not provider.is_active:
        raise HTTPException(status_code=403, detail={"code": "PROVIDER_PROFILE_REQUIRED", "message": "Tài khoản chưa có hồ sơ cơ sở hoạt động."})
    initial = db.scalar(select(Booking).where(Booking.id == booking_id, Booking.provider_id == provider.id))
    if initial is None:
        raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Không tìm thấy yêu cầu đặt chỗ."})
    slot = db.scalar(select(ExperienceSlot).where(ExperienceSlot.id == initial.slot_id).with_for_update())
    booking = db.scalar(select(Booking).where(Booking.id == booking_id, Booking.provider_id == provider.id).with_for_update())
    if booking is None or booking.status != "cancellation_requested":
        raise HTTPException(status_code=409, detail={"code": "CANCELLATION_NOT_PENDING", "message": "Không có yêu cầu hủy đang chờ xử lý."})
    if payload.action == "reject" and slot is not None and slot.status == "cancelled":
        raise HTTPException(status_code=409, detail={"code": "PROVIDER_CANCELLED_SLOT", "message": "Không thể từ chối hủy sau khi cơ sở đã hủy ca."})
    successful_payment = db.scalar(select(PaymentTransaction).where(
        PaymentTransaction.booking_id == booking.id,
        PaymentTransaction.status.in_(["succeeded", "refund_pending"]),
    ).limit(1))
    if payload.action == "approve" and booking.amount_vnd > 0 and successful_payment is None:
        raise HTTPException(status_code=409, detail={"code": "PAYMENT_RECORD_REQUIRED", "message": "Không thể xử lý hủy/hoàn khi thiếu giao dịch thanh toán đã xác minh."})
    if payload.action == "approve" and successful_payment is not None:
        raise HTTPException(status_code=503, detail={
            "code": "REFUND_GATEWAY_NOT_CONFIGURED",
            "message": "Yêu cầu hủy được ghi nhận nhưng chưa thể hoàn tiền vì cổng thanh toán chưa được cấu hình. Booking chưa bị đánh dấu đã hoàn.",
        })
    old = booking.status
    if payload.action == "approve":
        booking.status = "cancelled"
        booking.cancelled_at = _now()
        booking.hold_expires_at = None
        event_type = "provider_approved_unpaid_cancellation"
    else:
        booking.status = "confirmed"
        event_type = "provider_rejected_cancellation"
    booking.updated_at = _now()
    _event(db, booking, user, event_type, old, {"note": payload.note.strip()})
    db.commit()
    db.refresh(booking)
    return _payload(db, booking)


@router.get("/api/bookings/{booking_id}/history")
def booking_history(booking_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Không tìm thấy yêu cầu đặt chỗ."})
    provider = db.get(Provider, user.provider_id) if user.provider_id else None
    if user.id != booking.user_id and (provider is None or provider.id != booking.provider_id) and user.role != "admin":
        raise HTTPException(status_code=403, detail={"code": "BOOKING_FORBIDDEN", "message": "Bạn không có quyền xem lịch sử yêu cầu này."})
    rows = db.scalars(select(BookingEvent).where(BookingEvent.booking_id == booking.id).order_by(BookingEvent.created_at)).all()
    return [{"id": row.id, "event_type": row.event_type, "from_status": row.from_status,
             "to_status": row.to_status, "details": row.details, "created_at": row.created_at} for row in rows]
