"""Phase 3: every route declares its protection; the matrix lives in the database; service accounts replace the shared key."""

from sqlalchemy import select

from app.api.permissions import DEFAULT_GRANTS, SERVICE_GRANTABLE, registry
from app.models.auth_entities import RolePermission, ServiceAccount
from app.models.entities import AuditLog
from app.services.rbac_service import create_service_account, sync_catalog
from tests.helpers import bearer_for, make_user
from tests.route_inventory import inventory

# Adding a public route must be a conscious, reviewed change to this list.
PUBLIC_ROUTES = {
    ("push_notifications", "GET", "/api/notifications/push/vapid-public-key"),
    ("admin_bot", "GET", "/api/bot/webhook"), ("admin_bot", "POST", "/api/bot/webhook"),
    ("ai", "GET", "/api/ai/prompts"),
    ("auth", "GET", "/api/auth/google/callback"), ("auth", "GET", "/api/auth/google/start"), ("auth", "GET", "/api/auth/google/status"),
    ("auth", "POST", "/api/auth/claim-ticket"), ("auth", "POST", "/api/auth/login"), ("auth", "POST", "/api/auth/login/mfa"), ("auth", "POST", "/api/auth/logout"),
    ("auth", "POST", "/api/auth/refresh"), ("auth", "POST", "/api/auth/partner/register"), ("auth", "POST", "/api/auth/register"),
    # Phase 4: anonymous by nature; each is authenticated by a single-use emailed token or reveals nothing.
    ("auth", "POST", "/api/auth/password/forgot"), ("auth", "POST", "/api/auth/password/reset"), ("auth", "POST", "/api/auth/email/verify"),
    # Portal platform: the traveler web reads published content and reviews, and sends anonymous page views.
    ("analytics", "POST", "/api/analytics/pageview"), ("reviews", "GET", "/api/experiences/{experience_id}/reviews"),
    ("site_content", "GET", "/api/content/home"), ("site_content", "GET", "/api/content/articles"), ("site_content", "GET", "/api/content/articles/{slug}"),
    ("bookings", "GET", "/api/payments/momo/return"), ("bookings", "GET", "/api/payments/status"), ("bookings", "GET", "/api/payments/vnpay/ipn"),
    ("bookings", "GET", "/api/payments/vnpay/return"), ("bookings", "POST", "/api/payments/momo/ipn"),
    ("catalog", "GET", "/api/experience-search"), ("catalog", "GET", "/api/experiences"), ("catalog", "GET", "/api/experiences/{experience_id}"),
    ("catalog", "GET", "/api/experiences/{experience_id}/slots"), ("catalog", "GET", "/api/pois"), ("catalog", "GET", "/api/pois/{poi_id}"), ("catalog", "GET", "/api/partners"), ("catalog", "GET", "/api/partners/{slug}"),
    ("chat", "GET", "/api/chat/status"),
    ("health", "GET", "/health"), ("health", "GET", "/ready"),
    ("main", "GET", "/"),
    ("ml", "GET", "/api/ml/status"), ("ml", "POST", "/api/ml/flood-risk"), ("ml", "POST", "/api/ml/rank-experiences"),
    ("models_3d", "GET", "/models-3d/calibration"), ("models_3d", "GET", "/models-3d/calibration/{model_id}"),
    ("planner", "GET", "/api/shared/itineraries/{share_token}"),
    # The high-entropy invite is the credential for read-only access; proposing still needs a traveler session.
    ("collaboration", "GET", "/api/collaborations/{token}"),
    ("routing", "GET", "/api/geocoding/forward"), ("routing", "GET", "/api/routing/capabilities"),
}


def test_every_route_declares_exactly_one_access_policy():
    rows = inventory()
    assert len(rows) > 100                                  # guards against the inventory silently finding nothing
    undeclared = [(m, meth, p) for m, meth, p, pols in rows if len(pols) == 0]
    ambiguous = [(m, meth, p) for m, meth, p, pols in rows if len(pols) > 1]
    assert not undeclared, f"routes with no public()/require(): {undeclared}"
    assert not ambiguous, f"routes with several policies: {ambiguous}"


def test_the_set_of_public_routes_is_exactly_the_reviewed_list():
    actual = {(m, meth, p) for m, meth, p, pols in inventory() if pols[0].kind == "public"}
    assert actual - PUBLIC_ROUTES == set(), "new public routes must be added to PUBLIC_ROUTES after review"
    assert PUBLIC_ROUTES - actual == set(), "routes listed as public are no longer public; update PUBLIC_ROUTES"


def test_public_routes_state_why():
    reasons = [pols[0].reason for _, _, _, pols in inventory() if pols[0].kind == "public"]
    assert all(r and len(r) > 8 for r in reasons)


