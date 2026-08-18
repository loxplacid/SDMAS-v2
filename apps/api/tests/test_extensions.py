"""Zero-fork extension architecture tests (TASK 14).

Covers:

- the manifest contract: valid manifests pass, every violation (unknown
  permission, out-of-root route, unknown event, unknown policy scope,
  unknown section, malformed config schema) is rejected deterministically
- config schema validation: values validated against the declared schema
- semver compatibility: parsing, ranges, prerelease ordering, fail-closed
- lifecycle: register → publish → grant → enable → disable → retire,
  idempotency, and the state machine guards
- the authorization gate: enabling fails while any declared permission is
  un-granted; revoking a required permission auto-disables the extension
- policy enforcement: extensions cannot bypass the policy engine (deny
  raises, fail closed)
- tenant isolation: campus A can never see or mutate campus B extensions
- audit: lifecycle mutations are recorded through the audit domain
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.domains.audit.actors import ActorType, AuditActor
from app.domains.audit.models import AuditLog
from app.multi_tenant.models import TenantContext
from app.platform.extensions.compat import (
    CORE_VERSION,
    core_satisfies,
    parse_version,
    satisfies,
)
from app.platform.extensions.manifest import validate_config_value
from app.platform.extensions.models import (
    EXT_STATUS_DISABLED,
    EXT_STATUS_INSTALLED,
    EXT_STATUS_REGISTERED,
    EXT_STATUS_RETIRED,
    VER_STATUS_DISABLED,
    VER_STATUS_ENABLED,
    VER_STATUS_PENDING,
    ExtensionDefinition,
    ExtensionVersion,
)
from app.platform.extensions.registry import (
    DEFAULT_SUBSCRIBE_CATALOG,
    ExtensionRegistry,
)
from app.platform.extensions.schemas import (
    ConfigUpdate,
    ExtensionManifest,
    ExtensionRegister,
    ExtensionVersionPublish,
    GrantCreate,
)
from app.platform.extensions.service import ExtensionService
from app.platform.policy.schemas import (
    Condition,
    PolicyCreate,
    PolicyVersionCreate,
    PublishVersion,
    RuleDef,
)
from app.platform.policy.service import PolicyService

# Deterministic HMAC for the (guarded) audit-chain hook on audit writes.
os.environ.setdefault("AUDIT_CHAIN_SECRET", "test-secret")


@pytest.fixture
def tenant_a() -> TenantContext:
    return TenantContext(campus_id=1, institution_id=1, user_id=99)


@pytest.fixture
def tenant_b() -> TenantContext:
    return TenantContext(campus_id=2, institution_id=1, user_id=98)


def _actor(user_id: int = 99) -> AuditActor:
    return AuditActor(actor_type=ActorType.USER, actor_id=str(user_id))


# ---------------------------------------------------------------------------
# Manifest fixtures
# ---------------------------------------------------------------------------

GOOD_MANIFEST: dict[str, Any] = {
    "identity": {
        "extension_id": "transport.rfid",
        "name": "RFID Transport",
        "description": "RFID gate integration",
        "provider": "Acme Systems",
        "version": "1.0.0",
        "core_compat": ">=0.1.0,<1.0.0",
    },
    "permissions": [
        {"permission": "students.read", "reason": "lookup students at the gate"},
        {"permission": "attendance.write", "reason": "record gate scans"},
    ],
    "routes": [{"method": "GET", "path": "/api/v1/ext/transport.rfid/events"}],
    "events": [{"subscribe": "attendance.recorded", "handler": "on_attendance"}],
    "config_schema": {
        "type": "object",
        "properties": {
            "reader_url": {"type": "string"},
            "poll_interval_s": {"type": "integer", "enum": [5, 10, 30]},
        },
        "required": ["reader_url"],
    },
    "migrations": ["abc123def456_add_rfid_tables"],
    "frontend": {
        "entrypoint": "rfid.js",
        "routes": [{"path": "/ext/transport.rfid"}],
        "menu": [{"id": "rfid", "label": "RFID", "icon": "chip", "href": "/ext/transport.rfid"}],
    },
    "policy": {"scope": "attendance"},
}


def _manifest(**overrides: Any) -> dict[str, Any]:
    manifest = dict(GOOD_MANIFEST)
    manifest.update(overrides)
    return manifest


def _manifest_schema(**overrides: Any) -> ExtensionManifest:
    return ExtensionManifest(**_manifest(**overrides))


def _register_data(**overrides: Any) -> ExtensionRegister:
    base = {
        "extension_id": "transport.rfid",
        "name": "RFID Transport",
        "provider": "Acme Systems",
    }
    base.update(overrides)
    return ExtensionRegister(**base)


def _publish(manifest: ExtensionManifest | None = None) -> ExtensionVersionPublish:
    return ExtensionVersionPublish(manifest=manifest or _manifest_schema())


async def _registered(
    db_session: AsyncSession,
    tenant: TenantContext,
    **overrides: Any,
) -> tuple[ExtensionService, ExtensionDefinition]:
    svc = ExtensionService(db_session, tenant)
    definition = await svc.register(_register_data(**overrides), actor=_actor())
    return svc, definition


async def _installed(
    db_session: AsyncSession,
    tenant: TenantContext,
    **manifest_overrides: Any,
) -> tuple[ExtensionService, ExtensionDefinition, ExtensionVersion]:
    svc, definition = await _registered(db_session, tenant)
    version = await svc.publish_version(
        definition.id, _publish(_manifest_schema(**manifest_overrides)), actor=_actor()
    )
    return svc, definition, version


async def _enabled(
    db_session: AsyncSession,
    tenant: TenantContext,
) -> tuple[ExtensionService, ExtensionDefinition, ExtensionVersion]:
    svc, definition, version = await _installed(db_session, tenant)
    for perm in GOOD_MANIFEST["permissions"]:
        await svc.grant_permission(
            definition.id, GrantCreate(permission=perm["permission"]), actor=_actor()
        )
    version = await svc.enable(definition.id, actor=_actor())
    return svc, definition, version


# ---------------------------------------------------------------------------
# Manifest contract
# ---------------------------------------------------------------------------


class TestManifestContract:
    def test_valid_manifest_passes(self) -> None:
        assert ExtensionRegistry().validate_manifest(GOOD_MANIFEST) == []

    def test_unknown_permission_rejected(self) -> None:
        manifest = _manifest(
            permissions=[{"permission": "students.hack"}, {"permission": "nope.nope"}]
        )
        problems = ExtensionRegistry().validate_manifest(manifest)
        assert any("students.hack" in p for p in problems)
        assert any("nope.nope" in p for p in problems)

    def test_duplicate_permission_rejected(self) -> None:
        manifest = _manifest(
            permissions=[
                {"permission": "students.read"},
                {"permission": "students.read"},
            ]
        )
        problems = ExtensionRegistry().validate_manifest(manifest)
        assert any("duplicate" in p and "students.read" in p for p in problems)

    def test_route_outside_mount_root_rejected(self) -> None:
        manifest = _manifest(routes=[{"method": "GET", "path": "/api/v1/admin/delete-all"}])
        problems = ExtensionRegistry().validate_manifest(manifest)
        assert any("path" in p for p in problems)

    def test_route_cross_extension_namespace_rejected(self) -> None:
        # An extension cannot mount routes under another extension's namespace.
        manifest = _manifest(routes=[{"method": "GET", "path": "/api/v1/ext/other.ext/x"}])
        problems = ExtensionRegistry().validate_manifest(manifest)
        assert any("path" in p for p in problems)

    def test_route_bad_method_rejected(self) -> None:
        manifest = _manifest(routes=[{"method": "TRACE", "path": "/api/v1/ext/transport.rfid/x"}])
        problems = ExtensionRegistry().validate_manifest(manifest)
        assert any("method" in p for p in problems)

    def test_unknown_event_rejected(self) -> None:
        manifest = _manifest(events=[{"subscribe": "not.a.real.event", "handler": "x"}])
        problems = ExtensionRegistry().validate_manifest(manifest)
        assert any("event catalog" in p for p in problems)

    def test_known_event_accepted(self) -> None:
        assert "attendance.recorded" in DEFAULT_SUBSCRIBE_CATALOG
        manifest = _manifest(events=[{"subscribe": "attendance.recorded", "handler": "x"}])
        assert ExtensionRegistry().validate_manifest(manifest) == []

    def test_unknown_policy_scope_rejected(self) -> None:
        manifest = _manifest(policy={"scope": "sports"})
        problems = ExtensionRegistry().validate_manifest(manifest)
        assert any("policy.scope" in p for p in problems)

    def test_unknown_section_rejected(self) -> None:
        manifest = _manifest(nuclear_launch_codes={"x": 1})
        problems = ExtensionRegistry().validate_manifest(manifest)
        assert any("unknown section" in p for p in problems)

    def test_bad_extension_id_rejected(self) -> None:
        manifest = _manifest(identity={**GOOD_MANIFEST["identity"], "extension_id": "..evil.."})
        problems = ExtensionRegistry().validate_manifest(manifest)
        assert any("extension_id" in p for p in problems)

    def test_bad_migration_revision_rejected(self) -> None:
        manifest = _manifest(migrations=["rm -rf /"])
        problems = ExtensionRegistry().validate_manifest(manifest)
        assert any("migrations" in p for p in problems)

    def test_frontend_must_be_namespaced(self) -> None:
        manifest = _manifest(
            frontend={"entrypoint": "rfid.js", "routes": [{"path": "/admin"}], "menu": []}
        )
        problems = ExtensionRegistry().validate_manifest(manifest)
        assert any("frontend.routes" in p for p in problems)

    def test_deterministic(self) -> None:
        registry = ExtensionRegistry()
        manifest = _manifest(
            permissions=[{"permission": "students.hack"}],
            routes=[{"method": "GET", "path": "/api/v1/admin/x"}],
            events=[{"subscribe": "nope.nope", "handler": "x"}],
        )
        assert registry.validate_manifest(manifest) == registry.validate_manifest(manifest)

    def test_pydantic_extra_forbidden(self) -> None:
        with pytest.raises(ValueError):
            ExtensionManifest(**_manifest(), mystery_field=True)


class TestConfigSchemaValidation:
    def test_valid_config_passes(self) -> None:
        schema = GOOD_MANIFEST["config_schema"]
        ok = {"reader_url": "http://gate:8080", "poll_interval_s": 10}
        assert validate_config_value(schema, ok) == []
        # Required-only subset is fine when the schema's required field is present.
        minimal = {"reader_url": "http://gate:8080"}
        assert validate_config_value(schema, minimal) == []

    def test_invalid_config_rejected(self) -> None:
        schema = GOOD_MANIFEST["config_schema"]
        problems = validate_config_value(schema, {"reader_url": 42})
        assert any("string required" in p for p in problems)
        problems = validate_config_value(schema, {"poll_interval_s": 7})
        assert any("must be one of" in p for p in problems)
        problems = validate_config_value(schema, {"foo": 1})
        assert any("required property missing" in p for p in problems)
        # Not an object at all.
        assert validate_config_value(schema, ["nope"]) != []

    def test_nested_schema(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "endpoints": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "settings": {
                    "type": "object",
                    "properties": {"retries": {"type": "integer"}},
                    "required": ["retries"],
                },
            },
            "required": ["endpoints"],
        }
        assert validate_config_value(schema, {"endpoints": ["a"], "settings": {"retries": 3}}) == []
        assert validate_config_value(schema, {"endpoints": [1], "settings": {"retries": 3}}) != []
        assert validate_config_value(schema, {"endpoints": [], "settings": {}}) != []


class TestSemverCompatibility:
    def test_parse(self) -> None:
        v = parse_version("1.2.3")
        assert v is not None and (v.major, v.minor, v.patch) == (1, 2, 3)
        assert parse_version("1.2") is not None  # normalized
        assert parse_version("1") is not None
        assert parse_version("not-a-version") is None
        assert parse_version("1.2.3.4") is None
        assert parse_version("") is None

    def test_ranges(self) -> None:
        assert satisfies("1.2.3", ">=1.0.0,<2.0.0")
        assert satisfies("1.2.3", ">=1.0.0")
        assert not satisfies("0.9.0", ">=1.0.0")
        assert satisfies("2.0.0", "<2.0.1")
        assert not satisfies("2.0.0", "<2.0.0")
        assert satisfies("1.2.3", "==1.2.3")
        assert not satisfies("1.2.4", "==1.2.3")
        assert satisfies("1.2.3", "!=2.0.0")
        assert satisfies("3.1.4", "*")

    def test_prerelease_ordering(self) -> None:
        assert satisfies("1.0.0-rc1", ">=0.1.0,<1.0.0")  # pre < release
        assert not satisfies("1.0.0-rc1", ">=1.0.0")
        rc1 = parse_version("1.0.0-rc1")
        release = parse_version("1.0.0")
        rc2 = parse_version("1.0.0-rc2")
        assert rc1 is not None and release is not None and rc2 is not None
        assert rc1 < release
        assert rc2 > rc1

    def test_fails_closed(self) -> None:
        assert satisfies(None, ">=1.0.0") is False
        assert satisfies("1.0.0", None) is False
        assert satisfies("1.0.0", "") is False
        assert satisfies("1.0.0", ">=banana") is False
        assert satisfies("1.0.0", "banana") is False

    def test_core_satisfies(self) -> None:
        assert core_satisfies(">=0.1.0,<1.0.0") is True
        assert core_satisfies(">=2.0.0") is False
        assert CORE_VERSION == "0.1.0"


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    async def test_register_idempotent(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExtensionService(db_session, tenant_a)
        definition = await svc.register(_register_data(), actor=_actor())
        assert definition.campus_id == 1
        assert definition.status == EXT_STATUS_REGISTERED

        again = await svc.register(_register_data(), actor=_actor())
        assert again.id == definition.id
        definitions, total = await svc.list_definitions()
        assert total == 1

    async def test_publish_version_pending(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = ExtensionService(db_session, tenant_a)
        definition = await svc.register(_register_data(), actor=_actor())
        version = await svc.publish_version(definition.id, _publish(), actor=_actor())
        assert version.status == VER_STATUS_PENDING
        assert version.is_current is True
        assert version.version == "1.0.0"
        definition = await svc.get_definition(definition.id)
        assert definition.status == EXT_STATUS_INSTALLED
        assert definition.current_version == "1.0.0"
        assert definition.core_compat == ">=0.1.0,<1.0.0"

    async def test_publish_manifest_mismatch_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition = await _registered(db_session, tenant_a)
        other = _manifest_schema(
            identity={
                **GOOD_MANIFEST["identity"],
                "extension_id": "some.other.ext",
                "version": "1.0.0",
            }
        )
        with pytest.raises(ValidationError):
            await svc.publish_version(definition.id, _publish(other), actor=_actor())

    async def test_publish_invalid_manifest_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition = await _registered(db_session, tenant_a)
        bad = _manifest_schema(
            permissions=[{"permission": "students.hack"}],
            routes=[{"method": "GET", "path": "/api/v1/admin/x"}],
            events=[{"subscribe": "nope.nope", "handler": "x"}],
        )
        with pytest.raises(ValidationError):
            await svc.publish_version(definition.id, _publish(bad), actor=_actor())
        # Nothing persisted.
        versions, total = await svc.list_versions(definition.id)
        assert total == 0

    async def test_publish_incompatible_core_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition = await _registered(db_session, tenant_a)
        incompatible = _manifest_schema(
            identity={**GOOD_MANIFEST["identity"], "core_compat": ">=99.0.0"}
        )
        with pytest.raises(ConflictError):
            await svc.publish_version(definition.id, _publish(incompatible), actor=_actor())

    async def test_publish_duplicate_version_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition = await _registered(db_session, tenant_a)
        await svc.publish_version(definition.id, _publish(), actor=_actor())
        with pytest.raises(ConflictError):
            await svc.publish_version(definition.id, _publish(), actor=_actor())

    async def test_publish_new_version_supersedes(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition, v1 = await _installed(db_session, tenant_a)
        v2_manifest = _manifest_schema(
            identity={**GOOD_MANIFEST["identity"], "version": "1.1.0"},
            permissions=[{"permission": "students.read"}],
        )
        v2 = await svc.publish_version(definition.id, _publish(v2_manifest), actor=_actor())
        assert v2.version == "1.1.0"
        assert v2.is_current is True
        v1 = await svc.repo.get_version_or_404(v1.id)
        assert v1.is_current is False
        assert v1.status == "superseded"

    async def test_enable_requires_grants(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition, version = await _installed(db_session, tenant_a)
        with pytest.raises(ValidationError) as exc:
            await svc.enable(definition.id, actor=_actor())
        message = str(exc.value)
        assert "attendance.write" in message and "students.read" in message

        # Granting only one of two is still insufficient.
        await svc.grant_permission(
            definition.id, GrantCreate(permission="students.read"), actor=_actor()
        )
        with pytest.raises(ValidationError) as exc:
            await svc.enable(definition.id, actor=_actor())
        assert "attendance.write" in str(exc.value)

    async def test_enable_after_all_grants(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition, version = await _enabled(db_session, tenant_a)
        assert version.status == VER_STATUS_ENABLED
        definition = await svc.get_definition(definition.id)
        assert definition.status == EXT_STATUS_INSTALLED
        # Second enable is a conflict (already enabled).
        with pytest.raises(ConflictError):
            await svc.enable(definition.id, actor=_actor())

    async def test_disable_and_reenable(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition, version = await _enabled(db_session, tenant_a)
        disabled = await svc.disable(definition.id, actor=_actor())
        assert disabled is not None and disabled.status == VER_STATUS_DISABLED
        definition = await svc.get_definition(definition.id)
        assert definition.status == EXT_STATUS_DISABLED

        # Re-enable works because grants are still complete.
        version = await svc.enable(definition.id, actor=_actor())
        assert version.status == VER_STATUS_ENABLED

    async def test_retire_terminal(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc, definition, version = await _enabled(db_session, tenant_a)
        retired = await svc.retire(definition.id, actor=_actor())
        assert retired.status == EXT_STATUS_RETIRED
        # Current enabled version auto-disabled.
        version = await svc.repo.get_version_or_404(version.id)
        assert version.status != VER_STATUS_ENABLED
        with pytest.raises(ConflictError):
            await svc.enable(definition.id, actor=_actor())


# ---------------------------------------------------------------------------
# Grants
# ---------------------------------------------------------------------------


class TestGrants:
    async def test_grant_idempotent(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition, _ = await _installed(db_session, tenant_a)
        grant = await svc.grant_permission(
            definition.id, GrantCreate(permission="students.read"), actor=_actor()
        )
        again = await svc.grant_permission(
            definition.id, GrantCreate(permission="students.read"), actor=_actor()
        )
        assert again.id == grant.id
        grants, total = await svc.list_grants(definition.id)
        assert total == 1

    async def test_grant_unknown_permission_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition, _ = await _installed(db_session, tenant_a)
        with pytest.raises(ValidationError):
            await svc.grant_permission(
                definition.id, GrantCreate(permission="students.hack"), actor=_actor()
            )

    async def test_revoke_auto_disables(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition, version = await _enabled(db_session, tenant_a)
        assert version.status == VER_STATUS_ENABLED

        # Revoking a permission the enabled manifest requires → auto-disable.
        revoked = await svc.revoke_permission(definition.id, "attendance.write", actor=_actor())
        assert revoked is not None and revoked.revoked_at is not None
        version = await svc.repo.get_version_or_404(version.id)
        assert version.status == VER_STATUS_DISABLED
        definition = await svc.get_definition(definition.id)
        assert definition.status == EXT_STATUS_DISABLED

        # Cannot re-enable until the grant is restored.
        with pytest.raises(ValidationError):
            await svc.enable(definition.id, actor=_actor())
        await svc.grant_permission(
            definition.id, GrantCreate(permission="attendance.write"), actor=_actor()
        )
        version = await svc.enable(definition.id, actor=_actor())
        assert version.status == VER_STATUS_ENABLED

    async def test_revoke_non_declared_permission_keeps_running(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition, version = await _enabled(db_session, tenant_a)
        # Grant + revoke a permission the manifest does not declare.
        await svc.grant_permission(
            definition.id, GrantCreate(permission="reports.export"), actor=_actor()
        )
        await svc.revoke_permission(definition.id, "reports.export", actor=_actor())
        version = await svc.repo.get_version_or_404(version.id)
        assert version.status == VER_STATUS_ENABLED  # still running


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestConfig:
    async def test_set_config_validated(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition, _ = await _installed(db_session, tenant_a)
        saved = await svc.set_config(
            definition.id,
            ConfigUpdate(config={"reader_url": "http://gate:8080", "poll_interval_s": 10}),
            actor=_actor(),
        )
        assert saved.config["reader_url"] == "http://gate:8080"
        assert saved.schema_version == "1.0.0"

        fetched = await svc.get_config(definition.id)
        assert fetched is not None and fetched.config["reader_url"] == "http://gate:8080"

    async def test_set_config_invalid_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition, _ = await _installed(db_session, tenant_a)
        with pytest.raises(ValidationError):
            await svc.set_config(
                definition.id, ConfigUpdate(config={"reader_url": 42}), actor=_actor()
            )
        with pytest.raises(ValidationError):
            await svc.set_config(
                definition.id, ConfigUpdate(config={"poll_interval_s": 7}), actor=_actor()
            )
        # Nothing persisted.
        assert await svc.get_config(definition.id) is None

    async def test_no_version_no_config(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition = await _registered(db_session, tenant_a)
        with pytest.raises(NotFoundError):
            await svc.set_config(
                definition.id, ConfigUpdate(config={"reader_url": "x"}), actor=_actor()
            )


# ---------------------------------------------------------------------------
# Policy enforcement
# ---------------------------------------------------------------------------


class TestPolicyEnforcement:
    async def _policy_deny_all(self, db_session: AsyncSession, tenant_a: TenantContext) -> str:
        svc = PolicyService(db_session, tenant_a)
        policy = await svc.create_policy(
            PolicyCreate(
                policy_id="ext.deny_all",
                name="Deny all extension ops",
                scope="global",
            ),
            actor=_actor(),
        )
        version = await svc.add_version(
            policy.id,
            PolicyVersionCreate(
                title="deny",
                rules=[
                    RuleDef(
                        id="deny-all",
                        condition=Condition(op="is_true", field="x"),
                        effect="deny",
                        reason="policy test",
                    )
                ],
            ),
            actor=_actor(),
        )
        await svc.publish_version(version.id, PublishVersion(note="ok"), actor=_actor())
        return "ext.deny_all"

    async def test_check_policy_deny_raises(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        policy_id = await self._policy_deny_all(db_session, tenant_a)
        svc, definition, _ = await _enabled(db_session, tenant_a)
        with pytest.raises(AuthorizationError) as exc:
            await svc.check_policy(
                definition.id,
                policy_id,
                {"x": True},
                actor=_actor(),
                subject_type="extension",
                subject_id="transport.rfid",
            )
        assert "denied by policy" in str(exc.value)

    async def test_check_policy_allow_returns_decision(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        policy_id = await self._policy_deny_all(db_session, tenant_a)
        svc, definition, _ = await _enabled(db_session, tenant_a)
        decision = await svc.check_policy(
            definition.id,
            policy_id,
            {"x": False},
            actor=_actor(),
        )
        assert decision == "allow"

    async def test_check_policy_retired_extension_conflict(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        policy_id = await self._policy_deny_all(db_session, tenant_a)
        svc, definition, _ = await _enabled(db_session, tenant_a)
        await svc.retire(definition.id, actor=_actor())
        with pytest.raises(ConflictError):
            await svc.check_policy(definition.id, policy_id, {"x": False})


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    async def test_cross_tenant_definition_invisible(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = ExtensionService(db_session, tenant_a)
        definition = await svc_a.register(_register_data(), actor=_actor())
        assert definition.campus_id == 1

        svc_b = ExtensionService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.get_definition(definition.id)
        definitions_b, total_b = await svc_b.list_definitions()
        assert total_b == 0

    async def test_cross_tenant_publish_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a, definition, _ = await _installed(db_session, tenant_a)
        svc_b = ExtensionService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.publish_version(definition.id, _publish(), actor=_actor())

    async def test_cross_tenant_enable_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a, definition, _ = await _installed(db_session, tenant_a)
        svc_b = ExtensionService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.enable(definition.id, actor=_actor())

    async def test_cross_tenant_grant_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a, definition, _ = await _installed(db_session, tenant_a)
        svc_b = ExtensionService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.grant_permission(
                definition.id, GrantCreate(permission="students.read"), actor=_actor()
            )

    async def test_cross_tenant_revoke_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a, definition, _ = await _enabled(db_session, tenant_a)
        svc_b = ExtensionService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.revoke_permission(definition.id, "students.read", actor=_actor())

    async def test_cross_tenant_config_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a, definition, _ = await _installed(db_session, tenant_a)
        svc_b = ExtensionService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.set_config(
                definition.id,
                ConfigUpdate(config={"reader_url": "x"}),
                actor=_actor(),
            )

    async def test_cross_tenant_policy_check_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a, definition, _ = await _enabled(db_session, tenant_a)
        svc_b = ExtensionService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.check_policy(definition.id, "ext.deny_all", {"x": False})

    async def test_same_extension_id_different_campus_ok(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = ExtensionService(db_session, tenant_a)
        svc_b = ExtensionService(db_session, tenant_b)
        definition_a = await svc_a.register(_register_data(), actor=_actor())
        definition_b = await svc_b.register(_register_data(), actor=_actor())
        assert definition_a.id != definition_b.id  # per-campus uniqueness

    async def test_cross_tenant_version_list_invisible(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a, definition, _ = await _installed(db_session, tenant_a)
        svc_b = ExtensionService(db_session, tenant_b)
        with pytest.raises(NotFoundError):
            await svc_b.list_versions(definition.id)


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class TestAudit:
    async def test_lifecycle_ops_audited(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc, definition, version = await _enabled(db_session, tenant_a)
        await svc.disable(definition.id, actor=_actor())
        await svc.grant_permission(
            definition.id, GrantCreate(permission="reports.export"), actor=_actor()
        )
        await svc.set_config(
            definition.id, ConfigUpdate(config={"reader_url": "http://x"}), actor=_actor()
        )
        records = (await db_session.execute(select(AuditLog))).scalars().all()
        actions = {r.action for r in records}
        # register, publish, 2x grant, enable, disable, grant, configure
        assert {"CREATE", "PUBLISH", "GRANT", "ENABLE", "DISABLE", "CONFIGURE"} <= actions
