"""Add opt-in and consent-gated recommendation interaction storage.

Revision ID: 0013_recommendation_behavior
Revises: 0012_slot_timestamps_utc
"""

import sqlalchemy as sa
from alembic import op


revision = "0013_recommendation_behavior"
down_revision = "0012_slot_timestamps_utc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_consents",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("personalization_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("model_training_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("consent_version", sa.String(40), nullable=False, server_default="behavior-v1"),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "recommendation_interactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("experience_id", sa.String(36), sa.ForeignKey("experiences.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("context_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("candidate_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("model_training_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("consent_version", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('impression', 'selected', 'dismissed')",
            name="ck_recommendation_interactions_event_type",
        ),
        sa.CheckConstraint("position IS NULL OR position >= 0", name="ck_recommendation_interactions_position"),
    )
    op.create_index(
        "ix_recommendation_interactions_user_created",
        "recommendation_interactions",
        ["user_id", "created_at"],
    )
    op.create_index("ix_recommendation_interactions_request", "recommendation_interactions", ["request_id"])
    op.create_index("ix_recommendation_interactions_training", "recommendation_interactions", ["model_training_eligible", "created_at"])
    op.create_index("ix_recommendation_interactions_experience_id", "recommendation_interactions", ["experience_id"])
    op.create_index("ix_recommendation_interactions_created_at", "recommendation_interactions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_recommendation_interactions_created_at", table_name="recommendation_interactions")
    op.drop_index("ix_recommendation_interactions_experience_id", table_name="recommendation_interactions")
    op.drop_index("ix_recommendation_interactions_training", table_name="recommendation_interactions")
    op.drop_index("ix_recommendation_interactions_request", table_name="recommendation_interactions")
    op.drop_index("ix_recommendation_interactions_user_created", table_name="recommendation_interactions")
    op.drop_table("recommendation_interactions")
    op.drop_table("recommendation_consents")
