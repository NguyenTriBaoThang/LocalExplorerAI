import secrets

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.llm.provider import NotConfiguredLLMProvider, OpenAICompatibleLLMProvider, StructuredOutputProvider
from app.core.config import settings
from app.db.session import get_db
from app.services.planner_service import PlannerService
from app.services.auth_service import AuthNotConfigured, decode_session_token
from app.models.entities import User
from app.services.integration_config import IntegrationSecretConfigurationError, resolve_integration_value


def get_planner_service(db: Session = Depends(get_db)) -> PlannerService:
    return PlannerService(db)


def get_llm_provider(db: Session = Depends(get_db)) -> StructuredOutputProvider:
    try:
        selected = (resolve_integration_value(db, "ai", "provider") or "openai").strip().lower()
    except IntegrationSecretConfigurationError:
        return NotConfiguredLLMProvider()
    if selected == "gemini":
        key_name, base_name, model_name = "gemini_api_key", "gemini_base_url", "gemini_model"
    elif selected == "openai":
        key_name, base_name, model_name = "openai_api_key", "openai_base_url", "openai_model"
    else:
        return NotConfiguredLLMProvider()
    try:
        api_key = resolve_integration_value(db, "ai", key_name)
        base_url = resolve_integration_value(db, "ai", base_name)
        model = resolve_integration_value(db, "ai", model_name)
    except IntegrationSecretConfigurationError:
        return NotConfiguredLLMProvider()
    if not api_key or not base_url or not model:
        return NotConfiguredLLMProvider()
    return OpenAICompatibleLLMProvider(
        api_key=api_key.strip(),
        model_name=model.strip(),
        base_url=base_url.strip(),
        timeout_seconds=settings.openai_timeout_seconds,
    )


def require_admin(
    request: Request,
    db: Session = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
) -> None:
    if settings.admin_api_key and x_admin_key and secrets.compare_digest(x_admin_key, settings.admin_api_key):
        return
    if x_admin_key and settings.admin_api_key and not secrets.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(status_code=401, detail={"code": "ADMIN_UNAUTHORIZED", "message": "The admin key is invalid."})
    authorization = request.headers.get("Authorization", "")
    token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else request.cookies.get("le_session")
    if not token:
        status = 503 if not settings.admin_api_key and not settings.auth_secret and settings.app_env.lower() not in {"development", "test"} else 401
        code = "ADMIN_AUTH_NOT_CONFIGURED" if status == 503 else "ADMIN_UNAUTHORIZED"
        message = "Configure AUTH_SECRET or ADMIN_API_KEY." if status == 503 else "Sign in with an administrator account."
        raise HTTPException(status_code=status, detail={"code": code, "message": message})
    try:
        user_id = decode_session_token(token)
    except AuthNotConfigured as error:
        raise HTTPException(status_code=503, detail={"code": "AUTH_NOT_CONFIGURED", "message": str(error)}) from error
    except ValueError as error:
        raise HTTPException(status_code=401, detail={"code": "INVALID_SESSION", "message": "Your session is invalid or expired."}) from error
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active or user.role != "admin":
        raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN", "message": "Administrator access is required."})


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    authorization = request.headers.get("Authorization", "")
    token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else request.cookies.get("le_session")
    if not token:
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "Sign in to continue."})
    try:
        user_id = decode_session_token(token)
    except AuthNotConfigured as error:
        raise HTTPException(status_code=503, detail={"code": "AUTH_NOT_CONFIGURED", "message": str(error)}) from error
    except ValueError as error:
        raise HTTPException(status_code=401, detail={"code": "INVALID_SESSION", "message": "Your session is invalid or expired."}) from error
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"code": "ACCOUNT_DISABLED", "message": "This account is unavailable."})
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    authorization = request.headers.get("Authorization", "")
    token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else request.cookies.get("le_session")
    if not token:
        return None
    try:
        user_id = decode_session_token(token)
    except AuthNotConfigured as error:
        raise HTTPException(status_code=503, detail={"code": "AUTH_NOT_CONFIGURED", "message": str(error)}) from error
    except ValueError as error:
        raise HTTPException(status_code=401, detail={"code": "INVALID_SESSION", "message": "Your session is invalid or expired."}) from error
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"code": "ACCOUNT_DISABLED", "message": "This account is unavailable."})
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN", "message": "This account does not have permission for this action."})
        return user
    return dependency
