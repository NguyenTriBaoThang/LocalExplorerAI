import base64
import hashlib
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import settings
from app.models.auth_entities import AuthSession
from app.models.entities import AuditLog, Itinerary, Provider, User
from app.schemas.partner import PartnerApplicationUpdate, PartnerRegisterRequest, apply_application_fields
from app.schemas.auth import (
    ClaimTicketRequest, ForgotPasswordRequest, LoginRequest, MfaChallenge, MfaLoginRequest, PasswordChangeRequest, ProfileUpdateRequest,
    RegisterRequest, ResetPasswordRequest, SessionRead, UserRead, VerifyEmailRequest,
)
from app.api.auth_cookies import REFRESH_NAMES, clear_auth_cookies, read_cookie, set_auth_cookies
from app.api.authn import current_session_id
from app.auth import WeakPassword, hash_password, validate_password_policy, verify_password as _verify_password
from app.core.client_ip import client_ip
from app.services import account_tokens, login_throttle, mfa_service
from app.services.account_tokens import InvalidAccountToken
from app.services.auth_runtime import invalidate_user_state
from app.services.notifications import queue_account_link
from app.services.session_service import (
    bump_token_version, record_event, revoke_all_sessions, revoke_by_refresh_token, revoke_family, rotate_session, start_session,
)
from app.services.ticket_service import is_shadow_email
from app.services.integration_config import IntegrationSecretConfigurationError, resolve_integration_value
from app.api.guards import public, require_user
from app.api.permissions import P

router = APIRouter(prefix="/api/auth", tags=["authentication"])
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


def verify_password(password: str, encoded: str | None) -> bool:
    return _verify_password(password, encoded).valid


def _ip(request: Request) -> str | None:
    return client_ip(request, settings.trusted_proxy_ips)


def _reject_reserved_email(email: str) -> None:
    if is_shadow_email(email):
        raise HTTPException(status_code=422, detail={"code": "EMAIL_RESERVED", "message": "This email address cannot be used."})


def _send_verification(db: Session, user: User) -> bool:
    row, raw = account_tokens.issue(db, user, account_tokens.VERIFY_EMAIL)
    return queue_account_link(db, user, purpose=account_tokens.VERIFY_EMAIL, token_id=row.id, raw_token=raw)


def _invalid_token() -> HTTPException:
    return HTTPException(status_code=400, detail={"code": "TOKEN_INVALID", "message": "This link is invalid, expired or has already been used."})


def _start_session(response: Response, request: Request, db: Session, user: User, amr: tuple[str, ...] = ("pwd",)) -> None:
    issued = start_session(db, user, ip=_ip(request), user_agent=request.headers.get("user-agent"), amr=amr)
    set_auth_cookies(response, request, issued)


def _cookie_flags(request: Request) -> dict:
    return {"httponly": True, "secure": request.url.scheme == "https" or settings.app_env.lower() not in {"development", "test"}, "samesite": "lax"}


def _google_config(db: Session) -> dict[str, str]:
    try:
        return {
            "client_id": (resolve_integration_value(db, "google_oauth", "client_id") or "").strip(),
            "client_secret": (resolve_integration_value(db, "google_oauth", "client_secret") or "").strip(),
            "redirect_uri": (resolve_integration_value(db, "google_oauth", "redirect_uri") or "").strip(),
        }
    except IntegrationSecretConfigurationError:
        return {"client_id": "", "client_secret": "", "redirect_uri": ""}


def _google_configuration_issue(db: Session) -> str | None:
    config = _google_config(db)
    client_id = config["client_id"]
    client_secret = config["client_secret"]
    if not client_id or not client_secret:
        return "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to enable Google sign-in."
    try:
        callback = urlsplit(config["redirect_uri"])
        valid_callback = (
            callback.scheme in {"http", "https"}
            and bool(callback.hostname)
            and callback.username is None
            and callback.password is None
            and callback.path == "/api/auth/google/callback"
            and not callback.query
            and not callback.fragment
        )
    except ValueError:
        valid_callback = False
    if not valid_callback:
        return "GOOGLE_REDIRECT_URI must be an absolute URL ending exactly in /api/auth/google/callback."
    if settings.app_env.lower() not in {"development", "test"} and callback.scheme != "https":
        return "GOOGLE_REDIRECT_URI must use HTTPS outside development and tests."
    return None


