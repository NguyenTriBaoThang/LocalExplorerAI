"""Plain configuration for the auth package (kept free of the application's Settings class)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .errors import AuthNotConfigured
from .keys import KeyRing
from .refresh import LifetimePolicy
from .tokens import TokenService


@dataclass(frozen=True)
class AuthConfig:
    issuer: str = "local-explorer-ai"
    audience: str = "local-explorer-api"
    key_id: str | None = None
    private_key_b64: str | None = None
    public_keys_b64: dict[str, str] = field(default_factory=dict)
    access_ttl_seconds: int = 900
    refresh_threshold_seconds: int = 180
    lifetime: LifetimePolicy = field(default_factory=LifetimePolicy)

    def build_keyring(self) -> KeyRing:
        return KeyRing.from_b64(active_kid=self.key_id, private_key_b64=self.private_key_b64, public_keys_b64=self.public_keys_b64)

    def build_token_service(self) -> TokenService:
        return TokenService(self.build_keyring(), issuer=self.issuer, audience=self.audience, access_ttl_seconds=self.access_ttl_seconds)


def parse_public_keys(value: str | None) -> dict[str, str]:
    """Parse ``{"kid": "<base64 pem>", ...}`` (JSON) from an environment variable."""
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError as error:
        raise AuthNotConfigured("AUTH_JWT_PUBLIC_KEYS_B64 must be a JSON object of kid -> base64 PEM.") from error
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        raise AuthNotConfigured("AUTH_JWT_PUBLIC_KEYS_B64 must be a JSON object of kid -> base64 PEM.")
    return data
