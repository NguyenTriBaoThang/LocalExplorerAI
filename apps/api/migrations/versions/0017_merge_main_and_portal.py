"""Merge the sourced-catalog line (0012_slot_timestamps_utc) with the auth/portal line (0016_portal_platform).

Revision ID: 0017_merge_main_and_portal
Revises: 0012_slot_timestamps_utc, 0016_portal_platform

Schema-only merge: the two lines touch different tables/columns, so there is nothing to apply.
"""

revision = "0017_merge_main_and_portal"
down_revision = ("0012_slot_timestamps_utc", "0016_portal_platform")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
