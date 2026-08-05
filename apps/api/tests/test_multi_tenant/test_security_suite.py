"""Dedicated multi-tenant security test suite (end-to-end, API level).

Proves the isolation chain:

    Authenticated User → Tenant Membership → Tenant Context
    → Tenant-Scoped Query → Resource-Level Authorization

is enforced *structurally* for every tenant-owned surface: a user
belonging to Campus A can never read, list, update, delete, search,
export, batch-process, or reach-through-to a record owned by Campus B —
whether by guessing an ID (IDOR), through relationships / 360 views,
through analytics aggregates, background jobs, notifications, or
document downloads.

Scenarios (each maps to the hardening checklist):
  1. read-by-ID IDOR            — GET /students/{b_id}, /classes/{b_id}, ...
  2. write IDOR                 — PATCH / DELETE on B-owned rows
  3. list isolation             — list endpoints never leak B rows
  4. relationship isolation     — 360 views, enrollment/attendance/fee joins
  5. search isolation           — global search never returns B rows
  6. reports & exports          — CSV exports contain only the caller's campus
  7. bulk APIs                  — batch enroll / fee-dues cannot touch B rows
  8. analytics                  — aggregates are campus-scoped
  9. background jobs            — jobs owned by B are invisible
 10. notifications              — notifications never leak across campuses
 11. document downloads         — B documents unreachable (get + download)
 12. platform authorization     — default-deny for unscoped users, and only
                                 an explicit platform permission enables
                                 cross-tenant access

Every ``_b`` (campus B) row is seeded directly through the same engine
the API uses, so a leaked response is guaranteed to be visible if any
layer forgets to scope.
"""

from __future__ import annotations

import datetime
from datetime import timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.database import Base, get_session

# Import all models so Base.metadata can resolve cross-module FKs.
from app.domains.institution.models import (  # noqa: F401
    Institution, Campus,
)
from app.domains.auth.models import (  # noqa: F401
    User, UserSchoolMembership,
)
from app.domains.auth.security import hash_password  # noqa: F401
from app.domains.student.models import Student  # noqa: F401
from app.domains.academic.models import (  # noqa: F401
    AcademicYear, Class, Section, Enrollment, Teacher, Subject,
)
from app.domains.fees.models import (  # noqa: F401
    FeeType, FeeStructure, FeeDue,
)
from app.domains.attendance.models import AttendanceRecord  # noqa: F401
from app.domains.academic_ops.models import Room  # noqa: F401
from app.domains.notifications.models import Notification  # noqa: F401
from app.domains.jobs.models import Job  # noqa: F401
from app.domains.documents.models import (  # noqa: F401
    Document, DocumentCategory,
)
from app.domains.admission.models import AdmissionApplication  # noqa: F401
from app.domains.parent.models import Guardian  # noqa: F401
from app.domains.communications.models import CommunicationMessage  # noqa: F401
from app.domains.student_portal.models import Assignment  # noqa: F401
from app.domains.audit.models import AuditLog  # noqa: F401
from app.multi_tenant.models import platform_context

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

NOW = datetime.datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Test environment fixture: two campuses + users on each + platform actors
# ---------------------------------------------------------------------------


class _TenantEnv:
    """Namespace exposing the API client, the shared session factory and
    seeded identities."""

    def __init__(self, client: AsyncClient, factory, admin_a_id: int, admin_b_id: int):
        self.client = client
        self.factory = factory
        self.admin_a_id = admin_a_id
        self.admin_b_id = admin_b_id
        self.campus_a = 1
        self.campus_b = 2


@pytest_asyncio.fixture
async def tenant_env() -> _TenantEnv:
    """In-memory DB with Institution, Campus A (1) and Campus B (2), plus:
    * admin_a  — member of campus A (default membership)   → scoped to A
    * admin_b  — member of campus B (default membership)   → scoped to B
    * staff_x  — no campus, no membership, no platform perm → default-deny
    * plat_admin — no campus, explicit ``platform.access`` → cross-tenant
    """
    from app.main import app  # registers every model with Base.metadata

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with factory() as seed:
        institution = Institution(name="Test District", code="TST-SEC")
        seed.add(institution)
        await seed.flush()
        campus_a = Campus(
            institution_id=institution.id, name="Campus A", code="SEC-A",
            status="active",
        )
        campus_b = Campus(
            institution_id=institution.id, name="Campus B", code="SEC-B",
            status="active",
        )
        seed.add_all([campus_a, campus_b])
        await seed.flush()

        admin_a = User(
            username="admin_a", email="admin_a@test.local",
            password_hash=hash_password("AdminA123!"),
            display_name="Admin A", role="admin",
            campus_id=campus_a.id, is_active=True,
        )
        admin_b = User(
            username="admin_b", email="admin_b@test.local",
            password_hash=hash_password("AdminB123!"),
            display_name="Admin B", role="admin",
            campus_id=campus_b.id, is_active=True,
        )
        staff_x = User(
            username="staff_x", email="staff_x@test.local",
            password_hash=hash_password("StaffX123!"),
            display_name="Staff X", role="staff",
            campus_id=None, is_active=True,
        )
        plat_admin = User(
            username="plat_admin", email="plat_admin@test.local",
            password_hash=hash_password("PlatA123!"),
            display_name="Platform Admin", role="platform_admin",
            campus_id=None, is_active=True,
        )
        seed.add_all([admin_a, admin_b, staff_x, plat_admin])
        await seed.flush()

        seed.add_all([
            UserSchoolMembership(
                user_id=admin_a.id, campus_id=campus_a.id,
                role="admin", is_default=True, is_active=True,
            ),
            UserSchoolMembership(
                user_id=admin_b.id, campus_id=campus_b.id,
                role="admin", is_default=True, is_active=True,
            ),
        ])
        await seed.commit()

    async def override_get_session():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield _TenantEnv(
            client=ac, factory=factory,
            admin_a_id=admin_a.id, admin_b_id=admin_b.id,
        )

    app.dependency_overrides.clear()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Login helpers
