"""P15 — contextual communications.

This module is the boundary between the communications domain and the
operational entities a message can be linked to (student, case, fee due,
admission). It owns two things:

1. :func:`render_template_variables` — a *bounded* template renderer.
   ``{name}`` and ``{name.path}`` placeholders are resolved from a flat
   variables dict. There is deliberately NO Python ``format`` spec syntax
   (``{:s}``), NO attribute access and NO indexing, so a template can never
   read objects the sender did not explicitly provide — no arbitrary code
   execution, no ``__globals__``-style tricks.

2. :func:`load_context_variables` — deterministic per-entity loaders that
   turn a live record into a variables dict (student name / class /
   attendance, case number / priority / status, fee amount / due date,
   applicant name / status) plus the guardian user ids linked to a student
   (used to validate parent recipients against the context).
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.communications.constants import (
    CONTEXT_ADMISSION,
    CONTEXT_ANNOUNCEMENT,
    CONTEXT_CASE,
    CONTEXT_FEE_DUE,
    CONTEXT_STUDENT,
)
from app.multi_tenant.guards import assert_tenant_scope
from app.multi_tenant.models import TenantContext

# {name} or {name.path} — dot-notation keys only, no format specs.
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.]*)\}")


def render_template_variables(
    text: str,
    variables: dict[str, Any],
    escape: bool = True,
) -> str:
    """Resolve ``{name}`` / ``{name.path}`` placeholders against a flat dict.

    * Unknown keys and dead paths render as ``""`` (never crash, never leak
      the raw placeholder).
    * The default ``escape=True`` is the delivery-safe path (HTML/JS
      entities are stripped). ``escape=False`` is for plain-text channels.
    * No format specs, no attribute/index access — the regex above only
      allows identifiers and dots.
    """

    def _lookup(path: str) -> Any:
        node: Any = variables
        for part in path.split("."):
            if isinstance(node, dict):
                if part not in node:
                    return ""
                node = node[part]
            elif node is None:
                return ""
            else:
                # non-dict nodes cannot be traversed further
                return ""
        if node is None:
            return ""
        return str(node)

    def _replace(m: re.Match[str]) -> str:
        value = _lookup(m.group(1))
        if not escape:
            return value
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    return _PLACEHOLDER.sub(_replace, text)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return str(value)


def _iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value)


# ── Entity loaders ────────────────────────────────────────────────────


async def load_context_variables(
    session: AsyncSession,
    context_type: str,
    context_id: int,
    tenant: TenantContext | None = None,
) -> dict[str, Any]:
    """Deterministic variable dict for an operational context.

    Each loader is intentionally small and keyed to the entity's real
    columns — a template author can rely on ``{student.name}``,
    ``{case.number}``, ``{fee.amount}``, ``{applicant.name}`` etc.

    ``tenant`` is the caller's :class:`TenantContext` (from the router's
    ``require_tenant_context`` dependency). When provided, every loaded
    entity is passed through :func:`assert_tenant_scope` so a caller can
    never read a context entity belonging to another campus (IDOR). When
    ``None`` (background jobs, tests) no guard is applied.
    """
    loader = _LOADERS.get(context_type)
    if loader is None:
        raise NotFoundError(f"Unknown context type: {context_type}")
    return await loader(session, context_id, tenant=tenant)


async def _load_student(
    session: AsyncSession,
    student_id: int,
    tenant: TenantContext | None = None,
) -> dict[str, Any]:
    from app.domains.student.models import Student

    result = await session.execute(select(Student).where(Student.id == student_id))
    s = result.scalar_one_or_none()
    if s is None:
        raise NotFoundError(f"Student {student_id} not found")
    if tenant is not None:
        assert_tenant_scope(s, tenant, resource="student")

    class_name = None
    section_name = None
    try:
        from app.domains.academic.models import Class, Enrollment, Section

        row = await session.execute(
            select(Class.name, Section.name)
            .select_from(Enrollment)
            .join(Class, Class.id == Enrollment.class_id)
            .outerjoin(Section, Section.id == Enrollment.section_id)
            .where(
                Enrollment.student_id == student_id,
                Enrollment.status == "active",
            )
            .limit(1)
        )
        pair = row.first()
        if pair:
            class_name, section_name = pair
    except Exception:
        # enrollment data is best-effort — never block messaging on it
        pass

    return {
        "student": {
            "id": s.id,
            "name": f"{s.first_name} {s.last_name}".strip(),
            "first_name": s.first_name,
            "last_name": s.last_name,
            "number": s.student_number,
            "email": s.email or "",
            "status": s.status,
            "class": class_name or "",
            "section": section_name or "",
        }
    }


async def _load_case(
    session: AsyncSession,
    case_id: int,
    tenant: TenantContext | None = None,
) -> dict[str, Any]:
    from app.domains.cases.models import Case

    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if case is None:
        raise NotFoundError(f"Case {case_id} not found")
    if tenant is not None:
        assert_tenant_scope(case, tenant, resource="case")
    return {
        "case": {
            "id": case.id,
            "number": case.case_number,
            "title": case.title,
            "type": case.case_type,
            "priority": case.priority,
            "status": case.status,
            "student_id": case.student_id or "",
            "due_at": _iso(case.due_at),
        }
    }


async def _load_fee_due(
    session: AsyncSession,
    fee_due_id: int,
    tenant: TenantContext | None = None,
) -> dict[str, Any]:
    from app.domains.fees.models import FeeDue

    result = await session.execute(select(FeeDue).where(FeeDue.id == fee_due_id))
    due = result.scalar_one_or_none()
    if due is None:
        raise NotFoundError(f"Fee due {fee_due_id} not found")
    if tenant is not None:
        assert_tenant_scope(due, tenant, resource="fee due")
    return {
        "fee": {
            "id": due.id,
            "student_id": due.student_id,
            "amount": due.original_amount,
            "paid": due.amount_paid,
            "balance": max(0, due.original_amount - due.amount_paid),
            "due_date": _iso_date(due.due_date),
            "status": due.status,
        }
    }


async def _load_admission(
    session: AsyncSession,
    admission_id: int,
    tenant: TenantContext | None = None,
) -> dict[str, Any]:
    from app.domains.admission.models import AdmissionApplication

    result = await session.execute(
        select(AdmissionApplication).where(AdmissionApplication.id == admission_id)
    )
    app_row = result.scalar_one_or_none()
    if app_row is None:
        raise NotFoundError(f"Admission application {admission_id} not found")
    if tenant is not None:
        assert_tenant_scope(app_row, tenant, resource="admission application")
    return {
        "applicant": {
            "id": app_row.id,
            "name": app_row.applicant_name,
            "email": app_row.email or "",
            "phone": app_row.phone or "",
            "status": app_row.status,
            "applied_at": _iso(app_row.applied_at),
        }
    }


async def _load_announcement(
    _session: AsyncSession,
    _id: int,
    tenant: TenantContext | None = None,
) -> dict[str, Any]:
    # Announcements are broadcast-style; there is no single entity to load.
    return {}


_LOADERS: dict[str, Any] = {
    CONTEXT_STUDENT: _load_student,
    CONTEXT_CASE: _load_case,
    CONTEXT_FEE_DUE: _load_fee_due,
    CONTEXT_ADMISSION: _load_admission,
    CONTEXT_ANNOUNCEMENT: _load_announcement,
}


# ── Context summary (for the composer's context badge) ────────────────


async def load_context_summary(
    session: AsyncSession,
    context_type: str,
    context_id: int,
    tenant: TenantContext | None = None,
) -> dict[str, Any]:
    """A short human label + the variables for a context.

    Returns ``{context_type, context_id, label, detail, variables,
    guardian_ids}``. ``guardian_ids`` (user accounts linked to the student)
    lets the composer pre-fill a parent recipient and lets the service
    validate that a parent recipient actually belongs to the context.

    ``tenant`` scoping is enforced inside :func:`load_context_variables`
    (see there) — a cross-campus context id resolves to ``NotFound`` /
    ``AuthorizationError``, never leaked data.
    """
    variables = await load_context_variables(session, context_type, context_id, tenant=tenant)
    guardian_ids: list[int] = []
    if context_type == CONTEXT_STUDENT:
        # The student was loaded + tenant-guarded above; the links that
        # follow therefore belong to an in-scope student.
        guardian_ids = await load_guardian_user_ids(session, context_id)

    label, detail = _describe(context_type, variables)
    return {
        "context_type": context_type,
        "context_id": context_id,
        "label": label,
        "detail": detail,
        "variables": variables,
        "guardian_ids": guardian_ids,
    }


def _describe(context_type: str, variables: dict[str, Any]) -> tuple[str, str]:
    if context_type == CONTEXT_STUDENT:
        st = variables.get("student", {})
        label = st.get("name", "Student")
        detail = " · ".join(
            p for p in [f"#{st.get('number', '')}", st.get("class", "")] if p
        ) or "Student"
        return label, detail
    if context_type == CONTEXT_CASE:
        cs = variables.get("case", {})
        return cs.get("number", "Case"), cs.get("title", "Case") or "Case"
    if context_type == CONTEXT_FEE_DUE:
        fee = variables.get("fee", {})
        return f"Fee #{fee.get('id', '')}", fee.get("status", "fee") or "fee"
    if context_type == CONTEXT_ADMISSION:
        ap = variables.get("applicant", {})
        return ap.get("name", "Applicant"), ap.get("status", "application") or "application"
    if context_type == CONTEXT_ANNOUNCEMENT:
        return "Announcement", "Broadcast"
    return context_type, ""


async def load_guardian_user_ids(session: AsyncSession, student_id: int) -> list[int]:
    """User accounts linked to a student via ``guardian_links``.

    Used to (a) pre-fill parent recipients in the composer and (b) validate
    that a ``parent`` recipient actually belongs to the context student —
    a staff member can only message guardians of the student the message
    is about.
    """
    from sqlalchemy import text

    try:
        result = await session.execute(
            text(
                "SELECT user_id FROM guardian_links WHERE student_id = :sid"
            ),
            {"sid": student_id},
        )
        return [row[0] for row in result.all()]
    except Exception:
        return []
