from datetime import datetime, timedelta, timezone
import hmac
import json
from ipaddress import ip_address
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.client_ip import client_ip as request_client_ip
from app.core.config import settings
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
from app.services.integration_config import IntegrationSecretConfigurationError, resolve_integration_value
from app.services.momo import MomoProviderError, MomoRejectedError, build_create_payload, create_payment_url, get_momo_config, verify_ipn_signature
from app.services.vnpay import build_payment_url, get_vnpay_config, verify_params
from app.api.guards import public, require_user
from app.api.permissions import P

router = APIRouter(tags=["bookings and payments"])
_LIVE_STATUSES = ("pending_provider", "awaiting_payment", "confirmed", "cancellation_requested")
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
    payment_status = db.scalar(select(PaymentTransaction.status).where(
        PaymentTransaction.booking_id == booking.id,
    ).order_by(PaymentTransaction.created_at.desc()).limit(1))
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
        "payment_status": payment_status,
        "hold_expires_at": booking.hold_expires_at,
        "provider_confirmed_at": booking.provider_confirmed_at,
        "confirmed_at": booking.confirmed_at,
        "cancellation_reason": booking.cancellation_reason,
        "created_at": booking.created_at,
        "updated_at": booking.updated_at,
    }


@router.get("/api/payments/status", dependencies=[Depends(public('gateway readiness; no sensitive data'))])
def payment_status(db: Session = Depends(get_db)):
    try:
        selected = (resolve_integration_value(db, "payments", "provider") or "vnpay").strip().lower()
        vnpay = get_vnpay_config(db)
        momo = get_momo_config(db)
    except IntegrationSecretConfigurationError:
        return {"provider": "unavailable", "checkout_enabled": False, "refunds_enabled": False,
                "message": "Integration configuration could not be decrypted. Check INTEGRATION_SECRETS_KEY."}
    configured = vnpay.vnpay_checkout_enabled if selected == "vnpay" else momo.checkout_enabled if selected == "momo" else False
    return {
        "provider": selected,
        "environment": momo.environment if selected == "momo" else vnpay.vnpay_environment,
        "checkout_enabled": configured,
        "available_providers": {"vnpay": vnpay.vnpay_checkout_enabled, "momo": momo.checkout_enabled},
        "refunds_enabled": False,
        "message": (
            f"Thanh toán {selected} đã được cấu hình; xác nhận booking chỉ dựa trên IPN đã xác minh."
            if configured else
            f"{selected} chưa sẵn sàng: kiểm tra merchant credentials, endpoint môi trường và Return/IPN URL HTTPS công khai."
        ),
    }


def _vnpay_callback_params(request: Request) -> dict[str, str] | None:
    pairs = [(key, value) for key, value in request.query_params.multi_items() if key.startswith("vnp_")]
    params: dict[str, str] = {}
    for key, value in pairs:
        if key in params:
            return None
        params[key] = value
    return params


def _vnpay_reply(code: str, message: str) -> dict[str, str]:
    return {"RspCode": code, "Message": message}


def _payment_return_redirect(*, payment: str, booking: Booking | None = None) -> RedirectResponse:
    target = f"{settings.web_app_url.rstrip('/')}/itinerary/{booking.itinerary_id}" if booking and booking.itinerary_id else settings.web_app_url.rstrip("/")
    query = {"payment": payment}
    if booking:
        query["booking"] = booking.id
    return RedirectResponse(f"{target}?{urlencode(query)}", status_code=303)


@router.get("/api/payments/vnpay/return", include_in_schema=False, dependencies=[Depends(public('browser redirect from the gateway; result verified by signature'))])
def vnpay_return(request: Request, db: Session = Depends(get_db)):
    """Display-only return; settlement is exclusively performed by the signed IPN."""
    try:
        config = get_vnpay_config(db)
    except IntegrationSecretConfigurationError:
        return _payment_return_redirect(payment="invalid")
    params = _vnpay_callback_params(request)
    if not params or not config.vnpay_credentials_configured or not verify_params(params, (config.vnpay_hash_secret or "").strip()):
        return _payment_return_redirect(payment="invalid")
    if not hmac.compare_digest(params.get("vnp_TmnCode", ""), (config.vnpay_tmn_code or "").strip()):
        return _payment_return_redirect(payment="invalid")
    reference = params.get("vnp_TxnRef", "")
    payment = db.scalar(select(PaymentTransaction).where(
        PaymentTransaction.provider == "vnpay",
        PaymentTransaction.provider_reference == reference,
    )) if reference else None
    booking = db.get(Booking, payment.booking_id) if payment else None
    if booking is None:
        return _payment_return_redirect(payment="invalid")
    return _payment_return_redirect(payment="returned", booking=booking)


