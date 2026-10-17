"""TOTP (RFC 6238) and recovery codes. Framework-independent: no database, no web."""

from __future__ import annotations

import hmac
import secrets
import time
from dataclasses import dataclass

import pyotp
import segno

from .refresh import hash_refresh_token  # SHA-256 hex helper, reused for recovery codes

STEP_SECONDS = 30
DIGITS = 6
WINDOW = 1                 # accept the previous and next step to tolerate clock drift
RECOVERY_CODE_COUNT = 10
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"   # no 0/o/1/i/l: easy to read aloud and copy


def new_secret() -> str:
    return pyotp.random_base32(32)  # 160 bits, base32


def provisioning_uri(secret: str, account: str, issuer: str) -> str:
    return pyotp.TOTP(secret, digits=DIGITS, interval=STEP_SECONDS).provisioning_uri(name=account, issuer_name=issuer)


def qr_data_uri(uri: str) -> str:
    """The QR code as an SVG data URI (built here so the browser needs no QR library and no inline markup)."""
    return segno.make(uri, error="m").svg_data_uri(scale=5, border=2)


@dataclass(frozen=True)
class TotpMatch:
    step: int


def verify(secret: str, code: str, *, last_used_step: int | None = None, now: float | None = None) -> TotpMatch | None:
    """Return the matched time step, or ``None``. A step at or before ``last_used_step`` is refused (no code replay)."""
    cleaned = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(cleaned) != DIGITS:
        return None
    current = int((time.time() if now is None else now) // STEP_SECONDS)
    totp = pyotp.TOTP(secret, digits=DIGITS, interval=STEP_SECONDS)
    for step in range(current - WINDOW, current + WINDOW + 1):
        if last_used_step is not None and step <= last_used_step:
            continue
        if hmac.compare_digest(totp.at(step * STEP_SECONDS), cleaned):
            return TotpMatch(step=step)
    return None


def code_at(secret: str, now: float) -> str:
    """The code valid at ``now`` (used by tests and the E2E helper; never needed in production code paths)."""
    return pyotp.TOTP(secret, digits=DIGITS, interval=STEP_SECONDS).at(now)


def new_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    """Ten single-use codes, 10 characters from a 31-letter alphabet (about 50 bits each), shown as ``xxxxx-xxxxx``."""
    out = []
    for _ in range(count):
        raw = "".join(secrets.choice(_ALPHABET) for _ in range(10))
        out.append(f"{raw[:5]}-{raw[5:]}")
    return out


def normalize_recovery_code(code: str) -> str:
    return "".join(ch for ch in (code or "").lower() if ch.isalnum())


def hash_recovery_code(code: str) -> str:
    return hash_refresh_token(normalize_recovery_code(code))


def is_totp_shaped(code: str) -> bool:
    """Six digits (spaces allowed) is an authenticator code; anything else is treated as a recovery code."""
    cleaned = "".join(ch for ch in (code or "") if not ch.isspace())
    return len(cleaned) == DIGITS and cleaned.isdigit()
