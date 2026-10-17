"""Editorial heritage content; independent of operational booking verification."""
from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StorySource(StrictModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    title: str = Field(min_length=1, max_length=200)
    url: str = Field(max_length=2000)
    accessed_on: date

    @field_validator("url")
    @classmethod
    def safe_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Nguồn phải là URL HTTPS, không chứa thông tin đăng nhập")
        return value


class StoryFact(StrictModel):
    text: str = Field(default="", max_length=1600)
    source_ids: list[str] = Field(default_factory=list, max_length=12)
    status: Literal["sourced", "unverified"] = "unverified"

    @model_validator(mode="after")
    def sourced_needs_source(self):
        if self.status == "sourced" and (not self.text or not self.source_ids):
            raise ValueError("Thông tin có nguồn cần nội dung và ít nhất một nguồn")
        return self


class StoryImage(StrictModel):
    url: str = Field(max_length=2000)
    caption: str = Field(min_length=1, max_length=300)
    credit: str = Field(min_length=1, max_length=300)
    source_url: str = Field(max_length=2000)

    @field_validator("source_url")
    @classmethod
    def safe_source(cls, value):
        return StorySource.safe_url(value)

    @field_validator("url")
    @classmethod
    def safe_image(cls, value):
        if value.startswith("/images/") and ".." not in value and "\\" not in value:
            return value
        return StorySource.safe_url(value)


class TimelineEvent(StoryFact):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    period: str = Field(min_length=1, max_length=80)
    year_start: int = Field(ge=1, le=2200)
    year_end: int | None = Field(default=None, ge=1, le=2200)
    image: StoryImage | None = None

    @model_validator(mode="after")
    def ordered_period(self):
        if self.year_end is not None and self.year_end < self.year_start:
            raise ValueError("Năm kết thúc phải từ năm bắt đầu trở đi")
        return self


class ArchitectureDetail(StoryFact):
    title: str = Field(min_length=1, max_length=200)
    view: Literal["front", "top", "park", "cinematic"] | None = None


class VisitInfo(StrictModel):
    address: StoryFact = Field(default_factory=StoryFact)
    duration: StoryFact = Field(default_factory=StoryFact)
    hours: StoryFact = Field(default_factory=StoryFact)
    admission: StoryFact = Field(default_factory=StoryFact)
    notes: StoryFact = Field(default_factory=StoryFact)
    checked_on: date | None = None

    @model_validator(mode="after")
    def operational_facts_need_date(self):
        if (self.hours.status == "sourced" or self.admission.status == "sourced") and not self.checked_on:
            raise ValueError("Giờ tham quan và giá vé có nguồn cần ngày đối chiếu")
        return self


class LandmarkStoryPayload(StrictModel):
    overview: StoryFact = Field(default_factory=StoryFact)
    image: StoryImage | None = None
    timeline: list[TimelineEvent] = Field(default_factory=list, max_length=40)
    architecture: list[ArchitectureDetail] = Field(default_factory=list, max_length=15)
    visit: VisitInfo = Field(default_factory=VisitInfo)
    sources: list[StorySource] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def valid_references(self):
        source_ids = [s.id for s in self.sources]
        event_ids = [e.id for e in self.timeline]
        if len(set(source_ids)) != len(source_ids) or len(set(event_ids)) != len(event_ids):
            raise ValueError("ID nguồn và ID mốc lịch sử phải duy nhất")
        facts = [self.overview, *self.timeline, *self.architecture,
                 self.visit.address, self.visit.duration, self.visit.hours, self.visit.admission, self.visit.notes]
        for fact in facts:
            if not set(fact.source_ids).issubset(source_ids):
                raise ValueError("Có tham chiếu đến nguồn không tồn tại")
        return self


class StorySave(StrictModel):
    revision: int = Field(ge=0)
    content: LandmarkStoryPayload


class StoryAction(StrictModel):
    revision: int = Field(ge=0)
