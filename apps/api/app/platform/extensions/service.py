"""Zero-fork extension architecture — application service.

Owns the extension lifecycle and the enforcement invariants that keep
extensions from bypassing the platform's guarantees:

- **Tenant isolation**  — every operation is tenant-scoped through the
  repository; an extension in campus A is invisible to campus B.
- **Authorization**     — an extension's manifest only *declares* the
  permissions it needs; nothing takes effect until an administrator
  grants each one (``grant_permission``).  ``enable`` fails listing every
  missing grant, and ``revoke_permission`` automatically disables an
  enabled version whose declared permissions are no longer complete —
  extensions can never grant themselves capabilities or keep running
  with permissions that were revoked.
- **Audit**             — every lifecycle mutation (register, publish,
  enable, disable, retire, grant, revoke, config) is recorded through the
  existing audit domain.
- **Policy**            — the manifest's declared policy scope must be in
  the policy engine's catalog; ``check_policy`` evaluates a named policy
  through :class:`PolicyService` and raises ``AuthorizationError`` on a
  deny — fail closed.
- **Data validation**   — the manifest itself is validated against the
  closed catalogs before it can be stored, and configuration values are
  validated against the manifest's declared config schema before persist.
- **Compatibility**     — publishing/enabling requires the extension's
  ``core_compat`` range to be satisfied by the running core version.

Lifecycle: ``register`` -> ``publish_version`` (pending) ->
``grant_permission`` (for each declared permission) -> ``enable``.
``disable`` pauses; ``retire`` is terminal.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.domains.audit.actors import ActorType, AuditActor
from app.domains.audit.service import AuditService
from app.multi_tenant.models import TenantContext
from app.platform.extensions.compat import CORE_VERSION, core_satisfies, parse_version
from app.platform.extensions.manifest import validate_config_value
from app.platform.extensions.models import (
    EXT_STATUS_DISABLED,
    EXT_STATUS_INSTALLED,
    EXT_STATUS_REGISTERED,
    EXT_STATUS_RETIRED,
    VER_STATUS_DISABLED,
    VER_STATUS_ENABLED,
    VER_STATUS_PENDING,
    VER_STATUS_SUPERSEDED,
    ExtensionConfig,
    ExtensionDefinition,
    ExtensionGrant,
    ExtensionVersion,
)
from app.platform.extensions.registry import (
    ExtensionRegistry,
    extension_registry,
)
from app.platform.extensions.repository import ExtensionRepository
from app.platform.extensions.schemas import (
    ConfigUpdate,
    ExtensionRegister,
    ExtensionVersionPublish,
    GrantCreate,
)
from app.platform.policy.schemas import EvaluateInput
from app.platform.policy.service import PolicyService

logger = logging.getLogger(__name__)


class ExtensionService:
    """Extension lifecycle operations (one tenant per instance)."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
        registry: Optional[ExtensionRegistry] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.repo = ExtensionRepository(session, tenant)
        self.audit = AuditService(session, tenant)
        self.registry = registry or extension_registry

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def register(
        self, data: ExtensionRegister, actor: AuditActor | None = None
    ) -> ExtensionDefinition:
        """Register an extension.  Idempotent: re-registering an existing
        ``extension_id`` returns the existing definition."""
        existing = await self.repo.find_by_key(data.extension_id)
        if existing is not None:
            return existing
        definition = ExtensionDefinition(
            campus_id=self.repo._effective_campus_id(),
            extension_id=data.extension_id,
            name=data.name,
            description=data.description,
            provider=data.provider,
            homepage=data.homepage,
            license=data.license,
            status=EXT_STATUS_REGISTERED,
            created_by=data.created_by or _actor_id(actor),
        )
        definition = await self.repo.create_definition(definition)
        await self.audit.record(
            action="CREATE",
            resource_type="extension",
            resource_id=str(definition.id),
            actor=actor,
            details={"extension_id": data.extension_id, "name": data.name},
        )
        return definition

    async def publish_version(
        self,
        definition_id: int,
        data: ExtensionVersionPublish,
        actor: AuditActor | None = None,
    ) -> ExtensionVersion:
        """Publish a new manifest version.

        The manifest is validated against the closed catalogs and the
        extension's ``core_compat`` range against the running core before
        it can be stored.  Publishing supersedes the previous current
        version (its status becomes ``superseded``); the new version is
        ``pending`` until every declared permission is granted and
        ``enable`` is called.
        """
        definition = await self.repo.get_definition_or_404(definition_id)
        manifest = data.manifest.model_dump(exclude_none=True)
        problems = self.registry.validate_manifest(manifest)
        if problems:
            raise ValidationError("invalid extension manifest: " + "; ".join(problems))

        # The manifest's identity must match the registered definition.
        manifest_identity = manifest.get("identity") or {}
        if manifest_identity.get("extension_id") != definition.extension_id:
            raise ValidationError(
                "manifest identity.extension_id must match the registered extension_id"
            )
        version = manifest_identity.get("version")
        if not isinstance(version, str) or parse_version(version) is None:
            raise ValidationError(f"invalid semantic version: {version!r}")
        core_compat = manifest_identity.get("core_compat")
        if not core_satisfies(core_compat):
            raise ConflictError(
                f"extension {definition.extension_id!r} requires core {core_compat!r}, "
                f"running core is {CORE_VERSION}"
            )

        previous = await self.repo.find_current_version(definition.id)
        if previous is not None:
            if previous.version == version:
                raise ConflictError(
                    f"extension version {version!r} already published for "
                    f"{definition.extension_id!r}"
                )
            previous.is_current = False
            previous.status = VER_STATUS_SUPERSEDED

        record = ExtensionVersion(
            campus_id=definition.campus_id,
            extension_def_id=definition.id,
            version=version,
            manifest=manifest,
            status=VER_STATUS_PENDING,
            is_current=True,
            created_by=data.created_by or _actor_id(actor),
        )
        record = await self.repo.create_version(record)

        definition.core_compat = core_compat
        definition.current_version = version
        definition.status = EXT_STATUS_INSTALLED
        await self.session.flush()

        await self.audit.record(
            action="PUBLISH",
            resource_type="extension_version",
            resource_id=str(record.id),
            actor=actor,
            details={
                "extension_id": definition.extension_id,
                "version": version,
                "core_compat": core_compat,
            },
        )
        return record

    async def enable(
        self,
        definition_id: int,
        *,
        version_id: Optional[int] = None,
        actor: AuditActor | None = None,
    ) -> ExtensionVersion:
        """Enable a pending version.

        The authorization gate: every permission the version's manifest
        declares must already be granted, or ``enable`` fails listing the
        missing grants.  An extension can never run with unapproved
        capabilities.
        """
        definition = await self.repo.get_definition_or_404(definition_id)
        if definition.status == EXT_STATUS_RETIRED:
            raise ConflictError("a retired extension cannot be enabled")
        version = (
            await self.repo.get_version_or_404(version_id)
            if version_id is not None
            else await self.repo.find_current_version(definition.id)
        )
        if version is None:
            raise NotFoundError("no extension version to enable")
        if version.extension_def_id != definition.id:
            raise ValidationError("version does not belong to this extension")
        if version.status not in (VER_STATUS_PENDING, VER_STATUS_DISABLED):
            raise ConflictError(
                f"only a pending or disabled version can be enabled (got {version.status!r})"
            )

        missing = await self._missing_grants(definition.id, version)
        if missing:
            raise ValidationError(
                "cannot enable: missing permission grant(s): " + ", ".join(sorted(missing))
            )

        version.status = VER_STATUS_ENABLED
        version.installed_by = _actor_id(actor)
        version.installed_at = _now()
        definition.status = EXT_STATUS_INSTALLED
        await self.session.flush()

        await self.audit.record(
            action="ENABLE",
            resource_type="extension_version",
            resource_id=str(version.id),
            actor=actor,
            details={
                "extension_id": definition.extension_id,
                "version": version.version,
            },
        )
        return version

    async def disable(
        self,
        definition_id: int,
        *,
        actor: AuditActor | None = None,
    ) -> ExtensionVersion | None:
        """Disable the currently enabled version (if any)."""
        definition = await self.repo.get_definition_or_404(definition_id)
        version = await self.repo.find_current_version(definition.id)
        if version is None or version.status != VER_STATUS_ENABLED:
            return None
        version.status = VER_STATUS_DISABLED
        definition.status = EXT_STATUS_DISABLED
        await self.session.flush()
        await self.audit.record(
            action="DISABLE",
            resource_type="extension_version",
            resource_id=str(version.id),
            actor=actor,
            details={"extension_id": definition.extension_id, "version": version.version},
        )
        return version

    async def retire(
        self,
        definition_id: int,
        *,
        actor: AuditActor | None = None,
    ) -> ExtensionDefinition:
        """Terminal lifecycle state — uninstall the extension."""
        definition = await self.repo.get_definition_or_404(definition_id)
        if definition.status == EXT_STATUS_RETIRED:
            return definition
        current = await self.repo.find_current_version(definition.id)
        if current is not None and current.status == VER_STATUS_ENABLED:
            current.status = VER_STATUS_DISABLED
        definition.status = EXT_STATUS_RETIRED
        await self.session.flush()
        await self.audit.record(
            action="RETIRE",
            resource_type="extension",
            resource_id=str(definition.id),
            actor=actor,
            details={"extension_id": definition.extension_id},
        )
        return definition

    # ------------------------------------------------------------------
    # Grants (the authorization gate)
    # ------------------------------------------------------------------

    async def grant_permission(
        self,
        definition_id: int,
        data: GrantCreate,
        actor: AuditActor | None = None,
    ) -> ExtensionGrant:
        """Grant a permission to an extension.  Idempotent.  The permission
        must be a valid ``scope.action`` from the closed catalogs."""
        definition = await self.repo.get_definition_or_404(definition_id)
        if definition.status == EXT_STATUS_RETIRED:
            raise ConflictError("a retired extension cannot receive grants")
        if not self.registry.valid_permission(data.permission):
            raise ValidationError(f"unknown permission {data.permission!r} (format scope.action)")
        existing = await self.repo.find_grant(definition.id, data.permission)
        if existing is not None:
            return existing
        scope = data.permission.split(".")[0]
        # Re-granting a previously revoked permission resurrects the original
        # row (the ``(extension_def_id, permission)`` unique constraint keeps
        # one row per permission forever).
        revoked = await self.repo.find_grant_any(definition.id, data.permission)
        if revoked is not None:
            revoked.revoked_at = None
            revoked.granted_by = data.granted_by or _actor_id(actor)
            revoked.granted_at = _now()
            grant = revoked
        else:
            grant = ExtensionGrant(
                campus_id=definition.campus_id,
                extension_def_id=definition.id,
                permission=data.permission,
                scope=scope,
                granted_by=data.granted_by or _actor_id(actor),
            )
            grant = await self.repo.create_grant(grant)
        await self.audit.record(
            action="GRANT",
            resource_type="extension_grant",
            resource_id=str(grant.id),
            actor=actor,
            details={
                "extension_id": definition.extension_id,
                "permission": data.permission,
            },
        )
        return grant

    async def revoke_permission(
        self,
        definition_id: int,
        permission: str,
        actor: AuditActor | None = None,
    ) -> ExtensionGrant | None:
        """Revoke a grant.  If the current enabled version still declares
        the permission, the extension is automatically disabled — it can
        never keep running with a capability that was revoked."""
        definition = await self.repo.get_definition_or_404(definition_id)
        grant = await self.repo.find_grant(definition.id, permission)
        if grant is None:
            return None
        grant.revoked_at = _now()
        await self.session.flush()

        current = await self.repo.find_current_version(definition.id)
        if current is not None and current.status == VER_STATUS_ENABLED:
            missing = await self._missing_grants(definition.id, current)
            if missing:
                current.status = VER_STATUS_DISABLED
                definition.status = EXT_STATUS_DISABLED

        await self.audit.record(
            action="REVOKE",
            resource_type="extension_grant",
            resource_id=str(grant.id),
            actor=actor,
            details={
                "extension_id": definition.extension_id,
                "permission": permission,
                "auto_disabled": current is not None and current.status == VER_STATUS_DISABLED,
            },
        )
        return grant

    async def _missing_grants(self, definition_id: int, version: ExtensionVersion) -> set[str]:
        """Declared permissions without an active grant."""
        declared = {
            perm["permission"]
            for perm in (version.manifest or {}).get("permissions", [])
            if isinstance(perm, dict) and isinstance(perm.get("permission"), str)
        }
        if not declared:
            return set()
        granted = {g.permission for g in await self.repo.list_active_grants(definition_id)}
        return declared - granted

    # ------------------------------------------------------------------
    # Configuration (validated against the declared schema)
    # ------------------------------------------------------------------

    async def set_config(
        self,
        definition_id: int,
        data: ConfigUpdate,
        actor: AuditActor | None = None,
    ) -> ExtensionConfig:
        """Set the extension's configuration.

        Values are validated against the ``config_schema`` declared in the
        current version's manifest before they can be stored.  An
        extension's configuration can never violate its own declared
        schema.
        """
        definition = await self.repo.get_definition_or_404(definition_id)
        current = await self.repo.find_current_version(definition.id)
        if current is None:
            raise NotFoundError("extension has no published version to configure")
        schema = (current.manifest or {}).get("config_schema")
        problems = validate_config_value(schema, data.config)
        if problems:
            raise ValidationError("invalid extension configuration: " + "; ".join(problems))
        config = ExtensionConfig(
            campus_id=definition.campus_id,
            extension_def_id=definition.id,
            config=data.config,
            schema_version=current.version,
            updated_by=data.updated_by or _actor_id(actor),
        )
        saved = await self.repo.upsert_config(config)
        await self.audit.record(
            action="CONFIGURE",
            resource_type="extension_config",
            resource_id=str(saved.id),
            actor=actor,
            details={
                "extension_id": definition.extension_id,
                "schema_version": current.version,
            },
        )
        return saved

    # ------------------------------------------------------------------
    # Policy enforcement (extensions cannot bypass policy)
    # ------------------------------------------------------------------

    async def check_policy(
        self,
        definition_id: int,
        policy_id: str,
        data: dict[str, Any],
        actor: AuditActor | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> str:
        """Evaluate a named policy for an extension operation.

        Extensions may declare a policy scope, but the actual decision
        always goes through the policy engine.  On ``deny`` this raises
        ``AuthorizationError`` (fail closed); ``review`` and ``allow``
        return the decision so the caller can route accordingly.
        """
        definition = await self.repo.get_definition_or_404(definition_id)
        if definition.status == EXT_STATUS_RETIRED:
            raise ConflictError("a retired extension cannot perform operations")
        policy_service = PolicyService(self.session, self.tenant)
        result = await policy_service.evaluate(
            policy_id,
            EvaluateInput(
                subject_type=subject_type,
                subject_id=subject_id,
                data=data,
                evaluated_by=_actor_id(actor),
            ),
            actor=actor,
        )
        if result.decision == "deny":
            raise AuthorizationError(
                f"extension {definition.extension_id!r} denied by policy {policy_id!r}: "
                f"{result.reason}"
            )
        return result.decision

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_definition(self, definition_id: int) -> ExtensionDefinition:
        return await self.repo.get_definition_or_404(definition_id)

    async def list_definitions(
        self,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[ExtensionDefinition], int]:
        return await self.repo.list_definitions(status=status, skip=skip, limit=limit)

    async def list_versions(
        self,
        definition_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[ExtensionVersion], int]:
        return await self.repo.list_versions(definition_id, skip=skip, limit=limit)

    async def list_grants(
        self,
        definition_id: int,
        *,
        include_revoked: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[ExtensionGrant], int]:
        return await self.repo.list_grants(
            definition_id,
            include_revoked=include_revoked,
            skip=skip,
            limit=limit,
        )

    async def get_config(self, definition_id: int) -> Optional[ExtensionConfig]:
        return await self.repo.get_config(definition_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _actor_id(actor: AuditActor | None) -> Optional[int]:
    if actor is None or actor.actor_type != ActorType.USER:
        return None
    raw = actor.actor_id
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)
