"""Join the two merge heads created by integrating sit and uat.

Revision ID: 0023_merge_sit_into_main
Revises: 0022_merge_trip_planner_reviews, 0022_merge_trip_runtime
"""

revision = "0023_merge_sit_into_main"
down_revision = ("0022_merge_trip_planner_reviews", "0022_merge_trip_runtime")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
