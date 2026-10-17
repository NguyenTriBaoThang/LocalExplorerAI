"""Shared test helpers."""

from app.services.auth_runtime import token_service


def default_amr(user) -> tuple[str, ...]:
    """Administrators must have passed a second factor, so test sessions for them carry it unless a test says otherwise."""
    return ("pwd", "otp") if user.role == "admin" else ("pwd",)


def sign_in(client, user, *, amr=None) -> str:
    """Authenticate ``client`` as ``user`` by setting a valid access-token cookie (no refresh cookie)."""
    amr = amr if amr is not None else default_amr(user)
    token, _ = token_service().issue_access(
        user_id=user.id, session_id="test-session", role=user.role, provider_id=user.provider_id,
        token_version=user.token_version or 0, amr=amr,
    )
    client.cookies.set("le_at", token)
    return token


def bearer_for(user, *, amr=None) -> dict:
    """Authorization header for one request, leaving the client's cookies untouched."""
    amr = amr if amr is not None else default_amr(user)
    token, _ = token_service().issue_access(
        user_id=user.id, session_id="test-session", role=user.role, provider_id=user.provider_id,
        token_version=user.token_version or 0, amr=amr,
    )
    return {"Authorization": f"Bearer {token}"}


def make_user(db, role: str, **kw):
    """Create and commit a user. Any column (email, password_hash, is_active, ...) can be overridden through ``kw``."""
    from datetime import datetime, timezone
    from uuid import uuid4
    from app.models.entities import User
    fields = {"id": str(uuid4()), "email": f"{role}-{uuid4().hex[:8]}@example.test", "display_name": role.title(), "role": role,
              "email_verified_at": datetime.now(timezone.utc)}  # most tests are about other rules; booking needs it
    fields.update(kw)
    user = User(**fields)
    db.add(user)
    db.commit()
    return user