# ---------------------------------------------------------------------------


async def _login(client: AsyncClient, username: str, password: str) -> dict[str, str]:
    resp = await client.post(
        "/auth/login", json={"login": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def headers_a(tenant_env: _TenantEnv) -> dict[str, str]:
    return await _login(tenant_env.client, "admin_a", "AdminA123!")


@pytest_asyncio.fixture
async def headers_b(tenant_env: _TenantEnv) -> dict[str, str]:
    return await _login(tenant_env.client, "admin_b", "AdminB123!")


@pytest_asyncio.fixture
async def headers_staff_none(tenant_env: _TenantEnv) -> dict[str, str]:
    return await _login(tenant_env.client, "staff_x", "StaffX123!")


@pytest_asyncio.fixture
async def headers_platform(tenant_env: _TenantEnv) -> dict[str, str]:
    return await _login(tenant_env.client, "plat_admin", "PlatA123!")


# ---------------------------------------------------------------------------
# Seeding helpers (direct inserts via the shared engine)
# ---------------------------------------------------------------------------


async def _seed_student(factory, campus_id: int, number: str, last_name: str) -> int:
    async with factory() as s:
        st = Student(
            first_name=f"Sec{last_name}", last_name=last_name,
            student_number=number, campus_id=campus_id, status="active",
        )
        s.add(st)
        await s.commit()
        return st.id


async def _seed_academic(factory, campus_id: int, tag: str) -> dict:
    """Seed academic year + class + section + teacher + subject for a campus."""
    async with factory() as s:
        year = AcademicYear(
            name=f"Sec Year {tag}", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31), campus_id=campus_id,
            status="active",
        )
        s.add(year)
        await s.flush()
        cls = Class(
            name=f"Sec Class {tag}", academic_year_id=year.id,
            campus_id=campus_id, status="active",
        )
        s.add(cls)
        await s.flush()
        sec = Section(
            name=f"Sec Section {tag}", class_id=cls.id,
            campus_id=campus_id, status="active",
        )
        teacher = Teacher(
            first_name=f"Sec", last_name=f"Teacher {tag}",
            employee_number=f"SEC-T-{tag}", campus_id=campus_id,
            status="active",
        )
        subject = Subject(
            name=f"Sec Subject {tag}", code=f"SEC-S-{tag}",
            campus_id=campus_id, status="active",
        )
        s.add_all([sec, teacher, subject])
        await s.commit()
        return {
            "year_id": year.id, "class_id": cls.id, "section_id": sec.id,
            "teacher_id": teacher.id, "subject_id": subject.id,
        }


async def _seed_fee(factory, campus_id: int, tag: str, student_id: int,
                    year_id: int, class_id: int) -> dict:
    async with factory() as s:
        ft = FeeType(name=f"Sec Fee {tag}", campus_id=campus_id, status="active")
        s.add(ft)
        await s.flush()
        fs = FeeStructure(
            academic_year_id=year_id, class_id=class_id, fee_type_id=ft.id,
            campus_id=campus_id, amount=1000, frequency="annual", status="active",
        )
        s.add(fs)
        await s.flush()
        due = FeeDue(
            student_id=student_id, academic_year_id=year_id,
            fee_structure_id=fs.id, original_amount=500, amount_paid=0,
            campus_id=campus_id, status="unpaid",
        )
        s.add(due)
        await s.commit()
        return {"fee_type_id": ft.id, "structure_id": fs.id, "due_id": due.id}


async def _seed_enrollment(factory, campus_id: int, student_id: int,
                           year_id: int, class_id: int, section_id: int) -> int:
    async with factory() as s:
        enr = Enrollment(
            student_id=student_id, academic_year_id=year_id, class_id=class_id,
            section_id=section_id, campus_id=campus_id, status="active",
        )
        s.add(enr)
        await s.commit()
        return enr.id


async def _seed_attendance(factory, campus_id: int, student_id: int,
                           year_id: int, class_id: int, section_id: int) -> int:
    async with factory() as s:
        rec = AttendanceRecord(
            student_id=student_id, academic_year_id=year_id, class_id=class_id,
            section_id=section_id, campus_id=campus_id,
            attendance_date="2026-07-01", status="present",
        )
        s.add(rec)
        await s.commit()
        return rec.id


async def _seed_room(factory, campus_id: int, tag: str) -> int:
    async with factory() as s:
        room = Room(
            name=f"Sec Room {tag}", code=f"SEC-R-{tag}", campus_id=campus_id,
            status="active",
        )
        s.add(room)
        await s.commit()
        return room.id


async def _seed_notification(factory, campus_id: int, user_id: int,
                             title: str) -> int:
    async with factory() as s:
        n = Notification(
            type="system", title=title, message=f"msg-{title}",
            campus_id=campus_id, user_id=user_id,
        )
        s.add(n)
        await s.commit()
        return n.id


async def _seed_job(factory, campus_id: int, tag: str, user_id: int | None = None) -> int:
    async with factory() as s:
        job = Job(
            job_type=f"sec-{tag}", status="pending", campus_id=campus_id,
            user_id=user_id,
            created_at=NOW, updated_at=NOW,
        )
        s.add(job)
        await s.commit()
        return job.id


async def _seed_document(factory, campus_id: int, uploaded_by: int,
                         storage_key: str) -> int:
    async with factory() as s:
        cat = DocumentCategory(code=f"cat-{storage_key}", name=f"Cat {storage_key}")
        s.add(cat)
        await s.flush()
        doc = Document(
            category_id=cat.id, original_filename=f"{storage_key}.pdf",
            storage_key=storage_key, mime_type="application/pdf", file_size=10,
            lifecycle_state="active", campus_id=campus_id, uploaded_by=uploaded_by,
        )
        s.add(doc)
        await s.commit()
        return doc.id


async def _seed_admission(factory, campus_id: int, tag: str) -> int:
    async with factory() as s:
        app_ = AdmissionApplication(
            applicant_name=f"Sec Applicant {tag}", campus_id=campus_id,
        )
        s.add(app_)
        await s.commit()
        return app_.id


async def _seed_guardian(factory, user_id: int, student_id: int,
                         campus_id: int) -> int:
    async with factory() as s:
        g = Guardian(user_id=user_id, student_id=student_id, campus_id=campus_id)
        s.add(g)
        await s.commit()
        return g.id


async def _seed_role_user(factory, username: str, role: str, campus_id: int,
                          password: str = "RoleUsr123!") -> int:
    """Seed a user with a concrete role + school membership (so both
    ``require_role`` and ``require_tenant_context`` resolve)."""
    async with factory() as s:
        u = User(
            username=username, email=f"{username}@test.local",
            password_hash=hash_password(password), display_name=username,
            role=role, campus_id=campus_id, is_active=True,
        )
        s.add(u)
        await s.flush()
        s.add(UserSchoolMembership(
            user_id=u.id, campus_id=campus_id, role=role,
            is_default=True, is_active=True,
        ))
        await s.commit()
        return u.id


async def _seed_announcement(factory, campus_id: int | None, sender_id: int,
                             subject: str, message_type: str = "announcement") -> int:
    """Seed a sent communication message (campus_id=None ⇒ system-wide)."""
    async with factory() as s:
        msg = CommunicationMessage(
            subject=subject, body=f"body-{subject}", message_type=message_type,
            status="sent", campus_id=campus_id, sender_id=sender_id,
        )
        s.add(msg)
        await s.commit()
        return msg.id


async def _seed_audit(factory, campus_id: int | None, action: str,
                      resource: str, marker: str) -> int:
    """Seed an audit log entry with a unique marker in its details."""
    import json

    async with factory() as s:
        entry = AuditLog(
            event_id=marker, user_id=None, username=None, actor_type="user",
            action=action, resource_type=resource, resource_id="1",
            campus_id=campus_id,
            details=json.dumps({"marker": marker}),
        )
        s.add(entry)
        await s.commit()
        return entry.id


# ---------------------------------------------------------------------------
# 1 + 2. Read / update / delete IDOR across every tenant-owned surface
# ---------------------------------------------------------------------------


class TestIdorIsolation:
    """Tenant A can never read/update/delete a record owned by Tenant B."""

    @pytest.mark.asyncio
    async def test_student_idor(self, tenant_env, headers_a, headers_b):
        client = tenant_env.client
        b_id = await _seed_student(tenant_env.factory, 2, "SEC-STU-B", "StuB")
        a_id = await _seed_student(tenant_env.factory, 1, "SEC-STU-A", "StuA")

        # B can read its own.
        ok = await client.get(f"/students/{b_id}", headers=headers_b)
        assert ok.status_code == 200, ok.text
        # A cannot read B's student.
        resp = await client.get(f"/students/{b_id}", headers=headers_a)
        assert resp.status_code in (403, 404), resp.text
        # A can read its own.
        resp = await client.get(f"/students/{a_id}", headers=headers_a)
        assert resp.status_code == 200, resp.text

        # A cannot update B's student.
        resp = await client.patch(
            f"/students/{b_id}", json={"last_name": "Hijacked"}, headers=headers_a
        )
        assert resp.status_code in (403, 404), resp.text
        # A cannot delete B's student.
        resp = await client.delete(f"/students/{b_id}", headers=headers_a)
        assert resp.status_code in (403, 404), resp.text

    @pytest.mark.asyncio
    async def test_class_and_children_idor(self, tenant_env, headers_a, headers_b):
        client = tenant_env.client
        b = await _seed_academic(tenant_env.factory, 2, "B")
        a = await _seed_academic(tenant_env.factory, 1, "A")

        for endpoint in [
            "/api/academic-years/{id}",
            "/api/classes/{id}",
            "/api/sections/{id}",
            "/api/teachers/{id}",
            "/api/subjects/{id}",
        ]:
            b_path = endpoint.replace("{id}", str(_id_of(b, endpoint)))
            a_path = endpoint.replace("{id}", str(_id_of(a, endpoint)))
            resp = await client.get(b_path, headers=headers_a)
            assert resp.status_code in (403, 404), f"{b_path}: {resp.status_code}"
            own = await client.get(a_path, headers=headers_a)
            assert own.status_code == 200, f"own {a_path}: {own.status_code}"

        # PATCH a B-owned class from A.
        resp = await client.patch(
            f"/api/classes/{b['class_id']}",
            json={"name": "Hijacked"}, headers=headers_a,
        )
        assert resp.status_code in (403, 404), resp.text
        # DELETE a B-owned class from A.
        resp = await client.delete(
            f"/api/classes/{b['class_id']}", headers=headers_a
        )
        assert resp.status_code in (403, 404), resp.text

    @pytest.mark.asyncio
    async def test_fee_room_enrollment_attendance_idor(
        self, tenant_env, headers_a, headers_b
    ):
        client = tenant_env.client
        b_ac = await _seed_academic(tenant_env.factory, 2, "B2")
        a_ac = await _seed_academic(tenant_env.factory, 1, "A2")
        b_stu = await _seed_student(tenant_env.factory, 2, "SEC-STU-B2", "StuB2")
        a_stu = await _seed_student(tenant_env.factory, 1, "SEC-STU-A2", "StuA2")
        b_fee = await _seed_fee(
            tenant_env.factory, 2, "B2", b_stu, b_ac["year_id"], b_ac["class_id"]
        )
        a_fee = await _seed_fee(
            tenant_env.factory, 1, "A2", a_stu, a_ac["year_id"], a_ac["class_id"]
        )
        b_enr = await _seed_enrollment(
            tenant_env.factory, 2, b_stu, b_ac["year_id"],
            b_ac["class_id"], b_ac["section_id"],
        )
        a_enr = await _seed_enrollment(
            tenant_env.factory, 1, a_stu, a_ac["year_id"],
            a_ac["class_id"], a_ac["section_id"],
        )
        b_att = await _seed_attendance(
            tenant_env.factory, 2, b_stu, b_ac["year_id"],
            b_ac["class_id"], b_ac["section_id"],
        )
        a_att = await _seed_attendance(
            tenant_env.factory, 1, a_stu, a_ac["year_id"],
            a_ac["class_id"], a_ac["section_id"],
        )
        b_room = await _seed_room(tenant_env.factory, 2, "B2")
        a_room = await _seed_room(tenant_env.factory, 1, "A2")

        for path, b_path, a_path in [
            ("/api/fees/fee-types/{id}", b_fee["fee_type_id"], a_fee["fee_type_id"]),
            ("/api/fees/dues/{id}", b_fee["due_id"], a_fee["due_id"]),
            ("/api/enrollments/{id}", b_enr, a_enr),
            ("/attendance/{id}", b_att, a_att),
            ("/api/academic/rooms/{id}", b_room, a_room),
        ]:
            b_url = path.replace("{id}", str(b_path))
            a_url = path.replace("{id}", str(a_path))
            resp = await client.get(b_url, headers=headers_a)
            assert resp.status_code in (403, 404), f"{b_url}: {resp.status_code}"
            own = await client.get(a_url, headers=headers_a)
            assert own.status_code == 200, f"own {a_url}: {own.status_code}"


def _id_of(mapping: dict, endpoint: str) -> int:
    """Map an endpoint back to the seeded id for the "own campus" check."""
    if "academic-years" in endpoint:
        return mapping["year_id"]
    if "classes" in endpoint:
        return mapping["class_id"]
    if "sections" in endpoint:
        return mapping["section_id"]
    if "teachers" in endpoint:
        return mapping["teacher_id"]
    if "subjects" in endpoint:
        return mapping["subject_id"]
    return 0


# ---------------------------------------------------------------------------
# 3. List isolation
# ---------------------------------------------------------------------------


class TestListIsolation:
    @pytest.mark.asyncio
    async def test_student_list_excludes_other_campus(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        await _seed_student(tenant_env.factory, 2, "SEC-LST-B", "LstB")
        await _seed_student(tenant_env.factory, 1, "SEC-LST-A", "LstA")

        resp = await client.get("/students", headers=headers_a)
        assert resp.status_code == 200, resp.text
        body = resp.text
        assert "SEC-LST-B" not in body
        assert "SEC-LST-A" in body

    @pytest.mark.asyncio
    async def test_class_and_fee_list_exclude_other_campus(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        b_ac = await _seed_academic(tenant_env.factory, 2, "B3")
        a_ac = await _seed_academic(tenant_env.factory, 1, "A3")
        await _seed_fee(
            tenant_env.factory, 2, "B3",
            await _seed_student(tenant_env.factory, 2, "SEC-LST-B2", "LstB2"),
            b_ac["year_id"], b_ac["class_id"],
        )
        await _seed_fee(
            tenant_env.factory, 1, "A3",
            await _seed_student(tenant_env.factory, 1, "SEC-LST-A2", "LstA2"),
            a_ac["year_id"], a_ac["class_id"],
        )

        for path, b_token, a_token in [
            ("/api/classes", "Sec Class B3", "Sec Class A3"),
            ("/api/fees/fee-types", "Sec Fee B3", "Sec Fee A3"),
            ("/api/fees/dues", "", ""),
        ]:
            resp = await client.get(path, headers=headers_a)
            assert resp.status_code == 200, f"{path}: {resp.status_code}"
            body = resp.text
            if b_token:
                assert b_token not in body, f"leak in {path}"
            if a_token:
                assert a_token in body, f"missing own data in {path}"

    @pytest.mark.asyncio
    async def test_admission_list_excludes_other_campus(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        await _seed_admission(tenant_env.factory, 2, "B")
        await _seed_admission(tenant_env.factory, 1, "A")
        resp = await client.get("/api/admissions/applications", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert "Sec Applicant B" not in resp.text
        assert "Sec Applicant A" in resp.text


# ---------------------------------------------------------------------------
# 4. Relationship isolation (360 views + nested resources)
# ---------------------------------------------------------------------------


class TestRelationshipIsolation:
    @pytest.mark.asyncio
    async def test_360_views_are_tenant_scoped(self, tenant_env, headers_a):
        client = tenant_env.client
        b_ac = await _seed_academic(tenant_env.factory, 2, "B4")
        a_ac = await _seed_academic(tenant_env.factory, 1, "A4")
        b_stu = await _seed_student(tenant_env.factory, 2, "SEC-360-B", "V360B")
        a_stu = await _seed_student(tenant_env.factory, 1, "SEC-360-A", "V360A")

        # B-owned resources must be unreachable through 360 views.
        for path in [
            f"/students/{b_stu}/360",
            f"/classes/{b_ac['class_id']}/360",
            f"/teachers/{b_ac['teacher_id']}/360",
        ]:
            resp = await client.get(path, headers=headers_a)
            assert resp.status_code in (403, 404), f"{path}: {resp.status_code}"

        # Own resources are reachable.
        for path in [
            f"/students/{a_stu}/360",
            f"/classes/{a_ac['class_id']}/360",
            f"/teachers/{a_ac['teacher_id']}/360",
        ]:
            resp = await client.get(path, headers=headers_a)
            assert resp.status_code == 200, f"{path}: {resp.status_code}"

    @pytest.mark.asyncio
    async def test_guardian_junction_cannot_link_cross_tenant(
        self, tenant_env, headers_a, headers_b
    ):
        """A guardian link row is tenant-tagged; the canonical scoped
        repository of tenant A cannot resolve a link owned by tenant B."""
        client = tenant_env.client
        b_stu = await _seed_student(tenant_env.factory, 2, "SEC-GRD-B", "GrdB")
        b_link = await _seed_guardian(
            tenant_env.factory, tenant_env.admin_b_id, b_stu, 2
        )

        from app.multi_tenant.repository import TenantScopedRepository
        from app.multi_tenant.models import TenantContext

        async with tenant_env.factory() as s:
            repo = TenantScopedRepository(s, TenantContext(campus_id=1))
            found = await repo.get_by_id(Guardian, b_link)
            assert found is None, "tenant A resolved a guardian link owned by B"

            repo_b = TenantScopedRepository(s, TenantContext(campus_id=2))
            own = await repo_b.get_by_id(Guardian, b_link)
            assert own is not None, "tenant B cannot read its own guardian link"


# ---------------------------------------------------------------------------
# 5. Search isolation
# ---------------------------------------------------------------------------


class TestSearchIsolation:
    @pytest.mark.asyncio
    async def test_global_search_excludes_other_campus(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        b_id = await _seed_student(tenant_env.factory, 2, "SEC-SCH-B", "SchBUnique")
        a_id = await _seed_student(tenant_env.factory, 1, "SEC-SCH-A", "SchAUnique")

        resp = await client.post(
            "/api/search",
            json={"query": "SchBUnique", "types": ["student"]},
            headers=headers_a,
        )
        assert resp.status_code == 200, resp.text
        # The response echoes the query string, so inspect the results array.
        body = resp.json()
        entity_ids = {int(r["entity_id"]) for r in body.get("results", [])}
        assert b_id not in entity_ids, "search leaked a campus-B student"

        resp = await client.post(
            "/api/search",
            json={"query": "SchAUnique", "types": ["student"]},
            headers=headers_a,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        entity_ids = {int(r["entity_id"]) for r in body.get("results", [])}
        assert a_id in entity_ids, "search missed an own-campus student"


# ---------------------------------------------------------------------------
# 6. Reports & exports
# ---------------------------------------------------------------------------


class TestReportsAndExports:
    @pytest.mark.asyncio
    async def test_class_attendance_report_other_campus_denied(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        b_ac = await _seed_academic(tenant_env.factory, 2, "B5")
        resp = await client.get(
            f"/api/reports/attendance/class/{b_ac['class_id']}",
            params={"academic_year_id": b_ac["year_id"]},
            headers=headers_a,
        )
        assert resp.status_code in (403, 404), resp.text

    @pytest.mark.asyncio
    async def test_export_students_csv_excludes_other_campus(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        await _seed_student(tenant_env.factory, 2, "SEC-EXP-B", "ExpB")
        await _seed_student(tenant_env.factory, 1, "SEC-EXP-A", "ExpA")

        resp = await client.get("/api/reports/export/students", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert "SEC-EXP-B" not in resp.text
        assert "SEC-EXP-A" in resp.text

    @pytest.mark.asyncio
    async def test_export_attendance_csv_excludes_other_campus(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        b_ac = await _seed_academic(tenant_env.factory, 2, "B6")
        a_ac = await _seed_academic(tenant_env.factory, 1, "A6")
        b_stu = await _seed_student(tenant_env.factory, 2, "SEC-EXP-AB", "ExpAB")
        a_stu = await _seed_student(tenant_env.factory, 1, "SEC-EXP-AA", "ExpAA")
        await _seed_attendance(
            tenant_env.factory, 2, b_stu, b_ac["year_id"],
            b_ac["class_id"], b_ac["section_id"],
        )
        await _seed_attendance(
            tenant_env.factory, 1, a_stu, a_ac["year_id"],
            a_ac["class_id"], a_ac["section_id"],
        )

        resp = await client.get("/api/reports/export/attendance", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert "SEC-EXP-AB" not in resp.text
        assert "SEC-EXP-AA" in resp.text


# ---------------------------------------------------------------------------
# 7. Bulk APIs
# ---------------------------------------------------------------------------


class TestBulkApiIsolation:
    @pytest.mark.asyncio
    async def test_batch_enroll_cannot_use_other_campus_student(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        a_ac = await _seed_academic(tenant_env.factory, 1, "A7")
        b_stu = await _seed_student(tenant_env.factory, 2, "SEC-BULK-B", "BulkB")

        resp = await client.post(
            "/api/reports/batch/enroll",
            json={
                "academic_year_id": a_ac["year_id"],
                "enrollments": [
                    {"student_id": b_stu, "class_id": a_ac["class_id"]}
                ],
            },
            headers=headers_a,
        )
        # The bulk call must not create a cross-tenant association: the
        # B-owned student is invisible to A, so the row fails cleanly.
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["succeeded"] == 0
        assert body["failed"] == 1

        async with tenant_env.factory() as s:
            rows = (await s.execute(
                select(Enrollment).where(Enrollment.student_id == b_stu)
            )).scalars().all()
        assert len(rows) == 0, "cross-tenant enrollment was created!"

    @pytest.mark.asyncio
    async def test_rollover_preview_other_campus_year_denied(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        b_ac = await _seed_academic(tenant_env.factory, 2, "B7")
        resp = await client.post(
            "/api/reports/rollover/preview",
            json={
                "from_year_id": b_ac["year_id"],
                "to_year_name": "Sec Roll 2027",
                "to_start_date": "2027-01-01",
                "to_end_date": "2027-12-31",
            },
            headers=headers_a,
        )
        assert resp.status_code in (403, 404), resp.text


# ---------------------------------------------------------------------------
# 8. Analytics
# ---------------------------------------------------------------------------


class TestAnalyticsIsolation:
    @pytest.mark.asyncio
    async def test_analytics_overview_excludes_other_campus(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        await _seed_student(tenant_env.factory, 2, "SEC-ANA-B", "AnaB")
        await _seed_student(tenant_env.factory, 1, "SEC-ANA-A", "AnaA")

        resp = await client.get("/api/analytics/overview", headers=headers_a)
        assert resp.status_code == 200, resp.text
        # Analytics returns aggregates — only campus A's student may be
        # counted, never campus B's.
        body = resp.json()
        assert body["total_students"] == 1, body

    @pytest.mark.asyncio
    async def test_analytics_students_overview_excludes_other_campus(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        await _seed_student(tenant_env.factory, 2, "SEC-ANA2-B", "Ana2B")
        await _seed_student(tenant_env.factory, 1, "SEC-ANA2-A", "Ana2A")

        resp = await client.get("/api/analytics/students/overview", headers=headers_a)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("total_students", body.get("total", 0)) == 1, body


# ---------------------------------------------------------------------------
# 9. Background jobs
# ---------------------------------------------------------------------------


class TestJobsIsolation:
    @pytest.mark.asyncio
    async def test_jobs_list_and_get_are_tenant_scoped(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        # Jobs list filters by the current user; tie each job to its owner.
        b_job = await _seed_job(
            tenant_env.factory, 2, "bjob", user_id=tenant_env.admin_b_id
        )
        a_job = await _seed_job(
            tenant_env.factory, 1, "ajob", user_id=tenant_env.admin_a_id
        )

        resp = await client.get(f"/jobs/{b_job}", headers=headers_a)
        assert resp.status_code in (403, 404), resp.text

        resp = await client.get("/jobs", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert "sec-bjob" not in resp.text
        assert "sec-ajob" in resp.text


# ---------------------------------------------------------------------------
# 10. Notifications
# ---------------------------------------------------------------------------


class TestNotificationsIsolation:
    @pytest.mark.asyncio
    async def test_notifications_never_leak_across_campuses(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        await _seed_notification(
            tenant_env.factory, 2, tenant_env.admin_b_id,
            "SEC-NOTIF-B-SECRET",
        )
        await _seed_notification(
            tenant_env.factory, 1, tenant_env.admin_a_id,
            "SEC-NOTIF-A-VISIBLE",
        )

        resp = await client.get("/api/notifications", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert "SEC-NOTIF-B-SECRET" not in resp.text
        assert "SEC-NOTIF-A-VISIBLE" in resp.text


# ---------------------------------------------------------------------------
# 11. Document downloads
# ---------------------------------------------------------------------------


class TestDocumentIsolation:
    @pytest.mark.asyncio
    async def test_document_get_and_download_are_tenant_scoped(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        b_doc = await _seed_document(
            tenant_env.factory, 2, tenant_env.admin_b_id, "SEC-DOC-B"
        )
        a_doc = await _seed_document(
            tenant_env.factory, 1, tenant_env.admin_a_id, "SEC-DOC-A"
        )

        resp = await client.get(f"/api/documents/{b_doc}", headers=headers_a)
        assert resp.status_code in (403, 404), resp.text
        resp = await client.get(
            f"/api/documents/{b_doc}/download", headers=headers_a
        )
        assert resp.status_code in (403, 404), resp.text

        resp = await client.get(f"/api/documents/{a_doc}", headers=headers_a)
        assert resp.status_code == 200, resp.text
        resp = await client.get("/api/documents", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert "SEC-DOC-B" not in resp.text
        assert "SEC-DOC-A" in resp.text


# ---------------------------------------------------------------------------
# 13. Parent junctions + portal announcements + student resolution
# ---------------------------------------------------------------------------


class TestParentAndPortalIsolation:
    """Guardian junctions and portal reads must never cross campus
    boundaries (relationship-table writes + portal fallback resolution)."""

    @pytest.mark.asyncio
    async def test_parent_cannot_link_cross_tenant_student(
        self, tenant_env
    ):
        """A parent on campus A must not be able to link (and thereby
        read) a student owned by campus B."""
        client = tenant_env.client
        parent_a = await _seed_role_user(
            tenant_env.factory, "parent_sec_a", "parent", 1
        )
        a_stu = await _seed_student(tenant_env.factory, 1, "SEC-PAR-A", "ParA")
        b_stu = await _seed_student(tenant_env.factory, 2, "SEC-PAR-B", "ParB")

        headers = await _login(client, "parent_sec_a", "RoleUsr123!")

        # Linking a cross-campus student is denied.
        resp = await client.post(
            "/api/parent/children/link",
            json={"student_id": b_stu, "relationship": "parent"},
            headers=headers,
        )
        assert resp.status_code in (403, 404), resp.text

        # No cross-tenant guardian junction may exist afterwards.
        async with tenant_env.factory() as s:
            rows = (await s.execute(
                select(Guardian).where(Guardian.student_id == b_stu)
            )).scalars().all()
        assert len(rows) == 0, "cross-tenant guardian link was created!"

        # Own-campus linking still works.
        resp = await client.post(
            "/api/parent/children/link",
            json={"student_id": a_stu, "relationship": "parent"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text

    @pytest.mark.asyncio
    async def test_parent_announcements_are_campus_scoped(
        self, tenant_env
    ):
        """Announcements from another campus are never listed for a parent."""
        client = tenant_env.client
        await _seed_role_user(tenant_env.factory, "parent_sec_b", "parent", 2)
        await _seed_announcement(
            tenant_env.factory, 2, tenant_env.admin_b_id, "SEC-ANN-B-SECRET"
        )
        await _seed_announcement(
            tenant_env.factory, 1, tenant_env.admin_a_id, "SEC-ANN-A-VISIBLE"
        )
        # System-wide announcement (campus NULL) stays visible everywhere.
        await _seed_announcement(
            tenant_env.factory, None, tenant_env.admin_a_id, "SEC-ANN-GLOBAL"
        )

        headers = await _login(client, "parent_sec_b", "RoleUsr123!")
        resp = await client.get("/api/parent/announcements", headers=headers)
        assert resp.status_code == 200, resp.text
        assert "SEC-ANN-B-SECRET" in resp.text
        assert "SEC-ANN-A-VISIBLE" not in resp.text
        assert "SEC-ANN-GLOBAL" in resp.text

    @pytest.mark.asyncio
    async def test_student_portal_resolution_stays_in_own_campus(
        self, tenant_env
    ):
        """A student user must never resolve to (and thus read) a student
        record owned by another campus — including the fallback path when
        the email match misses."""
        client = tenant_env.client
        a_stu = await _seed_student(
            tenant_env.factory, 1, "SEC-PTL-A", "PtlA"
        )
        b_stu = await _seed_student(
            tenant_env.factory, 2, "SEC-PTL-B", "PtlB"
        )
        # Student user on campus A whose email matches NO student record
        # (forces the fallback branch of ``resolve_student``).
        student_user = await _seed_role_user(
            tenant_env.factory, "student_sec_a", "student", 1,
            password="StuUsr123!",
        )

        from app.domains.student_portal.service import StudentPortalService

        async with tenant_env.factory() as s:
            svc = StudentPortalService(s)
            resolved = await svc.resolve_student(
                student_user, "no-match@nowhere.test", campus_id=1
            )
            assert resolved.id == a_stu, "fallback escaped the user's campus!"
            assert resolved.id != b_stu

    @pytest.mark.asyncio
    async def test_student_portal_announcements_are_campus_scoped(
        self, tenant_env
    ):
        """Student portal announcements must not leak another campus's
        messages."""
        client = tenant_env.client
        await _seed_role_user(
            tenant_env.factory, "student_sec_b", "student", 2,
            password="StuUsr123!",
        )
        await _seed_announcement(
            tenant_env.factory, 2, tenant_env.admin_b_id, "SEC-SANN-B-SECRET"
        )
        await _seed_announcement(
            tenant_env.factory, 1, tenant_env.admin_a_id, "SEC-SANN-A-VISIBLE"
        )

        headers = await _login(client, "student_sec_b", "StuUsr123!")
        resp = await client.get("/api/student/portal/announcements", headers=headers)
        assert resp.status_code == 200, resp.text
        assert "SEC-SANN-B-SECRET" in resp.text
        assert "SEC-SANN-A-VISIBLE" not in resp.text


# ---------------------------------------------------------------------------
# 12. Platform authorization
# ---------------------------------------------------------------------------


class TestPlatformAuthorization:
    @pytest.mark.asyncio
    async def test_unscoped_user_without_platform_is_denied(
        self, tenant_env, headers_staff_none
    ):
        """Default-deny: an authenticated user with no tenant membership and
        no explicit platform permission is rejected by tenant-scoped routes."""
        client = tenant_env.client
        resp = await client.get("/students", headers=headers_staff_none)
        assert resp.status_code == 403, resp.text

        resp = await client.get("/api/classes", headers=headers_staff_none)
        assert resp.status_code == 403, resp.text

    @pytest.mark.asyncio
    async def test_platform_admin_can_operate_cross_tenant(
        self, tenant_env, headers_platform
    ):
        """Explicit platform authorization is the ONLY path to cross-tenant
        reads — a platform_admin with ``platform.access`` may list rows from
        every campus (including campus B's)."""
        client = tenant_env.client
        b_stu = await _seed_student(tenant_env.factory, 2, "SEC-PLAT-B", "PlatB")
        resp = await client.get("/students", headers=headers_platform)
        assert resp.status_code == 200, resp.text
        assert "SEC-PLAT-B" in resp.text

        resp = await client.get(f"/students/{b_stu}", headers=headers_platform)
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_cannot_switch_to_school_you_do_not_belong_to(
        self, tenant_env, headers_a
    ):
        """Server-side membership gate: switching the active school to a
        campus the user is not a member of must fail."""
        client = tenant_env.client
        resp = await client.post(
            "/auth/schools/switch", json={"campus_id": 2}, headers=headers_a
        )
        assert resp.status_code in (403, 404), resp.text

    @pytest.mark.asyncio
    async def test_platform_context_allows_cross_tenant_link(
        self, tenant_env
    ):
        """Explicit platform authorization is the only path that may create
        a cross-campus guardian junction."""
        from app.domains.parent.service import ParentService
        from app.multi_tenant.models import TenantContext

        b_stu = await _seed_student(tenant_env.factory, 2, "SEC-PLATL-B", "PlatL")
        async with tenant_env.factory() as s:
            # Scoped parent service (campus 1) → denied.
            scoped = ParentService(s, TenantContext(campus_id=1))
            try:
                await scoped.link_child(9999, b_stu, "parent")
                raised = False
            except Exception:
                raised = True
            assert raised, "scoped parent linked a cross-campus student!"

            # Explicit platform context → allowed.
            platform = ParentService(
                s, TenantContext(user_id=1, platform=True)
            )
            linked = await platform.link_child(9999, b_stu, "parent")
            assert linked is not None

    @pytest.mark.asyncio
    async def test_audit_log_export_is_tenant_scoped(
        self, tenant_env, headers_a
    ):
        """A campus admin cannot export another campus's audit entries via
        the CSV export endpoint, even with a forged ``campus_id`` filter."""
        client = tenant_env.client
        await _seed_audit(
            tenant_env.factory, 2, "CREATE", "student", "SEC-EXP-AUD-B"
        )
        await _seed_audit(
            tenant_env.factory, 1, "CREATE", "student", "SEC-EXP-AUD-A"
        )

        resp = await client.get(
            "/api/admin/audit-logs/export",
            params={"campus_id": 2},
            headers=headers_a,
        )
        assert resp.status_code == 200, resp.text
        assert "SEC-EXP-AUD-B" not in resp.text
        assert "SEC-EXP-AUD-A" in resp.text
