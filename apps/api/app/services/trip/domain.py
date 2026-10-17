import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TAGS = {
    "cafe-chill", "an-chay", "an-dia-phuong", "hai-san", "thien-nhien", "check-in",
    "lich-su", "van-hoa", "dem", "yen-tinh", "soi-dong", "gia-dinh", "lang-man",
    "mua-sam", "view-dep", "gia-re", "sang-trong",
}

# Intent = lý do lớn của chuyến đi, gom nhiều Tag. gia-dinh, gia-re, sang-trong là ràng buộc, không phải Intent.
INTENTS = {
    "am-thuc": ("an-dia-phuong", "hai-san", "an-chay"),
    "thien-nhien": ("thien-nhien", "view-dep"),
    "van-hoa": ("lich-su", "van-hoa"),
    "thu-gian": ("cafe-chill", "yen-tinh", "lang-man"),
    "vui-choi": ("soi-dong", "dem", "mua-sam", "check-in"),
}
# Khớp INTENT_LABELS ở client/src/api.ts
INTENT_LABELS = {"am-thuc": "Ẩm thực", "thien-nhien": "Thiên nhiên", "van-hoa": "Văn hoá", "thu-gian": "Thư giãn",
                 "vui-choi": "Vui chơi"}


def place_intents(tags) -> set[str]:
    tags = set(tags)
    return {i for i, ts in INTENTS.items() if tags.intersection(ts)}
KINDS = ("an-uong", "cafe", "tham-quan", "giai-tri", "cho-o")
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

Pace = Literal["thong-tha", "vua", "day"]
TravelMode = Literal["xe-may", "grab", "xe-may-rieng", "o-to-rieng"]
ArrivalMode = Literal["may-bay", "xe-khach", "tau", "tu-lai"]
DEFAULT_TRAVEL_MODE: TravelMode = "xe-may"
PACE_STOPS = {"thong-tha": (3, 4), "vua": (5, 5), "day": (6, 7)}
PACE_HOURS = {"thong-tha": ("09:00", "20:00"), "vua": ("08:00", "21:00"), "day": ("07:00", "22:00")}

HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class Trip(BaseModel):
    destination: str
    days: int = Field(ge=1, le=7)
    start_date: dt.date | None = None
    budget: int = Field(gt=0)
    travelers: int = Field(default=1, ge=1, le=10)
    required_tags: list[str] = []
    preferred_tags: list[str] = []
    avoided_tags: list[str] = []
    pace: Pace = "vua"
    travel_mode: TravelMode | None = None  # None = người dùng chưa nói → hỏi lại, không trả lời thì DEFAULT_TRAVEL_MODE
    origin_city: str | None = None
    arrival_mode: ArrivalMode | None = None
    arrival_time: str | None = Field(default=None, pattern=HHMM)
    departure_time: str | None = Field(default=None, pattern=HHMM)
    # giờ muốn xong mọi hoạt động ngày cuối (vd bay 17:00 nhưng xong lúc 13:00 để ra sân bay sớm)
    last_day_end: str | None = Field(default=None, pattern=HHMM)

    @field_validator("required_tags", "preferred_tags", "avoided_tags")
    @classmethod
    def known_tags(cls, v: list[str]) -> list[str]:
        return [t for t in v if t in TAGS]  # LLM có thể bịa Tag → bỏ qua Tag lạ

    @model_validator(mode="after")
    def departure_after_arrival(self):
        if self.days == 1 and self.arrival_time and self.departure_time and self.departure_time <= self.arrival_time:
            raise ValueError("Giờ về phải sau giờ đến")
        return self


def intent_weights(trip: Trip) -> dict[str, int]:
    """Trọng số Intent của Trip: có Tag bắt buộc → 2, chỉ có Tag ưu tiên → 1 (spec D3)."""
    w = {i: 1 for i in place_intents(trip.preferred_tags)}
    w.update({i: 2 for i in place_intents(trip.required_tags)})
    return w


class TripAnswers(BaseModel):
    """Câu trả lời cho event clarify; trường bỏ trống = người dùng không trả lời."""
    travel_mode: TravelMode | None = None
    arrival_mode: ArrivalMode | None = None
    arrival_time: str | None = Field(default=None, pattern=HHMM)
    departure_time: str | None = Field(default=None, pattern=HHMM)


class Hub(BaseModel):
    """Sân bay/bến xe/ga của một Destination — điểm đầu ngày 1 và điểm cuối ngày cuối."""
    name: str
    lat: float
    lon: float


class Place(BaseModel):
    id: int
    destination: str
    name: str
    kind: str
    lat: float
    lon: float
    price: int
    open_hours: dict[str, list[str] | None]  # {} = luôn mở; "mon": null = đóng cửa
    outdoor: bool
    tags: list[str]
    description: str = ""
    photo_url: str | None = None


class DraftStop(BaseModel):
    place_id: int
    start_time: str = Field(pattern=HHMM)
    duration_min: int = Field(ge=15, le=480)
    reason: str = ""
    pinned: bool = False


class DraftDay(BaseModel):
    stops: list[DraftStop] = Field(min_length=1)


class Draft(BaseModel):
    """Itinerary do LLM đề xuất, chưa có chi phí/Leg/Conflict."""
    stay_place_id: int | None = None
    days: list[DraftDay]
    summary: str = ""


class Stop(DraftStop):
    est_cost: int


class Leg(BaseModel):
    from_place_id: int | None  # None = Hub
    to_place_id: int | None
    distance_km: float
    duration_min: int
    mode: Literal["walk", "xe-may", "grab", "o-to"]
    cost: int


class Day(BaseModel):
    date: dt.date | None = None
    stops: list[Stop]
    legs: list[Leg]
    rain_chance: int | None = None


class Conflict(BaseModel):
    kind: Literal["over_budget", "closed", "missing_tag", "rain_outdoor", "before_arrival", "after_departure",
                  "missing_meal", "no_travel_time"]
    message: str
    day_index: int | None = None
    place_id: int | None = None


class Itinerary(BaseModel):
    stay_place_id: int | None
    days: list[Day]
    total_cost: int
    conflicts: list[Conflict] = []
    summary: str = ""
    intents: dict[str, bool] = {}  # Intent của Trip → Itinerary có Stop đáp ứng không
    retention: float | None = None  # Intent Retention R; None khi Trip không có Intent


class Disruption(BaseModel):
    """Sự cố người dùng báo: closed/disliked/late trên một Stop, rain trên cả ngày (spec §13 C6). Lát D thêm insert."""
    kind: Literal["closed", "disliked", "rain", "late"]
    day_index: int = Field(ge=0)
    stop_index: int | None = Field(default=None, ge=0)
    minutes: int | None = Field(default=None, ge=5, le=240)

    @model_validator(mode="after")
    def _shape(self):
        if (self.stop_index is None) != (self.kind == "rain"):
            raise ValueError("stop_index bắt buộc với sự cố trên Stop, bỏ trống với mưa")
        if (self.minutes is None) != (self.kind != "late"):
            raise ValueError("minutes chỉ dùng và bắt buộc với late")
        return self
