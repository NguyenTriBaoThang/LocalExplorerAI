from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


IntentName = Literal["thủ_công", "ẩm_thực", "văn_hóa", "thư_giãn"]
TravelMode = Literal["motorcycle", "walking", "car", "transit"]
WeatherSensitivity = Literal["indoor_safe", "rain_sensitive", "outdoor_only"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StructuredConstraints(StrictModel):
    trip_date: date | None = None
    group_size: int | None = Field(default=None, ge=1, le=50)
    start_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    return_deadline: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    budget_vnd: int | None = Field(default=None, ge=0)
    travel_mode: TravelMode
    travel_mode_confirmed: bool = False
    intent_weights: dict[IntentName, float]
    locked_pois: list[str]
    is_complete: bool
    missing_fields: list[str]
    clarification_question_vi: str | None

    @model_validator(mode="after")
    def check_consistency(self):
        for field_name in ("start_time", "return_deadline"):
            value = getattr(self, field_name)
            if value:
                hour, minute = map(int, value.split(":"))
                if hour > 23 or minute > 59:
                    raise ValueError(f"{field_name} must be a valid HH:mm time")
        if set(self.intent_weights) != {"thủ_công", "ẩm_thực", "văn_hóa", "thư_giãn"}:
            raise ValueError("intent_weights must contain the four PRD intent keys")
        if any(value < 0 or value > 1 for value in self.intent_weights.values()):
            raise ValueError("intent_weights values must be in [0,1]")
        if abs(sum(self.intent_weights.values()) - 1.0) > 0.01:
            raise ValueError("intent_weights must sum to 1")
        missing = {
            "group_size": self.group_size is None,
            "start_time": self.start_time is None,
            "return_deadline": self.return_deadline is None,
            "budget_vnd": self.budget_vnd is None,
        }
        actual_missing = {key for key, value in missing.items() if value}
        if self.is_complete != (not actual_missing) or not actual_missing.issubset(set(self.missing_fields)):
            raise ValueError("is_complete and missing_fields do not match required fields")
        if self.is_complete and self.clarification_question_vi is not None:
            raise ValueError("complete constraints cannot ask a clarification question")
        if not self.is_complete and not self.clarification_question_vi:
            raise ValueError("incomplete constraints require a clarification question")
        return self


class ExperienceMetadata(StrictModel):
    experience_id: str
    is_hands_on: bool
    is_indoor: bool
    primary_intent: IntentName
    intent_tags: list[str]
    hands_on_justification: str
    weather_sensitivity: WeatherSensitivity


class SimilarityScore(StrictModel):
    experience_a_id: str
    experience_b_id: str
    semantic_score: float = Field(ge=0, le=1)
    tag_overlap_score: float = Field(ge=0, le=1)
    final_score: float = Field(ge=0, le=1)
    can_substitute_purpose: bool
    comparison_reasoning_vi: str


class ReplanProposal(StrictModel):
    code: Literal["B", "C"]
    title: str
    candidate_experience_id: str
    preserved_intents: list[str]
    lost_intents: list[str]
    cost_diff_vnd: int
    travel_time_diff_min: int
    estimated_return_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    is_recommended: bool
    recommendation_reason_vi: str

    @field_validator("estimated_return_time")
    @classmethod
    def validate_estimated_return_time(cls, value: str) -> str:
        hour, minute = map(int, value.split(":"))
        if hour > 23 or minute > 59:
            raise ValueError("estimated_return_time must be a valid HH:mm time")
        return value


class DisruptionSummary(StrictModel):
    cancelled_experience_title: str
    impact_message_vi: str


class ReplanProposals(StrictModel):
    disruption_summary: DisruptionSummary
    proposals: list[ReplanProposal] = Field(max_length=2)

    @model_validator(mode="after")
    def at_most_one_recommended(self):
        if sum(proposal.is_recommended for proposal in self.proposals) > 1:
            raise ValueError("At most one replan proposal can be recommended")
        return self


class XAIExplanation(StrictModel):
    headline_vi: str = Field(max_length=160)
    core_explanation_vi: str = Field(min_length=1, max_length=1200)
    trade_off_breakdown: dict[str, str]
    data_timestamp: str

    @field_validator("headline_vi")
    @classmethod
    def headline_word_limit(cls, value: str) -> str:
        if len(value.split()) > 14:
            raise ValueError("headline_vi must be under 15 words")
        return value

    @field_validator("core_explanation_vi")
    @classmethod
    def explanation_sentence_count(cls, value: str) -> str:
        import re

        sentence_count = len(re.findall(r"[.!?](?:\s|$)", value.strip()))
        if sentence_count not in {2, 3}:
            raise ValueError("core_explanation_vi must contain two or three sentences")
        return value

    @field_validator("trade_off_breakdown")
    @classmethod
    def exact_tradeoff_fields(cls, value: dict[str, str]) -> dict[str, str]:
        if set(value) != {"why_selected", "why_rejected"}:
            raise ValueError("trade_off_breakdown must include why_selected and why_rejected")
        return value


class ProviderSlotAction(StrictModel):
    action: Literal["CANCEL_SLOT", "UPDATE_CAPACITY", "PAUSE_DAY"]
    target_time_window: str
    new_status: Literal["open", "full", "cancelled"]
    available_reported: int | None = Field(ge=0)
    reason_note: str
    confirmation_sms_for_artisan_vi: str


class FeedbackTrainingSample(StrictModel):
    itinerary_id: str
    relevance_grade: Literal[0, 1, 2, 3]
    rubric_justification_vi: str
    objective_achieved_ratio: float = Field(ge=0, le=1)
    is_usable_for_training: bool


class WeatherAdjustment(StrictModel):
    weather_condition: Literal["rainy", "sunny", "extreme_heat"]
    indoor_priority_boost: bool
    impacted_outdoor_activities: list[str]
    advisory_message_vi: str


ChatRoute = Literal["planning", "travel_information", "out_of_scope"]
ChatTopic = Literal["weather", "place", "activity", "opening_hours", "food", "transport", "other"]


class ChatIntentDecision(StrictModel):
    intent: ChatRoute
    topic: ChatTopic | None = None


class TravelQuestionAnswer(StrictModel):
    reply: str = Field(min_length=1, max_length=2000)


class ChatDestinationContext(StrictModel):
    name: str = Field(min_length=1, max_length=180)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ChatTripContext(StrictModel):
    trip_date: date | None = None
    destination: ChatDestinationContext | None = None
    has_planning_context: bool = False
    planner_constraints: StructuredConstraints | None = None


class ChatWeatherForecast(StrictModel):
    location: str
    forecast_date: date
    precipitation_probability_pct: int = Field(ge=0, le=100)
    precipitation_sum_mm: float = Field(ge=0)
    retrieved_at: datetime
    source: Literal["Open-Meteo"] = "Open-Meteo"
    source_url: str
    attribution: str


class ChatReply(StrictModel):
    status: Literal["parsed", "fallback"]
    assistant_mode: Literal["openai_compatible", "gemini_compatible", "local_fallback", "unavailable"]
    conversation_id: str | None = None
    prompt_version: str | None = None
    fallback_version: str | None = None
    fallback_reason: Literal["llm_not_configured", "llm_unavailable", "invalid_model_output"] | None = None
    intent: ChatRoute
    reply: str = Field(min_length=1, max_length=4000)
    structured_constraints: StructuredConstraints | None = None
    weather_forecast: ChatWeatherForecast | None = None
    landmark_context: dict | None = None


class ChatMessage(StrictModel):
    message: str = Field(min_length=1, max_length=1000)
    language: Literal["vi", "en"] = "vi"
    prior_user_messages: list[str] = Field(default_factory=list, max_length=30)
    conversation_id: str | None = Field(default=None, max_length=128)
    trip_context: ChatTripContext | None = None
    # Earlier clients send the parsed constraints back instead of a trip context; treat them as the planner constraints.
    previous_constraints: StructuredConstraints | None = None
    model_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def adopt_previous_constraints(self):
        if self.previous_constraints is not None and (self.trip_context is None or self.trip_context.planner_constraints is None):
            context = self.trip_context or ChatTripContext()
            self.trip_context = context.model_copy(update={"has_planning_context": True, "planner_constraints": self.previous_constraints})
        return self

    @model_validator(mode="after")
    def bound_conversation_context(self):
        if len(self.message) + sum(len(message) for message in self.prior_user_messages) > 3900:
            raise ValueError("The current and prior user messages must fit within 3,900 characters")
        return self


class ExperienceTagRequest(StrictModel):
    additional_context: str | None = Field(default=None, max_length=2000)


class IntentSimilarityRequest(StrictModel):
    experience_a_id: str
    experience_b_id: str


class ReplanAdviceRequest(StrictModel):
    event_id: str


class ReplanAcceptRequest(StrictModel):
    event_id: str
    affected_stop_id: str
    candidate_experience_id: str
    candidate_slot_id: str
    proposal_code: Literal["B", "C"]
    base_version: int = Field(ge=1)


class ProviderActionPreviewRequest(StrictModel):
    message: str = Field(min_length=1, max_length=2000)
    slot_ids: list[str] = Field(min_length=1, max_length=100)


class ProviderActionConfirmRequest(StrictModel):
    confirmation_token: str = Field(min_length=20, max_length=4096)
    expires_at: datetime | None = None


class FeedbackLabelRequest(StrictModel):
    review_text: str = Field(min_length=1, max_length=4000)
    rating: int | None = Field(default=None, ge=1, le=5)


class WeatherAdviceRequest(StrictModel):
    rain_mm_per_hour: float = Field(ge=0, le=500)
    aqi_pm25: int = Field(ge=0, le=1000)
    temperature_c: float = Field(ge=-20, le=60)
    children_in_group: bool = False
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def observed_at_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone offset")
        return value
