"""Store admin-managed integration settings as encrypted values.

Revision ID: 0009_integration_secrets
Revises: 0008_operations_notifications
"""

import sqlalchemy as sa
from alembic import op


revision = "0009_integration_secrets"
down_revision = "0008_operations_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_secrets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("service", sa.String(40), nullable=False),
        sa.Column("config_key", sa.String(80), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("service", "config_key", name="uq_integration_service_key"),
    )
    op.create_index("ix_integration_secrets_service", "integration_secrets", ["service"])


def downgrade() -> None:
    op.drop_index("ix_integration_secrets_service", table_name="integration_secrets")
    op.drop_table("integration_secrets")
