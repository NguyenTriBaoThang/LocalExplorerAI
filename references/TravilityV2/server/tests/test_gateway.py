import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import gateway, kv
from app.config import settings

OK = {"id": "c1", "choices": [{"message": {"role": "assistant", "content": "xin chào"}}]}
CHAT = {"model": "m1", "messages": [{"role": "user", "content": "hi"}]}
EMB = {"model": "e1", "input": ["cà phê"], "dimensions": 768}

client = TestClient(gateway.app)


class Upstream:
    """Provider giả: replies[host] = (status | Exception, body); mặc định 200 OK."""

    def __init__(self):
        self.calls, self.replies = [], {}

    def __call__(self, request):
        self.calls.append(request)
        status, body = self.replies.get(request.url.host, (200, OK))
        if isinstance(status, Exception):
            raise status
        return httpx.Response(status, text=body) if isinstance(body, str) else httpx.Response(status, json=body)

    @property
    def hosts(self):
        return [c.url.host for c in self.calls]


@pytest.fixture
def up(monkeypatch, rds):
    u = Upstream()
    monkeypatch.setattr(gateway, "http", httpx.Client(transport=httpx.MockTransport(u)))
    for k, v in dict(llm_base_url="https://primary.test/v1/", llm_api_key="k1", llm_model="m1",
                     embed_base_url="https://embed.test/v1", embed_api_key="ke",
                     llm2_base_url="", llm2_api_key="", llm2_model="",
                     gateway_cache="on", gateway_chat_ttl=86400, llm_rpm=0).items():
        monkeypatch.setattr(settings, k, v)
    return u


def post(body=CHAT):
    return client.post("/v1/chat/completions", json=body)


def ask(i):
    """Một request chat khác nhau cho mỗi i (không trúng cache của nhau)."""
    return post({**CHAT, "messages": [{"role": "user", "content": f"câu {i}"}]})


def test_health():
    assert client.get("/health").json() == {"ok": True}


def test_proxies_with_gateway_key_not_callers(up):
    r = client.post("/v1/chat/completions", json=CHAT, headers={"Authorization": "Bearer cua-ben-goi"})
    assert r.status_code == 200 and r.json() == OK and r.headers["x-cache"] == "miss"
    req = up.calls[0]
    assert str(req.url) == "https://primary.test/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer k1"
    assert json.loads(req.content) == CHAT


def test_same_request_hits_cache_regardless_of_key_order(up, rds):
    post()
    r = post({"messages": CHAT["messages"], "model": "m1"})
    assert r.json() == OK and r.headers["x-cache"] == "hit" and len(up.calls) == 1
    assert rds.mget("gw:stat:hit", "gw:stat:miss", "gw:stat:provider_call") == ["1", "1", "1"]


def test_different_request_misses(up):
    ask(1)
    assert ask(2).headers["x-cache"] == "miss" and len(up.calls) == 2


def test_chat_expires_embedding_does_not(up, rds):
    post()
    r = client.post("/v1/embeddings", json=EMB)
    assert r.status_code == 200
    assert str(up.calls[1].url) == "https://embed.test/v1/embeddings"
    assert up.calls[1].headers["authorization"] == "Bearer ke"
    ttls = sorted(rds.ttl(k) for k in rds.keys("gw:cache:*"))
    assert ttls[0] == -1 and 0 < ttls[1] <= 86400


def test_chat_ttl_zero_never_expires(up, rds, monkeypatch):
    monkeypatch.setattr(settings, "gateway_chat_ttl", 0)
    post()
    assert [rds.ttl(k) for k in rds.keys("gw:cache:*")] == [-1]


def test_off_always_calls_provider(up, rds, monkeypatch):
    monkeypatch.setattr(settings, "gateway_cache", "off")
    post()
    post()
    assert len(up.calls) == 2 and rds.keys("gw:cache:*") == []


def test_replay_serves_recorded_and_rejects_unrecorded(up, monkeypatch):
    post()
    monkeypatch.setattr(settings, "gateway_cache", "replay")
    assert post().json() == OK
    r = ask(1)
    assert r.status_code == 503 and "chưa ghi" in r.json()["error"]["message"]
    assert len(up.calls) == 1  # replay không bao giờ gọi provider


def test_provider_error_passed_through_not_cached(up):
    up.replies["primary.test"] = (400, {"error": {"message": "bad"}})
    r = post()
    assert r.status_code == 400 and r.json() == {"error": {"message": "bad"}}
    post()
    assert len(up.calls) == 2


def test_non_json_provider_error_passed_through(up):
    up.replies["primary.test"] = (502, "<html>Bad Gateway</html>")
    r = post()
    assert r.status_code == 502 and r.text == "<html>Bad Gateway</html>"


def test_provider_unreachable_gives_504(up):
    up.replies["primary.test"] = (httpx.ConnectError("offline"), None)
    r = post()
    assert r.status_code == 504 and "không phản hồi" in r.json()["error"]["message"]


