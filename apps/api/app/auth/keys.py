"""RSA key handling for RS256 tokens.

Keys come from environment variables as base64-encoded PEM. The active key signs; every key in the ring
(including retired ones kept for a while) verifies, selected by the JWT ``kid`` header.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from .errors import AuthNotConfigured

MIN_RSA_BITS = 2048


def _b64decode(value: str) -> bytes:
    cleaned = "".join(value.split())
    try:
        return base64.b64decode(cleaned + "=" * (-len(cleaned) % 4), altchars=b"-_" if ("-" in cleaned or "_" in cleaned) else None, validate=True)
    except (binascii.Error, ValueError) as error:
        raise AuthNotConfigured("An auth key is not valid base64.") from error


def _load_private(b64_pem: str) -> rsa.RSAPrivateKey:
    try:
        key = serialization.load_pem_private_key(_b64decode(b64_pem), password=None)
    except (ValueError, TypeError) as error:
        raise AuthNotConfigured("The auth private key is not a valid unencrypted PEM key.") from error
    if not isinstance(key, rsa.RSAPrivateKey):
        raise AuthNotConfigured("The auth private key must be an RSA key.")
    if key.key_size < MIN_RSA_BITS:
        raise AuthNotConfigured(f"The auth private key must be at least {MIN_RSA_BITS} bits.")
    return key


def _load_public(b64_pem: str) -> rsa.RSAPublicKey:
    try:
        key = serialization.load_pem_public_key(_b64decode(b64_pem))
    except (ValueError, TypeError) as error:
        raise AuthNotConfigured("An auth public key is not a valid PEM key.") from error
    if not isinstance(key, rsa.RSAPublicKey):
        raise AuthNotConfigured("Auth public keys must be RSA keys.")
    if key.key_size < MIN_RSA_BITS:
        raise AuthNotConfigured(f"Auth public keys must be at least {MIN_RSA_BITS} bits.")
    return key


@dataclass(frozen=True)
class KeyRing:
    active_kid: str
    private_key: rsa.RSAPrivateKey
    public_keys: dict[str, rsa.RSAPublicKey]

    @classmethod
    def from_b64(cls, *, active_kid: str | None, private_key_b64: str | None, public_keys_b64: dict[str, str] | None = None) -> "KeyRing":
        if not private_key_b64 or not active_kid:
            raise AuthNotConfigured("Set the auth signing key id and base64 private key (see scripts/generate_auth_keys.py).")
        private = _load_private(private_key_b64)
        public = {kid: _load_public(value) for kid, value in (public_keys_b64 or {}).items()}
        # The active key always verifies its own tokens; extra public keys are retired keys still honoured.
        public[active_kid] = private.public_key()
        return cls(active_kid=active_kid, private_key=private, public_keys=public)

    def public_for(self, kid: str | None) -> rsa.RSAPublicKey | None:
        return self.public_keys.get(kid) if kid else None


def generate_rsa_keypair(bits: int = 3072) -> tuple[str, str]:
    """Return (private_pem_b64, public_pem_b64) suitable for environment variables."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    private_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public_pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(private_pem).decode("ascii"), base64.b64encode(public_pem).decode("ascii")