def test_every_required_permission_is_granted_to_somebody_by_default():
    granted = set().union(*map(set, DEFAULT_GRANTS.values()))
    needed = {pols[0].permission for _, _, _, pols in inventory() if pols[0].kind == "require"}
    assert needed <= registry.names()
    assert needed <= granted | SERVICE_GRANTABLE, f"permissions nobody holds: {needed - granted}"
    assert registry.names() <= granted, f"catalogue permissions that no route needs or no role holds: {registry.names() - granted}"


def test_default_grants_keep_the_original_role_boundaries(client, db_session):
    admin, provider, traveler = (make_user(db_session, r) for r in ("admin", "provider", "traveler"))
    checks = [
        (traveler, "/api/admin/dashboard", 403), (provider, "/api/admin/dashboard", 403), (admin, "/api/admin/dashboard", 200),
        (traveler, "/api/provider/me", 403), (admin, "/api/provider/me", 403),
        (traveler, "/api/ops/status", 403), (admin, "/api/ops/status", 200),
    ]
    for user, path, expected in checks:
        assert client.get(path, headers=bearer_for(user)).status_code == expected, (user.role, path)
    assert client.get("/api/admin/dashboard").status_code == 401        # anonymous


def test_matrix_is_visible_to_admins_only(client, db_session):
    assert client.get("/api/admin/rbac", headers=bearer_for(make_user(db_session, "traveler"))).status_code == 403
    matrix = client.get("/api/admin/rbac", headers=bearer_for(make_user(db_session, "admin")))
    assert matrix.status_code == 200
    roles = {r["name"]: r for r in matrix.json()["roles"]}
    assert set(roles) == {"traveler", "provider", "admin"} and all(r["is_system"] for r in roles.values())
    assert "admin:rbac" in roles["admin"]["permissions"] and "admin:rbac" not in roles["traveler"]["permissions"]


def test_editing_the_matrix_takes_effect_immediately_and_is_audited(client, db_session):
    admin = make_user(db_session, "admin")
    traveler = make_user(db_session, "traveler")
    headers = bearer_for(admin)
    assert client.get("/api/admin/audit", headers=bearer_for(traveler)).status_code == 403

    traveler_perms = next(r for r in client.get("/api/admin/rbac", headers=headers).json()["roles"] if r["name"] == "traveler")["permissions"]
    granted = client.put("/api/admin/rbac/roles/traveler/permissions", headers=headers, json={"permissions": traveler_perms + ["admin:audit"]})
    assert granted.status_code == 200 and granted.json()["added"] == ["admin:audit"]
    assert client.get("/api/admin/audit", headers=bearer_for(traveler)).status_code == 200      # no re-login needed

    revoked = client.put("/api/admin/rbac/roles/traveler/permissions", headers=headers, json={"permissions": traveler_perms})
    assert revoked.json()["removed"] == ["admin:audit"]
    assert client.get("/api/admin/audit", headers=bearer_for(traveler)).status_code == 403
    actions = [a.action for a in db_session.scalars(select(AuditLog).where(AuditLog.action == "rbac.role_permissions_updated"))]
    assert len(actions) == 2


def test_the_admin_role_cannot_be_stripped_of_access_management(client, db_session):
    headers = bearer_for(make_user(db_session, "admin"))
    admin_perms = next(r for r in client.get("/api/admin/rbac", headers=headers).json()["roles"] if r["name"] == "admin")["permissions"]
    for protected in ("admin:rbac", "admin:users", "admin:service_accounts"):
        attempt = client.put("/api/admin/rbac/roles/admin/permissions", headers=headers, json={"permissions": [p for p in admin_perms if p != protected]})
        assert attempt.status_code == 409 and attempt.json()["error"]["code"] == "ADMIN_LOCKOUT", protected
    still = {r.permission_name for r in db_session.scalars(select(RolePermission).where(RolePermission.role_name == "admin"))}
    assert {"admin:rbac", "admin:users", "admin:service_accounts"} <= still


def test_unknown_permissions_and_roles_are_rejected(client, db_session):
    headers = bearer_for(make_user(db_session, "admin"))
    unknown = client.put("/api/admin/rbac/roles/traveler/permissions", headers=headers, json={"permissions": ["nonsense:thing"]})
    assert unknown.status_code == 422 and unknown.json()["error"]["code"] == "UNKNOWN_PERMISSION"
    missing = client.put("/api/admin/rbac/roles/ghost/permissions", headers=headers, json={"permissions": []})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "ROLE_NOT_FOUND"


