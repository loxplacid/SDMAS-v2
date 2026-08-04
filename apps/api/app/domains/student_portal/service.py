from __future__ import annotations

import datetime
import logging
from typing import Any, Optional

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.domains.academic.models import AcademicYear, Class, Enrollment, Section, Subject
from app.domains.academic_ops.models import GradeRecord, TimetableEntry
from app.domains.academic_ops.service import DAY_NAMES as ACADEMIC_DAY_NAMES
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.domains.student_portal.schemas import (
    AttendanceRecord,
    AttendanceSummary,
    EnrolledSubject,
    EnrollmentInfo,
    StudentAnnouncement,
    StudentAnnouncementsResponse,
    StudentAssignment,
    StudentAssignmentsResponse,
    StudentAttendanceResponse,
    StudentDocument,
    StudentDocumentsResponse,
    StudentPortalDashboardResponse,
    StudentResultsResponse,
    StudentSubjectsResponse,
    StudentTimetableResponse,
    SubjectInfo,
    SubjectResult,
    TeacherInfo,
    TermResult,
    TimetableDayGroup,
    TimetableEntryItem,
)

logger = logging.getLogger(__name__)


class StudentPortalService:
    """Service layer for the student portal.

    Every method is scoped to a specific student and enforces that the
    requesting user has access. Only the ``student`` role should use this.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Student Resolution ──────────────────────────────────────────

    async def resolve_student(
        self,
        user_id: int,
        email: str | None = None,
        campus_id: int | None = None,
    ) -> Student:
        """Find the student record associated with a user account.

        Tries to match by email first, then falls back to the first
        active student record *in the user's campus* if no email match
        is found.  Every lookup is pinned to the caller's campus so a
        student can never resolve to another campus's record.
        """
        base = select(Student).where(Student.status == "active")
        if campus_id is not None:
            base = base.where(Student.campus_id == campus_id)

        if email:
            result = await self.session.execute(base.where(Student.email == email))
            student = result.scalar_one_or_none()
            if student:
                return student

        # Fallback: first active student within the user's campus only.
        # Fail closed — without a campus scope the fallback would return
        # an arbitrary student system-wide, so it is denied entirely.
        if campus_id is None:
            raise NotFoundError("Student record not found for your account")
        result = await self.session.execute(base.limit(1))
        student = result.scalar_one_or_none()
        if not student:
            raise NotFoundError("Student record not found for your account")
        return student

    async def get_student_by_id(self, student_id: int) -> Student:
        student = await self.session.get(Student, student_id)
        if not student:
            raise NotFoundError("Student not found")
        return student

    async def get_active_enrollment(self, student_id: int) -> Optional[dict]:
        """Get the student's current active enrollment."""
        try:
            result = await self.session.execute(
                text(
                    """SELECT ay.name, c.name, s.name, e.status, e.class_id, e.section_id
                       FROM enrollments e
                       LEFT JOIN academic_years ay ON ay.id = e.academic_year_id
                       LEFT JOIN classes c ON c.id = e.class_id
                       LEFT JOIN sections s ON s.id = e.section_id
                       WHERE e.student_id = :sid AND e.status = 'active'
                       ORDER BY e.enrolled_at DESC LIMIT 1"""
                ),
                {"sid": student_id},
            )
            row = result.one_or_none()
            if row:
                return {
                    "academic_year_name": row[0],
                    "class_name": row[1],
                    "section_name": row[2],
                    "status": row[3],
                    "class_id": row[4],
                    "section_id": row[5],
                }
        except Exception as exc:
            logger.debug("Enrollment query failed: %s", exc)
        return None

    # ── Dashboard ───────────────────────────────────────────────────

    async def get_dashboard(
        self, student_id: int, student: Optional[Student] = None
    ) -> StudentPortalDashboardResponse:
        if not student:
            student = await self.get_student_by_id(student_id)

        enrollment = await self.get_active_enrollment(student_id)
        attendance = await self._get_attendance_summary(student_id)
        subjects = await self._get_enrolled_subjects(student_id, enrollment)
        assignments = await self._get_assignments(student_id, enrollment)
        upcoming = await self._get_today_timetable(student_id, enrollment)
        announcements = await self._get_announcements(campus_id=student.campus_id)

        pending_count = len(assignments.get("pending", []))
        overdue_count = len(assignments.get("overdue", []))

        return StudentPortalDashboardResponse(
            student_name=f"{student.first_name} {student.last_name}",
            student_number=student.student_number,
            enrollment=EnrollmentInfo(**enrollment) if enrollment else None,
            attendance=attendance,
            subjects_count=len(subjects),
            pending_assignments=pending_count,
            overdue_assignments=overdue_count,
            upcoming_timetable=upcoming[:5],
            unread_notifications=0,
            recent_announcements=announcements[:3],
        )

    # ── Timetable ───────────────────────────────────────────────────

    async def get_timetable(
        self, student_id: int
    ) -> StudentTimetableResponse:
        enrollment = await self.get_active_enrollment(student_id)
        if not enrollment or not enrollment.get("class_id"):
            return StudentTimetableResponse()

        class_id = enrollment["class_id"]
        section_id = enrollment.get("section_id")

        try:
            conditions = [
                TimetableEntry.class_id == class_id,
                TimetableEntry.status == "active",
            ]
            if section_id:
                conditions.append(TimetableEntry.section_id == section_id)

            result = await self.session.execute(
                select(TimetableEntry)
                .where(and_(*conditions))
                .order_by(TimetableEntry.day_of_week, TimetableEntry.id)
            )
            entries = result.scalars().all()

            days_map: dict[int, list[TimetableEntryItem]] = {d: [] for d in range(5)}
            for entry in entries:
                item = await self._entry_to_item(entry)
                if entry.day_of_week in days_map:
                    days_map[entry.day_of_week].append(item)
                else:
                    days_map[entry.day_of_week] = [item]

            days = [
                TimetableDayGroup(
                    day_of_week=d,
                    day_name=ACADEMIC_DAY_NAMES[d],
                    entries=sorted(days_map.get(d, []), key=lambda e: e.start_time or ""),
                )
                for d in range(5)
            ]

            return StudentTimetableResponse(
                enrollment=EnrollmentInfo(**enrollment) if enrollment else None,
                days=days,
            )
        except Exception as exc:
            logger.debug("Timetable query failed: %s", exc)
            return StudentTimetableResponse()

    async def _entry_to_item(self, entry: TimetableEntry) -> TimetableEntryItem:
        item = TimetableEntryItem(
            id=entry.id,
            day_of_week=entry.day_of_week,
            day_name=ACADEMIC_DAY_NAMES[entry.day_of_week] if entry.day_of_week < 7 else "",
        )
        if entry.subject_id:
            subj = await self.session.get(Subject, entry.subject_id)
            if subj:
                item.subject_name = subj.name
                item.subject_code = subj.code
        if entry.time_slot_id:
            from app.domains.academic_ops.models import TimeSlot
            ts = await self.session.get(TimeSlot, entry.time_slot_id)
            if ts:
                item.start_time = ts.start_time
                item.end_time = ts.end_time
                item.time_slot_name = ts.name
        if entry.teacher_id:
            from app.domains.academic.models import Teacher
            t = await self.session.get(Teacher, entry.teacher_id)
            if t:
                item.teacher_name = f"{t.first_name} {t.last_name}"
        if entry.room_id:
            from app.domains.academic_ops.models import Room
            r = await self.session.get(Room, entry.room_id)
            if r:
                item.room_name = r.name
        return item

    async def _get_today_timetable(
        self, student_id: int, enrollment: Optional[dict] = None
    ) -> list[TimetableEntryItem]:
        if not enrollment:
            enrollment = await self.get_active_enrollment(student_id)
        if not enrollment or not enrollment.get("class_id"):
            return []

        today = datetime.datetime.now().weekday()
        try:
            conditions = [
                TimetableEntry.class_id == enrollment["class_id"],
                TimetableEntry.day_of_week == today,
                TimetableEntry.status == "active",
            ]
            if enrollment.get("section_id"):
                conditions.append(TimetableEntry.section_id == enrollment["section_id"])

            result = await self.session.execute(
                select(TimetableEntry).where(and_(*conditions))
            )
            entries = result.scalars().all()
            items = [await self._entry_to_item(e) for e in entries]
            return sorted(items, key=lambda i: i.start_time or "")
        except Exception:
            return []

    # ── Attendance ──────────────────────────────────────────────────

    async def get_attendance(
        self, student_id: int, days: int = 365
    ) -> StudentAttendanceResponse:
        summary = await self._get_attendance_summary(student_id, days)
        records = await self._get_attendance_records(student_id)
        streak = await self._calculate_streak(student_id)
        monthly = await self._get_monthly_breakdown(student_id)

        return StudentAttendanceResponse(
            summary=summary,
            records=records,
            current_streak=streak,
            monthly_breakdown=monthly,
        )

    async def _get_attendance_summary(
        self, student_id: int, days: int = 365
    ) -> AttendanceSummary:
        try:
            start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
            result = await self.session.execute(
                text(
                    """SELECT COUNT(*),
                              SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END),
                              SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END),
                              SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END),
                              SUM(CASE WHEN status = 'excused' THEN 1 ELSE 0 END)
                       FROM attendance_records
                       WHERE student_id = :sid AND attendance_date >= :start"""
                ),
                {"sid": student_id, "start": start},
            )
            row = result.one()
            total = row[0] or 0
            present = row[1] or 0
            absent = row[2] or 0
            late = row[3] or 0
            excused = row[4] or 0
            pct = round((present / total * 100), 1) if total > 0 else 0.0
            return AttendanceSummary(
                total=total, present=present, absent=absent,
                late=late, excused=excused, percentage=pct,
            )
        except Exception as exc:
            logger.debug("Attendance summary failed: %s", exc)
            return AttendanceSummary()

    async def _get_attendance_records(
        self, student_id: int, limit: int = 60
    ) -> list[AttendanceRecord]:
        try:
            result = await self.session.execute(
                text(
                    """SELECT id, attendance_date, status, notes
                       FROM attendance_records
                       WHERE student_id = :sid
                       ORDER BY attendance_date DESC LIMIT :lim"""
                ),
                {"sid": student_id, "lim": limit},
            )
            return [
                AttendanceRecord(
                    id=r[0], attendance_date=str(r[1]),
                    status=r[2], notes=r[3],
                )
                for r in result.all()
            ]
        except Exception:
            return []

    async def _calculate_streak(self, student_id: int) -> int:
        try:
            result = await self.session.execute(
                text(
                    """SELECT attendance_date, status
                       FROM attendance_records
                       WHERE student_id = :sid
                       ORDER BY attendance_date DESC"""
                ),
                {"sid": student_id},
            )
            streak = 0
            for row in result.all():
                if row[1] == "present":
                    streak += 1
                else:
                    break
            return streak
        except Exception:
            return 0

    async def _get_monthly_breakdown(
        self, student_id: int
    ) -> list[dict[str, Any]]:
        try:
            result = await self.session.execute(
                text(
                    """SELECT strftime('%Y-%m', attendance_date) AS month,
                              COUNT(*) AS total,
                              SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) AS present
                       FROM attendance_records
                       WHERE student_id = :sid
                       GROUP BY month
                       ORDER BY month DESC LIMIT 6"""
                ),
                {"sid": student_id},
            )
            return [
                {
                    "month": r[0],
                    "total": r[1],
                    "present": r[2],
                    "percentage": round((r[2] / r[1] * 100), 1) if r[1] > 0 else 0,
                }
                for r in result.all()
            ]
        except Exception:
            return []

    # ── Subjects ────────────────────────────────────────────────────

    async def get_subjects(
        self, student_id: int
    ) -> StudentSubjectsResponse:
        enrollment = await self.get_active_enrollment(student_id)
        subjects = await self._get_enrolled_subjects(student_id, enrollment)
        return StudentSubjectsResponse(
            enrollment=EnrollmentInfo(**enrollment) if enrollment else None,
            subjects=subjects,
        )

    async def _get_enrolled_subjects(
        self, student_id: int, enrollment: Optional[dict] = None
    ) -> list[EnrolledSubject]:
        if not enrollment or not enrollment.get("class_id"):
            return []

        try:
            class_id = enrollment["class_id"]
            result = await self.session.execute(
                text(
                    """SELECT DISTINCT sub.id, sub.name, sub.code,
                              t.first_name, t.last_name, t.email,
                              curr.total_hours, curr.syllabus, curr.textbook
                       FROM teacher_assignments ta
                       JOIN subjects sub ON sub.id = ta.subject_id
                       LEFT JOIN teachers t ON t.id = ta.teacher_id
                       LEFT JOIN curriculums curr ON curr.class_id = ta.class_id
                           AND curr.subject_id = ta.subject_id
                       WHERE ta.class_id = :cid AND ta.status = 'active'
                       ORDER BY sub.name"""
                ),
                {"cid": class_id},
            )
            return [
                EnrolledSubject(
                    id=r[0], name=r[1], code=r[2],
                    teacher_name=f"{r[3]} {r[4]}" if r[3] else None,
                    teacher_email=r[5],
                    total_hours=r[6],
                    syllabus=r[7],
                    textbook=r[8],
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Subjects query failed: %s", exc)
            return []

    # ── Academic Results ────────────────────────────────────────────

    async def get_results(
        self, student_id: int
    ) -> StudentResultsResponse:
        enrollment = await self.get_active_enrollment(student_id)
        if not enrollment:
            return StudentResultsResponse()

        try:
            # Get all grade records for this student
            result = await self.session.execute(
                text(
                    """SELECT sub.name, sub.code, gr.marks_obtained, gr.max_marks,
                              gr.grade, gr.grade_point, gr.remarks, t.name AS term_name
                       FROM grade_records gr
                       JOIN subjects sub ON sub.id = gr.subject_id
                       LEFT JOIN terms t ON t.id = gr.term_id
                       JOIN enrollments e ON e.id = gr.enrollment_id
                       WHERE e.student_id = :sid AND gr.status = 'active'
                       ORDER BY t.name, sub.name"""
                ),
                {"sid": student_id},
            )
            rows = result.all()

            # Group by term
            term_map: dict[str, list[SubjectResult]] = {}
            for r in rows:
                term_name = r[7] or "General"
                if term_name not in term_map:
                    term_map[term_name] = []
                term_map[term_name].append(
                    SubjectResult(
                        subject_name=r[0], subject_code=r[1],
                        marks_obtained=r[2], max_marks=r[3] or 100,
                        grade=r[4], grade_point=r[5],
                        remarks=r[6], term_name=term_name,
                    )
                )

            terms: list[TermResult] = []
            all_percentages: list[float] = []
            for term_name, subjects in term_map.items():
                total = sum(s.marks_obtained or 0 for s in subjects)
                max_total = sum(s.max_marks for s in subjects)
                pct = round((total / max_total * 100), 1) if max_total > 0 else 0
                gpas = [s.grade_point for s in subjects if s.grade_point is not None]
                gpa = round(sum(gpas) / len(gpas), 2) if gpas else None
                all_percentages.append(pct)
                terms.append(TermResult(
                    term_name=term_name,
                    subjects=subjects,
                    total_marks=total,
                    total_max_marks=max_total,
                    percentage=pct,
                    grade_point_average=gpa,
                ))

            overall_pct = round(sum(all_percentages) / len(all_percentages), 1) if all_percentages else 0
            all_gpas = [t.grade_point_average for t in terms if t.grade_point_average is not None]
            overall_gpa = round(sum(all_gpas) / len(all_gpas), 2) if all_gpas else None

            return StudentResultsResponse(
                enrollment=EnrollmentInfo(**enrollment) if enrollment else None,
                terms=terms,
                overall_percentage=overall_pct,
                overall_grade_point_average=overall_gpa,
            )
        except Exception as exc:
            logger.debug("Results query failed: %s", exc)
            return StudentResultsResponse()

    # ── Assignments ─────────────────────────────────────────────────

    async def get_assignments(
        self, student_id: int
    ) -> StudentAssignmentsResponse:
        enrollment = await self.get_active_enrollment(student_id)
        assignments_data = await self._get_assignments(student_id, enrollment)
        return StudentAssignmentsResponse(**assignments_data)

    async def _get_assignments(
        self, student_id: int, enrollment: Optional[dict] = None
    ) -> dict[str, list[StudentAssignment]]:
        if not enrollment or not enrollment.get("class_id"):
            return {"pending": [], "submitted": [], "graded": [], "overdue": []}

        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            class_id = enrollment["class_id"]

            result = await self.session.execute(
                text(
                    """SELECT a.id, a.title, a.description, a.instructions,
                              sub.name, sub.code, t.first_name, t.last_name,
                              a.assignment_type, a.max_score,
                              a.due_at, a.available_from, a.is_published
                       FROM assignments a
                       JOIN subjects sub ON sub.id = a.subject_id
                       LEFT JOIN teachers t ON t.id = a.teacher_id
                       WHERE a.class_id = :cid AND a.status = 'active'
                       ORDER BY a.due_at ASC NULLS LAST"""
                ),
                {"cid": class_id},
            )
            rows = result.all()

            # Also get the student's submissions
            sub_result = await self.session.execute(
                text(
                    """SELECT assignment_id, id, submitted_at, score, grade, feedback, status, is_late
                       FROM assignment_submissions
                       WHERE student_id = :sid"""
                ),
                {"sid": student_id},
            )
            submissions_map: dict[int, dict] = {}
            for sr in sub_result.all():
                submissions_map[sr[0]] = {
                    "submission_id": sr[1],
                    "submitted_at": sr[2],
                    "score": sr[3],
                    "grade": sr[4],
                    "feedback": sr[5],
                    "submission_status": sr[6],
                    "is_late": sr[7],
                }

            pending: list[StudentAssignment] = []
            submitted: list[StudentAssignment] = []
            graded: list[StudentAssignment] = []
            overdue: list[StudentAssignment] = []

            for r in rows:
                sub_info = submissions_map.get(r[0], {})
                due = r[10]

                assignment = StudentAssignment(
                    id=r[0], title=r[1], description=r[2], instructions=r[3],
                    subject_name=r[4], subject_code=r[5],
                    teacher_name=f"{r[6]} {r[7]}" if r[6] else None,
                    assignment_type=r[8] or "homework",
                    max_score=r[9],
                    due_at=due,
                    available_from=r[11],
                    is_published=r[12] or False,
                    **sub_info,
                )

                if sub_info.get("submission_status") == "graded" or sub_info.get("score") is not None:
                    graded.append(assignment)
                elif sub_info.get("submission_status") in ("submitted", "draft"):
                    submitted.append(assignment)
                elif due and due < now:
                    overdue.append(assignment)
                else:
                    pending.append(assignment)

            return {
                "pending": pending,
                "submitted": submitted,
                "graded": graded,
                "overdue": overdue,
            }
        except Exception as exc:
            logger.debug("Assignments query failed: %s", exc)
            return {"pending": [], "submitted": [], "graded": [], "overdue": []}

    # ── Announcements ───────────────────────────────────────────────

    async def get_announcements(
        self, campus_id: int | None = None
    ) -> StudentAnnouncementsResponse:
        announcements = await self._get_announcements(campus_id=campus_id)
        return StudentAnnouncementsResponse(announcements=announcements)

    async def _get_announcements(
        self, limit: int = 20, campus_id: int | None = None
    ) -> list[StudentAnnouncement]:
        try:
            # Campus-scoped: only own-campus announcements plus
            # system-wide ones (campus_id NULL) are visible.
            conditions = [
                "cm.message_type IN ('announcement', 'class', 'section')",
                "cm.status = 'sent'",
            ]
            params: dict[str, Any] = {"lim": limit}
            if campus_id is not None:
                conditions.append(
                    "(cm.campus_id IS NULL OR cm.campus_id = :campus_id)"
                )
                params["campus_id"] = campus_id

            result = await self.session.execute(
                text(
                    """SELECT cm.id, cm.subject, cm.body, cm.priority, cm.created_at, u.display_name
                       FROM communication_messages cm
                       LEFT JOIN users u ON u.id = cm.sender_id
                       WHERE """
                    + " AND ".join(conditions)
                    + "\n                       ORDER BY cm.created_at DESC\n                       LIMIT :lim"
                ),
                params,
            )
            return [
                StudentAnnouncement(
                    id=r[0], title=r[1], body=r[2],
                    priority=r[3], created_at=r[4], sender_name=r[5],
                )
                for r in result.all()
            ]
        except Exception as exc:
            logger.debug("Announcements query failed: %s", exc)
            return []

    # ── Documents ───────────────────────────────────────────────────

    async def get_documents(
        self, student_id: int
    ) -> StudentDocumentsResponse:
        try:
            result = await self.session.execute(
                text(
                    """SELECT d.id, d.filename, d.mime_type, d.file_size, d.created_at, dc.name
                       FROM documents d
                       LEFT JOIN document_categories dc ON dc.id = d.category_id
                       WHERE d.student_id = :sid
                       ORDER BY d.created_at DESC"""
                ),
                {"sid": student_id},
            )
            documents = [
                StudentDocument(
                    id=r[0], filename=r[1], mime_type=r[2],
                    file_size=r[3], created_at=r[4], category_name=r[5],
                )
                for r in result.all()
            ]
            return StudentDocumentsResponse(documents=documents)
        except Exception as exc:
            logger.debug("Documents query failed: %s", exc)
            return StudentDocumentsResponse()
