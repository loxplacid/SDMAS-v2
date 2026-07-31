from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import Class, Section, Subject, Teacher, Term
from app.domains.academic_ops.models import TimetableEntry, TimeSlot, Room
from app.domains.report_builder.base import BaseReportBuilder, ReportMeta, ReportFilter, ReportColumn
from app.domains.report_builder.registry import ReportRegistry


@ReportRegistry.register
class TeacherWorkloadReport(BaseReportBuilder):
    @classmethod
    def meta(cls) -> ReportMeta:
        return ReportMeta(
            code="teacher_workload",
            name="Teacher Workload",
            description="Teacher workload breakdown with timetable periods per week per subject and class",
            category="academic",
            allowed_roles=["admin", "manager"],
            filters=[
                ReportFilter(key="academic_year_id", label="Academic Year", type="select", required=True),
                ReportFilter(key="term_id", label="Term", type="select", required=False),
                ReportFilter(key="teacher_id", label="Teacher", type="select", required=False),
            ],
            columns=[
                ReportColumn(key="teacher_name", header="Teacher Name"),
                ReportColumn(key="teacher_code", header="Teacher Code"),
                ReportColumn(key="subject_name", header="Subject"),
                ReportColumn(key="class_name", header="Class"),
                ReportColumn(key="section_name", header="Section"),
                ReportColumn(key="day_of_week", header="Day of Week", type="integer"),
                ReportColumn(key="start_time", header="Start Time"),
                ReportColumn(key="end_time", header="End Time"),
                ReportColumn(key="room_name", header="Room"),
                ReportColumn(key="periods_per_week", header="Periods/Week", type="integer"),
            ],
        )

    async def fetch_data(
        self, params: dict[str, Any], user_id: int, campus_id: Optional[int], session: AsyncSession
    ) -> Any:
        academic_year_id = params["academic_year_id"]
        term_id = params.get("term_id")
        teacher_id = params.get("teacher_id")

        conditions = [TimetableEntry.academic_year_id == academic_year_id]
        if term_id is not None:
            conditions.append(TimetableEntry.term_id == term_id)
        if teacher_id is not None:
            conditions.append(TimetableEntry.teacher_id == teacher_id)
        if campus_id is not None:
            conditions.append(TimetableEntry.campus_id == campus_id)

        stmt = (
            select(
                TimetableEntry,
                Teacher,
                Subject,
                Class,
                Section,
                TimeSlot,
                Room,
            )
            .join(Teacher, TimetableEntry.teacher_id == Teacher.id)
            .join(Subject, TimetableEntry.subject_id == Subject.id)
            .join(Class, TimetableEntry.class_id == Class.id)
            .join(TimeSlot, TimetableEntry.time_slot_id == TimeSlot.id)
            .outerjoin(Section, TimetableEntry.section_id == Section.id)
            .outerjoin(Room, TimetableEntry.room_id == Room.id)
            .where(and_(*conditions))
            .order_by(Teacher.last_name, Teacher.first_name, Subject.name, TimetableEntry.day_of_week, TimeSlot.start_time)
        )

        result = await session.execute(stmt)
        records = result.all()

        period_count_stmt = (
            select(
                TimetableEntry.teacher_id,
                func.count().label("periods"),
            )
            .where(and_(*conditions))
            .group_by(TimetableEntry.teacher_id)
        )

        count_result = await session.execute(period_count_stmt)
        period_counts = {row.teacher_id: row.periods for row in count_result.all()}

        return {
            "records": records,
            "period_counts": period_counts,
        }

    def build_rows(self, data: Any) -> list[dict[str, Any]]:
        rows = []
        for row in data["records"]:
            entry, teacher, subject, cls, section, time_slot, room = row
            rows.append({
                "teacher_name": f"{teacher.first_name} {teacher.last_name}",
                "teacher_code": teacher.employee_number,
                "subject_name": subject.name,
                "class_name": cls.name,
                "section_name": section.name if section else "",
                "day_of_week": entry.day_of_week,
                "start_time": time_slot.start_time,
                "end_time": time_slot.end_time,
                "room_name": room.name if room else "",
                "periods_per_week": data["period_counts"].get(entry.teacher_id, 0),
            })
        return rows

    def build_summary(self, data: Any) -> dict[str, Any]:
        teacher_ids = set()
        for row in data["records"]:
            entry = row[0]
            teacher_ids.add(entry.teacher_id)

        total_teachers = len(teacher_ids)
        total_periods = sum(data["period_counts"].values())
        avg_periods = round(total_periods / total_teachers, 1) if total_teachers > 0 else 0.0

        return {
            "total_teachers": total_teachers,
            "total_periods": total_periods,
            "average_periods_per_teacher": avg_periods,
        }
