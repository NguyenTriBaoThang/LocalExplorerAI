"""Shared test helpers."""

from app.services.auth_runtime import token_service


def sign_in(client, user, *, amr=("pwd",)) -> str:
    """Authenticate ``client`` as ``user`` by setting a valid access-token cookie (no refresh cookie)."""
    token, _ = token_service().issue_access(
        user_id=user.id, session_id="test-session", role=user.role, provider_id=user.provider_id,
        token_version=user.token_version or 0, amr=amr,
    )
    client.cookies.set("le_at", token)
    return token


def bearer_for(user, *, amr=("pwd",)) -> dict:
    """Authorization header for one request, leaving the client's cookies untouched."""
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
