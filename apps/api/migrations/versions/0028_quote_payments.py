"""Let payment_transactions pay a quote deposit instead of a booking.

Revision ID: 0028_quote_payments
Revises: 0027_quotes
"""

import sqlalchemy as sa
from alembic import op

revision = "0028_quote_payments"
down_revision = "0027_quotes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("payment_transactions") as batch:
        batch.alter_column("booking_id", existing_type=sa.String(length=36), nullable=True)
        batch.add_column(sa.Column("quote_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_payment_transactions_quote_id", "quotes", ["quote_id"], ["id"], ondelete="RESTRICT")
        batch.create_check_constraint("ck_payment_exactly_one_target", "(booking_id IS NULL) <> (quote_id IS NULL)")
    op.create_index("ix_payment_transactions_quote_id", "payment_transactions", ["quote_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_transactions_quote_id", table_name="payment_transactions")
    op.execute("DELETE FROM payment_transactions WHERE quote_id IS NOT NULL")
    with op.batch_alter_table("payment_transactions") as batch:
        batch.drop_constraint("ck_payment_exactly_one_target", type_="check")
        batch.drop_constraint("fk_payment_transactions_quote_id", type_="foreignkey")
        batch.drop_column("quote_id")
        batch.alter_column("booking_id", existing_type=sa.String(length=36), nullable=False)
