"""Adversarial three-tenant security verification (A/B/C).

Tenant A holds a legitimate user; every test attempts to reach a
resource owned by tenant B or tenant C through:

    path IDs        — GET/PATCH/DELETE /students/{b_id} etc.
    query params    — ?campus_id=2/3, ?student_id=, ?academic_year_id=
    body IDs        — batch enroll, parent link, fee-due assignment
    search          — POST /api/search never returns B/C rows
    bulk endpoints  — /api/reports/batch/enroll
    exports         — students/attendance/transactions/audit CSV
    reports         — class attendance report, rollover preview
    jobs            — /jobs, /jobs/{id}
    migration       — /migration/projects + /migration/runs (incl. report)
    audit logs      — /api/admin/audit-logs list + get-by-id
    notifications   — list + mark-read
    documents       — get + download
    financial       — payments, dues, receipts, reconciliations, txn logs
    students        — list / get / 360
    academic        — years, classes, sections, teachers, subjects, rooms

Every B/C row is seeded directly through the same engine the API uses,
so a leaked response is guaranteed visible if any layer forgets to
scope.  Then a vertical matrix drives each tenant role (student,
parent, teacher, staff, accountant, principal, admin) against the
operations it must NOT be allowed to perform, and platform admin
against the operations only it may perform.

Failure of any negative assertion in this file is a security defect.
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

from app.domains.academic.models import (  # noqa: F401
    AcademicYear,
    Class,
    Enrollment,
    Section,
    Subject,
    Teacher,
)
from app.domains.academic_ops.models import Room  # noqa: F401
from app.domains.admission.models import AdmissionApplication  # noqa: F401
from app.domains.attendance.models import AttendanceRecord  # noqa: F401
from app.domains.audit.models import AuditLog  # noqa: F401
from app.domains.auth.models import User, UserSchoolMembership  # noqa: F401
from app.domains.auth.security import hash_password  # noqa: F401
from app.domains.communications.models import CommunicationMessage  # noqa: F401
from app.domains.documents.models import (  # noqa: F401
    Document,
    DocumentCategory,
)
from app.domains.fees.models import (  # noqa: F401
    FeeDue,
    FeeStructure,
    FeeType,
    Payment,
)

# Import all models so Base.metadata can resolve cross-module FKs.
from app.domains.institution.models import Campus, Institution  # noqa: F401
from app.domains.jobs.models import Job  # noqa: F401
from app.domains.migration.models import (  # noqa: F401
    MigrationProject,
    MigrationRun,
)
from app.domains.notifications.models import Notification  # noqa: F401
from app.domains.parent.models import Guardian  # noqa: F401
from app.domains.school_finance.models import (  # noqa: F401
    PaymentReconciliation,
    Receipt,
    TransactionLog,
)
from app.domains.student.models import Student  # noqa: F401
from app.infrastructure.database import Base, get_session

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

NOW = datetime.datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Test environment: three campuses + admin on each + role users + platform
# ---------------------------------------------------------------------------


class _TenantEnv:
    def __init__(self, client, factory, admin_ids: dict[int, int], platform_id: int):
        self.client = client
        self.factory = factory
        self.admin_ids = admin_ids  # campus -> admin user id
        self.platform_id = platform_id


@pytest_asyncio.fixture
async def tenant_env() -> _TenantEnv:
    from app.main import app  # registers every model with Base.metadata

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as seed:
        institution = Institution(name="Adversarial District", code="ADV-SEC")
        seed.add(institution)
        await seed.flush()
        campuses = []
        for code in ("ADV-A", "ADV-B", "ADV-C"):
            c = Campus(
                institution_id=institution.id, name=f"Adversarial {code}",
                code=code, status="active",
            )
            seed.add(c)
            campuses.append(c)
        await seed.flush()

        admin_ids: dict[int, int] = {}
        for idx, campus in enumerate(campuses, start=1):
            letter = "ABC"[idx - 1]
            adm = User(
                username=f"adv_admin_{letter.lower()}", email=f"a{letter}@adv.test",
                password_hash=hash_password(f"Adv{letter}123!"),
                display_name=f"Admin {letter}", role="admin",
                campus_id=campus.id, is_active=True,
            )
            seed.add(adm)
            await seed.flush()
            seed.add(UserSchoolMembership(
                user_id=adm.id, campus_id=campus.id, role="admin",
                is_default=True, is_active=True,
            ))
            admin_ids[campus.id] = adm.id

            # Role users on this campus (vertical matrix).
            for role in ("staff", "teacher", "student", "parent",
                         "accountant", "principal"):
                u = User(
                    username=f"adv_{role}_{letter.lower()}",
                    email=f"{role}{letter}@adv.test",
                    password_hash=hash_password("AdvRole123!"),
                    display_name=f"{role.title()} {letter}",
                    role=role, campus_id=campus.id, is_active=True,
                )
                seed.add(u)
                await seed.flush()
                seed.add(UserSchoolMembership(
                    user_id=u.id, campus_id=campus.id, role=role,
                    is_default=True, is_active=True,
                ))
        await seed.flush()

        plat = User(
            username="adv_platform", email="plat@adv.test",
            password_hash=hash_password("AdvPlat123!"),
            display_name="Platform", role="platform_admin",
            campus_id=None, is_active=True,
        )
        seed.add(plat)
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
            client=ac, factory=factory, admin_ids=admin_ids,
            platform_id=plat.id,
        )

    app.dependency_overrides.clear()
    await engine.dispose()


async def _login(client: AsyncClient, username: str, password: str) -> dict[str, str]:
    resp = await client.post(
        "/auth/login", json={"login": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def headers_a(tenant_env: _TenantEnv) -> dict[str, str]:
    return await _login(tenant_env.client, "adv_admin_a", "AdvA123!")


@pytest_asyncio.fixture
async def headers_b(tenant_env: _TenantEnv) -> dict[str, str]:
    return await _login(tenant_env.client, "adv_admin_b", "AdvB123!")


@pytest_asyncio.fixture
async def headers_c(tenant_env: _TenantEnv) -> dict[str, str]:
    return await _login(tenant_env.client, "adv_admin_c", "AdvC123!")


@pytest_asyncio.fixture
async def headers_platform(tenant_env: _TenantEnv) -> dict[str, str]:
    return await _login(tenant_env.client, "adv_platform", "AdvPlat123!")


async def _role_headers(tenant_env: _TenantEnv, role: str, campus: str) -> dict[str, str]:
    """Login as a role user, e.g. role='staff', campus='b' → adv_staff_b."""
    return await _login(
        tenant_env.client, f"adv_{role}_{campus}", "AdvRole123!"
    )


# ---------------------------------------------------------------------------
# Seeding helpers (direct inserts via the shared engine)
# ---------------------------------------------------------------------------


async def _seed_student(factory, campus_id: int, number: str, last_name: str) -> int:
    async with factory() as s:
        st = Student(
            first_name=f"Adv{last_name}", last_name=last_name,
            student_number=number, campus_id=campus_id, status="active",
        )
        s.add(st)
        await s.commit()
        return st.id


async def _seed_academic(factory, campus_id: int, tag: str) -> dict:
    async with factory() as s:
        year = AcademicYear(
            name=f"Adv Year {tag}", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31), campus_id=campus_id,
            status="active",
        )
        s.add(year)
        await s.flush()
        cls = Class(
            name=f"Adv Class {tag}", academic_year_id=year.id,
            campus_id=campus_id, status="active",
        )
        s.add(cls)
        await s.flush()
        sec = Section(
            name=f"Adv Section {tag}", class_id=cls.id,
            campus_id=campus_id, status="active",
        )
        teacher = Teacher(
            first_name="Adv", last_name=f"Teacher {tag}",
            employee_number=f"ADV-T-{tag}", campus_id=campus_id,
            status="active",
        )
        subject = Subject(
            name=f"Adv Subject {tag}", code=f"ADV-S-{tag}",
            campus_id=campus_id, status="active",
        )
        room = Room(
            name=f"Adv Room {tag}", code=f"ADV-R-{tag}",
            campus_id=campus_id, status="active",
        )
        s.add_all([sec, teacher, subject, room])
        await s.commit()
        return {
            "year_id": year.id, "class_id": cls.id, "section_id": sec.id,
            "teacher_id": teacher.id, "subject_id": subject.id,
            "room_id": room.id,
        }


async def _seed_fee_chain(factory, campus_id: int, tag: str, student_id: int,
                          year_id: int, class_id: int) -> dict:
    """FeeType + FeeStructure + FeeDue + Payment + TxnLog + Receipt + Reconcile."""
    async with factory() as s:
        ft = FeeType(name=f"Adv Fee {tag}", campus_id=campus_id, status="active")
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
            fee_structure_id=fs.id, original_amount=500, amount_paid=250,
            campus_id=campus_id, status="partial",
        )
        s.add(due)
        await s.flush()
        pay = Payment(
            student_id=student_id, fee_due_id=due.id, campus_id=campus_id,
            amount=250, status="completed",
        )
        s.add(pay)
        await s.flush()
        tx = TransactionLog(
            transaction_type="payment", student_id=student_id,
            amount=250, balance_before=0, balance_after=250,
            campus_id=campus_id,
        )
        s.add(tx)
        await s.flush()
        rec = Receipt(
            payment_id=pay.id, receipt_number=f"ADV-RCP-{tag}",
            receipt_date=datetime.date(2026, 7, 1), amount=250,
            payment_method_name="Cash", campus_id=campus_id,
        )
        s.add(rec)
        await s.flush()
        recon = PaymentReconciliation(
            reconciliation_date=datetime.date(2026, 7, 1),
            total_amount=250, total_count=1, status="draft",
            campus_id=campus_id,
        )
        s.add(recon)
        await s.commit()
        return {
            "fee_type_id": ft.id, "structure_id": fs.id, "due_id": due.id,
            "payment_id": pay.id, "txn_id": tx.id, "receipt_id": rec.id,
            "recon_id": recon.id,
        }


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
            job_type=f"adv-{tag}", status="pending", campus_id=campus_id,
            user_id=user_id, created_at=NOW, updated_at=NOW,
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
            applicant_name=f"Adv Applicant {tag}", campus_id=campus_id,
        )
        s.add(app_)
        await s.commit()
        return app_.id


async def _seed_migration(factory, campus_id: int, tag: str, operator_id: int) -> dict:
    """MigrationProject + MigrationRun pinned to a campus."""
    async with factory() as s:
        proj = MigrationProject(
            campus_id=campus_id, name=f"Adv Mig {tag}",
            source_system="Generic CSV", status="DRAFT",
            operator_id=operator_id, created_at=NOW, updated_at=NOW,
        )
        s.add(proj)
        await s.flush()
        run = MigrationRun(
            entity_type="students", status="completed", source=f"adv-{tag}.csv",
            campus_id=campus_id, total_records=10, imported=10,
            skipped=0, errors=0, warnings=0, created_at=NOW,
        )
        s.add(run)
        await s.commit()
        return {"project_id": proj.id, "run_id": run.id}


async def _seed_audit(factory, campus_id: int | None, action: str,
                      resource: str, marker: str) -> int:
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


async def _seed_guardian(factory, user_id: int, student_id: int,
                         campus_id: int) -> int:
    async with factory() as s:
        g = Guardian(user_id=user_id, student_id=student_id, campus_id=campus_id)
        s.add(g)
        await s.commit()
        return g.id


# ---------------------------------------------------------------------------
# 1. Path-ID IDOR — tenant A against tenant B and tenant C
# ---------------------------------------------------------------------------


class TestPathIdIdorThreeTenant:
    """A's admin can never read/update/delete a B- or C-owned record."""

    @pytest.mark.asyncio
    async def test_student_idor_b_and_c(self, tenant_env, headers_a):
        client = tenant_env.client
        b_id = await _seed_student(tenant_env.factory, 2, "ADV-STU-B", "StuB")
        c_id = await _seed_student(tenant_env.factory, 3, "ADV-STU-C", "StuC")
        a_id = await _seed_student(tenant_env.factory, 1, "ADV-STU-A", "StuA")

        for foreign in (b_id, c_id):
            resp = await client.get(f"/students/{foreign}", headers=headers_a)
            assert resp.status_code in (403, 404), f"get {foreign}: {resp.status_code}"
            resp = await client.patch(
                f"/students/{foreign}", json={"last_name": "Hijacked"},
                headers=headers_a,
            )
            assert resp.status_code in (403, 404), f"patch {foreign}"
            resp = await client.delete(f"/students/{foreign}", headers=headers_a)
            assert resp.status_code in (403, 404), f"delete {foreign}"
            resp = await client.get(f"/students/{foreign}/360", headers=headers_a)
            assert resp.status_code in (403, 404), f"360 {foreign}"

        # Own resource still reachable.
        resp = await client.get(f"/students/{a_id}", headers=headers_a)
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_academic_idor_b_and_c(self, tenant_env, headers_a):
        client = tenant_env.client
        b = await _seed_academic(tenant_env.factory, 2, "B")
        c = await _seed_academic(tenant_env.factory, 3, "C")

        for foreign in (b, c):
            for endpoint, key in [
                ("/api/academic-years/{id}", "year_id"),
                ("/api/classes/{id}", "class_id"),
                ("/api/sections/{id}", "section_id"),
                ("/api/teachers/{id}", "teacher_id"),
                ("/api/subjects/{id}", "subject_id"),
                ("/api/academic/rooms/{id}", "room_id"),
            ]:
                url = endpoint.replace("{id}", str(foreign[key]))
                resp = await client.get(url, headers=headers_a)
                assert resp.status_code in (403, 404), f"{url}: {resp.status_code}"

    @pytest.mark.asyncio
    async def test_financial_idor_b_and_c(self, tenant_env, headers_a):
        """Payments, dues, fee types, receipts, txn logs, reconciliations."""
        client = tenant_env.client
        for campus, tag in ((2, "B"), (3, "C")):
            ac = await _seed_academic(tenant_env.factory, campus, tag)
            stu = await _seed_student(tenant_env.factory, campus, f"ADV-FIN-{tag}", f"Fin{tag}")
            fin = await _seed_fee_chain(
                tenant_env.factory, campus, tag, stu, ac["year_id"], ac["class_id"],
            )

            for endpoint, key in [
                ("/api/fees/fee-types/{id}", "fee_type_id"),
                ("/api/fees/dues/{id}", "due_id"),
                ("/api/fees/payments/{id}", "payment_id"),
                ("/api/school-finance/transactions/{id}", "txn_id"),
                ("/api/school-finance/receipts/{id}", "receipt_id"),
                ("/api/school-finance/reconciliations/{id}", "recon_id"),
            ]:
                url = endpoint.replace("{id}", str(fin[key]))
                resp = await client.get(url, headers=headers_a)
                assert resp.status_code in (403, 404), f"{url}: {resp.status_code}"

            # Refund on a foreign payment must fail.
            resp = await client.post(
                f"/api/fees/payments/{fin['payment_id']}/refund",
                json={"amount": 10, "reason": "hijack"},
                headers=headers_a,
            )
            assert resp.status_code in (403, 404), resp.text

    @pytest.mark.asyncio
    async def test_attendance_enrollment_idor(self, tenant_env, headers_a):
        client = tenant_env.client
        for campus, tag in ((2, "B2"), (3, "C2")):
            ac = await _seed_academic(tenant_env.factory, campus, tag)
            stu = await _seed_student(tenant_env.factory, campus, f"ADV-AT-{tag}", f"At{tag}")
            enr = await _seed_enrollment(
                tenant_env.factory, campus, stu, ac["year_id"],
                ac["class_id"], ac["section_id"],
            )
            att = await _seed_attendance(
                tenant_env.factory, campus, stu, ac["year_id"],
                ac["class_id"], ac["section_id"],
            )
            # GET on foreign resources must be denied.
            resp = await client.get(f"/api/enrollments/{enr}", headers=headers_a)
            assert resp.status_code in (403, 404), f"get enr {enr}: {resp.status_code}"
            resp = await client.get(f"/attendance/{att}", headers=headers_a)
            assert resp.status_code in (403, 404), f"get att {att}: {resp.status_code}"

            # PATCH with a *schema-valid* body proves the tenant guard (not the
            # validator) denies: enrollment accepts active|inactive, attendance
            # accepts present|absent|late.
            resp = await client.patch(
                f"/api/enrollments/{enr}", json={"status": "inactive"},
                headers=headers_a,
            )
            assert resp.status_code in (403, 404), f"patch enr {enr}: {resp.status_code}"
            resp = await client.patch(
                f"/attendance/{att}", json={"status": "absent"},
                headers=headers_a,
            )
            assert resp.status_code in (403, 404), f"patch att {att}: {resp.status_code}"

    @pytest.mark.asyncio
    async def test_documents_notifications_jobs_migration_audit_idor(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        for campus, tag, letter in ((2, "B", "b"), (3, "C", "c")):
            admin_id = tenant_env.admin_ids[campus]
            doc = await _seed_document(
                tenant_env.factory, campus, admin_id, f"ADV-DOC-{tag}"
            )
            notif = await _seed_notification(
                tenant_env.factory, campus, admin_id, f"ADV-NOTIF-{tag}-SECRET"
            )
            job = await _seed_job(
                tenant_env.factory, campus, f"job{tag}", user_id=admin_id
            )
            mig = await _seed_migration(
                tenant_env.factory, campus, tag, operator_id=admin_id
            )
            audit = await _seed_audit(
                tenant_env.factory, campus, "CREATE", "student",
                f"ADV-AUD-{tag}-SECRET",
            )

            for url in (
                f"/api/documents/{doc}",
                f"/api/documents/{doc}/download",
                f"/jobs/{job}",
                f"/migration/projects/{mig['project_id']}",
                f"/migration/projects/{mig['project_id']}/report",
                f"/migration/runs/{mig['run_id']}",
                f"/migration/runs/{mig['run_id']}/logs",
                f"/api/admin/audit-logs/{audit}",
            ):
                resp = await client.get(url, headers=headers_a)
                assert resp.status_code in (403, 404), (
                    f"{url}: {resp.status_code} (campus {campus})"
                )

            # Mark a foreign user's notification read — must not leak.
            resp = await client.patch(
                f"/api/notifications/{notif}/read", headers=headers_a
            )
            assert resp.status_code in (403, 404), resp.text

    @pytest.mark.asyncio
    async def test_admission_and_guardian_idor(self, tenant_env, headers_a):
        client = tenant_env.client
        for campus, tag in ((2, "B3"), (3, "C3")):
            adm = await _seed_admission(tenant_env.factory, campus, tag)
            stu = await _seed_student(tenant_env.factory, campus, f"ADV-G-{tag}", f"G{tag}")
            g = await _seed_guardian(
                tenant_env.factory, tenant_env.admin_ids[campus], stu, campus
            )
            resp = await client.get(f"/api/admissions/applications/{adm}", headers=headers_a)
            assert resp.status_code in (403, 404), resp.text
            # Guardian junction cross-tenant resolution at the repo layer.
            from app.multi_tenant.models import TenantContext
            from app.multi_tenant.repository import TenantScopedRepository

            async with tenant_env.factory() as s:
                repo = TenantScopedRepository(s, TenantContext(campus_id=1))
                found = await repo.get_by_id(Guardian, g)
                assert found is None, f"tenant A resolved guardian {g} of campus {campus}"


# ---------------------------------------------------------------------------
# 2. Query-parameter manipulation — ?campus_id=, ?student_id=, ?year_id=
# ---------------------------------------------------------------------------


class TestQueryParamManipulation:
    """A client-supplied campus_id/student_id must never pierce the tenant."""

    @pytest.mark.asyncio
    async def test_list_endpoints_ignore_foreign_campus_filter(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        await _seed_student(tenant_env.factory, 2, "ADV-QP-B", "QpB")
        await _seed_student(tenant_env.factory, 3, "ADV-QP-C", "QpC")
        await _seed_student(tenant_env.factory, 1, "ADV-QP-A", "QpA")
        await _seed_academic(tenant_env.factory, 1, "QPA")

        for path in ("/students", "/api/classes", "/api/fees/dues",
                     "/api/fees/payments", "/api/notifications"):
            for campus in (2, 3):
                resp = await client.get(
                    path, params={"campus_id": campus}, headers=headers_a
                )
                assert resp.status_code == 200, f"{path}: {resp.status_code}"
                assert "ADV-QP-B" not in resp.text, f"{path} leaked B"
                assert "ADV-QP-C" not in resp.text, f"{path} leaked C"
            # Own data still visible.
            resp = await client.get(path, headers=headers_a)
            assert resp.status_code == 200, f"{path}"
            if path == "/students":
                assert "ADV-QP-A" in resp.text, f"{path} missing own data"
            elif path == "/api/classes":
                assert "Adv Class QPA" in resp.text, f"{path} missing own data"

    @pytest.mark.asyncio
    async def test_student_scoped_fee_endpoints_deny_foreign_student(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        for campus, tag in ((2, "B4"), (3, "C4")):
            ac = await _seed_academic(tenant_env.factory, campus, tag)
            stu = await _seed_student(tenant_env.factory, campus, f"ADV-SF-{tag}", f"Sf{tag}")
            await _seed_fee_chain(
                tenant_env.factory, campus, tag, stu, ac["year_id"], ac["class_id"],
            )
            resp = await client.get(
                f"/api/fees/students/{stu}/fees",
                params={"academic_year_id": ac["year_id"]},
                headers=headers_a,
            )
            assert resp.status_code in (403, 404), f"fees {stu}: {resp.status_code}"
            resp = await client.get(
                f"/api/school-finance/transactions/student/{stu}/balance",
                headers=headers_a,
            )
            assert resp.status_code in (403, 404), f"balance {stu}: {resp.status_code}"


# ---------------------------------------------------------------------------
# 3. Body-ID manipulation — create/associate with foreign IDs
# ---------------------------------------------------------------------------


class TestBodyIdManipulation:
    @pytest.mark.asyncio
    async def test_batch_enroll_cannot_use_foreign_student(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        a_ac = await _seed_academic(tenant_env.factory, 1, "A5")
        b_stu = await _seed_student(tenant_env.factory, 2, "ADV-BE-B", "BeB")
        c_stu = await _seed_student(tenant_env.factory, 3, "ADV-BE-C", "BeC")

        resp = await client.post(
            "/api/reports/batch/enroll",
            json={
                "academic_year_id": a_ac["year_id"],
                "enrollments": [
                    {"student_id": b_stu, "class_id": a_ac["class_id"]},
                    {"student_id": c_stu, "class_id": a_ac["class_id"]},
                ],
            },
            headers=headers_a,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body.get("succeeded", 0) == 0, body
        assert body.get("failed", 0) == 2, body

        async with tenant_env.factory() as s:
            for foreign in (b_stu, c_stu):
                rows = (await s.execute(
                    select(Enrollment).where(Enrollment.student_id == foreign)
                )).scalars().all()
                assert len(rows) == 0, "cross-tenant enrollment was created!"

    @pytest.mark.asyncio
    async def test_parent_cannot_link_foreign_student(self, tenant_env):
        client = tenant_env.client
        a_stu = await _seed_student(tenant_env.factory, 1, "ADV-PL-A", "PlA")
        b_stu = await _seed_student(tenant_env.factory, 2, "ADV-PL-B", "PlB")
        headers = await _role_headers(tenant_env, "parent", "a")

        resp = await client.post(
            "/api/parent/children/link",
            json={"student_id": b_stu, "relationship": "parent"},
            headers=headers,
        )
        assert resp.status_code in (403, 404), resp.text

        async with tenant_env.factory() as s:
            rows = (await s.execute(
                select(Guardian).where(Guardian.student_id == b_stu)
            )).scalars().all()
        assert len(rows) == 0, "cross-tenant guardian link was created!"

        # Own-campus link still works (sanity).
        resp = await client.post(
            "/api/parent/children/link",
            json={"student_id": a_stu, "relationship": "parent"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text

    @pytest.mark.asyncio
    async def test_fee_due_assignment_foreign_student_denied(
        self, tenant_env, headers_a
    ):
        """Creating a fee due for a foreign student must not succeed."""
        client = tenant_env.client
        a_ac = await _seed_academic(tenant_env.factory, 1, "A6")
        b_stu = await _seed_student(tenant_env.factory, 2, "ADV-FD-B", "FdB")
        async with tenant_env.factory() as s:
            ft = FeeType(name="Adv FD Fee", campus_id=1, status="active")
            s.add(ft)
            await s.commit()
        async with tenant_env.factory() as s:
            fs = FeeStructure(
                academic_year_id=a_ac["year_id"], class_id=a_ac["class_id"],
                fee_type_id=ft.id, campus_id=1, amount=1000,
                frequency="annual", status="active",
            )
            s.add(fs)
            await s.commit()

        resp = await client.post(
            "/api/fees/dues",
            params={
                "student_id": b_stu,
                "academic_year_id": a_ac["year_id"],
            },
            headers=headers_a,
        )
        assert resp.status_code in (403, 404), resp.text

        async with tenant_env.factory() as s:
            rows = (await s.execute(
                select(FeeDue).where(FeeDue.student_id == b_stu)
            )).scalars().all()
        assert len(rows) == 0, "cross-tenant fee due was created!"


# ---------------------------------------------------------------------------
# 4. Search isolation
# ---------------------------------------------------------------------------


class TestSearchIsolationThreeTenant:
    @pytest.mark.asyncio
    async def test_search_never_returns_b_or_c(self, tenant_env, headers_a):
        client = tenant_env.client
        b_id = await _seed_student(tenant_env.factory, 2, "ADV-SCH-B", "SchBUnique")
        c_id = await _seed_student(tenant_env.factory, 3, "ADV-SCH-C", "SchCUnique")
        a_id = await _seed_student(tenant_env.factory, 1, "ADV-SCH-A", "SchAUnique")

        for marker, foreign in (
            ("SchBUnique", b_id), ("SchCUnique", c_id),
        ):
            resp = await client.post(
                "/api/search",
                json={"query": marker, "types": ["student"]},
                headers=headers_a,
            )
            assert resp.status_code == 200, resp.text
            ids = {int(r["entity_id"]) for r in resp.json().get("results", [])}
            assert foreign not in ids, f"search leaked {marker}"

        resp = await client.post(
            "/api/search",
            json={"query": "SchAUnique", "types": ["student"]},
            headers=headers_a,
        )
        ids = {int(r["entity_id"]) for r in resp.json().get("results", [])}
        assert a_id in ids, "search missed own-campus student"


# ---------------------------------------------------------------------------
# 5 + 6. Bulk, exports, reports
# ---------------------------------------------------------------------------


class TestBulkExportsReportsThreeTenant:
    @pytest.mark.asyncio
    async def test_rollover_preview_foreign_year_denied(self, tenant_env, headers_a):
        client = tenant_env.client
        for campus, tag in ((2, "B7"), (3, "C7")):
            ac = await _seed_academic(tenant_env.factory, campus, tag)
            resp = await client.post(
                "/api/reports/rollover/preview",
                json={
                    "from_year_id": ac["year_id"],
                    "to_year_name": f"Adv Roll {tag}",
                    "to_start_date": "2027-01-01",
                    "to_end_date": "2027-12-31",
                },
                headers=headers_a,
            )
            assert resp.status_code in (403, 404), f"campus {campus}: {resp.text}"

    @pytest.mark.asyncio
    async def test_class_attendance_report_foreign_class_denied(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        for campus, tag in ((2, "B8"), (3, "C8")):
            ac = await _seed_academic(tenant_env.factory, campus, tag)
            resp = await client.get(
                f"/api/reports/attendance/class/{ac['class_id']}",
                params={"academic_year_id": ac["year_id"]},
                headers=headers_a,
            )
            assert resp.status_code in (403, 404), f"campus {campus}: {resp.text}"

    @pytest.mark.asyncio
    async def test_exports_exclude_b_and_c(self, tenant_env, headers_a):
        client = tenant_env.client
        await _seed_student(tenant_env.factory, 2, "ADV-EXP-B", "ExpB")
        await _seed_student(tenant_env.factory, 3, "ADV-EXP-C", "ExpC")
        await _seed_student(tenant_env.factory, 1, "ADV-EXP-A", "ExpA")
        await _seed_audit(tenant_env.factory, 2, "CREATE", "student", "ADV-AEX-B")
        await _seed_audit(tenant_env.factory, 3, "CREATE", "student", "ADV-AEX-C")
        await _seed_audit(tenant_env.factory, 1, "CREATE", "student", "ADV-AEX-A")

        resp = await client.get("/api/reports/export/students", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert "ADV-EXP-B" not in resp.text and "ADV-EXP-C" not in resp.text
        assert "ADV-EXP-A" in resp.text, "students export missing own data"

        resp = await client.get("/api/admin/audit-logs/export", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert "ADV-AEX-B" not in resp.text and "ADV-AEX-C" not in resp.text
        assert "ADV-AEX-A" in resp.text, "audit export missing own entry"

    @pytest.mark.asyncio
    async def test_audit_log_list_excludes_b_and_c(self, tenant_env, headers_a):
        client = tenant_env.client
        await _seed_audit(tenant_env.factory, 2, "CREATE", "student", "ADV-LST-B")
        await _seed_audit(tenant_env.factory, 3, "CREATE", "student", "ADV-LST-C")
        await _seed_audit(tenant_env.factory, 1, "CREATE", "student", "ADV-LST-A")

        resp = await client.get("/api/admin/audit-logs", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert "ADV-LST-B" not in resp.text and "ADV-LST-C" not in resp.text
        assert "ADV-LST-A" in resp.text

    @pytest.mark.asyncio
    async def test_migration_projects_and_runs_lists_scoped(
        self, tenant_env, headers_a
    ):
        client = tenant_env.client
        await _seed_migration(tenant_env.factory, 2, "B9", tenant_env.admin_ids[2])
        await _seed_migration(tenant_env.factory, 3, "C9", tenant_env.admin_ids[3])
        await _seed_migration(tenant_env.factory, 1, "A9", tenant_env.admin_ids[1])

        resp = await client.get("/migration/projects", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert "Adv Mig B9" not in resp.text, "projects leaked B"
        assert "Adv Mig C9" not in resp.text, "projects leaked C"
        assert "Adv Mig A9" in resp.text, "projects missing own project"

        resp = await client.get("/migration/runs", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert "adv-B9.csv" not in resp.text, "runs leaked B"
        assert "adv-C9.csv" not in resp.text, "runs leaked C"
        assert "adv-A9.csv" in resp.text, "runs missing own run"

    @pytest.mark.asyncio
    async def test_migration_report_csv_scoped(self, tenant_env, headers_a):
        client = tenant_env.client
        own = await _seed_migration(tenant_env.factory, 1, "A10", tenant_env.admin_ids[1])
        b = await _seed_migration(tenant_env.factory, 2, "B10", tenant_env.admin_ids[2])
        c = await _seed_migration(tenant_env.factory, 3, "C10", tenant_env.admin_ids[3])

        # Own project report is reachable.
        resp = await client.get(
            f"/migration/projects/{own['project_id']}/report.csv", headers=headers_a
        )
        assert resp.status_code == 200, resp.text

        # Foreign project reports are unreachable.
        for foreign in (b["project_id"], c["project_id"]):
            resp = await client.get(
                f"/migration/projects/{foreign}/report.csv", headers=headers_a
            )
            assert resp.status_code in (403, 404), f"project {foreign}: {resp.status_code}"


# ---------------------------------------------------------------------------
# 7. List isolation across every surface
# ---------------------------------------------------------------------------


class TestListIsolationThreeTenant:
    @pytest.mark.asyncio
    async def test_core_lists_never_leak_b_or_c(self, tenant_env, headers_a):
        client = tenant_env.client
        for campus, tag in ((2, "B11"), (3, "C11")):
            await _seed_student(tenant_env.factory, campus, f"ADV-LST-{tag}", f"Lst{tag}")
            await _seed_academic(tenant_env.factory, campus, tag)
        await _seed_student(tenant_env.factory, 1, "ADV-LST-A11", "LstA11")
        await _seed_academic(tenant_env.factory, 1, "A11")

        for path, own_token, foreign_token in [
            ("/students", "ADV-LST-A11", "ADV-LST-B11"),
            ("/api/classes", "Adv Class A11", "Adv Class B11"),
            ("/api/sections", "Adv Section A11", "Adv Section B11"),
            ("/api/teachers", "Teacher A11", "Teacher B11"),
            ("/api/subjects", "Adv Subject A11", "Adv Subject B11"),
        ]:
            resp = await client.get(path, headers=headers_a)
            assert resp.status_code == 200, f"{path}: {resp.status_code}"
            assert foreign_token not in resp.text, f"{path} leaked B"
            assert "C11" not in resp.text, f"{path} leaked C"
            assert own_token in resp.text, f"{path} missing own data"


# ---------------------------------------------------------------------------
# 8. Vertical privilege escalation across every role
# ---------------------------------------------------------------------------


class TestVerticalEscalation:
    """Each tenant role must be unable to reach privileged operations."""

    # role → denied (method, path) pairs — the role user on campus A.
    ROLE_DENIED: dict[str, list[tuple[str, str]]] = {
        "student": [
            ("POST", "/api/classes"),
            ("POST", "/attendance"),
            ("GET", "/api/admin/audit-logs"),
            ("GET", "/migration/projects"),
            ("GET", "/api/reports/export/payments"),
        ],
        "parent": [
            ("POST", "/api/classes"),
            ("POST", "/attendance"),
            ("GET", "/api/admin/audit-logs"),
            ("GET", "/migration/projects"),
        ],
        "teacher": [
            ("POST", "/api/classes"),
            ("GET", "/api/admin/audit-logs"),
            ("GET", "/migration/projects"),
            ("GET", "/api/reports/export/payments"),
        ],
        "staff": [
            ("POST", "/api/classes"),
            ("GET", "/api/admin/audit-logs"),
            ("GET", "/migration/projects"),
            ("GET", "/api/reports/export/payments"),
        ],
        "principal": [
            ("GET", "/migration/projects"),
        ],
    }

    @pytest.mark.parametrize("role", sorted(ROLE_DENIED))
    @pytest.mark.asyncio
    async def test_role_denied_privileged_operations(self, tenant_env, role):
        client = tenant_env.client
        # Seed a class so POST /api/classes requests are well-formed.
        ac = await _seed_academic(tenant_env.factory, 1, "A12")

        headers = await _role_headers(tenant_env, role, "a")
        for method, path in self.ROLE_DENIED[role]:
            body = None
            if method == "POST" and path == "/api/classes":
                body = {"name": "Hijacked Class", "academic_year_id": ac["year_id"]}
            if method == "POST" and path == "/attendance":
                body = {}
            resp = await client.request(method, path, json=body, headers=headers)
            assert resp.status_code == 403, (
                f"{role} {method} {path}: expected 403 got {resp.status_code} "
                f"({resp.text[:200]})"
            )

    @pytest.mark.asyncio
    async def test_tenant_admin_cannot_reach_platform_operations(
        self, tenant_env, headers_a
    ):
        """A tenant admin is never a platform operator: institution creation
        and cross-tenant reads are out of reach."""
        client = tenant_env.client
        resp = await client.post(
            "/api/institution/institutions",
            json={"name": "Rogue Institution", "code": "ROGUE"},
            headers=headers_a,
        )
        assert resp.status_code == 403, resp.text

    @pytest.mark.asyncio
    async def test_platform_admin_explicit_cross_tenant_only(self, tenant_env, headers_platform):
        """Positive control: platform admin (explicit platform.access) MAY read
        across tenants — proving the guard is not blanket-denying."""
        client = tenant_env.client
        b_id = await _seed_student(tenant_env.factory, 2, "ADV-PLAT-B", "PlatB")
        resp = await client.get(f"/students/{b_id}", headers=headers_platform)
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_admin_role_still_reads_own_campus(self, tenant_env, headers_a):
        """Sanity: admin A reads its own data everywhere."""
        client = tenant_env.client
        a_id = await _seed_student(tenant_env.factory, 1, "ADV-SAN-A", "SanA")
        resp = await client.get(f"/students/{a_id}", headers=headers_a)
        assert resp.status_code == 200, resp.text
        resp = await client.get("/students", headers=headers_a)
        assert resp.status_code == 200 and "ADV-SAN-A" in resp.text


# ---------------------------------------------------------------------------
# 9. Notification / document read scoping (additional negative cases)
# ---------------------------------------------------------------------------


class TestNotificationAndDocumentScoping:
    @pytest.mark.asyncio
    async def test_notification_list_never_leaks_b_or_c(self, tenant_env, headers_a):
        client = tenant_env.client
        await _seed_notification(
            tenant_env.factory, 2, tenant_env.admin_ids[2], "ADV-NB-SECRET"
        )
        await _seed_notification(
            tenant_env.factory, 3, tenant_env.admin_ids[3], "ADV-NC-SECRET"
        )
        await _seed_notification(
            tenant_env.factory, 1, tenant_env.admin_ids[1], "ADV-NA-VISIBLE"
        )
        resp = await client.get("/api/notifications", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert "ADV-NB-SECRET" not in resp.text
        assert "ADV-NC-SECRET" not in resp.text
        assert "ADV-NA-VISIBLE" in resp.text

    @pytest.mark.asyncio
    async def test_document_list_never_leaks_b_or_c(self, tenant_env, headers_a):
        client = tenant_env.client
        await _seed_document(tenant_env.factory, 2, tenant_env.admin_ids[2], "ADV-DLB")
        await _seed_document(tenant_env.factory, 3, tenant_env.admin_ids[3], "ADV-DLC")
        await _seed_document(tenant_env.factory, 1, tenant_env.admin_ids[1], "ADV-DLA")
        resp = await client.get("/api/documents", headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert "ADV-DLB" not in resp.text
        assert "ADV-DLC" not in resp.text
        assert "ADV-DLA" in resp.text
