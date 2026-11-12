"""M10: send, public quote link, accept, deposit checkout, IPN settlement and follow-up rules."""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.api.routes import public_quotes
from app.core.config import settings
from app.models.entities import AuditLog, OperatorOrg, PaymentTransaction, Quote
from app.services.momo import IPN_SIGNATURE_FIELDS
from app.services.quote import quote_service as qs
from app.services.vnpay import sign_params
from tests.helpers import bearer_for, make_user
from tests.test_operator_quotes import DEMO_REQ, llm, post, seeded  # noqa: F401  (fixtures)

NOW = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
SECRET_KEYS = {"cost", "cost_total_vnd", "pricing", "margin_floor_pct", "explanation", "raw_message", "customer_contact", "modes", "p_win",
               "margin_pct", "lines", "expected_profit", "rate_card_versions", "unit_vnd", "amount_vnd"}


def keys(obj) -> set:
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in keys(v)}
    return set()


def make_sent(client, seeded, llm):  # noqa: F811
    _, user = seeded
    h = bearer_for(user)
    q = post(client, user, {"request": DEMO_REQ}).json()["quote"]
    sent = client.post(f"/api/operator/quotes/{q['id']}/send", headers=h)
    assert sent.status_code == 200, sent.text
    return q, sent.json(), sent.json()["share_url"].rsplit("/q/", 1)[1], h


# ---- send ---------------------------------------------------------------------------------------------------------

def test_send_hashes_token_rotates_and_keeps_price(client, seeded, llm, db_session):
    q, sent, token, h = make_sent(client, seeded, llm)
    row = db_session.get(Quote, q["id"])
    assert sent["share_url"].startswith(settings.web_app_url.rstrip("/") + "/q/") and len(token) >= 43
    assert row.public_token_hash == hashlib.sha256(token.encode()).hexdigest() and token not in json.dumps(sent["quote"])
    assert row.status == "sent" and row.sent_at and row.expires_at - row.sent_at == timedelta(days=7)
    assert q["code"] in sent["message"] and sent["share_url"] in sent["message"] and "Tổng" in sent["message"]
    assert row.price_vnd == q["price_vnd"]
    assert client.post(f"/api/operator/quotes/{q['id']}/select-mode", json={"mode": "safe"}, headers=h).status_code == 409  # no re-pricing
    again = client.post(f"/api/operator/quotes/{q['id']}/send", headers=h).json()["share_url"].rsplit("/q/", 1)[1]
    assert again != token
    assert client.get(f"/api/public/quotes/{token}").status_code == 404
    assert client.get(f"/api/public/quotes/{again}").status_code == 200


def test_send_is_org_scoped_and_blocked_after_accept(client, seeded, llm, db_session):
    q, _, token, h = make_sent(client, seeded, llm)
    other = OperatorOrg(name="Org B", slug="org-b-link", settings={})
    db_session.add(other)
    db_session.commit()
    b = bearer_for(make_user(db_session, "operator", operator_org_id=other.id))
    assert client.post(f"/api/operator/quotes/{q['id']}/send", headers=b).status_code == 404
    assert client.post(f"/api/operator/quotes/{q['id']}/send", headers=bearer_for(make_user(db_session, "traveler"))).status_code == 403
    client.post(f"/api/public/quotes/{token}/accept", json={"name": "An", "phone": "0901234567"})
    assert client.post(f"/api/operator/quotes/{q['id']}/send", headers=h).status_code == 409


# ---- public view --------------------------------------------------------------------------------------------------

def test_public_view_is_customer_safe_and_tracks_views(client, seeded, llm, db_session):
    q, _, token, h = make_sent(client, seeded, llm)
    first = client.get(f"/api/public/quotes/{token}")
    assert first.status_code == 200
    body = first.json()
    assert not (keys(body) & SECRET_KEYS), keys(body) & SECRET_KEYS
    assert body["price_vnd"] == q["price_vnd"] and body["status"] == "viewed" and body["can_accept"]
    assert body["deposit_vnd"] == qs.deposit_vnd(q["price_vnd"], 30) and body["company_name"] and body["itinerary"][0]["stops"]
    assert {"Xe du lịch đưa đón theo lịch trình", "Hướng dẫn viên"} <= set(body["inclusions"])
    assert "ticket_code" not in json.dumps(body) and "distance_km" not in json.dumps(body)
    client.get(f"/api/public/quotes/{token}")
    row = db_session.get(Quote, q["id"])
    db_session.refresh(row)
    assert row.view_count == 2 and row.first_viewed_at is not None and row.status == "viewed"
    detail = client.get(f"/api/operator/quotes/{q['id']}", headers=h).json()
    assert detail["view_count"] == 2 and detail["sent_at"] and detail["deposit_paid_at"] is None
    assert client.get("/api/public/quotes/not-a-token").status_code == 404


