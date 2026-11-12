from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


class ExperienceDraftRequest(BaseModel):
    poi_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(min_length=1, max_length=10000)
    primary_intent: Literal["thủ_công", "ẩm_thực", "văn_hóa", "thư_giãn"]
    intent_tags: list[str] = Field(default_factory=list, max_length=30)
    is_hands_on: bool = False
    is_indoor: bool = True
    duration_min: int = Field(ge=10, le=1440)
    price_vnd: int = Field(ge=0)
    price_basis: Literal["per_person", "per_group"] = "per_person"


class POIDraftRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=10000)
    district: str | None = Field(default=None, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    category: str = Field(min_length=2, max_length=40)
    address: str = Field(min_length=5, max_length=300)


class SlotCreateRequest(BaseModel):
    start_at: datetime
    end_at: datetime
    capacity_total: int = Field(ge=1, le=10000)
    available_reported: int = Field(ge=0, le=10000)
    expires_at: datetime

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Datetime must include a timezone offset")
        return value

    @field_validator("expires_at")
    @classmethod
    def require_expiry_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Expiry must include a timezone offset")
        return value


class SlotUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    status: Literal["open", "full", "cancelled"]
    available_reported: int | None = Field(default=None, ge=0, le=10000)
    capacity_total: int | None = Field(default=None, ge=1, le=10000)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def require_expiry_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Expiry must include a timezone offset")
        return value


class EvidenceCreateRequest(BaseModel):
    target_type: Literal["poi", "experience"]
    target_id: str = Field(min_length=1, max_length=36)
    source_uri: str = Field(min_length=8, max_length=1000)
    source_type: Literal["official_website", "provider_confirmation", "field_visit", "document", "government_dataset", "other"]
    source_label: str | None = Field(default=None, max_length=180)
    license: str | None = Field(default=None, max_length=120)
    fields_covered: list[str] = Field(min_length=1, max_length=20)
    observed_at: datetime
    expires_at: datetime
    notes: str = Field(default="", max_length=1000)

    @field_validator("source_uri")
    @classmethod
    def require_source_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Source must be a traceable http(s) URL")
        return value.strip()

    @field_validator("observed_at", "expires_at")
    @classmethod
    def require_evidence_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Evidence timestamps must include a timezone offset")
        return value

    @model_validator(mode="after")
    def require_positive_validity_window(self):
        if self.expires_at <= self.observed_at:
            raise ValueError("Evidence expiry must be after its observation time")
        return self


class ModerationRequest(BaseModel):
    action: Literal["approve", "reject", "hide"]
    note: str = Field(default="", max_length=1000)


class ProviderCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    contact_phone: str | None = Field(default=None, max_length=40)
    address: str = Field(default="", max_length=300)


class AdminUserUpdateRequest(BaseModel):
    role: Literal["traveler", "provider", "operator", "admin"]
    is_active: bool
    provider_id: str | None = None
    operator_org_id: str | None = None


class POIMergeRequest(BaseModel):
    keep_id: str = Field(min_length=1, max_length=36)
    duplicate_id: str = Field(min_length=1, max_length=36)
    reason: str = Field(min_length=3, max_length=1000)
