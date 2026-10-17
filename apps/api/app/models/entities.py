from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    false,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from app.core.enums import ItineraryStatus, PriceBasis, SlotStatus, VerificationStatus
from app.db.base import Base
from app.db.types import UTCDateTime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# PostgreSQL uses native array/JSONB columns to match the team's schema. JSON on
# SQLite keeps the same models usable by the lightweight test suite.
TEXT_ARRAY = JSON().with_variant(ARRAY(Text()), "postgresql")
JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class LandmarkStory(Base):
    __tablename__ = "landmark_stories"
    model_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    draft: Mapped[dict] = mapped_column(JSON, nullable=False)
    published: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    workflow: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class PointGeometry(TypeDecorator):
    """PostGIS POINT in production; plain text in SQLite's non-spatial tests."""

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Geometry("POINT", srid=4326, spatial_index=False))
        return dialect.type_descriptor(String())

    def process_bind_param(self, value, dialect):
        if value is not None and dialect.name != "postgresql":
            return getattr(value, "data", value)
        return value


def provider_slug_default(context) -> str:
    name = context.get_current_parameters().get("name", "provider")
    return "-".join(str(name).lower().split())[:180] or "provider"


def experience_title_default(context) -> str:
    return context.get_current_parameters().get("name", "")


class Provider(Base):
    __tablename__ = "providers"
    __table_args__ = (UniqueConstraint("slug", name="uq_providers_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(180))
    slug: Mapped[str] = mapped_column(String(180), default=provider_slug_default)
    description: Mapped[str] = mapped_column(Text, default="")
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    address: Mapped[str] = mapped_column(String(300), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Partner lifecycle: pending (self-registered, awaiting review) -> verified | rejected; verified <-> suspended.
    # "mock" and "simulated" are legacy demo values and behave like verified.
    verification_status: Mapped[str] = mapped_column(String(32), default="mock")
    portal_access_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Partner application submitted through the portal, and the administrator's review of it.
    business_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tax_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    business_license_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    document_urls: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, default=list)
    application_note: Mapped[str] = mapped_column(Text, default="")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)  # user id; no FK, users already reference providers
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Retained for compatibility with the first project schema/API.
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    experiences: Mapped[list["Experience"]] = relationship(back_populates="provider")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('traveler', 'provider', 'admin')", name="ck_users_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(180), default="")
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(24), default="traveler", index=True)
    provider_id: Mapped[str | None] = mapped_column(ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Bumped on role change, deactivation, password change or "sign out everywhere": invalidates every access token at once.
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class POI(Base):
    __tablename__ = "pois"
    __table_args__ = (Index("ix_pois_geom", "geom", postgresql_using="gist"),)

    # String IDs support both existing UUID values and the team's readable IDs.
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(180), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    district: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    latitude: Mapped[float]
    longitude: Mapped[float]
    geom: Mapped[object] = mapped_column(PointGeometry(), nullable=False)
    category: Mapped[str] = mapped_column(String(40), index=True)
    address: Mapped[str] = mapped_column(String(300), default="")
    source_attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by_provider_id: Mapped[str | None] = mapped_column(ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True)
    is_in_pilot_polygon: Mapped[bool] = mapped_column(Boolean, default=False)
    image_urls: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, default=list)
    # Visitor information curated in the admin portal (not part of the evidence-backed required fields).
    opening_hours: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ticket_info: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, default=list)
    is_landmark: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Untouched, source-backed place facts (e.g. OSM tags and image credits).
    # These are descriptive catalog metadata, not proof of operational verification.
    details: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict)
    verification_status: Mapped[str] = mapped_column(String(24), default=VerificationStatus.SIMULATED.value)
    data_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    experiences: Mapped[list["Experience"]] = relationship(back_populates="poi")
    stops: Mapped[list["ItineraryStop"]] = relationship(back_populates="poi")


