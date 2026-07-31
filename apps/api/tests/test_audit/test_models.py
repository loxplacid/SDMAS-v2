"""Tests for the AuditLog ORM model."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.models import AuditLog
from app.infrastructure.database import Base


class TestAuditLogModel:
    """Verify that the AuditLog model has the correct schema."""

    async def test_table_exists(self, db_session: AsyncSession):
        """The audit_logs table should be creatable from metadata."""
        # The conftest creates all tables, so just verify the model is
        # registered in Base.metadata
        tables = Base.metadata.tables
        assert "audit_logs" in tables

    async def test_create_and_read(self, db_session: AsyncSession):
        entry = AuditLog(
            user_id=1,
            username="admin",
            action="CREATE",
            resource_type="student",
            resource_id="42",
            details='{"before": null, "after": {"name": "Test"}}',
            ip_address="10.0.0.1",
            user_agent="curl/7.88.1",
            campus_id=1,
        )
        db_session.add(entry)
        await db_session.flush()

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.id == entry.id)
        )
        found = result.scalar_one()

        assert found.user_id == 1
        assert found.username == "admin"
        assert found.action == "CREATE"
        assert found.resource_type == "student"
        assert found.resource_id == "42"
        assert found.ip_address == "10.0.0.1"
        assert found.user_agent == "curl/7.88.1"
        assert found.campus_id == 1
        assert found.created_at is not None

    async def test_nullable_fields_are_nullable(self, db_session: AsyncSession):
        """Most fields should accept None."""
        entry = AuditLog(
            action="DELETE",
            resource_type="fee",
        )
        db_session.add(entry)
        await db_session.flush()

        assert entry.user_id is None
        assert entry.username is None
        assert entry.details is None
        assert entry.ip_address is None
        assert entry.campus_id is None
