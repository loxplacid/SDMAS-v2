from __future__ import annotations

import datetime
import logging
import os
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ConflictError, ValidationError
from app.domains.audit.actors import AuditActor
from app.domains.audit.service import AuditService
from app.domains.documents.validation import FileValidator
from app.domains.jobs.schemas import JobCreate
from app.domains.jobs.service import JobService
from app.domains.migration.discovery import (
    build_default_mapping,
    detect_entities,
    parse_source,
    profile_columns,
    suggest_mappings,
)
from app.domains.migration.models import (
    MIGRATION_STATUS_CANCELLED,
    MIGRATION_STATUS_COMPLETED,
    MIGRATION_STATUS_DISCOVERING,
    MIGRATION_STATUS_DRAFT,
    MIGRATION_STATUS_IMPORTING,
    MIGRATION_STATUS_MAPPING,
    MIGRATION_STATUS_RECONCILING,
    MIGRATION_STATUS_READY,
    MIGRATION_STATUS_ROLLED_BACK,
    MIGRATION_STATUS_VALIDATING,
    MIGRATION_TRANSITIONS,
    MigrationProject,
)
from app.domains.migration.project_repository import MigrationProjectRepository
from app.domains.migration.transforms import apply_mapping
from app.domains.migration.workspace_import import student_rows
from app.domains.migration.workspace_validation import validate_records
from app.multi_tenant.models import TenantContext

logger = logging.getLogger(__name__)

#: File types the migration workspace can parse (D2.2 / Step 2).
ALLOWED_MIGRATION_EXTENSIONS = (".csv", ".xlsx", ".json", ".jsonl")

#: Import chunk size for the background job (D2.8).
IMPORT_CHUNK_SIZE = 200


