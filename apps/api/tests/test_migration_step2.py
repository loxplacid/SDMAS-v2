"""Step 2 — Enterprise Headless Data Migration Engine tests.

Covers the capabilities added on top of the D2 workspace:

* XLSX parsing (openpyxl)
* deterministic cross-cutting validation (duplicates, dates, amounts,
  emails, enums, orphan/conflicting references)
* per-category validation summaries + preview action classification
* multi-entity import (students → academic → attendance → fees) with
  reference resolution through the run's mapping table
* idempotent re-runs, reconciliation across entity runs
* CSV/JSON report downloads
* tenant IDOR (cross-campus denials at both service and API level)
* the messy demo fixture catching every intended defect
"""

from __future__ import annotations

import io
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
from app.domains.migration.discovery import (
    parse_source,
)
from app.domains.migration.import_job import run_project_import
from app.domains.migration.models import MigrationProject
from app.domains.migration.project_service import MigrationProjectService
from app.domains.migration.workspace_validation import (
    BLOCKING,
    validate_records,
)

# Import every domain touched by the multi-entity import so the test
# database's ``create_all`` sees the full FK graph (student + academic +
# attendance + fees tables) before any query runs.
from app.domains.student.models import Student  # noqa: F401
from app.multi_tenant.models import TenantContext

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# ── Fixtures ──────────────────────────────────────────────────────────────

# Two rows that carry *all four* streams: person + class/section/year +
# attendance + a fee payment.  Used for the full end-to-end import.
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
    name: str = "Step2 import",
) -> MigrationProject:
    svc = MigrationProjectService(db_session, tenant, user_id=tenant.user_id, username="admin")
    return await svc.create_project(
        name=name,
        source_system="PowerSchool-style export",
        description="step 2 fixture",
        filename="legacy_export.csv",
        file_data=csv.encode("utf-8"),
        mime_type="text/csv",
    )


# ── XLSX parsing (Step 2) ────────────────────────────────────────────────


class TestXlsx:
    def _make_xlsx(self, rows: list[list[Any]]) -> bytes:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        try:
            buf = io.BytesIO()
            wb.save(buf)
            return buf.getvalue()
        finally:
            wb.close()

    def test_parse_xlsx_first_sheet(self) -> None:
        data = self._make_xlsx(
            [["Student ID", "Student Name"], ["S1", "John Doe"], ["S2", "Jane Smith"]]
        )
        records = parse_source(data, "students.xlsx")
        assert len(records) == 2
        assert records[0]["Student ID"] == "S1"
        assert records[1]["Student Name"] == "Jane Smith"

    def test_parse_xlsx_date_cells_stringified(self) -> None:
        import datetime

        data = self._make_xlsx([["DOB"], [datetime.date(2005, 8, 14)], ["garbage"]])
        records = parse_source(data, "students.xlsx")
        assert records[0]["DOB"] == "2005-08-14"

    def test_parse_xlsx_header_only_workbook(self) -> None:
        # A workbook with only a header row yields zero records — the
        # parser must not crash or invent data.
        data = self._make_xlsx([["Student ID", "Student Name"]])
        assert parse_source(data, "empty.xlsx") == []


# ── Cross-cutting validation (Step 2) ────────────────────────────────────


