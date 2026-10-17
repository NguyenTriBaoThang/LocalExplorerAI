import logging
import time

import openai
from sqlalchemy.orm import Session

from app.api.dependencies import resolve_llm_config
from app.core.config import settings
from app.services.integration_config import IntegrationSecretConfigurationError, resolve_integration_value

log = logging.getLogger(__name__)

EMBED_DIM = 768


def chat_client(db: Session) -> tuple[openai.OpenAI, str] | None:
    """Chat client + model of the configured provider; None when no provider is configured."""
    config = resolve_llm_config(db)
    if config is None:
        return None
    api_key, base_url, model = config
    return openai.OpenAI(api_key=api_key, base_url=base_url, timeout=settings.openai_timeout_seconds), model


def embed(db: Session, texts: list[str], wait_on_rate_limit: bool = False) -> list[list[float]] | None:
    """Gemini embeddings; None (never raises) when the key is missing or the call fails.

    The live path fails fast (no SDK retries, no sleeping) so search falls back to keywords;
    only the offline bulk import passes wait_on_rate_limit=True.
    """
    try:
        api_key = resolve_integration_value(db, "ai", "gemini_api_key")
        base_url = resolve_integration_value(db, "ai", "gemini_base_url")
    except IntegrationSecretConfigurationError:
        return None
    if not api_key or not base_url:
        return None
    try:
        client = openai.OpenAI(api_key=api_key.strip(), base_url=base_url.strip(), timeout=settings.openai_timeout_seconds,
                               max_retries=2 if wait_on_rate_limit else 0)
        out: list[list[float]] = []
        for i in range(0, len(texts), 100):  # keep each request under Gemini's batch limit
            batch = texts[i:i + 100]
            try:
                r = client.embeddings.create(model=settings.gemini_embed_model, input=batch, dimensions=EMBED_DIM)
            except openai.RateLimitError:
                if not wait_on_rate_limit:
                    raise
                # free tier: 100 texts/minute, wait out the window once
                time.sleep(62)
                r = client.embeddings.create(model=settings.gemini_embed_model, input=batch, dimensions=EMBED_DIM)
            out.extend(d.embedding for d in r.data)
        return out
    except Exception as error:
        log.warning("trip embedding failed: %s", error)
        return None
