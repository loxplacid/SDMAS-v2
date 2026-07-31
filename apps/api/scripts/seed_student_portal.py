"""
SDMAS student portal seed script.

Populates sample data for the student portal: timetable entries, grade
records, assignments + submissions, additional attendance records, rooms,
time slots, teacher assignments, and enrollments.

Usage:
    uv run python -m scripts.seed_student_portal

Requires that the main ``seed.py`` has already been run so that base data
(academic year, classes, subjects, teachers, students) exist.
"""

import asyncio
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domains.academic.models import (
    AcademicYear,
    Class,
    Enrollment,
    Section,
    Subject,
    Teacher,
    TeacherAssignment,
    Term,
)
from app.domains.academic_ops.models import (
    GradeRecord,
    Room,
    TimeSlot,
    TimetableEntry,
)
from app.domains.attendance.models import AttendanceRecord
from app.domains.student.models import Student
from app.domains.student_portal.models import Assignment, AssignmentSubmission
from app.infrastructure.database import create_engine_and_factory


# ═══════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════

faker_random = random.Random(42)  # deterministic


def pick[T](items: list[T]) -> T:
    return faker_random.choice(items)


def rand_int(lo: int, hi: int) -> int:
    return faker_random.randint(lo, hi)


def maybe(prob: float = 0.5) -> bool:
    return faker_random.random() < prob


async def get_or_none(session: AsyncSession, model, **filters):
    """Fetch first matching record or None."""
    stmt = select(model)
    for attr, val in filters.items():
        stmt = stmt.where(getattr(model, attr) == val)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ═══════════════════════════════════════════════
# 1. Rooms
# ═══════════════════════════════════════════════

ROOMS = [
    ("Room 101", "R101", "Main Building", "1", 35, "classroom"),
    ("Room 102", "R102", "Main Building", "1", 30, "classroom"),
    ("Room 201", "R201", "Main Building", "2", 40, "classroom"),
    ("Science Lab", "LAB1", "Science Wing", "1", 25, "laboratory"),
    ("Computer Lab", "LAB2", "Science Wing", "1", 30, "laboratory"),
    ("Auditorium", "AUDI", "Main Building", "G", 200, "auditorium"),
]


async def seed_rooms(session: AsyncSession) -> dict[str, int]:
    """Create rooms and return {code: id} mapping."""
    existing = await session.execute(select(Room))
    if existing.scalars().first():
        print("  >> Rooms already exist, skipping")
        result = await session.execute(select(Room))
        return {r.code: r.id for r in result.scalars().all()}

    room_ids: dict[str, int] = {}
    for name, code, building, floor, capacity, room_type in ROOMS:
        room = Room(
            name=name, code=code, building=building, floor=floor,
            capacity=capacity, room_type=room_type, status="active",
        )
        session.add(room)
        await session.flush()
        room_ids[code] = room.id
    print(f"  [OK] {len(room_ids)} rooms created")
    return room_ids


# ═══════════════════════════════════════════════
# 2. Time Slots
# ═══════════════════════════════════════════════