class TestWorkspaceValidation:
    def test_duplicate_student_number_blocks(self) -> None:
        records = [
            {"student_number": "A1", "first_name": "John"},
            {"student_number": "A1", "first_name": "Jane"},
        ]
        result = validate_records(records)
        assert len(result.blocking) == 1
        assert result.blocking[0].category == "duplicate"
        assert result.blocking[0].severity == BLOCKING
        assert "A1" in result.blocking[0].message

    def test_invalid_date_blocks_when_source_was_present(self) -> None:
        transformed = [{"attendance_date": None, "student_number": "S1"}]
        original = [{"Attendance Date": "2026-13-40", "Student ID": "S1"}]
        mapping = {"Attendance Date": {"target": "attendance_date"}}
        result = validate_records(transformed, original, mapping)
        assert any(f.category == "invalid_date" for f in result.blocking)

    def test_empty_date_is_not_an_error(self) -> None:
        transformed = [{"date_of_birth": None, "student_number": "S1", "first_name": "X"}]
        original = [{"DOB": "", "Student ID": "S1"}]
        result = validate_records(transformed, original)
        assert not any(f.category == "invalid_date" for f in result.blocking)

    def test_negative_amount_blocks(self) -> None:
        records = [{"amount_paid": "-5000", "student_number": "S1"}]
        result = validate_records(records)
        assert any(f.category == "invalid_amount" for f in result.blocking)
        assert any("non-negative" in f.message for f in result.blocking)

    def test_non_numeric_amount_blocks(self) -> None:
        records = [{"amount_paid": "not-a-number", "student_number": "S1"}]
        result = validate_records(records)
        assert any(f.category == "invalid_amount" for f in result.blocking)

    def test_invalid_email_blocks_and_missing_email_warns(self) -> None:
        records = [
            {"email": "not-an-email", "student_number": "S1", "first_name": "A"},
            {"email": None, "student_number": "S2", "first_name": "B"},
        ]
        result = validate_records(records)
        assert any(f.category == "invalid_email" for f in result.blocking)
        assert any(f.category == "missing_optional" for f in result.warnings)

    def test_orphan_student_reference_blocks(self) -> None:
        records = [
            {"student_number": "S1", "first_name": "Known"},
            {"student_number": "S99", "attendance_date": "2026-08-10"},
        ]
        result = validate_records(records)
        orphan = [f for f in result.blocking if f.category == "orphan_reference"]
        assert orphan and "S99" in orphan[0].message

    def test_orphan_class_reference_blocks(self) -> None:
        records = [
            {
                "student_number": "S1",
                "first_name": "A",
                "class_name": "10-A",
                "section_name": "Sec 1",
            },
            {
                "student_number": "S2",
                "attendance_date": "2026-08-10",
                "class_name": "12-C",
                "section_name": "Sec 9",
            },
        ]
        result = validate_records(records)
        orphan = [f for f in result.blocking if f.category == "orphan_reference"]
        assert any("12-C" in f.message for f in orphan)

    def test_conflicting_class_reference_warns(self) -> None:
        # S2 uses (11-B, Sec 2), so the combo exists in the file; S1's
        # attendance row pointing at S2's combo is a conflict, not an orphan.
        records = [
            {
                "student_number": "S1",
                "first_name": "A",
                "class_name": "10-A",
                "section_name": "Sec 1",
            },
            {
                "student_number": "S2",
                "first_name": "B",
                "class_name": "11-B",
                "section_name": "Sec 2",
            },
            {
                "student_number": "S1",
                "attendance_date": "2026-08-10",
                "class_name": "11-B",
                "section_name": "Sec 2",
            },
        ]
        result = validate_records(records)
        assert any(f.category == "conflicting_reference" for f in result.warnings)
        assert not any(f.category == "orphan_reference" for f in result.blocking)

    def test_invalid_attendance_status_blocks(self) -> None:
        records = [
            {"student_number": "S1", "attendance_date": "2026-08-10", "attendance_status": "maybe"}
        ]
        result = validate_records(records)
        assert any(f.category == "invalid_enum" for f in result.blocking)

    def test_categories_aggregate_counts(self) -> None:
        records = [
            {"student_number": "A1", "first_name": "A"},
            {"student_number": "A1", "first_name": "B"},
            {"amount_paid": "-5", "student_number": "C1"},
        ]
        result = validate_records(records)
        assert result.categories["duplicate"] == 1
        assert result.categories["invalid_amount"] == 1


# ── Demo fixture: every intended defect is caught ────────────────────────


class TestDemoFixture:
    async def test_demo_fixture_detects_all_issues(
        self, db_session, tenant_a, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a, csv=DEMO_CSV)
        assert project.row_count == 12

        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        summary = await svc.run_validation(project.id)

        assert summary["is_ready"] is False
        assert summary["blocking"] == 5
        categories = summary["categories"]
        assert categories.get("duplicate") == 1
        assert categories.get("invalid_date") == 1
        assert categories.get("invalid_amount") == 1
        assert categories.get("orphan_reference") == 2
        # Missing email on student records (rows 4 and 5) → advisory warning.
        assert summary["warnings"] == 2
        assert categories.get("missing_optional") == 2

        # Samples carry the row + category so the UI can explain the defect.
        samples = summary["samples"]
        assert samples and all("issues" in s for s in samples)
        assert {s["category"] for s in samples} <= set(categories)

    async def test_demo_mapping_covers_all_entities(
        self, db_session, tenant_a, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a, csv=DEMO_CSV)
        entities = project.discovery["entities"]
        # Migrator entity names — the import job routes on these.
        assert set(entities) == {"students", "academic", "attendance", "fees"}


# ── Multi-entity import (Step 2) ─────────────────────────────────────────


