"""Producer integration tests for the durable outbox and background jobs.

Covers:
  - Fee services enqueue durable ``FeeDueCreatedEvent`` / ``PaymentReceivedEvent``
    rows (with deterministic ``event_id`` and tenant ``school_id``) instead of
    fire-and-forget in-process dispatch.
  - Rollover enqueues a durable ``rollover_completed`` event.
  - ``ExportJobService.create_job`` enqueues a durable ``report_builder.export``
    job (no more ``asyncio.create_task``), and executing that job through the
    worker produces a completed export.
  - ``JobService.execute_job`` restores tenant context (``event_context``)
    for the executed job from ``job.campus_id`` / ``job.identity_key``.
"""

from __future__ import annotations

import datetime
from datetime import timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.events.outbox import OutboxEvent
from app.domains.fees.models import FeeDue
from app.domains.fees.repository import (
    FeeDueRepository,
    FeeTypeRepository,
    FeeStructureRepository,
    PaymentRepository,
)
from app.domains.fees.schemas import PaymentCreate
from app.domains.fees.service import PaymentService
from app.domains.jobs.models import Job
from app.domains.jobs.service import JobService
from app.domains.report_builder.service import ExportJobService
from app.domains.report_builder.registry import ReportRegistry

NOW = datetime.datetime.now(timezone.utc)


async def _outbox_rows(db_session: AsyncSession, event_type: str) -> list[OutboxEvent]:
    rows = (
        await db_session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.event_type == event_type)
            .order_by(OutboxEvent.id)
        )
    ).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# Fee producers
# ---------------------------------------------------------------------------


class TestFeeProducers:
    async def _seed_fee_env(self, db_session: AsyncSession, campus_id: int = 7):
        from app.domains.academic.models import AcademicYear, Class, Enrollment
        from app.domains.academic.repository import (
            AcademicYearRepository,
            ClassRepository,
            EnrollmentRepository,
        )
        from app.domains.fees.schemas import FeeStructureCreate, FeeTypeCreate
        from app.domains.fees.service import FeeDueService, FeeStructureService, FeeTypeService
        from app.domains.student.models import Student
        from app.domains.student.repository import StudentRepository

        year_repo = AcademicYearRepository(db_session)
        class_repo = ClassRepository(db_session)
        enrollment_repo = EnrollmentRepository(db_session)
        student_repo = StudentRepository(db_session)
        ft_repo = FeeTypeRepository(db_session)
        fs_repo = FeeStructureRepository(db_session)
        fd_repo = FeeDueRepository(db_session)

        year = await year_repo.create(
            AcademicYear(
                name="Outbox Year", start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 12, 31), status="active",
                campus_id=campus_id,
            )
        )
        cls = await class_repo.create(
            Class(name="Grade 10", academic_year_id=year.id, status="active")
        )
        student = await student_repo.create(
            Student(first_name="Alice", last_name="Smith", student_number="OUT-1", status="active")
        )
        await enrollment_repo.create(
            Enrollment(
                student_id=student.id, academic_year_id=year.id,
                class_id=cls.id, status="active", campus_id=campus_id,
            )
        )
        ft = await FeeTypeService(ft_repo).create(FeeTypeCreate(name="Tuition"))
        fs = await FeeStructureService(fs_repo, year_repo, class_repo, ft_repo).create(
            FeeStructureCreate(
                academic_year_id=year.id, class_id=cls.id,
                fee_type_id=ft.id, amount=50000, frequency="annual",
            )
        )
        fee_due_svc = FeeDueService(
            fd_repo, student_repo, year_repo, class_repo,
            enrollment_repo, fs_repo, ft_repo,
        )
        return {"fee_due_svc": fee_due_svc, "student": student, "year": year, "fs": fs}

    async def test_create_dues_enqueues_fee_due_event(
        self, db_session: AsyncSession
    ) -> None:
        env = await self._seed_fee_env(db_session)
        due = (await env["fee_due_svc"].create_dues(env["student"].id, env["year"].id))[0]

        rows = await _outbox_rows(db_session, "FeeDueCreatedEvent")
        assert len(rows) == 1
        row = rows[0]
        payload = row.payload or {}
        assert payload["student_id"] == env["student"].id
        assert payload["academic_year_id"] == env["year"].id
        assert due.id in payload["due_ids"]
        assert row.event_id == f"fee_due:{env['student'].id}:{env['year'].id}"

    async def test_record_payment_enqueues_payment_event_with_tenant(
        self, db_session: AsyncSession
    ) -> None:
        from app.domains.student.models import Student
        from app.domains.student.repository import StudentRepository

        student = Student(
            first_name="Bob", last_name="Jones", student_number="OUT-2", status="active"
        )
        db_session.add(student)
        await db_session.flush()
        due = FeeDue(
            student_id=student.id,
            academic_year_id=2026,
            fee_structure_id=1,
            original_amount=1000,
            amount_paid=0,
            status="unpaid",
            campus_id=7,
            created_at=NOW,
            updated_at=NOW,
        )
        db_session.add(due)
        await db_session.flush()

        svc = PaymentService(
            PaymentRepository(db_session),
            FeeDueRepository(db_session),
            StudentRepository(db_session),
        )
        result = await svc.record_payment(
            PaymentCreate(
                student_id=student.id,
                fee_due_id=due.id,
                amount=500,
                payment_method="cash",
                receipt_number="OUT-R1",
                idempotency_key="outbox-key-1",
            )
        )
        payment_id = result["payment"].id

        rows = await _outbox_rows(db_session, "PaymentReceivedEvent")
        assert len(rows) == 1
        row = rows[0]
        payload = row.payload or {}
        assert payload["payment_id"] == payment_id
        assert payload["amount"] == 500.0
        assert row.event_id == f"payment:{payment_id}"
        assert row.school_id == 7
        assert payload["fee_due_id"] == due.id

    async def test_duplicate_publish_collapses_to_one_row(
        self, db_session: AsyncSession
    ) -> None:
        """Re-publishing the same logical event collapses into one outbox row."""
        from app.domains.events.outbox import publish_durable
        from app.domains.notifications.events import PaymentReceivedEvent

        event = PaymentReceivedEvent(
            student_id=1, fee_due_id=2, payment_id=3,
            amount=100.0, payment_method="cash",
        )
        await publish_durable(event, session=db_session, event_id="payment:3")
        await publish_durable(event, session=db_session, event_id="payment:3")
        rows = await _outbox_rows(db_session, "PaymentReceivedEvent")
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Rollover producer
# ---------------------------------------------------------------------------


