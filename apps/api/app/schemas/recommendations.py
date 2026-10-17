from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


CONSENT_VERSION = "behavior-v2"


class RecommendationConsentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    personalization_enabled: bool
    model_training_enabled: bool
    admin_history_enabled: bool | None = None
    consent_version: Literal["behavior-v1", "behavior-v2"] = CONSENT_VERSION


class RecommendationConsentRead(BaseModel):
    personalization_enabled: bool = False
    model_training_enabled: bool = False
    admin_history_enabled: bool = False
    consent_version: str = CONSENT_VERSION


class BehaviorExperimentRankRequest(BaseModel):
    """Only IDs and coarse filters cross the API; candidate features come from the DB."""

    model_config = ConfigDict(extra="forbid")

    experience_ids: list[str] = Field(min_length=1, max_length=100)
    intent_tags: list[str] = Field(default_factory=list, max_length=8)
    budget_band: Literal["under_500k", "500k_1m", "1m_2m", "over_2m"]
    group_size: int = Field(ge=1, le=50)
    center_latitude: float = Field(default=10.7769, ge=-90, le=90)
    center_longitude: float = Field(default=106.7009, ge=-180, le=180)

    @field_validator("intent_tags")
    @classmethod
    def validate_intent_tags(cls, values: list[str]) -> list[str]:
        allowed = {"food", "handicraft", "culture", "nature", "relaxation"}
        normalized = [value.strip().casefold() for value in values]
        if any(value not in allowed for value in normalized):
            raise ValueError("Only the supported Explore categories may be used.")
        return list(dict.fromkeys(normalized))

    @field_validator("experience_ids")
    @classmethod
    def deduplicate_experience_ids(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class RecommendationContext(BaseModel):
    """Allowlisted, coarse context; deliberately excludes free-text searches."""

    model_config = ConfigDict(extra="forbid")

    intent_tags: list[str] = Field(default_factory=list, max_length=8)
    budget_band: Literal["under_500k", "500k_1m", "1m_2m", "over_2m"] | None = None
    group_size: int | None = Field(default=None, ge=1, le=50)
    indoor_preference: Literal["all", "indoor", "outdoor"] | None = None
    time_bucket: Literal["morning", "afternoon", "evening"] | None = None

    @field_validator("intent_tags")
    @classmethod
    def validate_intent_tags(cls, values: list[str]) -> list[str]:
        allowed = {"food", "handicraft", "culture", "nature", "relaxation"}
        normalized = [value.strip().casefold() for value in values]
        if any(value not in allowed for value in normalized):
            raise ValueError("Only the supported Explore categories may be recorded.")
        return list(dict.fromkeys(normalized))


class RecommendationInteractionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    request_id: UUID
    experience_id: str = Field(min_length=1, max_length=36)
    event_type: Literal["impression", "selected", "dismissed"]
    position: int | None = Field(default=None, ge=0, le=10000)
    context: RecommendationContext = Field(default_factory=RecommendationContext)


class RecommendationInteractionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[RecommendationInteractionCreate] = Field(min_length=1, max_length=100)
