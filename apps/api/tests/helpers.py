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
