"""Phase 5: two-factor authentication (TOTP + recovery codes), the administrator gate and operator recovery."""

import re
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select, update

from app.api.routes import auth as auth_routes
from app.auth import hash_password, totp
from app.core.config import settings
from app.models.auth_entities import AuthEvent, AuthSession, AuthToken, MFARecoveryCode, UserMFA
from app.models.entities import User
from app.services import account_tokens
from app.services.auth_runtime import token_service
from scripts import admin_recovery
from tests.helpers import bearer_for, make_user, sign_in

PASSWORD = "long-enough-password"


@pytest.fixture(autouse=True)
def master_key(monkeypatch):
    monkeypatch.setattr(settings, "integration_secrets_key", Fernet.generate_key().decode())


@pytest.fixture(autouse=True)
def mfa_enforced(monkeypatch):
    """These tests describe the production behaviour; the switch itself is tested separately."""
    monkeypatch.setattr(settings, "admin_mfa_required", True)


@pytest.fixture
def clock(monkeypatch):
    """Controllable time for TOTP only (other modules, such as token expiry, keep the real clock)."""
    state = {"t": float(int(time.time() // 30) * 30 + 5)}
    monkeypatch.setattr(totp, "time", SimpleNamespace(time=lambda: state["t"]))
    return state


def person(db, role="traveler", **kw):
    return make_user(db, role, password_hash=hash_password(PASSWORD), **kw)


def enrol(client, db, user, clock):
    """Run the real setup + enable flow as the user; returns (seed, recovery_codes)."""
    client.cookies.clear()
    start = bearer_for(user, amr=("pwd",))        # a header, so the only cookies afterwards are the ones the server sets
    seed = client.post("/api/auth/mfa/setup", headers=start).json()["secret"]
    enabled = client.post("/api/auth/mfa/enable", json={"code": totp.code_at(seed, clock["t"])}, headers=start)
    assert enabled.status_code == 200, enabled.text
    clock["t"] += 30                       # the enrolment code's step is spent; the next login uses the following step
    return seed, enabled.json()["recovery_codes"]


def password_step(client, user):
    return client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})


def second_step(client, ticket, code):
    return client.post("/api/auth/login/mfa", json={"mfa_ticket": ticket, "code": code})


def cookie_names(response):
    return {h.split("=", 1)[0] for h in response.headers.get_list("set-cookie")}


# ───────────────────────────── enrolment ─────────────────────────────
def test_setup_returns_the_seed_once_and_enforces_nothing_until_confirmed(client, db_session):
    user = person(db_session)
    sign_in(client, user)
    body = client.post("/api/auth/mfa/setup").json()
    assert body["otpauth_uri"].startswith("otpauth://totp/") and body["qr"].startswith("data:image/svg+xml")
    status = client.get("/api/auth/mfa").json()
    assert status == {"enabled": False, "required": False, "setup_pending": True, "recovery_codes_remaining": 0}
    assert "secret" not in str(status)
    assert password_step(client, user).json().get("mfa_required") is None                  # still a normal login
    again = client.post("/api/auth/mfa/setup").json()["secret"]
    assert again != body["secret"]                                                           # restarting replaces the pending seed


def test_the_seed_is_stored_encrypted(client, db_session):
    user = person(db_session)
    sign_in(client, user)
    seed = client.post("/api/auth/mfa/setup").json()["secret"]
    stored = db_session.get(UserMFA, user.id).secret_encrypted
    assert seed not in stored and stored.startswith("gAAAA")                                # a Fernet token, not the seed


def test_enable_needs_a_correct_code_and_hands_out_recovery_codes_once(client, db_session, clock):
    user = person(db_session)
    sign_in(client, user)
    seed = client.post("/api/auth/mfa/setup").json()["secret"]
    wrong = client.post("/api/auth/mfa/enable", json={"code": "000000"})
    assert wrong.status_code == 401 and wrong.json()["error"]["code"] == "MFA_CODE_INVALID"
    db_session.refresh(user)
    assert user.mfa_enabled is False

    ok = client.post("/api/auth/mfa/enable", json={"code": totp.code_at(seed, clock["t"])})
    assert ok.status_code == 200 and len(ok.json()["recovery_codes"]) == 10
    db_session.refresh(user)
    assert user.mfa_enabled is True
    stored = db_session.scalars(select(MFARecoveryCode).where(MFARecoveryCode.user_id == user.id)).all()
    assert len(stored) == 10 and not {c.code_hash for c in stored} & set(ok.json()["recovery_codes"])   # only hashes are kept
    assert {"le_at", "le_rt"} <= cookie_names(ok)
    assert client.get("/api/auth/mfa").json()["recovery_codes_remaining"] == 10


def test_enable_without_setup_and_double_setup_are_refused(client, db_session, clock):
    user = person(db_session)
    sign_in(client, user)
    assert client.post("/api/auth/mfa/enable", json={"code": "123456"}).json()["error"]["code"] == "MFA_SETUP_REQUIRED"
    enrol(client, db_session, user, clock)
    again = client.post("/api/auth/mfa/setup")
    assert again.status_code == 409 and again.json()["error"]["code"] == "MFA_ALREADY_ENABLED"


def test_enabling_signs_other_devices_out_but_keeps_this_one(client, db_session, clock):
    user = person(db_session)
    other_device = bearer_for(user)
    assert client.get("/api/auth/me", headers=other_device).status_code == 200
    enrol(client, db_session, user, clock)
    assert client.get("/api/auth/me", headers=other_device).status_code == 401              # never passed a second factor
    assert client.get("/api/auth/me").status_code == 200                                      # this device was upgraded
    session = db_session.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))).one()
    assert "otp" in session.amr


