import base64
import hashlib
import secrets
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, get_optional_user
from app.core.config import settings
from app.models.entities import User, Itinerary
from app.schemas.auth import ClaimTicketRequest, LoginRequest, PasswordChangeRequest, ProfileUpdateRequest, RegisterRequest, UserRead
from app.services.auth_service import AuthNotConfigured, create_session_token, hash_password, verify_password
from app.services.integration_config import IntegrationSecretConfigurationError, resolve_integration_value

router = APIRouter(prefix="/api/auth", tags=["authentication"])
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


def _session_cookie(response: Response, user: User, request: Request) -> None:
    try:
        token = create_session_token(user.id)
    except AuthNotConfigured as error:
        raise HTTPException(status_code=503, detail={"code": "AUTH_NOT_CONFIGURED", "message": str(error)}) from error
    response.set_cookie(
        "le_session", token, httponly=True, secure=request.url.scheme == "https" or settings.app_env.lower() not in {"development", "test"},
        samesite="lax", max_age=settings.session_ttl_seconds, path="/",
    )


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


@router.post("/register", response_model=UserRead, status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail={"code": "EMAIL_IN_USE", "message": "This email is already registered."})
    user = User(email=email, display_name=payload.display_name.strip(), password_hash=hash_password(payload.password), role="traveler")
    db.add(user)
    db.commit()
    db.refresh(user)
    _session_cookie(response, user, request)
    return user


@router.post("/login", response_model=UserRead)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS", "message": "Email or password is incorrect."})
    _session_cookie(response, user, request)
    return user


@router.get("/me", response_model=UserRead)
def get_profile(user: User = Depends(get_current_user)):
    return user


@router.get("/session")
def get_session(user: User | None = Depends(get_optional_user)):
    """Bootstrap the UI without treating an anonymous visitor as an API error."""
    return {"user": UserRead.model_validate(user) if user is not None else None}


@router.patch("/me", response_model=UserRead)
def update_profile(payload: ProfileUpdateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.display_name = payload.display_name.strip()
    user.phone = payload.phone.strip() if payload.phone else None
    db.commit()
    db.refresh(user)
    return user


@router.post("/password")
def change_password(payload: PasswordChangeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.password_hash and not verify_password(payload.current_password or "", user.password_hash):
        raise HTTPException(status_code=400, detail={"code": "CURRENT_PASSWORD_INVALID", "message": "Current password is incorrect."})
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"updated": True}


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie("le_session", path="/", httponly=True, samesite="lax")


@router.get("/google/start")
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


@router.get("/google/status")
def google_status(db: Session = Depends(get_db)):
    config = _google_config(db)
    issue = _google_configuration_issue(db)
    return {
        "enabled": issue is None,
        "redirect_uri": config["redirect_uri"],
        "configuration_message": issue,
    }


@router.get("/google/callback")
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
        if user is not None and user.google_sub not in (None, google_sub):
            return RedirectResponse(f"{settings.web_app_url}/login?error=google_account_conflict", status_code=303)
        if user is None:
            user = User(email=email, display_name=str(profile.get("name") or email.split("@")[0]), google_sub=google_sub, role="traveler")
            db.add(user)
        else:
            user.google_sub = google_sub
        db.commit()
        db.refresh(user)
    if not user.is_active:
        return RedirectResponse(f"{settings.web_app_url}/login?error=account_disabled", status_code=303)
    response = RedirectResponse(settings.web_app_url, status_code=303)
    _session_cookie(response, user, request)
    flags = _cookie_flags(request)
    response.delete_cookie("le_google_state", path="/api/auth/google", **flags)
    response.delete_cookie("le_google_verifier", path="/api/auth/google", **flags)
    return response


@router.post("/claim-ticket", response_model=UserRead)
def claim_ticket(payload: ClaimTicketRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    itinerary = db.scalar(select(Itinerary).where(Itinerary.share_token == payload.share_token))
    if itinerary is None:
        raise HTTPException(status_code=404, detail={"code": "TICKET_NOT_FOUND", "message": "Không tìm thấy chuyến đi tương ứng với vé này."})

    target_email = str(payload.email).strip().lower()
    existing_user = db.scalar(select(User).where(User.email == target_email))

    if existing_user is not None:
        if not verify_password(payload.password, existing_user.password_hash):
            raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS", "message": "Mật khẩu tài khoản không chính xác."})
        itinerary.user_id = existing_user.id
        db.commit()
        db.refresh(existing_user)
        _session_cookie(response, existing_user, request)
        return existing_user

    shadow_user = db.scalar(select(User).where(User.id == itinerary.user_id)) if itinerary.user_id else None
    if shadow_user is not None and shadow_user.email.startswith("zalo_"):
        shadow_user.email = target_email
        if payload.display_name:
            shadow_user.display_name = payload.display_name.strip()
        shadow_user.password_hash = hash_password(payload.password)
        db.commit()
        db.refresh(shadow_user)
        _session_cookie(response, shadow_user, request)
        return shadow_user

    new_user = User(
        email=target_email,
        display_name=payload.display_name.strip() if payload.display_name else target_email.split("@")[0],
        password_hash=hash_password(payload.password),
        role="traveler"
    )
    db.add(new_user)
    db.flush()
    itinerary.user_id = new_user.id
    db.commit()
    db.refresh(new_user)
    _session_cookie(response, new_user, request)
    return new_user
