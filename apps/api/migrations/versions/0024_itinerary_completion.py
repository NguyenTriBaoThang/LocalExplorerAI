"""Track when a traveler confirms that an itinerary was completed.

Revision ID: 0024_itinerary_completion
Revises: 0023_merge_sit_into_main
"""

import sqlalchemy as sa
from alembic import op


revision = "0024_itinerary_completion"
down_revision = "0023_merge_sit_into_main"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("itineraries", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("itineraries", "completed_at")