# (name, day_of_week, start, end, slot_type)
TIME_SLOTS: list[tuple[str, int, str, str, str]] = [
    # Monday (0)
    ("Mon Period 1", 0, "08:00", "08:45", "regular"),
    ("Mon Period 2", 0, "08:50", "09:35", "regular"),
    ("Mon Break",    0, "09:35", "09:55", "break"),
    ("Mon Period 3", 0, "09:55", "10:40", "regular"),
    ("Mon Period 4", 0, "10:45", "11:30", "regular"),
    ("Mon Period 5", 0, "11:35", "12:20", "regular"),
    # Tuesday (1)
    ("Tue Period 1", 1, "08:00", "08:45", "regular"),
    ("Tue Period 2", 1, "08:50", "09:35", "regular"),
    ("Tue Break",    1, "09:35", "09:55", "break"),
    ("Tue Period 3", 1, "09:55", "10:40", "regular"),
    ("Tue Period 4", 1, "10:45", "11:30", "regular"),
    ("Tue Period 5", 1, "11:35", "12:20", "regular"),
    # Wednesday (2)
    ("Wed Period 1", 2, "08:00", "08:45", "regular"),
    ("Wed Period 2", 2, "08:50", "09:35", "regular"),
    ("Wed Break",    2, "09:35", "09:55", "break"),
    ("Wed Period 3", 2, "09:55", "10:40", "regular"),
    ("Wed Period 4", 2, "10:45", "11:30", "regular"),
    ("Wed Lab",      2, "11:35", "13:00", "lab"),
    # Thursday (3)
    ("Thu Period 1", 3, "08:00", "08:45", "regular"),
    ("Thu Period 2", 3, "08:50", "09:35", "regular"),
    ("Thu Break",    3, "09:35", "09:55", "break"),
    ("Thu Period 3", 3, "09:55", "10:40", "regular"),
    ("Thu Period 4", 3, "10:45", "11:30", "regular"),
    ("Thu Period 5", 3, "11:35", "12:20", "regular"),
    # Friday (4)
    ("Fri Period 1", 4, "08:00", "08:45", "regular"),
    ("Fri Period 2", 4, "08:50", "09:35", "regular"),
    ("Fri Break",    4, "09:35", "09:55", "break"),
    ("Fri Period 3", 4, "09:55", "10:40", "regular"),
    ("Fri Period 4", 4, "10:45", "11:30", "regular"),
    ("Fri Assembly", 4, "11:35", "12:20", "assembly"),
]


async def seed_time_slots(session: AsyncSession) -> dict[str, int]:
    """Create time slots and return {name: id} mapping."""
    existing = await session.execute(select(TimeSlot))
    if existing.scalars().first():
        print("  >> Time slots already exist, skipping")
        result = await session.execute(select(TimeSlot))
        return {r.name: r.id for r in result.scalars().all()}

    slot_ids: dict[str, int] = {}
    for name, dow, start, end, slot_type in TIME_SLOTS:
        slot = TimeSlot(
            name=name, day_of_week=dow,
            start_time=start, end_time=end,
            slot_type=slot_type, status="active",
        )
        session.add(slot)
        await session.flush()
        slot_ids[name] = slot.id
    print(f"  [OK] {len(slot_ids)} time slots created")
    return slot_ids


# ═══════════════════════════════════════════════
# 3. Teacher Assignments
# ═══════════════════════════════════════════════

TEACHER_SUBJECT_MAP: list[tuple[str, str]] = [
    ("Alice", "Mathematics"),     # Teacher T001
    ("Alice", "History"),         # Teacher T001 also teaches History
    ("Bob", "English"),           # Teacher T002
    ("Bob", "Science"),           # Teacher T002 also teaches Science
]


async def seed_teacher_assignments(
    session: AsyncSession,
    class_ids: dict[str, int],
    subject_ids: dict[str, int],
    teacher_ids: dict[str, int],
) -> list[dict]:
    """Create teacher-class-subject assignments."""
    existing = await session.execute(select(TeacherAssignment).limit(1))
    if existing.scalar_one_or_none():
        print("  >> Teacher assignments already exist, skipping")
        return []

    assignments_created = []
    for teacher_name, subject_name in TEACHER_SUBJECT_MAP:
        tid = teacher_ids[teacher_name]
        subj_id = subject_ids[subject_name]
        for class_key, cid in class_ids.items():
            # Check not duplicate
            dup = await get_or_none(
                session, TeacherAssignment,
                teacher_id=tid, class_id=cid, subject_id=subj_id,
            )
            if dup:
                continue
            ta = TeacherAssignment(
                teacher_id=tid, class_id=cid,
                subject_id=subj_id, status="active",
            )
            session.add(ta)
            await session.flush()
            assignments_created.append({
                "teacher_name": teacher_name,
                "subject": subject_name,
                "class_key": class_key,
            })
    print(f"  [OK] {len(assignments_created)} teacher assignments created")
    return assignments_created


# ═══════════════════════════════════════════════
# 4. Enrollments
# ═══════════════════════════════════════════════