class TestMultiEntityImport:
    async def test_imports_all_four_streams(self, db_session, tenant_a, storage_root) -> None:
        from app.domains.student.models import Student

        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        assert set(project.discovery["entities"]) == {"students", "academic", "attendance", "fees"}

        summary = await svc.run_validation(project.id)
        assert summary["is_ready"] is True, summary["samples"]

        result = await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()

        assert result["entities"]["students"]["imported"] == 2
        assert (
            result["entities"]["academic"]["imported"] == 5
        )  # 1 ay + 1 class + 1 section + 2 enrollments
        assert result["entities"]["attendance"]["imported"] == 2
        assert (
            result["entities"]["fees"]["imported"] == 6
        )  # 1 type + 1 structure + 2 dues + 2 payments

        assert len((await db_session.execute(select(Student))).scalars().all()) == 2
        assert len((await db_session.execute(select(AcademicYear))).scalars().all()) == 1
        assert len((await db_session.execute(select(Class))).scalars().all()) == 1
        assert len((await db_session.execute(select(Section))).scalars().all()) == 1
        assert len((await db_session.execute(select(Enrollment))).scalars().all()) == 2
        assert len((await db_session.execute(select(AttendanceRecord))).scalars().all()) == 2
        assert len((await db_session.execute(select(FeeType))).scalars().all()) == 1
        assert len((await db_session.execute(select(FeeStructure))).scalars().all()) == 1
        assert len((await db_session.execute(select(FeeDue))).scalars().all()) == 2
        assert len((await db_session.execute(select(Payment))).scalars().all()) == 2

        # Derivation sanity: the year range comes from the name.
        year = (await db_session.execute(select(AcademicYear))).scalar_one()
        assert year.name == "2025-2026"
        assert year.start_date.isoformat() == "2025-04-01"

    async def test_rerun_is_idempotent_across_entities(
        self, db_session, tenant_a, storage_root
    ) -> None:
        from app.domains.student.models import Student

        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)
        await svc.run_validation(project.id)

        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        # Re-run after a "crash": nothing may duplicate.
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()

        assert len((await db_session.execute(select(Student))).scalars().all()) == 2
        assert len((await db_session.execute(select(AcademicYear))).scalars().all()) == 1
        assert len((await db_session.execute(select(AttendanceRecord))).scalars().all()) == 2
        assert len((await db_session.execute(select(Payment))).scalars().all()) == 2

    async def test_attendance_skip_logs_once_across_resume(
        self, db_session, tenant_a, storage_root
    ) -> None:
        """Resume-safety for unresolvable attendance references.

        A row whose student cannot be resolved is never committed to the
        mapping table, so a retry regenerates the same ``skipped_refs``.
        Re-logging would violate ``uq_migration_log_entry`` (one entry per
        record per run) and fail the job on resume — the log-once guard
        must keep a second run a true no-op.
        """
        from app.domains.migration.models import MigrationLog

        # Attendance row for a student number that never appears as a person.
        csv = (
            "Admission No,Student Name,Class,Section,Academic Year,"
            "Attendance Date,Attendance Status\n"
            "ST-2001,John  Doe ,10-A,Sec 1,2025-2026,2026-08-10,Present\n"
            "ST-9999,,10-A,Sec 1,2025-2026,2026-08-10,Present\n"
        )
        project = await _make_project(db_session, tenant_a, csv=csv)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)
        await svc.run_validation(project.id)

        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()

        # Run 1 logged exactly one unresolved-reference error (ST-9999);
        # the migrator also logs a benign "imported" entry for ST-2001.
        first_run = (
            await db_session.execute(
                select(MigrationLog).where(
                    MigrationLog.entity_type == "attendance",
                    MigrationLog.level == "error",
                )
            )
        ).scalars().all()
        assert len(first_run) == 1
        assert "ST-9999" in first_run[0].legacy_id

        # Resume ("crash" + retry) must not duplicate log entries.
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        second_run = (
            await db_session.execute(
                select(MigrationLog).where(
                    MigrationLog.entity_type == "attendance",
                    MigrationLog.level == "error",
                )
            )
        ).scalars().all()
        assert len(second_run) == 1

    async def test_reconciliation_aggregates_entity_runs(
        self, db_session, tenant_a, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)
        await svc.run_validation(project.id)
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()

        report = await svc.reconcile(project.id)
        assert report["created"] == 15  # 2 students + 5 academic + 2 attendance + 6 fees
        assert report["rejected"] == 0
        assert set(report["entities"]) == {"students", "academic", "attendance", "fees"}
        assert report["source_records"] == 2


# ── Preview action classification (Step 2) ───────────────────────────────


class TestPreviewActions:
    async def test_preview_classifies_create_update_error(
        self, db_session, tenant_a, storage_root
    ) -> None:

        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)

        # Pre-insert one student → its row must classify as UPDATE.
        db_session.add(
            Student(
                first_name="Existing",
                last_name="Student",
                student_number="ST-2001",
                campus_id=1,
            )
        )
        await db_session.flush()

        preview = await svc.preview(project.id, limit=2)
        actions = {row["action"] for row in preview["rows"]}
        assert "UPDATE" in actions  # row 1 (already in SDMAS)
        assert "CREATE" in actions  # row 2 (new)
        assert all(row["status"] == "ok" for row in preview["rows"])

    async def test_preview_marks_blocked_rows_as_error(
        self, db_session, tenant_a, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a, csv=DEMO_CSV)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)
        preview = await svc.preview(project.id, limit=12)
        errors = [r for r in preview["rows"] if r["action"] == "ERROR"]
        assert len(errors) == 5
        assert all(r["action_reason"] for r in errors)


