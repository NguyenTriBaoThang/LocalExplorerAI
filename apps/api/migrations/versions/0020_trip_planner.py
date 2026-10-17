"""Add the AI Chat trip planner tables and the trip:use permission."""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0020_trip_planner"
down_revision = "0019_itinerary_collaboration"
branch_labels = None
depends_on = None

PERMISSIONS = {
    "trip:use": ("Plan and edit multi-day trips in AI Chat", ("traveler",)),
}

JSON_DOC = sa.JSON().with_variant(JSONB(), "postgresql")
TS = sa.DateTime(timezone=True)


def _id() -> sa.Column:
    return sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True)


def _trip_fk() -> sa.Column:
    return sa.Column("trip_id", sa.Integer(), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "trip_destinations",
        sa.Column("slug", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("hubs", JSON_DOC, nullable=False),
    )
    op.create_table(
        "trip_places",
        _id(),
        sa.Column("ext_id", sa.String(128), nullable=False, unique=True),
        sa.Column("destination", sa.String(64), sa.ForeignKey("trip_destinations.slug"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("open_hours", JSON_DOC, nullable=False),
        sa.Column("outdoor", sa.Boolean(), nullable=False),
        sa.Column("tags", JSON_DOC, nullable=False),
        sa.Column("raw_tags", JSON_DOC, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("embedding", JSON_DOC, nullable=True),
    )
    op.create_index("ix_trip_places_destination", "trip_places", ["destination"])
    op.create_index("ix_trip_places_kind", "trip_places", ["kind"])
    op.create_table(
        "trips",
        _id(),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("spec", JSON_DOC, nullable=False),
        sa.Column("user_messages", JSON_DOC, nullable=False),
        sa.Column("pending_replan", JSON_DOC, nullable=True),
        sa.Column("pinned_place_ids", JSON_DOC, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_index("ix_trips_user_id", "trips", ["user_id"])
    op.create_table(
        "trip_itineraries",
        _id(),
        _trip_fk(),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("data", JSON_DOC, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.UniqueConstraint("trip_id", "version", name="uq_trip_itinerary_version"),
    )
    op.create_index("ix_trip_itineraries_trip_id", "trip_itineraries", ["trip_id"])
    op.create_table(
        "trip_messages",
        _id(),
        _trip_fk(),
        sa.Column("role", sa.String(8), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.CheckConstraint("role IN ('user', 'ai')", name="ck_trip_message_role"),
    )
    op.create_index("ix_trip_messages_trip_id_id", "trip_messages", ["trip_id", "id"])
    op.create_table(
        "trip_proposals",
        _id(),
        _trip_fk(),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("disruption", JSON_DOC, nullable=False),
        sa.Column("options", JSON_DOC, nullable=False),
        sa.Column("no_feasible", JSON_DOC, nullable=True),
        sa.Column("chosen_index", sa.Integer(), nullable=True),
        sa.Column("applied_version", sa.Integer(), nullable=True),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_trip_proposals_trip_id", "trip_proposals", ["trip_id"])
    op.create_table(
        "trip_group_reviews",
        _id(),
        _trip_fk(),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("candidate", JSON_DOC, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("applied_version", sa.Integer(), nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.CheckConstraint("status IN ('pending', 'applied', 'cancelled')", name="ck_trip_group_review_status"),
    )
    op.create_index("ix_trip_group_reviews_trip_id", "trip_group_reviews", ["trip_id"])

    upgrade_permissions()


def upgrade_permissions() -> None:
    permissions = sa.table("permissions", sa.column("name", sa.String), sa.column("description", sa.String),
                           sa.column("created_at", sa.DateTime(timezone=True)))
    role_permissions = sa.table("role_permissions", sa.column("role_name", sa.String), sa.column("permission_name", sa.String))
    now = datetime.now(timezone.utc)
    op.bulk_insert(permissions, [{"name": name, "description": description, "created_at": now} for name, (description, _) in PERMISSIONS.items()])
    op.bulk_insert(role_permissions, [{"role_name": role, "permission_name": name} for name, (_, roles) in PERMISSIONS.items() for role in roles])


def downgrade_permissions() -> None:
    names = ", ".join(f"'{name}'" for name in PERMISSIONS)
    op.execute(sa.text(f"DELETE FROM role_permissions WHERE permission_name IN ({names})"))
    op.execute(sa.text(f"DELETE FROM permissions WHERE name IN ({names})"))


def downgrade() -> None:
    downgrade_permissions()
    for table in ("trip_group_reviews", "trip_proposals", "trip_messages", "trip_itineraries", "trips", "trip_places", "trip_destinations"):
        op.drop_table(table)
