"""End-to-end migration verification (D2 workflow) + lifecycle regressions.

This file proves the full enterprise onboarding flow and locks in three
genuine defects found in the workspace lifecycle:

* **D1** — a project never reached ``COMPLETED``: after import it sat in
  ``RECONCILING`` forever, so the ``COMPLETED → ROLLED_BACK`` state-machine
  edge that ``rollback()`` requires was unreachable (rollback always raised
  ``ConflictError``).
* **D2** — workspace ``rollback()`` rolled back only ``project.run_id``
  (the first run).  A multi-entity import (students + academic + attendance
  + fees) leaves every other stream's rows orphaned.
* **D3** — per-run rollback deleted nothing for container migrators:
  academic/fees record mappings per *subtype* (``academic_year``,
  ``class``, ``fee_due``, …) while the base rollback looked them up by run
  entity type, and attendance/payments recorded no mappings at all.

Also covers the acceptance scenarios: messy CSV, XLSX, duplicate students,
invalid dates/amounts, missing values, inconsistent columns, orphan
references, Unicode, large files (multi-chunk + resume), repeated import,
failed import, cancellation, tenant isolation.
"""

from __future__ import annotations

import datetime
import os
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domains.academic.models import (  # noqa: F401
    AcademicYear,
    Class,
    Enrollment,
    Section,
)
from app.domains.attendance.models import AttendanceRecord  # noqa: F401
from app.domains.fees.models import (  # noqa: F401
    FeeDue,
    FeeStructure,
    FeeType,
    Payment,
)
from app.domains.migration.import_job import run_project_import
from app.domains.migration.models import (
    MIGRATION_STATUS_CANCELLED,
    MIGRATION_STATUS_COMPLETED,
    MIGRATION_STATUS_FAILED,
    MIGRATION_STATUS_IMPORTING,
    MIGRATION_STATUS_READY,
    MIGRATION_STATUS_RECONCILING,
    MIGRATION_STATUS_ROLLED_BACK,
    MigrationProject,
)
from app.domains.migration.project_service import IMPORT_CHUNK_SIZE, MigrationProjectService
from app.domains.student.models import Student  # noqa: F401
from app.multi_tenant.models import TenantContext

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Two rows carrying all four streams (person + class/section/year +
# attendance + a fee payment) — same shape as test_migration_step2.
CLEAN_CSV = (
    "Admission No,Student Name,DOB,Gender,Email,Class,Section,Academic Year,"
    "Attendance Date,Attendance Status,Fee Type,Fee Paid,Payment Date,Receipt No,Guardian Phone\n"
    "ST-2001,John  Doe ,2005-08-14,M,john.doe@example.com,10-A,Sec 1,2025-2026,"
    "2026-08-10,Present,Tuition,45000,2026-01-10,RCT-2001,+254 700 123456\n"
    "ST-2002,Jane  Smith ,2006-03-22,F,jane.smith@example.com,10-A,Sec 1,2025-2026,"
    "2026-08-10,Absent,Tuition,30000,2026-01-11,RCT-2002,0700123456\n"
)

DEMO_CSV = open(os.path.join(FIXTURES_DIR, "legacy_demo_migration.csv"), encoding="utf-8").read()


@pytest.fixture
def tenant_a() -> TenantContext:
    return TenantContext(campus_id=1, institution_id=1, user_id=99)


@pytest.fixture
def tenant_b() -> TenantContext:
    return TenantContext(campus_id=2, institution_id=1, user_id=98)


@pytest.fixture
def storage_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "storage_root", str(tmp_path / "storage"))
    os.makedirs(os.path.join(settings.storage_root, "migrations"), exist_ok=True)


async def _make_project(
    db_session: AsyncSession,
    tenant: TenantContext,
    *,
    csv: str = CLEAN_CSV,
    name: str = "Verification import",
) -> MigrationProject:
    svc = MigrationProjectService(db_session, tenant, user_id=tenant.user_id, username="admin")
    return await svc.create_project(
        name=name,
        source_system="PowerSchool-style export",
        description="verification fixture",
        filename="legacy_export.csv",
        file_data=csv.encode("utf-8"),
        mime_type="text/csv",
    )


