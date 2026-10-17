"""Access tokens: short-lived RS256 JWTs."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

import jwt

from .errors import TokenExpired, TokenInvalid
from .keys import KeyRing

_REQUIRED = ["exp", "iat", "nbf", "iss", "aud", "sub", "jti"]


@dataclass(frozen=True)
class AccessClaims:
    sub: str
    sid: str
    role: str
    provider_id: str | None
    ver: int
    amr: tuple[str, ...]
    jti: str
    iat: int
    exp: int


class TokenService:
    def __init__(self, keyring: KeyRing, *, issuer: str, audience: str, access_ttl_seconds: int = 900, leeway_seconds: int = 10):
        self._keys = keyring
        self._issuer = issuer
        self._audience = audience
        self._ttl = access_ttl_seconds
        self._leeway = leeway_seconds

    @property
    def access_ttl_seconds(self) -> int:
        return self._ttl

    def issue_access(self, *, user_id: str, session_id: str, role: str, provider_id: str | None, token_version: int,
                     amr: tuple[str, ...] | list[str] = ("pwd",), ttl_seconds: int | None = None) -> tuple[str, AccessClaims]:
        now = int(time.time())
        claims = AccessClaims(
            sub=user_id, sid=session_id, role=role, provider_id=provider_id, ver=int(token_version), amr=tuple(amr),
            jti=uuid.uuid4().hex, iat=now, exp=now + (self._ttl if ttl_seconds is None else ttl_seconds),
        )
        payload = {
            "iss": self._issuer, "aud": self._audience, "sub": claims.sub, "iat": claims.iat, "nbf": claims.iat, "exp": claims.exp,
            "jti": claims.jti, "sid": claims.sid, "role": claims.role, "provider_id": claims.provider_id, "ver": claims.ver,
            "amr": list(claims.amr),
        }
        token = jwt.encode(payload, self._keys.private_key, algorithm="RS256", headers={"kid": self._keys.active_kid})
        return token, claims

    def verify_access(self, token: str) -> AccessClaims:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise TokenInvalid() from error
        public_key = self._keys.public_for(header.get("kid"))
        if public_key is None:
            raise TokenInvalid()
        try:
            data = jwt.decode(
                token, public_key, algorithms=["RS256"], audience=self._audience, issuer=self._issuer,
                leeway=self._leeway, options={"require": _REQUIRED},
            )
        except jwt.ExpiredSignatureError as error:
            raise TokenExpired() from error
        except jwt.PyJWTError as error:
            raise TokenInvalid() from error
        sub, sid, role = data.get("sub"), data.get("sid"), data.get("role")
        if not all(isinstance(value, str) and value for value in (sub, sid, role)) or not isinstance(data.get("ver"), int):
            raise TokenInvalid()
        return AccessClaims(
            sub=sub, sid=sid, role=role, provider_id=data.get("provider_id"), ver=data["ver"],
            amr=tuple(str(item) for item in data.get("amr", [])), jti=data["jti"], iat=int(data["iat"]), exp=int(data["exp"]),
        )
