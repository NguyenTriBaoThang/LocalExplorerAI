"""Add operator documents (uploaded rate sheets / invoices) and versioned supplier rate cards.

Revision ID: 0026_operator_docs_rate_cards
Revises: 0025_operator_orgs
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0026_operator_docs_rate_cards"
down_revision = "0025_operator_orgs"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "operator_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("operator_orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=400), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="uploaded"),
        sa.Column("extracted", JSON, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "sha256", name="uq_operator_documents_org_sha256"),
        sa.CheckConstraint("kind IN ('rate_sheet', 'invoice')", name="ck_operator_documents_kind"),
        sa.CheckConstraint("status IN ('uploaded', 'extracted', 'failed', 'approved', 'rejected')", name="ck_operator_documents_status"),
    )
    op.create_index("ix_operator_documents_org_id", "operator_documents", ["org_id"])
    op.create_table(
        "rate_cards",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("operator_orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier", sa.String(length=180), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source_document_id", sa.String(length=36), sa.ForeignKey("operator_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "supplier", "category", "version", name="uq_rate_cards_version"),
        sa.CheckConstraint("category IN ('vehicle', 'guide', 'meal', 'ticket', 'hotel', 'surcharge')", name="ck_rate_cards_category"),
        sa.CheckConstraint("status IN ('draft', 'active', 'archived')", name="ck_rate_cards_status"),
    )
    op.create_index("ix_rate_cards_org_id", "rate_cards", ["org_id"])
    op.create_table(
        "rate_card_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("card_id", sa.String(length=36), sa.ForeignKey("rate_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("operator_orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=True),
        sa.Column("max_pax", sa.Integer(), nullable=True),
        sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
        sa.Column("experience_id", sa.String(length=36), sa.ForeignKey("experiences.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conditions", JSON, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.UniqueConstraint("card_id", "code", name="uq_rate_card_items_code"),
        sa.CheckConstraint("unit IN ('per_km', 'per_day', 'per_trip', 'per_pax', 'per_room_night', 'pct')", name="ck_rate_card_items_unit"),
    )
    op.create_index("ix_rate_card_items_card_id", "rate_card_items", ["card_id"])
    op.create_index("ix_rate_card_items_org_id", "rate_card_items", ["org_id"])


def downgrade() -> None:
    op.drop_table("rate_card_items")
    op.drop_table("rate_cards")
    op.drop_table("operator_documents")
