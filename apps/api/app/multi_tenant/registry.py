"""Tenant-owned model registry.

This module is the *single canonical source of truth* for how each model
participates in multi-tenant isolation.  Two classification helpers are
provided:

* :func:`tenant_scope_of` — classify a model class as one of
  ``TENANT_DIRECT``, ``TENANT_PARENT`` or ``PLATFORM``.
* :func:`tenant_filter_for` — return the SQLAlchemy predicate (and any
  required join) that scopes a query to the current tenant campus.

The repository layer (:mod:`app.multi_tenant.repository`) consults this
registry so that **every** query built for a tenant-owned model carries
the tenant predicate at construction time.  Developers adding a new model
do not need to remember to filter — they only need to declare how their
model inherits tenancy (most models already carry a ``campus_id`` column
and are classified automatically).
"""

from __future__ import annotations

import importlib
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Scope classifications
# ---------------------------------------------------------------------------

#: Model carries its own ``campus_id`` column — filtered directly.
TENANT_DIRECT = "tenant_direct"
#: Model inherits tenancy from a parent entity via a foreign key.
TENANT_PARENT = "tenant_parent"
#: Global / platform data — never tenant filtered.
PLATFORM = "platform"

_UNKNOWN = object()


# ---------------------------------------------------------------------------
# Parent-tenancy declarations.
#
# key: ``"module.path:ClassName"`` of the child model
# value: ``(parent_key, child_fk_attr, parent_tenant_attr)``
#   - parent_key      — ``"module.path:ClassName"`` of the parent model
#   - child_fk_attr   — attribute on the child that FK's to the parent PK
#   - parent_tenant_attr — tenant column on the parent (usually campus_id)
#
# These are resolved lazily to avoid import cycles between domain models
# and the multi-tenant package.
# ---------------------------------------------------------------------------

PARENT_TENANT_PATHS: dict[str, tuple[str, str, str]] = {
    # Admission sub-entities inherit tenancy from their application.
    "app.domains.admission.models:AdmissionDocument": (
        "app.domains.admission.models:AdmissionApplication",
        "application_id",
        "campus_id",
    ),
    "app.domains.admission.models:AdmissionInterview": (
        "app.domains.admission.models:AdmissionApplication",
        "application_id",
        "campus_id",
    ),
    "app.domains.admission.models:AdmissionMeritEntry": (
        "app.domains.admission.models:AdmissionApplication",
        "application_id",
        "campus_id",
    ),
    "app.domains.admission.models:AdmissionSeatAllocation": (
        "app.domains.admission.models:AdmissionApplication",
        "application_id",
        "campus_id",
    ),
    # Documents: versions and shares inherit from the document.
    "app.domains.documents.models:DocumentVersion": (
        "app.domains.documents.models:Document",
        "document_id",
        "campus_id",
    ),
    "app.domains.documents.models:DocumentShare": (
        "app.domains.documents.models:Document",
        "document_id",
        "campus_id",
    ),
    # Communications: per-message children inherit from the message.
    "app.domains.communications.models:MessageRecipient": (
        "app.domains.communications.models:CommunicationMessage",
        "message_id",
        "campus_id",
    ),
    "app.domains.communications.models:MessageAttachment": (
        "app.domains.communications.models:CommunicationMessage",
        "message_id",
        "campus_id",
    ),
    "app.domains.communications.models:MessageSchedule": (
        "app.domains.communications.models:CommunicationMessage",
        "message_id",
        "campus_id",
    ),
    # Attendance intelligence: per-student records inherit from the period.
    "app.domains.attendance_intelligence.models:PeriodAttendanceRecord": (
        "app.domains.attendance_intelligence.models:PeriodAttendance",
        "period_attendance_id",
        "campus_id",
    ),
    # Academic ops: substitutions inherit from the timetable entry.
    "app.domains.academic_ops.models:Substitution": (
        "app.domains.academic_ops.models:TimetableEntry",
        "timetable_entry_id",
        "campus_id",
    ),
    # School finance: reconciliation items inherit from the reconciliation.
    "app.domains.school_finance.models:ReconciliationItem": (
        "app.domains.school_finance.models:PaymentReconciliation",
        "reconciliation_id",
        "campus_id",
    ),
    # Workflow: approval history inherits from the workflow instance.
    "app.domains.workflow.models:ApprovalHistory": (
        "app.domains.workflow.models:WorkflowInstance",
        "instance_id",
        "campus_id",
    ),
    # Student portal: submissions inherit from the assignment, which in
    # turn inherits from its academic year (carries campus_id).
    "app.domains.student_portal.models:AssignmentSubmission": (
        "app.domains.student_portal.models:Assignment",
        "assignment_id",
        "campus_id",
    ),
}

