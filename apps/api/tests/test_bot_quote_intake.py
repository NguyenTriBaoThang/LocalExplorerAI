from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.models.entities import OperatorOrg, Quote
from app.services.bot_service import bot_service

TOUR = "Công ty em 32 người đi Củ Chi và Mekong 2 ngày 1 đêm, khởi hành 30/04, ngân sách 2tr/người"
Q_ONLY = "Cho em hỏi tour Củ Chi giá sao"


@pytest.fixture
def org(db_session, monkeypatch):
    from scripts.seed_operator_demo import ORG_SLUG, seed
    seed(lambda: db_session)
    cfg = {"quote_org_id": ORG_SLUG, "secret_token": "zs"}
    monkeypatch.setattr(bot_service, "get_config", lambda: cfg)
    monkeypatch.setattr(bot_service, "add_message", lambda *a, **k: None)
    return db_session.query(OperatorOrg).filter_by(slug=ORG_SLUG).one()


def zalo(client, text, mid="m1"):
    body = {"message": {"chat": {"id": "c1"}, "from": {"first_name": "An"}, "text": text, "message_id": mid}}
    return client.post("/api/bot/webhook", json=body, headers={"X-Bot-Api-Secret-Token": "zs"})


def quotes(db):
    db.expire_all()
    return db.query(Quote).all()


def test_zalo_creates_draft_acks_and_dedups(client, org, db_session):
    with patch.object(bot_service, "send_zalo_message", new=AsyncMock()) as send:
        assert zalo(client, TOUR).status_code == 200
        assert zalo(client, TOUR).status_code == 200  # same provider message id
    rows = quotes(db_session)
    assert len(rows) == 1 and rows[0].channel == "zalo" and rows[0].customer_contact == "c1" and rows[0].status == "draft"
    assert rows[0].channel_message_id == "m1"
    send.assert_awaited_once()
    assert "soạn báo giá" in send.await_args.args[1] and "đ" not in send.await_args.args[1].replace("đang", "")
    with patch.object(bot_service, "send_zalo_message", new=AsyncMock()):
        zalo(client, TOUR, mid="m2")
    assert len(quotes(db_session)) == 2


def test_missing_fields_reply_with_questions_and_no_quote(client, org, db_session):
    with patch.object(bot_service, "send_zalo_message", new=AsyncMock()) as send:
        zalo(client, Q_ONLY)
    assert quotes(db_session) == []
    assert "Đoàn" in send.await_args.args[1] or "mấy" in send.await_args.args[1]


def test_non_tour_message_untouched(client, org, db_session):
    with patch.object(bot_service, "send_zalo_message", new=AsyncMock()) as send:
        assert zalo(client, "xin chào shop").status_code == 200
    send.assert_not_awaited()
    assert quotes(db_session) == []


def test_no_org_configured_keeps_old_behaviour(client, org, db_session, monkeypatch):
    monkeypatch.setattr(bot_service, "get_config", lambda: {"secret_token": "zs"})
    with patch.object(bot_service, "send_zalo_message", new=AsyncMock()) as send:
        zalo(client, TOUR)
    send.assert_not_awaited()
    assert quotes(db_session) == []


def tg(client, secret, update_id=1, text=TOUR):
    headers = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret else {}
    return client.post("/api/bot/telegram/webhook", json={"update_id": update_id, "message": {"chat": {"id": 77}, "text": text}}, headers=headers)


def test_telegram_secret_checks(client, org, monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "")
    assert tg(client, "x").status_code == 503
    monkeypatch.setattr(settings, "telegram_webhook_secret", "tgs")
    assert tg(client, None).status_code == 403
    assert tg(client, "bad").status_code == 403


def test_telegram_valid_creates_draft_and_replies(client, org, db_session, monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "tgs")
    monkeypatch.setattr(settings, "telegram_bot_token", "TKN")
    with patch("httpx.AsyncClient.post", new=AsyncMock()) as post:
        assert tg(client, "tgs").status_code == 200
        assert tg(client, "tgs").status_code == 200  # redelivery
    rows = quotes(db_session)
    assert len(rows) == 1 and rows[0].channel == "telegram" and rows[0].customer_contact == "77"
    post.assert_awaited_once()
    assert "TKN" in post.await_args.args[0] and post.await_args.kwargs["json"]["chat_id"] == "77"


def test_telegram_send_failure_is_not_an_error(client, org, db_session, monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "tgs")
    monkeypatch.setattr(settings, "telegram_bot_token", "TKN")
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=RuntimeError("down"))):
        assert tg(client, "tgs").status_code == 200
    assert len(quotes(db_session)) == 1


def test_unhandled_request_replies_honestly_audits_and_lists_in_inbox(client, org, db_session):
    from app.services.quote.bot_intake import HUMAN
    from app.models.entities import User
    from tests.helpers import bearer_for
    text = "Em 10 người đi Cần Giờ và Vũng Tàu 3 ngày, khởi hành 30/04"
    with patch.object(bot_service, "send_zalo_message", new=AsyncMock()) as send:
        zalo(client, text)
    send.assert_awaited_once()
    assert send.await_args.args[1] == HUMAN
    assert quotes(db_session) == []
    user = db_session.query(User).filter_by(operator_org_id=org.id).one()
    rows = client.get("/api/operator/quotes/intake-inbox", headers=bearer_for(user)).json()
    assert len(rows) == 1 and rows[0]["channel"] == "zalo" and rows[0]["contact"] == "c1" and "Cần Giờ" in rows[0]["text"]


def test_inbox_is_org_scoped(client, org, db_session):
    from app.models.entities import User
    from tests.helpers import bearer_for, make_user
    other = OperatorOrg(id="other-org", name="B", slug="b")
    db_session.add(other)
    db_session.flush()
    stranger = make_user(db_session, "operator", operator_org_id=other.id)
    with patch.object(bot_service, "send_zalo_message", new=AsyncMock()):
        zalo(client, "Em 10 người đi Cần Giờ và Vũng Tàu 3 ngày, khởi hành 30/04")
    assert client.get("/api/operator/quotes/intake-inbox", headers=bearer_for(stranger)).json() == []
