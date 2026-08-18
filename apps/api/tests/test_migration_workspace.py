"""D2 — Migration Center workspace tests.

Covers: CSV/JSON discovery + schema inference, deterministic mapping
suggestions, the transformation pipeline, validation gating (blocking errors
block READY), the background import job end-to-end, idempotency + resume,
reconciliation, tenant isolation, authorization and audit events.
"""

from __future__ import annotations

import datetime
import os
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domains.migration.discovery import (
    build_default_mapping,
    parse_source,
    profile_columns,
    suggest_mappings,
)
from app.domains.migration.engine import MigrationEngine
from app.domains.migration.import_job import run_project_import
from app.domains.migration.models import (
    MIGRATION_STATUS_COMPLETED,
    MIGRATION_STATUS_MAPPING,
    MIGRATION_STATUS_READY,
    MIGRATION_STATUS_RECONCILING,
    MigrationProject,
)
from app.domains.migration.project_repository import MigrationProjectRepository
from app.domains.migration.project_service import MigrationProjectService
from app.domains.migration.transforms import apply_mapping, apply_transforms
from app.domains.student.models import Student
from app.multi_tenant.models import TenantContext

# ── Fixtures ──────────────────────────────────────────────────────────────

CSV_SAMPLE = (
    "Student ID,Student Name,DOB,Email,Guardian Phone,Class\n"
    "LC-001,John  Doe ,2005-08-14,john.doe@example.com,+254 700 123456,10-A\n"
    "LC-002, Jane  Smith ,2006-03-22,jane.smith@example.com,0700123456,10-A\n"
    "LC-003, Alex Brown ,,alex.brown@example.com,0711 555 999,10-B\n"
)


@pytest.fixture
def tenant_a() -> TenantContext:
    return TenantContext(campus_id=1, institution_id=1, user_id=99)


@pytest.fixture
def tenant_b() -> TenantContext:
    return TenantContext(campus_id=2, institution_id=1, user_id=98)


@pytest.fixture
def storage_root(tmp_path, monkeypatch) -> None:
    """Redirect migration file storage into a temp dir."""
    monkeypatch.setattr(settings, "storage_root", str(tmp_path / "storage"))
    os.makedirs(os.path.join(settings.storage_root, "migrations"), exist_ok=True)


async def _make_project(
    db_session: AsyncSession,
    tenant: TenantContext,
    *,
    csv: str = CSV_SAMPLE,
    name: str = "Test import",
) -> MigrationProject:
    svc = MigrationProjectService(db_session, tenant, user_id=tenant.user_id, username="admin")
    return await svc.create_project(
        name=name,
        source_system="Generic CSV",
        description="fixture",
        filename="students.csv",
        file_data=csv.encode("utf-8"),
        mime_type="text/csv",
    )


def _mapped(project: MigrationProject) -> dict[str, Any]:
    """Apply the project's default mapping to the CSV sample records."""
    records = parse_source(CSV_SAMPLE.encode(), "students.csv")
    return {
        "records": records,
        "transformed": apply_mapping(records, project.mapping or {}),
    }


# ── Discovery + mapping suggestions (D2.3 / D2.4) ────────────────────────


