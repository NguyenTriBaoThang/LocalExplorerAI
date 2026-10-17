"""Place reviews, Google Maps ratings cache, review moderation.

Revision ID: 0019_place_reviews
Revises: 0018_web_push_notifications

Adds traveler reviews of places, a short-lived cache of the public rating read from Google Maps (with a monthly call
counter so a demo stays inside the free allowance), moderation fields on experience reviews, and the ``admin:reviews``
permission.
"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "0019_place_reviews"
down_revision = "0018_web_push_notifications"
branch_labels = None
depends_on = None

# Frozen copy (see 0012): the permission this revision adds and the roles holding it by default.
PERMISSIONS = {"admin:reviews": ("Hide and restore traveler reviews of places and experiences", ("admin",))}


def upgrade() -> None:
    op.add_column("pois", sa.Column("google_place_id", sa.String(255), nullable=True))
    op.add_column("experience_reviews", sa.Column("moderation_note", sa.Text(), nullable=True))
    op.add_column("experience_reviews", sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("experience_reviews", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "place_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("poi_id", sa.String(36), sa.ForeignKey("pois.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("visited_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="published"),
        sa.Column("moderation_note", sa.Text(), nullable=True),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("poi_id", "user_id", name="uq_place_reviews_poi_user"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_place_reviews_rating"),
        sa.CheckConstraint("status IN ('published', 'hidden')", name="ck_place_reviews_status"),
    )
    op.create_index("ix_place_reviews_poi_id", "place_reviews", ["poi_id"])
    op.create_index("ix_place_reviews_user_id", "place_reviews", ["user_id"])
    op.create_index("ix_place_reviews_created_at", "place_reviews", ["created_at"])

    op.create_table(
        "place_external_ratings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("poi_id", sa.String(36), sa.ForeignKey("pois.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(24), nullable=False, server_default="google"),
        sa.Column("external_place_id", sa.String(255), nullable=True),
        sa.Column("matched_name", sa.String(300), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("rating_count", sa.Integer(), nullable=True),
        sa.Column("maps_uri", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("poi_id", "source", name="uq_place_external_ratings_poi_source"),
        sa.CheckConstraint("status IN ('ok', 'not_found', 'error')", name="ck_place_external_ratings_status"),
    )
    op.create_index("ix_place_external_ratings_poi_id", "place_external_ratings", ["poi_id"])

    op.create_table(
        "external_api_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("service", sa.String(40), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("service", "period", name="uq_external_api_usage_service_period"),
    )
    upgrade_permissions()


def upgrade_permissions() -> None:
    """The RBAC part on its own (the seed-matrix test replays it without the schema changes)."""
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
    op.drop_table("external_api_usage")
    op.drop_table("place_external_ratings")
    op.drop_table("place_reviews")
    with op.batch_alter_table("experience_reviews") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("moderated_at")
        batch.drop_column("moderation_note")
    with op.batch_alter_table("pois") as batch:
        batch.drop_column("google_place_id")
