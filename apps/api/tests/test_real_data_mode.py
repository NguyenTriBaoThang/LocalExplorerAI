import pytest

from app.core.config import settings
from app.services.ticket_service import TicketService


def test_legacy_ticket_generator_is_disabled_in_real_data_mode(monkeypatch):
    monkeypatch.setattr(settings, "real_data_only", True)

    with pytest.raises(RuntimeError, match="disabled in REAL_DATA_ONLY mode"):
        TicketService().generate_ticket("chat-1", "Traveler")
