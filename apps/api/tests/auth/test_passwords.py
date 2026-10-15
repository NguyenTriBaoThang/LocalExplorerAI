import pytest

from app.auth import WeakPassword, hash_password, validate_password_policy, verify_password
from app.services.auth_service import hash_password as legacy_hash_password


def test_argon2id_roundtrip():
    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith("$argon2id$")
    result = verify_password("correct horse battery staple", encoded)
    assert result.valid and not result.needs_rehash
    assert not verify_password("wrong password value", encoded).valid


def test_legacy_scrypt_hash_verifies_and_requests_rehash():
    legacy = legacy_hash_password("old password 123")
    result = verify_password("old password 123", legacy)
    assert result.valid and result.needs_rehash
    assert not verify_password("different", legacy).valid


def test_missing_or_malformed_hash_never_validates():
    assert not verify_password("anything at all", None).valid
    assert not verify_password("anything at all", "").valid
    assert not verify_password("anything at all", "not-a-hash").valid
    assert not verify_password("anything at all", "scrypt$broken").valid


@pytest.mark.parametrize("password", ["short1", "password1234", "aaaaaaaaaaaaaaaa", "x" * 129])
def test_policy_rejects_weak_passwords(password):
    with pytest.raises(WeakPassword):
        validate_password_policy(password)


def test_policy_rejects_password_containing_email_name():
    with pytest.raises(WeakPassword):
        validate_password_policy("nguyenmaibao-2026!", email="nguyenmaibao@example.com")


def test_policy_accepts_a_good_passphrase():
    validate_password_policy("tram-xanh-bay-qua-song-2026", email="a@example.com")
