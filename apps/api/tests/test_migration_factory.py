"""Migration Factory tests (TASK 15).

Covers the enterprise pipeline stages added on top of the existing
migration workspace, over a **realistic messy legacy dataset**:

- renamed columns ("Student Fullname", "Admission No", "Grade", "Sec",
  "Fees Paid", "Att Date", "Rcpt No")
- inconsistent capitalization + whitespace
- a duplicate student (same admission number, second row)
- a missing email
- an invalid attendance date (2026-02-30)
- an orphan class reference (grade "13-Z" with no academic year)
- unicode names
- valid fee records

Stages exercised:

- DISCOVER + PROFILE — source profiling: entity distribution, quality
  scorecard, PII columns, duplicate-key candidates
- IDENTITY MATCH — deterministic legacy->SDMAS matching (exact number /
  email / phone / name+DOB / fuzzy), ambiguous handling
- MAP — mapping versioning history on every save
- APPROVE — optional approval gate: request blocks import, approve
  unblocks, reject resets to VALIDATING
- DRY RUN — full pipeline transform -> validate -> classify
  (CREATE/UPDATE/SKIP/ERROR) WITHOUT touching target tables; persisted
  as an immutable snapshot
- VERIFY — post-import source-vs-target counts + spot checks
- CUTOVER — completed-only; cutover-live blocks rollback (rollback
  safety); rollback plan previews without changing data
- evidence — verify/cutover package migration evidence (non-fatal)
- tenant isolation — every factory op is campus-scoped
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.domains.migration.factory import (
    classify_rows,
    match_identity,
    profile_source,
)
from app.domains.migration.import_job import run_project_import
from app.domains.migration.models import (
    APPROVAL_APPROVED,
    APPROVAL_REJECTED,
    APPROVAL_REQUIRED_STATE,
    CUTOVER_LIVE,
    MIGRATION_STATUS_APPROVAL_REQUIRED,
    MIGRATION_STATUS_APPROVED,
    MIGRATION_STATUS_COMPLETED,
    MIGRATION_STATUS_VALIDATING,
    MigrationProject,
    MigrationSnapshot,
)
from app.domains.migration.project_service import MigrationProjectService
from app.domains.student.models import Student
from app.multi_tenant.models import TenantContext

# ---------------------------------------------------------------------------
# Realistic messy legacy dataset (renamed columns, dirty values, defects)
# ---------------------------------------------------------------------------

MESSY_CSV = (
    "Admission No,Student Fullname,DOB,Gender,E-mail,Class,Sec,Academic Year,"
    "Att Date,Attendance Status,Fee Type,Fees Paid,Payment Date,Rcpt No,Guardian Phone\n"
    # Row 1 — clean student + attendance + fee (all four streams).
    "ST-2001,John  Doe ,2005-08-14,M,john.doe@example.com,10-A,Sec 1,2025-2026,"
    "2026-08-10,Present,Tuition,45000,2026-01-10,RCT-2001,+254 700 123456\n"
    # Row 2 — duplicate of ST-2001 (same admission number) with a fee.
    "ST-2001,John DOE,2005-08-14,M,john.doe@example.com,10-A,Sec 1,2025-2026,"
    "2026-08-11,Present,Tuition,20000,2026-02-05,RCT-2001-DUP,+254 700 123456\n"
    # Row 3 — clean student, missing email, uppercase name.
    "ST-2002,JANE  SMITH ,2006-03-22,F,,10-A,Sec 1,2025-2026,"
    "2026-08-10,Absent,Tuition,30000,2026-01-11,RCT-2002,0700123456\n"
    # Row 4 — invalid attendance date (2026-02-30) + orphan class ref
    # (grade 13-Z, no year mapping).
    "ST-2003,Alex Brown,2007-01-30,M,alex.brown@example.com,13-Z,Sec 2,2025-2026,"
    "2026-02-30,Present,Tuition,15000,2026-03-01,RCT-2003,0711555999\n"
    # Row 5 — unicode name + valid fee.
    "ST-2004,\u00c9lodie M\u00fcller,2008-07-12,F,elodie.muller@example.com,9-B,Sec 1,2025-2026,"
    "2026-08-12,Present,Library,5000,2026-02-20,RCT-2004,+1 555 010 2000\n"
)

# Clean dataset (no blocking defects) for the full import → verify →
# cutover → rollback flow — same shape as MESSY_CSV so the auto-mapping
# picks up all four streams.
CLEAN_CSV = (
    "Admission No,Student Fullname,DOB,Gender,E-mail,Class,Sec,Academic Year,"
    "Att Date,Attendance Status,Fee Type,Fees Paid,Payment Date,Rcpt No,Guardian Phone\n"
    "ST-2001,John  Doe ,2005-08-14,M,john.doe@example.com,10-A,Sec 1,2025-2026,"
    "2026-08-10,Present,Tuition,45000,2026-01-10,RCT-2001,+254 700 123456\n"
    "ST-2002,Jane  Smith ,2006-03-22,F,jane.smith@example.com,10-A,Sec 1,2025-2026,"
    "2026-08-10,Absent,Tuition,30000,2026-01-11,RCT-2002,0700123456\n"
    "ST-2003,Alex Brown,2007-01-30,M,alex.brown@example.com,9-B,Sec 1,2025-2026,"
    "2026-08-11,Present,Library,5000,2026-02-20,RCT-2003,0711555999\n"
)


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
    csv: str = MESSY_CSV,
    name: str = "Legacy school export",
) -> MigrationProject:
    svc = MigrationProjectService(db_session, tenant, user_id=tenant.user_id, username="admin")
    return await svc.create_project(
        name=name,
        source_system="Legacy ERP export",
        description="messy legacy fixture",
        filename="legacy_school_export.csv",
        file_data=csv.encode("utf-8"),
        mime_type="text/csv",
    )


async def _make_clean_project(
    db_session: AsyncSession,
    tenant: TenantContext,
    *,
    name: str = "Clean import",
) -> MigrationProject:
    svc = MigrationProjectService(db_session, tenant, user_id=tenant.user_id, username="admin")
    return await svc.create_project(
        name=name,
        source_system="Legacy ERP export",
        description="clean fixture for import flow",
        filename="clean_export.csv",
        file_data=CLEAN_CSV.encode("utf-8"),
        mime_type="text/csv",
    )


def _svc(db_session: AsyncSession, tenant: TenantContext) -> MigrationProjectService:
    return MigrationProjectService(db_session, tenant, user_id=tenant.user_id, username="admin")


async def _insert_student(
    db_session: AsyncSession,
    *,
    student_number: str,
    first_name: str,
    last_name: str,
    email: str | None = None,
    dob: str | None = None,
    campus_id: int = 1,
) -> Student:
    import datetime

    parsed_dob = None
    if dob:
        parsed_dob = datetime.date.fromisoformat(dob)
    student = Student(
        campus_id=campus_id,
        student_number=student_number,
        first_name=first_name,
        last_name=last_name,
        email=email,
        date_of_birth=parsed_dob,
        status="active",
    )
    db_session.add(student)
    await db_session.flush()
    return student


# ---------------------------------------------------------------------------
# Pure: source profiling
# ---------------------------------------------------------------------------


class TestSourceProfiling:
    def test_entity_distribution_and_duplicates(self) -> None:
        from app.domains.migration.discovery import parse_source
        from app.domains.migration.transforms import apply_mapping

        records = parse_source(MESSY_CSV.encode(), "legacy_school_export.csv")
        project = _mapping_project()
        transformed = apply_mapping(records, project.mapping)
        profile = profile_source(records, project.mapping)

        assert profile["row_count"] == 5
        assert profile["entities"]["students"] == 5
        # The duplicate ST-2001 is flagged as a duplicate-key candidate.
        numbers = [c["value"] for c in profile["duplicate_candidates"]]
        assert "ST-2001" in numbers
        # Scorecard covers mapped targets.
        assert "student_number" in profile["scorecard"]
        assert "email" in profile["scorecard"]
        assert profile["scorecard"]["email"]["fill_rate"] < 1.0  # row 3 missing
        # PII columns detected deterministically.
        assert "E-mail" in profile["pii_columns"]
        assert len(transformed) == 5

    def test_profile_is_deterministic(self) -> None:
        from app.domains.migration.discovery import parse_source

        records = parse_source(MESSY_CSV.encode(), "x.csv")
        project = _mapping_project()
        assert profile_source(records, project.mapping) == profile_source(records, project.mapping)

    async def test_profile_endpoint_persists(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = _svc(db_session, tenant_a)
        profile = await svc.profile(project.id)
        assert profile["row_count"] == 5
        assert profile["profiled_at"] is not None
        refreshed = await svc.repo.get_by_id(project.id)
        assert refreshed.profile is not None
        assert refreshed.profile["row_count"] == 5


# ---------------------------------------------------------------------------
# Pure: identity matching
# ---------------------------------------------------------------------------


class TestIdentityMatching:
    def test_matching_ladder(self) -> None:
        existing = [
            {
                "id": 11,
                "student_number": "ST-2001",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "guardian_phone": "+254700123456",
                "date_of_birth": "2005-08-14",
            },
            {
                "id": 12,
                "student_number": "ST-9999",
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane.smith@example.com",
                "guardian_phone": "0700123456",
                "date_of_birth": "2006-03-22",
            },
        ]
        transformed = [
            # Exact number match (high).
            {
                "student_number": "ST-2001",
                "first_name": "John",
                "last_name": "Doe",
                "email": None,
                "guardian_phone": None,
                "date_of_birth": None,
            },
            # Email match (high), different number.
            {
                "student_number": "NEW-1",
                "first_name": "J.",
                "last_name": "Smith",
                "email": "JANE.SMITH@EXAMPLE.COM",
                "guardian_phone": None,
                "date_of_birth": None,
            },
            # Phone match (medium).
            {
                "student_number": "NEW-2",
                "first_name": "Someone",
                "last_name": "Else",
                "email": None,
                "guardian_phone": "0700 123 456",
                "date_of_birth": None,
            },
            # No match.
            {
                "student_number": "NEW-3",
                "first_name": "Nobody",
                "last_name": "Here",
                "email": "nobody@example.com",
                "guardian_phone": None,
                "date_of_birth": "2009-09-09",
            },
        ]
        result = match_identity(transformed, existing)
        assert result["total"] == 4
        assert result["matched"] == 3
        assert result["no_match"] == 1
        by_row = {r["row"]: r for r in result["rows"]}
        assert by_row[1]["sdmas_id"] == 11
        assert by_row[1]["method"] == "student_number"
        assert by_row[1]["confidence"] == "high"
        assert by_row[2]["sdmas_id"] == 12
        assert by_row[2]["method"] == "email"
        assert by_row[3]["sdmas_id"] == 12
        assert by_row[3]["method"] == "guardian_phone"
        assert by_row[4]["decision"] == "no_match"

    def test_name_dob_and_ambiguous(self) -> None:
        existing = [
            # A1 uniquely shares Z1's name+DOB (2009) — unambiguous match.
            {
                "id": 21,
                "student_number": "A1",
                "first_name": "Alice",
                "last_name": "Ng",
                "email": None,
                "guardian_phone": None,
                "date_of_birth": "2009-05-05",
            },
            # A2 and A3 are indistinguishable twins (identical name+DOB) —
            # any row with this name+DOB must be flagged for manual review.
            {
                "id": 22,
                "student_number": "A2",
                "first_name": "Alice",
                "last_name": "Ng",
                "email": None,
                "guardian_phone": None,
                "date_of_birth": "2010-05-05",
            },
            {
                "id": 23,
                "student_number": "A3",
                "first_name": "Alice",
                "last_name": "Ng",
                "email": None,
                "guardian_phone": None,
                "date_of_birth": "2010-05-05",
            },
        ]
        transformed = [
            # Name+DOB exact match (medium) — only A1 shares this DOB.
            {
                "student_number": "Z1",
                "first_name": "Alice",
                "last_name": "Ng",
                "email": None,
                "guardian_phone": None,
                "date_of_birth": "05/05/2009",
            },
            # Ambiguous: this name+DOB is shared by TWO existing students
            # (A2, A3) — the matcher must flag it, not pick one.
            {
                "student_number": "Z2",
                "first_name": "Alice",
                "last_name": "Ng",
                "email": None,
                "guardian_phone": None,
                "date_of_birth": "2010-05-05",
            },
        ]
        result = match_identity(transformed, existing)
        by_row = {r["row"]: r for r in result["rows"]}
        assert by_row[1]["decision"] == "match"
        assert by_row[1]["method"] == "name_dob"
        assert by_row[1]["sdmas_id"] == 21
        assert by_row[2]["decision"] == "ambiguous"
        assert by_row[2]["candidates"] == 2
        assert result["ambiguous"] == 1

    async def test_identity_match_service(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        await _insert_student(
            db_session,
            student_number="ST-2001",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            dob="2005-08-14",
        )
        await _insert_student(
            db_session,
            student_number="ST-2002",
            first_name="Jane",
            last_name="Smith",
            email=None,
            dob="2006-03-22",
        )
        project = await _make_project(db_session, tenant_a)
        svc = _svc(db_session, tenant_a)
        result = await svc.identity_match(project.id)
        assert result["total"] == 5
        # Rows 1 and 3 match by student_number (ST-2001 / ST-2002).
        by_row = {r["row"]: r for r in result["rows"]}
        assert by_row[1]["decision"] == "match"
        assert by_row[1]["sdmas_id"] is not None
        assert by_row[3]["decision"] == "match"
        refreshed = await svc.repo.get_by_id(project.id)
        assert refreshed.identity_match is not None
        assert refreshed.identity_match["matched"] >= 2


# ---------------------------------------------------------------------------
# Mapping versioning
# ---------------------------------------------------------------------------


class TestMappingVersioning:
    async def test_each_save_appends_version(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = _svc(db_session, tenant_a)
        mapping = dict(project.mapping or {})
        await svc.save_mapping(project.id, mapping)
        mapping["Student Fullname"] = {**mapping["Student Fullname"], "target": "first_name"}
        await svc.save_mapping(project.id, mapping)
        refreshed = await svc.repo.get_by_id(project.id)
        versions = refreshed.mapping_versions or []
        assert len(versions) == 3  # auto-discovered + 2 manual saves
        assert versions[-1]["version"] == 3
        assert versions[-1]["mapping"]["Student Fullname"]["target"] == "first_name"
        assert versions[-1]["saved_by"] == 99


# ---------------------------------------------------------------------------
# Approval gate
# ---------------------------------------------------------------------------


class TestApprovalGate:
    async def test_request_blocks_import_approve_unblocks(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        project = await _make_clean_project(db_session, tenant_a)
        svc = _svc(db_session, tenant_a)
        # Validate to READY first.
        summary = await svc.run_validation(project.id)
        assert summary["is_ready"] is True, summary.get("samples")
        assert (await svc.repo.get_by_id(project.id)).status == "READY"

        project = await svc.request_approval(project.id, note="financial migration")
        assert project.status == MIGRATION_STATUS_APPROVAL_REQUIRED
        assert project.approval["status"] == APPROVAL_REQUIRED_STATE

        # Import is blocked while awaiting approval.
        with pytest.raises(ConflictError):
            await svc.start_import(project.id)

        # Reject → back to VALIDATING, import still blocked.
        project = await svc.reject_approval(project.id, reason="fix fee amounts")
        assert project.status == MIGRATION_STATUS_VALIDATING
        assert project.approval["status"] == APPROVAL_REJECTED
        with pytest.raises(ConflictError):
            await svc.start_import(project.id)

        # Re-validate, request again, then approve → import allowed.
        summary = await svc.run_validation(project.id)
        assert summary["is_ready"] is True
        project = await svc.request_approval(project.id)
        project = await svc.approve(project.id, note="ok to proceed", approver_id=7)
        assert project.status == MIGRATION_STATUS_APPROVED
        assert project.approval["status"] == APPROVAL_APPROVED
        assert project.approval["approver_id"] == 7
        project = await svc.start_import(project.id)
        assert project.status == "IMPORTING"

    async def test_approval_is_optional(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        """Projects that never request approval import directly (back-compat)."""
        project = await _make_clean_project(db_session, tenant_a)
        svc = _svc(db_session, tenant_a)
        summary = await svc.run_validation(project.id)
        assert summary["is_ready"] is True
        project = await svc.start_import(project.id)
        assert project.status == "IMPORTING"

    async def test_approve_requires_pending_state(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = _svc(db_session, tenant_a)
        with pytest.raises(ConflictError):
            await svc.approve(project.id, note="nope")


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


class TestDryRun:
    async def test_dry_run_classifies_without_writing(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = _svc(db_session, tenant_a)
        result = await svc.dry_run(project.id)
        assert result["summary"]["total"] == 5
        # No students written.
        students = (await db_session.execute(select(Student))).scalars().all()
        assert len(students) == 0
        # Duplicate row 2 is CREATE (dry run does not dedupe within file),
        # row 4 is ERROR (invalid date), row 5 is CREATE with unicode.
        actions = {r["row"]: r["action"] for r in result["rows"]}
        assert actions[4] == "ERROR"
        assert actions[1] == "CREATE"
        # Snapshot persisted as evidence.
        snapshots = (await db_session.execute(select(MigrationSnapshot))).scalars().all()
        assert len(snapshots) == 1
        assert snapshots[0].kind == "dry_run"
        assert snapshots[0].row_count == 5

    async def test_dry_run_sees_existing_students_as_update(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        await _insert_student(
            db_session, student_number="ST-2001", first_name="John", last_name="Doe"
        )
        project = await _make_project(db_session, tenant_a)
        svc = _svc(db_session, tenant_a)
        result = await svc.dry_run(project.id)
        actions = {r["row"]: r["action"] for r in result["rows"]}
        assert actions[1] == "UPDATE"

    async def test_snapshots_list_and_get(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = _svc(db_session, tenant_a)
        await svc.dry_run(project.id)
        snapshots = await svc.list_snapshots(project.id)
        assert len(snapshots) == 1
        snapshot = await svc.get_snapshot(project.id, snapshots[0]["id"])
        assert snapshot["kind"] == "dry_run"
        assert snapshot["payload"]["rows"]

    async def test_pure_classifier(self) -> None:
        transformed = [
            {"student_number": "S1", "first_name": "A"},
            {"student_number": "S2", "first_name": "B"},
            {},
        ]
        records = [{"x": 1}, {"x": 2}, {}]
        blocking = {2: ["bad date"]}
        rows = classify_rows(transformed, records, blocking, {"S1"})
        assert rows[0]["action"] == "UPDATE"
        assert rows[1]["action"] == "ERROR"
        assert rows[2]["action"] == "SKIP"


# ---------------------------------------------------------------------------
# Full import → reconcile → verify → cutover
# ---------------------------------------------------------------------------


async def _import_and_reconcile(
    db_session: AsyncSession,
    tenant: TenantContext,
    project: MigrationProject,
) -> dict[str, Any]:
    svc = _svc(db_session, tenant)
    summary = await svc.run_validation(project.id)
    assert summary["is_ready"] is True, summary.get("samples")
    await run_project_import(db_session, tenant, project.id, job_id=None)
    await db_session.commit()
    report = await svc.reconcile(project.id)
    await db_session.commit()
    return report


class TestVerifyAndCutover:
    async def test_verify_after_import(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        project = await _make_clean_project(db_session, tenant_a)
        await _import_and_reconcile(db_session, tenant_a, project)
        svc = _svc(db_session, tenant_a)
        assert (await svc.repo.get_by_id(project.id)).status == MIGRATION_STATUS_COMPLETED

        verification = await svc.verify(project.id)
        assert verification["source_row_count"] == 3
        assert verification["passed"] is True, verification["entities"]
        student_entity = next(e for e in verification["entities"] if e["entity"] == "students")
        assert student_entity["source"] == 3
        assert student_entity["target"] == 3
        academic_classes = next(
            e for e in verification["entities"] if e["entity"] == "academic_classes"
        )
        assert academic_classes["source"] == 2  # 10-A, 9-B
        assert verification["spot_checks"]
        refreshed = await svc.repo.get_by_id(project.id)
        assert refreshed.verification is not None
        assert refreshed.verification["passed"] is True
        # Verify snapshot recorded.
        snapshots = await svc.list_snapshots(project.id, kind="verify")
        assert len(snapshots) == 1

    async def test_verify_requires_completed(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        svc = _svc(db_session, tenant_a)
        with pytest.raises(ConflictError):
            await svc.verify(project.id)

    async def test_cutover_requires_completed(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        project = await _make_clean_project(db_session, tenant_a)
        svc = _svc(db_session, tenant_a)
        with pytest.raises(ConflictError):
            await svc.cutover(project.id)

    async def test_cutover_marks_live_and_blocks_rollback(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        project = await _make_clean_project(db_session, tenant_a)
        await _import_and_reconcile(db_session, tenant_a, project)
        svc = _svc(db_session, tenant_a)
        project = await svc.cutover(project.id, note="switch over")
        assert project.cutover["status"] == CUTOVER_LIVE
        assert project.cutover["cutover_by"] == 99

        # Rollback is blocked on a cut-over migration (rollback safety).
        with pytest.raises(ConflictError):
            await svc.rollback(project.id)

    async def test_rollback_plan_previews_without_changes(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        project = await _make_clean_project(db_session, tenant_a)
        await _import_and_reconcile(db_session, tenant_a, project)
        svc = _svc(db_session, tenant_a)
        plan = await svc.rollback_plan(project.id)
        assert plan, "expected at least one run in the rollback plan"
        entities = {p["entity_type"] for p in plan}
        assert "students" in entities
        # No records removed by a plan.
        students = (await db_session.execute(select(Student))).scalars().all()
        assert len(students) == 3

    async def test_rollback_still_works_when_not_cutover(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        project = await _make_clean_project(db_session, tenant_a)
        await _import_and_reconcile(db_session, tenant_a, project)
        svc = _svc(db_session, tenant_a)
        result = await svc.rollback(project.id)
        assert result["records_removed"] >= 3
        students = (await db_session.execute(select(Student))).scalars().all()
        assert len(students) == 0


# ---------------------------------------------------------------------------
# Evidence packaging (non-fatal)
# ---------------------------------------------------------------------------


class TestMigrationEvidence:
    async def test_verify_packages_evidence(
        self, db_session: AsyncSession, tenant_a: TenantContext, storage_root
    ) -> None:
        project = await _make_clean_project(db_session, tenant_a)
        await _import_and_reconcile(db_session, tenant_a, project)
        svc = _svc(db_session, tenant_a)
        await svc.verify(project.id)
        await db_session.commit()
        from app.platform.evidence.models import EvidencePackage

        packages = (await db_session.execute(select(EvidencePackage))).scalars().all()
        keys = {p.package_key for p in packages}
        assert f"migration.project.{project.id}" in keys


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    async def test_factory_ops_cross_tenant_denied(
        self,
        db_session: AsyncSession,
        tenant_a: TenantContext,
        tenant_b: TenantContext,
        storage_root,
    ) -> None:
        project = await _make_project(db_session, tenant_a)
        svc_b = _svc(db_session, tenant_b)
        # All factory reads/mutations resolve A's project to 404 for B.
        with pytest.raises(NotFoundError):
            await svc_b.profile(project.id)
        with pytest.raises(NotFoundError):
            await svc_b.identity_match(project.id)
        with pytest.raises(NotFoundError):
            await svc_b.dry_run(project.id)
        with pytest.raises(NotFoundError):
            await svc_b.list_snapshots(project.id)
        with pytest.raises(NotFoundError):
            await svc_b.request_approval(project.id)
        with pytest.raises(NotFoundError):
            await svc_b.rollback_plan(project.id)
        with pytest.raises(NotFoundError):
            await svc_b.verify(project.id)
        with pytest.raises(NotFoundError):
            await svc_b.cutover(project.id)
        with pytest.raises(NotFoundError):
            await svc_b.get_snapshot(project.id, 1)

    async def test_cross_tenant_student_data_invisible(
        self,
        db_session: AsyncSession,
        tenant_a: TenantContext,
        tenant_b: TenantContext,
        storage_root,
    ) -> None:
        """Identity matching and dry runs only ever see the caller's campus."""
        await _insert_student(
            db_session,
            student_number="ST-2001",
            first_name="John",
            last_name="Doe",
            campus_id=2,  # tenant B's student
        )
        project = await _make_project(db_session, tenant_a)
        svc = _svc(db_session, tenant_a)
        match_result = await svc.identity_match(project.id)
        # A's match sees NO B students — ST-2001 rows are no_match for A.
        by_row = {r["row"]: r for r in match_result["rows"]}
        assert by_row[1]["decision"] == "no_match"
        dry = await svc.dry_run(project.id)
        actions = {r["row"]: r["action"] for r in dry["rows"]}
        assert actions[1] == "CREATE"  # not UPDATE — B's student is invisible


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mapping_project() -> MigrationProject:
    """A lightweight stand-in carrying just the discovered mapping (pure
    tests only — no DB involved)."""
    from app.domains.migration.discovery import (
        build_default_mapping,
        parse_source,
        profile_columns,
        suggest_mappings,
    )

    records = parse_source(MESSY_CSV.encode(), "legacy_school_export.csv")
    profiles = profile_columns(records)
    suggestions = suggest_mappings([p.name for p in profiles], profiles)
    mapping = build_default_mapping(suggestions)
    project = MigrationProject(id=1, campus_id=1, name="pure", status="DRAFT")
    project.mapping = mapping
    return project
