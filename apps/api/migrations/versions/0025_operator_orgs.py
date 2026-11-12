"""Add operator organisations (quote & margin copilot tenancy) and the operator role.

Revision ID: 0025_operator_orgs
Revises: 0024_itinerary_completion
"""

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0025_operator_orgs"
down_revision = "0024_itinerary_completion"
branch_labels = None
depends_on = None

# Snapshot at this revision, so later edits to app.api.permissions cannot change what this migration seeds.
NEW_PERMISSIONS = {
    "operator:quote": "Build and send quotes",
    "operator:rate_card": "Manage supplier rate cards",
    "operator:reconcile": "Reconcile supplier invoices",
    "operator:analytics": "Read margin and ROI analytics",
    "operator:settings": "Read and edit the operator organisation settings",
}
ACCOUNT_PERMISSIONS = ["account:read", "account:update", "account:password", "account:mfa", "account:sessions",
                       "booking:read", "booking:history"]


def upgrade() -> None:
    op.create_table(
        "operator_orgs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("margin_floor_pct", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("default_markup_pct", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("deposit_pct", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("quote_validity_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("ota_commission_pct", sa.Integer(), nullable=False, server_default="18"),
        sa.Column("manual_minutes_per_quote", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("settings", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_operator_orgs_slug"),
    )
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("operator_org_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_users_operator_org_id", "operator_orgs", ["operator_org_id"], ["id"], ondelete="SET NULL")
        batch.drop_constraint("ck_users_role", type_="check")
        batch.create_check_constraint("ck_users_role", "role IN ('traveler', 'provider', 'operator', 'admin')")
    op.create_index("ix_users_operator_org_id", "users", ["operator_org_id"], unique=False)
    upgrade_permissions()


def upgrade_permissions() -> None:
    now = datetime.now(timezone.utc)
    roles = sa.table("roles", sa.column("name", sa.String), sa.column("description", sa.String),
                     sa.column("is_system", sa.Boolean), sa.column("created_at", sa.DateTime(timezone=True)))
    permissions = sa.table("permissions", sa.column("name", sa.String), sa.column("description", sa.String),
                           sa.column("created_at", sa.DateTime(timezone=True)))
    role_permissions = sa.table("role_permissions", sa.column("role_name", sa.String), sa.column("permission_name", sa.String))
    op.bulk_insert(roles, [{"name": "operator", "description": "Tour operator", "is_system": True, "created_at": now}])
    op.bulk_insert(permissions, [{"name": n, "description": d, "created_at": now} for n, d in NEW_PERMISSIONS.items()])
    op.bulk_insert(role_permissions, [{"role_name": "operator", "permission_name": n} for n in ACCOUNT_PERMISSIONS + list(NEW_PERMISSIONS)])


def downgrade_permissions() -> None:
    names = ", ".join(f"'{name}'" for name in NEW_PERMISSIONS)
    op.execute(sa.text(f"DELETE FROM role_permissions WHERE role_name = 'operator' OR permission_name IN ({names})"))
    op.execute(sa.text(f"DELETE FROM permissions WHERE name IN ({names})"))
    op.execute(sa.text("DELETE FROM roles WHERE name = 'operator'"))


def downgrade() -> None:
    downgrade_permissions()
    op.drop_index("ix_users_operator_org_id", table_name="users")
    op.execute("UPDATE users SET role = 'traveler' WHERE role = 'operator'")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_role", type_="check")
        batch.create_check_constraint("ck_users_role", "role IN ('traveler', 'provider', 'admin')")
        batch.drop_constraint("fk_users_operator_org_id", type_="foreignkey")
        batch.drop_column("operator_org_id")
    op.drop_table("operator_orgs")
