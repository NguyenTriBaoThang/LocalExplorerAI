"""Add owner-approved itinerary collaboration."""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0019_itinerary_collaboration"
down_revision = "0018_web_push_notifications"
branch_labels = None
depends_on = None

PERMISSIONS = {
    "itinerary:collaborate": ("View and propose changes to an invited itinerary", ("traveler",)),
}


def upgrade() -> None:
    op.add_column("itineraries", sa.Column("collaboration_token_hash", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_itineraries_collaboration_token_hash",
        "itineraries",
        ["collaboration_token_hash"],
        unique=True,
    )

    op.create_table(
        "itinerary_edit_proposals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("itinerary_id", sa.String(length=36), nullable=False),
        sa.Column("proposer_id", sa.String(length=36), nullable=True),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("proposed_stops", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'stale')",
            name="ck_itinerary_edit_proposal_status",
        ),
        sa.ForeignKeyConstraint(["itinerary_id"], ["itineraries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["proposer_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_itinerary_edit_proposals_itinerary_id", "itinerary_edit_proposals", ["itinerary_id"])
    op.create_index("ix_itinerary_edit_proposals_proposer_id", "itinerary_edit_proposals", ["proposer_id"])
    op.create_index("ix_itinerary_edit_proposals_status", "itinerary_edit_proposals", ["status"])
    op.create_index("ix_itinerary_edit_proposals_reviewed_by", "itinerary_edit_proposals", ["reviewed_by"])
    op.create_index(
        "ix_itinerary_edit_proposal_owner_queue",
        "itinerary_edit_proposals",
        ["itinerary_id", "status", "created_at"],
    )

    upgrade_permissions()


def upgrade_permissions() -> None:
    """Grant signed-in travelers access to invited itinerary collaboration."""
    permissions = sa.table("permissions", sa.column("name", sa.String), sa.column("description", sa.String),
                           sa.column("created_at", sa.DateTime(timezone=True)))
    role_permissions = sa.table("role_permissions", sa.column("role_name", sa.String), sa.column("permission_name", sa.String))
    now = datetime.now(timezone.utc)
    op.bulk_insert(permissions, [{"name": name, "description": description, "created_at": now} for name, (description, _) in PERMISSIONS.items()])
    op.bulk_insert(role_permissions, [{"role_name": role, "permission_name": name} for name, (_, roles) in PERMISSIONS.items() for role in roles])


def downgrade_permissions() -> None:
    names = ", ".join(f"'{name}'" for name in PERMISSIONS)
    op.execute(sa.text(f"DELETE FROM role_permissions WHERE permission_name IN ({names})"))
    op.execute(sa.text(f"DELETE FROM permissions WHERE name IN ({names})"))


def downgrade() -> None:
    downgrade_permissions()
    op.drop_index("ix_itinerary_edit_proposal_owner_queue", table_name="itinerary_edit_proposals")
    op.drop_index("ix_itinerary_edit_proposals_reviewed_by", table_name="itinerary_edit_proposals")
    op.drop_index("ix_itinerary_edit_proposals_status", table_name="itinerary_edit_proposals")
    op.drop_index("ix_itinerary_edit_proposals_proposer_id", table_name="itinerary_edit_proposals")
    op.drop_index("ix_itinerary_edit_proposals_itinerary_id", table_name="itinerary_edit_proposals")
    op.drop_table("itinerary_edit_proposals")
    op.drop_index("ix_itineraries_collaboration_token_hash", table_name="itineraries")
    op.drop_column("itineraries", "collaboration_token_hash")
