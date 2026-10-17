"""Join the trip planner / collaboration branch with place reviews, landmark stories and Meshy jobs.

Revision ID: 0022_merge_trip_planner_reviews
Revises: 0021_merge_place_reviews, 0020_trip_planner
"""

revision = "0022_merge_trip_planner_reviews"
down_revision = ("0021_merge_place_reviews", "0020_trip_planner")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