def test_sync_restores_new_permissions_without_undoing_deliberate_removals(client, db_session):
    db_session.execute(RolePermission.__table__.delete().where(RolePermission.role_name == "traveler", RolePermission.permission_name == "chat:use"))
    db_session.commit()
    assert sync_catalog(db_session) == []                                       # nothing new -> nothing re-granted
    still = {r.permission_name for r in db_session.scalars(select(RolePermission).where(RolePermission.role_name == "traveler"))}
    assert "chat:use" not in still


def test_service_account_lifecycle(client, db_session):
    admin = bearer_for(make_user(db_session, "admin"))
    created = client.post("/api/admin/service-accounts", headers=admin, json={"name": "uptime-monitor", "permissions": ["ops:read"]})
    assert created.status_code == 201
    key, account_id = created.json()["key"], created.json()["id"]
    assert key.startswith("lek_")

    listing = client.get("/api/admin/service-accounts", headers=admin).json()
    assert [a["name"] for a in listing] == ["uptime-monitor"]
    assert "key" not in listing[0] and "key_hash" not in listing[0]                 # the secret is shown exactly once
    stored = db_session.scalars(select(ServiceAccount)).one()
    assert key.split("_", 2)[2] not in stored.key_hash and key not in stored.key_hash

    bearer = {"Authorization": f"Bearer {key}"}
    assert client.get("/api/ops/status", headers=bearer).status_code == 200
    db_session.refresh(stored)
    assert stored.last_used_at is not None
    # an API key is for machines: it holds only what it was granted
    assert client.get("/api/admin/dashboard", headers=bearer).status_code == 403
    assert client.get("/api/auth/me", headers=bearer).status_code == 403

    assert client.delete(f"/api/admin/service-accounts/{account_id}", headers=admin).status_code == 200
    assert client.get("/api/ops/status", headers=bearer).status_code == 401
    actions = {a.action for a in db_session.scalars(select(AuditLog))}
    assert {"service_account.created", "service_account.revoked"} <= actions


def test_service_accounts_cannot_hold_human_permissions_or_duplicate_names(client, db_session):
    admin = bearer_for(make_user(db_session, "admin"))
    too_much = client.post("/api/admin/service-accounts", headers=admin, json={"name": "greedy", "permissions": ["admin:users"]})
    assert too_much.status_code == 422 and too_much.json()["error"]["code"] == "PERMISSION_NOT_GRANTABLE"
    assert client.post("/api/admin/service-accounts", headers=admin, json={"name": "monitor-1"}).status_code == 201
    assert client.post("/api/admin/service-accounts", headers=admin, json={"name": "monitor-1"}).status_code == 409
    assert client.post("/api/admin/service-accounts", headers=admin, json={"name": "BAD NAME"}).status_code == 422


def test_a_wrong_secret_for_a_real_key_id_is_rejected(client, db_session):
    _, key = create_service_account(db_session, "monitor", ["ops:read"], None)
    key_id = key.split("_", 2)[1]
    assert client.get("/api/ops/status", headers={"Authorization": f"Bearer lek_{key_id}_not-the-secret"}).status_code == 401
    assert client.get("/api/ops/status", headers={"Authorization": "Bearer lek_unknown_secret"}).status_code == 401


def test_removing_ops_from_a_role_removes_access_at_once(client, db_session):
    admin = make_user(db_session, "admin")
    perms = next(r for r in client.get("/api/admin/rbac", headers=bearer_for(admin)).json()["roles"] if r["name"] == "admin")["permissions"]
    assert client.get("/api/ops/status", headers=bearer_for(admin)).status_code == 200
    client.put("/api/admin/rbac/roles/admin/permissions", headers=bearer_for(admin), json={"permissions": [p for p in perms if p != "ops:read"]})
    assert client.get("/api/ops/status", headers=bearer_for(admin)).status_code == 403


def test_the_old_shared_admin_key_no_longer_grants_anything(client):
    assert client.get("/api/ops/status", headers={"X-Admin-Key": "test-admin-key"}).status_code == 401
    assert client.post("/api/ai/intent-similarity", headers={"X-Admin-Key": "test-admin-key"}, json={}).status_code == 401


