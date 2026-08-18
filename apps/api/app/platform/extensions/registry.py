"""Extension registry — the closed catalogs of the extension contract.

:class:`ExtensionRegistry` is the single source of truth for what an
extension may declare.  No concrete extensions are hard-coded here; the
registry only catalogs:

- **permission scopes/actions** — the ``scope.action`` grammar extensions
  may require (e.g. ``students.read``, ``fees.write``)
- **route mount root** — every extension route must live under
  ``/api/v1/ext/{extension_id}/`` so extensions can never shadow core routes
- **event subscribe catalog** — the platform event types an extension may
  subscribe to (mirrors ``app.domains.events.catalog.EVENT_CATALOG``; the
  app layer may inject the live catalog at startup)
- **policy scopes** — delegated to the policy registry's catalog, so an
  extension's declared policy scope is exactly the set the policy engine
  understands

``validate_manifest`` runs the full manifest through the closed validators;
a manifest with any unknown permission, out-of-root route, unknown event
type, malformed config schema, or invalid policy scope is rejected before
it can be stored.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

from app.platform.extensions.manifest import (
    validate_manifest as _validate_manifest,
)
from app.platform.policy.registry import PolicyRegistry, policy_registry

#: Safe route/frontend path segment (no dots — no traversal).
_SAFE_SEGMENT_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

# ---------------------------------------------------------------------------
# Closed catalogs
# ---------------------------------------------------------------------------

#: Permission scopes — the platform domains extensions may touch.
PERMISSION_SCOPES = frozenset(
    {
        "students",
        "teachers",
        "parents",
        "academics",
        "attendance",
        "fees",
        "school_finance",
        "admission",
        "documents",
        "communications",
        "reports",
        "migration",
        "audit",
        "settings",
        "platform",
        "global",
    }
)

#: Permission actions within a scope.
PERMISSION_ACTIONS = frozenset({"read", "write", "delete", "admin", "export", "execute"})

#: Route mount root — every extension route must live under this prefix.
ROUTE_MOUNT_ROOT = "/api/v1/ext/"

#: Default event subscribe catalog.  Mirrors the event types registered in
#: ``app.domains.events.catalog.EVENT_CATALOG`` at the time of writing; the
#: app layer can pass the live catalog when constructing the registry.
DEFAULT_SUBSCRIBE_CATALOG = frozenset(
    {
        "academic_year.rollover_completed",
        "academic_year.rollover_completed_legacy",
        "academic_year.rollover_failed",
        "academic_year.rollover_started",
        "admin.important",
        "admission.approved",
        "admission.rejected",
        "admission.submitted",
        "attendance.recorded",
        "attendance.threshold_breached",
        "batch.operation_completed",
        "document.uploaded",
        "document.verified",
        "fee.due_created",
        "leave.approved",
        "leave.rejected",
        "leave.submitted",
        "payment.overdue",
        "payment.recorded",
        "student.created",
        "student.enrolled",
        "student.status_changed",
        "student.updated",
        "workflow.approved",
        "workflow.cancelled",
        "workflow.rejected",
        "workflow.submitted",
    }
)


class ExtensionRegistry:
    """Closed catalogs for the extension contract (stateless)."""

    def __init__(
        self,
        *,
        subscribe_catalog: Optional[Iterable[str]] = None,
        policy_registry_: Optional[PolicyRegistry] = None,
    ) -> None:
        self._subscribe = frozenset(
            subscribe_catalog if subscribe_catalog is not None else DEFAULT_SUBSCRIBE_CATALOG
        )
        self._policy_registry = policy_registry_ or policy_registry

    # ------------------------------------------------------------------
    # Catalog queries
    # ------------------------------------------------------------------

    @property
    def subscribe_catalog(self) -> frozenset:
        return self._subscribe

    def valid_permission(self, permission: str) -> bool:
        """Whether ``permission`` matches the ``scope.action`` grammar and
        both sides are in the closed catalogs."""
        if not isinstance(permission, str):
            return False
        parts = permission.split(".")
        if len(parts) != 2:
            return False
        scope, action = parts
        return scope in PERMISSION_SCOPES and action in PERMISSION_ACTIONS

    def valid_route_path(self, extension_id: str, path: str) -> bool:
        """Whether ``path`` is a legal extension route: under the mount
        root, namespaced by the extension id, with only safe segments."""
        prefix = f"{ROUTE_MOUNT_ROOT}{extension_id}"
        if not path.startswith(prefix + "/"):
            return False
        for segment in path[len(prefix) + 1 :].split("/"):
            if not segment or not _SAFE_SEGMENT_RE.match(segment):
                return False
        return True

    def valid_event(self, event_type: str) -> bool:
        return isinstance(event_type, str) and event_type in self._subscribe

    def valid_policy_scope(self, scope: str) -> bool:
        return self._policy_registry.has_scope(scope)

    # ------------------------------------------------------------------
    # Manifest validation
    # ------------------------------------------------------------------

    def validate_manifest(self, manifest: dict) -> list[str]:
        """Validate a manifest against the closed catalogs.

        Returns a list of problem strings (empty == valid).  The manifest
        is never mutated here.
        """
        return _validate_manifest(manifest, self)


#: Module-level default registry (stateless — safe to share).
extension_registry = ExtensionRegistry()

__all__ = [
    "PERMISSION_SCOPES",
    "PERMISSION_ACTIONS",
    "ROUTE_MOUNT_ROOT",
    "DEFAULT_SUBSCRIBE_CATALOG",
    "ExtensionRegistry",
    "extension_registry",
]
