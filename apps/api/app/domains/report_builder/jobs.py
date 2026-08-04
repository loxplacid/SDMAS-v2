from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.jobs.models import Job
from app.domains.jobs.registry import BaseJob, register_job
from app.domains.report_builder.service import REPORT_EXPORT_JOB_TYPE, process_export_job

logger = logging.getLogger(__name__)


@register_job
class ReportExportJob(BaseJob):
    job_type = REPORT_EXPORT_JOB_TYPE

    async def run(self, job: Job, session: AsyncSession) -> dict[str, Any]:
        export_job_id = (job.params or {}).get("export_job_id")
        if not export_job_id:
            raise ValueError(f"{REPORT_EXPORT_JOB_TYPE} job missing export_job_id")

        logger.info("Executing export job %s", export_job_id)
        return await process_export_job(session, export_job_id)
