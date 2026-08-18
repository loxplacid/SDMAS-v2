"""End-to-end verification: a real migration import records lineage.

The hook ``_record_import_lineage`` in ``app/domains/migration/import_job.py``
runs after every successful import; this test proves the lineage tables are
actually populated by a real ``run_project_import`` call (no mocks).
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Register every model on Base.metadata before create_all (the migration
# import touches students/enrollments across domains).
import app.infrastructure.models as _all_models  # noqa: F401,E402
from app.domains.migration.import_job import run_project_import
from app.domains.migration.models import MigrationProject
from app.domains.migration.project_service import MigrationProjectService
from app.multi_tenant.models import TenantContext
from app.platform.lineage.models import (
    DataAsset,
    DataSource,
    EvidenceReference,
    LineageEdge,
    Transformation,
)

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
def storage_root(tmp_path, monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "storage_root", str(tmp_path / "storage"))
    os.makedirs(os.path.join(settings.storage_root, "migrations"), exist_ok=True)


async def test_real_import_populates_lineage(
    db_session: AsyncSession, tenant_a: TenantContext, storage_root: None
) -> None:
    svc = MigrationProjectService(db_session, tenant_a, user_id=99, username="admin")
    project: MigrationProject = await svc.create_project(
        name="Lineage hook import",
        source_system="Generic CSV",
        description="fixture",
        filename="students.csv",
        file_data=CSV_SAMPLE.encode("utf-8"),
        mime_type="text/csv",
    )
    await svc.run_validation(project.id)
    assert project.file_key is not None

    result = await run_project_import(db_session, tenant_a, project.id, job_id=None)
    assert result["imported"] == 3
    await db_session.commit()

    # Lineage nodes were recorded for the run.
    sources = (await db_session.execute(select(DataSource))).scalars().all()
    assert len(sources) == 1
    assert sources[0].source_type == "file"
    assert sources[0].external_ref == project.file_key

    transforms = (await db_session.execute(select(Transformation))).scalars().all()
    assert len(transforms) == 1
    assert transforms[0].transform_type == "import"

    assets = (await db_session.execute(select(DataAsset))).scalars().all()
    assert len(assets) >= 1
    assert any(a.ref and a.ref.startswith(f"migration_projects:{project.id}:") for a in assets)

    edges = (await db_session.execute(select(LineageEdge))).scalars().all()
    assert len(edges) >= 2  # source->transform and transform->asset(s)

    evidence = (await db_session.execute(select(EvidenceReference))).scalars().all()
    assert any(e.kind == "migration_run" for e in evidence)
