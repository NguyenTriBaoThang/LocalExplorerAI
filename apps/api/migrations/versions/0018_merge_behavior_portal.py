"""Join the portal and consent-based recommendation branches.

Revision ID: 0018_merge_behavior_portal
Revises: 0017_merge_main_and_portal, 0015_admin_history_consent
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_merge_behavior_portal"
down_revision = ("0017_merge_main_and_portal", "0015_admin_history_consent")
branch_labels = None
depends_on = None


def upgrade() -> None:
    permissions = sa.table("permissions", sa.column("name", sa.String), sa.column("description", sa.String), sa.column("created_at", sa.DateTime(timezone=True)))
    grants = sa.table("role_permissions", sa.column("role_name", sa.String), sa.column("permission_name", sa.String))
    connection = op.get_bind()
    name = "recommendations:use"
    if connection.scalar(sa.select(permissions.c.name).where(permissions.c.name == name)) is None:
        connection.execute(permissions.insert().values(name=name, description="Manage own recommendation consent and interactions", created_at=sa.func.now()))
        connection.execute(grants.insert().values(role_name="traveler", permission_name=name))


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_name = 'recommendations:use'")
    op.execute("DELETE FROM permissions WHERE name = 'recommendations:use'")
