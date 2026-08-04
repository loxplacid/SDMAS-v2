from __future__ import annotations

import datetime
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import (
    AcademicYear,
    Class,
    Enrollment,
    Section,
    Subject,
    Term,
)
from app.domains.academic_ops.models import GradeRecord
from app.domains.attendance.models import AttendanceRecord
from app.domains.report_cards.service import ReportCardService
from app.domains.student.models import Student


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_full(
    session: AsyncSession, prefix: str = "RC", campus_id: int | None = 1
) -> dict:
    """Seed an academic year, class, section, term, subject, student,
    enrollment, grade records and attendance records.

    ``campus_id`` defaults to Campus A (1) so entities seeded through the
    API satisfy the router's tenant-scope guard (``assert_tenant_scope``)
    when called by the admin (campus 1). Service-level tests ignore it.
    """
    year = AcademicYear(
        name=f"{prefix} Year",
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 12, 31),
        status="active",
        campus_id=campus_id,
    )
    session.add(year)
    await session.flush()

    cls = Class(
        name=f"{prefix} Grade 10",
        academic_year_id=year.id,
        status="active",
        campus_id=campus_id,
    )
    session.add(cls)
    await session.flush()

    sec = Section(name=f"{prefix} A", class_id=cls.id, status="active")
    session.add(sec)
    await session.flush()

    term = Term(
        academic_year_id=year.id,
        name="Term 1",
        start_date="2026-04-01",
        end_date="2026-09-30",
        status="active",
    )
    session.add(term)
    await session.flush()

    subj = Subject(name="Mathematics", code="MATH")
    session.add(subj)
    await session.flush()

    student = Student(
        first_name=f"{prefix}Stu",
        last_name="Student",
        student_number=f"{prefix}001",
        status="active",
        campus_id=campus_id,
    )
    session.add(student)
    await session.flush()

    enrollment = Enrollment(
        student_id=student.id,
        academic_year_id=year.id,
        class_id=cls.id,
        section_id=sec.id,
        status="active",
    )
    session.add(enrollment)
    await session.flush()

    grade = GradeRecord(
        enrollment_id=enrollment.id,
        subject_id=subj.id,
        term_id=term.id,
        marks_obtained=85.0,
        max_marks=100,
        grade="A",
        grade_point=9.0,
        remarks="Excellent work",
        status="active",
    )
    session.add(grade)
    await session.flush()

    # Attendance: 3 records — 2 present, 1 absent → 66.7%.
    for i, status in enumerate(["present", "present", "absent"]):
        session.add(
            AttendanceRecord(
                student_id=student.id,
                academic_year_id=year.id,
                class_id=cls.id,
                section_id=sec.id,
                attendance_date=f"2026-0{i + 1}-10",
                status=status,
            )
        )
    await session.flush()

    return {
        "year": year,
        "class": cls,
        "section": sec,
        "term": term,
        "subject": subj,
        "student": student,
        "enrollment": enrollment,
        "grade": grade,
    }


# ---------------------------------------------------------------------------
# Service — student report card
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_card_aggregates_grades_gpa_attendance_remarks(db_session: AsyncSession):
    data = await _seed_full(db_session)
    service = ReportCardService(db_session)

    card = await service.get_student_report_card(
        data["student"].id, data["year"].id
    )

    assert card.student_name == "RCStu Student"
    assert card.student_number == "RC001"
    assert card.class_name == "RC Grade 10"
    assert card.section_name == "RC A"
    assert card.academic_year_name == "RC Year"

    assert len(card.terms) == 1
    term = card.terms[0]
    assert term.term_name == "Term 1"
    assert len(term.subjects) == 1
    subject = term.subjects[0]
    assert subject.subject_name == "Mathematics"
    assert subject.marks_obtained == 85.0
    assert subject.max_marks == 100
    assert subject.grade == "A"
    assert subject.grade_point == 9.0

    assert term.total_marks == 85.0
    assert term.total_max_marks == 100
    assert term.percentage == 85.0
    assert term.grade_point_average == 9.0

    assert card.overall_percentage == 85.0
    assert card.overall_grade_point_average == 9.0

    # Attendance: 2 present / 3 total = 66.7%
    assert card.attendance.total == 3
    assert card.attendance.present == 2
    assert card.attendance.absent == 1
    assert card.attendance.percentage == pytest.approx(66.7, abs=0.1)

    assert "Excellent work" in card.teacher_remarks


