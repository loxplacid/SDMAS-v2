"""Regression tests for two production defects found during acceptance.

1. ``audit_logs.action`` was ``String(30)`` but the migration domain emits
   actions up to 34 chars (``MIGRATION_PROJECT_IMPORT_STARTED``,
   ``MIGRATION_PROJECT_IMPORT_COMPLETED``).  The INSERT raised
   ``StringDataRightTruncationError`` on PostgreSQL, which poisoned the
   request session and turned ``POST /migration/projects/{id}/import`` into
   a 500.  Fixed by widening the column to 64 (alembic 049) — these tests
   pin the ORM contract and the end-to-end behaviour.

2. The worker process imports only its narrow execution graph, so models
   referenced by cross-domain foreign keys (``notifications.campus_id`` →
   ``campuses``) could be missing from the worker's SQLAlchemy metadata,
   making outbox delivery fail with ``NoReferencedTableError``.  Fixed by
   importing ``app.infrastructure.models`` at worker startup — this test
   pins that registration.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.domains.audit.models import AuditLog
from app.domains.audit.service import AuditService
from app.multi_tenant.models import TenantContext

# The exact actions that previously exceeded String(30).
LONG_MIGRATION_ACTIONS = (
    "MIGRATION_PROJECT_IMPORT_STARTED",
    "MIGRATION_PROJECT_IMPORT_COMPLETED",
    "MIGRATION_PROJECT_MAPPING_SAVED",
)


@pytest.mark.asyncio
async def test_audit_action_column_is_at_least_64_chars(db_session) -> None:
    """The ORM column must accept every action the domains emit."""
    from sqlalchemy import Integer, String

    col = AuditLog.__table__.c.action
    assert isinstance(col.type, String)
    assert col.type.length >= 64


@pytest.mark.asyncio
async def test_long_migration_actions_persist_without_error(db_session) -> None:
    """Recording each long action must not raise (was StringDataRightTruncation)."""
    tenant = TenantContext(campus_id=1, institution_id=1, user_id=1)
    service = AuditService(db_session, tenant)
    for action in LONG_MIGRATION_ACTIONS:
        entry = await service.record(
            action=action,
            resource_type="migration_project",
            resource_id="1",
            user_id=1,
            username="apex.admin",
            details={"rows": 2},
        )
        assert entry.action == action

    await db_session.commit()

    rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action.in_(LONG_MIGRATION_ACTIONS))
        )
    ).scalars().all()
    assert len(rows) == len(LONG_MIGRATION_ACTIONS)


@pytest.mark.asyncio
async def test_worker_model_site_registers_cross_domain_fk_targets() -> None:
    """app.infrastructure.models must register campuses for notifications."""
    from app.infrastructure.database import Base
    from app.infrastructure import models as _models  # noqa: F401

    assert "campuses" in Base.metadata.tables
    assert "notifications" in Base.metadata.tables

    # The FK target must resolve: notifications.campus_id -> campuses.id.
    fk = next(
        fk
        for fk in Base.metadata.tables["notifications"].c.campus_id.foreign_keys
    )
    assert fk.column.table.name == "campuses"
