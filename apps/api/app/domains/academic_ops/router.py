from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.academic_ops.schemas import (
    CurriculumCreate,
    CurriculumPage,
    CurriculumResponse,
    CurriculumUpdate,
    ExamScheduleCreate,
    ExamSchedulePage,
    ExamScheduleResponse,
    ExamScheduleUpdate,
    GradeRecordCreate,
    GradeRecordPage,
    GradeRecordResponse,
    GradeRecordUpdate,
    GradingStructureCreate,
    GradingStructurePage,
    GradingStructureResponse,
    GradingStructureUpdate,
    RoomCreate,
    RoomPage,
    RoomResponse,
    RoomUpdate,
    SubstitutionCreate,
    SubstitutionPage,
    SubstitutionResponse,
    SubstitutionUpdate,
    TimetableCheckResult,
    TimetableEntryCreate,
    TimetableEntryDetail,
    TimetableEntryPage,
    TimetableEntryResponse,
    TimetableEntryUpdate,
    TimetableWeekView,
    TimeSlotCreate,
    TimeSlotPage,
    TimeSlotResponse,
    TimeSlotUpdate,
)
from app.domains.academic_ops.service import (
    CurriculumService,
    ExamScheduleService,
    GradeRecordService,
    GradingStructureService,
    RoomService,
    SubstitutionService,
    TimeSlotService,
    TimetableService,
)
from app.domains.auth.dependencies import require_permission
from app.domains.auth.models import User
from app.domains.auth.permissions import (
    ACADEMIC_CREATE,
    ACADEMIC_DELETE,
    ACADEMIC_UPDATE,
    ACADEMIC_VIEW,
)
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.guards import assert_tenant_scope, effective_campus_id, inject_campus
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/academic", tags=["academic-ops"])


# ── Dependency helpers ──────────────────────────────────────────────────


async def get_room_service(session: AsyncSession = Depends(get_session)) -> RoomService:
    return RoomService(session)


async def get_timeslot_service(session: AsyncSession = Depends(get_session)) -> TimeSlotService:
    return TimeSlotService(session)


async def get_timetable_service(session: AsyncSession = Depends(get_session)) -> TimetableService:
    return TimetableService(session)


async def get_substitution_service(session: AsyncSession = Depends(get_session)) -> SubstitutionService:
    return SubstitutionService(session)


async def get_exam_service(session: AsyncSession = Depends(get_session)) -> ExamScheduleService:
    return ExamScheduleService(session)


async def get_grading_service(session: AsyncSession = Depends(get_session)) -> GradingStructureService:
    return GradingStructureService(session)


async def get_grade_record_service(session: AsyncSession = Depends(get_session)) -> GradeRecordService:
    return GradeRecordService(session)


async def get_curriculum_service(session: AsyncSession = Depends(get_session)) -> CurriculumService:
    return CurriculumService(session)


# ═══════════════════════════════════════════════════════════════════════
# ROOMS
# ═══════════════════════════════════════════════════════════════════════