class MigrationProjectService:
    """Tenant-scoped orchestration for the D2 Migration Center.

    Every method takes the caller's ``TenantContext``; projects are resolved
    through :class:`MigrationProjectRepository` which pins to ``campus_id``.
    Every mutating operation writes an audit entry with the caller as actor.
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        *,
        user_id: int | None = None,
        username: str | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.user_id = user_id
        self.username = username
        self.repo = MigrationProjectRepository(session, tenant)

    # ── Audit helper ────────────────────────────────────────────────────

    async def _audit(
        self,
        action: str,
        resource_id: str,
        *,
        details: dict[str, Any] | None = None,
        result: str = "SUCCESS",
        failure_reason: str | None = None,
    ) -> None:
        try:
            actor = (
                AuditActor.user(self.user_id, self.username)
                if self.user_id is not None
                else AuditActor.system(reason="migration_workspace")
            )
            await AuditService(self.session, self.tenant).record(
                action=action,
                resource_type="migration_project",
                resource_id=resource_id,
                actor=actor,
                details=details,
                result=result,
                failure_reason=failure_reason,
            )
        except Exception:
            logger.warning("Failed to write audit for %s %s (non-fatal)", action, resource_id)

    # ── Lifecycle guard ─────────────────────────────────────────────────

    def _assert_transition(self, project: MigrationProject, to: str) -> None:
        allowed = MIGRATION_TRANSITIONS.get(project.status, set())
        if to not in allowed:
            raise ConflictError(f"Cannot move migration project from {project.status} to {to}")

    # ── File storage ────────────────────────────────────────────────────

    def _storage(self):
        return migration_storage()

    # ── Create + discover (D2.2 / D2.3) ─────────────────────────────────

    async def create_project(
        self,
        *,
        name: str,
        source_system: str,
        description: str | None,
        filename: str,
        file_data: bytes,
        mime_type: str | None = None,
    ) -> MigrationProject:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Project name is required")

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_MIGRATION_EXTENSIONS:
            raise ValidationError(
                "Unsupported file type "
                f"'{ext}'. Supported: {', '.join(ALLOWED_MIGRATION_EXTENSIONS)}"
            )
        FileValidator.validate_size(len(file_data))

        now = datetime.datetime.now(datetime.timezone.utc)
        project = MigrationProject(
            campus_id=self.tenant.campus_id,
            name=name,
            source_system=(source_system or "Generic CSV").strip() or "Generic CSV",
            description=description,
            status=MIGRATION_STATUS_DRAFT,
            original_filename=os.path.basename(filename)[:255],
            file_mime=mime_type,
            file_size=len(file_data),
            operator_id=self.user_id,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
        )
        project = await self.repo.create(project)

        # Store under a generated key — never a user-controlled path.
        safe_ext = ext.lstrip(".") or "csv"
        storage_key = f"{self.tenant.campus_id}/{project.id}/{uuid.uuid4().hex}.{safe_ext}"
        await self._storage().upload(
            file_data, storage_key, mime_type or "application/octet-stream"
        )
        await self.repo.touch(project.id, file_key=storage_key)
        project.file_key = storage_key

        await self._discover(project)
        # Re-read so JSON columns (discovery, mapping) are populated on the
        # returned object (repo.touch issues targeted UPDATEs, not refreshes).
        return await self.repo.get_by_id(project.id)

    async def _discover(self, project: MigrationProject) -> None:
        """Parse the uploaded file, profile columns, infer mappings (D2.3)."""
        self._assert_transition(project, MIGRATION_STATUS_DISCOVERING)
        await self.repo.update_status(project.id, MIGRATION_STATUS_DISCOVERING)

        file_data = await self._storage().download(project.file_key)
        records = parse_source(file_data, project.original_filename or "")
        profiles = profile_columns(records)
        suggestions = suggest_mappings([p.name for p in profiles], profiles)
        mapping = build_default_mapping(suggestions)
        entities = detect_entities(mapping)

        discovery = {
            "record_count": len(records),
            "columns": [vars(p) for p in profiles],
            "suggestions": [vars(s) for s in suggestions],
            "entities": entities,
        }
        await self.repo.touch(
            project.id,
            discovery=discovery,
            mapping=mapping,
            row_count=len(records),
            status=MIGRATION_STATUS_MAPPING,
            last_activity_at=datetime.datetime.now(datetime.timezone.utc),
        )
        await self._audit(
            "MIGRATION_PROJECT_DISCOVERED",
            str(project.id),
            details={
                "rows": len(records),
                "columns": len(profiles),
                "source_system": project.source_system,
            },
        )
        logger.info(
            "Migration project %s discovered: %d records, %d columns",
            project.id,
            len(records),
            len(profiles),
        )

    # ── Mapping (D2.4) ──────────────────────────────────────────────────

    async def save_mapping(self, project_id: int, mapping: dict[str, Any]) -> MigrationProject:
        project = await self.repo.get_by_id(project_id)
        if project.status not in (
            MIGRATION_STATUS_MAPPING,
            MIGRATION_STATUS_VALIDATING,
            MIGRATION_STATUS_READY,
        ):
            self._assert_transition(project, MIGRATION_STATUS_MAPPING)
        if not isinstance(mapping, dict):
            raise ValidationError("Mapping must be an object")

        entities = detect_entities(mapping)
        await self.repo.touch(
            project_id,
            mapping=mapping,
            status=MIGRATION_STATUS_MAPPING,
            validation=None,
            last_activity_at=datetime.datetime.now(datetime.timezone.utc),
        )
        if project.discovery is not None:
            discovery = dict(project.discovery)
            discovery["entities"] = entities
            await self.repo.touch(project_id, discovery=discovery)
        await self._audit(
            "MIGRATION_PROJECT_MAPPING_SAVED",
            str(project_id),
            details={
                "mapped_fields": len(
                    [s for s in mapping.values() if isinstance(s, dict) and s.get("target")]
                )
            },
        )
        return await self.repo.get_by_id(project_id)

    # ── Validate (D2.6 / Step 2) ───────────────────────────────────────

    async def run_validation(self, project_id: int) -> dict[str, Any]:
        """Apply mapping + transforms, run migrator rules + Step-2 checks.

        Combines the migrator's own rule sets (single source of truth for
        what each importer accepts) with the cross-cutting workspace checks
        (duplicates, malformed dates/amounts/emails, enums, orphan
        references).  Results are categorised BLOCKING / WARNING / INFO;
        a migration cannot reach READY while blocking errors exist.
        """
        project = await self.repo.get_by_id(project_id)
        if not project.mapping:
            raise ValidationError("Save a field mapping before validating")

        file_data = await self._storage().download(project.file_key)
        records = parse_source(file_data, project.original_filename or "")
        transformed = apply_mapping(records, project.mapping)

        entities = detect_entities(project.mapping) or ["students"]
        blocking: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        # 1. Migrator rule sets for the detected entities — the same rules
        #    the importer enforces at execution time.
        if "students" in entities:
            from app.domains.migration.engine import get_migrator
            from app.domains.migration.validators import ValidationEngine

            migrator = get_migrator("students")
            if migrator is not None:
                engine = ValidationEngine()
                engine.add_rules("students", migrator._rules())
                for i, record in enumerate(transformed):
                    # Only rows that describe a person feed the student
                    # stream — attendance/fee rows share the file and must
                    # not fail the student rules.
                    if not student_rows([record]):
                        continue
                    _, vresult = engine.validate("students", [record])[0]
                    if vresult.errors:
                        blocking.append(
                            {
                                "row": i + 1,
                                "issues": vresult.errors,
                                "category": "migration_rule",
                                "record": _preview_record(record),
                            }
                        )
                    warnings.extend(
                        {"row": i + 1, "message": msg, "category": "migration_rule"}
                        for msg in vresult.warnings
                    )

        # 2. Cross-cutting workspace checks across ALL rows.
        workspace = validate_records(transformed, records, project.mapping)
        for finding in workspace.blocking:
            blocking.append(
                {
                    "row": finding.row,
                    "issues": [finding.message],
                    "category": finding.category,
                    "field": finding.field,
                    "record": _preview_record(transformed[finding.row - 1]),
                }
            )
        warnings.extend(
            {"row": f.row, "message": f.message, "category": f.category} for f in workspace.warnings
        )

        # Workspace categories already count every workspace finding once;
        # only add categories the workspace checks do not produce (e.g. the
        # migrator's own rule failures).
        categories: dict[str, int] = dict(workspace.categories)
        for entry in blocking:
            category = entry.get("category")
            if category and category not in workspace.categories:
                categories[category] = categories.get(category, 0) + 1

        summary = {
            "blocking": len(blocking),
            "warnings": len(warnings),
            "info": 0,
            "total": len(transformed),
            "samples": blocking[:25],
            "categories": categories,
            "is_ready": len(blocking) == 0,
            "validated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        status = MIGRATION_STATUS_READY if summary["is_ready"] else MIGRATION_STATUS_VALIDATING
        await self.repo.touch(
            project_id,
            validation=summary,
            status=status,
            last_activity_at=datetime.datetime.now(datetime.timezone.utc),
        )
        await self._audit(
            "MIGRATION_PROJECT_VALIDATED",
            str(project_id),
            details={
                "blocking": summary["blocking"],
                "total": summary["total"],
                "ready": summary["is_ready"],
            },
        )
        return summary

    # ── Preview (D2.7 / Step 2) ────────────────────────────────────────

    async def preview(self, project_id: int, *, limit: int = 10) -> dict[str, Any]:
        """Show BEFORE → AFTER → ACTION for representative rows.

        Each row is classified CREATE / UPDATE / SKIP / ERROR:

        * ERROR — the row fails validation (shown with its issues).
        * UPDATE — the mapped student already exists in SDMAS.
        * CREATE — a new record will be inserted.
        * SKIP — no mapped target fields on the row.
        """
        project = await self.repo.get_by_id(project_id)
        file_data = await self._storage().download(project.file_key)
        records = parse_source(file_data, project.original_filename or "")
        transformed = apply_mapping(records, project.mapping)

        # Full-set validation so duplicate/orphan checks have global context.
        validation = validate_records(transformed, records, project.mapping)
        blocking_by_row = validation.blocking_by_row

        # Which mapped student numbers already exist? (one batched query)
        sample_numbers = [
            str(transformed[i].get("student_number", ""))
            for i in range(min(limit, len(transformed)))
            if transformed[i].get("student_number")
        ]
        existing_numbers: set[str] = set()
        if sample_numbers:
            from sqlalchemy import select as sa_select

            from app.domains.student.models import Student

            result = await self.session.execute(
                sa_select(Student.student_number).where(Student.student_number.in_(sample_numbers))
            )
            existing_numbers = {str(r[0]) for r in result.all()}

        rows: list[dict[str, Any]] = []
        for i in range(min(limit, len(transformed))):
            before = records[i] if i < len(records) else {}
            after = transformed[i]
            row_no = i + 1
            issues = blocking_by_row.get(row_no, [])
            if issues:
                action, reason = "ERROR", " ".join(issues)
            elif after.get("student_number") and str(after["student_number"]) in existing_numbers:
                action, reason = "UPDATE", "Student already exists in SDMAS — will be skipped"
            elif _has_mapped_target(after):
                action, reason = "CREATE", "A new record will be created"
            else:
                action, reason = "SKIP", "No mapped target fields on this row"
            rows.append(
                {
                    "row": row_no,
                    "before": before,
                    "after": after,
                    "status": "error" if issues else "ok",
                    "action": action,
                    "action_reason": reason,
                }
            )
        return {
            "total": len(records),
            "limit": limit,
            "rows": rows,
            "mapping": project.mapping,
        }

    # ── Import (D2.8) ───────────────────────────────────────────────────

    async def start_import(self, project_id: int) -> MigrationProject:
        project = await self.repo.get_by_id(project_id)
        self._assert_transition(project, MIGRATION_STATUS_IMPORTING)

        # Imported lazily to avoid a module-level cycle (import_job imports
        # this module for chunk-size/entity constants).
        from app.domains.migration.import_job import MIGRATION_IMPORT_JOB_TYPE

        job_svc = JobService(self.session, self.tenant)
        job = await job_svc.create_job(
            JobCreate(
                job_type=MIGRATION_IMPORT_JOB_TYPE,
                params={"project_id": project.id},
                user_id=self.user_id,
                campus_id=self.tenant.campus_id,
                identity_key=f"migration.import.project.{project.id}",
            )
        )
        now = datetime.datetime.now(datetime.timezone.utc)
        await self.repo.touch(
            project_id,
            job_id=job.id,
            status=MIGRATION_STATUS_IMPORTING,
            started_at=now,
            last_activity_at=now,
        )
        await self._audit(
            "MIGRATION_PROJECT_IMPORT_STARTED",
            str(project_id),
            details={"job_id": job.id, "rows": project.row_count},
        )
        return await self.repo.get_by_id(project_id)

    async def get_progress(self, project_id: int) -> dict[str, Any]:
        project = await self.repo.get_by_id(project_id)
        job = None
        if project.job_id:
            from app.domains.jobs.repository import JobRepository
            from app.multi_tenant.models import platform_context

            job_repo = JobRepository(self.session, platform_context())
            job = await job_repo.get_by_id(project.job_id)
        return {
            "project_id": project.id,
            "status": project.status,
            "records_processed": project.records_processed,
            "records_imported": project.records_imported,
            "records_updated": project.records_updated,
            "records_skipped": project.records_skipped,
            "records_rejected": project.records_rejected,
            "warnings": project.warnings,
            "row_count": project.row_count,
            "job": {
                "id": job.id,
                "status": job.status,
                "progress": job.progress,
                "last_error": job.last_error,
            }
            if job
            else None,
        }

    # ── Reconcile (D2.9 / Step 2) ───────────────────────────────────────

    async def reconcile(self, project_id: int) -> dict[str, Any]:
        """Derive the reconciliation report across all entity runs.

        A multi-entity migration produces one run per stream; totals are
        aggregated across every run owned by the project so the report
        reflects the whole import, not just the primary stream.
        """
        project = await self.repo.get_by_id(project_id)
        if not project.run_id:
            raise ConflictError("No migration run to reconcile — import first")

        from sqlalchemy import select as sa_select

        from app.domains.migration.models import MigrationRun
        from app.domains.migration.repository import MigrationLogRepository

        runs = (
            (
                await self.session.execute(
                    sa_select(MigrationRun).where(MigrationRun.project_id == project.id)
                )
            )
            .scalars()
            .all()
        )
        if not runs:
            raise ConflictError(f"No migration runs found for project {project.id}")

        log_repo = MigrationLogRepository(self.session)
        duplicate_count = 0
        for run in runs:
            entries, _ = await log_repo.list_by_run(run.id, level="skipped", limit=5000)
            duplicate_count += sum(
                1 for e in entries if e.message and "already exists" in e.message
            )

        created = sum(r.imported for r in runs)
        skipped = sum(r.skipped for r in runs)
        rejected = sum(r.errors for r in runs)
        warnings = sum(r.warnings for r in runs)
        report = {
            "source_records": project.row_count,
            "target_records": created + skipped,
            "created": created,
            "updated": project.records_updated,
            "skipped": skipped,
            "rejected": rejected,
            "duplicates": duplicate_count,
            "warnings": warnings,
            "run_id": project.run_id,
            "run_status": max(r.status for r in runs),
            "entities": [r.entity_type for r in runs],
            "reconciled_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        # RECONCILING → COMPLETED: reconciliation is the terminal step of the
        # project lifecycle (D2.1).  Without this transition the project would
        # sit in RECONCILING forever, and the COMPLETED → ROLLED_BACK state
        # machine edge (which ``rollback()`` requires) would be unreachable.
        if project.status == MIGRATION_STATUS_RECONCILING:
            self._assert_transition(project, MIGRATION_STATUS_COMPLETED)
            await self.repo.update_status(project_id, MIGRATION_STATUS_COMPLETED)
            project.status = MIGRATION_STATUS_COMPLETED
        await self.repo.touch(project_id, reconciliation=report)
        return report

    # ── Report (D2.10 / Step 2) ────────────────────────────────────────

    async def _report_data(self, project: MigrationProject) -> dict[str, Any]:
        """Structured report payload shared by the text/CSV/JSON views."""
        rec = project.reconciliation or {}
        entities = detect_entities(project.mapping or {}) or ["students"]
        return {
            "migration_id": project.id,
            "name": project.name,
            "source_system": project.source_system,
            "operator": project.operator_id,
            "filename": project.original_filename,
            "entities": entities,
            "created_at": project.created_at.isoformat(),
            "started_at": project.started_at.isoformat() if project.started_at else None,
            "completed_at": project.completed_at.isoformat() if project.completed_at else None,
            "status": project.status,
            "reconciliation": {
                "source_records": rec.get("source_records", project.row_count),
                "created": rec.get("created", project.records_imported),
                "updated": rec.get("updated", project.records_updated),
                "skipped": rec.get("skipped", project.records_skipped),
                "rejected": rec.get("rejected", project.records_rejected),
                "duplicates": rec.get("duplicates", 0),
                "warnings": rec.get("warnings", project.warnings),
            },
            "mapping": project.mapping or {},
        }

    async def generate_report(self, project_id: int) -> str:
        """Generate the downloadable migration report (plain text)."""
        project = await self.repo.get_by_id(project_id)
        data = await self._report_data(project)
        rec = data["reconciliation"]
        lines = [
            "=" * 72,
            "  SDMAS MIGRATION REPORT",
            "=" * 72,
            f"  Migration ID:    {data['migration_id']}",
            f"  Name:            {data['name']}",
            f"  Source system:   {data['source_system']}",
            f"  Operator:        {data['operator']}",
            f"  Created:         {data['created_at']}",
            f"  Started:         {data['started_at'] or '-'}",
            f"  Completed:       {data['completed_at'] or '-'}",
            f"  Status:          {data['status']}",
            f"  Entities:        {', '.join(data['entities'])}",
            "",
            "  RECONCILIATION",
            "  --------------",
            f"  Source records:  {rec['source_records']}",
            f"  Created:         {rec['created']}",
            f"  Updated:         {rec['updated']}",
            f"  Skipped:         {rec['skipped']}",
            f"  Rejected:        {rec['rejected']}",
            f"  Duplicates:      {rec['duplicates']}",
            f"  Warnings:        {rec['warnings']}",
            "",
            "  MAPPING",
            "  -------",
        ]
        for source, spec in (project.mapping or {}).items():
            if isinstance(spec, dict):
                lines.append(
                    f"    {source} -> {spec.get('target', '-')} "
                    f"({spec.get('confidence', '-')}) "
                    f"transforms={[t.get('op') for t in (spec.get('transforms') or [])]}"
                )
        lines.append("")
        lines.append("=" * 72)
        return "\n".join(lines)

    async def generate_report_csv(self, project_id: int) -> str:
        """Flat key/value CSV view of the report (importable into sheets)."""
        project = await self.repo.get_by_id(project_id)
        data = await self._report_data(project)
        lines = ["section,key,value"]
        for section, fields in (
            (
                "identity",
                {
                    "migration_id": data["migration_id"],
                    "name": data["name"],
                    "source_system": data["source_system"],
                    "operator": data["operator"],
                    "filename": data["filename"] or "",
                    "status": data["status"],
                    "entities": "|".join(data["entities"]),
                    "created_at": data["created_at"],
                    "started_at": data["started_at"] or "",
                    "completed_at": data["completed_at"] or "",
                },
            ),
            ("reconciliation", data["reconciliation"]),
        ):
            for key, value in fields.items():
                lines.append(f"{section},{key},{value}")
        return "\n".join(lines)

    async def generate_report_json(self, project_id: int) -> str:
        """Structured JSON view of the report (machine-readable)."""
        import json

        project = await self.repo.get_by_id(project_id)
        data = await self._report_data(project)
        return json.dumps(data, indent=2, default=str)

    # ── Cancel / rollback (D2.12) ───────────────────────────────────────

    async def cancel(self, project_id: int) -> MigrationProject:
        project = await self.repo.get_by_id(project_id)
        if project.status == MIGRATION_STATUS_IMPORTING and project.job_id:
            job_svc = JobService(self.session, self.tenant)
            job = await job_svc.cancel_job(project.job_id)
            if job is not None:
                logger.info("Cancelled job %d for migration project %d", job.id, project_id)
        await self.repo.update_status(project_id, MIGRATION_STATUS_CANCELLED)
        await self._audit("MIGRATION_PROJECT_CANCELLED", str(project_id))
        return await self.repo.get_by_id(project_id)

    async def rollback(self, project_id: int) -> dict[str, Any]:
        """Roll back records created by this project's import (D2.12).

        Only touches records whose origin is tracked in ``migration_mappings``
        for this run — pre-existing records are never deleted.
        """
        project = await self.repo.get_by_id(project_id)
        self._assert_transition(project, MIGRATION_STATUS_ROLLED_BACK)
        if not project.run_id:
            raise ConflictError("Nothing to roll back — no import run exists")

        from sqlalchemy import select as sa_select

        from app.domains.migration.models import MigrationRun
        from app.domains.migration.rollback import RollbackService

        # A multi-entity import produced one run per stream (students,
        # academic, attendance, fees).  Rolling back only ``project.run_id``
        # (the first run) would orphan every other stream's rows — e.g.
        # deleting students while their enrollments, attendance and payments
        # remain.  Roll back EVERY run owned by the project, in reverse
        # dependency order (fees/attendance first, then academic, then
        # students) so FK constraints never break.
        runs = (
            await self.session.execute(
                sa_select(MigrationRun).where(MigrationRun.project_id == project.id)
            )
        ).scalars().all()
        if not runs:
            raise ConflictError("No migration runs to roll back — import first")

        svc = RollbackService(self.session)
        ordered = sorted(
            runs,
            key=lambda r: RollbackService.ROLLBACK_ORDER.get(r.entity_type, 5),
        )
        total = 0
        for run in ordered:
            total += await svc.execute_rollback(run.id, campus_id=project.campus_id)
        await self.repo.touch(
            project_id,
            status=MIGRATION_STATUS_ROLLED_BACK,
            completed_at=datetime.datetime.now(datetime.timezone.utc),
        )
        await self._audit(
            "MIGRATION_PROJECT_ROLLED_BACK",
            str(project_id),
            details={"records_removed": total, "runs_rolled_back": len(ordered)},
        )
        return {"records_removed": total, "runs_rolled_back": len(ordered)}


def _preview_record(record: dict[str, Any]) -> dict[str, Any]:
    """Trim a record for embedding in validation summaries."""
    return {k: str(v)[:80] for k, v in list(record.items())[:8]}


def _has_mapped_target(record: dict[str, Any]) -> bool:
    """True when the transformed record carries at least one mapped field
    that the importer could act on."""
    targets = {
        "student_number",
        "first_name",
        "last_name",
        "email",
        "date_of_birth",
        "gender",
        "status",
        "guardian_phone",
        "class_name",
        "section_name",
        "academic_year_name",
        "attendance_date",
        "attendance_status",
        "amount_paid",
        "fee_type_name",
        "payment_date",
        "receipt_no",
    }
    return any(record.get(field) is not None for field in targets)


def migration_storage():
    """Shared storage backend for migration source files.

    Files live under ``{storage_root}/migrations/{campus_id}/{project_id}/``
    with generated keys — never user-controlled paths (D2.15).
    """
    from app.domains.documents.storage import LocalStorageBackend

    root = os.path.join(settings.storage_root, "migrations")
    return LocalStorageBackend(root=root)