async def seed_enrollments(
    session: AsyncSession,
    year_id: int,
    class_ids: dict[str, int],
    section_ids: dict[str, int],
    student_ids: list[int],
) -> list[int]:
    """Enroll students into classes/sections. Returns enrollment IDs."""
    existing = await session.execute(
        select(Enrollment).where(Enrollment.academic_year_id == year_id).limit(1)
    )
    if existing.scalar_one_or_none():
        print("  >> Enrollments already exist for this year, skipping")
        result = await session.execute(
            select(Enrollment).where(Enrollment.academic_year_id == year_id)
        )
        return [r.id for r in result.scalars().all()]

    enrollment_ids: list[int] = []
    section_keys = list(section_ids.keys())

    for sid in student_ids:
        # Assign each student to Grade 9, Section A or B randomly
        sec_key = "grade9_a" if student_ids.index(sid) % 2 == 0 else "grade9_b"
        enrollment = Enrollment(
            student_id=sid,
            academic_year_id=year_id,
            class_id=class_ids["grade9"],
            section_id=section_ids[sec_key],
            status="active",
        )
        session.add(enrollment)
        await session.flush()
        enrollment_ids.append(enrollment.id)

    print(f"  [OK] {len(enrollment_ids)} enrollments created")
    return enrollment_ids


# ═══════════════════════════════════════════════
# 5. Timetable Entries
# ═══════════════════════════════════════════════

TIMETABLE_MAP: list[tuple[int, str, str, str, str]] = [
    # (day_of_week, time_slot_name, subject_name, teacher_name, room_code)
    # Monday
    (0, "Mon Period 1", "Mathematics", "Alice", "R101"),
    (0, "Mon Period 2", "English",     "Bob",   "R101"),
    (0, "Mon Period 3", "Science",     "Bob",   "LAB1"),
    (0, "Mon Period 4", "History",     "Alice", "R102"),
    (0, "Mon Period 5", "Mathematics", "Alice", "R101"),
    # Tuesday
    (1, "Tue Period 1", "English",     "Bob",   "R101"),
    (1, "Tue Period 2", "Mathematics", "Alice", "R101"),
    (1, "Tue Period 3", "Science",     "Bob",   "LAB1"),
    (1, "Tue Period 4", "History",     "Alice", "R102"),
    (1, "Tue Period 5", "English",     "Bob",   "R101"),
    # Wednesday
    (2, "Wed Period 1", "Mathematics", "Alice", "R101"),
    (2, "Wed Period 2", "History",     "Alice", "R102"),
    (2, "Wed Period 3", "Science",     "Bob",   "R201"),
    (2, "Wed Period 4", "English",     "Bob",   "R101"),
    (2, "Wed Lab",      "Science",     "Bob",   "LAB2"),
    # Thursday
    (3, "Thu Period 1", "Science",     "Bob",   "R201"),
    (3, "Thu Period 2", "Mathematics", "Alice", "R101"),
    (3, "Thu Period 3", "English",     "Bob",   "R101"),
    (3, "Thu Period 4", "History",     "Alice", "R102"),
    (3, "Thu Period 5", "Mathematics", "Alice", "R101"),
    # Friday
    (4, "Fri Period 1", "English",     "Bob",   "R101"),
    (4, "Fri Period 2", "Science",     "Bob",   "R201"),
    (4, "Fri Period 3", "Mathematics", "Alice", "R101"),
    (4, "Fri Period 4", "History",     "Alice", "R102"),
    (4, "Fri Assembly", "History",     "Alice", "AUDI"),
]


