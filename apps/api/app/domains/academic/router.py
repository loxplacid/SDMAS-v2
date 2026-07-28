from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    SectionRepository,
    EnrollmentRepository,
    TermRepository,
    SubjectRepository,
    TeacherRepository,
    TeacherAssignmentRepository,
)
from app.domains.academic.schemas import (
    AcademicYearCreate,
    AcademicYearResponse,
    AcademicYearUpdate,
    ClassCreate,
    ClassResponse,
    ClassUpdate,
    SectionCreate,
    SectionResponse,
    SectionUpdate,
    EnrollmentCreate,
    EnrollmentResponse,
    EnrollmentUpdate,
    TermCreate,
    TermResponse,
    TermUpdate,
    SubjectCreate,
    SubjectResponse,
    SubjectUpdate,
    TeacherCreate,
    TeacherResponse,
    TeacherUpdate,
    TeacherAssignmentCreate,
    TeacherAssignmentResponse,
)
from app.domains.academic.service import (
    AcademicYearService,
    ClassService,
    SectionService,
    EnrollmentService,
    TermService,
    SubjectService,
    TeacherService,
    TeacherAssignmentService,
)
from app.domains.student.repository import StudentRepository
from app.infrastructure.database import get_session

router = APIRouter(prefix="/api", tags=["academic"])


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


async def get_year_service(
    session: AsyncSession = Depends(get_session),
) -> AcademicYearService:
    return AcademicYearService(AcademicYearRepository(session))


async def get_class_service(
    session: AsyncSession = Depends(get_session),
) -> ClassService:
    return ClassService(
        ClassRepository(session), AcademicYearRepository(session)
    )


async def get_section_service(
    session: AsyncSession = Depends(get_session),
) -> SectionService:
    return SectionService(
        SectionRepository(session), ClassRepository(session)
    )


async def get_enrollment_service(
    session: AsyncSession = Depends(get_session),
) -> EnrollmentService:
    return EnrollmentService(
        EnrollmentRepository(session),
        AcademicYearRepository(session),
        ClassRepository(session),
        SectionRepository(session),
        StudentRepository(session),
    )


async def get_term_service(
    session: AsyncSession = Depends(get_session),
) -> TermService:
    return TermService(
        TermRepository(session), AcademicYearRepository(session)
    )


async def get_subject_service(
    session: AsyncSession = Depends(get_session),
) -> SubjectService:
    return SubjectService(SubjectRepository(session))


async def get_teacher_service(
    session: AsyncSession = Depends(get_session),
) -> TeacherService:
    return TeacherService(TeacherRepository(session))


async def get_assignment_service(
    session: AsyncSession = Depends(get_session),
) -> TeacherAssignmentService:
    return TeacherAssignmentService(
        TeacherAssignmentRepository(session),
        TeacherRepository(session),
        ClassRepository(session),
        SubjectRepository(session),
    )


# ---------------------------------------------------------------------------
# Academic Years
# ---------------------------------------------------------------------------


