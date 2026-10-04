import hashlib
import hmac
from datetime import datetime
from urllib.parse import urlencode


def _canonical_query(params: dict[str, str]) -> str:
    values = [
        (key, str(value)) for key, value in params.items()
        if key.startswith("vnp_") and key not in {"vnp_SecureHash", "vnp_SecureHashType"} and value is not None
    ]
    return urlencode(sorted(values), doseq=False)


def sign_params(params: dict[str, str], secret: str) -> str:
    query = _canonical_query(params)
    return hmac.new(secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha512).hexdigest()


def verify_params(params: dict[str, str], secret: str) -> bool:
    supplied = params.get("vnp_SecureHash", "")
    if not supplied or len(supplied) != 128:
        return False
    return hmac.compare_digest(sign_params(params, secret), supplied.lower())


def build_payment_url(
    *,
    payment_url: str,
    tmn_code: str,
    hash_secret: str,
    return_url: str,
    amount_vnd: int,
    transaction_ref: str,
    order_info: str,
    client_ip: str,
    created_at: datetime,
    expires_at: datetime,
) -> str:
    params = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": tmn_code,
        "vnp_Amount": str(amount_vnd * 100),
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": transaction_ref,
        "vnp_OrderInfo": order_info,
        "vnp_OrderType": "other",
        "vnp_Locale": "vn",
        "vnp_ReturnUrl": return_url,
        "vnp_IpAddr": client_ip,
        "vnp_CreateDate": created_at.strftime("%Y%m%d%H%M%S"),
        "vnp_ExpireDate": expires_at.strftime("%Y%m%d%H%M%S"),
    }
    query = _canonical_query(params)
    signature = hmac.new(hash_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha512).hexdigest()
    return f"{payment_url}?{query}&vnp_SecureHash={signature}"
