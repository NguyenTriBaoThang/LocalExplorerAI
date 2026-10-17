from fastapi import Depends
from sqlalchemy.orm import Session

from app.adapters.llm.provider import NotConfiguredLLMProvider, OpenAICompatibleLLMProvider, StructuredOutputProvider
from app.core.config import settings
from app.db.session import get_db
from app.services.planner_service import PlannerService
from app.services.integration_config import IntegrationSecretConfigurationError, resolve_integration_value


def get_planner_service(db: Session = Depends(get_db)) -> PlannerService:
    return PlannerService(db)


def resolve_llm_config(db: Session) -> tuple[str, str, str] | None:
    """(api_key, base_url, model) of the selected chat provider, or None when not configured."""
    try:
        selected = (resolve_integration_value(db, "ai", "provider") or "openai").strip().lower()
    except IntegrationSecretConfigurationError:
        return None
    if selected == "gemini":
        key_name, base_name, model_name = "gemini_api_key", "gemini_base_url", "gemini_model"
    elif selected == "openai":
        key_name, base_name, model_name = "openai_api_key", "openai_base_url", "openai_model"
    else:
        return None
    try:
        api_key = resolve_integration_value(db, "ai", key_name)
        base_url = resolve_integration_value(db, "ai", base_name)
        model = resolve_integration_value(db, "ai", model_name)
    except IntegrationSecretConfigurationError:
        return None
    if not api_key or not base_url or not model:
        return None
    return api_key.strip(), base_url.strip(), model.strip()


def get_llm_provider(db: Session = Depends(get_db)) -> StructuredOutputProvider:
    config = resolve_llm_config(db)
    if config is None:
        return NotConfiguredLLMProvider()
    api_key, base_url, model = config
    return OpenAICompatibleLLMProvider(
        api_key=api_key,
        model_name=model,
        base_url=base_url,
        timeout_seconds=settings.openai_timeout_seconds,
    )