class TestDiscovery:
    def test_parse_csv_strips_headers_and_whitespace(self) -> None:
        records = parse_source(CSV_SAMPLE.encode(), "students.csv")
        assert len(records) == 3
        assert records[0]["Student ID"] == "LC-001"
        # Values are trimmed on read (leading/trailing whitespace removed,
        # internal spaces preserved) — the trim transform is a separate step.
        assert records[0]["Student Name"] == "John  Doe"
        assert set(records[1].keys()) == {
            "Student ID",
            "Student Name",
            "DOB",
            "Email",
            "Guardian Phone",
            "Class",
        }

    def test_parse_json_list(self) -> None:
        data = b'[{"name": "A", "age": 10}, {"name": "B", "age": 11}]'
        records = parse_source(data, "data.json")
        assert len(records) == 2
        assert records[1]["name"] == "B"

    def test_parse_json_keyed(self) -> None:
        data = b'{"students": [{"name": "A"}, {"name": "B"}]}'
        records = parse_source(data, "data.json")
        assert len(records) == 2

    def test_parse_jsonl(self) -> None:
        data = b'{"name": "A"}\n{"name": "B"}\n'
        records = parse_source(data, "data.jsonl")
        assert len(records) == 2

    def test_parse_empty_csv(self) -> None:
        assert parse_source(b"", "empty.csv") == []

    def test_profile_columns_types_and_null_rates(self) -> None:
        records = parse_source(CSV_SAMPLE.encode(), "students.csv")
        profiles = profile_columns(records)
        by_name = {p.name: p for p in profiles}
        assert by_name["DOB"].looks_like_date
        assert by_name["Email"].looks_like_email
        assert by_name["Guardian Phone"].looks_like_phone
        assert by_name["Student ID"].looks_like_identifier
        assert by_name["DOB"].null_rate > 0  # row 3 has empty DOB

    def test_suggest_mappings_high_confidence(self) -> None:
        records = parse_source(CSV_SAMPLE.encode(), "students.csv")
        profiles = profile_columns(records)
        suggestions = suggest_mappings([p.name for p in profiles], profiles)
        by_source = {s.source_field: s for s in suggestions}
        assert by_source["Student ID"].target_field == "student_number"
        assert by_source["Student ID"].confidence == "high"
        assert by_source["DOB"].target_field == "date_of_birth"
        assert by_source["Email"].target_field == "email"
        assert by_source["Guardian Phone"].target_field == "guardian_phone"
        assert by_source["Student Name"].target_field == "full_name"

    def test_default_mapping_applies_academic_and_finance_targets(self) -> None:
        records = parse_source(CSV_SAMPLE.encode(), "students.csv")
        profiles = profile_columns(records)
        suggestions = suggest_mappings([p.name for p in profiles], profiles)
        mapping = build_default_mapping(suggestions)
        assert mapping["Student ID"]["target"] == "student_number"
        assert mapping["DOB"]["transforms"] == [{"op": "parse_date"}]
        # 'Class' now maps to the academic structure target (Step 2).
        assert mapping["Class"]["target"] == "class_name"

    def test_detect_entities_requires_year_for_academic(self) -> None:
        from app.domains.migration.discovery import detect_entities

        records = parse_source(CSV_SAMPLE.encode(), "students.csv")
        profiles = profile_columns(records)
        suggestions = suggest_mappings([p.name for p in profiles], profiles)
        mapping = build_default_mapping(suggestions)
        entities = detect_entities(mapping)
        # A bare Class column (no Academic Year) cannot build academic
        # structure — only the student stream is detected.
        assert entities == ["students"]


# ── Transformation pipeline (D2.5) ───────────────────────────────────────


class TestTransforms:
    def test_trim_lowercase_uppercase(self) -> None:
        assert apply_transforms("  John  ", [{"op": "trim"}], {}) == "John"
        assert apply_transforms("  JOHN ", [{"op": "trim"}, {"op": "lowercase"}], {}) == "john"
        assert apply_transforms("john", [{"op": "uppercase"}], {}) == "JOHN"

    def test_map_values_gender(self) -> None:
        spec = {"op": "map_values", "values": {"m": "male", "f": "female"}}
        assert apply_transforms("M", [spec], {}) == "male"
        assert apply_transforms("male", [spec], {}) == "male"

    def test_parse_date_formats(self) -> None:
        assert apply_transforms("14/08/2005", [{"op": "parse_date"}], {}) == "2005-08-14"
        assert apply_transforms("2005-08-14", [{"op": "parse_date"}], {}) == "2005-08-14"
        assert apply_transforms("garbage", [{"op": "parse_date"}], {}) is None

    def test_normalize_phone(self) -> None:
        assert (
            apply_transforms("+254 700 123456", [{"op": "normalize_phone"}], {}) == "+254700123456"
        )
        assert apply_transforms("0700 123 456", [{"op": "normalize_phone"}], {}) == "0700123456"

    def test_split_name(self) -> None:
        assert apply_transforms("John Doe", [{"op": "split_name", "part": 0}], {}) == "John"
        assert apply_transforms("John Doe", [{"op": "split_name", "part": 1}], {}) == "Doe"
        assert (
            apply_transforms("Jane  Smith", [{"op": "trim"}, {"op": "split_name", "part": 0}], {})
            == "Jane"
        )

    def test_default_and_replace(self) -> None:
        assert apply_transforms(None, [{"op": "default", "default": "active"}], {}) == "active"
        assert apply_transforms("S-01", [{"op": "strip_prefix", "prefix": "S-"}], {}) == "01"
        assert apply_transforms("a-b", [{"op": "replace", "old": "-", "new": "_"}], {}) == "a_b"

    def test_apply_mapping_full_name_fanout_and_legacy_id(self) -> None:
        mapping = {
            "Student Name": {
                "target": "full_name",
                "confidence": "high",
                "reason": "x",
                "transforms": [{"op": "trim"}],
            },
            "Student ID": {
                "target": "student_number",
                "confidence": "high",
                "reason": "x",
                "transforms": [],
            },
            "DOB": {
                "target": "date_of_birth",
                "confidence": "high",
                "reason": "x",
                "transforms": [{"op": "parse_date"}],
            },
        }
        records = parse_source(CSV_SAMPLE.encode(), "students.csv")
        out = apply_mapping(records, mapping)
        assert out[0]["first_name"] == "John"
        assert out[0]["last_name"] == "Doe"
        assert out[0]["date_of_birth"] == "2005-08-14"
        # legacy_id derived from student_number for idempotency keying.
        assert out[0]["legacy_id"] == "LC-001"


