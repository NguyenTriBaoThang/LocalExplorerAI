"""Add separate consent for identifiable customer activity history in admin.

Revision ID: 0015_admin_history_consent
Revises: 0014_personalization_eligibility
"""

import sqlalchemy as sa
from alembic import op


revision = "0015_admin_history_consent"
down_revision = "0014_personalization_eligibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recommendation_consents",
        sa.Column("admin_history_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "recommendation_interactions",
        sa.Column("admin_history_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("recommendation_interactions", "admin_history_eligible")
    op.drop_column("recommendation_consents", "admin_history_enabled")