@router.get("/api/payments/vnpay/ipn", include_in_schema=False, dependencies=[Depends(public('server-to-server webhook verified by HMAC signature'))])
def vnpay_ipn(request: Request, db: Session = Depends(get_db)):
    """Idempotent VNPay server callback. Never trust browser return parameters for settlement."""
    try:
        config = get_vnpay_config(db)
    except IntegrationSecretConfigurationError:
        return _vnpay_reply("99", "Invalid configuration or parameters")
    params = _vnpay_callback_params(request)
    if not params or not config.vnpay_credentials_configured:
        return _vnpay_reply("99", "Invalid configuration or parameters")
    if not verify_params(params, (config.vnpay_hash_secret or "").strip()):
        return _vnpay_reply("97", "Invalid signature")
    if not hmac.compare_digest(params.get("vnp_TmnCode", ""), (config.vnpay_tmn_code or "").strip()):
        return _vnpay_reply("97", "Invalid merchant")

    reference = params.get("vnp_TxnRef", "")
    payment = db.scalar(select(PaymentTransaction).where(
        PaymentTransaction.provider == "vnpay",
        PaymentTransaction.provider_reference == reference,
    )) if reference else None
    if payment is None:
        return _vnpay_reply("01", "Order not found")
    amount_text = params.get("vnp_Amount", "")
    if not amount_text.isascii() or not amount_text.isdigit():
        return _vnpay_reply("04", "Invalid amount")
    received_amount = int(amount_text)
    if received_amount != payment.amount_vnd * 100 or payment.currency != "VND":
        return _vnpay_reply("04", "Invalid amount")
    if params.get("vnp_CurrCode") != "VND":
        return _vnpay_reply("04", "Invalid currency")
    response_code = params.get("vnp_ResponseCode")
    transaction_status = params.get("vnp_TransactionStatus")
    if response_code is None or transaction_status is None:
        return _vnpay_reply("99", "Missing transaction status")
    if response_code in {"00", "07"} and transaction_status != "00":
        return _vnpay_reply("99", "Transaction result is not final")
    gateway_transaction_no = params.get("vnp_TransactionNo", "")
    if response_code in {"00", "07"} and (not gateway_transaction_no or not gateway_transaction_no.isascii()):
        return _vnpay_reply("99", "Missing gateway transaction reference")

    booking_preview = db.get(Booking, payment.booking_id)
    if booking_preview is None:
        return _vnpay_reply("01", "Order not found")
    # Follow slot -> booking -> payment lock order, shared with provider slot edits,
    # so a callback cannot deadlock while reconciling a slot cancellation.
    slot = db.scalar(select(ExperienceSlot).where(ExperienceSlot.id == booking_preview.slot_id).with_for_update())
    booking = db.scalar(select(Booking).where(Booking.id == payment.booking_id).with_for_update())
    payment = db.scalar(select(PaymentTransaction).where(PaymentTransaction.id == payment.id)
                        .with_for_update().execution_options(populate_existing=True))
    if booking is None or payment is None:
        return _vnpay_reply("01", "Order not found")
    if payment.status == "succeeded":
        return _vnpay_reply("02", "Order already confirmed")
    if payment.status not in {"created", "pending", "failed"}:
        return _vnpay_reply("02", "Order already processed")
    if payment.status == "failed" and (response_code != "00" or transaction_status != "00"):
        return _vnpay_reply("02", "Order already processed")

    now = _now()
    if response_code not in {"00", "07"} or transaction_status != "00":
        payment.status = "failed"
        payment.updated_at = now
        _event(db, booking, None, "payment_failed", booking.status, {
            "payment_transaction_id": payment.id,
            "gateway_response_code": response_code,
            "gateway_transaction_status": transaction_status,
        })
        db.commit()
        return _vnpay_reply("00", "Confirm Success")

    payment.status = "succeeded"
    payment.updated_at = now
    old_status = booking.status
    expiry = _aware(booking.hold_expires_at)
    can_settle_booking = booking.status == "awaiting_payment" and expiry is not None and expiry > now
    if can_settle_booking:
        can_settle_booking = bool(
            slot and slot.status == "open" and slot.available_reported is not None
            and slot_is_operationally_verified(db, slot)
            and _held_seats(db, booking.slot_id, now) <= slot.available_reported
        )
    if can_settle_booking and response_code == "00":
        booking.status = "confirmed"
        booking.confirmed_at = now
        booking.hold_expires_at = None
        event_type = "payment_confirmed"
    elif booking.status == "confirmed":
        # This can occur only after a separate payment attempt captured late; keep the
        # existing confirmed reservation and flag the extra capture for manual review.
        event_type = "extra_payment_captured_reconciliation_required"
    else:
        booking.status = "refund_pending"
        booking.hold_expires_at = None
        event_type = (
            "payment_suspicious_reconciliation_required"
            if response_code == "07" else "payment_captured_reconciliation_required"
        )
    booking.updated_at = now
    _event(db, booking, None, event_type, old_status, {
        "payment_transaction_id": payment.id,
        "gateway_transaction_no": params.get("vnp_TransactionNo"),
        "gateway_pay_date": params.get("vnp_PayDate"),
        "gateway_response_code": response_code,
        "gateway_transaction_status": transaction_status,
        "amount_vnd": payment.amount_vnd,
        "manual_refund_reconciliation_required": event_type != "payment_confirmed",
    })
    db.commit()
    return _vnpay_reply("00", "Confirm Success")