def test_stream_rejected(up):
    r = post({**CHAT, "stream": True})
    assert r.status_code == 400 and up.calls == []


def test_redis_down_still_answers(up, monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://localhost:1/0")
    monkeypatch.setattr(kv, "_client", None)
    assert post().status_code == 200 and post().headers["x-cache"] == "miss"
    assert len(up.calls) == 2


class Clock:
    def __init__(self, second_of_minute):
        self.t, self.slept = 60_000_000.0 + second_of_minute, []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def use_clock(monkeypatch, second_of_minute, rpm):
    c = Clock(second_of_minute)
    monkeypatch.setattr(gateway, "_now", c.now)
    monkeypatch.setattr(gateway, "_sleep", c.sleep)
    monkeypatch.setattr(settings, "llm_rpm", rpm)
    return c


def test_out_of_slots_waits_for_next_minute(up, rds, monkeypatch):
    clock = use_clock(monkeypatch, second_of_minute=50, rpm=2)
    assert [ask(i).status_code for i in range(3)] == [200, 200, 200]
    assert clock.slept == [10] and len(up.calls) == 3
    assert rds.get("gw:stat:wait") == "1"


def test_gives_429_after_waiting_30s(up, monkeypatch):
    clock = use_clock(monkeypatch, second_of_minute=0, rpm=1)
    ask(1)
    r = ask(2)
    assert r.status_code == 429 and "hết lượt" in r.json()["error"]["message"]
    assert clock.slept == [30] and len(up.calls) == 1


def test_cache_hit_does_not_take_a_slot(up, monkeypatch):
    clock = use_clock(monkeypatch, second_of_minute=0, rpm=1)
    assert [post().status_code, post().status_code] == [200, 200]
    assert clock.slept == [] and len(up.calls) == 1


def test_embeddings_not_rate_limited(up, monkeypatch):
    clock = use_clock(monkeypatch, second_of_minute=0, rpm=1)
    for i in range(3):
        assert client.post("/v1/embeddings", json={**EMB, "input": [f"q{i}"]}).status_code == 200
    assert clock.slept == []


def test_rpm_zero_means_no_limit(up, rds):
    for i in range(5):
        ask(i)
    assert len(up.calls) == 5 and rds.keys("gw:rl:*") == []


@pytest.fixture
def backup(up, monkeypatch):
    for k, v in dict(llm2_base_url="https://backup.test/v1", llm2_api_key="k2", llm2_model="m2").items():
        monkeypatch.setattr(settings, k, v)
    return up


@pytest.mark.parametrize("failure", [(429, {}), (500, {}), (httpx.ReadTimeout("chậm"), None)])
def test_chat_falls_back_and_swaps_model(backup, rds, failure):
    backup.replies["primary.test"] = failure
    r = post()
    assert r.status_code == 200 and r.json() == OK
    assert backup.hosts == ["primary.test", "backup.test"]
    second = backup.calls[1]
    assert json.loads(second.content)["model"] == "m2" and second.headers["authorization"] == "Bearer k2"
    assert rds.get("gw:stat:fallback") == "1"


def test_bad_request_does_not_fall_back(backup):
    backup.replies["primary.test"] = (400, {"error": {"message": "bad"}})
    assert post().status_code == 400 and backup.hosts == ["primary.test"]


def test_embedding_never_falls_back(backup):
    backup.replies["embed.test"] = (500, {})
    assert client.post("/v1/embeddings", json=EMB).status_code == 500
    assert backup.hosts == ["embed.test"]


def test_no_backup_returns_primary_error(up):
    up.replies["primary.test"] = (500, {"error": {"message": "hỏng"}})
    assert post().status_code == 500 and up.hosts == ["primary.test"]


def test_backup_error_is_returned(backup):
    backup.replies["primary.test"] = (500, {})
    backup.replies["backup.test"] = (503, {"error": {"message": "cũng hỏng"}})
    r = post()
    assert r.status_code == 503 and r.json()["error"]["message"] == "cũng hỏng"


def test_three_failures_skip_primary(backup):
    backup.replies["primary.test"] = (500, {})
    for i in range(3):
        ask(i)
    assert ask(3).status_code == 200
    assert backup.hosts == ["primary.test", "backup.test"] * 3 + ["backup.test"]


def test_success_resets_failure_count(backup):
    backup.replies["primary.test"] = (500, {})
    ask(0)
    ask(1)
    del backup.replies["primary.test"]
    ask(2)  # thành công → đếm lại từ đầu
    backup.replies["primary.test"] = (500, {})
    ask(3)
    ask(4)
    assert backup.hosts[-2:] == ["primary.test", "backup.test"]  # lần thứ 5 vẫn thử provider chính


def test_skipped_primary_without_backup_gives_503(up):
    up.replies["primary.test"] = (500, {})
    for i in range(3):
        ask(i)
    r = ask(3)
    assert r.status_code == 503 and "tạm nghỉ" in r.json()["error"]["message"]
    assert len(up.calls) == 3
