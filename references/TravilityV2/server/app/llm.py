from openai import OpenAI

from app.config import settings

EMBED_DIM = 768


def chat_client() -> OpenAI:
    return OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)


def embed(texts: list[str]) -> list[list[float]]:
    client = OpenAI(base_url=settings.embed_base_url, api_key=settings.embed_api_key)
    r = client.embeddings.create(model=settings.embed_model, input=texts, dimensions=EMBED_DIM)
    return [d.embedding for d in r.data]
