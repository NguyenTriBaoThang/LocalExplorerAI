"""Add cost_actuals: quoted vs invoiced cost per line for post-tour reconciliation.

Revision ID: 0029_cost_actuals
Revises: 0028_quote_payments
"""

import sqlalchemy as sa
from alembic import op

revision = "0029_cost_actuals"
down_revision = "0028_quote_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cost_actuals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("operator_orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quote_id", sa.String(length=36), sa.ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("operator_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("quoted_vnd", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("actual_vnd", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("variance_vnd", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(length=20), nullable=True),
        sa.Column("matched_cost_line", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("reason IS NULL OR reason IN ('price_change', 'pax_change', 'unplanned', 'surcharge', 'not_used', 'other')", name="ck_cost_actuals_reason"),
    )
    op.create_index("ix_cost_actuals_org_id", "cost_actuals", ["org_id"])
    op.create_index("ix_cost_actuals_quote_id", "cost_actuals", ["quote_id"])


def downgrade() -> None:
    op.drop_table("cost_actuals")