@router.post("/rooms", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    data: RoomCreate,
    service: RoomService = Depends(get_room_service),
    _actor: User = Depends(require_permission(ACADEMIC_CREATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> RoomResponse:
    room = await service.create(data)
    inject_campus(room, tenant)
    return RoomResponse.model_validate(room)


@router.get("/rooms/{room_id}", response_model=RoomResponse)
async def get_room(
    room_id: int,
    service: RoomService = Depends(get_room_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> RoomResponse:
    room = await service.get(room_id)
    assert_tenant_scope(room, tenant, resource="room")
    return RoomResponse.model_validate(room)


@router.get("/rooms", response_model=RoomPage)
async def list_rooms(
    pagination: PaginationParams = Depends(),
    room_type: Optional[str] = Query(None, alias="room_type"),
    status_filter: Optional[str] = Query(None, alias="status"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    service: RoomService = Depends(get_room_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> RoomPage:
    items, total = await service.list(
        room_type=room_type, status=status_filter, campus_id=effective_campus_id(tenant, campus_id),
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[RoomResponse.model_validate(r) for r in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.patch("/rooms/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: int,
    data: RoomUpdate,
    service: RoomService = Depends(get_room_service),
    _actor: User = Depends(require_permission(ACADEMIC_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> RoomResponse:
    existing = await service.get(room_id)
    assert_tenant_scope(existing, tenant, resource="room")
    return RoomResponse.model_validate(await service.update(room_id, data))


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: int,
    service: RoomService = Depends(get_room_service),
    _actor: User = Depends(require_permission(ACADEMIC_DELETE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await service.get(room_id)
    assert_tenant_scope(existing, tenant, resource="room")
    await service.delete(room_id)


# ═══════════════════════════════════════════════════════════════════════
# TIME SLOTS
# ═══════════════════════════════════════════════════════════════════════


@router.post("/time-slots", response_model=TimeSlotResponse, status_code=status.HTTP_201_CREATED)
async def create_time_slot(
    data: TimeSlotCreate,
    service: TimeSlotService = Depends(get_timeslot_service),
    _actor: User = Depends(require_permission(ACADEMIC_CREATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> TimeSlotResponse:
    slot = await service.create(data)
    inject_campus(slot, tenant)
    return TimeSlotResponse.model_validate(slot)


@router.get("/time-slots/{slot_id}", response_model=TimeSlotResponse)
async def get_time_slot(
    slot_id: int,
    service: TimeSlotService = Depends(get_timeslot_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> TimeSlotResponse:
    slot = await service.get(slot_id)
    assert_tenant_scope(slot, tenant, resource="time slot")
    return TimeSlotResponse.model_validate(slot)


@router.get("/time-slots", response_model=TimeSlotPage)
async def list_time_slots(
    pagination: PaginationParams = Depends(),
    day_of_week: Optional[int] = Query(None, alias="day_of_week"),
    slot_type: Optional[str] = Query(None, alias="slot_type"),
    status_filter: Optional[str] = Query(None, alias="status"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    service: TimeSlotService = Depends(get_timeslot_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> TimeSlotPage:
    items, total = await service.list(
        day_of_week=day_of_week, slot_type=slot_type, status=status_filter,
        campus_id=effective_campus_id(tenant, campus_id), skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[TimeSlotResponse.model_validate(s) for s in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.patch("/time-slots/{slot_id}", response_model=TimeSlotResponse)
async def update_time_slot(
    slot_id: int,
    data: TimeSlotUpdate,
    service: TimeSlotService = Depends(get_timeslot_service),
    _actor: User = Depends(require_permission(ACADEMIC_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> TimeSlotResponse:
    existing = await service.get(slot_id)
    assert_tenant_scope(existing, tenant, resource="time slot")
    return TimeSlotResponse.model_validate(await service.update(slot_id, data))


@router.delete("/time-slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_time_slot(
    slot_id: int,
    service: TimeSlotService = Depends(get_timeslot_service),
    _actor: User = Depends(require_permission(ACADEMIC_DELETE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await service.get(slot_id)
    assert_tenant_scope(existing, tenant, resource="time slot")
    await service.delete(slot_id)


# ═══════════════════════════════════════════════════════════════════════
# TIMETABLE ENTRIES (with conflict detection)
# ═══════════════════════════════════════════════════════════════════════


@router.post("/timetable", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_timetable_entry(
    data: TimetableEntryCreate,
    service: TimetableService = Depends(get_timetable_service),
    _actor: User = Depends(require_permission(ACADEMIC_CREATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> dict:
    entry, check = await service.create_entry(data)
    inject_campus(entry, tenant)
    return {
        "entry": TimetableEntryResponse.model_validate(entry).model_dump(),
        "conflict_check": check.model_dump(),
    }


@router.post("/timetable/check", response_model=TimetableCheckResult)
async def check_timetable_conflicts(
    data: TimetableEntryCreate,
    service: TimetableService = Depends(get_timetable_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> TimetableCheckResult:
    return await service.check_conflicts(data)


@router.get("/timetable/{entry_id}", response_model=TimetableEntryResponse)
async def get_timetable_entry(
    entry_id: int,
    service: TimetableService = Depends(get_timetable_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> TimetableEntryResponse:
    entry = await service.get_entry(entry_id)
    assert_tenant_scope(entry, tenant, resource="timetable entry")
    return TimetableEntryResponse.model_validate(entry)


@router.get("/timetable", response_model=TimetableEntryPage)
async def list_timetable_entries(
    pagination: PaginationParams = Depends(),
    class_id: Optional[int] = Query(None, alias="class_id"),
    section_id: Optional[int] = Query(None, alias="section_id"),
    teacher_id: Optional[int] = Query(None, alias="teacher_id"),
    room_id: Optional[int] = Query(None, alias="room_id"),
    day_of_week: Optional[int] = Query(None, alias="day_of_week"),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    status_filter: Optional[str] = Query(None, alias="status"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    service: TimetableService = Depends(get_timetable_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> TimetableEntryPage:
    items, total = await service.list_entries(
        class_id=class_id, section_id=section_id, teacher_id=teacher_id,
        room_id=room_id, day_of_week=day_of_week, academic_year_id=academic_year_id,
        status=status_filter, campus_id=effective_campus_id(tenant, campus_id),
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[TimetableEntryResponse.model_validate(e) for e in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.patch("/timetable/{entry_id}", response_model=dict)
async def update_timetable_entry(
    entry_id: int,
    data: TimetableEntryUpdate,
    service: TimetableService = Depends(get_timetable_service),
    _actor: User = Depends(require_permission(ACADEMIC_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> dict:
    existing = await service.get_entry(entry_id)
    assert_tenant_scope(existing, tenant, resource="timetable entry")
    entry, check = await service.update_entry(entry_id, data)
    return {
        "entry": TimetableEntryResponse.model_validate(entry).model_dump(),
        "conflict_check": check.model_dump(),
    }


@router.delete("/timetable/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timetable_entry(
    entry_id: int,
    service: TimetableService = Depends(get_timetable_service),
    _actor: User = Depends(require_permission(ACADEMIC_DELETE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await service.get_entry(entry_id)
    assert_tenant_scope(existing, tenant, resource="timetable entry")
    await service.delete_entry(entry_id)


# ═══════════════════════════════════════════════════════════════════════
# TIMETABLE WEEK VIEWS
# ═══════════════════════════════════════════════════════════════════════


@router.get("/timetable/week/class/{class_id}", response_model=TimetableWeekView)
async def get_class_timetable_week(
    class_id: int,
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    service: TimetableService = Depends(get_timetable_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> TimetableWeekView:
    return await service.get_week_view(
        class_id=class_id, academic_year_id=academic_year_id,
        campus_id=effective_campus_id(tenant, None),
    )


@router.get("/timetable/week/teacher/{teacher_id}", response_model=TimetableWeekView)
async def get_teacher_timetable_week(
    teacher_id: int,
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    service: TimetableService = Depends(get_timetable_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> TimetableWeekView:
    return await service.get_week_view(
        teacher_id=teacher_id, academic_year_id=academic_year_id,
        campus_id=effective_campus_id(tenant, None),
    )


@router.get("/timetable/week/room/{room_id}", response_model=TimetableWeekView)
async def get_room_timetable_week(
    room_id: int,
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    service: TimetableService = Depends(get_timetable_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> TimetableWeekView:
    return await service.get_week_view(
        room_id=room_id, academic_year_id=academic_year_id,
        campus_id=effective_campus_id(tenant, None),
    )


# ═══════════════════════════════════════════════════════════════════════
# SUBSTITUTIONS
# ═══════════════════════════════════════════════════════════════════════


@router.post("/substitutions", response_model=SubstitutionResponse, status_code=status.HTTP_201_CREATED)
async def create_substitution(
    data: SubstitutionCreate,
    service: SubstitutionService = Depends(get_substitution_service),
    _actor: User = Depends(require_permission(ACADEMIC_CREATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> SubstitutionResponse:
    sub = await service.create(data)
    inject_campus(sub, tenant)
    return SubstitutionResponse.model_validate(sub)


@router.get("/substitutions/{sub_id}", response_model=SubstitutionResponse)
async def get_substitution(
    sub_id: int,
    service: SubstitutionService = Depends(get_substitution_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> SubstitutionResponse:
    sub = await service.get(sub_id)
    assert_tenant_scope(sub, tenant, resource="substitution")
    return SubstitutionResponse.model_validate(sub)


@router.get("/substitutions", response_model=SubstitutionPage)
async def list_substitutions(
    pagination: PaginationParams = Depends(),
    timetable_entry_id: Optional[int] = Query(None, alias="timetable_entry_id"),
    substitute_teacher_id: Optional[int] = Query(None, alias="substitute_teacher_id"),
    status_filter: Optional[str] = Query(None, alias="status"),
    from_date: Optional[str] = Query(None, alias="from_date"),
    to_date: Optional[str] = Query(None, alias="to_date"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    service: SubstitutionService = Depends(get_substitution_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> SubstitutionPage:
    items, total = await service.list(
        timetable_entry_id=timetable_entry_id, substitute_teacher_id=substitute_teacher_id,
        status=status_filter, from_date=from_date, to_date=to_date,
        campus_id=effective_campus_id(tenant, campus_id),
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[SubstitutionResponse.model_validate(s) for s in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.patch("/substitutions/{sub_id}", response_model=SubstitutionResponse)
async def update_substitution(
    sub_id: int,
    data: SubstitutionUpdate,
    service: SubstitutionService = Depends(get_substitution_service),
    _actor: User = Depends(require_permission(ACADEMIC_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> SubstitutionResponse:
    existing = await service.get(sub_id)
    assert_tenant_scope(existing, tenant, resource="substitution")
    return SubstitutionResponse.model_validate(await service.update(sub_id, data))


@router.post("/substitutions/{sub_id}/approve", response_model=SubstitutionResponse)
async def approve_substitution(
    sub_id: int,
    service: SubstitutionService = Depends(get_substitution_service),
    _actor: User = Depends(require_permission(ACADEMIC_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> SubstitutionResponse:
    existing = await service.get(sub_id)
    assert_tenant_scope(existing, tenant, resource="substitution")
    return SubstitutionResponse.model_validate(await service.approve(sub_id))


@router.post("/substitutions/{sub_id}/decline", response_model=SubstitutionResponse)
async def decline_substitution(
    sub_id: int,
    service: SubstitutionService = Depends(get_substitution_service),
    _actor: User = Depends(require_permission(ACADEMIC_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> SubstitutionResponse:
    existing = await service.get(sub_id)
    assert_tenant_scope(existing, tenant, resource="substitution")
    return SubstitutionResponse.model_validate(await service.decline(sub_id))


@router.delete("/substitutions/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_substitution(
    sub_id: int,
    service: SubstitutionService = Depends(get_substitution_service),
    _actor: User = Depends(require_permission(ACADEMIC_DELETE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await service.get(sub_id)
    assert_tenant_scope(existing, tenant, resource="substitution")
    await service.delete(sub_id)


# ═══════════════════════════════════════════════════════════════════════
# EXAM SCHEDULES
# ═══════════════════════════════════════════════════════════════════════


@router.post("/exam-schedules", response_model=ExamScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_exam_schedule(
    data: ExamScheduleCreate,
    service: ExamScheduleService = Depends(get_exam_service),
    _actor: User = Depends(require_permission(ACADEMIC_CREATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> ExamScheduleResponse:
    exam = await service.create(data)
    inject_campus(exam, tenant)
    return ExamScheduleResponse.model_validate(exam)


@router.get("/exam-schedules/{exam_id}", response_model=ExamScheduleResponse)
async def get_exam_schedule(
    exam_id: int,
    service: ExamScheduleService = Depends(get_exam_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> ExamScheduleResponse:
    exam = await service.get(exam_id)
    assert_tenant_scope(exam, tenant, resource="exam schedule")
    return ExamScheduleResponse.model_validate(exam)


@router.get("/exam-schedules", response_model=ExamSchedulePage)
async def list_exam_schedules(
    pagination: PaginationParams = Depends(),
    class_id: Optional[int] = Query(None, alias="class_id"),
    subject_id: Optional[int] = Query(None, alias="subject_id"),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    term_id: Optional[int] = Query(None, alias="term_id"),
    status_filter: Optional[str] = Query(None, alias="status"),
    from_date: Optional[str] = Query(None, alias="from_date"),
    to_date: Optional[str] = Query(None, alias="to_date"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    service: ExamScheduleService = Depends(get_exam_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> ExamSchedulePage:
    items, total = await service.list(
        class_id=class_id, subject_id=subject_id, academic_year_id=academic_year_id,
        term_id=term_id, status=status_filter, from_date=from_date, to_date=to_date,
        campus_id=effective_campus_id(tenant, campus_id),
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[ExamScheduleResponse.model_validate(e) for e in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.patch("/exam-schedules/{exam_id}", response_model=ExamScheduleResponse)
async def update_exam_schedule(
    exam_id: int,
    data: ExamScheduleUpdate,
    service: ExamScheduleService = Depends(get_exam_service),
    _actor: User = Depends(require_permission(ACADEMIC_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> ExamScheduleResponse:
    existing = await service.get(exam_id)
    assert_tenant_scope(existing, tenant, resource="exam schedule")
    return ExamScheduleResponse.model_validate(await service.update(exam_id, data))


@router.delete("/exam-schedules/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam_schedule(
    exam_id: int,
    service: ExamScheduleService = Depends(get_exam_service),
    _actor: User = Depends(require_permission(ACADEMIC_DELETE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await service.get(exam_id)
    assert_tenant_scope(existing, tenant, resource="exam schedule")
    await service.delete(exam_id)


# ═══════════════════════════════════════════════════════════════════════
# GRADING STRUCTURES
# ═══════════════════════════════════════════════════════════════════════


@router.post("/grading-structures", response_model=GradingStructureResponse, status_code=status.HTTP_201_CREATED)
async def create_grading_structure(
    data: GradingStructureCreate,
    service: GradingStructureService = Depends(get_grading_service),
    _actor: User = Depends(require_permission(ACADEMIC_CREATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> GradingStructureResponse:
    gs = await service.create(data)
    inject_campus(gs, tenant)
    return GradingStructureResponse.model_validate(gs)


@router.get("/grading-structures/{gs_id}", response_model=GradingStructureResponse)
async def get_grading_structure(
    gs_id: int,
    service: GradingStructureService = Depends(get_grading_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> GradingStructureResponse:
    gs = await service.get(gs_id)
    assert_tenant_scope(gs, tenant, resource="grading structure")
    return GradingStructureResponse.model_validate(gs)


@router.get("/grading-structures", response_model=GradingStructurePage)
async def list_grading_structures(
    pagination: PaginationParams = Depends(),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    class_id: Optional[int] = Query(None, alias="class_id"),
    subject_id: Optional[int] = Query(None, alias="subject_id"),
    status_filter: Optional[str] = Query(None, alias="status"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    service: GradingStructureService = Depends(get_grading_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> GradingStructurePage:
    items, total = await service.list(
        academic_year_id=academic_year_id, class_id=class_id, subject_id=subject_id,
        status=status_filter, campus_id=effective_campus_id(tenant, campus_id),
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[GradingStructureResponse.model_validate(g) for g in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.patch("/grading-structures/{gs_id}", response_model=GradingStructureResponse)
async def update_grading_structure(
    gs_id: int,
    data: GradingStructureUpdate,
    service: GradingStructureService = Depends(get_grading_service),
    _actor: User = Depends(require_permission(ACADEMIC_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> GradingStructureResponse:
    existing = await service.get(gs_id)
    assert_tenant_scope(existing, tenant, resource="grading structure")
    return GradingStructureResponse.model_validate(await service.update(gs_id, data))


@router.delete("/grading-structures/{gs_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grading_structure(
    gs_id: int,
    service: GradingStructureService = Depends(get_grading_service),
    _actor: User = Depends(require_permission(ACADEMIC_DELETE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await service.get(gs_id)
    assert_tenant_scope(existing, tenant, resource="grading structure")
    await service.delete(gs_id)


# ═══════════════════════════════════════════════════════════════════════
# GRADE RECORDS
# ═══════════════════════════════════════════════════════════════════════


@router.post("/grade-records", response_model=GradeRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_grade_record(
    data: GradeRecordCreate,
    service: GradeRecordService = Depends(get_grade_record_service),
    _actor: User = Depends(require_permission(ACADEMIC_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> GradeRecordResponse:
    record = await service.create(data)
    inject_campus(record, tenant)
    return GradeRecordResponse.model_validate(record)


@router.get("/grade-records/{rec_id}", response_model=GradeRecordResponse)
async def get_grade_record(
    rec_id: int,
    service: GradeRecordService = Depends(get_grade_record_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> GradeRecordResponse:
    record = await service.get(rec_id)
    assert_tenant_scope(record, tenant, resource="grade record")
    return GradeRecordResponse.model_validate(record)


@router.get("/grade-records", response_model=GradeRecordPage)
async def list_grade_records(
    pagination: PaginationParams = Depends(),
    enrollment_id: Optional[int] = Query(None, alias="enrollment_id"),
    subject_id: Optional[int] = Query(None, alias="subject_id"),
    term_id: Optional[int] = Query(None, alias="term_id"),
    status_filter: Optional[str] = Query(None, alias="status"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    service: GradeRecordService = Depends(get_grade_record_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> GradeRecordPage:
    items, total = await service.list(
        enrollment_id=enrollment_id, subject_id=subject_id, term_id=term_id,
        status=status_filter, campus_id=effective_campus_id(tenant, campus_id),
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[GradeRecordResponse.model_validate(r) for r in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.patch("/grade-records/{rec_id}", response_model=GradeRecordResponse)
async def update_grade_record(
    rec_id: int,
    data: GradeRecordUpdate,
    service: GradeRecordService = Depends(get_grade_record_service),
    _actor: User = Depends(require_permission(ACADEMIC_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> GradeRecordResponse:
    existing = await service.get(rec_id)
    assert_tenant_scope(existing, tenant, resource="grade record")
    return GradeRecordResponse.model_validate(await service.update(rec_id, data))


@router.delete("/grade-records/{rec_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grade_record(
    rec_id: int,
    service: GradeRecordService = Depends(get_grade_record_service),
    _actor: User = Depends(require_permission(ACADEMIC_DELETE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await service.get(rec_id)
    assert_tenant_scope(existing, tenant, resource="grade record")
    await service.delete(rec_id)


# ═══════════════════════════════════════════════════════════════════════
# CURRICULUM
# ═══════════════════════════════════════════════════════════════════════


@router.post("/curricula", response_model=CurriculumResponse, status_code=status.HTTP_201_CREATED)
async def create_curriculum(
    data: CurriculumCreate,
    service: CurriculumService = Depends(get_curriculum_service),
    _actor: User = Depends(require_permission(ACADEMIC_CREATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> CurriculumResponse:
    curr = await service.create(data)
    inject_campus(curr, tenant)
    return CurriculumResponse.model_validate(curr)


@router.get("/curricula/{curr_id}", response_model=CurriculumResponse)
async def get_curriculum(
    curr_id: int,
    service: CurriculumService = Depends(get_curriculum_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> CurriculumResponse:
    curr = await service.get(curr_id)
    assert_tenant_scope(curr, tenant, resource="curriculum")
    return CurriculumResponse.model_validate(curr)


@router.get("/curricula", response_model=CurriculumPage)
async def list_curricula(
    pagination: PaginationParams = Depends(),
    academic_year_id: Optional[int] = Query(None, alias="academic_year_id"),
    class_id: Optional[int] = Query(None, alias="class_id"),
    subject_id: Optional[int] = Query(None, alias="subject_id"),
    term_id: Optional[int] = Query(None, alias="term_id"),
    status_filter: Optional[str] = Query(None, alias="status"),
    campus_id: Optional[int] = Query(None, alias="campus_id"),
    service: CurriculumService = Depends(get_curriculum_service),
    _actor: User = Depends(require_permission(ACADEMIC_VIEW)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> CurriculumPage:
    items, total = await service.list(
        academic_year_id=academic_year_id, class_id=class_id, subject_id=subject_id,
        term_id=term_id, status=status_filter, campus_id=effective_campus_id(tenant, campus_id),
        skip=pagination.offset, limit=pagination.limit,
    )
    return Page.create(
        items=[CurriculumResponse.model_validate(c) for c in items],
        total=total, page=pagination.page, size=pagination.size,
    )


@router.patch("/curricula/{curr_id}", response_model=CurriculumResponse)
async def update_curriculum(
    curr_id: int,
    data: CurriculumUpdate,
    service: CurriculumService = Depends(get_curriculum_service),
    _actor: User = Depends(require_permission(ACADEMIC_UPDATE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> CurriculumResponse:
    existing = await service.get(curr_id)
    assert_tenant_scope(existing, tenant, resource="curriculum")
    return CurriculumResponse.model_validate(await service.update(curr_id, data))


@router.delete("/curricula/{curr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_curriculum(
    curr_id: int,
    service: CurriculumService = Depends(get_curriculum_service),
    _actor: User = Depends(require_permission(ACADEMIC_DELETE)),
    tenant: TenantContext = Depends(require_tenant_context),
) -> None:
    existing = await service.get(curr_id)
    assert_tenant_scope(existing, tenant, resource="curriculum")
    await service.delete(curr_id)
