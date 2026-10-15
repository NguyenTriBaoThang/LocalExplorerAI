"""Store source-backed POI metadata and image credits.

Revision ID: 0011_poi_source_details
Revises: 0010_place_import_staging
"""

import sqlalchemy as sa
from alembic import op


revision = "0011_poi_source_details"
down_revision = "0010_place_import_staging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pois",
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("pois", "details")