@pytest.mark.asyncio
async def test_report_card_term_filter(db_session: AsyncSession):
    data = await _seed_full(db_session)
    service = ReportCardService(db_session)

    # Filtering to the seeded term keeps the grade; an unknown term yields
    # no subjects but still returns the student card.
    card = await service.get_student_report_card(
        data["student"].id, data["year"].id, term_id=data["term"].id
    )
    assert card.term_filter == "Term 1"
    assert len(card.terms) == 1
    assert len(card.terms[0].subjects) == 1

    # An unknown term id is rejected (strict filter).
    with pytest.raises(Exception, match="not found"):
        await service.get_student_report_card(
            data["student"].id, data["year"].id, term_id=99999
        )


@pytest.mark.asyncio
async def test_report_card_unknown_student_raises(db_session: AsyncSession):
    await _seed_full(db_session)
    service = ReportCardService(db_session)
    with pytest.raises(Exception, match="not found"):
        await service.get_student_report_card(99999, 1)


@pytest.mark.asyncio
async def test_report_card_no_enrollment_raises(db_session: AsyncSession):
    await _seed_full(db_session)
    service = ReportCardService(db_session)

    # A second student with no enrollment in the year.
    orphan = Student(first_name="No", last_name="Enroll", student_number="RC999", status="active")
    db_session.add(orphan)
    await db_session.flush()

    with pytest.raises(Exception, match="no enrollment"):
        await service.get_student_report_card(orphan.id, 1)


# ---------------------------------------------------------------------------
# Service — class marksheet
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_class_marksheet_lists_students_and_subjects(db_session: AsyncSession):
    data = await _seed_full(db_session)
    service = ReportCardService(db_session)

    marksheet = await service.get_class_marksheet(
        data["class"].id, data["year"].id
    )

    assert marksheet.class_name == "RC Grade 10"
    assert marksheet.academic_year_name == "RC Year"
    assert [s.name for s in marksheet.subjects] == ["Mathematics"]
    assert len(marksheet.rows) == 1

    row = marksheet.rows[0]
    assert row.student_name == "RCStu Student"
    assert row.student_number == "RC001"
    assert len(row.subjects) == 1
    cell = row.subjects[0]
    assert cell.subject_name == "Mathematics"
    assert cell.marks_obtained == 85.0
    assert cell.grade == "A"
    assert row.total_marks == 85.0
    assert row.max_marks == 100
    assert row.percentage == 85.0
    assert row.grade_point_average == 9.0
    assert row.attendance_percentage == pytest.approx(66.7, abs=0.1)


@pytest.mark.asyncio
async def test_class_marksheet_empty_class_returns_empty_rows(db_session: AsyncSession):
    data = await _seed_full(db_session)
    service = ReportCardService(db_session)

    other = Class(name="RC Grade 11", academic_year_id=data["year"].id, status="active")
    db_session.add(other)
    await db_session.flush()

    marksheet = await service.get_class_marksheet(other.id, data["year"].id)
    assert marksheet.class_name == "RC Grade 11"
    assert marksheet.rows == []
    assert marksheet.subjects == []


# ---------------------------------------------------------------------------
# API layer
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _app_session() -> AsyncIterator[AsyncSession]:
    """Yield a live session bound to the app's test engine (see
    ``tests/test_timeline/test_api.py`` for the rationale)."""
    from app.main import app

    override = app.dependency_overrides[__import__("app.infrastructure.database", fromlist=["get_session"]).get_session]
    gen = override()
    try:
        session = await gen.__anext__()
        yield session
        await session.commit()
    finally:
        await gen.aclose()


