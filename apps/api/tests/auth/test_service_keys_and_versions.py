import pytest

from app.auth import (
    AccessClaims, AccountDisabled, InMemoryStateStore, RedisStateStore, TokenRevoked, TokenVersionChecker, UserState,
    generate_service_key, parse_service_key, verify_secret,
)


def test_service_key_roundtrip_and_hash_only_storage():
    generated = generate_service_key()
    assert generated.full_key.startswith("lek_") and generated.secret_hash not in generated.full_key
    key_id, secret = parse_service_key(generated.full_key)
    assert key_id == generated.key_id
    assert verify_secret(secret, generated.secret_hash)
    assert not verify_secret(secret + "x", generated.secret_hash)


def test_secrets_containing_underscores_still_parse():
    assert parse_service_key("lek_abc123_se_cr_et-value") == ("abc123", "se_cr_et-value")


@pytest.mark.parametrize("raw", ["", "lek", "lek_only", "xxx_id_secret", "lek__secret", "lek_id_"])
def test_malformed_service_keys_are_rejected(raw):
    assert parse_service_key(raw) is None


def claims(ver=0, sub="u1"):
    return AccessClaims(sub=sub, sid="s", role="traveler", provider_id=None, ver=ver, amr=("pwd",), jti="j", iat=0, exp=1)


class Loader:
    def __init__(self, state):
        self.state, self.calls = state, 0

    def __call__(self, user_id):
        self.calls += 1
        return self.state


def test_matching_version_passes_and_is_cached():
    loader = Loader(UserState(2, True))
    checker = TokenVersionChecker(InMemoryStateStore(), loader)
    checker.check(claims(ver=2))
    checker.check(claims(ver=2))
    assert loader.calls == 1


def test_bumped_version_revokes_the_old_token_once_the_cache_is_invalidated():
    loader = Loader(UserState(1, True))
    checker = TokenVersionChecker(InMemoryStateStore(), loader)
    checker.check(claims(ver=1))
    loader.state = UserState(2, True)       # role changed -> token_version bumped
    checker.invalidate("u1")
    with pytest.raises(TokenRevoked):
        checker.check(claims(ver=1))
    checker.check(claims(ver=2))


def test_disabled_or_unknown_users_are_rejected():
    with pytest.raises(AccountDisabled):
        TokenVersionChecker(InMemoryStateStore(), Loader(UserState(0, False))).check(claims())
    with pytest.raises(AccountDisabled):
        TokenVersionChecker(InMemoryStateStore(), Loader(None)).check(claims())


class FakeRedis:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def setex(self, key, ttl, value):
        self.data[key] = value

    def delete(self, key):
        self.data.pop(key, None)


class DeadRedis:
    def get(self, key):
        raise ConnectionError("down")

    setex = delete = get


def test_redis_store_roundtrip():
    store = RedisStateStore(FakeRedis())
    assert store.get("u1") is None
    store.set("u1", UserState(5, True))
    assert store.get("u1") == UserState(5, True)
    store.set("u2", UserState(1, False))
    assert store.get("u2") == UserState(1, False)
    store.invalidate("u1")
    assert store.get("u1") is None


def test_database_is_used_when_redis_is_down():
    loader = Loader(UserState(3, True))
    checker = TokenVersionChecker(RedisStateStore(DeadRedis()), loader)
    checker.check(claims(ver=3))
    with pytest.raises(TokenRevoked):
        checker.check(claims(ver=2))
    assert loader.calls == 2
