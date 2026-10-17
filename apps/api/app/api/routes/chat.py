from fastapi import APIRouter, Depends, HTTPException

from app.adapters.llm.provider import LLMNotConfigured, LLMProviderError, StructuredOutputProvider
from app.api.dependencies import get_db, get_llm_provider
from app.core.config import settings
from app.prompts.registry import catalog
from app.schemas.ai import ChatMessage, ChatReply
from app.services.chat_response_service import route_chat_message
from app.services.integration_config import IntegrationSecretConfigurationError, resolve_integration_value
from sqlalchemy.orm import Session
from app.models.entities import User
from app.api.guards import public, require_user
from app.api.permissions import P
from app.services.journey_service import landmark_context

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/message", response_model=ChatReply)
def chat_message(
    payload: ChatMessage,
    provider: StructuredOutputProvider = Depends(get_llm_provider),
    db: Session = Depends(get_db),
    user: User | None = Depends(require_user(P.CHAT_USE, optional=True)),
):
    if user is not None and user.role != "traveler":
        raise HTTPException(status_code=403, detail={"code": "ROLE_FORBIDDEN", "message": "AI chat is a traveler feature."})
    context = landmark_context(db, payload.model_id) if payload.model_id else None
    try:
        response = route_chat_message(payload, provider, db).model_dump()
    except LLMNotConfigured as error:
        raise HTTPException(status_code=503, detail={"code": "LLM_NOT_CONFIGURED", "message": "Configure an AI provider or enable LLM_FALLBACK_ENABLED."}) from error
    except LLMProviderError as error:
        raise HTTPException(status_code=502, detail={"code": "LLM_PROVIDER_ERROR", "message": "The external LLM is unavailable and the local fallback is disabled."}) from error
    return _with_context(response, context)


def _with_context(response: dict, context: dict | None) -> dict:
    if context:
        response["reply"] = "\n\n".join(filter(None, [context["description"], context["notice"], response["reply"]]))
        response["landmark_context"] = context
    return response


@router.get("/status", dependencies=[Depends(public('reports whether the concierge is LLM-backed or on the fallback'))])
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


