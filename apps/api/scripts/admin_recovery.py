"""Operator break-glass for administrator accounts (run on the server; nothing here is reachable over HTTP).

    python -m scripts.admin_recovery set-password --email admin@example.com
    python -m scripts.admin_recovery reset-mfa    --email admin@example.com

Administrators cannot recover their password by email until they have enrolled two-factor authentication, and cannot
turn it off themselves. These two commands cover a lost password (before enrolment) and a lost authenticator plus
recovery codes. Both end every session of the account, and both are written to ``auth_events`` as ``operator_*``.
"""

import argparse
import secrets
import sys

from sqlalchemy import delete, select

from app.auth import hash_password
from app.models.auth_entities import MFARecoveryCode, UserMFA
from app.models.entities import User
from app.services.auth_runtime import invalidate_user_state
from app.services.session_service import bump_token_version, record_event


def _admin(db, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or user.role != "admin":
        raise SystemExit(f"No administrator account with the email {email!r}.")
    return user


def set_password(db, email: str) -> str:
    """Give the account a new random password (printed once) and sign it out everywhere."""
    user = _admin(db, email)
    password = secrets.token_urlsafe(18)
    user.password_hash = hash_password(password)
    bump_token_version(db, user, reason="operator_set_password")
    record_event(db, "operator_set_password", user_id=user.id)
    db.commit()
    invalidate_user_state(user.id)
    return password


def reset_mfa(db, email: str) -> None:
    """Remove two-factor authentication so the administrator can enrol a new authenticator at the next sign-in."""
    user = _admin(db, email)
    db.execute(delete(MFARecoveryCode).where(MFARecoveryCode.user_id == user.id))
    db.execute(delete(UserMFA).where(UserMFA.user_id == user.id))
    user.mfa_enabled = False
    bump_token_version(db, user, reason="operator_reset_mfa")
    record_event(db, "operator_reset_mfa", user_id=user.id)
    db.commit()
    invalidate_user_state(user.id)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["set-password", "reset-mfa"])
    parser.add_argument("--email", required=True)
    args = parser.parse_args(argv)
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        if args.command == "set-password":
            print(f"New password for {args.email}: {set_password(db, args.email)}\nAll sessions were ended. Change it after signing in.")
        else:
            reset_mfa(db, args.email)
            print(f"Two-factor authentication removed for {args.email}. They must enrol again at the next sign-in.")


if __name__ == "__main__":
    sys.exit(main())
