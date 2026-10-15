"""Two-factor authentication management (TOTP authenticator app plus single-use recovery codes)."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.auth_cookies import set_auth_cookies
from app.api.guards import require_user
from app.api.permissions import P
from app.auth import verify_password
from app.core.client_ip import client_ip
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import User
from app.schemas.auth import MfaCodeRequest, MfaDisableRequest
from app.services import mfa_service
from app.services.session_service import start_session

router = APIRouter(prefix="/api/auth/mfa", tags=["two-factor authentication"])


def _http(error: mfa_service.MfaError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message})


def _context(request: Request) -> dict:
    return {"ip": client_ip(request, settings.trusted_proxy_ips), "user_agent": request.headers.get("user-agent")}


@router.get("")
def mfa_status(user: User = Depends(require_user(P.ACCOUNT_MFA)), db: Session = Depends(get_db)):
    return mfa_service.status(db, user)


@router.post("/setup")
def mfa_setup(user: User = Depends(require_user(P.ACCOUNT_MFA)), db: Session = Depends(get_db)):
    """Start enrolment: returns the seed (shown once), the otpauth link and a QR code. Nothing is enforced until confirmed."""
    try:
        return mfa_service.begin_setup(db, user)
    except mfa_service.MfaError as error:
        raise _http(error) from error


@router.post("/enable")
def mfa_enable(payload: MfaCodeRequest, request: Request, response: Response, user: User = Depends(require_user(P.ACCOUNT_MFA)),
               db: Session = Depends(get_db)):
    """Confirm enrolment with a code. Returns the recovery codes **once**; other devices are signed out, this one upgraded."""
    try:
        codes = mfa_service.enable(db, user, payload.code, **_context(request))
    except mfa_service.MfaError as error:
        raise _http(error) from error
    issued = start_session(db, user, amr=("pwd", "otp"), **_context(request))
    set_auth_cookies(response, request, issued)
    return {"enabled": True, "recovery_codes": codes}


@router.post("/recovery-codes")
def mfa_regenerate_codes(payload: MfaCodeRequest, request: Request, user: User = Depends(require_user(P.ACCOUNT_MFA)),
                         db: Session = Depends(get_db)):
    """Replace all recovery codes (the old ones stop working). Needs a current code."""
    try:
        return {"recovery_codes": mfa_service.regenerate_recovery_codes(db, user, payload.code, **_context(request))}
    except mfa_service.MfaError as error:
        raise _http(error) from error


@router.post("/disable")
def mfa_disable(payload: MfaDisableRequest, request: Request, response: Response, user: User = Depends(require_user(P.ACCOUNT_MFA)),
                db: Session = Depends(get_db)):
    """Turn two-factor authentication off (not allowed for administrators). Needs the password and a current code."""
    if user.password_hash and not verify_password(payload.password or "", user.password_hash).valid:
        raise HTTPException(status_code=400, detail={"code": "CURRENT_PASSWORD_INVALID", "message": "Current password is incorrect."})
    try:
        mfa_service.disable(db, user, payload.code, **_context(request))
    except mfa_service.MfaError as error:
        raise _http(error) from error
    issued = start_session(db, user, amr=("pwd",), **_context(request))
    set_auth_cookies(response, request, issued)
    return {"enabled": False}
