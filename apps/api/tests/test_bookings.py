from datetime import datetime, timedelta, timezone
from uuid import uuid4
from urllib.parse import parse_qs, urlsplit

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select

from tests.helpers import sign_in
from app.api.routes import bookings as booking_routes
from app.core.config import settings
from app.models.entities import (
    Booking,
    Evidence,
    Experience,
    ExperienceSlot,
    Itinerary,
    ItineraryStop,
    PaymentTransaction,
    POI,
    Provider,
    User,
)
from app.services.vnpay import sign_params, verify_params
from app.services.momo import IPN_SIGNATURE_FIELDS
import hashlib
import hmac


def _verified_evidence(db_session, target_type, target_id, revision, fields, now, expires):
    db_session.add(Evidence(
        id=str(uuid4()), source_uri="https://example.org/verified-record", source_type="provider_confirmation",
        source_label="Verified source", submitted_by=None, target_type=target_type, target_id=target_id,
        target_revision=revision, fields_covered=fields, observed_at=now - timedelta(minutes=2),
        expires_at=expires, verification_status="verified", verified_at=now - timedelta(minutes=1),
    ))


def _booking_fixture(db_session, quantity_capacity=2, price=100_000):
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(days=2)
    provider = Provider(id=str(uuid4()), name="Verified provider", slug=f"verified-{uuid4().hex[:8]}", is_active=True, verification_status="verified")
    provider_user = User(id=str(uuid4()), email=f"provider-{uuid4().hex[:8]}@example.org", display_name="Provider", role="provider", provider_id=provider.id)
    traveler = User(id=str(uuid4()), email=f"traveler-{uuid4().hex[:8]}@example.org", display_name="Traveler", role="traveler",
                    email_verified_at=datetime.now(timezone.utc))
    poi = POI(name="Verified POI", description="Workshop", latitude=10.77, longitude=106.7,
              geom=WKTElement("POINT(106.7 10.77)", srid=4326), category="craft", address="Verified address",
              verification_status="verified", data_revision=1)
    experience = Experience(poi=poi, provider=provider, name="Verified workshop", title="Verified workshop",
                            description="Hands-on", intent_tags=["handicraft"], is_hands_on=True,
                            duration_min=60, price_basis="per_person", price_vnd=price,
                            verification_status="verified", data_revision=1)
    slot = ExperienceSlot(experience=experience, start_at=expiry, end_at=expiry + timedelta(hours=1),
                          capacity_total=quantity_capacity, available_reported=quantity_capacity,
                          confirmed_at=now, expires_at=expiry - timedelta(hours=1), status="open", version=1)
    itinerary = Itinerary(user_id=traveler.id, group_size=quantity_capacity, budget_vnd=1_000_000,
                          travel_mode="driving", start_at=expiry - timedelta(hours=1), end_at=expiry + timedelta(hours=2),
                          status="feasible", constraints={}, estimated_cost_vnd=price * quantity_capacity)
    stop = ItineraryStop(itinerary=itinerary, experience=experience, slot=slot, poi=poi, stop_order=1,
                         position=1, arrival_at=expiry, departure_at=expiry + timedelta(hours=1),
                         start_at=expiry, end_at=expiry + timedelta(hours=1), activity_duration_min=60,
                         cost_vnd=price * quantity_capacity)
    db_session.add_all([provider_user, traveler, poi, experience, slot, itinerary, stop])
    db_session.flush()
    _verified_evidence(db_session, "poi", poi.id, poi.data_revision,
                       ["name", "address", "latitude", "longitude", "category"], now, expiry + timedelta(days=20))
    _verified_evidence(db_session, "experience", experience.id, experience.data_revision,
                       ["title", "description", "primary_intent", "intent_tags", "is_hands_on", "duration_min", "price_vnd", "price_basis"], now, expiry + timedelta(days=20))
    _verified_evidence(db_session, "slot", slot.id, slot.version,
                       ["start_at", "end_at", "capacity_total", "available_reported", "status"], now, slot.expires_at)
    db_session.commit()
    return traveler, provider_user, itinerary, stop, slot


