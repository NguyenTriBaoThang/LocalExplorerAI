"""Phase 4: password recovery, email verification, session management and the claim-ticket fix."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.api.routes import auth as auth_routes
from app.auth import hash_password
from app.main import app
from app.models.auth_entities import AuthSession, AuthToken
from app.models.entities import Itinerary, ItineraryClaimToken, User
from app.services import account_tokens
from tests.helpers import bearer_for, make_user

PASSWORD = "long-enough-password"
NEW_PASSWORD = "a-brand-new-passphrase"
SHADOW_EMAIL = "zalo_555@localexplorer.site"


def test_auto_verify_registration_without_email(client, db_session, monkeypatch):
    monkeypatch.setattr(auth_routes.settings, 'auto_verify_email', True)
    def no_mail(*args, **kwargs):
        raise AssertionError('Automatic verification must not send an email')
    monkeypatch.setattr(auth_routes, 'queue_account_link', no_mail)
    response = client.post('/api/auth/register', json={
        'email': 'automatic@example.test', 'password': PASSWORD, 'display_name': 'Automatic',
    })
    assert response.status_code == 201
    user = db_session.scalar(select(User).where(User.email == 'automatic@example.test'))
    assert user.email_verified_at is not None
    assert user.role == 'traveler'


@pytest.fixture
def mailbox(monkeypatch):
    """Capture the raw single-use tokens that would be emailed (the outbox only stores rows when SMTP is configured)."""
    sent: list[SimpleNamespace] = []

    def fake(db, user, *, purpose, token_id, raw_token):
        sent.append(SimpleNamespace(purpose=purpose, email=user.email, token=raw_token))
        return True

    monkeypatch.setattr(auth_routes, "queue_account_link", fake)
    return sent


def tokens_of(mailbox, purpose):
    return [m for m in mailbox if m.purpose == purpose]


def person(db, role="traveler", password=PASSWORD, **kw):
    return make_user(db, role, password_hash=hash_password(password), **kw)


def login(client, user, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": user.email, "password": password})


def access_cookie(client):
    return client.cookies.get("le_at")


def as_bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ───────────────────────────── forgot password ─────────────────────────────
def test_forgot_password_does_not_reveal_whether_the_account_exists(client, db_session, mailbox):
    known = person(db_session)
    unknown = client.post("/api/auth/password/forgot", json={"email": "nobody@example.test"})
    real = client.post("/api/auth/password/forgot", json={"email": known.email})
    assert unknown.status_code == real.status_code == 202
    assert unknown.json() == real.json() == {"accepted": True}
    assert [m.email for m in tokens_of(mailbox, "reset_password")] == [known.email]
    assert db_session.scalars(select(AuthToken)).all().__len__() == 1               # nothing was created for the stranger


def test_forgot_password_sends_at_most_one_email_a_minute(client, db_session, mailbox):
    user = person(db_session)
    for _ in range(3):
        assert client.post("/api/auth/password/forgot", json={"email": user.email}).status_code == 202
    assert len(tokens_of(mailbox, "reset_password")) == 1
    assert len(db_session.scalars(select(AuthToken)).all()) == 1


def test_placeholder_and_disabled_accounts_never_get_reset_links(client, db_session, mailbox):
    shadow = person(db_session, email=SHADOW_EMAIL)
    disabled = person(db_session, is_active=False)
    for email in (shadow.email, disabled.email):
        assert client.post("/api/auth/password/forgot", json={"email": email}).status_code == 202
    assert mailbox == []


# ───────────────────────────── reset password ─────────────────────────────
def _request_reset(client, mailbox, user):
    client.post("/api/auth/password/forgot", json={"email": user.email})
    return tokens_of(mailbox, "reset_password")[-1].token


def test_reset_changes_the_password_and_signs_every_device_out(client, db_session, mailbox):
    user = person(db_session, email_verified_at=None)
    login(client, user)
    old_access = access_cookie(client)
    client.cookies.clear()
    token = _request_reset(client, mailbox, user)

    reset = client.post("/api/auth/password/reset", json={"token": token, "new_password": NEW_PASSWORD})
    assert reset.status_code == 200 and reset.json() == {"reset": True}
    assert client.get("/api/auth/me", headers=as_bearer(old_access)).status_code == 401      # the old session died at once
    assert login(client, user, PASSWORD).status_code == 401                                   # the old password is gone
    assert login(client, user, NEW_PASSWORD).status_code == 200
    db_session.refresh(user)
    assert user.email_verified_at is not None                                                 # the link reached the inbox


def test_a_reset_link_works_exactly_once(client, db_session, mailbox):
    user = person(db_session)
    token = _request_reset(client, mailbox, user)
    assert client.post("/api/auth/password/reset", json={"token": token, "new_password": NEW_PASSWORD}).status_code == 200
    again = client.post("/api/auth/password/reset", json={"token": token, "new_password": "yet-another-passphrase"})
    assert again.status_code == 400 and again.json()["error"]["code"] == "TOKEN_INVALID"
    assert login(client, user, NEW_PASSWORD).status_code == 200                               # the second attempt changed nothing


def test_a_weak_password_is_refused_without_burning_the_link(client, db_session, mailbox):
    user = person(db_session)
    token = _request_reset(client, mailbox, user)
    weak = client.post("/api/auth/password/reset", json={"token": token, "new_password": "password1234"})
    assert weak.status_code == 422 and weak.json()["error"]["code"] == "WEAK_PASSWORD"
    assert login(client, user, PASSWORD).status_code == 200                                    # nothing changed
    assert client.post("/api/auth/password/reset", json={"token": token, "new_password": NEW_PASSWORD}).status_code == 200


def test_expired_and_foreign_purpose_tokens_are_rejected(client, db_session, mailbox):
    user = person(db_session, email_verified_at=None)
    token = _request_reset(client, mailbox, user)
    db_session.execute(update(AuthToken).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    db_session.commit()
    expired = client.post("/api/auth/password/reset", json={"token": token, "new_password": NEW_PASSWORD})
    assert expired.status_code == 400 and expired.json()["error"]["code"] == "TOKEN_INVALID"

    _, verify_token = account_tokens.issue(db_session, user, account_tokens.VERIFY_EMAIL)
    db_session.commit()
    assert client.post("/api/auth/password/reset", json={"token": verify_token, "new_password": NEW_PASSWORD}).status_code == 400
    _, reset_token = account_tokens.issue(db_session, user, account_tokens.RESET_PASSWORD)
    db_session.commit()
    assert client.post("/api/auth/email/verify", json={"token": reset_token}).status_code == 400
    assert client.post("/api/auth/password/reset", json={"token": "x" * 43, "new_password": NEW_PASSWORD}).status_code == 400


def test_a_new_link_retires_the_previous_one(db_session):
    user = person(db_session)
    _, first = account_tokens.issue(db_session, user, account_tokens.RESET_PASSWORD)
    _, second = account_tokens.issue(db_session, user, account_tokens.RESET_PASSWORD)
    db_session.commit()
    with pytest.raises(account_tokens.InvalidAccountToken):
        account_tokens.consume(db_session, first, account_tokens.RESET_PASSWORD)
    assert account_tokens.consume(db_session, second, account_tokens.RESET_PASSWORD).id == user.id


def test_only_a_hash_of_each_token_is_stored(db_session):
    user = person(db_session)
    row, raw = account_tokens.issue(db_session, user, account_tokens.RESET_PASSWORD)
    db_session.commit()
    assert raw not in (row.token_hash or "") and len(row.token_hash) == 64


# ───────────────────────────── registration & verification ─────────────────────────────
def test_registration_sends_a_verification_email_and_blocks_booking_until_verified(client, db_session, mailbox):
    response = client.post("/api/auth/register", json={"email": "fresh@example.test", "display_name": "Fresh", "password": PASSWORD})
    assert response.status_code == 201 and response.json()["email_verified_at"] is None
    sent = tokens_of(mailbox, "verify_email")
    assert [m.email for m in sent] == ["fresh@example.test"]
    assert client.get("/api/auth/me").status_code == 200                                      # browsing and planning still work

    body = {"itinerary_id": "nope", "itinerary_stop_id": "nope", "quantity": 1}
    blocked = client.post("/api/bookings", json=body)
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"
    assert client.post("/api/bookings/anything/checkout").json()["error"]["code"] == "EMAIL_NOT_VERIFIED"

    verified = client.post("/api/auth/email/verify", json={"token": sent[0].token})
    assert verified.status_code == 200 and verified.json() == {"verified": True}
    passed = client.post("/api/bookings", json=body)
    assert passed.status_code != 403 or passed.json()["error"]["code"] != "EMAIL_NOT_VERIFIED"
    assert passed.status_code == 404 and passed.json()["error"]["code"] == "ITINERARY_NOT_FOUND"   # now it reaches the real checks
    assert client.post("/api/auth/email/verify", json={"token": sent[0].token}).status_code == 400  # one use only


def test_resending_the_verification_email_is_rate_limited_and_idempotent(client, db_session, mailbox):
    client.post("/api/auth/register", json={"email": "again@example.test", "display_name": "A", "password": PASSWORD})
    too_soon = client.post("/api/auth/email/verify/resend")
    assert too_soon.status_code == 429 and too_soon.json()["error"]["code"] == "VERIFICATION_RECENTLY_SENT"

    db_session.execute(update(AuthToken).values(created_at=datetime.now(timezone.utc) - timedelta(minutes=2)))
    db_session.commit()
    again = client.post("/api/auth/email/verify/resend")
    assert again.status_code == 202 and again.json() == {"email_queued": True}
    first, second = tokens_of(mailbox, "verify_email")
    assert client.post("/api/auth/email/verify", json={"token": first.token}).status_code == 400   # retired by the newer one
    assert client.post("/api/auth/email/verify", json={"token": second.token}).status_code == 200
    assert client.post("/api/auth/email/verify/resend").json() == {"already_verified": True}


def test_resend_requires_a_signed_in_user(client):
    assert client.post("/api/auth/email/verify/resend").status_code == 401


def test_registration_enforces_the_password_policy_and_reserved_addresses(client, mailbox):
    weak = client.post("/api/auth/register", json={"email": "weak@example.test", "display_name": "W", "password": "password1234"})
    assert weak.status_code == 422 and weak.json()["error"]["code"] == "WEAK_PASSWORD"
    short = client.post("/api/auth/register", json={"email": "short@example.test", "display_name": "S", "password": "short-one"})
    assert short.status_code == 422
    reserved = client.post("/api/auth/register", json={"email": SHADOW_EMAIL, "display_name": "R", "password": PASSWORD})
    assert reserved.status_code == 422 and reserved.json()["error"]["code"] == "EMAIL_RESERVED"
    assert mailbox == []


def test_changing_the_password_also_enforces_the_policy(client, db_session):
    user = person(db_session)
    login(client, user)
    weak = client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "password1234"})
    assert weak.status_code == 422 and weak.json()["error"]["code"] == "WEAK_PASSWORD"
    assert login(client, user, PASSWORD).status_code == 200


# ───────────────────────────── session management ─────────────────────────────
def two_devices(db_session):
    user = person(db_session)
    phone = TestClient(app)
    laptop = TestClient(app)
    assert login(laptop, user).status_code == 200
    assert login(phone, user).status_code == 200
    return user, laptop, phone


def test_session_list_marks_the_current_device(db_session, client):
    _, laptop, phone = two_devices(db_session)
    seen = laptop.get("/api/auth/sessions").json()
    assert len(seen) == 2 and [s["current"] for s in seen].count(True) == 1
    assert {"id", "created_at", "last_used_at", "expires_at", "ip", "user_agent", "amr", "current"} <= set(seen[0])
    mine = next(s["id"] for s in seen if s["current"])
    assert next(s for s in phone.get("/api/auth/sessions").json() if s["current"])["id"] != mine


def test_removing_another_device_ends_only_that_device_at_once(db_session, client):
    _, laptop, phone = two_devices(db_session)
    other = next(s["id"] for s in laptop.get("/api/auth/sessions").json() if not s["current"])
    phone_token = access_cookie(phone)
    assert laptop.delete(f"/api/auth/sessions/{other}").status_code == 204
    assert phone.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=as_bearer(phone_token)).status_code == 401
    assert laptop.get("/api/auth/me").status_code == 200
    assert len(laptop.get("/api/auth/sessions").json()) == 1


def test_removing_the_current_device_clears_cookies_and_kills_its_token(db_session, client):
    _, laptop, _ = two_devices(db_session)
    mine = next(s["id"] for s in laptop.get("/api/auth/sessions").json() if s["current"])
    token = access_cookie(laptop)
    response = laptop.delete(f"/api/auth/sessions/{mine}")
    assert response.status_code == 204
    cleared = " ".join(response.headers.get_list("set-cookie"))
    assert "le_at=" in cleared and "le_rt=" in cleared
    assert client.get("/api/auth/me", headers=as_bearer(token)).status_code == 401


def test_other_peoples_sessions_cannot_be_seen_or_removed(db_session, client):
    _, laptop, _ = two_devices(db_session)
    stranger = TestClient(app)
    login(stranger, person(db_session))
    victim_session = laptop.get("/api/auth/sessions").json()[0]["id"]
    assert all(s["id"] != victim_session for s in stranger.get("/api/auth/sessions").json())
    gone = stranger.delete(f"/api/auth/sessions/{victim_session}")
    assert gone.status_code == 404 and gone.json()["error"]["code"] == "SESSION_NOT_FOUND"
    assert laptop.get("/api/auth/me").status_code == 200
    assert stranger.delete("/api/auth/sessions/does-not-exist").status_code == 404


def test_logout_all_ends_every_device(db_session, client):
    _, laptop, phone = two_devices(db_session)
    tokens = [access_cookie(laptop), access_cookie(phone)]
    assert laptop.post("/api/auth/logout-all").status_code == 204
    for token in tokens:
        assert client.get("/api/auth/me", headers=as_bearer(token)).status_code == 401
    assert phone.get("/api/auth/me").status_code == 401


def test_logout_makes_the_old_access_token_useless_immediately(client, db_session):
    user = person(db_session)
    login(client, user)
    token = access_cookie(client)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me", headers=as_bearer(token)).status_code == 401


def test_session_endpoints_require_a_signed_in_user(client):
    assert client.get("/api/auth/sessions").status_code == 401
    assert client.delete("/api/auth/sessions/x").status_code == 401
    assert client.post("/api/auth/logout-all").status_code == 401


# ───────────────────────────── claim ticket ─────────────────────────────
def itinerary_for(db, owner):
    itinerary = Itinerary(user_id=owner.id if owner else None, group_size=1, budget_vnd=100_000,
                          start_at=datetime.now(timezone.utc), end_at=datetime.now(timezone.utc) + timedelta(hours=4),
                          status="feasible", constraints={}, estimated_cost_vnd=0, share_token=f"share-{datetime.now().timestamp()}-{id(owner)}")
    db.add(itinerary)
    db.commit()
    return itinerary, account_tokens.issue_claim_token(db, itinerary.id)


def claim(client, token, email, password=NEW_PASSWORD, **extra):
    return client.post("/api/auth/claim-ticket", json={"claim_token": token, "email": email, "password": password, **extra})


def shadow_owned(db):
    shadow = person(db, email=SHADOW_EMAIL)
    itinerary, token = itinerary_for(db, shadow)
    db.commit()
    return shadow, itinerary, token


def test_claiming_with_a_new_email_creates_a_traveler_and_spends_the_token(client, db_session, mailbox):
    shadow, itinerary, token = shadow_owned(db_session)
    response = claim(client, token, "newcomer@example.test", display_name="Newcomer")
    assert response.status_code == 200 and response.json()["role"] == "traveler"
    created = db_session.scalar(select(User).where(User.email == "newcomer@example.test"))
    db_session.refresh(itinerary)
    assert itinerary.user_id == created.id and created.email_verified_at is None
    assert [m.email for m in tokens_of(mailbox, "verify_email")] == ["newcomer@example.test"]
    assert {"le_at", "le_rt"} <= {h.split("=", 1)[0] for h in response.headers.get_list("set-cookie")}
    db_session.refresh(shadow)
    assert shadow.email == SHADOW_EMAIL                                                      # the placeholder is never taken over
    again = claim(TestClient(app), token, "second@example.test")
    assert again.status_code == 400 and again.json()["error"]["code"] == "TOKEN_INVALID"


def test_claiming_with_an_existing_account_only_signs_in_and_leaves_it_untouched(client, db_session, mailbox):
    _, itinerary, token = shadow_owned(db_session)
    account = person(db_session, password=PASSWORD)
    naive = lambda value: value.replace(tzinfo=None)   # SQLite hands datetimes back without a timezone
    before = (account.password_hash, account.display_name, naive(account.email_verified_at))
    response = claim(client, token, account.email, PASSWORD, display_name="Hijack attempt")
    assert response.status_code == 200 and response.json()["id"] == account.id
    db_session.refresh(account)
    db_session.refresh(itinerary)
    assert itinerary.user_id == account.id
    assert (account.password_hash, account.display_name, naive(account.email_verified_at)) == before
    assert db_session.scalars(select(User).where(User.email == account.email)).all().__len__() == 1
    assert mailbox == []


def test_a_wrong_password_does_not_spend_the_claim_token(client, db_session, mailbox):
    _, itinerary, token = shadow_owned(db_session)
    account = person(db_session, password=PASSWORD)
    wrong = claim(client, token, account.email, "not-the-password")
    assert wrong.status_code == 401 and wrong.json()["error"]["code"] == "INVALID_CREDENTIALS"
    db_session.refresh(itinerary)
    assert itinerary.user_id != account.id
    assert claim(client, token, account.email, PASSWORD).status_code == 200


def test_an_itinerary_that_belongs_to_a_real_user_cannot_be_claimed(client, db_session, mailbox):
    owner = person(db_session)
    itinerary, token = itinerary_for(db_session, owner)
    attacker = claim(client, token, "attacker@example.test")
    assert attacker.status_code == 409 and attacker.json()["error"]["code"] == "TICKET_ALREADY_CLAIMED"
    db_session.refresh(itinerary)
    assert itinerary.user_id == owner.id
    assert db_session.scalar(select(User).where(User.email == "attacker@example.test")) is None


def test_the_public_share_token_is_not_a_credential(client, db_session, mailbox):
    _, itinerary, _ = shadow_owned(db_session)
    forged = claim(client, itinerary.share_token, "thief@example.test")
    assert forged.status_code in (400, 422)
    db_session.refresh(itinerary)
    assert db_session.scalar(select(User).where(User.email == "thief@example.test")) is None
    legacy = client.post("/api/auth/claim-ticket", json={"share_token": itinerary.share_token, "email": "thief@example.test", "password": NEW_PASSWORD})
    assert legacy.status_code == 422                                                         # the old request shape is gone


def test_staff_accounts_cannot_claim_tickets(client, db_session, mailbox):
    _, itinerary, token = shadow_owned(db_session)
    admin = person(db_session, role="admin", password=PASSWORD)
    response = claim(client, token, admin.email, PASSWORD)
    assert response.status_code == 403 and response.json()["error"]["code"] == "CLAIM_ROLE_FORBIDDEN"
    db_session.refresh(itinerary)
    assert itinerary.user_id != admin.id
    assert claim(client, token, "fine@example.test").status_code == 200                       # the token was not consumed


def test_expired_claim_tokens_are_rejected(client, db_session, mailbox):
    _, _, token = shadow_owned(db_session)
    db_session.execute(update(ItineraryClaimToken).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    db_session.commit()
    expired = claim(client, token, "late@example.test")
    assert expired.status_code == 400 and expired.json()["error"]["code"] == "TOKEN_INVALID"


def test_claiming_enforces_the_password_policy_for_new_accounts_without_spending_the_token(client, db_session, mailbox):
    _, _, token = shadow_owned(db_session)
    weak = claim(client, token, "weak@example.test", "password1234")
    assert weak.status_code == 422 and weak.json()["error"]["code"] == "WEAK_PASSWORD"
    assert claim(client, token, "weak@example.test", NEW_PASSWORD).status_code == 200


def test_reserved_addresses_cannot_be_used_to_claim(client, db_session, mailbox):
    _, _, token = shadow_owned(db_session)
    response = claim(client, token, "zalo_999@localexplorer.site")
    assert response.status_code == 422 and response.json()["error"]["code"] == "EMAIL_RESERVED"


def test_an_unowned_itinerary_can_be_claimed(client, db_session, mailbox):
    itinerary, token = itinerary_for(db_session, None)
    assert claim(client, token, "owner@example.test").status_code == 200
    db_session.refresh(itinerary)
    assert itinerary.user_id is not None


def test_claim_tokens_are_stored_only_as_hashes(db_session):
    shadow, itinerary, token = shadow_owned(db_session)
    row = db_session.scalars(select(ItineraryClaimToken)).one()
    assert token not in row.token_hash and len(row.token_hash) == 64


def test_new_endpoints_are_not_reachable_with_the_old_admin_key(client):
    assert client.get("/api/auth/sessions", headers={"X-Admin-Key": "test-admin-key"}).status_code == 401
