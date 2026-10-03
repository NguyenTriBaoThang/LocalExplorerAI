"""Add durable notification outbox and worker execution history.

Revision ID: 0008_operations_notifications
Revises: 0007_booking_payments
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_operations_notifications"
down_revision = "0007_booking_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("recipient_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recipient_email", sa.String(254), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False, server_default="email"),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("channel IN ('email')", name="ck_notification_channel"),
        sa.CheckConstraint("status IN ('queued', 'sending', 'retry', 'sent', 'failed')", name="ck_notification_status"),
        sa.CheckConstraint("attempts >= 0", name="ck_notification_attempts"),
        sa.UniqueConstraint("idempotency_key", name="uq_notification_idempotency_key"),
    )
    for name, column in (
        ("ix_notification_deliveries_recipient_user_id", "recipient_user_id"),
        ("ix_notification_deliveries_event_id", "event_id"),
        ("ix_notification_deliveries_booking_id", "booking_id"),
        ("ix_notification_deliveries_status", "status"),
        ("ix_notification_deliveries_available_at", "available_at"),
        ("ix_notification_deliveries_created_at", "created_at"),
    ):
        op.create_index(name, "notification_deliveries", [column])
    op.create_index("ix_notification_queue", "notification_deliveries", ["status", "available_at", "created_at"])

    op.create_table(
        "ops_job_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_name", sa.String(80), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.String(1000), nullable=True),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_ops_job_status"),
    )
    op.create_index("ix_ops_job_runs_job_name", "ops_job_runs", ["job_name"])
    op.create_index("ix_ops_job_runs_status", "ops_job_runs", ["status"])
    op.create_index("ix_ops_job_runs_started_at", "ops_job_runs", ["started_at"])
    op.create_index("ix_ops_job_name_started", "ops_job_runs", ["job_name", "started_at"])


def downgrade() -> None:
    op.drop_table("ops_job_runs")
    op.drop_table("notification_deliveries")
