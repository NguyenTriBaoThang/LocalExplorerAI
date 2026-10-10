"""Normalize legacy HCMC-local SQLite slot timestamps to UTC.

Revision ID: 0012_slot_timestamps_utc
Revises: 0011_poi_source_details
"""

import sqlalchemy as sa
from alembic import op


revision = "0012_slot_timestamps_utc"
down_revision = "0011_poi_source_details"
branch_labels = None
depends_on = None

LEGACY_SLOT_SOURCE = "https://hcmc.gov.vn/slots/%"


def _adjust_legacy_sqlite_slots(offset: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        # PostgreSQL converted the original aware Asia/Ho_Chi_Minh values to UTC
        # when they were inserted, so only SQLite needs this legacy correction.
        return

    bind.execute(sa.text(
        """
        UPDATE experience_slots
        SET start_at = datetime(start_at, :offset),
            end_at = datetime(end_at, :offset),
            expires_at = CASE WHEN expires_at IS NULL THEN NULL ELSE datetime(expires_at, :offset) END
        WHERE id IN (
            SELECT target_id FROM evidence
            WHERE target_type = 'slot' AND source_uri LIKE :source_pattern
        )
        """
    ), {"offset": offset, "source_pattern": LEGACY_SLOT_SOURCE})
    bind.execute(sa.text(
        """
        UPDATE evidence
        SET expires_at = datetime(expires_at, :offset)
        WHERE target_type = 'slot' AND source_uri LIKE :source_pattern
          AND expires_at IS NOT NULL
        """
    ), {"offset": offset, "source_pattern": LEGACY_SLOT_SOURCE})


def upgrade() -> None:
    _adjust_legacy_sqlite_slots("-7 hours")


def downgrade() -> None:
    _adjust_legacy_sqlite_slots("+7 hours")
