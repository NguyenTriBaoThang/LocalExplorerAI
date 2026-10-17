"""Add opt-in web-push subscriptions and booking notification delivery."""

from alembic import op
import sqlalchemy as sa


revision = "0018_web_push_notifications"
down_revision = "0017_merge_main_and_portal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notification_deliveries") as batch:
        batch.drop_constraint("ck_notification_channel", type_="check")
        batch.create_check_constraint("ck_notification_channel", "channel IN ('email', 'webpush')")

    op.create_table(
        "web_push_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("endpoint", sa.String(length=2048), nullable=False),
        sa.Column("p256dh_key", sa.String(length=256), nullable=False),
        sa.Column("auth_key", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint", name="uq_web_push_subscription_endpoint"),
    )
    op.create_index("ix_web_push_user_active", "web_push_subscriptions", ["user_id", "is_active"])


def downgrade() -> None:
    op.execute("DELETE FROM notification_deliveries WHERE channel = 'webpush'")
    with op.batch_alter_table("notification_deliveries") as batch:
        batch.drop_constraint("ck_notification_channel", type_="check")
        batch.create_check_constraint("ck_notification_channel", "channel IN ('email')")
    op.drop_index("ix_web_push_user_active", table_name="web_push_subscriptions")
    op.drop_table("web_push_subscriptions")
