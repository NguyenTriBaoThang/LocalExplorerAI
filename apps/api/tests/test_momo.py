from app.services.momo import (
    CREATE_SIGNATURE_FIELDS,
    MomoConfig,
    build_create_payload,
    sign_create_payload,
    verify_ipn_signature,
)


def test_create_payload_uses_capture_wallet_and_momo_signature():
    config = MomoConfig(
        environment="sandbox", partner_code="MOMO_TEST", access_key="access-test", secret_key="secret-test",
        api_url="https://test-payment.momo.vn/v2/gateway/api/create",
        return_url="https://payments.example.org/api/payments/momo/return",
        ipn_url="https://payments.example.org/api/payments/momo/ipn",
    )
    payload = build_create_payload(
        config, amount_vnd=25_000, order_id="a1b2c3", request_id="f6e7d8", order_info="booking",
    )

    assert payload["requestType"] == "captureWallet"
    assert payload["amount"] == 25_000
    assert payload["signature"] == sign_create_payload(payload, config.access_key, config.secret_key)
    assert tuple(sorted(CREATE_SIGNATURE_FIELDS)) == CREATE_SIGNATURE_FIELDS


def test_ipn_signature_verification_rejects_tampering():
    payload = {
        "amount": 25000,
        "extraData": "",
        "message": "Successful.",
        "orderId": "a1b2c3",
        "orderInfo": "booking",
        "orderType": "momo_wallet",
        "partnerCode": "MOMO_TEST",
        "payType": "qr",
        "requestId": "f6e7d8",
        "responseTime": 1_760_000_000_000,
        "resultCode": 0,
        "transId": 123456,
    }
    from app.services.momo import IPN_SIGNATURE_FIELDS
    import hashlib
    import hmac

    canonical = "&".join(f"{key}={payload.get(key, '')}" for key in IPN_SIGNATURE_FIELDS)
    payload["signature"] = hmac.new(b"secret-test", canonical.replace("accessKey=", "accessKey=access-test", 1).encode(), hashlib.sha256).hexdigest()
    assert verify_ipn_signature(payload, "access-test", "secret-test") is True
    payload["amount"] += 1
    assert verify_ipn_signature(payload, "access-test", "secret-test") is False
