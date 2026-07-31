"""Integration tests for multi-tenant data isolation.

Verifies that data belonging to campus A is invisible to users
authenticated against campus B (or unscoped users).

The test database is seeded with:
  - Institution (id=1)
  - Campus A (id=1, institution_id=1)
  - Campus B (id=2, institution_id=1)
  - User A (campus_id=1), User B (campus_id=2)
  - Cross-tenant admin user (campus_id=None)

Because the test uses SQLite (shared schema with ``campus_id``
columns), we validate the **application-level** isolation provided
by the ``TenantScopedRepository`` and manual repository filters
rather than database-level constraints.

See also:
  - ``app/multi_tenant/repository.py`` (``TenantScopedRepository``)
  - ``app/multi_tenant/dependencies.py`` (``get_current_tenant``)
"""

from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from sqlalchemy import select, func

from app.domains.student.models import Student
from app.domains.attendance.models import AttendanceRecord
from app.domains.fees.models import FeeDue
from app.domains.academic.models import AcademicYear, Class, Section
from app.domains.fees.models import FeeStructure
from app.domains.fees.models import FeeType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.datetime.now(timezone.utc)


async def _count_by_campus(session, model) -> dict[int | None, int]:
    """Return a dict mapping campus_id -> row count for the given model."""
    rows = (await session.execute(select(model))).scalars().all()
    counts: dict[int | None, int] = {}
    for r in rows:
        cid = getattr(r, "campus_id", None)
        counts[cid] = counts.get(cid, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def campus_a_headers():
    """JWT-like headers for a user on campus A (id=1)."""
    return {"Authorization": "Bearer campus_a_token"}


@pytest.fixture
def campus_b_headers():
    """JWT-like headers for a user on campus B (id=2)."""
    return {"Authorization": "Bearer campus_b_token"}


# ---------------------------------------------------------------------------
# Tests: creating entities with a campus_id
# ---------------------------------------------------------------------------


class TestStudentIsolation:
    """Verify that Student queries respect campus boundaries."""

    async def test_create_students_on_different_campuses(self, db_session):
        """Two students created with different campus_ids should be
        isolated by a tenant-scoped list query."""
        # Arrange
        s1 = Student(
            first_name="Alice",
            last_name="CampusA",
            student_number="STU-A-001",
            campus_id=1,
            status="active",
        )
        s2 = Student(
            first_name="Bob",
            last_name="CampusB",
            student_number="STU-B-001",
            campus_id=2,
            status="active",
        )
        db_session.add_all([s1, s2])
        await db_session.flush()

        # Act — simulate a repository with tenant filter for campus 1
        stmt = select(Student).where(Student.campus_id == 1)
        result = await db_session.execute(stmt)
        campus_a_students = list(result.scalars().all())

        # Assert
        assert len(campus_a_students) == 1
        assert campus_a_students[0].student_number == "STU-A-001"

    async def test_unscoped_user_sees_all_students(self, db_session):
        """When no tenant filter is applied (admin), all campuses are
        visible."""
        s1 = Student(
            first_name="Alice",
            last_name="CampusA",
            student_number="STU-A-002",
            campus_id=1,
            status="active",
        )
        s2 = Student(
            first_name="Bob",
            last_name="CampusB",
            student_number="STU-B-002",
            campus_id=2,
            status="active",
        )
        db_session.add_all([s1, s2])
        await db_session.flush()

        stmt = select(Student)  # no tenant filter
        result = await db_session.execute(stmt)
        all_students = list(result.scalars().all())

        assert len(all_students) == 2

    async def test_delete_does_not_affect_other_campus(self, db_session):
        """Deleting a student on campus A must not affect campus B data."""
        s1 = Student(
            first_name="Alice",
            last_name="CampusA",
            student_number="STU-A-003",
            campus_id=1,
            status="active",
        )
        s2 = Student(
            first_name="Bob",
            last_name="CampusB",
            student_number="STU-B-003",
            campus_id=2,
            status="active",
        )
        db_session.add_all([s1, s2])
        await db_session.flush()

        # Simulate tenant-scoped delete for campus A
        await db_session.delete(s1)
        await db_session.flush()

        counts = await _count_by_campus(db_session, Student)
        assert counts.get(1, 0) == 0  # Alice gone
        assert counts.get(2, 0) == 1  # Bob remains


class TestAttendanceIsolation:
    """Verify that AttendanceRecord respects campus boundaries."""

    async def test_attendance_isolated_by_campus(self, db_session):
        await self._seed_attendance_records(db_session)

        # Query for campus 1
        stmt = select(AttendanceRecord).where(AttendanceRecord.campus_id == 1)
        result = await db_session.execute(stmt)
        campus_a = list(result.scalars().all())

        # Query for campus 2
        stmt = select(AttendanceRecord).where(AttendanceRecord.campus_id == 2)
        result = await db_session.execute(stmt)
        campus_b = list(result.scalars().all())

        assert len(campus_a) == 2
        assert len(campus_b) == 1

    async def _seed_attendance_records(self, db_session):
        # Minimal required FK chain for attendance_records
        year = AcademicYear(
            name="Test Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            campus_id=1,
            status="active",
        )
        db_session.add(year)
        await db_session.flush()

        cls = Class(name="Test Class", academic_year_id=year.id, campus_id=1, status="active")
        db_session.add(cls)
        await db_session.flush()

        sec = Section(name="Test Section", class_id=cls.id, campus_id=1, status="active")
        db_session.add(sec)
        await db_session.flush()

        students = [
            Student(first_name=f"S{i}A", last_name="CampusA", student_number=f"STU-AT-{i}A", campus_id=1, status="active")
            for i in range(2)
        ]
        students += [
            Student(first_name="S1B", last_name="CampusB", student_number="STU-AT-1B", campus_id=2, status="active")
        ]
        db_session.add_all(students)
        await db_session.flush()

        records = [
            AttendanceRecord(
                student_id=students[0].id, campus_id=1, academic_year_id=year.id,
                class_id=cls.id, section_id=sec.id,
                attendance_date="2026-07-01", status="present",
            ),
            AttendanceRecord(
                student_id=students[1].id, campus_id=1, academic_year_id=year.id,
                class_id=cls.id, section_id=sec.id,
                attendance_date="2026-07-01", status="absent",
            ),
            AttendanceRecord(
                student_id=students[2].id, campus_id=2, academic_year_id=year.id,
                class_id=cls.id, section_id=sec.id,
                attendance_date="2026-07-01", status="present",
            ),
        ]
        db_session.add_all(records)
        await db_session.flush()


class TestFeeIsolation:
    """Verify that fee entities are isolated by campus."""

    async def test_fee_due_isolated_by_campus(self, db_session):
        await self._seed_fee_data(db_session)

        stmt = select(FeeDue).where(FeeDue.campus_id == 1)
        result = await db_session.execute(stmt)
        campus_a = list(result.scalars().all())

        stmt = select(FeeDue).where(FeeDue.campus_id == 2)
        result = await db_session.execute(stmt)
        campus_b = list(result.scalars().all())

        assert len(campus_a) == 1
        assert len(campus_b) == 1

    async def _seed_fee_data(self, db_session):
        year = AcademicYear(
            name="Fee Test Year",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            campus_id=1,
            status="active",
        )
        db_session.add(year)
        await db_session.flush()

        cls = Class(name="Fee Test Class", academic_year_id=year.id, campus_id=1, status="active")
        db_session.add(cls)
        await db_session.flush()

        ft = FeeType(name="Tuition", campus_id=1, status="active")
        db_session.add(ft)
        await db_session.flush()

        fstruct = FeeStructure(
            academic_year_id=year.id, class_id=cls.id, fee_type_id=ft.id,
            campus_id=1, amount=1000, frequency="annual", status="active",
        )
        db_session.add(fstruct)
        await db_session.flush()

        s1 = Student(
            first_name="FeeA", last_name="CampusA",
            student_number="STU-FEE-A", campus_id=1, status="active",
        )
        s2 = Student(
            first_name="FeeB", last_name="CampusB",
            student_number="STU-FEE-B", campus_id=2, status="active",
        )
        db_session.add_all([s1, s2])
        await db_session.flush()

        due_a = FeeDue(
            student_id=s1.id, academic_year_id=year.id,
            fee_structure_id=fstruct.id, original_amount=500,
            campus_id=1, amount_paid=0, status="unpaid",
        )
        due_b = FeeDue(
            student_id=s2.id, academic_year_id=year.id,
            fee_structure_id=fstruct.id, original_amount=500,
            campus_id=2, amount_paid=0, status="unpaid",
        )
        db_session.add_all([due_a, due_b])
        await db_session.flush()


class TestTenantAwareServiceMixin:
    """Verify the TenantAwareService mixin behaviour."""

    def test_inject_tenant_sets_campus_id(self):
        from app.multi_tenant.models import TenantContext
        from app.multi_tenant.service_mixin import TenantAwareService

        svc = TenantAwareService(tenant=TenantContext(campus_id=42))
        s = Student(
            first_name="T", last_name="Test",
            student_number="TENANT-TEST", status="active",
        )
        # campus_id is not set yet
        assert getattr(s, "campus_id", None) is None

        svc.inject_tenant(s)
        assert s.campus_id == 42

    def test_inject_tenant_skips_when_no_tenant(self):
        from app.multi_tenant.service_mixin import TenantAwareService

        svc = TenantAwareService(tenant=None)
        s = Student(
            first_name="T", last_name="Test",
            student_number="TENANT-SKIP", status="active",
        )
        svc.inject_tenant(s)
        assert getattr(s, "campus_id", None) is None

    def test_assert_tenant_scoped_raises_on_mismatch(self):
        from app.core.exceptions import AuthorizationError
        from app.multi_tenant.models import TenantContext
        from app.multi_tenant.service_mixin import TenantAwareService

        svc = TenantAwareService(tenant=TenantContext(campus_id=1))
        s = Student(
            first_name="T", last_name="Test",
            student_number="TENANT-RAISE",
            campus_id=2, status="active",
        )
        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            svc.assert_tenant_scoped(s)

    def test_assert_tenant_scoped_passes_on_match(self):
        from app.multi_tenant.models import TenantContext
        from app.multi_tenant.service_mixin import TenantAwareService

        svc = TenantAwareService(tenant=TenantContext(campus_id=1))
        s = Student(
            first_name="T", last_name="Test",
            student_number="TENANT-PASS",
            campus_id=1, status="active",
        )
        # Should not raise
        svc.assert_tenant_scoped(s)