def test_public_expiry_blocks_view_accept_and_checkout(client, seeded, llm, db_session):
    q, _, token, h = make_sent(client, seeded, llm)
    row = db_session.get(Quote, q["id"])
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    view = client.get(f"/api/public/quotes/{token}")
    assert view.json()["status"] == "expired" and not view.json()["can_accept"]
    assert client.post(f"/api/public/quotes/{token}/accept", json={"name": "An", "phone": "0901234567"}).status_code == 410
    assert client.post(f"/api/public/quotes/{token}/checkout", json={}).status_code == 410
    # the operator can re-send an expired quote: new link, validity renewed
    assert client.post(f"/api/operator/quotes/{q['id']}/send", headers=h).status_code == 200
    db_session.refresh(row)
    assert row.status == "sent"


def test_accept(client, seeded, llm, db_session):
    q, _, token, h = make_sent(client, seeded, llm)
    assert client.post(f"/api/public/quotes/{token}/accept", json={"name": "", "phone": "09"}).status_code == 422
    ok = client.post(f"/api/public/quotes/{token}/accept", json={"name": " Nguyễn An ", "phone": "0901 234 567"})
    assert ok.status_code == 200 and ok.json()["status"] == "accepted" and ok.json()["can_pay"]
    row = db_session.get(Quote, q["id"])
    assert row.status == "accepted" and row.accepted_at and row.customer_name == "Nguyễn An"
    assert db_session.scalar(select(AuditLog).where(AuditLog.target_id == q["id"], AuditLog.action == "quote.accepted"))
    assert client.post(f"/api/public/quotes/{token}/accept", json={"name": "X", "phone": "0901234567"}).status_code == 200  # idempotent


# ---- deposit ------------------------------------------------------------------------------------------------------

def test_deposit_amount_rounding():
    assert qs.deposit_vnd(10_000_000, 30) == 3_000_000
    assert qs.deposit_vnd(12_345_000, 30) == 3_704_000  # 3,703,500 -> next 1,000
    assert qs.deposit_vnd(500, 100) == 500  # never above the price


