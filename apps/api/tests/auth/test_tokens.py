import base64
import hashlib
import hmac
import json
import time

import jwt
import pytest

from app.auth import (
    AuthNotConfigured, KeyRing, TokenExpired, TokenInvalid, TokenService, generate_rsa_keypair,
)
from tests.auth.conftest import issue


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def test_roundtrip_preserves_claims(tokens):
    token, issued = issue(tokens, role="provider", provider_id="p1", token_version=3, amr=("pwd", "otp"))
    claims = tokens.verify_access(token)
    assert (claims.sub, claims.sid, claims.role, claims.provider_id, claims.ver, claims.amr) == ("u1", "s1", "provider", "p1", 3, ("pwd", "otp"))
    assert claims.jti == issued.jti and claims.exp - claims.iat == 900


def test_expired_token_is_rejected(tokens):
    token, _ = issue(tokens, ttl_seconds=-120)
    with pytest.raises(TokenExpired):
        tokens.verify_access(token)


def test_wrong_audience_and_issuer_are_rejected(keyring, tokens):
    token, _ = issue(tokens)
    with pytest.raises(TokenInvalid):
        TokenService(keyring, issuer="iss", audience="other").verify_access(token)
    with pytest.raises(TokenInvalid):
        TokenService(keyring, issuer="other", audience="aud").verify_access(token)


def test_tampered_payload_is_rejected(tokens):
    token, _ = issue(tokens)
    header, payload, signature = token.split(".")
    data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    data["role"] = "admin"
    forged = ".".join([header, _b64(json.dumps(data).encode()), signature])
    with pytest.raises(TokenInvalid):
        tokens.verify_access(forged)


def test_alg_none_is_rejected(tokens):
    payload = {"iss": "iss", "aud": "aud", "sub": "u1", "sid": "s1", "role": "admin", "ver": 0, "jti": "x",
               "iat": int(time.time()), "nbf": int(time.time()), "exp": int(time.time()) + 600}
    forged = _b64(json.dumps({"alg": "none", "typ": "JWT", "kid": "k1"}).encode()) + "." + _b64(json.dumps(payload).encode()) + "."
    with pytest.raises(TokenInvalid):
        tokens.verify_access(forged)


def test_hs256_signed_with_the_public_key_is_rejected(tokens, keypair):
    """Classic algorithm-confusion attack: HMAC-sign using the (public) RSA key as the secret."""
    _, public_b64 = keypair
    public_pem = base64.b64decode(public_b64)
    now = int(time.time())
    payload = {"iss": "iss", "aud": "aud", "sub": "u1", "sid": "s1", "role": "admin", "ver": 0, "jti": "x", "iat": now, "nbf": now, "exp": now + 600}
    unsigned = _b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": "k1"}).encode()) + "." + _b64(json.dumps(payload).encode())
    signature = hmac.new(public_pem, unsigned.encode(), hashlib.sha256).digest()
    with pytest.raises(TokenInvalid):
        tokens.verify_access(unsigned + "." + _b64(signature))


def test_unknown_kid_is_rejected(keyring, tokens):
    other_private, _ = generate_rsa_keypair(bits=2048)
    other = TokenService(KeyRing.from_b64(active_kid="other", private_key_b64=other_private), issuer="iss", audience="aud")
    token, _ = issue(other)
    with pytest.raises(TokenInvalid):
        tokens.verify_access(token)


def test_same_kid_but_different_key_is_rejected(tokens):
    other_private, _ = generate_rsa_keypair(bits=2048)
    impostor = TokenService(KeyRing.from_b64(active_kid="k1", private_key_b64=other_private), issuer="iss", audience="aud")
    token, _ = issue(impostor)
    with pytest.raises(TokenInvalid):
        tokens.verify_access(token)


def test_missing_required_claim_is_rejected(keyring, tokens):
    now = int(time.time())
    payload = {"iss": "iss", "aud": "aud", "sub": "u1", "role": "traveler", "ver": 0, "jti": "x", "iat": now, "nbf": now, "exp": now + 600}  # no sid
    token = jwt.encode(payload, keyring.private_key, algorithm="RS256", headers={"kid": "k1"})
    with pytest.raises(TokenInvalid):
        tokens.verify_access(token)


@pytest.mark.parametrize("garbage", ["", "abc", "a.b.c", "not.a.jwt.at.all"])
def test_garbage_is_rejected(tokens, garbage):
    with pytest.raises(TokenInvalid):
        tokens.verify_access(garbage)


def test_retired_key_still_verifies_after_rotation():
    old_private, old_public = generate_rsa_keypair(bits=2048)
    new_private, _ = generate_rsa_keypair(bits=2048)
    old_service = TokenService(KeyRing.from_b64(active_kid="2026-01", private_key_b64=old_private), issuer="i", audience="a")
    rotated = TokenService(KeyRing.from_b64(active_kid="2026-04", private_key_b64=new_private, public_keys_b64={"2026-01": old_public}), issuer="i", audience="a")
    old_token, _ = issue(old_service)
    new_token, _ = issue(rotated)
    assert rotated.verify_access(old_token).sub == "u1"
    assert rotated.verify_access(new_token).sub == "u1"
    assert jwt.get_unverified_header(new_token)["kid"] == "2026-04"


def test_key_ring_configuration_errors(keypair):
    private_b64, public_b64 = keypair
    with pytest.raises(AuthNotConfigured):
        KeyRing.from_b64(active_kid=None, private_key_b64=private_b64)
    with pytest.raises(AuthNotConfigured):
        KeyRing.from_b64(active_kid="k", private_key_b64=None)
    with pytest.raises(AuthNotConfigured):
        KeyRing.from_b64(active_kid="k", private_key_b64="%%% not base64 %%%")
    with pytest.raises(AuthNotConfigured):
        KeyRing.from_b64(active_kid="k", private_key_b64=base64.b64encode(b"not a pem").decode())
    with pytest.raises(AuthNotConfigured):  # a public key is not accepted as the signing key
        KeyRing.from_b64(active_kid="k", private_key_b64=public_b64)


def test_weak_rsa_key_is_refused():
    weak_private, _ = generate_rsa_keypair(bits=1024)
    with pytest.raises(AuthNotConfigured):
        KeyRing.from_b64(active_kid="k", private_key_b64=weak_private)