def test_booking_hold_capacity_provider_confirmation_and_payment_fail_closed(client, db_session):
    traveler, provider_user, itinerary, stop, slot = _booking_fixture(db_session, quantity_capacity=2, price=125_000)
    sign_in(client, traveler)

    response = client.post("/api/bookings", json={"itinerary_id": itinerary.id, "itinerary_stop_id": stop.id, "quantity": 2})
    assert response.status_code == 201, response.text
    booking_id = response.json()["id"]
    assert response.json()["status"] == "pending_provider"
    assert response.json()["amount_vnd"] == 250_000

    # The reservation is counted against available seats before another traveler can request them.
    second_traveler = User(id=str(uuid4()), email=f"second-{uuid4().hex[:8]}@example.org", display_name="Second", role="traveler",
                           email_verified_at=datetime.now(timezone.utc))
    second_itinerary = Itinerary(user_id=second_traveler.id, group_size=1, budget_vnd=200_000,
                                 start_at=itinerary.start_at, end_at=itinerary.end_at, status="feasible",
                                 constraints={}, estimated_cost_vnd=125_000)
    second_stop = ItineraryStop(itinerary=second_itinerary, experience=stop.experience, slot=slot, poi=stop.poi,
                                stop_order=1, position=1, arrival_at=stop.arrival_at, departure_at=stop.departure_at,
                                start_at=stop.start_at, end_at=stop.end_at, activity_duration_min=60, cost_vnd=125_000)
    db_session.add_all([second_traveler, second_itinerary, second_stop])
    db_session.commit()
    sign_in(client, second_traveler)
    rejected = client.post("/api/bookings", json={"itinerary_id": second_itinerary.id, "itinerary_stop_id": second_stop.id, "quantity": 1})
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "INSUFFICIENT_CAPACITY"

    sign_in(client, provider_user)
    accepted = client.post(f"/api/provider/me/bookings/{booking_id}/decision", json={"action": "accept", "note": "Seats checked"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "awaiting_payment"
    sign_in(client, traveler)
    checkout = client.post(f"/api/bookings/{booking_id}/checkout")
    assert checkout.status_code == 503
    assert checkout.json()["error"]["code"] == "PAYMENT_GATEWAY_NOT_CONFIGURED"
    assert db_session.scalar(select(func.count(PaymentTransaction.id))) == 0
    assert db_session.get(Booking, booking_id).status == "awaiting_payment"
    cancelled = client.post(f"/api/bookings/{booking_id}/cancel", json={"reason": "Plan changed"})
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    history = client.get(f"/api/bookings/{booking_id}/history")
    assert history.status_code == 200
    assert [row["to_status"] for row in history.json()] == ["pending_provider", "awaiting_payment", "cancelled"]


def test_free_reservation_becomes_confirmed_after_provider_capacity_acceptance(client, db_session):
    traveler, provider_user, itinerary, stop, _slot = _booking_fixture(db_session, quantity_capacity=1, price=0)
    sign_in(client, traveler)
    hold = client.post("/api/bookings", json={"itinerary_id": itinerary.id, "itinerary_stop_id": stop.id, "quantity": 1})
    assert hold.status_code == 201, hold.text
    sign_in(client, provider_user)
    confirmation = client.post(f"/api/provider/me/bookings/{hold.json()['id']}/decision", json={"action": "accept"})
    assert confirmation.status_code == 200, confirmation.text
    assert confirmation.json()["status"] == "confirmed"
    assert confirmation.json()["confirmed_at"] is not None


def _prepare_vnpay_booking(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "vnpay_environment", "sandbox")
    monkeypatch.setattr(settings, "vnpay_tmn_code", "TESTTMN1")
    monkeypatch.setattr(settings, "vnpay_hash_secret", "test-vnpay-secret")
    monkeypatch.setattr(settings, "vnpay_payment_url", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
    monkeypatch.setattr(settings, "vnpay_return_url", "https://payments.example.org/api/payments/vnpay/return")
    monkeypatch.setattr(settings, "vnpay_ipn_url", "https://payments.example.org/api/payments/vnpay/ipn")

    traveler, provider_user, itinerary, stop, _slot = _booking_fixture(db_session, quantity_capacity=2, price=125_000)
    sign_in(client, traveler)
    hold = client.post("/api/bookings", json={"itinerary_id": itinerary.id, "itinerary_stop_id": stop.id, "quantity": 2})
    assert hold.status_code == 201, hold.text
    booking_id = hold.json()["id"]
    sign_in(client, provider_user)
    accepted = client.post(f"/api/provider/me/bookings/{booking_id}/decision", json={"action": "accept", "note": "Capacity checked"})
    assert accepted.status_code == 200, accepted.text
    sign_in(client, traveler)
    checkout = client.post(f"/api/bookings/{booking_id}/checkout")
    assert checkout.status_code == 200, checkout.text
    payment = db_session.scalar(select(PaymentTransaction).where(PaymentTransaction.booking_id == booking_id))
    assert payment is not None
    return traveler, booking_id, payment, checkout.json()["checkout_url"]


def _signed_ipn(payment, *, amount_vnd=None, response_code="00", transaction_status="00"):
    params = {
        "vnp_TmnCode": "TESTTMN1",
        "vnp_TxnRef": payment.provider_reference,
        "vnp_Amount": str((amount_vnd if amount_vnd is not None else payment.amount_vnd) * 100),
        "vnp_CurrCode": "VND",
        "vnp_ResponseCode": response_code,
        "vnp_TransactionStatus": transaction_status,
        "vnp_TransactionNo": "9988776655",
        "vnp_PayDate": "20261004120000",
    }
    params["vnp_SecureHash"] = sign_params(params, "test-vnpay-secret")
    return params


def test_vnpay_checkout_uses_signed_gateway_url_and_reuses_pending_transaction(client, db_session, monkeypatch):
    _traveler, booking_id, payment, checkout_url = _prepare_vnpay_booking(client, db_session, monkeypatch)
    params = {key: values[0] for key, values in parse_qs(urlsplit(checkout_url).query).items()}
    assert urlsplit(checkout_url).netloc == "sandbox.vnpayment.vn"
    assert params["vnp_TmnCode"] == "TESTTMN1"
    assert params["vnp_TxnRef"] == payment.provider_reference
    assert params["vnp_Amount"] == str(payment.amount_vnd * 100)
    assert verify_params(params, "test-vnpay-secret")
    again = client.post(f"/api/bookings/{booking_id}/checkout")
    assert again.status_code == 200
    assert again.json()["checkout_url"] == checkout_url
    assert db_session.scalar(select(func.count(PaymentTransaction.id)).where(PaymentTransaction.booking_id == booking_id)) == 1


def test_vnpay_return_is_display_only_and_signed_ipn_confirms_idempotently(client, db_session, monkeypatch):
    _traveler, booking_id, payment, _checkout_url = _prepare_vnpay_booking(client, db_session, monkeypatch)
    params = _signed_ipn(payment)

    browser_return = client.get("/api/payments/vnpay/return", params=params, follow_redirects=False)
    assert browser_return.status_code == 303
    assert f"booking={booking_id}" in browser_return.headers["location"]
    assert db_session.get(Booking, booking_id).status == "awaiting_payment"

    invalid_signature = dict(params, vnp_SecureHash="0" * 128)
    invalid = client.get("/api/payments/vnpay/ipn", params=invalid_signature)
    assert invalid.json()["RspCode"] == "97"
    mismatch = _signed_ipn(payment, amount_vnd=payment.amount_vnd + 1)
    mismatched = client.get("/api/payments/vnpay/ipn", params=mismatch)
    assert mismatched.json()["RspCode"] == "04"
    assert db_session.get(Booking, booking_id).status == "awaiting_payment"

    settled = client.get("/api/payments/vnpay/ipn", params=params)
    assert settled.json()["RspCode"] == "00"
    assert db_session.get(PaymentTransaction, payment.id).status == "succeeded"
    assert db_session.get(Booking, booking_id).status == "confirmed"
    duplicate = client.get("/api/payments/vnpay/ipn", params=params)
    assert duplicate.json()["RspCode"] == "02"


def test_vnpay_capture_after_hold_expiry_goes_to_reconciliation_not_confirmation(client, db_session, monkeypatch):
    _traveler, booking_id, payment, _checkout_url = _prepare_vnpay_booking(client, db_session, monkeypatch)
    booking = db_session.get(Booking, booking_id)
    booking.hold_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    response = client.get("/api/payments/vnpay/ipn", params=_signed_ipn(payment))
    assert response.json()["RspCode"] == "00"
    assert db_session.get(PaymentTransaction, payment.id).status == "succeeded"
    assert db_session.get(Booking, booking_id).status == "refund_pending"


def test_vnpay_failed_attempt_is_visible_and_checkout_can_be_retried(client, db_session, monkeypatch):
    _traveler, booking_id, payment, _checkout_url = _prepare_vnpay_booking(client, db_session, monkeypatch)
    failed = client.get("/api/payments/vnpay/ipn", params=_signed_ipn(payment, response_code="24", transaction_status="02"))
    assert failed.json()["RspCode"] == "00"
    assert db_session.get(PaymentTransaction, payment.id).status == "failed"
    assert db_session.get(Booking, booking_id).status == "awaiting_payment"
    listing = client.get("/api/bookings")
    assert listing.status_code == 200
    assert listing.json()[0]["payment_status"] == "failed"

    retry = client.post(f"/api/bookings/{booking_id}/checkout")
    assert retry.status_code == 200
    assert retry.json()["checkout_url"] != _checkout_url
    assert db_session.scalar(select(func.count(PaymentTransaction.id)).where(PaymentTransaction.booking_id == booking_id)) == 2


def test_vnpay_suspicious_capture_requires_reconciliation(client, db_session, monkeypatch):
    _traveler, booking_id, payment, _checkout_url = _prepare_vnpay_booking(client, db_session, monkeypatch)
    nonfinal = client.get("/api/payments/vnpay/ipn", params=_signed_ipn(payment, response_code="00", transaction_status="01"))
    assert nonfinal.json()["RspCode"] == "99"
    assert db_session.get(PaymentTransaction, payment.id).status == "pending"

    suspicious = client.get("/api/payments/vnpay/ipn", params=_signed_ipn(payment, response_code="07", transaction_status="00"))
    assert suspicious.json()["RspCode"] == "00"
    assert db_session.get(PaymentTransaction, payment.id).status == "succeeded"
    assert db_session.get(Booking, booking_id).status == "refund_pending"


def _prepare_momo_booking(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "payment_provider", "momo")
    monkeypatch.setattr(settings, "momo_environment", "sandbox")
    monkeypatch.setattr(settings, "momo_partner_code", "MOMO_TEST")
    monkeypatch.setattr(settings, "momo_access_key", "access-test")
    monkeypatch.setattr(settings, "momo_secret_key", "secret-test")
    monkeypatch.setattr(settings, "momo_api_url", "https://test-payment.momo.vn/v2/gateway/api/create")
    monkeypatch.setattr(settings, "momo_return_url", "https://payments.example.org/api/payments/momo/return")
    monkeypatch.setattr(settings, "momo_ipn_url", "https://payments.example.org/api/payments/momo/ipn")
    monkeypatch.setattr(booking_routes, "create_payment_url", lambda _config, _payload: "https://test-payment.momo.vn/v2/gateway/pay?test=1")

    traveler, provider_user, itinerary, stop, _slot = _booking_fixture(db_session, quantity_capacity=2, price=125_000)
    sign_in(client, traveler)
    hold = client.post("/api/bookings", json={"itinerary_id": itinerary.id, "itinerary_stop_id": stop.id, "quantity": 2})
    assert hold.status_code == 201, hold.text
    booking_id = hold.json()["id"]
    sign_in(client, provider_user)
    accepted = client.post(f"/api/provider/me/bookings/{booking_id}/decision", json={"action": "accept", "note": "Capacity checked"})
    assert accepted.status_code == 200, accepted.text
    sign_in(client, traveler)
    checkout = client.post(f"/api/bookings/{booking_id}/checkout")
    assert checkout.status_code == 200, checkout.text
    payment = db_session.scalar(select(PaymentTransaction).where(PaymentTransaction.booking_id == booking_id))
    assert payment is not None and payment.provider == "momo"
    return booking_id, payment, checkout.json()["checkout_url"]


def _signed_momo_ipn(payment, *, amount=None, result_code=0):
    payload = {
        "orderType": "momo_wallet",
        "amount": payment.amount_vnd if amount is None else amount,
        "partnerCode": "MOMO_TEST",
        "orderId": payment.provider_reference,
        "extraData": "",
        "transId": 123456789,
        "responseTime": 1_760_000_000_000,
        "resultCode": result_code,
        "message": "Successful." if result_code == 0 else "Failed.",
        "payType": "qr",
        "requestId": payment.idempotency_key,
        "orderInfo": "LocalExplorer booking",
    }
    canonical = "&".join(f"{key}={payload.get(key, '')}" for key in IPN_SIGNATURE_FIELDS)
    payload["signature"] = hmac.new(b"secret-test", ("accessKey=access-test&" + canonical.split("&", 1)[1]).encode(), hashlib.sha256).hexdigest()
    return payload


def test_momo_checkout_return_and_signed_ipn_are_idempotent(client, db_session, monkeypatch):
    booking_id, payment, checkout_url = _prepare_momo_booking(client, db_session, monkeypatch)
    assert checkout_url.startswith("https://test-payment.momo.vn/v2/gateway/pay")
    browser_return = client.get("/api/payments/momo/return", params={"orderId": payment.provider_reference}, follow_redirects=False)
    assert browser_return.status_code == 303
    assert db_session.get(Booking, booking_id).status == "awaiting_payment"

    invalid = _signed_momo_ipn(payment)
    invalid["signature"] = "0" * 64
    assert client.post("/api/payments/momo/ipn", json=invalid).status_code == 401
    mismatch = client.post("/api/payments/momo/ipn", json=_signed_momo_ipn(payment, amount=payment.amount_vnd + 1))
    assert mismatch.status_code == 400
    assert db_session.get(Booking, booking_id).status == "awaiting_payment"

    settled = client.post("/api/payments/momo/ipn", json=_signed_momo_ipn(payment))
    assert settled.status_code == 204
    assert db_session.get(PaymentTransaction, payment.id).status == "succeeded"
    assert db_session.get(Booking, booking_id).status == "confirmed"
    duplicate = client.post("/api/payments/momo/ipn", json=_signed_momo_ipn(payment))
    assert duplicate.status_code == 204
