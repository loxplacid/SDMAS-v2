from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    SectionRepository,
)
from app.domains.attendance.models import AttendanceRecord
from app.domains.attendance.repository import AttendanceRepository
from app.domains.attendance.schemas import (
    VALID_ATTENDANCE_STATUSES,
    AttendanceRecordCreate,
    AttendanceRecordUpdate,
    DailyAttendanceCreate,
)
from app.domains.student.repository import StudentRepository
from app.domains.audit.constants import ATTENDANCE, CREATE, UPDATE
from app.domains.audit.service import AuditService
from app.domains.notifications import dispatcher as notification_dispatcher
from app.domains.notifications.events import LowAttendanceEvent

logger = logging.getLogger(__name__)


class AttendanceService:
    def __init__(
        self,
        attendance_repo: AttendanceRepository,
        student_repo: StudentRepository,
        year_repo: AcademicYearRepository,
        class_repo: ClassRepository,
        section_repo: SectionRepository,
    ) -> None:
        self.repo = attendance_repo
        self.student_repo = student_repo
        self.year_repo = year_repo
        self.class_repo = class_repo
        self.section_repo = section_repo

    async def _validate_student(self, student_id: int):
        student = await self.student_repo.get_by_id(student_id)
        if student.status != "active":
            raise ValidationError(
                "Cannot record attendance for an inactive student"
            )
        return student

    async def _validate_academic_year(self, year_id: int):
        year = await self.year_repo.get_by_id(year_id)
        if year.status != "active":
            raise ValidationError(
                "Cannot record attendance for an inactive academic year"
            )
        return year

    async def _validate_class(self, class_id: int):
        cls = await self.class_repo.get_by_id(class_id)
        if cls.status != "active":
            raise ValidationError(
                "Cannot record attendance for an inactive class"
            )
        return cls

    async def _validate_section(self, section_id: int):
        section = await self.section_repo.get_by_id(section_id)
        if section.status != "active":
            raise ValidationError(
                "Cannot record attendance for an inactive section"
            )
        return section

    async def _validate_student_enrolled_in_section(
        self, student_id: int, section_id: int
    ) -> None:
        from app.domains.academic.repository import EnrollmentRepository

        enrollment_repo = EnrollmentRepository(self.repo.session)
        enrollments, _ = await enrollment_repo.list(
            section_id=section_id, limit=10000
        )
        enrolled = any(e.student_id == student_id for e in enrollments)
        if not enrolled:
            raise ValidationError(
                f"Student {student_id} is not enrolled in section {section_id}"
            )

    async def record_attendance(self, data: AttendanceRecordCreate) -> AttendanceRecord:
        student = await self._validate_student(data.student_id)
        await self._validate_academic_year(data.academic_year_id)
        await self._validate_class(data.class_id)
        section = await self._validate_section(data.section_id)

        if not data.attendance_date or not data.attendance_date.strip():
            raise ValidationError("Attendance date is required")

        if data.status not in VALID_ATTENDANCE_STATUSES:
            raise ValidationError(
                f"Invalid attendance status. Must be one of: {', '.join(sorted(VALID_ATTENDANCE_STATUSES))}"
            )

        await self._validate_student_enrolled_in_section(
            student.id, section.id
        )

        duplicate = await self.repo.find_duplicate(
            student.id, data.attendance_date, section.id
        )
        if duplicate is not None:
            raise ConflictError(
                f"Attendance record already exists for student {student.id} on {data.attendance_date} in section {section.id}"
            )

        import datetime
        from datetime import timezone

        now = datetime.datetime.now(timezone.utc)
        record = AttendanceRecord(
            student_id=student.id,
            academic_year_id=data.academic_year_id,
            class_id=data.class_id,
            section_id=section.id,
            attendance_date=data.attendance_date,
            status=data.status,
            notes=data.notes,
            recorded_at=now,
            updated_at=now,
        )
        created = await self.repo.create(record)

        # Audit: attendance recorded
        try:
            audit_svc = AuditService(self.repo.session)
            await audit_svc.record(
                action=CREATE,
                resource_type=ATTENDANCE,
                resource_id=str(created.id),
                details={
                    "student_id": data.student_id,
                    "section_id": data.section_id,
                    "date": data.attendance_date,
                    "status": data.status,
                },
            )
            await self.repo.session.flush()
        except Exception:
            logger.warning("Failed to write audit entry for attendance (non-fatal)", exc_info=True)

        return created

    async def record_daily_attendance(
        self, data: DailyAttendanceCreate
    ) -> list[AttendanceRecord]:
        if data.section_id is None:
            raise ValidationError("Section id is required")
        if not data.attendance_date or not data.attendance_date.strip():
            raise ValidationError("Date is required")
        if not data.records:
            raise ValidationError("Attendance records must be a non-empty array")

        for item in data.records:
            if item.student_id is None:
                raise ValidationError("Student id is required for each attendance record")
            if item.status not in VALID_ATTENDANCE_STATUSES:
                raise ValidationError(
                    f"Invalid attendance status for student {item.student_id}. "
                    f"Must be one of: {', '.join(sorted(VALID_ATTENDANCE_STATUSES))}"
                )

        section = await self._validate_section(data.section_id)
        cls = await self.class_repo.get_by_id(section.class_id)
        year = await self._validate_academic_year(cls.academic_year_id)

        student_ids = [r.student_id for r in data.records]

        from app.domains.student.models import Student as StudentModel
        from app.domains.academic.models import Enrollment as EnrollmentModel

        student_result = await self.repo.session.execute(
            select(StudentModel).where(StudentModel.id.in_(student_ids))
        )
        students = {s.id: s for s in student_result.scalars().all()}
        for sid in student_ids:
            s = students.get(sid)
            if s is None:
                raise ValidationError(f"Student with id {sid} not found")
            if s.status != "active":
                raise ValidationError(f"Cannot record attendance for an inactive student (id={sid})")

        enrollment_result = await self.repo.session.execute(
            select(EnrollmentModel.student_id).where(
                EnrollmentModel.student_id.in_(student_ids),
                EnrollmentModel.section_id == data.section_id,
                EnrollmentModel.status == "active",
            )
        )
        enrolled_ids = {row[0] for row in enrollment_result.all()}
        for sid in student_ids:
            if sid not in enrolled_ids:
                raise ValidationError(f"Student {sid} is not enrolled in section {data.section_id}")

        duplicate_result = await self.repo.session.execute(
            select(AttendanceRecord.student_id).where(
                AttendanceRecord.student_id.in_(student_ids),
                AttendanceRecord.attendance_date == data.attendance_date,
                AttendanceRecord.section_id == data.section_id,
            )
        )
        duplicate_ids = {row[0] for row in duplicate_result.all()}
        for sid in student_ids:
            if sid in duplicate_ids:
                raise ConflictError(
                    f"Attendance record already exists for student {sid} on {data.attendance_date} in section {data.section_id}"
                )

        import datetime
        from datetime import timezone

        now = datetime.datetime.now(timezone.utc)
        saved_records: list[AttendanceRecord] = []
        for item in data.records:
            record = AttendanceRecord(
                student_id=item.student_id,
                academic_year_id=year.id,
                class_id=cls.id,
                section_id=data.section_id,
                attendance_date=data.attendance_date,
                status=item.status,
                notes=item.notes,
                recorded_at=now,
                updated_at=now,
            )
            saved = await self.repo.create(record)
            saved_records.append(saved)

        try:
            absent_records = [r for r in saved_records if r.status in ("absent", "late")]
            if absent_records:
                absent_ids = [r.student_id for r in absent_records]
                all_records_result = await self.repo.session.execute(
                    select(AttendanceRecord).where(
                        AttendanceRecord.student_id.in_(absent_ids),
                        AttendanceRecord.attendance_date >= "1900-01-01",
                        AttendanceRecord.attendance_date <= "2100-12-31",
                    )
                )
                all_absent_records = all_records_result.scalars().all()
                by_student: dict[int, list[AttendanceRecord]] = {}
                for rec in all_absent_records:
                    by_student.setdefault(rec.student_id, []).append(rec)

                for rec in absent_records:
                    total_records = by_student.get(rec.student_id, [])
                    total_count = len(total_records) + 1
                    absences = sum(1 for r in total_records if r.status in ("absent", "late")) + 1
                    pct = ((total_count - absences) / total_count) * 100

                    if pct < 75.0:
                        event = LowAttendanceEvent(
                            student_id=rec.student_id,
                            academic_year_id=year.id,
                            section_id=data.section_id,
                            attendance_percentage=round(pct, 1),
                            threshold=75.0,
                            total_absences=absences,
                        )
                        await notification_dispatcher.dispatch(event, session=self.repo.session)
        except Exception:
            logger.warning("Failed to dispatch LowAttendanceEvent (non-fatal)", exc_info=True)

        return saved_records

    async def get_attendance(self, record_id: int) -> AttendanceRecord:
        return await self.repo.get_by_id(record_id)

    async def update_attendance(
        self, record_id: int, data: AttendanceRecordUpdate
    ) -> AttendanceRecord:
        existing = await self.repo.get_by_id(record_id)
        before_status = existing.status

        if data.status is not None:
            if data.status not in VALID_ATTENDANCE_STATUSES:
                raise ValidationError(
                    f"Invalid attendance status. Must be one of: {', '.join(sorted(VALID_ATTENDANCE_STATUSES))}"
                )
            existing.status = data.status
        if data.notes is not None:
            existing.notes = data.notes

        import datetime
        from datetime import timezone

        existing.updated_at = datetime.datetime.now(timezone.utc)
        updated = await self.repo.update(existing)

        # Audit: attendance edit
        if data.status is not None and data.status != before_status:
            try:
                audit_svc = AuditService(self.repo.session)
                await audit_svc.record(
                    action=UPDATE,
                    resource_type=ATTENDANCE,
                    resource_id=str(record_id),
                    details={
                        "before": {"status": before_status},
                        "after": {"status": data.status},
                    },
                )
                await self.repo.session.flush()
            except Exception:
                logger.warning("Failed to write audit entry for attendance edit (non-fatal)", exc_info=True)

        return updated

    async def get_student_attendance(
        self,
        student_id: int,
        academic_year_id: Optional[int] = None,
        class_id: Optional[int] = None,
        section_id: Optional[int] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AttendanceRecord], int]:
        if status is not None and status not in VALID_ATTENDANCE_STATUSES:
            raise ValidationError(
                f"Invalid attendance status filter. Must be one of: {', '.join(sorted(VALID_ATTENDANCE_STATUSES))}"
            )
        return await self.repo.find_by_student_and_filters(
            student_id=student_id,
            academic_year_id=academic_year_id,
            class_id=class_id,
            section_id=section_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )

    async def get_section_attendance(
        self,
        section_id: int,
        date: str,
    ) -> Sequence[AttendanceRecord]:
        return await self.repo.find_by_section_and_date(section_id, date)

    async def get_student_summary(
        self,
        student_id: int,
        start_date: str,
        end_date: str,
    ) -> dict:
        records = await self.repo.find_by_student_and_date_range(
            student_id, start_date, end_date
        )

        total = len(records)
        present = 0
        absent = 0
        late = 0
        excused = 0

        for record in records:
            if record.status == "present":
                present += 1
            elif record.status == "absent":
                absent += 1
            elif record.status == "late":
                late += 1
            elif record.status == "excused":
                excused += 1

        percentage = round((present / total) * 10000) / 100 if total > 0 else 0.0

        return {
            "student_id": student_id,
            "start_date": start_date,
            "end_date": end_date,
            "total": total,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "percentage": percentage,
        }

    async def get_section_summary(
        self,
        section_id: int,
        date: str,
    ) -> dict:
        from app.domains.academic.repository import EnrollmentRepository

        enrollment_repo = EnrollmentRepository(self.repo.session)
        enrollments, _ = await enrollment_repo.list(
            section_id=section_id, limit=10000
        )
        records = await self.repo.find_by_section_and_date(section_id, date)

        present = 0
        absent = 0
        late = 0
        excused = 0

        for record in records:
            if record.status == "present":
                present += 1
            elif record.status == "absent":
                absent += 1
            elif record.status == "late":
                late += 1
            elif record.status == "excused":
                excused += 1

        total_marked = len(records)
        present_percentage = (
            round((present / total_marked) * 10000) / 100
            if total_marked > 0
            else 0.0
        )

        return {
            "section_id": section_id,
            "attendance_date": date,
            "total_students": len(enrollments),
            "total_marked": total_marked,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "present_percentage": present_percentage,
        }