"""Request bodies for the portal: admin places, site content, analytics collection and reviews."""

from datetime import date, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _https(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Must be an HTTPS URL without credentials")
    return value


def _image(value: str) -> str:
    """Images may be absolute HTTPS URLs or site-relative paths (e.g. /images/banner.jpg)."""
    value = value.strip()
    if value.startswith("/") and not value.startswith("//"):
        return value
    if _https(value) is None:
        raise ValueError("Image must be an HTTPS URL or a site path")
    return value


class PlaceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=180)
    category: str = Field(min_length=2, max_length=40)
    district: str | None = Field(default=None, max_length=120)
    address: str = Field(min_length=5, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    description: str = Field(default="", max_length=10000)
    image_urls: list[str] = Field(default_factory=list, max_length=20)
    opening_hours: str | None = Field(default=None, max_length=200)
    ticket_info: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=20)
    is_landmark: bool = False
    source_url: str | None = Field(default=None, max_length=1000)
    google_place_id: str | None = Field(default=None, max_length=255, pattern=r"^[A-Za-z0-9_-]*$")

    @field_validator("image_urls")
    @classmethod
    def validate_images(cls, value: list[str]) -> list[str]:
        return [_image(item) for item in value if item.strip()]

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(tag.strip()[:40] for tag in value if tag.strip()))

    @field_validator("source_url")
    @classmethod
    def validate_source(cls, value: str | None) -> str | None:
        return _https(value)


class PlaceStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["publish", "hide", "draft"]
    source_url: str | None = Field(default=None, max_length=1000)

    @field_validator("source_url")
    @classmethod
    def validate_source(cls, value: str | None) -> str | None:
        return _https(value)


class BannerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=180)
    subtitle: str = Field(default="", max_length=300)
    image_url: str = Field(min_length=1, max_length=1000)
    link_url: str = Field(default="/", max_length=500)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=1000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @field_validator("image_url")
    @classmethod
    def validate_image(cls, value: str) -> str:
        return _image(value)

    @field_validator("link_url")
    @classmethod
    def validate_link(cls, value: str) -> str:
        value = value.strip() or "/"
        if value.startswith("/") and not value.startswith("//"):
            return value
        if _https(value) is None:
            raise ValueError("Link must be a site path or an HTTPS URL")
        return value


class ArticlePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=2, max_length=220)
    slug: str = Field(default="", max_length=220, pattern=r"^[a-z0-9-]*$")
    excerpt: str = Field(default="", max_length=600)
    body: str = Field(default="", max_length=100_000)
    cover_url: str = Field(default="", max_length=1000)
    category: str = Field(default="Cẩm nang", min_length=1, max_length=60)
    status: Literal["draft", "published"] = "draft"

    @field_validator("cover_url")
    @classmethod
    def validate_cover(cls, value: str) -> str:
        return _image(value) if value.strip() else ""


class CollectionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=600)
    place_ids: list[str] = Field(default_factory=list, max_length=50)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=1000)


class PageViewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visitor_id: str = Field(min_length=8, max_length=64)
    session_id: str = Field(min_length=8, max_length=64)
    path: str = Field(min_length=1, max_length=300)
    referrer: str | None = Field(default=None, max_length=1000)
    entity_type: Literal["poi", "experience", "article"] | None = None
    entity_id: str | None = Field(default=None, max_length=36)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        value = value.split("?", 1)[0].split("#", 1)[0]  # never keep query strings: they can carry personal data
        if not value.startswith("/"):
            raise ValueError("Path must start with /")
        return value


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


class ReviewReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply: str = Field(min_length=1, max_length=2000)


class PlaceReviewWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)
    visited_on: date | None = None


class ReviewModeration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["hide", "restore"]
    note: str = Field(default="", max_length=500)
