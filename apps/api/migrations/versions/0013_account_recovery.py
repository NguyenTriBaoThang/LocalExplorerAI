"""Account recovery and session management: itinerary claim tokens and the ``account:sessions`` permission.

Revision ID: 0013_account_recovery
Revises: 0012_rbac_seed

Password-reset and email-verification tokens reuse ``auth_tokens`` from 0011. Ticket itineraries created before
this revision have no claim token, so they can still be viewed through their share link but no longer claimed.
"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "0013_account_recovery"
down_revision = "0012_rbac_seed"
branch_labels = None
depends_on = None

# Frozen copy (see 0012): the permission and the roles that hold it by default.
PERMISSION = ("account:sessions", "List and revoke own sign-in sessions")
GRANTED_TO = ("admin", "provider", "traveler")


def upgrade() -> None:
    op.create_table(
        "itinerary_claim_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("itinerary_id", sa.String(36), sa.ForeignKey("itineraries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_itinerary_claim_tokens_itinerary_id", "itinerary_claim_tokens", ["itinerary_id"])
    op.create_index("ix_itinerary_claim_tokens_token_hash", "itinerary_claim_tokens", ["token_hash"], unique=True)

    permissions = sa.table("permissions", sa.column("name", sa.String), sa.column("description", sa.String),
                           sa.column("created_at", sa.DateTime(timezone=True)))
    role_permissions = sa.table("role_permissions", sa.column("role_name", sa.String), sa.column("permission_name", sa.String))
    op.bulk_insert(permissions, [{"name": PERMISSION[0], "description": PERMISSION[1], "created_at": datetime.now(timezone.utc)}])
    op.bulk_insert(role_permissions, [{"role_name": role, "permission_name": PERMISSION[0]} for role in GRANTED_TO])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM role_permissions WHERE permission_name = 'account:sessions'"))
    op.execute(sa.text("DELETE FROM permissions WHERE name = 'account:sessions'"))
    op.drop_index("ix_itinerary_claim_tokens_token_hash", table_name="itinerary_claim_tokens")
    op.drop_index("ix_itinerary_claim_tokens_itinerary_id", table_name="itinerary_claim_tokens")
    op.drop_table("itinerary_claim_tokens")
