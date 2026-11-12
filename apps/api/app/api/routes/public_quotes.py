"""Customer-facing quote link (M10): view, accept and pay the deposit. The unguessable token is the credential."""
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.guards import public
from app.core.client_ip import client_ip as request_client_ip
from app.core.config import settings
from app.models.entities import OperatorOrg, PaymentTransaction, Quote
from app.services.integration_config import IntegrationSecretConfigurationError, resolve_integration_value
from app.services.momo import MomoProviderError, MomoRejectedError, build_create_payload, create_payment_url, get_momo_config
from app.services.quote import quote_service as qs
from app.services.vnpay import build_payment_url, get_vnpay_config

router = APIRouter(prefix="/api/public/quotes", tags=["public quotes"])
MOMO_MAX_VND = 50_000_000
VNPAY_MIN_VND = 5_000


def _credential():
    return public("the unguessable quote token is the credential")


def _fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


class AcceptBody(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    phone: str = Field(min_length=6, max_length=30, pattern=r"^[0-9+\-. ()]+$")


class CheckoutBody(BaseModel):
    provider: str | None = Field(default=None, pattern="^(vnpay|momo)$")


def _load(db: Session, token: str, *, lock: bool = False) -> tuple[Quote, OperatorOrg]:
    stmt = select(Quote).where(Quote.public_token_hash == qs.token_hash(token))
    q = db.scalar(stmt.with_for_update() if lock else stmt)
    if q is None:
        raise _fail(404, "QUOTE_LINK_INVALID", "Liên kết báo giá không hợp lệ hoặc đã được thay bằng liên kết mới.")
    if qs.expire_due(q, datetime.now(timezone.utc)):
        db.commit()
    return q, db.get(OperatorOrg, q.org_id)


@router.get("/{token}", dependencies=[Depends(_credential())])
def view_quote(token: str, db: Session = Depends(get_db)):
    q, org = _load(db, token)
    now = datetime.now(timezone.utc)
    q.view_count += 1
    if q.first_viewed_at is None:
        q.first_viewed_at = now
    if q.status == "sent":
        q.status = "viewed"
    db.commit()
    return qs.public_view(org, q, now)


@router.post("/{token}/accept", dependencies=[Depends(_credential())])
def accept_quote(token: str, body: AcceptBody, db: Session = Depends(get_db)):
    q, org = _load(db, token, lock=True)
    if q.status == "expired":
        raise _fail(410, "QUOTE_EXPIRED", "Báo giá đã hết hiệu lực. Vui lòng liên hệ nhà điều hành để được gia hạn.")
    if q.status in ("sent", "viewed"):
        q.status, q.accepted_at = "accepted", datetime.now(timezone.utc)
        q.customer_name = body.name.strip()
        q.customer_contact = q.customer_contact or body.phone.strip()
        qs._audit(db, None, "quote.accepted", q, {"name": q.customer_name, "phone": body.phone.strip()})
        db.commit()
    elif q.status not in ("accepted", "deposit_paid"):
        raise _fail(409, "QUOTE_NOT_ACCEPTABLE", "Báo giá này không còn ở trạng thái chờ xác nhận.")
    return qs.public_view(org, q, datetime.now(timezone.utc))


def _unavailable() -> HTTPException:
    return _fail(503, "PAYMENT_CONFIGURATION_UNAVAILABLE", "Cấu hình thanh toán chưa sẵn sàng.")


@router.post("/{token}/checkout", dependencies=[Depends(_credential())])
def checkout_quote(token: str, body: CheckoutBody, request: Request, db: Session = Depends(get_db)):
    q, org = _load(db, token, lock=True)
    if q.status == "expired":
        raise _fail(410, "QUOTE_EXPIRED", "Báo giá đã hết hiệu lực. Vui lòng liên hệ nhà điều hành để được gia hạn.")
    if q.status == "deposit_paid":
        raise _fail(409, "DEPOSIT_ALREADY_PAID", "Khoản đặt cọc của báo giá này đã được thanh toán.")
    if q.status != "accepted":
        raise _fail(409, "QUOTE_NOT_ACCEPTED", "Vui lòng chấp nhận báo giá trước khi đặt cọc.")
    amount = qs.deposit_vnd(q.price_vnd, org.deposit_pct)
    try:
        provider = body.provider or (resolve_integration_value(db, "payments", "provider") or "vnpay").strip().lower()
    except IntegrationSecretConfigurationError as error:
        raise _unavailable() from error
    if provider not in ("vnpay", "momo"):
        raise _fail(503, "PAYMENT_PROVIDER_UNSUPPORTED", "Cổng thanh toán được cấu hình chưa được hỗ trợ.")
    now = datetime.now(timezone.utc)
    ref = uuid4().hex
    info = f"Coc bao gia {q.code}"
    if provider == "momo":
        if amount > MOMO_MAX_VND:
            raise _fail(422, "PAYMENT_AMOUNT_UNSUPPORTED", f"Tiền cọc {amount:,} VND vượt hạn mức 50.000.000 VND của ví MoMo. Vui lòng chọn VNPay hoặc liên hệ nhà điều hành.")
        try:
            momo = get_momo_config(db)
        except IntegrationSecretConfigurationError as error:
            raise _unavailable() from error
        if not momo.checkout_enabled:
            raise _fail(503, "PAYMENT_GATEWAY_NOT_CONFIGURED", "MoMo chưa sẵn sàng; chưa có khoản tiền nào bị thu.")
        payment = PaymentTransaction(id=str(uuid4()), quote_id=q.id, provider="momo", provider_reference=ref, idempotency_key=uuid4().hex,
                                     amount_vnd=amount, currency="VND", status="created", created_at=now, updated_at=now)
        db.add(payment)
        db.commit()
        try:
            checkout_url = create_payment_url(momo, build_create_payload(momo, amount_vnd=amount, order_id=ref, request_id=payment.idempotency_key, order_info=info))
        except MomoRejectedError as error:
            payment.status = "failed"
            db.commit()
            raise _fail(502, "PAYMENT_PROVIDER_REJECTED", "MoMo từ chối giao dịch này.") from error
        except MomoProviderError as error:
            raise _fail(502, "PAYMENT_PROVIDER_ERROR", "MoMo chưa tạo được phiên thanh toán, vui lòng thử lại.") from error
        payment.checkout_url, payment.status, payment.updated_at = checkout_url, "pending", datetime.now(timezone.utc)
    else:
        try:
            vnpay = get_vnpay_config(db)
        except IntegrationSecretConfigurationError as error:
            raise _unavailable() from error
        if not vnpay.vnpay_checkout_enabled:
            raise _fail(503, "PAYMENT_GATEWAY_NOT_CONFIGURED", "VNPay chưa sẵn sàng; chưa có khoản tiền nào bị thu.")
        if amount < VNPAY_MIN_VND or amount * 100 > 999_999_999_999:
            raise _fail(422, "PAYMENT_AMOUNT_UNSUPPORTED", "Số tiền cọc nằm ngoài hạn mức VNPay.")
        try:
            remote_ip = str(ip_address(request_client_ip(request, settings.trusted_proxy_ips)))
        except ValueError:
            if settings.app_env.lower() in {"prod", "production"}:
                raise _fail(503, "PAYMENT_CLIENT_IP_UNAVAILABLE", "Không xác định được địa chỉ IP yêu cầu thanh toán.")
            remote_ip = "127.0.0.1"
        vn = ZoneInfo("Asia/Ho_Chi_Minh")
        checkout_url = build_payment_url(
            payment_url=vnpay.vnpay_payment_url.strip(), tmn_code=(vnpay.vnpay_tmn_code or "").strip(),
            hash_secret=(vnpay.vnpay_hash_secret or "").strip(), return_url=(vnpay.vnpay_return_url or "").strip(),
            amount_vnd=amount, transaction_ref=ref, order_info=info, client_ip=remote_ip,
            created_at=now.astimezone(vn), expires_at=(now + timedelta(minutes=15)).astimezone(vn))
        db.add(PaymentTransaction(id=str(uuid4()), quote_id=q.id, provider="vnpay", provider_reference=ref, idempotency_key=str(uuid4()),
                                  amount_vnd=amount, currency="VND", status="pending", checkout_url=checkout_url, created_at=now, updated_at=now))
    qs._audit(db, None, "quote.deposit_checkout_created", q, {"provider": provider, "amount_vnd": amount})
    db.commit()
    return {"checkout_url": checkout_url, "provider": provider, "amount_vnd": amount}
