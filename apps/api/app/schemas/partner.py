"""Partner (provider) self-registration and the administrator's review of it."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.auth import RegisterRequest

BusinessType = Literal["household", "company", "cooperative", "individual", "other"]


def _http_url(value: str) -> str:
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Must be an http(s) URL")
    return value


class PartnerApplicationUpdate(BaseModel):
    """Business details a partner submits for review (also used to resubmit after a rejection)."""
    model_config = ConfigDict(extra="forbid")

    business_name: str = Field(min_length=2, max_length=180)
    business_type: BusinessType
    description: str = Field(default="", max_length=4000)
    contact_phone: str = Field(min_length=6, max_length=40)
    address: str = Field(min_length=5, max_length=300)
    tax_code: str | None = Field(default=None, max_length=40)
    business_license_no: str | None = Field(default=None, max_length=80)
    website: str | None = Field(default=None, max_length=300)
    document_urls: list[str] = Field(default_factory=list, max_length=10)
    application_note: str = Field(default="", max_length=2000)

    @field_validator("website")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        return _http_url(value) if value and value.strip() else None

    @field_validator("document_urls")
    @classmethod
    def validate_documents(cls, value: list[str]) -> list[str]:
        return [_http_url(item) for item in value if item.strip()]


class PartnerRegisterRequest(RegisterRequest):
    """A new account and its partner application in one step."""
    application: PartnerApplicationUpdate


class ProviderDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "reject", "suspend", "reactivate"]
    note: str = Field(default="", max_length=2000)


def apply_application_fields(provider, payload: PartnerApplicationUpdate) -> None:
    provider.name = payload.business_name.strip()
    provider.business_type = payload.business_type
    provider.description = payload.description.strip()
    provider.contact_phone = payload.contact_phone.strip()
    provider.address = payload.address.strip()
    provider.tax_code = (payload.tax_code or "").strip() or None
    provider.business_license_no = (payload.business_license_no or "").strip() or None
    provider.website = payload.website
    provider.document_urls = payload.document_urls
    provider.application_note = payload.application_note.strip()