class Experience(Base):
    __tablename__ = "experiences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    poi_id: Mapped[str] = mapped_column(ForeignKey("pois.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id", ondelete="RESTRICT"), index=True)
    # `name` is the original API field; `title` is the team's canonical field.
    name: Mapped[str] = mapped_column(String(180), index=True)
    title: Mapped[str] = mapped_column(String(180), default=experience_title_default)
    description: Mapped[str] = mapped_column(Text, default="")
    intent_tags: Mapped[list[str]] = mapped_column(TEXT_ARRAY, default=list)
    is_hands_on: Mapped[bool] = mapped_column(Boolean, default=False)
    is_indoor: Mapped[bool] = mapped_column(Boolean, default=True)
    primary_intent: Mapped[str | None] = mapped_column(String(40), nullable=True)
    weather_sensitivity: Mapped[str | None] = mapped_column(String(24), nullable=True)
    tagger_prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duration_min: Mapped[int] = mapped_column(Integer)
    price_basis: Mapped[str] = mapped_column(String(24), default=PriceBasis.PER_PERSON.value)
    price_vnd: Mapped[int] = mapped_column(BigInteger, default=0)
    verification_status: Mapped[str] = mapped_column(String(24), default=VerificationStatus.SIMULATED.value)
    data_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    # Legacy alias column retained so current API clients and seed data continue working.
    indoor: Mapped[bool] = mapped_column(Boolean, default=True)
    poi: Mapped[POI] = relationship(back_populates="experiences")
    provider: Mapped[Provider] = relationship(back_populates="experiences")
    slots: Mapped[list["ExperienceSlot"]] = relationship(back_populates="experience", cascade="all, delete-orphan")
    similarities_as_a: Mapped[list["IntentSimilarity"]] = relationship(
        foreign_keys="IntentSimilarity.experience_a_id", back_populates="experience_a"
    )
    similarities_as_b: Mapped[list["IntentSimilarity"]] = relationship(
        foreign_keys="IntentSimilarity.experience_b_id", back_populates="experience_b"
    )


class ExperienceSlot(Base):
    __tablename__ = "experience_slots"
    __table_args__ = (
        UniqueConstraint("experience_id", "start_at", name="uq_slot_experience_start"),
        CheckConstraint(
            "status IN ('open', 'full', 'cancelled', 'available', 'unavailable', 'tentative')",
            name="ck_experience_slots_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    experience_id: Mapped[str] = mapped_column(ForeignKey("experiences.id", ondelete="CASCADE"), index=True)
    start_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime())
    capacity_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_reported: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default=SlotStatus.TENTATIVE.value)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    experience: Mapped[Experience] = relationship(back_populates="slots")
    itinerary_stops: Mapped[list["ItineraryStop"]] = relationship(back_populates="slot")


