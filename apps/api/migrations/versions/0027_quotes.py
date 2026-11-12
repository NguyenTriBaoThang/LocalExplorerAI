"""Add quotes, quote revisions and tour templates for the quote copilot.

Revision ID: 0027_quotes
Revises: 0026_operator_docs_rate_cards
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0027_quotes"
down_revision = "0026_operator_docs_rate_cards"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "tour_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("operator_orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("itinerary", JSON, nullable=False),
        sa.Column("meal_plan", JSON, nullable=False),
        sa.UniqueConstraint("org_id", "code", name="uq_tour_templates_code"),
    )
    op.create_index("ix_tour_templates_org_id", "tour_templates", ["org_id"])
    op.create_table(
        "quotes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("operator_orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("channel", sa.String(length=20), nullable=False, server_default="portal"),
        sa.Column("customer_name", sa.String(length=180), nullable=True),
        sa.Column("customer_contact", sa.String(length=255), nullable=True),
        sa.Column("raw_message", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request", JSON, nullable=False),
        sa.Column("itinerary", JSON, nullable=False),
        sa.Column("cost", JSON, nullable=False),
        sa.Column("pricing", JSON, nullable=False),
        sa.Column("cost_total_vnd", sa.BigInteger(), nullable=False),
        sa.Column("price_vnd", sa.BigInteger(), nullable=True),
        sa.Column("price_mode", sa.String(length=20), nullable=False, server_default="balanced"),
        sa.Column("rate_card_versions", JSON, nullable=False),
        sa.Column("margin_floor_pct", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("public_token_hash", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_reason", sa.String(length=255), nullable=True),
        sa.Column("actual_cost_vnd", sa.BigInteger(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "code", name="uq_quotes_org_code"),
        sa.CheckConstraint("status IN ('draft', 'sent', 'viewed', 'accepted', 'deposit_paid', 'won', 'lost', 'expired')", name="ck_quotes_status"),
        sa.CheckConstraint("channel IN ('portal', 'zalo', 'telegram')", name="ck_quotes_channel"),
    )
    op.create_index("ix_quotes_org_id", "quotes", ["org_id"])
    op.create_index("ix_quotes_status", "quotes", ["status"])
    op.create_index("ix_quotes_public_token_hash", "quotes", ["public_token_hash"])
    op.create_table(
        "quote_revisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("quote_id", sa.String(length=36), sa.ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("operator_orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", JSON, nullable=False),
        sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("quote_id", "revision", name="uq_quote_revisions_rev"),
    )
    op.create_index("ix_quote_revisions_quote_id", "quote_revisions", ["quote_id"])
    op.create_index("ix_quote_revisions_org_id", "quote_revisions", ["org_id"])


def downgrade() -> None:
    op.drop_table("quote_revisions")
    op.drop_table("quotes")
    op.drop_table("tour_templates")
