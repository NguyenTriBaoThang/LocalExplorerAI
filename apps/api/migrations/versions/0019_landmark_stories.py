"""Versioned editorial stories for 3D landmarks."""
from alembic import op
import sqlalchemy as sa

revision = "0019_landmark_stories"
down_revision = "0018_merge_behavior_portal"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "landmark_stories",
        sa.Column("model_id", sa.String(64), primary_key=True),
        sa.Column("draft", sa.JSON(), nullable=False),
        sa.Column("published", sa.JSON(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("workflow", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("landmark_stories")
