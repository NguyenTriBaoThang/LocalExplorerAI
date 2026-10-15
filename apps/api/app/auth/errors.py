"""Errors raised by the auth package.

``code`` values match the ones the web client already understands (INVALID_SESSION, ROLE_FORBIDDEN, ...),
so replacing the old helpers does not change the HTTP contract.
"""

from __future__ import annotations


class AuthError(Exception):
    status_code = 401
    code = "AUTH_REQUIRED"
    default_message = "Sign in to continue."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)

    def to_detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class AuthRequired(AuthError):
    pass


class AuthNotConfigured(AuthError):
    status_code = 503
    code = "AUTH_NOT_CONFIGURED"
    default_message = "Authentication is not configured."


class TokenInvalid(AuthError):
    code = "INVALID_SESSION"
    default_message = "Your session is invalid or expired."


class TokenExpired(TokenInvalid):
    pass


class TokenRevoked(TokenInvalid):
    pass


class AccountDisabled(AuthError):
    code = "ACCOUNT_DISABLED"
    default_message = "This account is unavailable."


class Forbidden(AuthError):
    status_code = 403
    code = "ROLE_FORBIDDEN"
    default_message = "This account does not have permission for this action."


class MfaRequired(Forbidden):
    """An administrator session that has not passed a second factor may only enrol one."""

    code = "MFA_REQUIRED"
    default_message = "Two-factor authentication is required for administrators."


class PolicyMissing(Forbidden):
    """A resource-level check was requested but no policy is registered: fail closed."""

    code = "POLICY_MISSING"
    default_message = "No access policy is defined for this action."


class WeakPassword(AuthError):
    status_code = 422
    code = "WEAK_PASSWORD"
    default_message = "The password does not meet the password policy."

    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))
