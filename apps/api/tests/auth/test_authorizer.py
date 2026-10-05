import pytest

from app.auth import (
    Authorizer, CachedRoleMatrix, Forbidden, PermissionRegistry, PolicyMissing, PolicyRegistry, Principal,
    PrincipalKind, StaticRoleMatrix,
)

MATRIX = StaticRoleMatrix({
    "traveler": ["itinerary:read", "booking:create"],
    "provider": ["slot:update", "booking:decide"],
    "admin": ["user:update", "slot:update"],
})


def user(role="traveler", id="u1", provider_id=None):
    return Principal(id=id, kind=PrincipalKind.USER, role=role, provider_id=provider_id)


def test_permission_comes_from_the_role():
    authz = Authorizer(MATRIX)
    assert authz.can(user("traveler"), "itinerary:read")
    assert not authz.can(user("traveler"), "user:update")
    assert not authz.can(user("unknown-role"), "itinerary:read")


def test_authorize_raises_forbidden_with_the_existing_error_code():
    with pytest.raises(Forbidden) as error:
        Authorizer(MATRIX).authorize(user("traveler"), "user:update")
    assert error.value.status_code == 403 and error.value.code == "ROLE_FORBIDDEN"


def test_resource_check_without_a_policy_fails_closed():
    with pytest.raises(PolicyMissing):
        Authorizer(MATRIX).can(user("provider"), "slot:update", resource=object())


def test_ownership_policy_is_enforced():
    policies = PolicyRegistry()
    policies.register("slot:update", lambda who, slot: who.provider_id == slot["provider_id"])
    authz = Authorizer(MATRIX, policies)
    mine, theirs = {"provider_id": "p1"}, {"provider_id": "p2"}
    assert authz.can(user("provider", provider_id="p1"), "slot:update", mine)
    assert not authz.can(user("provider", provider_id="p1"), "slot:update", theirs)
    assert not authz.can(user("traveler", provider_id="p1"), "slot:update", mine)  # role lacks the permission


def test_service_principal_uses_only_its_explicit_permissions():
    service = Principal(id="monitor", kind=PrincipalKind.SERVICE, role="admin", explicit_permissions=frozenset({"ops:read"}))
    authz = Authorizer(MATRIX)
    assert authz.can(service, "ops:read") is True
    assert authz.can(service, "user:update") is False   # not inherited from the admin role
    assert service.audit_actor == "system:monitor"


def test_duplicate_policy_registration_is_an_error():
    policies = PolicyRegistry()
    policies.register("a:b", lambda *_: True)
    with pytest.raises(ValueError):
        policies.register("a:b", lambda *_: True)


def test_permission_registry_validates_names():
    registry = PermissionRegistry()
    assert registry.define("slot:update", "Edit a slot") == "slot:update"
    assert "slot:update" in registry
    for bad in ("slot", "Slot:Update", "slot:", ":update", "a:b:c"):
        with pytest.raises(ValueError):
            registry.define(bad)
    with pytest.raises(ValueError):
        registry.define("slot:update")


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_cached_matrix_reloads_on_version_change_and_ttl():
    state = {"grants": {"traveler": frozenset({"a:b"})}, "version": 1, "loads": 0}

    def loader():
        state["loads"] += 1
        return dict(state["grants"])

    clock = Clock()
    matrix = CachedRoleMatrix(loader, version=lambda: state["version"], ttl_seconds=60, clock=clock)
    assert matrix.permissions_for("traveler") == {"a:b"} and state["loads"] == 1
    matrix.permissions_for("traveler")
    assert state["loads"] == 1                       # served from cache
    state["grants"] = {"traveler": frozenset({"a:b", "c:d"})}
    assert matrix.permissions_for("traveler") == {"a:b"}   # no signal yet: still cached
    state["version"] = 2                              # an admin edit bumps the shared version
    assert matrix.permissions_for("traveler") == {"a:b", "c:d"} and state["loads"] == 2
    clock.now = 61
    matrix.permissions_for("traveler")
    assert state["loads"] == 3                        # TTL expiry also reloads


def test_cached_matrix_keeps_serving_when_the_version_source_is_down():
    def broken():
        raise ConnectionError("redis down")

    matrix = CachedRoleMatrix(lambda: {"admin": frozenset({"x:y"})}, version=broken, ttl_seconds=60, clock=Clock())
    assert matrix.permissions_for("admin") == {"x:y"}
    assert matrix.permissions_for("admin") == {"x:y"}