def test_mfa_needs_the_master_key_and_says_so(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "integration_secrets_key", None)
    sign_in(client, person(db_session))
    response = client.post("/api/auth/mfa/setup")
    assert response.status_code == 503 and response.json()["error"]["code"] == "MFA_NOT_CONFIGURED"


# ───────────────────────────── two-step sign-in ─────────────────────────────
def test_password_alone_does_not_open_a_session_for_an_mfa_account(client, db_session, clock):
    user = person(db_session)
    enrol(client, db_session, user, clock)
    client.cookies.clear()
    step1 = password_step(client, user)
    assert step1.status_code == 200 and step1.json()["mfa_required"] is True and step1.json()["expires_in"] == 300
    assert cookie_names(step1) == set()
    assert client.get("/api/auth/me").status_code == 401
    wrong = client.post("/api/auth/login", json={"email": user.email, "password": "not-the-password"})
    assert wrong.status_code == 401 and "mfa_ticket" not in wrong.text                      # no ticket for a wrong password


def test_a_correct_code_completes_the_sign_in_with_a_second_factor(client, db_session, clock):
    user = person(db_session)
    seed, _ = enrol(client, db_session, user, clock)
    client.cookies.clear()
    ticket = password_step(client, user).json()["mfa_ticket"]
    done = second_step(client, ticket, totp.code_at(seed, clock["t"]))
    assert done.status_code == 200 and done.json()["email"] == user.email and {"le_at", "le_rt"} <= cookie_names(done)
    claims = token_service().verify_access(client.cookies.get("le_at"))
    assert claims.amr == ("pwd", "otp")


def test_a_wrong_code_keeps_the_ticket_alive_and_a_right_one_spends_it(client, db_session, clock):
    user = person(db_session)
    seed, _ = enrol(client, db_session, user, clock)
    client.cookies.clear()
    ticket = password_step(client, user).json()["mfa_ticket"]
    bad = second_step(client, ticket, "000000")
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "MFA_CODE_INVALID" and cookie_names(bad) == set()
    assert second_step(client, ticket, totp.code_at(seed, clock["t"])).status_code == 200
    reuse = second_step(client, ticket, totp.code_at(seed, clock["t"] + 30))
    assert reuse.status_code == 400 and reuse.json()["error"]["code"] == "TOKEN_INVALID"   # one ticket, one session


def test_an_authenticator_code_works_only_once_even_inside_its_window(client, db_session, clock):
    user = person(db_session)
    seed, _ = enrol(client, db_session, user, clock)
    client.cookies.clear()
    code = totp.code_at(seed, clock["t"])
    assert second_step(client, password_step(client, user).json()["mfa_ticket"], code).status_code == 200
    client.cookies.clear()
    replay = second_step(client, password_step(client, user).json()["mfa_ticket"], code)
    assert replay.status_code == 401 and replay.json()["error"]["code"] == "MFA_CODE_INVALID"
    clock["t"] += 30
    client.cookies.clear()
    assert second_step(client, password_step(client, user).json()["mfa_ticket"], totp.code_at(seed, clock["t"])).status_code == 200