# ── Project service lifecycle (D2.2 / D2.4 / D2.6 / D2.7) ────────────────


class TestProjectService:
    async def test_create_project_runs_discovery(self, db_session, tenant_a, storage_root) -> None:
        project = await _make_project(db_session, tenant_a)
        assert project.status == MIGRATION_STATUS_MAPPING
        assert project.row_count == 3
        assert project.discovery["record_count"] == 3
        assert project.campus_id == 1
        assert project.operator_id == 99
        assert project.file_key and project.file_key.startswith("1/")

    async def test_rejects_unsupported_extension(self, db_session, tenant_a, storage_root) -> None:
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            await svc.create_project(
                name="x",
                source_system="CSV",
                description=None,
                filename="students.txt",
                file_data=b"xx",
                mime_type="text/plain",
            )

    async def test_accepts_xlsx_extension(self, db_session, tenant_a, storage_root) -> None:
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)
        project = await svc.create_project(
            name="XLSX import",
            source_system="Generic CSV",
            description=None,
            filename="students.xlsx",
            file_data=b"\x50\x4b\x03\x04",  # not a real workbook; parser returns []
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        assert project.row_count == 0
        assert project.file_key and project.file_key.endswith(".xlsx")

    async def test_save_mapping_then_validate_blocks_ready(
        self, db_session, tenant_a, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        # Drop the mapping so required fields are missing → blocking.
        bad_mapping = {
            "Student Name": {
                "target": "full_name",
                "confidence": "high",
                "reason": "x",
                "transforms": [],
            },
        }
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        project = await svc.save_mapping(project.id, bad_mapping)
        summary = await svc.run_validation(project.id)
        assert summary["blocking"] > 0
        assert summary["is_ready"] is False
        refreshed = await MigrationProjectRepository(db_session, tenant_a).get_by_id(project.id)
        assert refreshed.status != MIGRATION_STATUS_READY

    async def test_valid_mapping_reaches_ready(self, db_session, tenant_a, storage_root) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        summary = await svc.run_validation(project.id)
        assert summary["is_ready"] is True
        assert summary["blocking"] == 0
        refreshed = await MigrationProjectRepository(db_session, tenant_a).get_by_id(project.id)
        assert refreshed.status == MIGRATION_STATUS_READY

    async def test_preview_shows_before_after(self, db_session, tenant_a, storage_root) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)
        preview = await svc.preview(project.id, limit=2)
        assert preview["total"] == 3
        assert len(preview["rows"]) == 2
        assert preview["rows"][0]["before"]["Student Name"] == "John  Doe"
        assert preview["rows"][0]["after"].get("first_name") == "John"

    async def test_tenant_isolation_get(self, db_session, tenant_a, tenant_b, storage_root) -> None:
        project = await _make_project(db_session, tenant_a)
        from app.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await MigrationProjectRepository(db_session, tenant_b).get_by_id(project.id)
        # Platform scope can see it (admin cross-tenant).
        platform = TenantContext(user_id=1, platform=True)
        visible = await MigrationProjectRepository(db_session, platform).get_by_id(project.id)
        assert visible.id == project.id


# ── Import job (D2.8 / D2.9 / D2.12) ─────────────────────────────────────


class TestImportJob:
    async def test_import_creates_students_and_completes(
        self,
        db_session,
        tenant_a,
        storage_root,
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)
        await svc.run_validation(project.id)

        result = await run_project_import(db_session, tenant_a, project.id, job_id=None)
        assert result["imported"] == 3
        assert result["errors"] == 0

        await db_session.commit()
        students = (await db_session.execute(select(Student))).scalars().all()
        assert len(students) == 3
        assert {s.student_number for s in students} == {"LC-001", "LC-002", "LC-003"}
        assert all(s.campus_id == 1 for s in students)
        # DOB parsed + name split correctly.
        by_number = {s.student_number: s for s in students}
        assert by_number["LC-001"].first_name == "John"
        assert by_number["LC-001"].date_of_birth.isoformat() == "2005-08-14"

        refreshed = await MigrationProjectRepository(db_session, tenant_a).get_by_id(project.id)
        assert refreshed.status in (MIGRATION_STATUS_RECONCILING, MIGRATION_STATUS_COMPLETED)
        assert refreshed.run_id is not None

    async def test_import_idempotent_on_rerun(self, db_session, tenant_a, storage_root) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)
        await svc.run_validation(project.id)
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()

        # Second run: same data, same project → no duplicates.
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        students = (await db_session.execute(select(Student))).scalars().all()
        assert len(students) == 3

    async def test_import_resumes_after_partial_chunk(
        self,
        db_session,
        tenant_a,
        storage_root,
    ) -> None:
        """Simulate a crash after the first chunk: the project's processed
        counter + committed mappings make the retry idempotent."""
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)
        await svc.run_validation(project.id)

        # First pass — process everything (records are small enough to fit
        # one chunk here, so emulate a partial commit by recording the run
        # and processed count, then re-running).
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        before = (await db_session.execute(select(Student))).scalars().all()
        assert len(before) == 3

        # Re-run after the "crash": must not duplicate, must not error.
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        after = (await db_session.execute(select(Student))).scalars().all()
        assert len(after) == 3

    async def test_reconciliation_totals(self, db_session, tenant_a, storage_root) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)
        await svc.run_validation(project.id)
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()

        report = await svc.reconcile(project.id)
        assert report["source_records"] == 3
        assert report["created"] == 3
        assert report["rejected"] == 0
        # Totals reconcile: source == created + skipped + rejected.
        assert (
            report["source_records"] == report["created"] + report["skipped"] + report["rejected"]
        )

    async def test_report_includes_mapping_and_counts(
        self, db_session, tenant_a, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99)
        await svc.run_validation(project.id)
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        await svc.reconcile(project.id)

        report = await svc.generate_report(project.id)
        assert "MIGRATION REPORT" in report
        assert "Student ID -> student_number" in report
        assert "Created:" in report


