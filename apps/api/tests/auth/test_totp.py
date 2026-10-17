import time

import pytest

from app.auth import totp

# RFC 6238 appendix B: ASCII secret "12345678901234567890", SHA-1; at T=59 the 8-digit code is 94287082, so 6 digits is 287082.
RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


def test_matches_the_rfc_6238_test_vector():
    assert totp.code_at(RFC_SECRET, 59) == "287082"
    assert totp.verify(RFC_SECRET, "287082", now=59) is not None


def test_accepts_the_neighbouring_steps_but_nothing_further():
    secret, now = totp.new_secret(), 1_000_000.0
    for offset, ok in ((-60, False), (-30, True), (0, True), (30, True), (60, False)):
        assert (totp.verify(secret, totp.code_at(secret, now + offset), now=now) is not None) is ok, offset


def test_a_code_cannot_be_used_twice():
    secret, now = totp.new_secret(), 2_000_000.0
    code = totp.code_at(secret, now)
    first = totp.verify(secret, code, now=now)
    assert first is not None
    assert totp.verify(secret, code, last_used_step=first.step, now=now) is None
    assert totp.verify(secret, totp.code_at(secret, now - 30), last_used_step=first.step, now=now) is None   # an older step too
    assert totp.verify(secret, totp.code_at(secret, now + 30), last_used_step=first.step, now=now) is not None


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", "12 34 5x", None])
def test_malformed_codes_are_refused(code):
    assert totp.verify(totp.new_secret(), code or "", now=time.time()) is None


def test_spaces_inside_a_code_are_tolerated():
    secret, now = totp.new_secret(), 3_000_000.0
    code = totp.code_at(secret, now)
    assert totp.verify(secret, f"{code[:3]} {code[3:]}", now=now) is not None


def test_provisioning_uri_and_qr_do_not_leak_markup_or_extra_secrets():
    secret = totp.new_secret()
    uri = totp.provisioning_uri(secret, "a+b@example.com", "Local Explorer AI")
    assert uri.startswith("otpauth://totp/") and f"secret={secret}" in uri and "issuer=Local%20Explorer%20AI" in uri
    qr = totp.qr_data_uri(uri)
    assert qr.startswith("data:image/svg+xml") and "<script" not in qr.lower()
    assert secret not in qr        # the seed is encoded in the pattern, not written as text


def test_secrets_are_long_and_unique():
    seeds = {totp.new_secret() for _ in range(50)}
    assert len(seeds) == 50 and all(len(s) >= 32 for s in seeds)


def test_recovery_codes_are_unique_readable_and_hash_consistently():
    codes = totp.new_recovery_codes()
    assert len(codes) == 10 == len(set(codes))
    assert all(len(c) == 11 and c[5] == "-" and not set(c) & set("01ilo") for c in codes)
    code = codes[0]
    variants = [code, code.upper(), code.replace("-", ""), f" {code[:5]} {code[6:]} "]
    assert len({totp.hash_recovery_code(v) for v in variants}) == 1
    assert totp.hash_recovery_code(codes[0]) != totp.hash_recovery_code(codes[1])
    assert code not in totp.hash_recovery_code(code) and len(totp.hash_recovery_code(code)) == 64


def test_authenticator_codes_and_recovery_codes_are_told_apart():
    assert totp.is_totp_shaped("123456") and totp.is_totp_shaped("123 456")
    assert not totp.is_totp_shaped("abcde-fghjk") and not totp.is_totp_shaped("12345") and not totp.is_totp_shaped("1234567")