def test_seed_migration_matches_the_catalogue_it_froze():
    """The migration is a frozen copy: it may lag behind the code (sync_rbac covers the gap) but never contradict it."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("m0012", "migrations/versions/0012_rbac_seed.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.PERMISSIONS) <= registry.names(), "a permission was removed from the code; add a migration for it"
    for role, perms in module.GRANTS.items():
        assert set(perms) <= set(DEFAULT_GRANTS[role]) | set(module.GRANTS[role])
        assert set(perms) <= set(module.PERMISSIONS)
    assert module.PERMISSIONS == {name: registry.description(name) for name in module.PERMISSIONS}


def _load_migration(name: str, path: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_migration_runs_and_loads_the_expected_matrix():
    """0012 seeds the matrix and later revisions add their permissions; together they equal the code defaults."""
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    module = _load_migration("m0012", "migrations/versions/0012_rbac_seed.py")
    m0016 = _load_migration("m0016", "migrations/versions/0016_portal_platform.py")
    m0019 = _load_migration("m0019", "migrations/versions/0019_itinerary_collaboration.py")
    m0020 = _load_migration("m0020", "migrations/versions/0020_trip_planner.py")
    later = [_load_migration("m0013", "migrations/versions/0013_account_recovery.py"), _load_migration("m0014", "migrations/versions/0014_mfa.py"),
             # 0016 also changes the schema; only its permission seed applies to this bare RBAC database.
             type("PermissionsOnly0016", (), {"upgrade": staticmethod(m0016.upgrade_permissions), "downgrade": staticmethod(m0016.downgrade_permissions)}),
             # 0019 also adds schema; exercise only its traveler permission seed here.
             type("PermissionsOnly0019", (), {"upgrade": staticmethod(m0019.upgrade_permissions), "downgrade": staticmethod(m0019.downgrade_permissions)}),
             # 0020 also adds schema; exercise only its trip:use seed here.
             type("PermissionsOnly0020", (), {"upgrade": staticmethod(m0020.upgrade_permissions), "downgrade": staticmethod(m0020.downgrade_permissions)})]
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE roles (name VARCHAR(40) PRIMARY KEY, description VARCHAR(255), is_system BOOLEAN, created_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE permissions (name VARCHAR(80) PRIMARY KEY, description VARCHAR(255), created_at DATETIME)"))
        conn.execute(sa.text("CREATE TABLE role_permissions (role_name VARCHAR(40), permission_name VARCHAR(80))"))
        # stand-ins for tables created by 0011 that revision 0014 alters
        conn.execute(sa.text("CREATE TABLE user_mfa (user_id VARCHAR(36) PRIMARY KEY, secret_encrypted TEXT)"))
        conn.execute(sa.text("CREATE TABLE auth_tokens (id VARCHAR(36) PRIMARY KEY, purpose VARCHAR(32) NOT NULL, "
                             "CONSTRAINT ck_auth_tokens_purpose CHECK (purpose IN ('reset_password', 'verify_email')))"))
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            for revision in later:
                revision.upgrade()
        grants = {}
        for role, perm in conn.execute(sa.text("SELECT role_name, permission_name FROM role_permissions")):
            grants.setdefault(role, set()).add(perm)
        assert {r: sorted(p) for r, p in grants.items()} == {r: sorted(set(p)) for r, p in DEFAULT_GRANTS.items()}
        with Operations.context(MigrationContext.configure(conn)):
            for revision in reversed(later):
                revision.downgrade()
            assert conn.execute(sa.text("SELECT COUNT(*) FROM permissions WHERE name = 'account:sessions'")).scalar() == 0
            module.downgrade()
        assert conn.execute(sa.text("SELECT COUNT(*) FROM roles")).scalar() == 0


def test_seed_migration_also_renders_as_offline_postgresql_sql():
    """`alembic upgrade --sql` must work for operators who apply migrations by hand."""
    import importlib.util
    from io import StringIO
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    spec = importlib.util.spec_from_file_location("m0012", "migrations/versions/0012_rbac_seed.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    buffer = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buffer})
    with Operations.context(context):
        module.upgrade()
    sql = buffer.getvalue()
    expected = len(module.ROLES) + len(module.PERMISSIONS) + sum(len(p) for p in module.GRANTS.values())
    assert sql.count("INSERT INTO") == expected


def test_deprecated_provider_access_key_still_works_but_every_use_is_logged(db_session, sample_experience, caplog):
    import logging
    from app.api.routes import ai as ai_routes
    sample_experience.provider.portal_access_key = "provider-test-key"
    sample_experience.provider.is_active = True
    db_session.commit()
    with caplog.at_level(logging.WARNING, logger=ai_routes.log.name):
        provider = ai_routes._provider_auth(db_session, sample_experience.provider.id, "provider-test-key")
    assert provider.id == sample_experience.provider.id
    assert any("X-Provider-Access-Key" in record.getMessage() and "deprecated" in record.getMessage() for record in caplog.records)
    caplog.clear()
    try:
        ai_routes._provider_auth(db_session, sample_experience.provider.id, "wrong-key")
    except Exception as error:                                   # a failed attempt is rejected and is not the deprecation warning
        assert getattr(error, "status_code", None) == 401
    assert not any("deprecated" in record.getMessage() for record in caplog.records)
