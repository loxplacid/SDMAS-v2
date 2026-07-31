from __future__ import annotations

import datetime
from typing import Optional, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.academic.models import (
    AcademicYear,
    Class,
    Section,
    Subject,
    Teacher,
    TeacherAssignment,
    Term,
)
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    SectionRepository,
    SubjectRepository,
    TeacherRepository,
)
from app.domains.academic_ops.models import (
    Curriculum,
    ExamSchedule,
    GradeRecord,
    GradingStructure,
    Room,
    Substitution,
    TimeSlot,
    TimetableEntry,
)
from app.domains.academic_ops.schemas import (
    ConflictInfo,
    TimetableCheckResult,
    TimetableDayView,
    TimetableEntryDetail,
    TimetableWeekView,
    CurriculumCreate,
    CurriculumUpdate,
    ExamScheduleCreate,
    ExamScheduleUpdate,
    GradeRecordCreate,
    GradeRecordUpdate,
    GradingStructureCreate,
    GradingStructureUpdate,
    RoomCreate,
    RoomUpdate,
    SubstitutionCreate,
    SubstitutionUpdate,
    TimeSlotCreate,
    TimeSlotUpdate,
    TimetableEntryCreate,
    TimetableEntryUpdate,
)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ── Room Service ────────────────────────────────────────────────────────

class RoomService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_room(self, room_id: int) -> Room:
        result = await self.session.execute(select(Room).where(Room.id == room_id))
        room = result.scalar_one_or_none()
        if room is None:
            raise NotFoundError(f"Room with id {room_id} not found")
        return room

    async def create(self, data: RoomCreate) -> Room:
        existing = await self.session.execute(
            select(Room).where(Room.code == data.code.upper())
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(f"Room with code '{data.code.upper()}' already exists")
        room = Room(
            name=data.name.strip(),
            code=data.code.upper(),
            building=data.building,
            floor=data.floor,
            capacity=data.capacity,
            room_type=data.room_type,
            status="active",
        )
        self.session.add(room)
        await self.session.flush()
        return room

    async def get(self, room_id: int) -> Room:
        return await self._get_room(room_id)

    async def update(self, room_id: int, data: RoomUpdate) -> Room:
        room = await self._get_room(room_id)
        if data.name is not None:
            room.name = data.name.strip()
        if data.code is not None:
            code = data.code.upper()
            existing = await self.session.execute(
                select(Room).where(Room.code == code, Room.id != room_id)
            )
            if existing.scalar_one_or_none() is not None:
                raise ConflictError(f"Room with code '{code}' already exists")
            room.code = code
        if data.building is not None:
            room.building = data.building
        if data.floor is not None:
            room.floor = data.floor
        if data.capacity is not None:
            room.capacity = data.capacity
        if data.room_type is not None:
            room.room_type = data.room_type
        if data.status is not None:
            room.status = data.status
        await self.session.flush()
        return room

    async def delete(self, room_id: int) -> None:
        room = await self._get_room(room_id)
        await self.session.delete(room)

    async def list(
        self,
        room_type: Optional[str] = None,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Room], int]:
        query = select(Room)
        count_query = select(func.count(Room.id))
        if room_type is not None:
            query = query.where(Room.room_type == room_type)
            count_query = count_query.where(Room.room_type == room_type)
        if status is not None:
            query = query.where(Room.status == status)
            count_query = count_query.where(Room.status == status)
        if campus_id is not None:
            query = query.where(Room.campus_id == campus_id)
            count_query = count_query.where(Room.campus_id == campus_id)
        query = query.offset(skip).limit(limit).order_by(Room.name)
        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query)
        return result.scalars().all(), total


# ── TimeSlot Service ────────────────────────────────────────────────────

