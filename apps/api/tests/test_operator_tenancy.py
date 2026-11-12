from app.models.entities import OperatorOrg
from tests.helpers import bearer_for, make_user


def _org(db, name):
    org = OperatorOrg(name=name, slug=name.lower(), settings={})
    db.add(org)
    db.commit()
    return org


def test_operator_reads_and_patches_only_own_org(client, db_session):
    a, b = _org(db_session, "OrgA"), _org(db_session, "OrgB")
    op_a = make_user(db_session, "operator", operator_org_id=a.id)
    got = client.get("/api/operator/me/org", headers=bearer_for(op_a))
    assert got.status_code == 200 and got.json()["id"] == a.id and got.json()["margin_floor_pct"] == 15
    patched = client.patch("/api/operator/me/org", json={"margin_floor_pct": 20}, headers=bearer_for(op_a))
    assert patched.json()["margin_floor_pct"] == 20
    db_session.refresh(b)
    assert b.margin_floor_pct == 15


def test_operator_without_org_gets_404(client, db_session):
    orphan = make_user(db_session, "operator")
    assert client.get("/api/operator/me/org", headers=bearer_for(orphan)).status_code == 404
    assert client.patch("/api/operator/me/org", json={"deposit_pct": 10}, headers=bearer_for(orphan)).status_code == 404


def test_traveler_and_provider_forbidden(client, db_session):
    for role in ("traveler", "provider"):
        user = make_user(db_session, role)
        assert client.get("/api/operator/me/org", headers=bearer_for(user)).status_code == 403
        assert client.patch("/api/operator/me/org", json={}, headers=bearer_for(user)).status_code == 403


def test_admin_creates_org_and_assigns_operator(client, db_session):
    admin = make_user(db_session, "admin")
    created = client.post("/api/admin/operator-orgs", json={"name": "Saigon Tours"}, headers=bearer_for(admin))
    assert created.status_code == 201
    org_id = created.json()["id"]
    target = make_user(db_session, "traveler")
    assert client.patch(f"/api/admin/users/{target.id}", json={"role": "operator", "is_active": True}, headers=bearer_for(admin)).status_code == 422
    ok = client.patch(f"/api/admin/users/{target.id}", json={"role": "operator", "is_active": True, "operator_org_id": org_id}, headers=bearer_for(admin))
    assert ok.status_code == 200 and ok.json()["operator_org_id"] == org_id
    assert client.post("/api/admin/operator-orgs", json={"name": "X Y"}, headers=bearer_for(make_user(db_session, "operator"))).status_code == 403