@router.post("/register", response_model=UserRead, status_code=201, dependencies=[Depends(public('account creation'))])
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    _reject_reserved_email(email)
    validate_password_policy(payload.password, email=email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail={"code": "EMAIL_IN_USE", "message": "This email is already registered."})
    user = User(email=email, display_name=payload.display_name.strip(), password_hash=hash_password(payload.password), role="traveler")
    db.add(user)
    db.flush()
    _send_verification(db, user)  # browsing and planning work at once; booking waits for the verified email
    db.commit()
    db.refresh(user)
    _start_session(response, request, db, user)
    return user


@router.post("/login", response_model=UserRead | MfaChallenge, dependencies=[Depends(public('credentials are checked in the handler'))])
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    login_throttle.check(db, email, _ip(request))  # before any password work
    user = db.scalar(select(User).where(User.email == email))
    check = _verify_password(payload.password, user.password_hash if user else None)  # hashes anyway when the user is unknown
    if user is None or not user.is_active or not check.valid:
        record_event(db, "login", outcome="failure", user_id=user.id if user else None, ip=_ip(request),
                     user_agent=request.headers.get("user-agent"), detail=login_throttle.failure_detail(email))
        db.commit()
        raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS", "message": "Email or password is incorrect."})
    if check.needs_rehash:
        user.password_hash = hash_password(payload.password)
        db.commit()
    if user.mfa_enabled:
        # Password is right but no session yet: hand out a short-lived, single-use ticket for the code step.
        row, ticket = account_tokens.issue(db, user, account_tokens.MFA_LOGIN)
        record_event(db, "mfa_challenge", user_id=user.id, ip=_ip(request), user_agent=request.headers.get("user-agent"))
        db.commit()
        return MfaChallenge(mfa_ticket=ticket, expires_in=account_tokens.TTL_SECONDS[account_tokens.MFA_LOGIN])
    _start_session(response, request, db, user)
    return user


@router.post("/login/mfa", response_model=UserRead, dependencies=[Depends(public('authenticated by the single-use MFA ticket plus a one-time code'))])
def login_mfa(payload: MfaLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        ticket, user = account_tokens.peek(db, payload.mfa_ticket, account_tokens.MFA_LOGIN)
    except InvalidAccountToken:
        raise _invalid_token()
    try:
        method = mfa_service.check_code(db, user, payload.code, ip=_ip(request), user_agent=request.headers.get("user-agent"))
    except mfa_service.MfaError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message})
    if method is None:
        raise HTTPException(status_code=401, detail={"code": "MFA_CODE_INVALID", "message": "That code is not correct."})
    try:
        account_tokens.spend(db, ticket)  # a ticket opens exactly one session
    except InvalidAccountToken:
        db.rollback()
        raise _invalid_token()
    db.commit()
    _start_session(response, request, db, user, amr=("pwd", "otp"))
    return user


@router.post("/refresh", response_model=UserRead, dependencies=[Depends(public('authenticated by the refresh cookie'))])
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = read_cookie(request, REFRESH_NAMES)
    if not token:
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "Sign in to continue."})
    issued = rotate_session(db, token, ip=_ip(request), user_agent=request.headers.get("user-agent"))
    set_auth_cookies(response, request, issued)
    return db.get(User, issued.user_id)


@router.get("/me", response_model=UserRead)
def get_profile(user: User = Depends(require_user(P.ACCOUNT_READ))):
    return user


@router.patch("/me", response_model=UserRead)
def update_profile(payload: ProfileUpdateRequest, user: User = Depends(require_user(P.ACCOUNT_UPDATE)), db: Session = Depends(get_db)):
    user.display_name = payload.display_name.strip()
    user.phone = payload.phone.strip() if payload.phone else None
    db.commit()
    db.refresh(user)
    return user