async def _login(api_client, username: str = "admin", password: str = "AdminPass123!") -> dict:
    resp = await api_client.post(
        "/auth/login", json={"login": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _seed_via_app(api_client) -> dict:
    from app.infrastructure.database import get_session

    async def _seed(session: AsyncSession) -> dict:
        return await _seed_full(session, prefix="API")

    from app.main import app

    override = app.dependency_overrides[get_session]
    gen = override()
    try:
        session = await gen.__anext__()
        data = await _seed(session)
        await session.commit()
    finally:
        await gen.aclose()
    return data


@pytest.mark.asyncio
async def test_report_card_endpoints_require_auth(api_client):
    resp = await api_client.get(
        "/api/report-cards/students/1", params={"academic_year_id": 1}
    )
    assert resp.status_code in (401, 403)

    resp = await api_client.get(
        "/api/report-cards/classes/1", params={"academic_year_id": 1}
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_report_card_endpoint_happy_path(api_client):
    data = await _seed_via_app(api_client)
    headers = await _login(api_client)

    resp = await api_client.get(
        f"/api/report-cards/students/{data['student'].id}",
        params={"academic_year_id": data["year"].id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["student_number"] == "API001"
    assert len(body["terms"]) == 1
    assert body["attendance"]["present"] == 2


@pytest.mark.asyncio
async def test_marksheet_endpoint_happy_path(api_client):
    data = await _seed_via_app(api_client)
    headers = await _login(api_client)

    resp = await api_client.get(
        f"/api/report-cards/classes/{data['class'].id}",
        params={"academic_year_id": data["year"].id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["rows"]) == 1
    assert body["rows"][0]["student_number"] == "API001"
    assert body["rows"][0]["subjects"][0]["grade"] == "A"


@pytest.mark.asyncio
async def test_report_card_pdf_download(api_client):
    data = await _seed_via_app(api_client)
    headers = await _login(api_client)

    resp = await api_client.get(
        f"/api/report-cards/students/{data['student'].id}/pdf",
        params={"academic_year_id": data["year"].id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert resp.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_marksheet_pdf_download(api_client):
    data = await _seed_via_app(api_client)
    headers = await _login(api_client)

    resp = await api_client.get(
        f"/api/report-cards/classes/{data['class'].id}/pdf",
        params={"academic_year_id": data["year"].id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_report_card_unknown_student_404(api_client):
    headers = await _login(api_client)
    resp = await api_client.get(
        "/api/report-cards/students/99999",
        params={"academic_year_id": 1},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_report_card_cross_tenant_denied(api_client):
    """A campus-scoped staff user must not read another campus's card."""
    from app.domains.auth.models import User
    from app.domains.auth.security import hash_password
    from sqlalchemy import select

    from app.infrastructure.database import get_session
    from app.main import app

    # Seed a student on campus 1 through the app session.
    async def _seed(session: AsyncSession) -> dict:
        return await _seed_full(session, prefix="XT")

    override = app.dependency_overrides[get_session]
    gen = override()
    try:
        session = await gen.__anext__()
        data = await _seed(session)
        student = await session.get(Student, data["student"].id)
        student.campus_id = 1
        # Staff user pinned to campus 2 (legacy column path).
        existing = await session.execute(select(User).where(User.username == "xtstaff"))
        if existing.scalar_one_or_none() is None:
            session.add(
                User(
                    username="xtstaff",
                    email="xtstaff@test.local",
                    password_hash=hash_password("AdminPass123!"),
                    display_name="XT Staff",
                    role="staff",
                    campus_id=2,
                    is_active=True,
                )
            )
        await session.commit()
    finally:
        await gen.aclose()

    headers = await _login(api_client, "xtstaff", "AdminPass123!")
    resp = await api_client.get(
        f"/api/report-cards/students/{data['student'].id}",
        params={"academic_year_id": data["year"].id},
        headers=headers,
    )
    assert resp.status_code == 403
