"""M11: turn a Zalo/Telegram message into a draft quote. Never sends a price: the customer only gets an acknowledgement or questions."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_llm_provider
from app.models.entities import AuditLog, OperatorOrg, Quote
from app.services.bot_service import bot_service
from app.services.quote import quote_service
from app.services.quote.request_parser import parse_offline

log = logging.getLogger(__name__)

HUMAN = "Cảm ơn anh/chị! Yêu cầu này cần nhân viên tư vấn thiết kế riêng, bên em sẽ liên hệ lại sớm."
ACK = "Cảm ơn anh/chị, bên em đang soạn báo giá, sẽ gửi trong ít phút."


def quote_org(db: Session) -> OperatorOrg | None:
    ref = str(bot_service.get_config().get("quote_org_id") or "").strip()
    if not ref:
        return None
    return db.scalar(select(OperatorOrg).where((OperatorOrg.id == ref) | (OperatorOrg.slug == ref)))


def looks_like_tour_request(text: str) -> bool:
    # ponytail: offline keyword parse, needs a headcount, a duration or a known destination; add an LLM classifier if false positives hurt.
    from datetime import date
    req = parse_offline(text, date.today())
    return bool(req.pax or req.days or req.destinations)


def handle_bot_message(db: Session, text: str, channel: str, contact: str, message_id: str | None) -> str | None:
    """-> reply text for the customer, or None when nothing should be sent (not a tour request, no org, or a duplicate)."""
    org = quote_org(db)
    if org is None or not looks_like_tour_request(text):
        return None
    if message_id and db.scalar(select(Quote.id).where(Quote.org_id == org.id, Quote.channel == channel, Quote.channel_message_id == message_id)):
        return None
    try:
        result = quote_service.draft_from_message(db, org, text, channel, contact, None, provider=get_llm_provider(db), channel_message_id=message_id)
    except IntegrityError:  # concurrent redelivery lost the race on the unique constraint
        db.rollback()
        return None
    except (quote_service.CustomTourNotSupported, quote_service.NoRates) as error:
        db.add(AuditLog(id=str(uuid4()), actor_id=None, action="quote.intake_needs_human", target_type="operator_org", target_id=org.id,
                        details={"channel": channel, "contact": contact, "text": text[:300], "reason": str(error)}, created_at=datetime.now(timezone.utc)))
        db.commit()
        return HUMAN
    if result.questions:
        return "Để báo giá chính xác, anh/chị vui lòng cho em biết thêm:\n- " + "\n- ".join(result.questions)
    return ACK
