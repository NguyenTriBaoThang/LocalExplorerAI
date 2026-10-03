"""Durable notification outbox and SMTP delivery helpers."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import Booking, NotificationDelivery, User


def enqueue_email(
    db: Session,
    *,
    idempotency_key: str,
    recipient: User | None,
    recipient_email: str | None = None,
    subject: str,
    body: str,
    booking_id: str | None = None,
    event_id: str | None = None,
) -> bool:
    """Add to the same DB transaction as the business event; never sends inline."""
    email = (recipient.email if recipient else recipient_email or "").strip().lower()
    if not settings.email_is_configured or not email:
        return False
    db.add(NotificationDelivery(
        id=str(uuid4()), idempotency_key=idempotency_key[:128],
        recipient_user_id=recipient.id if recipient else None, recipient_email=email,
        event_id=event_id, booking_id=booking_id, subject=subject[:255], body_text=body,
        status="queued",
    ))
    return True


def queue_booking_status(db: Session, booking: Booking, event_type: str) -> bool:
    """Notify the opposite party about an important booking state transition."""
    from app.models.entities import Provider

    if event_type == "hold_requested":
        provider = db.get(Provider, booking.provider_id)
        recipient = db.query(User).filter(User.provider_id == booking.provider_id, User.role == "provider", User.is_active.is_(True)).first()
        email = recipient.email if recipient else (provider.contact_email if provider else None)
        destination = recipient
        verb = "có yêu cầu giữ chỗ mới"
    else:
        destination = db.get(User, booking.user_id)
        email = destination.email if destination else None
        verb = {
            "provider_rejected": "cơ sở đã từ chối yêu cầu giữ chỗ",
            "provider_confirmed_free_booking": "cơ sở đã xác nhận lịch miễn phí",
            "provider_capacity_confirmed": "cơ sở đã xác nhận sức chứa; booking đang chờ thanh toán",
            "cancelled_before_payment": "yêu cầu giữ chỗ đã được hủy",
            "slot_cancelled_before_payment": "ca hoạt động đã bị hủy; yêu cầu giữ chỗ đã kết thúc",
            "provider_cancelled_paid_booking_refund_review_required": "ca hoạt động bị hủy; yêu cầu cần được hỗ trợ hoàn tiền",
        }.get(event_type)
        if not verb:
            return False
    return enqueue_email(
        db, idempotency_key=f"booking:{booking.id}:{event_type}", recipient=destination,
        recipient_email=email, subject=f"Local Explorer AI: {verb}",
        body=f"Xin chào,\n\nThông báo: {verb}.\nMã yêu cầu: {booking.id}\nTrạng thái hiện tại: {booking.status}.\n\nVui lòng đăng nhập Local Explorer AI để xem chi tiết.",
        booking_id=booking.id,
    )


def deliver_email(recipient: str, subject: str, body: str) -> None:
    """Synchronous worker-only SMTP call; raises for retry handling by the worker."""
    if not settings.email_is_configured:
        raise RuntimeError("SMTP is not configured")
    message = EmailMessage()
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    context = ssl.create_default_context()
    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context) as smtp:
            _smtp_login_and_send(smtp, message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.ehlo()
            if settings.smtp_starttls:
                smtp.starttls(context=context)
                smtp.ehlo()
            _smtp_login_and_send(smtp, message)


def _smtp_login_and_send(smtp, message: EmailMessage) -> None:
    if settings.smtp_username:
        smtp.login(settings.smtp_username, settings.smtp_password or "")
    smtp.send_message(message)
