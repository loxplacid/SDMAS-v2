from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import select

from app.domains.attendance.models import AttendanceRecord
from app.domains.migration.base import BaseMigrator, MigratorResult
from app.domains.migration.engine import register_migrator
from app.domains.migration.validators import ValidationRule, one_of, required


@register_migrator
class AttendanceMigrator(BaseMigrator):
    """Migrates attendance records.

    Expects records with fields:
        legacy_id, student_id, academic_year_id, class_id, section_id,
        attendance_date, status, notes, campus_id (optional)
    """

    entity_type = "attendance"
    table_name = "attendance_records"
    dependencies = ["students", "academic"]

    def _rules(self) -> list[ValidationRule]:
        return [
            required("student_id"),
            required("academic_year_id"),
            required("class_id"),
            required("section_id"),
            required("attendance_date"),
            required("status"),
            one_of("status", {"present", "absent", "late", "excused", "holiday"}),
        ]

    async def validate(
        self,
        records: list[dict[str, Any]],
        session: Any,
        run_id: int,
        log_repo: Any,
    ) -> list[dict[str, Any]]:
        from app.domains.migration.validators import ValidationEngine

        engine = ValidationEngine()
        engine.add_rules("attendance", self._rules())
        validated: list[dict[str, Any]] = []
        for record, result in engine.validate("attendance", records):
            if result.is_valid:
                validated.append(record)
            else:
                await log_repo.log(
                    run_id=run_id,
                    level="error",
                    entity_type="attendance",
                    legacy_id=record.get("legacy_id"),
                    message="Validation failed",
                    details={"errors": result.errors},
                )
        return validated

    async def migrate(
        self,
        records: list[dict[str, Any]],
        session: Any,
        run_id: int,
        mapping_repo: Any,
        log_repo: Any,
    ) -> MigratorResult:
        result = MigratorResult(entity_type="attendance", total=len(records))

        for record in records:
            legacy_id = str(record.get("legacy_id", ""))
            student_id = record.get("student_id")
            att_date = str(record.get("attendance_date", ""))
            section_id = record.get("section_id")

            try:
                existing = await session.execute(
                    select(AttendanceRecord).where(
                        AttendanceRecord.student_id == student_id,
                        AttendanceRecord.attendance_date == att_date,
                        AttendanceRecord.section_id == section_id,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    result.skipped += 1
                    await log_repo.log(
                        run_id=run_id,
                        level="skipped",
                        entity_type="attendance",
                        legacy_id=legacy_id,
                        message=f"Attendance for student {student_id} on {att_date} already exists",
                    )
                    continue

                rec = AttendanceRecord(
                    student_id=student_id,
                    academic_year_id=record.get("academic_year_id"),
                    class_id=record.get("class_id"),
                    section_id=section_id,
                    attendance_date=att_date,
                    status=record.get("status", "present"),
                    notes=record.get("notes"),
                    campus_id=record.get("campus_id"),
                    recorded_at=datetime.datetime.now(datetime.timezone.utc),
                    updated_at=datetime.datetime.now(datetime.timezone.utc),
                )
                session.add(rec)
                await session.flush()
                # Track the record in the run's mapping table so rollback
                # can remove exactly the rows this run created.
                await mapping_repo.record(run_id, "attendance", legacy_id, rec.id)

                result.imported += 1
                await log_repo.log(
                    run_id=run_id,
                    level="imported",
                    entity_type="attendance",
                    legacy_id=legacy_id,
                    message=f"Attendance record imported as SDMAS ID {rec.id}",
                )
            except Exception as exc:
                result.errors += 1
                result.error_details.append(
                    {
                        "legacy_id": legacy_id,
                        "student_id": student_id,
                        "date": att_date,
                        "error": str(exc),
                    }
                )
                await log_repo.log(
                    run_id=run_id,
                    level="error",
                    entity_type="attendance",
                    legacy_id=legacy_id,
                    message=f"Failed: {exc}",
                    details={"error": str(exc)},
                )

        return result
