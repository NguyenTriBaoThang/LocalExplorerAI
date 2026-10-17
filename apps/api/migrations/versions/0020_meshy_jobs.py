"""Durable Meshy jobs; drafts remain private until published."""
from alembic import op
import sqlalchemy as sa
revision = "0020_meshy_jobs"
down_revision = "0019_landmark_stories"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("meshy_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_key", sa.String(36), unique=True, nullable=False),
        sa.Column("parent_id", sa.String(36), unique=True),
        sa.Column("task_id", sa.String(100)),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("previewed_at", sa.DateTime(timezone=True)))
    for col in ("actor_id", "status", "created_at"):
        op.create_index("ix_meshy_jobs_" + col, "meshy_jobs", [col])

def downgrade():
    op.drop_table("meshy_jobs")
