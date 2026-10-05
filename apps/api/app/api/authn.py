"""Request authentication: verify the access token, transparently refresh it, and check revocation."""

from __future__ import annotations

import time

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.api.auth_cookies import ACCESS_NAMES, REFRESH_NAMES, read_cookie, set_auth_cookies
from app.auth import AccountDisabled, AuthError, AuthRequired, TokenExpired, TokenInvalid, needs_refresh
from app.core.client_ip import client_ip
from app.core.config import settings
from app.models.entities import User
from app.services.auth_runtime import auth_config, token_service, version_checker
from app.services.session_service import rotate_session

_CACHE_ATTR = "_auth_result"


def _bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    return header[7:].strip() if header[:7].lower() == "bearer " and header[7:].strip() else None


def has_credentials(request: Request) -> bool:
    return bool(_bearer(request) or read_cookie(request, ACCESS_NAMES) or read_cookie(request, REFRESH_NAMES))


def authenticate(request: Request, response: Response, db: Session, *, required: bool = True) -> User | None:
    """Return the signed-in user, or ``None`` when ``required`` is false and nobody is signed in.

    When the access token is expired (or about to expire) and a refresh cookie is present, the pair is rotated and
    fresh cookies are set on ``response``, so the browser never has to call a refresh endpoint explicitly.
    """
    cached = getattr(request.state, _CACHE_ATTR, None)
    if cached is not None:
        return cached
    service = token_service()  # AuthNotConfigured -> 503
    bearer = _bearer(request)
    access = bearer or read_cookie(request, ACCESS_NAMES)
    refresh_raw = None if bearer else read_cookie(request, REFRESH_NAMES)
    ip, agent = client_ip(request, settings.trusted_proxy_ips), request.headers.get("user-agent")

    claims, issued, failure = None, None, None
    if access:
        try:
            claims = service.verify_access(access)
        except (TokenExpired, TokenInvalid) as error:
            failure = error
    if claims is None and refresh_raw:
        issued = rotate_session(db, refresh_raw, ip=ip, user_agent=agent)
        claims = service.verify_access(issued.access_token)
    elif claims is not None and refresh_raw and needs_refresh(claims.exp, int(time.time()), auth_config().refresh_threshold_seconds):
        try:
            issued = rotate_session(db, refresh_raw, ip=ip, user_agent=agent)
        except AuthError:
            issued = None  # the current access token is still valid; let it run its course

    if claims is None:
        if failure is not None:
            raise failure
        if required:
            raise AuthRequired()
        return None

    version_checker(db).check(claims)
    user = db.get(User, claims.sub)
    if user is None or not user.is_active:
        raise AccountDisabled()
    if issued is not None:
        set_auth_cookies(response, request, issued)
    setattr(request.state, _CACHE_ATTR, user)
    return user