class TestRolloverProducer:
    async def test_rollover_completed_is_durable(self, db_session: AsyncSession) -> None:
        from app.domains.academic.models import AcademicYear
        from app.domains.academic.repository import (
            AcademicYearRepository,
            ClassRepository,
            SectionRepository,
            EnrollmentRepository,
        )
        from app.domains.reports.rollover_service import RolloverService
        from app.domains.student.repository import StudentRepository

        year = await AcademicYearRepository(db_session).create(
            AcademicYear(
                name="From Year", start_date=datetime.date(2025, 1, 1),
                end_date=datetime.date(2025, 12, 31), status="active",
            )
        )
        svc = RolloverService(session=db_session)
        result = await svc.execute_rollover(
            from_year_id=year.id,
            to_year_name="To Year",
            to_start_date="2026-01-01",
            to_end_date="2026-12-31",
        )
        rows = await _outbox_rows(db_session, "academic_year.rollover_completed")
        assert len(rows) == 1
        row = rows[0]
        assert row.event_id == f"rollover_completed:{year.id}:{result['academic_year_id']}"
        assert row.payload["new_year_id"] == result["academic_year_id"]


# ---------------------------------------------------------------------------
# Durable report export job
# ---------------------------------------------------------------------------


class TestExportJob:
    async def _definition_id(self, db_session: AsyncSession, code: str) -> int:
        from app.domains.report_builder.models import ReportDefinition

        row = (
            await db_session.execute(
                select(ReportDefinition).where(ReportDefinition.code == code)
            )
        ).scalar_one_or_none()
        if row is not None:
            return row.id
        # Seed definitions then re-query.
        import app.domains.report_builder.builders  # noqa: F401
        await ReportRegistry.ensure_definitions(db_session)
        row = (
            await db_session.execute(
                select(ReportDefinition).where(ReportDefinition.code == code)
            )
        ).scalar_one()
        return row.id

    async def test_create_job_enqueues_durable_job(self, db_session: AsyncSession) -> None:
        from app.domains.report_builder.schemas import ExportJobCreate

        definition_id = await self._definition_id(db_session, "student_directory")
        svc = ExportJobService(db_session)
        export_job = await svc.create_job(
            1,
            ExportJobCreate(report_definition_id=definition_id, format="csv", params={"academic_year_id": 2026}),
            campus_id=7,
        )

        job = (
            await db_session.execute(
                select(Job).where(Job.job_type == "report_builder.export")
            )
        ).scalar_one()
        assert job.params["export_job_id"] == export_job.id
        assert job.campus_id == 7
        assert job.user_id == 1
        assert job.identity_key == f"export:{export_job.id}"
        assert export_job.status == "pending"

    async def test_executing_job_completes_export(self, db_session: AsyncSession) -> None:
        """The worker path (JobService.execute_job) runs the export end-to-end."""
        from app.domains.jobs.loader import load_all_jobs
        from app.domains.report_builder.schemas import ExportJobCreate

        load_all_jobs()
        definition_id = await self._definition_id(db_session, "student_directory")
        svc = ExportJobService(db_session)
        export_job = await svc.create_job(
            1,
            ExportJobCreate(report_definition_id=definition_id, format="csv", params={"academic_year_id": 2026}),
            campus_id=7,
        )
        job = (
            await db_session.execute(
                select(Job).where(Job.identity_key == f"export:{export_job.id}")
            )
        ).scalar_one()
        job_id = job.id
        export_job_id = export_job.id

        # The worker claims the job (flips to running) then executes it.
        from app.domains.jobs.repository import JobRepository

        claimed = await JobRepository(db_session).acquire_next()
        assert claimed is not None and claimed.id == job_id

        job_service = JobService(db_session)
        await job_service.execute_job(claimed.id)

        completed = (
            await db_session.execute(
                select(Job).where(Job.id == job_id).execution_options(populate_existing=True)
            )
        ).scalar_one()
        assert completed.status == "completed"

        from app.domains.report_builder.models import ExportJob

        done = (
            await db_session.execute(
                select(ExportJob).where(ExportJob.id == export_job_id).execution_options(populate_existing=True)
            )
        ).scalar_one()
        assert done.status == "completed"
        assert done.result_data is not None
        assert done.total_rows == 0

    async def test_re_executing_completed_export_is_idempotent(
        self, db_session: AsyncSession
    ) -> None:
        from app.domains.jobs.loader import load_all_jobs
        from app.domains.jobs.repository import JobRepository
        from app.domains.report_builder.schemas import ExportJobCreate
        from app.domains.report_builder.service import process_export_job

        load_all_jobs()
        definition_id = await self._definition_id(db_session, "student_directory")
        svc = ExportJobService(db_session)
        export_job = await svc.create_job(
            1,
            ExportJobCreate(report_definition_id=definition_id, format="csv", params={"academic_year_id": 2026}),
            campus_id=7,
        )
        job = (
            await db_session.execute(
                select(Job).where(Job.identity_key == f"export:{export_job.id}")
            )
        ).scalar_one()
        job_id = job.id
        export_job_id = export_job.id

        claimed = await JobRepository(db_session).acquire_next()
        assert claimed is not None and claimed.id == job_id
        await JobService(db_session).execute_job(claimed.id)

        first = (
            await db_session.execute(
                select(Job).where(Job.id == job_id).execution_options(populate_existing=True)
            )
        ).scalar_one()
        assert first.status == "completed"

        # Simulate a crash-restart replay: process the same export again.
        # The consumer guard must short-circuit (skip) and not clobber the
        # completed result.
        outcome = await process_export_job(db_session, export_job_id)
        assert outcome["status"] == "completed"
        assert outcome["skipped"] is True