@router.post("/password")
def change_password(payload: PasswordChangeRequest, request: Request, response: Response, user: User = Depends(require_user(P.ACCOUNT_PASSWORD)), db: Session = Depends(get_db)):
    if user.password_hash and not verify_password(payload.current_password or "", user.password_hash):
        raise HTTPException(status_code=400, detail={"code": "CURRENT_PASSWORD_INVALID", "message": "Current password is incorrect."})
    validate_password_policy(payload.new_password, email=user.email)
    user.password_hash = hash_password(payload.new_password)
    bump_token_version(db, user, reason="password_changed")  # signs every other device out
    record_event(db, "password_changed", user_id=user.id, ip=_ip(request))
    db.commit()
    invalidate_user_state(user.id)
    _start_session(response, request, db, user)  # but keep the device that made the change signed in
    return {"updated": True}


@router.post("/logout", status_code=204, dependencies=[Depends(public('idempotent; revokes the refresh token it is given'))])
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = read_cookie(request, REFRESH_NAMES)
    if token:
        revoke_by_refresh_token(db, token)
    clear_auth_cookies(response, request)


@router.post("/password/forgot", status_code=202, dependencies=[Depends(public('always answers 202 whether or not the account exists'))])
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email)) if payload.email else None
    if user is not None and user.is_active and not is_shadow_email(user.email) and not (settings.admin_mfa_required and user.role == "admin" and not user.mfa_enabled):
        # (An administrator without two-factor authentication gets no link: whoever controlled the inbox could enrol their own
        # authenticator and take the account. Such accounts are recovered by an operator, see scripts/admin_recovery.py.)
        # At most one email a minute per account, so the endpoint cannot be used to flood someone's inbox.
        if not account_tokens.issued_recently(db, user, account_tokens.RESET_PASSWORD):
            row, raw = account_tokens.issue(db, user, account_tokens.RESET_PASSWORD)
            queued = queue_account_link(db, user, purpose=account_tokens.RESET_PASSWORD, token_id=row.id, raw_token=raw)
            record_event(db, "password_reset_requested", user_id=user.id, ip=_ip(request), user_agent=request.headers.get("user-agent"),
                         detail={"email_queued": queued})
            db.commit()
    return {"accepted": True}


@router.post("/password/reset", dependencies=[Depends(public('authenticated by the single-use emailed token'))])
def reset_password(payload: ResetPasswordRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        user = account_tokens.consume(db, payload.token, account_tokens.RESET_PASSWORD)
    except InvalidAccountToken:
        db.rollback()
        raise _invalid_token()
    if settings.admin_mfa_required and user.role == "admin" and not user.mfa_enabled:
        db.rollback()
        raise HTTPException(status_code=403, detail={"code": "ADMIN_RESET_FORBIDDEN", "message": "Administrator passwords cannot be reset by email without two-factor authentication."})
    try:
        validate_password_policy(payload.new_password, email=user.email)
    except WeakPassword:
        db.rollback()  # undo the consumption so the user can retry the same link with a stronger password
        raise
    user.password_hash = hash_password(payload.new_password)
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)  # the link reached the inbox, which proves ownership
    bump_token_version(db, user, reason="password_reset")  # every device signs in again with the new password
    record_event(db, "password_reset", user_id=user.id, ip=_ip(request), user_agent=request.headers.get("user-agent"))
    db.commit()
    invalidate_user_state(user.id)
    clear_auth_cookies(response, request)
    return {"reset": True}


@router.post("/email/verify", dependencies=[Depends(public('authenticated by the single-use emailed token'))])
def verify_email(payload: VerifyEmailRequest, request: Request, db: Session = Depends(get_db)):
    try:
        user = account_tokens.consume(db, payload.token, account_tokens.VERIFY_EMAIL)
    except InvalidAccountToken:
        db.rollback()
        raise _invalid_token()
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
        record_event(db, "email_verified", user_id=user.id, ip=_ip(request))
    db.commit()
    return {"verified": True}


