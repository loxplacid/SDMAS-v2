"""Zero-fork extension architecture (platform).

A controlled extension system: core SDMAS + tenant-specific extension
without customer-specific forks of the core repository.

The internal contract is a *manifest* — a JSON document declaring what an
extension provides and what it requires from the core:

- ``identity``     — extension_id, name, provider, version, core_compat
- ``permissions``  — declared permission requirements (``scope.action``)
- ``routes``       — API routes, namespaced under ``/api/v1/ext/{id}/``
- ``events``       — platform event types the extension subscribes to
- ``config_schema``— JSON schema the extension's configuration must match
- ``migrations``   — alembic revision ids the extension ships
- ``frontend``     — frontend registration (entrypoint, routes, menu)
- ``policy``       — policy scope the extension's operations are subject to

The contract is **closed**: every field is validated against the catalogs
in :class:`ExtensionRegistry` (permission grammar, route mount root,
platform event catalog, policy scopes) before a manifest can be stored.
No code is ever evaluated from a manifest — routes/events/migrations are
declarations the core app wires through its own router/dispatcher/alembic
flow.

Extensions cannot bypass the platform's guarantees:

- **Tenant isolation** — every table carries ``campus_id`` (direct tenant
  scoping) and the repository pins it on every query.
- **Authorization**    — declared permissions must be granted by an
  administrator before ``enable`` succeeds; revoking a required permission
  auto-disables the extension.
- **Audit**            — every lifecycle mutation is recorded through the
  audit domain.
- **Policy**           — declared policy scopes come from the policy
  engine's catalog, and ``check_policy`` routes actual decisions through
  :class:`PolicyService` (deny raises, fail closed).
- **Data validation**  — manifests and configuration values are validated
  before they can be stored.

Lifecycle: ``register`` -> ``publish_version`` (pending) ->
``grant_permission`` (per declared permission) -> ``enable``.
``disable`` pauses; ``retire`` is terminal.  Versioning is semver-based
with a required ``core_compat`` range (see ``compat.py``).
"""

from app.platform.extensions.compat import (
    CORE_VERSION,
    Version,
    core_satisfies,
    parse_version,
    satisfies,
)
from app.platform.extensions.manifest import (
    CONFIG_TYPES,
    ENTRYPOINT_RE,
    EXTENSION_ID_RE,
    MENU_ID_RE,
    MIGRATION_REVISION_RE,
    ROUTE_METHODS,
    validate_config_value,
    validate_manifest,
)
from app.platform.extensions.models import (
    EXT_STATUS_DISABLED,
    EXT_STATUS_INSTALLED,
    EXT_STATUS_REGISTERED,
    EXT_STATUS_RETIRED,
    EXT_STATUSES,
    VER_STATUS_DISABLED,
    VER_STATUS_ENABLED,
    VER_STATUS_PENDING,
    VER_STATUS_SUPERSEDED,
    VER_STATUSES,
    ExtensionConfig,
    ExtensionDefinition,
    ExtensionGrant,
    ExtensionVersion,
)
from app.platform.extensions.registry import (
    DEFAULT_SUBSCRIBE_CATALOG,
    PERMISSION_ACTIONS,
    PERMISSION_SCOPES,
    ROUTE_MOUNT_ROOT,
    ExtensionRegistry,
    extension_registry,
)
from app.platform.extensions.repository import ExtensionRepository
from app.platform.extensions.service import ExtensionService

__all__ = [
    "CORE_VERSION",
    "Version",
    "core_satisfies",
    "parse_version",
    "satisfies",
    "CONFIG_TYPES",
    "ENTRYPOINT_RE",
    "EXTENSION_ID_RE",
    "MENU_ID_RE",
    "MIGRATION_REVISION_RE",
    "ROUTE_METHODS",
    "validate_config_value",
    "validate_manifest",
    "EXT_STATUS_DISABLED",
    "EXT_STATUS_INSTALLED",
    "EXT_STATUS_REGISTERED",
    "EXT_STATUS_RETIRED",
    "EXT_STATUSES",
    "VER_STATUS_DISABLED",
    "VER_STATUS_ENABLED",
    "VER_STATUS_PENDING",
    "VER_STATUS_SUPERSEDED",
    "VER_STATUSES",
    "ExtensionConfig",
    "ExtensionDefinition",
    "ExtensionGrant",
    "ExtensionVersion",
    "DEFAULT_SUBSCRIBE_CATALOG",
    "PERMISSION_ACTIONS",
    "PERMISSION_SCOPES",
    "ROUTE_MOUNT_ROOT",
    "ExtensionRegistry",
    "extension_registry",
    "ExtensionRepository",
    "ExtensionService",
]
