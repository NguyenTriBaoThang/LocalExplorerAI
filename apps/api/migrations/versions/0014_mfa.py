"""Two-factor authentication: TOTP replay protection, the MFA login ticket and the ``account:mfa`` permission.

Revision ID: 0014_mfa
Revises: 0013_account_recovery

The tables ``user_mfa`` and ``mfa_recovery_codes`` already exist (0011). This revision adds the column that stops a
TOTP code from being used twice, allows ``auth_tokens.purpose = 'mfa_login'`` (the 5-minute ticket handed out between
the password step and the code step), and seeds the new permission for the roles that hold it by default.
"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "0014_mfa"
down_revision = "0013_account_recovery"
branch_labels = None
depends_on = None

PERMISSION = ("account:mfa", "Manage own two-factor authentication")
GRANTED_TO = ("admin", "provider", "traveler")
OLD_PURPOSES = "purpose IN ('reset_password', 'verify_email')"
NEW_PURPOSES = "purpose IN ('reset_password', 'verify_email', 'mfa_login')"


def upgrade() -> None:
    op.add_column("user_mfa", sa.Column("last_used_step", sa.BigInteger(), nullable=True))
    with op.batch_alter_table("auth_tokens") as batch:
        batch.drop_constraint("ck_auth_tokens_purpose", type_="check")
        batch.create_check_constraint("ck_auth_tokens_purpose", NEW_PURPOSES)

    permissions = sa.table("permissions", sa.column("name", sa.String), sa.column("description", sa.String),
                           sa.column("created_at", sa.DateTime(timezone=True)))
    role_permissions = sa.table("role_permissions", sa.column("role_name", sa.String), sa.column("permission_name", sa.String))
    op.bulk_insert(permissions, [{"name": PERMISSION[0], "description": PERMISSION[1], "created_at": datetime.now(timezone.utc)}])
    op.bulk_insert(role_permissions, [{"role_name": role, "permission_name": PERMISSION[0]} for role in GRANTED_TO])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM role_permissions WHERE permission_name = 'account:mfa'"))
    op.execute(sa.text("DELETE FROM permissions WHERE name = 'account:mfa'"))
    op.execute(sa.text("DELETE FROM auth_tokens WHERE purpose = 'mfa_login'"))   # rows the old constraint would reject
    with op.batch_alter_table("auth_tokens") as batch:
        batch.drop_constraint("ck_auth_tokens_purpose", type_="check")
        batch.create_check_constraint("ck_auth_tokens_purpose", OLD_PURPOSES)
    op.drop_column("user_mfa", "last_used_step")