@router.post("/email/verify/resend", status_code=202)
def resend_verification(user: User = Depends(require_user(P.ACCOUNT_UPDATE)), db: Session = Depends(get_db)):
    if user.email_verified_at is not None:
        return {"already_verified": True}
    if account_tokens.issued_recently(db, user, account_tokens.VERIFY_EMAIL):
        raise HTTPException(status_code=429, detail={"code": "VERIFICATION_RECENTLY_SENT", "message": "A verification email was sent recently; try again in a minute."})
    queued = _send_verification(db, user)
    db.commit()
    return {"email_queued": queued}


def _current_family(db: Session, request: Request) -> str | None:
    sid = current_session_id(request)
    row = db.get(AuthSession, sid) if sid else None
    return row.family_id if row else None


@router.get("/sessions", response_model=list[SessionRead])
def list_sessions(request: Request, user: User = Depends(require_user(P.ACCOUNT_SESSIONS)), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    # Each family's head row (not rotated, not revoked, not expired) is one signed-in device.
    heads = db.scalars(select(AuthSession).where(
        AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None), AuthSession.rotated_at.is_(None), AuthSession.expires_at > now,
    ).order_by(AuthSession.last_used_at.desc())).all()
    started = dict(db.execute(select(AuthSession.family_id, func.min(AuthSession.issued_at))
                              .where(AuthSession.family_id.in_([h.family_id for h in heads])).group_by(AuthSession.family_id)).all())
    current = _current_family(db, request)
    return [SessionRead(id=h.family_id, created_at=started.get(h.family_id, h.issued_at), last_used_at=h.last_used_at,
                        expires_at=h.expires_at, absolute_expires_at=h.absolute_expires_at, ip=h.ip, user_agent=h.user_agent,
                        amr=list(h.amr or []), current=h.family_id == current) for h in heads]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: str, request: Request, response: Response, user: User = Depends(require_user(P.ACCOUNT_SESSIONS)),
                   db: Session = Depends(get_db)):
    owned = db.scalar(select(AuthSession.id).where(AuthSession.family_id == session_id, AuthSession.user_id == user.id,
                                                   AuthSession.revoked_at.is_(None)).limit(1))
    if owned is None:  # unknown, already revoked, or someone else's: indistinguishable on purpose
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "Session not found."})
    is_current = session_id == _current_family(db, request)
    revoke_family(db, session_id, "user_revoked")
    record_event(db, "session_revoked", user_id=user.id, ip=_ip(request), detail={"family_id": session_id, "current": is_current})
    db.commit()
    if is_current:
        clear_auth_cookies(response, request)


@router.post("/logout-all", status_code=204)
def logout_all(request: Request, response: Response, user: User = Depends(require_user(P.ACCOUNT_SESSIONS)), db: Session = Depends(get_db)):
    revoke_all_sessions(db, user)  # bumps token_version: every access token of this user stops working at once
    clear_auth_cookies(response, request)


@router.get("/google/start", dependencies=[Depends(public('starts the OAuth flow'))])
def google_start(request: Request, db: Session = Depends(get_db)):
    config = _google_config(db)
    issue = _google_configuration_issue(db)
    if issue:
        raise HTTPException(status_code=503, detail={"code": "GOOGLE_AUTH_NOT_CONFIGURED", "message": issue})
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode("ascii")
    query = urlencode({
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    })
    response = RedirectResponse(f"{GOOGLE_AUTH_ENDPOINT}?{query}", status_code=302)
    flags = _cookie_flags(request)
    response.set_cookie("le_google_state", state, path="/api/auth/google", max_age=600, **flags)
    response.set_cookie("le_google_verifier", verifier, path="/api/auth/google", max_age=600, **flags)
    return response


@router.get("/google/status", dependencies=[Depends(public('reports whether Google sign-in is configured'))])
def google_status(db: Session = Depends(get_db)):
    config = _google_config(db)
    issue = _google_configuration_issue(db)
    return {
        "enabled": issue is None,
        "redirect_uri": config["redirect_uri"],
        "configuration_message": issue,
    }


