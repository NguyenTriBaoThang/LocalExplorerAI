"""The application's permission catalogue and the default role -> permission grants.

Names are declared here (so routes reference constants and a test can check coverage); *which role holds which
permission* lives in the database (roles / permissions / role_permissions) and is seeded from DEFAULT_GRANTS.
The defaults reproduce the behaviour the routes had when they used ``require_roles(...)``.
"""

from app.auth import PermissionRegistry

registry = PermissionRegistry()


def _p(name: str, description: str) -> str:
    return registry.define(name, description)


class P:
    # Account (every signed-in role)
    ACCOUNT_READ = _p("account:read", "Read own profile")
    ACCOUNT_UPDATE = _p("account:update", "Update own profile")
    ACCOUNT_PASSWORD = _p("account:password", "Change own password")
    # Traveler
    ITINERARY_PLAN = _p("itinerary:plan", "Generate an itinerary")
    ITINERARY_READ = _p("itinerary:read", "Open an itinerary (ownership is enforced per object)")
    ITINERARY_LIST = _p("itinerary:list", "List own itineraries")
    ITINERARY_COMPARE = _p("itinerary:compare", "Compare two own itineraries")
    ITINERARY_VERSIONS = _p("itinerary:versions", "Read itinerary version history")
    ITINERARY_SHARE = _p("itinerary:share", "Create or revoke a share link")
    ITINERARY_FEEDBACK = _p("itinerary:feedback", "Submit and read feedback")
    NOTIFICATION_READ = _p("notification:read", "Read own slot-cancellation notices")
    CHAT_USE = _p("chat:use", "Use the AI concierge")
    REPLAN_ADVISE = _p("replan:advise", "Ask for replanning advice")
    REPLAN_ACCEPT = _p("replan:accept", "Accept a replanning proposal")
    BOOKING_CREATE = _p("booking:create", "Create a seat hold")
    BOOKING_READ = _p("booking:read", "List own bookings")
    BOOKING_CANCEL = _p("booking:cancel", "Cancel own unpaid booking")
    BOOKING_CHECKOUT = _p("booking:checkout", "Start payment for own booking")
    BOOKING_HISTORY = _p("booking:history", "Read a booking's status history (participants only)")
    # Provider
    PROVIDER_PROFILE = _p("provider:profile", "Read own provider profile")
    PROVIDER_EXPERIENCE = _p("provider:experience", "Manage own experiences")
    PROVIDER_POI = _p("provider:poi", "Manage own POIs")
    PROVIDER_EVIDENCE = _p("provider:evidence", "Submit and read evidence")
    PROVIDER_SLOT = _p("provider:slot", "Manage own slots")
    PROVIDER_AUDIT = _p("provider:audit", "Read the provider audit log")
    PROVIDER_BOOKING_READ = _p("provider:booking_read", "Read booking requests addressed to the provider")
    PROVIDER_BOOKING_DECIDE = _p("provider:booking_decide", "Accept or reject bookings and cancellations")
    PROVIDER_SLOT_ASSIST = _p("provider:slot_assist", "Use the slot assistant")
    # Administration
    ADMIN_DASHBOARD = _p("admin:dashboard", "Read the admin dashboard")
    ADMIN_USERS = _p("admin:users", "List and update users")
    ADMIN_PROVIDERS = _p("admin:providers", "List and create providers")
    ADMIN_MODERATION = _p("admin:moderation", "Review the moderation queue")
    ADMIN_DUPLICATES = _p("admin:duplicates", "Detect and merge duplicate POIs")
    ADMIN_PLACE_IMPORT = _p("admin:place_import", "Review and promote imported places")
    ADMIN_AUDIT = _p("admin:audit", "Read the system audit log")
    ADMIN_INTEGRATIONS = _p("admin:integrations", "Manage third-party integration settings")
    ADMIN_AI_TOOLS = _p("admin:ai_tools", "Run administrator AI tools")
    ADMIN_BOT = _p("admin:bot", "Manage the chat bot")
    ADMIN_SYSTEM = _p("admin:system", "Manage system settings and metrics")
    ADMIN_MODELS_3D = _p("admin:models_3d", "Save 3D model calibration")
    ADMIN_RBAC = _p("admin:rbac", "View and edit the role-permission matrix")
    ADMIN_SERVICE_ACCOUNTS = _p("admin:service_accounts", "Manage service accounts")
    OPS_READ = _p("ops:read", "Read operational status (also grantable to service accounts)")


_ACCOUNT = [P.ACCOUNT_READ, P.ACCOUNT_UPDATE, P.ACCOUNT_PASSWORD, P.BOOKING_READ, P.BOOKING_HISTORY]
DEFAULT_GRANTS: dict[str, list[str]] = {
    "traveler": _ACCOUNT + [
        P.ITINERARY_PLAN, P.ITINERARY_READ, P.ITINERARY_LIST, P.ITINERARY_COMPARE, P.ITINERARY_VERSIONS, P.ITINERARY_SHARE,
        P.ITINERARY_FEEDBACK, P.NOTIFICATION_READ, P.CHAT_USE, P.REPLAN_ADVISE, P.REPLAN_ACCEPT, P.BOOKING_CREATE,
        P.BOOKING_CANCEL, P.BOOKING_CHECKOUT,
    ],
    "provider": _ACCOUNT + [
        P.PROVIDER_PROFILE, P.PROVIDER_EXPERIENCE, P.PROVIDER_POI, P.PROVIDER_EVIDENCE, P.PROVIDER_SLOT, P.PROVIDER_AUDIT,
        P.PROVIDER_BOOKING_READ, P.PROVIDER_BOOKING_DECIDE, P.PROVIDER_SLOT_ASSIST,
    ],
    "admin": _ACCOUNT + [name for name in registry.names() if name.startswith("admin:")] + [P.OPS_READ],
}
SYSTEM_ROLES = {"traveler": "Signed-in visitor", "provider": "Experience provider", "admin": "Platform administrator"}

# Permissions an API key (service account) may ever hold. Everything else is for people.
SERVICE_GRANTABLE: frozenset[str] = frozenset({P.OPS_READ})
# The admin role must always keep these, so nobody can lock every administrator out of access management.
ADMIN_REQUIRED: frozenset[str] = frozenset({P.ADMIN_RBAC, P.ADMIN_USERS, P.ADMIN_SERVICE_ACCOUNTS})
