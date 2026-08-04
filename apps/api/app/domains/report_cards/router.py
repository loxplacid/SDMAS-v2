from __future__ import annotations

from typing import Optional, TypeVar

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.dependencies import require_role
from app.domains.auth.models import User
from app.domains.report_cards.pdf import (
    build_class_marksheet_pdf,
    build_report_card_pdf,
)
from app.domains.report_cards.schemas import (
    ClassMarksheet,
    StudentReportCard,
)
from app.domains.report_cards.service import ReportCardService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import assert_tenant_scope
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/report-cards", tags=["report-cards"])

# Report cards are an academic/reporting capability — every leadership
# role (and teachers, who enter the grades) may view them.
_REPORT_ROLES = ("admin", "principal", "staff", "teacher", "accountant")


async def get_report_card_service(
    session: AsyncSession = Depends(get_session),
) -> ReportCardService:
    return ReportCardService(session)


_T = TypeVar("_T")


async def _tenant_guard(
    session: AsyncSession,
    tenant: TenantContext,
    model: type[_T],
    resource_id: int,
    resource: str,
) -> _T:
    """Load the tenant-owned parent record and assert it belongs to the
    caller's campus (IDOR guard), mirroring the student-360 pattern.

    Returns the entity so callers can reuse it (no second fetch).
    """
    entity = await session.get(model, resource_id)
    if entity is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError(f"{resource} {resource_id} not found")
    assert_tenant_scope(entity, tenant, resource=resource)
    return entity


@router.get("/students/{student_id}", response_model=StudentReportCard)
async def get_student_report_card(
    student_id: int,
    academic_year_id: int = Query(..., alias="academic_year_id"),
    term_id: Optional[int] = Query(None, alias="term_id"),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
    service: ReportCardService = Depends(get_report_card_service),
    _user: User = Depends(require_role(*_REPORT_ROLES)),
) -> StudentReportCard:
    from app.domains.student.models import Student

    await _tenant_guard(session, tenant, Student, student_id, "student")
    return await service.get_student_report_card(
        student_id, academic_year_id, term_id
    )


@router.get("/students/{student_id}/pdf")
async def get_student_report_card_pdf(
    student_id: int,
    academic_year_id: int = Query(..., alias="academic_year_id"),
    term_id: Optional[int] = Query(None, alias="term_id"),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
    service: ReportCardService = Depends(get_report_card_service),
    _user: User = Depends(require_role(*_REPORT_ROLES)),
) -> Response:
    from app.domains.student.models import Student

    await _tenant_guard(session, tenant, Student, student_id, "student")
    card = await service.get_student_report_card(
        student_id, academic_year_id, term_id
    )
    content = build_report_card_pdf(card)
    filename = f"report-card-{card.student_number}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/classes/{class_id}", response_model=ClassMarksheet)
async def get_class_marksheet(
    class_id: int,
    academic_year_id: int = Query(..., alias="academic_year_id"),
    term_id: Optional[int] = Query(None, alias="term_id"),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
    service: ReportCardService = Depends(get_report_card_service),
    _user: User = Depends(require_role(*_REPORT_ROLES)),
) -> ClassMarksheet:
    from app.domains.academic.models import Class

    await _tenant_guard(session, tenant, Class, class_id, "class")
    return await service.get_class_marksheet(
        class_id, academic_year_id, term_id
    )


@router.get("/classes/{class_id}/pdf")
async def get_class_marksheet_pdf(
    class_id: int,
    academic_year_id: int = Query(..., alias="academic_year_id"),
    term_id: Optional[int] = Query(None, alias="term_id"),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
    service: ReportCardService = Depends(get_report_card_service),
    _user: User = Depends(require_role(*_REPORT_ROLES)),
) -> Response:
    from app.domains.academic.models import Class

    await _tenant_guard(session, tenant, Class, class_id, "class")
    marksheet = await service.get_class_marksheet(
        class_id, academic_year_id, term_id
    )
    content = build_class_marksheet_pdf(marksheet)
    filename = f"marksheet-class-{class_id}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