def test_a_ticket_is_bound_to_its_own_user(client, db_session, clock):
    alice, bob = person(db_session), person(db_session)
    alice_seed, _ = enrol(client, db_session, alice, clock)
    bob_seed, _ = enrol(client, db_session, bob, clock)
    client.cookies.clear()
    ticket_for_alice = password_step(client, alice).json()["mfa_ticket"]
    assert second_step(client, ticket_for_alice, totp.code_at(bob_seed, clock["t"])).status_code == 401   # Bob's code is no use
    assert second_step(client, ticket_for_alice, totp.code_at(alice_seed, clock["t"])).status_code == 200


def test_the_mfa_ticket_expires(client, db_session, clock):
    user = person(db_session)
    seed, _ = enrol(client, db_session, user, clock)
    client.cookies.clear()
    ticket = password_step(client, user).json()["mfa_ticket"]
    db_session.execute(update(AuthToken).where(AuthToken.purpose == "mfa_login").values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    db_session.commit()
    late = second_step(client, ticket, totp.code_at(seed, clock["t"]))
    assert late.status_code == 400 and late.json()["error"]["code"] == "TOKEN_INVALID"


def test_five_wrong_codes_lock_further_attempts_for_a_while(client, db_session, clock):
    user = person(db_session)
    seed, _ = enrol(client, db_session, user, clock)
    client.cookies.clear()
    ticket = password_step(client, user).json()["mfa_ticket"]
    for _ in range(5):
        assert second_step(client, ticket, "000000").status_code == 401
    locked = second_step(client, ticket, totp.code_at(seed, clock["t"]))                   # even the right code is refused now
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "MFA_LOCKED"
    db_session.execute(update(AuthEvent).where(AuthEvent.event_type == "mfa_verify").values(created_at=datetime.now(timezone.utc) - timedelta(minutes=16)))
    db_session.commit()
    assert second_step(client, ticket, totp.code_at(seed, clock["t"])).status_code == 200


# ───────────────────────────── recovery codes ─────────────────────────────
def test_a_recovery_code_signs_in_once_and_is_then_gone(client, db_session, clock):
    user = person(db_session)
    _, codes = enrol(client, db_session, user, clock)
    client.cookies.clear()
    messy = f"  {codes[0].upper()} "                                                         # case and spacing do not matter
    first = second_step(client, password_step(client, user).json()["mfa_ticket"], messy)
    assert first.status_code == 200
    assert client.get("/api/auth/mfa").json()["recovery_codes_remaining"] == 9
    client.cookies.clear()
    second = second_step(client, password_step(client, user).json()["mfa_ticket"], codes[0])
    assert second.status_code == 401 and second.json()["error"]["code"] == "MFA_CODE_INVALID"
    assert db_session.scalar(select(AuthEvent).where(AuthEvent.event_type == "mfa_verify", AuthEvent.outcome == "success")) is not None


def test_recovery_codes_can_be_regenerated_and_the_old_ones_die(client, db_session, clock):
    user = person(db_session)
    seed, old = enrol(client, db_session, user, clock)
    no_code = client.post("/api/auth/mfa/recovery-codes", json={"code": "000000"})
    assert no_code.status_code == 401
    new = client.post("/api/auth/mfa/recovery-codes", json={"code": totp.code_at(seed, clock["t"])}).json()["recovery_codes"]
    assert len(new) == 10 and not set(new) & set(old)
    client.cookies.clear()
    assert second_step(client, password_step(client, user).json()["mfa_ticket"], old[0]).status_code == 401
    assert second_step(client, password_step(client, user).json()["mfa_ticket"], new[0]).status_code == 200


# ───────────────────────────── turning it off ─────────────────────────────
def test_a_traveler_can_turn_mfa_off_with_password_and_code(client, db_session, clock):
    user = person(db_session)
    seed, _ = enrol(client, db_session, user, clock)
    old_token = client.cookies.get("le_at")
    assert client.post("/api/auth/mfa/disable", json={"password": "wrong-password", "code": totp.code_at(seed, clock["t"])}).status_code == 400
    assert client.post("/api/auth/mfa/disable", json={"password": PASSWORD, "code": "000000"}).status_code == 401
    off = client.post("/api/auth/mfa/disable", json={"password": PASSWORD, "code": totp.code_at(seed, clock["t"])})
    assert off.status_code == 200 and off.json() == {"enabled": False}
    db_session.refresh(user)
    assert user.mfa_enabled is False and db_session.get(UserMFA, user.id) is None
    assert db_session.scalars(select(MFARecoveryCode)).all() == []
    assert client.get("/api/auth/me", headers=as_header(old_token)).status_code == 401
    client.cookies.clear()
    assert password_step(client, user).json().get("mfa_required") is None


def as_header(token):
    return {"Authorization": f"Bearer {token}"}


# ───────────────────────────── administrators ─────────────────────────────
def test_an_administrator_without_mfa_can_sign_in_but_only_enrol(client, db_session, clock):
    admin = person(db_session, role="admin")
    login = password_step(client, admin)
    assert login.status_code == 200 and "mfa_required" not in login.json()
    blocked = client.get("/api/admin/dashboard")
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "MFA_REQUIRED"
    assert client.get("/api/ops/status").json()["error"]["code"] == "MFA_REQUIRED"
    assert client.get("/api/auth/me").status_code == 200 and client.get("/api/auth/mfa").json()["required"] is True
    seed = client.post("/api/auth/mfa/setup").json()["secret"]
    assert client.post("/api/auth/mfa/enable", json={"code": totp.code_at(seed, clock["t"])}).status_code == 200
    assert client.get("/api/admin/dashboard").status_code == 200                              # the upgraded session passes the gate


def test_an_old_password_only_session_cannot_reach_admin_routes_even_after_enrolment(client, db_session, clock):
    admin = person(db_session, role="admin")
    stale = bearer_for(admin, amr=("pwd",))
    enrol(client, db_session, admin, clock)                                                    # bumps token_version too
    assert client.get("/api/admin/dashboard", headers=stale).status_code == 401
    client.cookies.clear()
    password_only = bearer_for(admin, amr=("pwd",))
    # a token with a current version but no second factor is still refused by the gate
    db_session.refresh(admin)
    password_only = bearer_for(admin, amr=("pwd",))
    assert client.get("/api/admin/dashboard", headers=password_only).json()["error"]["code"] == "MFA_REQUIRED"


def test_administrators_cannot_turn_mfa_off(client, db_session, clock):
    admin = person(db_session, role="admin")
    seed, _ = enrol(client, db_session, admin, clock)
    refused = client.post("/api/auth/mfa/disable", json={"password": PASSWORD, "code": totp.code_at(seed, clock["t"])})
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "MFA_REQUIRED_FOR_ROLE"
    db_session.refresh(admin)
    assert admin.mfa_enabled is True


def test_an_administrator_with_mfa_signs_in_in_two_steps_and_reaches_admin_routes(client, db_session, clock):
    admin = person(db_session, role="admin")
    seed, _ = enrol(client, db_session, admin, clock)
    client.cookies.clear()
    ticket = password_step(client, admin).json()["mfa_ticket"]
    assert second_step(client, ticket, totp.code_at(seed, clock["t"])).status_code == 200
    assert client.get("/api/admin/dashboard").status_code == 200


def test_service_accounts_are_not_subject_to_the_administrator_gate(client, db_session):
    from app.services.rbac_service import create_service_account
    _, key = create_service_account(db_session, "monitor", ["ops:read"], None)
    assert client.get("/api/ops/status", headers={"Authorization": f"Bearer {key}"}).status_code == 200


# ───────────────────────────── password recovery for administrators ─────────────────────────────
@pytest.fixture
def mailbox(monkeypatch):
    sent = []
    monkeypatch.setattr(auth_routes, "queue_account_link", lambda db, user, *, purpose, token_id, raw_token: sent.append((purpose, user.email, raw_token)) or True)
    return sent


def test_an_administrator_without_mfa_gets_no_reset_email(client, db_session, mailbox):
    admin = person(db_session, role="admin")
    assert client.post("/api/auth/password/forgot", json={"email": admin.email}).status_code == 202
    assert mailbox == []
    _, token = account_tokens.issue(db_session, admin, account_tokens.RESET_PASSWORD)          # even a token that somehow exists is refused
    db_session.commit()
    refused = client.post("/api/auth/password/reset", json={"token": token, "new_password": "a-brand-new-passphrase"})
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "ADMIN_RESET_FORBIDDEN"
    assert client.post("/api/auth/login", json={"email": admin.email, "password": PASSWORD}).status_code == 200


def test_an_administrator_with_mfa_can_reset_by_email_but_still_needs_the_code_to_sign_in(client, db_session, clock, mailbox):
    admin = person(db_session, role="admin")
    seed, _ = enrol(client, db_session, admin, clock)
    client.cookies.clear()
    client.post("/api/auth/password/forgot", json={"email": admin.email})
    token = mailbox[-1][2]
    assert client.post("/api/auth/password/reset", json={"token": token, "new_password": "a-brand-new-passphrase"}).status_code == 200
    step1 = client.post("/api/auth/login", json={"email": admin.email, "password": "a-brand-new-passphrase"})
    assert step1.json()["mfa_required"] is True                                                # email access alone is not enough


# ───────────────────────────── operator recovery ─────────────────────────────
def test_operator_can_set_an_administrator_password_and_reset_mfa(client, db_session, clock):
    admin = person(db_session, role="admin")
    seed, _ = enrol(client, db_session, admin, clock)
    token = client.cookies.get("le_at")
    new_password = admin_recovery.set_password(db_session, admin.email)
    assert client.get("/api/auth/me", headers=as_header(token)).status_code == 401           # every session ended
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": admin.email, "password": new_password}).json()["mfa_required"] is True
    admin_recovery.reset_mfa(db_session, admin.email)
    db_session.refresh(admin)
    assert admin.mfa_enabled is False and db_session.get(UserMFA, admin.id) is None
    login = client.post("/api/auth/login", json={"email": admin.email, "password": new_password})
    assert "mfa_required" not in login.json()                                                  # enrols again at the next sign-in
    events = {e.event_type for e in db_session.scalars(select(AuthEvent))}
    assert {"operator_set_password", "operator_reset_mfa"} <= events


def test_operator_commands_refuse_non_administrators(db_session):
    traveler = person(db_session)
    with pytest.raises(SystemExit):
        admin_recovery.set_password(db_session, traveler.email)
    with pytest.raises(SystemExit):
        admin_recovery.reset_mfa(db_session, "nobody@example.test")


def test_mfa_endpoints_require_a_signed_in_user(client):
    assert client.get("/api/auth/mfa").status_code == 401
    assert client.post("/api/auth/mfa/setup").status_code == 401
    assert client.post("/api/auth/mfa/enable", json={"code": "123456"}).status_code == 401


# ───────────────────────────── the ADMIN_MFA_REQUIRED switch ─────────────────────────────
def _settings(**kw):
    from app.core.config import Settings
    return Settings(_env_file=None, **kw)


def test_the_switch_defaults_to_on_in_production_and_off_elsewhere():
    prod, dev = _settings(app_env="production"), _settings(app_env="development")
    assert prod.admin_mfa_required is True and dev.admin_mfa_required is False
    assert _settings(app_env="test").admin_mfa_required is False


def test_an_explicit_value_always_wins_in_either_direction():
    assert _settings(app_env="production", admin_mfa_required=False).admin_mfa_required is False
    assert _settings(app_env="development", admin_mfa_required=True).admin_mfa_required is True


def test_with_the_switch_off_administrators_are_not_gated(client, db_session, monkeypatch, mailbox):
    monkeypatch.setattr(settings, "admin_mfa_required", False)
    admin = person(db_session, role="admin")
    password_only = bearer_for(admin, amr=("pwd",))
    assert client.get("/api/admin/dashboard", headers=password_only).status_code == 200
    assert client.get("/api/auth/mfa", headers=password_only).json()["required"] is False
    assert client.post("/api/auth/password/forgot", json={"email": admin.email}).status_code == 202
    assert [m[1] for m in mailbox] == [admin.email]                                         # normal e-mail recovery returns


def test_with_the_switch_off_an_administrator_may_turn_mfa_off_but_can_still_choose_to_use_it(client, db_session, clock, monkeypatch):
    monkeypatch.setattr(settings, "admin_mfa_required", False)
    admin = person(db_session, role="admin")
    seed, _ = enrol(client, db_session, admin, clock)
    off = client.post("/api/auth/mfa/disable", json={"password": PASSWORD, "code": totp.code_at(seed, clock["t"])})
    assert off.status_code == 200
    db_session.refresh(admin)
    assert admin.mfa_enabled is False


def test_flipping_the_switch_takes_effect_on_the_next_request(client, db_session, monkeypatch):
    admin = person(db_session, role="admin")
    password_only = bearer_for(admin, amr=("pwd",))
    monkeypatch.setattr(settings, "admin_mfa_required", False)
    assert client.get("/api/admin/dashboard", headers=password_only).status_code == 200
    monkeypatch.setattr(settings, "admin_mfa_required", True)
    assert client.get("/api/admin/dashboard", headers=password_only).json()["error"]["code"] == "MFA_REQUIRED"