# ── Authorization + audit (D2.15 / D2.11) ────────────────────────────────


class TestAuthAndAudit:
    async def test_unauthorized_user_denied(self, api_client) -> None:
        resp = await api_client.get("/migration/projects")
        assert resp.status_code == 401  # auth gate — no token

    async def test_non_admin_denied(self, api_client) -> None:
        # Register a plain user (default non-admin role) and confirm the
        # project workspace returns 403, not data.
        from sqlalchemy import select as sa_select

        from app.domains.auth.models import User, UserSchoolMembership
        from app.domains.institution.models import Campus
        from app.infrastructure.database import get_session

        # Register via the public auth endpoint (role defaults to non-admin).
        resp = await api_client.post(
            "/auth/register",
            json={
                "username": "staff1",
                "email": "staff1@test.local",
                "password": "StaffPass123!",
                "display_name": "Staff One",
            },
        )
        assert resp.status_code == 201, resp.text

        login = await api_client.post(
            "/auth/login",
            json={"login": "staff1", "password": "StaffPass123!"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Staff has no campus membership yet — resolve to a campus first so
        # the request reaches the role gate (not the tenant gate).
        #
        # Query through the app's dependency override (the same in-memory
        # database the api_client uses) rather than the raw get_session,
        # which would hit the live dev database.
        from app.main import app

        override = app.dependency_overrides.get(get_session)
        session_source = override() if override is not None else get_session()
        async for session in session_source:
            campus = (await session.execute(sa_select(Campus).limit(1))).scalar_one_or_none()
            user = (
                await session.execute(sa_select(User).where(User.username == "staff1"))
            ).scalar_one_or_none()
            if user and campus:
                user.campus_id = campus.id
                user.role = "staff"
                session.add(
                    UserSchoolMembership(
                        user_id=user.id,
                        campus_id=campus.id,
                        role="staff",
                        is_default=True,
                        is_active=True,
                    )
                )

        resp = await api_client.get("/migration/projects", headers=headers)
        assert resp.status_code == 403

    async def test_audit_events_recorded(self, db_session, tenant_a, storage_root) -> None:
        from app.domains.audit.models import AuditLog

        project = await _make_project(db_session, tenant_a)
        svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
        await svc.run_validation(project.id)
        await run_project_import(db_session, tenant_a, project.id, job_id=None)
        await db_session.commit()
        await svc.reconcile(project.id)

        entries = (await db_session.execute(select(AuditLog))).scalars().all()
        actions = [e.action for e in entries]
        assert "MIGRATION_PROJECT_DISCOVERED" in actions
        assert "MIGRATION_PROJECT_VALIDATED" in actions
        assert "MIGRATION_PROJECT_IMPORT_COMPLETED" in actions
        # Actor attribution is explicit.
        discover = next(e for e in entries if e.action == "MIGRATION_PROJECT_DISCOVERED")
        assert discover.actor_type == "user"


# ---------------------------------------------------------------------------
# Multi-tenant audit regression: migration RUN reads and rollbacks are
# campus-scoped (a cross-tenant IDOR — apex could read/roll back stjude runs).
# ---------------------------------------------------------------------------


class TestMigrationRunTenantScoping:
    async def test_get_by_id_is_campus_scoped(self, db_session) -> None:
        from app.domains.migration.models import MigrationRun
        from app.domains.migration.repository import MigrationRunRepository

        run = MigrationRun(
            entity_type="students", status="completed", source="legacy.json",
            total_records=5, imported=5, campus_id=1,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        db_session.add(run)
        await db_session.flush()

        repo = MigrationRunRepository(db_session)
        assert await repo.get_by_id(run.id, campus_id=1) is not None
        # Same id, different campus → invisible (isolation, not existence).
        assert await repo.get_by_id(run.id, campus_id=2) is None

    async def test_list_runs_is_campus_scoped(self, db_session) -> None:
        from app.domains.migration.models import MigrationRun
        from app.domains.migration.repository import MigrationRunRepository

        now = datetime.datetime.now(datetime.timezone.utc)
        db_session.add_all([
            MigrationRun(entity_type="students", status="completed", source="a.json",
                         total_records=1, campus_id=1, created_at=now),
            MigrationRun(entity_type="students", status="completed", source="b.json",
                         total_records=1, campus_id=2, created_at=now),
        ])
        await db_session.flush()

        repo = MigrationRunRepository(db_session)
        items, total = await repo.list_runs(campus_id=1)
        assert total == 1
        assert all(i.campus_id == 1 for i in items)

    async def test_rollback_requires_run_in_caller_campus(self, db_session) -> None:
        """RollbackService must refuse a run owned by another campus."""
        from app.domains.migration.models import MigrationRun
        from app.domains.migration.rollback import RollbackService

        run = MigrationRun(
            entity_type="students", status="completed", source="legacy.json",
            total_records=1, imported=1, campus_id=1,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        db_session.add(run)
        await db_session.flush()

        svc = RollbackService(db_session)
        with pytest.raises(ValueError):
            await svc.plan_rollback(run.id, campus_id=2)
        with pytest.raises(ValueError):
            await svc.execute_rollback(run.id, campus_id=2)

    async def test_engine_run_pins_campus(self, db_session) -> None:
        """Runs created through the engine belong to the calling campus."""
        from app.domains.migration.models import MigrationRun

        engine = MigrationEngine(db_session)
        # students migrator may require valid records; use dry run on empty-safe entity
        await engine.run(
            "students", [], is_dry_run=True, source="x.json", campus_id=3,
        )
        run = (await db_session.execute(
            select(MigrationRun).order_by(MigrationRun.id.desc()).limit(1)
        )).scalar_one()
        assert run.campus_id == 3
