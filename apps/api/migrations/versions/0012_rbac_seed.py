"""Seed the role-permission matrix.

Revision ID: 0012_rbac_seed
Revises: 0011_auth_foundation

The data below is a frozen copy of the catalogue at the time of writing (migrations must not import code that
keeps changing). Permissions added to the code later are inserted by ``python -m scripts.sync_rbac``, which also
grants them to the roles that hold them by default.
"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op


revision = "0012_rbac_seed"
down_revision = "0011_auth_foundation"
branch_labels = None
depends_on = None

ROLES = {'admin': 'Platform administrator', 'provider': 'Experience provider', 'traveler': 'Signed-in visitor'}

PERMISSIONS = {'account:password': 'Change own password',
 'account:read': 'Read own profile',
 'account:update': 'Update own profile',
 'admin:ai_tools': 'Run administrator AI tools',
 'admin:audit': 'Read the system audit log',
 'admin:bot': 'Manage the chat bot',
 'admin:dashboard': 'Read the admin dashboard',
 'admin:duplicates': 'Detect and merge duplicate POIs',
 'admin:integrations': 'Manage third-party integration settings',
 'admin:models_3d': 'Save 3D model calibration',
 'admin:moderation': 'Review the moderation queue',
 'admin:place_import': 'Review and promote imported places',
 'admin:providers': 'List and create providers',
 'admin:rbac': 'View and edit the role-permission matrix',
 'admin:service_accounts': 'Manage service accounts',
 'admin:system': 'Manage system settings and metrics',
 'admin:users': 'List and update users',
 'booking:cancel': 'Cancel own unpaid booking',
 'booking:checkout': 'Start payment for own booking',
 'booking:create': 'Create a seat hold',
 'booking:history': "Read a booking's status history (participants only)",
 'booking:read': 'List own bookings',
 'chat:use': 'Use the AI concierge',
 'itinerary:compare': 'Compare two own itineraries',
 'itinerary:feedback': 'Submit and read feedback',
 'itinerary:list': 'List own itineraries',
 'itinerary:plan': 'Generate an itinerary',
 'itinerary:read': 'Open an itinerary (ownership is enforced per object)',
 'itinerary:share': 'Create or revoke a share link',
 'itinerary:versions': 'Read itinerary version history',
 'notification:read': 'Read own slot-cancellation notices',
 'ops:read': 'Read operational status (also grantable to service accounts)',
 'provider:audit': 'Read the provider audit log',
 'provider:booking_decide': 'Accept or reject bookings and cancellations',
 'provider:booking_read': 'Read booking requests addressed to the provider',
 'provider:evidence': 'Submit and read evidence',
 'provider:experience': 'Manage own experiences',
 'provider:poi': 'Manage own POIs',
 'provider:profile': 'Read own provider profile',
 'provider:slot': 'Manage own slots',
 'provider:slot_assist': 'Use the slot assistant',
 'replan:accept': 'Accept a replanning proposal',
 'replan:advise': 'Ask for replanning advice'}

GRANTS = {'admin': ['account:password',
           'account:read',
           'account:update',
           'admin:ai_tools',
           'admin:audit',
           'admin:bot',
           'admin:dashboard',
           'admin:duplicates',
           'admin:integrations',
           'admin:models_3d',
           'admin:moderation',
           'admin:place_import',
           'admin:providers',
           'admin:rbac',
           'admin:service_accounts',
           'admin:system',
           'admin:users',
           'booking:history',
           'booking:read',
           'ops:read'],
 'provider': ['account:password',
              'account:read',
              'account:update',
              'booking:history',
              'booking:read',
              'provider:audit',
              'provider:booking_decide',
              'provider:booking_read',
              'provider:evidence',
              'provider:experience',
              'provider:poi',
              'provider:profile',
              'provider:slot',
              'provider:slot_assist'],
 'traveler': ['account:password',
              'account:read',
              'account:update',
              'booking:cancel',
              'booking:checkout',
              'booking:create',
              'booking:history',
              'booking:read',
              'chat:use',
              'itinerary:compare',
              'itinerary:feedback',
              'itinerary:list',
              'itinerary:plan',
              'itinerary:read',
              'itinerary:share',
              'itinerary:versions',
              'notification:read',
              'replan:accept',
              'replan:advise']}


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    # Typed columns are required so the migration also renders correctly as offline SQL (alembic upgrade --sql).
    roles = sa.table("roles", sa.column("name", sa.String), sa.column("description", sa.String),
                     sa.column("is_system", sa.Boolean), sa.column("created_at", sa.DateTime(timezone=True)))
    permissions = sa.table("permissions", sa.column("name", sa.String), sa.column("description", sa.String),
                           sa.column("created_at", sa.DateTime(timezone=True)))
    role_permissions = sa.table("role_permissions", sa.column("role_name", sa.String), sa.column("permission_name", sa.String))
    op.bulk_insert(roles, [{"name": n, "description": d, "is_system": True, "created_at": now} for n, d in ROLES.items()])
    op.bulk_insert(permissions, [{"name": n, "description": d, "created_at": now} for n, d in PERMISSIONS.items()])
    op.bulk_insert(role_permissions, [{"role_name": r, "permission_name": p} for r, ps in GRANTS.items() for p in ps])


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions")
    op.execute("DELETE FROM permissions")
    op.execute("DELETE FROM roles")