@router.get("/api/payments/momo/return", include_in_schema=False, dependencies=[Depends(public('browser redirect from the gateway; result verified by signature'))])
def momo_return(request: Request, db: Session = Depends(get_db)):
    """MoMo browser redirect is display-only; signed IPN alone settles the ledger."""
    order_id = request.query_params.get("orderId", "")
    payment = db.scalar(select(PaymentTransaction).where(
        PaymentTransaction.provider == "momo",
        PaymentTransaction.provider_reference == order_id,
    )) if order_id else None
    booking = db.get(Booking, payment.booking_id) if payment else None
    if booking is None:
        return _payment_return_redirect(payment="invalid")
    return _payment_return_redirect(payment="returned", booking=booking)


@router.post("/api/payments/momo/ipn", include_in_schema=False, dependencies=[Depends(public('server-to-server webhook verified by HMAC signature'))])
async def momo_ipn(request: Request, db: Session = Depends(get_db)):
    """Validate MoMo's HMAC notification and acknowledge it with the documented 204."""
    try:
        config = get_momo_config(db)
    except IntegrationSecretConfigurationError:
        return Response(status_code=503)
    if not config.checkout_enabled:
        return Response(status_code=503)
    content_length = request.headers.get("content-length", "")
    if content_length.isdigit() and int(content_length) > 16_384:
        return Response(status_code=413)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 16_384:
            return Response(status_code=413)
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return Response(status_code=400)
    if not isinstance(payload, dict) or not verify_ipn_signature(payload, config.access_key, config.secret_key):
        return Response(status_code=401)
    if not hmac.compare_digest(str(payload.get("partnerCode", "")), config.partner_code):
        return Response(status_code=401)

    order_id = str(payload.get("orderId", ""))
    request_id = str(payload.get("requestId", ""))
    payment = db.scalar(select(PaymentTransaction).where(
        PaymentTransaction.provider == "momo",
        PaymentTransaction.provider_reference == order_id,
    )) if order_id else None
    if payment is None:
        return Response(status_code=204)
    amount = payload.get("amount")
    if isinstance(amount, bool) or not (isinstance(amount, int) or isinstance(amount, str) and amount.isascii() and amount.isdigit()):
        return Response(status_code=400)
    if int(amount) != payment.amount_vnd or payment.currency != "VND":
        return Response(status_code=400)
    if not hmac.compare_digest(request_id, payment.idempotency_key):
        return Response(status_code=400)
    result_code = payload.get("resultCode")
    if isinstance(result_code, bool) or not isinstance(result_code, int):
        return Response(status_code=400)
    trans_id = payload.get("transId")
    if result_code in {0, 9000} and (isinstance(trans_id, bool) or not str(trans_id).isascii() or not str(trans_id).isdigit()):
        return Response(status_code=400)

    booking_preview = db.get(Booking, payment.booking_id)
    if booking_preview is None:
        return Response(status_code=204)
    # Keep lock acquisition consistent with VNPay and slot-capacity changes.
    slot = db.scalar(select(ExperienceSlot).where(ExperienceSlot.id == booking_preview.slot_id).with_for_update())
    booking = db.scalar(select(Booking).where(Booking.id == payment.booking_id).with_for_update())
    payment = db.scalar(select(PaymentTransaction).where(PaymentTransaction.id == payment.id)
                        .with_for_update().execution_options(populate_existing=True))
    if booking is None or payment is None or payment.status == "succeeded":
        return Response(status_code=204)
    if payment.status not in {"created", "pending", "failed"}:
        return Response(status_code=204)
    if payment.status == "failed" and result_code not in {0, 9000}:
        return Response(status_code=204)
    # 9000 is an authorization, not a captured payment. This integration does not
    # implement a separate capture call, so never confirm a reservation for it.
    if result_code == 9000:
        return Response(status_code=204)

    now = _now()
    if result_code != 0:
        payment.status = "failed"
        payment.updated_at = now
        _event(db, booking, None, "payment_failed", booking.status, {
            "payment_transaction_id": payment.id,
            "gateway": "momo",
            "gateway_result_code": result_code,
        })
        db.commit()
        return Response(status_code=204)

    payment.status = "succeeded"
    payment.updated_at = now
    old_status = booking.status
    expiry = _aware(booking.hold_expires_at)
    can_settle_booking = booking.status == "awaiting_payment" and expiry is not None and expiry > now
    if can_settle_booking:
        can_settle_booking = bool(
            slot and slot.status == "open" and slot.available_reported is not None
            and slot_is_operationally_verified(db, slot)
            and _held_seats(db, booking.slot_id, now) <= slot.available_reported
        )
    if can_settle_booking:
        booking.status = "confirmed"
        booking.confirmed_at = now
        booking.hold_expires_at = None
        event_type = "payment_confirmed"
    elif booking.status == "confirmed":
        event_type = "extra_payment_captured_reconciliation_required"
    else:
        booking.status = "refund_pending"
        booking.hold_expires_at = None
        event_type = "payment_captured_reconciliation_required"
    booking.updated_at = now
    _event(db, booking, None, event_type, old_status, {
        "payment_transaction_id": payment.id,
        "gateway": "momo",
        "gateway_transaction_id": str(trans_id),
        "gateway_response_time": str(payload.get("responseTime", "")),
        "amount_vnd": payment.amount_vnd,
        "manual_refund_reconciliation_required": event_type != "payment_confirmed",
    })
    db.commit()
    return Response(status_code=204)


