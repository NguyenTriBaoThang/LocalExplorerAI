# ruff: noqa: F401  (this module only re-exports the package API)
"""Authentication and authorization toolkit.

The core modules here do not import FastAPI or the application's models; the FastAPI adapter and the database
repositories are added in later phases (see docs/auth-design.md).
"""

from .authorizer import Authorizer, PolicyRegistry
from .config import AuthConfig, parse_public_keys
from .errors import (
    AccountDisabled, AuthError, AuthNotConfigured, AuthRequired, Forbidden, MfaRequired, PolicyMissing,
    TokenExpired, TokenInvalid, TokenRevoked, WeakPassword,
)
from .keys import KeyRing, generate_rsa_keypair
from .passwords import VerifyResult, hash_password, validate_password_policy, verify_password
from .permissions import CachedRoleMatrix, PermissionRegistry, RoleMatrix, StaticRoleMatrix
from .principal import Principal, PrincipalKind
from .refresh import (
    LifetimePolicy, RefreshOutcome, RefreshToken, SessionLifetime, StoredSession, decide_refresh,
    hash_refresh_token, needs_refresh, new_refresh_token,
)
from .service_accounts import GeneratedKey, generate_service_key, parse_service_key, verify_secret
from .tokens import AccessClaims, TokenService
from . import totp
from .versions import InMemoryStateStore, RedisStateStore, TokenVersionChecker, UserState

__all__ = [name for name in dir() if not name.startswith("_")]