async def seed_timetable(
    session: AsyncSession,
    year_id: int,
    term_ids: list[int],
    class_ids: dict[str, int],
    section_ids: dict[str, int],
    subject_ids: dict[str, int],
    teacher_ids: dict[str, int],
    time_slot_ids: dict[str, int],
    room_ids: dict[str, int],
) -> None:
    """Create timetable entries for Grade 9 Section A."""
    existing = await session.execute(
        select(TimetableEntry).where(
            TimetableEntry.academic_year_id == year_id,
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        print("  >> Timetable entries already exist, skipping")
        return

    count = 0
    term_id = term_ids[0] if term_ids else None
    class_id = class_ids["grade9"]
    section_id = section_ids["grade9_a"]

    for dow, slot_name, subj_name, teacher_name, room_code in TIMETABLE_MAP:
        entry = TimetableEntry(
            academic_year_id=year_id,
            term_id=term_id,
            class_id=class_id,
            section_id=section_id,
            subject_id=subject_ids[subj_name],
            teacher_id=teacher_ids[teacher_name],
            room_id=room_ids.get(room_code),
            time_slot_id=time_slot_ids[slot_name],
            day_of_week=dow,
            status="active",
        )
        session.add(entry)
        await session.flush()
        count += 1

    print(f"  [OK] {count} timetable entries created for Grade 9 Section A")


# ═══════════════════════════════════════════════
# 6. Grade Records (academic results)
# ═══════════════════════════════════════════════


async def seed_grade_records(
    session: AsyncSession,
    enrollment_ids: list[int],
    subject_ids: dict[str, int],
    term_ids: list[int],
    student_ids: list[int],
) -> None:
    """Create sample grade records for students across terms/subjects."""
    existing = await session.execute(
        select(GradeRecord).where(
            GradeRecord.enrollment_id.in_(enrollment_ids)
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        print("  >> Grade records already exist, skipping")
        return

    subjects_list = list(subject_ids.items())  # [(name, id), ...]
    count = 0

    for term_id in term_ids:
        # Map each enrollment to a student_id
        for eid, sid in zip(enrollment_ids, student_ids):
            for subj_name, subj_id in subjects_list:
                marks = rand_int(30, 100)
                max_m = 100
                grade, gp = _auto_grade(marks, max_m)
                gr = GradeRecord(
                    enrollment_id=eid,
                    subject_id=subj_id,
                    marks_obtained=marks,
                    max_marks=max_m,
                    grade=grade,
                    grade_point=gp,
                    term_id=term_id,
                    status="active",
                )
                session.add(gr)
                await session.flush()
                count += 1

    print(f"  [OK] {count} grade records created across {len(term_ids)} term(s)")


def _auto_grade(marks: float, max_marks: int) -> tuple[str, float]:
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


# ═══════════════════════════════════════════════
# 7. Assignments + Submissions
# ═══════════════════════════════════════════════

# (title, subject_name, assignment_type, max_score, days_from_now_for_due)
ASSIGNMENT_DEFS: list[tuple[str, str, str, int, int]] = [
    # Pending assignments (due in the future)
    ("Algebra Problem Set",   "Mathematics", "homework",  100,  7),
    ("Essay: The Renaissance", "History",    "homework",  100, 10),
    ("Lab Report: Acids",     "Science",     "lab_report", 50,  5),
    ("Book Review",           "English",     "homework",  100, 14),
    ("Geometry Worksheet",    "Mathematics", "homework",   50,  3),
    # Overdue assignments (due in the past)
    ("Poetry Analysis",       "English",     "homework",  100, -5),
    ("History Quiz Prep",     "History",     "quiz",       25, -3),
    ("Science Homework Ch 4", "Science",     "homework",   75, -7),
    ("Math Test Revision",    "Mathematics", "homework",  100, -2),
]


async def seed_assignments(
    session: AsyncSession,
    year_id: int,
    class_ids: dict[str, int],
    section_ids: dict[str, int],
    subject_ids: dict[str, int],
    teacher_ids: dict[str, int],
    term_ids: list[int],
) -> list[int]:
    """Create sample assignments and return their IDs."""
    existing = await session.execute(
        select(Assignment).where(
            Assignment.academic_year_id == year_id
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        print("  >> Assignments already exist, skipping")
        result = await session.execute(
            select(Assignment.id).where(
                Assignment.academic_year_id == year_id
            )
        )
        return [r[0] for r in result.all()]

    now = datetime.now(timezone.utc)
    class_id = class_ids["grade9"]
    section_id = section_ids["grade9_a"]
    term_id = term_ids[0] if term_ids else None

    assignment_ids: list[int] = []

    for title, subj_name, a_type, max_score, days_offset in ASSIGNMENT_DEFS:
        due = now + timedelta(days=days_offset)
        is_pending = days_offset > 0

        assignment = Assignment(
            title=title,
            description=f"Complete the {title.lower()} and submit before the due date.",
            instructions=f"1. Read the instructions carefully\n2. Complete all questions\n3. Submit via the portal\n\nGood luck!",
            subject_id=subject_ids[subj_name],
            class_id=class_id,
            section_id=section_id,
            teacher_id=teacher_ids.get("Alice" if subj_name in ("Mathematics", "History") else "Bob"),
            academic_year_id=year_id,
            term_id=term_id,
            assignment_type=a_type,
            max_score=max_score,
            due_at=due,
            available_from=now - timedelta(days=3),
            is_published=True,
            allow_late_submission=True,
            status="active",
        )
        session.add(assignment)
        await session.flush()
        assignment_ids.append(assignment.id)

    print(f"  [OK] {len(assignment_ids)} assignments created")
    return assignment_ids


async def seed_submissions(
    session: AsyncSession,
    assignment_ids: list[int],
    student_ids: list[int],
) -> None:
    """Create sample submissions for some assignments."""
    existing = await session.execute(
        select(AssignmentSubmission).limit(1)
    )
    if existing.scalar_one_or_none():
        print("  >> Submissions already exist, skipping")
        return

    now = datetime.now(timezone.utc)
    count = 0

    # Map: assignment index in ASSIGNMENT_DEFS -> submission pattern
    # Indices 5, 6, 7, 8 are overdue — create submissions for some
    submission_map = {
        5: {0: (85, "B+"), 1: (92, "A")},   # Poetry Analysis
        6: {2: (18, "B-")},                    # History Quiz Prep
        7: {0: (60, "C+"), 3: (45, "D")},     # Science Homework
        8: {1: (78, "B+"), 4: (88, "A-")},    # Math Test Revision
    }

    for a_idx, student_scores in submission_map.items():
        if a_idx >= len(assignment_ids):
            continue
        aid = assignment_ids[a_idx]
        for s_idx, (score, grade) in student_scores.items():
            if s_idx >= len(student_ids):
                continue
            sid = student_ids[s_idx]
            is_late = a_idx in (5, 6)  # Poetry and Quiz are late

            submission = AssignmentSubmission(
                assignment_id=aid,
                student_id=sid,
                submitted_text=f"Here is my submission for assignment #{aid}.",
                score=score,
                grade=grade,
                feedback=(
                    f"Good work! Score: {score}. Keep practicing to improve further."
                    if score >= 50 else
                    f"Please revise and resubmit. Score: {score}. See me for help."
                ),
                graded_by=1,  # admin user
                graded_at=now - timedelta(hours=rand_int(1, 48)),
                is_late=is_late,
                status="graded",
            )
            session.add(submission)
            await session.flush()
            count += 1

    print(f"  [OK] {count} submissions created")


# ═══════════════════════════════════════════════
# 8. Additional Attendance Records
# ═══════════════════════════════════════════════


async def seed_attendance(
    session: AsyncSession,
    year_id: int,
    class_ids: dict[str, int],
    section_ids: dict[str, int],
    student_ids: list[int],
) -> None:
    """Add more attendance records for a fuller picture."""
    existing = await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.academic_year_id == year_id
        ).limit(1)
    )
    # We always add more records if fewer than 60 records exist
    result = await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.academic_year_id == year_id,
        )
    )
    existing_count = len(result.scalars().all())
    if existing_count >= 60:
        print(f"  >> Attendance records already exist ({existing_count}), skipping")
        return

    status_weights = ["present"] * 70 + ["absent"] * 10 + ["late"] * 12 + ["excused"] * 8
    class_id = class_ids["grade9"]
    section_id = section_ids["grade9_a"]
    count = existing_count

    start_date = date(2025, 9, 1)
    for day_offset in range(90):
        d = start_date + timedelta(days=day_offset)
        if d.weekday() >= 5:
            continue  # skip weekends
        for sid in student_ids[:3]:  # first 3 students
            dup = await get_or_none(
                session, AttendanceRecord,
                student_id=sid, attendance_date=d.isoformat(),
                section_id=section_id,
            )
            if dup:
                continue
            rec = AttendanceRecord(
                student_id=sid,
                academic_year_id=year_id,
                class_id=class_id,
                section_id=section_id,
                attendance_date=d.isoformat(),
                status=pick(status_weights),
            )
            session.add(rec)
            await session.flush()
            count += 1

    print(f"  [OK] {count} total attendance records (added {count - existing_count} new)")


# ═══════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════


async def seed() -> None:
    """Run the student portal seed pipeline."""
    engine, factory = create_engine_and_factory()

    async with factory() as session:
        # ── Resolve existing base data ─────────────────────────────
        year = await session.execute(
            select(AcademicYear).where(AcademicYear.status == "active")
        )
        year = year.scalar_one_or_none()
        if not year:
            print("[FAIL] No active academic year found. Run seed.py first.")
            return

        year_id = year.id
        print(f"  >> Using academic year: {year.name} (id={year_id})")

        # Fetch base data
        classes_q = await session.execute(
            select(Class).where(Class.academic_year_id == year_id)
        )
        classes_raw = classes_q.scalars().all()
        class_ids: dict[str, int] = {}
        for c in classes_raw:
            key = c.name.lower().replace(" ", "_")
            class_ids[key] = c.id
        print(f"  >> Found {len(class_ids)} classes: {list(class_ids.keys())}")

        sections_q = await session.execute(select(Section))
        sections_raw = sections_q.scalars().all()
        section_ids: dict[str, int] = {}
        for s in sections_raw:
            # Build predictable keys like "grade9_a" from "Grade 9 - Section A"
            parts = s.name.replace(" - ", " ").split()
            # parts = ["Grade", "9", "Section", "A"]
            key = f"{parts[0].lower()}{parts[1]}_{parts[2].lower()}{parts[3].lower()}" if len(parts) >= 4 else s.name.lower().replace(" ", "_")
            section_ids[key] = s.id

        subjects_q = await session.execute(select(Subject))
        subjects_raw = subjects_q.scalars().all()
        subject_ids: dict[str, int] = {s.name: s.id for s in subjects_raw}

        teachers_q = await session.execute(select(Teacher))
        teachers_raw = teachers_q.scalars().all()
        teacher_ids: dict[str, int] = {t.first_name: t.id for t in teachers_raw}

        terms_q = await session.execute(
            select(Term).where(Term.academic_year_id == year_id)
        )
        term_ids = [t.id for t in terms_q.scalars().all()]

        students_q = await session.execute(
            select(Student).where(Student.status == "active")
        )
        student_ids = [s.id for s in students_q.scalars().all()]

        print(f"  >> Teachers: {list(teacher_ids.keys())}")
        print(f"  >> Subjects: {list(subject_ids.keys())}")
        print(f"  >> Students: {len(student_ids)} active")
        print(f"  >> Terms: {len(term_ids)}")

        # ── Seed data ──────────────────────────────────────────
        room_ids = await seed_rooms(session)
        time_slot_ids = await seed_time_slots(session)

        if "grade9" in class_ids:
            await seed_teacher_assignments(
                session, class_ids, subject_ids, teacher_ids,
            )
            enrollment_ids = await seed_enrollments(
                session, year_id, class_ids, section_ids, student_ids,
            )
            await seed_timetable(
                session, year_id, term_ids, class_ids, section_ids,
                subject_ids, teacher_ids, time_slot_ids, room_ids,
            )
            await seed_grade_records(
                session, enrollment_ids, subject_ids, term_ids, student_ids,
            )
            assignment_ids = await seed_assignments(
                session, year_id, class_ids, section_ids,
                subject_ids, teacher_ids, term_ids,
            )
            await seed_submissions(session, assignment_ids, student_ids)
            await seed_attendance(
                session, year_id, class_ids, section_ids, student_ids,
            )
        else:
            print("[WARN] No 'grade9' class found — skipping class-specific seeds")

        await session.commit()

    await engine.dispose()
    print()
    print("[OK] Student portal seed complete!")
    print()
    print("  Seeded data includes:")
    print("    - 6 rooms, 30 time slots")
    print("    - 4 teacher assignments")
    print("    - 5 enrollments (Grade 9 Section A/B)")
    print("    - 25 timetable entries (Grade 9A full week)")
    print("    - ~80 grade records (4 subjects × 5 students × 3 terms)")
    print("    - 9 assignments (pending + overdue)")
    print("    - 8 graded submissions")
    print("    - ~270 attendance records per student")
    print()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
