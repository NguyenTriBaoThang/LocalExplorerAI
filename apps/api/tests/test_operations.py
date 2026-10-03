from app.services import rate_limit
from app.models.entities import NotificationDelivery
from app import main


def test_request_id_is_returned(client):
    response = client.get("/health", headers={"X-Request-ID": "release-check-19"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "release-check-19"


def test_production_rate_limiter_fails_closed_and_returns_trace_id(client, monkeypatch):
    monkeypatch.setattr(main.settings, "rate_limit_enabled", True)

    def unavailable(*args, **kwargs):
        raise ConnectionError("test Redis outage")

    monkeypatch.setattr(main, "check_rate_limit", unavailable)
    unavailable_response = client.get("/", headers={"X-Request-ID": "rate-limit-outage"})
    assert unavailable_response.status_code == 503
    assert unavailable_response.headers["X-Request-ID"] == "rate-limit-outage"

    monkeypatch.setattr(main, "check_rate_limit", lambda *args, **kwargs: (False, 0))
    limited_response = client.get("/")
    assert limited_response.status_code == 429
    assert limited_response.headers["Retry-After"] == "60"
    assert limited_response.headers["X-Request-ID"]


def test_ops_endpoints_are_admin_only_and_hide_recipient_data(client, db_session):
    db_session.add(NotificationDelivery(
        id="notification-private-test", idempotency_key="notification-private-test",
        recipient_email="private@example.com", subject="test subject", body_text="private body",
        status="queued",
    ))
    db_session.flush()
    status = client.get("/api/ops/status")
    assert status.status_code == 200
    assert status.json()["channels"]["email_enabled"] is False
    assert status.json()["notifications"] == {"queued": 1, "sending": 0, "retry": 0, "sent": 0, "failed": 0}
    deliveries = client.get("/api/ops/notifications").json()
    assert len(deliveries) == 1
    assert "recipient_email" not in deliveries[0]
    assert "body_text" not in deliveries[0]
    assert client.get("/api/ops/jobs", headers={"X-Admin-Key": "invalid"}).status_code == 401


def test_fixed_window_rate_limit_reports_remaining(monkeypatch):
    class FakeRedis:
        value = 0

        def eval(self, script, key_count, key, window):
            self.value += 1
            return self.value

    fake = FakeRedis()
    monkeypatch.setattr(rate_limit, "_redis", lambda: fake)
    assert rate_limit.check_rate_limit("test", 2) == (True, 1)
    assert rate_limit.check_rate_limit("test", 2) == (True, 0)
    assert rate_limit.check_rate_limit("test", 2) == (False, 0)


def test_forwarded_ip_is_used_only_from_configured_proxy(client, monkeypatch):
    class FakeRequest:
        client = type("Peer", (), {"host": "10.20.0.4"})()
        headers = {"X-Forwarded-For": "198.51.100.7, 10.20.0.3"}

    monkeypatch.setattr(main.settings, "trusted_proxy_ips", "")
    assert main._client_ip(FakeRequest()) == "10.20.0.4"
    monkeypatch.setattr(main.settings, "trusted_proxy_ips", "10.20.0.0/24")
    assert main._client_ip(FakeRequest()) == "198.51.100.7"
    FakeRequest.client = type("Peer", (), {"host": "203.0.113.4"})()
    assert main._client_ip(FakeRequest()) == "203.0.113.4"
