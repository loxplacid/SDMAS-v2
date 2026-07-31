from __future__ import annotations

import datetime
from typing import Any

from app.domains.migration.base import BaseMigrator, MigratorResult
from app.domains.migration.engine import register_migrator
from app.domains.migration.validators import (
    ValidationRule,
    max_length,
    one_of,
    required,
)


@register_migrator
class StudentMigrator(BaseMigrator):
    """Migrates students from the legacy system.

    Expects records with fields:
        legacy_id, first_name, last_name, student_number, email,
        date_of_birth, status, campus_id (optional)
    """

    entity_type = "students"
    dependencies = ["users"]

    def _rules(self) -> list[ValidationRule]:
        return [
            required("first_name"),
            required("last_name"),
            required("student_number"),
            max_length("first_name", 100),
            max_length("last_name", 100),
            max_length("student_number", 50),
            max_length("email", 255),
            one_of("status", {"active", "inactive", "graduated", "transferred", "suspended"}),
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
        engine.add_rules("students", self._rules())
        validated: list[dict[str, Any]] = []
        for record, result in engine.validate("students", records):
            if result.is_valid:
                validated.append(record)
            else:
                await log_repo.log(
                    run_id=run_id, level="error",
                    entity_type="students", legacy_id=record.get("legacy_id"),
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
        from app.domains.student.models import Student
        from sqlalchemy import select

        result = MigratorResult(entity_type="students", total=len(records))

        for record in records:
            legacy_id = str(record.get("legacy_id", ""))
            student_number = record.get("student_number", "")

            try:
                existing = await session.execute(
                    select(Student).where(
                        Student.student_number == student_number
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    result.skipped += 1
                    await log_repo.log(
                        run_id=run_id, level="skipped",
                        entity_type="students", legacy_id=legacy_id,
                        message=f"Student '{student_number}' already exists — skipped",
                    )
                    continue

                dob = record.get("date_of_birth")
                if isinstance(dob, str) and dob.strip():
                    dob = datetime.date.fromisoformat(dob)
                elif dob is None:
                    dob = None

                student = Student(
                    first_name=record.get("first_name", ""),
                    last_name=record.get("last_name", ""),
                    student_number=student_number,
                    email=record.get("email"),
                    date_of_birth=dob,
                    status=record.get("status", "active"),
                    campus_id=record.get("campus_id"),
                    created_at=datetime.datetime.now(datetime.timezone.utc),
                    updated_at=datetime.datetime.now(datetime.timezone.utc),
                )
                session.add(student)
                await session.flush()

                await mapping_repo.record(run_id, "students", legacy_id, student.id)
                result.imported += 1
                await log_repo.log(
                    run_id=run_id, level="imported",
                    entity_type="students", legacy_id=legacy_id,
                    message=f"Student '{student_number}' imported as SDMAS ID {student.id}",
                )
            except Exception as exc:
                result.errors += 1
                result.error_details.append({
                    "legacy_id": legacy_id,
                    "student_number": student_number,
                    "error": str(exc),
                })
                await log_repo.log(
                    run_id=run_id, level="error",
                    entity_type="students", legacy_id=legacy_id,
                    message=f"Failed to import student: {exc}",
                    details={"error": str(exc)},
                )

        return result