@router.get("/google/callback", dependencies=[Depends(public('OAuth callback; validated by state and PKCE'))])
def google_callback(request: Request, db: Session = Depends(get_db)):
    config = _google_config(db)
    if _google_configuration_issue(db):
        return RedirectResponse(f"{settings.web_app_url}/login?error=google_not_configured", status_code=303)
    code = request.query_params.get("code")
    returned_state = request.query_params.get("state")
    state_cookie = request.cookies.get("le_google_state")
    verifier = request.cookies.get("le_google_verifier")
    if not code or not returned_state or not state_cookie or not verifier or not secrets.compare_digest(returned_state, state_cookie):
        return RedirectResponse(f"{settings.web_app_url}/login?error=google_login_failed", status_code=303)
    try:
        token_response = httpx.post(GOOGLE_TOKEN_ENDPOINT, data={
            "code": code,
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "redirect_uri": config["redirect_uri"],
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        }, timeout=10.0)
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise ValueError("Google did not return an access token")
        profile_response = httpx.get(GOOGLE_USERINFO_ENDPOINT, headers={"Authorization": f"Bearer {access_token}"}, timeout=10.0)
        profile_response.raise_for_status()
        profile = profile_response.json()
    except (httpx.HTTPError, ValueError):
        return RedirectResponse(f"{settings.web_app_url}/login?error=google_login_failed", status_code=303)
    email = str(profile.get("email", "")).strip().lower()
    google_sub = profile.get("sub")
    if not email or not google_sub or profile.get("email_verified") not in (True, "true"):
        return RedirectResponse(f"{settings.web_app_url}/login?error=google_email_unverified", status_code=303)
    user = db.scalar(select(User).where(User.google_sub == google_sub))
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
        if user is not None and user.role == "admin":
            # Administrators sign in with a password and MFA only; never link a Google identity to them.
            return RedirectResponse(f"{settings.web_app_url}/login?error=admin_requires_password", status_code=303)
        if user is not None and user.google_sub not in (None, google_sub):
            return RedirectResponse(f"{settings.web_app_url}/login?error=google_account_conflict", status_code=303)
        if user is None:
            user = User(email=email, display_name=str(profile.get("name") or email.split("@")[0]), google_sub=google_sub, role="traveler")
            db.add(user)
        else:
            user.google_sub = google_sub
        db.commit()
        db.refresh(user)
    if user.email_verified_at is None and user.email == email:
        user.email_verified_at = datetime.now(timezone.utc)  # Google reported this exact address as verified
        db.commit()
    if not user.is_active:
        return RedirectResponse(f"{settings.web_app_url}/login?error=account_disabled", status_code=303)
    if user.role == "admin":
        return RedirectResponse(f"{settings.web_app_url}/login?error=admin_requires_password", status_code=303)
    response = RedirectResponse(settings.web_app_url, status_code=303)
    _start_session(response, request, db, user, amr=("google",))
    flags = _cookie_flags(request)
    response.delete_cookie("le_google_state", path="/api/auth/google", **flags)
    response.delete_cookie("le_google_verifier", path="/api/auth/google", **flags)
    return response