# ── Reports (Step 2) ─────────────────────────────────────────────────────


class TestReports:
    async def test_csv_and_json_reports(self, auth_client, storage_root) -> None:
        files = {"file": ("legacy.csv", CLEAN_CSV.encode(), "text/csv")}
        data = {"name": "API import", "source_system": "Generic CSV"}
        resp = await auth_client.post("/migration/projects", data=data, files=files)
        assert resp.status_code == 201, resp.text
        pid = resp.json()["id"]

        csv_resp = await auth_client.get(f"/migration/projects/{pid}/report.csv")
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]
        assert "section,key,value" in csv_resp.text
        assert "reconciliation,created," in csv_resp.text

        json_resp = await auth_client.get(f"/migration/projects/{pid}/report.json")
        assert json_resp.status_code == 200
        assert "application/json" in json_resp.headers["content-type"]
        assert '"migration_id"' in json_resp.text

    async def test_report_reflects_entities_and_reconciliation(
        self, db_session, tenant_a, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)
        await svc.run_validation(project.id)
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        await svc.reconcile(project.id)

        text = await svc.generate_report(project.id)
        assert "Entities:        students, academic, attendance, fees" in text
        assert "Source records:  2" in text

        import json

        json_report = json.loads(await svc.generate_report_json(project.id))
        assert json_report["entities"] == ["students", "academic", "attendance", "fees"]
        assert json_report["reconciliation"]["created"] == 15


# ── Tenant IDOR (Step 2 security) ────────────────────────────────────────


class TestTenantIsolation:
    @pytest.mark.parametrize(
        "operation",
        [
            "validate",
            "preview",
            "start_import",
            "generate_report",
            "reconcile",
            "cancel",
            "rollback",
        ],
    )
    async def test_cross_tenant_service_denials(
        self, db_session, tenant_a, tenant_b, storage_root, operation
    ) -> None:
        from app.core.exceptions import NotFoundError

        project = await _make_project(db_session, tenant_a)
        svc_a = MigrationProjectService(db_session, tenant_a, user_id=99)
        await svc_a.run_validation(project.id)

        svc_b = MigrationProjectService(db_session, tenant_b, user_id=98)
        with pytest.raises(NotFoundError):
            if operation == "validate":
                await svc_b.run_validation(project.id)
            elif operation == "preview":
                await svc_b.preview(project.id)
            elif operation == "start_import":
                await svc_b.start_import(project.id)
            elif operation == "generate_report":
                await svc_b.generate_report(project.id)
            elif operation == "reconcile":
                await svc_b.reconcile(project.id)
            elif operation == "cancel":
                await svc_b.cancel(project.id)
            elif operation == "rollback":
                await svc_b.rollback(project.id)

    async def test_foreign_user_api_denied(self, auth_client, storage_root) -> None:
        """A user outside the owning campus cannot read another campus's
        migration workspace through the API.

        The service-level test above proves a *campus-scoped* tenant B gets
        a 404 (the id is invisible).  Here we prove the gate itself denies
        a foreign user (fresh registration — no campus membership, no admin
        role): they must receive 403, never data.
        """
        files = {"file": ("legacy.csv", CLEAN_CSV.encode(), "text/csv")}
        data = {"name": "Campus A import", "source_system": "Generic CSV"}
        resp = await auth_client.post("/migration/projects", data=data, files=files)
        assert resp.status_code == 201, resp.text
        pid = resp.json()["id"]

        # Register + login a brand-new user (default role, no campus).
        resp = await auth_client.post(
            "/auth/register",
            json={
                "username": "outsider",
                "email": "outsider@test.local",
                "password": "OutsiderPass123!",
                "display_name": "Outsider",
            },
        )
        assert resp.status_code == 201, resp.text
        login = await auth_client.post(
            "/auth/login",
            json={"login": "outsider", "password": "OutsiderPass123!"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        get_resp = await auth_client.get(f"/migration/projects/{pid}", headers=headers)
        assert get_resp.status_code == 403
        report_resp = await auth_client.get(
            f"/migration/projects/{pid}/report.csv", headers=headers
        )
        assert report_resp.status_code == 403
        list_resp = await auth_client.get("/migration/projects", headers=headers)
        assert list_resp.status_code == 403
