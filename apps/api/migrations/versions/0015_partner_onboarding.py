"""Partner self-registration: application fields and review trail on providers.

Revision ID: 0015_partner_onboarding
Revises: 0014_mfa

Until now only administrators created providers, and they were stored as ``pending`` although nothing reviewed them.
Those rows were vetted by the administrator who created them, so they become ``verified``; from this revision on
``pending`` means a self-registered partner waiting for review, and the provider portal blocks writes until approval.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "0015_partner_onboarding"
down_revision = "0014_mfa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("providers", sa.Column("business_type", sa.String(40), nullable=True))
    op.add_column("providers", sa.Column("tax_code", sa.String(40), nullable=True))
    op.add_column("providers", sa.Column("business_license_no", sa.String(80), nullable=True))
    op.add_column("providers", sa.Column("website", sa.String(300), nullable=True))
    op.add_column("providers", sa.Column("document_urls", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False, server_default="[]"))
    op.add_column("providers", sa.Column("application_note", sa.Text(), nullable=False, server_default=""))
    op.add_column("providers", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("providers", sa.Column("review_note", sa.Text(), nullable=False, server_default=""))
    op.add_column("providers", sa.Column("reviewed_by", sa.String(36), nullable=True))
    op.add_column("providers", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_providers_verification_status", "providers", ["verification_status"])
    op.execute(sa.text("UPDATE providers SET verification_status = 'verified' WHERE verification_status = 'pending'"))


def downgrade() -> None:
    op.drop_index("ix_providers_verification_status", table_name="providers")
    for column in ("reviewed_at", "reviewed_by", "review_note", "applied_at", "application_note", "document_urls",
                   "website", "business_license_no", "tax_code", "business_type"):
        op.drop_column("providers", column)