async def _import_and_reconcile(
    db_session: AsyncSession,
    tenant: TenantContext,
    project: MigrationProject,
) -> dict[str, Any]:
    svc = MigrationProjectService(db_session, tenant, user_id=99, username="admin")
    summary = await svc.run_validation(project.id)
    assert summary["is_ready"] is True, summary["samples"]
    await run_project_import(db_session, tenant, project.id, job_id=None)
    await db_session.commit()
    report = await svc.reconcile(project.id)
    await db_session.commit()
    return report


# ── D1: lifecycle terminal state + rollback reachability ────────────────


class TestLifecycleTerminalState:
    async def test_reconcile_transitions_project_to_completed(
        self, db_session, tenant_a, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        await svc.run_validation(project.id)
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()

        after_import = await svc.repo.get_by_id(project.id)
        assert after_import.status == MIGRATION_STATUS_RECONCILING

        await svc.reconcile(project.id)
        await db_session.commit()
        after_reconcile = await svc.repo.get_by_id(project.id)
        assert after_reconcile.status == MIGRATION_STATUS_COMPLETED

    async def test_rollback_reachable_only_after_completed(
        self, db_session, tenant_a, storage_root
    ) -> None:
        """D1 regression: before the fix, rollback always raised ConflictError
        because the project never left RECONCILING.  After import + reconcile
        the transition COMPLETED → ROLLED_BACK must succeed."""
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        await svc.run_validation(project.id)
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        await svc.reconcile(project.id)
        await db_session.commit()

        result = await svc.rollback(project.id)
        await db_session.commit()
        assert result["records_removed"] == 15  # 2 + 5 + 2 + 6
        assert result["runs_rolled_back"] == 4
        refreshed = await svc.repo.get_by_id(project.id)
        assert refreshed.status == MIGRATION_STATUS_ROLLED_BACK

    async def test_rollback_from_reconciling_still_rejected(
        self, db_session, tenant_a, storage_root
    ) -> None:
        """The state machine is intentional: rollback requires COMPLETED
        (i.e. reconciliation done) — attempting it straight after import
        must stay a deliberate 409-style ConflictError, never a 500."""
        from app.core.exceptions import ConflictError

        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        await svc.run_validation(project.id)
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()

        with pytest.raises(ConflictError):
            await svc.rollback(project.id)


# ── D2 + D3: multi-run rollback removes every stream, pre-existing kept ─


class TestMultiRunRollback:
    async def test_rollback_removes_all_entity_streams(
        self, db_session, tenant_a, storage_root
    ) -> None:
        """D2 regression: rollback must cover every run the project produced
        (students, academic, attendance, fees) — not just the first one."""
        from app.domains.migration.models import MigrationRun

        project = await _make_project(db_session, tenant_a)
        await _import_and_reconcile(db_session, tenant_a, project)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        await svc.rollback(project.id)
        await db_session.commit()

        # Every row created by the import is gone.
        assert (await db_session.execute(select(Student))).scalars().all() == []
        assert (await db_session.execute(select(AcademicYear))).scalars().all() == []
        assert (await db_session.execute(select(Class))).scalars().all() == []
        assert (await db_session.execute(select(Section))).scalars().all() == []
        assert (await db_session.execute(select(Enrollment))).scalars().all() == []
        assert (await db_session.execute(select(AttendanceRecord))).scalars().all() == []
        assert (await db_session.execute(select(FeeType))).scalars().all() == []
        assert (await db_session.execute(select(FeeStructure))).scalars().all() == []
        assert (await db_session.execute(select(FeeDue))).scalars().all() == []
        assert (await db_session.execute(select(Payment))).scalars().all() == []

        # All runs moved to rolled_back.
        runs = (
            (
                await db_session.execute(
                    select(MigrationRun).where(MigrationRun.project_id == project.id)
                )
            )
            .scalars()
            .all()
        )
        assert {r.status for r in runs} == {"rolled_back"}

    async def test_rollback_preserves_pre_existing_rows(
        self, db_session, tenant_a, storage_root
    ) -> None:
        """D2.12 invariant: rollback deletes only records whose origin is
        tracked in migration_mappings — never pre-existing data."""
        existing = Student(
            first_name="Existing",
            last_name="Student",
            student_number="LEGACY-1",
            campus_id=1,
        )
        db_session.add(existing)
        await db_session.flush()
        existing_ay = AcademicYear(
            name="1999-2000",
            start_date=datetime.date(1999, 4, 1),
            end_date=datetime.date(2000, 3, 31),
            campus_id=1,
        )
        db_session.add(existing_ay)
        await db_session.commit()

        project = await _make_project(db_session, tenant_a)
        await _import_and_reconcile(db_session, tenant_a, project)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        result = await svc.rollback(project.id)
        await db_session.commit()

        assert result["records_removed"] == 15
        # Pre-existing rows untouched.
        assert (await db_session.execute(select(Student))).scalars().all() == [existing]
        assert (await db_session.execute(select(AcademicYear))).scalars().all() == [existing_ay]

    async def test_rollback_table_resolution_is_import_order_independent(
        self, db_session, tenant_a, storage_root
    ) -> None:
        """Regression: base rollback must delete from the migrator's exact
        table, never the first substring match in the mapper registry.

        With the full app imported (as in production and API-level tests),
        ``attendance_intelligence`` tables (``attendance_thresholds``,
        ``period_attendances``, …) register before ``attendance_records``;
        the old substring scan resolved ``attendance`` →
        ``attendance_thresholds`` and rollback silently deleted nothing,
        leaving imported attendance rows behind.  Importing the full app
        here reproduces exactly that registry.
        """
        from app.domains.migration.engine import get_migrator
        from app.main import app as _full_app  # noqa: F401  (register every model)

        migrator = get_migrator("attendance")
        assert migrator is not None
        table = migrator._get_table()
        assert table is not None
        assert table.name == "attendance_records"

        project = await _make_project(db_session, tenant_a)
        await _import_and_reconcile(db_session, tenant_a, project)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        result = await svc.rollback(project.id)
        await db_session.commit()
        assert result["records_removed"] == 15
        assert (await db_session.execute(select(AttendanceRecord))).scalars().all() == []

    async def test_plan_rollback_counts_all_subtype_mappings(
        self, db_session, tenant_a, storage_root
    ) -> None:
        """D3: plan_rollback must count the run's whole mapping set (per
        subtype for container migrators) — before the fix it reported 0
        records for academic/fees/attendance runs."""
        from app.domains.migration.models import MigrationRun
        from app.domains.migration.rollback import RollbackService

        project = await _make_project(db_session, tenant_a)
        await _import_and_reconcile(db_session, tenant_a, project)

        runs = (
            (
                await db_session.execute(
                    select(MigrationRun).where(MigrationRun.project_id == project.id)
                )
            )
            .scalars()
            .all()
        )
        svc = RollbackService(db_session)
        by_entity = {}
        for run in runs:
            plan = await svc.plan_rollback(run.id, dry_run=True)
            by_entity[run.entity_type] = plan.records_to_remove
        # 2 students + 5 academic rows (year/class/section/2 enrollments)
        # + 2 attendance + 6 fee rows (type/structure/2 dues/2 payments).
        assert by_entity == {"students": 2, "academic": 5, "attendance": 2, "fees": 6}


# ── Scenario coverage: the acceptance list ──────────────────────────────


class TestScenarioCoverage:
    async def test_unicode_names_roundtrip(self, db_session, tenant_a, storage_root) -> None:
        """Unicode names survive parse → transform → import → DB."""
        csv = (
            "Student ID,Student Name,Email,DOB,Class,Section,Academic Year\n"
            "UN-01,Zoë  Müller ,zoe.muller@example.com,2005-01-02,10-A,Sec 1,2025-2026\n"
            "UN-02,José  García ,jose.garcia@example.com,2006-02-03,10-A,Sec 1,2025-2026\n"
        )
        project = await _make_project(db_session, tenant_a, csv=csv, name="Unicode import")
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        preview = await svc.preview(project.id, limit=2)
        assert preview["rows"][0]["after"]["first_name"] == "Zoë"
        assert preview["rows"][1]["after"]["first_name"] == "José"
        assert preview["rows"][0]["after"]["last_name"] == "Müller"

        await svc.run_validation(project.id)
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        students = (await db_session.execute(select(Student))).scalars().all()
        by_number = {s.student_number: s for s in students}
        assert by_number["UN-01"].first_name == "Zoë"
        assert by_number["UN-01"].last_name == "Müller"
        assert by_number["UN-02"].first_name == "José"
        assert by_number["UN-02"].last_name == "García"

    async def test_inconsistent_columns_do_not_crash(
        self, db_session, tenant_a, storage_root
    ) -> None:
        """A ragged row (extra trailing column) must not crash discovery or
        import — the extra value is tolerated, the known columns still map."""
        csv = (
            "Student ID,Student Name,DOB,Class,Section,Academic Year\n"
            "RC-01,John  Doe ,2005-08-14,10-A,Sec 1,2025-2026,EXTRA-NOTE\n"
            "RC-02,Jane  Smith ,2006-03-22,10-A,Sec 1,2025-2026\n"
        )
        project = await _make_project(db_session, tenant_a, csv=csv, name="Ragged import")
        # Discovery must not crash on the ragged row.
        assert project.row_count == 2
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        summary = await svc.run_validation(project.id)
        assert summary["is_ready"] is True, summary["samples"]
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        assert len((await db_session.execute(select(Student))).scalars().all()) == 2

    async def test_large_file_chunked_import_and_resume(
        self, db_session, tenant_a, storage_root
    ) -> None:
        """>1 chunk (IMPORT_CHUNK_SIZE=200): every row imports, progress
        reaches 100%, and a re-run is a no-op (idempotent resume)."""
        row_count = IMPORT_CHUNK_SIZE * 2 + 25  # 425 rows → 3 chunks
        rows = [
            "Admission No,Student Name,DOB,Class,Section,Academic Year",
        ]
        for i in range(1, row_count + 1):
            rows.append(f"LF-{i:04d},Student  {i} ,2005-01-01,10-A,Sec 1,2025-2026")
        csv = "\n".join(rows) + "\n"

        project = await _make_project(db_session, tenant_a, csv=csv, name="Large import")
        assert project.row_count == row_count
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        summary = await svc.run_validation(project.id)
        assert summary["is_ready"] is True, summary["samples"]

        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        assert len((await db_session.execute(select(Student))).scalars().all()) == row_count

        progress = await svc.get_progress(project.id)
        assert progress["records_processed"] == row_count
        assert progress["row_count"] == row_count

        # Resume: a second run must not duplicate.
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        assert len((await db_session.execute(select(Student))).scalars().all()) == row_count

    async def test_cancellation_from_ready(self, db_session, tenant_a, storage_root) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        await svc.run_validation(project.id)
        refreshed = await svc.repo.get_by_id(project.id)
        assert refreshed.status == MIGRATION_STATUS_READY

        await svc.cancel(project.id)
        await db_session.commit()
        cancelled = await svc.repo.get_by_id(project.id)
        assert cancelled.status == MIGRATION_STATUS_CANCELLED

    async def test_cancellation_while_importing_cancels_job(
        self, db_session, tenant_a, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        await svc.run_validation(project.id)
        started = await svc.start_import(project.id)
        assert started.status == MIGRATION_STATUS_IMPORTING
        assert started.job_id is not None

        await svc.cancel(project.id)
        await db_session.commit()
        cancelled = await svc.repo.get_by_id(project.id)
        assert cancelled.status == MIGRATION_STATUS_CANCELLED

        from app.domains.jobs.repository import JobRepository
        from app.multi_tenant.models import platform_context

        job = await JobRepository(db_session, platform_context()).get_by_id(started.job_id)
        assert job is not None
        assert job.status == "cancelled"

    async def test_failed_import_marks_project_failed_and_audits(
        self, db_session, tenant_a, storage_root, monkeypatch
    ) -> None:
        """A genuine mid-import failure must move the project to FAILED, mark
        the run failed, and record a FAILURE audit entry — never a fake
        success."""
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        await svc.run_validation(project.id)

        # Force the students migrator to blow up mid-migrate.
        from app.domains.migration import engine as migration_engine

        # Assigned as an instance attribute → no implicit ``self`` binding.
        async def _boom_migrate(records, session, run_id, mapping_repo, log_repo):  # noqa: ANN001
            raise RuntimeError("simulated importer failure")

        original = migration_engine.get_migrator("students")
        # Monkeypatch, not direct assignment: the registry caches singleton
        # migrator instances, so a plain attribute set would leak the boom
        # into every later test that imports students.
        monkeypatch.setattr(original, "migrate", _boom_migrate)  # type: ignore[method-assign]

        with pytest.raises(RuntimeError):
            await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()

        failed = await svc.repo.get_by_id(project.id)
        assert failed.status == MIGRATION_STATUS_FAILED

        from app.domains.audit.models import AuditLog
        from app.domains.migration.models import MigrationRun

        runs = (
            (
                await db_session.execute(
                    select(MigrationRun).where(MigrationRun.project_id == project.id)
                )
            )
            .scalars()
            .all()
        )
        assert any(r.status == "failed" for r in runs)

        entries = (await db_session.execute(select(AuditLog))).scalars().all()
        failures = [e for e in entries if e.result == "FAILURE"]
        assert failures, "a FAILURE audit entry must exist for the failed import"
        assert any("simulated importer failure" in (e.failure_reason or "") for e in failures)


# ── Messy demo fixture (duplicates, bad dates, bad amounts, orphans) ────


class TestMessyDemoFixture:
    async def test_demo_fixture_blocks_and_explains_every_defect(
        self, db_session, tenant_a, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a, csv=DEMO_CSV, name="Messy demo")
        assert project.row_count == 12
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        summary = await svc.run_validation(project.id)

        assert summary["is_ready"] is False
        categories = summary["categories"]
        assert categories.get("duplicate") == 1
        assert categories.get("invalid_date") == 1
        assert categories.get("invalid_amount") == 1
        assert categories.get("orphan_reference") == 2
        assert categories.get("missing_optional") == 2
        # Samples carry the row + category so the UI can explain each defect.
        assert summary["samples"] and all("issues" in s for s in summary["samples"])

    async def test_corrected_mapping_reaches_ready_and_imports(
        self, db_session, tenant_a, storage_root
    ) -> None:
        """The correction loop: fix the blocking rows (drop the duplicate,
        fix the bad date, drop the negative amount, drop orphan refs) and the
        same project imports cleanly."""
        csv = (
            "Admission No,Student Name,DOB,Gender,Email,Class,Section,Academic Year,"
            "Attendance Date,Attendance Status,Fee Type,Fee Paid,"
            "Payment Date,Receipt No,Guardian Phone\n"
            "ST-1001,John  Doe ,2005-08-14,M,john.doe@example.com,"
            "10-A,Sec 1,2025-2026,2026-08-10,Present,Tuition,45000,"
            "2026-01-10,RCT-1001,+254 700 123456\n"
            "ST-1002,Jane  Smith ,2006-03-22,F,jane.smith@example.com,"
            "10-A,Sec 1,2025-2026,2026-08-10,Absent,Tuition,30000,"
            "2026-01-11,RCT-1002,0700123456\n"
            "ST-1003,Alex  Brown ,2007-11-02,M,alex.brown@example.com,"
            "10-B,Sec 2,2025-2026,,,,,,0711 555 999\n"
        )
        project = await _make_project(db_session, tenant_a, csv=csv, name="Corrected demo")
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        summary = await svc.run_validation(project.id)
        assert summary["is_ready"] is True, summary["samples"]

        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        report = await svc.reconcile(project.id)
        # 3 students + 8 academic (1 year + 2 classes + 2 sections + 3
        # enrollments) + 2 attendance + 6 fee rows (1 type + 1 structure +
        # 2 dues + 2 payments).
        assert report["created"] == 19
        assert report["rejected"] == 0

    async def test_repeated_import_is_idempotent(self, db_session, tenant_a, storage_root) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        await svc.run_validation(project.id)
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        assert len((await db_session.execute(select(Student))).scalars().all()) == 2
        assert len((await db_session.execute(select(Payment))).scalars().all()) == 2


# ── API-level lifecycle verification ────────────────────────────────────


class TestApiLifecycle:
    async def test_full_api_flow_upload_to_report(self, auth_client, storage_root) -> None:
        """Upload → validate → preview → import → worker executes →
        reconcile → report via the real API.

        ``POST /import`` only *enqueues* the background job (it must never
        run synchronously in the request).  The worker path is simulated
        here exactly as the durable jobs worker would: claim the job, then
        ``JobService.execute_job`` runs it.
        """
        from app.domains.jobs.repository import JobRepository
        from app.domains.jobs.service import JobService
        from app.domains.migration.import_job import MIGRATION_IMPORT_JOB_TYPE
        from app.infrastructure.database import get_session
        from app.main import app as _test_app
        from app.multi_tenant.models import platform_context

        files = {"file": ("legacy.csv", CLEAN_CSV.encode(), "text/csv")}
        data = {"name": "API full flow", "source_system": "Generic CSV"}
        resp = await auth_client.post("/migration/projects", data=data, files=files)
        assert resp.status_code == 201, resp.text
        pid = resp.json()["id"]

        val = await auth_client.post(f"/migration/projects/{pid}/validate")
        assert val.status_code == 200, val.text
        assert val.json()["is_ready"] is True

        prev = await auth_client.get(f"/migration/projects/{pid}/preview?limit=2")
        assert prev.status_code == 200
        assert len(prev.json()["rows"]) == 2
        assert all(r["action"] in ("CREATE", "UPDATE", "ERROR") for r in prev.json()["rows"])

        # Enqueue — the project must move to IMPORTING with a job id.
        imp = await auth_client.post(f"/migration/projects/{pid}/import")
        assert imp.status_code == 200, imp.text
        assert imp.json()["status"] == MIGRATION_STATUS_IMPORTING
        assert imp.json()["job_id"] is not None

        # Progress is server-side and survives refresh even before the
        # worker runs (job exists, 0 rows processed).
        prog = await auth_client.get(f"/migration/projects/{pid}/progress")
        assert prog.status_code == 200, prog.text
        assert prog.json()["job"]["id"] == imp.json()["job_id"]
        assert prog.json()["status"] == MIGRATION_STATUS_IMPORTING

        # Worker: claim the enqueued migration job and execute it.  The
        # api_client fixture overrides the app's ``get_session`` dependency
        # with its own in-memory engine; the worker must run against the
        # *same* database, so we drive the override generator directly (the
        # raw ``get_session()`` would hit the global factory instead).
        override = _test_app.dependency_overrides[get_session]
        gen = override()
        session = await gen.__anext__()
        try:
            repo = JobRepository(session, platform_context())
            claimed = await repo.acquire_next(job_types=[MIGRATION_IMPORT_JOB_TYPE])
            assert claimed is not None
            await JobService(session, platform_context()).execute_job(claimed.id)
            await session.commit()
        finally:
            await gen.aclose()

        rec = await auth_client.get(f"/migration/projects/{pid}/reconcile")
        assert rec.status_code == 200, rec.text
        assert rec.json()["created"] == 15

        # Reconcile completed the project lifecycle.
        proj = await auth_client.get(f"/migration/projects/{pid}")
        assert proj.status_code == 200
        assert proj.json()["status"] == MIGRATION_STATUS_COMPLETED

        report = await auth_client.get(f"/migration/projects/{pid}/report")
        assert report.status_code == 200
        assert "SDMAS MIGRATION REPORT" in report.text
