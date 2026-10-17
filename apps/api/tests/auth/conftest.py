import pytest

from app.auth import KeyRing, TokenService, generate_rsa_keypair


@pytest.fixture(scope="session")
def keypair():
    return generate_rsa_keypair(bits=2048)


@pytest.fixture(scope="session")
def keyring(keypair):
    private_b64, _ = keypair
    return KeyRing.from_b64(active_kid="k1", private_key_b64=private_b64)


@pytest.fixture
def tokens(keyring):
    return TokenService(keyring, issuer="iss", audience="aud", access_ttl_seconds=900)


def issue(service: TokenService, **overrides):
    args = dict(user_id="u1", session_id="s1", role="traveler", provider_id=None, token_version=0, amr=("pwd",))
    args.update(overrides)
    return service.issue_access(**args)