class Booking(Base):
    """A time-limited seat hold and provider-confirmation workflow."""

    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("quantity BETWEEN 1 AND 10000", name="ck_bookings_quantity_positive"),
        CheckConstraint("amount_vnd >= 0", name="ck_bookings_amount_nonnegative"),
        CheckConstraint(
            "status IN ('pending_provider', 'awaiting_payment', 'confirmed', 'rejected', 'cancelled', 'expired', 'cancellation_requested', 'refund_pending', 'refunded')",
            name="ck_bookings_status",
        ),
        Index("ix_bookings_slot_status_expiry", "slot_id", "status", "hold_expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id", ondelete="RESTRICT"), index=True)
    itinerary_id: Mapped[str] = mapped_column(ForeignKey("itineraries.id", ondelete="SET NULL"), nullable=True, index=True)
    itinerary_stop_id: Mapped[str | None] = mapped_column(ForeignKey("itinerary_stops.id", ondelete="SET NULL"), nullable=True, index=True)
    experience_id: Mapped[str] = mapped_column(ForeignKey("experiences.id", ondelete="RESTRICT"), index=True)
    slot_id: Mapped[str] = mapped_column(ForeignKey("experience_slots.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    amount_vnd: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="VND")
    status: Mapped[str] = mapped_column(String(32), default="pending_provider", index=True)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    provider_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PaymentTransaction(Base):
    """Payment ledger; records real gateway references only (never client claims)."""

    __tablename__ = "payment_transactions"
    __table_args__ = (
        CheckConstraint("amount_vnd >= 0", name="ck_payment_amount_nonnegative"),
        CheckConstraint(
            "status IN ('created', 'pending', 'succeeded', 'failed', 'refund_pending', 'refunded')",
            name="ck_payment_transaction_status",
        ),
        UniqueConstraint("provider", "provider_reference", name="uq_payment_provider_reference"),
        UniqueConstraint("idempotency_key", name="uq_payment_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id", ondelete="RESTRICT"), index=True)
    provider: Mapped[str] = mapped_column(String(40), default="unconfigured")
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    amount_vnd: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="VND")
    status: Mapped[str] = mapped_column(String(24), default="created", index=True)
    checkout_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BookingEvent(Base):
    """Append-only audit trail for reservation, cancellation and payment transitions."""

    __tablename__ = "booking_events"
    __table_args__ = (Index("ix_booking_events_booking_created", "booking_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60))
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    details: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class NotificationDelivery(Base):
    """Durable notification outbox row with retry state and idempotency key."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        CheckConstraint("channel IN ('email', 'webpush')", name="ck_notification_channel"),
        CheckConstraint("status IN ('queued', 'sending', 'retry', 'sent', 'failed')", name="ck_notification_status"),
        CheckConstraint("attempts >= 0", name="ck_notification_attempts"),
        UniqueConstraint("idempotency_key", name="uq_notification_idempotency_key"),
        Index("ix_notification_queue", "status", "available_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    recipient_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    recipient_email: Mapped[str] = mapped_column(String(254))
    channel: Mapped[str] = mapped_column(String(16), default="email")
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True)
    booking_id: Mapped[str | None] = mapped_column(ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String(255))
    body_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class WebPushSubscription(Base):
    """A user's opted-in browser endpoint and encryption keys; never returned to admin APIs."""

    __tablename__ = "web_push_subscriptions"
    __table_args__ = (
        UniqueConstraint("endpoint", name="uq_web_push_subscription_endpoint"),
        Index("ix_web_push_user_active", "user_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    endpoint: Mapped[str] = mapped_column(String(2048))
    p256dh_key: Mapped[str] = mapped_column(String(256))
    auth_key: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class OpsJobRun(Base):
    """Observable execution record for worker jobs (not application request logs)."""

    __tablename__ = "ops_job_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_ops_job_status"),
        Index("ix_ops_job_name_started", "job_name", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_name: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(16), default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class IntentSimilarity(Base):
    __tablename__ = "intent_similarities"
    __table_args__ = (
        CheckConstraint("experience_a_id < experience_b_id", name="ck_similarity_canonical_pair"),
        CheckConstraint("semantic_similarity BETWEEN 0 AND 1", name="ck_similarity_semantic_range"),
        CheckConstraint("tag_overlap_score BETWEEN 0 AND 1", name="ck_similarity_tag_range"),
        CheckConstraint("final_score BETWEEN 0 AND 1", name="ck_similarity_final_range"),
    )

    experience_a_id: Mapped[str] = mapped_column(ForeignKey("experiences.id", ondelete="CASCADE"), primary_key=True)
    experience_b_id: Mapped[str] = mapped_column(ForeignKey("experiences.id", ondelete="CASCADE"), primary_key=True)
    semantic_similarity: Mapped[float] = mapped_column(Float)
    tag_overlap_score: Mapped[float] = mapped_column(Float)
    final_score: Mapped[float] = mapped_column(Float)
    can_substitute_purpose: Mapped[bool] = mapped_column(Boolean, default=False)
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_human_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    experience_a: Mapped[Experience] = relationship(foreign_keys=[experience_a_id], back_populates="similarities_as_a")
    experience_b: Mapped[Experience] = relationship(foreign_keys=[experience_b_id], back_populates="similarities_as_b")


class Itinerary(Base):
    __tablename__ = "itineraries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    origin_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    origin_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    city: Mapped[str] = mapped_column(String(100), default="Ho Chi Minh City")
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    group_size: Mapped[int] = mapped_column(Integer)
    budget_vnd: Mapped[int] = mapped_column(BigInteger)
    travel_mode: Mapped[str] = mapped_column(String(24), default="driving")
    target_intents: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    # Legacy fields remain populated for current API responses and planner behavior.
    version: Mapped[int] = mapped_column(Integer, default=1)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default=ItineraryStatus.DRAFT.value)
    constraints: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict)
    estimated_cost_vnd: Mapped[int] = mapped_column(BigInteger, default=0)
    data_mode: Mapped[str] = mapped_column(String(24), default="simulated")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    stops: Mapped[list["ItineraryStop"]] = relationship(
        back_populates="itinerary", cascade="all, delete-orphan", order_by="ItineraryStop.stop_order"
    )
    versions: Mapped[list["ItineraryVersion"]] = relationship(back_populates="itinerary", cascade="all, delete-orphan")
    decision_logs: Mapped[list["DecisionLog"]] = relationship(back_populates="itinerary", cascade="all, delete-orphan")
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="itinerary", cascade="all, delete-orphan")


class ItineraryStop(Base):
    __tablename__ = "itinerary_stops"
    __table_args__ = (UniqueConstraint("itinerary_id", "stop_order", name="uq_itinerary_stop_order"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    itinerary_id: Mapped[str] = mapped_column(ForeignKey("itineraries.id", ondelete="CASCADE"), index=True)
    experience_id: Mapped[str] = mapped_column(ForeignKey("experiences.id", ondelete="RESTRICT"), index=True)
    slot_id: Mapped[str] = mapped_column(ForeignKey("experience_slots.id", ondelete="RESTRICT"), index=True)
    poi_id: Mapped[str] = mapped_column(ForeignKey("pois.id", ondelete="RESTRICT"), index=True)
    stop_order: Mapped[int] = mapped_column(Integer)
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    wait_duration_min: Mapped[int] = mapped_column(Integer, default=0)
    activity_duration_min: Mapped[int] = mapped_column(Integer, default=0)
    cost_vnd: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(24), default="planned")
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    # Compatibility columns from the first project schema.
    position: Mapped[int] = mapped_column(Integer)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    itinerary: Mapped[Itinerary] = relationship(back_populates="stops")
    experience: Mapped[Experience] = relationship()
    slot: Mapped[ExperienceSlot] = relationship(back_populates="itinerary_stops")
    poi: Mapped[POI] = relationship(back_populates="stops")


class ItineraryVersion(Base):
    __tablename__ = "itinerary_versions"
    __table_args__ = (UniqueConstraint("itinerary_id", "version_number", name="uq_itinerary_version_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    itinerary_id: Mapped[str] = mapped_column(ForeignKey("itineraries.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    stops_snapshot: Mapped[list[dict]] = mapped_column(JSON_DOCUMENT, default=list)
    total_cost_vnd: Mapped[int] = mapped_column(BigInteger, default=0)
    total_travel_time_s: Mapped[int] = mapped_column(Integer, default=0)
    preserved_intents_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    itinerary: Mapped[Itinerary] = relationship(back_populates="versions")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("event_type IN ('SLOT_CANCELLED', 'WEATHER_ALERT')", name="ck_events_event_type"),
        CheckConstraint("target_type IN ('experience_slot', 'poi')", name="ck_events_target_type"),
        CheckConstraint("status IN ('active', 'resolved')", name="ck_events_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON_DOCUMENT, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decision_logs: Mapped[list["DecisionLog"]] = relationship(back_populates="trigger_event")


class Feedback(Base):
    """User feedback and the PRD 3.0 rubric label used to prepare ML samples."""

    __tablename__ = "feedbacks"
    __table_args__ = (
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_feedback_rating_range"),
        CheckConstraint("relevance_grade IS NULL OR relevance_grade BETWEEN 0 AND 3", name="ck_feedback_relevance_range"),
        CheckConstraint("objective_achieved_ratio IS NULL OR objective_achieved_ratio BETWEEN 0 AND 1", name="ck_feedback_objective_ratio"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    itinerary_id: Mapped[str] = mapped_column(ForeignKey("itineraries.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rubric_justification_vi: Mapped[str | None] = mapped_column(Text, nullable=True)
    objective_achieved_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_usable_for_training: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    labeler_prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    itinerary: Mapped[Itinerary] = relationship(back_populates="feedbacks")


class RecommendationConsent(Base):
    """Separate, revocable choices for personalization and model-training use."""

    __tablename__ = "recommendation_consents"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    personalization_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model_training_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    admin_history_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_version: Mapped[str] = mapped_column(String(40), default="behavior-v2", nullable=False)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RecommendationInteraction(Base):
    """Consent-gated impressions and selections used to prepare future ranking data."""

    __tablename__ = "recommendation_interactions"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('impression', 'selected', 'dismissed')",
            name="ck_recommendation_interactions_event_type",
        ),
        CheckConstraint("position IS NULL OR position >= 0", name="ck_recommendation_interactions_position"),
        Index("ix_recommendation_interactions_user_created", "user_id", "created_at"),
        Index("ix_recommendation_interactions_request", "request_id"),
        Index("ix_recommendation_interactions_training", "model_training_eligible", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    experience_id: Mapped[str | None] = mapped_column(
        ForeignKey("experiences.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_snapshot: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict, nullable=False)
    candidate_snapshot: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict, nullable=False)
    personalization_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model_training_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    admin_history_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_uri: Mapped[str] = mapped_column(String(1000))
    source_type: Mapped[str] = mapped_column(String(40))
    source_label: Mapped[str | None] = mapped_column(String(180), nullable=True)
    license: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    submitted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    target_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    fields_covered: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, default=list, nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(180), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlaceImportBatch(Base):
    """An immutable registration of a raw place-data import."""

    __tablename__ = "place_import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_name: Mapped[str] = mapped_column(String(255))
    source_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    worksheet_name: Mapped[str] = mapped_column(String(100))
    imported_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    quality_summary: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    candidates: Mapped[list["PlaceImportCandidate"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="PlaceImportCandidate.source_row"
    )


class PlaceImportCandidate(Base):
    """Raw source row plus explicit quality flags; never a live catalog POI."""

    __tablename__ = "place_import_candidates"
    __table_args__ = (UniqueConstraint("batch_id", "external_id", name="uq_place_candidate_batch_external_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    batch_id: Mapped[str] = mapped_column(ForeignKey("place_import_batches.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(128))
    source_row: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(180), index=True)
    kind: Mapped[str] = mapped_column(String(80), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict)
    quality_flags: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, default=list)
    review_status: Mapped[str] = mapped_column(String(32), default="needs_enrichment", index=True)
    target_poi_id: Mapped[str | None] = mapped_column(ForeignKey("pois.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    batch: Mapped[PlaceImportBatch] = relationship(back_populates="candidates")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(40), index=True)
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    details: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class DecisionLog(Base):
    __tablename__ = "decision_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    itinerary_id: Mapped[str] = mapped_column(ForeignKey("itineraries.id", ondelete="CASCADE"), index=True)
    trigger_event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True)
    base_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preserved_intents: Mapped[list[str]] = mapped_column(TEXT_ARRAY, default=list)
    lost_intents: Mapped[list[str]] = mapped_column(TEXT_ARRAY, default=list)
    comparative_metrics: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict)
    explanation_vi: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason_codes: Mapped[list[str]] = mapped_column(TEXT_ARRAY, default=list)
    rejected_candidates: Mapped[list[dict]] = mapped_column(JSON_DOCUMENT, default=list)
    model_version: Mapped[str] = mapped_column(String(80), default="heuristic-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    itinerary: Mapped[Itinerary] = relationship(back_populates="decision_logs")
    trigger_event: Mapped[Event | None] = relationship(back_populates="decision_logs")


class IntegrationSecret(Base):
    """Encrypted admin-managed integration setting; ciphertext only is stored."""

    __tablename__ = "integration_secrets"
    __table_args__ = (UniqueConstraint("service", "config_key", name="uq_integration_service_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    service: Mapped[str] = mapped_column(String(40), index=True)
    config_key: Mapped[str] = mapped_column(String(80))
    encrypted_value: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ItineraryClaimToken(Base):
    """Single-use link that lets a chat-bot traveller attach a ticket itinerary to a real account.

    Kept apart from ``itineraries.share_token``: the share token only grants read access and may be passed around,
    while this token transfers ownership. Only its SHA-256 hash is stored.
    """

    __tablename__ = "itinerary_claim_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    itinerary_id: Mapped[str] = mapped_column(ForeignKey("itineraries.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Register the auth tables on Base (they live in their own module to keep the auth package independent).
from app.models import auth_entities  # noqa: E402,F401


class SiteBanner(Base):
    """Hero banner on the traveler web home page, managed in the admin portal."""

    __tablename__ = "site_banners"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(180))
    subtitle: Mapped[str] = mapped_column(String(300), default="")
    image_url: Mapped[str] = mapped_column(String(1000))
    link_url: Mapped[str] = mapped_column(String(500), default="/")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SiteArticle(Base):
    """Travel guide / news article shown on the traveler web."""

    __tablename__ = "site_articles"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_site_articles_slug"),
        CheckConstraint("status IN ('draft', 'published')", name="ck_site_articles_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(220))
    slug: Mapped[str] = mapped_column(String(220), index=True)
    excerpt: Mapped[str] = mapped_column(String(600), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    cover_url: Mapped[str] = mapped_column(String(1000), default="")
    category: Mapped[str] = mapped_column(String(60), default="Cẩm nang")
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    author_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SiteCollection(Base):
    """Curated list of places featured on the traveler web."""

    __tablename__ = "site_collections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(String(600), default="")
    place_ids: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PageView(Base):
    """One page view on the traveler web. No IP address is stored and the browser id is hashed before it is saved."""

    __tablename__ = "page_views"
    __table_args__ = (Index("ix_page_views_entity", "entity_type", "entity_id", "occurred_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    visitor_hash: Mapped[str] = mapped_column(String(64), index=True)
    session_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    path: Mapped[str] = mapped_column(String(300))
    entity_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    referrer_host: Mapped[str | None] = mapped_column(String(200), nullable=True)
    device: Mapped[str] = mapped_column(String(16), default="desktop")


class ExperienceReview(Base):
    """A traveler's review of an experience they attended (one per booking), with the partner's public reply."""

    __tablename__ = "experience_reviews"
    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_experience_reviews_booking"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_experience_reviews_rating"),
        CheckConstraint("status IN ('published', 'hidden')", name="ck_experience_reviews_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    experience_id: Mapped[str] = mapped_column(ForeignKey("experiences.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id", ondelete="CASCADE"), index=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="published")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

class MeshyJob(Base):
    __tablename__ = "meshy_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    request_key: Mapped[str] = mapped_column(String(36), unique=True)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(24), default="submitting", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    credits: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    previewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
