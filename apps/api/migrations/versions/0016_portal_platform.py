"""Portal platform: curated place details, site content, page-view analytics and experience reviews.

Revision ID: 0016_portal_platform
Revises: 0015_partner_onboarding

Adds the data the partner/admin portal manages and the traveler web reads: visitor info on POIs, home-page banners,
articles and place collections, privacy-preserving page views (hashed browser id, no IP) and booking-based reviews.
"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "0016_portal_platform"
down_revision = "0015_partner_onboarding"
branch_labels = None
depends_on = None

JSON_DOCUMENT = sa.JSON().with_variant(JSONB(), "postgresql")
# Frozen copy (see 0012): new permissions and the roles that hold them by default.
PERMISSIONS = {
    "review:write": ("Review an experience after attending it", ("traveler",)),
    "provider:reviews": ("Read and reply to reviews of own experiences", ("provider",)),
    "provider:analytics": ("Read views and conversion of own experiences", ("provider",)),
    "admin:places": ("Create, edit, publish and hide places and landmarks", ("admin",)),
    "admin:content": ("Manage banners, articles and collections on the traveler web", ("admin",)),
    "admin:analytics": ("Read traffic analytics", ("admin",)),
}


def upgrade() -> None:
    op.add_column("pois", sa.Column("opening_hours", sa.String(200), nullable=True))
    op.add_column("pois", sa.Column("ticket_info", sa.String(200), nullable=True))
    op.add_column("pois", sa.Column("tags", JSON_DOCUMENT, nullable=False, server_default="[]"))
    op.add_column("pois", sa.Column("is_landmark", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("pois", sa.Column("source_url", sa.String(1000), nullable=True))

    op.create_table(
        "site_banners",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("subtitle", sa.String(300), nullable=False, server_default=""),
        sa.Column("image_url", sa.String(1000), nullable=False),
        sa.Column("link_url", sa.String(500), nullable=False, server_default="/"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "site_articles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(220), nullable=False),
        sa.Column("slug", sa.String(220), nullable=False),
        sa.Column("excerpt", sa.String(600), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("cover_url", sa.String(1000), nullable=False, server_default=""),
        sa.Column("category", sa.String(60), nullable=False, server_default="Cẩm nang"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_site_articles_slug"),
        sa.CheckConstraint("status IN ('draft', 'published')", name="ck_site_articles_status"),
    )
    op.create_index("ix_site_articles_slug", "site_articles", ["slug"])
    op.create_index("ix_site_articles_status", "site_articles", ["status"])
    op.create_table(
        "site_collections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.String(600), nullable=False, server_default=""),
        sa.Column("place_ids", JSON_DOCUMENT, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "page_views",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("visitor_hash", sa.String(64), nullable=False),
        sa.Column("session_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("path", sa.String(300), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("referrer_host", sa.String(200), nullable=True),
        sa.Column("device", sa.String(16), nullable=False, server_default="desktop"),
    )
    op.create_index("ix_page_views_occurred_at", "page_views", ["occurred_at"])
    op.create_index("ix_page_views_visitor_hash", "page_views", ["visitor_hash"])
    op.create_index("ix_page_views_entity", "page_views", ["entity_type", "entity_id", "occurred_at"])
    op.create_table(
        "experience_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("experience_id", sa.String(36), sa.ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("reply", sa.Text(), nullable=True),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="published"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("booking_id", name="uq_experience_reviews_booking"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_experience_reviews_rating"),
        sa.CheckConstraint("status IN ('published', 'hidden')", name="ck_experience_reviews_status"),
    )
    op.create_index("ix_experience_reviews_experience_id", "experience_reviews", ["experience_id"])
    op.create_index("ix_experience_reviews_provider_id", "experience_reviews", ["provider_id"])
    op.create_index("ix_experience_reviews_created_at", "experience_reviews", ["created_at"])

    upgrade_permissions()


def upgrade_permissions() -> None:
    """The RBAC part of this revision on its own (the seed-matrix test replays it without the schema changes)."""
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
    op.drop_table("experience_reviews")
    op.drop_table("page_views")
    op.drop_table("site_collections")
    op.drop_table("site_articles")
    op.drop_table("site_banners")
    for column in ("source_url", "is_landmark", "tags", "ticket_info", "opening_hours"):
        op.drop_column("pois", column)