def _require_verified_email(user: User) -> None:
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail={"code": "EMAIL_NOT_VERIFIED", "message": "Vui lòng xác minh email trước khi giữ chỗ hoặc thanh toán."})


@router.post("/api/bookings", status_code=201)
def request_booking(payload: BookingHoldRequest, user: User = Depends(require_user(P.BOOKING_CREATE)), db: Session = Depends(get_db)):
    _require_verified_email(user)
    now = _now()
    # Serialize booking creation with collaboration edits so an active booking
    # cannot be attached to a stop while an owner-approved proposal removes it.
    itinerary = db.scalar(
        select(Itinerary).where(Itinerary.id == payload.itinerary_id).with_for_update()
    )
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
def my_bookings(itinerary_id: str | None = Query(default=None, max_length=36), user: User = Depends(require_user(P.BOOKING_READ)), db: Session = Depends(get_db)):
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
def cancel_booking(booking_id: str, payload: BookingCancelRequest, user: User = Depends(require_user(P.BOOKING_CANCEL)), db: Session = Depends(get_db)):
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
def begin_checkout(booking_id: str, request: Request, user: User = Depends(require_user(P.BOOKING_CHECKOUT)), db: Session = Depends(get_db)):
    _require_verified_email(user)
    booking = db.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
    if booking is None or booking.user_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Không tìm thấy yêu cầu đặt chỗ."})
    now = _now()
    hold_expires_at = _aware(booking.hold_expires_at)
    if booking.status != "awaiting_payment" or hold_expires_at is None or hold_expires_at <= now + timedelta(seconds=30):
        raise HTTPException(status_code=409, detail={"code": "BOOKING_NOT_READY_FOR_PAYMENT", "message": "Cơ sở chưa xác nhận yêu cầu hoặc thời hạn giữ chỗ đã hết."})
    try:
        selected_provider = (resolve_integration_value(db, "payments", "provider") or "vnpay").strip().lower()
    except IntegrationSecretConfigurationError as error:
        raise HTTPException(status_code=503, detail={"code": "PAYMENT_CONFIGURATION_UNAVAILABLE", "message": "Payment integration settings could not be decrypted."}) from error

    if selected_provider == "momo":
        try:
            momo = get_momo_config(db)
        except IntegrationSecretConfigurationError as error:
            raise HTTPException(status_code=503, detail={"code": "PAYMENT_CONFIGURATION_UNAVAILABLE", "message": "Payment integration settings could not be decrypted."}) from error
        if not momo.checkout_enabled:
            raise HTTPException(status_code=503, detail={"code": "PAYMENT_GATEWAY_NOT_CONFIGURED", "message": "MoMo is not ready. Configure merchant credentials and public HTTPS return/IPN URLs."})
        if booking.amount_vnd < 1_000 or booking.amount_vnd > 50_000_000:
            raise HTTPException(status_code=422, detail={"code": "PAYMENT_AMOUNT_UNSUPPORTED", "message": "MoMo wallet checkout supports amounts from 1,000 to 50,000,000 VND."})
        pending = db.scalar(select(PaymentTransaction).where(
            PaymentTransaction.booking_id == booking.id,
            PaymentTransaction.status.in_(["created", "pending"]),
        ).order_by(PaymentTransaction.created_at.desc()).with_for_update())
        if pending and pending.provider != "momo":
            raise HTTPException(status_code=409, detail={"code": "PAYMENT_ATTEMPT_IN_PROGRESS", "message": "A payment attempt with another provider is still pending."})
        if pending and pending.checkout_url:
            return {"checkout_url": pending.checkout_url}
        if pending is None:
            pending = PaymentTransaction(
                id=str(uuid4()), booking_id=booking.id, provider="momo", provider_reference=uuid4().hex,
                idempotency_key=uuid4().hex, amount_vnd=booking.amount_vnd, currency="VND",
                status="created", created_at=now, updated_at=now,
            )
            db.add(pending)
            db.add(AuditLog(
                id=str(uuid4()), actor_id=user.id, action="booking.payment_checkout_created",
                target_type="booking", target_id=booking.id,
                details={"provider": "momo", "payment_transaction_id": pending.id}, created_at=now,
            ))
            db.commit()
        try:
            create_payload = build_create_payload(
                momo, amount_vnd=booking.amount_vnd, order_id=pending.provider_reference,
                request_id=pending.idempotency_key, order_info=f"LocalExplorer booking {booking.id}",
            )
            checkout_url = create_payment_url(momo, create_payload)
        except MomoRejectedError as error:
            pending.status = "failed"
            pending.updated_at = _now()
            db.commit()
            raise HTTPException(status_code=502, detail={"code": "PAYMENT_PROVIDER_REJECTED", "message": "MoMo rejected this payment attempt. Review merchant setup before retrying."}) from error
        except MomoProviderError as error:
            raise HTTPException(status_code=502, detail={"code": "PAYMENT_PROVIDER_ERROR", "message": "MoMo could not create a checkout session. The request can be safely retried."}) from error
        pending.checkout_url = checkout_url
        pending.status = "pending"
        pending.updated_at = _now()
        db.commit()
        return {"checkout_url": checkout_url}

    if selected_provider != "vnpay":
        raise HTTPException(status_code=503, detail={"code": "PAYMENT_PROVIDER_UNSUPPORTED", "message": "The configured payment provider is not supported."})
    try:
        vnpay = get_vnpay_config(db)
    except IntegrationSecretConfigurationError as error:
        raise HTTPException(status_code=503, detail={"code": "PAYMENT_CONFIGURATION_UNAVAILABLE", "message": "Payment integration settings could not be decrypted."}) from error
    if not vnpay.vnpay_checkout_enabled:
        raise HTTPException(status_code=503, detail={
            "code": "PAYMENT_GATEWAY_NOT_CONFIGURED",
            "message": "VNPay chưa sẵn sàng; chưa có khoản tiền nào bị thu. Cần cấu hình merchant và callback công khai.",
        })
    if booking.amount_vnd < 5_000 or booking.amount_vnd * 100 > 999_999_999_999:
        raise HTTPException(status_code=422, detail={
            "code": "PAYMENT_AMOUNT_UNSUPPORTED",
            "message": "VNPay yêu cầu tối thiểu 5.000 VND và giới hạn số tiền gửi theo trường 12 chữ số; hạn mức thực tế còn phụ thuộc tài khoản/ngân hàng.",
        })

    other_provider_pending = db.scalar(select(PaymentTransaction).where(
        PaymentTransaction.booking_id == booking.id,
        PaymentTransaction.status.in_(["created", "pending"]),
        PaymentTransaction.provider != "vnpay",
    ).order_by(PaymentTransaction.created_at.desc()).with_for_update())
    if other_provider_pending:
        raise HTTPException(status_code=409, detail={"code": "PAYMENT_ATTEMPT_IN_PROGRESS", "message": "A payment attempt with another provider is still pending."})

    pending = db.scalar(select(PaymentTransaction).where(
        PaymentTransaction.booking_id == booking.id,
        PaymentTransaction.provider == "vnpay",
        PaymentTransaction.status.in_(["created", "pending"]),
    ).order_by(PaymentTransaction.created_at.desc()).with_for_update())
    if pending and pending.checkout_url:
        return {"checkout_url": pending.checkout_url}

    try:
        remote_ip = str(ip_address(request_client_ip(request, settings.trusted_proxy_ips)))
    except ValueError:
        if settings.app_env.lower() in {"prod", "production"}:
            raise HTTPException(status_code=503, detail={"code": "PAYMENT_CLIENT_IP_UNAVAILABLE", "message": "Không xác định được địa chỉ IP yêu cầu thanh toán."})
        remote_ip = "127.0.0.1"
    transaction_ref = uuid4().hex
    timezone_vn = ZoneInfo("Asia/Ho_Chi_Minh")
    checkout_url = build_payment_url(
        payment_url=vnpay.vnpay_payment_url.strip(),
        tmn_code=(vnpay.vnpay_tmn_code or "").strip(),
        hash_secret=(vnpay.vnpay_hash_secret or "").strip(),
        return_url=(vnpay.vnpay_return_url or "").strip(),
        amount_vnd=booking.amount_vnd,
        transaction_ref=transaction_ref,
        order_info=f"LocalExplorer booking {booking.id}",
        client_ip=remote_ip,
        created_at=now.astimezone(timezone_vn),
        expires_at=hold_expires_at.astimezone(timezone_vn),
    )
    payment = PaymentTransaction(
        id=str(uuid4()), booking_id=booking.id, provider="vnpay", provider_reference=transaction_ref,
        idempotency_key=str(uuid4()), amount_vnd=booking.amount_vnd, currency="VND",
        status="pending", checkout_url=checkout_url, created_at=now, updated_at=now,
    )
    db.add(payment)
    db.add(AuditLog(
        id=str(uuid4()), actor_id=user.id, action="booking.payment_checkout_created",
        target_type="booking", target_id=booking.id,
        details={"provider": "vnpay", "payment_transaction_id": payment.id}, created_at=now,
    ))
    db.commit()
    return {"checkout_url": checkout_url}


