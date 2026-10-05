"""Two-factor authentication: enrolment, verification (authenticator code or recovery code), lockout, disable.

Every state change that must happen exactly once (accepting a TOTP step, spending a recovery code) is an atomic
``UPDATE ... WHERE`` so two simultaneous requests cannot both succeed. Failed attempts are counted from ``auth_events``
(the database), so the limit holds across workers and does not depend on Redis.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.auth import totp
from app.models.auth_entities import AuthEvent, MFARecoveryCode, UserMFA
from app.core.config import settings
from app.models.entities import User
from app.services.auth_runtime import invalidate_user_state
from app.services.integration_config import IntegrationSecretConfigurationError, decrypt_text, encrypt_text
from app.services.session_service import bump_token_version, record_event

ISSUER = "Local Explorer AI"
MAX_FAILURES = 5
LOCK_WINDOW = timedelta(minutes=15)


class MfaError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code, self.message, self.status_code = code, message, status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row(db: Session, user: User) -> UserMFA | None:
    return db.get(UserMFA, user.id)


def _secret(row: UserMFA) -> str:
    try:
        return decrypt_text(row.secret_encrypted)
    except IntegrationSecretConfigurationError as error:
        raise MfaError("MFA_NOT_CONFIGURED", "Two-factor authentication needs INTEGRATION_SECRETS_KEY to be configured.", 503) from error
    except Exception as error:  # a wrong master key makes the stored seed unreadable
        raise MfaError("MFA_SECRET_UNREADABLE", "The stored two-factor secret cannot be read; check the master key.", 503) from error


def remaining_recovery_codes(db: Session, user: User) -> int:
    return db.scalar(select(func.count(MFARecoveryCode.id)).where(MFARecoveryCode.user_id == user.id, MFARecoveryCode.used_at.is_(None))) or 0


def status(db: Session, user: User) -> dict:
    row = _row(db, user)
    return {"enabled": bool(user.mfa_enabled), "required": user.role == "admin" and bool(settings.admin_mfa_required), "setup_pending": bool(row and row.confirmed_at is None),
            "recovery_codes_remaining": remaining_recovery_codes(db, user) if user.mfa_enabled else 0}


def failures_in_window(db: Session, user: User) -> int:
    since = _now() - LOCK_WINDOW
    return db.scalar(select(func.count(AuthEvent.id)).where(AuthEvent.user_id == user.id, AuthEvent.event_type == "mfa_verify",
                                                           AuthEvent.outcome == "failure", AuthEvent.created_at > since)) or 0


def ensure_not_locked(db: Session, user: User) -> None:
    if failures_in_window(db, user) >= MAX_FAILURES:
        raise MfaError("MFA_LOCKED", "Too many incorrect codes. Try again in 15 minutes.", 429)


def begin_setup(db: Session, user: User) -> dict:
    if user.mfa_enabled:
        raise MfaError("MFA_ALREADY_ENABLED", "Two-factor authentication is already enabled.", 409)
    secret = totp.new_secret()
    try:
        encrypted = encrypt_text(secret)
    except IntegrationSecretConfigurationError as error:
        raise MfaError("MFA_NOT_CONFIGURED", "Two-factor authentication needs INTEGRATION_SECRETS_KEY to be configured.", 503) from error
    row = _row(db, user)
    if row is None:
        db.add(UserMFA(user_id=user.id, secret_encrypted=encrypted))
    else:  # restarting setup replaces any earlier unconfirmed seed
        row.secret_encrypted, row.confirmed_at, row.last_used_step = encrypted, None, None
    db.commit()
    uri = totp.provisioning_uri(secret, user.email, ISSUER)
    return {"secret": secret, "otpauth_uri": uri, "qr": totp.qr_data_uri(uri)}


def check_code(db: Session, user: User, code: str, *, pending: bool = False, ip: str | None = None, user_agent: str | None = None) -> str | None:
    """Verify an authenticator code or a recovery code. Returns ``"totp"``/``"recovery"`` or ``None``; commits either way."""
    ensure_not_locked(db, user)
    row = _row(db, user)
    method = None
    if row is not None and (row.confirmed_at is not None or pending):
        if totp.is_totp_shaped(code):
            match = totp.verify(_secret(row), code, last_used_step=row.last_used_step)
            if match is not None:
                won = db.execute(update(UserMFA).where(UserMFA.user_id == user.id, or_(UserMFA.last_used_step.is_(None), UserMFA.last_used_step < match.step))
                                 .values(last_used_step=match.step))
                method = "totp" if won.rowcount == 1 else None
        elif not pending:
            candidate = db.scalar(select(MFARecoveryCode.id).where(MFARecoveryCode.user_id == user.id, MFARecoveryCode.used_at.is_(None),
                                                                   MFARecoveryCode.code_hash == totp.hash_recovery_code(code)))
            if candidate is not None:
                spent = db.execute(update(MFARecoveryCode).where(MFARecoveryCode.id == candidate, MFARecoveryCode.used_at.is_(None)).values(used_at=_now()))
                method = "recovery" if spent.rowcount == 1 else None
    record_event(db, "mfa_verify", outcome="success" if method else "failure", user_id=user.id, ip=ip, user_agent=user_agent, detail={"method": method})
    db.commit()
    return method


def _replace_recovery_codes(db: Session, user: User) -> list[str]:
    codes = totp.new_recovery_codes()
    db.execute(delete(MFARecoveryCode).where(MFARecoveryCode.user_id == user.id))
    db.add_all(MFARecoveryCode(user_id=user.id, code_hash=totp.hash_recovery_code(code)) for code in codes)
    return codes


def enable(db: Session, user: User, code: str, *, ip: str | None = None, user_agent: str | None = None) -> list[str]:
    row = _row(db, user)
    if user.mfa_enabled or row is None or row.confirmed_at is not None:
        raise MfaError("MFA_SETUP_REQUIRED", "Start setup first, then confirm with a code from your authenticator app.", 409)
    if check_code(db, user, code, pending=True, ip=ip, user_agent=user_agent) != "totp":
        raise MfaError("MFA_CODE_INVALID", "That code is not correct.", 401)
    row = _row(db, user)
    row.confirmed_at = _now()
    user.mfa_enabled = True
    codes = _replace_recovery_codes(db, user)
    record_event(db, "mfa_enabled", user_id=user.id, ip=ip, user_agent=user_agent)
    bump_token_version(db, user, reason="mfa_enabled")  # earlier sessions never passed a second factor
    db.commit()
    invalidate_user_state(user.id)
    return codes


def regenerate_recovery_codes(db: Session, user: User, code: str, *, ip: str | None = None, user_agent: str | None = None) -> list[str]:
    if not user.mfa_enabled:
        raise MfaError("MFA_NOT_ENABLED", "Two-factor authentication is not enabled.", 409)
    if check_code(db, user, code, ip=ip, user_agent=user_agent) is None:
        raise MfaError("MFA_CODE_INVALID", "That code is not correct.", 401)
    codes = _replace_recovery_codes(db, user)
    record_event(db, "mfa_recovery_codes_regenerated", user_id=user.id, ip=ip, user_agent=user_agent)
    db.commit()
    return codes


def disable(db: Session, user: User, code: str, *, ip: str | None = None, user_agent: str | None = None) -> None:
    """The caller has already checked the password."""
    if user.role == "admin" and settings.admin_mfa_required:
        raise MfaError("MFA_REQUIRED_FOR_ROLE", "Administrators must keep two-factor authentication enabled.", 403)
    if not user.mfa_enabled:
        raise MfaError("MFA_NOT_ENABLED", "Two-factor authentication is not enabled.", 409)
    if check_code(db, user, code, ip=ip, user_agent=user_agent) is None:
        raise MfaError("MFA_CODE_INVALID", "That code is not correct.", 401)
    db.execute(delete(MFARecoveryCode).where(MFARecoveryCode.user_id == user.id))
    db.execute(delete(UserMFA).where(UserMFA.user_id == user.id))
    user.mfa_enabled = False
    record_event(db, "mfa_disabled", user_id=user.id, ip=ip, user_agent=user_agent)
    bump_token_version(db, user, reason="mfa_disabled")
    db.commit()
    invalidate_user_state(user.id)