def _gateways(monkeypatch):
    monkeypatch.setattr(settings, "vnpay_environment", "sandbox")
    monkeypatch.setattr(settings, "vnpay_tmn_code", "TESTTMN1")
    monkeypatch.setattr(settings, "vnpay_hash_secret", "test-vnpay-secret")
    monkeypatch.setattr(settings, "vnpay_payment_url", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
    monkeypatch.setattr(settings, "vnpay_return_url", "https://payments.example.org/api/payments/vnpay/return")
    monkeypatch.setattr(settings, "vnpay_ipn_url", "https://payments.example.org/api/payments/vnpay/ipn")
    monkeypatch.setattr(settings, "momo_environment", "sandbox")
    monkeypatch.setattr(settings, "momo_partner_code", "MOMO_TEST")
    monkeypatch.setattr(settings, "momo_access_key", "access-test")
    monkeypatch.setattr(settings, "momo_secret_key", "secret-test")
    monkeypatch.setattr(settings, "momo_api_url", "https://test-payment.momo.vn/v2/gateway/api/create")
    monkeypatch.setattr(settings, "momo_return_url", "https://payments.example.org/api/payments/momo/return")
    monkeypatch.setattr(settings, "momo_ipn_url", "https://payments.example.org/api/payments/momo/ipn")
    monkeypatch.setattr(public_quotes, "create_payment_url", lambda _c, _p: "https://test-payment.momo.vn/v2/gateway/pay?test=1")


def accepted(client, seeded, llm):  # noqa: F811
    q, _, token, h = make_sent(client, seeded, llm)
    client.post(f"/api/public/quotes/{token}/accept", json={"name": "An", "phone": "0901234567"})
    return q, token


def test_checkout_requires_accept_and_computes_deposit(client, seeded, llm, db_session, monkeypatch):
    _gateways(monkeypatch)
    q, _, token, _h = make_sent(client, seeded, llm)
    assert client.post(f"/api/public/quotes/{token}/checkout", json={"provider": "vnpay"}).status_code == 409
    client.post(f"/api/public/quotes/{token}/accept", json={"name": "An", "phone": "0901234567"})
    r = client.post(f"/api/public/quotes/{token}/checkout", json={"provider": "vnpay"})
    assert r.status_code == 200, r.text
    expected = qs.deposit_vnd(q["price_vnd"], 30)
    pay = db_session.scalar(select(PaymentTransaction).where(PaymentTransaction.quote_id == q["id"]))
    assert r.json()["amount_vnd"] == expected == pay.amount_vnd and pay.booking_id is None and pay.checkout_url.startswith("https://sandbox.vnpayment.vn")
    assert f"vnp_Amount={expected * 100}" in r.json()["checkout_url"]
    m = client.post(f"/api/public/quotes/{token}/checkout", json={"provider": "momo"})
    assert m.status_code == 200 and m.json()["checkout_url"].startswith("https://test-payment.momo.vn")


def test_momo_cap_rejects_large_deposit(client, seeded, llm, db_session, monkeypatch):
    _gateways(monkeypatch)
    q, token = accepted(client, seeded, llm)
    row = db_session.get(Quote, q["id"])
    row.price_vnd = 200_000_000  # 30% = 60,000,000 > 50,000,000
    db_session.commit()
    r = client.post(f"/api/public/quotes/{token}/checkout", json={"provider": "momo"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "PAYMENT_AMOUNT_UNSUPPORTED" and "MoMo" in json.dumps(r.json(), ensure_ascii=False)
    assert client.post(f"/api/public/quotes/{token}/checkout", json={"provider": "vnpay"}).status_code == 200


# ---- IPN ----------------------------------------------------------------------------------------------------------

def vnpay_ipn(payment, *, amount=None, code="00"):
    params = {"vnp_TmnCode": "TESTTMN1", "vnp_TxnRef": payment.provider_reference,
              "vnp_Amount": str((amount if amount is not None else payment.amount_vnd) * 100), "vnp_CurrCode": "VND",
              "vnp_ResponseCode": code, "vnp_TransactionStatus": "00" if code == "00" else "02", "vnp_TransactionNo": "9988776655",
              "vnp_PayDate": "20261004120000"}
    params["vnp_SecureHash"] = sign_params(params, "test-vnpay-secret")
    return params


def momo_ipn(payment, *, amount=None, result_code=0):
    payload = {"orderType": "momo_wallet", "amount": payment.amount_vnd if amount is None else amount, "partnerCode": "MOMO_TEST",
               "orderId": payment.provider_reference, "extraData": "", "transId": 123456789, "responseTime": 1_760_000_000_000,
               "resultCode": result_code, "message": "ok", "payType": "qr", "requestId": payment.idempotency_key, "orderInfo": "Coc"}
    canonical = "&".join(f"{k}={payload.get(k, '')}" for k in IPN_SIGNATURE_FIELDS)
    payload["signature"] = hmac.new(b"secret-test", ("accessKey=access-test&" + canonical.split("&", 1)[1]).encode(), hashlib.sha256).hexdigest()
    return payload


def paid_state(db_session, q):
    db_session.expire_all()
    return db_session.get(Quote, q["id"]).status


def test_vnpay_ipn_settles_quote_deposit_idempotently(client, seeded, llm, db_session, monkeypatch):
    _gateways(monkeypatch)
    q, token = accepted(client, seeded, llm)
    client.post(f"/api/public/quotes/{token}/checkout", json={"provider": "vnpay"})
    pay = db_session.scalar(select(PaymentTransaction).where(PaymentTransaction.quote_id == q["id"]))
    bad = vnpay_ipn(pay)
    bad["vnp_SecureHash"] = "0" * 128
    assert client.get("/api/payments/vnpay/ipn", params=bad).json()["RspCode"] == "97"
    assert client.get("/api/payments/vnpay/ipn", params=vnpay_ipn(pay, amount=pay.amount_vnd + 1000)).json()["RspCode"] == "04"
    assert paid_state(db_session, q) == "accepted"
    ret = client.get("/api/payments/vnpay/return", params=vnpay_ipn(pay), follow_redirects=False)
    assert ret.status_code == 303 and "/q/result?status=returned" in ret.headers["location"]
    assert paid_state(db_session, q) == "accepted"  # browser return never settles
    assert client.get("/api/payments/vnpay/ipn", params=vnpay_ipn(pay)).json()["RspCode"] == "00"
    assert paid_state(db_session, q) == "deposit_paid"
    assert client.get("/api/payments/vnpay/ipn", params=vnpay_ipn(pay)).json()["RspCode"] == "02"  # duplicate: no-op
    assert db_session.query(AuditLog).filter_by(target_id=q["id"], action="quote.deposit_paid").count() == 1
    assert client.post(f"/api/public/quotes/{token}/checkout", json={"provider": "vnpay"}).status_code == 409
    detail = client.get(f"/api/operator/quotes/{q['id']}", headers=bearer_for(seeded[1])).json()
    assert detail["status"] == "deposit_paid" and detail["deposit_paid_at"]


def test_vnpay_failed_payment_keeps_quote_accepted(client, seeded, llm, db_session, monkeypatch):
    _gateways(monkeypatch)
    q, token = accepted(client, seeded, llm)
    client.post(f"/api/public/quotes/{token}/checkout", json={"provider": "vnpay"})
    pay = db_session.scalar(select(PaymentTransaction).where(PaymentTransaction.quote_id == q["id"]))
    assert client.get("/api/payments/vnpay/ipn", params=vnpay_ipn(pay, code="24")).json()["RspCode"] == "00"
    db_session.refresh(pay)
    assert pay.status == "failed" and paid_state(db_session, q) == "accepted"


def test_momo_ipn_settles_quote_deposit_idempotently(client, seeded, llm, db_session, monkeypatch):
    _gateways(monkeypatch)
    q, token = accepted(client, seeded, llm)
    client.post(f"/api/public/quotes/{token}/checkout", json={"provider": "momo"})
    pay = db_session.scalar(select(PaymentTransaction).where(PaymentTransaction.quote_id == q["id"]))
    bad = momo_ipn(pay)
    bad["signature"] = "0" * 64
    assert client.post("/api/payments/momo/ipn", json=bad).status_code == 401
    assert client.post("/api/payments/momo/ipn", json=momo_ipn(pay, amount=pay.amount_vnd + 1)).status_code == 400
    assert paid_state(db_session, q) == "accepted"
    ret = client.get("/api/payments/momo/return", params={"orderId": pay.provider_reference, "resultCode": "0"}, follow_redirects=False)
    assert ret.status_code == 303 and "/q/result?status=returned" in ret.headers["location"]
    assert client.post("/api/payments/momo/ipn", json=momo_ipn(pay)).status_code == 204
    assert paid_state(db_session, q) == "deposit_paid"
    assert client.post("/api/payments/momo/ipn", json=momo_ipn(pay)).status_code == 204  # duplicate
    assert db_session.query(AuditLog).filter_by(target_id=q["id"], action="quote.deposit_paid").count() == 1


def test_payment_target_check_constraint(db_session):
    from sqlalchemy.exc import IntegrityError
    db_session.add(PaymentTransaction(provider="momo", idempotency_key="k-none", amount_vnd=1000))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ---- follow-up ----------------------------------------------------------------------------------------------------

def quote(status, **kw):
    return Quote(status=status, code="Q-2026-0001", customer_name="Chị Lan", price_vnd=10_000_000, **kw)


def test_followup_rules_with_frozen_time():
    far = NOW + timedelta(days=5)
    f = lambda q, now=NOW: qs.followup_reason(q, now)
    assert f(quote("sent", sent_at=NOW - timedelta(hours=25), expires_at=far)) == "not_viewed"
    assert f(quote("sent", sent_at=NOW - timedelta(hours=23), expires_at=far)) is None
    assert f(quote("viewed", sent_at=NOW - timedelta(days=3), first_viewed_at=NOW - timedelta(hours=49), expires_at=far)) == "not_accepted"
    assert f(quote("viewed", sent_at=NOW - timedelta(days=3), first_viewed_at=NOW - timedelta(hours=47), expires_at=far)) is None
    assert f(quote("viewed", sent_at=NOW, first_viewed_at=NOW, expires_at=NOW + timedelta(hours=23))) == "expiring"
    assert f(quote("sent", sent_at=NOW, expires_at=NOW + timedelta(hours=25))) is None
    assert f(quote("sent", sent_at=NOW - timedelta(days=9), expires_at=NOW - timedelta(minutes=1))) is None  # already expired
    assert f(quote("accepted", sent_at=NOW - timedelta(days=3), expires_at=NOW + timedelta(hours=2))) is None
    assert f(quote("draft")) is None
    assert "Chị Lan" in qs.reminder_text(quote("sent", expires_at=far), "not_viewed") and "Q-2026-0001" in qs.reminder_text(quote("sent", expires_at=far), "expiring")


def test_followup_endpoint(client, seeded, llm, db_session):
    q, _, token, h = make_sent(client, seeded, llm)
    assert client.get("/api/operator/quotes?needs_followup=1", headers=h).json() == []
    row = db_session.get(Quote, q["id"])
    row.sent_at = datetime.now(timezone.utc) - timedelta(hours=30)
    db_session.commit()
    rows = client.get("/api/operator/quotes?needs_followup=1", headers=h).json()
    assert [r["id"] for r in rows] == [q["id"]] and rows[0]["followup_reason"] == "not_viewed" and q["code"] in rows[0]["reminder_text"]
    client.get(f"/api/public/quotes/{token}")  # viewed -> no longer "not viewed"
    assert client.get("/api/operator/quotes?needs_followup=1", headers=h).json() == []