@router.post("/claim-ticket", response_model=UserRead, dependencies=[Depends(public('authenticated by the single-use claim token from the chat bot'))])
def claim_ticket(payload: ClaimTicketRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Attach a chat-bot ticket itinerary to a real account, signing in to an existing one or creating a new one.

    Only itineraries that nobody owns yet (or that still belong to the bot's placeholder account) can be claimed,
    and an existing account is only ever *signed in to* with its password, never modified.
    """
    try:
        claim = account_tokens.find_claim_token(db, payload.claim_token)
    except InvalidAccountToken:
        raise _invalid_token()
    itinerary = db.scalar(select(Itinerary).where(Itinerary.id == claim.itinerary_id).with_for_update())
    owner = db.get(User, itinerary.user_id) if itinerary is not None and itinerary.user_id else None
    if itinerary is None or (owner is not None and not is_shadow_email(owner.email)):
        raise HTTPException(status_code=409, detail={"code": "TICKET_ALREADY_CLAIMED", "message": "Vé này đã được liên kết với một tài khoản."})

    email = payload.email
    _reject_reserved_email(email)
    login_throttle.check(db, email, _ip(request))  # a claim with an existing address is a password guess too
    account = db.scalar(select(User).where(User.email == email))
    if account is not None:
        check = _verify_password(payload.password, account.password_hash)
        if not account.is_active or not check.valid:
            record_event(db, "login", outcome="failure", user_id=account.id, ip=_ip(request), user_agent=request.headers.get("user-agent"),
                         detail=login_throttle.failure_detail(email, via="claim_ticket"))
            db.commit()
            raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS", "message": "Email or password is incorrect."})
        if account.role != "traveler":
            # Staff accounts sign in through the normal login (admins with MFA) and do not own itineraries.
            raise HTTPException(status_code=403, detail={"code": "CLAIM_ROLE_FORBIDDEN", "message": "Chỉ tài khoản du khách mới có thể nhận vé."})
        if check.needs_rehash:
            account.password_hash = hash_password(payload.password)
    else:
        validate_password_policy(payload.password, email=email)
        display_name = (payload.display_name or "").strip() or email.split("@")[0]
        account = User(email=email, display_name=display_name, password_hash=hash_password(payload.password), role="traveler")
        db.add(account)
        db.flush()
        _send_verification(db, account)

    try:
        account_tokens.consume_claim_token(db, claim, account)
    except InvalidAccountToken:
        db.rollback()
        raise _invalid_token()
    itinerary.user_id = account.id
    record_event(db, "itinerary_claimed", user_id=account.id, ip=_ip(request), detail={"itinerary_id": itinerary.id})
    db.commit()
    db.refresh(account)
    _start_session(response, request, db, account)
    return account


def _open_partner_application(db: Session, user: User, application: PartnerApplicationUpdate) -> Provider:
    """Create the pending provider profile for ``user`` and link the account to it as a provider."""
    slug_base = re.sub(r"[^a-z0-9]+", "-", application.business_name.strip().lower()).strip("-")[:160] or "partner"
    provider = Provider(id=str(uuid4()), slug=f"{slug_base}-{uuid4().hex[:8]}", contact_email=user.email,
                        verification_status="pending", is_active=True, applied_at=datetime.now(timezone.utc))
    apply_application_fields(provider, application)
    db.add(provider)
    db.flush()
    user.role, user.provider_id = "provider", provider.id
    db.add(AuditLog(id=str(uuid4()), actor_id=user.id, action="partner.application_submitted", target_type="provider",
                    target_id=provider.id, details={}, created_at=datetime.now(timezone.utc)))
    return provider


@router.post("/partner/register", response_model=UserRead, status_code=201, dependencies=[Depends(public('partner account creation; the profile stays pending until an administrator approves it'))])
def register_partner(payload: PartnerRegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    _reject_reserved_email(email)
    validate_password_policy(payload.password, email=email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail={"code": "EMAIL_IN_USE", "message": "This email is already registered."})
    user = User(email=email, display_name=payload.display_name.strip(), password_hash=hash_password(payload.password), role="traveler")
    db.add(user)
    db.flush()
    _open_partner_application(db, user, payload.application)
    _send_verification(db, user)
    db.commit()
    db.refresh(user)
    _start_session(response, request, db, user)
    return user


@router.post("/partner/apply", response_model=UserRead, status_code=201)
def apply_as_partner(payload: PartnerApplicationUpdate, request: Request, response: Response,
                     user: User = Depends(require_user(P.ACCOUNT_UPDATE)), db: Session = Depends(get_db)):
    """An existing traveler account applies to become a partner. The role change ends its old sessions, so a new one starts."""
    if user.role != "traveler" or user.provider_id:
        raise HTTPException(status_code=409, detail={"code": "ALREADY_STAFF", "message": "Only traveler accounts can apply to become a partner."})
    _open_partner_application(db, user, payload)
    bump_token_version(db, user, reason="role_or_status_changed")
    db.commit()
    invalidate_user_state(user.id)
    db.refresh(user)
    _start_session(response, request, db, user)
    return user