@router.get("/api/provider/me/bookings")
def provider_bookings(user: User = Depends(require_user(P.PROVIDER_BOOKING_READ)), db: Session = Depends(get_db)):
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
def decide_booking(booking_id: str, payload: BookingDecisionRequest, user: User = Depends(require_user(P.PROVIDER_BOOKING_DECIDE)), db: Session = Depends(get_db)):
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
def decide_cancellation(booking_id: str, payload: BookingCancellationDecisionRequest, user: User = Depends(require_user(P.PROVIDER_BOOKING_DECIDE)), db: Session = Depends(get_db)):
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
def booking_history(booking_id: str, user: User = Depends(require_user(P.BOOKING_HISTORY)), db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail={"code": "BOOKING_NOT_FOUND", "message": "Không tìm thấy yêu cầu đặt chỗ."})
    provider = db.get(Provider, user.provider_id) if user.provider_id else None
    if user.id != booking.user_id and (provider is None or provider.id != booking.provider_id) and user.role != "admin":
        raise HTTPException(status_code=403, detail={"code": "BOOKING_FORBIDDEN", "message": "Bạn không có quyền xem lịch sử yêu cầu này."})
    rows = db.scalars(select(BookingEvent).where(BookingEvent.booking_id == booking.id).order_by(BookingEvent.created_at)).all()
    return [{"id": row.id, "event_type": row.event_type, "from_status": row.from_status,
             "to_status": row.to_status, "details": row.details, "created_at": row.created_at} for row in rows]
