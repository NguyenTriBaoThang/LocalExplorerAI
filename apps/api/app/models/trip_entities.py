"""Trip planner tables (ported from Travility). Imported at the end of entities.py so they register on Base."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime
from app.models.entities import JSON_DOCUMENT, utcnow


class TripDestination(Base):
    __tablename__ = "trip_destinations"

    slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    hubs: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict)


class TripPlace(Base):
    __tablename__ = "trip_places"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ext_id: Mapped[str] = mapped_column(String(128), unique=True)
    destination: Mapped[str] = mapped_column(ForeignKey("trip_destinations.slug"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    price: Mapped[int] = mapped_column(Integer, default=0)
    open_hours: Mapped[dict] = mapped_column(JSON_DOCUMENT, default=dict)
    outdoor: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, default=list)
    raw_tags: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    address: Mapped[str] = mapped_column(Text, default="")
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(JSON_DOCUMENT, nullable=True)


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    spec: Mapped[dict] = mapped_column(JSON_DOCUMENT)
    user_messages: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, default=list)
    pending_replan: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    pinned_place_ids: Mapped[list[int]] = mapped_column(JSON_DOCUMENT, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class TripItinerary(Base):
    __tablename__ = "trip_itineraries"
    __table_args__ = (UniqueConstraint("trip_id", "version", name="uq_trip_itinerary_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON_DOCUMENT)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class TripMessage(Base):
    __tablename__ = "trip_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'ai')", name="ck_trip_message_role"),
        Index("ix_trip_messages_trip_id_id", "trip_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(8))
    text: Mapped[str] = mapped_column(Text)
    version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class TripProposal(Base):
    __tablename__ = "trip_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    base_version: Mapped[int] = mapped_column(Integer)
    disruption: Mapped[dict] = mapped_column(JSON_DOCUMENT)
    options: Mapped[list] = mapped_column(JSON_DOCUMENT)
    no_feasible: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    chosen_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    applied_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class TripGroupReview(Base):
    __tablename__ = "trip_group_reviews"
    __table_args__ = (CheckConstraint("status IN ('pending', 'applied', 'cancelled')", name="ck_trip_group_review_status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    source_version: Mapped[int] = mapped_column(Integer)
    base_version: Mapped[int] = mapped_column(Integer)
    feedback: Mapped[str] = mapped_column(Text)
    candidate: Mapped[dict] = mapped_column(JSON_DOCUMENT)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    applied_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