# ---------------------------------------------------------------------------
# Job tenant-context restoration
# ---------------------------------------------------------------------------


class TestJobTenantContext:
    async def test_execute_job_restores_tenant_context(
        self, db_session: AsyncSession
    ) -> None:
        from app.domains.events.context import get_correlation_id, get_school_id
        from app.domains.jobs.registry import BaseJob, register_job, clear_registry

        captured: dict = {}

        @register_job
        class ContextProbeJob(BaseJob):
            job_type = "test.context_probe"

            async def run(self, job, session):
                captured["school_id"] = get_school_id()
                captured["correlation_id"] = get_correlation_id()
                captured["job_campus"] = self.tenant.campus_id if self.tenant else None
                captured["job_user"] = self.tenant.user_id if self.tenant else None
                return {"ok": True}

        try:
            job = Job(
                job_type="test.context_probe",
                status="pending",
                params={},
                identity_key="probe-1",
                user_id=42,
                campus_id=99,
                created_at=NOW,
                updated_at=NOW,
                progress=0.0,
            )
            db_session.add(job)
            await db_session.flush()

            # The worker claims (flips to running) then executes the job.
            from app.domains.jobs.repository import JobRepository

            claimed = await JobRepository(db_session).acquire_next()
            assert claimed is not None and claimed.id == job.id
            await JobService(db_session).execute_job(claimed.id)

            assert captured["school_id"] == 99
            assert captured["job_campus"] == 99
            assert captured["job_user"] == 42
            assert captured["correlation_id"] == "probe-1"
        finally:
            clear_registry()
