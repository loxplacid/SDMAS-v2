from __future__ import annotations

import datetime
import logging
from collections import defaultdict
from datetime import timezone
from typing import Optional, Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.pagination import PaginationParams
from app.domains.attendance_intelligence.models import (
    AbsenceReason,
    AttendanceCorrection,
    AttendanceThreshold,
    PeriodAttendance,
    PeriodAttendanceRecord,
)
from app.domains.attendance_intelligence.schemas import (
    VALID_CORRECTION_STATUSES,
    AttendanceCorrectionCreate,
    AttendanceCorrectionReview,
    AttendanceCorrectionUpdate,
    AttendanceThresholdCreate,
    AttendanceThresholdUpdate,
    PeriodAttendanceBatchCreate,
    PeriodAttendanceCreate,
    PeriodAttendanceRecordUpdate,
    AbsenceReasonCreate,
    AbsenceReasonUpdate,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Absence Reason Service
# ═══════════════════════════════════════════════════════════════════════


class AbsenceReasonService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: AbsenceReasonCreate) -> AbsenceReason:
        existing = await self._find_by_code(data.code, data.campus_id)
        if existing:
            raise ConflictError(f"Absence reason with code '{data.code}' already exists")
        reason = AbsenceReason(**data.model_dump())
        self.session.add(reason)
        await self.session.flush()
        return reason

    async def get(self, reason_id: int) -> AbsenceReason:
        result = await self.session.execute(
            select(AbsenceReason).where(AbsenceReason.id == reason_id)
        )
        reason = result.scalar_one_or_none()
        if reason is None:
            raise NotFoundError(f"Absence reason {reason_id} not found")
        return reason

    async def list(
        self,
        campus_id: Optional[int] = None,
        requires_approval: Optional[bool] = None,
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AbsenceReason], int]:
        conditions = []
        if campus_id is not None:
            conditions.append(AbsenceReason.campus_id == campus_id)
        if requires_approval is not None:
            conditions.append(AbsenceReason.requires_approval == requires_approval)
        if status_filter is not None:
            conditions.append(AbsenceReason.status == status_filter)

        count_q = select(func.count(AbsenceReason.id))
        if conditions:
            count_q = count_q.where(and_(*conditions))
        total = (await self.session.execute(count_q)).scalar() or 0

        q = select(AbsenceReason)
        if conditions:
            q = q.where(and_(*conditions))
        q = q.offset(skip).limit(limit).order_by(AbsenceReason.name)
        result = await self.session.execute(q)
        return result.scalars().all(), total

    async def update(self, reason_id: int, data: AbsenceReasonUpdate) -> AbsenceReason:
        reason = await self.get(reason_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(reason, field, value)
        reason.updated_at = datetime.datetime.now(timezone.utc)  # type: ignore
        await self.session.flush()
        return reason

    async def delete(self, reason_id: int) -> None:
        reason = await self.get(reason_id)
        await self.session.delete(reason)
        await self.session.flush()

    async def _find_by_code(
        self, code: str, campus_id: Optional[int] = None
    ) -> AbsenceReason | None:
        conditions = [AbsenceReason.code == code]
        if campus_id is not None:
            conditions.append(AbsenceReason.campus_id == campus_id)
        result = await self.session.execute(
            select(AbsenceReason).where(and_(*conditions))
        )
        return result.scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════════════
# Period Attendance Service
# ═══════════════════════════════════════════════════════════════════════


class PeriodAttendanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_period(self, data: PeriodAttendanceCreate) -> PeriodAttendance:
        existing = await self._find_existing_period(
            section_id=data.section_id,
            date=data.attendance_date,
            period_number=data.period_number,
        )
        if existing:
            raise ConflictError(
                f"Period attendance already exists for section {data.section_id} "
                f"on {data.attendance_date} period {data.period_number}"
            )
        period = PeriodAttendance(**data.model_dump())
        self.session.add(period)
        await self.session.flush()
        return period

    async def batch_create(
        self, data: PeriodAttendanceBatchCreate
    ) -> PeriodAttendance:
        period = await self.create_period(data.attendance)
        for rec_data in data.records:
            self._validate_late_arrival(rec_data)
            self._validate_early_departure(rec_data)
            record = PeriodAttendanceRecord(
                period_attendance_id=period.id,
                **rec_data.model_dump(),
            )
            self.session.add(record)
            if rec_data.status == "absent" and rec_data.absence_reason_id:
                await self._validate_absence_reason(rec_data.absence_reason_id)
        await self.session.flush()

        result = await self.session.execute(
            select(PeriodAttendance)
            .where(PeriodAttendance.id == period.id)
            .options(joinedload(PeriodAttendance.records))
        )
        return result.scalar_one()

    async def get_period(self, period_id: int) -> PeriodAttendance:
        result = await self.session.execute(
            select(PeriodAttendance)
            .where(PeriodAttendance.id == period_id)
            .options(joinedload(PeriodAttendance.records))
        )
        period = result.scalar_one_or_none()
        if period is None:
            raise NotFoundError(f"Period attendance {period_id} not found")
        return period

    async def list_periods(
        self,
        section_id: Optional[int] = None,
        class_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        teacher_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[PeriodAttendance], int]:
        conditions = []
        if section_id is not None:
            conditions.append(PeriodAttendance.section_id == section_id)
        if class_id is not None:
            conditions.append(PeriodAttendance.class_id == class_id)
        if subject_id is not None:
            conditions.append(PeriodAttendance.subject_id == subject_id)
        if teacher_id is not None:
            conditions.append(PeriodAttendance.teacher_id == teacher_id)
        if academic_year_id is not None:
            conditions.append(PeriodAttendance.academic_year_id == academic_year_id)
        if from_date is not None:
            conditions.append(PeriodAttendance.attendance_date >= from_date)
        if to_date is not None:
            conditions.append(PeriodAttendance.attendance_date <= to_date)

        cnt = select(func.count(PeriodAttendance.id))
        if conditions:
            cnt = cnt.where(and_(*conditions))
        total = (await self.session.execute(cnt)).scalar() or 0

        q = select(PeriodAttendance).options(joinedload(PeriodAttendance.records))
        if conditions:
            q = q.where(and_(*conditions))
        q = q.offset(skip).limit(limit).order_by(
            PeriodAttendance.attendance_date, PeriodAttendance.period_number
        )
        result = await self.session.execute(q)
        items = list({r.id: r for r in result.scalars().all()}.values())
        return items[:limit], total

    async def update_record(
        self, record_id: int, data: PeriodAttendanceRecordUpdate
    ) -> PeriodAttendanceRecord:
        result = await self.session.execute(
            select(PeriodAttendanceRecord).where(
                PeriodAttendanceRecord.id == record_id
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise NotFoundError(f"Period attendance record {record_id} not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(record, field, value)
        record.updated_at = datetime.datetime.now(timezone.utc)  # type: ignore
        await self.session.flush()
        return record

    async def get_student_records(
        self,
        student_id: int,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[PeriodAttendanceRecord], int]:
        conditions = [PeriodAttendanceRecord.student_id == student_id]
        if from_date is not None:
            conditions.append(
                PeriodAttendanceRecord.period_attendance.has(
                    PeriodAttendance.attendance_date >= from_date
                )
            )
        if to_date is not None:
            conditions.append(
                PeriodAttendanceRecord.period_attendance.has(
                    PeriodAttendance.attendance_date <= to_date
                )
            )
        cnt = select(func.count(PeriodAttendanceRecord.id)).where(and_(*conditions))
        total = (await self.session.execute(cnt)).scalar() or 0

        q = (
            select(PeriodAttendanceRecord)
            .where(and_(*conditions))
            .options(joinedload(PeriodAttendanceRecord.period_attendance))
            .offset(skip)
            .limit(limit)
            .order_by(PeriodAttendanceRecord.id)
        )
        result = await self.session.execute(q)
        return result.scalars().all(), total

    async def _find_existing_period(
        self, section_id: int, date: str, period_number: int
    ) -> PeriodAttendance | None:
        result = await self.session.execute(
            select(PeriodAttendance).where(
                PeriodAttendance.section_id == section_id,
                PeriodAttendance.attendance_date == date,
                PeriodAttendance.period_number == period_number,
            )
        )
        return result.scalar_one_or_none()

    async def _validate_absence_reason(self, reason_id: int) -> None:
        result = await self.session.execute(
            select(AbsenceReason).where(AbsenceReason.id == reason_id)
        )
        if result.scalar_one_or_none() is None:
            raise ValidationError(f"Absence reason {reason_id} not found")

    def _validate_late_arrival(self, data) -> None:
        if data.arrival_time and data.status != "late" and data.status != "present":
            pass
        if data.status == "late" and not data.arrival_time and not data.late_minutes:
            pass

    def _validate_early_departure(self, data) -> None:
        if data.departure_time and data.status != "present":
            pass
        if data.early_departure_minutes and not data.departure_time:
            pass


# ═══════════════════════════════════════════════════════════════════════
# Attendance Correction Service
# ═══════════════════════════════════════════════════════════════════════


class AttendanceCorrectionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, data: AttendanceCorrectionCreate, requested_by: int
    ) -> AttendanceCorrection:
        previous_status = await self._get_current_status(
            data.record_type, data.record_id
        )
        correction = AttendanceCorrection(
            record_type=data.record_type,
            record_id=data.record_id,
            requested_by=requested_by,
            requested_status=data.requested_status,
            previous_status=previous_status,
            absence_reason_id=data.absence_reason_id,
            reason=data.reason,
            campus_id=data.campus_id,
            status="pending",
        )
        self.session.add(correction)
        await self.session.flush()
        return correction

    async def get(self, correction_id: int) -> AttendanceCorrection:
        result = await self.session.execute(
            select(AttendanceCorrection).where(
                AttendanceCorrection.id == correction_id
            )
        )
        correction = result.scalar_one_or_none()
        if correction is None:
            raise NotFoundError(f"Attendance correction {correction_id} not found")
        return correction

    async def list(
        self,
        status_filter: Optional[str] = None,
        record_type: Optional[str] = None,
        requested_by: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AttendanceCorrection], int]:
        conditions = []
        if status_filter is not None:
            conditions.append(AttendanceCorrection.status == status_filter)
        if record_type is not None:
            conditions.append(AttendanceCorrection.record_type == record_type)
        if requested_by is not None:
            conditions.append(AttendanceCorrection.requested_by == requested_by)

        cnt = select(func.count(AttendanceCorrection.id))
        if conditions:
            cnt = cnt.where(and_(*conditions))
        total = (await self.session.execute(cnt)).scalar() or 0

        q = select(AttendanceCorrection)
        if conditions:
            q = q.where(and_(*conditions))
        q = q.offset(skip).limit(limit).order_by(AttendanceCorrection.created_at.desc())
        result = await self.session.execute(q)
        return result.scalars().all(), total

    async def review(
        self, correction_id: int, data: AttendanceCorrectionReview, reviewed_by: int
    ) -> AttendanceCorrection:
        correction = await self.get(correction_id)
        if correction.status != "pending":
            raise ValidationError(
                f"Correction {correction_id} is already {correction.status}"
            )

        correction.status = data.status
        correction.reviewed_by = reviewed_by
        correction.reviewed_at = datetime.datetime.now(timezone.utc)
        correction.review_notes = data.review_notes
        await self.session.flush()

        if data.status == "approved":
            await self._apply_correction(correction)

        return correction

    async def _get_current_status(
        self, record_type: str, record_id: int
    ) -> Optional[str]:
        if record_type == "daily":
            from app.domains.attendance.models import AttendanceRecord

            result = await self.session.execute(
                select(AttendanceRecord.status).where(
                    AttendanceRecord.id == record_id
                )
            )
            return result.scalar_one_or_none()
        elif record_type == "period":
            result = await self.session.execute(
                select(PeriodAttendanceRecord.status).where(
                    PeriodAttendanceRecord.id == record_id
                )
            )
            return result.scalar_one_or_none()
        return None

    async def _apply_correction(self, correction: AttendanceCorrection) -> None:
        if correction.record_type == "daily":
            from app.domains.attendance.models import AttendanceRecord

            result = await self.session.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.id == correction.record_id
                )
            )
            record = result.scalar_one_or_none()
            if record:
                record.status = correction.requested_status
                record.updated_at = datetime.datetime.now(timezone.utc)  # type: ignore
                await self.session.flush()

        elif correction.record_type == "period":
            result = await self.session.execute(
                select(PeriodAttendanceRecord).where(
                    PeriodAttendanceRecord.id == correction.record_id
                )
            )
            record = result.scalar_one_or_none()
            if record:
                record.status = correction.requested_status
                if correction.absence_reason_id:
                    record.absence_reason_id = correction.absence_reason_id
                record.updated_at = datetime.datetime.now(timezone.utc)  # type: ignore
                await self.session.flush()

    async def delete(self, correction_id: int) -> None:
        correction = await self.get(correction_id)
        await self.session.delete(correction)
        await self.session.flush()


