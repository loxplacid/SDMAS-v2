from __future__ import annotations

import datetime
from typing import Any, Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.report_builder.base import BaseReportBuilder
from app.domains.report_builder.exporters import export_csv, export_excel, export_pdf
from app.domains.report_builder.models import ExportJob, ReportDefinition, SavedReport
from app.domains.report_builder.registry import ReportRegistry

REPORT_EXPORT_JOB_TYPE = "report_builder.export"


async def process_export_job(session: AsyncSession, export_job_id: int) -> dict[str, Any]:
    """Execute a single export idempotently.

    Used by the durable ``report_builder.export`` job worker.  Jobs that are
    already terminal (completed/failed) are left untouched so a retry after a
    crash never re-runs or clobbers a completed export.  Progress is committed
    incrementally so long-running exports survive worker restarts.
    """
    query = select(ExportJob).where(ExportJob.id == export_job_id)
    result = await session.execute(query)
    job = result.scalar_one_or_none()
    if not job:
        raise ValueError(f"Export job {export_job_id} not found")

    if job.status in ("completed", "failed"):
        return {"export_job_id": export_job_id, "status": job.status, "skipped": True}

    def_query = select(ReportDefinition).where(ReportDefinition.id == job.report_definition_id)
    def_result = await session.execute(def_query)
    definition = def_result.scalar_one_or_none()
    if not definition:
        job.status = "failed"
        job.error_message = "Report definition not found"
        await session.commit()
        return {"export_job_id": export_job_id, "status": "failed"}

    builder_cls = ReportRegistry.get(definition.code)
    if not builder_cls:
        job.status = "failed"
        job.error_message = f"Report builder not found for code: {definition.code}"
        await session.commit()
        return {"export_job_id": export_job_id, "status": "failed"}

    builder = builder_cls()
    params = job.params

    job.status = "processing"
    job.progress = 5
    await session.commit()

    data = await builder.fetch_data(params, job.user_id, job.campus_id, session)

    job.progress = 50
    await session.commit()

    rows = builder.build_rows(data)
    job.total_rows = len(rows)
    job.progress = 70
    await session.commit()

    meta = builder_cls.meta()
    filename = f"{meta.code}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if job.format == "csv":
        content = export_csv(meta.columns, rows)
        job.result_data = content
        job.result_filename = f"{filename}.csv"
    elif job.format == "excel":
        content = export_excel(meta.columns, rows, meta.name)
        job.result_data = content.hex()
        job.result_filename = f"{filename}.xlsx"
    elif job.format == "pdf":
        content = export_pdf(meta.columns, rows, meta.name)
        job.result_data = content.hex()
        job.result_filename = f"{filename}.pdf"

    job.status = "completed"
    job.progress = 100
    await session.commit()
    return {"export_job_id": export_job_id, "status": "completed", "rows": len(rows)}


class SavedReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: int, data: Any) -> SavedReport:
        report = SavedReport(user_id=user_id, **data.model_dump())
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def list(self, user_id: int, skip: int = 0, limit: int = 20) -> tuple[list[SavedReport], int]:
        query = (
            select(SavedReport)
            .where(SavedReport.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(SavedReport.updated_at.desc())
        )
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        count_query = select(func.count(SavedReport.id)).where(SavedReport.user_id == user_id)
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0
        return items, total

    async def get(self, report_id: int, user_id: int) -> SavedReport:
        query = select(SavedReport).where(SavedReport.id == report_id, SavedReport.user_id == user_id)
        result = await self.session.execute(query)
        report = result.scalar_one_or_none()
        if not report:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Saved report not found")
        return report

    async def update(self, report_id: int, user_id: int, data: Any) -> SavedReport:
        report = await self.get(report_id, user_id)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(report, key, value)
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def delete(self, report_id: int, user_id: int) -> None:
        report = await self.get(report_id, user_id)
        await self.session.delete(report)
        await self.session.commit()

    async def list_by_definition(self, definition_id: int, user_id: int) -> list[SavedReport]:
        query = (
            select(SavedReport)
            .where(
                SavedReport.report_definition_id == definition_id,
                SavedReport.user_id == user_id,
            )
            .order_by(SavedReport.updated_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


class ExportJobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_job(
        self, user_id: int, data: Any, campus_id: Optional[int] = None
    ) -> ExportJob:
        definition_id = data.report_definition_id
        def_query = select(ReportDefinition).where(ReportDefinition.id == definition_id)
        def_result = await self.session.execute(def_query)
        definition = def_result.scalar_one_or_none()
        if not definition:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Report definition not found")

        builder_cls = ReportRegistry.get(definition.code)
        if not builder_cls:
            from app.core.exceptions import NotFoundError
            raise NotFoundError(f"Report builder not found for code: {definition.code}")

        job = ExportJob(
            user_id=user_id,
            report_definition_id=definition_id,
            params=data.params,
            format=data.format,
            status="pending",
            campus_id=campus_id,
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24),
        )
        self.session.add(job)
        await self.session.flush()

        # Persist a durable job row so the standalone worker process (not an
        # in-process fire-and-forget task) performs the export.  Execution is
        # idempotent: process_export_job skips jobs already terminal.
        from app.domains.jobs.models import Job as QueuedJob

        now = datetime.datetime.now(datetime.timezone.utc)
        queued = QueuedJob(
            job_type=REPORT_EXPORT_JOB_TYPE,
            status="pending",
            params={"export_job_id": job.id, "format": job.format},
            priority=100,
            max_retries=3,
            identity_key=f"export:{job.id}",
            user_id=user_id,
            campus_id=campus_id,
            created_at=now,
            updated_at=now,
            progress=0.0,
        )
        self.session.add(queued)

        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_job(self, job_id: int, user_id: int) -> ExportJob:
        query = select(ExportJob).where(ExportJob.id == job_id, ExportJob.user_id == user_id)
        result = await self.session.execute(query)
        job = result.scalar_one_or_none()
        if not job:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Export job not found")
        return job

    async def list_jobs(
        self, user_id: int, skip: int = 0, limit: int = 20, status_filter: Optional[str] = None
    ) -> tuple[list[ExportJob], int]:
        conditions = [ExportJob.user_id == user_id]
        if status_filter:
            conditions.append(ExportJob.status == status_filter)

        query = (
            select(ExportJob)
            .where(*conditions)
            .offset(skip)
            .limit(limit)
            .order_by(ExportJob.created_at.desc())
        )
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        count_query = select(func.count(ExportJob.id)).where(*conditions)
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0
        return items, total

    async def get_result_data(self, job_id: int, user_id: int) -> tuple[Optional[str], Optional[str], str]:
        job = await self.get_job(job_id, user_id)
        if job.status != "completed":
            from app.core.exceptions import ValidationError
            raise ValidationError("Export job is not yet completed")
        return job.result_data, job.result_filename, job.format

    async def cleanup_expired(self) -> int:
        query = delete(ExportJob).where(
            ExportJob.expires_at < datetime.datetime.now(datetime.timezone.utc),
            ExportJob.status.in_(["completed", "failed"]),
        )
        result = await self.session.execute(query)
        await self.session.commit()
        return result.rowcount or 0


class ReportDefinitionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(self, skip: int = 0, limit: int = 20) -> tuple[list[ReportDefinition], int]:
        query = (
            select(ReportDefinition)
            .where(ReportDefinition.is_active == True)
            .offset(skip)
            .limit(limit)
            .order_by(ReportDefinition.category, ReportDefinition.name)
        )
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        count_query = select(func.count(ReportDefinition.id)).where(ReportDefinition.is_active == True)
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0
        return items, total

    async def get_by_code(self, code: str) -> Optional[ReportDefinition]:
        query = select(ReportDefinition).where(ReportDefinition.code == code)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_category(self, category: str) -> list[ReportDefinition]:
        query = (
            select(ReportDefinition)
            .where(ReportDefinition.category == category, ReportDefinition.is_active == True)
            .order_by(ReportDefinition.name)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
