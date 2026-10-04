from fastapi import APIRouter, Depends, HTTPException

from app.adapters.llm.provider import (
    LLMNotConfigured,
    LLMProviderError,
    StructuredOutputProvider,
)
from app.api.dependencies import get_llm_provider, get_optional_user
from app.api.dependencies import get_db
from app.core.config import settings
from app.prompts.registry import catalog
from app.schemas.ai import ChatMessage, StructuredConstraints
from app.services.offline_chat_fallback import build_offline_constraints
from app.services.integration_config import IntegrationSecretConfigurationError, resolve_integration_value
from sqlalchemy.orm import Session
from app.services.prompt_service import InvalidStructuredOutput, PromptRunner
from app.models.entities import User

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/message")
def chat_message(
    payload: ChatMessage,
    provider: StructuredOutputProvider = Depends(get_llm_provider),
    user: User | None = Depends(get_optional_user),
):
    if user is not None and user.role != "traveler":
        raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN", "message": "AI chat is a traveler feature."})
    try:
        constraints = PromptRunner(provider).run(
            "CONVERSATION_PARSER",
            {"message": payload.message, "conversation_id": payload.conversation_id},
            StructuredConstraints,
        )
    except LLMNotConfigured:
        return _fallback_response(payload, "llm_not_configured")
    except LLMProviderError:
        return _fallback_response(payload, "llm_unavailable")
    except InvalidStructuredOutput:
        return _fallback_response(payload, "invalid_model_output")

    return {
        "status": "parsed",
        "assistant_mode": "openai_compatible",
        "conversation_id": payload.conversation_id,
        "prompt_version": catalog.version,
        "fallback_version": None,
        "fallback_reason": None,
        "reply": constraints.clarification_question_vi or "Mình đã ghi nhận các ràng buộc chuyến đi.",
        "structured_constraints": constraints.model_dump(),
    }


@router.get("/status")
def chat_status(provider: StructuredOutputProvider = Depends(get_llm_provider), db: Session = Depends(get_db)):
    configured = provider.model_name != "not-configured"
    try:
        selected = resolve_integration_value(db, "ai", "provider") or settings.llm_provider
    except IntegrationSecretConfigurationError:
        selected = settings.llm_provider
    return {
        "assistant_mode": f"{selected}_compatible" if configured else ("local_fallback" if settings.llm_fallback_enabled else "unavailable"),
        "llm_configured": configured,
        "fallback_available": settings.llm_fallback_enabled,
        "fallback_version": "1.0.0" if settings.llm_fallback_enabled else None,
    }


def _fallback_response(payload: ChatMessage, reason: str) -> dict:
    if not settings.llm_fallback_enabled:
        if reason == "llm_not_configured":
            raise HTTPException(status_code=503, detail={"code": "LLM_NOT_CONFIGURED", "message": "Configure OPENAI_API_KEY or enable LLM_FALLBACK_ENABLED."})
        raise HTTPException(status_code=502, detail={"code": "LLM_PROVIDER_ERROR", "message": "The external LLM is unavailable and the local fallback is disabled."})
    constraints, reply = build_offline_constraints(payload.message, reason)
    return {
        "status": "fallback",
        "assistant_mode": "local_fallback",
        "conversation_id": payload.conversation_id,
        "prompt_version": None,
        "fallback_version": "1.0.0",
        "fallback_reason": reason,
        "reply": reply,
        "structured_constraints": constraints.model_dump(),
    }
