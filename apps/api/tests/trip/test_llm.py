import httpx
import openai

from app.services.trip import llm


def test_timeout_is_reported_without_losing_saved_trip(db_session):
    import json
    from app.services.trip.flow import guarded

    def timed_out():
        raise openai.APITimeoutError(request=httpx.Request("POST", "https://example.test"))
        yield

    events = list(guarded(db_session, timed_out()))
    event = json.loads(events[0].removeprefix("data: "))
    assert event["type"] == "error"
    assert "quá nhiều thời gian" in event["message"]
    assert "kiểm tra mạng" not in event["message"]


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
