import httpx
import openai

from app.services.trip import llm


def test_embed_returns_none_without_sleeping_on_rate_limit(db_session, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not sleep on the live path")

    monkeypatch.setattr(llm.time, "sleep", boom)
    monkeypatch.setattr(llm, "resolve_integration_value", lambda db, service, key: "x")

    def limited(**kwargs):
        req = httpx.Request("POST", "http://x")
        raise openai.RateLimitError("quota", response=httpx.Response(429, request=req), body=None)

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.embeddings = type("E", (), {"create": staticmethod(limited)})

    monkeypatch.setattr(llm.openai, "OpenAI", FakeOpenAI)
    assert llm.embed(db_session, ["a"]) is None