class TimeSlotService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_slot(self, slot_id: int) -> TimeSlot:
        result = await self.session.execute(select(TimeSlot).where(TimeSlot.id == slot_id))
        slot = result.scalar_one_or_none()
        if slot is None:
            raise NotFoundError(f"TimeSlot with id {slot_id} not found")
        return slot

    async def create(self, data: TimeSlotCreate) -> TimeSlot:
        existing = await self.session.execute(
            select(TimeSlot).where(
                TimeSlot.day_of_week == data.day_of_week,
                TimeSlot.start_time == data.start_time,
                TimeSlot.end_time == data.end_time,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("TimeSlot already exists for this day and time")
        slot = TimeSlot(
            name=data.name.strip(),
            day_of_week=data.day_of_week,
            start_time=data.start_time,
            end_time=data.end_time,
            slot_type=data.slot_type,
            status="active",
        )
        self.session.add(slot)
        await self.session.flush()
        return slot

    async def get(self, slot_id: int) -> TimeSlot:
        return await self._get_slot(slot_id)

    async def update(self, slot_id: int, data: TimeSlotUpdate) -> TimeSlot:
        slot = await self._get_slot(slot_id)
        if data.name is not None:
            slot.name = data.name.strip()
        if data.day_of_week is not None:
            slot.day_of_week = data.day_of_week
        if data.start_time is not None:
            slot.start_time = data.start_time
        if data.end_time is not None:
            slot.end_time = data.end_time
        if data.slot_type is not None:
            slot.slot_type = data.slot_type
        if data.status is not None:
            slot.status = data.status
        await self.session.flush()
        return slot

    async def delete(self, slot_id: int) -> None:
        slot = await self._get_slot(slot_id)
        await self.session.delete(slot)

    async def list(
        self,
        day_of_week: Optional[int] = None,
        slot_type: Optional[str] = None,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[TimeSlot], int]:
        query = select(TimeSlot)
        count_query = select(func.count(TimeSlot.id))
        if day_of_week is not None:
            query = query.where(TimeSlot.day_of_week == day_of_week)
            count_query = count_query.where(TimeSlot.day_of_week == day_of_week)
        if slot_type is not None:
            query = query.where(TimeSlot.slot_type == slot_type)
            count_query = count_query.where(TimeSlot.slot_type == slot_type)
        if status is not None:
            query = query.where(TimeSlot.status == status)
            count_query = count_query.where(TimeSlot.status == status)
        if campus_id is not None:
            query = query.where(TimeSlot.campus_id == campus_id)
            count_query = count_query.where(TimeSlot.campus_id == campus_id)
        query = query.offset(skip).limit(limit).order_by(TimeSlot.day_of_week, TimeSlot.start_time)
        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query)
        return result.scalars().all(), total


# ── Timetable Service (with conflict detection) ─────────────────────────

class TimetableService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_entry(self, entry_id: int) -> TimetableEntry:
        result = await self.session.execute(
            select(TimetableEntry).where(TimetableEntry.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            raise NotFoundError(f"TimetableEntry with id {entry_id} not found")
        return entry

    async def _check_conflicts(
        self,
        day_of_week: int,
        time_slot_id: int,
        teacher_id: int,
        room_id: Optional[int],
        class_id: int,
        section_id: Optional[int],
        academic_year_id: int,
        exclude_id: Optional[int] = None,
    ) -> list[ConflictInfo]:
        conflicts: list[ConflictInfo] = []
        base_conditions = [
            TimetableEntry.day_of_week == day_of_week,
            TimetableEntry.time_slot_id == time_slot_id,
            TimetableEntry.academic_year_id == academic_year_id,
            TimetableEntry.status == "active",
        ]
        if exclude_id is not None:
            base_conditions.append(TimetableEntry.id != exclude_id)

        # Teacher conflict
        teacher_conflict = await self.session.execute(
            select(TimetableEntry).where(
                and_(
                    *base_conditions,
                    TimetableEntry.teacher_id == teacher_id,
                )
            )
        )
        if teacher_conflict.scalar_one_or_none() is not None:
            conflicts.append(ConflictInfo(
                type="teacher",
                description=f"Teacher is already scheduled for this time slot",
                entity_ids={"teacher_id": teacher_id},
            ))

        # Room conflict
        if room_id is not None:
            room_conflict = await self.session.execute(
                select(TimetableEntry).where(
                    and_(
                        *base_conditions,
                        TimetableEntry.room_id == room_id,
                    )
                )
            )
            if room_conflict.scalar_one_or_none() is not None:
                conflicts.append(ConflictInfo(
                    type="room",
                    description=f"Room is already booked for this time slot",
                    entity_ids={"room_id": room_id},
                ))

        # Class-section conflict
        section_cond = (
            TimetableEntry.section_id == section_id
            if section_id is not None
            else TimetableEntry.section_id.is_(None)
        )
        class_conflict = await self.session.execute(
            select(TimetableEntry).where(
                and_(
                    *base_conditions,
                    TimetableEntry.class_id == class_id,
                    section_cond,
                )
            )
        )
        if class_conflict.scalar_one_or_none() is not None:
            conflicts.append(ConflictInfo(
                type="class_section",
                description=f"Class already has a lesson scheduled for this time slot",
                entity_ids={"class_id": class_id},
            ))

        return conflicts

    async def create_entry(self, data: TimetableEntryCreate) -> tuple[TimetableEntry, TimetableCheckResult]:
        conflicts = await self._check_conflicts(
            day_of_week=data.day_of_week,
            time_slot_id=data.time_slot_id,
            teacher_id=data.teacher_id,
            room_id=data.room_id,
            class_id=data.class_id,
            section_id=data.section_id,
            academic_year_id=data.academic_year_id,
        )
        entry = TimetableEntry(
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            class_id=data.class_id,
            section_id=data.section_id,
            subject_id=data.subject_id,
            teacher_id=data.teacher_id,
            room_id=data.room_id,
            time_slot_id=data.time_slot_id,
            day_of_week=data.day_of_week,
            status="active",
        )
        self.session.add(entry)
        await self.session.flush()
        return entry, TimetableCheckResult(has_conflicts=len(conflicts) > 0, conflicts=conflicts)

    async def check_conflicts(self, data: TimetableEntryCreate) -> TimetableCheckResult:
        conflicts = await self._check_conflicts(
            day_of_week=data.day_of_week,
            time_slot_id=data.time_slot_id,
            teacher_id=data.teacher_id,
            room_id=data.room_id,
            class_id=data.class_id,
            section_id=data.section_id,
            academic_year_id=data.academic_year_id,
        )
        return TimetableCheckResult(has_conflicts=len(conflicts) > 0, conflicts=conflicts)

    async def get_entry(self, entry_id: int) -> TimetableEntry:
        return await self._get_entry(entry_id)

    async def update_entry(self, entry_id: int, data: TimetableEntryUpdate) -> tuple[TimetableEntry, TimetableCheckResult]:
        entry = await self._get_entry(entry_id)
        if data.teacher_id is not None:
            entry.teacher_id = data.teacher_id
        if data.room_id is not None:
            entry.room_id = data.room_id
        if data.time_slot_id is not None:
            entry.time_slot_id = data.time_slot_id
        if data.day_of_week is not None:
            entry.day_of_week = data.day_of_week
        if data.status is not None:
            entry.status = data.status
        await self.session.flush()

        conflicts = await self._check_conflicts(
            day_of_week=entry.day_of_week,
            time_slot_id=entry.time_slot_id,
            teacher_id=entry.teacher_id,
            room_id=entry.room_id,
            class_id=entry.class_id,
            section_id=entry.section_id,
            academic_year_id=entry.academic_year_id,
            exclude_id=entry_id,
        )
        return entry, TimetableCheckResult(has_conflicts=len(conflicts) > 0, conflicts=conflicts)

    async def delete_entry(self, entry_id: int) -> None:
        entry = await self._get_entry(entry_id)
        await self.session.delete(entry)

    async def list_entries(
        self,
        class_id: Optional[int] = None,
        section_id: Optional[int] = None,
        teacher_id: Optional[int] = None,
        room_id: Optional[int] = None,
        day_of_week: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[TimetableEntry], int]:
        query = select(TimetableEntry)
        count_query = select(func.count(TimetableEntry.id))
        if class_id is not None:
            query = query.where(TimetableEntry.class_id == class_id)
            count_query = count_query.where(TimetableEntry.class_id == class_id)
        if section_id is not None:
            query = query.where(TimetableEntry.section_id == section_id)
            count_query = count_query.where(TimetableEntry.section_id == section_id)
        if teacher_id is not None:
            query = query.where(TimetableEntry.teacher_id == teacher_id)
            count_query = count_query.where(TimetableEntry.teacher_id == teacher_id)
        if room_id is not None:
            query = query.where(TimetableEntry.room_id == room_id)
            count_query = count_query.where(TimetableEntry.room_id == room_id)
        if day_of_week is not None:
            query = query.where(TimetableEntry.day_of_week == day_of_week)
            count_query = count_query.where(TimetableEntry.day_of_week == day_of_week)
        if academic_year_id is not None:
            query = query.where(TimetableEntry.academic_year_id == academic_year_id)
            count_query = count_query.where(TimetableEntry.academic_year_id == academic_year_id)
        if status is not None:
            query = query.where(TimetableEntry.status == status)
            count_query = count_query.where(TimetableEntry.status == status)
        query = query.offset(skip).limit(limit).order_by(TimetableEntry.day_of_week, TimetableEntry.id)
        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query)
        return result.scalars().all(), total

    async def get_week_view(
        self,
        class_id: Optional[int] = None,
        teacher_id: Optional[int] = None,
        room_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
    ) -> TimetableWeekView:
        conditions = [TimetableEntry.status == "active"]
        class_name = section_name = teacher_name = room_name = None

        if class_id is not None:
            conditions.append(TimetableEntry.class_id == class_id)
            cls = await self.session.get(Class, class_id)
            class_name = cls.name if cls else None
        if teacher_id is not None:
            conditions.append(TimetableEntry.teacher_id == teacher_id)
            t = await self.session.get(Teacher, teacher_id)
            teacher_name = f"{t.first_name} {t.last_name}" if t else None
        if room_id is not None:
            conditions.append(TimetableEntry.room_id == room_id)
            r = await self.session.get(Room, room_id)
            room_name = r.name if r else None
        if academic_year_id is not None:
            conditions.append(TimetableEntry.academic_year_id == academic_year_id)

        result = await self.session.execute(
            select(TimetableEntry)
            .options(
                selectinload(TimetableEntry.room),
                selectinload(TimetableEntry.time_slot),
            )
            .where(and_(*conditions))
            .order_by(TimetableEntry.day_of_week)
        )
        entries = result.scalars().all()

        subject_ids = {e.subject_id for e in entries if e.subject_id}
        teacher_ids = {e.teacher_id for e in entries if e.teacher_id}
        class_ids = {e.class_id for e in entries if e.class_id}
        section_ids = {e.section_id for e in entries if e.section_id}

        subjects = {}
        if subject_ids:
            rows = await self.session.execute(select(Subject).where(Subject.id.in_(subject_ids)))
            subjects = {s.id: s for s in rows.scalars().all()}

        teachers = {}
        if teacher_ids:
            rows = await self.session.execute(select(Teacher).where(Teacher.id.in_(teacher_ids)))
            teachers = {t.id: t for t in rows.scalars().all()}

        classes = {}
        if class_ids:
            rows = await self.session.execute(select(Class).where(Class.id.in_(class_ids)))
            classes = {c.id: c for c in rows.scalars().all()}

        sections = {}
        if section_ids:
            rows = await self.session.execute(select(Section).where(Section.id.in_(section_ids)))
            sections = {s.id: s for s in rows.scalars().all()}

        days_map: dict[int, list[TimetableEntryDetail]] = {d: [] for d in range(5)}
        for entry in entries:
            detail = TimetableEntryDetail(
                id=entry.id,
                day_of_week=entry.day_of_week,
                status=entry.status,
                subject_name=subjects[entry.subject_id].name if entry.subject_id in subjects else None,
                teacher_name=f"{teachers[entry.teacher_id].first_name} {teachers[entry.teacher_id].last_name}" if entry.teacher_id in teachers else None,
                room_name=entry.room.name if entry.room else None,
                class_name=classes[entry.class_id].name if entry.class_id in classes else None,
                section_name=sections[entry.section_id].name if entry.section_id and entry.section_id in sections else None,
                time_slot_name=entry.time_slot.name if entry.time_slot else None,
                start_time=entry.time_slot.start_time if entry.time_slot else None,
                end_time=entry.time_slot.end_time if entry.time_slot else None,
            )
            if entry.day_of_week in days_map:
                days_map[entry.day_of_week].append(detail)
            else:
                days_map[entry.day_of_week] = [detail]

        days_view = [
            TimetableDayView(
                day_of_week=d,
                day_name=DAY_NAMES[d],
                entries=sorted(days_map.get(d, []), key=lambda e: e.start_time or ""),
            )
            for d in range(5)
        ]

        return TimetableWeekView(
            class_name=class_name,
            section_name=section_name,
            teacher_name=teacher_name,
            room_name=room_name,
            days=days_view,
        )


# ── Substitution Service ────────────────────────────────────────────────

class SubstitutionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get(self, sub_id: int) -> Substitution:
        result = await self.session.execute(
            select(Substitution).where(Substitution.id == sub_id)
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            raise NotFoundError(f"Substitution with id {sub_id} not found")
        return sub

    async def create(self, data: SubstitutionCreate) -> Substitution:
        entry_result = await self.session.execute(
            select(TimetableEntry).where(TimetableEntry.id == data.timetable_entry_id)
        )
        entry = entry_result.scalar_one_or_none()
        if entry is None:
            raise NotFoundError(f"TimetableEntry with id {data.timetable_entry_id} not found")

        sub_date = datetime.date.fromisoformat(data.substitution_date)

        teacher_result = await self.session.execute(
            select(Teacher).where(Teacher.id == data.substitute_teacher_id, Teacher.status == "active")
        )
        if teacher_result.scalar_one_or_none() is None:
            raise ValidationError("Substitute teacher not found or inactive")

        existing = await self.session.execute(
            select(Substitution).where(
                Substitution.timetable_entry_id == data.timetable_entry_id,
                Substitution.substitution_date == sub_date,
                Substitution.status.in_(["pending", "approved"]),
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("A pending or approved substitution already exists for this entry on this date")

        sub = Substitution(
            timetable_entry_id=data.timetable_entry_id,
            original_teacher_id=data.original_teacher_id,
            substitute_teacher_id=data.substitute_teacher_id,
            substitution_date=sub_date,
            reason=data.reason,
            status="pending",
        )
        self.session.add(sub)
        await self.session.flush()
        return sub

    async def get(self, sub_id: int) -> Substitution:
        return await self._get(sub_id)

    async def update(self, sub_id: int, data: SubstitutionUpdate) -> Substitution:
        sub = await self._get(sub_id)
        if data.substitute_teacher_id is not None:
            sub.substitute_teacher_id = data.substitute_teacher_id
        if data.status is not None:
            sub.status = data.status
        if data.reason is not None:
            sub.reason = data.reason
        await self.session.flush()
        return sub

    async def approve(self, sub_id: int) -> Substitution:
        sub = await self._get(sub_id)
        if sub.status != "pending":
            raise ValidationError(f"Cannot approve substitution with status '{sub.status}'")
        sub.status = "approved"
        await self.session.flush()
        return sub

    async def decline(self, sub_id: int) -> Substitution:
        sub = await self._get(sub_id)
        if sub.status != "pending":
            raise ValidationError(f"Cannot decline substitution with status '{sub.status}'")
        sub.status = "declined"
        await self.session.flush()
        return sub

    async def delete(self, sub_id: int) -> None:
        sub = await self._get(sub_id)
        await self.session.delete(sub)

    async def list(
        self,
        timetable_entry_id: Optional[int] = None,
        substitute_teacher_id: Optional[int] = None,
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Substitution], int]:
        query = select(Substitution)
        count_query = select(func.count(Substitution.id))
        if timetable_entry_id is not None:
            query = query.where(Substitution.timetable_entry_id == timetable_entry_id)
            count_query = count_query.where(Substitution.timetable_entry_id == timetable_entry_id)
        if substitute_teacher_id is not None:
            query = query.where(Substitution.substitute_teacher_id == substitute_teacher_id)
            count_query = count_query.where(Substitution.substitute_teacher_id == substitute_teacher_id)
        if status is not None:
            query = query.where(Substitution.status == status)
            count_query = count_query.where(Substitution.status == status)
        if from_date is not None:
            query = query.where(Substitution.substitution_date >= from_date)
            count_query = count_query.where(Substitution.substitution_date >= from_date)
        if to_date is not None:
            query = query.where(Substitution.substitution_date <= to_date)
            count_query = count_query.where(Substitution.substitution_date <= to_date)
        query = query.offset(skip).limit(limit).order_by(Substitution.substitution_date.desc())
        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query)
        return result.scalars().all(), total


# ── ExamSchedule Service ────────────────────────────────────────────────

class ExamScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get(self, exam_id: int) -> ExamSchedule:
        result = await self.session.execute(
            select(ExamSchedule).where(ExamSchedule.id == exam_id)
        )
        exam = result.scalar_one_or_none()
        if exam is None:
            raise NotFoundError(f"ExamSchedule with id {exam_id} not found")
        return exam

    async def create(self, data: ExamScheduleCreate) -> ExamSchedule:
        exam_date = datetime.date.fromisoformat(data.exam_date)

        existing = await self.session.execute(
            select(ExamSchedule).where(
                ExamSchedule.class_id == data.class_id,
                ExamSchedule.subject_id == data.subject_id,
                ExamSchedule.exam_date == exam_date,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("Exam already scheduled for this class and subject on this date")

        if data.room_id is not None:
            room_exam = await self.session.execute(
                select(ExamSchedule).where(
                    ExamSchedule.room_id == data.room_id,
                    ExamSchedule.exam_date == exam_date,
                    ExamSchedule.start_time < data.end_time,
                    ExamSchedule.end_time > data.start_time,
                )
            )
            if room_exam.scalar_one_or_none() is not None:
                raise ConflictError("Room is already booked for another exam during this time")

        exam = ExamSchedule(
            academic_year_id=data.academic_year_id,
            term_id=data.term_id,
            class_id=data.class_id,
            section_id=data.section_id,
            subject_id=data.subject_id,
            exam_date=exam_date,
            start_time=data.start_time,
            end_time=data.end_time,
            room_id=data.room_id,
            invigilator_id=data.invigilator_id,
            max_marks=data.max_marks,
            pass_marks=data.pass_marks,
            status="scheduled",
        )
        self.session.add(exam)
        await self.session.flush()
        return exam

    async def get(self, exam_id: int) -> ExamSchedule:
        return await self._get(exam_id)

    async def update(self, exam_id: int, data: ExamScheduleUpdate) -> ExamSchedule:
        exam = await self._get(exam_id)
        if data.exam_date is not None:
            exam.exam_date = datetime.date.fromisoformat(data.exam_date)
        if data.start_time is not None:
            exam.start_time = data.start_time
        if data.end_time is not None:
            exam.end_time = data.end_time
        if data.room_id is not None:
            exam.room_id = data.room_id
        if data.invigilator_id is not None:
            exam.invigilator_id = data.invigilator_id
        if data.status is not None:
            exam.status = data.status
        await self.session.flush()
        return exam

    async def delete(self, exam_id: int) -> None:
        exam = await self._get(exam_id)
        await self.session.delete(exam)

    async def list(
        self,
        class_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        term_id: Optional[int] = None,
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[ExamSchedule], int]:
        query = select(ExamSchedule)
        count_query = select(func.count(ExamSchedule.id))
        if class_id is not None:
            query = query.where(ExamSchedule.class_id == class_id)
            count_query = count_query.where(ExamSchedule.class_id == class_id)
        if subject_id is not None:
            query = query.where(ExamSchedule.subject_id == subject_id)
            count_query = count_query.where(ExamSchedule.subject_id == subject_id)
        if academic_year_id is not None:
            query = query.where(ExamSchedule.academic_year_id == academic_year_id)
            count_query = count_query.where(ExamSchedule.academic_year_id == academic_year_id)
        if term_id is not None:
            query = query.where(ExamSchedule.term_id == term_id)
            count_query = count_query.where(ExamSchedule.term_id == term_id)
        if status is not None:
            query = query.where(ExamSchedule.status == status)
            count_query = count_query.where(ExamSchedule.status == status)
        if from_date is not None:
            query = query.where(ExamSchedule.exam_date >= from_date)
            count_query = count_query.where(ExamSchedule.exam_date >= from_date)
        if to_date is not None:
            query = query.where(ExamSchedule.exam_date <= to_date)
            count_query = count_query.where(ExamSchedule.exam_date <= to_date)
        query = query.offset(skip).limit(limit).order_by(ExamSchedule.exam_date, ExamSchedule.start_time)
        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query)
        return result.scalars().all(), total


# ── GradingStructure Service ────────────────────────────────────────────

class GradingStructureService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get(self, gs_id: int) -> GradingStructure:
        result = await self.session.execute(select(GradingStructure).where(GradingStructure.id == gs_id))
        gs = result.scalar_one_or_none()
        if gs is None:
            raise NotFoundError(f"GradingStructure with id {gs_id} not found")
        return gs

    async def create(self, data: GradingStructureCreate) -> GradingStructure:
        existing = await self.session.execute(
            select(GradingStructure).where(
                GradingStructure.academic_year_id == data.academic_year_id,
                GradingStructure.class_id == data.class_id,
                GradingStructure.subject_id == data.subject_id,
                GradingStructure.name == data.name,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(f"Grading structure '{data.name}' already exists")
        gs = GradingStructure(
            academic_year_id=data.academic_year_id,
            class_id=data.class_id,
            subject_id=data.subject_id,
            name=data.name.strip(),
            min_percentage=data.min_percentage,
            max_percentage=data.max_percentage,
            grade_point=data.grade_point,
            description=data.description,
            status="active",
        )
        self.session.add(gs)
        await self.session.flush()
        return gs

    async def get(self, gs_id: int) -> GradingStructure:
        return await self._get(gs_id)

    async def update(self, gs_id: int, data: GradingStructureUpdate) -> GradingStructure:
        gs = await self._get(gs_id)
        if data.name is not None:
            gs.name = data.name.strip()
        if data.min_percentage is not None:
            gs.min_percentage = data.min_percentage
        if data.max_percentage is not None:
            gs.max_percentage = data.max_percentage
        if data.grade_point is not None:
            gs.grade_point = data.grade_point
        if data.description is not None:
            gs.description = data.description
        if data.status is not None:
            gs.status = data.status
        await self.session.flush()
        return gs

    async def delete(self, gs_id: int) -> None:
        gs = await self._get(gs_id)
        await self.session.delete(gs)

    async def list(
        self,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[GradingStructure], int]:
        query = select(GradingStructure)
        count_query = select(func.count(GradingStructure.id))
        if academic_year_id is not None:
            query = query.where(GradingStructure.academic_year_id == academic_year_id)
            count_query = count_query.where(GradingStructure.academic_year_id == academic_year_id)
        if class_id is not None:
            query = query.where(GradingStructure.class_id == class_id)
            count_query = count_query.where(GradingStructure.class_id == class_id)
        if subject_id is not None:
            query = query.where(GradingStructure.subject_id == subject_id)
            count_query = count_query.where(GradingStructure.subject_id == subject_id)
        if status is not None:
            query = query.where(GradingStructure.status == status)
            count_query = count_query.where(GradingStructure.status == status)
        query = query.offset(skip).limit(limit).order_by(GradingStructure.min_percentage)
        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query)
        return result.scalars().all(), total


# ── GradeRecord Service ─────────────────────────────────────────────────

class GradeRecordService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get(self, rec_id: int) -> GradeRecord:
        result = await self.session.execute(select(GradeRecord).where(GradeRecord.id == rec_id))
        rec = result.scalar_one_or_none()
        if rec is None:
            raise NotFoundError(f"GradeRecord with id {rec_id} not found")
        return rec

    async def _auto_grade(self, marks: float, max_marks: int, gs_id: Optional[int]) -> tuple[str, float]:
        if gs_id is not None:
            gs = await self.session.get(GradingStructure, gs_id)
            if gs:
                pct = (marks / max_marks) * 100
                if gs.min_percentage <= pct <= gs.max_percentage:
                    return gs.name, gs.grade_point
        pct = (marks / max_marks) * 100
        if pct >= 90:
            return "A+", 4.0
        elif pct >= 80:
            return "A", 3.7
        elif pct >= 70:
            return "B+", 3.3
        elif pct >= 65:
            return "B", 3.0
        elif pct >= 60:
            return "C+", 2.7
        elif pct >= 55:
            return "C", 2.3
        elif pct >= 50:
            return "D", 2.0
        elif pct >= 40:
            return "E", 1.0
        else:
            return "F", 0.0

    async def create(self, data: GradeRecordCreate) -> GradeRecord:
        existing = await self.session.execute(
            select(GradeRecord).where(
                GradeRecord.enrollment_id == data.enrollment_id,
                GradeRecord.subject_id == data.subject_id,
                GradeRecord.term_id == data.term_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("Grade record already exists for this enrollment, subject, and term")
        grade = data.grade
        grade_point = data.grade_point
        if data.marks_obtained is not None and grade is None:
            grade, grade_point = await self._auto_grade(
                data.marks_obtained, data.max_marks, data.grading_structure_id
            )
        rec = GradeRecord(
            enrollment_id=data.enrollment_id,
            subject_id=data.subject_id,
            grading_structure_id=data.grading_structure_id,
            marks_obtained=data.marks_obtained,
            max_marks=data.max_marks,
            grade=grade,
            grade_point=grade_point,
            term_id=data.term_id,
            remarks=data.remarks,
            status="active",
        )
        self.session.add(rec)
        await self.session.flush()
        return rec

    async def get(self, rec_id: int) -> GradeRecord:
        return await self._get(rec_id)

    async def update(self, rec_id: int, data: GradeRecordUpdate) -> GradeRecord:
        rec = await self._get(rec_id)
        if data.marks_obtained is not None:
            rec.marks_obtained = data.marks_obtained
        if data.grading_structure_id is not None:
            rec.grading_structure_id = data.grading_structure_id
        if data.grade is not None:
            rec.grade = data.grade
        if data.grade_point is not None:
            rec.grade_point = data.grade_point
        if data.remarks is not None:
            rec.remarks = data.remarks
        if data.status is not None:
            rec.status = data.status
        if data.marks_obtained is not None and data.grade is None:
            grade, gp = await self._auto_grade(
                rec.marks_obtained, rec.max_marks, rec.grading_structure_id
            )
            rec.grade = grade
            rec.grade_point = gp
        await self.session.flush()
        return rec

    async def delete(self, rec_id: int) -> None:
        rec = await self._get(rec_id)
        await self.session.delete(rec)

    async def list(
        self,
        enrollment_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        term_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[GradeRecord], int]:
        query = select(GradeRecord)
        count_query = select(func.count(GradeRecord.id))
        if enrollment_id is not None:
            query = query.where(GradeRecord.enrollment_id == enrollment_id)
            count_query = count_query.where(GradeRecord.enrollment_id == enrollment_id)
        if subject_id is not None:
            query = query.where(GradeRecord.subject_id == subject_id)
            count_query = count_query.where(GradeRecord.subject_id == subject_id)
        if term_id is not None:
            query = query.where(GradeRecord.term_id == term_id)
            count_query = count_query.where(GradeRecord.term_id == term_id)
        if status is not None:
            query = query.where(GradeRecord.status == status)
            count_query = count_query.where(GradeRecord.status == status)
        query = query.offset(skip).limit(limit).order_by(GradeRecord.id)
        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query)
        return result.scalars().all(), total


# ── Curriculum Service ──────────────────────────────────────────────────

class CurriculumService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get(self, curr_id: int) -> Curriculum:
        result = await self.session.execute(select(Curriculum).where(Curriculum.id == curr_id))
        curr = result.scalar_one_or_none()
        if curr is None:
            raise NotFoundError(f"Curriculum with id {curr_id} not found")
        return curr

    async def create(self, data: CurriculumCreate) -> Curriculum:
        existing = await self.session.execute(
            select(Curriculum).where(
                Curriculum.academic_year_id == data.academic_year_id,
                Curriculum.class_id == data.class_id,
                Curriculum.subject_id == data.subject_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("Curriculum already exists for this year, class, and subject")
        curr = Curriculum(
            academic_year_id=data.academic_year_id,
            class_id=data.class_id,
            subject_id=data.subject_id,
            term_id=data.term_id,
            topics=data.topics,
            objectives=data.objectives,
            total_hours=data.total_hours,
            syllabus=data.syllabus,
            textbook=data.textbook,
            status="active",
        )
        self.session.add(curr)
        await self.session.flush()
        return curr

    async def get(self, curr_id: int) -> Curriculum:
        return await self._get(curr_id)

    async def update(self, curr_id: int, data: CurriculumUpdate) -> Curriculum:
        curr = await self._get(curr_id)
        if data.topics is not None:
            curr.topics = data.topics
        if data.objectives is not None:
            curr.objectives = data.objectives
        if data.total_hours is not None:
            curr.total_hours = data.total_hours
        if data.syllabus is not None:
            curr.syllabus = data.syllabus
        if data.textbook is not None:
            curr.textbook = data.textbook
        if data.status is not None:
            curr.status = data.status
        await self.session.flush()
        return curr

    async def delete(self, curr_id: int) -> None:
        curr = await self._get(curr_id)
        await self.session.delete(curr)

    async def list(
        self,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        term_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Curriculum], int]:
        query = select(Curriculum)
        count_query = select(func.count(Curriculum.id))
        if academic_year_id is not None:
            query = query.where(Curriculum.academic_year_id == academic_year_id)
            count_query = count_query.where(Curriculum.academic_year_id == academic_year_id)
        if class_id is not None:
            query = query.where(Curriculum.class_id == class_id)
            count_query = count_query.where(Curriculum.class_id == class_id)
        if subject_id is not None:
            query = query.where(Curriculum.subject_id == subject_id)
            count_query = count_query.where(Curriculum.subject_id == subject_id)
        if term_id is not None:
            query = query.where(Curriculum.term_id == term_id)
            count_query = count_query.where(Curriculum.term_id == term_id)
        if status is not None:
            query = query.where(Curriculum.status == status)
            count_query = count_query.where(Curriculum.status == status)
        query = query.offset(skip).limit(limit).order_by(Curriculum.id)
        total = (await self.session.execute(count_query)).scalar() or 0
        result = await self.session.execute(query)
        return result.scalars().all(), total
