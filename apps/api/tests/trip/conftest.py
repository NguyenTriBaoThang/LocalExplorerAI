import json
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.trip import distance

from openai.types.chat import ChatCompletionMessage

from app.services.trip.domain import WEEKDAYS
from app.models.trip_entities import TripDestination, TripPlace


def reply(*calls, content=None):
    tool_calls = [
        {"id": f"call{i}", "type": "function",
         "function": {"name": name, "arguments": args if isinstance(args, str) else json.dumps(args)}}
        for i, (name, args) in enumerate(calls)
    ]
    msg = ChatCompletionMessage.model_validate({"role": "assistant", "content": content, "tool_calls": tool_calls})
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class FakeClient:
    """Giả lập openai.OpenAI: trả lần lượt các response đã soạn sẵn."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def with_options(self, **options):
        self.options = options
        return self


@pytest.fixture
def trip_places(db_session) -> dict[str, TripPlace]:
    """TP.HCM destination with an airport hub and 8 places in District 1, keyed by ext_id."""
    db_session.add(TripDestination(
        slug="tp-hcm", name="TP. Hồ Chí Minh", lat=10.7769, lon=106.7009,
        hubs={"may-bay": {"name": "Sân bay Tân Sơn Nhất", "lat": 10.8188, "lon": 106.6519}},
    ))
    day = lambda o, c: {d: [o, c] for d in WEEKDAYS}
    rows = [
        ("an-pho", "Phở Lệ", "an-uong", 10.7700, 106.6900, 60_000, day("06:00", "22:00"), False),
        ("an-com", "Cơm Tấm Ba Ghiền", "an-uong", 10.7720, 106.6950, 70_000, day("06:00", "22:00"), False),
        ("an-toi", "Quán Nướng Đêm", "an-uong", 10.7740, 106.7000, 150_000, day("17:00", "23:00"), False),
        ("cf-1", "Cà Phê Chung Cư", "cafe", 10.7710, 106.6970, 45_000, day("07:00", "22:00"), False),
        ("cf-2", "The Workshop", "cafe", 10.7730, 106.7040, 55_000, day("07:00", "22:00"), False),
        ("tq-dinh", "Dinh Độc Lập", "tham-quan", 10.7770, 106.6953, 65_000, day("08:00", "17:00"), False),
        ("tq-cong-vien", "Công viên Tao Đàn", "tham-quan", 10.7750, 106.6930, 0, day("05:00", "21:00"), True),
        ("o-1", "Khách sạn Quận 1", "cho-o", 10.7760, 106.7010, 900_000, day("00:00", "23:59"), False),
    ]
    places = {}
    for ext_id, name, kind, lat, lon, price, hours, outdoor in rows:
        places[ext_id] = TripPlace(
            ext_id=ext_id, destination="tp-hcm", name=name, kind=kind, lat=lat, lon=lon, price=price,
            open_hours=hours, outdoor=outdoor, tags=[], raw_tags=[], description="", address="Quận 1, TP.HCM",
        )
    db_session.add_all(places.values())
    db_session.commit()
    return places


@pytest.fixture(autouse=True)
def _clean_distance(monkeypatch):
    distance._cache.clear()
    distance._down_until = 0.0
    monkeypatch.setattr(settings, "goong_api_key", "")
