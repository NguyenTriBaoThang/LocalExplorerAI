"""Cookie names and flags for the access/refresh tokens.

Over HTTPS (or in any non-development environment) the cookies use the ``__Host-`` / ``__Secure-`` prefixes, which
the browser only accepts when ``Secure`` is set. Plain-HTTP development uses the unprefixed names.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import Request, Response

from app.core.config import settings

ACCESS_NAMES = ("__Host-le_at", "le_at")
REFRESH_NAMES = ("__Secure-le_rt", "le_rt")
REFRESH_PATH = "/api"


def is_secure(request: Request) -> bool:
    return request.url.scheme == "https" or settings.app_env.lower() not in {"development", "test"}


def _names(secure: bool) -> tuple[str, str]:
    return (ACCESS_NAMES[0], REFRESH_NAMES[0]) if secure else (ACCESS_NAMES[1], REFRESH_NAMES[1])


def read_cookie(request: Request, names: tuple[str, ...]) -> str | None:
    """Read the cookie for this transport only. Where the prefixed name is in force the bare name is ignored, otherwise a
    cookie planted by a sibling subdomain or over plain HTTP could stand in for the protected one."""
    return request.cookies.get(names[0] if is_secure(request) else names[1]) or None


def set_auth_cookies(response: Response, request: Request, issued) -> None:
    secure = is_secure(request)
    access_name, refresh_name = _names(secure)
    common = {"httponly": True, "secure": secure, "samesite": "lax"}
    response.set_cookie(access_name, issued.access_token, max_age=max(1, int(issued.access_expires_at - time.time())), path="/", **common)
    if issued.refresh_token and issued.refresh_expires_at:
        seconds = int((issued.refresh_expires_at - datetime.now(timezone.utc)).total_seconds())
        response.set_cookie(refresh_name, issued.refresh_token, max_age=max(1, seconds), path=REFRESH_PATH, **common)


def clear_auth_cookies(response: Response, request: Request) -> None:
    secure = is_secure(request)
    common = {"httponly": True, "secure": secure, "samesite": "lax"}
    access_name, refresh_name = _names(secure)
    response.delete_cookie(access_name, path="/", **common)
    response.delete_cookie(refresh_name, path=REFRESH_PATH, **common)