# ═══════════════════════════════════════════════════════════════════════
# Attendance Threshold Service
# ═══════════════════════════════════════════════════════════════════════


class AttendanceThresholdService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: AttendanceThresholdCreate) -> AttendanceThreshold:
        threshold = AttendanceThreshold(**data.model_dump())
        self.session.add(threshold)
        await self.session.flush()
        return threshold

    async def get(self, threshold_id: int) -> AttendanceThreshold:
        result = await self.session.execute(
            select(AttendanceThreshold).where(
                AttendanceThreshold.id == threshold_id
            )
        )
        t = result.scalar_one_or_none()
        if t is None:
            raise NotFoundError(f"Attendance threshold {threshold_id} not found")
        return t

    async def list(
        self,
        campus_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        threshold_type: Optional[str] = None,
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AttendanceThreshold], int]:
        conditions = []
        if campus_id is not None:
            conditions.append(AttendanceThreshold.campus_id == campus_id)
        if academic_year_id is not None:
            conditions.append(
                AttendanceThreshold.academic_year_id == academic_year_id
            )
        if threshold_type is not None:
            conditions.append(
                AttendanceThreshold.threshold_type == threshold_type
            )
        if status_filter is not None:
            conditions.append(AttendanceThreshold.status == status_filter)

        cnt = select(func.count(AttendanceThreshold.id))
        if conditions:
            cnt = cnt.where(and_(*conditions))
        total = (await self.session.execute(cnt)).scalar() or 0

        q = select(AttendanceThreshold)
        if conditions:
            q = q.where(and_(*conditions))
        q = q.offset(skip).limit(limit).order_by(AttendanceThreshold.percentage)
        result = await self.session.execute(q)
        return result.scalars().all(), total

    async def update(
        self, threshold_id: int, data: AttendanceThresholdUpdate
    ) -> AttendanceThreshold:
        t = await self.get(threshold_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(t, field, value)
        t.updated_at = datetime.datetime.now(timezone.utc)  # type: ignore
        await self.session.flush()
        return t

    async def delete(self, threshold_id: int) -> None:
        t = await self.get(threshold_id)
        await self.session.delete(t)
        await self.session.flush()

    async def get_active_thresholds(
        self, campus_id: Optional[int] = None, academic_year_id: Optional[int] = None
    ) -> list[AttendanceThreshold]:
        conditions = [AttendanceThreshold.status == "active"]
        if campus_id is not None:
            conditions.append(AttendanceThreshold.campus_id == campus_id)
        if academic_year_id is not None:
            conditions.append(
                AttendanceThreshold.academic_year_id == academic_year_id
            )
        result = await self.session.execute(
            select(AttendanceThreshold)
            .where(and_(*conditions))
            .order_by(AttendanceThreshold.percentage)
        )
        return list(result.scalars().all())


# ═══════════════════════════════════════════════════════════════════════
# Analytics Service
# ═══════════════════════════════════════════════════════════════════════


class AttendanceAnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_student_trend(
        self,
        student_id: int,
        start_date: str,
        end_date: str,
    ) -> dict:
        records = await self.session.execute(
            select(PeriodAttendanceRecord)
            .where(
                PeriodAttendanceRecord.student_id == student_id,
                PeriodAttendanceRecord.created_at >= start_date,
                PeriodAttendanceRecord.created_at <= end_date,
            )
            .options(joinedload(PeriodAttendanceRecord.period_attendance))
            .order_by(PeriodAttendanceRecord.period_attendance.has(
                PeriodAttendance.attendance_date
            ))
        )
        items = records.scalars().all()

        trend = []
        present = absent = late = excused = 0
        late_arrivals = early_departures = 0

        for r in items:
            status = r.status
            trend.append({
                "date": str(r.period_attendance.attendance_date) if r.period_attendance else "",
                "status": status,
                "period_number": r.period_attendance.period_number if r.period_attendance else None,
            })
            if status == "present":
                present += 1
            elif status == "absent":
                absent += 1
            elif status == "late":
                late += 1
                if r.late_minutes:
                    late_arrivals += 1
            elif status == "excused":
                excused += 1
            if r.early_departure_minutes:
                early_departures += 1

        total = len(items) or 1
        pct = round(((present + late + excused) / total) * 100, 1)

        return {
            "student_id": student_id,
            "start_date": start_date,
            "end_date": end_date,
            "trend": trend,
            "total_periods": len(items),
            "present_count": present,
            "absent_count": absent,
            "late_count": late,
            "excused_count": excused,
            "attendance_percentage": pct,
            "late_arrivals": late_arrivals,
            "early_departures": early_departures,
        }

    async def get_class_trend(
        self,
        class_id: int,
        start_date: str,
        end_date: str,
    ) -> dict:
        periods = await self.session.execute(
            select(PeriodAttendance).where(
                PeriodAttendance.class_id == class_id,
                PeriodAttendance.attendance_date >= start_date,
                PeriodAttendance.attendance_date <= end_date,
            )
        )
        period_ids = [p.id for p in periods.scalars().all()]
        if not period_ids:
            return {
                "class_id": class_id,
                "start_date": start_date,
                "end_date": end_date,
                "total_students": 0,
                "total_periods": 0,
                "average_attendance_percentage": 0.0,
                "present_count": 0,
                "absent_count": 0,
                "late_count": 0,
                "excused_count": 0,
            }

        records = await self.session.execute(
            select(PeriodAttendanceRecord).where(
                PeriodAttendanceRecord.period_attendance_id.in_(period_ids)
            )
        )
        items = records.scalars().all()
        total_students = len(set(r.student_id for r in items))
        present = sum(1 for r in items if r.status == "present")
        absent = sum(1 for r in items if r.status == "absent")
        late = sum(1 for r in items if r.status == "late")
        excused = sum(1 for r in items if r.status == "excused")
        total = len(items) or 1
        pct = round(((present + late + excused) / total) * 100, 1)

        return {
            "class_id": class_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_students": total_students,
            "total_periods": len(period_ids),
            "average_attendance_percentage": pct,
            "present_count": present,
            "absent_count": absent,
            "late_count": late,
            "excused_count": excused,
        }

    async def get_section_trend(
        self,
        section_id: int,
        start_date: str,
        end_date: str,
    ) -> dict:
        periods = await self.session.execute(
            select(PeriodAttendance).where(
                PeriodAttendance.section_id == section_id,
                PeriodAttendance.attendance_date >= start_date,
                PeriodAttendance.attendance_date <= end_date,
            )
        )
        period_ids = [p.id for p in periods.scalars().all()]
        if not period_ids:
            return {
                "section_id": section_id,
                "class_id": 0,
                "start_date": start_date,
                "end_date": end_date,
                "total_students": 0,
                "total_periods": 0,
                "average_attendance_percentage": 0.0,
                "present_count": 0,
                "absent_count": 0,
                "late_count": 0,
                "excused_count": 0,
            }

        first = periods.scalars().first()
        class_id = first.class_id if first else 0

        records = await self.session.execute(
            select(PeriodAttendanceRecord).where(
                PeriodAttendanceRecord.period_attendance_id.in_(period_ids)
            )
        )
        items = records.scalars().all()
        total_students = len(set(r.student_id for r in items))
        present = sum(1 for r in items if r.status == "present")
        absent = sum(1 for r in items if r.status == "absent")
        late = sum(1 for r in items if r.status == "late")
        excused = sum(1 for r in items if r.status == "excused")
        total = len(items) or 1
        pct = round(((present + late + excused) / total) * 100, 1)

        return {
            "section_id": section_id,
            "class_id": class_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_students": total_students,
            "total_periods": len(period_ids),
            "average_attendance_percentage": pct,
            "present_count": present,
            "absent_count": absent,
            "late_count": late,
            "excused_count": excused,
        }

    async def get_chronic_absenteeism(
        self,
        campus_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        threshold_pct: float = 75.0,
        consecutive_days: int = 5,
        limit: int = 50,
    ) -> list[dict]:
        conditions = [PeriodAttendanceRecord.status == "absent"]
        if campus_id is not None:
            conditions.append(PeriodAttendance.campus_id == campus_id)
        if academic_year_id is not None:
            conditions.append(
                PeriodAttendance.academic_year_id == academic_year_id
            )

        records = await self.session.execute(
            select(PeriodAttendanceRecord)
            .join(PeriodAttendanceRecord.period_attendance)
            .where(and_(*conditions))
            .order_by(
                PeriodAttendanceRecord.student_id,
                PeriodAttendance.attendance_date,
            )
        )
        items = records.scalars().all()

        student_absences: dict[int, list[str]] = defaultdict(list)
        for r in items:
            date_str = str(r.period_attendance.attendance_date)
            if date_str not in student_absences[r.student_id]:
                student_absences[r.student_id].append(date_str)

        all_students = await self.session.execute(
            select(PeriodAttendanceRecord.student_id)
            .distinct()
        )
        total_students_list = list(all_students.scalars().all())

        result = []
        for sid in total_students_list:
            abs_dates = sorted(student_absences.get(sid, []))
            total_absent = len(abs_dates)

            total_records = await self.session.execute(
                select(func.count(PeriodAttendanceRecord.id)).where(
                    PeriodAttendanceRecord.student_id == sid
                )
            )
            total = total_records.scalar() or 1
            present_records = await self.session.execute(
                select(func.count(PeriodAttendanceRecord.id)).where(
                    PeriodAttendanceRecord.student_id == sid,
                    PeriodAttendanceRecord.status.in_(["present", "late", "excused"]),
                )
            )
            present_total = total - total_absent
            pct = round((present_total / total) * 100, 1)

            consecutive = self._count_consecutive(abs_dates)

            if pct < threshold_pct or consecutive >= consecutive_days:
                result.append({
                    "student_id": sid,
                    "total_periods": total,
                    "absent_count": total_absent,
                    "attendance_percentage": pct,
                    "consecutive_absences": consecutive,
                    "threshold": threshold_pct,
                    "threshold_name": "Chronic Absenteeism",
                })

        result.sort(key=lambda x: x["attendance_percentage"])
        return result[:limit]

    def _count_consecutive(self, dates: list[str]) -> int:
        if not dates:
            return 0
        from datetime import date as dt_date

        parsed = []
        for d in dates:
            try:
                parsed.append(dt_date.fromisoformat(d))
            except (ValueError, TypeError):
                continue
        parsed.sort()

        max_run = 1
        current_run = 1
        for i in range(1, len(parsed)):
            diff = (parsed[i] - parsed[i - 1]).days
            if diff == 1:
                current_run += 1
                max_run = max(max_run, current_run)
            elif diff > 1:
                current_run = 1
        return max_run

    async def get_low_attendance_alerts(
        self,
        campus_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
    ) -> list[dict]:
        threshold_svc = AttendanceThresholdService(self.session)
        thresholds = await threshold_svc.get_active_thresholds(
            campus_id, academic_year_id
        )
        if not thresholds:
            thresholds = [
                type("obj", (object,), {
                    "percentage": 75.0,
                    "name": "Default Warning",
                    "threshold_type": "warning",
                    "notification_enabled": True,
                })()
            ]

        alerts = []
        for t in thresholds:
            chronic = await self.get_chronic_absenteeism(
                campus_id=campus_id,
                academic_year_id=academic_year_id,
                threshold_pct=t.percentage,
                limit=20,
            )
            for item in chronic:
                alerts.append({
                    "student_id": item["student_id"],
                    "attendance_percentage": item["attendance_percentage"],
                    "threshold": t.percentage,
                    "threshold_name": t.name,
                    "total_absences": item["absent_count"],
                })

        alerts.sort(key=lambda x: x["attendance_percentage"])
        seen = set()
        unique = []
        for a in alerts:
            key = (a["student_id"], a["threshold_name"])
            if key not in seen:
                seen.add(key)
                unique.append(a)
        return unique

    async def get_dashboard(
        self,
        campus_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        today_date: Optional[str] = None,
    ) -> dict:
        if today_date is None:
            today_date = datetime.date.today().isoformat()

        today_periods = await self.session.execute(
            select(PeriodAttendance).where(
                PeriodAttendance.attendance_date == today_date
            )
        )
        today_ids = [p.id for p in today_periods.scalars().all()]

        today_records = []
        if today_ids:
            r = await self.session.execute(
                select(PeriodAttendanceRecord).where(
                    PeriodAttendanceRecord.period_attendance_id.in_(today_ids)
                )
            )
            today_records = list(r.scalars().all())

        present_today = sum(1 for rec in today_records if rec.status == "present")
        absent_today = sum(1 for rec in today_records if rec.status == "absent")
        late_today = sum(1 for rec in today_records if rec.status == "late")

        total_students_q = await self.session.execute(
            select(func.count(func.distinct(PeriodAttendanceRecord.student_id)))
        )
        total_students = total_students_q.scalar() or 0

        all_records = await self.session.execute(
            select(PeriodAttendanceRecord)
        )
        all_items = list(all_records.scalars().all())
        total = len(all_items) or 1
        present = sum(1 for r in all_items if r.status == "present")
        late = sum(1 for r in all_items if r.status == "late")
        excused = sum(1 for r in all_items if r.status == "excused")
        overall_pct = round(((present + late + excused) / total) * 100, 1)

        chronic = await self.get_chronic_absenteeism(
            campus_id=campus_id,
            academic_year_id=academic_year_id,
            limit=10,
        )

        alerts = await self.get_low_attendance_alerts(
            campus_id=campus_id, academic_year_id=academic_year_id
        )

        return {
            "total_students": total_students,
            "overall_attendance_percentage": overall_pct,
            "present_today": present_today,
            "absent_today": absent_today,
            "late_today": late_today,
            "chronic_count": len(chronic),
            "low_attendance_alerts": alerts[:10],
            "top_absenteeism": chronic[:10],
        }
