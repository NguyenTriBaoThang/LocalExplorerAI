"""Track whether each interaction was captured under personalization consent.

Revision ID: 0014_personalization_eligibility
Revises: 0013_recommendation_behavior
"""

import sqlalchemy as sa
from alembic import op


revision = "0014_personalization_eligibility"
down_revision = "0013_recommendation_behavior"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recommendation_interactions",
        sa.Column("personalization_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("recommendation_interactions", "personalization_eligible")
