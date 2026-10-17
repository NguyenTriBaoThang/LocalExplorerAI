"""API keys for machine callers (scripts, monitors): ``lek_<key_id>_<secret>``; only a hash of the secret is stored."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

PREFIX = "lek"


@dataclass(frozen=True)
class GeneratedKey:
    key_id: str
    full_key: str       # shown to the operator once
    secret_hash: str    # stored


def hash_secret(secret: str) -> str:
    # The secret is 256 bits of randomness, so a plain SHA-256 is sufficient (no password stretching needed).
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_service_key() -> GeneratedKey:
    key_id = secrets.token_hex(6)
    secret = secrets.token_urlsafe(32)
    return GeneratedKey(key_id=key_id, full_key=f"{PREFIX}_{key_id}_{secret}", secret_hash=hash_secret(secret))


def parse_service_key(raw: str) -> tuple[str, str] | None:
    parts = raw.split("_", 2)
    if len(parts) != 3 or parts[0] != PREFIX or not parts[1] or not parts[2]:
        return None
    return parts[1], parts[2]


def verify_secret(secret: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(secret), stored_hash)
