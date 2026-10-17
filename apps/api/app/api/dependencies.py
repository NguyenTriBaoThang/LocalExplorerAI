from fastapi import Depends
from sqlalchemy.orm import Session

from app.adapters.llm.provider import NotConfiguredLLMProvider, OpenAICompatibleLLMProvider, StructuredOutputProvider
from app.core.config import settings
from app.db.session import get_db
from app.services.planner_service import PlannerService
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
