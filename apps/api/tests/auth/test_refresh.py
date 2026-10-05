from datetime import datetime, timedelta, timezone

import pytest

from app.auth import (
    LifetimePolicy, RefreshOutcome, StoredSession, decide_refresh, hash_refresh_token, needs_refresh, new_refresh_token,
)

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


def test_refresh_tokens_are_unique_and_only_the_hash_is_derivable():
    a, b = new_refresh_token(), new_refresh_token()
    assert a.raw != b.raw and a.hash != b.hash
    assert a.hash == hash_refresh_token(a.raw) and a.raw not in a.hash and len(a.hash) == 64


def test_lifetimes_follow_the_agreed_numbers():
    policy = LifetimePolicy()
    user = policy.new_session("traveler", NOW)
    admin = policy.new_session("admin", NOW)
    assert user.expires_at - NOW == timedelta(days=7) and user.absolute_expires_at - NOW == timedelta(days=30)
    assert admin.expires_at - NOW == timedelta(days=1) and admin.absolute_expires_at - NOW == timedelta(days=7)


def test_sliding_refresh_is_capped_by_the_absolute_limit():
    policy = LifetimePolicy()
    session = policy.new_session("traveler", NOW)
    late = NOW + timedelta(days=29)
    rotated = policy.rotate("traveler", late, session.absolute_expires_at)
    assert rotated.expires_at == session.absolute_expires_at
    mid = policy.rotate("traveler", NOW + timedelta(days=2), session.absolute_expires_at)
    assert mid.expires_at == NOW + timedelta(days=9)


def _session(**kw):
    base = dict(expires_at=NOW + timedelta(days=1), absolute_expires_at=NOW + timedelta(days=20), rotated_at=None, revoked_at=None)
    base.update(kw)
    return StoredSession(**base)


def test_decisions():
    assert decide_refresh(_session(), NOW, 10) is RefreshOutcome.ROTATE
    assert decide_refresh(_session(revoked_at=NOW - timedelta(minutes=1)), NOW, 10) is RefreshOutcome.REVOKED
    assert decide_refresh(_session(expires_at=NOW - timedelta(seconds=1)), NOW, 10) is RefreshOutcome.EXPIRED
    assert decide_refresh(_session(absolute_expires_at=NOW - timedelta(seconds=1)), NOW, 10) is RefreshOutcome.EXPIRED


def test_replay_inside_grace_is_tolerated_but_late_replay_is_theft():
    inside = _session(rotated_at=NOW - timedelta(seconds=4))
    late = _session(rotated_at=NOW - timedelta(seconds=11))
    assert decide_refresh(inside, NOW, 10) is RefreshOutcome.REPLAY_IN_GRACE
    assert decide_refresh(late, NOW, 10) is RefreshOutcome.REUSE_DETECTED


def test_revoked_wins_over_everything_else():
    both = _session(revoked_at=NOW, rotated_at=NOW - timedelta(days=1), expires_at=NOW - timedelta(hours=1))
    assert decide_refresh(both, NOW, 10) is RefreshOutcome.REVOKED


@pytest.mark.parametrize("remaining,expected", [(900, False), (181, False), (180, True), (1, True), (-5, True)])
def test_needs_refresh_threshold(remaining, expected):
    assert needs_refresh(1000 + remaining, 1000, 180) is expected