_IMPORT_CACHE: dict[str, Any] = {}


def _resolve(key: str) -> Any:
    if key in _IMPORT_CACHE:
        return _IMPORT_CACHE[key]
    module_path, _, class_name = key.partition(":")
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    _IMPORT_CACHE[key] = cls
    return cls


def _class_key(model: Any) -> Optional[str]:
    return f"{model.__module__}:{model.__name__}"


def _resolve_parent(model: Any) -> Optional[tuple[Any, str, str]]:
    """Resolve the parent declaration for a model, or ``None``."""
    entry = PARENT_TENANT_PATHS.get(_class_key(model))
    if entry is None:
        return None
    parent_key, child_fk_attr, parent_tenant_attr = entry
    return _resolve(parent_key), child_fk_attr, parent_tenant_attr


def tenant_scope_of(model: Any) -> str:
    """Classify ``model`` into one of the scope constants.

    A model with a direct ``campus_id`` column, or one declared in the
    parent registry, is tenant-owned.  Everything else is treated as
    platform data (so global tables such as ``roles``, ``permissions``,
    ``plans`` and ``migration_runs`` are never accidentally filtered).
    """
    if hasattr(model, "campus_id"):
        return TENANT_DIRECT
    if _resolve_parent(model) is not None:
        return TENANT_PARENT
    return PLATFORM


def tenant_join_spec(model: Any) -> Optional[tuple[Any, Any, Any]]:
    """Return ``(parent_cls, join_condition, parent_tenant_attr)`` for a
    parent-scoped model, or ``None`` when the model is directly scoped or
    platform data."""
    resolved = _resolve_parent(model)
    if resolved is None:
        return None
    parent_cls, child_fk_attr, parent_tenant_attr = resolved
    child_fk = getattr(model, child_fk_attr)
    join_condition = child_fk == getattr(parent_cls, "id")
    return parent_cls, join_condition, parent_tenant_attr


def tenant_filter_for(model: Any, campus_id: int) -> Optional[tuple[Any, ...]]:
    """Return the tenant predicate (and join specification, if needed).

    Returns a tuple ``(predicate, join_spec)`` where ``join_spec`` is
    ``None`` for directly-scoped models and ``(parent_cls, onclause)``
    for parent-scoped models.  Returns ``None`` for platform models.

    Callers apply the predicate to both the SELECT and the COUNT query.
    """
    scope = tenant_scope_of(model)
    if scope == TENANT_DIRECT:
        return (getattr(model, "campus_id") == campus_id, None)
    if scope == TENANT_PARENT:
        parent_cls, onclause, parent_tenant_attr = tenant_join_spec(model)  # type: ignore[misc]
        predicate = getattr(parent_cls, parent_tenant_attr) == campus_id
        return (predicate, (parent_cls, onclause))
    return None


def apply_tenant_filter(query: Any, model: Any, campus_id: int) -> Any:
    """Apply the canonical tenant filter to a SELECT query.

    ``campus_id`` must be a concrete integer — callers are responsible
    for resolving the effective scope first (see ``guards.effective_campus_id``).
    """
    spec = tenant_filter_for(model, campus_id)
    if spec is None:
        return query
    predicate, join_spec = spec
    if join_spec is not None:
        parent_cls, onclause = join_spec
        query = query.join(parent_cls, onclause)
    return query.where(predicate)
