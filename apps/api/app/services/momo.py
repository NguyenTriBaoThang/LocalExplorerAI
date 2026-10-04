"""MoMo captureWallet checkout and signed notification helpers."""

from dataclasses import dataclass
import hashlib
import hmac
import ipaddress
import re
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.integration_config import resolve_integration_value


@dataclass(frozen=True)
class MomoConfig:
    environment: str
    partner_code: str
    access_key: str
    secret_key: str
    api_url: str
    return_url: str
    ipn_url: str

    @property
    def checkout_enabled(self) -> bool:
        if not all((self.partner_code, self.access_key, self.secret_key, self.api_url, self.return_url, self.ipn_url)):
            return False
        try:
            api = urlparse(self.api_url)
            returned = urlparse(self.return_url)
            ipn = urlparse(self.ipn_url)
        except ValueError:
            return False
        expected_host = "test-payment.momo.vn" if self.environment == "sandbox" else "payment.momo.vn"
        if api.scheme != "https" or api.hostname != expected_host or api.path != "/v2/gateway/api/create":
            return False
        return _valid_callback(returned, "/api/payments/momo/return") and _valid_callback(ipn, "/api/payments/momo/ipn")


def _valid_callback(parsed, expected_path: str) -> bool:
    if (
        parsed.scheme != "https" or not parsed.hostname or parsed.path != expected_path
        or parsed.query or parsed.fragment or parsed.username or parsed.password
    ):
        return False
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".test", ".example")):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return "." in host


def get_momo_config(db: Session | None) -> MomoConfig:
    def value(name: str) -> str:
        return (resolve_integration_value(db, "payments", f"momo_{name}") or "").strip()

    return MomoConfig(
        environment=value("environment") or "sandbox",
        partner_code=value("partner_code"),
        access_key=value("access_key"),
        secret_key=value("secret_key"),
        api_url=value("api_url"),
        return_url=value("return_url"),
        ipn_url=value("ipn_url"),
    )


def _signing_string(values: dict[str, object], keys: tuple[str, ...]) -> str:
    return "&".join(f"{key}={values.get(key) if values.get(key) is not None else ''}" for key in keys)


CREATE_SIGNATURE_FIELDS = (
    "accessKey", "amount", "extraData", "ipnUrl", "orderId", "orderInfo",
    "partnerCode", "redirectUrl", "requestId", "requestType",
)
IPN_SIGNATURE_FIELDS = (
    "accessKey", "amount", "extraData", "message", "orderId", "orderInfo",
    "orderType", "partnerCode", "payType", "requestId", "responseTime", "resultCode", "transId",
)
CREATE_RESPONSE_SIGNATURE_FIELDS = (
    "accessKey", "amount", "message", "orderId", "partnerCode", "payUrl",
    "requestId", "responseTime", "resultCode",
)


def sign_create_payload(values: dict[str, object], access_key: str, secret_key: str) -> str:
    signed = {**values, "accessKey": access_key}
    return hmac.new(
        secret_key.encode("utf-8"),
        _signing_string(signed, CREATE_SIGNATURE_FIELDS).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_ipn_signature(payload: dict[str, object], access_key: str, secret_key: str) -> bool:
    supplied = payload.get("signature")
    if not isinstance(supplied, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", supplied):
        return False
    expected = hmac.new(
        secret_key.encode("utf-8"),
        _signing_string({**payload, "accessKey": access_key}, IPN_SIGNATURE_FIELDS).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(supplied.lower(), expected)


def verify_create_response_signature(payload: dict[str, object], access_key: str, secret_key: str) -> bool:
    supplied = payload.get("signature")
    if not isinstance(supplied, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", supplied):
        return False
    expected = hmac.new(
        secret_key.encode("utf-8"),
        _signing_string({**payload, "accessKey": access_key}, CREATE_RESPONSE_SIGNATURE_FIELDS).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(supplied.lower(), expected)


def build_create_payload(
    config: MomoConfig,
    *,
    amount_vnd: int,
    order_id: str,
    request_id: str,
    order_info: str,
) -> dict[str, object]:
    values: dict[str, object] = {
        "partnerCode": config.partner_code,
        "requestId": request_id,
        "amount": amount_vnd,
        "orderId": order_id,
        "orderInfo": order_info[:255],
        "redirectUrl": config.return_url,
        "ipnUrl": config.ipn_url,
        "requestType": "captureWallet",
        "extraData": "",
        "autoCapture": True,
        "lang": "vi",
    }
    values["signature"] = sign_create_payload(values, config.access_key, config.secret_key)
    return values


class MomoProviderError(RuntimeError):
    pass


class MomoRejectedError(MomoProviderError):
    """MoMo returned a signed, definitive rejection for the create request."""


def create_payment_url(config: MomoConfig, payload: dict[str, object]) -> str:
    """Call the configured MoMo endpoint; never expose response bodies in exceptions."""
    try:
        with httpx.Client(timeout=max(30.0, settings.openai_timeout_seconds)) as client:
            response = client.post(config.api_url, json=payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise MomoProviderError("MoMo payment creation request failed.") from error
    if not isinstance(result, dict) or not verify_create_response_signature(result, config.access_key, config.secret_key):
        raise MomoProviderError("MoMo returned an invalid payment response signature.")
    if (
        str(result.get("partnerCode", "")) != config.partner_code
        or str(result.get("orderId", "")) != str(payload.get("orderId", ""))
        or str(result.get("requestId", "")) != str(payload.get("requestId", ""))
        or str(result.get("amount", "")) != str(payload.get("amount", ""))
    ):
        raise MomoProviderError("MoMo response did not match the payment request.")
    if result.get("resultCode") != 0:
        raise MomoRejectedError("MoMo rejected the payment session request.")
    pay_url = result.get("payUrl")
    if not isinstance(pay_url, str):
        raise MomoProviderError("MoMo response did not include a payment URL.")
    parsed = urlparse(pay_url)
    allowed_hosts = {"test-payment.momo.vn", "payment.momo.vn"}
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts or parsed.username or parsed.password or parsed.fragment:
        raise MomoProviderError("MoMo returned an untrusted payment URL.")
    return pay_url
