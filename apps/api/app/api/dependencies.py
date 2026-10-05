import secrets

from fastapi import Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.adapters.llm.provider import NotConfiguredLLMProvider, OpenAICompatibleLLMProvider, StructuredOutputProvider
from app.core.config import settings
from app.db.session import get_db
from app.services.planner_service import PlannerService
from app.api.authn import authenticate
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
    response: Response,
    db: Session = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
) -> None:
    # Legacy shared key, to be replaced by service accounts (docs/auth-design.md, phase 3).
    if settings.admin_api_key and x_admin_key and secrets.compare_digest(x_admin_key, settings.admin_api_key):
        return
    if x_admin_key and settings.admin_api_key and not secrets.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(status_code=401, detail={"code": "ADMIN_UNAUTHORIZED", "message": "The admin key is invalid."})
    user = authenticate(request, response, db, required=False)
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "ADMIN_UNAUTHORIZED", "message": "Sign in with an administrator account."})
    if user.role != "admin":
        raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN", "message": "Administrator access is required."})


def get_current_user(request: Request, response: Response, db: Session = Depends(get_db)) -> User:
    return authenticate(request, response, db, required=True)


def get_optional_user(request: Request, response: Response, db: Session = Depends(get_db)) -> User | None:
    return authenticate(request, response, db, required=False)


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN", "message": "This account does not have permission for this action."})
        return user
    return dependency
