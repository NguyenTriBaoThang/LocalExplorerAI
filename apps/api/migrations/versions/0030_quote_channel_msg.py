"""Add quotes.channel_message_id with a unique (org, channel, message id) so a redelivered bot message cannot create a second quote.

Revision ID: 0030_quote_channel_msg
Revises: 0029_cost_actuals
"""

import sqlalchemy as sa
from alembic import op

revision = "0030_quote_channel_msg"
down_revision = "0029_cost_actuals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("quotes") as batch:
        batch.add_column(sa.Column("channel_message_id", sa.String(length=120), nullable=True))
        batch.create_unique_constraint("uq_quotes_org_channel_msg", ["org_id", "channel", "channel_message_id"])


def downgrade() -> None:
    with op.batch_alter_table("quotes") as batch:
        batch.drop_constraint("uq_quotes_org_channel_msg", type_="unique")
        batch.drop_column("channel_message_id")