@router.post(
    "/academic-years",
    response_model=AcademicYearResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_academic_year(
    data: AcademicYearCreate,
    service: AcademicYearService = Depends(get_year_service),
) -> AcademicYearResponse:
    year = await service.create_year(data)
    return AcademicYearResponse.model_validate(year)


@router.get("/academic-years/{year_id}", response_model=AcademicYearResponse)
async def get_academic_year(
    year_id: int,
    service: AcademicYearService = Depends(get_year_service),
) -> AcademicYearResponse:
    year = await service.get_year(year_id)
    return AcademicYearResponse.model_validate(year)


@router.get("/academic-years", response_model=Page[AcademicYearResponse])
async def list_academic_years(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by status"
    ),
    service: AcademicYearService = Depends(get_year_service),
) -> Page[AcademicYearResponse]:
    years, total = await service.list_years(
        status=status_filter,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    items = [AcademicYearResponse.model_validate(y) for y in years]
    return Page.create(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch("/academic-years/{year_id}", response_model=AcademicYearResponse)
async def update_academic_year(
    year_id: int,
    data: AcademicYearUpdate,
    service: AcademicYearService = Depends(get_year_service),
) -> AcademicYearResponse:
    year = await service.update_year(year_id, data)
    return AcademicYearResponse.model_validate(year)


@router.delete("/academic-years/{year_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_academic_year(
    year_id: int,
    service: AcademicYearService = Depends(get_year_service),
) -> None:
    await service.delete_year(year_id)


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------


@router.post(
    "/classes",
    response_model=ClassResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_class(
    data: ClassCreate,
    service: ClassService = Depends(get_class_service),
) -> ClassResponse:
    cls = await service.create_class(data)
    return ClassResponse.model_validate(cls)


@router.get("/classes/{class_id}", response_model=ClassResponse)
async def get_class(
    class_id: int,
    service: ClassService = Depends(get_class_service),
) -> ClassResponse:
    cls = await service.get_class(class_id)
    return ClassResponse.model_validate(cls)


@router.get("/classes", response_model=Page[ClassResponse])
async def list_classes(
    pagination: PaginationParams = Depends(),
    year_id: Optional[int] = Query(
        default=None, alias="academic_year_id", description="Filter by academic year"
    ),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by status"
    ),
    service: ClassService = Depends(get_class_service),
) -> Page[ClassResponse]:
    classes, total = await service.list_classes(
        year_id=year_id,
        status=status_filter,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    items = [ClassResponse.model_validate(c) for c in classes]
    return Page.create(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch("/classes/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: int,
    data: ClassUpdate,
    service: ClassService = Depends(get_class_service),
) -> ClassResponse:
    cls = await service.update_class(class_id, data)
    return ClassResponse.model_validate(cls)


@router.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: int,
    service: ClassService = Depends(get_class_service),
) -> None:
    await service.delete_class(class_id)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


@router.post(
    "/sections",
    response_model=SectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_section(
    data: SectionCreate,
    service: SectionService = Depends(get_section_service),
) -> SectionResponse:
    section = await service.create_section(data)
    return SectionResponse.model_validate(section)


@router.get("/sections/{section_id}", response_model=SectionResponse)
async def get_section(
    section_id: int,
    service: SectionService = Depends(get_section_service),
) -> SectionResponse:
    section = await service.get_section(section_id)
    return SectionResponse.model_validate(section)


@router.get("/sections", response_model=Page[SectionResponse])
async def list_sections(
    pagination: PaginationParams = Depends(),
    class_id: Optional[int] = Query(
        default=None, alias="class_id", description="Filter by class"
    ),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by status"
    ),
    service: SectionService = Depends(get_section_service),
) -> Page[SectionResponse]:
    sections, total = await service.list_sections(
        class_id=class_id,
        status=status_filter,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    items = [SectionResponse.model_validate(s) for s in sections]
    return Page.create(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch("/sections/{section_id}", response_model=SectionResponse)
async def update_section(
    section_id: int,
    data: SectionUpdate,
    service: SectionService = Depends(get_section_service),
) -> SectionResponse:
    section = await service.update_section(section_id, data)
    return SectionResponse.model_validate(section)


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: int,
    service: SectionService = Depends(get_section_service),
) -> None:
    await service.delete_section(section_id)


# ---------------------------------------------------------------------------
# Enrollments
# ---------------------------------------------------------------------------


@router.post(
    "/enrollments",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_enrollment(
    data: EnrollmentCreate,
    service: EnrollmentService = Depends(get_enrollment_service),
) -> EnrollmentResponse:
    enrollment = await service.create_enrollment(data)
    return EnrollmentResponse.model_validate(enrollment)


@router.get("/enrollments/{enrollment_id}", response_model=EnrollmentResponse)
async def get_enrollment(
    enrollment_id: int,
    service: EnrollmentService = Depends(get_enrollment_service),
) -> EnrollmentResponse:
    enrollment = await service.get_enrollment(enrollment_id)
    return EnrollmentResponse.model_validate(enrollment)


@router.get("/enrollments", response_model=Page[EnrollmentResponse])
async def list_enrollments(
    pagination: PaginationParams = Depends(),
    student_id: Optional[int] = Query(
        default=None, alias="student_id", description="Filter by student"
    ),
    academic_year_id: Optional[int] = Query(
        default=None,
        alias="academic_year_id",
        description="Filter by academic year",
    ),
    class_id: Optional[int] = Query(
        default=None, alias="class_id", description="Filter by class"
    ),
    section_id: Optional[int] = Query(
        default=None, alias="section_id", description="Filter by section"
    ),
    service: EnrollmentService = Depends(get_enrollment_service),
) -> Page[EnrollmentResponse]:
    enrollments, total = await service.list_enrollments(
        student_id=student_id,
        academic_year_id=academic_year_id,
        class_id=class_id,
        section_id=section_id,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    items = [EnrollmentResponse.model_validate(e) for e in enrollments]
    return Page.create(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch("/enrollments/{enrollment_id}", response_model=EnrollmentResponse)
async def update_enrollment(
    enrollment_id: int,
    data: EnrollmentUpdate,
    service: EnrollmentService = Depends(get_enrollment_service),
) -> EnrollmentResponse:
    enrollment = await service.update_enrollment(enrollment_id, data)
    return EnrollmentResponse.model_validate(enrollment)


@router.delete(
    "/enrollments/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_enrollment(
    enrollment_id: int,
    service: EnrollmentService = Depends(get_enrollment_service),
) -> None:
    await service.delete_enrollment(enrollment_id)


# ---------------------------------------------------------------------------
# Terms
# ---------------------------------------------------------------------------


@router.post(
    "/academic-years/{year_id}/terms",
    response_model=TermResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_term(
    year_id: int,
    data: TermCreate,
    service: TermService = Depends(get_term_service),
) -> TermResponse:
    term = await service.create_term(year_id, data)
    return TermResponse.model_validate(term)


@router.get("/terms/{term_id}", response_model=TermResponse)
async def get_term(
    term_id: int,
    service: TermService = Depends(get_term_service),
) -> TermResponse:
    term = await service.get_term(term_id)
    return TermResponse.model_validate(term)


@router.get("/academic-years/{year_id}/terms", response_model=Page[TermResponse])
async def list_terms(
    year_id: int,
    pagination: PaginationParams = Depends(),
    service: TermService = Depends(get_term_service),
) -> Page[TermResponse]:
    terms, total = await service.list_terms(
        year_id=year_id,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    items = [TermResponse.model_validate(t) for t in terms]
    return Page.create(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch("/terms/{term_id}", response_model=TermResponse)
async def update_term(
    term_id: int,
    data: TermUpdate,
    service: TermService = Depends(get_term_service),
) -> TermResponse:
    term = await service.update_term(term_id, data)
    return TermResponse.model_validate(term)


# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------


@router.post(
    "/subjects",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subject(
    data: SubjectCreate,
    service: SubjectService = Depends(get_subject_service),
) -> SubjectResponse:
    subject = await service.create_subject(data)
    return SubjectResponse.model_validate(subject)


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
async def get_subject(
    subject_id: int,
    service: SubjectService = Depends(get_subject_service),
) -> SubjectResponse:
    subject = await service.get_subject(subject_id)
    return SubjectResponse.model_validate(subject)


@router.get("/subjects", response_model=Page[SubjectResponse])
async def list_subjects(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by status"
    ),
    service: SubjectService = Depends(get_subject_service),
) -> Page[SubjectResponse]:
    subjects, total = await service.list_subjects(
        status=status_filter,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    items = [SubjectResponse.model_validate(s) for s in subjects]
    return Page.create(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch("/subjects/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: int,
    data: SubjectUpdate,
    service: SubjectService = Depends(get_subject_service),
) -> SubjectResponse:
    subject = await service.update_subject(subject_id, data)
    return SubjectResponse.model_validate(subject)


# ---------------------------------------------------------------------------
# Teachers
# ---------------------------------------------------------------------------


@router.post(
    "/teachers",
    response_model=TeacherResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_teacher(
    data: TeacherCreate,
    service: TeacherService = Depends(get_teacher_service),
) -> TeacherResponse:
    teacher = await service.create_teacher(data)
    return TeacherResponse.model_validate(teacher)


@router.get("/teachers/{teacher_id}", response_model=TeacherResponse)
async def get_teacher(
    teacher_id: int,
    service: TeacherService = Depends(get_teacher_service),
) -> TeacherResponse:
    teacher = await service.get_teacher(teacher_id)
    return TeacherResponse.model_validate(teacher)


@router.get("/teachers", response_model=Page[TeacherResponse])
async def list_teachers(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by status"
    ),
    service: TeacherService = Depends(get_teacher_service),
) -> Page[TeacherResponse]:
    teachers, total = await service.list_teachers(
        status=status_filter,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    items = [TeacherResponse.model_validate(t) for t in teachers]
    return Page.create(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch("/teachers/{teacher_id}", response_model=TeacherResponse)
async def update_teacher(
    teacher_id: int,
    data: TeacherUpdate,
    service: TeacherService = Depends(get_teacher_service),
) -> TeacherResponse:
    teacher = await service.update_teacher(teacher_id, data)
    return TeacherResponse.model_validate(teacher)


# ---------------------------------------------------------------------------
# Teacher Assignments
# ---------------------------------------------------------------------------


@router.post(
    "/teacher-assignments",
    response_model=TeacherAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_teacher(
    data: TeacherAssignmentCreate,
    service: TeacherAssignmentService = Depends(get_assignment_service),
) -> TeacherAssignmentResponse:
    assignment = await service.assign_teacher(data)
    return TeacherAssignmentResponse.model_validate(assignment)


@router.get(
    "/teacher-assignments/{assignment_id}",
    response_model=TeacherAssignmentResponse,
)
async def get_teacher_assignment(
    assignment_id: int,
    service: TeacherAssignmentService = Depends(get_assignment_service),
) -> TeacherAssignmentResponse:
    assignment = await service.get_assignment(assignment_id)
    return TeacherAssignmentResponse.model_validate(assignment)


@router.get(
    "/teacher-assignments",
    response_model=Page[TeacherAssignmentResponse],
)
async def list_teacher_assignments(
    pagination: PaginationParams = Depends(),
    class_id: Optional[int] = Query(
        default=None, alias="class_id", description="Filter by class"
    ),
    teacher_id: Optional[int] = Query(
        default=None, alias="teacher_id", description="Filter by teacher"
    ),
    service: TeacherAssignmentService = Depends(get_assignment_service),
) -> Page[TeacherAssignmentResponse]:
    assignments, total = await service.list_assignments(
        class_id=class_id,
        teacher_id=teacher_id,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    items = [
        TeacherAssignmentResponse.model_validate(a) for a in assignments
    ]
    return Page.create(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.delete(
    "/teacher-assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unassign_teacher(
    assignment_id: int,
    service: TeacherAssignmentService = Depends(get_assignment_service),
) -> None:
    await service.unassign(assignment_id)