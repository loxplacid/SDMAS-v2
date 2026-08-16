from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import select

from app.domains.academic.models import (
    AcademicYear,
    Class,
    Enrollment,
    Section,
    Subject,
    Teacher,
    TeacherAssignment,
    Term,
)
from app.domains.migration.base import BaseMigrator, MigratorResult
from app.domains.migration.engine import register_migrator
from app.domains.migration.validators import ValidationRule, max_length, required


@register_migrator
class AcademicMigrator(BaseMigrator):
    """Migrates academic structure: academic_years, classes, sections,
    subjects, teachers, terms, enrollments, teacher_assignments.

    Expects a list-of-dicts where each dict has a key per entity type::

        {"academic_years": [...], "classes": [...], ...}
    """

    entity_type = "academic"
    dependencies = ["students"]

    async def validate(
        self,
        records: list[dict[str, Any]],
        session: Any,
        run_id: int,
        log_repo: Any,
    ) -> list[dict[str, Any]]:
        return records

    async def migrate(
        self,
        records: list[dict[str, Any]],
        session: Any,
        run_id: int,
        mapping_repo: Any,
        log_repo: Any,
    ) -> MigratorResult:
        result = MigratorResult(entity_type="academic", total=len(records))

        for container in records:
            ay_records = container.get("academic_years", [])
            cls_records = container.get("classes", [])
            sec_records = container.get("sections", [])
            subj_records = container.get("subjects", [])
            tchr_records = container.get("teachers", [])
            term_records = container.get("terms", [])
            enroll_records = container.get("enrollments", [])
            assign_records = container.get("teacher_assignments", [])

            # academic_years
            for rec in ay_records:
                await self._import_ay(rec, session, run_id, mapping_repo, log_repo, result)

            # classes
            for rec in cls_records:
                await self._import_class(rec, session, run_id, mapping_repo, log_repo, result)

            # sections
            for rec in sec_records:
                await self._import_section(rec, session, run_id, mapping_repo, log_repo, result)

            # subjects
            for rec in subj_records:
                await self._import_subject(rec, session, run_id, mapping_repo, log_repo, result)

            # teachers
            for rec in tchr_records:
                await self._import_teacher(rec, session, run_id, mapping_repo, log_repo, result)

            # terms
            for rec in term_records:
                await self._import_term(rec, session, run_id, mapping_repo, log_repo, result)

            # enrollments
            for rec in enroll_records:
                await self._import_enrollment(rec, session, run_id, mapping_repo, log_repo, result)

            # teacher_assignments
            for rec in assign_records:
                await self._import_assignment(rec, session, run_id, mapping_repo, log_repo, result)

        return result

    async def _import_ay(self, rec, session, run_id, mapping_repo, log_repo, result):
        lid = str(rec.get("legacy_id", ""))
        try:
            entity = AcademicYear(
                name=rec.get("name", ""),
                start_date=_parse_date(rec.get("start_date")),
                end_date=_parse_date(rec.get("end_date")),
                campus_id=rec.get("campus_id"),
                status=rec.get("status", "active"),
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(entity)
            await session.flush()
            await mapping_repo.record(run_id, "academic_year", lid, entity.id)
            result.imported += 1
            await log_repo.log(run_id, "imported", "academic", lid, "academic_year",
                               f"AcademicYear '{entity.name}' imported as ID {entity.id}")
        except Exception as exc:
            result.errors += 1
            result.error_details.append({"legacy_id": lid, "subtype": "academic_year", "error": str(exc)})
            await log_repo.log(run_id, "error", "academic", lid, "academic_year", f"Failed: {exc}")

    async def _import_class(self, rec, session, run_id, mapping_repo, log_repo, result):
        lid = str(rec.get("legacy_id", ""))
        try:
            entity = Class(
                name=rec.get("name", ""),
                academic_year_id=rec.get("academic_year_id"),
                campus_id=rec.get("campus_id"),
                status=rec.get("status", "active"),
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(entity)
            await session.flush()
            await mapping_repo.record(run_id, "class", lid, entity.id)
            result.imported += 1
            await log_repo.log(run_id, "imported", "academic", lid, "class",
                               f"Class '{entity.name}' imported as ID {entity.id}")
        except Exception as exc:
            result.errors += 1
            result.error_details.append({"legacy_id": lid, "subtype": "class", "error": str(exc)})
            await log_repo.log(run_id, "error", "academic", lid, "class", f"Failed: {exc}")

    async def _import_section(self, rec, session, run_id, mapping_repo, log_repo, result):
        lid = str(rec.get("legacy_id", ""))
        try:
            entity = Section(
                name=rec.get("name", ""),
                class_id=rec.get("class_id"),
                campus_id=rec.get("campus_id"),
                status=rec.get("status", "active"),
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(entity)
            await session.flush()
            await mapping_repo.record(run_id, "section", lid, entity.id)
            result.imported += 1
            await log_repo.log(run_id, "imported", "academic", lid, "section",
                               f"Section '{entity.name}' imported as ID {entity.id}")
        except Exception as exc:
            result.errors += 1
            result.error_details.append({"legacy_id": lid, "subtype": "section", "error": str(exc)})
            await log_repo.log(run_id, "error", "academic", lid, "section", f"Failed: {exc}")

    async def _import_subject(self, rec, session, run_id, mapping_repo, log_repo, result):
        lid = str(rec.get("legacy_id", ""))
        try:
            entity = Subject(
                name=rec.get("name", ""),
                code=rec.get("code", ""),
                description=rec.get("description"),
                campus_id=rec.get("campus_id"),
                status=rec.get("status", "active"),
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(entity)
            await session.flush()
            await mapping_repo.record(run_id, "subject", lid, entity.id)
            result.imported += 1
            await log_repo.log(run_id, "imported", "academic", lid, "subject",
                               f"Subject '{entity.name}' imported as ID {entity.id}")
        except Exception as exc:
            result.errors += 1
            result.error_details.append({"legacy_id": lid, "subtype": "subject", "error": str(exc)})
            await log_repo.log(run_id, "error", "academic", lid, "subject", f"Failed: {exc}")

    async def _import_teacher(self, rec, session, run_id, mapping_repo, log_repo, result):
        lid = str(rec.get("legacy_id", ""))
        try:
            entity = Teacher(
                first_name=rec.get("first_name", ""),
                last_name=rec.get("last_name", ""),
                employee_number=rec.get("employee_number", ""),
                email=rec.get("email"),
                campus_id=rec.get("campus_id"),
                status=rec.get("status", "active"),
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(entity)
            await session.flush()
            await mapping_repo.record(run_id, "teacher", lid, entity.id)
            result.imported += 1
            await log_repo.log(run_id, "imported", "academic", lid, "teacher",
                               f"Teacher '{entity.employee_number}' imported as ID {entity.id}")
        except Exception as exc:
            result.errors += 1
            result.error_details.append({"legacy_id": lid, "subtype": "teacher", "error": str(exc)})
            await log_repo.log(run_id, "error", "academic", lid, "teacher", f"Failed: {exc}")

    async def _import_term(self, rec, session, run_id, mapping_repo, log_repo, result):
        lid = str(rec.get("legacy_id", ""))
        try:
            entity = Term(
                name=rec.get("name", ""),
                academic_year_id=rec.get("academic_year_id"),
                start_date=str(rec.get("start_date", "")),
                end_date=str(rec.get("end_date", "")),
                campus_id=rec.get("campus_id"),
                status=rec.get("status", "active"),
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(entity)
            await session.flush()
            await mapping_repo.record(run_id, "term", lid, entity.id)
            result.imported += 1
            await log_repo.log(run_id, "imported", "academic", lid, "term",
                               f"Term '{entity.name}' imported as ID {entity.id}")
        except Exception as exc:
            result.errors += 1
            result.error_details.append({"legacy_id": lid, "subtype": "term", "error": str(exc)})
            await log_repo.log(run_id, "error", "academic", lid, "term", f"Failed: {exc}")

    async def _import_enrollment(self, rec, session, run_id, mapping_repo, log_repo, result):
        lid = str(rec.get("legacy_id", ""))
        try:
            entity = Enrollment(
                student_id=rec.get("student_id"),
                academic_year_id=rec.get("academic_year_id"),
                class_id=rec.get("class_id"),
                section_id=rec.get("section_id"),
                campus_id=rec.get("campus_id"),
                status=rec.get("status", "active"),
                enrolled_at=datetime.datetime.now(datetime.timezone.utc),
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(entity)
            await session.flush()
            await mapping_repo.record(run_id, "enrollment", lid, entity.id)
            result.imported += 1
            await log_repo.log(run_id, "imported", "academic", lid, "enrollment",
                               f"Enrollment imported as ID {entity.id}")
        except Exception as exc:
            result.errors += 1
            result.error_details.append({"legacy_id": lid, "subtype": "enrollment", "error": str(exc)})
            await log_repo.log(run_id, "error", "academic", lid, "enrollment", f"Failed: {exc}")

    async def rollback(self, run_id, session, mapping_repo):
        """Delete every academic row this run created, in FK-safe order.

        The academic migrator records mappings per *subtype* (``academic_year``,
        ``class``, ``section``, ``enrollment``, …) — the base rollback looks
        them up by run entity type and would find nothing.  Here the run's
        whole mapping set is grouped by subtype and deleted children-first so
        FK constraints never break.
        """
        from sqlalchemy import delete

        mappings = await mapping_repo.list_by_run(run_id)
        by_type: dict[str, list[int]] = {}
        for m in mappings:
            by_type.setdefault(m.entity_type, []).append(m.sdmas_id)

        # Child tables before parents: assignments → enrollments → terms →
        # sections → subjects → classes → teachers → academic_years.
        table_by_type = [
            ("teacher_assignment", TeacherAssignment),
            ("enrollment", Enrollment),
            ("term", Term),
            ("section", Section),
            ("subject", Subject),
            ("class", Class),
            ("teacher", Teacher),
            ("academic_year", AcademicYear),
        ]
        total = 0
        for entity_type, model in table_by_type:
            ids = by_type.get(entity_type)
            if not ids:
                continue
            result = await session.execute(delete(model).where(model.id.in_(ids)))
            total += result.rowcount
        await session.flush()
        return total

    async def _import_assignment(self, rec, session, run_id, mapping_repo, log_repo, result):
        lid = str(rec.get("legacy_id", ""))
        try:
            entity = TeacherAssignment(
                teacher_id=rec.get("teacher_id"),
                class_id=rec.get("class_id"),
                subject_id=rec.get("subject_id"),
                campus_id=rec.get("campus_id"),
                status=rec.get("status", "active"),
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(entity)
            await session.flush()
            await mapping_repo.record(run_id, "teacher_assignment", lid, entity.id)
            result.imported += 1
            await log_repo.log(run_id, "imported", "academic", lid, "teacher_assignment",
                               f"TeacherAssignment imported as ID {entity.id}")
        except Exception as exc:
            result.errors += 1
            result.error_details.append({"legacy_id": lid, "subtype": "teacher_assignment", "error": str(exc)})
            await log_repo.log(run_id, "error", "academic", lid, "teacher_assignment", f"Failed: {exc}")


def _parse_date(val: Any) -> datetime.date | None:
    if val is None:
        return None
    if isinstance(val, datetime.date):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return datetime.date.fromisoformat(val.strip())
        except ValueError:
            pass
    return None
